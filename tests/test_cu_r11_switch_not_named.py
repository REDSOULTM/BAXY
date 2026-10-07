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


def test_put_mode_without_a_switch_of_that_name_goes_to_the_mode() -> None:
    view = {
        "window": {"title": "Calculadora", "process": "calc"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Abrir navegación", "state": ""},
            {"i": 1, "kind": "Button", "name": "Alternar grados", "state": "off"},
        ],
        "text": {},
    }
    step = computer_use.deterministic_step(goal="activar modo programador", view=view, history=[])
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"]["label"] == "Abrir navegación"


def test_put_mode_with_a_switch_of_that_name_is_left_to_the_switch_rules() -> None:
    view = {
        "window": {"title": "Ajustes", "process": "ajustes"},
        "controls": [{"i": 0, "kind": "Button", "name": "Modo oscuro", "state": "off", "toggle": True}],
        "text": {},
    }
    step = computer_use.deterministic_step(goal="activar modo oscuro", view=view, history=[])
    assert step is None or step["arguments"].get("label") != "Abrir navegación"


def test_the_navigation_button_goes_before_a_name_clicked_by_label_alone() -> None:
    controls = [{"i": 0, "kind": "Button", "name": "Abrir navegación", "state": ""}]
    controls += [{"i": i, "kind": "Button", "name": f"Tecla {i}", "state": ""} for i in range(1, 60)]
    view = {"window": {"title": "Calculadora", "process": "calc"}, "controls": controls, "text": {}, "controlCount": 90}
    step = computer_use.deterministic_step(goal="ir a programador", view=view, history=[])
    assert step is not None and step["arguments"]["label"] == "Abrir navegación"
    opened = [{"step": 1, "operation": "input.visible.click", "label": "Abrir navegación", "ok": True}]
    after = computer_use.deterministic_step(goal="ir a programador", view=view, history=opened)
    assert after is not None and after["arguments"].get("label") == "programador"
