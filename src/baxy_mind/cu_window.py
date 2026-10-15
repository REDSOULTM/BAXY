"""The mission's window: whether it is the application's (never a developer's or BAXY's own), its frame and
system menu (never a place a goal names), what the validator vetoes of it, and the page of a web browser.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from .semantic.cu_buscar import (
    asks_for_the_window_menu, caption_verb, closes_by_caption, leaves_the_window, system_menu_name,
)
from .semantic.missions import fold
from .cu_view import _FIELD_KINDS, _area, _drawn, _focused, _inside, _without_row_cells
from .cu_goals import _goal_names_control
from .cu_fields import _ADDRESS_NAME


# The windows where the person's own work and BAXY live: never taken for another application. Each is adopted only
# when the request names that very application (the words on the right).
_PROTECTED_PROCESSES: dict[str, frozenset[str]] = {
    "code": frozenset({"code", "vs code", "vscode", "visual studio code"}),
    "code - insiders": frozenset({"code insiders", "visual studio code insiders"}),
    "devenv": frozenset({"visual studio", "devenv"}),
    "windowsterminal": frozenset({"terminal", "windows terminal"}),
    "openconsole": frozenset({"terminal", "windows terminal"}),
    "powershell": frozenset({"powershell", "windows powershell"}),
    "pwsh": frozenset({"powershell", "pwsh"}),
    "cmd": frozenset({"cmd", "simbolo del sistema", "command prompt"}),
    "conhost": frozenset({"cmd", "simbolo del sistema", "command prompt", "consola"}),
    "baxy": frozenset({"baxy"}),
    "baxy-core": frozenset({"baxy"}),
}
_GENERIC_APPLICATION_WORDS = frozenset({
    "the", "los", "las", "navegador", "browser", "google", "microsoft", "mozilla", "app", "aplicacion",
})


def _window_fold(value: object) -> str:
    """fold without format characters (Edge writes «Microsoft\u200b Edge» in its titles)."""

    return fold("".join(character for character in str(value or "") if unicodedata.category(character) != "Cf"))


def _process_key(process: object) -> str:
    folded = _window_fold(process)
    return folded[:-4] if folded.endswith(".exe") else folded


def protected_process(process: object, application: str | None) -> bool:
    """A developer's or BAXY's own window (an editor, a terminal, a console, BAXY) that the request did not name."""

    names = _PROTECTED_PROCESSES.get(_process_key(process))
    return names is not None and _window_fold(application) not in names


def _title_names(title: object, application: str) -> bool:
    """The application named as whole words in the title's last « - » segment, where windows put their own name
    («SteamLocalAdapter.cs - BAXY - Visual Studio Code» names Visual Studio Code, never Steam). A title with no
    separator is the application's name itself («Steam», «Calculadora»)."""

    segment = re.split(r"\s+[-\u2013\u2014|]\s+", _window_fold(title))[-1].strip()
    wanted = _window_fold(application)
    return bool(segment) and bool(wanted) and re.search(rf"(?<!\w){re.escape(wanted)}(?!\w)", segment) is not None


def reopens_unraised(view: dict) -> bool:
    """cu-v3-elevacion: the view's window runs as administrator and its program would open again with the person's
    rights (window.elevated and window.reopensUnraised, read by the provider from the process token and the
    program's manifest). Twin of ComputerUseMission.ReopensUnraisedFirst."""

    window = view.get("window") if isinstance(view, dict) else None
    return isinstance(window, dict) and window.get("elevated") is True and window.get("reopensUnraised") is True


def application_is_in_front(view: dict, application: str | None) -> bool:
    """Whether the window of the view is the application's: the provider resolved it for the application
    (``requested``), its process is the application's executable, or its title names it in its last segment. Never a
    developer's or BAXY's own window unless that is what was named (safety review 2026-10-07)."""

    if not application:
        return True
    window = view.get("window") if isinstance(view, dict) else None
    if not isinstance(window, dict):
        return False
    process = _process_key(window.get("process"))
    if protected_process(process, application):
        return False
    if window.get("requested") is True:
        return True
    tokens = [token for token in _window_fold(application).split() if len(token) >= 3 and token not in _GENERIC_APPLICATION_WORDS]
    joined = "".join(_window_fold(application).split())
    if process and (process == joined or process in tokens):
        return True
    return _title_names(window.get("title"), application) or (
        any(_title_names(window.get("title"), token) for token in tokens) and _segment_only_names(window.get("title"), tokens)
    )


def _segment_only_names(title: object, tokens: list[str]) -> bool:
    """A word of the application's name names it in the title only when the title's own name says nothing else: every
    word of its last segment is one of the name's («Reproductor multimedia» for «Reproductor multimedia (Windows 11)»,
    «Word» for «Microsoft Word»). Another application whose name shares one word is not it (v3-36 r7: «notas» of «Notas
    rápidas» in «lista.txt: Bloc de notas» took the Notepad in front for the notes app, and the mission searched there)."""

    segment = re.split(r"\s+[-–—|]\s+", _window_fold(title))[-1]
    words = [word for word in re.findall(r"\w+", segment) if len(word) >= 3 and word not in _GENERIC_APPLICATION_WORDS]
    named = {word for token in tokens for word in re.findall(r"\w+", token)}
    return bool(words) and all(word in named for word in words)


# The navigation kinds that may be the window's system menu (``_system_menu``), never a tab or an entry.
_MENU_KINDS = frozenset({"MenuItem", "MenuBar"})


def _system_menu(view: dict, control: dict) -> bool:
    """The window's system menu (its icon's menu: restore, move, close), never a place of the window: a menu control
    listed with no rectangle, or drawn inside the window's title bar as its only menu item (live v3-34: «Sistema» in
    «Barra de menús del sistema», a 28-pixel square at the corner of a notes app's sign-in screen). A title bar that
    holds several menu items holds the window's own menus. Only a menu: tabs in a title bar (an editor's open files)
    and list or tree entries are places of the window wherever they are drawn, or read without a rectangle."""

    if str(control.get("kind")) not in _MENU_KINDS:
        return False
    if not _drawn(view, control):
        return True
    rect = control.get("rect")
    if _area(rect) <= 0:
        return False
    controls = [item for item in view.get("controls") or [] if isinstance(item, dict)]
    x = float(rect["x"]) + float(rect["w"]) / 2  # type: ignore[index]
    y = float(rect["y"]) + float(rect["h"]) / 2  # type: ignore[index]

    def inside(box: object, px: float, py: float) -> bool:
        return _area(box) > 0 and float(box["x"]) <= px <= float(box["x"]) + float(box["w"]) and (  # type: ignore[index]
            float(box["y"]) <= py <= float(box["y"]) + float(box["h"]))  # type: ignore[index]

    for bar in controls:
        if str(bar.get("kind")) != "TitleBar" or not inside(bar.get("rect"), x, y):
            continue
        items = [
            item for item in controls if str(item.get("kind")) == "MenuItem" and _area(item.get("rect")) > 0
            and inside(bar.get("rect"), float(item["rect"]["x"]) + float(item["rect"]["w"]) / 2,
                       float(item["rect"]["y"]) + float(item["rect"]["h"]) / 2)
        ]
        return len(items) <= 1
    return False


def _system_menu_off_goal(view: dict, control: object, goal: str | None) -> bool:
    """Pasada r15b (A1: v3-13, v3-16, v3-32, v3-33, v3-38, v3-39): the window's system menu (a menu control named as
    Windows names it, «Sistema», «Barra de menús del sistema», or one ``_system_menu`` finds drawn alone in the title
    bar) when the goal does not ask to move, restore, minimize, maximize, resize or close the window. It is never
    listed to the model nor pressed. A menu read without a rectangle is no system menu by that alone here (Word lists
    its ribbon's «Tabla» so): only its name says it."""

    if not isinstance(control, dict) or str(control.get("kind")) not in _MENU_KINDS:
        return False
    if control.get("systemMenu") is True:
        # Ronda 20b, palanca 8: the provider found it hanging from the title bar (its chain, not its name).
        return not asks_for_the_window_menu(goal)
    named_as_system = system_menu_name(control.get("name"))
    drawn_alone = _area(control.get("rect")) > 0 and _system_menu(view, control)
    if not (drawn_alone or named_as_system):
        return False
    if not named_as_system and _goal_names_control(goal, control.get("name")):
        # Review of sistema-cumplido, finding 5: a lone menu of the application's own drawn in the title bar («Más
        # opciones») that the goal names («abre más opciones y elige exportar») is the goal's place, not the system menu.
        return False
    return not asks_for_the_window_menu(goal)


def _frame_off_goal(view: dict, control: object, goal: str | None) -> bool:
    """Ronda 20b, palanca 8 (pasada r18, v3-51: the model was offered «TitleBar «Añadir escena»» and pressed it as the
    dialog's content): the window's frame is no act. The title bar never; a caption button (minimize, maximize,
    restore, close) drawn inside a title bar of the view only when the goal asks to move, restore, minimize, maximize,
    resize or close the window. The caption button by its first word, as the mission's ``CaptionInTitleBar`` takes it:
    a packaged frame names it after the window («Minimizar Seguridad de Windows», v3-62). Encargo EX (tanda n5 t4-c06:
    after «Libro en blanco» the model pressed «Libro1 - Excel», the title's own button, and it opened «Guardar este
    archivo»): a button named as the whole title of a window that shows a document names the window, never a step."""

    if not isinstance(control, dict):
        return False
    kind = str(control.get("kind"))
    if kind == "TitleBar":
        return True
    window = view.get("window") if isinstance(view, dict) and isinstance(view.get("window"), dict) else {}
    title = _window_fold(window.get("title")).strip()
    if kind == "Button" and re.search(r"\s[-–—|]\s", title) and _window_fold(control.get("name")).strip() == title:
        return True
    if kind != "Button" or not caption_verb(control.get("name")) or asks_for_the_window_menu(goal):
        return False
    bars = [
        bar for bar in view.get("controls") or []
        if isinstance(bar, dict) and str(bar.get("kind")) == "TitleBar" and isinstance(bar.get("rect"), dict)
    ]
    holding = [bar for bar in bars if _inside(control.get("rect"), bar.get("rect"))]
    if not holding:
        return False
    # Review 3 of palanca 8 (B2): the close of a frame is the way out of a window whose content offers none, and of a
    # dialog drawn over the window (its title bar narrower than the window's); never hidden then, whatever the goal
    # says («sal del aviso», «dismiss the notice»), nor when the goal leaves the window («quit the calculator»).
    if closes_by_caption(control.get("name")) and (
        leaves_the_window(goal) or _dialog_bar(bars, holding) or _content_without_way_out(view, bars)
    ):
        return False
    return True


# The kinds that hold content without being any (the frame's own pieces are told by their place, in a title bar).
_CONTAINER_KINDS = frozenset({"Pane", "Window", "Document", "Group", "Custom", "TitleBar"})
# The kinds written or drawn for reading only: content that offers no act.
_READ_ONLY_KINDS = frozenset({"Text", "Image"})


def _dialog_bar(bars: list[dict], holding: list[dict]) -> bool:
    """The title bar holding the button is a dialog's drawn over the window: narrower than the view's widest one."""

    widest = max(_width(bar.get("rect")) for bar in bars)
    return all(_width(bar.get("rect")) < widest for bar in holding)


def _width(rect: object) -> float:
    try:
        return max(float(rect["w"]), 0.0)  # type: ignore[index]
    except (KeyError, TypeError, ValueError):
        return 0.0


def _content_without_way_out(view: dict, bars: list[dict]) -> bool:
    """The view shows content outside its title bars (a text, an image) and none of it is a control to act on: the
    frame's close is the only way out of it. A view of the frame alone (v3-51: the content not read yet) is not one."""

    content = [
        control for control in view.get("controls") or []
        if isinstance(control, dict) and str(control.get("kind")) not in _CONTAINER_KINDS
        and control.get("systemMenu") is not True
        and not any(_inside(control.get("rect"), bar.get("rect")) for bar in bars)
    ]
    return bool(content) and all(
        str(control.get("kind")) in _READ_ONLY_KINDS or "readonly" in str(control.get("state") or "")
        for control in content
    )


# A web address as an address bar shows it: with its scheme, from «www.», or a host with its domain.
# Bound again in this module below: the later binding is the one every reader sees. A duplicate kept as it was:
# resolving it changes behaviour.
_WEB_ADDRESS = re.compile(r"^(?:[a-z][a-z0-9+.-]*://\S+|www\.\S+|[\w-]+(?:\.[\w-]+)+(?:[/:?#]\S*)?)$")


def _without_vetoed(view: dict, goal: str | None, names: Iterable[str] | None = None) -> dict:
    """Ronda 23 (v3-23): the view without the controls the validator vetoes for this goal (``_system_menu_off_goal``,
    ``_frame_off_goal``: the ones ``compact_view_text`` never shows the model either). Revisión 1 de r23 (a): with
    ``names``, the vetoed ones go only when another control not vetoed is named exactly so (they would tie with it);
    when a vetoed control is the only one so named, the view is returned whole (the press goes to the validator, as
    before), so a control that merely carries the name never stands in for it (OBS «Bandeja del sistema» for «Sistema»)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return view
    vetoed = _vetoed_controls(view, goal)
    if not vetoed or (names is not None and not _named_exactly(controls, names, vetoed, kept=True)):
        return view
    return {**view, "controls": [control for control in controls if not any(control is out for out in vetoed)]}


def _vetoed_controls(view: dict, goal: str | None) -> list[dict]:
    controls = view.get("controls") if isinstance(view, dict) else None
    return [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and (
            _system_menu_off_goal(view, control, goal) or _frame_off_goal(view, control, goal)
        )
    ]


def _named_exactly(controls: list, names: Iterable[str], vetoed: list[dict], *, kept: bool) -> bool:
    """Whether a control (a row's own cell counted as its row) is named exactly one of ``names`` and is, when ``kept``,
    none of ``vetoed``; when not ``kept``, one of them."""

    wanted = {fold(name).strip() for name in names if fold(name).strip()}
    return any(
        isinstance(control, dict) and fold(control.get("name")).strip() in wanted
        and any(control is out for out in vetoed) is not kept
        for control in _without_row_cells(controls)
    )


# What a browser's address field holds on a site: «https://es.wikipedia.org/…», «es.wikipedia.org/wiki/…» (a folder
# path or «Este equipo > Descargas» is a file explorer's).
_WEB_ADDRESS = re.compile(r"^(?:https?://)?(?:[\w-]+\.)+[^\W\d_]{2,}(?::\d+)?(?:[/?#]|$)")


def _web_browser(view: dict) -> bool:
    """The window is a web browser showing a site: a field named as the address holds a web address."""

    controls = view.get("controls") if isinstance(view, dict) else None
    focused = _focused(view)
    candidates = [*(controls if isinstance(controls, list) else []), *([focused] if focused is not None else [])]
    return any(
        isinstance(control, dict) and control.get("kind") in _FIELD_KINDS
        and _ADDRESS_NAME.search(fold(control.get("name"))) is not None
        and _WEB_ADDRESS.match(str(control.get("value") or "").strip()) is not None
        for control in candidates
    )


def _page(view: dict) -> dict | None:
    """The web page in a browser's view: its largest document, when it is the size of a page (a quarter of the
    window; 200×150 without the window's rectangle). None while the page is not exposed (measured on Opera loading:
    only a 22×22 «Cargando…» document beside the frame)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    documents = [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and control.get("kind") == "Document" and _area(control.get("rect")) > 0
    ]
    if not documents:
        return None
    page = max(documents, key=lambda control: _area(control.get("rect")))
    rect = page["rect"]
    window = view.get("window") if isinstance(view, dict) else None
    window_area = _area(window.get("rect")) if isinstance(window, dict) else 0.0
    if window_area > 0:
        return page if _area(rect) >= window_area / 4 else None
    return page if float(rect["w"]) >= 200 and float(rect["h"]) >= 150 else None


def _of_the_page(view: dict, control: dict) -> bool:
    """A control is the window's own unless the window is a web browser: there only what lies inside the page and
    comes after it in the tree is the page's. The tab strip's «Buscar pestañas», the bookmarks and the side bar lie
    outside it; the browser's own pop-ups (its tab search) are drawn over it but listed before it (measured on Opera)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if not _web_browser(view) or not any(isinstance(item, dict) and item.get("rect") for item in controls or []):
        # Not a browser, or a view without rectangles: nothing tells the frame from the page.
        return True
    return _inside_the_page(view, control)


def _inside_the_page(view: dict, control: dict) -> bool:
    """The control lies inside the page document and after it in the tree; False when no page is exposed."""

    page = _page(view)
    if page is None or not _inside(control.get("rect"), page.get("rect")):
        return False
    position, page_position = control.get("i"), page.get("i")
    return not (isinstance(position, int) and isinstance(page_position, int)) or position > page_position
