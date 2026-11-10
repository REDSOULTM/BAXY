"""Rules ``weekday_date`` and ``unread_date`` of the answer check (VER1, PR-03 «en siete días es el viernes 12»): a weekday
told with a date the calendar puts on another one, or a date other than today's told with its weekday that nothing of
the turn gave. They compare the calendar and what the turn brought; the model keeps its tools and writes its answer again."""
import datetime as dt
import pathlib

import pytest

from baxy_mind.answer_check import check
from baxy_mind.mind import Mind
from test_answer_check import _r
from test_mind_final import _call, _mind, _say

TODAY = dt.date(2026, 11, 9)  # a Monday
READS = "read_only"  # the risk of a tool that changes nothing


def _found(rule: str, answer: str, request: str = "", receipts: list[dict] | None = None,
           today: dt.date | None = TODAY) -> list[dict]:
    return [f for f in check(answer, request, receipts or [], [], today=today) if f["rule"] == rule]


def _calendar(**asked: dict) -> dict:
    return _r("system.time", {"status": "completed", "verification": "output_only", "observed": {"calendar": {
        "today": {"date": "2026-11-09", "weekday": "Monday"}, **asked}}})


@pytest.mark.parametrize("answer, fact", [
    ("En siete días es el viernes 12.", "el 12 de noviembre de 2026 es jueves, no viernes"),
    ("Mañana es viernes 12.", "el 12 de noviembre de 2026 es jueves, no viernes"),
    ("Pasado mañana es martes 11 de noviembre de 2026.", "el 11 de noviembre de 2026 es miércoles, no martes"),
    ("El 27 de noviembre de 2026 es un **jueves**.", "el 27 de noviembre de 2026 es viernes, no jueves"),
    ("El 15 de enero de 2027 va a caer en un jueves.", "el 15 de enero de 2027 es viernes, no jueves"),
    ("El 18 de septiembre fue un sábado.", "el 18 de septiembre de 2026 es viernes, no sábado"),  # the nearest one
    ("December 25th, 2026 is a Thursday.", "el 25 de diciembre de 2026 es viernes, no jueves"),
    ("Thursday, November 13th, 2026 works.", "el 13 de noviembre de 2026 es viernes, no jueves"),
    ("Son las 22:10 de hoy, lunes 10 de noviembre de 2026.", "el 10 de noviembre de 2026 es martes, no lunes"),
    ("El 29 de febrero es lunes.", "el 29 de febrero de 2028 es martes, no lunes"),  # the nearest 29 February
    ("El 11 de septiembre de 2001 fue un lunes.", "el 11 de septiembre de 2001 es martes, no lunes"),
])
def test_a_weekday_that_is_not_the_dates_is_flagged_with_the_calendars_fact(answer: str, fact: str) -> None:
    findings = _found("weekday_date", answer)
    assert findings and findings[0]["fact"] == fact


@pytest.mark.parametrize("answer", [
    "Pasado mañana es miércoles 11 de noviembre de 2026.",
    "El 27 de noviembre de 2026 es un viernes.",
    "Hoy es lunes 9 de noviembre de 2026, a las 22:10.",
    "Este viernes que viene es el 13 de noviembre de 2026.",
    "El viernes 13 y el sábado 14 llueve.",
    "El lunes 30 lo entregué.",  # no month: last month's, this one's or the next
    "El viernes 12:30 nos vemos.",  # a time
    "El viernes 12 personas vienen a cenar.",  # an amount
    "El viernes a las 12 de la mañana.",
    "El 1 de enero no es lunes, es viernes.",
    "El lunes 9 hay clases, pero el 12 de noviembre no es martes.",
    "El 11 de septiembre de 2001 fue un martes.",
    "El cuento empieza un domingo 32 de enero.",  # not a date
])
def test_a_pair_the_calendar_has_or_that_is_no_date_is_not_said_to_be_another_weekday(answer: str) -> None:
    assert not _found("weekday_date", answer)


def test_a_pair_the_person_said_or_a_result_brings_is_theirs() -> None:
    said = "anota la reunión del viernes 12 de noviembre"
    assert not _found("weekday_date", "Anoté la reunión del viernes 12 de noviembre.", request=said)
    page = _r("web.fetch", {"status": "completed", "verification": "output_only",
                            "observed": {"text": "El evento es el lunes 12 de diciembre de 2026."}})
    assert not _found("weekday_date", "Según la página, el evento es el lunes 12 de diciembre de 2026.", receipts=[page])


def test_a_date_the_calendar_of_a_result_gives_on_that_weekday_backs_it() -> None:
    # system.time's reading of «27 de noviembre» with no year: the coming one and the last one; the answer tells the last.
    read = _calendar(onDate={"coming": {"date": "2026-11-27", "weekday": "Friday", "daysFromToday": 18},
                             "last": {"date": "2025-11-27", "weekday": "Thursday", "daysFromToday": -347}})
    assert not _found("weekday_date", "El 27 de noviembre del año pasado cayó jueves.", receipts=[read])
    assert not _found("weekday_date", "El 27 de noviembre fue jueves.", receipts=[read])
    assert _found("weekday_date", "El 27 de noviembre fue miércoles.", receipts=[read])


# The other half: the calendar has the pair, and it is a date the model counted («pasado mañana es martes 10» on Monday
# the 9th, three times of three with system.time's calendar a call away; «anteayer fue el sábado 28 de noviembre»).
@pytest.mark.parametrize("answer", [
    "Pasado mañana es martes 10 de noviembre de 2026.",
    "Anteayer fue el sábado 28 de noviembre de 2026.",
    "Mañana es martes, 10 de noviembre de 2026.",
    "El miércoles de la próxima semana es el 18 de noviembre.",  # the weekday first, the date as what it is: not read
    "Navidad cae viernes 25 de diciembre.",
    "This year Thanksgiving falls on Thursday, November 26th, 2026.",
])
def test_a_date_with_its_weekday_that_nothing_gave_is_told_as_counted(answer: str) -> None:
    expected = "próxima semana" not in answer
    assert bool(_found("unread_date", answer)) is expected


@pytest.mark.parametrize("answer, said, receipts", [
    ("Hoy es lunes 9 de noviembre de 2026.", "", []),  # the clock line's own
    ("El martes 10 tienes reunión.", "recuérdame que el martes 10 tengo reunión", []),
    ("El 11 de septiembre de 2001 fue un martes.", "", []),  # history, not a count from today
    ("El viernes 12:30 nos vemos.", "", []),
    ("Pasado mañana es miércoles 11 de noviembre de 2026.", "",
     [_calendar(inDays={"date": "2026-11-11", "weekday": "Wednesday", "daysFromToday": 2})]),
    ("La final es el sábado 28 de noviembre.", "",
     [_r("web.search", {"status": "completed", "verification": "output_only", "observed": {"results": [
         {"title": "Final", "url": "https://futbol.example/final", "snippet": "La final se juega el 28 de noviembre."}]}})]),
    ("Listo, la alarma queda para el viernes 13 a las 8.", "",
     [{**_r("schedule.alarms", {"status": "completed", "verification": "readback", "observed": {"created": True}}),
       "arguments": {"action": "create", "at": "2026-11-13T08:00"}}]),
])
def test_a_date_the_turn_gave_or_todays_own_is_not_told_as_counted(answer: str, said: str, receipts: list[dict]) -> None:
    assert not _found("unread_date", answer, request=said, receipts=receipts)


def test_with_no_clock_the_rules_read_nothing() -> None:
    assert not _found("weekday_date", "Mañana es viernes 12.", today=None)
    assert not _found("unread_date", "Pasado mañana es martes 10 de noviembre de 2026.", today=None)


@pytest.mark.parametrize("first, fact", [
    ("En siete días es el viernes 12.", "el 12 de noviembre de 2026 es jueves, no viernes"),
    ("En siete días es martes 10 de noviembre de 2026.", "la contaste tú"),
])
def test_the_mind_tells_the_fact_keeps_the_tools_and_the_second_answer_is_the_models(
        tmp_path: pathlib.Path, monkeypatch, first: str, fact: str) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    monkeypatch.setattr(Mind, "_today", staticmethod(lambda: TODAY))
    second = "En siete días es lunes 16 de noviembre."
    mind, server = _mind(tmp_path, [_say(first), _call("system_time", {"daysFromToday": 7}), _say(second)])
    mind.wire_to_op = {"system_time": "system.time"}
    mind.risk = {**mind.risk, "system_time": READS}
    step = mind.decide(1, "¿qué fecha es en siete días?")
    note = server.bodies[-1]["messages"][-1]["content"]
    assert fact in note and "system_time" in note
    assert step["kind"] != "conversation"  # the model looked the date up: its call goes out
    reading = _calendar(inDays={"date": "2026-11-16", "weekday": "Monday", "daysFromToday": 7})
    assert mind.continue_turn(2, reading["observation"])["reply"] == second


def test_the_rules_are_an_aid_that_can_be_switched_off(tmp_path: pathlib.Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "answer_check")
    monkeypatch.setattr(Mind, "_today", staticmethod(lambda: TODAY))
    first = "En siete días es el viernes 12."
    mind, _ = _mind(tmp_path, [_say(first)])
    assert mind.decide(1, "¿qué fecha es en siete días?")["reply"] == first
