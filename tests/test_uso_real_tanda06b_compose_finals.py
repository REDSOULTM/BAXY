"""Uso real tanda 6b (Thursday 2026-09-24, Curicó, official window): composition defects.

Every real draft is replayed here as a regression row, next to es/en/spanglish paraphrases no fix names and negative
controls that keep a false fact out.

1. t5 «¿hoy es lunes?» → «No, hoy no es lunes. Hoy es jueves.» died three times as missing_name: the weekday
   question carried the whole date and the draft had to say the day of the month. A weekday (or a part of the
   week) asked alone is answered by the observed weekday; a date said with it must still be the observed one.
   Owners: semantic.network.calendar_parts_asked («weekday»), llm._calendar_facts / _misses_calendar_facts /
   _states_only_the_weekday; mirror UserMessagePolicy.PreservesObservedDate.
2. t21 «let me know my current location» → all three drafts added the temperature, humidity and wind and died as
   extra_claim: the narrator got the whole weather read. The place asked alone sends only the place fields; the
   validator stays, and a weather draft is told the place focus. Owners: llm._project_weather_read,
   _weather_answer_instruction, _weather_fact_defect, the invented_number hint.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm
from baxy_mind.semantic.network import calendar_parts_asked
from test_c03_cpu_actor import Recorder

# --- 1. a weekday asked alone is answered by the weekday ---------------------------------------------------------

# Thursday 2026-09-24 21:48 at UTC-3, as system.time observed it in tanda-06b t5.
_CLOCK = {
    "kind": "operation", "operation": "system.time", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "utc": "2026-09-25T00:48:03.7496569+00:00", "localUtcOffsetMinutes": -180},
}


def _clock_defect(reply: str, asked: str, language: str = "es") -> str:
    payload = llm._compose_situation_payload(_CLOCK, language, asked)
    return llm.compose_visible_defect(reply, "status", asked, {"situation": json.dumps(_CLOCK)}) or (
        llm._payload_fact_defect(reply, payload, asked)
    )


@pytest.mark.parametrize(
    ("asked", "part"),
    [
        ("¿hoy es lunes?", "weekday"),  # t5, verbatim
        ("is it monday today?", "weekday"),
        ("¿es viernes hoy o qué?", "weekday"),
        ("today is tuesday right?", "weekday"),
        ("¿ya es finde?", "weekday"),
        ("what day of the week is it", "weekday"),
        ("hoy es sábado, cierto?", "weekday"),
        ("is it el weekend already", "weekday"),
        # A day of the month, the date or «qué día es» asks for the date.
        ("¿hoy es lunes 28?", "date"),
        ("¿qué día es hoy?", "date"),
        ("what's the date today", "date"),
        ("is today monday the 28th", "date"),
        ("¿qué día de la semana es el 4 de octubre?", "date"),
    ],
)
def test_the_weekday_asked_alone_is_the_part_asked(asked: str, part: str) -> None:
    assert calendar_parts_asked(asked) == (part,)


def test_the_weekday_asked_alone_carries_only_the_weekday() -> None:
    assert llm._compose_situation_payload(_CLOCK, "es", "¿hoy es lunes?") == {
        "weekday": "jueves", "operation": "system.time",
    }
    assert llm._compose_situation_payload(_CLOCK, "en", "is it monday today?")["weekday"] == "Thursday"
    assert "say yes or no first" in llm._calendar_instruction("¿hoy es lunes?")
    assert "no date is needed" in llm._calendar_instruction("¿hoy es lunes?")


@pytest.mark.parametrize(
    ("asked", "reply", "language"),
    [
        ("¿hoy es lunes?", "No, hoy no es lunes. Hoy es jueves.", "es"),  # t5's three drafts, verbatim
        ("¿hoy es lunes?", "No, hoy es jueves.", "es"),
        ("¿hoy es lunes?", "No, es jueves 24 de septiembre.", "es"),  # a true date may still be said
        ("is it monday today?", "No, it's Thursday.", "en"),
        ("¿es viernes hoy o qué?", "Todavía no: hoy es jueves.", "es"),
        ("today is tuesday right?", "No, today is Thursday.", "en"),
        ("¿ya es finde?", "No, hoy es jueves.", "es"),
        ("what day of the week is it", "It's Thursday.", "en"),
        ("hoy es sábado, cierto?", "No, ni sábado: hoy es jueves.", "es"),
        ("is it el weekend already", "No, hoy es jueves.", "es"),
    ],
)
def test_the_true_weekday_answers_the_weekday_question(asked: str, reply: str, language: str) -> None:
    assert _clock_defect(reply, asked, language) == ""


@pytest.mark.parametrize(
    ("asked", "reply", "defect"),
    [
        ("¿hoy es lunes?", "Sí, hoy es lunes.", "missing_name"),
        ("¿hoy es lunes?", "No, hoy es viernes.", "missing_name"),
        ("¿hoy es lunes?", "No, hoy no es lunes.", "missing_name"),
        ("is it monday today?", "Yes, it's Monday.", "missing_name"),
        ("¿ya es finde?", "Sí, ya es fin de semana.", "missing_name"),
        # The weekday is right and the date is false: the clock still denies it.
        ("¿hoy es lunes?", "No, hoy es jueves 25 de septiembre.", "false_date"),
        ("is it monday today?", "No, it's Thursday, September 23.", "false_date"),
        # A day of the month asked still needs the date.
        ("¿hoy es lunes 28?", "No, hoy es jueves.", "missing_name"),
    ],
)
def test_a_false_weekday_or_date_is_still_rejected(asked: str, reply: str, defect: str) -> None:
    assert _clock_defect(reply, asked) == defect


# --- 2. where the person is: only the place is sent ---------------------------------------------------------------

# The weather.current receipt of tanda-06b (t1, t21, t39 read the same one).
_WEATHER_SEEN = {
    "version": 1, "location": "Curico", "region": "Region de Curico", "country": "Chile",
    "locatedBy": "public_ip_address", "observedAtLocal": "2026-09-24T21:45", "timezone": "America/Santiago",
    "temperatureC": 14.1, "apparentC": 14.8, "humidityPercent": 92, "windKmh": 1.5, "precipitationMm": 0,
    "uvIndex": 0, "dewPointC": 12.8, "weatherCode": 3, "condition": "nublado",
    "today": {"date": "2026-09-24", "weekday": "jueves", "maxC": 18.9, "minC": 12.6, "rainProbabilityPercent": 3,
              "uvIndexMax": 4.8, "sunrise": "07:33", "sunset": "19:44"},
    "tomorrow": {"date": "2026-09-25", "weekday": "viernes", "maxC": 21, "minC": 12.5, "rainProbabilityPercent": 6,
                 "uvIndexMax": 5.5, "condition": "nublado", "sunrise": "07:31", "sunset": "19:45"},
    "laterDays": [
        {"date": "2026-09-26", "weekday": "sábado", "condition": "nublado", "maxC": 19.9, "minC": 12,
         "rainProbabilityPercent": 0},
        {"date": "2026-09-27", "weekday": "domingo", "condition": "nublado", "maxC": 20, "minC": 14.5,
         "rainProbabilityPercent": 0},
        {"date": "2026-09-28", "weekday": "lunes", "condition": "parcialmente nublado", "maxC": 19, "minC": 13.2,
         "rainProbabilityPercent": 6},
        {"date": "2026-09-29", "weekday": "martes", "condition": "nublado", "maxC": 18.8, "minC": 13.1,
         "rainProbabilityPercent": 2},
        {"date": "2026-09-30", "weekday": "miércoles", "condition": "llovizna", "maxC": 20.3, "minC": 12.1,
         "rainProbabilityPercent": 4},
    ],
    "airQuality": {"usAqi": 81, "category": "moderada", "pm25": 23.2, "pm10": 27.6},
    "authority": "open_meteo_forecast_v1",
}
_WEATHER = {
    "kind": "operation", "operation": "weather.current", "polarity": "success", "verified": True, "succeeded": True,
    "observed": _WEATHER_SEEN,
}


def _weather_defect(reply: str, asked: str, language: str = "es") -> str:
    """Both composer checks of a weather final, on the payload the narrator was given."""

    payload = llm._compose_situation_payload(_WEATHER, language, asked)
    return llm.compose_visible_defect(reply, "status", asked, {"situation": json.dumps(_WEATHER)}) or (
        llm._payload_fact_defect(reply, payload, asked)
    )


@pytest.mark.parametrize(
    "asked",
    ["let me know my current location", "¿dónde estoy?", "where am i rn", "en qué ciudad estoy",
     "what city am i in right now", "dime mi ubicación actual"],
)
def test_the_own_place_question_sends_only_the_place(asked: str) -> None:
    payload = llm._compose_situation_payload(_WEATHER, "en", asked)
    assert payload["seen"] == {
        "location": "Curico", "region": "Region de Curico", "country": "Chile",
        "locatedBy": "public_ip_address",
    }
    instruction = llm._weather_answer_instruction(asked, "en")
    assert "temperatureC" not in instruction and "nothing about the weather" in instruction


def test_a_weather_question_still_gets_the_whole_read() -> None:
    assert llm._compose_situation_payload(_WEATHER, "es", "¿qué tiempo hace?")["seen"]["temperatureC"] == 14.1


@pytest.mark.parametrize(
    ("asked", "reply", "language"),
    [
        ("let me know my current location", "You are in Curico, Region de Curico, Chile.", "en"),
        ("¿dónde estoy?", "Estás en Curicó, Chile.", "es"),
        ("where am i rn", "Around Curico, Chile.", "en"),
        ("dime mi ubicación actual", "Estás cerca de Curicó, en la Región de Curicó.", "es"),
    ],
)
def test_the_place_alone_answers(asked: str, reply: str, language: str) -> None:
    assert _weather_defect(reply, asked, language) == ""


@pytest.mark.parametrize(
    ("asked", "reply", "defect"),
    [
        # t21's three drafts, verbatim: the weather numbers are no longer even in what the narrator was given.
        ("let me know my current location",
         "You are currently in Curico, Region of Curico, Chile. The temperature is 14.1°C, humidity 92%, "
         "wind speed 1.5 km/h.", "invented_number"),
        ("let me know my current location",
         "You are in Curico, Region de Curico, Chile. The current temperature is 14.1°C, with a humidity of "
         "92%, wind speed of 1.5 km/h, and a dew point of 12.8°C.", "invented_number"),
        ("let me know my current location",
         "I am in Curico, Region de Curico, Chile. The current temperature is 14.1°C with a humidity of 92% "
         "and wind speed of 1.5 km/h.", "invented_number"),
        ("let me know my current location", "You are in Curico, Chile, where the temperature is mild.",
         "extra_claim"),
        ("¿dónde estoy?", "Estás en Curicó, Chile, y está nublado.", "extra_claim"),
        ("where am i", "You're in Curico, where it's mild.", "extra_claim"),
        # Another place is not the place read.
        ("¿dónde estoy?", "Estás en Santiago, Chile.", "missing_state"),
    ],
)
def test_the_weather_or_another_place_is_not_the_place_answer(asked: str, reply: str, defect: str) -> None:
    assert _weather_defect(reply, asked, "en") == defect


def test_the_place_prompt_carries_no_weather_and_a_weather_draft_is_told_the_place_focus() -> None:
    drafted = "You are in Curico, Chile. The temperature is 14.1°C."
    answer = "You are in Curico, Region de Curico, Chile."
    client = Recorder([drafted, answer])
    reply = client.compose_user_message(
        "let me know my current location", "status", {"situation": json.dumps(_WEATHER)},
    )
    assert reply == answer
    first = json.dumps(client.payloads[0]["messages"], ensure_ascii=False)
    assert "humidityPercent" not in first and "temperatureC" not in first
    assert "nothing about the weather" in json.dumps(client.payloads[1]["messages"], ensure_ascii=False)
