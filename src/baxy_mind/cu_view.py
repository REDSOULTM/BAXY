"""Reading a view of the window: its controls and written lines, a control found by its label, the geometry
(drawn, title bar, inside, rows), what has the keyboard, switches and closed menu entries, and the quoting of a
cited name.
"""

from __future__ import annotations

import re

from .semantic.cu_buscar import frame_button, scroll_part_name
from .semantic.missions import fold
from .semantic.cu_semejanza import acts_on_the_window
from .cu_vocabulary import _PLACE_TOGGLE, _WORD, _function_words


def _scroll_part(control: object, view: dict) -> bool:
    """A line or page button of a scroll bar: inside a ScrollBar's rectangle in the view, or so named when the view
    gives no rectangles. Scrolling is the scroll act; such a button is never a goal's place (measured on v3-40: «split
    the pane vertical» pressed «Aumento grande vertical»)."""

    if not isinstance(control, dict) or control.get("kind") != "Button":
        return False
    if scroll_part_name(control.get("name")):
        return True
    controls = view.get("controls") if isinstance(view, dict) else None
    bars = [
        item.get("rect") for item in (controls if isinstance(controls, list) else [])
        if isinstance(item, dict) and item.get("kind") == "ScrollBar" and isinstance(item.get("rect"), dict)
    ]
    return any(_inside(control.get("rect"), bar) for bar in bars)


def _view_strings(view: dict) -> list[str]:
    found: list[str] = []
    window = view.get("window") if isinstance(view, dict) else None
    if isinstance(window, dict):
        found.append(str(window.get("title") or ""))
    controls = view.get("controls") if isinstance(view, dict) else None
    if isinstance(controls, list):
        for control in controls:
            if isinstance(control, dict):
                found.append(str(control.get("name") or ""))
                if control.get("value"):
                    found.append(str(control.get("value")))
    text = view.get("text") if isinstance(view, dict) else None
    if isinstance(text, dict):
        for zone_lines in text.values():
            if isinstance(zone_lines, list):
                found.extend(str(line) for line in zone_lines)
    return found


def citation_pieces(citation: str) -> list[str]:
    """Ronda 20 P6: the pieces of a citation split by the « | » ``compact_view_text`` joins a zone's lines with, each
    trimmed; the citation itself when it holds no such separator. Twin of ComputerUseSuccessCheck.CitationPieces."""

    return [piece.strip() for piece in str(citation or "").split("|") if piece.strip()]


def _view_holds(view: dict, needle: str) -> bool:
    folded = fold(needle)
    if not folded:
        return False
    joined = " ".join(fold(item) for item in _view_strings(view))
    return folded in joined


def view_contains(view: dict, needle: str) -> bool:
    """Whether the view shows ``needle``. Ronda 20 P6 (v3-16: the done «paisaJe.Jpg | Restablecer | 9» cited a whole
    «texto TL» line of the listing and was refused): a citation of several of the view's lines joined by « | » is shown
    when each of its pieces is; one piece the view lacks and it is not. Twin of ComputerUseSuccessCheck.ViewContains."""

    if _view_holds(view, needle):
        return True
    pieces = citation_pieces(needle)
    return len(pieces) > 1 and all(_view_holds(view, piece) for piece in pieces)


def _edit_distance(left: str, right: str, cap: int) -> int:
    if abs(len(left) - len(right)) > cap:
        return cap + 1
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, 1):
        current = [row]
        for column, right_char in enumerate(right, 1):
            current.append(min(previous[column] + 1, current[column - 1] + 1, previous[column - 1] + (left_char != right_char)))
        if min(current) > cap:
            return cap + 1
        previous = current
    return previous[-1]


def label_names(label: str, name: str) -> bool:
    """Requested label against a seen name: folded equality, containment, or a typo per five letters."""

    needle, haystack = fold(label), fold(name)
    if not needle or not haystack:
        return False
    if needle == haystack or needle in haystack:
        return True
    allowed = len(needle) // 5
    return allowed > 0 and _edit_distance(needle, haystack, allowed) <= allowed


_DESCRIPTIVE_KINDS = frozenset({"Text", "Group", "Pane", "Custom", "Document"})

# Ronda 20 P6 (v3-15: «Parecidos al objetivo: [7] Ocupado» led to pressing a busy indicator): the UI Automation control
# types that only show a state, never something to press.
_STATUS_KINDS = frozenset({"ProgressBar", "StatusBar"})


def _short_name(name: str, label: str) -> bool:
    """A control's name short enough to be what it names: at most six words beyond the label's own."""

    return len(fold(name).split()) <= len(fold(label).split()) + 6


def _disabled_controls(view: dict) -> list[dict]:
    """The actionables the window shows disabled (the shell's ``disabled``, apart from the controls and without index):
    they exist and wait for another step first; nothing presses them."""

    listed = view.get("disabled") if isinstance(view, dict) else None
    return [control for control in listed if isinstance(control, dict) and control.get("name")] if isinstance(listed, list) else []


# Ronda 23 (v3-23): the items whose own cell repeats their name (a row of a data grid, a list item, a tree node).
_ROW_KINDS = frozenset({"ListItem", "DataItem", "TreeItem"})


def _row_cell(control: object, listed: list) -> bool:
    """Ronda 23 (v3-23: the DataItem «Sistema» and its Text cell «Sistema» counted as two places, so the content row
    was no single control and the current node never opened): a control that only shows words (``_DESCRIPTIVE_KINDS``)
    drawn inside an item of a row kind (``_ROW_KINDS``) of the same name is that item's cell, not a second control.
    Two items of the same name, neither inside the other, stay two."""

    if not isinstance(control, dict) or str(control.get("kind")) not in _DESCRIPTIVE_KINDS:
        return False
    name = fold(control.get("name")).strip()
    return bool(name) and any(
        isinstance(row, dict) and row is not control and str(row.get("kind")) in _ROW_KINDS
        and fold(row.get("name")).strip() == name and _inside(control.get("rect"), row.get("rect"))
        for row in listed
    )


def _without_row_cells(listed: list) -> list:
    """The listed controls without the cells of their own rows (``_row_cell``)."""

    return [control for control in listed if not _row_cell(control, listed)]


def find_control(
    view: dict, label: str, index: int | None = None, kind: str | None = None, *, placing: bool = False,
) -> dict | None:
    """The one control the label (and index, when given; of that kind, when given) names; None when absent or
    ambiguous. Going to a place (``placing``), containment never makes another place the one (``_not_the_place``): a
    list, tree, grid or table («Search results» for «search»), nor a name that adds words of its own («Pantalla de
    bloqueo» for «pantalla»); only its exact name does."""

    listed = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(listed, list):
        return None
    if isinstance(index, int) and 0 <= index < len(listed):
        candidate = listed[index]
        if (
            isinstance(candidate, dict)
            and (kind is None or candidate.get("kind") == kind)
            and label_names(label, str(candidate.get("name") or ""))
        ):
            return candidate
    controls = [
        control for control in _without_row_cells(listed)
        if isinstance(control, dict) and (kind is None or control.get("kind") == kind)
    ]
    exact = [control for control in controls if fold(control.get("name")) == fold(label)]
    if len(exact) == 1:
        return exact[0]
    # A sentence that merely mentions the name is no place (measured on Settings: «Usa un servidor proxy para conexiones
    # Ethernet o Wi-Fi…» was clicked for «Wi-Fi» on a PC without one): containment counts in short names only.
    loose = [
        control for control in controls
        if label_names(label, str(control.get("name") or ""))
        and (str(control.get("kind")) not in _DESCRIPTIVE_KINDS or _short_name(str(control.get("name") or ""), label))
        and not (placing and _not_the_place(label, control, view))
    ]
    if len(loose) == 1:
        return loose[0]
    if len(loose) > 1:
        # «Biblioteca» as a navigation item and as a heading: the actionable one wins when unique.
        actionable = [control for control in loose if str(control.get("kind")) in effect_intent_actionable_kinds()]
        if len(actionable) == 1:
            return actionable[0]
    return None


def _not_the_place(label: str, control: dict, view: object) -> bool:
    """Going to the place ``label`` names, a control that holds the name but is not that place. Ronda 24b (banco r23
    u9: the grid «Search results» was pressed for «go to Search» and chose a suggestion): a list, tree, grid or table.
    Estabilización G2 (``names_another_place``): a name that adds words of its own."""

    return str(control.get("kind")) in _LIST_KINDS or names_another_place(label, str(control.get("name") or ""), view)


# What joins several places in one name («Bluetooth y dispositivos», «Bluetooth & devices», «Hora e idioma», a title's
# « - YouTube»): each part is a place of its own.
_PLACE_JOINS = re.compile(r"\s*(?:[,&/|·:]|\s-\s|\b(?:y|e|and)\b)\s*")


def names_another_place(label: str, name: str, view: object = None, *, written: bool = False) -> bool:
    """Estabilización G2 (tandas f2 del notebook, t2-c03 «abre configuracion que quiero ver lo de la pantalla»: the rule
    pressed the recommendation «Pantalla de bloqueo» for «ir a pantalla» by containment, and the mission wandered in
    Personalización): ``name`` holds ``label`` as whole words and adds words of its own that make it another place
    («Pantalla de bloqueo» is no «pantalla», «Lock screen» no «screen»). A name that joins the place to others
    («Bluetooth y dispositivos»), or adds only function words («Tu biblioteca»), a verb that leads there («Ver centro de
    movilidad»), numbers, or the window's own title («Configuración de pantalla» in «Configuración») is still the
    place; equal names, and a name that holds the label only with a typo or glued to other letters, are judged as
    before. A ``written`` line (the reading of a window's text) joins neighbouring labels with a space (measured on
    Steam: «BIBLIOTECA COMUNIDAD», the URL «store.steampowered.com»): its words are one name only when a function word
    links them («Pantalla de bloqueo», «Buscar en la tienda»)."""

    wanted, folded = " ".join(fold(label).split()), " ".join(fold(name).split())
    if not wanted or wanted == folded:
        return False
    parts = [" ".join(part.split()) for part in _PLACE_JOINS.split(folded)]
    whole = re.compile(rf"(?<!\w){re.escape(wanted)}(?!\w)")
    member = None if wanted in parts else next((part for part in parts if whole.search(part)), None)
    if member is None:
        return False
    # A verb that opens the place or leads to it is no word of another place (data «computerUse.placeToggle»: «Ver
    # centro de movilidad» on the Control Panel, «Abre Tu biblioteca»).
    lead = next((verb for verb in (*_PLACE_TOGGLE["opening"], *_PLACE_TOGGLE["leadsTo"]) if member.startswith(verb)), "")
    member = member[len(lead):]
    window = view.get("window") if isinstance(view, dict) else None
    title = fold(window.get("title")) if isinstance(window, dict) else ""
    function = _function_words()
    added = _WORD.findall(whole.sub(" ", member, count=1))
    if written and not any(word in function for word in added):
        return False
    common = set(_WORD.findall(title)) | function
    return any(len(word) > 2 and not word.isdigit() and word not in common for word in added)


_KIND_WORDS: dict[str, str] = {
    "pestana": "TabItem", "tab": "TabItem", "solapa": "TabItem", "boton": "Button", "button": "Button",
    "enlace": "Hyperlink", "link": "Hyperlink", "casilla": "CheckBox", "checkbox": "CheckBox",
}


def effect_intent_actionable_kinds() -> frozenset[str]:
    return frozenset({
        "Button", "MenuItem", "ListItem", "TabItem", "Hyperlink", "CheckBox", "RadioButton",
        "Edit", "ComboBox", "TreeItem", "SplitButton", "Slider", "Document",
    })


def _text_line_with(view: dict, label: str, *, placing: bool = False) -> str | None:
    """Ronda 25 (n5): the line that holds the label as whole words in a short line, never a sentence that mentions it;
    else the only line (the OCR reads twice: the same line twice is one) with one misread letter per five. Going to a
    place (``placing``), never a line that names another place (``names_another_place``: «Pantalla de bloqueo»)."""
    lines = _view_lines(view)
    hits = [
        line for line in lines if _whole_words_name(label, line) and _short_name(line, label)
        and not (placing and names_another_place(label, line, view, written=True))
    ]
    near = {" ".join(fold(line).split()): line for line in lines if _one_typo(line, label)}
    return hits[0] if hits else next(iter(near.values())) if len(near) == 1 else None


def _one_typo(text: str, name: str) -> bool:
    """``text`` is ``name`` with one misread letter per five, never the same text."""
    wanted, seen = " ".join(fold(name).split()), " ".join(fold(text).split())
    allowed = len(wanted) // 5
    return allowed > 0 and wanted != seen and _edit_distance(wanted, seen, allowed) <= allowed


# A name the view cut short («8 procesadores prin...»): its cut is no part of it.
_CUT_SHORT = re.compile(r"\s*(?:\.\.\.|…)$")


def _shown_whole(view: dict, name: str) -> bool:
    """Review of lectura-ruta (finding 4): the view shows ``name`` itself, not a word of it inside a phrase: a control or
    a line of text named exactly so (folded, without the view's «...» cut), or a line that starts with it and goes on
    after a separator («AMD Ryzen 7 5800H with Radeon Graphics» in «AMD Ryzen 7 5800H with Radeon Graphics, 3201 Mhz,
    …»). «Wi-Fi» inside «Usa un servidor proxy para conexiones Ethernet o Wi-Fi», or «Red» in «Red e Internet», is not
    the item «Wi-Fi» or «Red» of a list further down."""

    wanted = _CUT_SHORT.sub("", fold(name)).strip()
    if not wanted:
        return False
    controls = view.get("controls") if isinstance(view, dict) else None
    seen = [str(control.get("name") or "") for control in controls or () if isinstance(control, dict)]
    for shown in (*seen, *_view_lines(view)):
        folded = _CUT_SHORT.sub("", fold(shown)).strip()
        rest = folded[len(wanted):] if folded.startswith(wanted) else None
        if rest is not None and (not rest or rest[0] in ",;:" or rest.lstrip().startswith("(")):
            return True
    return False


def _focused(view: dict) -> dict | None:
    window = view.get("window") if isinstance(view, dict) else None
    focused = window.get("focused") if isinstance(window, dict) else None
    return focused if isinstance(focused, dict) else None


def _focused_is_password(view: dict) -> bool:
    controls = view.get("controls") if isinstance(view, dict) else None
    if isinstance(controls, list):
        for control in controls:
            if isinstance(control, dict) and "focused" in str(control.get("state") or "") and "password" in str(control.get("state") or ""):
                return True
    return False


def _drawn(view: dict, control: dict) -> bool:
    """The control is drawn on screen: it has a rectangle of some area, or the view gives rectangles to none (a view
    without geometry cannot tell). The window's system menu is listed with no rectangle (measured on Seguridad de
    Windows, Reproductor multimedia, Terminal)."""

    if _area(control.get("rect")) > 0:
        return True
    controls = view.get("controls") if isinstance(view, dict) else None
    return not any(isinstance(item, dict) and _area(item.get("rect")) > 0 for item in (controls or []))


def _in_title_bar(view: dict, control: dict) -> bool:
    """The control lies in the window's title bar: the band its frame buttons (minimize, maximize, close) are drawn
    in, when the view shows them with rectangles. The account button, the quick access toolbar and the window's own
    menus live there (measured on Word and PowerPoint: «Minimizar» and the account at y=1…61)."""

    rect = control.get("rect")
    if _area(rect) <= 0:
        return False
    band = _title_band(view, control)
    if band is None:
        return False
    top, bottom = band
    middle = float(rect["y"]) + float(rect["h"]) / 2  # type: ignore[index]
    return top <= middle <= bottom


def _title_band(view: dict, control: object = None) -> tuple[float, float] | None:
    """The band (top, bottom) the window's frame buttons are drawn in, when the view shows them with rectangles; None
    otherwise. Revisión 2 de ronda 24 (v3-07): the frame buttons are one row, the topmost: a button lower in the window
    whose name starts with a frame verb («Minimizar el panel de carpetas» at y=173) is a pane's, and never stretches
    the band over the ribbon's tabs."""

    controls = view.get("controls") if isinstance(view, dict) else None
    band = [
        item["rect"] for item in (controls if isinstance(controls, list) else [])
        if isinstance(item, dict) and item is not control
        and (frame_button(fold(item.get("name"))) or acts_on_the_window(item.get("name")))
        and _area(item.get("rect")) > 0 and float(item["rect"].get("h") or 0) <= _ONE_LINE_HEIGHT
    ]
    if not band:
        return None
    first = min(band, key=lambda item: float(item["y"]))
    row = [item for item in band if float(item["y"]) < float(first["y"]) + float(first["h"])]
    return min(float(item["y"]) for item in row), max(float(item["y"]) + float(item["h"]) for item in row)


def _view_words(view: dict) -> str:
    """The listed controls' names and the view's lines, folded, one per line."""

    controls = view.get("controls")
    named = [str(control.get("name") or "") for control in controls if isinstance(control, dict)] if isinstance(controls, list) else []
    appeared = view.get("newText")
    lines = [str(line) for line in appeared] if isinstance(appeared, list) else []
    return "\n".join(fold(text) for text in (*named, *lines, *_view_lines(view)))


def _shown_as_words(name: str, shown: str) -> bool:
    return bool(name) and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", shown) is not None


_CONTENT_KINDS = {"ListItem", "DataItem"}


def is_content_item(control: dict, view: dict | None = None) -> bool:
    """A ListItem or DataItem of a content view (files, pictures, results), where one click selects and does not
    open: out of the window's left column (zones L, TL, BL), where navigation lists sit; or in it, when another item
    of the view sits in the same row out of that column (a grid of tiles that starts at the left edge). Same row:
    vertical centres within half the item's height (the App's ``IsContentItem`` reads it the same way)."""

    zone = str(control.get("zone") or "")
    if str(control.get("kind")) not in _CONTENT_KINDS or not zone:
        return False
    if not zone.endswith("L"):
        return True
    controls = view.get("controls") if isinstance(view, dict) else None
    centre, height = _vertical_centre(control.get("rect"))
    if centre is None or not isinstance(controls, list):
        return False
    for other in controls:
        if other is control or not isinstance(other, dict) or str(other.get("kind")) not in _CONTENT_KINDS:
            continue
        other_zone = str(other.get("zone") or "")
        other_centre, _ = _vertical_centre(other.get("rect"))
        if (
            other_zone and not other_zone.endswith("L") and other_centre is not None
            and abs(other_centre - centre) <= height / 2 and _same_size(control.get("rect"), other.get("rect"))
        ):
            return True
    return False


def _same_size(rect: object, other: object) -> bool:
    """A tile of the same grid has the item's size; a card of the page beside a navigation list does not."""

    try:
        width, height = float(rect["w"]), float(rect["h"])  # type: ignore[index]
        other_width, other_height = float(other["w"]), float(other["h"])  # type: ignore[index]
    except (KeyError, TypeError, ValueError):
        return False
    return width > 0 and height > 0 and abs(other_width - width) <= width * 0.25 and abs(other_height - height) <= height * 0.25


def _vertical_centre(rect: object) -> tuple[float | None, float]:
    try:
        top, height = float(rect["y"]), float(rect["h"])  # type: ignore[index]
    except (KeyError, TypeError, ValueError):
        return None, 0.0
    return (top + height / 2, height) if height > 0 else (None, 0.0)


# A one-line field is at most this tall (physical pixels at 200 %) and this share of the window's area.
_ONE_LINE_HEIGHT = 80

_FIELD_KINDS = frozenset({"Edit", "ComboBox"})

_LIST_KINDS = frozenset({"List", "Tree", "DataGrid", "Table"})
_ITEM_KINDS = frozenset({"ListItem", "TreeItem", "DataItem"})


def _same_row(one: dict, other: dict) -> bool:
    """Two controls drawn side by side: their vertical middles within half the shorter one's height, and neither twice
    as tall as the other."""

    a, b = one["rect"], other["rect"]
    ha, hb = float(a["h"]), float(b["h"])
    if min(ha, hb) <= 0 or max(ha, hb) > 2 * min(ha, hb):
        return False
    return abs((float(a["y"]) + ha / 2) - (float(b["y"]) + hb / 2)) <= min(ha, hb) / 2


def _same_control(control: dict, other: dict) -> bool:
    """Two entries of a view are the same control: the same index when both carry one, else the same kind and name."""

    if isinstance(control.get("i"), int) and isinstance(other.get("i"), int):
        return control.get("i") == other.get("i")
    return control.get("kind") == other.get("kind") and fold(control.get("name")).strip() == fold(other.get("name")).strip()


def _area(rect: object) -> float:
    try:
        return max(float(rect["w"]), 0.0) * max(float(rect["h"]), 0.0)  # type: ignore[index]
    except (KeyError, TypeError, ValueError):
        return 0.0


# The button that opens a window's navigation or menu, by its whole name in either language: «Abrir navegación»,
# «Open Navigation», «Menú», «Más opciones», «More options», «Main menu», a hamburger. Its opposite («Cerrar
# navegación»), a group of buttons, a resize handle or a «Más» that is an operator are not.
_NAVIGATION_OPENER = re.compile(
    r"^(?:(?:abrir|abre|open|mostrar|muestra|show|expandir|expand|alternar|toggle)\s+(?:(?:el|la|the)\s+)?)?"
    r"(?:(?:panel|barra|pane|menu)\s+(?:de\s+)?)?"
    r"(?:navegacion|navigation|nav|menu|menu\s+principal|main\s+menu|hamburguesa|hamburger|"
    r"mas\s+opciones|more\s+options|mas\s+acciones|more\s+actions|more)"
    r"(?:\s+(?:menu|button|boton|pane|panel|principal|de\s+navegacion))?$"
)
# A bare «Menú» or «More» (a list's «more», a card's menu) says nothing of navigation: it opens the window's
# navigation only with a verb («Abrir menú») or the navigation's own words («Menú de navegación», «Hamburger menu»).
_BARE_OPENER = re.compile(
    r"^(?:(?:panel|barra|pane|menu)\s+(?:de\s+)?)?(?:menu|more)(?:\s+(?:menu|button|boton|pane|panel))?$"
)


def _opener_name(name: object) -> bool:
    folded = fold(name).strip()
    return _NAVIGATION_OPENER.match(folded) is not None and _BARE_OPENER.match(folded) is None


def _whole_words_name(name: str, text: str) -> bool:
    """``text`` carries the name ``name`` as whole words («red» in «Red e Internet», never in «Shared»)."""

    needle = fold(name).strip()
    return bool(needle) and re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", fold(text)) is not None


def _view_lines(view: dict) -> list[str]:
    text = view.get("text") if isinstance(view, dict) else None
    if not isinstance(text, dict):
        return []
    return [str(line) for zone_lines in text.values() if isinstance(zone_lines, list) for line in zone_lines]


def _inside(inner: object, outer: object) -> bool:
    if not isinstance(inner, dict) or not isinstance(outer, dict):
        return False
    try:
        x, y = float(inner["x"]) + float(inner["w"]) / 2, float(inner["y"]) + float(inner["h"]) / 2
        return float(outer["x"]) <= x <= float(outer["x"]) + float(outer["w"]) and float(outer["y"]) <= y <= float(outer["y"]) + float(outer["h"])
    except (KeyError, TypeError, ValueError):
        return False


# Ronda 24 (t-menu-2): which holder of items is the window's content, for its empty space. The content surface (body)
# first, then a list, a grid or a table, then a tree or a pane; within one rank the most items, the first on a tie.
_CONTENT_HOLDER_RANK = {"List": 1, "DataGrid": 1, "Table": 1, "Tree": 0, "Pane": 0}


def _list_holding_items(view: dict, empty_space: bool = False) -> int | None:
    """The index of the list (or pane) holding the most items of the view, by their rectangles; the first list when
    the view carries no rectangles; None when there is no list. That holder is the one the wheel turns and the one a
    trimmed view keeps: a registry editor's tree of keys beside a list of one value scrolls the tree.

    Ronda 24 (t-menu-2), only with ``empty_space`` (the container whose empty space opens the list's menu): the content
    surface (body) when it holds items, else a List, DataGrid or Table that holds any even when a Tree holds more (a
    folder's files beside its navigation tree); a Tree, or a Pane holding three or more, only when no list holds any.
    Review 1 of ronda 24 (finding 2): that rank never moves the wheel's or the trim's holder."""

    controls = [control for control in (view.get("controls") or []) if isinstance(control, dict)]
    items = [control for control in controls if control.get("kind") in _ITEM_KINDS]
    best: tuple[int, int, int] | None = None
    first_list: int | None = None
    for control in controls:
        if not isinstance(control.get("i"), int):
            continue
        kind = control.get("kind")
        body = empty_space and control.get("body") is True
        if kind in _LIST_KINDS and first_list is None:
            first_list = control["i"]
        if kind not in _LIST_KINDS and kind != "Pane" and not body:
            continue
        held = sum(1 for item in items if _inside(item.get("rect"), control.get("rect")))
        if not held or not (kind in _LIST_KINDS or body or held >= 3):
            continue
        rank = (2 if body else _CONTENT_HOLDER_RANK.get(str(kind), 0)) if empty_space else 0
        if best is None or (rank, held) > (best[0], best[1]):
            best = (rank, held, control["i"])
    return best[2] if best is not None else first_list


_SWITCH_KINDS = frozenset({"CheckBox", "RadioButton", "ToggleButton", "Slider"})


def _is_switch(control: dict) -> bool:
    """A control that sets something when pressed: a check box, a radio button, a toggle or a slider, or any control
    shown on/off/checked or checkable."""

    state = str(control.get("state") or "").split()
    # A button named as the act of switching («Alternar grados», «Toggle units») switches even without a state
    # (measured on the Calculator: going to «Científica» the model pressed «Alternar grados» and DEG became RAD).
    name = fold(control.get("name"))
    # «Alternar navegación» / «Toggle navigation» opens a menu: it shows places, it sets nothing.
    toggles = re.match(r"(?:alternar|cambiar entre|toggle|switch between)\b", name) is not None and re.search(
        r"\b(?:navegacion|navigation|menu|panel|pane|barra lateral|sidebar)\b", name
    ) is None
    # Revision 2 of ronda 20b (B2): a classic menu entry whose static read shows a check mark or a radio check is
    # «checkable» (it toggles a setting), a neutral fact that never claims its state now.
    return control.get("kind") in _SWITCH_KINDS or toggles or any(
        word in {"on", "off", "checked", "unchecked", "checkable"} for word in state
    )


def closed_menu_entry(control: object) -> bool:
    """An entry of a window's classic menu read without opening it (the App's ``nameSource`` «menu», identity
    «hmenu.<id>»): listed so it can be pressed by its command, never drawn on screen (revision 3 of ronda 20b, B-A).
    Twin of ComputerUseSuccessCheck.ClosedMenuEntry."""

    return isinstance(control, dict) and (
        control.get("nameSource") == "menu" or str(control.get("id") or "").startswith("hmenu.")
    )


def _state_unknown_switch(control: object) -> bool:
    """A closed menu entry that toggles a setting (``checkable``) with no state of now: pressed for «activar» or
    «desactivar» it would flip the setting whichever way it is (revision 3 of ronda 20b, B-B)."""

    states = set(str(control.get("state") or "").split()) if isinstance(control, dict) else set()
    return closed_menu_entry(control) and "checkable" in states and not states & {"on", "off", "checked", "unchecked"}


def _without_state_unknown_switches(view: dict) -> dict:
    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return view
    return {**view, "controls": [control for control in controls if not _state_unknown_switch(control)]}


# The states that show a control chosen (an item selected, a switch or a toggle button on), and the kinds that only
# show or take text, never an option chosen.
_CHOSEN_STATES = frozenset({"selected", "on"})
_NEVER_CHOSEN_KINDS = frozenset({"Text", "Edit", "Document", "Pane", "Window", "TitleBar", "Group", "ComboBox"})


def _chosen(control: object) -> bool:
    return (
        isinstance(control, dict) and str(control.get("kind") or "") not in _NEVER_CHOSEN_KINDS
        and bool(_CHOSEN_STATES & set(str(control.get("state") or "").split()))
    )


# The quotes a citation or a name may come wrapped in, opener to closer.
_QUOTE_PAIRS = {"«": "»", '"': '"', "'": "'", "“": "”", "‘": "’"}
_QUOTE_OPENERS = {closer: opener for opener, closer in _QUOTE_PAIRS.items()}


def _bare(text: object) -> str:
    """Ronda 24 (pasada r23, v3-53): the folded text without the quotes that wrap it, a balanced pair or a lone mark with
    no partner inside, never a mark that is part of the name: «Silenciar 'Audio del escritorio'» keeps its closing
    quote, so the citation and the control's name meet. Both sides of every comparison by name go through it. Twin of
    ComputerUseSuccessCheck.Bare."""

    bare = fold(text).strip()
    while bare:
        head, tail = bare[0], bare[-1]
        if len(bare) >= 2 and _QUOTE_PAIRS.get(head) == tail:
            bare = bare[1:-1].strip()
        elif head in _QUOTE_PAIRS and _QUOTE_PAIRS[head] not in bare[1:]:
            bare = bare[1:].strip()
        elif tail in _QUOTE_OPENERS and _QUOTE_OPENERS[tail] not in bare[:-1]:
            bare = bare[:-1].strip()
        else:
            break
    return bare


# The kinds whose arrow or list ``open`` reaches by kind alone (the worker opens them by ExpandCollapse).
_ARROW_KINDS = frozenset({"SplitButton", "ComboBox"})


def _has_arrow(control: dict | None) -> bool:
    """The control has an arrow or a list to open apart from its action: a split button, a drop-down, or a control the
    view marks collapsed (its ExpandCollapse). One already expanded has its list on screen."""

    if not isinstance(control, dict) or not isinstance(control.get("i"), int) or isinstance(control.get("i"), bool):
        return False
    states = set(str(control.get("state") or "").split())
    if "expanded" in states:
        return False
    return "collapsed" in states or str(control.get("kind") or "") in _ARROW_KINDS


def _viewed_control(view: dict, index: object) -> dict | None:
    """The control the view handed out at this index (its own ``i``), or None."""

    if not isinstance(index, int) or isinstance(index, bool):
        return None
    controls = view.get("controls") if isinstance(view, dict) else None
    return next(
        (control for control in controls or [] if isinstance(control, dict) and control.get("i") == index), None
    )
