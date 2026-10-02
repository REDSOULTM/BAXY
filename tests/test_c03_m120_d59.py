"""M120: owner decisions D59 (2026-10-02) items 1, 3, 6 and 7, on the mind's side.

1. Messaging adapts to the PC: a closed WhatsApp or Discord is opened by the provider before the draft
   (DesktopMessagingAdapter, M120ClienteCerradoTests). Here: the draft's final says the client was opened only when it
   was (``clientOpened``), and the two ways the open can end (not installed, not ready in time) have their facts.
3. «baja / sube / apaga / prende las luces» with no screen named is the house: a plain limit the model writes
   (semantic.system.physical_world_request); the screen's brightness only when the screen or its brightness is named.
6. «avísame cuando haya noticias de X» / «let me know when there's news about X»: no operation watches the news; the
   limit offers to search them now (semantic.web.asks_to_watch_the_news, the «news_watch_limit» shape).
7. A turn not understood with no valid question is asked with the person's own words
   (semantic.dialogue.words_floor_question), never a fixed «no pude entender».

Every phrasing below is our own.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider, web
from baxy_mind.semantic.conversation import _conversation_presentation_shape
from baxy_mind.semantic.dialogue import words_floor_question
from baxy_mind.semantic.patterns import known_unsupported_effect_request

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_concision_2026_09_24 import ChatRecorder  # noqa: E402

OPERATIONS = (
    "system.settings.adjust", "system.settings.set", "system.settings.status", "web.search", "web.news.headlines",
    "notification.schedule", "reminder.create", "message.draft", "app.open", "media.play.youtube",
)


class _Decider:
    """A contextual decider that decides what it is given; every reply it writes is counted."""

    def __init__(self, decision: str, operations: tuple[str, ...] = ()) -> None:  # noqa: D107
        self.decision = decision
        self.operations = operations
        self.chats = 0

    def decide_in_context(self, text: str, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        return decider.ContextDecision(request=text, decision=self.decision, operations=self.operations, question="")

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats += 1
        return "Eso no lo hago.", []

    @staticmethod
    def formulate_explicit_clarification_question(*_args: object, **_kwargs: object) -> str:
        return "¿Cuánto?"

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


def _turn(text: str, model: _Decider) -> dict[str, object]:
    tools = {name: _tool(name) for name in OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "m120", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


# ------------------------------------------------------------------ 1. the client opened for the draft


def _draft(opened: bool) -> dict:
    return {
        "kind": "operation", "operation": "message.draft", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"version": 1, "channel": "whatsapp", "displayName": "Tere", "text": "llego en diez",
                     "draftVisible": True, "sent": False, "clientOpened": opened, "evidenceHash": "ab12",
                     "authority": "desktop_client_composer_ocr_postread"},
    }


def test_a_client_opened_for_the_draft_is_told() -> None:
    payload = llm._compose_situation_payload(_draft(True), "es", "déjale escrito a Tere en whatsapp que llego en diez")
    assert payload["seen"]["clientOpened"] is True
    shape = llm._compose_shape_instruction(_draft(True), "es", "déjale escrito a Tere en whatsapp que llego en diez")
    assert "clientOpened is true" in shape


def test_the_final_that_says_the_client_was_opened_is_published() -> None:
    final = "Abrí WhatsApp y dejé escrito «llego en diez» en el chat con Tere, sin enviarlo."
    asked = "déjale escrito a Tere en whatsapp que llego en diez"
    assert llm.compose_visible_defect(final, "status", asked, {"situation": json.dumps(_draft(True))}) == ""


def test_a_client_already_open_is_no_news() -> None:
    payload = llm._compose_situation_payload(_draft(False), "en", "leave Tere a whatsapp saying I'm ten minutes out")
    assert "clientOpened" not in payload["seen"]
    shape = llm._compose_shape_instruction(_draft(False), "en", "leave Tere a whatsapp saying I'm ten minutes out")
    assert "clientOpened" not in shape


@pytest.mark.parametrize(
    ("code", "client"),
    [
        ("whatsapp_client_not_installed", "WhatsApp"),
        ("discord_client_not_installed", "Discord"),
        ("whatsapp_client_open_not_verified", "WhatsApp"),
        ("discord_client_open_not_verified", "Discord"),
    ],
)
def test_the_ways_the_open_can_end_have_their_fact(code: str, client: str) -> None:
    fact = llm._cause_in_prose(code, "es")
    assert client in fact and "_" not in fact


# ------------------------------------------------------------------ 3. the lights of the house


@pytest.mark.parametrize(
    "text",
    [
        "baja las luces",
        "sube las luces porfa",
        "apágame las luces",
        "prende la luz",
        "turn off the lights",
        "turn the lights down please",
        "enciende las lámparas",
    ],
)
def test_the_lights_with_no_screen_named_are_a_limit(text: str) -> None:
    assert known_unsupported_effect_request(text, OPERATIONS)
    # Even when the decider reads the screen's brightness, the turn is the limit the model writes.
    model = _Decider("action", ("system.settings.adjust",))
    result = _turn(text, model)
    assert result["kind"] == "conversation" and result["conversationKind"] == "unsupported"
    assert model.chats == 1


@pytest.mark.parametrize(
    "text",
    [
        "baja la luz de la pantalla",
        "sube el brillo de la pantalla",
        "baja el brillo al 30",
        "activa la luz nocturna",
        "turn on night light",
        "pon un video de luces de navidad",
        "pon luz natural",
    ],
)
def test_the_screen_and_its_light_are_not_the_house(text: str) -> None:
    assert not known_unsupported_effect_request(text, OPERATIONS)


# ------------------------------------------------------------------ 6. being told when there is news


WATCHES = [
    ("avísame cuando haya noticias de bitcoin", "bitcoin"),
    ("notifícame cuando salgan noticias sobre la huelga de puertos", "la huelga de puertos"),
    ("dime cuando haya noticias del partido de mañana", "partido de mañana"),
    ("mantenme al tanto de las noticias sobre el volcán", "el volcán"),
    ("let me know when there's news about the Artemis launch", "the Artemis launch"),
    ("tell me when there is news on the rail strike please", "the rail strike"),
    ("keep me posted on news about SpaceX", "SpaceX"),
]


@pytest.mark.parametrize(("text", "subject"), WATCHES)
def test_being_told_when_there_is_news_is_a_watch(text: str, subject: str) -> None:
    assert web.asks_to_watch_the_news(text)
    assert web.news_watch_subject(text) == subject
    assert known_unsupported_effect_request(text, OPERATIONS)


@pytest.mark.parametrize(
    "text",
    [
        "noticias de bitcoin",
        "dime si hay noticias de bitcoin",
        "what's the news about SpaceX",
        "avísame a las ocho para leer las noticias",
        "avísame en diez minutos para ver las noticias",
        "remind me in an hour to read the news",
    ],
)
def test_the_news_now_or_a_notice_at_a_time_is_no_watch(text: str) -> None:
    assert not web.asks_to_watch_the_news(text)


@pytest.mark.parametrize(
    ("decision", "operations"),
    [("action", ("notification.schedule",)), ("action", ("web.news.headlines",)), ("talk", ()), ("limit", ())],
)
@pytest.mark.parametrize("text", [text for text, _ in WATCHES])
def test_a_watch_is_the_limit_whatever_was_decided(text: str, decision: str, operations: tuple[str, ...]) -> None:
    model = _Decider(decision, operations)
    result = _turn(text, model)
    assert result["kind"] == "conversation" and result["conversationKind"] == "unsupported"
    assert not result.get("effectOperations")


@pytest.mark.parametrize("kind", ["unsupported", "knowledge", None])
def test_the_watch_limit_has_its_shape(kind: str | None) -> None:
    text = "avísame cuando haya noticias de bitcoin"
    assert _conversation_presentation_shape(text, conversation_kind=kind, has_history=False) == "news_watch_limit"
    assert json.loads(llm._shaped_presentation_text(text, "news_watch_limit", response_language="es")) == {
        "response_language": "es", "subject": "bitcoin",
    }


@pytest.mark.parametrize(
    ("text", "language", "reply"),
    [
        ("avísame cuando haya noticias de bitcoin", "es",
         "No estoy pendiente de las noticias ni aviso cuando salen. ¿Quieres que busque ahora las noticias de bitcoin?"),
        ("let me know when there's news about the Artemis launch", "en",
         "I don't keep watch on the news or tell you when it comes out. Want me to search the news about the Artemis "
         "launch now?"),
    ],
)
def test_the_limit_with_its_offer_is_published(text: str, language: str, reply: str) -> None:
    client = ChatRecorder([(reply, "stop")])
    answer, _ = client.chat(text, history=[], conversation_kind="unsupported", response_language=language)
    assert answer == reply
    assert client.payloads[0]["messages"][0]["content"] == llm.NEWS_WATCH_LIMIT_PRESENTATION_PROMPT


@pytest.mark.parametrize(
    "reply",
    [
        "Te avisaré cuando haya noticias de bitcoin.",  # a promise to watch
        "I'll let you know when there's news. Want me to search now?",  # a promise to watch, with the offer
        "No vigilo las noticias.",  # no offer
        "¿Quieres que busque las noticias de bitcoin?",  # no limit said
    ],
)
def test_a_promise_to_watch_or_a_missing_part_is_refused(reply: str) -> None:
    assert llm._shaped_conversation_answer_violates_contract(
        reply, "avísame cuando haya noticias de bitcoin", "news_watch_limit",
    )


# ------------------------------------------------------------------ 7. a turn not understood, asked with their words


@pytest.mark.parametrize(
    ("said", "language", "question"),
    [
        ("y si allá son las 10 de la mañana acá qué hora es", "es", '¿Qué quieres que haga con "si allá son las 10…"?'),
        ("oye baxy, lo del otro día por favor", "es", '¿Qué quieres que haga con "lo del otro día"?'),
        ("the purple one near the thing", "en", 'What should I do with "the purple one near the thing"?'),
        ("flip the wobbly gizmo sideways with the other gizmo", "en",
         'What should I do with "flip the wobbly gizmo sideways…"?'),
        ("¿?", "es", ""),
    ],
)
def test_the_question_is_built_with_the_persons_words(said: str, language: str, question: str) -> None:
    assert words_floor_question(said, language) == question


class _Silent:
    """A recovery whose model writes no valid question at all."""

    def __init__(self) -> None:  # noqa: D107
        self.asked: list[str] = []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        return "No pude entender bien la solicitud."

    def compose_user_message(self, _text: str, intent: str, _facts: dict) -> str:
        self.asked.append(intent)
        return ""


@pytest.mark.parametrize(
    ("said", "question"),
    [
        ("lo de la gallina azul con el cosito", '¿Qué quieres que haga con "lo de la gallina azul…"?'),
        ("make the wobbly one quieter", 'What should I do with "make the wobbly one quieter"?'),
    ],
)
def test_the_recovery_asks_with_the_persons_words(said: str, question: str) -> None:
    composer = _Silent()
    result = sidecar._recover_failed_turn({"id": "m120", "text": said, "history": []}, composer,
                                          failure_kinds=("runtime", "runtime"))
    assert result["kind"] == "clarify" and result["question"] == question
    assert result["turn_recovery"] == "words_floor_question"
    assert not result["effectOperations"]


def test_a_recovered_limit_is_not_asked_about() -> None:
    composer = _Silent()
    result = sidecar._recover_failed_turn(
        {"id": "m120", "text": "send flowers to Deimos", "history": []}, composer,
        failure_kinds=("runtime", "runtime"),
    )
    assert result["kind"] == "conversation" and result["question"] == ""


def test_a_question_drafts_could_not_write_is_asked_with_their_words() -> None:
    client = ChatRecorder([("Here it is.", "stop")] * 4)
    final = client.compose_user_message(
        "the purple one near the thing", "clarification",
        {"situation": json.dumps({"kind": "clarification", "polarity": "pending", "cause": "ambiguous_request"})},
    )
    assert final == 'What should I do with "the purple one near the thing"?'
