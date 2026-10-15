"""Looking up a destination that is not on screen: the window's search box or button, its shortcut, a search
burst, the result that names the target, the navigation button, the place's own button, the wheel, and the
blind lookups left to the model while the encoder is down.
"""

from __future__ import annotations

import re
from typing import Callable, Iterable

from .semantic.cu_buscar import browser_or_computer_place, frame_button, quick_switcher_name
from .semantic.missions import fold, label_alternatives, view_option_named
from .semantic.cu_semejanza import acts_on_the_window, names_a_search
from .cu_vocabulary import CONTENT_KEEPING_KEYS, _PLACE_TOGGLE, _evidence_rules, _named_by_list
from .cu_view import (
    _DESCRIPTIVE_KINDS, _FIELD_KINDS, _ITEM_KINDS, _area, _focused, _in_title_bar, _is_switch, _list_holding_items,
    _one_typo, _opener_name, _short_name, _view_lines, _whole_words_name, find_control, label_names,
)
from .cu_goals import _POSSESSIVE
from .cu_fields import (
    _ADDRESS_NAME, _COMPOSER_NAME, _EDITABLE_KINDS, _SEARCH_KEYS, _SEARCH_NAME, _example_text, _focused_controls,
    _focused_field, _is_search_field, _looked_behind, _message_window, _own_name, _search_document, key_arguments,
)
from .cu_acts import _REASON_FIND, _click, _key, _none, _type, typed_text

# Encargo IMP2: the App's twin is ComputerUseMission.SearchPending.
SEARCH_PENDING = "search_pending"
from .cu_window import _inside_the_page, _of_the_page, _web_browser
from .cu_history import (
    _appeared, _may_have_acted, _search_started, _spent_keys, _steps_ok, _typed_target, key_without_effect,
)
from .cu_unasked import opens_help
from .cu_languages import _TRANSLATED_ITEM_KINDS, _name_to_look_up, _said_in_other_language, _translation_clickable
from .cu_meaning import ENCODER_COLD, SemanticMatcher
from .cu_options import _view_option_shown
from .cu_navigation import _names_a_switch
from .cu_menus import _menus_to_open


def _searches_content(step: object) -> bool:
    """The step looks a name up in the window's search of its content: a text typed, a search shortcut, a click on a
    search field."""

    if not isinstance(step, dict):
        return False
    arguments = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
    operation = step.get("operation")
    return (
        operation == "input.text.type"
        or (operation == "input.key.press" and arguments.get("key") in _SEARCH_KEYS)
        or (operation == "input.visible.click" and (
            _is_search_field({"name": arguments.get("label")}) or bool(str(arguments.get("search") or "").strip())
        ))
    )


REASON_BY_NAME = "el objetivo lo nombra y la vista no lo lista: lo busco por su nombre en toda la ventana"

_SEARCH_KINDS = ("Edit", "Document", "ComboBox", "Button", "ListItem")

_SENTENCE_END = re.compile(r"[.!?]\s")

# What a search shows its results as, best first; the field itself is never a result.
_RESULT_KINDS = ("ListItem", "TreeItem", "Button", "Hyperlink", "DataItem", "MenuItem", "TabItem")

# Ronda 25: what may name a search's result by holding the name among other words (an entry of a list, a link, a menu).
_ENTRY_KINDS = _ITEM_KINDS | {"Hyperlink", "MenuItem"}

_SCROLLS = 3

_REASON_UNSOUGHT = "el atajo abrió algo que no busqué y Escape no lo cerró: lo cancelo"
# Where a key leaves the keyboard when it brought nothing up: the window's own frame (its system menu bar, its title).
_FRAME_FOCUS_KINDS = frozenset({"MenuBar", "TitleBar"})
# A dialog's own way out that leaves everything as it was; never «Cerrar»/«Close», which may be the window's.
_CANCEL_NAMES = frozenset({"cancelar", "cancel"})


def _escape_left_it_open(view: dict, history: list[dict]) -> dict | None:
    """The Cancel the routine presses after its own Escape left what its search key brought up on screen (t-menu-3):
    the last two steps are a search key that changed the view (never ``sameView``) and the Escape the routine pressed
    right after it (``rule``), whose look kept the view as it was; the view's one Cancel button appeared with that key
    (the shell's ``appeared``: no control had its name in the look before the key). Never a Cancel the person's window
    already showed (review of fable/cu-v3-menus-teclas, finding 2: a copy in progress, a form being edited)."""

    if len(history) < 2 or not all(isinstance(step, dict) for step in history[-2:]):
        return None
    key, escape = history[-2], history[-1]
    if not (
        key.get("operation") == "input.key.press" and key.get("key") in _SEARCH_KEYS and key.get("ok") is True
        and key.get("sameView") is not True
        and escape.get("operation") == "input.key.press" and escape.get("key") == "escape" and escape.get("rule") is True
        and key_without_effect(escape)
    ):
        return None
    cancel = _cancel_button(view)
    if cancel is None or fold(cancel.get("name")).strip() not in _appeared(key):
        return None
    return cancel


def _cancel_button(view: dict) -> dict | None:
    """The one Cancel button of the view (a dialog's), outside the window's title bar."""

    found = [
        control for control in view.get("controls") or []
        if isinstance(control, dict) and control.get("kind") == "Button" and isinstance(control.get("i"), int)
        and fold(control.get("name")).strip() in _CANCEL_NAMES and not _in_title_bar(view, control)
    ]
    return found[0] if len(found) == 1 else None


def document_content(view: dict) -> bool:
    """Ronda 21 (pasada r18 v3-36): the view shows a document's content, by the App's own measure
    (ComputerUseMissionWindow.DocumentContent): a Document, or an Edit that takes a quarter of the window, that the
    provider does not read as read-only (a web page that takes no text is none)."""

    window = view.get("window") if isinstance(view, dict) else None
    window_area = _area(window.get("rect")) if isinstance(window, dict) else 0.0
    controls = view.get("controls") if isinstance(view, dict) else None
    focused = window.get("focused") if isinstance(window, dict) else None
    for control in [*(controls if isinstance(controls, list) else []), *([focused] if isinstance(focused, dict) else [])]:
        if not isinstance(control, dict) or "readonly" in str(control.get("state") or "").split():
            continue
        if control.get("kind") == "Document":
            return True
        if control.get("kind") == "Edit" and window_area > 0 and _area(control.get("rect")) >= window_area / 4:
            return True
    return False


# The window's frame as UIA lists it: never a sign that the window exposes its content.
_FRAME_KINDS = frozenset({"TitleBar", "MenuBar", "Window", "Pane"})
# A window lists at least this many controls of its own, beyond its frame, when it exposes a tree.
_TREE_CONTROLS = 3


def _exposes_a_tree(view: dict) -> bool:
    """The window lists controls of its own beyond its frame (its title bar, its system menu, minimize, maximize and
    close): a window drawn without an accessible tree (Electron, CEF) lists those and little else."""

    controls = view.get("controls") if isinstance(view, dict) else None
    own = [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and str(control.get("kind") or "") not in _FRAME_KINDS
        and not frame_button(fold(control.get("name"))) and not acts_on_the_window(control.get("name"))
        and not _in_title_bar(view, control)
    ]
    return len(own) >= _TREE_CONTROLS


def _command_box(control: object) -> bool:
    """The box that finds the application's own commands and help («Búsqueda de Microsoft», «Tell me», «Dime qué
    deseas hacer», «Search commands»; data «computerUse.evidence.commandBox»), by its own name: never the search of the
    window's content."""

    if not isinstance(control, dict):
        return False
    name = _SENTENCE_END.split(_own_name(control), 1)[0].strip(" :?¿")
    return bool(name) and re.match(_evidence_rules()["commandBox"], name) is not None


def _content_search_instead(view: dict, history: list[dict] | None, control: dict | None) -> dict | None:
    """For a search of content aimed at the command box: the view's other search field, never one already pressed in
    vain; None when the command box is not the target or the view has no other."""

    if not _command_box(control):
        return None
    other = _search_affordance(view, history or [])
    return other if other is not None and "i" in other and not _command_box(other) else None


def _search_affordance(view: dict, history: list[dict]) -> dict | None:
    """The search field or button of the window not used yet in this sub-goal, fields first; in a web browser, the
    page's own (measured on Opera: the tab search was clicked and «Ñuñoa» typed into it)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return None
    # A control is a search when its name says so before any sentence of help it carries: an entry of a search's
    # history («speedtest. Presione la tecla Suprimir para borrar el historial de búsqueda.», measured on a packaged
    # store) is one of its suggestions, not the search.
    found = [
        control for control in controls
        if isinstance(control, dict) and control.get("kind") in _SEARCH_KINDS
        and (control.get("kind") != "Document" or _search_document(view, control))
        and _is_search_field({**control, "name": _SENTENCE_END.split(str(control.get("name") or ""), 1)[0]})
        and not _steps_ok(history, "input.visible.click", label=str(control.get("name") or ""))
        and _of_the_page(view, control)
    ]
    # P4: the field is chosen by its NAME first: one that says it searches («Buscar:», a Document on the Character Map)
    # before one that only goes somewhere («Ir a Unicode:», an Edit, measured on v3-29/v3-30), then by kind.
    found.sort(key=lambda control: (
        # Lote r11 (v3-10): the box of the application's commands and help is the last place to look anything up in.
        _command_box(control),
        not names_a_search(_SENTENCE_END.split(str(control.get("name") or ""), 1)[0]),
        _SEARCH_KINDS.index(str(control.get("kind"))),
    ))
    if found:
        return found[0]
    if _web_browser(view):
        # The written lines of a browser mix the frame with the page (OCR has no tree to tell them apart).
        return None
    # A window that exposes no tree still writes its search box (measured on WhatsApp: «Buscar un chat o iniciar uno
    # nuevo» read by OCR, nothing in UIA): the written line is clicked like the field.
    # In a window with a tree, a written name of filters is a label or a button's (v3-52: OBS's «Filtros» panel
    # title), never its search box, which the tree lists. Its frame alone is no tree (review finding 5: an Electron
    # window lists its minimize, maximize and close and nothing else).
    written_kind = "Button" if _exposes_a_tree(view) else None
    written = [
        line.strip() for line in _view_lines(view)
        if 0 < len(line.split()) <= 8 and _is_search_field({"name": line, "kind": written_kind})
        and not _steps_ok(history, "input.visible.click", label=line.strip())
    ]
    written.sort(key=lambda line: (len(line.split()[0]) <= 2, len(line)))
    return {"name": written[0]} if written else None


# Bound again in this module below: the later binding is the one every reader sees. A duplicate kept as it was:
# resolving it changes behaviour.
_OPENER_KINDS = frozenset({"Button", "MenuItem", "SplitButton"})


def _has_address_field(view: dict) -> bool:
    """A text field named as an address, whatever it holds (a browser on a new tab holds nothing)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    focused = _focused(view)
    candidates = [*(controls if isinstance(controls, list) else []), *([focused] if focused is not None else [])]
    return any(
        isinstance(control, dict) and control.get("kind") in _FIELD_KINDS
        and _ADDRESS_NAME.search(fold(control.get("name"))) is not None
        for control in candidates
    )


def _navigation_opener(view: dict, history: list[dict]) -> dict | None:
    """The window's navigation or menu button not clicked yet in this sub-goal and not open already. Where the window
    has an address field (a browser, even on an empty tab), only one inside the page: the frame's menu is not where
    the page keeps its places. Never a switch."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return None
    framed = _has_address_field(view)
    for control in controls:
        if (
            isinstance(control, dict) and control.get("kind") in _OPENER_KINDS
            and _opener_name(control.get("name"))
            and "expanded" not in str(control.get("state") or "").split() and not _is_switch(control)
            and not _steps_ok(history, "input.visible.click", label=str(control.get("name") or ""))
            and (_inside_the_page(view, control) if framed else _of_the_page(view, control))
        ):
            return control
    return None


def _type_into(view: dict, history: list[dict], target: str, clicked: dict | None = None) -> dict[str, object] | None:
    """Typing the name into the search field in focus; a search field that still holds an earlier text is selected
    whole first, so the name replaces it (measured on Settings: «colores» appended to a leftover «colorespantalla»).
    One that already holds the name is not typed into again: its results are picked, else the name is selected and
    typed once more so the search runs. Select-all only in a field named as a search (in a document editor exposed as
    a text field it would select the person's work); a field without a search name that holds text is left to the
    model. With no field in focus (a window behind the person's reports none), the field the last click named
    (``clicked``) is the one: holding text, it is replaced whole by its index (r15b t-scroll-3: «times new roman» went
    in at the caret a click had left inside «fuentes», «fuetimes new romanntes»), never by keys sent to the window;
    one with no index to replace it by is left to the model."""

    focused = _focused_field(view)
    field = focused or (clicked if isinstance(clicked, dict) and clicked.get("kind") in _FIELD_KINDS else None)
    held = str((field or {}).get("value") or "").strip()
    if field is not None and _example_text(field, held):
        # Ronda 20 P1 (v3-03): only the field's example text («Buscar»), nothing of anyone's to select. With an index
        # the field takes the name by it (replacing the example), never by Ctrl+A and keys that go wherever the
        # keyboard lands when the window comes to the front (a slide's shape took «Organizador de diapositivas»).
        index = field.get("i")
        if isinstance(index, int) and not isinstance(index, bool) and field.get("kind") != "Document":
            arguments = {"text": typed_text(target), "index": index, "replace": True}
            return {"operation": "input.text.type", "arguments": arguments, "reason": _REASON_FIND}
        held = ""
    if not held:
        return _type(target)
    if not _is_search_field(field or {}) or (field or {}).get("kind") == "Document":
        # Never select-all in a Document that holds text: whatever its name, that text may be the person's work.
        return None
    last = history[-1] if history and isinstance(history[-1], dict) else {}
    if focused is not None and last.get("operation") == "input.key.press" and last.get("key") == "ctrl_a":
        return _type(target)
    if fold(held) == fold(target):
        picked = _result_naming(view, target, history)
        if picked is not None:
            return picked
    if focused is None:
        # No field has the keyboard: a key would go to whatever has it, and typed text would land at the caret inside
        # the leftover. Only the clicked field's index replaces it; without one the model decides (review finding 4).
        index = (field or {}).get("i")
        if not isinstance(index, int) or isinstance(index, bool):
            return None
        arguments = {"text": typed_text(target), "index": index, "replace": True}
        return {"operation": "input.text.type", "arguments": arguments, "reason": _REASON_FIND}
    return _key("ctrl_a")


REASON_SEARCH_FOCUS_UNPROVEN = "el clic en el cuadro de búsqueda escrito no probó que tomara el teclado: no se escribe nada"
SEARCH_FOCUS_UNPROVEN = "search_focus_unproven"


def _search_line_appeared(view: dict, clicked: str = "") -> str | None:
    """A written search prompt the last act made appear (a box that opened or took the caret: «Q Buscar por nombre»),
    other than the line just clicked."""

    for line in view.get("newText") or []:
        line = str(line).strip()
        if 0 < len(line.split()) <= 8 and _is_search_field({"name": line}) and fold(line) != fold(clicked):
            return line
    return None


def _written_box_took_keyboard(view: dict, label: str) -> bool:
    """The next look after a click on a search box's written line proves it took the keyboard: a written search prompt
    appeared with the click, or the clicked line is gone (its placeholder cleared for the caret) while the rest of the
    window stayed (a few new lines at most: a window that went elsewhere is no box with the caret)."""

    if _search_line_appeared(view, label) is not None:
        return True
    appeared = view.get("newText")
    if not isinstance(appeared, list) or not label.strip() or len(appeared) > 3:
        return False
    # Gone only when no line holds it at all (in a longer line, misread twice): never ``_text_line_with`` (ronda 25).
    return bool(_view_lines(view)) and not any(label_names(label, line) for line in _view_lines(view))


def _keyboard_on_another_field(view: dict) -> bool:
    """The view reports the keyboard on a field that is not a search: a message box (whatever its kind), a password,
    or a text field named otherwise. Typing a name there would write into it, or send it with the next Enter."""

    focused = _focused(view)
    candidates = [focused] if focused is not None else []
    controls = view.get("controls") if isinstance(view, dict) else None
    if isinstance(controls, list):
        candidates += [
            control for control in controls
            if isinstance(control, dict) and "focused" in str(control.get("state") or "").split()
        ]
    for control in candidates:
        if "password" in str(control.get("state") or ""):
            return True
        name = fold(control.get("name"))
        if _COMPOSER_NAME.search(name) and not _is_search_field(control):
            return True
        if control.get("kind") in _FIELD_KINDS and not _is_search_field(control):
            return True
        if (
            control.get("kind") == "Document" and str(control.get("value") or "").strip()
            and not _search_document(view, control)
        ):
            # A document that holds text has the keyboard: a name typed now would land in the person's work.
            return True
    return False


def _typed_into_written_search(view: dict, history: list[dict]) -> bool:
    """The last step typed into a written search box whose keyboard was proven (the step before it was a search key or
    a click on a search's written line) and the text now shows as that box's new line, with no other field reporting
    the keyboard: the Enter that follows submits the search."""

    if len(history) < 2 or _keyboard_on_another_field(view):
        return False
    typed, before = history[-1], history[-2]
    if typed.get("operation") != "input.text.type" or typed.get("ok") is not True or before.get("ok") is not True:
        return False
    searched = (
        (before.get("operation") == "input.key.press" and before.get("key") in _SEARCH_KEYS)
        or (before.get("operation") == "input.visible.click" and _is_search_field({"name": before.get("label")})
            and not isinstance(before.get("index"), int))
    )
    text = fold(typed.get("text")).strip(" «»\"'")
    if not searched or not text:
        return False
    # The box's own line: the typed text alone, after at most a drawn magnifier («Q Cuphead»).
    return any(
        re.fullmatch(rf"(?:\S{{1,2}}\s+)?{re.escape(text)}", fold(line).strip()) is not None
        for line in view.get("newText") or []
    )


def _search_result_of_the_interface(control: dict, view: dict) -> bool:
    """A search's result a name the person did not say may land on (``_interface_control`` without its content-view
    rule: a search's results are the items of a list beside the field, «Configuración de fuentes» on Settings): no
    DataItem (the person's files and rows), and no list or tree item of a window that writes to people (its contacts
    and conversations)."""

    kind = str(control.get("kind") or "")
    return kind != "DataItem" and (kind not in _TRANSLATED_ITEM_KINDS or not _message_window(view))


def _field_echo(text: str, typed: Iterable[str]) -> bool:
    """A line or control that only repeats a text typed into the search: the text itself, or with the field's glyphs
    around it, one character each (the OCR reads the magnifier as «Q»: «Q fonts», t-scroll-3 r9)."""

    words = fold(text).split()
    while words and len(words[0]) == 1:
        words = words[1:]
    while words and len(words[-1]) == 1:
        words = words[:-1]
    bare = " ".join(words)
    return bool(bare) and any(bare == " ".join(fold(item).split()) for item in typed if str(item or "").strip())


def _result_naming(
    view: dict, target: str, history: list[dict], also: Iterable[str] = (), asked: str | None = None,
) -> dict[str, object] | None:
    """The result of a search that names the target (or, ``also``, one of the place's other names as whole words:
    «fonts» typed and «Configuración de fuentes» listed): a control (list item, tree item, button, link first), else a
    line the search made appear. Never Enter: a voice channel stays a click RiskPolicy confirms. Never a switch (going
    to a place changes no setting on the way), and never the offer to look the name up in the help or on the web.

    Ronda 25 (c7, n5, s04, s13, u1; twin SearchBurst.ResultNaming): the exact name, or whole words in a short entry
    (``_ENTRY_KINDS``) or a short button or line new with the act (``newText``), never a tab or a sentence; one typo
    only in the one entry so named; never the echo of a text typed or a field's value («cotele», «Q fonts»).

    With ``asked`` (the person's request: going to a place, never a search for their words) a result is never an act
    the request does not ask for (``_translation_clickable``: «Guardar en Tu biblioteca» for «library», an account
    act RiskPolicy would not confirm), and one named only by another name is a control of the interface, never the
    person's content (``_search_result_of_the_interface``), as any name the person did not say."""

    others = tuple(dict.fromkeys(str(name) for name in also if str(name).strip() and fold(name) != fold(target)))
    exact = {" ".join(fold(name).split()) for name in (target, *others)}
    controls = [control for control in (view.get("controls") or []) if isinstance(control, dict)]
    echoes = (target, *(str(step.get("text") or "") for step in _steps_ok(history, "input.text.type")),
              *(str(control.get("value") or "") for control in controls if control.get("kind") in _FIELD_KINDS))
    new = view.get("newText") if isinstance(view.get("newText"), list) else None
    fresh = None if new is None else {" ".join(fold(line).split()) for line in new}
    # Encargo TZ-OSC (tandas z3/z4 t4-c04 t3): once the result named exactly so was pressed, a name that only holds it
    # is something else («Gris oscuro», «Menta oscuro», colours, pressed one after another after the mode «Oscuro»).
    exact_pressed = any(
        " ".join(fold(step.get("label")).split()) in exact for step in _steps_ok(history, "input.visible.click")
    )

    def naming(text: str, control: dict | None = None) -> bool:
        bare = " ".join(fold(text).split())
        if exact_pressed and bare not in exact:
            return False
        if _field_echo(text, echoes) and (control is None or control.get("kind") in _DESCRIPTIVE_KINDS or bare not in exact):
            return False
        if asked is not None and not _translation_clickable(asked, text):
            return False
        kind = (control or {}).get("kind")
        if bare not in exact and (not _short_name(text, target) or kind in _DESCRIPTIVE_KINDS or kind == "TabItem" or (
                kind not in _ENTRY_KINDS and fresh is not None and bare not in fresh)):
            return False
        if _whole_words_name(target, text):
            return True
        if not any(_whole_words_name(name, text) for name in others):
            return False
        # A line is the control written with its name, when one is listed: the same guard.
        carriers = [control] if control is not None else [listed for listed in controls if fold(listed.get("name")) == fold(text)]
        return not carriers or any(_search_result_of_the_interface(carrier, view) for carrier in carriers)

    listed = [
        control for control in controls
        if control.get("kind") not in _FIELD_KINDS and control.get("kind") != "Document"
        and not _is_switch(control) and not opens_help(control.get("name"), view, target)
        and not _steps_ok(history, "input.visible.click", label=str(control.get("name") or ""))
        and _of_the_page(view, control) and not _frame_of_the_window(view, control)
    ]
    named = [control for control in listed if naming(str(control.get("name") or ""), control)]
    near = [control for control in listed if control.get("kind") in _ENTRY_KINDS and _one_typo(str(control.get("name") or ""), target)
            and (asked is None or _translation_clickable(asked, str(control.get("name") or "")))]
    named = named or (near if len(near) == 1 and not exact_pressed else [])
    if named:
        # A result first (a list item, a link…), and among the results the one that is exactly the name: «Ñuñoa del
        # Mar» before «Festival de Ñuñoa», never the place whose name only contains it.
        named.sort(key=lambda control: (
            control.get("kind") not in _RESULT_KINDS,
            fold(control.get("name")) not in exact,
            _RESULT_KINDS.index(str(control.get("kind"))) if control.get("kind") in _RESULT_KINDS else len(_RESULT_KINDS),
        ))
        return _click(named[0], "el resultado de la búsqueda")
    for line in map(str, _view_lines(view) if new is None else new):
        if (
            naming(line) and not _is_the_window_title(view, line)
            and not _steps_ok(history, "input.visible.click", label=line.strip())
            and not _names_a_switch(view, line.strip()) and not opens_help(line, view, target)
        ):
            return {"operation": "input.visible.click", "arguments": {"label": line.strip()}, "reason": "el resultado de la búsqueda"}
    return None


def _find_step(
    target: str, view: dict, history: list[dict], *, navigate: bool = True, choose: bool = True,
    objective: str | None = None, others: Iterable[str] = (),
) -> dict[str, object] | None:
    """The next step of looking the target up (``_find_content_step``). Review of palanca 6 (finding 3): an option of
    the window's view or of its order (``view_option_named``: «ordenar por nombre», «vista de iconos grandes») is never
    looked up in the search of the content, by any route that reaches here, while the window shows the control of that
    option (``_view_option_shown``): such a step is left to the model. Review 2 (finding 2): without that control the
    words are a place's name like any other («vista de tareas» in a settings window) and the lookup stays."""

    step = _find_content_step(target, view, history, navigate=navigate, choose=choose, objective=objective, others=others)
    if view_option_named(target) is not None and _searches_content(step) and _view_option_shown(view, target):
        return None
    if navigate and _searches_content(step) and (
        own_place_button(view, target) is not None or _pressed_place_button(history, target, view)
    ):
        # Encargo S (banco e1/e2 u1, y8, v8: «tu biblioteca» and «inicio» typed into a player's search, a stranger's
        # list called «Tu biblioteca» opened and played): a place of the window with its own button is reached by that
        # button, never looked up in the search of its content, whose results are content named like it.
        return None
    return step


def _names_own_place(name: object, place: object) -> bool | None:
    """What a control's name says of the place as its own button (``own_place_button``): True when it names the place
    after a verb that closes it (the place is open), False after a verb that opens it or leads to it, None when it is no
    such name. A name that is only the place's carries no verb: a card, a server or a channel may be called so too
    (measured on Discord: «Cotele» a server and an activity card)."""

    folded = fold(name).strip()
    for verbs, said in ((_PLACE_TOGGLE["closing"], True), (_PLACE_TOGGLE["opening"], False)):
        verb = next((verb for verb in verbs if folded.startswith(verb)), None)
        if verb is not None:
            return said if _is_the_place(folded[len(verb):], place) else None
    return None


def _is_the_place(name: object, place: object) -> bool:
    """A name that is the place's, articles and possessives aside, in any of its languages (the place table's other
    names: «Abre Tu biblioteca» is the button of «your library»; revisión S, H3)."""

    bare = _POSSESSIVE.sub("", fold(place).strip()).strip()
    said = _POSSESSIVE.sub("", fold(name).strip()).strip()
    return len(bare) >= 3 and (said == bare or said in {fold(other) for other in label_alternatives(bare)})


def own_place_button(view: object, place: object) -> tuple[dict, bool] | None:
    """The window's own button of a place: a Button that names the place (articles and possessives aside) after a verb
    that opens it («Abre Tu biblioteca») or closes it («Comprimir Tu biblioteca», there only while the place is open;
    data «computerUse.placeToggle»). (button, open): open is True for the closing one, which wins (an open panel also
    offers to expand it). None when the window has none. Twin of the App's ComputerUseSuccessCheck.PlaceToggle."""

    controls = view.get("controls") if isinstance(view, dict) else None
    found: tuple[dict, bool] | None = None
    for control in controls if isinstance(controls, list) else ():
        if not isinstance(control, dict) or control.get("kind") != "Button":
            continue
        state = _names_own_place(control.get("name"), place)
        if state is True:
            return control, True
        if state is False:
            found = found or (control, False)
    return found


def _pressed_own_button(history: list[dict] | None, place: object) -> bool:
    """A click of the sub-goal that may have acted (``_may_have_acted``) on the place's own button, by its label."""

    return any(
        isinstance(step, dict) and step.get("operation") == "input.visible.click" and _may_have_acted(step)
        and _names_own_place(step.get("label"), place) is not None
        for step in history or ()
    )


def _layer_holds_the_keyboard(view: dict, history: list[dict]) -> bool:
    """The last step wrote a text the provider refused because the field could not take the keyboard
    (``input_field_not_reachable``), the view's keyboard is on a window inside the mission's window (a layer: a quick
    switcher, a pop-up dialog; never the window itself) and no Escape was pressed after that refusal."""

    last = history[-1] if history and isinstance(history[-1], dict) else None
    focused = _focused(view) or {}
    window = view.get("window") if isinstance(view, dict) else None
    title = fold((window or {}).get("title")).strip() if isinstance(window, dict) else ""
    return (
        last is not None and last.get("operation") == "input.text.type" and last.get("ok") is not True
        and "input_field_not_reachable" in str(last.get("error") or "")
        and focused.get("kind") == "Window" and bool(fold(focused.get("name")).strip())
        and fold(focused.get("name")).strip() != title
        and not any(isinstance(step, dict) and step.get("key") == "escape" for step in history)
    )


def _pressed_place_button(history: list[dict] | None, place: object, view: object) -> bool:
    """A click of the sub-goal that may have acted on a Button named as the place itself (fase 2 con S, v8 ×2: the
    press on a player's «Inicio» did not hold behind the person's window and «inicio» was typed into its search): the
    place has a button of its own and is never looked up by its name after it was pressed (its own button with a verb,
    ``_pressed_own_button``, too). A list item or a link of that name (a channel, a chat) keeps its lookup."""

    buttons = {
        fold(control.get("name")).strip() for control in (view.get("controls") if isinstance(view, dict) else None) or ()
        if isinstance(control, dict) and control.get("kind") == "Button"
    }
    return _pressed_own_button(history, place) or any(
        isinstance(step, dict) and step.get("operation") == "input.visible.click" and _may_have_acted(step)
        and _is_the_place(step.get("label"), place)
        and (step.get("kind") == "Button" or fold(step.get("label")).strip() in buttons)
        for step in history or ()
    )


def _find_content_step(
    target: str, view: dict, history: list[dict], *, navigate: bool = True, choose: bool = True,
    objective: str | None = None, others: Iterable[str] = (),
) -> dict[str, object] | None:
    """The next step of looking the target up when it is not on screen, from the view and this sub-goal's history
    alone, the same in any application: a search field or button (click, type the name, click the result naming it),
    else the window's navigation or menu button (the target is then looked for among what appeared), else ctrl_k and
    ctrl_f (kept only when a field takes the keyboard, otherwise escape), else scrolling the list that
    may hold it (up to three times while the view changes). The navigation button only when ``navigate`` (going to a
    place; a search is the window's search). None leaves the step to the model.

    With ``objective`` (a place, never a search for the person's words) the place is looked up by its name in the
    window's language (``_name_to_look_up``: the table's names and the translator's, ``others``), and a result that
    names it by any of those names is its result (t-scroll-3, r9: «fonts» typed into a Spanish Settings)."""

    said = target
    also: tuple[str, ...] = ()
    if objective is not None:
        target = _name_to_look_up(said, others, view, history, objective)
        if fold(target) != fold(said) or _said_in_other_language(said, view, objective):
            # The place's other names count only when it was said in another language than the window's (or is
            # looked up by another name): on an English window an English request's «network» is never «Sha·red».
            also = tuple(
                name for name in dict.fromkeys((said, *label_alternatives(said), *others))
                if str(name).strip() and fold(name) != fold(target)
            )
    last = history[-1] if history else None
    if last is not None and last.get("searchBurst") is True and last.get("ok") is not True:
        # A search burst that stopped before its last sub-act: a result that needs the person's yes is asked for with
        # that exact result named; any other stop leaves its opener used and the next way is tried (never a key or a
        # text on what the burst left half done).
        confirmed = _burst_with_choice(view, history, target, last, (said, *also))
        if confirmed is not None:
            return confirmed
        last = None
    last_operation = last.get("operation") if last is not None else None
    cancel = _escape_left_it_open(view, history)
    if cancel is not None:
        # The Escape left what the shortcut brought up on screen (t-menu-3, t-long-4: Notepad's «Vínculo» stayed after
        # ctrl_k and Escape, and ctrl_f followed onto it): its own Cancel, which came with the key, closes it, by
        # identity, with no key.
        return _click(cancel, _REASON_UNSOUGHT)
    if last is not None and last_operation == "input.text.type" and fold(last.get("text")) == fold(target):
        # The name was just typed: its result; else, in a search or address field, Enter once submits it (measured on
        # v3-59: «wikipedia» typed in a new tab's search box and Escape pressed); else the search closed to try the
        # next way.
        picked = _result_naming(view, target, history, also, objective)
        if picked is not None:
            return picked
        if _submits_with_enter(view, history):
            return {"operation": "input.key.press", "arguments": key_arguments("enter", view, history),
                    "reason": "escribí el nombre en la búsqueda y ningún resultado lo nombra: Enter la envía"}
        if last.get("query") is True and last.get("awaited") is not True:
            # Encargo IMP2 (imp1 imp-wa-abrir: «musica» typed in a chat search, Escape pressed 550 ms later, and the result
            # «Música» drawn under that Escape, measured on redpc 750 to 880 ms after the text): a search's results are
            # looked at once more, a moment later, before the search is closed (the App waits and marks «awaited»; «query»
            # is the App's word that the text went into a box that only searches).
            return _none("la búsqueda todavía no muestra sus resultados", code=SEARCH_PENDING)
        return _key("escape")
    if (
        last is not None and last_operation == "input.visible.click" and last.get("ok") is True
        and last.get("awaited") is not True and _whole_words_name(target, str(last.get("label") or ""))
        and _typed_target(history, target)
    ):
        # Encargo IMP4 (imp3 imp-wa-leer: «Música 29/9/2026» pressed, the look 700 ms later still the list, and the next
        # result naming «musica», another person's chat, pressed): a result pressed is given the same moment a search's
        # results are before anything else is pressed (the App waits once and marks «awaited»).
        return _none("el resultado pulsado todavía no se abrió", code=SEARCH_PENDING)
    if _typed_target(history, target):
        # Encargo TZ-WA2: a chat search left holding the name (IMP3, imp2) is cu_chats.chat_search_step's, by the
        # application's data; here only a name typed in this sub-goal has its results read.
        picked = _result_naming(view, target, history, also, objective)
        if picked is not None:
            return picked
    if last is not None and last_operation == "input.key.press" and last.get("key") in _SEARCH_KEYS:
        if key_without_effect(last):
            # Teclas sin efecto (r9: v3-37, v3-39, v3-16): the shortcut left the window exactly as it was (the App's
            # look after it kept the view's signature). No Escape and no other blind key after it (an Escape closed
            # the Photos viewer on v3-16): the next step is a visible control, the model's.
            return None
        # Ronda 23 (g1, r21): a look read behind the person's window, of a window drawn without an accessible tree
        # (a web view), tells neither where the keyboard is nor what the key brought up: the tree reads a window
        # behind, the screen does not. On it no Escape and no next shortcut is pressed blind; only a written proof
        # (a search line that appeared) is followed, and anything else is the model's.
        blind = _looked_behind(view) and not _exposes_a_tree(view)
        focused = _focused_field(view)
        # P4: the field the shortcut brought up is a search only when it is named as one, by its own name or by the
        # prompt written with it (a quick switcher's «Busca servidores, canales o MD»); any other field (measured on
        # t-menu-3: ctrl_k opened Notepad's «Insertar vínculo» and «view» was typed there) is closed, never typed into.
        if focused is not None and (_is_search_field(focused) or _search_line_appeared(view) is not None):
            return _type_into(view, history, target)
        if focused is not None:
            # A field that holds text may be the person's work (a document editor exposed as a text field): left to
            # the model, no key on it.
            return None if blind or str(focused.get("value") or "").strip() else _key("escape")
        # The focused control's own name is no search prompt (a document or a web window's root titled «… Buscar»).
        own = str((_focused(view) or {}).get("name") or "")
        if _search_line_appeared(view, own) is not None and not _keyboard_on_another_field(view):
            # The key brought up a written search prompt (measured on Steam's library: ctrl_f wrote «Q Buscar por
            # nombre» where only a magnifier was drawn, with no tree to report the focus): that box has the keyboard.
            return _type_into(view, history, target)
        if blind:
            return None
        if str((_focused(view) or {}).get("kind") or "") in _FRAME_FOCUS_KINDS and not _appeared(last):
            # The key only moved the keyboard to the window's own frame (v3-52: ctrl_k on OBS's «Ajustes» focused its
            # «Barra de menús del sistema», the OCR read a stray «-ustes»): it brought nothing up, and an Escape there
            # closes the dialog the mission had reached. The next way is tried. A key that made controls appear brought
            # a window up, whatever its frame has the keyboard: that one is closed (review finding 4).
            pass
        elif view.get("newText") != [] or _focused(view) is not None:
            # A look that cannot say what changed (no «newText») still closes whatever the key may have opened (r8),
            # except on a blind look behind (above).
            return _key("escape")
        # The key changed nothing on screen (no line appeared): there is nothing to close, and an Escape would only
        # spend a look that changes nothing (measured on Steam: ctrl_k and Escape left the screen still twice and the
        # mission stopped before ctrl_f); the next way is tried.
    if last is not None and last_operation == "input.visible.click":
        clicked = find_control(view, str(last.get("label") or ""))
        # A search box clicked by its written line (no tree to tell focus) takes the keyboard as a person expects.
        written_box = clicked is None and last.get("ok") is True and not isinstance(last.get("index"), int)
        # A field the receipt says was clicked keeps the caret when the next look no longer lists it (a pop-up of
        # its suggestions or history came up over it): a person types now, never picks a suggestion as the search.
        hidden_field = clicked is None and last.get("ok") is True and last.get("kind") in _FIELD_KINDS
        # A search button that changed the window opened its box (measured on Discord: «Buscar o iniciar una
        # conversación» opens the quick switcher, whose field the tree does not report focused): a person types now.
        opened_box = (
            clicked is not None and last.get("ok") is True and clicked.get("kind") in {"Button", "SplitButton", "MenuItem"}
            and (last.get("surfaceChanged") is True or bool(view.get("newText")))
        )
        if _is_search_field({"name": last.get("label")}) and (
            _focused_field(view) is not None
            or (clicked is not None and (clicked.get("kind") in _FIELD_KINDS or _search_document(view, clicked)))
            or opened_box or hidden_field
        ):
            return _type_into(view, history, target, clicked)
        if _is_search_field({"name": last.get("label")}) and written_box:
            # A box clicked by its written line (no tree to tell focus) takes the name only when the next look proves
            # it has the keyboard (its line changed); otherwise the name could land in a message box or another field.
            if _keyboard_on_another_field(view) or not _written_box_took_keyboard(view, str(last.get("label") or "")):
                return _none(REASON_SEARCH_FOCUS_UNPROVEN, code=SEARCH_FOCUS_UNPROVEN)
            return _type_into(view, history, target)
    searched = _typed_target(history, target)
    if not searched:
        focused = _focused_field(view)
        if focused is not None and _is_search_field(focused):
            return _type_into(view, history, target)
        if navigate and not browser_or_computer_place(target) and _empty_address_search(view) is not None:
            # A browser's empty tab with the keyboard on its address-and-search box (measured on v3-59: «Barra de
            # direcciones y búsqueda» focused, empty): a person types a site there and presses Enter. A place of the
            # browser or the computer («descargas», «historial») is reached through the browser's own menu: typed
            # there it would be a web search, and a result named like it a false place.
            return _type(target)
        affordance = _search_affordance(view, history)
        if affordance is not None:
            return _search_click(affordance, target) if choose else _click(affordance, _REASON_FIND)
    opener = _navigation_opener(view, history) if navigate else None
    if opener is not None:
        # Modes, sections and pages often live behind the window's navigation or menu button (the Calculator's
        # modes, a WinUI app's pages, a web app's «Menú»): opened before any blind shortcut, and the target is then
        # looked for among what appeared.
        return _click(opener, "el destino no está en pantalla: abro la navegación")
    if choose and _menus_to_open(view, history):
        # A window with a menu bar not opened yet in this sub-goal: what the goal names is reached through its menus
        # (t-menu-3: «view» was Notepad's «Ver», and ctrl_k opened «Vínculo»); there a shortcut finds in the document
        # or inserts, never in the interface. The model, which sees the menus named, takes the step.
        return None
    # In a web browser ctrl_k searches the web from the address bar, not the page: only the page's find (ctrl_f).
    keys = ("ctrl_f",) if _web_browser(view) else _SEARCH_KEYS
    if document_content(view):
        # Ronda 21 (pasada r18 v3-36): over a document's content only a shortcut that alters none of it (the find,
        # ctrl_f) is pressed blind; ctrl_k inserts a link in an editor (t-menu-3) and the App's guard refuses it on a
        # document the mission may not touch.
        keys = tuple(key for key in keys if key in CONTENT_KEEPING_KEYS)
    # A shortcut that brought up something not sought earlier in the mission, on this application, is never pressed
    # again there (the shell carries it across sub-goals, ``spent``).
    keys = tuple(key for key in keys if key not in _spent_keys(view))
    # A blind shortcut that changed nothing in this sub-goal says the window has none: no other one is tried.
    blind_failed = any(key_without_effect(step) and step.get("key") in _SEARCH_KEYS for step in history)
    for key in () if blind_failed else keys:
        if not any(step.get("operation") == "input.key.press" and step.get("key") == key for step in history):
            return _key(key)
    return _scroll_step(view, history)


# The kinds of a search affordance that OPEN its box or list instead of being it (a button, a menu entry, a combo box's
# drop-down): what they open may live only while the window is active (measured live: a chat application's channel
# search closed 32 ms after the front went back), and the front goes back before every decision.
_OPENER_KINDS = frozenset({"Button", "SplitButton", "MenuItem", "ComboBox"})
SEARCH_RESULT_NEEDS_CONFIRMATION = "visible_search_result_needs_confirmation"
_REASON_BURST = "el destino no está en pantalla: abro la búsqueda, escribo el nombre y elijo el resultado en una sola ráfaga"
_REASON_BURST_CHOICE = "el resultado de la búsqueda llega a otras personas: lo elijo sólo con tu confirmación"


def _search_click(affordance: dict, target: str) -> dict[str, object]:
    """The click on the window's search (goal v3 point 0, fix 3). A control that opens the box or the list (``_OPENER_KINDS``,
    or one that says it is collapsed), identified by the view, carries the whole sequence (``search``): the shell opens
    it, types the destination and chooses the result that names it in one burst inside a pause of the person, the result
    read and pressed by its identity. A field that is already the box (an Edit, a Document, a written line) is clicked
    alone, as before: its typing reaches it behind the person's window."""

    step = _click(affordance, _REASON_FIND)
    states = str(affordance.get("state") or "").split()
    if isinstance(affordance.get("i"), int) and (affordance.get("kind") in _OPENER_KINDS or "collapsed" in states):
        step["arguments"]["search"] = target
        step["reason"] = _REASON_BURST
    return step


def _burst_with_choice(
    view: dict, history: list[dict], target: str, last: dict, also: Iterable[str] = (),
) -> dict[str, object] | None:
    """A search burst found the result but did not press it, since it reaches a person or cannot be undone (a voice
    channel): the same burst, with that exact result named (``choose``), so RiskPolicy asks for this invocation and the
    shell presses only that result once the person says yes. None when the burst stopped for any other cause or its
    opener is no longer on the view. The burst is the one launched with the place's name or, ``also``, any of its other
    names (the window's language's, chosen at the step that launched it)."""

    if last.get("error") != SEARCH_RESULT_NEEDS_CONFIRMATION or not str(last.get("label") or "").strip():
        return None
    names = {fold(name) for name in (target, *also) if str(name or "").strip()}
    opened = next(
        (step for step in reversed(history) if step.get("search") and fold(step.get("search")) in names), None
    )
    control = find_control(view, str(opened.get("label") or "")) if opened is not None else None
    if control is None or not isinstance(control.get("i"), int):
        return None
    step = _click(control, _REASON_BURST_CHOICE)
    searched = str(opened.get("search")).strip()
    step["arguments"]["search"] = target if fold(searched) == fold(target) else searched
    step["arguments"]["choose"] = str(last.get("label")).strip()
    return step


def _empty_address_search(view: dict) -> dict | None:
    """The focused, empty text field named as both an address and a search («Barra de direcciones y búsqueda», «Search
    or enter web address»): a browser's tab with nothing loaded. One that holds an address is the page's, never
    replaced on the way to a place."""

    for control in _focused_controls(view):
        name = _own_name(control)
        if (
            control.get("kind") in _FIELD_KINDS and "password" not in str(control.get("state") or "")
            and "readonly" not in str(control.get("state") or "").split()
            and _ADDRESS_NAME.search(name) and _SEARCH_NAME.search(name) and not str(control.get("value") or "").strip()
        ):
            return control
    return None


def _submits_with_enter(view: dict, history: list[dict]) -> bool:
    """Enter submits what was just typed, once: the keyboard is on a search box that is no quick switcher and no
    result of it is highlighted (Enter there opens the highlighted one, not the goal: a voice channel would be joined
    without RiskPolicy asking, see ``_result_naming``), or on a browser's address-and-search box (an address alone is a
    form's field, never submitted). Never a message box nor a password, and only while the field shows what was
    typed when the view exposes its value."""

    typed_at = max((position for position, step in enumerate(history) if step.get("operation") == "input.text.type"), default=-1)
    if typed_at < 0 or any(
        step.get("operation") == "input.key.press" and step.get("key") == "enter" for step in history[typed_at + 1:]
    ):
        return False
    typed = fold(history[typed_at].get("text"))
    for control in _focused_controls(view):
        name = _own_name(control)
        if control.get("kind") not in _FIELD_KINDS or "password" in str(control.get("state") or ""):
            continue
        if _COMPOSER_NAME.search(fold(control.get("name"))) and not _is_search_field(control):
            continue
        value = control.get("value")
        if isinstance(value, str) and not fold(value).startswith(typed):
            continue
        if _ADDRESS_NAME.search(name) and _SEARCH_NAME.search(name):
            return True
        if _is_search_field(control) and not quick_switcher_name(name) and not _highlighted_result(view):
            return True
    return False


def _highlighted_result(view: dict) -> bool:
    """The view shows an item selected in a list of results: Enter in the search would open it."""

    return any(
        isinstance(control, dict) and control.get("kind") in {"ListItem", "TreeItem", "MenuItem", "DataItem"}
        and "selected" in str(control.get("state") or "").split()
        for control in view.get("controls") or []
    )


def _scroll_step(view: dict, history: list[dict]) -> dict[str, object] | None:
    scrolls = [step for step in history if step.get("operation") == "input.scroll"]
    if len(scrolls) >= _SCROLLS or any(
        step.get("ok") is not True or step.get("changed") is False or step.get("surfaceChanged") is False
        for step in scrolls
    ):
        return None
    arguments: dict[str, object] = {"direction": "down", "amount": 5}
    holder = _list_holding_items(view)
    if holder is not None:
        arguments["index"] = holder
    return {"operation": "input.scroll", "arguments": arguments, "reason": _REASON_FIND}


def _held_for_the_encoder(
    semantic: SemanticMatcher | None, target: str, names: Iterable[str], translated: Iterable[str],
    translate: Callable[[str], tuple[str, ...]] | None, view: dict, history: list[dict], objective: str | None,
) -> bool:
    """A blind lookup of the place is first left to the model (lat-e5, v3-14): the encoder was still loading (cold; one
    that failed answering in time is loaded, and the search goes on as before), the place has no other name (none from
    the table, ``names``, none from the translator, and the translator did not give the name itself back, as for
    «Hollow Knight»: ``LabelTranslator.said_as_is``), nothing was looked up yet in this sub-goal, and the place was said
    in another language than the window's (``_said_in_other_language``). Anything else is looked up as before: the
    encoder adds nothing to that search. The held search stays the model's fallback (``_decide_step``)."""

    translated = tuple(translated)
    if semantic is None or semantic.state != ENCODER_COLD or _search_started(history):
        return False
    if translated:
        # Ronda 20 P1 (v3-03): the translator's name may be wrong («Organizador de diapositivas» for «slide sorter»,
        # with «Clasificador de diapositivas» on screen). It exempts the search only when no control of the view
        # shares a content word with the place as said or translated; else the model decides with the view first.
        return _view_resembles(view, (target, *translated)) and _said_in_other_language(target, view, objective)
    if len({fold(name).strip() for name in (target, *names) if str(name).strip()}) > 1:
        return False
    said_as_is = getattr(translate, "said_as_is", None)
    if callable(said_as_is) and said_as_is(target):
        return False
    return _said_in_other_language(target, view, objective)


def _blind_lookup(
    step: dict[str, object] | None, history: list[dict], view: dict | None = None, names: Iterable[str] = (),
    objective: str | None = None,
) -> bool:
    """A shortcut of the literal lookup (``_find_step``) before anything was looked up: a key may open what the window
    binds to it (ctrl_k: «Insertar vínculo», t-menu-3). Never a turn of the wheel: it changes nothing and brings a
    place below the list's edge into view (t-scroll-3: «Fuentes» lies below what Settings shows). Ronda 20 P1 (v3-03):
    with ``view``, the click on the window's search (``_search_click``) is blind too when the place (the first of
    ``names``) was said in another language than the window's and a control of the view shares a content word with
    one of its ``names`` (as said or translated): the window may show it with other words."""

    names = tuple(names)
    if not isinstance(step, dict) or _search_started(history):
        return False
    if step.get("reason") == _REASON_FIND and step.get("operation") == "input.key.press":
        return True
    return (
        view is not None and step.get("operation") == "input.visible.click"
        and step.get("reason") in {_REASON_FIND, _REASON_BURST, REASON_BY_NAME} and bool(names)
        and _view_resembles(view, names)
        and _said_in_other_language(names[0], view, objective)
    )


# A content word of a name: five letters or more (no article, preposition or conjunction of either language).
_CONTENT_WORD = re.compile(r"[a-z0-9]{5,}")


def _view_resembles(view: dict, names: Iterable[str]) -> bool:
    """A control of the view that takes no text and is not the place already chosen (selected, on or checked: the
    window is there, the goal is elsewhere; «Biblioteca de música» selected while looking for the video library)
    shares a content word with one of ``names`` (ronda 20 P1)."""

    words = {word for name in names for word in _CONTENT_WORD.findall(fold(name))}
    controls = view.get("controls") if isinstance(view, dict) else None
    if not words or not isinstance(controls, list):
        return False
    return any(
        isinstance(control, dict) and control.get("kind") not in _EDITABLE_KINDS and not _is_search_field(control)
        and not {"selected", "on", "checked"} & set(str(control.get("state") or "").split())
        and words & set(_CONTENT_WORD.findall(fold(control.get("name"))))
        for control in controls
    )


# The kinds of the window's frame and its bars: never a search's result.
_FRAME_RESULT_KINDS = frozenset({"TitleBar", "Window", "ToolBar", "MenuBar", "ScrollBar", "StatusBar"})
# The kinds a frame's navigation button is drawn as.
_FRAME_BUTTON_KINDS = frozenset({"Button", "SplitButton"})


def _window_title(view: dict) -> str:
    window = view.get("window") if isinstance(view, dict) else None
    return str(window.get("title") or "") if isinstance(window, dict) else ""


def _is_the_window_title(view: dict, name: object) -> bool:
    """The name is the window's own title (its title bar, its root pane, a line that repeats it). Integración 20b: apart
    from ``_names_the_window`` (review 3 of r20 P1), which tells whether a name is the document the title names."""

    title = fold(_window_title(view)).strip()
    return bool(title) and fold(name).strip() == title


def _frame_of_the_window(view: dict, control: dict) -> bool:
    """Ronda 20b, palanca 6 (v3-41, v3-43: «iconos grandes - Panel de control», the root pane titled as the window, and
    «Actualizar "Opciones de energía" (F5)» taken as a search's result): the window's frame and its navigation, by kind
    and by the window's title, the navigation buttons by data (``frameNavigation``): never a result."""

    kind = str(control.get("kind") or "")
    if kind in _FRAME_RESULT_KINDS or _is_the_window_title(view, control.get("name")):
        return True
    zone = str(control.get("zone") or "")
    return kind in _FRAME_BUTTON_KINDS and (not zone or zone.startswith("T")) and _named_by_list(
        control.get("name"), "frameNavigation")
