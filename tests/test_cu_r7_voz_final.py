"""The final voice of a computer-use mission (live 2026-10-07, cu-universal v2 bench).

v2-v9 «en el Reloj andá a Reloj mundial» and v2-u7/v2-w1 «… andá a Alarma» reached their place, but every draft
(«Ya estoy en la pantalla del reloj mundial, que marca las 7:58.») died as extra_claim: the clock the window wrote was
not counted as observed. The turns ended in the floor «Lo hice en la aplicación «Reloj»; hay 2: «Reloj mundial».», the
steps counted as a list read. v2-n5 (Wi-Fi on a PC without Wi-Fi) and v2-e2 failed and their floor said «No pude hacerlo
en la aplicación «Configuración».» with no cause, after drafts in the second person («No pudiste…») died as
missing_failure. Every situation here is our own shape of those runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import computer_use, llm  # noqa: E402

LRM = "‎"


def _reached(goal: str, place: str, screen: dict, application: str = "Reloj") -> dict:
    return {
        "kind": "operation",
        "operation": "mission.computer.use",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {
            "goal": goal,
            "application": application,
            "reached": True,
            "steps": [
                {"step": 1, "operation": "app.open", "appId": application, "ok": True, "changed": True},
                {"step": 2, "operation": "input.visible.click", "label": place, "ok": True, "name": place,
                 "kind": "ListItem", "selected": True, "changed": True},
            ],
            "window": {"title": application, "process": "ApplicationFrameHost"},
            "joined": False,
            "satisfiedBy": f"control:{place.casefold()}:current",
            "screen": screen,
        },
    }


WORLD_CLOCK = _reached("ir a reloj mundial", "Reloj mundial", {
    "title": "Reloj",
    "values": [{"name": "Reloj", "value": "Reloj"}, {"name": "Reloj mundial", "state": "selected"}],
    "numbers": [f"Hora local, {LRM}7{LRM}:{LRM}58{LRM}, miércoles, 7 de octubre de 2026", "7:58"],
    "lines": ["7:58", "Hora local", "Reloj", "Temporizador", "Alarma"],
})
ALARM = _reached("ir a alarma", "Alarma", {
    "title": "Reloj",
    "values": [{"name": "Alarma", "state": "selected"}, {"name": "Reloj", "value": "Reloj"}],
    "numbers": [f"EDITAR ALARMA, Buenos días, 7{LRM}:{LRM}00{LRM}, Diariamente,", "en 28 minutos", "7:00"],
    "lines": ["7:00", "Buenos días", "Lu Ma Mi Ju"],
})


def _failed(stopped_by: str) -> dict:
    reason = {
        "kind": "operation",
        "operation": "mission.computer.use",
        "polarity": "failure",
        "verified": False,
        "succeeded": False,
        "error": stopped_by,
        "observed": {
            "goal": "ir a red e internet; luego ir a wi-fi",
            "application": "Configuración",
            "reached": False,
            "steps": [
                {"step": 1, "operation": "input.visible.click", "label": "Red e Internet", "ok": True,
                 "name": "Red e Internet", "selected": True, "changed": True},
                {"step": 2, "operation": "input.visible.click", "label": "wi-fi", "ok": True, "name": "Wi-Fi",
                 "changed": True},
            ],
            "window": {"title": "Configuración", "process": "ApplicationFrameHost"},
            "joined": False,
            "subgoals": [
                {"goal": "ir a red e internet", "application": "Configuración", "reached": True},
                {"goal": "ir a wi-fi", "application": "Configuración", "reached": False},
            ],
            "screen": {"title": "Configuración", "lines": ["Red e Internet > Proxy", "Proxy"]},
            "stoppedBy": stopped_by,
        },
    }
    return {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
            "reason": reason}


def _defect(text: str, situation: dict, intent: str = "status", said: str = "") -> str:
    return llm.compose_visible_defect(text, intent, said, {"situation": json.dumps(situation, ensure_ascii=False)})


def _floor(situation: dict, language: str = "es") -> str:
    return llm._deterministic_final(situation, {}, "", language)


def test_a_clock_the_window_wrote_is_observed_even_with_bidi_marks() -> None:
    assert computer_use.screen_clocks(computer_use.project_seen(WORLD_CLOCK["observed"], "es")) == {"07:58"}
    said = "en el Reloj andá a Reloj mundial"
    assert _defect("Ya estoy en la pantalla del reloj mundial, que marca las 7:58.", WORLD_CLOCK, said=said) == ""
    assert _defect("Estoy en la sección de Reloj mundial y ahora se muestra la hora de 7:58.", WORLD_CLOCK) == ""
    assert _defect("Ya estoy en la pantalla de la alarma, que dice 7:00.", ALARM) == ""
    assert _defect("He abierto la pestaña de la alarma en el reloj y se muestra la hora de 7:00.", ALARM) == ""


def test_a_clock_the_window_did_not_write_is_still_invented() -> None:
    assert _defect("Ya estoy en Reloj mundial; son las 9:15.", WORLD_CLOCK) == "extra_claim"
    assert _defect("Ya estoy en Alarma; tienes una alarma a las 6:30.", ALARM) == "extra_claim"


def test_the_part_of_the_day_is_said_only_when_the_window_writes_it() -> None:
    # v2-v9 retry: «… las 7:58 de la tarde del miércoles…» over a window that writes «7:58» only.
    assert _defect(
        "Llegué al reloj mundial, que ahora muestra las 7:58 de la tarde del miércoles 7 de octubre de 2026.",
        WORLD_CLOCK,
    ) == "extra_claim"
    assert _defect("Ya estoy en Reloj mundial: son las 7:58 p. m.", WORLD_CLOCK) == "extra_claim"
    written = json.loads(json.dumps(WORLD_CLOCK))
    written["observed"]["screen"]["lines"].append("7:58 p. m.")
    assert _defect("Ya estoy en Reloj mundial: son las 7:58 p. m.", written) == ""


def test_going_somewhere_never_becomes_a_change_said_done() -> None:
    assert _defect("Listo, puse la alarma de las 7:00.", ALARM) == "extra_claim"
    assert _defect("Ya configuré la alarma para las 7:00.", ALARM) == "extra_claim"
    seen = computer_use.project_seen(ALARM["observed"], "es")
    assert computer_use.mission_defect("ya estoy en alarma y no cambie nada.", seen) is None
    assert computer_use.mission_defect("ya estoy en alarma y no puse ninguna alarma.", seen) is None


def test_the_floor_of_a_reached_place_names_the_place_as_the_window_writes_it() -> None:
    assert _floor(WORLD_CLOCK) == "Listo, estoy en «Reloj mundial»."
    assert _floor(WORLD_CLOCK, "en") == "Done, I'm in «Reloj mundial»."
    assert _floor(ALARM) == "Listo, estoy en «Alarma»."
    assert _defect(_floor(WORLD_CLOCK), WORLD_CLOCK) == ""


def test_the_floor_of_a_reached_act_names_the_application() -> None:
    dark = _reached("activar modo oscuro", "Modo oscuro", {"title": "Configuración"}, application="Configuración")
    assert _floor(dark) == "Listo, lo hice en «Configuración»."


def test_the_floor_of_a_failed_mission_says_what_was_not_reached_and_why() -> None:
    surface = _failed("computer_use_surface_unchanged")
    assert _floor(surface) == "No pude llegar a «Wi-Fi»: la pantalla dejó de cambiar tras lo que hice."
    assert _floor(surface, "en") == "I couldn't get to «Wi-Fi»: the screen stopped changing after what I did."
    assert _defect(_floor(surface), surface, intent="error") == ""
    # An untyped stop code is never said as prose.
    assert _floor(_failed("computer_use_something_new")) == "No pude llegar a «Wi-Fi»."


def test_a_failed_mission_gets_the_first_person_failure_voice() -> None:
    surface = _failed("computer_use_surface_unchanged")
    shape = llm._compose_shape_instruction(surface, "es", "en configuración andá a red e internet y luego a wi-fi")
    assert "first person singular" in shape and "never «pudiste»" in shape and "reason.seen" in shape
    # The veto stays: the person did not act.
    assert _defect("No pudiste llegar a Wi-Fi porque la pantalla dejó de cambiar.", surface, intent="error") == (
        "missing_failure"
    )
    assert _defect("No pude llegar a Wi-Fi: la pantalla dejó de cambiar.", surface, intent="error") == ""
