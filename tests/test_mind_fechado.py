"""Aid «dated_search» (feria 2026-10-27): a question about something of a given year, answered in words from memory with
nothing looked at, is decided once more with a note to look it up. After «conversación nueva» the 4B model answered every
dated sports question from memory, 3 of 5 wrong; the rule of the prompt alone did not hold."""
import json
from pathlib import Path

from baxy_mind.mind import DATED_NOTE

from test_mind_final import _call, _mind, _say


def _trace(mind) -> list[dict]:
    return [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()]


def test_a_dated_question_answered_from_memory_is_looked_up(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    search = _call("web_search", {"query": "ganador mundial 2022"})
    mind, server = _mind(tmp_path, [_say("Lo ganó Francia."), search])
    step = mind.decide(1, "¿Quién ganó el mundial de fútbol 2022?")
    assert step["kind"] == "action" and step["operation"] == "web_search"
    assert server.bodies[-1]["messages"][-1]["content"] == DATED_NOTE
    assert "tool_choice" not in server.bodies[-1]
    assert DATED_NOTE not in [m.get("content") for m in mind.conversation]
    assert "Lo ganó Francia." not in [m.get("content") for m in mind.conversation]
    assert [r["stage"] for r in _trace(mind)].count("turn.dated") == 1


def test_the_answer_after_the_note_stands_whatever_it_says(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_say("Lo ganó Francia."), _say("Lo ganó Argentina.")])
    step = mind.decide(1, "¿quién ganó el mundial 2022?")
    assert step["kind"] == "conversation" and step["reply"] == "Lo ganó Argentina." and len(server.bodies) == 2


def test_questions_without_one_year_alone_and_answers_after_calls_are_not_held(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_say("Canberra."), _say("6000."), _say("En 1969."), _say("Vale."),
                                    _call("system_status", {}), _say("Son las 10 del 2026.")])
    assert mind.decide(1, "¿Cuál es la capital de Australia?")["reply"] == "Canberra."
    assert mind.decide(2, "¿Cuánto es 2000 por 3?")["reply"] == "6000."
    assert mind.decide(3, "¿En qué año llegó el hombre a la Luna?")["reply"] == "En 1969."
    assert mind.decide(4, "Escribe un poema sobre el 2026")["reply"] == "Vale."
    mind.decide(5, "¿Qué hora es en 2026?")
    assert mind.continue_turn(6, json.dumps({"status": "completed"}))["reply"] == "Son las 10 del 2026."
    assert len(server.bodies) == 6


def test_without_the_aid_a_dated_question_is_answered_as_written(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, server = _mind(tmp_path, [_say("Lo ganó Francia.")])
    assert mind.decide(1, "¿Quién ganó el mundial 2022?")["reply"] == "Lo ganó Francia." and len(server.bodies) == 1
