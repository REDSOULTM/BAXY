"""Rule ``future_past`` of the answer check (encargo 71): a date after today told with a verb in the past, in a turn with
results. It compares only the date with the clock and the form of the verb; the model writes its answer again."""
import datetime as dt
from pathlib import Path

import pytest

from baxy_mind.answer_check import check
from baxy_mind.mind import Mind
from test_answer_check import _r
from test_mind_final import _call, _mind, _say

TODAY = dt.date(2026, 11, 3)
FILM = {"title": "Película de prueba", "url": "https://cine.example/prueba",
        "snippet": "La película se estrenará el 20 de diciembre de 2026 en todo el país."}


def _searched(*results: dict) -> dict:
    return _r("web.search", {"status": "completed", "verification": "output_only",
                             "observed": {"query": "prueba", "results": list(results or [FILM]),
                                          "resultCount": len(results or [FILM]), "answeredBy": "DuckDuckGo"}})


def _flagged(answer: str, receipts: list[dict] | None = None, today: dt.date | None = TODAY) -> list[dict]:
    return [f for f in check(answer, "¿cuándo sale?", [_searched()] if receipts is None else receipts, [], today=today)
            if f["rule"] == "future_past"]


@pytest.mark.parametrize("answer", [
    "La película se estrenó el 20 de diciembre de 2026.",
    "La película de prueba, según la web, se estrenó el 20 de diciembre de 2026.",
    "El 20 de diciembre de 2026 se estrenó la película.",
    "Salió en diciembre de 2026.",
    "Se estrenó el 20/12/2026.",
    "Se estrenó el 20-12-2026.",
    "Fue lanzada el 20 de diciembre de 2026.",
    "Ya se estrenaron los dos episodios el 20 de diciembre de 2026.",
    "Salió en 2027.",
    "Se estrenó el 20 de diciembre.",  # the year, from the result that brings that day
])
def test_a_date_after_today_told_in_the_past_is_flagged(answer: str) -> None:
    findings = _flagged(answer)
    assert findings
    assert "03/11/2026" in findings[0]["fact"]


@pytest.mark.parametrize("answer", [
    "La película se estrenará el 20 de diciembre de 2026.",
    "Se estrena el 20 de diciembre de 2026.",
    "Está programada para el 20 de diciembre de 2026.",
    "La anterior se estrenó el 3 de mayo de 2025.",
    "Salió en octubre de 2026.",
    "Salió hoy, 3 de noviembre de 2026.",
    "Salió en noviembre de 2026.",  # this month: it may have been
    "Marvel anunció que se estrenará el 20 de diciembre de 2026.",
    "Dijeron que llega el 20 de diciembre de 2026.",
    "Se retrasó hasta marzo de 2027.",
    "Se pospuso para marzo de 2027.",
    "Se pospuso para el 14 de enero de 2027.",
    "La retrasaron hasta el 14 de enero de 2027.",
    "La movieron al 12 de marzo de 2027.",
    "Se abrió en octubre y seguirá abierto hasta el 31 de enero de 2027.",
    "La primera salió en 2025 y la segunda saldrá el 14 de enero de 2027.",
    "Todavía no se estrenó: llegará el 20 de diciembre de 2026.",
    "No salió el 20 de diciembre de 2026.",
    "Si se estrenó el 20 de diciembre de 2026, te lo cuento.",
    "¿Se estrenó el 20 de diciembre de 2026?",
    "El cartel dice «se estrenó el 20 de diciembre de 2026».",
    "Se estrenó el 20 de diciembre.",  # no result brings that day: which year it means is not known
])
def test_what_is_not_a_later_date_told_in_the_past_is_not_flagged(answer: str) -> None:
    other = {"title": "Otra", "url": "https://cine.example/otra", "snippet": "Llega el 20 de enero de 2027."}
    receipts = [_searched(other)] if answer == "Se estrenó el 20 de diciembre." else None
    assert not _flagged(answer, receipts)


def test_a_turn_with_no_result_is_not_read() -> None:
    story = "En el cuento, la nave llegó a Marte el 20 de diciembre de 2150."
    assert not _flagged(story, [])
    assert not _flagged(story, [_r("web.search", {"status": "failed", "error": "web_search_unavailable"})])


def test_with_no_clock_the_rule_reads_nothing() -> None:
    assert not _flagged("La película se estrenó el 20 de diciembre de 2026.", today=None)


def test_the_mind_asks_again_with_the_date_and_the_second_answer_is_the_models(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    monkeypatch.setattr(Mind, "_today", staticmethod(lambda: TODAY))
    first, second = "Se estrenó el 20 de diciembre de 2026.", "Se estrenará el 20 de diciembre de 2026."
    mind, server = _mind(tmp_path, [_call("web_search", {"query": "prueba"}), _say(first), _say(second)])
    mind.wire_to_op = {"web_search": "web.search"}
    mind.risk = {**mind.risk, "web_search": "read_only"}
    mind.decide(1, "¿cuándo sale?")
    result = mind.continue_turn(2, _searched()["observation"])
    assert result["reply"] == second
    note = server.bodies[-1]["messages"][-1]["content"]
    assert "03/11/2026" in note and first[:-1] in note


def test_the_rule_is_an_aid_that_can_be_switched_off(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "answer_check")
    monkeypatch.setattr(Mind, "_today", staticmethod(lambda: TODAY))
    first = "Se estrenó el 20 de diciembre de 2026."
    mind, _ = _mind(tmp_path, [_call("web_search", {"query": "prueba"}), _say(first)])
    mind.wire_to_op = {"web_search": "web.search"}
    mind.risk = {**mind.risk, "web_search": "read_only"}
    mind.decide(1, "¿cuándo sale?")
    assert mind.continue_turn(2, _searched()["observation"])["reply"] == first
