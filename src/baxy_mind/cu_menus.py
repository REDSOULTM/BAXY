"""Menus: the context menu of a control, the window's menu bar opened before its shortcuts, and the entry of
the menu a click opened.
"""

from __future__ import annotations

import re
from contextvars import ContextVar

from .semantic.account_acts import account_act
from .semantic.missions import EMPTY_SPACE_TARGET, fold
from .cu_view import (
    _ITEM_KINDS, _area, _in_title_bar, _inside, _list_holding_items, _same_row, find_control, label_names,
)
from .cu_fields import key_arguments
from .cu_acts import _click
from .cu_history import _steps_ok
from .cu_navigation import _runs_when_opened


def _menu_left_open(step: dict) -> bool:
    """Ronda 21: a verified act whose receipt says it opened a menu (``opened``; the mission's window holds the front
    while it acts, so no menu closes with it)."""

    return step.get("ok") is True and step.get("opened") is True


def _menu_act_on(step: dict, target: str, view: dict) -> bool:
    """Revisión 1 de la ronda 21 (hallazgo 3): a menu act counts for «abrir el menu contextual de X» only when it was
    opened on X (its label names X, as the shell's ``menuOpened:X`` reads it), and for an empty space only on the list
    that holds the view's items (the same container the rule opens it on): a menu left open on another element
    («lista.txt» for «notas.txt») is none of X's."""

    label = fold(step.get("label"))
    if fold(target) == fold(EMPTY_SPACE_TARGET):
        holder = _list_holding_items(view, empty_space=True)
        container = next(
            (control for control in (view.get("controls") or []) if isinstance(control, dict) and control.get("i") == holder),
            None,
        ) if holder is not None else None
        return container is not None and bool(label) and fold(container.get("name")) == label
    return bool(fold(target)) and fold(target) in label


def _menu_on_screen(view: dict) -> bool:
    return any(isinstance(control, dict) and control.get("kind") == "Menu" for control in (view.get("controls") or []))


def _context_menu_step(target: str, view: dict, history: list[dict]) -> dict[str, object] | None:
    """«abrir el menu contextual de X» (clic derecho en X). Ronda 21 (t-menu-1, t-menu-2): first X's own context menu
    by its identity (the click in the manner «menu»: ShowContextMenu or WM_CONTEXTMENU, no key, no pointer); once an
    act opened a menu (its receipt, or a menu the view shows) nothing more is pressed, never the context-menu key over
    an open menu. The fallback when that act failed or opened nothing is the one before: X chosen by its click, then
    the context-menu key, which opens the menu of what is chosen. An empty space of a list is the list's own context
    menu (the container that holds the view's items, never one of them); a window with no list holding items, X not
    on screen, or an empty space whose menu act failed, is the model's step."""

    menus = [
        step for step in history if step.get("operation") == "input.visible.click" and step.get("manner") == "menu"
        and _menu_act_on(step, target, view)
    ]
    if any(_menu_left_open(step) for step in menus) or (any(step.get("ok") is True for step in menus) and _menu_on_screen(view)):
        return None
    if fold(target) == fold(EMPTY_SPACE_TARGET):
        if menus:
            return None
        holder = _list_holding_items(view, empty_space=True)
        controls = [control for control in (view.get("controls") or []) if isinstance(control, dict)]
        container = next((control for control in controls if control.get("i") == holder), None) if holder is not None else None
        if container is None or not str(container.get("name") or "").strip() or not any(
            control.get("kind") in _ITEM_KINDS and _inside(control.get("rect"), container.get("rect")) for control in controls
        ):
            return None
        step = _click(container, "abro el menú del espacio vacío de la lista")
        step["arguments"]["manner"] = "menu"
        return step
    plain = [step for step in _steps_ok(history, "input.visible.click") if not step.get("manner")]
    if not menus and not plain:
        control = find_control(view, target)
        if control is None or _runs_when_opened(control) and control.get("kind") not in _ITEM_KINDS:
            return None
        step = _click(control, "abro el menú del elemento")
        step["arguments"]["manner"] = "menu"
        return step
    if not plain:
        control = find_control(view, target)
        if control is None or _runs_when_opened(control) and control.get("kind") not in _ITEM_KINDS:
            return None
        return _click(control, "elijo el elemento antes de abrir su menú")
    if _menu_on_screen(view):
        return None
    if not _steps_ok(history, "input.key.press", key="context_menu"):
        return {"operation": "input.key.press", "arguments": key_arguments("context_menu", view, history),
                "reason": "abro el menú del elemento elegido"}
    return None


# The menus of a bar the model opens before the routine's blind shortcuts and the wheel come back (OBS lists eight).
_MENUS_BEFORE_KEYS = 2
# Whether a menu bar holds the routine's blind shortcuts back for the model; off for the literal step that follows a
# model that took none of the menus (``_decide_step``).
_MENU_BAR_HOLDS: ContextVar[bool] = ContextVar("cu_menu_bar_holds", default=True)


def _menu_bar(view: dict) -> list[dict]:
    """The window's menu bar: the collapsed MenuItems drawn side by side in one row, at least two, each with a
    rectangle and outside the title bar. The window's system menu and an account button are no bar: listed without a
    rectangle or alone in their row (review of fable/cu-v3-menus-teclas, finding 1: «Sistema» and the account,
    without rectangles, held the shortcuts on six real windows that have no menu bar)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    items = [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and control.get("kind") == "MenuItem"
        and "collapsed" in str(control.get("state") or "").split() and _area(control.get("rect")) > 0
        and str(control.get("name") or "").strip() and account_act(str(control.get("name") or "")) is None
        and not _in_title_bar(view, control)
    ]
    return [control for control in items if any(other is not control and _same_row(control, other) for other in items)]


def _menus_to_open(view: dict, history: list[dict]) -> list[dict]:
    """The menu bar's entries not clicked yet in this sub-goal, while the sub-goal opened fewer than
    ``_MENUS_BEFORE_KEYS`` of them (none once the model has looked in that many: the routine's ways come back)."""

    if not _MENU_BAR_HOLDS.get():
        return []
    clicked = {
        fold(step.get("label")) for step in history
        if isinstance(step, dict) and step.get("operation") == "input.visible.click"
    }
    bar = _menu_bar(view)
    if sum(1 for control in bar if fold(control.get("name")) in clicked) >= _MENUS_BEFORE_KEYS:
        return []
    return [control for control in bar if fold(control.get("name")) not in clicked]


def _menu_opened_by(view: dict, history: list[dict], target: str, goal: str = "") -> str | None:
    """The entry of the short menu the last click, made on ``target``, opened that the goal's words name best, else
    the place's own page, else its first entry when the menu is in the tree; never an entry that does something
    (play, install, send…). None when no menu opened or none of those holds."""

    # The last verified click: a failed step after it (a learned entry no longer on the menu, measured on Steam: the
    # replayed click was ambiguous and the model answered none) leaves the menu it opened on screen.
    verified = [step for step in history if isinstance(step, dict) and step.get("ok") is True]
    last = verified[-1] if verified else None
    if last is None or last.get("operation") != "input.visible.click":
        return None
    trailing = history[history.index(last) + 1:]
    if any(isinstance(step, dict) and step.get("operation") != "input.visible.click" for step in trailing):
        return None
    clicked = str(last.get("label") or "")
    if not (label_names(target, clicked) or label_names(clicked, target)):
        return None
    # What the verified click made appear: after failed clicks the view's newText is what the last look changed
    # (nothing, for a click that changed nothing), so the App's newTextAfterClick (the look right after the last
    # verified click) is read instead; without it the menu cannot be told.
    if trailing:
        after_click = view.get("newTextAfterClick")
        if not isinstance(after_click, list):
            return None
        new_lines = after_click
    else:
        new_lines = view.get("newText") or []
    # A menu's entries are short new lines; the OCR also rereads, garbled, the long lines the menu now covers.
    # OCR noise (a cut word, an address, a mark) is not an entry: an entry is a short run of real words.
    appeared = [
        str(line).strip() for line in new_lines
        if str(line).strip() and len(str(line).split()) <= 3 and len(str(line)) <= 30
        and re.fullmatch(r"[^\W\d_][\w'’.-]*(?:\s+[\w'’.-]+){0,2}", str(line).strip()) is not None
        and "://" not in str(line) and len(fold(line).replace(" ", "")) >= 3
    ]
    if not 1 < len(appeared) <= 8:
        return None
    entries = [
        entry for entry in appeared
        if not label_names(clicked, entry) and not _steps_ok(history, "input.visible.click", label=entry)
        and _ACT_ENTRY.search(fold(entry)) is None
    ]
    # «colecciones de la biblioteca» after a click on «Biblioteca»: the goal's other words name the entry.
    words = [word for word in fold(goal).split() if len(word) >= 4 and not label_names(word, clicked)]
    scored = sorted(
        ((sum(1 for word in words if label_names(word, entry)), position) for position, entry in enumerate(entries)),
        key=lambda pair: (-pair[0], pair[1]),
    )
    if scored and scored[0][0] > 0:
        return entries[scored[0][1]]
    # No word of the goal names an entry: the destination's own page when the menu offers one by that name
    # (measured on Steam: «BIBLIOTECA» → «Página principal»), else the first entry only when the menu is in the tree
    # (its entries are menu or list items that appeared together); never a blind click on a written line.
    home = next((entry for entry in entries if _HOME_ENTRY.fullmatch(fold(entry).strip()) is not None), None)
    if home is not None:
        return home
    first = appeared[0]
    return first if first in entries and _menu_in_tree(view, appeared) else None


# The entry of a place's menu that is the place's own page.
_HOME_ENTRY = re.compile(
    r"(?:pagina\s+principal|principal|inicio|home|home\s+page|main|main\s+page|overview|vista\s+general|resumen)"
)
# An entry that does something instead of going somewhere: never chosen by default.
_ACT_ENTRY = re.compile(
    r"(?<!\w)(?:jugar|play|instalar|install|iniciar|launch|ejecutar|run|comprar|buy|enviar|send|unirse|join|"
    r"desinstalar|uninstall|eliminar|delete)(?!\w)"
)
_MENU_ENTRY_KINDS = frozenset({"MenuItem", "ListItem"})


def _menu_in_tree(view: dict, appeared: list[str]) -> bool:
    """Every appeared entry is a menu or list item of the view's controls: the menu is in the tree."""

    controls = view.get("controls") if isinstance(view, dict) else None
    named = {
        fold(control.get("name")).strip() for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and str(control.get("kind")) in _MENU_ENTRY_KINDS
    }
    return bool(appeared) and all(fold(entry).strip() in named for entry in appeared)
