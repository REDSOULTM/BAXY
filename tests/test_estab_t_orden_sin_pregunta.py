"""Estabilización T (tandas estab 1 y 2 sobre el mismo código, juicio estab_tandas_12): t4-c03 t4 «ya cierra discord» and
t2-c03 t2 «ya cierra configuracion que me esta laggeando el valorant» were asked back in all four runs. The decider chose
clarify with no valid question of its own; the recovery (the last barrier, which by its prompt supposes no action) wrote
a different question each run, and the said-back reading of ronda 24 read that one. Only the decider's own question says
what it doubts: when it asks nothing, the complete order in the person's words is done (the kernel still asks, bound to
the invocation, what its policy confirms: a close with unsaved work). Contracasos: a pointer, two orders, an order taken
back, no order, a missing amount, what reaches a person, and a real question of the decider's own keep asking.
"""

from __future__ import annotations

import pytest

from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind import turn_decide


class _Decider:
    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision
        self.recoveries = 0

    def decide_in_context(self, *_args: object, **_kwargs: object) -> ContextDecision:
        return self.decision

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        return "", []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        self.recoveries += 1
        return "¿Quieres que te avise cuando Discord se cierre?"

    def formulate_explicit_clarification_question(self, *_args: object, **_kwargs: object) -> str:
        return "¿Cuánto lo subo?"

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


def _tool(name: str, risk: str, properties: dict | None = None, required: list | None = None) -> dict:
    schema = {"type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False}
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": risk, "parameters": schema}}


# Risks and the volume schema are the real catalog's (src/Baxy.Kernel/Operations/ProductCatalog.cs).
_TOOLS = {
    "app.close": _tool("app.close", "work_loss"),
    "app.open": _tool("app.open", "low_reversible"),
    "window.active": _tool("window.active", "read_only"),
    "message.send": _tool("message.send", "external_communication"),
    "audio.volume.adjust": _tool(
        "audio.volume.adjust", "low_reversible",
        {"amount": {"type": "integer", "minimum": 1, "maximum": 100},
         "direction": {"type": "string", "enum": ["down", "up"]}},
        ["amount", "direction"],
    ),
}
_APPLICATIONS = ("Discord", "Spotify", "Configuración")
# t4-c03 before turn 4: Discord opened, a message sent, an alarm set.
_HISTORY = [
    {"role": "user", "content": "abre discord porfa"},
    {"role": "assistant", "content": "Abrí la aplicación «Discord»."},
    {"role": "user", "content": "y ponme una alarma a las 8:50 pa acordarme"},
    {"role": "assistant", "content": "He programado la alarma para las 08:50 con el título \"Acordarme para jugar\"."},
]


def _route(text: str, question: str = "", history: list[dict] | None = None) -> tuple[dict, _Decider]:
    llm = _Decider(ContextDecision(text, "clarify", (), question))
    before = _HISTORY if history is None else history
    result = turn_decide._prepare_turn_result(
        {"id": "turn-estab-t", "text": text, "history": [*before, {"role": "user", "content": text}]},
        llm=llm,
        planner_catalog=PlannerCatalog(list(_TOOLS.values())),
        encoder=lambda _texts: (),
        tool_by_name=_TOOLS,
        application_names=_APPLICATIONS,
    )
    return result, llm


@pytest.mark.parametrize(
    "text",
    [
        "ya cierra discord",
        "ya cierra configuracion que me esta laggeando el valorant",
        "cierra discord porque me laggea",
        "close discord",
    ],
)
def test_a_complete_order_the_decider_asked_nothing_about_is_done(text: str) -> None:
    result, llm = _route(text)

    assert result["kind"] == "action"
    assert result["operation"] == "app.close"
    assert llm.recoveries == 0


@pytest.mark.parametrize(
    "text",
    [
        # Two orders: the decider's doubt may be the split.
        "cierra discord y spotify",
        # Taken back, or no order at all.
        "ya cierra discord, bueno no, mejor no",
        "cierra discord pero no todavía",
        "close discord but not yet",
        "¿y si cierro discord?",
        "should I close discord?",
        # A required value missing (owner rule H0027: no default step).
        "aumenta el volumen",
        # What reaches a person keeps its question.
        "mandale a Ron92 que ya llegué",
    ],
)
def test_what_is_no_complete_order_keeps_asking(text: str) -> None:
    result, llm = _route(text)

    assert result["kind"] == "clarify"
    assert result.get("operation") is None
    assert not result.get("effectOperations")
    assert llm.recoveries == 1


# Estabilización X2: these three pointers were contracases here with t4-c03's history, where Discord was opened two turns
# before; the pointer now points at the application the conversation is in (``conversation_application``), as M96's
# did at the one just opened. A pointer with no application in the conversation is still never filled (M19/M118).
_POINTERS = ("ciérralo", "cierra eso", "close it")
_NO_APPLICATION = [
    {"role": "user", "content": "ponme una alarma a las 8:50 pa acordarme"},
    {"role": "assistant", "content": "He programado la alarma para las 08:50 con el título \"Acordarme para jugar\"."},
]


@pytest.mark.parametrize("text", _POINTERS)
def test_a_pointer_with_no_application_in_the_conversation_keeps_asking(text: str) -> None:
    result, llm = _route(text, history=_NO_APPLICATION)

    assert result["kind"] == "clarify"
    assert result.get("operation") is None
    assert not result.get("effectOperations")
    assert llm.recoveries == 1


@pytest.mark.parametrize("text", _POINTERS)
def test_a_pointer_closes_the_application_the_conversation_opened(text: str) -> None:
    result, llm = _route(text)

    assert (result["kind"], result["operation"]) == ("action", "app.close")
    assert "discord" in str(result["objective"]).lower()
    assert llm.recoveries == 0


def test_a_real_question_of_the_deciders_own_is_asked() -> None:
    question = "¿Cuál de las dos ventanas de Discord cierro?"
    result, llm = _route("ya cierra discord", question)

    assert result["kind"] == "clarify"
    assert result["question"] == question
    assert llm.recoveries == 0
