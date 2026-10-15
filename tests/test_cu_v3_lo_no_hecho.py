"""Ronda 19 (uso real r17, palanca «lo-no-hecho-se-dice»): lo que no se hizo se dice, y lo que la pantalla muestra no se
cuenta como acto propio.

- t3-c07 (y t1-c09, t2-c07): «mandale a ron92 por discord…» con Discord cerrado. ``message.recipient.resolve`` falló
  con ``discord_client_not_running`` y dejó ``message.send`` sin hacer (notDone). «No envié el mensaje a ron92…
  porque el cliente no estaba abierto» murió dos veces en missing_failure (``_denies_the_failed_act`` sólo contaba los
  actos de resolver) y el respaldo dijo «No pude enviar el mensaje a «ron92».», sin causa.
- t3-c11/1 y t2-c16 T1: «hazme una captura de pantalla y guárdala en el escritorio», «…guardala en mis imagenes». La
  captura no acepta destino; la parte se perdió sin decirlo y quedó «Hice la captura de pantalla.».
- t3-c05/1: «what's the weather gonna be like in Curico tomorrow morning»: el tiempo trae el resumen del día, no la
  mañana; la respuesta lo dio como si fuera la mañana.
  La parte no servida de t3-c11, t2-c16 y t3-c05 se retiró en la revisión adversarial 2 (cambiaba el prompt de
  operaciones que no son computer use y daba falsos «quedó fuera»); sus sondas fijan la base.
- t3-c18/2 «Llegué al Programador… y elegí el modo Decimal.», t3-c19/3 «…y ahora el pincel está listo.», t2-c04 T2
  «He cambiado la escala a 125…»: valores que sólo la pantalla muestra (o que nadie vio) dichos como actos propios.
- t3-c18 (colocación): «Word se acomodó a la izquierda» no contaba como la colocación dicha.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from baxy_mind import llm, operation_floor
from baxy_mind import compose_payload
from baxy_mind import deterministic_finals
from baxy_mind import visible_defect
from baxy_mind import clock_facts
from baxy_mind import failure_wording
from baxy_mind import computer_use_finals
from baxy_mind.semantic import claims as semantic_claims
from baxy_mind.semantic import windows
from baxy_mind.semantic.normalize import fold

# ---------------------------------------------------------------- t3-c07: lo no hecho cuenta como la falla dicha
C07_SAID = "mandale a ron92 por discord que ya voy saliendo que me espere en la entrada"
C07_SITUATION = {
    "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
    "reason": {
        "kind": "operation", "operation": "message.recipient.resolve", "polarity": "failure", "verified": False,
        "succeeded": False, "error": "discord_client_not_running", "target": "ron92",
        "attempted": {"channel": "discord", "recipient": "ron92"},
        "notDone": [{"operation": "message.send", "target": "ron92"}],
    },
}
C07_DRAFT = "No envié el mensaje a ron92 en discord porque el cliente no estaba abierto."


def _facts(situation: dict) -> dict:
    return {"situation": json.dumps(situation, ensure_ascii=False)}


def test_c07_the_act_left_undone_denied_is_the_failure_told() -> None:
    assert failure_wording._denies_the_failed_act(C07_DRAFT, C07_SITUATION)
    assert visible_defect.compose_visible_defect(C07_DRAFT, "error", C07_SAID, _facts(C07_SITUATION)) != "missing_failure"


def test_c07_contracase_an_act_of_neither_stays_a_defect() -> None:
    # «no lo cerré» denies an act that is neither the failed one nor one left undone.
    assert not failure_wording._denies_the_failed_act("No lo cerré.", C07_SITUATION)


def test_contracase_no_lo_cerre_over_a_play_stays_a_defect() -> None:
    play = {
        "kind": "operation", "operation": "media.play.query", "polarity": "failure", "verified": False,
        "succeeded": False, "error": "spotify_query_result_mismatch", "target": "los bunkers",
    }
    assert not failure_wording._denies_the_failed_act("No lo cerré.", play)
    assert failure_wording._denies_the_failed_act("No puse los bunkers en Spotify porque no respondió.", play)


def test_contracase_a_real_failure_told_as_success_stays_vetoed() -> None:
    told = "Le envié el mensaje a ron92 por Discord."
    assert visible_defect.compose_visible_defect(told, "error", C07_SAID, _facts(C07_SITUATION)) != ""


def test_c07_the_last_sentence_says_the_cause_of_the_failure_family() -> None:
    said = deterministic_finals._deterministic_final(C07_SITUATION, {}, C07_SAID, "es")
    assert said.startswith("No pude enviar el mensaje a «ron92»")
    assert said.endswith(", porque " + operation_floor.failure_family_cause("discord_client_not_running", False) + ".")
    english = deterministic_finals._deterministic_final(C07_SITUATION, {}, "tell ron92 on discord I'm leaving", "en")
    assert english.endswith(", because " + operation_floor.failure_family_cause("discord_client_not_running", True) + ".")
    # The App's twin floor keeps its plain clause (tests/data/c03_m107_floor_twins.json).
    assert operation_floor.floor_final(C07_SITUATION, False) == "No pude enviar el mensaje a «ron92»."


def test_contracase_an_uncertain_step_keeps_its_own_but() -> None:
    # Encargo IMP2 (imp1 imp-wa-enviar, «Intenté enviar el mensaje a «Música», pero no pude confirmar si se hizo.» over a
    # contact search that failed before any send): the send a failed contact search left undone was not done, whatever
    # the search may have touched; it is said not done, with the cause of its family. An uncertain step that is itself
    # the act (a send left unconfirmed) keeps its own «pero no pude confirmar» and no cause.
    uncertain = json.loads(json.dumps(C07_SITUATION))
    uncertain["reason"]["effectUncertain"] = True
    said = deterministic_finals._deterministic_final(uncertain, {}, C07_SAID, "es")
    assert said.startswith("No pude enviar el mensaje a «ron92»") and "confirmar" not in said
    sent = {"kind": "operation", "operation": "message.send", "polarity": "failure", "verified": False,
            "succeeded": False, "error": "message_draft_not_verified", "effectUncertain": True, "target": "ron92"}
    told = operation_floor.with_family_cause(operation_floor.floor_final(sent, False), sent, False)
    assert told.startswith("Intenté enviar el mensaje") and ", porque" not in told


def test_floor_families_cover_the_app_not_running_not_installed_not_found() -> None:
    for code in ("discord_client_not_running", "spotify_client_not_running", "user_browser_not_running",
                 "whatsapp_client_not_installed", "app_not_found"):
        assert operation_floor.failure_family_cause(code, False), code
        assert operation_floor.failure_family_cause(code, True), code
    # A code of no family keeps the plain clause.
    assert operation_floor.failure_family_cause("verification_failed", False) == ""
    # «whatsapp_not_found» ends in «app_not_found» only by letters, not by its last words.
    assert operation_floor.failure_family_cause("whatsapp_not_found", False) == ""


def _mission_failed(operation: str, code: str, target: str = "") -> dict:
    reason = {
        "kind": "operation", "operation": operation, "polarity": "failure", "verified": False, "succeeded": False,
        "error": code,
    }
    if target:
        reason["target"] = target
    return {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
            "reason": reason}


# Revisión adversarial 2 (bloqueante 4): «…_not_found» names a control, a folder, a tab or the radios, not the act's
# object; the floor says no cause for it, never «porque no se encontró» of the song or the command.
@pytest.mark.parametrize(
    ("operation", "code", "target", "said", "base"),
    [
        ("media.play.query", "spotify_exact_play_control_not_found", "los bunkers", "pon los bunkers en spotify",
         "No pude poner la música «los bunkers»."),
        ("shell.command.run", "shell_command_directory_not_found", "dir", "ejecuta dir en la carpeta proyectos", ""),
        ("media.play.youtube", "youtube_tab_not_found", "", "pausa el video de youtube", ""),
        ("network.airplane.mode", "airplane_mode_radios_not_found", "", "activa el modo avión", ""),
        ("window.resolve", "window_not_found", "Nébula", "ponla a la izquierda", ""),
    ],
)
def test_a_not_found_of_another_thing_says_no_cause(
    operation: str, code: str, target: str, said: str, base: str,
) -> None:
    situation = _mission_failed(operation, code, target)
    final = deterministic_finals._deterministic_final(situation, {}, said, "es")
    assert "porque" not in final and "no se encontró" not in final
    assert final == operation_floor.floor_final(situation, False, clock_facts._local_now())
    if base:
        assert final == base
    english = deterministic_finals._deterministic_final(situation, {}, said, "en")
    assert "because" not in english and "wasn't found" not in english


def test_the_app_not_found_is_said_of_the_app() -> None:
    situation = _mission_failed("app.open", "app_not_found", "Nébula")
    final = deterministic_finals._deterministic_final(situation, {}, "abre nébula", "es")
    assert final.endswith(", porque no se encontró la aplicación.")


# ---------------------------------------------------------------- t3-c11, t2-c16, t3-c05: la parte no servida, retirada
# Revisión adversarial 2 de r19 (bloqueantes 1, 2, 3 y 7): la parte no servida («notServed») viajaba al redactor como
# hecho e instrucción nuevos en operaciones que no son computer use (capture.screenshot, weather.current,
# message.send, reminder.create…), y la regla dura del goal v3 prohíbe cambiar su prompt; además leía las partes del
# día sin la hora, buscaba el verbo de guardar a través de cláusulas subordinadas y citaba la parte plegada («en la
# manana»). Se retiró entera: estas sondas fijan que la base queda igual (ningún veto missing_not_served, ningún
# «quedó fuera» en el suelo, ningún hecho notServed para el redactor).
CAPTURE = {
    "kind": "operation", "operation": "capture.screenshot", "polarity": "success", "verified": True,
    "succeeded": True, "observed": {
        "version": 1, "captureId": "capture_8555e7683ae94ab295f68a4ed3f5783e", "width": 1920, "height": 1080,
        "sha256": "86d6d0a2d67721daf230bc43ac63c885e86174a79c4434355485c4598afebbdc", "scope": "virtual_screen",
        "createdAtUtc": "2026-10-09T04:05:37.7827044+00:00",
    },
}
C11_SAID = "hazme una captura de pantalla y guárdala en el escritorio"
C16_SAID = "toma una captura de pantalla y guardala en mis imagenes"
WEATHER = {
    "kind": "operation", "operation": "weather.current", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {
        "location": "Curicó", "country": "Chile", "temperatureC": 10.2, "condition": "mayormente despejado",
        "today": {"date": "2026-10-09", "maxC": 18, "minC": 9.2},
        "tomorrow": {"date": "2026-10-10", "maxC": 22.4, "minC": 12.1, "condition": "llovizna"},
    },
}
MESSAGE_SENT = {
    "kind": "operation", "operation": "message.send", "polarity": "success", "verified": True, "succeeded": True,
    "target": "Ana", "observed": {
        "messageId": "message_1", "recipientId": "recipient_1", "channel": "whatsapp", "displayName": "Ana",
        "delivery": "visible_postcondition",
        "contentSha256": "5f2b7c1e0d3a4b6c8e9f0a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5",
    },
}
REMINDER_CREATED = {
    "kind": "operation", "operation": "reminder.create", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"reminderId": "reminder_1", "title": "Guardar el informe", "dueAt": "2026-10-10T17:00:00-03:00"},
}
VOLUME_SET = {
    "kind": "operation", "operation": "audio.volume", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "volume": 30, "muted": False},
}
MINIMIZE_ALL = {
    "kind": "operation", "operation": "window.minimize.all", "polarity": "success", "verified": True,
    "succeeded": True, "observed": {"version": 1, "minimizedWindows": 6},
}
# (lo que la persona dijo, el resultado, un borrador verdadero, idioma)
RETIRED_PROBES = [
    # Bloqueante 1: la parte del día en curso sí queda servida por las condiciones actuales.
    ("¿cómo está el clima esta tarde en Curicó?", WEATHER,
     "Ahora en Curicó hay 10,2 °C, mayormente despejado.", "es"),
    ("how's the weather this morning in Curico?", WEATHER,
     "Right now in Curicó it's 10.2 °C and mostly clear.", "en"),
    ("va a hacer frío esta noche en Curicó?", WEATHER,
     "Ahora en Curicó hay 10,2 °C, mayormente despejado.", "es"),
    ("el weather en Curicó this afternoon?", WEATHER,
     "Ahora en Curicó hay 10,2 °C, mayormente despejado.", "es"),
    ("this morning it was raining, what's the weather now in Curico", WEATHER,
     "Right now in Curicó it's 10.2 °C and mostly clear.", "en"),
    ("no, te dije en la mañana que era Curicó, no Ñuñoa; el clima", WEATHER,
     "Ahora en Curicó hay 10,2 °C, mayormente despejado.", "es"),
    # Bloqueante 2: «guardé/dejé/saved» dentro del contenido o de una cláusula con «que» no es el destino.
    ("dile a Ana por whatsapp que guardé las fotos en el escritorio", MESSAGE_SENT,
     "Le envié el mensaje a Ana por WhatsApp.", "es"),
    ("tell Ana on whatsapp that I saved the photos to my desktop", MESSAGE_SENT,
     "I sent the message to Ana on WhatsApp.", "en"),
    ("mandale a Ana que le dejé el archivo en descargas", MESSAGE_SENT,
     "Le envié el mensaje a Ana por WhatsApp.", "es"),
    ("recuérdame mañana a las 5 guardar el informe en documentos", REMINDER_CREATED,
     "Listo, te recordaré mañana a las 17:00 «Guardar el informe».", "es"),
    ("baja el volumen a 30, que dejé el parlante en el escritorio", VOLUME_SET, "Dejé el volumen en 30.", "es"),
    # Bloqueante 3: la parte nunca se cita plegada («en la manana», «en mis imagenes», «en mi musica»).
    ("qué tiempo hará mañana en la mañana en Curicó", WEATHER,
     "Mañana en Curicó habrá llovizna, con máxima de 22,4 °C y mínima de 12,1 °C.", "es"),
    (C16_SAID, CAPTURE, "Hice la captura de toda la pantalla.", "es"),
    ("toma una captura y guárdala en mi música", CAPTURE, "Hice la captura de toda la pantalla.", "es"),
    # Los turnos de la ronda: el resultado se dice como en la base.
    (C11_SAID, CAPTURE, "Hice la captura de toda la pantalla.", "es"),
    ("what's the weather gonna be like in Curico tomorrow morning", WEATHER,
     "Tomorrow in Curicó will be drizzle with a high of 22.4°C and a low of 12.1°C.", "en"),
    ("vuelve al escritorio", MINIMIZE_ALL, "Minimicé todas las ventanas.", "es"),
    ("go to the desktop", MINIMIZE_ALL, "I minimized all the windows.", "en"),
]


@pytest.mark.parametrize(("said", "situation", "draft", "language"), RETIRED_PROBES)
def test_retired_not_served_vetoes_nothing_and_adds_nothing(
    said: str, situation: dict, draft: str, language: str,
) -> None:
    assert visible_defect.compose_visible_defect(draft, "status", said, _facts(situation), said=said) != "missing_not_served"
    payload = compose_payload._compose_situation_payload(situation, language, said)
    assert "notServed" not in payload
    final = deterministic_finals._deterministic_final(situation, payload, said, language)
    assert "quedó fuera" not in final and "left out" not in final
    assert "manana" not in final and "imagenes" not in final and "musica" not in final


def test_retired_weather_probe_keeps_the_base_verdict() -> None:
    # Bloqueante 1, sonda literal: base '' y el suelo «En Curicó hay 10,2 °C ahora, mayormente despejado.».
    said = "¿cómo está el clima esta tarde en Curicó?"
    draft = "Ahora en Curicó hay 10,2 °C, mayormente despejado."
    assert visible_defect.compose_visible_defect(draft, "status", said, _facts(WEATHER), said=said) == ""
    payload = compose_payload._compose_situation_payload(WEATHER, "es", said)
    assert deterministic_finals._deterministic_final(WEATHER, payload, said, "es") == (
        "En Curicó hay 10,2 °C ahora, mayormente despejado."
    )


def test_the_writer_prompt_carries_no_not_served_instruction() -> None:
    # Bloqueante 7: el prompt de operaciones que no son computer use no cambia.
    # llm.py was split by responsibility: the writer's prompts and checks now sit in its sibling modules.
    source = "".join(path.read_text(encoding="utf-8") for path in sorted(Path(llm.__file__).parent.glob("*.py")))
    assert "notServed" not in source and "missing_not_served" not in source
    assert importlib.util.find_spec("baxy_mind.semantic.unserved") is None


def test_c11_the_honest_draft_naming_the_place_is_not_an_invented_location() -> None:
    honest = "Hice la captura de toda la pantalla y quedó guardada de forma privada, no en el escritorio."
    assert visible_defect.compose_visible_defect(honest, "status", C11_SAID, _facts(CAPTURE), said=C11_SAID) == ""


@pytest.mark.parametrize(
    "draft",
    [
        # Bloqueante 5: cada lugar de la cláusula cuenta, no sólo el primero.
        "Hice la captura; quedó guardada, no en descargas sino en el escritorio.",
        "Hice la captura y quedó no solo en tu carpeta privada sino también en el escritorio.",
        # La base, intacta.
        "Hice la captura y quedó guardada en el escritorio.",
        "Hice la captura; se guardó en descargas.",
        "I took the screenshot and saved it to your desktop.",
    ],
)
def test_a_capture_place_claimed_after_a_negated_one_is_still_invented(draft: str) -> None:
    assert computer_use_finals._capture_place_claimed(fold(draft))
    said = "take a screenshot and save it to my desktop" if draft.startswith("I ") else C11_SAID
    assert visible_defect.compose_visible_defect(draft, "status", said, _facts(CAPTURE), said=said) == (
        "invented_capture_location"
    )


@pytest.mark.parametrize(
    "draft",
    [
        "Hice la captura de toda la pantalla y quedó guardada de forma privada, no en el escritorio.",
        "Hice la captura; no quedó en el escritorio sino en tu carpeta privada de BAXY.",
        "I took the screenshot; it was not saved to the desktop.",
    ],
)
def test_a_capture_place_only_denied_is_no_invented_location(draft: str) -> None:
    assert not computer_use_finals._capture_place_claimed(fold(draft))


# ---------------------------------------------------------------- t3-c18/2, t3-c19/3, t2-c04 T2: objeto del acto
C18_SITUATION = {
    "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
    "succeeded": True, "observed": {
        "goal": "hacer clic en programador", "application": "Calculadora", "reached": True,
        "successCheck": "stepDone:input.visible.click:programador", "stepCount": 2,
        "steps": [
            {"step": 1, "operation": "input.visible.click", "label": "Abrir navegación", "ok": True,
             "name": "Abrir navegación", "kind": "Button", "changed": True},
            {"step": 2, "operation": "input.visible.click", "label": "Programador Calculadora", "ok": True,
             "name": "Programador Calculadora", "kind": "ListItem", "changed": True},
        ],
        "window": {"title": "Calculadora", "process": "CalculatorApp"},
        "satisfiedBy": "stepDone:input.visible.click:programador",
        "screen": {"title": "Calculadora", "values": [
            {"name": "Decimal 0", "state": "selected"}, {"name": "Teclado numérico completo", "state": "selected"},
        ], "numbers": ["Hexadecimal 0", "Decimal 0", "Octal 0", "Binario 0"]},
    },
}


def test_c18_a_screen_value_told_as_an_act_is_vetoed() -> None:
    told = "Llegué al Programador de la Calculadora y elegí el modo Decimal."
    assert computer_use_finals._screen_value_told_as_act(told, C18_SITUATION) == "decimal"
    assert computer_use_finals._claims_defect(told, "status", C18_SITUATION) == "unbacked_act"


def test_c18_contracase_the_step_done_told_as_an_act_passes() -> None:
    told = "Llegué a la Calculadora y elegí el modo Programador."
    assert computer_use_finals._screen_value_told_as_act(told, C18_SITUATION) == ""
    # Said as what the screen shows, the value is an observation, not an act.
    assert computer_use_finals._screen_value_told_as_act("Elegí Programador; quedó en Decimal.", C18_SITUATION) == ""


def test_c18_the_place_of_the_act_is_not_its_object_in_english() -> None:
    # Revisión r19 (bloqueante d): «in the Calculator window» is where the act happened; the window's process
    # («CalculatorApp») is its identity, not a value only the screen shows. English over a Spanish screen passes.
    told = "I clicked Programmer in the Calculator window."
    assert computer_use_finals._screen_value_told_as_act(told, C18_SITUATION) == ""
    assert computer_use_finals._claims_defect(told, "status", C18_SITUATION) != "unbacked_act"
    assert computer_use_finals._screen_value_told_as_act("I opened Programmer mode in Calculator.", C18_SITUATION) == ""
    # Spanglish, the same act.
    assert computer_use_finals._screen_value_told_as_act("Hice click en Programador in the Calculator window.", C18_SITUATION) == ""
    # How the result was checked («stepDone:input.visible.click:…») is no value the screen showed.
    assert computer_use_finals._screen_value_told_as_act("Hice clic en Programador.", C18_SITUATION) == ""


def test_c18_contracase_a_screen_value_told_as_an_act_in_english_stays_vetoed() -> None:
    assert computer_use_finals._screen_value_told_as_act("I clicked on Decimal.", C18_SITUATION) == "decimal"
    assert computer_use_finals._screen_value_told_as_act("I selected Decimal in the Calculator window.", C18_SITUATION) == "decimal"


def test_the_facts_keys_and_window_identity_are_not_what_the_screen_showed() -> None:
    seen = semantic_claims.screen_seen(C18_SITUATION["observed"])
    assert "calculatorapp" not in seen
    assert "stepdone" not in seen and "input.visible.click" not in seen
    assert "values" not in seen and "numbers" not in seen
    assert "decimal 0" in seen


C19_SITUATION = {
    "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
    "succeeded": True, "observed": {
        "goal": "hacer clic en color; luego seleccionar rojo", "application": "Paint", "reached": True,
        "stepCount": 2,
        "steps": [
            {"step": 1, "operation": "input.visible.click", "label": "Selector de colores", "ok": True,
             "name": "Selector de colores", "kind": "Button", "changed": True},
            {"step": 2, "operation": "input.visible.click", "label": "rojo", "ok": True, "name": "Rojo",
             "kind": "ListItem", "changed": True},
        ],
        "window": {"title": "Sin título - Paint", "process": "mspaint"},
        "satisfiedBy": "stepDone:input.visible.click:=rojo",
        "screen": {"title": "Sin título - Paint", "values": [
            {"name": "Seleccionar", "value": "Rectángulo"}, {"name": "Selector de colores", "state": "on"},
            {"name": "Pinceles", "value": "Cepillo"},
        ]},
    },
}


def test_c19_a_tool_only_the_screen_shows_told_as_ready_is_vetoed() -> None:
    told = "Llegué a Paint, elegí el color rojo y ahora el pincel está listo."
    assert computer_use_finals._screen_value_told_as_act(told, C19_SITUATION) == "pincel"
    assert computer_use_finals._screen_value_told_as_act("Llegué a Paint y elegí el color rojo.", C19_SITUATION) == ""


C04_SITUATION = {
    "kind": "operation", "operation": "input.visible.click", "polarity": "success", "verified": True,
    "succeeded": True, "observed": {
        "version": 1, "ok": True, "effectObserved": True, "error": "", "labelStillOnScreen": True,
        "name": "pantalla", "controlIdentity": "ocr.1290.379", "absentOrDisabled": False, "selected": True,
        "surfaceChanged": True, "observedText": "YOU ahi ponle la escala en 125 BAXY Listo, estoy en «Pantalla».",
        "method": "render", "cascadeStage": "ocr",
    },
}


def test_c04_a_number_told_as_done_that_nothing_saw_is_vetoed() -> None:
    told = "He cambiado la escala a 125 en Configuración > Pantalla."
    assert computer_use_finals._screen_value_told_as_act(told, C04_SITUATION) == "125"


def test_c04_the_manner_of_the_act_is_not_its_object() -> None:
    # Revisión r19 (bloqueante d): «en 2 pasos» says how, not what; «Pantalla» is the step done.
    assert computer_use_finals._screen_value_told_as_act("Entré a Pantalla en 2 pasos.", C04_SITUATION) == ""
    assert computer_use_finals._screen_value_told_as_act("I got to Pantalla in 2 steps.", C04_SITUATION) == ""
    # Contracase: the number told as the act's own object stays vetoed in English too.
    assert computer_use_finals._screen_value_told_as_act("I set the scale to 125 in Settings.", C04_SITUATION) == "125"


def test_contracase_a_question_about_the_number_is_no_claim() -> None:
    assert computer_use_finals._screen_value_told_as_act("¿Subo la escala a 125?", C04_SITUATION) == ""


def test_contracase_a_key_pressed_with_its_step_done_passes() -> None:
    pressed = {
        "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
        "succeeded": True, "observed": {
            "goal": "en la calculadora apretá 5", "application": "Calculadora", "reached": True, "stepCount": 1,
            "steps": [{"step": 1, "operation": "input.visible.click", "label": "Cinco", "ok": True, "name": "Cinco",
                       "kind": "Button", "changed": True}],
            "screen": {"title": "Calculadora", "numbers": ["Se muestra 5"]},
        },
    }
    assert computer_use_finals._screen_value_told_as_act("En la calculadora apreté 5.", pressed) == ""


# Revisión adversarial 2 (bloqueante 6): the kind of the thing the step clicked («video») may stand anywhere on the
# screen («Reproducir video»); the name the reply quotes, or a place in a list («el primer video»), is the object.
def _video_mission(goal: str) -> dict:
    return {
        "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
        "succeeded": True, "observed": {
            "goal": goal, "application": "Navegador", "reached": True, "stepCount": 2,
            "steps": [
                {"step": 1, "operation": "input.visible.type", "text": "gatos", "ok": True, "changed": True},
                {"step": 2, "operation": "input.visible.click", "label": "Gatos graciosos 2024", "ok": True,
                 "name": "Gatos graciosos 2024", "kind": "Link", "changed": True},
            ],
            "screen": {"title": "Gatos graciosos 2024", "values": [
                {"name": "Reproducir video", "state": "on"}, {"name": "Suscribirse", "state": "off"},
            ]},
        },
    }


VIDEO_MISSION = _video_mission("busca gatos en youtube y abre el primero")


@pytest.mark.parametrize(
    "told",
    [
        "Abrí el video «Gatos graciosos 2024».",
        "I opened the video «Gatos graciosos 2024».",
        "Busqué gatos en YouTube y abrí el primer video.",
        "I searched for gatos on YouTube and opened the first video.",
        "Abrí el video Gatos graciosos 2024.",
    ],
)
def test_the_kind_of_the_thing_clicked_is_not_a_screen_value(told: str) -> None:
    assert computer_use_finals._screen_value_told_as_act(told, VIDEO_MISSION) == ""
    assert computer_use_finals._claims_defect(told, "status", VIDEO_MISSION) != "unbacked_act"


def test_contracase_a_screen_value_told_beside_the_name_stays_vetoed() -> None:
    # A name the screen shows and no step did is still told as an act, quoted kind or not.
    told = "Abrí el video «Gatos graciosos 2024» y elegí Suscribirse."
    assert computer_use_finals._screen_value_told_as_act(told, VIDEO_MISSION) == "suscribirse"
    assert computer_use_finals._screen_value_told_as_act("I opened the first video and pressed Suscribirse.", VIDEO_MISSION) == (
        "suscribirse"
    )
    # In Paint the tool told as ready is still the screen's alone (t3-c19/3).
    told = "Llegué a Paint, elegí el color rojo y ahora el pincel está listo."
    assert computer_use_finals._screen_value_told_as_act(told, C19_SITUATION) == "pincel"


# ---------------------------------------------------------------- t3-c18: la pasiva refleja dice la colocación
def test_c18_reflexive_passive_tells_the_placement() -> None:
    assert windows.tells_a_window_placement("Word se acomodó a la izquierda y Edge no estaba abierto.")
    assert windows.tells_a_window_placement("Las ventanas se colocaron una al lado de la otra.")
    assert not windows.tells_a_window_placement("No puedo colocar la ventana.")


def test_claims_reader_still_reads_acts() -> None:
    assert semantic_claims.claimed_acts("Elegí el modo Decimal.")


# ---------------------------------------------------------------- revisión adversarial 3: tecla, texto y cadena
# The veto judged every input.* operation and every step of a chain: «Pulsé Enter» died on the key the receipt holds,
# «Escribí 2024» on a number only the request gave, and «Abrí el Bloc de notas y escribí…» on the window's title the
# typing step saw. Each turn was right in the base and ended in the floor after three drafts. The receipts below are
# the adapter's (WindowsDesktopInteractionAdapter: the keyboard path and the window-message path).
class _Drafts(llm.LlmRuntime):
    """The drafts stand in for the model in order (the last one repeats); every request is kept."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.requests.append(payload)
        content = self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def _key_receipt(key: str, title: str = "Sin título: Bloc de notas") -> dict:
    return {
        "version": 1, "ok": True, "effectObserved": True, "action": "key", "key": key, "textLength": 0,
        "method": "keyboard", "acceptedEvents": 2, "expectedEvents": 2, "inputSize": 40, "lastWin32Error": 0,
        "foregroundProcessIdBefore": 4242, "foregroundProcessIdAfter": 4242, "foregroundTitleBefore": title,
        "authority": "win32_sendinput_return_count", "error": None,
    }


def _text_receipt(length: int, before: str = "Sin título: Bloc de notas", after: str | None = None) -> dict:
    return {
        "version": 1, "ok": True, "effectObserved": True, "action": "text", "key": None, "textLength": length,
        "method": "wm_char", "fieldClass": "RichEditD2DPT", "window": 132, "windowTitle": before,
        "foregroundProcessIdBefore": 4242, "foregroundProcessIdAfter": 4242, "foregroundTitleBefore": before,
        "foregroundTitleAfter": after or before, "frontChanged": False, "frontRestored": False,
        "authority": "win32_edit_message_reread", "error": None,
    }


def _verified(operation: str, observed: dict) -> dict:
    return {
        "kind": "operation", "operation": operation, "polarity": "success", "verified": True, "succeeded": True,
        "observed": observed,
    }


def _chain(second: dict, request: str) -> dict:
    opened = _verified(
        "app.open", {"appId": "notepad", "displayName": "Bloc de notas", "alreadyRunning": False, "windowHandle": 132},
    )
    return {
        "kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 2,
        "steps": [json.dumps(step, ensure_ascii=False) for step in (opened, second)], "completedRequest": request,
    }


KEY_TYPE_CHAIN_PROBES = [
    ("pulsa enter", _verified("input.key.press", _key_receipt("Enter")), "Pulsé Enter en el Bloc de notas."),
    ("press enter", _verified("input.key.press", _key_receipt("Enter")), "I pressed Enter."),
    ("guarda con ctrl+s", _verified("input.key.press", _key_receipt("ctrl+s")), "Apreté Ctrl+S en el Bloc de notas."),
    ("dale enter porfa", _verified("input.key.press", _key_receipt("Enter")), "Le di Enter."),
    ("escribe 2024", _verified("input.text.type", _text_receipt(4)), "Escribí 2024 en el Bloc de notas."),
    (
        "escribe hola mundo",
        _verified("input.text.type", _text_receipt(10, "Nueva pestaña - Opera", "hola mundo - Buscar con Google - Opera")),
        "Escribí hola mundo en el buscador.",
    ),
    (
        "abre el bloc de notas y escribe hola mundo",
        _chain(_verified("input.text.type", _text_receipt(10)), "Abre el bloc de notas y escribe hola mundo."),
        "Abrí el Bloc de notas y escribí «hola mundo».",
    ),
    (
        "abre el bloc de notas y escribe 2024",
        _chain(_verified("input.text.type", _text_receipt(4)), "Abre el bloc de notas y escribe 2024."),
        "Abrí el Bloc de notas y escribí 2024.",
    ),
    (
        "abre el bloc de notas y pulsa enter",
        _chain(_verified("input.key.press", _key_receipt("Enter")), "Abre el bloc de notas y pulsa enter."),
        "Abrí el Bloc de notas y pulsé Enter.",
    ),
    ("pulsa enter", _verified("input.key.press", _key_receipt("Enter")), "Pulsé la tecla Enter."),
]


@pytest.mark.parametrize(("said", "situation", "draft"), KEY_TYPE_CHAIN_PROBES)
def test_a_key_a_text_or_a_chain_told_as_done_is_not_a_screen_value(said: str, situation: dict, draft: str) -> None:
    assert computer_use_finals._screen_value_told_as_act(draft, situation) == ""
    assert computer_use_finals._claims_defect(draft, "status", situation) != "unbacked_act"
    facts = _facts(situation)
    assert visible_defect.compose_visible_defect(draft, "status", said, facts, said=said) == ""
    # A scripted writer repeating the draft: the first draft goes out, in the request's language, with no retry.
    writer = _Drafts([draft])
    assert writer.compose_user_message(said, "status", facts) == draft
    assert len(writer.requests) == 1


def test_a_visible_click_is_still_judged_but_not_by_the_window_title() -> None:
    clicked = _verified("input.visible.click", {
        "version": 1, "ok": True, "name": "Guardar", "kind": "Button", "surfaceChanged": True,
        "windowTitle": "Guardar como", "foregroundTitleBefore": "Guardar como",
        "foregroundTitleAfter": "Sin título: Bloc de notas", "authority": "windows_uia_invoke", "error": None,
    })
    assert computer_use_finals._screen_value_told_as_act("Hice clic en Guardar en el Bloc de notas.", clicked) == ""
    assert computer_use_finals._screen_value_told_as_act("Abrí el Bloc de notas y hice clic en Guardar.", clicked) == ""


def test_contracase_a_screen_value_told_in_a_chain_step_stays_vetoed() -> None:
    # The mission step of a chain is still judged, and what another step did does not back the screen's value.
    chain = _chain(C18_SITUATION, "Abre la calculadora y entra al modo programador.")
    told = "Abrí la Calculadora, llegué al Programador y elegí el modo Decimal."
    assert computer_use_finals._screen_value_told_as_act(told, chain) == "decimal"
    assert computer_use_finals._claims_defect(told, "status", chain) == "unbacked_act"
    assert computer_use_finals._screen_value_told_as_act("Abrí la Calculadora y elegí el modo Programador.", chain) == ""


def test_the_window_titles_and_the_receipt_fields_are_not_what_the_screen_showed() -> None:
    seen = semantic_claims.screen_seen(_text_receipt(10, "Nueva pestaña - Opera", "hola mundo - Buscar con Google"))
    for word in ("opera", "hola", "buscar", "wm_char", "richedit", "win32", "text"):
        assert word not in seen
