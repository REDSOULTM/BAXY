"""M131 (D58, 2026-10-02): the first-turn readers that decide without the decider, by their ledger.

Ledger of every branch of ``explicit_effects`` / ``explicit_conversation`` (and recovery) that answers a first message
before the contextual decider, against the isolated decider full3: reserve (2 757 first messages, v1 and v2 labels),
DEV-D and DEV-F (offline, with the decider's recorded decisions, and the App's v4k runs), DEV-C where the mind runs
recorded a decision; DEV-E only in aggregate.

1. A first message read as a plain web search waits for the decider. Where it chose a typed read that serves the
   question more specifically (the day's headlines, the weather with its later days, what this PC plays), both were
   right by the labels and the decider's is the turn; its talk, question, limit or a personal read keep the search (the
   decider's errors the search fixed). ``system.time`` is not one of them: it reads only today's clock, and the weekday
   of another day of the calendar is looked up.
2. The sister-operation branches with fixes keep reading first: their choice is the reviewed product mapping (music
   with no provider plays on YouTube, MUSIC1559; «recuérdame…» is a reminder, H0102/H0222/H0259; «… en Spotify» is
   the Spotify search, H0163/H0237) or the more specific operation for the words said.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.web import search_has_typed_reads, typed_read_over_search


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

    def public_lookup_requested(self, _text):
        return False

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

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
    "media.play.exact", "media.play.query", "media.play.youtube", "media.status", "memory.recall",
    "notification.schedule", "reminder.create", "system.time", "weather.current", "web.news.headlines", "web.search",
)


def _tool(name: str) -> dict:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": "read_only", "parameters": schema}}


def _turn(text: str, model: _Decider) -> dict:
    tools = {name: _tool(name) for name in _OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "m131", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (), tool_by_name=tools,
        dialogue_state=DialogueState(),
    )


def _decided(text: str, decision: str, operations: tuple[str, ...] = ()) -> _Decider:
    return _Decider(ContextDecision(request=text, decision=decision, operations=operations, question=""))


# ------------------------------------------------------------------ 1. a plain web search waits for the decider


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        # DEV-D D-s021, reserve es2098: the world's news are the day's headlines.
        ("me gustaría saber qué está pasando por el mundo", "web.news.headlines"),
        # DEV-F F-s031: the coming Sunday's rain is the weather read with its later days.
        ("va a llover en Tandil el domingo? queremos subir a la Movediza con los chicos y no quiero mojarme",
         "weather.current"),
        # reserve es6134: the song playing now is what this PC plays.
        ("averigua que canción es esta y dime el nombre", "media.status"),
    ],
)
def test_the_deciders_more_specific_typed_read_is_the_turn(text: str, operation: str) -> None:
    model = _decided(text, "action", (operation,))

    result = _turn(text, model)

    assert model.decisions == 1
    assert result["kind"] == "action" and result["effectOperations"] == [operation]
    # the readers read it as a plain web search: with the decider talking, the search stands
    talking = _decided(text, "talk")
    assert _turn(text, talking)["effectOperations"] == ["web.search"] and talking.decisions == 1


@pytest.mark.parametrize(
    ("text", "decision", "operations"),
    [
        # reserve es12289 / es5324: the decider talked where the live lookup was right.
        ("hay un atasco en mi ruta", "talk", ()),
        ("hola tenéis entrega a domicilio", "talk", ()),
        # reserve es15020: a person's age is no memory of the user's.
        ("cuántos años tiene santiago segura", "action", ("memory.recall",)),
        # reserve es310: the weekday of another day is looked up; this PC's clock reads only today.
        ("en que día cae nochevieja este año", "action", ("system.time",)),
    ],
)
def test_any_other_decision_keeps_the_search(text: str, decision: str, operations: tuple[str, ...]) -> None:
    model = _decided(text, decision, operations)

    result = _turn(text, model)

    assert model.decisions == 1
    assert result["kind"] == "action" and result["effectOperations"] == ["web.search"]


def test_only_one_typed_read_serves_better_than_a_search() -> None:
    assert typed_read_over_search(("web.news.headlines",))
    assert typed_read_over_search(["weather.current"])
    assert typed_read_over_search(("media.status",))
    assert not typed_read_over_search(("system.time",))
    assert not typed_read_over_search(("memory.recall",))
    assert not typed_read_over_search(("web.search",))
    assert not typed_read_over_search(("weather.current", "web.news.headlines"))
    assert not typed_read_over_search(())


def test_a_catalog_with_no_typed_read_never_waits_for_the_decider() -> None:
    assert search_has_typed_reads(("web.search", "media.status"))
    assert not search_has_typed_reads(("web.search", "system.time"))
    text = "me gustaría saber qué está pasando por el mundo"
    tool = _tool("web.search")
    model = _Decider()

    result = sidecar._prepare_turn_result(
        {"id": "m131", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog([tool]), encoder=lambda _t: (), tool_by_name={"web.search": tool},
        dialogue_state=DialogueState(),
    )

    assert model.decisions == 0
    assert result["kind"] == "action" and result["effectOperations"] == ["web.search"]


# ------------------------------------------------------------------ 2. the sister branches with fixes read first


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        # MUSIC1559 (reviewed H0068, H0213): music named with no provider plays on YouTube.
        ("pon una cancion de michael jackson", "media.play.youtube"),
        # H0237: «… en Spotify» is the Spotify search.
        ("pon michael jackson en spotify", "media.play.query"),
        # H0222: «recuérdame …» with its moment is a reminder.
        ("recuérdame llamar al dentista a las 5", "reminder.create"),
        # a typed weather read never waits: it is the more specific read itself.
        ("qué clima hace hoy en Buenos Aires", "weather.current"),
    ],
)
def test_the_sister_branches_that_fix_the_decider_still_read_first(text: str, operation: str) -> None:
    model = _Decider()

    result = _turn(text, model)

    assert model.decisions == 0
    assert result["kind"] == "action" and result["effectOperations"] == [operation]
