"""Live y1 (2026-10-07): «poné el modo programador» clicked the Calculator's «Alternar grados» on the way."""

from baxy_mind import computer_use


def _view() -> dict:
    controls = [
        {"i": 0, "kind": "Button", "name": "Abrir navegación", "state": ""},
        {"i": 1, "kind": "Button", "name": "Alternar grados", "state": "off"},
        {"i": 2, "kind": "ListItem", "name": "Programador", "state": ""},
        {"i": 3, "kind": "Button", "name": "Bluetooth", "state": "off"},
    ]
    return {"window": {"title": "Calculadora", "process": "calc"}, "controls": controls, "text": {}}


def _decide(goal: str, label: str, index: int) -> dict:
    raw = {"act": "click", "label": label, "i": index, "why": "probar"}
    return computer_use.validate_decision(raw, view=_view(), last_failed=None, application_names=[], goal=goal, history=[])


def test_a_setting_goal_never_flips_a_switch_it_does_not_name() -> None:
    step = _decide("activar modo programador", "Alternar grados", 1)
    assert step["operation"] == "none" and step.get("code") == "changes_a_setting"


def test_the_switch_the_goal_names_is_pressed() -> None:
    step = _decide("activar bluetooth", "Bluetooth", 3)
    assert step["operation"] == "input.visible.click"


def test_a_setting_goal_still_clicks_what_is_not_a_switch() -> None:
    step = _decide("activar modo programador", "Programador", 2)
    assert step["operation"] == "input.visible.click"
