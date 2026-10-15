"""Moving through a window's navigation and content: a long list scrolled to an item, the navigation tree
opened toward a place, the current node first, and the content items that open (folders) or run.
"""

from __future__ import annotations

import re

from .semantic.missions import fold, label_alternatives, names_a_file
from .cu_view import (
    _CONTENT_KINDS, _area, _drawn, _in_title_bar, _inside, _is_switch, _list_holding_items, _vertical_centre,
    closed_menu_entry, find_control, is_content_item, label_names,
)
from .semantic.limits import LIMIT_CODE, limits_data
from .cu_acts import _none, _reveal_arguments
from .cu_window import _window_fold
from .cu_history import _manner_opened
from .cu_unasked import _safe_to_unfold
from .cu_meaning import ENCODER_READY, SemanticMatcher


def _on_screen(view: dict) -> dict:
    """The view without the entries of closed menus (``closed_menu_entry``): what is on screen."""

    controls = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(controls, list):
        return view
    return {**view, "controls": [control for control in controls if not closed_menu_entry(control)]}


def _reveal_step(target: str, view: dict, history: list[dict]) -> dict[str, object] | None:
    """«mostrar X» (bajá en la lista hasta X): the list that holds the items scrolled down while X is not on screen
    and each scroll moves it; shown (``control:=X``) is the shell's check, so nothing is pressed once X is there.
    Estabilización L4 (en vivo t-scroll-2: the wheel did not move the Character Map's grid and the model typed into its
    search; t-scroll-3): a list the wheel no longer moves, or moved the turns a sub-goal may spend (data
    «longListScrolls»), without showing X is the long list limit, said as such and never handed to the model."""

    names = (target, *label_alternatives(target))
    # Revision 3 of ronda 20b (B-A): a closed menu's entry («Herramientas › Opciones...») is listed, never shown; the
    # list is still scrolled until the item itself is on screen.
    shown = _on_screen(view)
    if any(find_control(shown, name) is not None for name in names):
        return None
    scrolls = [step for step in history if step.get("operation") == "input.scroll"]
    # First by its name through UI Automation (the model's «reveal» act, the same step): no wheel and no front.
    if not any(step.get("label") for step in scrolls):
        return {"operation": "input.scroll", "arguments": _reveal_arguments(target), "reason": "traigo el elemento a la vista"}
    # A list whose patterns could not bring it: the wheel over the list, while each turn moves it.
    scrolls = [step for step in scrolls if not step.get("label")]
    if len(scrolls) >= int(limits_data()["longListScrolls"]) or any(
        step.get("ok") is not True or step.get("changed") is False or step.get("surfaceChanged") is False for step in scrolls
    ):
        return _none("la lista no acaba", code=LIMIT_CODE + "long_list")
    arguments: dict[str, object] = {"direction": "down", "amount": 5}
    holder = _list_holding_items(view)
    if holder is not None:
        arguments["index"] = holder
    return {"operation": "input.scroll", "arguments": arguments, "reason": "bajo en la lista hasta que se vea"}


_NAVIGATION_ITEM_KINDS = frozenset({"TreeItem", "ListItem", "TabItem"})


def _navigation_item(control: dict, view: dict) -> bool:
    """An item of the window's navigation: a tree, list or tab item in the left column (zones L, TL, BL) that is not
    an item of a content view (``is_content_item``)."""

    return (
        str(control.get("kind")) in _NAVIGATION_ITEM_KINDS and str(control.get("zone") or "").endswith("L")
        and not is_content_item(control, view)
    )


# Ronda 21, bajada por el árbol de navegación (v3-26, v3-23: «Sistema» lives under the collapsed «Registros de Windows»
# and nothing opened it with the encoder cold). At most this many nodes are opened per sub-goal, at most this many
# levels below the place the window is in.
_TREE_DESCENT_NODES = 4
_TREE_DESCENT_LEVELS = 2
REASON_DESCENT = "el destino no está en la vista: abro el nodo del árbol de navegación que puede contenerlo"
REASON_DESCENT_FIRST = "el destino sólo está en el contenido del nodo actual cerrado: lo abro antes de pulsarlo"
# A node whose own type says it is a network place or a drive: opening it reads a disk or the network (slow, and it
# may wake a drive or ask for credentials); never opened blind.
_SLOW_NODE_TYPE = re.compile(r"(?<!\w)(?:red|network|unidad|drive|disco|disk|volumen|volume)(?!\w)")


def _navigation_tree_nodes(view: dict) -> list[dict]:
    """The tree items of the window's navigation column (``_navigation_item``) the view hands out with an index."""

    controls = view.get("controls") if isinstance(view, dict) else None
    return [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and control.get("kind") == "TreeItem" and isinstance(control.get("i"), int)
        and str(control.get("name") or "").strip() and _navigation_item(control, view)
    ]


def _tree_indent(control: dict) -> float | None:
    rect = control.get("rect")
    if not isinstance(rect, dict) or _area(rect) <= 0:
        return None
    x = rect.get("x")
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _openable_tree_node(control: dict, view: dict) -> bool:
    """A collapsed navigation tree node that may be opened without the model: drawn, out of the title bar, past the
    safety filters of an unfolding, and no network place or drive by its own type."""

    return (
        "collapsed" in str(control.get("state") or "").split() and _drawn(view, control)
        and not _in_title_bar(view, control) and _safe_to_unfold(control)
        and _SLOW_NODE_TYPE.search(fold(control.get("itemType"))) is None
    )


def _tree_descent_step(
    target: str, view: dict, history: list[dict], semantic: SemanticMatcher | None,
) -> dict[str, object] | None:
    """Ronda 21 (v3-26): the place a goal goes to or clicks is not in the view and the window's navigation is a tree
    with collapsed nodes: what a node holds appears only when it opens. The node the window is in first (when it is
    still collapsed), then the others shallow first (by their indentation, when the view gives rectangles), the most
    similar to the place first when the encoder is ready, else in tree order; each opened by its identity (``manner``
    «open»: ExpandCollapse, nothing is pressed), at most ``_TREE_DESCENT_NODES`` per sub-goal and
    ``_TREE_DESCENT_LEVELS`` levels below the place. Once the place shows, the goal's own rule clicks it. A window with
    no collapsed node in its navigation column (a calculator, a settings window) is left as it was.

    Pendiente (revision 1): the nodes this descent opened stay open after the mission; ``ListsLeftOpen`` (the App)
    skips tree items on purpose, since collapsing an ancestor of the node the window ends in moves its selection. A
    collapse of only the opened nodes that hold no selection needs the tree's parentage, which the view does not give."""

    if names_a_file(target):
        # Revision 1 (finding 1): a file is never a node of a navigation tree; it is a row of a folder's content.
        return None
    nodes = _navigation_tree_nodes(view)
    opened = _manner_opened(history)
    if not nodes or len(opened) >= _TREE_DESCENT_NODES:
        return None
    opened_names = {fold(step.get("label")).strip() for step in opened}
    opened_indices = {step.get("index") for step in opened if isinstance(step.get("index"), int)}
    indents = sorted({round(indent / 4) for node in nodes if (indent := _tree_indent(node)) is not None})
    selected = [node for node in nodes if "selected" in str(node.get("state") or "").split()]
    base = 0
    if selected and (indent := _tree_indent(selected[0])) is not None and round(indent / 4) in indents:
        base = indents.index(round(indent / 4))

    def level(node: dict) -> int:
        indent = _tree_indent(node)
        return indents.index(round(indent / 4)) if indent is not None and round(indent / 4) in indents else 0

    candidates = [
        node for node in nodes
        if _openable_tree_node(node, view) and node.get("i") not in opened_indices
        and fold(node.get("name")).strip() not in opened_names and level(node) <= base + _TREE_DESCENT_LEVELS
    ]
    if not candidates:
        return None
    scores: dict[str, float] = {}
    if semantic is not None and semantic.state == ENCODER_READY:
        scores = {fold(name).strip(): score for name, score in semantic.scored(target, view)}
    candidates.sort(key=lambda node: (
        "selected" not in str(node.get("state") or "").split(), level(node),
        -scores.get(fold(node.get("name")).strip(), 0.0), node["i"],
    ))
    node = candidates[0]
    return {"operation": "input.visible.click",
            "arguments": {"label": str(node.get("name") or ""), "index": node["i"], "manner": "open"},
            "reason": REASON_DESCENT}


def _current_node_first(control: dict, view: dict, history: list[dict]) -> dict[str, object] | None:
    """Ronda 21 (v3-23): the place a goal goes to («ir a») is only a row of the content (a list or data item) while
    the navigation node the window is in is still collapsed: the row only shows what the node holds, and its click only
    chooses it. The node opens first, by its identity, once; its own child (a tree item of the same name) is then the
    place. Never for a file or what runs: opening a node shows its children, not its files. A click on the row
    («hacer clic en») never comes here: it presses the row."""

    if str(control.get("kind")) not in _CONTENT_KINDS or not is_content_item(control, view):
        return None
    name = str(control.get("name") or "")
    if names_a_file(name) or _runs_when_opened(control):
        return None
    opened = _manner_opened(history)
    if len(opened) >= _TREE_DESCENT_NODES:
        return None
    opened_names = {fold(step.get("label")).strip() for step in opened}
    node = next((
        node for node in _navigation_tree_nodes(view)
        if "selected" in str(node.get("state") or "").split() and _openable_tree_node(node, view)
        and fold(node.get("name")).strip() not in opened_names
    ), None)
    if node is None:
        return None
    return {"operation": "input.visible.click",
            "arguments": {"label": str(node.get("name") or ""), "index": node["i"], "manner": "open"},
            "reason": REASON_DESCENT_FIRST}


def _without_name(view: dict, name: str) -> dict:
    """The view without the controls and written lines whose whole folded name is ``name``."""

    if not isinstance(view, dict):
        return view
    wanted = fold(name)
    controls = view.get("controls")
    text = view.get("text")
    return {
        **view,
        "controls": [
            control for control in controls if not (isinstance(control, dict) and fold(control.get("name")) == wanted)
        ] if isinstance(controls, list) else controls,
        "text": {
            zone: [line for line in lines if fold(line) != wanted] if isinstance(lines, list) else lines
            for zone, lines in text.items()
        } if isinstance(text, dict) else text,
    }


def _names_a_switch(view: dict, line: str) -> bool:
    """A written line that is a switch's own name (the same words, a typo apart): clicking it presses the switch."""

    controls = view.get("controls") if isinstance(view, dict) else None
    return any(
        isinstance(control, dict) and _is_switch(control)
        and label_names(str(control.get("name") or ""), line) and label_names(line, str(control.get("name") or ""))
        for control in (controls if isinstance(controls, list) else [])
    )


# A file that runs, installs or launches something when opened.
_RUNS_WHEN_OPENED = re.compile(r"\.(?:exe|msi|bat|cmd|ps1|vbs|js|lnk|appx|msix|reg|hta|scr|cpl|jar|com|pif)(?!\w)")
# What a file view calls a folder or a drive: the item's own type (the App's ``itemType``), or the type cell of its
# row in a details view.
_CONTAINER_TYPE = re.compile(r"(?<!\w)(?:carpeta|folder|directorio|directory|unidad|drive)")
_CONTAINER_CELL = frozenset({"carpeta de archivos", "file folder"})


# Only an uninstall offered by the window vetoes Enter on a chosen item (a list of programs); delete-like commands are
# on every file view (Explorer's «Eliminar (Supr)») and only count when they are the chosen item's own name.
_UNINSTALL_NAME = re.compile(r"(?<!\w)(?:desinstal\w*|uninstall\w*)(?!\w)")


def _offers_uninstall(view: dict) -> bool:
    controls = view.get("controls") if isinstance(view, dict) else None
    return any(
        isinstance(control, dict) and _UNINSTALL_NAME.search(fold(control.get("name"))) is not None
        for control in (controls if isinstance(controls, list) else ())
    )


def _runs_when_opened(control: dict) -> bool:
    return _RUNS_WHEN_OPENED.search(fold(control.get("name"))) is not None


def _is_container(control: dict, view: dict) -> bool:
    """Positive evidence that the item is a folder or a drive (opening it shows what it holds and starts nothing):
    its ``itemType`` says so, or a control on its row (vertical centres within half the item's height) is the
    type cell «Carpeta de archivos» / «File folder». Without it, nothing tells a folder from an application."""

    item_type = fold(control.get("itemType"))
    if item_type:
        # The item says what it is: only a folder or a drive opens without running anything.
        return _CONTAINER_TYPE.search(item_type) is not None
    centre, height = _vertical_centre(control.get("rect"))
    controls = view.get("controls") if isinstance(view, dict) else None
    if centre is None or not isinstance(controls, list):
        return False
    for other in controls:
        if other is control or not isinstance(other, dict):
            continue
        other_centre, _ = _vertical_centre(other.get("rect"))
        if other_centre is None or abs(other_centre - centre) > height / 2 or not _inside(other.get("rect"), control.get("rect")):
            continue
        if fold(other.get("name")).strip() in _CONTAINER_CELL or fold(other.get("value")).strip() in _CONTAINER_CELL:
            return True
    return False


def _content_item_chosen(view: dict, history: list[dict], names: tuple[str, ...]) -> dict | None:
    """The content item named as the place that the last step, a verified click on it, left selected while the
    window's title does not name the place yet; None otherwise."""

    last = history[-1] if history and isinstance(history[-1], dict) else None
    if last is None or last.get("operation") != "input.visible.click" or last.get("ok") is not True:
        return None
    if not any(label_names(name, str(last.get("label") or "")) for name in names):
        return None
    window = view.get("window") if isinstance(view, dict) else None
    title = _window_fold(window.get("title")) if isinstance(window, dict) else ""
    if any(re.search(rf"(?<!\w){re.escape(fold(name))}(?!\w)", title) for name in names if fold(name)):
        return None
    controls = view.get("controls") if isinstance(view, dict) else None
    for control in controls if isinstance(controls, list) else ():
        if (
            isinstance(control, dict)
            and is_content_item(control, view)
            and "selected" in str(control.get("state") or "").split()
            and any(fold(control.get("name")) == fold(name) for name in names)
        ):
            return control
    return None
