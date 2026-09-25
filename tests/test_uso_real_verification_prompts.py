"""Uso real final verification (2026-09-25): replies the concision rules (defe564f) and the public lookup (fa327140)
broke against the 3.5 close (cien-102, owner script, layers A/C).

1. Small talk («Me gusta como se desenvuelven», «mmm», «Bien, bien.») was answered with a question and became a
   clarification: the concise prompt told the model to «answer exactly what is asked», and a comment asks nothing.
   The prompt now says how small talk is answered. Owner: llm.SYSTEM_PROMPT.
2. English messages («my name is Alex», «order soup on Vesta») were answered in Spanish, failed their language
   contract and fell into recovery: the longer Spanish prompts outweighed the language policy for the 4B model. A
   reply in English is written under the same prompts in English. Owner: llm.SYSTEM_PROMPT_EN,
   llm.UNSUPPORTED_PRESENTATION_PROMPT_EN.
3. «rent a studio on Haumea» was looked up (a page about studios in Doha): what no operation of this PC reaches is
   a boundary, never a lookup. Owner: __main__._public_lookup_applies (semantic.patterns.out_of_world_request).
4. «describe yourself briefly» was answered in Spanish: its English words (a reflexive, an adverb) were no
   evidence, and no evidence reads as Spanish. Owner: semantic/request._EN_WORDS.
5. «Interesante, ¿qué tipo de cosas te gustaría crear?» was taken for an offer (c8670b0b): a question that starts
   with a question word asks about the person. Owner: llm.visible_reply_offers_more.
6. «Me gusta como se desenvuelven» → «…el modo en que se desarrollan…» was rejected for not repeating the word: a
   taste said as a manner names no thing. Owner: llm._shaped_conversation_answer_violates_contract (preference_ack).
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.semantic.request import read_request
from test_concision_2026_09_24 import ChatRecorder


def test_the_prompt_says_small_talk_is_answered_not_questioned() -> None:
    assert "A la charla" in llm.SYSTEM_PROMPT and "sin pedirle que aclare nada" in llm.SYSTEM_PROMPT
    assert "To small talk" in llm.SYSTEM_PROMPT_EN and "without asking them to clarify" in llm.SYSTEM_PROMPT_EN


@pytest.mark.parametrize(
    ("language", "prompt", "other"),
    [("en", llm.SYSTEM_PROMPT_EN, llm.SYSTEM_PROMPT), ("es", llm.SYSTEM_PROMPT, llm.SYSTEM_PROMPT_EN)],
)
def test_a_reply_is_written_under_the_prompt_in_its_language(language: str, prompt: str, other: str) -> None:
    client = ChatRecorder([("Nice to meet you, Alex." if language == "en" else "Encantado, Alex.", "stop")])
    client.chat("my name is Alex" if language == "en" else "me llamo Alex", history=[],
                conversation_kind="knowledge", response_language=language)
    system = client.payloads[0]["messages"][0]["content"]
    assert system.startswith(prompt)
    assert other not in system


@pytest.mark.parametrize(
    ("language", "prompt"),
    [("en", llm.UNSUPPORTED_PRESENTATION_PROMPT_EN), ("es", llm.UNSUPPORTED_PRESENTATION_PROMPT)],
)
def test_a_limit_is_written_under_the_prompt_in_its_language(language: str, prompt: str) -> None:
    reply = "I don't do that: soup deliveries to Vesta are out of my reach." if language == "en" else (
        "Eso no lo hago: la sopa a Vesta no la pido yo."
    )
    client = ChatRecorder([(reply, "stop")])
    client.chat("order soup on Vesta" if language == "en" else "pide sopa en Vesta", history=[],
                conversation_kind="unsupported", response_language=language)
    assert client.payloads[0]["messages"][0]["content"].startswith(prompt)


class _AlwaysPublic:
    def public_lookup_requested(self, text: str) -> bool:
        return True


class _Catalog(dict):
    pass


@pytest.mark.parametrize(
    "text", ["rent a studio on Haumea", "reserve a cabin on Triton", "búscame un depto en Ceres", "compra pan en Eris"],
)
def test_what_no_operation_reaches_is_never_looked_up(text: str) -> None:
    catalog = _Catalog({"web.search": object()})
    assert not sidecar._public_lookup_applies(text, text, _AlwaysPublic(), ("web.search",), catalog)


def test_a_public_question_is_still_looked_up() -> None:
    catalog = _Catalog({"web.search": object()})
    assert sidecar._public_lookup_applies(
        "who directed Oppenheimer", "who directed Oppenheimer", _AlwaysPublic(), ("web.search",), catalog,
    )


@pytest.mark.parametrize("text", ["describe yourself briefly", "introduce yourself", "describe yourself quickly"])
def test_english_reflexives_and_adverbs_are_english_evidence(text: str) -> None:
    assert read_request(text).language == "en"


@pytest.mark.parametrize("text", ["descríbete brevemente", "preséntate", "describe tu casa"])
def test_spanish_stays_spanish(text: str) -> None:
    assert read_request(text).language == "es"


@pytest.mark.parametrize(
    "reply",
    ["Interesante, ¿qué tipo de cosas te gustaría crear?", "Nice! What would you like to build?",
     "¿Y qué te gustaría hacer hoy?", "Qué buena. ¿Cómo te fue?"],
)
def test_a_question_about_the_person_is_no_offer(reply: str) -> None:
    assert not llm.visible_reply_offers_more(reply)


@pytest.mark.parametrize(
    "reply",
    ["Claro. ¿Quieres que hablemos de algo específico?", "Would you like me to play something?",
     "¿Te gustaría que te cuente un chiste?", "Sure. Do you want me to open it?"],
)
def test_an_offer_is_still_an_offer(reply: str) -> None:
    assert llm.visible_reply_offers_more(reply)


@pytest.mark.parametrize(
    ("request_text", "reply", "violates"),
    [
        ("Me gusta como se desenvuelven", "Interesante, el modo en que se desarrollan te llama la atención.", False),
        ("I love how they talk", "Their way of speaking really draws you in.", False),
        ("Me gusta el café", "Qué bien que disfrutes una buena taza.", True),
        ("Me gusta el café", "Qué bien que te guste el café.", False),
        ("Me gusta como se desenvuelven", "A mí también me gusta.", True),
    ],
)
def test_a_taste_said_as_a_manner_is_acknowledged_in_other_words(request_text: str, reply: str, violates: bool) -> None:
    assert llm._shaped_conversation_answer_violates_contract(reply, request_text, "preference_ack") is violates
