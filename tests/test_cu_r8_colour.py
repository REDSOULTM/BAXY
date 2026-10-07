"""A basic colour the palette does not carry by its name: its closest shade, by whole name (cu-r8, live e2)."""

from baxy_mind import computer_use
from baxy_mind.semantic import missions
from baxy_mind.semantic.colours import changes_the_tool, colour_shades, shade_of

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
    step = computer_use.deterministic_step(goal="seleccionar pincel", view=view, history=[])
    assert step is None or step["reason"] != computer_use.REASON_SHADE


def test_the_live_case_tries_the_name_then_the_closest_shade_present() -> None:
    # The palette lies beyond the listed controls: «blue» and «azul» by label found nothing; «Añil» is next.
    view = _tools()
    first = computer_use.deterministic_step(goal="seleccionar blue", view=view, history=[])
    assert first is not None and first["arguments"] == {"label": "blue"}
    history = [_failed(1, "blue"), _failed(2, "azul")]
    shade = computer_use.deterministic_step(goal="seleccionar blue", view=view, history=history)
    assert shade is not None and shade["arguments"] == {"label": "Añil"} and shade["reason"] == computer_use.REASON_SHADE
    # Each shade once, closest first, in the window's language (its names are Spanish): never an English swatch.
    history.append(_failed(3, "Añil"))
    then = computer_use.deterministic_step(goal="seleccionar blue", view=view, history=history)
    assert then is not None and then["arguments"] == {"label": "Índigo"}
    tried = list(history)
    labels = []
    for step_no in range(4, 20):
        step = computer_use.deterministic_step(goal="seleccionar blue", view=view, history=tried)
        if step is None or step["reason"] != computer_use.REASON_SHADE:
            break
        labels.append(step["arguments"]["label"])
        tried.append(_failed(step_no, step["arguments"]["label"]))
    assert labels == ["Índigo", "Azul oscuro", "Azul marino", "Azul claro", "Celeste", "Turquesa", "Cian"]


def test_a_listed_shade_is_clicked_by_its_index_never_a_grey_holding_the_word() -> None:
    view = _tools(count=60, total=60, palette=_PALETTE)
    step = computer_use.deterministic_step(goal="seleccionar azul", view=view, history=[])
    assert step is not None and step["arguments"]["label"] == "Añil" and isinstance(step["arguments"]["index"], int)
    assert step["reason"] == computer_use.REASON_SHADE


def test_a_family_member_absent_gives_no_false_success() -> None:
    # A palette with no blue at all, whole tree listed: nothing by shade, and no grey or shape for it.
    palette = tuple(name for name in _PALETTE if name not in {"Añil", "Turquesa", "Turquesa claro"})
    view = _tools(count=60, total=60, palette=palette)
    step = computer_use.deterministic_step(goal="seleccionar azul", view=view, history=[])
    assert step is None
    # A failed click on a shade is never the colour chosen: the check needs the click verified.
    observed = {"goal": "seleccionar azul", "reached": False, "steps": [_failed(1, "Añil")]}
    assert "chosenShade" not in computer_use.project_seen(observed, "es")


def test_red_that_exists_is_chosen_never_its_darker_shade_nor_the_current_colour() -> None:
    view = _tools(count=60, total=60, palette=_PALETTE)
    step = computer_use.deterministic_step(goal="seleccionar rojo", view=view, history=[])
    assert step is not None and step["arguments"] == {"label": "Rojo", "index": 5 + _PALETTE.index("Rojo")}
    # Unlisted: the label «rojo» is matched whole by the click, never «Rojo oscuro».
    unlisted = computer_use.deterministic_step(goal="seleccionar rojo", view=_tools(), history=[])
    assert unlisted is not None and unlisted["arguments"] == {"label": "rojo"}
    assert shade_of("rojo", "Rojo oscuro") and not shade_of("rojo", "Rojo") and not shade_of("azul", "Gris azulado")


def test_the_whole_name_rule_still_holds_for_red() -> None:
    atoms = _check("en Paint elegí el color rojo")
    assert "stepDone:input.visible.click:=rojo" in atoms and "stepDone:input.visible.click:=red" in atoms
    assert not any(atom.endswith((":red", ":rojo")) for atom in atoms)
    # «Rectángulo redondeado» is listed and holds «red»: never the colour's control.
    step = computer_use.deterministic_step(goal="seleccionar red", view=_tools(count=10, total=10), history=[])
    assert step is None or "redondeado" not in str(step["arguments"].get("label")).lower()


def test_choosing_a_colour_never_clicks_a_tool_that_picks_colours() -> None:
    assert changes_the_tool("Selector de colores") and changes_the_tool("Color picker") and changes_the_tool("Cuentagotas")
    assert not changes_the_tool("Añil")
    view = _tools()
    refused = computer_use.validate_decision(
        {"act": "click", "i": 1}, view=view, last_failed=None, application_names=(), history=[], goal="seleccionar azul",
    )
    assert refused["operation"] == "none" and refused["code"] == "changes_the_tool"
    # Another goal may choose that tool by its name.
    allowed = computer_use.validate_decision(
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
    seen = computer_use.project_seen(observed, "en")
    assert seen["chosenShade"] == {"asked": "blue", "chosen": "Añil"}
    assert "seen.chosenShade" in computer_use.compose_instruction(seen, "en")
    assert computer_use.mission_defect("listo, elegi el azul.", seen) == "shade_unnamed"
    assert computer_use.mission_defect("listo, elegi anil, el azul de la paleta.", seen) is None
    assert computer_use.floor_sentence(observed, False, True) == "Listo, elegí Añil, el azul de la paleta."
    assert computer_use.floor_sentence(observed, True, True) == "Done, I picked Añil, the blue of the palette."
    # The colour clicked by its own name is no shade to explain.
    plain = {**observed, "steps": [{"step": 1, "operation": "input.visible.click", "label": "Rojo", "name": "Rojo", "ok": True}],
             "goal": "seleccionar rojo"}
    assert "chosenShade" not in computer_use.project_seen(plain, "es")
