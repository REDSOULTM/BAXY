"""REG1, C-2 of REV11 (the rules of MEM1/MEM2 «unread_memory», «unbacked_memory»): good answers they took as a datum of the
person told as remembered, in REV11's battery (tmp\\REV11\\zonas\\C\\casos.py: 8 of 9 flagged on mem2, 0 on int31-cand).
- What the person said in this conversation backs the datum as a value read from the memory does: «Mi perro se llama
  Toby. ¿Qué nombre le pongo al gato?» → «Me dijiste que tu perro se llama Toby…» is true, and the note («si no lo trae,
  no lo sabes») would have led the model to deny what the person had just said.
- «sé que / ya sabes que / I know (that) you / you know,» tell a datum of the person only with one of theirs named after
  them (tu, your): «Sé que te puede resultar confuso, pero la capital…» tells none.
- «No tengo registro de tus llamadas» says nothing of the memory: only a record said of the memory is."""
from __future__ import annotations

import json

import pytest

from baxy_mind.answer_check import check

MEMORY_RULES = ("unread_memory", "unbacked_memory", "memory_subject")


def _rules(answer: str, request: str, receipts: list | None = None) -> list[str]:
    receipts = receipts or []
    session = [(r["op"], r["completed"], r["read"]) for r in receipts]
    return [f["rule"] for f in check(answer, request, receipts, session, memory="memory_recall")
            if f["rule"] in MEMORY_RULES]


def _recall(*records: tuple[str, str]) -> dict:
    observed = {"records": [{"label": label, "value": value} for label, value in records]}
    return {"op": "memory.recall", "tool": "memory_recall", "arguments": {}, "completed": True, "read": True,
            "outcome": "completed", "observation": json.dumps({"status": "completed", "observed": observed})}


# REV11 battery FP1-FP3, FP5, FP7-FP9, and their kin.
@pytest.mark.parametrize(("answer", "request_"), [
    ("Sé que te puede resultar confuso, pero la capital de Australia es Canberra.", "¿Cuál es la capital de Australia?"),
    ("Sé que es molesto. Bebe agua y descansa un rato.", "Me duele mi cabeza, ¿qué hago?"),
    ("I know you are busy, so in short: Canberra is the capital.", "What's the capital of Australia? I'm in a hurry"),
    ("Ya sabes que la fotosíntesis convierte luz en azúcar en tus plantas.", "Explícame la fotosíntesis"),
    ("You know, the best laptop for you is a light one.", "What's the best laptop for my work?"),
    ("I know that you want it quick: press Win+Shift+S.", "How do I take a screenshot on my PC?"),
    ("Ya sabés que el mate se ceba con agua a unos 80 grados.", "¿Cómo se ceba bien el mate?"),
])
def test_a_knowing_phrase_with_no_datum_of_the_person_is_no_finding(answer: str, request_: str) -> None:
    assert _rules(answer, request_) == []


@pytest.mark.parametrize(("answer", "request_"), [
    ("Me dijiste que tu perro se llama Toby, así que lo llamaré así.",
     "Mi perro se llama Toby. ¿Qué nombre le pongo al gato?"),
    ("Como me contaste que tu hija cumple 7 años, una piñata es buena idea.",
     "Mi hija cumple 7 años el sábado. ¿Qué le regalo?"),
    ("You told me your sister lives in Lyon, so a train from Paris takes two hours.",
     "My sister lives in Lyon. How long is the train from Paris?"),
    ("Recuerdo que tu gata se llama Nube; para el perro, ¿qué tal Trueno?",
     "Mi gata se llama Nube. ¿Qué nombre le pongo al perro?"),
])
def test_a_datum_the_person_said_in_the_conversation_backs_it(answer: str, request_: str) -> None:
    assert _rules(answer, request_) == []


def test_the_persons_words_back_it_also_after_a_memory_read_that_did_not_bring_it() -> None:
    assert _rules("Me dijiste que tu perro se llama Toby, así que lo llamaré así.",
                  "Mi perro se llama Toby. ¿Qué nombre le pongo al gato?",
                  [_recall(("color favorito", "turquesa"))]) == []


@pytest.mark.parametrize(("answer", "request_"), [
    ("No tengo registro de tus llamadas: no veo el teléfono.", "¿Me llamó alguien hoy?"),
    ("No tengo ningún registro de tus compras en esa tienda.", "¿Cuánto gasté este mes?"),
])
def test_a_record_not_said_of_the_memory_is_no_finding(answer: str, request_: str) -> None:
    assert _rules(answer, request_) == []


# What MEM1 and MEM2 caught stays caught.
@pytest.mark.parametrize(("answer", "request_"), [
    ("Recuerdo que tu color favorito es el azul.", "¿Cuál es mi color favorito?"),
    ("Sí, te acuerdas que tu color favorito es el azul.", "¿Te acuerdas de cuál es mi color favorito?"),
    ("Sé que tu color favorito es el azul.", "¿Te acuerdas de cuál es mi color favorito?"),
    ("Ya sabes que tu color favorito es el azul.", "¿Cuál es mi color favorito?"),
    ("I know your favorite color is mauve.", "What's my favorite color?"),
    ("Claro, tu color favorito es el azul.", "¿Te acuerdas de mi color favorito?"),
    ("No tengo registro de tu gato en mi memoria.", "¿Cómo se llama mi gato?"),
    ("Me dijiste que tu perro se llama Toby.", "¿Cómo se llama mi perro?"),
    # The datum asked as a question is not told by the person: «¿Mi color favorito es el azul?» → «Sí, recuerdo…».
    ("Sí, recuerdo que tu color favorito es el azul.", "¿Mi color favorito es el azul?"),
    # Said by the person in part only: «Toby» is theirs, «labrador» is not.
    ("Me dijiste que tu perro Toby es un labrador.", "Mi perro se llama Toby. ¿Qué collar le compro?"),
    # MEM1/MEM2 bench answers (static sweep of their rows): a bare «no tengo registro» to a question of theirs is of the
    # memory, and a claim whose datum comes in the next sentence is still one.
    ("No tengo registro de tu cumpleaños. ¿Podrías decirme cuál es?", "¿Cuándo es mi cumpleaños?"),
    ("No tengo registro de tus alergias en este momento.", "¿Te acuerdas de mis alergias?"),
    ("No tengo registro de tu talla de zapatos en mi memoria.", "Oye, ¿sabes qué talla de zapatos uso yo?"),
    ("¡Ya lo tengo guardado! Tu perro se llama Chispo.", "¿Cómo se llama mi perro?"),
])
def test_a_datum_of_the_person_told_as_remembered_with_nothing_backing_it_stays(answer: str, request_: str) -> None:
    assert _rules(answer, request_) == ["unread_memory"]


def test_an_unbacked_datum_the_person_did_not_say_stays() -> None:
    assert _rules("Recuerdo que tu color favorito es el azul.", "¿Cuál es mi color favorito?",
                  [_recall(("color favorito", "turquesa"))]) == ["unbacked_memory"]
