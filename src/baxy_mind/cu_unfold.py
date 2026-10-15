"""Before a «none» ends a sub-goal with steps left: the one control named exactly as the goal, an order looked
up in the window's search of orders, and what may lead to the goal and is still closed, opened.
"""

from __future__ import annotations

import re

from .semantic.cu_buscar import text_slot
from .semantic.missions import CONTEXT_MENU_GOAL, fold
from .semantic.cu_tipos import OPEN_FILE_GOAL
from .cu_vocabulary import _named_by_list, _screen_lists
from .cu_view import (
    _FIELD_KINDS, _ONE_LINE_HEIGHT, _area, _drawn, _focused, _in_title_bar, _inside, _is_switch, _same_row,
    _scroll_part, _title_band, _viewed_control, effect_intent_actionable_kinds,
)
from .cu_goals import FIELD_GOAL, REVEAL_GOAL, _GOING_HEADS, _TO_APPEAR_ATOMS, _check_names, _goal_target, reading_goal
from .cu_acts import _click, _none
from .cu_window import _system_menu_off_goal
from .cu_history import _appeared, _typed_target, _wrote_or_sent
from .cu_unasked import _safe_to_unfold, opens_help
from .cu_languages import _said_in_other_language
from .cu_meaning import SemanticMatcher, _UNFOLDED_CONTROLS
from .cu_creation import _creating_object
from .cu_options import _word_folds, combo_value
from .cu_navigation import _tree_descent_step
from .cu_menus import _menus_to_open
from .cu_lookup import REASON_SEARCH_FOCUS_UNPROVEN, SEARCH_FOCUS_UNPROVEN, _result_naming, _type_into
from .cu_validate import _checked_manner


# The kinds whose collapsed list the fallback opens: a split button's arrow, a drop-down, a menu. Ronda 24: a
# drop-down holds values, not orders, so it is opened only when the goal names it or its value (``_goal_names_combo``).
_UNFOLD_FALLBACK_KINDS = frozenset({"SplitButton", "ComboBox", "MenuItem"})
REASON_UNFOLD_BEFORE_NONE = "la orden puede vivir en una lista cerrada: la abro antes de rendirme"
REASON_UNFOLD_TAB = "el destino puede vivir en otra pestaña de la ventana: la elijo antes de rendirme"
REASON_EXACT_NAME = "un solo control de la vista lleva entero el nombre que pide el objetivo"
# Ronda 24 (v3-03, v3-04, v3-17, v3-40): the kinds that are a frame or a text, never a step: never named as similar
# to the goal nor offered by the retry.
_NOT_ACTIONABLE_KINDS = frozenset({"Group", "Text", "Pane", "ScrollBar", "Thumb", "TitleBar", "Window"})
# Revisión 1 de ronda 24: the kinds the exact name presses blind are the ones that are pressed; never one that keeps
# a value a press would change (a slider's middle, a check box's mark, a field, a drop-down, a document).
_EXACT_NAME_KINDS = effect_intent_actionable_kinds() - {
    "Slider", "CheckBox", "RadioButton", "Edit", "ComboBox", "Document",
}


REASON_COMMAND_SEARCH = "la orden se busca en la búsqueda de órdenes de la ventana"
# The goals that are no order: a place, a search of content, a text, a key, a calculation, a send.
_NOT_AN_ORDER = ("buscar ", "escribir ", "ir a ", "calcular ", "apretar ", "enviar")


def _is_order_goal(goal: str | None) -> bool:
    """The goal is an order of the window said freely («dividir el panel en vertical»): no place, no control named
    with a kind, no search of content, no text to write."""

    folded = fold(goal or "").strip()
    if not folded or folded.startswith(_NOT_AN_ORDER) or folded.startswith(
        (REVEAL_GOAL, CONTEXT_MENU_GOAL, FIELD_GOAL, OPEN_FILE_GOAL)
    ):
        return False
    # Review of palanca 6 (finding 2): a goal that only looks («leer el perfil predeterminado», «decir cuál es el tema»,
    # «verificar que quedó oscuro») or carries a question is no order: it never presses the palette nor types there.
    if reading_goal(goal) or "?" in folded or _named_by_list(folded, "lookingGoals"):
        return False
    # Ronda 24 (v3-01, v3-04: a title to write opened «Pegar» and «Dictar»): a goal of writing into a named part
    # (``text_slot``) is no order either.
    if text_slot(goal) is not None:
        return False
    return _goal_target(goal or "") is None


# Review 2 of palanca 6 (finding 1): the kinds a window's search of its own orders is drawn as: a field or a button
# (an entry of a menu that opens it, as the Terminal's «Paleta de comandos»). Never a text, a link, a pane.
_COMMAND_SEARCH_KINDS = _FIELD_KINDS | frozenset({"Button", "SplitButton", "MenuItem"})


def _names_the_command_search(name: object) -> bool:
    """The whole name is one of the data's names of a search of orders (``commandSearch``), never a name that only
    starts with one (review 2, finding 1: a web page's «¿Qué quieres hacer hoy?» is no search of orders)."""

    folded = re.sub(r"\s+", " ", fold(name)).strip(" ¿?¡!.:")
    return bool(folded) and folded in _screen_lists().get("commandSearch", ())


def _command_search_control(view: dict) -> dict | None:
    """The window's search of its own orders drawn on screen (a command palette, a «tell me» box): a field or a button
    (``_COMMAND_SEARCH_KINDS``) whose whole name is one of the data's names (``commandSearch``)."""

    controls = view.get("controls") if isinstance(view, dict) else None
    return next((
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and str(control.get("kind") or "") in _COMMAND_SEARCH_KINDS
        and _names_the_command_search(control.get("name")) and _drawn(view, control)
    ), None)


def _order_lookup(goal: str | None, view: dict, history: list[dict]) -> dict[str, object] | None:
    """An order looked up in the window's search of orders: its entry pressed once, the order typed where it put the
    keyboard, then the result that names it (``_result_naming``). Only for an order (``_is_order_goal``): a search of
    content («buscar hola») goes to the window's search, never here."""

    if not _is_order_goal(goal):
        return None
    order = str(goal or "").strip()
    pressed = next((
        step for step in reversed(history) if isinstance(step, dict) and step.get("operation") == "input.visible.click"
        and _names_the_command_search(step.get("label"))
    ), None)
    if pressed is None:
        control = _command_search_control(view)
        return _click(control, REASON_COMMAND_SEARCH) if control is not None else None
    if pressed.get("ok") is not True:
        return None
    if not _typed_target(history, order):
        # Review of palanca 6 (finding 2: «insertar una tabla» typed into the person's document after «¿Qué desea
        # hacer?» was pressed without the keyboard; the Terminal's shell prompt took «dividir el panel en vertical»):
        # the order is typed only into the search of orders proved to have the keyboard, as ``_find_step`` asks of a
        # search; otherwise nothing is typed and the sub-goal says why.
        if not _order_search_has_keyboard(view, pressed):
            return _none(REASON_SEARCH_FOCUS_UNPROVEN, code=SEARCH_FOCUS_UNPROVEN)
        return _type_into(view, history, order)
    return _result_naming(view, order, history)


def _order_search_has_keyboard(view: dict, pressed: dict) -> bool:
    """The search of orders the press brought up has the keyboard: the field in focus (never a document, a password)
    is the search of orders itself (its whole name is one of ``commandSearch``), or one the press made appear (the
    shell's ``appeared`` for that step names it: no control had its name in the look before the press) holding no text
    yet. Review 2 of palanca 6 (finding 1): a search field that already had the keyboard before the press («Buscar en
    el documento», a site's own search) is the search of the content, never the one of orders."""

    keyboard = _focused(view)
    if keyboard is None:
        controls = view.get("controls") if isinstance(view, dict) else None
        keyboard = next((
            control for control in (controls if isinstance(controls, list) else [])
            if isinstance(control, dict) and "focused" in str(control.get("state") or "").split()
        ), None)
    if keyboard is None or keyboard.get("kind") not in _FIELD_KINDS or "password" in str(keyboard.get("state") or ""):
        return False
    if _names_the_command_search(keyboard.get("name")):
        return True
    name = fold(keyboard.get("name")).strip()
    return bool(name) and name in _appeared(pressed) and not str(keyboard.get("value") or "").strip()


def _routine_opens_help(step: object, view: dict, goal: str | None, objective: str | None) -> bool:
    """A routine's press (``deterministic_step``) on the offer to look the name up in the help or on the web, which the
    person did not ask for (``opens_help``): never pressed by a rule (ronda 20b, palanca 6, v3-44: «Buscar «devices and
    printers» en Ayuda y soporte técnico» opened a browser's help page)."""

    if not isinstance(step, dict) or step.get("operation") != "input.visible.click":
        return False
    arguments = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
    control = _viewed_control(view, arguments.get("index"))
    names = [arguments.get("label"), *((control.get("name"),) if control is not None else ())]
    return any(opens_help(name, view, goal, objective) for name in names if str(name or "").strip())


def _unfold_kind_of_goal(goal: str | None) -> str | None:
    """Ronda 24: what a goal is for the blind unfolding before a «none»: «place» for a goal that names a control or a
    place («ir a sistema», «desactivar reading pane»), «order» for an order said freely (``_is_order_goal``), None for
    any other (a reading, a search, a text to write, a drawing, a key): those never open anything blind."""

    folded = fold(goal or "").strip()
    if not folded or reading_goal(goal) or "?" in folded:
        return None
    parsed = _goal_target(goal or "")
    if parsed is not None and parsed[2].strip():
        return "place"
    return "order" if _is_order_goal(goal) else None


def _goal_names_combo(goal: str | None, objective: str | None, control: dict) -> bool:
    """Ronda 24 (v3-27, v3-29, v3-30, v3-17, t-form-3, t-scroll-2): a drop-down holds values; the fallback opens one
    only when the goal names it («cambia la fuente a Wingdings» on «Fuente:», ``combo_value``) or its shown value."""

    if combo_value(goal, objective, control.get("name")) is not None:
        return True
    words = f" {' '.join(_word_folds(str(goal or '').split()))} "
    label = " ".join(word for word in _word_folds(str(control.get("name") or "").split()) if word)
    value = " ".join(word for word in _word_folds(str(control.get("value") or "").split()) if word)
    return any(len(said) > 2 and f" {said} " in words for said in (label, value))


def _calls_an_assistant(control: dict) -> bool:
    """Ronda 24 (v3-07: «Copilot» opened blind): a command whose first words call an assistant (data
    «assistantCommand»)."""

    words = fold(control.get("name")).split()
    return any(word in _screen_lists().get("assistantCommand", ()) for word in words[:2])


def _assistant_or_creating(control: dict) -> bool:
    """Ronda 24 (v3-07: «Copilot» and «Nuevo correo electrónico» opened blind): a command that creates something (data
    «creatingCommand») or calls an assistant (data «assistantCommand»)."""

    return _creating_object(control) is not None or _calls_an_assistant(control)


def _covers_the_window(control: dict, view: dict) -> bool:
    """Revisión 2 de ronda 24 (v3-26, v3-24, t-file-1): a ``Window`` control drawn over the whole window below its
    title bar: as wide as the window, down to its bottom, from the frame buttons' band down (``_title_band``; the
    window's top plus ``_CAPTION_FALLBACK`` when the view shows no frame button). That is a modal layer: nothing of the
    window shows beside it (measured: Notepad's «Guardar como Markdown…» and its popup host, Paint's «Cambiar de tamaño
    y sesgar», Word's «¿Guardar los cambios…?»). A part of the window's own layout always leaves something uncovered:
    a console's document window starts below the menus and the toolbar (mmc: 65 px under the top, the band ends at
    39), a docked pane or a side panel leaves the rest of the width or the height (OBS's docks, Word's «Navegación»)."""

    window = view.get("window") if isinstance(view, dict) and isinstance(view.get("window"), dict) else {}
    outer, rect = window.get("rect"), control.get("rect")
    if _area(outer) <= 0 or _area(rect) <= 0:
        return False
    try:
        wx, wy, ww, wh = (float(outer[key]) for key in ("x", "y", "w", "h"))
        x, y, w, h = (float(rect[key]) for key in ("x", "y", "w", "h"))
    except (KeyError, TypeError, ValueError):
        return False
    band = _title_band(view)
    caption_bottom = band[1] if band is not None else wy + _CAPTION_FALLBACK
    tolerance = _EDGE_TOLERANCE
    return (
        x <= wx + tolerance and x + w >= wx + ww - tolerance and y + h >= wy + wh - tolerance
        and y <= caption_bottom + tolerance
    )


# Revisión 2 de ronda 24: the caption's height assumed when the view shows no frame button, and the pixels a layer's
# edge may stand off the window's edge and still cover it (Paint's dialog starts at 38 under a window at 0).
_CAPTION_FALLBACK = _ONE_LINE_HEIGHT / 2
_EDGE_TOLERANCE = 8.0


def _dialog_bounds(view: dict, history: list[dict]) -> tuple[bool, object]:
    """Ronda 24 (t-form-3, t-file-1): a dialog drawn over the window: a ``Window`` control that is not the window
    itself and covers it (``_covers_the_window``; revisión 2: a console's document window, a docked pane or a side
    panel is part of the window, never a dialog). (False, None) without one; (True, where it is drawn) when one of them
    appeared with the last act of the mission (the shell's ``appeared``; any of them, not only the first: a popup host
    is listed before the dialog it carries) and has a rectangle; (True, None) for one the mission did not bring: then
    nothing is unfolded blind."""

    controls = view.get("controls") if isinstance(view, dict) else None
    window = view.get("window") if isinstance(view, dict) and isinstance(view.get("window"), dict) else {}
    title = fold(window.get("title")).strip()
    dialogs = [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and control.get("kind") == "Window" and str(control.get("name") or "").strip()
        and fold(control.get("name")).strip() != title and _covers_the_window(control, view)
    ]
    if not dialogs:
        return False, None
    last = history[-1] if history and isinstance(history[-1], dict) else {}
    brought = _appeared(last) if last.get("ok") is True else frozenset()
    for dialog in dialogs:
        if fold(dialog.get("name")).strip() in brought and _area(dialog.get("rect")) > 0:
            # A layer covers the whole window, the window's own controls behind it too: the dialog is drawn where the
            # controls it brought are (the box around them inside the layer), the layer when none has a rectangle.
            parts = [
                control["rect"] for control in (controls if isinstance(controls, list) else [])
                if isinstance(control, dict) and control.get("kind") != "Window" and _area(control.get("rect")) > 0
                and fold(control.get("name")).strip() in brought and _inside(control.get("rect"), dialog.get("rect"))
            ]
            if not parts:
                return True, dialog.get("rect")
            left = min(float(rect["x"]) for rect in parts)
            top = min(float(rect["y"]) for rect in parts)
            right = max(float(rect["x"]) + float(rect["w"]) for rect in parts)
            bottom = max(float(rect["y"]) + float(rect["h"]) for rect in parts)
            return True, {"x": left, "y": top, "w": right - left, "h": bottom - top}
    return True, None


def _tab_names_the_window(tab: dict, view: dict) -> bool:
    """The selected tab names the window: the title's first part is in the tab's name, or the tab's name before its
    first period is in the title («hello world. Modificado.» in «hello world - Bloc de notas»)."""

    window = view.get("window") if isinstance(view, dict) and isinstance(view.get("window"), dict) else {}
    title = fold(window.get("title")).strip()
    name = fold(tab.get("name")).strip()
    if not title or not name:
        return False
    head = re.split(r"\s+[-–—|]\s+", title)[0].strip()
    first = name.split(". ")[0].strip(" .")
    return bool(head and head in name) or bool(first and first in title)


def _adds_a_page_of_the_window(control: dict, view: dict) -> bool:
    """Revisión 1 de ronda 24 (v3-38 against v3-07): a command that creates is opened blind only when it is the one
    that adds a page to the window's own strip of pages: the window has a strip of tabs whose one selected tab names
    the window (``_tab_names_the_window``: the window shows that page) and the command is drawn in that strip's row
    (side by side with one of its tabs; by the zone when a rectangle is missing). Its list holds the window's own
    kinds of page and settings («Nueva pestaña» beside the Terminal's tab), not objects of the person's: a creating
    command anywhere else («Nuevo correo electrónico» on a ribbon whose tabs are sections) is never opened blind."""

    controls = view.get("controls") if isinstance(view, dict) else None
    tabs = [
        tab for tab in (controls if isinstance(controls, list) else [])
        if isinstance(tab, dict) and tab.get("kind") == "TabItem" and str(tab.get("name") or "").strip()
    ]
    selected = [tab for tab in tabs if "selected" in str(tab.get("state") or "").split()]
    if len(selected) != 1 or not _tab_names_the_window(selected[0], view):
        return False

    def beside(tab: dict) -> bool:
        if _area(tab.get("rect")) > 0 and _area(control.get("rect")) > 0:
            return _same_row(tab, control)
        zone = str(control.get("zone") or "")
        return bool(zone) and str(tab.get("zone") or "") == zone

    return any(beside(tab) for tab in tabs)


def _unselected_tabs(view: dict, history: list[dict]) -> list[dict]:
    """Ronda 24 (v3-07: «Panel de lectura» lives under the unselected «Vista»): the unselected tabs of a strip of tabs
    in the window's top (zone T…), not pressed yet in this sub-goal."""

    controls = view.get("controls") if isinstance(view, dict) else None
    tabs = [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and control.get("kind") == "TabItem" and isinstance(control.get("i"), int)
        and str(control.get("name") or "").strip() and str(control.get("zone") or "").startswith("T")
    ]
    selected = [tab for tab in tabs if "selected" in str(tab.get("state") or "").split()]
    if len(tabs) < 2 or len(selected) != 1 or _tab_names_the_window(selected[0], view):
        # A strip whose selected tab names the window is one of the person's documents or pages (the editor's files,
        # the browser's pages, measured on t-menu-3): another of them is never selected blind. Nor a strip that marks
        # no tab selected: it cannot tell.
        return []
    pressed = {
        fold(step.get("label")).strip() for step in history
        if isinstance(step, dict) and step.get("operation") == "input.visible.click"
    }
    if len(pressed & {fold(tab.get("name")).strip() for tab in tabs}) >= _UNFOLDED_CONTROLS:
        # At most ``_UNFOLDED_CONTROLS`` tabs per sub-goal: never a tour of every tab.
        return []
    return [
        tab for tab in tabs
        if "selected" not in str(tab.get("state") or "").split() and fold(tab.get("name")).strip() not in pressed
        and _drawn(view, tab) and not _in_title_bar(view, tab) and _safe_to_unfold(tab)
        and not _assistant_or_creating(tab)
    ]


def _unfold_before_giving_up(
    view: dict, history: list[dict], goal: str | None, objective: str | None, last_failed: dict | None,
    *, semantic: SemanticMatcher | None = None,
) -> dict[str, object] | None:
    """Before a «none» ends the sub-goal with steps left, only what may lead to the goal and changes no value nor undoes
    what was done is opened (ronda 24). Only for a goal of a place or an order (``_unfold_kind_of_goal``); never after a
    text typed or sent in this sub-goal, never on a dialog the mission did not bring nor behind the one it did.

    For a goal that goes to a place or clicks it («ir a», «hacer clic en», revisión 2): the navigation tree's node that
    may hold it (``_tree_descent_step``), first without the encoder, else ranked with the rest. A collapsed split
    button or menu, opened by its identity (``manner`` «open», never its action) with no similarity asked (the order
    may live under a name that says nothing of it: «Configuración» under «Nueva pestaña»); a drop-down only when the
    goal names it or its value; for a place also an unselected tab of the window's strip. Ranked by similarity to the
    goal when the encoder answers (a drop-down the goal names first), else the window's top first and lists before
    tabs and the node. At most ``_UNFOLDED_CONTROLS`` lists and as many tabs per sub-goal. Never one in the title bar, the window's
    system menu, a scroll bar's part, one the safety filters refuse, a command that calls an assistant, nor the list
    of a command that creates (but the one adding a page to the window's strip of pages)."""

    kind_of_goal = _unfold_kind_of_goal(goal)
    if kind_of_goal is None or _wrote_or_sent(history):
        # Review of palanca 6 (finding 1: «leer la cantidad de palabras» opened Word's «Fuente» list): a goal that only
        # looks never opens a list blind; nor one that writes, searches or draws (ronda 24).
        return None
    has_dialog, bounds = _dialog_bounds(view, history)
    if has_dialog and bounds is None:
        return None
    controls = view.get("controls") if isinstance(view, dict) else None
    opened = [
        step for step in history if isinstance(step, dict) and step.get("operation") == "input.visible.click"
        and step.get("manner") == "open"
    ]
    target = _goal_target(goal or "")
    label = target[2] if target is not None else str(goal or "").strip()
    descent = None
    if (
        kind_of_goal == "place" and not has_dialog and target is not None and target[0] in _GOING_HEADS
        and not _said_in_other_language(label, view, objective)
    ):
        # Revisión 2 de ronda 24 (v3-07: «desactivar reading pane» opened the person's mail folders): as in the place's
        # own rule, the navigation tree is descended only for a goal that goes to a place or clicks it, said in the
        # window's language; a goal that switches or sets something never opens a node of the tree.
        descent = _tree_descent_step(label, view, history, semantic)
    lists_left = len(opened) < _UNFOLDED_CONTROLS
    opened_names = {fold(step.get("label")).strip() for step in opened}
    menu_bar = bool(_menus_to_open(view, history))
    opened_indices = {step.get("index") for step in opened if isinstance(step.get("index"), int)}
    candidates = [
        control for control in (controls if isinstance(controls, list) and lists_left else [])
        if isinstance(control, dict) and str(control.get("kind") or "") in _UNFOLD_FALLBACK_KINDS
        and "collapsed" in str(control.get("state") or "").split()
        and isinstance(control.get("i"), int) and str(control.get("name") or "").strip()
        and control.get("i") not in opened_indices and fold(control.get("name")).strip() not in opened_names
        and _drawn(view, control) and not _in_title_bar(view, control)
        and not _system_menu_off_goal(view, control, goal) and not _scroll_part(control, view)
        and _safe_to_unfold(control) and not _calls_an_assistant(control)
        # Revisión 1 de ronda 24: never the list of a command that creates, but the one that adds a page to the
        # window's own strip of pages (``_adds_a_page_of_the_window``).
        and (_creating_object(control) is None or _adds_a_page_of_the_window(control, view))
        and (str(control.get("kind") or "") != "ComboBox" or _goal_names_combo(goal, objective, control))
        # A menu bar's menus are its own routine's (``_menus_to_open``, ronda 12): never opened blind here.
        and not (str(control.get("kind") or "") == "MenuItem" and menu_bar)
    ]
    tabs = _unselected_tabs(view, history) if kind_of_goal == "place" and not has_dialog else []
    if bounds is not None:
        candidates = [control for control in candidates if _inside(control.get("rect"), bounds)]
    scores: dict[str, float] = {}
    if semantic is not None and (candidates or tabs or descent is not None) and label:
        scores = {fold(name).strip(): score for name, score in semantic.scored(label, view)}
    if descent is not None and not scores:
        # Without the encoder the tree's node goes first, as in the place's own rule (v3-26: «sistema» lives inside
        # «Registros de Windows»).
        return {**descent, "reason": REASON_UNFOLD_BEFORE_NONE}
    node = [] if descent is None else [
        {"name": descent["arguments"]["label"], "i": descent["arguments"]["index"], "kind": "TreeItem"}
    ]
    ranked = sorted(
        [(control, "list") for control in candidates] + [(tab, "tab") for tab in tabs]
        + [(item, "node") for item in node],
        # Revisión 2 de ronda 24: the tree's node, the tabs and the lists are ranked together by their similarity to the
        # goal. A drop-down left here is one the goal names: it goes first (v3-28: «Fuente» before «Pegar»).
        key=lambda pair: (
            pair[0].get("kind") != "ComboBox",
            -scores.get(fold(pair[0].get("name")).strip(), 0.0),
            not str(pair[0].get("zone") or "").startswith("T"), pair[1] != "list",
        ),
    )
    for control, what in ranked:
        if what == "node":
            return {**descent, "reason": REASON_UNFOLD_BEFORE_NONE}  # type: ignore[dict-item]
        if what == "tab":
            return _click(control, REASON_UNFOLD_TAB)
        step = _checked_manner({"i": control["i"]}, "open", view=view, goal=goal, objective=objective, history=history,
                               why=REASON_UNFOLD_BEFORE_NONE, last_failed=last_failed)
        if step.get("operation") != "none":
            return step
    return None


def _exactly_named_step(
    goal: str | None, success_check: str | None, view: dict, history: list[dict],
) -> dict[str, object] | None:
    """Ronda 24 (v3-37: the command palette chosen with the control of that very name on screen): for a goal of a place
    or an order, when exactly one control of the view carries the name the check (``born:``, ``control:``,
    ``appeared:``) or the goal's target says, its whole name is that name and its kind is one that is pressed
    (``_EXACT_NAME_KINDS``: never a slider, a check box or a field, whose press changes a value), it is pressed; not
    when another control carries the name too («Símbolo del sistema» beside «Símbolo del sistema (administrador)»),
    nor when the worker folded several controls into it («repeated»): the model decides; nor when it was pressed
    already in this sub-goal. Revisión 3: a ``born:`` or ``appeared:`` atom names what has to appear, so its name
    stands only for a control an act of this sub-goal brought (the ``appeared`` of an ok step); a control of that name
    the view already showed (the person's own tab «Símbolo del sistema», a folder «informes» that exists) is never
    pressed for it: pressing it makes nothing appear and acts on what the person did not ask."""

    if _unfold_kind_of_goal(goal) is None:
        return None
    target = _goal_target(goal or "")
    wanted = set(_check_names(success_check, ("control",)))
    brought = frozenset().union(*(
        _appeared(step) for step in history if isinstance(step, dict) and step.get("ok") is True
    ))
    wanted |= {name for name in _check_names(success_check, _TO_APPEAR_ATOMS) if name in brought}
    if target is not None and target[2].strip():
        wanted.add(fold(target[2]).strip())
    controls = view.get("controls") if isinstance(view, dict) else None
    pressed = {
        fold(step.get("label")).strip() for step in history
        if isinstance(step, dict) and step.get("operation") == "input.visible.click"
    }
    for name in sorted(wanted):
        carriers = [
            control for control in (controls if isinstance(controls, list) else [])
            if isinstance(control, dict) and name in fold(control.get("name")).strip()
        ]
        if len(carriers) != 1:
            continue
        control = carriers[0]
        kind = str(control.get("kind") or "")
        if (
            fold(control.get("name")).strip() != name or not isinstance(control.get("i"), int)
            # Revisión 1: only a kind that is pressed (``_EXACT_NAME_KINDS``), and one control, not the worker's
            # fold of several of that kind and name into one («repeated»).
            or kind not in _EXACT_NAME_KINDS or control.get("repeated")
            # Revisión 4: never a switch (``_is_switch``: a button shown on/off, Settings' «Bluetooth», a player's
            # «Repetir»): going to its place sets nothing on the way, and switching it is the switch's own rule's,
            # which reads its state first.
            or _is_switch(control)
            or name in pressed or not _drawn(view, control) or _in_title_bar(view, control)
            or not _safe_to_unfold(control, goal) or _assistant_or_creating(control)
        ):
            continue
        return _click(control, REASON_EXACT_NAME)
    return None
