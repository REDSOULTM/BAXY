"""Tanda 6 (2026-09-24): no reply, on any route, states a date about today that this PC's calendar denies.

t5 «Hoy es lunes 24 de septiembre de 2026.» (a Thursday, a system.time final), t40 «Sí, el año actual es 2024.» (a
conversation reply from memory), t47 «Hoy es el primero de marzo, creo.» (a search snippet reported as today). Every
weekday, day of the month, month and year a reply states about today is checked against the observed clock, or
this PC's own when the turn read none (llm._calendar_contradiction, in compose_visible_defect and
conversation_claim_defect), and never hedged. Denied values, other days said as such, history, songs and another
place's calendar are not claims about today.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from baxy_mind import llm

# Thursday 2026-09-24 18:55 at UTC-3, as system.time observed it in tanda-06.
_CLOCK = {
    "kind": "operation", "operation": "system.time", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "utc": "2026-09-24T21:55:05.5610298+00:00", "localUtcOffsetMinutes": -180},
}
_CLOCK_FACTS = {"situation": json.dumps(_CLOCK)}


@pytest.fixture
def thursday(monkeypatch: pytest.MonkeyPatch) -> None:
    """A turn that read no clock is checked against this PC's own: pinned to the Thursday of the run."""

    monkeypatch.setattr(llm, "_local_now", lambda: datetime(2026, 9, 24, 18, 55))


_SNIPPET_SEARCH = {
    "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "query": "en qué mes estamos", "count": 1, "results": [{
        "title": "¿En qué mes estamos? | Traducción", "url": "https://www.spanishdict.com/translate/mes",
        "snippet": "¿En qué mes estamos? - Hoy es el primero de marzo, creo. What month is it? - Today is March first.",
    }]},
}


@pytest.mark.usefixtures("thursday")
@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        # t47: a page's «today» is not today, on a search route with no clock read.
        ("necesito que me digas el mes en el que estamos ya, ¡rápido!", "Hoy es el primero de marzo, creo."),
        ("look up what month we are in", "Today is March first."),
        ("cuéntame algo de hoy", "Hoy es lunes y se celebra el día del café."),
        ("what's special about today?", "Today is Monday, September 21, International Peace Day."),
        ("dime algo", "Actualmente estamos en marzo de 2024."),
    ],
)
def test_a_search_report_never_states_another_day_as_today(asked: str, reply: str) -> None:
    facts = {"situation": json.dumps(_SNIPPET_SEARCH)}
    assert llm.compose_visible_defect(reply, "status", asked, facts) == "false_date"


@pytest.mark.usefixtures("thursday")
@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        ("¿sabes el año de ahora?", "Sí, el año actual es 2024."),  # t40, verbatim
        ("what year is it", "It's 2024, I believe."),
        ("¿en qué mes estamos, bro?", "Estamos en marzo."),
        ("is it the weekend yet?", "Yes, today is Saturday."),
        ("hola, ¿qué tal?", "Todo bien, hoy es martes y hace sol."),
        ("which day of the week is it", "It is Monday."),
    ],
)
def test_a_conversation_never_states_another_day_as_today(asked: str, reply: str) -> None:
    assert llm.conversation_claim_defect(reply, asked) in {"false_date", "hedged_date"}
    assert llm._shaped_conversation_answer_violates_contract(reply, asked, None)


@pytest.mark.usefixtures("thursday")
@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        # The true date said about today, in both languages.
        ("¿sabes el año de ahora?", "Estamos en 2026."),
        ("what day is it", "Today is Thursday, September 24th, 2026."),
        # Denied values, other days said as such, history, quotes of other dates, songs, other places.
        ("¿hoy es lunes?", "No, hoy no es lunes: es jueves."),
        ("¿estamos en 2025?", "No, no estamos en 2025: estamos en 2026."),
        ("qué pasó el 11 de septiembre de 1973", "Hoy se cumplen 53 años del golpe del 11 de septiembre de 1973."),
        ("cuéntame del torneo", "El torneo del 22 de marzo incluye la FIFA Series 2026."),
        ("pon September de Earth Wind and Fire", "Reproduciendo ahora September de Earth, Wind & Fire."),
        ("¿en qué año estamos?", "Estamos en 2026 y el mundial fue en 2022."),
        ("dime qué mes es", "Es septiembre; el próximo mes es octubre."),
        ("¿qué día es en Tokio?", "En Tokio ya es viernes 25 de septiembre."),
        ("¿cuántos días faltan para navidad?", "Faltan 92 días para Navidad, el 25 de diciembre."),
        ("qué tal", "Hoy es un buen día para correr."),
        ("hola", "Ahora es 5 veces más rápido."),
        ("what month is it", "It is September. May I help with anything else?"),
    ],
)
def test_true_dates_and_other_days_are_not_false_dates(asked: str, reply: str) -> None:
    assert llm._calendar_contradiction(reply, asked, llm._local_now()) == ""


def test_the_observed_clock_wins_over_this_pcs_own(monkeypatch: pytest.MonkeyPatch) -> None:
    # A turn that read the clock is checked against that reading, not against the moment it is checked.
    monkeypatch.setattr(llm, "_local_now", lambda: datetime(2026, 12, 31, 23, 59))
    assert llm.compose_visible_defect("Hoy es jueves 24 de septiembre.", "status", "¿qué día es hoy?", _CLOCK_FACTS) == ""


@pytest.mark.usefixtures("thursday")
@pytest.mark.parametrize(
    "reply", ["Creo que hoy es jueves.", "Today is Thursday, I think.", "Probablemente estamos en septiembre."]
)
def test_the_calendar_is_never_guessed(reply: str) -> None:
    # t47 «…, creo.»: a date is read from the clock, never hedged, even when it happens to be true.
    assert llm.conversation_claim_defect(reply, "¿qué día es hoy?") == "hedged_date"


@pytest.mark.parametrize(
    ("asked", "reply"),
    [("¿qué día es hoy?", "Creo que hoy es jueves 24 de septiembre."),
     ("what's the date today", "Today is Thursday, September 24, I think."),
     # t47's month, hedged: «…, creo.»
     ("necesito que me digas el mes en el que estamos ya, ¡rápido!", "Creo que estamos en septiembre.")],
)
def test_the_clock_read_is_never_hedged(asked: str, reply: str) -> None:
    assert llm.compose_visible_defect(reply, "status", asked, _CLOCK_FACTS) == "hedged_date"
