"""Rule ``past_future`` of the answer check (VER1, G-03): the mirror of ``future_past``: a date wholly before today told as
coming, in a turn with results («la próxima reunión es el 27-28 de octubre de 2026» on 9 November 2026). It compares
only the date with the clock and the form of what is said of it; the model writes its answer again."""
import datetime as dt
import pathlib

import pytest

from baxy_mind.answer_check import check
from baxy_mind.mind import Mind
from test_answer_check import _r
from test_mind_final import _call, _mind, _say

TODAY = dt.date(2026, 11, 9)
MEETINGS = {"title": "Calendario de reuniones", "url": "https://banco.example/calendario",
            "snippet": "Reunión del 27-28 de octubre de 2026. La siguiente es el 8-9 de diciembre de 2026."}


def _searched(*results: dict) -> dict:
    return _r("web.search", {"status": "completed", "verification": "output_only",
                             "observed": {"query": "reunión", "results": list(results or [MEETINGS]),
                                          "resultCount": len(results or [MEETINGS]), "answeredBy": "DuckDuckGo"}})


def _flagged(answer: str, receipts: list[dict] | None = None, today: dt.date | None = TODAY) -> list[dict]:
    return [f for f in check(answer, "¿cuándo es la próxima?", [_searched()] if receipts is None else receipts, [],
                             today=today) if f["rule"] == "past_future"]


@pytest.mark.parametrize("answer", [
    "La próxima reunión del Fed está programada para el 27-28 de octubre de 2026.",
    "La próxima reunión es el 27 de octubre de 2026.",
    "La Copa aún no tiene campeón: la final se jugará en octubre de 2026.",
    "El 27 de octubre de 2026 se jugará la final.",
    "La final será el 3 de noviembre de 2026.",
    "El estreno será en 2025.",
    "Van a reunirse el 27 de octubre de 2026.",
    "El partido se disputará el 27/10/2026.",
])
def test_a_date_before_today_told_as_coming_is_flagged(answer: str) -> None:
    findings = _flagged(answer)
    assert findings
    assert findings[0]["fact"] == "hoy es 2026-11-09: esa fecha ya pasó, no es la que viene"


@pytest.mark.parametrize("answer", [
    "La próxima reunión es el 8-9 de diciembre de 2026.",
    "La reunión anterior fue el 27-28 de octubre de 2026; la próxima será el 8 de diciembre de 2026.",
    "La final se jugará el 28 de noviembre de 2026.",
    "La final se jugará en noviembre de 2026.",  # this month: it may still come
    "La próxima vez que juegan es hoy, 9 de noviembre de 2026.",
    "La reunión del 27 de octubre de 2026 se repetirá en diciembre.",
    "No será el 27 de octubre de 2026.",
    "¿Será el 27 de octubre de 2026?",
    "Si la próxima es el 27 de octubre de 2026, ya pasó.",
    "Dijeron en octubre de 2026 que el próximo año subirá.",
    "El torneo terminó el 27 de octubre de 2026 y el próximo será en 2027.",
    "Sí, se reunieron el 27 de octubre de 2026.",
])
def test_what_is_not_an_earlier_date_told_as_coming_is_not_flagged(answer: str) -> None:
    assert not _flagged(answer)


def test_a_turn_with_no_result_is_not_read() -> None:
    plan = "En el cuento, la nave llegará a Marte el 20 de diciembre de 2020."
    assert not _flagged(plan, [])
    assert not _flagged(plan, [_r("web.search", {"status": "failed", "error": "web_search_unavailable"})])


def test_with_no_clock_the_rule_reads_nothing() -> None:
    assert not _flagged("La próxima reunión es el 27 de octubre de 2026.", today=None)


def test_the_mind_asks_again_with_todays_date_and_the_second_answer_is_the_models(tmp_path: pathlib.Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    monkeypatch.setattr(Mind, "_today", staticmethod(lambda: TODAY))
    first, second = "La próxima reunión es el 27-28 de octubre de 2026.", "La próxima reunión es el 8-9 de diciembre de 2026."
    mind, server = _mind(tmp_path, [_call("web_search", {"query": "reunión"}), _say(first), _say(second)])
    mind.wire_to_op = {"web_search": "web.search"}
    mind.risk = {**mind.risk, "web_search": "read_only"}
    mind.decide(1, "¿cuándo es la próxima reunión?")
    result = mind.continue_turn(2, _searched()["observation"])
    assert result["reply"] == second
    note = server.bodies[-1]["messages"][-1]["content"]
    assert "2026-11-09" in note and "ya pasó" in note


def test_the_rule_is_an_aid_that_can_be_switched_off(tmp_path: pathlib.Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "answer_check")
    monkeypatch.setattr(Mind, "_today", staticmethod(lambda: TODAY))
    first = "La próxima reunión es el 27-28 de octubre de 2026."
    mind, _ = _mind(tmp_path, [_call("web_search", {"query": "reunión"}), _say(first)])
    mind.wire_to_op = {"web_search": "web.search"}
    mind.risk = {**mind.risk, "web_search": "read_only"}
    mind.decide(1, "¿cuándo es la próxima reunión?")
    assert mind.continue_turn(2, _searched()["observation"])["reply"] == first
