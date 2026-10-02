"""Tanda 1 (2026-09-23): what BAXY says he does not know about the public world is looked up.

00_IDENTIDAD: «si no sabe algo, lo busca». «¿Conoces el lenguaje de programación Monkey C?» came back as
«No, no conozco…» with web.search served. The person's own things, BAXY himself and what he can do are
never searched, and a knowing answer stays an answer.
"""

from __future__ import annotations

import pytest

from baxy_mind.__main__ import _prepare_turn_result
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.decider import ContextDecision
from test_c03_pointless_questions import _tool


class _KnowledgeLlm:
    def __init__(self, reply: str) -> None:
        self.reply = reply

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "mode": "conversation", "operation": None, "question": "", "conversation_kind": "knowledge",
            "effect_count": "zero", "effect_operations": [], "effect_verification": "not_applicable",
            "response_language": "es",
        }

    @staticmethod
    def decide_in_context(text: str, *_args: object, **_kwargs: object) -> ContextDecision:
        # M123 (D58): a stable reading that waits for the contextual decider («¿qué es el zorbing?») is kept when it
        # talks.
        return ContextDecision(request=text, decision="talk", operations=(), question="")

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        return self.reply, []

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


def _turn(text: str, reply: str) -> dict[str, object]:
    tools = {"web.search": _tool("web.search", required=("query",))}
    return _prepare_turn_result(
        {"id": "turn-unknown", "text": text},
        llm=_KnowledgeLlm(reply),
        planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    ("text", "reply"),
    [
        ("¿qué es el zorbing?", "No tengo información sobre el zorbing."),
        ("what is a bogwoppit", "I don't know what a bogwoppit is."),
    ],
)
def test_what_baxy_does_not_know_is_looked_up(text: str, reply: str) -> None:
    result = _turn(text, reply)

    assert result["kind"] == "action"
    assert result["operation"] == "web.search"
    assert result["reply"] == ""


@pytest.mark.parametrize(
    ("text", "reply"),
    [
        # BAXY himself is answered as BAXY.
        ("¿quién eres?", "No sé muy bien cómo definirme, soy BAXY."),
        # A knowing answer stays an answer.
        ("¿qué es una silla?", "Una silla es un mueble para sentarse."),
    ],
)
def test_own_things_identity_and_known_answers_are_not_searched(text: str, reply: str) -> None:
    result = _turn(text, reply)

    assert result["kind"] == "conversation"
    assert result["effectOperations"] == []


# Tanda 4e: «oye compárteme algún chiste para hacerme feliz» came back from joke sites. Content asked for is written;
# a draft that happens to say «no sé» is not a question about the public world.
@pytest.mark.parametrize(
    ("text", "reply"),
    [
        ("cuéntame una historia de piratas", "No conozco esa historia, pero te invento una."),
    ],
)
def test_written_content_is_never_looked_up(text: str, reply: str) -> None:
    result = _turn(text, reply)

    assert result["kind"] == "conversation"
    assert result.get("operation") != "web.search"
