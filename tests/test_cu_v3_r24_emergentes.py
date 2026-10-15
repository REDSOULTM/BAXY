"""Ronda 24, palanca «emergentes-del-dueno-y-menus-que-se-reabren» (mind side).

Pasada r23: t-menu-3 (opening the menu bar's «Ver» never counted as its click, so «stepDone:…:view» never closed) and
t-menu-2 (the empty space's menu was opened on the navigation tree, which held more items than the folder's files).
"""

from __future__ import annotations

from baxy_mind import cu_view
from baxy_mind import cu_acts
from baxy_mind import cu_history
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind import cu_step_prompt

EMPTY = "abrir el menu contextual de espacio vacio"


def _open(**receipt: object) -> dict:
    return {"operation": "input.visible.click", "ok": True, "label": "Ver", "manner": "open", **receipt}


def test_opening_a_menu_entry_whose_only_action_is_to_open_is_its_press() -> None:
    # t-menu-3's receipt: «Ver» (MenuItem) opened by its manner, method expand, read open.
    menu_bar = _open(kind="MenuItem", method="expand", opened=True, changed=False)
    assert not cu_history.only_opened(menu_bar)
    # The App's verdict in the history handed to the mind says the same.
    assert not cu_history.only_opened(_open(kind="MenuItem", openPress=True))
    assert cu_history._clicks_on([menu_bar], "Ver") == [menu_bar]


def test_an_arrow_a_combo_box_or_a_context_menu_stay_only_opened() -> None:
    # Contracases (v3-37): the split button «Nueva pestaña» acts by itself; its arrow is only opened.
    assert cu_history.only_opened(_open(label="Nueva pestaña", kind="SplitButton", method="expand", opened=True))
    # A combo box's list chooses no value.
    assert cu_history.only_opened(_open(label="Tamaño", kind="ComboBox", method="expand", opened=True))
    # A context menu of a menu entry presses nothing.
    assert cu_history.only_opened(_open(kind="MenuItem", manner="menu", method="expand", opened=True))
    # A menu entry the receipt did not read open (an expand that showed nothing) is no press.
    assert cu_history.only_opened(_open(kind="MenuItem", method="expand", opened=False))
    assert cu_history.only_opened(_open(kind="MenuItem", method="invoke", opened=True))


# t-menu-2's Explorer: the navigation tree holds more items than the folder's file list.
_TREE_ITEMS = [
    {"i": 10 + n, "name": f"Carpeta {n}", "kind": "TreeItem", "rect": {"x": 10, "y": 100 + 22 * n, "w": 180, "h": 20}}
    for n in range(12)
]
_FILES = [
    {"i": 40 + n, "name": f"archivo{n}.txt", "kind": "ListItem", "rect": {"x": 260, "y": 110 + 22 * n, "w": 300, "h": 20}}
    for n in range(4)
]
EXPLORER = {
    "controls": [
        {"i": 0, "name": "Control de árbol de espacios de nombres", "kind": "Tree", "rect": {"x": 0, "y": 90, "w": 200, "h": 600}},
        {"i": 1, "name": "Vista de elementos", "kind": "List", "rect": {"x": 250, "y": 100, "w": 900, "h": 600}},
        *_TREE_ITEMS,
        *_FILES,
    ]
}


def test_the_empty_space_is_the_file_list_even_when_the_tree_holds_more() -> None:
    assert cu_view._list_holding_items(EXPLORER, empty_space=True) == 1
    step = cu_rules.deterministic_step(goal=EMPTY, view=EXPLORER, history=[])
    assert step is not None and step["arguments"] == {"label": "Vista de elementos", "index": 1, "manner": "menu"}


def test_a_pane_around_both_never_beats_the_list() -> None:
    framed = {"controls": [
        {"i": 2, "name": "Marco", "kind": "Pane", "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}}, *EXPLORER["controls"]]}
    assert cu_view._list_holding_items(framed, empty_space=True) == 1


def test_the_content_surface_with_items_comes_first() -> None:
    body = {"controls": [
        {"i": 3, "name": "Contenido", "kind": "Pane", "body": True, "rect": {"x": 250, "y": 100, "w": 900, "h": 600}},
        *EXPLORER["controls"]]}
    assert cu_view._list_holding_items(body, empty_space=True) == 3


def test_a_tree_alone_is_still_the_holder() -> None:
    # Contracase: a registry editor's only container with items is its tree.
    regedit = {"controls": [
        {"i": 0, "name": "Árbol", "kind": "Tree", "rect": {"x": 0, "y": 90, "w": 200, "h": 600}},
        {"i": 1, "name": "Valores", "kind": "List", "rect": {"x": 250, "y": 100, "w": 900, "h": 600}},
        *_TREE_ITEMS,
    ]}
    assert cu_view._list_holding_items(regedit, empty_space=True) == 0


def test_a_named_item_still_takes_its_own_menu() -> None:
    # Contracase: «clic derecho en archivo1.txt» names an item: the named branch, never the container.
    step = cu_rules.deterministic_step(goal="abrir el menu contextual de archivo1.txt", view=EXPLORER, history=[])
    assert step is not None and step["arguments"] == {"label": "archivo1.txt", "index": 41, "manner": "menu"}


# Review 1 of ronda 24 (finding 2): a registry editor's tree of 25 keys beside a list of values with one entry.
_KEYS = [
    {"i": 10 + n, "name": f"Clave {n}", "kind": "TreeItem", "rect": {"x": 10, "y": 100 + 22 * n, "w": 180, "h": 20}}
    for n in range(25)
]
REGISTRY = {
    "controls": [
        {"i": 0, "name": "Árbol", "kind": "Tree", "rect": {"x": 0, "y": 90, "w": 200, "h": 800}},
        {"i": 1, "name": "Valores", "kind": "List", "rect": {"x": 250, "y": 100, "w": 900, "h": 600}},
        *_KEYS,
        {"i": 60, "name": "(Predeterminado)", "kind": "ListItem", "rect": {"x": 260, "y": 110, "w": 300, "h": 20}},
    ]
}


def test_the_wheel_turns_the_tree_that_holds_the_most_items() -> None:
    # Contracase of the empty space's rank: a key of the tree off screen is brought by turning the tree, never the
    # list of values that does not move.
    assert cu_view._list_holding_items(REGISTRY) == 0
    assert cu_lookup._scroll_step(REGISTRY, []) == {
        "operation": "input.scroll",
        "arguments": {"direction": "down", "amount": 5, "index": 0},
        "reason": cu_acts._REASON_FIND,
    }
    # The Explorer's wheel, too, goes over the container with the most items, as before the rank.
    assert cu_view._list_holding_items(EXPLORER) == 0
    # The empty space of the very same view is still the list of values.
    assert cu_view._list_holding_items(REGISTRY, empty_space=True) == 1


def test_a_body_is_no_wheel_holder_by_itself() -> None:
    body = {"controls": [
        {"i": 3, "name": "Contenido", "kind": "Pane", "body": True, "rect": {"x": 250, "y": 100, "w": 900, "h": 600}},
        *EXPLORER["controls"]]}
    assert cu_view._list_holding_items(body) == 0


def test_a_trimmed_view_keeps_both_holders() -> None:
    filler = [{"i": 200 + n, "name": f"Botón {n}", "kind": "Button"} for n in range(40)]
    kept = cu_step_prompt._ranked_controls([*filler, *REGISTRY["controls"]], "clic derecho en un espacio vacío", 12)
    indices = {control.get("i") for control in kept}
    assert {0, 1} <= indices
