"""Tandas 6c and 7 (2026-09-25, official window): single-message misses.

- «¿quién te desarrolló?» → «No tengo información sobre quién me desarrolló.»: the identity answer told nothing about
  him; it now carries one of his facts (his name or the PC he lives on) beside the detail he does not have.
- «¿cuánto rato queda para las seis?» → a web search and «No se indica…»: the countdown reading knew only «cuánto
  (tiempo) falta/queda/resta»; any measure of time and any verb of remaining asks the same countdown.

The phrasings below are not the tandas': they are paraphrases (es/en/spanglish) the fixes do not name, with negative
controls.
"""

from __future__ import annotations

import pytest

from baxy_mind import llm
from baxy_mind.semantic import reading
from baxy_mind.semantic.temporal import countdown_target

_violates = llm._shaped_conversation_answer_violates_contract

# ------------------------------------------------------------------ identity: one of his facts, never a bare «no info»


@pytest.mark.parametrize(
    ("request_text", "reply"),
    [
        ("¿quién te programó?", "No tengo información sobre quién me programó."),
        ("who built you?", "I don't have information about who built you."),
        ("quién te hizo, bro", "No sé quién me hizo."),
        ("who's your creator", "I don't know who my creator is."),
    ],
)
def test_a_bare_no_information_identity_answer_is_rejected(request_text: str, reply: str) -> None:
    assert _violates(reply, request_text, "identity")


@pytest.mark.parametrize(
    ("request_text", "reply"),
    [
        ("¿quién te programó?", "Soy BAXY y vivo en este PC; quién me programó no lo sé."),
        ("who built you?", "I'm BAXY, a program that lives on this PC; I don't have who built me."),
        ("quién te hizo, bro", "No tengo ese dato: soy un programa que vive en este PC."),
        ("dime quién te creó", "Soy BAXY; no tengo el dato de quién me creó."),
    ],
)
def test_an_identity_answer_with_one_of_his_facts_passes(request_text: str, reply: str) -> None:
    assert not _violates(reply, request_text, "identity")


def test_the_identity_instructions_ask_for_one_of_his_facts_beside_the_missing_detail() -> None:
    prompt = llm.IDENTITY_PRESENTATION_PROMPT
    assert "say plainly you do not have that" in prompt
    assert "say who you are from these facts" in prompt


# ------------------------------------------------------------------ the time left to a clock time is a countdown


@pytest.mark.parametrize(
    ("text", "target"),
    [
        ("cuántas horas faltan para las 8 de la noche", "20:00"),
        ("cuantos minutos quedan pa las 3", "03:00"),
        ("qué tanto falta para que sean las once", "11:00"),
        ("cuánto rato falta hasta las 10 y media", "10:30"),
        ("how many minutes until 5 pm", "17:00"),
        ("how much time is left till noon", "12:00"),
        ("how long do we have until six o'clock", "06:00"),
        ("how many hours to go until midnight", "00:00"),
        ("oye, cuánto tiempo queda para las siete de la tarde?", "19:00"),
    ],
)
def test_the_time_left_to_a_clock_time_is_a_countdown(text: str, target: str) -> None:
    assert countdown_target(text) == target


@pytest.mark.parametrize(
    "text",
    [
        "cuánto falta para mi cumpleaños",
        "cuánto queda de batería",
        "how long until christmas",
        "cuánto rato queda de película",
        "cuántos minutos quedan en el temporizador",
        "how many minutes are left in the game",
    ],
)
def test_time_left_of_something_else_is_not_a_clock_countdown(text: str) -> None:
    assert countdown_target(text) is None


@pytest.mark.parametrize(
    "text", ["¿cuánto rato queda para las nueve?", "how many minutes until 4 pm", "cuántas horas faltan pa las 11"],
)
def test_a_countdown_is_read_on_the_clock_not_searched(text: str) -> None:
    got = reading.read(text, available_operations=("system.time", "web.search"))
    assert got.effects is not None and got.effects.operations == ("system.time",)
