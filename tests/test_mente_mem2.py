"""MEM2 (VIVOM1, the live test of MEM1): what MEM1's rule «unread_memory» left open with the real window.
- «¿Te acuerdas de cuál es mi color favorito?» → «Sí, te acuerdas que tu color favorito es el azul» (turquesa kept, nothing
  read; 5 of 6 live): a datum of the person told as remembered in the second person.
- H10: only «el color favorito de mi hija es el verde agua» kept → «Tu color favorito es el verde agua» after reading it
  (3 of 3): a value whose record is named as someone else's, given to the person (rule «memory_subject»).
- «¿Recuerdas cómo se hace una tortilla?» → read the memory and «No tengo esa información guardada» (2 of 2; the base
  searched and gave the recipe): a question of the world, of nobody's datum, is not one to the person's memory."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind.answer_check import check
from test_mind_final import _call, _mind, _say

ASKED = "¿Te acuerdas de cuál es mi color favorito?"
MEMORY_RULES = ("unread_memory", "unbacked_memory", "memory_subject")


def _recall(*records: tuple[str, str], completed: bool = True) -> dict:
    observed = {"shown": len(records), "total": len(records),
                "records": [{"label": label, "value": value} for label, value in records], "exactMatch": False}
    body = ({"status": "completed", "cause": "memory_records", "verification": "output_only", "observed": observed}
            if completed else {"status": "failed", "error": "memory_none"})
    return {"op": "memory.recall", "tool": "memory_recall", "arguments": {"scope": "exact", "selector": "color favorito"},
            "observation": json.dumps(body, ensure_ascii=False), "outcome": "completed" if completed else "failed",
            "completed": completed, "read": True}


def _rules(answer: str, receipts: list | None = None, request: str = ASKED, memory: str | None = "memory_recall") -> list:
    receipts = receipts or []
    session = [(r["op"], r["completed"], r["read"]) for r in receipts]
    return [f["rule"] for f in check(answer, request, receipts, session, memory=memory) if f["rule"] in MEMORY_RULES]


# VIVOM1 rows 6-28 and 50 (live, both arms), and their English.
@pytest.mark.parametrize("answer", [
    "Sí, te acuerdas que tu color favorito es el azul. ¿Te gustaría que haga algo con ese color?",
    "Sí, te acuerdas que tu color favorito es el azul. ¿Te gustaría que lo use para algo?",
    "Sí, recuerdas que tu color favorito es el azul.",
    "Sí, te acordás que tu color favorito es el azul.",
    "Ya sabes que tu color favorito es el azul.",
    "Sé que tu color favorito es el azul.",
    "Tu color favorito es el azul, lo recuerdo bien.",
    "Yes, you remember your favorite color is mauve.",
    "I know your favorite color is mauve.",
    "As you told me, your favorite color is mauve.",
])
def test_a_datum_of_the_person_told_as_remembered_in_any_person_with_nothing_read(answer: str) -> None:
    assert _rules(answer) == ["unread_memory"]


@pytest.mark.parametrize(("answer", "asked"), [
    ("Sí, tu perro se llama Toby. ¿Te gustaría hacer algo con él?", "Do you remember my dog's name?"),  # MEM2 P03 s2
    ("Sí, tu color favorito es el azul.", ASKED),
    ("Yes, your favorite color is mauve.", "Do you know my favorite color?"),
    ("Sí, tu jefe se llama Martín.", "¿Vos sabés cómo se llama mi jefe?"),
])
def test_a_yes_to_a_question_of_remembering_tells_the_datum_as_remembered(answer: str, asked: str) -> None:
    assert _rules(answer, request=asked) == ["unread_memory"]


@pytest.mark.parametrize(("answer", "asked"), [
    ("Sí, te explico: el IVA se calcula multiplicando el precio neto por 0,19.", "¿Sabes cómo se calcula el IVA?"),
    ("Sí, es Canberra.", "¿Sabes cuál es la capital de Australia?"),
    ("Tu color favorito es el azul.", "¿Cuál es mi color favorito?"),  # no yes, no remembering: as MEM1 left it
])
def test_a_yes_without_whose_it_is_or_without_a_question_of_remembering_is_no_finding(answer: str, asked: str) -> None:
    assert _rules(answer, request=asked) == []


@pytest.mark.parametrize("answer", [
    "Sí, te acuerdas que tu color favorito es el azul.",
    "Recuerdo que tu color favorito es el azul.",
    "Yes, I remember your favorite color is mauve.",
])
def test_a_remembered_datum_that_the_memory_read_does_not_bring(answer: str) -> None:
    """The memory was read and brought turquesa (or nothing): «azul» is in no value it brought."""
    assert _rules(answer, [_recall(("color favorito", "turquesa"))]) == ["unbacked_memory"]
    assert _rules(answer, [_recall(completed=False)]) == ["unread_memory"]


def test_the_fact_of_an_unbacked_datum_says_what_the_memory_brought() -> None:
    fact = next(f["fact"] for f in check("Recuerdo que tu color favorito es el azul.", ASKED,
                                         [_recall(("color favorito", "turquesa"))],
                                         [("memory.recall", True, True)], memory="memory_recall")
                if f["rule"] == "unbacked_memory")
    assert "turquesa" in fact and "azul" not in fact


@pytest.mark.parametrize("answer", [
    "Sí, te acuerdas que tu color favorito es el turquesa.",
    "Sí, recuerdo que tu color favorito es el turquesa. ¿Quieres que lo use para algo?",
    "Tu color favorito es el turquesa.",
    "Yes, I remember: your favorite color is turquoise.",
])
def test_a_remembered_datum_the_memory_read_brings_is_no_finding(answer: str) -> None:
    assert _rules(answer, [_recall(("color favorito", "turquesa"), ("favorite color", "turquoise"))]) == []


# VIVOM1 H10 (rows 41-43) and MEM1's held-out H08/H09 and dev D08: someone else's value given to the person.
@pytest.mark.parametrize(("record", "answer", "asked"), [
    (("color favorito de mi hija", "verde agua"), "Tu color favorito es el verde agua.", "¿Cuál es mi color favorito?"),
    (("color favorito de mi hija", "verde agua"), "Sí, tu color favorito es el verde agua.", ASKED),
    (("color favorito de mi hija", "verde agua"), "Tu color favorito es el verde agua, pero eso es de tu hija.",
     "¿Cuál es mi color favorito?"),
    (("cumpleaños de mi hermana Lucía", "2 de noviembre"), "Tu cumpleaños es el 2 de noviembre.",
     "¿Cuándo es mi cumple, que no me acuerdo?"),
    (("jefe de mi hermano", "Ramiro Benítez"), "Tu jefe se llama Ramiro Benítez.", "¿Vos sabés cómo se llama mi jefe?"),
    (("color favorito del auto", "rojo"), "Tu color favorito es el rojo.", "¿Cuál es mi color favorito?"),
    (("my daughter's favorite color", "teal"), "Your favorite color is teal.", "Which colour do I like the most?"),
])
def test_a_value_whose_record_is_someone_elses_given_to_the_person(record: tuple, answer: str, asked: str) -> None:
    assert _rules(answer, [_recall(record)], request=asked) == ["memory_subject"]


@pytest.mark.parametrize(("record", "answer", "asked"), [
    (("color favorito de mi hija", "verde agua"), "El color favorito de tu hija es el verde agua.",
     "¿Cuál es mi color favorito?"),
    (("color favorito de mi hija", "verde agua"), "Tu hija prefiere el verde agua; el tuyo no lo tengo guardado.",
     "¿Cuál es mi color favorito?"),
    (("color favorito de mi hija", "verde agua"), "Su color favorito es el verde agua.",
     "¿Cuál es el color favorito de mi hija?"),
    (("nombre de la bici", "Relámpago"), "Tu bici se llama Relámpago.", "¿Te acordás cómo le puse a mi bici?"),
    (("cat's name", "Biscuit"), "Your cat is called Biscuit.", "What's my cat called?"),
    (("proyecto actual", "Proyecto Garza"), "Tu proyecto es el Proyecto Garza.", "¿Qué te conté de mi proyecto?"),
    (("color favorito", "turquesa"), "Tu color favorito es el turquesa.", "¿Cuál es mi color favorito?"),
])
def test_a_value_given_to_whom_its_record_names_is_no_finding(record: tuple, answer: str, asked: str) -> None:
    assert _rules(answer, [_recall(record)], request=asked) == []


# VIVOM1 rows 47-48 and the held-out's controls: a question of the world with «recuerdas / te acuerdas / sabes».
@pytest.mark.parametrize(("answer", "asked"), [
    ("No tengo esa información guardada en mi memoria. ¿Te gustaría que busque cómo se hace?",
     "¿Recuerdas cómo se hace una tortilla?"),
    ("Sí, recuerdo que se hace con huevos, papas y cebolla.", "¿Recuerdas cómo se hace una tortilla?"),
    ("Sí, me acuerdo: ganó Argentina en 1986.", "¿Te acuerdas de quién ganó el mundial del 86?"),
    ("Sé que la capital de Australia es Canberra.", "¿Sabes cuál es la capital de Australia?"),
    ("I remember it was 1969.", "Do you remember when the moon landing was?"),
    # MEM2 held-out K08 and K01, live drafts: the «te» is of the next clause.
    ("No tengo guardado ese dato en mi memoria, pero te cuento: se marinan los pescados en limón.",
     "Causa, ¿recuerdas cómo se prepara el ceviche?"),
    ("No tengo guardada la receta del pozole rojo, pero te puedo decir que lleva maíz.",
     "Oye, ¿te acuerdas cómo se hace el pozole rojo?"),
])
def test_a_question_of_the_world_is_not_one_to_the_persons_memory(answer: str, asked: str) -> None:
    assert _rules(answer, request=asked) == []


def test_the_memory_said_not_to_hold_the_persons_datum_still_is_one() -> None:
    """MEM1 dev D06 stays: the person asked of theirs («mi»), or the answer says it of them («tu»)."""
    assert _rules("No tengo esa información guardada en mi memoria.", request="¿Cuál es mi comida favorita?") == [
        "unread_memory"]
    assert _rules("No tengo guardada tu comida favorita.", request="¿Y la comida favorita?") == ["unread_memory"]


def test_a_tortilla_turn_gets_the_lookup_note_not_the_memory_one(tmp_path: Path, monkeypatch) -> None:
    """VIVOM1 row 48: the memory's note (before the lookup's) sent «¿Recuerdas cómo se hace una tortilla?» to the memory
    three rounds; the lookup's note is the one that says to search what is of the world."""
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_say("No tengo esa información guardada en mi memoria."),
                                    _call("web_search", {"query": "cómo se hace una tortilla"})])
    mind.configure({"capabilities": [
        {"name": "web.search", "description": "Search the web.", "risk": "read_only", "group": "web",
         "argumentsSchema": {"type": "object", "properties": {"query": {"type": "string"}}}},
        {"name": "memory.recall", "description": "Read what BAXY remembers.", "risk": "read_only", "group": "memory",
         "argumentsSchema": {"type": "object", "properties": {"selector": {"type": "string"}}}}]})
    result = mind.decide(1, "¿Recuerdas cómo se hace una tortilla?")
    note = server.bodies[-1]["messages"][-1]["content"]
    assert result["kind"] == "action" and result["operation"] == "web.search"
    assert "memory_recall antes de responder" not in note and "web_search" in note


def test_an_unbacked_or_misattributed_datum_is_written_again_without_tools(tmp_path: Path, monkeypatch) -> None:
    """After a read, the model is not sent to read again: it writes its answer again with what the read brought."""
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("memory_recall", {"scope": "exact", "selector": "color favorito"}),
                                    _say("Tu color favorito es el verde agua."),
                                    _say("No tengo guardado tu color favorito; el de tu hija es el verde agua.")])
    mind.wire_to_op = {"memory_recall": "memory.recall"}
    mind.risk = {**mind.risk, "memory_recall": "read_only"}
    first = mind.decide(1, "¿Cuál es mi color favorito?")
    assert first["kind"] == "action" and first["operation"] == "memory.recall"
    result = mind.continue_turn(2, _recall(("color favorito de mi hija", "verde agua"))["observation"])
    note = server.bodies[-1]["messages"][-1]["content"]
    assert "color favorito de mi hija" in note and "Nota interna" in note
    assert "tools" not in server.bodies[-1] or not server.bodies[-1]["tools"]
    assert result["kind"] == "conversation" and "hija" in result["reply"]
