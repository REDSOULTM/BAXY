"""Tanda 6 (2026-09-24, a Thursday, official window): false dates, the most serious defect («nunca inventa»).

A. t5 «¿hoy es lunes?» → «Hoy es lunes 24 de septiembre de 2026.»: the question named a weekday, the payload carried
   only the date, and the narrator echoed the question's weekday. A weekday named in the question is asked
   (llm._requests_weekday), and a yes/no calendar question is answered yes or no, then with the observed value.
B. t40 «¿sabes el año de ahora?» → conversation «Sí, el año actual es 2024.» and t47 «necesito que me digas el mes en el
   que estamos ya, ¡rápido!» → a search snippet «Hoy es el primero de marzo, creo.»: the present said as «de ahora»,
   «en el que estamos», asked with «sabes»/«necesito que me digas» and followed by a hurry, is the clock read
   (semantic.network._direct_current_time_request).
C. t26 «¿sabes qué días fueron el último fin de semana?» → «No tengo información…»: a day counted from today is
   arithmetic on the observed date (semantic.temporal.relative_days, network.relative_calendar_days), carried as
   asked_days and checked (llm._calendar_facts, _misses_calendar_facts; mirror UserMessagePolicy.RelativeCalendarDay).

Every list holds es/en/spanglish paraphrases none of the fixes names, with negative controls.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from baxy_mind import llm
from baxy_mind.semantic.network import calendar_parts_asked, relative_calendar_days
from baxy_mind.semantic.reading import read
from baxy_mind.semantic.temporal import relative_days

_OPERATIONS = (
    "system.time", "web.search", "weather.current", "calendar.event.list", "notification.schedule",
    "reminder.create", "media.play.query", "audio.volume",
)
_THURSDAY = date(2026, 9, 24)
# Thursday 2026-09-24 18:55 at UTC-3, as system.time observed it in tanda-06.
_CLOCK = {
    "kind": "operation", "operation": "system.time", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "utc": "2026-09-24T21:55:05.5610298+00:00", "localUtcOffsetMinutes": -180},
}
_CLOCK_FACTS = {"situation": json.dumps(_CLOCK)}


def _effects(text: str) -> tuple[str, ...] | None:
    effects = read(text, available_operations=_OPERATIONS).effects
    return None if effects is None else effects.operations


def _clock_defect(reply: str, asked: str) -> str:
    """Both composer checks of a system.time final: the visible defects and the carried calendar facts."""

    payload = llm._compose_situation_payload(_CLOCK, "es", asked)
    return llm.compose_visible_defect(reply, "status", asked, _CLOCK_FACTS) or llm._payload_fact_defect(
        reply, payload, asked
    )


# ------------------------------------------------------------------ A. a weekday named in the question is asked


@pytest.mark.parametrize(
    "text",
    ["¿hoy es lunes?", "is today friday", "¿es martes hoy?", "hoy es jueves, ¿verdad?", "is it wednesday yet?",
     "sabes si hoy es domingo", "¿hoy es 24?", "is today the 25th?", "¿estamos a 3 de octubre?"],
)
def test_a_yes_no_day_question_reads_the_clock_and_carries_the_date(text: str) -> None:
    assert _effects(text) == ("system.time",)
    assert calendar_parts_asked(text) == ("date",)
    payload = llm._compose_situation_payload(_CLOCK, "es", text)
    assert payload["date"] == "2026-09-24"


@pytest.mark.parametrize("text", ["¿hoy es lunes?", "is today friday", "¿es martes hoy?", "hoy es jueves, ¿verdad?"])
def test_a_weekday_named_in_the_question_carries_the_observed_weekday(text: str) -> None:
    assert llm._compose_situation_payload(_CLOCK, "es", text)["weekday"] == "jueves"
    assert "say yes or no first" in llm._calendar_instruction(text)


@pytest.mark.parametrize(
    ("reply", "published"),
    [
        ("Hoy es lunes 24 de septiembre de 2026.", False),  # t5, verbatim
        ("Sí, hoy es lunes 24 de septiembre.", False),
        ("Hoy no es lunes. Es viernes.", False),  # t5's first draft: another false weekday, and no date
        ("No, hoy es jueves 24 de septiembre de 2026.", True),
        ("No, es jueves 24 de septiembre.", True),
    ],
)
def test_the_answer_to_hoy_es_lunes_is_the_true_weekday(reply: str, published: bool) -> None:
    assert (_clock_defect(reply, "¿hoy es lunes?") == "") is published


@pytest.mark.parametrize(
    ("asked", "reply", "published"),
    [
        ("is today friday", "No, today is Thursday, September 24.", True),
        ("is today friday", "Yes, today is Friday, September 24.", False),
        ("¿estamos en 2025?", "No, estamos en 2026.", True),
        ("¿estamos en 2025?", "Sí, estamos en 2025.", False),
        ("is it 2027 already?", "No, it is 2026.", True),
        ("¿hoy es 24?", "Sí, hoy es jueves 24 de septiembre.", True),
        ("¿hoy es 24?", "No, hoy es 23 de septiembre.", False),
    ],
)
def test_other_yes_no_calendar_questions(asked: str, reply: str, published: bool) -> None:
    assert (_clock_defect(reply, asked) == "") is published


# ------------------------------------------------------------------ B. the present, however it is said


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("¿sabes el año de ahora?", ("year",)),  # t40, verbatim
        ("necesito que me digas el mes en el que estamos ya, ¡rápido!", ("month",)),  # t47, verbatim
        ("¿sabes el año actual?", ("year",)),
        ("¿me dices la fecha de hoy?", ("date",)),
        ("quiero que me digas el año en curso", ("year",)),
        ("tell me the year we're in", ("year",)),
        ("dime el mes que corre, rapidito", ("month",)),
        ("can you tell me the current month, quick", ("month",)),
        ("¿sabes el día de ahorita?", ("date",)),
        ("¿estamos en 2025?", ("year",)),
    ],
)
def test_the_present_said_any_way_is_the_clock_read(text: str, parts: tuple[str, ...]) -> None:
    assert _effects(text) == ("system.time",)
    assert calendar_parts_asked(text) == parts


@pytest.mark.parametrize(
    "text",
    [
        "necesito que me digas el mes en que nació Messi",
        "¿sabes el año en que cayó el muro?",
        "dime el mes de las flores, rápido",
        "qué día es el partido",
        "¿qué día fue la independencia de Chile?",
        "what date is easter",
        "¿cuándo es tu cumpleaños?",
    ],
)
def test_the_date_of_something_else_is_not_the_clock(text: str) -> None:
    assert _effects(text) != ("system.time",)


@pytest.mark.parametrize(
    ("asked", "reply", "published"),
    [
        ("¿sabes el año de ahora?", "Sí, el año actual es 2024.", False),  # t40, verbatim
        ("¿sabes el año de ahora?", "Estamos en 2026.", True),
        ("necesito que me digas el mes en el que estamos ya, ¡rápido!", "Hoy es el primero de marzo, creo.", False),
        ("necesito que me digas el mes en el que estamos ya, ¡rápido!", "Estamos en septiembre.", True),
    ],
)
def test_the_present_is_answered_from_the_clock(asked: str, reply: str, published: bool) -> None:
    assert (_clock_defect(reply, asked) == "") is published


# ------------------------------------------------------------------ C. a day counted from today is arithmetic


@pytest.mark.parametrize(
    ("text", "days"),
    [
        ("¿sabes qué días fueron el último fin de semana?", ("2026-09-19", "2026-09-20")),  # t26, verbatim
        ("¿cuándo fue el fin de semana pasado?", ("2026-09-19", "2026-09-20")),
        ("which days were last weekend", ("2026-09-19", "2026-09-20")),
        ("¿qué día es mañana?", ("2026-09-25",)),
        ("¿mañana qué día es?", ("2026-09-25",)),
        ("what date was yesterday", ("2026-09-23",)),
        ("¿cuándo es pasado mañana?", ("2026-09-26",)),
        ("what day is the day after tomorrow", ("2026-09-26",)),
        ("¿qué día fue anteayer?", ("2026-09-22",)),
        ("qué fecha es el próximo lunes", ("2026-09-28",)),
        ("dime qué fecha cae el sábado que viene", ("2026-09-26",)),
        ("which day was last monday", ("2026-09-21",)),
        ("¿qué fecha fue el lunes pasado?", ("2026-09-21",)),
        ("¿qué día fue hace tres días?", ("2026-09-21",)),
        ("what day will it be in 10 days", ("2026-10-04",)),
        ("what was the date two days ago", ("2026-09-22",)),
        ("y dentro de una semana qué fecha será", ()),  # a week counted is not one day asked
    ],
)
def test_a_day_counted_from_today_is_computed_from_the_calendar(text: str, days: tuple[str, ...]) -> None:
    assert tuple(day.isoformat() for day in relative_calendar_days(text, _THURSDAY)) == days
    if days:
        assert _effects(text) == ("system.time",)


@pytest.mark.parametrize(
    "text",
    ["¿qué día es hoy?", "what day is the meeting tomorrow", "qué día es el partido del lunes",
     "¿qué días abre el museo el fin de semana?", "¿cuándo fue la última vez que llovió?"],
)
def test_today_and_the_days_of_other_things_are_not_counted(text: str) -> None:
    assert relative_calendar_days(text, _THURSDAY) == ()


def test_the_last_weekend_on_a_weekend_is_the_one_before() -> None:
    assert relative_days("el ultimo fin de semana", date(2026, 9, 27)) == (date(2026, 9, 19), date(2026, 9, 20))
    assert relative_days("el ultimo fin de semana", date(2026, 9, 26)) == (date(2026, 9, 19), date(2026, 9, 20))
    assert relative_days("el lunes pasado", date(2026, 9, 21)) == (date(2026, 9, 14),)


def test_the_asked_days_are_carried_with_their_weekdays_instead_of_today() -> None:
    payload = llm._compose_situation_payload(_CLOCK, "es", "¿sabes qué días fueron el último fin de semana?")
    assert payload == {
        "asked_days": [{"date": "2026-09-19", "weekday": "sábado"}, {"date": "2026-09-20", "weekday": "domingo"}],
        "operation": "system.time",
    }
    assert "clock" not in llm._compose_situation_payload(_CLOCK, "en", "¿cuándo es pasado mañana?")


@pytest.mark.parametrize(
    ("asked", "reply", "published"),
    [
        ("¿sabes qué días fueron el último fin de semana?",
         "El último fin de semana fue el sábado 19 y el domingo 20 de septiembre.", True),
        ("¿sabes qué días fueron el último fin de semana?", "Fueron el sábado 26 y el domingo 27 de septiembre.", False),
        ("¿sabes qué días fueron el último fin de semana?", "No tengo información sobre el último fin de semana.", False),
        ("¿qué día es mañana?", "Mañana es viernes 25 de septiembre.", True),
        ("¿qué día es mañana?", "Mañana es jueves 24 de septiembre.", False),
        ("¿qué día es mañana?", "Mañana es sábado 25.", False),
        ("what date was yesterday", "Yesterday was Wednesday, September 23.", True),
        ("what date was yesterday", "Yesterday was Tuesday, September 22.", False),
    ],
)
def test_the_asked_days_are_the_answer(asked: str, reply: str, published: bool) -> None:
    assert (_clock_defect(reply, asked) == "") is published
