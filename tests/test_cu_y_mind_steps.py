"""Deterministic steps of computer use: retries, genders, ambiguity and content items (cu-y-mind)."""

from baxy_mind import computer_use


def _ok(step: int, operation: str, **fields: object) -> dict:
    return {"step": step, "operation": operation, "ok": True, **fields}


def _rect(x: int, y: int, w: int, h: int) -> dict:
    return {"x": x, "y": y, "w": w, "h": h}


def test_a_failed_click_retry_reads_what_the_verified_click_made_appear_not_the_stale_new_text() -> None:
    # The failed look's newText is stale (lines of an earlier look); the App sent no newTextAfterClick, so no menu
    # can be told and nothing is clicked from those lines.
    view = {
        "window": {"title": "Steam", "process": "steamwebhelper", "focused": None},
        "controls": [],
        "newText": ["Página principal", "Colecciones"],
        "text": {"TL": ["BIBLIOTECA"]},
    }
    history = [
        _ok(1, "input.visible.click", label="BIBLIOTECA"),
        {"step": 2, "operation": "input.visible.click", "label": "Inicio", "ok": False},
    ]
    step = computer_use.deterministic_step(goal="ir a biblioteca", view=view, history=history)
    assert step is None or step["arguments"].get("label") != "Página principal"
    # With the App's newTextAfterClick the menu entry is the step.
    kept = {**view, "newText": [], "newTextAfterClick": ["Página principal", "Colecciones"]}
    step = computer_use.deterministic_step(goal="ir a biblioteca", view=kept, history=history)
    assert step is not None and step["arguments"].get("label") == "Página principal"


def test_a_place_keeps_the_gender_said() -> None:
    view = {
        "window": {"title": "Juego", "process": "game", "focused": None},
        "controls": [{"i": 0, "kind": "ListItem", "name": "Partida", "zone": "C"}],
        "text": {"C": ["Partida"]},
    }
    step = computer_use.deterministic_step(goal="ir a partido", view=view, history=[])
    assert step is None or step["arguments"].get("label") != "Partida"
    assert step is None or step["arguments"].get("index") != 0
    # A mode keeps both genders: «modo científico» finds «Científica».
    calculator = {
        "window": {"title": "Calculadora", "process": "CalculatorApp", "focused": None},
        "controls": [{"i": 0, "kind": "ListItem", "name": "Científica", "zone": "L"}],
        "text": {},
    }
    step = computer_use.deterministic_step(goal="ir a científico", view=calculator, history=[])
    assert step is not None and step["arguments"] == {"label": "Científica", "index": 0}


def test_a_name_inside_a_message_does_not_make_the_place_ambiguous() -> None:
    discord = {
        "window": {"title": "Mi servidor - Discord", "process": "Discord", "focused": None},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Buscar", "state": ""},
            {"i": 1, "kind": "ListItem", "name": "Ana: hoy hablamos en general de todo"},
            {"i": 2, "kind": "ListItem", "name": "Beto: nos vemos en general mañana"},
        ],
        "text": {"C": ["general"]},
    }
    step = computer_use.deterministic_step(goal="ir a general", view=discord, history=[])
    # Not two controls named «general»: the written word is clicked, never the search opened as for a doubt.
    assert step is not None and step["arguments"] == {"label": "general"}
    # Two controls that carry the name as their own («general», «general · Mi servidor») are the doubt.
    doubled = {
        **discord,
        "controls": [
            discord["controls"][0],
            {"i": 1, "kind": "ListItem", "name": "General (canal de texto)"},
            {"i": 2, "kind": "Button", "name": "general · Mi servidor"},
        ],
    }
    assert computer_use._controls_naming(doubled, ("general",), None, True) == 2
    assert computer_use._controls_naming(discord, ("general",), None, True) == 0


def _programs_view(item_name: str, *, extra: list[dict] | None = None, item_type: str = "") -> dict:
    return {
        "window": {"title": "Inicio - Explorador de archivos", "process": "explorer"},
        "controls": [
            {"i": 0, "kind": "ListItem", "name": item_name, "zone": "C", "state": "selected", "itemType": item_type},
            {"i": 1, "kind": "ListItem", "name": "Documentos", "zone": "C"},
            *(extra or []),
        ],
    }


def test_enter_is_never_the_default_on_a_file_that_runs_or_where_removal_is_offered() -> None:
    clicked = [_ok(1, "input.visible.click", label="setup.exe", index=0)]
    runs = _programs_view("setup.exe")
    assert computer_use.deterministic_step(goal="ir a setup.exe", view=runs, history=clicked) is None
    shortcut = [_ok(1, "input.visible.click", label="Juego.lnk", index=0)]
    assert computer_use.deterministic_step(goal="ir a Juego.lnk", view=_programs_view("Juego.lnk"), history=shortcut) is None
    # A list of programs with «Desinstalar» on offer: the step is the model's.
    chosen = [_ok(1, "input.visible.click", label="Hades", index=0)]
    programs = _programs_view("Hades", extra=[{"i": 2, "kind": "Button", "name": "Desinstalar"}], item_type="Carpeta de archivos")
    assert computer_use.deterministic_step(goal="ir a hades", view=programs, history=chosen) is None
    # A plain folder in a view without removal keeps its Enter; «Borradores» is no removal.
    folder = _programs_view("Hades", extra=[{"i": 2, "kind": "Button", "name": "Borradores"}], item_type="Carpeta de archivos")
    step = computer_use.deterministic_step(goal="ir a hades", view=folder, history=chosen)
    assert step is not None and step["operation"] == "input.key.press" and step["arguments"] == {"key": "enter"}


def test_a_tile_in_the_left_column_is_content_when_its_row_goes_on_out_of_it() -> None:
    tile = {"i": 0, "kind": "ListItem", "name": "Descargas", "zone": "L", "rect": _rect(10, 200, 120, 100), "state": "selected",
            "itemType": "Carpeta de archivos"}
    neighbour = {"i": 1, "kind": "ListItem", "name": "Documentos", "zone": "C", "rect": _rect(400, 220, 120, 100)}
    lower = {"i": 1, "kind": "ListItem", "name": "Documentos", "zone": "C", "rect": _rect(400, 320, 120, 100)}
    grid = {"window": {"title": "Inicio - Explorador de archivos", "process": "explorer"}, "controls": [tile, neighbour]}
    assert computer_use.is_content_item(tile, grid)
    # Another row (centres more than half the item's height apart): a side list.
    apart = {**grid, "controls": [tile, lower]}
    assert not computer_use.is_content_item(tile, apart)
    # The zone alone, without the view, still reads a left item as navigation.
    assert not computer_use.is_content_item(tile)
    # The chosen tile in the grid is opened with Enter.
    clicked = [_ok(1, "input.visible.click", label="Descargas", index=0)]
    step = computer_use.deterministic_step(goal="ir a descargas", view=grid, history=clicked)
    assert step is not None and step["operation"] == "input.key.press" and step["arguments"] == {"key": "enter"}
    step = computer_use.deterministic_step(goal="ir a descargas", view=apart, history=clicked)
    assert step is None or step["arguments"].get("key") != "enter"


def test_the_step_prompt_never_presses_enter_on_what_runs() -> None:
    prompt = computer_use.STEP_PROMPT
    assert "key enter" in prompt and "instalador" in prompt and "se ejecuta" in prompt
