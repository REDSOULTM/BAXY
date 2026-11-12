"""MEM1 (VIVO12 P1): «¿Cuál es mi color favorito?» → «Recuerdo que tu color favorito es el azul» (kept: turquesa), in a new
conversation and with no memory call. The answer check reads that claim against the conversation's calls: something of the
person told as remembered while no call to the memory completed in it (rule «unread_memory»)."""
from __future__ import annotations

from pathlib import Path

import pytest

from baxy_mind.answer_check import check
from test_mind_final import _call, _mind, _say

ASKED = "¿Cuál es mi color favorito?"


def _rules(answer: str, session: list | None = None, receipts: list | None = None, memory: str | None = "memory_recall",
           request: str = ASKED) -> list[str]:
    return [f["rule"] for f in check(answer, request, receipts or [], [] if session is None else session, memory=memory)
            if f["rule"] == "unread_memory"]


@pytest.mark.parametrize("answer", [
    "Recuerdo que tu color favorito es el azul.",
    "Mi memoria dice que tu color favorito es el azul. ¿Te suena?",
    "Sí, te acuerdo que tu color favorito es el azul. ¿Te gustaría que lo use para algo?",
    "Me dijiste que tu perro se llama Toby.",
    "Lo tengo guardado: tu cumpleaños es el 3 de mayo.",
    "Según mi memoria, tu jefa se llama Marta.",
    "I remember your kayak is called Nimbo.",
    "You told me your sister lives in Lyon.",
    "Sí, te acordé que tu comida favorita es la pizza.",  # MEM1 held-out H14, memory off
    "Me acordé de que tu gato se llama Luna.",
])
def test_something_of_the_person_told_as_remembered_with_no_memory_call(answer: str) -> None:
    assert _rules(answer) == ["unread_memory"]


# MEM1 base, held-out H04 and H06 (kept, never looked at): the memory said not to hold it with no call that looked.
@pytest.mark.parametrize("answer", [
    "No tengo guardada esa información en mi memoria.",
    "Mi memoria no guarda el nombre de tu gato. ¿Cómo se llama?",
    "No tengo registro de tu gato en mi memoria.",
    "No lo tengo en mi memoria.",
    "I don't have that saved.",
])
def test_the_memory_said_not_to_hold_it_with_nothing_that_looked(answer: str) -> None:
    assert _rules(answer) == ["unread_memory"]


@pytest.mark.parametrize("session", [
    [("memory.recall", False, True)],  # memory_none or memory_disabled: it looked
    [("memory.list", True, True)],
])
def test_a_memory_call_that_looked_backs_the_memory_said_not_to_hold_it(session: list) -> None:
    assert _rules("No tengo guardado tu cumpleaños.", session=session) == []


def test_without_the_memory_among_the_tools_saying_it_does_not_hold_it_is_no_finding() -> None:
    """MEM1, Esencial (no memory in the profile): «No tengo guardado…» is so, and told again it came back 3 rounds in 15
    turns of 90."""
    assert _rules("No tengo guardada esa información en mi memoria.", memory="") == []
    assert _rules("Recuerdo que tu color favorito es el azul.", memory="") == ["unread_memory"]


@pytest.mark.parametrize("answer", ["No recuerdo quién ganó ese mundial.", "No tengo esa información."])
def test_a_bare_not_remembering_is_not_of_the_memory(answer: str) -> None:
    assert _rules(answer) == []


@pytest.mark.parametrize("answer", [
    "No recuerdo cuál es tu color favorito.",
    "¿Quieres que lo recuerde?",
    "Lo recordaré si me lo dices.",
    "Tu color favorito es el turquesa.",
    "El azul suele recordarse como un color tranquilo.",
])
def test_no_claim_of_remembering_is_no_finding(answer: str) -> None:
    assert _rules(answer) == []


@pytest.mark.parametrize("session", [
    [("memory.recall", True, True)],
    [("memory.list", True, True)],
    [("memory.save", True, False)],
])
def test_a_memory_call_that_completed_in_the_conversation_backs_it(session: list) -> None:
    assert _rules("Recuerdo que tu color favorito es el turquesa.", session=session) == []


def test_a_memory_call_that_did_not_complete_backs_nothing() -> None:
    assert _rules("Recuerdo que tu color favorito es el azul.", session=[("memory.recall", False, True)]) == [
        "unread_memory"]


def test_not_read_with_the_session_unknown_or_without_the_memory_argument() -> None:
    assert [f for f in check("Recuerdo que tu color favorito es el azul.", ASKED, [], None, memory="memory_recall")
            if f["rule"] == "unread_memory"] == []
    assert [f for f in check("Recuerdo que tu color favorito es el azul.", ASKED, [], [])
            if f["rule"] == "unread_memory"] == []


def test_the_fact_names_the_call_that_reads_the_memory_or_says_it_is_not_there() -> None:
    fact = next(f["fact"] for f in check("Recuerdo que es el azul.", ASKED, [], [], memory="memory_recall")
                if f["rule"] == "unread_memory")
    assert "memory_recall" in fact
    off = next(f["fact"] for f in check("Recuerdo que es el azul.", ASKED, [], [], memory="")
               if f["rule"] == "unread_memory")
    assert "memory_recall" not in off and "memoria" in off


def test_the_note_keeps_the_tools_so_the_memory_is_read(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    first = "Recuerdo que tu color favorito es el azul."
    mind, server = _mind(tmp_path, [_say(first), _call("memory_recall", {"scope": "exact", "selector": "color favorito"})])
    mind.wire_to_op = {"memory_recall": "memory.recall"}
    mind.risk = {**mind.risk, "memory_recall": "read_only"}
    result = mind.decide(1, ASKED)
    assert result["kind"] == "action" and result["operation"] == "memory.recall", "it may read the memory"
    note = server.bodies[-1]["messages"][-1]["content"]
    assert "Nota interna" in note and "memory_recall" in note and first[:20] in note


def test_the_memory_note_goes_before_the_lookups(tmp_path: Path, monkeypatch) -> None:
    """MEM1 dev D06: «No tengo guardada esa información en mi memoria» was also a «denial_lookup», whose note («what is
    theirs, answer the same») left the memory unread."""
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_say("No tengo guardada esa información en mi memoria."),
                                    _call("memory_recall", {"scope": "exact", "selector": "comida favorita"})])
    mind.configure({"capabilities": [
        {"name": "web.search", "description": "Search the web.", "risk": "read_only", "group": "web",
         "argumentsSchema": {"type": "object", "properties": {"query": {"type": "string"}}}},
        {"name": "memory.recall", "description": "Read what BAXY remembers.", "risk": "read_only", "group": "memory",
         "argumentsSchema": {"type": "object", "properties": {"selector": {"type": "string"}}}}]})
    result = mind.decide(1, "¿Cuál es mi comida favorita?")
    assert result["kind"] == "action" and result["operation"] == "memory.recall"
    assert "memory_recall antes de responder" in server.bodies[-1]["messages"][-1]["content"]


def test_the_rule_is_an_aid_that_can_be_switched_off(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "answer_check")
    mind, server = _mind(tmp_path, [_say("Recuerdo que tu color favorito es el azul.")])
    mind.wire_to_op = {"memory_recall": "memory.recall"}
    mind.risk = {**mind.risk, "memory_recall": "read_only"}
    result = mind.decide(1, ASKED)
    assert result["kind"] == "conversation" and len(server.bodies) == 1
