"""Tandas 6c and 7 (2026-09-25, official window): single-message misses.

- «¿quién te desarrolló?» → «No tengo información sobre quién me desarrolló.»: the identity answer told nothing about
  him; it now carries one of his facts (his name or the PC he lives on) beside the detail he does not have.

The phrasings below are not the tandas': they are paraphrases (es/en/spanglish) the fixes do not name, with negative
controls.
"""

from __future__ import annotations

import pytest

from baxy_mind import llm

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
