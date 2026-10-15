"""M126 (D58, 2026-10-02): readers that answered first where the isolated decider was right, narrowed by their ledger.

Ledger against the isolated decider (full3) on the reserve (2 757 first messages, v1 and v2 labels), DEV-D and DEV-F
(offline, with the decider's recorded decisions); DEV-E only in aggregate.

1. Explicit clarifications whose question never fixed the decider and broke it where it was right (the meeting's
   start, «necesito hacer algo hoy», where to resume a book) wait for the decider; what it decides is the turn. The
   rest keep asking first (the hour without its part of the day, asked by reviewed literals until D61, is no longer
   asked: tests/test_c03_m129_d61_hora.py).
2. A live weather question is the typed weather read (REOPEN1993 group W), as the decider reads it: the asking frame
   stripped («tiempo ahora») no longer hid it, «what is the current temperature» / «the ten day forecast» are read, and
   the public live lookup no longer takes a question the reading gate reads as the weather. A year said in words is no
   live read: the decider decides it.
"""

from __future__ import annotations

import pytest

from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.patterns import clarification_awaits_decider, resolve_explicit_clarification_intent
from baxy_mind.semantic.system import _weather_read_intent
from baxy_mind import turn_decide


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision | None = None) -> None:
        self.decision = decision
        self.decisions = 0

    def decide_in_context(self, *_a, **_k):
        self.decisions += 1
        if self.decision is None:
            raise AssertionError("the decider was not to be asked")
        return self.decision

    def formulate_explicit_clarification_question(self, *_a, **_k):
        return "¿A qué hora?"

    def public_lookup_requested(self, _text):
        return False

    def _verify_semantic_effect_shape(self, _text):
        return "no_effect", "zero"

    def chat(self, *_a, **_k):
        return "Respuesta.", []

    def prepare_chat(self, *_a, **_k):
        return None

    def detect_response_language(self, _text):
        return "es"

    def consume_deferred_response_language(self, _text):
        return True, None

    def retire_deferred_response_language(self, _text):
        return None

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


_OPERATIONS = (
    "calendar.event.create", "calendar.event.list", "media.control", "notification.schedule", "reminder.create",
    "task.list", "weather.current", "web.search",
)


def _tool(name: str) -> dict:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": "read_only", "parameters": schema}}


def _turn(text: str, model: _Decider) -> dict:
    tools = {name: _tool(name) for name in _OPERATIONS}
    return turn_decide._prepare_turn_result(
        {"id": "m126", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (), tool_by_name=tools,
        dialogue_state=DialogueState(),
    )


# ------------------------------------------------------------------ 1. clarifications that wait for the decider


@pytest.mark.parametrize(
    ("text", "operations"),
    [
        ("quiero hacer algo mañana", ("task.list",)),
        ("i want a meeting until five o'clock", ("calendar.event.create",)),
    ],
)
def test_a_question_that_never_fixed_the_decider_waits_for_it(text: str, operations: tuple[str, ...]) -> None:
    asked = resolve_explicit_clarification_intent(text, _OPERATIONS)
    assert asked is not None and clarification_awaits_decider(asked.missing_fields)
    model = _Decider(ContextDecision(request=text, decision="action", operations=operations, question=""))

    result = _turn(text, model)

    assert model.decisions == 1
    assert result["kind"] == "action" and tuple(result["effectOperations"]) == operations


def test_resuming_a_book_by_where_it_stopped_is_the_deciders_limit() -> None:
    text = "reanuda el principito por donde paré la otra vez"
    asked = resolve_explicit_clarification_intent(text, _OPERATIONS)
    assert asked is not None and asked.missing_fields == ("source_app",)
    model = _Decider(ContextDecision(request=text, decision="limit", operations=(), question=""))

    result = _turn(text, model)

    assert model.decisions == 1
    assert result["kind"] == "conversation" and result["conversationKind"] == "unsupported"


@pytest.mark.parametrize(
    "text",
    [
        # The hour without its part of the day («recuérdame la junta de mañana a las cinco») was here until D61 (owner,
        # 2026-10-02): it is no longer asked at all (tests/test_c03_m129_d61_hora.py).
        # A repetition no alarm or reminder holds: the question is the honest limit.
        "please set a team meeting at ten a. m. for every tuesday in may",
    ],
)
def test_the_questions_with_a_reason_to_ask_first_still_ask_without_the_decider(text: str) -> None:
    asked = resolve_explicit_clarification_intent(text, _OPERATIONS)
    assert asked is not None and not clarification_awaits_decider(asked.missing_fields)
    model = _Decider()

    result = _turn(text, model)

    assert model.decisions == 0
    assert result["kind"] == "clarify"


# ------------------------------------------------------------------ 2. a live weather question is the weather read


@pytest.mark.parametrize(
    "text",
    [
        "qué tiempo hace ahora mismo",
        "cómo está el tiempo este sábado",
        "qué tiempo hará el próximo jueves",
        "what is the current temperature outside",
        "what is the five day forecast",
    ],
)
def test_a_live_weather_question_is_the_weather_read(text: str) -> None:
    read = _weather_read_intent(text, _OPERATIONS)
    assert read is not None and read.operations == ("weather.current",)


@pytest.mark.parametrize(
    "text",
    [
        "qué tiempo hizo el diez de mayo de dos mil quince",
        "what is a forecast",
        "what is the history of weather forecasting",
        "cuánto tiempo hace que no llueve",
    ],
)
def test_what_is_no_live_weather_read_stays_out(text: str) -> None:
    assert _weather_read_intent(text, _OPERATIONS) is None


def test_the_public_lookup_never_takes_a_question_the_reading_gate_reads_as_the_weather() -> None:
    text = "Oye, ¿qué tiempo va a hacer el domingo en Curicó? Que me voy a la playa con los cabros"
    model = _Decider()

    result = _turn(text, model)

    assert model.decisions == 0
    assert result["kind"] == "action" and result["effectOperations"] == ["weather.current"]
