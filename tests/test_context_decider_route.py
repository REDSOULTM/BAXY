"""Fase 3.5b (D18, M11, M13): the contextual decider decides every turn no reader proves.

The readers still decide what they prove on a first message and what the conversation readers keep; the
rest is the decider's, with the whole conversation in front of it. Its restatement is what the shell plans
and confirms; the reply language comes from the person's own words; talk and limits carry no request to
resume; a limit whose words the readers prove once they stand in their canonical surface is that request.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.decider import ContextDecision
from test_c03_pointless_questions import _NoEvidence

OPERATIONS = ("media.control", "media.play.query", "audio.mute", "web.search", "app.open", "system.time")


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


class _Decider:
    """A contextual decider that answers one scripted decision and records what it was asked."""

    def __init__(self, decision: ContextDecision, *, clarification: str = "¿Qué quieres que haga?") -> None:
        self.decision = decision
        self.clarification = clarification
        self.asked: list[str] = []
        self.chats: list[object] = []

    def decide_in_context(self, text: str, history: object, tools: object, **_kwargs: object) -> ContextDecision:
        self.asked.append(text)
        return self.decision

    def chat(self, *_args: object, conversation_kind: object = None, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats.append(conversation_kind)
        return ("Eso no lo hago." if conversation_kind == "unsupported" else "Setenta años, más o menos."), []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        return self.clarification

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"


def _turn(text: str, llm: _Decider, history: list[dict[str, str]] | None = None) -> dict[str, object]:
    tools = {name: _tool(name) for name in OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "turn-context-decider", "text": text, "history": [*(history or []), {"role": "user", "content": text}]},
        llm=llm,
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


def test_an_unproved_request_is_the_deciders_and_its_restatement_is_planned() -> None:
    llm = _Decider(ContextDecision("Reproducir la última canción que estaba sonando", "action", ("media.control",), ""))

    result = _turn("repeat the last song again", llm)

    assert llm.asked == ["repeat the last song again"]
    assert result["kind"] == "action"
    assert result["operation"] == "media.control"
    assert result["objective"] == "Reproducir la última canción que estaba sonando"
    # The decider restated an English request in Spanish; the reply keeps the person's language.
    assert result["responseLanguage"] == "en"


def test_two_operations_are_one_plan() -> None:
    llm = _Decider(ContextDecision("Abre Spotify y pon música tranquila", "action", ("app.open", "media.play.query"), ""))

    result = _turn("abrí spoti y poné algo tranqui", llm)

    assert result["kind"] == "plan"
    assert result["effectOperations"] == ["app.open", "media.play.query"]


def test_a_question_that_is_not_one_bounded_question_is_formulated_again() -> None:
    llm = _Decider(ContextDecision("Crear una lista", "clarify", (), "¿Qué lista? ¿Con qué cosas?"))

    result = _turn("crear una nueva lista de", llm)

    assert result["kind"] == "clarify"
    assert result["question"] == "¿Qué quieres que haga?"


def test_talk_is_answered_and_carries_no_request_to_resume() -> None:
    llm = _Decider(ContextDecision("¿Cuántos años vive un perro?", "talk", (), ""))

    result = _turn("¿cuántos años vive un perro?", llm)

    assert result["kind"] == "conversation"
    assert result["conversationKind"] == "knowledge"
    assert result["reply"] == "Setenta años, más o menos."
    assert "objective" not in result


def test_a_limit_the_readers_prove_in_its_canonical_surface_is_that_request() -> None:
    llm = _Decider(ContextDecision("Pausa el speaker.", "limit", (), ""))

    result = _turn("Pausa el speaker.", llm)

    assert result["kind"] == "action"
    assert result["operation"] == "media.control"
    assert llm.chats == []


def test_an_honest_limit_stays_a_limit_without_a_request_to_resume() -> None:
    llm = _Decider(ContextDecision("Pedir un taxi", "limit", (), ""))

    result = _turn("me gustaría que pidas un taxi", llm)

    assert result["kind"] == "conversation"
    assert result["conversationKind"] == "unsupported"
    assert "objective" not in result
    assert llm.chats == ["unsupported"]


@pytest.mark.parametrize("text", ["gracias", "muchas gracias!"])
def test_what_a_conversation_reader_keeps_never_reaches_the_decider(text: str) -> None:
    class NoDecider(_Decider):
        def decide_in_context(self, *_args: object, **_kwargs: object) -> ContextDecision:
            raise AssertionError("a turn the conversation readers keep is not the decider's")

    llm = NoDecider(ContextDecision("", "talk", (), ""))
    history = [{"role": "user", "content": "silencia el audio"}, {"role": "assistant", "content": "Listo, silenciado."}]

    result = _turn(text, llm, history)

    assert result["kind"] == "conversation"


def test_a_pointer_with_no_antecedent_is_asked_never_filled_by_the_model() -> None:
    # cien-104 «ábreme eso porfa» after the time: «Abre el navegador» opened a browser nobody named (M19).
    llm = _Decider(ContextDecision("Abre el navegador.", "action", ("app.open",), ""), clarification="¿Qué quieres que abra?")
    history = [{"role": "user", "content": "¿qué hora es?"}, {"role": "assistant", "content": "Son las 17:26."}]

    result = _turn("ábreme eso porfa", llm, history)

    assert result["kind"] == "clarify"
    assert result["effectOperations"] == []
    assert result["question"] == "¿Qué quieres que abra?"


def test_a_pointer_whose_antecedent_was_said_is_that_request() -> None:
    llm = _Decider(ContextDecision("Abre Spotify.", "action", ("app.open",), ""))
    history = [{"role": "user", "content": "¿está instalado Spotify?"}, {"role": "assistant", "content": "Sí, Spotify está instalado."}]

    result = _turn("ábreme eso porfa", llm, history)

    assert result["kind"] == "action"
    assert result["operation"] == "app.open"


def test_a_question_in_another_language_is_formulated_again_in_the_persons() -> None:
    # cien-104 «open that» was asked «¿Qué página web quieres que abra?».
    llm = _Decider(ContextDecision("Abre eso.", "clarify", (), "¿Qué quieres que abra?"), clarification="What should I open?")
    history = [{"role": "user", "content": "¿qué hora es?"}, {"role": "assistant", "content": "Son las 17:25."}]

    result = _turn("open that", llm, history)

    assert result["kind"] == "clarify"
    assert result["question"] == "What should I open?"


def test_a_question_about_an_unreachable_place_is_its_limit() -> None:
    # cien-105/106 «post a letter to Eris» → «What should the letter say?», a question about what cannot be done.
    llm = _Decider(ContextDecision("Enviar una carta a Eris", "clarify", (), "What should the letter say?"))

    result = _turn("post a letter to Eris", llm)

    assert result["kind"] == "conversation"
    assert result["conversationKind"] == "unsupported"
    assert llm.chats == ["unsupported"]
