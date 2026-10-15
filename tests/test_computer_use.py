"""Motor de computer use, lado mente (CONTRATO_VISTA_ACCION.md): lectura del
pedido, elección de un paso comprobada contra la vista, proyección y vetos."""

from __future__ import annotations

import json

from baxy_mind import computer_use
from baxy_mind import cu_view
from baxy_mind import cu_goals
from baxy_mind import cu_acts
from baxy_mind import cu_window
from baxy_mind import cu_first_look
from baxy_mind import cu_navigation
from baxy_mind import cu_menus
from baxy_mind import cu_rules
from baxy_mind import cu_evidence
from baxy_mind import cu_validate
from baxy_mind import cu_step_prompt
from baxy_mind import cu_projection
from baxy_mind import cu_reply_checks
from baxy_mind import cu_finals
from baxy_mind.semantic import missions
from baxy_mind.semantic.arguments import _explicit_arguments_from_evidence
from baxy_mind.effect_intent import (
    _is_direct_request,
    resolve_explicit_effects,
)
from baxy_mind import engine_handoff
from baxy_mind import computer_use_finals, visible_defect

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
    assert discord["successCheck"] == "control:cotele:current|title:cotele|page:cotele|mark:cotele"

    # Closing every tab is browser.control close_all (confirmed by RiskPolicy), never a mission of loose keys.
    tabs = resolve_explicit_effects("cerrá todas las pestañas de chrome", AVAILABLE, application_names=APPS)
    assert tabs is not None and tabs.operations == ("browser.control",)

    steam = _mission("abre Steam y ve a la biblioteca")
    assert steam["application"] == "Steam"
    assert steam["goal"] == "ir a la biblioteca" or steam["goal"] == "ir a biblioteca"
    assert steam["successCheck"] == "control:biblioteca:current|title:biblioteca|page:biblioteca|control:library:current|title:library|page:library|mark:biblioteca|mark:library"

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
    assert missions.read_clause("escribí hola mundo") == ("escribir hola mundo", missions.WRITTEN_CHECK)
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
    decision = cu_validate.validate_decision(
        {"act": "click", "i": 1, "label": "Biblioteca", "text": "", "key": "", "direction": "", "application": "", "evidence": "", "why": "es la sección"},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"] == {"label": "Biblioteca", "index": 1}
    # A drifted index with the right label is corrected by name.
    drifted = cu_validate.validate_decision(
        {"act": "click", "i": 0, "label": "bibloteca", "text": "", "key": "", "direction": "", "application": "", "evidence": "", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert drifted["arguments"] == {"label": "Biblioteca", "index": 1}
    # A label that is only in the OCR text clicks by label (the cascade finds it).
    ocr_only = cu_validate.validate_decision(
        {"act": "click", "i": -1, "label": "Comunidad", "text": "", "key": "", "direction": "", "application": "", "evidence": "", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert ocr_only["arguments"] == {"label": "Comunidad"}
    # A label nowhere in the view is refused.
    absent = cu_validate.validate_decision(
        {"act": "click", "i": 5, "label": "Descargas", "text": "", "key": "", "direction": "", "application": "", "evidence": "", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert absent["operation"] == "none" and absent["code"] == "label_not_visible"


def test_done_needs_evidence_on_screen_and_failed_steps_are_not_repeated() -> None:
    done = cu_validate.validate_decision(
        {"act": "done", "i": -1, "label": "", "text": "", "key": "", "direction": "", "application": "", "evidence": "Juegos recientes", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert done["operation"] == "done" and done["arguments"] == {"evidence": "Juegos recientes"}
    invented = cu_validate.validate_decision(
        {"act": "done", "i": -1, "label": "", "text": "", "key": "", "direction": "", "application": "", "evidence": "Descargando", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert invented["operation"] == "none" and invented["code"] == "evidence_not_visible"
    repeated = cu_validate.validate_decision(
        {"act": "click", "i": 1, "label": "Biblioteca", "text": "", "key": "", "direction": "", "application": "", "evidence": "", "why": ""},
        view=VIEW, last_failed={"operation": "input.visible.click", "label": "Biblioteca", "ok": False}, application_names=APPS,
    )
    assert repeated["operation"] == "none" and repeated["code"] == "repeated_step"


def test_keys_typing_and_opening_are_checked_against_the_view_and_the_catalog() -> None:
    key = cu_validate.validate_decision(
        {"act": "key", "i": -1, "label": "", "text": "", "key": "enter", "direction": "", "application": "", "evidence": "", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert key == {"operation": "input.key.press", "arguments": {"key": "enter"}, "reason": ""}
    composer_view = {
        "window": {"title": "Ron92 - Discord", "process": "Discord", "focused": {"kind": "Edit", "name": "Enviar mensaje a @Ron92", "value": "hola"}},
        "controls": [],
        "text": {},
    }
    sending = cu_validate.validate_decision(
        {"act": "key", "i": -1, "label": "", "text": "", "key": "enter", "direction": "", "application": "", "evidence": "", "why": ""},
        view=composer_view, last_failed=None, application_names=APPS,
    )
    assert sending["arguments"] == {"key": "enter", "target": "message_composer"}
    password_view = {"window": {"title": "Login"}, "controls": [{"i": 0, "kind": "Edit", "name": "Contraseña", "state": "focused password"}], "text": {}}
    typing = cu_validate.validate_decision(
        {"act": "type", "i": -1, "label": "", "text": "secreto", "key": "", "direction": "", "application": "", "evidence": "", "why": ""},
        view=password_view, last_failed=None, application_names=APPS,
    )
    assert typing["operation"] == "none" and typing["code"] == "password_field"
    opening = cu_validate.validate_decision(
        {"act": "open", "i": -1, "label": "", "text": "", "key": "", "direction": "", "application": "Steam", "evidence": "", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert opening == {"operation": "app.open", "arguments": {"appId": "Steam"}, "reason": ""}
    unknown = cu_validate.validate_decision(
        {"act": "open", "i": -1, "label": "", "text": "", "key": "", "direction": "", "application": "Photoshop", "evidence": "", "why": ""},
        view=VIEW, last_failed=None, application_names=APPS,
    )
    assert unknown["operation"] == "none"


def test_the_model_opens_only_an_application_the_request_names() -> None:
    # Banco r6 (t-drag-3): a word of an app's name in the request («pantalla») is no order to open that app; the
    # always-on-top window the model opened covered every later case.
    apps = (*APPS, "Teclado en pantalla", "Notas rápidas")
    act = {"act": "open", "i": -1, "label": "", "text": "", "key": "", "direction": "", "evidence": "", "why": ""}
    guessed = cu_validate.validate_decision(
        {**act, "application": "Teclado en pantalla"}, view=VIEW, last_failed=None, application_names=apps,
        objective="agarrá la nota adhesiva que dice «baxy prueba» y llevala arrastrando a la esquina de arriba a la "
        "derecha de la pantalla",
        goal="arrastrar la nota adhesiva a la esquina de arriba a la derecha de la pantalla",
    )
    assert guessed["operation"] == "none" and guessed["code"] == "application_not_requested"
    # Counter-cases: the request names it, by its name or by an alias of it, in any part of a chained request.
    named = cu_validate.validate_decision(
        {**act, "application": "Teclado en pantalla"}, view=VIEW, last_failed=None, application_names=apps,
        objective="abrí el teclado en pantalla", goal="abrir teclado en pantalla",
    )
    assert named == {"operation": "app.open", "arguments": {"appId": "Teclado en pantalla"}, "reason": ""}
    alias = cu_validate.validate_decision(
        {**act, "application": "Bloc de notas"}, view=VIEW, last_failed=None, application_names=apps,
        objective="en la calculadora calculá 12*12, copiá el resultado y pegalo en el Bloc de notas",
        goal="pegar en el bloc de notas",
    )
    assert alias["operation"] == "app.open"
    chained = cu_validate.validate_decision(
        {**act, "application": "Steam"}, view=VIEW, last_failed=None, application_names=apps,
        objective="en Discord andá al canal Cotele y después en Steam andá a la tienda", goal="ir a la tienda",
    )
    assert chained["operation"] == "app.open" and chained["arguments"] == {"appId": "Steam"}
    # A distinctive word of a longer name names it, as the mission reader takes it («edge», «teams»): only an ordinary
    # word one name contains («pantalla») does not.
    for objective, said, app in (
        ("en edge buscá gatos", "Microsoft Edge", "Microsoft Edge"),
        ("en teams mandale hola a Juan", "Microsoft Teams", "Microsoft Teams"),
        ("en la store buscá spotify", "Microsoft Store", "Microsoft Store"),
    ):
        short = cu_validate.validate_decision(
            {**act, "application": said}, view=VIEW, last_failed=None,
            application_names=(*apps, "Microsoft Edge", "Microsoft Teams", "Microsoft Store"), objective=objective,
            goal=objective,
        )
        assert short == {"operation": "app.open", "arguments": {"appId": app}, "reason": ""}, objective
    # The mission's own application (the planner's, said shorter in the request) is always one to open.
    own = cu_validate.validate_decision(
        {**act, "application": "Teclado en pantalla"}, view=VIEW, last_failed=None, application_names=apps,
        objective="en el teclado de la pantalla apretá la tecla Mayús", goal="apretar mayús",
        application="Teclado en pantalla",
    )
    assert own["operation"] == "app.open"
    # Without a request to ground it (an older caller), the catalog check alone decides, as before.
    assert cu_validate.validate_decision(
        {**act, "application": "Steam"}, view=VIEW, last_failed=None, application_names=apps,
    )["operation"] == "app.open"


def test_compact_view_text_is_short_and_names_every_control() -> None:
    text = cu_step_prompt.compact_view_text(VIEW)
    assert "ventana: «Steam» (steamwebhelper)" in text
    assert "1 · Button · «Biblioteca» · T · blue" in text
    assert "texto T: TIENDA | BIBLIOTECA | COMUNIDAD" in text
    assert len(text) < 600


def test_application_in_front_matches_by_title_or_process_tokens() -> None:
    assert cu_window.application_is_in_front(VIEW, "Steam")
    assert not cu_window.application_is_in_front(VIEW, "Discord")
    assert cu_window.application_is_in_front({"window": {"title": "Nueva pestaña", "process": "chrome"}}, "Google Chrome")
    assert cu_window.application_is_in_front({"window": {"title": "Configuración", "process": "SystemSettings"}}, "Configuración")


def test_a_window_whose_name_shares_one_word_with_the_application_is_not_it() -> None:
    # v3-36 r7: «notas» of «Notas rápidas» in the Notepad's title took the Notepad in front for the notes app.
    notepad = {"window": {"title": "lista.txt: Bloc de notas", "process": "Notepad"}}
    assert not cu_window.application_is_in_front(notepad, "Notas rápidas")
    assert not cu_window.application_is_in_front({"window": {"title": "Ayuda de Windows", "process": "x"}}, "Reproductor multimedia (Windows 11)")
    # Contracase: a title made only of the name's own words still names it.
    assert cu_window.application_is_in_front({"window": {"title": "Reproductor multimedia", "process": "x"}}, "Reproductor multimedia (Windows 11)")
    assert cu_window.application_is_in_front({"window": {"title": "Documento1 - Word", "process": "x"}}, "Microsoft Word")
    assert cu_window.application_is_in_front({"window": {"title": "Notas rápidas", "process": "x"}}, "Notas rápidas")
    assert cu_window.application_is_in_front(notepad, "Bloc de notas")


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
    seen = cu_projection.project_seen(OBSERVED, "es")
    assert seen["reached"] is True
    assert seen["stepsDone"] == ["trajo la aplicación al frente", "clic en «Biblioteca»"]
    assert seen["windowTitle"] == "Steam"
    assert seen["joined"] is False
    assert "surfaceChanged" not in str(seen)


def test_mission_vetoes() -> None:
    seen = cu_projection.project_seen(OBSERVED, "es")
    assert cu_reply_checks.mission_defect("abri steam y fui a la biblioteca.", seen) is None
    assert cu_reply_checks.mission_defect("ayer fui a la biblioteca de steam.", seen) == "extra_claim"
    assert cu_reply_checks.mission_defect("me uni al canal de voz.", seen) == "joined_claimed"
    joined = cu_projection.project_seen({**OBSERVED, "joined": True}, "es")
    assert cu_reply_checks.mission_defect("entre al canal de voz cotele.", joined) is None
    assert cu_reply_checks.mission_defect("no me uni al canal.", joined) == "joined_claimed"
    failed = cu_projection.project_seen({**OBSERVED, "reached": False, "stoppedBy": "computer_use_no_step_visible"}, "es")
    assert cu_reply_checks.mission_defect("listo, ya estas en la biblioteca.", failed) == "reversed_polarity"
    assert cu_reply_checks.mission_defect("no pude llegar a la biblioteca: no encontre el control.", failed) is None


def test_covered_window_names_the_cover_in_the_cause():
    covered = cu_projection.project_seen(
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
    plain = cu_projection.project_seen({**OBSERVED, "reached": False, "stoppedBy": "computer_use_window_covered"}, "en")
    assert plain["stoppedBecause"] == "another window covers the application"


# ------------------------------------------------------- pasos dictados


def test_deterministic_steps_follow_the_goal_family_and_the_view() -> None:
    calc = cu_rules.deterministic_step(goal="calcular 12×7", view=VIEW, history=[])
    assert calc == {"operation": "input.text.type", "arguments": {"text": "12*7"}, "reason": "el objetivo lo dice"}
    typed = [{"step": 1, "operation": "input.text.type", "text": "12*7", "ok": True}]
    assert cu_rules.deterministic_step(goal="calcular 12×7", view=VIEW, history=typed)["arguments"] == {"key": "enter"}
    entered = typed + [{"step": 2, "operation": "input.key.press", "key": "enter", "ok": True}]
    assert cu_rules.deterministic_step(goal="calcular 12×7", view=VIEW, history=entered) is None
    key = cu_rules.deterministic_step(goal="apretar enter", view=VIEW, history=[])
    # The focus of this window cannot be read: Enter may send what was written, so it is asked first.
    assert key == {"operation": "input.key.press", "arguments": {"key": "enter", "target": "message_composer"}, "reason": "el objetivo lo dice"}
    go = cu_rules.deterministic_step(goal="ir a la biblioteca", view=VIEW, history=[])
    assert go["operation"] == "input.visible.click" and go["arguments"] == {"label": "Biblioteca", "index": 1}
    # Not on screen: the focused search field takes the name (the FIND routine below).
    assert cu_rules.deterministic_step(goal="ir a descargas", view=VIEW, history=[])["arguments"] == {"text": "descargas"}
    # A failed click by label alone is found again by identity; the same act failed again hands it to the model.
    failed = [{"step": 1, "operation": "input.visible.click", "label": "Biblioteca", "ok": False}]
    assert cu_rules.deterministic_step(goal="ir a la biblioteca", view=VIEW, history=failed)["arguments"] == {"label": "Biblioteca", "index": 1}
    failed_again = [{"step": 1, "operation": "input.visible.click", "label": "Biblioteca", "index": 1, "ok": False}]
    # The same act failed again: the place is looked up instead (the window's search), never clicked once more.
    again = cu_rules.deterministic_step(goal="ir a la biblioteca", view=VIEW, history=failed_again)
    assert again is not None and again["arguments"] != {"label": "Biblioteca", "index": 1}
    assert again["arguments"].get("text") in (None, "biblioteca")
    toggle_view = {"window": {"title": "Configuración"}, "controls": [{"i": 4, "kind": "Button", "name": "Modo avión", "state": "off"}], "text": {}}
    on = cu_rules.deterministic_step(goal="activar modo avion", view=toggle_view, history=[])
    assert on["arguments"] == {"label": "Modo avión", "index": 4}
    already = {"window": {"title": "Configuración"}, "controls": [{"i": 4, "kind": "Button", "name": "Modo avión", "state": "on"}], "text": {}}
    assert cu_rules.deterministic_step(goal="activar modo avion", view=already, history=[]) is None


def test_a_failed_open_with_the_application_in_front_does_not_stop_the_dictated_steps() -> None:
    failed_open = [{"step": 1, "operation": "app.open", "appId": "Calculadora", "ok": False, "error": "verification_failed"}]
    calc_view = {"window": {"title": "Calculadora", "process": "CalculatorApp", "focused": None}, "controls": [{"i": 0, "kind": "Button", "name": "Uno"}], "text": {}}
    typed = cu_rules.deterministic_step(goal="calcular 12×7", view=calc_view, history=failed_open, application="Calculadora")
    assert typed == {"operation": "input.text.type", "arguments": {"text": "12*7"}, "reason": "el objetivo lo dice"}
    elsewhere = {"window": {"title": "Program Manager", "process": "explorer", "focused": None}, "controls": [], "text": {}}
    assert cu_rules.deterministic_step(goal="calcular 12×7", view=elsewhere, history=failed_open, application="Calculadora") is None


def test_mission_arguments_ground_without_a_literal_check() -> None:
    from baxy_mind.argument_grounding import _ground_explicit_arguments

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
        "application": "Bloc de notas", "goal": "escribir hola", "successCheck": missions.WRITTEN_CHECK,
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
    step = cu_rules.deterministic_step(
        goal="ir a la pestaña youtube", view=view, history=[], application=missions.BROWSER_CATEGORY,
    )
    assert step == {
        "operation": "input.visible.click",
        "arguments": {"label": "Rick Astley - Never Gonna Give You Up - YouTube", "index": 1},
        "reason": "el objetivo lo dice",
    }
    # Without the kind, the link and the tab both name YouTube and only the exact name is taken.
    assert cu_view.find_control(view, "youtube")["i"] == 2
    assert cu_view.find_control(view, "youtube", kind="TabItem")["i"] == 1
    clicked = [{"step": 1, "operation": "input.visible.click", "label": "Rick Astley - Never Gonna Give You Up - YouTube", "ok": True}]
    assert cu_rules.deterministic_step(goal="ir a la pestaña youtube", view=view, history=clicked) is None


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
    # Encargo IMP2 (imp1 imp-wa-enviar: the typed WhatsApp send failed, no v3 send by WhatsApp ever held): a message to
    # someone in WhatsApp is now the mission that sends in Discord (data conversation_acts «sendInPlace»), no longer
    # left to the decider; the loose verbs of other applications still are.
    assert _route("en WhatsApp escribile a Ron92 hola") == ("mission.computer.use",)
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
    name_only = cu_validate.validate_decision(
        {"act": "done", "evidence": "BIBLIOTECA"}, view=view, last_failed=None, application_names=APPS, goal="ir a biblioteca",
    )
    assert name_only["operation"] == "none" and name_only["code"] == "evidence_not_visible"
    reached = cu_validate.validate_decision(
        {"act": "done", "evidence": "TUS COLECCIONES"}, view=view, last_failed=None, application_names=APPS, goal="ir a biblioteca",
    )
    assert reached["operation"] == "done"
    # Banco r23b u1: the music player's library panel already expanded, a grid named as the place with its rows. The
    # grid is the place shown, not a label of it: the done citing it stands. Its header or its toggle alone do not.
    panel = {"window": {"title": "Spotify Premium", "process": "Spotify"}, "controls": [
        {"i": 0, "kind": "Button", "name": "Comprimir Tu biblioteca"}, {"i": 1, "kind": "Text", "name": "Tu biblioteca"},
        {"i": 2, "kind": "DataGrid", "name": "Tu biblioteca"}, {"i": 3, "kind": "DataItem", "name": "Canciones que te gustan"},
    ]}
    shown = cu_validate.validate_decision(
        {"act": "done", "evidence": "Tu biblioteca"}, view=panel, last_failed=None, application_names=APPS,
        goal="ir a tu biblioteca",
    )
    assert shown["operation"] == "done"
    panel["controls"] = panel["controls"][:2]
    header = cu_validate.validate_decision(
        {"act": "done", "evidence": "Tu biblioteca"}, view=panel, last_failed=None, application_names=APPS,
        goal="ir a tu biblioteca",
    )
    assert header["operation"] == "none" and header["code"] == "evidence_not_visible"
    # The text of the destination alone no longer satisfies a go-to: only the place selected or titled does.
    assert missions.read_clause("andá a la biblioteca")[1] == "control:biblioteca:current|title:biblioteca|page:biblioteca|control:library:current|title:library|page:library|mark:biblioteca|mark:library"


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
    step = cu_rules.deterministic_step(goal="ir a general", view=CHAT, history=[])
    assert step["operation"] == "input.visible.click" and step["arguments"] == {"label": "Buscar", "index": 0, "search": "general"}
    clicked = [_ok(1, "input.visible.click", label="Buscar")]
    searching = {**CHAT, "window": {**CHAT["window"], "focused": {"kind": "Edit", "name": "Buscar", "value": ""}}}
    assert cu_rules.deterministic_step(goal="ir a general", view=searching, history=clicked)["arguments"] == {"text": "general"}
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
    picked = cu_rules.deterministic_step(goal="ir a general", view=results, history=typed)
    # The list item, never the field that echoes the name, and never Enter (a voice channel stays a confirmed click).
    assert picked["operation"] == "input.visible.click" and picked["arguments"] == {"label": "general · Mi servidor", "index": 2}
    # A window without an accessible tree: the new line that is more than the typed name.
    ocr_only = {"window": {"title": "Steam"}, "controls": [], "newText": ["batman", "Batman: Arkham Knight"], "text": {"C": ["batman", "Batman: Arkham Knight"]}}
    batman = [_ok(1, "input.visible.click", label="Buscar"), _ok(2, "input.text.type", text="batman")]
    assert cu_rules.deterministic_step(goal="ir a batman", view=ocr_only, history=batman)["arguments"] == {"label": "Batman: Arkham Knight"}
    # Nothing names it: the search is closed and the next way is tried.
    empty = {"window": {"title": "Steam"}, "controls": [], "newText": [], "text": {}}
    assert cu_rules.deterministic_step(goal="ir a batman", view=empty, history=batman)["arguments"] == {"key": "escape"}
    escaped = batman + [_ok(3, "input.key.press", key="escape")]
    assert cu_rules.deterministic_step(goal="ir a batman", view=empty, history=escaped)["arguments"] == {"key": "ctrl_k"}


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
    assert cu_rules.deterministic_step(goal="ir a general", view=plain, history=[])["arguments"] == {"key": "ctrl_k"}
    after_k = [_ok(1, "input.key.press", key="ctrl_k")]
    switcher = {
        **plain,
        "window": {**plain["window"], "focused": {"kind": "Edit", "name": "", "value": ""}},
        "newText": ["Busca servidores, canales o MD"],
    }
    assert cu_rules.deterministic_step(goal="ir a general", view=switcher, history=after_k)["arguments"] == {"text": "general"}
    # The shortcut opened nothing: escape, then ctrl_f, then the list that holds the items.
    assert cu_rules.deterministic_step(goal="ir a general", view=plain, history=after_k)["arguments"] == {"key": "escape"}
    tried = after_k + [
        _ok(2, "input.key.press", key="escape"), _ok(3, "input.key.press", key="ctrl_f"), _ok(4, "input.key.press", key="escape"),
    ]
    scroll = cu_rules.deterministic_step(goal="ir a general", view=plain, history=tried)
    assert scroll["operation"] == "input.scroll" and scroll["arguments"] == {"direction": "down", "amount": 5, "index": 3}
    scrolled = tried + [_ok(5 + n, "input.scroll", direction="down") for n in range(3)]
    assert cu_rules.deterministic_step(goal="ir a general", view=plain, history=scrolled) is None
    unchanged = tried + [{"step": 5, "operation": "input.scroll", "ok": True, "changed": False}, _ok(6, "input.key.press", key="escape")]
    assert cu_rules.deterministic_step(goal="ir a general", view=plain, history=unchanged) is None


def test_find_never_types_into_a_composer_or_the_address_bar() -> None:
    composer = {
        "window": {
            "title": "#off-topic - Discord", "process": "Discord",
            "focused": {"kind": "Edit", "name": "Enviar mensaje a #off-topic", "value": ""},
        },
        "controls": [], "newText": ["algo"], "text": {},
    }
    after_k = [_ok(1, "input.key.press", key="ctrl_k")]
    assert cu_rules.deterministic_step(goal="ir a general", view=composer, history=after_k)["arguments"] == {"key": "escape"}
    browser = {
        "window": {"title": "Nueva pestaña - Google Chrome", "process": "chrome", "focused": None},
        "controls": [{"i": 0, "kind": "Edit", "name": "Barra de direcciones y de búsqueda", "state": ""}],
        "text": {},
    }
    assert cu_rules.deterministic_step(goal="ir a general", view=browser, history=[])["arguments"] == {"key": "ctrl_k"}


def test_an_english_goal_finds_the_spanish_control() -> None:
    step = cu_rules.deterministic_step(goal="ir a library", view=VIEW, history=[])
    assert step["arguments"] == {"label": "Biblioteca", "index": 1}
    check = missions.read_clause("go to the library")[1]
    assert "control:library:current" in check and "control:biblioteca:current" in check


def test_a_menu_entry_named_by_the_goal_wins_over_the_first_one() -> None:
    menu = {"window": {"title": "Steam"}, "controls": [], "newText": ["Página principal", "Colecciones", "Descargas"], "text": {}}
    clicked = [_ok(1, "input.visible.click", label="BIBLIOTECA")]
    named = cu_rules.deterministic_step(goal="ir a descargas de la biblioteca", view=menu, history=clicked)
    assert named["arguments"] == {"label": "Descargas"}
    first = cu_rules.deterministic_step(goal="ir a biblioteca", view=menu, history=clicked)
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
    covering = cu_validate.validate_decision({"act": "click", "i": 0}, view=view, last_failed=None, application_names=APPS)
    assert covering["operation"] == "none" and covering["code"] == "control_covers_window"
    button = cu_validate.validate_decision({"act": "click", "i": 1}, view=view, last_failed=None, application_names=APPS)
    assert button["arguments"] == {"label": "Siguiente", "index": 1}
    twice = [_ok(1, "input.visible.click", label="Siguiente"), _ok(2, "input.visible.click", label="Siguiente")]
    idle = cu_validate.validate_decision({"act": "click", "i": 1}, view=view, last_failed=None, application_names=APPS, history=twice)
    assert idle["operation"] == "none" and idle["code"] == "no_progress"
    moving = cu_validate.validate_decision(
        {"act": "click", "i": 1}, view={**view, "newText": ["Página 3"]}, last_failed=None, application_names=APPS, history=twice,
    )
    assert moving["operation"] == "input.visible.click"


# ------------------------------------------------------- el navegador: su marco y la página
# Synthetic views shaped like the live failure of 2026-10-07 (Opera, «buscá Ñuñoa» on es.wikipedia.org): the
# frame (tab strip with its tab search, address bar, bookmarks) above the page, the page a large document.

def _rect(x: int, y: int, w: int, h: int) -> dict:
    return {"x": x, "y": y, "w": w, "h": h}


_FRAME = [
    {"i": 0, "kind": "Button", "name": "Buscar pestañas", "rect": _rect(1420, 5, 37, 37)},
    {"i": 1, "kind": "Edit", "name": "Barra de direcciones", "value": "", "rect": _rect(160, 54, 1200, 37)},
    {"i": 2, "kind": "TabItem", "name": "Ciudad - Wikipedia, la enciclopedia libre", "state": "selected", "rect": _rect(100, 5, 240, 37)},
    {"i": 3, "kind": "Button", "name": "Nueva pestaña", "rect": _rect(344, 13, 22, 22)},
    {"i": 4, "kind": "Edit", "name": "Campo de dirección", "value": "https://es.wikipedia.org/wiki/Ciudad", "rect": _rect(210, 54, 970, 37)},
    {"i": 5, "kind": "Button", "name": "Marcador uno", "rect": _rect(60, 95, 180, 37)},
]
BROWSER_LOADING = {
    "window": {"title": "es.wikipedia.org/wiki/Ciudad - Navegador", "process": "browser", "rect": _rect(0, 0, 1575, 965), "focused": None},
    "controls": [*_FRAME, {"i": 6, "kind": "Document", "name": "Cargando…", "rect": _rect(106, 13, 22, 22)}],
    "text": {"TR": ["Q Buscar pestañas"]},
}
BROWSER_PAGE = {
    "window": {
        "title": "Ciudad - Wikipedia, la enciclopedia libre - Navegador", "process": "browser", "rect": _rect(0, 0, 1575, 965),
        "focused": {"kind": "Document", "name": "Ciudad - Wikipedia, la enciclopedia libre", "value": "https://es.wikipedia.org/wiki/Ciudad"},
    },
    "controls": [
        *_FRAME,
        {"i": 6, "kind": "Document", "name": "Ciudad - Wikipedia, la enciclopedia libre", "state": "readonly focused", "rect": _rect(53, 136, 1519, 825)},
        {"i": 7, "kind": "Edit", "name": "Buscar en Wikipedia", "value": "", "rect": _rect(435, 157, 506, 41)},
        {"i": 8, "kind": "Button", "name": "Buscar", "rect": _rect(939, 157, 90, 41)},
    ],
    "text": {"TR": ["Q Buscar pestañas"], "T": ["Buscar en Wikipedia"]},
}


def test_a_search_in_a_browser_uses_the_pages_field_never_the_tab_search() -> None:
    # The page is there: its own search field, never the tab strip's «Buscar pestañas» (measured: clicked first).
    step = cu_rules.deterministic_step(goal="buscar Ñuñoa", view=BROWSER_PAGE, history=[])
    assert step["operation"] == "input.visible.click" and step["arguments"] == {"label": "Buscar en Wikipedia", "index": 7}
    clicked = [_ok(1, "input.visible.click", label="Buscar en Wikipedia", index=7)]
    assert cu_rules.deterministic_step(goal="buscar Ñuñoa", view=BROWSER_PAGE, history=clicked)["arguments"] == {"text": "Ñuñoa"}
    typed = clicked + [_ok(2, "input.text.type", text="Ñuñoa")]
    assert cu_rules.deterministic_step(goal="buscar Ñuñoa", view=BROWSER_PAGE, history=typed)["arguments"]["key"] == "enter"
    # The page still loading shows only the frame: nothing of it is the page's search, its written lines neither, and
    # ctrl_k (the web search of the address bar) is not the page's: only the page's find.
    loading = cu_rules.deterministic_step(goal="buscar Ñuñoa", view=BROWSER_LOADING, history=[])
    assert loading == {"operation": "input.key.press", "arguments": {"key": "ctrl_f"}, "reason": cu_acts._REASON_FIND}


def test_a_browser_result_is_the_one_in_the_page_that_is_exactly_the_name() -> None:
    suggestions = {
        **BROWSER_PAGE,
        "controls": [
            *BROWSER_PAGE["controls"][:2],
            {"i": 2, "kind": "TabItem", "name": "Ñuñoa - Wikipedia", "rect": _rect(100, 5, 240, 37)},
            *BROWSER_PAGE["controls"][3:],
            {"i": 9, "kind": "ListItem", "name": "Festival Internacional de la Canción de Ñuñoa", "rect": _rect(435, 200, 506, 30)},
            {"i": 10, "kind": "ListItem", "name": "Ñuñoa", "rect": _rect(435, 230, 506, 30)},
        ],
    }
    typed = [_ok(1, "input.visible.click", label="Buscar en Wikipedia"), _ok(2, "input.text.type", text="Ñuñoa")]
    picked = cu_rules.deterministic_step(goal="ir a Ñuñoa", view=suggestions, history=typed)
    assert picked["arguments"] == {"label": "Ñuñoa", "index": 10}


def test_a_file_explorer_keeps_its_search_box_beside_the_address_bar() -> None:
    explorer = {
        "window": {"title": "Descargas - Explorador de archivos", "process": "explorer", "rect": _rect(0, 0, 1200, 800), "focused": None},
        "controls": [
            {"i": 0, "kind": "Edit", "name": "Barra de direcciones", "value": "C:\\Users\\persona\\Downloads", "rect": _rect(200, 60, 700, 30)},
            {"i": 1, "kind": "Edit", "name": "Buscar en Descargas", "value": "", "rect": _rect(920, 60, 260, 30)},
        ],
        "text": {},
    }
    step = cu_rules.deterministic_step(goal="buscar informe", view=explorer, history=[])
    assert step["arguments"] == {"label": "Buscar en Descargas", "index": 1}


def test_the_model_may_not_open_another_tab_unless_the_goal_says_so() -> None:
    refused = cu_validate.validate_decision(
        {"act": "click", "i": 3}, view=BROWSER_PAGE, last_failed=None, application_names=APPS, goal="buscar Ñuñoa",
    )
    assert refused["operation"] == "none" and refused["code"] == "opens_elsewhere"
    assert "opens_elsewhere" in computer_use._RETRIED
    by_text = cu_validate.validate_decision(
        {"act": "click", "text": "Open in new tab"}, view={**BROWSER_PAGE, "text": {"C": ["Open in new tab"]}},
        last_failed=None, application_names=APPS, goal="go to history",
    )
    assert by_text["code"] == "opens_elsewhere"
    asked = cu_validate.validate_decision(
        {"act": "click", "i": 3}, view=BROWSER_PAGE, last_failed=None, application_names=APPS, goal="abrir una pestaña nueva",
    )
    assert asked["arguments"] == {"label": "Nueva pestaña", "index": 3}
    # The page document covers most of the window: a click on it is no place to go.
    body = cu_validate.validate_decision({"act": "click", "i": 6}, view=BROWSER_PAGE, last_failed=None, application_names=APPS, goal="ir a historia")
    assert body["code"] == "control_covers_window"


# ------------------------------------------------------- misiones encadenadas

CHAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "application": {"type": ["string", "null"], "x-maxUtf8Bytes": 128},
        "budgetSteps": {"type": ["integer", "null"], "minimum": 1, "maximum": 30},
        "goal": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
        "successCheck": {"type": ["string", "null"], "x-maxUtf8Bytes": 512},
        "steps": {
            "type": "array", "minItems": 1, "maxItems": 10,
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
    assert chained["steps"][1]["successCheck"] == "control:general:current|title:general|page:general|mark:general"
    assert chained["goal"] == "ir a biblioteca; luego ir a general"
    # Typing into a place: go to it, then type; the application is carried forward.
    typing = missions.mission_request("en Discord andá a general y escribí hola", MORE_APPS).arguments()
    assert typing["steps"] == [
        {"goal": "ir a general", "application": "Discord", "successCheck": "control:general:current|title:general|page:general|mark:general"},
        {"goal": "escribir hola", "application": "Discord", "successCheck": missions.WRITTEN_CHECK},
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
    from baxy_mind.argument_grounding import _ground_explicit_arguments

    said = "en Discord andá a general y escribí hola, después en Steam andá a la biblioteca"
    assert _route(said) == ("mission.computer.use",)
    assert _is_direct_request("andá a la biblioteca en Steam y después a general en Discord")
    grounded = _ground_explicit_arguments("mission.computer.use", said, CHAIN_SCHEMA, MORE_APPS)
    assert grounded is not None and len(grounded["steps"]) == 3 and grounded["steps"][2]["application"] == "Steam"
    # v3 punto 2 (A7): a clause the reader cannot check is a free sub-goal of the chain, beside at least as many checked
    # ones, instead of leaving the whole turn to the decider; the place before it stays clean.
    assert _route("abre Steam, ve a la biblioteca y dibujá a Batman") == ("mission.computer.use",)
    batman = missions.mission_request("abre Steam, ve a la biblioteca y dibujá a Batman", MORE_APPS)
    assert batman is not None and [(step.goal, step.free) for step in batman.steps] == [
        ("ir a biblioteca", False), ("dibujá a Batman", True)]
    assert batman.steps[1].success_check is None
    # Searching is checked now (the name typed and submitted, or the page titled with it): the engine's.
    assert _route("abre Steam, ve a la biblioteca y busca Batman") == ("mission.computer.use",)


def test_a_free_form_goal_is_the_persons_clause_with_the_app_it_names() -> None:
    from baxy_mind.argument_grounding import _ground_explicit_arguments

    turned = _ground_explicit_arguments("mission.computer.use", "en Paint girá la imagen a la derecha", CHAIN_SCHEMA, MORE_APPS)
    assert turned == {"goal": "en Paint girá la imagen a la derecha", "application": "Paint"}
    # Estabilización L: a drawing is the drag limit, never the engine's goal.
    assert _ground_explicit_arguments("mission.computer.use", "en Paint dibujá un círculo rojo", CHAIN_SCHEMA, MORE_APPS) is None
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
    seen = cu_projection.project_seen(observed, "es")
    assert seen["firstUnreached"] == "ir a general" and [part["reached"] for part in seen["subgoals"]] == [True, False]
    assert "seen.firstUnreached" in cu_projection.compose_instruction(seen, "es")
    # Estabilización R1: an unreached part told as done is judged once, by the composer (unreached_claim over
    # subgoals[].reached, which exempts what a verified step backs, and missing_failure for a failed mission told as
    # done); the mission's own twin «subgoal_claimed» vetoed true failure finals (pasada r27 t-menu-3 «I opened View and
    # clicked Zoom once»: 0 right, 5 harmless, 1 right that unreached_claim or polarity also catch).
    failed = {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
        "reason": {"kind": "operation", "operation": "mission.computer.use", "polarity": "failure",
                   "verified": False, "succeeded": False, "error": observed["stoppedBy"], "observed": observed},
    }
    facts = {"situation": json.dumps(failed, ensure_ascii=False)}
    said = "en Steam andá a biblioteca y en Discord andá a general"
    assert computer_use_finals._computer_use_final_defect("Llegué a general en Discord.", failed) == "unreached_claim"
    assert visible_defect.compose_visible_defect("Fui a la biblioteca de Steam y después a general en Discord.", "status", said, facts)
    assert cu_reply_checks.mission_defect("fui a la biblioteca de steam y despues a general en discord.", seen) is None
    assert cu_reply_checks.mission_defect("fui a la biblioteca de steam, pero no pude llegar a general: no vi con que seguir.", seen) is None
    assert not computer_use_finals._computer_use_final_defect(
        "Fui a la biblioteca de Steam, pero no pude llegar a general: no vi con qué seguir.", failed
    )


def test_an_unserved_order_about_the_pc_is_tried_by_the_engine() -> None:
    apps = ("Discord", "Steam", "Spotify", "Paint")
    for said in ("en Paint girá la imagen a la derecha", "activá el modo oscuro de Discord", "ordená mi escritorio"):
        assert missions.engine_can_try(said, apps), said
    # Estabilización L: a drawing is a declared limit the engine has no act for.
    assert not missions.engine_can_try("en Paint dibujá un círculo", apps)
    # Never a question, a place outside the PC, a prohibition, or an undoing or paying goal.
    for said in ("¿qué hora es?", "andá a Marte", "no abras Steam", "borrá todos mis archivos", "comprá Hades en Steam"):
        assert not missions.engine_can_try(said, apps), said


def test_the_turn_hands_an_unserved_order_to_the_engine() -> None:
    from baxy_mind.engine_handoff import _engine_for_an_unserved_order

    limit = {"type": "turn.result", "id": "t", "kind": "conversation", "conversationKind": "unsupported",
             "effectOperations": [], "intentOperations": [], "reply": "", "question": ""}
    tools = {"mission.computer.use": {}}
    tried = _engine_for_an_unserved_order(limit, {"id": "t", "text": "en Paint girá la imagen a la derecha"}, tools, ("Paint",))
    assert tried["kind"] == "plan" and tried["effectOperations"] == ["mission.computer.use"]
    assert tried["objective"] == "en Paint girá la imagen a la derecha"
    # Estabilización L: the drag limit stays the limit the turn says.
    drawn = _engine_for_an_unserved_order(limit, {"id": "t", "text": "en Paint dibujá un círculo"}, tools, ("Paint",))
    assert drawn is limit
    kept = _engine_for_an_unserved_order(limit, {"id": "t", "text": "borrá todos mis archivos"}, tools, ("Paint",))
    assert kept is limit
    talk = {**limit, "conversationKind": "talk"}
    assert _engine_for_an_unserved_order(talk, {"id": "t", "text": "en Paint girá la imagen a la derecha"}, tools, ("Paint",)) is talk


def test_sending_what_was_written_is_always_asked_first() -> None:
    # Measured: an Enter not marked as sending delivered «prueba BAXY C6» without asking (Discord's editor exposes no value).
    unexposed = {"window": {"title": "Discord", "focused": {"kind": "Document", "name": "Enviar mensaje a @Ron92"}},
                 "controls": [], "text": {}}
    sent = cu_rules.deterministic_step(goal="enviar", view=unexposed, history=[])
    assert sent["arguments"] == {"key": "enter", "target": "message_composer"}
    enter = cu_rules.deterministic_step(goal="apretar enter", view=unexposed, history=[])
    assert enter["arguments"]["target"] == "message_composer"
    empty = {**unexposed, "window": {**unexposed["window"], "focused": {**unexposed["window"]["focused"], "value": ""}}}
    assert "target" not in cu_rules.deterministic_step(goal="apretar enter", view=empty, history=[])["arguments"]
    assert missions.read_clause("mandalo") == ("enviar", "stepDone:input.key.press:enter")


def test_find_clicks_a_written_search_box_when_the_window_has_no_tree_then_types() -> None:
    # Measured on WhatsApp: UIA exposed only the caption buttons; OCR read the search box.
    written = {
        "window": {"title": "WhatsApp", "process": "WhatsApp.Root", "focused": None},
        "controls": [{"i": 0, "kind": "Button", "name": "Minimize"}, {"i": 1, "kind": "Button", "name": "Close"}],
        "text": {"TL": ["WhatsApp", "Chats", "Q, Buscar un chat o iniciar uno nuevo", "Buscar un chat o iniciar uno nuevo", "Todos"]},
    }
    step = cu_rules.deterministic_step(goal="ir a ron92", view=written, history=[])
    assert step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Buscar un chat o iniciar uno nuevo"}
    clicked = [_ok(1, "input.visible.click", label="Buscar un chat o iniciar uno nuevo")]
    # The next look must prove the box took the keyboard: the same lines after the click prove nothing, so nothing
    # is typed and the mission says it could not.
    unproven = cu_rules.deterministic_step(goal="ir a ron92", view={**written, "newText": []}, history=clicked)
    assert unproven["operation"] == "none" and unproven["code"] == "search_focus_unproven"
    # Its placeholder cleared for the caret (the line is gone, the rest of the window stayed): the name is typed.
    cleared = {**written, "text": {"TL": ["WhatsApp", "Chats", "Q,", "Todos"]}, "newText": ["Q,"]}
    assert cu_rules.deterministic_step(goal="ir a ron92", view=cleared, history=clicked)["arguments"] == {"text": "ron92"}


# ------------------------------------------------- revisión de seguridad 2026-10-07

def _key_act(key: str) -> dict:
    return {"act": "key", "i": -1, "label": "", "text": "", "key": key, "direction": "", "application": "", "evidence": "", "why": ""}


def test_an_editor_whose_title_mentions_the_application_is_never_taken_for_it() -> None:
    editor = {"window": {"title": "SteamLocalAdapter.cs - BAXY Definitivo - Visual Studio Code", "process": "Code"}}
    assert not cu_window.application_is_in_front(editor, "Steam")
    # Not even when the provider says it resolved it: a developer's or BAXY's own window is not the application.
    assert not cu_window.application_is_in_front({"window": {**editor["window"], "requested": True}}, "Steam")
    assert not cu_window.application_is_in_front({"window": {"title": "Steam - Windows PowerShell", "process": "powershell"}}, "Steam")
    assert not cu_window.application_is_in_front({"window": {"title": "BAXY", "process": "Baxy"}}, "Steam")
    # The title names the application only in its last segment, as whole words.
    assert not cu_window.application_is_in_front({"window": {"title": "Steam - Bloc de notas", "process": "Notepad"}}, "Steam")
    assert not cu_window.application_is_in_front({"window": {"title": "Steamworks", "process": "x"}}, "Steam")
    assert cu_window.application_is_in_front({"window": {"title": "Ron92 - Discord", "process": "Update"}}, "Discord")
    assert cu_window.application_is_in_front({"window": {"title": "Inicio - Personal - Microsoft​ Edge", "process": "msedge"}}, "Microsoft Edge")
    assert cu_window.application_is_in_front({"window": {"title": "Artista - Canción", "process": "Spotify"}}, "Spotify")
    # Named on purpose, the editor is the application.
    assert cu_window.application_is_in_front(editor, "Visual Studio Code")


def test_enter_and_space_on_a_possible_message_box_are_marked_and_free_where_nothing_is_sent() -> None:
    def view(focused: dict | None) -> dict:
        return {"window": {"title": "App", "process": "app", "focused": focused}, "controls": [], "text": {}}

    asked = (
        {"kind": "Edit", "name": "Responder a Ron92"},
        {"kind": "Button", "name": "Send"},
        {"kind": "Document", "name": "(document)"},
        {"kind": "Edit", "name": "(edit)", "value": None},
    )
    for focused in asked:
        for key in ("enter", "space"):
            step = cu_validate.validate_decision(_key_act(key), view=view(focused), last_failed=None, application_names=APPS)
            assert step["arguments"] == {"key": key, "target": "message_composer"}, (focused, key)
    free = (
        None,  # a calculator: no focused editable
        {"kind": "Edit", "name": "Buscar", "value": "hades"},
        {"kind": "Edit", "name": "Barra de direcciones y de búsqueda", "value": "es.wikipedia.org"},
        {"kind": "Document", "name": "Editor de texto", "value": "lista: pan"},
        {"kind": "Document", "name": "(document)", "value": "lista: pan"},
        {"kind": "Edit", "name": "Enviar mensaje a @Ron92", "value": ""},
    )
    for focused in free:
        step = cu_validate.validate_decision(_key_act("enter"), view=view(focused), last_failed=None, application_names=APPS)
        assert step["arguments"] == {"key": "enter"}, focused
    # «calcular»: Enter on the Calculator's buttons stays free.
    calc = {"window": {"title": "Calculadora", "process": "CalculatorApp", "focused": None}, "controls": [{"i": 0, "kind": "Button", "name": "Uno"}], "text": {}}
    typed = [{"operation": "input.text.type", "ok": True, "text": "2+2"}]
    assert cu_rules.deterministic_step(goal="calcular 2+2", view=calc, history=typed)["arguments"] == {"key": "enter"}


def test_delete_is_marked_as_a_text_field_only_when_the_keyboard_is_on_one() -> None:
    on_field = {"window": {"title": "App", "focused": {"kind": "Edit", "name": "Nombre", "value": "x"}}, "controls": [], "text": {}}
    on_list = {"window": {"title": "Descargas", "focused": {"kind": "ListItem", "name": "informe.pdf"}}, "controls": [], "text": {}}
    assert cu_validate.validate_decision(_key_act("delete"), view=on_field, last_failed=None, application_names=APPS)["arguments"] == {"key": "delete", "target": "text_field"}
    assert cu_validate.validate_decision(_key_act("delete"), view=on_list, last_failed=None, application_names=APPS)["arguments"] == {"key": "delete"}


def test_a_typed_step_carries_one_line_without_tabs() -> None:
    raw = {"act": "type", "i": -1, "label": "", "text": "hola\nchau\r\n\tfin", "key": "", "direction": "", "application": "", "evidence": "", "why": ""}
    step = cu_validate.validate_decision(raw, view={"window": {"title": "App"}, "controls": [], "text": {}}, last_failed=None, application_names=APPS)
    assert step["operation"] == "input.text.type"
    assert step["arguments"]["text"] == "hola chau fin"
    blank = {**raw, "text": "\n\t\r\n"}
    assert cu_validate.validate_decision(blank, view={"window": {"title": "App"}, "controls": [], "text": {}}, last_failed=None, application_names=APPS)["operation"] == "none"


def test_no_way_into_the_engine_takes_an_undoing_paying_or_leaving_goal() -> None:
    apps = ("Discord", "Steam", "Spotify", "Paint", "Explorador de archivos")
    never = (
        "en Discord quitá a Ron92 de mis amigos",
        "sacá a Cotele del servidor",
        "en el explorador mandá informe.pdf a la papelera",
        "move the report to the trash",
        "descartá los cambios en Paint",
        "en Spotify cancelá la suscripción",
        "unsubscribe from this channel",
        "suscribime al canal de Ron92",
        "alquilá la película en Steam",
        "doná 5 dólares en Steam",
        "vendé mis cromos en Steam",
        "restablecé la configuración de Discord",
        "limpiá el historial de Steam",
        "vaciá la papelera de reciclaje",
        "empty the recycle bin",
        "en Discord salí del servidor de BAXY",
        "leave the server in Discord",
    )
    for said in never:
        assert not missions.engine_can_try(said, apps), said
        # The decider choosing the engine itself gets no arguments for it either.
        assert missions.free_form_arguments(said, apps) is None, said
        assert missions.mission_request(said, apps) is None, said
    for said in ("en Paint girá la imagen a la derecha", "sacá una captura de pantalla en Paint", "en el explorador creá una carpeta vacía"):
        assert missions.free_form_arguments(said, apps) is not None, said


def test_a_menu_opened_by_the_place_survives_a_failed_learned_click() -> None:
    # Measured on Steam: «BIBLIOTECA» opened its menu, the replayed entry was ambiguous, the model answered none.
    menu = {
        "window": {"title": "Steam", "process": "steamwebhelper", "focused": None},
        "controls": [],
        # The failed click changed nothing, so the last look's newText is empty; the App keeps what the verified
        # click made appear.
        "newText": [],
        "newTextAfterClick": ["Página principal", "Colecciones", "Descargas"],
        "text": {"TL": ["TIENDA", "BIBLIOTECA", "Página principal", "Colecciones", "Descargas"]},
    }
    history = [
        _ok(1, "input.visible.click", label="BIBLIOTECA"),
        {"step": 2, "operation": "input.visible.click", "label": "Inicio", "ok": False, "error": "visible_button_ambiguous"},
    ]
    step = cu_rules.deterministic_step(goal="ir a biblioteca", view=menu, history=history)
    assert step is not None and step["arguments"].get("label") == "Página principal"


def test_a_search_field_holding_old_text_is_selected_whole_before_typing() -> None:
    # Measured on Settings: «colores» was appended to a leftover «colorespantalla».
    settings = {
        "window": {"title": "Configuración", "process": "SystemSettings",
                   "focused": {"kind": "Edit", "name": "Cuadro de búsqueda, Buscar una opción", "value": "colorespantalla"}},
        "controls": [{"i": 0, "kind": "Edit", "name": "Cuadro de búsqueda, Buscar una opción", "state": "focused"}],
        "text": {},
    }
    first = cu_rules.deterministic_step(goal="ir a colores", view=settings, history=[])
    assert first["arguments"] == {"key": "ctrl_a"}
    selected = [_ok(1, "input.key.press", key="ctrl_a")]
    assert cu_rules.deterministic_step(goal="ir a colores", view=settings, history=selected)["arguments"] == {"text": "colores"}


def test_going_somewhere_never_presses_a_switch() -> None:
    # Measured on Settings: looking for «Colores» the model clicked «Invertir colores» of the Magnifier.
    view = {
        "window": {"title": "Configuración", "process": "SystemSettings"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Invertir colores", "state": "off"},
            {"i": 1, "kind": "CheckBox", "name": "Invertir colores de la lupa"},
            {"i": 2, "kind": "ListItem", "name": "Colores"},
        ],
        "text": {},
    }
    for index, label in ((0, "Invertir colores"), (1, "Invertir colores de la lupa")):
        refused = cu_validate.validate_decision(
            {"act": "click", "i": index}, view=view, last_failed=None, application_names=(), history=[], goal="ir a colores",
        )
        assert refused["operation"] == "none", label
    allowed = cu_validate.validate_decision(
        {"act": "click", "i": 2}, view=view, last_failed=None, application_names=(), history=[], goal="ir a colores",
    )
    assert allowed["operation"] == "input.visible.click"


def test_after_a_failed_learned_click_the_goal_step_is_found_again_by_identity() -> None:
    # Measured on Settings: a replayed «Sistema» by label was ambiguous (nav item and page card) and the model gave up.
    view = {
        "window": {"title": "Configuración", "process": "SystemSettings"},
        "controls": [
            {"i": 7, "kind": "ListItem", "name": "Sistema", "state": "", "zone": "L"},
            {"i": 20, "kind": "Button", "name": "Bluetooth y dispositivos", "zone": "C"},
        ],
        "text": {},
    }
    failed = [{"step": 1, "operation": "input.visible.click", "label": "Sistema", "ok": False, "error": "visible_button_ambiguous"}]
    step = cu_rules.deterministic_step(goal="ir a sistema", view=view, history=failed)
    assert step is not None and step["arguments"] == {"label": "Sistema", "index": 7}
    again = [{"step": 1, "operation": "input.visible.click", "label": "Sistema", "index": 7, "ok": False}]
    looked_up = cu_rules.deterministic_step(goal="ir a sistema", view=view, history=again)
    assert looked_up is None or looked_up["arguments"] != {"label": "Sistema", "index": 7}


def test_a_menu_with_ocr_noise_gives_its_first_entry_only_from_the_tree_and_the_window_body_is_never_clicked() -> None:
    # Measured on Steam: «COMUNIDAD» opened its menu among OCR noise; the model then clicked the web view itself.
    # Written lines alone never make a blind first-entry click (safety review cu-z): that step is the model's.
    menu = {
        "window": {"title": "Steam", "process": "steamwebhelper", "focused": None,
                   "rect": {"x": 0, "y": 0, "w": 1000, "h": 800}},
        "controls": [{"i": 0, "kind": "Pane", "name": "Chrome Legacy Window", "rect": {"x": 0, "y": 0, "w": 1000, "h": 800}}],
        "newText": ["https://steamcommunity.com/id/x/", "Actividad", "Perfil", "Amigos", "Grupos", "Contenido", "Insignias", "_ SOUL.TM", ".RED"],
        "text": {"TL": ["TIENDA BIBLIOTECA COMUNIDAD", "Actividad", "Perfil"]},
    }
    clicked = [_ok(1, "input.visible.click", label="COMUNIDAD")]
    step = cu_rules.deterministic_step(goal="ir a comunidad", view=menu, history=clicked)
    assert step is None or step["arguments"].get("label") != "Actividad"
    # The same menu exposed in the tree as menu items that appeared together: its first entry.
    entries = ["Actividad", "Perfil", "Amigos", "Grupos", "Contenido", "Insignias"]
    in_tree = {**menu, "controls": [*menu["controls"], *({"i": n + 1, "kind": "MenuItem", "name": name} for n, name in enumerate(entries))]}
    step = cu_rules.deterministic_step(goal="ir a comunidad", view=in_tree, history=clicked)
    assert step is not None and step["arguments"].get("label") == "Actividad"
    refused = cu_validate.validate_decision(
        {"act": "click", "label": "Chrome Legacy Window"}, view=menu, last_failed=None, application_names=(),
        history=clicked, goal="ir a comunidad",
    )
    assert refused["operation"] == "none"


def test_what_was_typed_is_never_the_evidence_of_arriving() -> None:
    view = {"window": {"title": "Steam"}, "controls": [], "text": {"T": ["Cuphead", "Buscar en la tienda"]}}
    history = [_ok(1, "input.text.type", text="Cuphead"), _ok(2, "input.key.press", key="enter")]
    refused = cu_validate.validate_decision(
        {"act": "done", "evidence": "Cuphead"}, view=view, last_failed=None, application_names=(), history=history,
        goal="buscar Cuphead",
    )
    assert refused["operation"] == "none"


def test_an_order_that_names_its_application_needs_no_context() -> None:
    # Live 2026-10-07: in a warm session every order after the first went to the contextual decider (a lone click, the
    # typed calculation) and failed; an order naming its application reads alone.
    from baxy_mind.effect_intent import EffectIntent

    apps = ("Reloj", "Calculadora", "Configuración")
    mission = EffectIntent(("mission.computer.use",), ("x",))
    assert engine_handoff._self_contained_mission("en el Reloj andá a Cronómetro", mission, apps)
    assert engine_handoff._self_contained_mission("en la calculadora calculá 9 por 8", mission, apps)
    assert not engine_handoff._self_contained_mission("y ahora andá a configuración", mission, apps)
    assert not engine_handoff._self_contained_mission("en el Reloj andá a Cronómetro", None, apps)


# ------------------------------------------------- modos detrás de la navegación


def test_switching_to_a_mode_reads_as_choosing_it_with_a_check_the_window_can_show() -> None:
    for said in (
        "en la calculadora cambiá a científica",
        "en la calculadora pasá a la científica",
        "en la calculadora cambiá al modo científico",
        "switch to scientific in the calculator",
        "in the calculator switch to scientific mode",
    ):
        arguments = _mission(said)
        assert arguments["application"] == "Calculadora", said
        assert arguments["goal"] in {"ir a cientifica", "ir a cientifico", "ir a scientific"}, said
        name = arguments["goal"][len("ir a "):]
        # The mode's header after the switch («Modo de calculadora Científica») names it; title and selection do not.
        assert f"header:{name}" in arguments["successCheck"].split("|"), said
    # The other gender of the adjective is the same mode («el modo científico», «Calculadora Científica»).
    assert "header:cientifica" in _mission(
        "en la calculadora cambiá al modo científico"
    )["successCheck"].split("|")
    put = _mission("en la calculadora poné el modo científico")
    assert put["goal"] == "activar modo cientifico"
    assert put["successCheck"].startswith("control:modo cientifico:on|")
    assert "header:cientifica" in put["successCheck"].split("|")
    # A tab is still a tab, and «poner» without a mode word is no mode.
    assert missions.mission_request("in Chrome switch to the Gmail tab", APPS).goal.startswith("ir a la pesta")
    assert missions.mission_request("en la calculadora poné la científica", APPS).goal != "ir a cientifica"
    assert missions.gender_twin("científico") == "cientifica"
    assert missions.gender_twin("inicio") is None and missions.gender_twin("biblioteca") is None


_NAVIGATION_CLOSED = {
    "window": {"title": "Calculadora", "process": "ApplicationFrameHost", "requested": True,
               "rect": {"x": 0, "y": 0, "w": 700, "h": 800}, "focused": {"kind": "Text", "name": "Se muestra 0"}},
    "controls": [
        {"i": 0, "kind": "Button", "name": "Cerrar Calculadora", "zone": "TR"},
        {"i": 1, "kind": "Button", "name": "Abrir navegación", "zone": "TL"},
        {"i": 2, "kind": "Button", "name": "Más", "zone": "B"},
        {"i": 3, "kind": "Button", "name": "Siete", "zone": "L"},
        {"i": 4, "kind": "Text", "name": "Modo de calculadora Estándar", "zone": "TL"},
    ],
    "text": {"TL": ["Calculadora", "Estándar"]},
}
_NAVIGATION_OPEN = {
    **_NAVIGATION_CLOSED,
    "controls": [
        {"i": 0, "kind": "Button", "name": "Cerrar navegación", "zone": "TL"},
        {"i": 1, "kind": "ListItem", "name": "Estándar Calculadora", "state": "selected", "zone": "L"},
        {"i": 2, "kind": "ListItem", "name": "Científica Calculadora", "zone": "L"},
        {"i": 3, "kind": "ListItem", "name": "Programador Calculadora", "zone": "L"},
        {"i": 4, "kind": "Button", "name": "Más", "zone": "B"},
    ],
    "newText": ["Estándar", "Científica", "Programador"],
}


def test_a_mode_behind_the_navigation_button_is_found_by_opening_it_before_any_shortcut() -> None:
    # Measured live (n2): «cambiá a científica» pressed ctrl_k and escape on the Calculator and stopped; its modes
    # are items of the navigation behind «Abrir navegación».
    for goal in ("ir a cientifica", "ir a cientifico", "activar modo cientifico"):
        first = cu_rules.deterministic_step(goal=goal, view=_NAVIGATION_CLOSED, history=[])
        assert first["operation"] == "input.visible.click", goal
        assert first["arguments"] == {"label": "Abrir navegación", "index": 1}, goal
        opened = [_ok(1, "input.visible.click", label="Abrir navegación", index=1)]
        picked = cu_rules.deterministic_step(goal=goal, view=_NAVIGATION_OPEN, history=opened)
        assert picked["arguments"] == {"label": "Científica Calculadora", "index": 2}, goal
    # Opened once and the mode is not there: the shortcuts follow, the opener is never clicked again, «Cerrar
    # navegación» and the «Más» operator are never taken for a menu.
    empty = {**_NAVIGATION_OPEN, "controls": _NAVIGATION_OPEN["controls"][:1] + _NAVIGATION_OPEN["controls"][4:]}
    opened = [_ok(1, "input.visible.click", label="Abrir navegación", index=1)]
    assert cu_rules.deterministic_step(goal="ir a cientifica", view=empty, history=opened)["arguments"] == {"key": "ctrl_k"}
    assert cu_rules.deterministic_step(goal="ir a cientifica", view=_NAVIGATION_CLOSED, history=opened)["arguments"] == {"key": "ctrl_k"}


def test_the_navigation_opener_is_a_button_by_its_whole_name_never_a_switch_or_an_open_one() -> None:
    def view(*controls: dict) -> dict:
        return {"window": {"title": "App", "process": "app"}, "controls": list(controls), "text": {}}

    for name, kind in (("Open Navigation", "Button"), ("Abrir menú", "Button"), ("Más opciones", "SplitButton"),
                       ("More options", "Button"), ("Main menu", "MenuItem"), ("Navegación", "Button")):
        step = cu_rules.deterministic_step(goal="ir a cientifica", view=view({"i": 0, "kind": kind, "name": name}), history=[])
        assert step["arguments"] == {"label": name, "index": 0}, name
    for control in (
        {"i": 0, "kind": "ToggleButton", "name": "Menú"},
        {"i": 0, "kind": "Button", "name": "Menú", "state": "off"},
        # A bare «Menú» or «More» says nothing of navigation (a card's menu, a list's «more»).
        {"i": 0, "kind": "Button", "name": "Menú"},
        {"i": 0, "kind": "Button", "name": "More"},
        {"i": 0, "kind": "Button", "name": "Abrir navegación", "state": "expanded"},
        {"i": 0, "kind": "Button", "name": "Cambiar el tamaño del menú de navegación principal"},
        {"i": 0, "kind": "Group", "name": "Botones de navegación"},
        {"i": 0, "kind": "Pane", "name": "Panel de navegación"},
    ):
        step = cu_rules.deterministic_step(goal="ir a cientifica", view=view(control), history=[])
        assert step["arguments"] == {"key": "ctrl_k"}, control
    # A search of the window still comes first.
    searchable = view({"i": 0, "kind": "Button", "name": "Abrir navegación"}, {"i": 1, "kind": "Edit", "name": "Buscar una configuración"})
    assert cu_rules.deterministic_step(goal="ir a colores", view=searchable, history=[])["arguments"] == {
        "label": "Buscar una configuración", "index": 1,
    }


def test_going_to_a_place_never_clicks_the_switch_that_carries_its_name() -> None:
    settings = {
        "window": {"title": "Configuración", "process": "SystemSettings"},
        "controls": [{"i": 0, "kind": "Button", "name": "Bluetooth", "state": "on"}],
        "text": {},
    }
    step = cu_rules.deterministic_step(goal="ir a bluetooth", view=settings, history=[])
    assert step is None or step["operation"] != "input.visible.click"
    # «poné el modo avión» where a switch is called so turns it on, as before.
    toggle = {**settings, "controls": [{"i": 0, "kind": "Button", "name": "Modo avión", "state": "off"}]}
    assert cu_rules.deterministic_step(goal="activar modo avion", view=toggle, history=[])["arguments"] == {
        "label": "Modo avión", "index": 0,
    }


# ------------------------------------------------ revisión x-mind 2026-10-07


def test_delete_after_an_address_is_pressed_only_with_the_keyboard_on_the_address_field() -> None:
    goal = "ir a la direccion es.wikipedia.org"
    typed = [_ok(1, "input.key.press", key="ctrl_l"), _ok(2, "input.text.type", text="es.wikipedia.org")]
    on_bar = {"window": {"title": "Opera", "focused": {"kind": "Edit", "name": "Campo de dirección", "value": "es.wikipedia.org/wiki/Curicó"}},
              "controls": [], "text": {}}
    step = cu_rules.deterministic_step(goal=goal, view=on_bar, history=typed)
    assert step["arguments"] == {"key": "delete", "target": "text_field"}
    # ctrl_l did not reach the bar (the page or a list item has the keyboard, or nothing is known): Delete would erase
    # what is selected, so nothing is pressed.
    for focused in (None, {"kind": "ListItem", "name": "informe.pdf"}, {"kind": "Edit", "name": "Buscar en la página", "value": "x"}):
        view = {"window": {"title": "Opera", "focused": focused}, "controls": [], "text": {}}
        assert cu_rules.deterministic_step(goal=goal, view=view, history=typed) is None, focused


def test_going_to_a_place_never_clicks_a_switch_by_its_written_name_or_as_a_search_result() -> None:
    settings = {
        "window": {"title": "Configuración", "process": "SystemSettings"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Bluetooth", "state": "on"},
            {"i": 1, "kind": "Edit", "name": "Buscar una configuración"},
        ],
        "text": {"C": ["Bluetooth"]},
    }
    # The switch's own written word is the switch: the place is looked up in the window's search.
    step = cu_rules.deterministic_step(goal="ir a bluetooth", view=settings, history=[])
    assert step["arguments"] == {"label": "Buscar una configuración", "index": 1}
    # The switch and the navigation item carry the same name: the item is the place.
    both = {**settings, "controls": [*settings["controls"], {"i": 2, "kind": "ListItem", "name": "Bluetooth"}]}
    assert cu_rules.deterministic_step(goal="ir a bluetooth", view=both, history=[])["arguments"] == {"label": "Bluetooth", "index": 2}
    # A search result that is a switch is never the result, nor its written name.
    results = {
        "window": {"title": "Configuración", "process": "SystemSettings",
                   "focused": {"kind": "Edit", "name": "Buscar una configuración", "value": "colores"}},
        "controls": [
            {"i": 0, "kind": "Edit", "name": "Buscar una configuración", "state": "focused"},
            {"i": 1, "kind": "Button", "name": "Colores", "state": "off"},
            {"i": 2, "kind": "ListItem", "name": "Colores de acento"},
        ],
        "newText": ["Colores"],
        "text": {"C": ["Colores", "Colores de acento"]},
    }
    typed = [_ok(1, "input.visible.click", label="Buscar una configuración"), _ok(2, "input.text.type", text="colores")]
    picked = cu_rules.deterministic_step(goal="ir a colores", view=results, history=typed)
    assert picked["arguments"] == {"label": "Colores de acento", "index": 2}
    only_switch = {**results, "controls": results["controls"][:2], "text": {"C": ["Colores"]}}
    # Goal v3 (lugar y clic M3): with no result to click, Enter once submits the search (never a click on the switch);
    # after that Enter, never a second one nor the switch.
    assert cu_rules.deterministic_step(goal="ir a colores", view=only_switch, history=typed)["arguments"] == {"key": "enter"}
    entered = [*typed, _ok(3, "input.key.press", key="enter")]
    after = cu_rules.deterministic_step(goal="ir a colores", view=only_switch, history=entered)
    assert after is None or after["arguments"] not in ({"key": "enter"}, {"label": "Colores", "index": 1})


def test_a_name_two_controls_carry_is_looked_up_never_clicked_by_its_written_word() -> None:
    # Live s13 Discord: «Cotele» was a server and an activity card; the click on the written word failed.
    discord = {
        "window": {"title": "Amigos - Discord", "process": "Discord", "focused": None},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Buscar", "state": ""},
            {"i": 1, "kind": "ListItem", "name": "Cotele"},
            {"i": 2, "kind": "Button", "name": "Cotele"},
        ],
        "text": {"C": ["Cotele"]},
    }
    step = cu_rules.deterministic_step(goal="ir a cotele", view=discord, history=[])
    assert step["arguments"] == {"label": "Buscar", "index": 0, "search": "cotele"}
    # No control names it: the written word is still clicked by its label.
    written = {**discord, "controls": discord["controls"][:1]}
    assert cu_rules.deterministic_step(goal="ir a cotele", view=written, history=[])["arguments"] == {"label": "cotele"}


def test_a_search_field_already_holding_the_name_is_not_typed_into_again() -> None:
    clicked = [_ok(1, "input.visible.click", label="Buscar")]
    holding = {
        "window": {"title": "Amigos - Discord", "process": "Discord", "focused": {"kind": "Edit", "name": "Buscar", "value": "general"}},
        "controls": [{"i": 0, "kind": "Edit", "name": "Buscar", "state": "focused"}, {"i": 1, "kind": "ListItem", "name": "general · Mi servidor"}],
        "text": {},
    }
    assert cu_rules.deterministic_step(goal="ir a general", view=holding, history=clicked)["arguments"] == {
        "label": "general · Mi servidor", "index": 1,
    }
    # No result yet: the name is selected whole and typed once more so the search runs, never appended.
    bare = {**holding, "controls": holding["controls"][:1]}
    assert cu_rules.deterministic_step(goal="ir a general", view=bare, history=clicked)["arguments"] == {"key": "ctrl_a"}
    selected = clicked + [_ok(2, "input.key.press", key="ctrl_a")]
    assert cu_rules.deterministic_step(goal="ir a general", view=bare, history=selected)["arguments"] == {"text": "general"}


def test_a_field_without_a_search_name_that_holds_text_is_never_selected_whole() -> None:
    # A document editor exposed as a text field took the keyboard after ctrl_k: select-all would take the person's work.
    editor = {
        "window": {"title": "tesis - Editor", "process": "editor", "focused": {"kind": "Edit", "name": "Editor de texto", "value": "mi tesis"}},
        "controls": [], "newText": ["algo"], "text": {},
    }
    after_k = [_ok(1, "input.key.press", key="ctrl_k")]
    assert cu_rules.deterministic_step(goal="ir a general", view=editor, history=after_k) is None
    empty = {**editor, "window": {**editor["window"], "focused": {"kind": "Edit", "name": "", "value": ""}}}
    # Goal v3 P4: an empty field the shortcut brought up takes the name only when it is named as a search, by itself or
    # by the prompt written with it; any other (t-menu-3: ctrl_k opened «Insertar vínculo») is closed with Escape.
    prompted = {**empty, "newText": ["Buscar canales"]}
    assert cu_rules.deterministic_step(goal="ir a general", view=prompted, history=after_k)["arguments"] == {"text": "general"}
    assert cu_rules.deterministic_step(goal="ir a general", view=empty, history=after_k)["arguments"] == {"key": "escape"}


def test_a_menu_after_failed_clicks_is_read_from_what_the_verified_click_made_appear() -> None:
    history = [
        _ok(1, "input.visible.click", label="BIBLIOTECA"),
        {"step": 2, "operation": "input.visible.click", "label": "Inicio", "ok": False},
    ]
    stale = {"window": {"title": "Steam"}, "controls": [], "newText": ["Página principal", "Colecciones"], "text": {}}
    # The current look's newText is not what the verified click made appear: without newTextAfterClick, no menu.
    assert cu_menus._menu_opened_by(stale, history, "biblioteca") is None
    kept = {**stale, "newText": [], "newTextAfterClick": ["Página principal", "Colecciones"]}
    assert cu_menus._menu_opened_by(kept, history, "biblioteca") == "Página principal"
    # Right after the verified click its own look's newText is the menu.
    assert cu_menus._menu_opened_by(stale, history[:1], "biblioteca") == "Página principal"


def test_the_navigation_opener_is_never_the_browser_frames_nor_used_by_a_search() -> None:
    browser = {
        "window": {"title": "Nueva pestaña - Opera", "process": "opera", "rect": _rect(0, 0, 1200, 800), "focused": None},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Main menu", "rect": _rect(0, 0, 40, 30)},
            {"i": 1, "kind": "Edit", "name": "Campo de dirección", "value": "", "rect": _rect(100, 40, 800, 30)},
            {"i": 2, "kind": "Document", "name": "Nueva pestaña", "rect": _rect(0, 80, 1200, 720)},
        ],
        "text": {},
    }
    step = cu_rules.deterministic_step(goal="ir a historia", view=browser, history=[])
    assert step is None or step["arguments"].get("label") != "Main menu"
    in_page = {**browser, "controls": [*browser["controls"], {"i": 3, "kind": "Button", "name": "Abrir navegación", "rect": _rect(10, 100, 40, 30)}]}
    assert cu_rules.deterministic_step(goal="ir a historia", view=in_page, history=[])["arguments"] == {"label": "Abrir navegación", "index": 3}
    # A search is the window's search, never its navigation.
    app = {"window": {"title": "App", "process": "app"}, "controls": [{"i": 0, "kind": "Button", "name": "Abrir navegación"}], "text": {}}
    assert cu_rules.deterministic_step(goal="buscar informe", view=app, history=[])["arguments"] == {"key": "ctrl_k"}
    assert cu_rules.deterministic_step(goal="ir a informe", view=app, history=[])["arguments"] == {"label": "Abrir navegación", "index": 0}


def test_evidence_that_holds_what_was_typed_proves_nothing_until_a_click_moved_the_window() -> None:
    title = "imagenes - Resultados de la búsqueda en ETC"
    view = {"window": {"title": title}, "controls": [{"i": 0, "kind": "ListItem", "name": "vacaciones.jpg"}], "text": {}}
    typed = [_ok(1, "input.text.type", text="imagenes"), _ok(2, "input.key.press", key="enter")]
    done = {"act": "done", "evidence": title}
    refused = cu_validate.validate_decision(done, view=view, last_failed=None, application_names=(), history=typed, goal="ir a imagenes")
    assert refused["operation"] == "none" and refused["code"] == "evidence_not_visible"
    moved = typed + [_ok(3, "input.visible.click", label="imagenes", changed=True)]
    accepted = cu_validate.validate_decision(done, view=view, last_failed=None, application_names=(), history=moved, goal="ir a imagenes")
    assert accepted["operation"] == "done"
    # A goal of writing a text is proved by the text it wrote.
    note = {"window": {"title": "hola mundo - Bloc de notas"}, "controls": [], "text": {}}
    wrote = [_ok(1, "input.text.type", text="hola mundo")]
    proof = cu_validate.validate_decision(
        {"act": "done", "evidence": "hola mundo - Bloc de notas"}, view=note, last_failed=None, application_names=(),
        history=wrote, goal="escribir hola mundo",
    )
    assert proof["operation"] == "done"


def test_a_key_or_typing_final_says_it_is_done_and_a_place_final_confirms_the_window() -> None:
    def instruction(goal: str, **more: object) -> str:
        return cu_projection.compose_instruction({"goal": goal, "reached": True, **more}, "es")

    for goal in ("apretar enter", "escribir hola"):
        said = instruction(goal)
        assert "Confirm the state" not in said and "Say only that it is done in that app" in said, goal
    for goal in ("ir a biblioteca", "calcular 2+2"):
        assert "Confirm the state" in instruction(goal), goal
    assert "Confirm the state" in instruction("apretar enter", question="¿está activado?")
    mixed = cu_projection.compose_instruction(
        {"goal": "x", "reached": True, "subgoals": [{"goal": "ir a general", "reached": True}, {"goal": "escribir hola", "reached": True}]}, "es",
    )
    assert "for a part that pressed a key or typed" in mixed
    unreached = cu_projection.compose_instruction(
        {"goal": "x", "reached": False, "subgoals": [{"goal": "ir a general", "reached": True}, {"goal": "escribir hola", "reached": False}]}, "es",
    )
    assert "at most TWO short sentences" in unreached


def test_a_button_named_as_switching_is_never_pressed_on_the_way_to_a_place() -> None:
    # Measured on the Calculator: going to «Científica» the model pressed «Alternar grados» and DEG became RAD.
    view = {"window": {"title": "Calculadora"}, "controls": [{"i": 0, "kind": "Button", "name": "Alternar grados"}], "text": {}}
    refused = cu_validate.validate_decision(
        {"act": "click", "i": 0}, view=view, last_failed=None, application_names=(), history=[], goal="ir a cientifica",
    )
    assert refused["operation"] == "none"


def test_a_search_button_that_opened_its_box_is_typed_into() -> None:
    # Measured on Discord: «Buscar o iniciar una conversación» opens the quick switcher; its field is not reported focused.
    view = {
        "window": {"title": "Discord", "process": "Discord", "focused": None},
        "controls": [{"i": 3, "kind": "Button", "name": "Buscar o iniciar una conversación"}],
        "newText": ["¿A dónde quieres ir?"],
        "text": {"C": ["¿A dónde quieres ir?"]},
    }
    clicked = [{"step": 1, "operation": "input.visible.click", "label": "Buscar o iniciar una conversación", "ok": True,
                "surfaceChanged": True}]
    step = cu_rules.deterministic_step(goal="ir a cotele", view=view, history=clicked)
    assert step is not None and step["operation"] == "input.text.type" and step["arguments"] == {"text": "cotele"}


def test_when_the_places_own_control_failed_the_place_is_looked_up() -> None:
    view = {
        "window": {"title": "Discord", "process": "Discord", "focused": None},
        "controls": [
            {"i": 2, "kind": "TreeItem", "name": "Cotele"},
            {"i": 3, "kind": "Button", "name": "Buscar o iniciar una conversación"},
        ],
        "text": {},
    }
    failed = [{"step": 1, "operation": "input.visible.click", "label": "Cotele", "index": 2, "ok": False,
               "error": "visible_button_postread_unchanged"}]
    step = cu_rules.deterministic_step(goal="ir a cotele", view=view, history=failed)
    assert step is not None and step["arguments"].get("label") == "Buscar o iniciar una conversación"


def test_a_file_views_delete_command_does_not_stop_opening_the_chosen_folder() -> None:
    # Explorer always shows «Eliminar (Supr)» in its command bar: only an uninstall offered, or a chosen item that runs
    # or removes, keeps the Enter from being pressed.
    view = {
        "window": {"title": "Inicio - Explorador de archivos", "process": "explorer"},
        "controls": [
            {"i": 1, "kind": "Button", "name": "Eliminar (Supr)", "zone": "T"},
            {"i": 5, "kind": "ListItem", "name": "Descargas", "state": "selected", "zone": "C",
             "itemType": "Carpeta de archivos", "rect": {"x": 600, "y": 300, "w": 120, "h": 40}},
        ],
        "text": {},
    }
    clicked = [{"step": 1, "operation": "input.visible.click", "label": "Descargas", "index": 5, "ok": True}]
    step = cu_rules.deterministic_step(goal="ir a descargas", view=view, history=clicked)
    assert step is not None and step["operation"] == "input.key.press" and step["arguments"].get("key") == "enter"


def test_a_sentence_that_mentions_the_place_is_not_the_place() -> None:
    view = {"window": {"title": "Configuración"}, "controls": [
        {"i": 0, "kind": "Text", "name": "Usa un servidor proxy para conexiones Ethernet o Wi-Fi. Esta configuración no se aplica a conexiones VPN."},
        {"i": 1, "kind": "ListItem", "name": "Proxy"},
    ], "text": {}}
    assert cu_view.find_control(view, "wi-fi") is None
    assert cu_view.find_control(view, "proxy")["i"] == 1


def test_round_four_review_fixes() -> None:
    # An explicit click on a named switch is the person's own order; on the way to a place it is refused.
    view = {"window": {"title": "Configuración"}, "controls": [{"i": 0, "kind": "Button", "name": "Modo avión", "state": "off"}], "text": {}}
    explicit = cu_validate.validate_decision({"act": "click", "i": 0}, view=view, last_failed=None, application_names=(),
                                              history=[], goal="hacer clic en modo avion")
    assert explicit["operation"] == "input.visible.click"
    going = cu_validate.validate_decision({"act": "click", "i": 0}, view=view, last_failed=None, application_names=(),
                                           history=[], goal="ir a red")
    assert going["operation"] == "none"
    # «apretá enter» where the focus cannot be read is asked first.
    blind = {"window": {"title": "WhatsApp", "focused": None}, "controls": [], "text": {}}
    step = cu_rules.deterministic_step(goal="apretar enter", view=blind, history=[])
    assert step["arguments"] == {"key": "enter", "target": "message_composer"}
    # An item whose type is an application never gets the Enter, whatever its row shows.
    app_item = {"kind": "ListItem", "name": "DiscordSetup", "itemType": "Aplicación", "rect": {"x": 0, "y": 0, "w": 200, "h": 20}}
    assert not cu_navigation._is_container(app_item, {"controls": [app_item]})


def test_a_toggle_that_opens_the_navigation_is_no_switch() -> None:
    assert not cu_view._is_switch({"kind": "Button", "name": "Alternar navegación"})
    assert not cu_view._is_switch({"kind": "Button", "name": "Toggle navigation"})
    assert cu_view._is_switch({"kind": "Button", "name": "Alternar grados"})


# ------------------------------------------------------------ falsos éxitos v3 M1 (cu-v3 r3a): el done del modelo


def _done(evidence: str, view: dict, goal: str, history: list[dict] | None = None) -> dict:
    return cu_validate.validate_decision(
        {"act": "done", "evidence": evidence, "why": ""}, view=view, last_failed=None, application_names=APPS,
        history=history or [], goal=goal,
    )


PHOTOS = {
    "window": {"title": "Fotos", "process": "Photos"},
    "controls": [
        {"i": 0, "kind": "ListItem", "name": "Galería", "state": ""},
        {"i": 1, "kind": "Edit", "name": "Buscar en la galería", "state": "", "value": ""},
    ],
    "text": {"C": ["Galería", "256 fotos"]},
}
NOTE = {
    "window": {"title": "Notas", "process": "Notes"},
    "controls": [{"i": 0, "kind": "Document", "name": "Nota", "state": "", "value": "Hoy hace moradosu"}],
    "text": {"C": ["Hoy hace moradosu"]},
}


def test_a_done_with_no_act_in_a_goal_of_doing_is_refused() -> None:
    # Twin of v3-17 (turn 2, «recórtala en proporción cuadrada»): done on the first look, citing the gallery.
    refused = _done("Galería", PHOTOS, "recortar la imagen en proporcion cuadrada")
    assert refused["operation"] == "none" and refused["code"] == "evidence_not_visible"
    # Twin of v3-17 (turn 3): «guárdala como copia», no step either.
    assert _done("256 fotos", PHOTOS, "guardar la imagen como copia en esa misma carpeta")["operation"] == "none"
    # Counter-cases: a reading, a place and a question cite what shows; a click that changed something is an act.
    assert _done("256 fotos", PHOTOS, "leer cuantas fotos hay")["operation"] == "done"
    assert _done("256 fotos", PHOTOS, "ir a la galeria")["operation"] == "done"
    assert _done("256 fotos", PHOTOS, f"abrir fotos{missions.QUESTION_MARK}¿cuántas fotos hay?")["operation"] == "done"
    clicked = [{"operation": "input.visible.click", "label": "Recortar", "ok": True, "changed": True}]
    assert _done("256 fotos", PHOTOS, "recortar la imagen en proporcion cuadrada", clicked)["operation"] == "done"
    unchanged = [{"operation": "input.visible.click", "label": "Recortar", "ok": True, "changed": False}]
    assert _done("256 fotos", PHOTOS, "recortar la imagen en proporcion cuadrada", unchanged)["operation"] == "none"
    # Opening the application is the act only of a goal of opening.
    opened = [{"operation": "app.open", "appId": "Fotos", "ok": True, "changed": True}]
    assert _done("256 fotos", PHOTOS, "recortar la imagen en proporcion cuadrada", opened)["operation"] == "none"
    assert _done("256 fotos", PHOTOS, "abrir fotos", opened)["operation"] == "done"


def test_a_done_citing_the_typed_text_glued_to_another_word_is_refused() -> None:
    # Twin of v3-35 (turn 3, «ahora ponla de color morado»): «morado» typed, «Hoy hace moradosu» cited.
    typed = [{"operation": "input.text.type", "text": "morado", "ok": True, "changed": True}]
    refused = _done("Hoy hace moradosu", NOTE, "poner la nota de color morado", typed)
    assert refused["operation"] == "none" and refused["code"] == "evidence_not_visible"
    # Counter-cases: an item that holds the text typed in a longer name (a file saved under it), a search's result line.
    folder = {
        "window": {"title": "Documentos", "process": "explorer"},
        "controls": [{"i": 0, "kind": "ListItem", "name": "informe final.txt", "state": ""}],
    }
    named = [{"operation": "input.text.type", "text": "informe", "ok": True, "into": "Nombre"},
             {"operation": "input.visible.click", "label": "Guardar", "ok": True, "changed": True}]
    assert _done("informe final.txt", folder, "guardar el documento como informe", named)["operation"] == "done"
    store = {
        "window": {"title": "Tienda", "process": "steamwebhelper"},
        "controls": [{"i": 0, "kind": "ListItem", "name": "Cuphead - Juego", "state": ""}],
        "text": {"C": ["1 resultado"]},
    }
    searched = [{"operation": "input.text.type", "text": "cuphead", "ok": True, "into": "Buscar en la tienda"},
                {"operation": "input.key.press", "key": "enter", "ok": True}]
    assert _done("1 resultado", store, "buscar cuphead", searched)["operation"] == "done"


def _seen_not_done(steps: list[dict]) -> dict:
    return {
        "goal": "recortar la imagen en proporcion cuadrada",
        "application": "Fotos",
        "reached": False,
        "steps": steps,
        "window": {"title": "Fotos", "process": "Photos"},
        "stoppedBy": "computer_use_seen_not_done",
        "seenNotDone": "Galería",
    }


def test_the_floor_never_says_done_without_a_verified_act() -> None:
    # v3-17 (turn 2): «Listo, lo hice en «Fotos»» with no step taken.
    nothing = {
        "goal": "recortar la imagen en proporcion cuadrada", "application": "Fotos", "reached": True, "steps": [],
        "window": {"title": "Fotos", "process": "Photos"}, "satisfiedBy": "model_evidence", "evidence": "Galería",
    }
    assert cu_finals.floor_sentence(nothing, False, True) == ""
    opened = dict(nothing, steps=[{"operation": "app.open", "appId": "Fotos", "ok": True}])
    assert cu_finals.floor_sentence(opened, False, True) == ""
    acted = dict(nothing, steps=[{"operation": "input.visible.click", "label": "Recortar", "ok": True, "changed": True}])
    # Ronda 22 (pasada r18 t3-c18): the model's own evidence is a weak proof; the act is counted, never told as done.
    assert cu_finals.floor_sentence(acted, False, True) == (
        "Llevo un paso en «Fotos», pero la pantalla todavía no muestra que haya quedado hecho.")
    proved = dict(acted, satisfiedBy="control:recortar:current")
    assert cu_finals.floor_sentence(proved, False, True) == "Listo, lo hice en «Fotos»."
    # Seen, not done: with no act it says so and quotes what shows; with acts it is a failure with its cause.
    assert cu_finals.floor_sentence(_seen_not_done([]), False, False) == (
        "No pude hacerlo en «Fotos»: no hice nada y ya se ve «Galería».")
    assert cu_finals.floor_sentence(_seen_not_done([]), True, False) == (
        "I couldn't do it in «Fotos»: I did nothing and «Galería» already shows.")
    stepped = cu_finals.floor_sentence(
        _seen_not_done([{"operation": "input.text.type", "text": "pruebas", "ok": True}]), False, False)
    assert stepped.startswith("No pude hacerlo en «Fotos»: ") and "Listo" not in stepped
    assert cu_projection.project_seen(_seen_not_done([]), "es")["seenNotDone"] == "Galería"


def test_a_click_label_with_a_quote_inside_or_a_purpose_names_nothing() -> None:
    # Twin of v3-11 (OneNote): «pagina» para crear una nueva pagina» was read as a label and its click as the check.
    assert missions.read_clause("pulsa «pagina» para crear una nueva pagina") == (
        "pulsa «pagina» para crear una nueva pagina", None)
    assert missions.read_clause("haz clic en pagina» para crear una nueva pagina")[1] is None
    assert missions.read_clause("haz clic en el boton para que se guarde")[1] is None
    # Counter-cases: a name with «para» and no verb after it, a plain name.
    assert missions.read_clause("haz clic en Opciones para desarrolladores") == (
        "hacer clic en opciones para desarrolladores", "stepDone:input.visible.click:opciones para desarrolladores")
    assert missions.read_clause("haz clic en Nueva página") == (
        "hacer clic en nueva pagina", "stepDone:input.visible.click:nueva pagina")


# ------------------------------------------------- revisión del juez (falsos éxitos v3 M1/M2): el espejo de la mente


def test_the_minds_judge_reads_a_place_goal_whatever_its_case() -> None:
    # The App's PlaceAsked ignores the case; the mirror did not («Ir a Sistema» was taken for a goal of doing).
    assert not cu_goals.done_needs_an_act("Ir a Sistema")
    assert not cu_goals.done_needs_an_act("ir a sistema")
    assert cu_goals.done_needs_an_act("Recortar la imagen")


def test_the_minds_judge_takes_the_apps_verdicts_on_echoes_and_searches() -> None:
    # Twin of v3-11: the query typed into a search and its own suggestion pressed (the App marks it «echo»).
    echoed = [{"operation": "input.text.type", "text": "pagina", "ok": True, "changed": True, "query": True},
              {"operation": "input.visible.click", "label": "pagina", "ok": True, "changed": True, "echo": True}]
    assert _done("256 fotos", PHOTOS, "crear una pagina nueva", echoed)["operation"] == "none"
    # Finding the thing is not doing it: its name searched and sent is no act unless the goal is the search.
    searched = [{"operation": "input.text.type", "text": "cuphead", "ok": True, "changed": True, "query": True},
                {"operation": "input.key.press", "key": "enter", "ok": True, "changed": True}]
    assert not cu_evidence.acted_with_effect(searched, "instalar cuphead")
    assert cu_evidence.acted_with_effect(searched, "buscar cuphead")
    assert cu_evidence.acted_with_effect(searched + [
        {"operation": "input.visible.click", "label": "Instalar", "ok": True, "changed": True}], "instalar cuphead")
    # Counter-cases: a name box is no search; a scroll counts only when it moved the content; Tab only moves the keyboard.
    assert cu_evidence.acted_with_effect(
        [{"operation": "input.text.type", "text": "informe", "ok": True, "changed": True}], "crear la carpeta informe")
    assert not cu_evidence.acted_with_effect(
        [{"operation": "input.scroll", "direction": "down", "ok": True, "changed": False}], "bajar hasta el final")
    assert cu_evidence.acted_with_effect(
        [{"operation": "input.scroll", "direction": "down", "ok": True, "changed": True}], "bajar hasta el final")
    assert not cu_evidence.acted_with_effect(
        [{"operation": "input.key.press", "key": "tab", "ok": True, "changed": True}], "marcar la casilla")


def _switches(bluetooth: str) -> dict:
    return {
        "window": {"title": "Configuración", "process": "SystemSettings"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Bluetooth", "state": ""},
            {"i": 1, "kind": "Text", "name": bluetooth, "state": ""},
            {"i": 2, "kind": "Button", "name": "Wi-Fi", "state": ""},
            {"i": 3, "kind": "Text", "name": "Activado", "state": ""},
        ],
    }


def test_the_minds_judge_refuses_what_the_first_look_showed_part_by_part() -> None:
    toggled = [{"operation": "input.visible.click", "label": "Bluetooth", "ok": True, "changed": True}]
    first = "\n".join(cu_first_look.look_parts(_switches("Desactivado")))
    # Twin of v3-40: what the first look showed already, cited after an act that did not bring it.
    same = dict(_switches("Desactivado"), firstLook=first)
    refused = _done("Activado", same, "activar el bluetooth", toggled)
    assert refused["operation"] == "none" and refused["code"] == "evidence_not_visible"
    # Counter-case: «Activado» newly beside the switch, though «Desactivado» held the word and Wi-Fi said it already.
    turned_on = dict(_switches("Activado"), firstLook=first)
    assert _done("Activado", turned_on, "activar el bluetooth", toggled)["operation"] == "done"
    # No first look handed over: nothing to judge against, the App still judges.
    assert _done("Activado", _switches("Desactivado"), "activar el bluetooth", toggled)["operation"] == "done"


def test_the_minds_judge_reads_the_sessions_typing_and_the_search_results() -> None:
    # Twin of v3-17 (turn 3): the gallery's search box still held the name typed a turn before.
    typed_before = "imagen prueba.png de la carpeta baxy-prueba-v3"
    gallery = {
        "window": {"title": "Fotos", "process": "Photos"},
        "controls": [{"i": 0, "kind": "Edit", "name": "Buscar en la galería", "state": "", "value": typed_before},
                     {"i": 1, "kind": "Button", "name": "Guardar como", "state": ""}],
        "typedInSession": [typed_before],
    }
    clicked = [{"operation": "input.visible.click", "label": "Guardar como", "ok": True, "changed": True}]
    assert _done(typed_before, gallery, "guardar la imagen como copia", clicked)["operation"] == "none"
    without = {key: value for key, value in gallery.items() if key != "typedInSession"}
    assert _done(typed_before, without, "guardar la imagen como copia", clicked)["operation"] == "done"
    # A search is proved by two result lines at least, never by the box nor a line saying nothing was found.
    searched = [{"operation": "input.text.type", "text": "cuphead", "ok": True, "changed": True, "query": True},
                {"operation": "input.key.press", "key": "enter", "ok": True, "changed": True}]
    box = [{"i": 0, "kind": "Edit", "name": "Buscar en la tienda", "state": "", "value": "cuphead"}]
    nothing = {"window": {"title": "Tienda", "process": "store"}, "controls": box,
               "text": {"C": ["cuphead", "No hay resultados para cuphead"]}}
    found = {"window": {"title": "Tienda", "process": "store"}, "controls": box,
             "text": {"C": ["cuphead", "1 resultado", "Cuphead Deluxe", "Cuphead Deluxe - Banda sonora"]}}
    one_line = {"window": {"title": "Tienda", "process": "store"}, "controls": box,
                "text": {"C": ["cuphead", "Cuphead Deluxe"]}}
    # (A click after the search moved the window, so the older echo rule leaves the judging to this one.)
    shown = searched + [{"operation": "input.visible.click", "label": "Ver todo", "ok": True, "changed": True}]
    assert _done("Cuphead", nothing, "buscar cuphead", shown)["operation"] == "none"
    assert _done("Cuphead Deluxe", one_line, "buscar cuphead", shown)["operation"] == "none"
    assert _done("Cuphead Deluxe", found, "buscar cuphead", shown)["operation"] == "done"
