"""Uso real tanda 6b (Thursday 2026-09-24, Curicó, official window): composition defects.

Every real draft is replayed here as a regression row, next to es/en/spanglish paraphrases no fix names and negative
controls that keep a false fact out.

1. t5 «¿hoy es lunes?» → «No, hoy no es lunes. Hoy es jueves.» died three times as missing_name: the weekday
   question carried the whole date and the draft had to say the day of the month. A weekday (or a part of the
   week) asked alone is answered by the observed weekday; a date said with it must still be the observed one.
   Owners: semantic.network.calendar_parts_asked («weekday»), llm._calendar_facts / _misses_calendar_facts /
   _states_only_the_weekday; mirror UserMessagePolicy.PreservesObservedDate.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm
from baxy_mind.semantic.network import calendar_parts_asked

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
