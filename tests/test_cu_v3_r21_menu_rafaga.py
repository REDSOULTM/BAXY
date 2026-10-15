"""Ronda 21, palanca «ruta-de-menu-en-una-rafaga-y-menu-contextual-por-estado» (mind side).

Pasada r18: t-menu-1 (the menu act opened the context menu but the check only took the key, and the rule pressed the
context-menu key over the open menu; explorer fell), t-menu-2 («espacio vacío» had no deterministic way). The context
menu is opened first by X's own menu act, its state closes the sub-goal, and the key is only the fallback.
"""

from __future__ import annotations

from baxy_mind import cu_rules
from baxy_mind.semantic import missions

GOAL = "abrir el menu contextual de notas.txt"
EMPTY = "abrir el menu contextual de espacio vacio"

# The Explorer items view as the look reads it (t-menu-2 evidence: a named list holding the files).
EXPLORER = {
    "controls": [
        {"i": 0, "name": "Vista de elementos", "kind": "List", "rect": {"x": 200, "y": 100, "w": 900, "h": 600}},
        {"i": 1, "name": "notas.txt", "kind": "ListItem", "rect": {"x": 210, "y": 110, "w": 300, "h": 22}},
        {"i": 2, "name": "lista.txt", "kind": "ListItem", "rect": {"x": 210, "y": 134, "w": 300, "h": 22}},
        {"i": 3, "name": "Atrás", "kind": "Button", "rect": {"x": 10, "y": 10, "w": 30, "h": 30}},
    ]
}


def _menu_act(**receipt: object) -> dict:
    return {"operation": "input.visible.click", "ok": True, "label": "notas.txt", "manner": "menu", **receipt}


def test_the_context_menu_is_opened_first_by_the_things_own_menu_act() -> None:
    step = cu_rules.deterministic_step(goal=GOAL, view=EXPLORER, history=[])
    assert step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "notas.txt", "index": 1, "manner": "menu"}


def test_a_menu_act_that_opened_the_menu_presses_nothing_more() -> None:
    # t-menu-1: the receipt says the menu opened; the rule never presses the context-menu key over it.
    assert cu_rules.deterministic_step(goal=GOAL, view=EXPLORER, history=[_menu_act(opened=True)]) is None
    # A menu the view shows after the act is the same state.
    shown = {"controls": [*EXPLORER["controls"], {"i": 4, "name": "Contexto", "kind": "Menu"}]}
    assert cu_rules.deterministic_step(goal=GOAL, view=shown, history=[_menu_act()]) is None


def test_a_failed_menu_act_falls_back_to_choosing_and_the_key() -> None:
    # Counter-case: the menu act failed (or opened nothing): the click that chooses, then the context-menu key.
    failed = [{"operation": "input.visible.click", "ok": False, "label": "notas.txt", "manner": "menu",
               "error": "visible_control_identity_stale"}]
    chose = cu_rules.deterministic_step(goal=GOAL, view=EXPLORER, history=failed)
    assert chose["operation"] == "input.visible.click" and "manner" not in chose["arguments"]
    chosen = [*failed, {"operation": "input.visible.click", "ok": True, "label": "notas.txt"}]
    key = cu_rules.deterministic_step(goal=GOAL, view=EXPLORER, history=chosen)
    assert key["operation"] == "input.key.press" and key["arguments"]["key"] == "context_menu"
    nothing = [_menu_act(opened=False)]
    assert cu_rules.deterministic_step(goal=GOAL, view=EXPLORER, history=nothing)["arguments"].get("manner") is None


def test_the_key_is_never_pressed_with_a_menu_open() -> None:
    chosen = [{"operation": "input.visible.click", "ok": True, "label": "notas.txt"}]
    shown = {"controls": [*EXPLORER["controls"], {"i": 4, "name": "Contexto", "kind": "Menu"}]}
    assert cu_rules.deterministic_step(goal=GOAL, view=shown, history=chosen) is None


def test_an_opened_menu_is_the_state_whatever_an_old_receipt_said_of_the_front() -> None:
    # Estabilización D: the mission's window holds the front while it acts (no front handed back between the act and
    # its look), so an opened menu stays open; a receipt that still says «frontHeld: false» (t-file-4, before) is no
    # lost opening any more, and nothing more is pressed over it.
    kept = [_menu_act(opened=True, frontHeld=False)]
    assert cu_rules.deterministic_step(goal=GOAL, view=EXPLORER, history=kept) is None


def test_an_empty_space_is_the_menu_of_the_list_holding_the_items() -> None:
    # t-menu-2: the container, never one of its items.
    step = cu_rules.deterministic_step(goal=EMPTY, view=EXPLORER, history=[])
    assert step["arguments"] == {"label": "Vista de elementos", "index": 0, "manner": "menu"}
    assert cu_rules.deterministic_step(goal=EMPTY, view=EXPLORER, history=[_menu_act(label="Vista de elementos", opened=True)]) is None


def test_an_empty_space_without_a_list_holding_items_is_the_models_step() -> None:
    # Counter-case: a window with no list that holds items, or an empty list.
    bare = {"controls": [{"i": 0, "name": "Lienzo", "kind": "Pane", "rect": {"x": 0, "y": 0, "w": 800, "h": 600}},
                         {"i": 1, "name": "Guardar", "kind": "Button", "rect": {"x": 5, "y": 5, "w": 20, "h": 20}}]}
    assert cu_rules.deterministic_step(goal=EMPTY, view=bare, history=[]) is None
    empty_list = {"controls": [{"i": 0, "name": "Vista de elementos", "kind": "List", "rect": {"x": 0, "y": 0, "w": 800, "h": 600}}]}
    assert cu_rules.deterministic_step(goal=EMPTY, view=empty_list, history=[]) is None
    # Its menu act failed: the model's step, never the key on whatever is chosen.
    failed = [{"operation": "input.visible.click", "ok": False, "label": "Vista de elementos", "manner": "menu"}]
    assert cu_rules.deterministic_step(goal=EMPTY, view=EXPLORER, history=failed) is None


def test_the_context_menu_check_takes_the_state_the_menu_act_left_on_its_own_target() -> None:
    # Revisión 1 (hallazgo 3): the atom carries X, so the shell takes only a menu opened on X.
    assert missions.CONTEXT_MENU_CHECK.split("|") == [
        "stepDone:input.key.press:context_menu", "stepDone:input.key.press:shift_f10"]
    assert missions.context_menu_check("notas.txt").split("|") == [
        "stepDone:input.key.press:context_menu", "stepDone:input.key.press:shift_f10", "menuOpened:notas.txt"]
    # An empty space's names no control: the shell takes the menu act on a container only.
    assert missions.context_menu_check(missions.EMPTY_SPACE_TARGET).endswith("|menuOpened:")
    steps = missions.mission_request(
        "en el Explorador de archivos haceme clic derecho en notas.txt y abrime las propiedades", ("Explorador de archivos",))
    assert steps is not None and steps.steps[0].success_check == missions.context_menu_check("notas.txt")


def test_a_menu_left_open_on_another_element_is_none_of_xs() -> None:
    # Revisión 1 (hallazgo 3): the model's menu act on lista.txt opened a menu; «notas.txt»'s is still to open, by its own
    # menu act, never cut short by the other element's.
    other = [_menu_act(label="lista.txt", index=2, opened=True)]
    step = cu_rules.deterministic_step(goal=GOAL, view=EXPLORER, history=other)
    assert step is not None and step["arguments"] == {"label": "notas.txt", "index": 1, "manner": "menu"}
    shown = {"controls": [*EXPLORER["controls"], {"i": 4, "name": "Contexto", "kind": "Menu"}]}
    assert cu_rules.deterministic_step(goal=GOAL, view=shown, history=[_menu_act(label="lista.txt")]) is not None
    # Counter-case: the same receipt on X itself closes the rule.
    assert cu_rules.deterministic_step(goal=GOAL, view=EXPLORER, history=[_menu_act(opened=True)]) is None


def test_an_empty_spaces_menu_is_only_the_containers() -> None:
    # Revisión 1 (hallazgo 3): a menu opened on an item is no empty space's; the container's is.
    on_item = [_menu_act(label="notas.txt", opened=True)]
    step = cu_rules.deterministic_step(goal=EMPTY, view=EXPLORER, history=on_item)
    assert step is not None and step["arguments"] == {"label": "Vista de elementos", "index": 0, "manner": "menu"}
    on_list = [_menu_act(label="Vista de elementos", opened=True)]
    assert cu_rules.deterministic_step(goal=EMPTY, view=EXPLORER, history=on_list) is None
