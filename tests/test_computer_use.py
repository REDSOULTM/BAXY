"""Motor de computer use, lado mente (CONTRATO_VISTA_ACCION.md): lectura del
pedido, elección de un paso comprobada contra la vista, proyección y vetos."""

from __future__ import annotations

from baxy_mind import computer_use
from baxy_mind.__main__ import _explicit_arguments_from_evidence
from baxy_mind.effect_intent import (
    _is_direct_request,
    resolve_explicit_effects,
)

APPS = ("Steam", "Discord", "Google Chrome", "Calculadora", "Configuración", "Notepad")
AVAILABLE = frozenset(
    {
        "app.open",
        "browser.control",
        "calculator.expression.evaluate",
        "client.channel.locate",
        "input.key.press",
        "input.scroll",
        "input.text.type",
        "input.visible.click",
        "input.visible.controls",
        "mission.computer.use",
        "system.time",
    }
)


def _mission(text: str):
    intent = resolve_explicit_effects(text, AVAILABLE, application_names=APPS)
    assert intent is not None, text
    assert intent.operations == ("mission.computer.use",), (text, intent.operations)
    arguments = _explicit_arguments_from_evidence("mission.computer.use", intent.evidence[0], APPS)
    assert arguments is not None, text
    return arguments


# ---------------------------------------------------------------- lectura


def test_the_six_cu1959_missions_read_as_one_engine_mission() -> None:
    discord = _mission("ve a Cotele en Discord")
    assert discord["application"] == "Discord"
    assert discord["goal"] == "ir a cotele"
    assert discord["successCheck"] == "stepDone:input.visible.click:cotele|control:cotele:selected|title:cotele"

    tabs = _mission("cerrá todas las pestañas de chrome")
    assert tabs == {"application": "Google Chrome", "goal": "cerrar todas las pestañas", "successCheck": "count:TabItem<=1"}

    steam = _mission("abre Steam y ve a la biblioteca")
    assert steam["application"] == "Steam"
    assert steam["goal"] == "ir a la biblioteca" or steam["goal"] == "ir a biblioteca"
    assert steam["successCheck"].startswith("stepDone:input.visible.click:")

    enter = _mission("en Discord apretá enter")
    assert enter == {"application": "Discord", "goal": "apretar enter", "successCheck": "stepDone:input.key.press:enter"}

    airplane = _mission("abrí Configuración y activá el modo avión")
    assert airplane == {"application": "Configuración", "goal": "activar modo avion", "successCheck": "control:modo avion:on"}

    calculator = _mission("en la calculadora calculá 12×7")
    assert calculator["application"] == "Calculadora"
    assert calculator["goal"] == "calcular 12×7"
    assert "stepDone:input.key.press:enter" in calculator["successCheck"]


def test_english_and_variant_phrasings_read_the_same_missions() -> None:
    assert _mission("Go to Cotele in Discord")["goal"] == "ir a cotele"
    assert _mission("Open Steam and go to the library")["goal"] in {"ir a the library", "ir a library"}
    assert _mission("close all tabs in chrome")["successCheck"] == "count:TabItem<=1"
    assert _mission("In Discord press enter")["successCheck"] == "stepDone:input.key.press:enter"
    assert _mission("abrí configuración y desactivá el modo avión")["successCheck"] == "control:modo avion:off"


def test_requests_outside_an_installed_application_are_not_missions() -> None:
    # A browser that is not installed keeps the product's own browser route.
    intent = resolve_explicit_effects("cerrá todas las pestañas de firefox", AVAILABLE, application_names=APPS)
    assert intent is None or intent.operations != ("mission.computer.use",)
    # A read elsewhere after opening an app is not doing inside it.
    intent = resolve_explicit_effects("abre Steam y decime la hora", AVAILABLE, application_names=APPS)
    assert intent is None or intent.operations != ("mission.computer.use",)
    # A prohibition is never a mission.
    assert computer_use.mission_request("no vayas a Cotele en Discord", APPS) is None
    # Without the operation served, the old routes stay.
    legacy = resolve_explicit_effects("ve a Cotele en Discord", AVAILABLE - {"mission.computer.use"}, application_names=APPS)
    assert legacy is not None and legacy.operations == ("client.channel.locate",)


def test_mission_shapes_pass_the_speech_act_gate() -> None:
    assert _is_direct_request("en discord apreta enter")
    assert _is_direct_request("abre steam y ve a la biblioteca")
    assert _is_direct_request("cerra todas las pestanas de chrome")
    assert not _is_direct_request("steam tiene biblioteca")


def test_read_clause_shapes() -> None:
    assert computer_use.read_clause("apretá la tecla escape") == ("apretar escape", "stepDone:input.key.press:escape")
    assert computer_use.read_clause("pulsá ctrl+w") == ("apretar ctrl+w", "stepDone:input.key.press:ctrl_w")
    assert computer_use.read_clause("hacé clic en Biblioteca") == ("hacer clic en biblioteca", "stepDone:input.visible.click:biblioteca")
    assert computer_use.read_clause("escribí hola mundo") == ("escribir hola mundo", "stepDone:input.text.type")
    assert computer_use.read_clause("la biblioteca") is None
    assert computer_use.read_clause("prendé el bluetooth") == ("activar bluetooth", "control:bluetooth:on")


# ------------------------------------------------------------ elegir paso

VIEW = {
    "window": {"title": "Steam", "process": "steamwebhelper", "focused": None},
    "controls": [
        {"i": 0, "kind": "Button", "name": "Tienda", "state": "", "zone": "T"},
        {"i": 1, "kind": "Button", "name": "Biblioteca", "state": "", "zone": "T", "color": "blue"},
        {"i": 2, "kind": "Edit", "name": "Buscar", "state": "focused", "value": ""},
    ],
    "text": {"T": ["TIENDA", "BIBLIOTECA", "COMUNIDAD"], "C": ["Juegos recientes"]},
}


def test_click_is_bound_to_a_control_of_the_view() -> None:
    decision = computer_use.validate_decision(
        {"act": "click", "i": 1, "label": "Biblioteca", "text": "", "key": "", "direction": "", "application": "", "evidence": "", "why": "es la sección"},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"] == {"label": "Biblioteca", "index": 1}
    # A drifted index with the right label is corrected by name.
    drifted = computer_use.validate_decision(
        {"act": "click", "i": 0, "label": "bibloteca", "text": "", "key": "", "direction": "", "application": "", "evidence": "", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert drifted["arguments"] == {"label": "Biblioteca", "index": 1}
    # A label that is only in the OCR text clicks by label (the cascade finds it).
    ocr_only = computer_use.validate_decision(
        {"act": "click", "i": -1, "label": "Comunidad", "text": "", "key": "", "direction": "", "application": "", "evidence": "", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert ocr_only["arguments"] == {"label": "Comunidad"}
    # A label nowhere in the view is refused.
    absent = computer_use.validate_decision(
        {"act": "click", "i": 5, "label": "Descargas", "text": "", "key": "", "direction": "", "application": "", "evidence": "", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert absent["operation"] == "none" and absent["code"] == "label_not_visible"


def test_done_needs_evidence_on_screen_and_failed_steps_are_not_repeated() -> None:
    done = computer_use.validate_decision(
        {"act": "done", "i": -1, "label": "", "text": "", "key": "", "direction": "", "application": "", "evidence": "Juegos recientes", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert done["operation"] == "done" and done["arguments"] == {"evidence": "Juegos recientes"}
    invented = computer_use.validate_decision(
        {"act": "done", "i": -1, "label": "", "text": "", "key": "", "direction": "", "application": "", "evidence": "Descargando", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert invented["operation"] == "none" and invented["code"] == "evidence_not_visible"
    repeated = computer_use.validate_decision(
        {"act": "click", "i": 1, "label": "Biblioteca", "text": "", "key": "", "direction": "", "application": "", "evidence": "", "why": ""},
        view=VIEW, last_failed={"operation": "input.visible.click", "label": "Biblioteca", "ok": False}, application_names=APPS,
    )
    assert repeated["operation"] == "none" and repeated["code"] == "repeated_step"


def test_keys_typing_and_opening_are_checked_against_the_view_and_the_catalog() -> None:
    key = computer_use.validate_decision(
        {"act": "key", "i": -1, "label": "", "text": "", "key": "enter", "direction": "", "application": "", "evidence": "", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert key == {"operation": "input.key.press", "arguments": {"key": "enter"}, "reason": ""}
    composer_view = {
        "window": {"title": "Ron92 - Discord", "process": "Discord", "focused": {"kind": "Edit", "name": "Enviar mensaje a @Ron92", "value": "hola"}},
        "controls": [],
        "text": {},
    }
    sending = computer_use.validate_decision(
        {"act": "key", "i": -1, "label": "", "text": "", "key": "enter", "direction": "", "application": "", "evidence": "", "why": ""},
        view=composer_view, last_failed=None, application_names=APPS,
    )
    assert sending["arguments"] == {"key": "enter", "target": "message_composer"}
    password_view = {"window": {"title": "Login"}, "controls": [{"i": 0, "kind": "Edit", "name": "Contraseña", "state": "focused password"}], "text": {}}
    typing = computer_use.validate_decision(
        {"act": "type", "i": -1, "label": "", "text": "secreto", "key": "", "direction": "", "application": "", "evidence": "", "why": ""},
        view=password_view, last_failed=None, application_names=APPS,
    )
    assert typing["operation"] == "none" and typing["code"] == "password_field"
    opening = computer_use.validate_decision(
        {"act": "open", "i": -1, "label": "", "text": "", "key": "", "direction": "", "application": "Steam", "evidence": "", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert opening == {"operation": "app.open", "arguments": {"appId": "Steam"}, "reason": ""}
    unknown = computer_use.validate_decision(
        {"act": "open", "i": -1, "label": "", "text": "", "key": "", "direction": "", "application": "Photoshop", "evidence": "", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert unknown["operation"] == "none"


def test_compact_view_text_is_short_and_names_every_control() -> None:
    text = computer_use.compact_view_text(VIEW)
    assert "ventana: «Steam» (steamwebhelper)" in text
    assert "1 · Button · «Biblioteca» · T · blue" in text
    assert "texto T: TIENDA | BIBLIOTECA | COMUNIDAD" in text
    assert len(text) < 600


def test_application_in_front_matches_by_title_or_process_tokens() -> None:
    assert computer_use.application_is_in_front(VIEW, "Steam")
    assert not computer_use.application_is_in_front(VIEW, "Discord")
    assert computer_use.application_is_in_front({"window": {"title": "Nueva pestaña", "process": "chrome"}}, "Google Chrome")
    assert computer_use.application_is_in_front({"window": {"title": "Configuración", "process": "SystemSettings"}}, "Configuración")


# -------------------------------------------------------------- compositor

OBSERVED = {
    "goal": "ir a la biblioteca",
    "application": "Steam",
    "reached": True,
    "steps": [
        {"step": 1, "operation": "app.open", "ok": True},
        {"step": 2, "operation": "input.visible.click", "label": "Biblioteca", "ok": True, "surfaceChanged": True},
    ],
    "window": {"title": "Steam", "process": "steamwebhelper"},
    "joined": False,
    "satisfiedBy": "stepDone:input.visible.click:biblioteca",
}


def test_projection_keeps_only_what_the_loop_observed() -> None:
    seen = computer_use.project_seen(OBSERVED, "es")
    assert seen["reached"] is True
    assert seen["stepsDone"] == ["trajo la aplicación al frente", "clic en «Biblioteca»"]
    assert seen["windowTitle"] == "Steam"
    assert seen["joined"] is False
    assert "surfaceChanged" not in str(seen)


def test_mission_vetoes() -> None:
    seen = computer_use.project_seen(OBSERVED, "es")
    assert computer_use.mission_defect("abri steam y fui a la biblioteca.", seen) is None
    assert computer_use.mission_defect("ayer fui a la biblioteca de steam.", seen) == "extra_claim"
    assert computer_use.mission_defect("me uni al canal de voz.", seen) == "joined_claimed"
    joined = computer_use.project_seen({**OBSERVED, "joined": True}, "es")
    assert computer_use.mission_defect("entre al canal de voz cotele.", joined) is None
    assert computer_use.mission_defect("no me uni al canal.", joined) == "joined_claimed"
    failed = computer_use.project_seen({**OBSERVED, "reached": False, "stoppedBy": "computer_use_no_step_visible"}, "es")
    assert computer_use.mission_defect("listo, ya estas en la biblioteca.", failed) == "reversed_polarity"
    assert computer_use.mission_defect("no pude llegar a la biblioteca: no encontre el control.", failed) is None


def test_covered_window_names_the_cover_in_the_cause():
    covered = computer_use.project_seen(
        {
            **OBSERVED,
            "reached": False,
            "stoppedBy": "computer_use_window_covered",
            "window": {"title": "Configuración", "process": "ApplicationFrameHost", "coveredBy": {"title": "Pelicula - PotPlayer", "process": "PotPlayerMini64"}},
        },
        "es",
    )
    assert covered["coveredBy"] == "Pelicula - PotPlayer"
    assert covered["stoppedBecause"] == "la ventana «Pelicula - PotPlayer» tapa la aplicación"
    plain = computer_use.project_seen({**OBSERVED, "reached": False, "stoppedBy": "computer_use_window_covered"}, "en")
    assert plain["stoppedBecause"] == "another window covers the application"


# ------------------------------------------------------- pasos dictados


def test_deterministic_steps_follow_the_goal_family_and_the_view() -> None:
    calc = computer_use.deterministic_step(goal="calcular 12×7", view=VIEW, history=[])
    assert calc == {"operation": "input.text.type", "arguments": {"text": "12*7"}, "reason": "el objetivo lo dice"}
    typed = [{"step": 1, "operation": "input.text.type", "text": "12*7", "ok": True}]
    assert computer_use.deterministic_step(goal="calcular 12×7", view=VIEW, history=typed)["arguments"] == {"key": "enter"}
    entered = typed + [{"step": 2, "operation": "input.key.press", "key": "enter", "ok": True}]
    assert computer_use.deterministic_step(goal="calcular 12×7", view=VIEW, history=entered) is None
    key = computer_use.deterministic_step(goal="apretar enter", view=VIEW, history=[])
    assert key == {"operation": "input.key.press", "arguments": {"key": "enter"}, "reason": "el objetivo lo dice"}
    go = computer_use.deterministic_step(goal="ir a la biblioteca", view=VIEW, history=[])
    assert go["operation"] == "input.visible.click" and go["arguments"] == {"label": "Biblioteca", "index": 1}
    assert computer_use.deterministic_step(goal="ir a descargas", view=VIEW, history=[]) is None
    # A failed last step hands the decision to the model.
    failed = [{"step": 1, "operation": "input.visible.click", "label": "Biblioteca", "ok": False}]
    assert computer_use.deterministic_step(goal="ir a la biblioteca", view=VIEW, history=failed) is None
    toggle_view = {"window": {"title": "Configuración"}, "controls": [{"i": 4, "kind": "Button", "name": "Modo avión", "state": "off"}], "text": {}}
    on = computer_use.deterministic_step(goal="activar modo avion", view=toggle_view, history=[])
    assert on["arguments"] == {"label": "Modo avión", "index": 4}
    already = {"window": {"title": "Configuración"}, "controls": [{"i": 4, "kind": "Button", "name": "Modo avión", "state": "on"}], "text": {}}
    assert computer_use.deterministic_step(goal="activar modo avion", view=already, history=[]) is None
    tabs_view = {"window": {"title": "Chrome"}, "controls": [{"i": 0, "kind": "TabItem", "name": "Nueva pestaña", "repeated": 2}], "text": {}}
    assert computer_use.deterministic_step(goal="cerrar todas las pestañas", view=tabs_view, history=[])["arguments"] == {"key": "ctrl_w"}
    one_tab = {"window": {"title": "Chrome"}, "controls": [{"i": 0, "kind": "TabItem", "name": "Nueva pestaña"}], "text": {}}
    assert computer_use.deterministic_step(goal="cerrar todas las pestañas", view=one_tab, history=[]) is None


def test_a_failed_open_with_the_application_in_front_does_not_stop_the_dictated_steps() -> None:
    failed_open = [{"step": 1, "operation": "app.open", "appId": "Calculadora", "ok": False, "error": "verification_failed"}]
    calc_view = {"window": {"title": "Calculadora", "process": "CalculatorApp", "focused": None}, "controls": [{"i": 0, "kind": "Button", "name": "Uno"}], "text": {}}
    typed = computer_use.deterministic_step(goal="calcular 12×7", view=calc_view, history=failed_open, application="Calculadora")
    assert typed == {"operation": "input.text.type", "arguments": {"text": "12*7"}, "reason": "el objetivo lo dice"}
    elsewhere = {"window": {"title": "Program Manager", "process": "explorer", "focused": None}, "controls": [], "text": {}}
    assert computer_use.deterministic_step(goal="calcular 12×7", view=elsewhere, history=failed_open, application="Calculadora") is None


def test_mission_arguments_ground_without_a_literal_check() -> None:
    from baxy_mind.__main__ import _ground_explicit_arguments

    schema = {
        "type": "object",
        "properties": {
            "application": {"type": ["string", "null"]},
            "budgetSteps": {"type": ["integer", "null"]},
            "goal": {"type": "string"},
            "successCheck": {"type": ["string", "null"]},
        },
        "required": ["goal"],
        "additionalProperties": False,
    }
    grounded = _ground_explicit_arguments("mission.computer.use", "en la calculadora calculá 12×7", schema, APPS)
    assert grounded is not None and grounded["application"] == "Calculadora" and grounded["goal"] == "calcular 12×7"


# ------------------------------------------------- pestañas y cualquier persona

MORE_APPS = (*APPS, "Paint", "Bloc de notas", "Opera GX Browser")
# The web routes that used to catch «ve a la pestaña de YouTube» are served too: the mission must win over them.
WEB = AVAILABLE | {"web.search", "browser.navigate", "browser.navigate.named", "media.play.query", "app.close"}


def _mission_in(text: str, apps: tuple[str, ...] = MORE_APPS) -> dict:
    intent = resolve_explicit_effects(text, WEB, application_names=apps)
    assert intent is not None and intent.operations == ("mission.computer.use",), (text, intent)
    arguments = _explicit_arguments_from_evidence("mission.computer.use", intent.evidence[0], apps)
    assert arguments is not None, text
    return arguments


def test_the_already_good_requests_keep_their_routes() -> None:
    assert _mission_in("ve a Cotele en Discord")["goal"] == "ir a cotele"
    assert _mission_in("abre Steam y ve a la biblioteca")["application"] == "Steam"
    assert _mission_in("en Discord apretá enter")["successCheck"] == "stepDone:input.key.press:enter"
    assert _mission_in("abrí Configuración y activá el modo avión")["successCheck"] == "control:modo avion:on"
    assert _mission_in("en la calculadora calculá 12×7")["goal"] == "calcular 12×7"
    # Every tab of the person's own browser stays its typed close (confirmed, the last tab kept).
    tabs = resolve_explicit_effects("cerrá todas las pestañas del navegador", WEB, application_names=MORE_APPS)
    assert tabs is not None and tabs.operations == ("browser.control",)


def test_going_to_a_tab_by_its_name_is_a_mission_in_the_persons_browser() -> None:
    wanted = {
        "application": computer_use.BROWSER_CATEGORY,
        "goal": "ir a la pestaña youtube",
        "successCheck": "control:youtube:selected|title:youtube",
    }
    for said in (
        "ve a la pestaña de YouTube",
        "andá a la pestaña YouTube",
        "cambiá a la pestaña de YouTube",
        "vaya a la pestaña de YouTube",
        "ir a la pestaña de YouTube",
        "ve a la pestaña de YouTube en el navegador",
        "go to the YouTube tab",
        "switch to the tab with YouTube",
    ):
        assert _mission_in(said) == wanted, said
        assert _is_direct_request(said), said


def test_a_named_browser_wins_over_the_category() -> None:
    assert _mission_in("ve a la pestaña de YouTube en Opera")["application"] == "Opera GX Browser"
    chrome = _mission_in("go to the YouTube tab in Chrome")
    assert chrome == {"application": "Google Chrome", "goal": "ir a la pestaña youtube", "successCheck": "control:youtube:selected|title:youtube"}


def test_a_tab_said_by_its_place_names_no_tab() -> None:
    for said in ("ve a la siguiente pestaña", "ve a la pestaña", "go to the next tab"):
        assert computer_use.mission_request(said, MORE_APPS) is None, said
    # Where to open a page, not which tab to go to.
    for said in ("ve a YouTube en otra pestaña", "go to youtube in a new tab", "ve a google en una pestaña"):
        assert computer_use.mission_request(said, MORE_APPS) is None, said


def test_a_doing_clause_reads_in_any_person() -> None:
    for said, goal in (
        ("en Paint elegí el color rojo", "elegi el color rojo"),
        ("en Paint elija el color rojo", "elige el color rojo"),
        ("en Paint elegir el color rojo", "elegir el color rojo"),
        ("en Paint seleccione el pincel", "selecciona el pincel"),
        ("en Paint marque la casilla", "marca la casilla"),
        ("in Paint pick the red color", "pick the red color"),
    ):
        arguments = _mission_in(said)
        assert arguments["application"] == "Paint" and arguments["goal"] == goal, said
    assert _mission_in("en Steam vaya a la tienda")["goal"] == "ir a tienda"
    assert _mission_in("en Steam ir a la tienda")["goal"] == "ir a tienda"
    assert _mission_in("en Discord pulse enter")["successCheck"] == "stepDone:input.key.press:enter"
    assert _mission_in("en la calculadora calcule 12x7")["goal"] == "calcular 12x7"
    assert _mission_in("en Configuración active el modo avión")["successCheck"] == "control:modo avion:on"
    # An application named with several words, before the clause.
    assert _mission_in("en el bloc de notas escribí hola") == {
        "application": "Bloc de notas", "goal": "escribir hola", "successCheck": "stepDone:input.text.type",
    }


def test_questions_statements_and_typed_requests_are_not_missions() -> None:
    for said in (
        "en Steam tengo 40 juegos",
        "¿en Steam puedo ir a la biblioteca?",
        "en Discord está Cotele",
        "abre Steam y decime la hora",
        # Music and a pronoun with nothing on screen to name keep their own routes.
        "abre Opera y ponme una canción de Michael Jackson",
        "buscalo en google",
        "open paint then close it",
    ):
        assert computer_use.mission_request(said, MORE_APPS) is None, said
    assert not computer_use.mission_clause_is_direct("en la mañana tengo que ir al banco")


def test_a_tab_is_clicked_by_a_part_of_its_title() -> None:
    view = {
        "window": {"title": "Recibidos (3) - Gmail - Opera", "process": "opera"},
        "controls": [
            {"i": 0, "kind": "TabItem", "name": "Recibidos (3) - Gmail", "state": "selected"},
            {"i": 1, "kind": "TabItem", "name": "Rick Astley - Never Gonna Give You Up - YouTube"},
            {"i": 2, "kind": "Hyperlink", "name": "YouTube"},
        ],
        "text": {},
    }
    step = computer_use.deterministic_step(
        goal="ir a la pestaña youtube", view=view, history=[], application=computer_use.BROWSER_CATEGORY,
    )
    assert step == {
        "operation": "input.visible.click",
        "arguments": {"label": "Rick Astley - Never Gonna Give You Up - YouTube", "index": 1},
        "reason": "el objetivo lo dice",
    }
    # Without the kind, the link and the tab both name YouTube and only the exact name is taken.
    assert computer_use.find_control(view, "youtube")["i"] == 2
    assert computer_use.find_control(view, "youtube", kind="TabItem")["i"] == 1
    clicked = [{"step": 1, "operation": "input.visible.click", "label": "Rick Astley - Never Gonna Give You Up - YouTube", "ok": True}]
    assert computer_use.deterministic_step(goal="ir a la pestaña youtube", view=view, history=clicked) is None
