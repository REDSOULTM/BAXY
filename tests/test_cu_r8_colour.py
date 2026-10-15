"""A basic colour the palette does not carry by its name: its closest shade, by whole name (cu-r8, live e2)."""

import pytest

from baxy_mind import cu_by_name
from baxy_mind import cu_rules
from baxy_mind import cu_validate
from baxy_mind import cu_projection
from baxy_mind import cu_reply_checks
from baxy_mind import cu_finals
from baxy_mind.semantic import missions
from baxy_mind.semantic.colours import changes_the_tool, colour_shades, names_the_colour_kind, shade_of

# Live e2 («abrí Paint y pick the blue color»): the palette's swatches, as UIA names them on a Spanish Windows.
_PALETTE = (
    "Negro", "Gris", "Rojo oscuro", "Rojo", "Naranja", "Amarillo", "Verde", "Turquesa", "Añil", "Púrpura", "Blanco",
    "Gris claro", "Marrón", "Rosa", "Dorado", "Amarillo claro", "Lima", "Turquesa claro", "Gris azulado", "Lavanda",
)


def _tools(count: int = 60, total: int | None = 118, palette: tuple[str, ...] = ()) -> dict:
    controls = [
        {"i": 0, "kind": "Button", "name": "Lápiz", "state": "off"},
        {"i": 1, "kind": "Button", "name": "Selector de colores", "state": "off"},
        {"i": 2, "kind": "ListItem", "name": "Rectángulo redondeado", "state": ""},
        {"i": 3, "kind": "RadioButton", "name": "Color 1: Rojo", "state": "on"},
        {"i": 4, "kind": "RadioButton", "name": "Color 2: Blanco", "state": "off"},
    ]
    controls += [{"i": len(controls) + n, "kind": "ListItem", "name": name, "state": ""} for n, name in enumerate(palette)]
    controls += [{"i": index, "kind": "Button", "name": f"Forma {index}", "state": "off"} for index in range(len(controls), count)]
    view = {
        "window": {"title": "Sin título - Paint", "process": "mspaint", "focused": None},
        "controls": controls,
        "text": {"TR": ["Colores", "Capas"]},
    }
    if total is not None:
        view["controlCount"] = total
    return view


def _failed(step: int, label: str) -> dict:
    return {"step": step, "operation": "input.visible.click", "label": label, "ok": False, "error": "visible_button_not_found"}


def _check(text: str) -> set[str]:
    return set(missions.mission_request(text, ("Paint",)).arguments()["successCheck"].split("|"))


def test_the_select_check_accepts_a_whole_click_on_a_shade_of_a_basic_colour() -> None:
    atoms = _check("abrí Paint y pick the blue color")
    assert {"stepDone:input.visible.click:=blue", "stepDone:input.visible.click:=azul"} <= atoms
    assert {"stepDone:input.visible.click:=anil", "stepDone:input.visible.click:=indigo",
            "stepDone:input.visible.click:=turquesa"} <= atoms
    # «azul oscuro» is already «=azul» whole; a grey that only holds the letters is never a blue.
    assert not any("azulado" in atom or "oscuro" in atom for atom in atoms)
    # A shade is only a click: a swatch selected before any step is no colour chosen.
    assert "control:=anil:selected" not in atoms


def test_every_shade_the_mind_may_click_fits_the_check() -> None:
    for word in ("azul", "blue", "rojo", "red", "verde", "morado", "purple", "rosa", "gris", "marron", "naranja"):
        check = missions._select_check(word)
        assert len(check.encode("utf-8")) <= 512
        folded = [missions.fold(shade) for shade in colour_shades(word)]
        for shade in folded:
            assert any(
                atom.startswith("stepDone:input.visible.click:=") and (
                    shade == atom.split("=", 1)[1] or f" {atom.split('=', 1)[1]} " in f" {shade} "
                )
                for atom in check.split("|")
            ), (word, shade)


def test_a_goal_that_is_not_a_colour_is_unaffected() -> None:
    atoms = _check("en Paint elegí el lápiz")
    assert atoms == {"control:=lapiz:selected", "control:=lapiz:on", "stepDone:input.visible.click:=lapiz",
                     "control:=pencil:selected", "control:=pencil:on", "stepDone:input.visible.click:=pencil"}
    view = _tools(palette=_PALETTE)
    step = cu_rules.deterministic_step(goal="seleccionar pincel", view=view, history=[])
    assert step is None or step["reason"] != cu_by_name.REASON_SHADE


def test_the_live_case_tries_the_name_then_the_closest_shade_present() -> None:
    # The palette lies beyond the listed controls: «blue» and «azul» by label found nothing; «Añil» is next.
    view = _tools()
    first = cu_rules.deterministic_step(goal="seleccionar blue", view=view, history=[])
    assert first is not None and first["arguments"] == {"label": "blue"}
    history = [_failed(1, "blue"), _failed(2, "azul")]
    shade = cu_rules.deterministic_step(goal="seleccionar blue", view=view, history=history)
    assert shade is not None and shade["arguments"] == {"label": "Añil"} and shade["reason"] == cu_by_name.REASON_SHADE
    # Each shade once, closest first, in the window's language (its names are Spanish): never an English swatch.
    history.append(_failed(3, "Añil"))
    then = cu_rules.deterministic_step(goal="seleccionar blue", view=view, history=history)
    assert then is not None and then["arguments"] == {"label": "Índigo"}
    tried = list(history)
    labels = []
    for step_no in range(4, 20):
        step = cu_rules.deterministic_step(goal="seleccionar blue", view=view, history=tried)
        if step is None or step["reason"] != cu_by_name.REASON_SHADE:
            break
        labels.append(step["arguments"]["label"])
        tried.append(_failed(step_no, step["arguments"]["label"]))
    assert labels == ["Índigo", "Azul oscuro", "Azul marino", "Azul claro", "Celeste", "Turquesa", "Cian"]


def test_a_listed_shade_is_clicked_by_its_index_never_a_grey_holding_the_word() -> None:
    view = _tools(count=60, total=60, palette=_PALETTE)
    step = cu_rules.deterministic_step(goal="seleccionar azul", view=view, history=[])
    assert step is not None and step["arguments"]["label"] == "Añil" and isinstance(step["arguments"]["index"], int)
    assert step["reason"] == cu_by_name.REASON_SHADE


def test_a_family_member_absent_gives_no_false_success() -> None:
    # A palette with no blue at all, whole tree listed: nothing by shade, and no grey or shape for it.
    palette = tuple(name for name in _PALETTE if name not in {"Añil", "Turquesa", "Turquesa claro"})
    view = _tools(count=60, total=60, palette=palette)
    step = cu_rules.deterministic_step(goal="seleccionar azul", view=view, history=[])
    assert step is None
    # A failed click on a shade is never the colour chosen: the check needs the click verified.
    observed = {"goal": "seleccionar azul", "reached": False, "steps": [_failed(1, "Añil")]}
    assert "chosenShade" not in cu_projection.project_seen(observed, "es")


def test_red_that_exists_is_chosen_never_its_darker_shade_nor_the_current_colour() -> None:
    view = _tools(count=60, total=60, palette=_PALETTE)
    step = cu_rules.deterministic_step(goal="seleccionar rojo", view=view, history=[])
    assert step is not None and step["arguments"] == {"label": "Rojo", "index": 5 + _PALETTE.index("Rojo")}
    # Unlisted: the label «rojo» is matched whole by the click, never «Rojo oscuro».
    unlisted = cu_rules.deterministic_step(goal="seleccionar rojo", view=_tools(), history=[])
    assert unlisted is not None and unlisted["arguments"] == {"label": "rojo"}
    assert shade_of("rojo", "Rojo oscuro") and not shade_of("rojo", "Rojo") and not shade_of("azul", "Gris azulado")


def test_the_whole_name_rule_still_holds_for_red() -> None:
    atoms = _check("en Paint elegí el color rojo")
    assert "stepDone:input.visible.click:=rojo" in atoms and "stepDone:input.visible.click:=red" in atoms
    assert not any(atom.endswith((":red", ":rojo")) for atom in atoms)
    # «Rectángulo redondeado» is listed and holds «red»: never the colour's control.
    step = cu_rules.deterministic_step(goal="seleccionar red", view=_tools(count=10, total=10), history=[])
    assert step is None or "redondeado" not in str(step["arguments"].get("label")).lower()


def test_choosing_a_colour_never_clicks_a_tool_that_picks_colours() -> None:
    assert changes_the_tool("Selector de colores") and changes_the_tool("Color picker") and changes_the_tool("Cuentagotas")
    assert not changes_the_tool("Añil")
    view = _tools()
    refused = cu_validate.validate_decision(
        {"act": "click", "i": 1}, view=view, last_failed=None, application_names=(), history=[], goal="seleccionar azul",
    )
    assert refused["operation"] == "none" and refused["code"] == "changes_the_tool"
    # Another goal may choose that tool by its name.
    allowed = cu_validate.validate_decision(
        {"act": "click", "i": 1}, view=view, last_failed=None, application_names=(), history=[],
        goal="seleccionar selector de colores",
    )
    assert allowed["operation"] == "input.visible.click"


def test_the_final_names_the_swatch_chosen() -> None:
    observed = {
        "goal": "seleccionar blue", "reached": True, "application": "Paint",
        "steps": [
            {"step": 1, "operation": "app.open", "ok": True},
            _failed(2, "blue"), _failed(3, "azul"),
            {"step": 4, "operation": "input.visible.click", "label": "Añil", "name": "Añil", "ok": True},
        ],
    }
    seen = cu_projection.project_seen(observed, "en")
    assert seen["chosenShade"] == {"asked": "blue", "chosen": "Añil"}
    assert "seen.chosenShade" in cu_projection.compose_instruction(seen, "en")
    assert cu_reply_checks.mission_defect("listo, elegi el azul.", seen) == "shade_unnamed"
    assert cu_reply_checks.mission_defect("listo, elegi anil, el azul de la paleta.", seen) is None
    assert cu_finals.floor_sentence(observed, False, True) == "Listo, elegí Añil, el azul de la paleta."
    assert cu_finals.floor_sentence(observed, True, True) == "Done, I picked Añil, the blue of the palette."
    # The colour clicked by its own name is no shade to explain.
    plain = {**observed, "steps": [{"step": 1, "operation": "input.visible.click", "label": "Rojo", "name": "Rojo", "ok": True}],
             "goal": "seleccionar rojo"}
    assert "chosenShade" not in cu_projection.project_seen(plain, "es")


# --------------------------------------------------------------------------- Estabilización G3 (tanda f2nb t3-c19)
# «y ponle color rojo» was restated «haz clic en color y selecciona rojo» and planned «hacer clic en color; luego
# seleccionar rojo»; the rule pressed «Editar colores» for «color» by containment, a button whose modal dialog hung the
# next read 20 s twice (journal 13:54:41–13:55:27), and the mission stopped with the window unreadable.

def _paint_f2nb() -> dict:
    """The live view of that turn, trimmed: the tools, the two current colours, «Editar colores», 60 of 114 listed."""

    controls = [
        {"i": 0, "kind": "Button", "name": "Lápiz", "state": "on"},
        {"i": 1, "kind": "Button", "name": "Selector de colores", "state": "off"},
        {"i": 2, "kind": "RadioButton", "name": "Color 1: Negro", "state": "selected"},
        {"i": 3, "kind": "RadioButton", "name": "Color 2: Blanco", "state": ""},
        {"i": 4, "kind": "Button", "name": "Editar colores", "state": ""},
    ]
    controls += [{"i": index, "kind": "Button", "name": f"Forma {index}", "state": "off"} for index in range(5, 60)]
    return {"window": {"title": "Sin título - Paint", "process": "mspaint", "focused": None}, "controls": controls,
            "controlCount": 114, "text": {"TR": ["Colores", "Capas"]}}


def test_g3_the_kind_alone_never_presses_a_control_that_carries_the_word() -> None:
    for goal in ("hacer clic en color", "hacer clic en colores", "ir a color", "hacer clic en el colour"):
        step = cu_rules.deterministic_step(goal=goal, view=_paint_f2nb(), history=[], application="Paint",
                                               objective="y ponle color rojo")
        assert step is None or "editar" not in str(step["arguments"].get("label")).lower(), goal


def test_g3_contracaso_a_control_named_the_kind_whole_is_still_pressed() -> None:
    view = _paint_f2nb()
    view["controls"].append({"i": 60, "kind": "Button", "name": "Colores", "state": ""})
    view["controlCount"] = 115
    step = cu_rules.deterministic_step(goal="hacer clic en colores", view=view, history=[], application="Paint")
    assert step is not None and step["arguments"] == {"label": "Colores", "index": 60}


def test_g3_the_colour_named_goes_to_its_swatch() -> None:
    step = cu_rules.deterministic_step(goal="seleccionar rojo", view=_paint_f2nb(), history=[], application="Paint",
                                           objective="y ponle color rojo")
    assert step is not None and step["arguments"] == {"label": "rojo"}


@pytest.mark.parametrize("text", [
    "En Paint, haz clic en color y selecciona rojo",
    "En Paint, haz clic en el color rojo",
    "en paint hace clic en el color rojo",
    "In Paint, click the red colour",
])
def test_g3_the_click_on_the_kind_and_the_colour_is_one_choice(text: str) -> None:
    mission = missions.mission_request(text, ("Paint",))
    assert mission is not None and not mission.steps
    assert mission.goal in ("seleccionar rojo", "seleccionar red")
    assert "stepDone:input.visible.click:=rojo" in str(mission.success_check)
    assert "color" not in mission.goal


@pytest.mark.parametrize("text", [
    "En Paint, haz clic en Formas y selecciona rojo",
    "En Paint, haz clic en color y selecciona el lápiz",
    "En Paint, haz clic en Editar colores",
])
def test_g3_contracaso_other_clicks_stay_their_own_sub_goals(text: str) -> None:
    mission = missions.mission_request(text, ("Paint",))
    assert mission is not None
    goals = [step.goal for step in mission.steps] or [mission.goal]
    assert any(goal.startswith("hacer clic en ") for goal in goals)


@pytest.mark.parametrize(("name", "expected"), [
    ("color", True), ("colores", True), ("colour", True), ("colours", True), ("Color", True),
    ("color rojo", False), ("editar colores", False), ("colorear", False), ("rojo", False), ("", False),
])
def test_g3_names_the_colour_kind(name: str, expected: bool) -> None:
    assert names_the_colour_kind(name) is expected
