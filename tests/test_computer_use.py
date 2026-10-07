"""Motor de computer use, lado mente (CONTRATO_VISTA_ACCION.md): lectura del
pedido, elección de un paso comprobada contra la vista, proyección y vetos."""

from __future__ import annotations

from baxy_mind import computer_use
from baxy_mind.semantic import missions
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
    # The reader reads the mission; the route is the catalog's typed channel read (test_the_mission_takes_over…).
    discord = missions.mission_request("ve a Cotele en Discord", APPS).arguments()
    assert discord["application"] == "Discord"
    assert discord["goal"] == "ir a cotele"
    assert discord["successCheck"] == "control:cotele:selected|title:cotele|page:cotele"

    # Closing every tab is browser.control close_all (confirmed by RiskPolicy), never a mission of loose keys.
    tabs = resolve_explicit_effects("cerrá todas las pestañas de chrome", AVAILABLE, application_names=APPS)
    assert tabs is not None and tabs.operations == ("browser.control",)

    steam = _mission("abre Steam y ve a la biblioteca")
    assert steam["application"] == "Steam"
    assert steam["goal"] == "ir a la biblioteca" or steam["goal"] == "ir a biblioteca"
    assert steam["successCheck"] == "control:biblioteca:selected|title:biblioteca|page:biblioteca|control:library:selected|title:library|page:library"

    enter = _mission("en Discord apretá enter")
    assert enter == {"application": "Discord", "goal": "apretar enter", "successCheck": "stepDone:input.key.press:enter"}

    airplane = _mission("abrí Configuración y activá el modo avión")
    assert airplane == {"application": "Configuración", "goal": "activar modo avion", "successCheck": "control:modo avion:on|control:airplane mode:on|control:modo de avion:on"}

    calculator = _mission("en la calculadora calculá 12×7")
    assert calculator["application"] == "Calculadora"
    assert calculator["goal"] == "calcular 12×7"
    assert "stepDone:input.key.press:enter" in calculator["successCheck"]


def test_english_and_variant_phrasings_read_the_same_missions() -> None:
    assert missions.mission_request("Go to Cotele in Discord", APPS).goal == "ir a cotele"
    assert _mission("Open Steam and go to the library")["goal"] in {"ir a the library", "ir a library"}
    assert _mission("In Discord press enter")["successCheck"] == "stepDone:input.key.press:enter"
    assert _mission("abrí configuración y desactivá el modo avión")["successCheck"] == "control:modo avion:off|control:airplane mode:off|control:modo de avion:off"


def test_requests_outside_an_installed_application_are_not_missions() -> None:
    # A browser that is not installed keeps the product's own browser route.
    intent = resolve_explicit_effects("cerrá todas las pestañas de firefox", AVAILABLE, application_names=APPS)
    assert intent is None or intent.operations != ("mission.computer.use",)
    # A read elsewhere after opening an app is not doing inside it.
    intent = resolve_explicit_effects("abre Steam y decime la hora", AVAILABLE, application_names=APPS)
    assert intent is None or intent.operations != ("mission.computer.use",)
    # A prohibition is never a mission.
    assert missions.mission_request("no vayas a Cotele en Discord", APPS) is None
    # Without the operation served, the old routes stay.
    legacy = resolve_explicit_effects("ve a Cotele en Discord", AVAILABLE - {"mission.computer.use"}, application_names=APPS)
    assert legacy is not None and legacy.operations == ("client.channel.locate",)


def test_mission_shapes_pass_the_speech_act_gate() -> None:
    assert _is_direct_request("en discord apreta enter")
    assert _is_direct_request("abre steam y ve a la biblioteca")
    assert _is_direct_request("cerra todas las pestanas de chrome")
    assert not _is_direct_request("steam tiene biblioteca")


def test_read_clause_shapes() -> None:
    assert missions.read_clause("apretá la tecla escape") == ("apretar escape", "stepDone:input.key.press:escape")
    assert missions.read_clause("pulsá ctrl+w") == ("apretar ctrl+w", "stepDone:input.key.press:ctrl_w")
    assert missions.read_clause("hacé clic en Biblioteca") == ("hacer clic en biblioteca", "stepDone:input.visible.click:biblioteca|stepDone:input.visible.click:library")
    assert missions.read_clause("escribí hola mundo") == ("escribir hola mundo", "stepDone:input.text.type")
    assert missions.read_clause("la biblioteca") is None
    assert missions.read_clause("prendé el bluetooth") == ("activar bluetooth", "control:bluetooth:on")


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
    # Not on screen: the focused search field takes the name (the FIND routine below).
    assert computer_use.deterministic_step(goal="ir a descargas", view=VIEW, history=[])["arguments"] == {"text": "descargas"}
    # A failed last step hands the decision to the model.
    failed = [{"step": 1, "operation": "input.visible.click", "label": "Biblioteca", "ok": False}]
    assert computer_use.deterministic_step(goal="ir a la biblioteca", view=VIEW, history=failed) is None
    toggle_view = {"window": {"title": "Configuración"}, "controls": [{"i": 4, "kind": "Button", "name": "Modo avión", "state": "off"}], "text": {}}
    on = computer_use.deterministic_step(goal="activar modo avion", view=toggle_view, history=[])
    assert on["arguments"] == {"label": "Modo avión", "index": 4}
    already = {"window": {"title": "Configuración"}, "controls": [{"i": 4, "kind": "Button", "name": "Modo avión", "state": "on"}], "text": {}}
    assert computer_use.deterministic_step(goal="activar modo avion", view=already, history=[]) is None


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
    assert missions.mission_request("ve a Cotele en Discord", MORE_APPS).goal == "ir a cotele"
    assert _mission_in("abre Steam y ve a la biblioteca")["application"] == "Steam"
    assert _mission_in("en Discord apretá enter")["successCheck"] == "stepDone:input.key.press:enter"
    assert _mission_in("abrí Configuración y activá el modo avión")["successCheck"] == "control:modo avion:on|control:airplane mode:on|control:modo de avion:on"
    assert _mission_in("en la calculadora calculá 12×7")["goal"] == "calcular 12×7"
    # Every tab of the person's own browser stays its typed close (confirmed, the last tab kept).
    tabs = resolve_explicit_effects("cerrá todas las pestañas del navegador", WEB, application_names=MORE_APPS)
    assert tabs is not None and tabs.operations == ("browser.control",)


def test_going_to_a_tab_by_its_name_is_a_mission_in_the_persons_browser() -> None:
    wanted = {
        "application": missions.BROWSER_CATEGORY,
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
        assert missions.mission_request(said, MORE_APPS) is None, said
    # Where to open a page, not which tab to go to.
    for said in ("ve a YouTube en otra pestaña", "go to youtube in a new tab", "ve a google en una pestaña"):
        assert missions.mission_request(said, MORE_APPS) is None, said


def test_a_doing_clause_reads_in_any_person() -> None:
    for said, goal in (
        # Choosing a tool or a colour is clicking it until it shows selected (computer use v2, owner 2026-10-07).
        ("en Paint elegí el color rojo", "seleccionar rojo"),
        ("en Paint elija el color rojo", "seleccionar rojo"),
        ("en Paint elegir el color rojo", "seleccionar rojo"),
        ("en Paint seleccione el pincel", "seleccionar pincel"),
        ("in Paint pick the red color", "seleccionar red"),
        # The reader reads the act; with no check of its own the route is the decider's (test below).
        ("en Paint marque la casilla", "marca la casilla"),
    ):
        arguments = missions.mission_request(said, MORE_APPS).arguments()
        assert arguments["application"] == "Paint" and arguments["goal"] == goal, said
    assert _mission_in("en Steam vaya a la tienda")["goal"] == "ir a tienda"
    assert missions.mission_request("en Steam ir a la tienda", MORE_APPS).goal == "ir a tienda"
    assert _mission_in("en Discord pulse enter")["successCheck"] == "stepDone:input.key.press:enter"
    assert _mission_in("en la calculadora calcule 12x7")["goal"] == "calcular 12x7"
    assert _mission_in("en Configuración active el modo avión")["successCheck"] == "control:modo avion:on|control:airplane mode:on|control:modo de avion:on"
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
        assert missions.mission_request(said, MORE_APPS) is None, said
    assert not missions.mission_clause_is_direct("en la mañana tengo que ir al banco")


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
        goal="ir a la pestaña youtube", view=view, history=[], application=missions.BROWSER_CATEGORY,
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


TYPED = WEB | {"system.settings.set", "audio.microphone.mute", "audio.volume.adjust", "message.send",
               "message.recipient.resolve", "streaming.play.named", "game.install"}


def _route(text: str) -> tuple[str, ...] | None:
    intent = resolve_explicit_effects(text, TYPED, application_names=(*MORE_APPS, "Spotify", "WhatsApp"))
    return intent.operations if intent is not None else None


def test_what_the_catalog_already_does_keeps_its_typed_operation() -> None:
    # D21: a typed operation Windows verifies better than the screen wins over the engine.
    assert _route("abrí Configuración y activá el modo avión") == ("system.settings.set",)
    assert _route("pon Bohemian Rhapsody en Spotify") == ("media.play.query",)
    assert _route("busca gatos en google") == ("browser.navigate",)
    # The clause inside the app is itself a catalog request: no mission.
    assert _route("en Discord activá el micrófono") != ("mission.computer.use",)


def test_a_loose_verb_inside_an_app_is_left_to_the_decider() -> None:
    assert _route("en Spotify baja el volumen") is None
    assert _route("en WhatsApp escribile a Ron92 hola") is None
    assert _route("en Paint marcá la casilla") is None
    # Choosing a colour now has its check (selected, or the verified click on it): the engine's.
    assert _route("en Paint elegí el color rojo") == ("mission.computer.use",)


def test_the_mission_takes_over_its_own_primitives() -> None:
    # Once a typed reading of open + click / channel locate: those are the mission's own steps. A channel of a chat
    # client is found by the engine's search on screen; joining a voice channel stays confirmed by RiskPolicy.
    assert _route("ve a Cotele en Discord") == ("mission.computer.use",)
    assert _route("abre Steam y ve a la biblioteca") == ("mission.computer.use",)
    assert _route("abrí el bloc de notas y escribí hola mundo") == ("mission.computer.use",)
    assert _route("ve a la pestaña de YouTube") == ("mission.computer.use",)


def test_reaching_a_place_needs_more_than_its_name_on_screen() -> None:
    # Measured on Steam: «BIBLIOTECA» is on screen before and after its click opened a menu.
    view = {"window": {"title": "Steam"}, "controls": [], "text": {"TL": ["BIBLIOTECA COMUNIDAD"], "C": ["TUS COLECCIONES"]}}
    name_only = computer_use.validate_decision(
        {"act": "done", "evidence": "BIBLIOTECA"}, view=view, last_failed=None, application_names=APPS, goal="ir a biblioteca",
    )
    assert name_only["operation"] == "none" and name_only["code"] == "evidence_not_visible"
    reached = computer_use.validate_decision(
        {"act": "done", "evidence": "TUS COLECCIONES"}, view=view, last_failed=None, application_names=APPS, goal="ir a biblioteca",
    )
    assert reached["operation"] == "done"
    # The text of the destination alone no longer satisfies a go-to: only the place selected or titled does.
    assert missions.read_clause("andá a la biblioteca")[1] == "control:biblioteca:selected|title:biblioteca|page:biblioteca|control:library:selected|title:library|page:library"


# ------------------------------------------------ buscar lo que no está en pantalla


def _ok(step: int, operation: str, **fields: object) -> dict:
    return {"step": step, "operation": operation, "ok": True, **fields}


CHAT = {
    "window": {"title": "Amigos - Discord", "process": "Discord", "focused": None},
    "controls": [
        {"i": 0, "kind": "Button", "name": "Buscar", "state": ""},
        {"i": 1, "kind": "ListItem", "name": "Cotele"},
        {"i": 2, "kind": "Edit", "name": "Enviar mensaje a @Ron92", "state": ""},
    ],
    "text": {"C": ["Cotele", "Ron92"]},
}


def test_find_uses_the_search_of_the_window_then_clicks_the_result() -> None:
    step = computer_use.deterministic_step(goal="ir a general", view=CHAT, history=[])
    assert step["operation"] == "input.visible.click" and step["arguments"] == {"label": "Buscar", "index": 0}
    clicked = [_ok(1, "input.visible.click", label="Buscar")]
    searching = {**CHAT, "window": {**CHAT["window"], "focused": {"kind": "Edit", "name": "Buscar", "value": ""}}}
    assert computer_use.deterministic_step(goal="ir a general", view=searching, history=clicked)["arguments"] == {"text": "general"}
    typed = clicked + [_ok(2, "input.text.type", text="general")]
    results = {
        "window": {"title": "Amigos - Discord", "process": "Discord", "focused": {"kind": "Edit", "name": "Buscar", "value": "general"}},
        "controls": [
            {"i": 0, "kind": "Edit", "name": "general", "state": "focused"},
            {"i": 1, "kind": "Text", "name": "general"},
            {"i": 2, "kind": "ListItem", "name": "general · Mi servidor"},
        ],
        "newText": ["general", "general · Mi servidor"],
        "text": {"C": ["general", "general · Mi servidor"]},
    }
    picked = computer_use.deterministic_step(goal="ir a general", view=results, history=typed)
    # The list item, never the field that echoes the name, and never Enter (a voice channel stays a confirmed click).
    assert picked["operation"] == "input.visible.click" and picked["arguments"] == {"label": "general · Mi servidor", "index": 2}
    # A window without an accessible tree: the new line that is more than the typed name.
    ocr_only = {"window": {"title": "Steam"}, "controls": [], "newText": ["batman", "Batman: Arkham Knight"], "text": {"C": ["batman", "Batman: Arkham Knight"]}}
    batman = [_ok(1, "input.visible.click", label="Buscar"), _ok(2, "input.text.type", text="batman")]
    assert computer_use.deterministic_step(goal="ir a batman", view=ocr_only, history=batman)["arguments"] == {"label": "Batman: Arkham Knight"}
    # Nothing names it: the search is closed and the next way is tried.
    empty = {"window": {"title": "Steam"}, "controls": [], "newText": [], "text": {}}
    assert computer_use.deterministic_step(goal="ir a batman", view=empty, history=batman)["arguments"] == {"key": "escape"}
    escaped = batman + [_ok(3, "input.key.press", key="escape")]
    assert computer_use.deterministic_step(goal="ir a batman", view=empty, history=escaped)["arguments"] == {"key": "ctrl_k"}


def test_find_without_a_search_field_tries_the_shortcuts_then_scrolls_the_list() -> None:
    plain = {
        "window": {"title": "App", "process": "app", "rect": {"x": 0, "y": 0, "w": 800, "h": 600}, "focused": None},
        "controls": [
            {"i": 0, "kind": "ListItem", "name": "Uno", "rect": {"x": 10, "y": 100, "w": 200, "h": 20}},
            {"i": 1, "kind": "ListItem", "name": "Dos", "rect": {"x": 10, "y": 120, "w": 200, "h": 20}},
            {"i": 2, "kind": "Pane", "name": "Contenido", "rect": {"x": 300, "y": 0, "w": 500, "h": 600}},
            {"i": 3, "kind": "List", "name": "Canales", "rect": {"x": 0, "y": 80, "w": 250, "h": 500}},
        ],
        "text": {},
    }
    assert computer_use.deterministic_step(goal="ir a general", view=plain, history=[])["arguments"] == {"key": "ctrl_k"}
    after_k = [_ok(1, "input.key.press", key="ctrl_k")]
    switcher = {
        **plain,
        "window": {**plain["window"], "focused": {"kind": "Edit", "name": "", "value": ""}},
        "newText": ["Busca servidores, canales o MD"],
    }
    assert computer_use.deterministic_step(goal="ir a general", view=switcher, history=after_k)["arguments"] == {"text": "general"}
    # The shortcut opened nothing: escape, then ctrl_f, then the list that holds the items.
    assert computer_use.deterministic_step(goal="ir a general", view=plain, history=after_k)["arguments"] == {"key": "escape"}
    tried = after_k + [
        _ok(2, "input.key.press", key="escape"), _ok(3, "input.key.press", key="ctrl_f"), _ok(4, "input.key.press", key="escape"),
    ]
    scroll = computer_use.deterministic_step(goal="ir a general", view=plain, history=tried)
    assert scroll["operation"] == "input.scroll" and scroll["arguments"] == {"direction": "down", "amount": 5, "index": 3}
    scrolled = tried + [_ok(5 + n, "input.scroll", direction="down") for n in range(3)]
    assert computer_use.deterministic_step(goal="ir a general", view=plain, history=scrolled) is None
    unchanged = tried + [{"step": 5, "operation": "input.scroll", "ok": True, "changed": False}, _ok(6, "input.key.press", key="escape")]
    assert computer_use.deterministic_step(goal="ir a general", view=plain, history=unchanged) is None


def test_find_never_types_into_a_composer_or_the_address_bar() -> None:
    composer = {
        "window": {
            "title": "#off-topic - Discord", "process": "Discord",
            "focused": {"kind": "Edit", "name": "Enviar mensaje a #off-topic", "value": ""},
        },
        "controls": [], "newText": ["algo"], "text": {},
    }
    after_k = [_ok(1, "input.key.press", key="ctrl_k")]
    assert computer_use.deterministic_step(goal="ir a general", view=composer, history=after_k)["arguments"] == {"key": "escape"}
    browser = {
        "window": {"title": "Nueva pestaña - Google Chrome", "process": "chrome", "focused": None},
        "controls": [{"i": 0, "kind": "Edit", "name": "Barra de direcciones y de búsqueda", "state": ""}],
        "text": {},
    }
    assert computer_use.deterministic_step(goal="ir a general", view=browser, history=[])["arguments"] == {"key": "ctrl_k"}


def test_an_english_goal_finds_the_spanish_control() -> None:
    step = computer_use.deterministic_step(goal="ir a library", view=VIEW, history=[])
    assert step["arguments"] == {"label": "Biblioteca", "index": 1}
    check = missions.read_clause("go to the library")[1]
    assert "control:library:selected" in check and "control:biblioteca:selected" in check


def test_a_menu_entry_named_by_the_goal_wins_over_the_first_one() -> None:
    menu = {"window": {"title": "Steam"}, "controls": [], "newText": ["Página principal", "Colecciones", "Descargas"], "text": {}}
    clicked = [_ok(1, "input.visible.click", label="BIBLIOTECA")]
    named = computer_use.deterministic_step(goal="ir a descargas de la biblioteca", view=menu, history=clicked)
    assert named["arguments"] == {"label": "Descargas"}
    first = computer_use.deterministic_step(goal="ir a biblioteca", view=menu, history=clicked)
    assert first["arguments"] == {"label": "Página principal"}


def test_a_click_on_the_whole_window_and_a_third_idle_repeat_are_refused() -> None:
    view = {
        "window": {"title": "Página", "rect": {"x": 0, "y": 0, "w": 1000, "h": 800}},
        "controls": [
            {"i": 0, "kind": "Document", "name": "Contenido", "rect": {"x": 0, "y": 40, "w": 1000, "h": 760}},
            {"i": 1, "kind": "Button", "name": "Siguiente", "rect": {"x": 10, "y": 10, "w": 80, "h": 24}},
        ],
        "text": {},
    }
    covering = computer_use.validate_decision({"act": "click", "i": 0}, view=view, last_failed=None, application_names=APPS)
    assert covering["operation"] == "none" and covering["code"] == "control_covers_window"
    button = computer_use.validate_decision({"act": "click", "i": 1}, view=view, last_failed=None, application_names=APPS)
    assert button["arguments"] == {"label": "Siguiente", "index": 1}
    twice = [_ok(1, "input.visible.click", label="Siguiente"), _ok(2, "input.visible.click", label="Siguiente")]
    idle = computer_use.validate_decision({"act": "click", "i": 1}, view=view, last_failed=None, application_names=APPS, history=twice)
    assert idle["operation"] == "none" and idle["code"] == "no_progress"
    moving = computer_use.validate_decision(
        {"act": "click", "i": 1}, view={**view, "newText": ["Página 3"]}, last_failed=None, application_names=APPS, history=twice,
    )
    assert moving["operation"] == "input.visible.click"


# ------------------------------------------------------- misiones encadenadas

CHAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "application": {"type": ["string", "null"], "x-maxUtf8Bytes": 128},
        "budgetSteps": {"type": ["integer", "null"], "minimum": 1, "maximum": 30},
        "goal": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
        "successCheck": {"type": ["string", "null"], "x-maxUtf8Bytes": 512},
        "steps": {
            "type": "array", "minItems": 1, "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
                    "application": {"type": ["string", "null"], "x-maxUtf8Bytes": 128},
                    "successCheck": {"type": ["string", "null"], "x-maxUtf8Bytes": 512},
                },
                "required": ["goal", "application", "successCheck"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["goal"],
    "additionalProperties": False,
}


def test_a_chained_request_reads_its_sub_goals_in_order() -> None:
    chained = _mission_in("abre Steam y ve a la biblioteca y después en Discord andá a general")
    assert [(step["application"], step["goal"]) for step in chained["steps"]] == [("Steam", "ir a biblioteca"), ("Discord", "ir a general")]
    assert chained["steps"][1]["successCheck"] == "control:general:selected|title:general|page:general"
    assert chained["goal"] == "ir a biblioteca; luego ir a general"
    # Typing into a place: go to it, then type; the application is carried forward.
    typing = missions.mission_request("en Discord andá a general y escribí hola", MORE_APPS).arguments()
    assert typing["steps"] == [
        {"goal": "ir a general", "application": "Discord", "successCheck": "control:general:selected|title:general|page:general"},
        {"goal": "escribir hola", "application": "Discord", "successCheck": "stepDone:input.text.type"},
    ]
    english = missions.mission_request("go to the library in Steam and then go to general in Discord", MORE_APPS)
    assert [step.application for step in english.steps] == ["Steam", "Discord"]
    # The going said once: «… y después a general en Discord».
    elliptic = missions.mission_request("andá a la biblioteca en Steam y después a general en Discord", MORE_APPS)
    assert [(step.application, step.goal) for step in elliptic.steps] == [("Steam", "ir a biblioteca"), ("Discord", "ir a general")]
    # An application opened with nothing to do in it is its own sub-goal.
    opened = missions.mission_request("andá a la tienda en Steam, luego abrí Discord", MORE_APPS)
    assert [step.goal for step in opened.steps] == ["ir a tienda", "abrir Discord"]


def test_a_single_clause_keeps_todays_arguments() -> None:
    assert "steps" not in _mission_in("abre Steam y ve a la biblioteca")
    # «y chau» is not a clause of doing: one text to type.
    assert missions.mission_request("en el bloc de notas escribí hola y chau", MORE_APPS).goal == "escribir hola y chau"
    # The place ends where the next clause begins.
    assert missions.read_clause("ve a la biblioteca y escribí hola")[0] == "ir a biblioteca"


def test_chained_missions_route_to_the_engine_and_ground_their_steps() -> None:
    from baxy_mind.__main__ import _ground_explicit_arguments

    said = "en Discord andá a general y escribí hola, después en Steam andá a la biblioteca"
    assert _route(said) == ("mission.computer.use",)
    assert _is_direct_request("andá a la biblioteca en Steam y después a general en Discord")
    grounded = _ground_explicit_arguments("mission.computer.use", said, CHAIN_SCHEMA, MORE_APPS)
    assert grounded is not None and len(grounded["steps"]) == 3 and grounded["steps"][2]["application"] == "Steam"
    # A clause the reader cannot check leaves the turn to the decider.
    assert _route("abre Steam, ve a la biblioteca y dibujá a Batman") != ("mission.computer.use",)
    # Searching is checked now (the name typed and submitted, or the page titled with it): the engine's.
    assert _route("abre Steam, ve a la biblioteca y busca Batman") == ("mission.computer.use",)


def test_a_free_form_goal_is_the_persons_clause_with_the_app_it_names() -> None:
    from baxy_mind.__main__ import _ground_explicit_arguments

    drawn = _ground_explicit_arguments("mission.computer.use", "en Paint dibujá un círculo rojo", CHAIN_SCHEMA, MORE_APPS)
    assert drawn == {"goal": "en Paint dibujá un círculo rojo", "application": "Paint"}
    front = _ground_explicit_arguments("mission.computer.use", "ordená esto por fecha", CHAIN_SCHEMA, MORE_APPS)
    assert front == {"goal": "ordená esto por fecha"}


class _CapturingModel:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def _post_schema_object(self, payload: dict, label: str) -> dict:
        del label
        self.payloads.append(payload)
        return {"act": "none"}


def test_the_step_prompt_names_the_sub_goal() -> None:
    model = _CapturingModel()
    computer_use.decide_step(
        model, objective="en Discord andá a general y escribí hola", goal="escribir", application=None, success_check=None,
        view={"window": {"title": "x"}, "controls": [], "text": {}}, history=[], budget_left=5, application_names=APPS,
        subgoal=1, subgoal_count=2,
    )
    assert "Sub-objetivo 2 de 2\nObjetivo: escribir" in model.payloads[0]["messages"][1]["content"]


def test_a_chained_result_is_told_part_by_part_and_never_claims_an_unreached_part() -> None:
    observed = {
        **OBSERVED,
        "reached": False,
        "stoppedBy": "computer_use_no_step_visible",
        "subgoals": [
            {"goal": "ir a biblioteca", "application": "Steam", "reached": True, "stepCount": 2, "satisfiedBy": "page:biblioteca"},
            {"goal": "ir a general", "application": "Discord", "reached": False, "stepCount": 4, "satisfiedBy": None},
        ],
    }
    seen = computer_use.project_seen(observed, "es")
    assert seen["firstUnreached"] == "ir a general" and [part["reached"] for part in seen["subgoals"]] == [True, False]
    assert "seen.firstUnreached" in computer_use.compose_instruction(seen, "es")
    assert computer_use.mission_defect("fui a la biblioteca de steam y despues a general en discord.", seen) == "subgoal_claimed"
    assert computer_use.mission_defect("fui a la biblioteca de steam, pero no pude llegar a general: no vi con que seguir.", seen) is None


def test_an_unserved_order_about_the_pc_is_tried_by_the_engine() -> None:
    apps = ("Discord", "Steam", "Spotify", "Paint")
    for said in ("en Paint dibujá un círculo", "activá el modo oscuro de Discord", "ordená mi escritorio"):
        assert missions.engine_can_try(said, apps), said
    # Never a question, a place outside the PC, a prohibition, or an undoing or paying goal.
    for said in ("¿qué hora es?", "andá a Marte", "no abras Steam", "borrá todos mis archivos", "comprá Hades en Steam"):
        assert not missions.engine_can_try(said, apps), said


def test_the_turn_hands_an_unserved_order_to_the_engine() -> None:
    from baxy_mind.__main__ import _engine_for_an_unserved_order

    limit = {"type": "turn.result", "id": "t", "kind": "conversation", "conversationKind": "unsupported",
             "effectOperations": [], "intentOperations": [], "reply": "", "question": ""}
    tools = {"mission.computer.use": {}}
    tried = _engine_for_an_unserved_order(limit, {"id": "t", "text": "en Paint dibujá un círculo"}, tools, ("Paint",))
    assert tried["kind"] == "plan" and tried["effectOperations"] == ["mission.computer.use"]
    assert tried["objective"] == "en Paint dibujá un círculo"
    kept = _engine_for_an_unserved_order(limit, {"id": "t", "text": "borrá todos mis archivos"}, tools, ("Paint",))
    assert kept is limit
    talk = {**limit, "conversationKind": "talk"}
    assert _engine_for_an_unserved_order(talk, {"id": "t", "text": "en Paint dibujá un círculo"}, tools, ("Paint",)) is talk


def test_sending_what_was_written_is_always_asked_first() -> None:
    # Measured: an Enter not marked as sending delivered «prueba BAXY C6» without asking (Discord's editor exposes no value).
    unexposed = {"window": {"title": "Discord", "focused": {"kind": "Document", "name": "Enviar mensaje a @Ron92"}},
                 "controls": [], "text": {}}
    sent = computer_use.deterministic_step(goal="enviar", view=unexposed, history=[])
    assert sent["arguments"] == {"key": "enter", "target": "message_composer"}
    enter = computer_use.deterministic_step(goal="apretar enter", view=unexposed, history=[])
    assert enter["arguments"]["target"] == "message_composer"
    empty = {**unexposed, "window": {**unexposed["window"], "focused": {**unexposed["window"]["focused"], "value": ""}}}
    assert "target" not in computer_use.deterministic_step(goal="apretar enter", view=empty, history=[])["arguments"]
    assert missions.read_clause("mandalo") == ("enviar", "stepDone:input.key.press:enter")
