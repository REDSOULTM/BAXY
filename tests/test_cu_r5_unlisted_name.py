"""The goal's own name clicked by label alone when the view lists only part of the window (cu-r5)."""

from baxy_mind import computer_use


def _tools(count: int = 60, total: int | None = 118, extra: list[dict] | None = None) -> dict:
    # A drawing window whose listing stops at the App's limit: tools and shapes, never the palette's colours.
    controls = [
        {"i": 0, "kind": "Button", "name": "Lápiz", "state": "off"},
        {"i": 1, "kind": "Button", "name": "Selector de colores", "state": "off"},
        {"i": 2, "kind": "ListItem", "name": "Rectángulo redondeado", "state": ""},
        {"i": 3, "kind": "Button", "name": "Rectángulo redondeado", "state": "off"},
        *(extra or []),
    ]
    controls += [{"i": index, "kind": "Button", "name": f"Forma {index}", "state": "off"} for index in range(len(controls), count)]
    view = {
        "window": {"title": "Sin título - Dibujo", "process": "dibujo", "focused": None},
        "controls": controls,
        "text": {"TR": ["Colores", "Capas"]},
    }
    if total is not None:
        view["controlCount"] = total
    return view


def _failed(step: int, label: str) -> dict:
    return {"step": step, "operation": "input.visible.click", "label": label, "ok": False, "error": "visible_button_not_found"}


def test_a_colour_beyond_the_listed_controls_is_clicked_by_its_own_name() -> None:
    step = computer_use.deterministic_step(goal="seleccionar rojo", view=_tools(), history=[])
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "rojo"}
    assert step["reason"] == computer_use.REASON_BY_NAME


def test_the_persons_word_first_then_the_other_language_name_once_each() -> None:
    first = computer_use.deterministic_step(goal="seleccionar blue", view=_tools(), history=[])
    assert first is not None and first["arguments"] == {"label": "blue"}
    # «blue» found nothing on a Spanish window: the other language's name is the next step.
    second = computer_use.deterministic_step(goal="seleccionar blue", view=_tools(), history=[_failed(1, "blue")])
    assert second is not None and second["arguments"] == {"label": "azul"}
    # Both tried and failed: nothing more by name; the model decides (never the same name again).
    third = computer_use.deterministic_step(
        goal="seleccionar blue", view=_tools(), history=[_failed(1, "blue"), _failed(2, "azul")],
    )
    assert third is None or third["arguments"].get("label") not in {"blue", "azul"}


def test_a_name_clicked_and_not_reached_is_not_clicked_again() -> None:
    done = [{"step": 1, "operation": "input.visible.click", "label": "rojo", "ok": True}]
    step = computer_use.deterministic_step(goal="seleccionar rojo", view=_tools(), history=done)
    assert step is None or fold_label(step) not in {"rojo"}
    after = computer_use.deterministic_step(goal="seleccionar rojo", view=_tools(), history=[*done, _failed(2, "red")])
    assert after is None or fold_label(after) not in {"rojo", "red"}


def fold_label(step: dict) -> str:
    return str((step.get("arguments") or {}).get("label") or "").lower()


def test_a_view_that_lists_the_whole_tree_leaves_the_step_to_the_model() -> None:
    # Everything the window holds is listed: a name not there is not hidden beyond the limit.
    assert computer_use.deterministic_step(goal="seleccionar rojo", view=_tools(count=10, total=10), history=[]) is None
    # Without controlCount a short listing is the whole tree too; a full one at the limit may not be.
    assert computer_use.deterministic_step(goal="seleccionar rojo", view=_tools(count=10, total=None), history=[]) is None
    full = computer_use.deterministic_step(goal="seleccionar rojo", view=_tools(count=60, total=None), history=[])
    assert full is not None and full["arguments"] == {"label": "rojo"}


def test_a_listed_or_written_name_keeps_its_own_click() -> None:
    listed = _tools(extra=[{"i": 4, "kind": "Button", "name": "Rojo", "state": "off"}])
    step = computer_use.deterministic_step(goal="seleccionar rojo", view=listed, history=[])
    assert step is not None and step["arguments"] == {"label": "Rojo", "index": 4}
    written = {**_tools(), "text": {"TR": ["Colores", "Rojo"]}}
    by_line = computer_use.deterministic_step(goal="seleccionar rojo", view=written, history=[])
    assert by_line is not None and fold_label(by_line) == "rojo" and "index" not in by_line["arguments"] and by_line["reason"] != computer_use.REASON_BY_NAME


def test_never_for_a_switch_a_kind_or_a_name_that_removes() -> None:
    view = _tools()
    for goal in ("activar rojo", "desactivar rojo", "hacer clic en la casilla rojo", "hacer clic en eliminar",
                 "ir a borrar todo", "seleccionar quitar fondo"):
        step = computer_use.deterministic_step(goal=goal, view=view, history=[])
        assert step is None or step["reason"] != computer_use.REASON_BY_NAME, goal


def test_going_to_a_place_tries_its_name_before_looking_it_up() -> None:
    view = _tools()
    first = computer_use.deterministic_step(goal="ir a capas avanzadas", view=view, history=[])
    assert first is not None and first["arguments"] == {"label": "capas avanzadas"}
    # Tried and not found: the place is looked up the way the window offers (here: the find shortcut).
    then = computer_use.deterministic_step(goal="ir a capas avanzadas", view=view, history=[_failed(1, "capas avanzadas")])
    assert then is not None and then.get("reason") != computer_use.REASON_BY_NAME


def test_a_chosen_colour_is_proved_by_its_whole_name_never_a_word_holding_it() -> None:
    # Measured on Paint: «red» inside «Rectángulo redondeado» passed a click on that shape as the colour chosen, and
    # the mission learned that click as the way to choose red.
    from baxy_mind.semantic import missions

    check = missions.mission_request("en Paint elegí el color rojo", ("Paint",)).arguments()["successCheck"]
    atoms = set(check.split("|"))
    assert {"control:=rojo:selected", "control:=rojo:on", "stepDone:input.visible.click:=rojo"} <= atoms
    assert "stepDone:input.visible.click:=red" in atoms
    assert not any(atom.endswith((":red", ":rojo")) or ":red:" in atom or ":rojo:" in atom for atom in atoms)


def test_the_name_the_window_writes_goes_before_the_persons_other_language_word() -> None:
    # «blue» said to a Spanish window that writes «azul» in a long name it lists (too long to be that colour's
    # control): the window's own name first, so the other language's click does not spend a step.
    palette = {"i": 4, "kind": "Group", "state": "",
               "name": "Paleta: negro, gris, blanco, rojo, naranja, amarillo, verde, azul, violeta, rosa"}
    first = computer_use.deterministic_step(goal="seleccionar blue", view=_tools(extra=[palette]), history=[])
    assert first is not None and first["arguments"] == {"label": "azul"}
    assert first["reason"] == computer_use.REASON_BY_NAME
    then = computer_use.deterministic_step(goal="seleccionar blue", view=_tools(extra=[palette]), history=[_failed(1, "azul")])
    assert then is not None and then["arguments"] == {"label": "blue"}
    # Neither name written anywhere: the person's word first, as before.
    plain = computer_use.deterministic_step(goal="seleccionar blue", view=_tools(), history=[])
    assert plain is not None and plain["arguments"] == {"label": "blue"}
