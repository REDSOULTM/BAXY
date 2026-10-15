"""Ronda 19b, palanca «recordatorio-por-id» (estab2 hallazgos 12 y 18).

t1-c04-2 «no, mejor a las nueve y media», right after BAXY made the reminder «llamar al dentista» with
``reminder.create`` → «No he podido borrar ni programar el recordatorio porque la instrucción era ambigua.»: the move
resolved the reminder just made by its title alone (M173), and the store held other «llamar al dentista» made in other
conversations, so ``reminder.resolve.exact`` failed with ``reminder_ambiguous``.

The correction of what the turn before made is bound to the id its verified ``reminder.create`` returned
(``reminder.resolve.exact`` with ``reminderId`` and the title, declared in ``ProductCatalog``; the store resolves that
id and checks the title, ``R19bRecordatorioPorIdTests``). Counter-cases: no reminder made in this conversation gives no
id (the same-titled ones of other conversations are never in it); a deletion with no referent («borra el recordatorio»)
still asks which; a catalog without ``reminderId`` keeps the title alone. No test reads the machine's clock (M108).
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind import turn_decide
from baxy_mind import turn_followups
from baxy_mind import plan_shape


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


TITLE = {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True}
REMINDER_CREATE = _schema({
    "details": {"type": "string", "x-maxUtf8Bytes": 65536},
    "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
    "title": TITLE,
}, ["dueUtc", "title"])
# As ProductCatalog declares it since r19b: the verified id beside the title, which stays required.
REMINDER_RESOLVE = _schema({
    "includeDeleted": {"type": "boolean"},
    "reminderId": {"type": "string", "maxLength": 36, "x-nonWhitespace": True},
    "title": TITLE,
}, ["title"])
# The catalog before r19b: the title alone.
REMINDER_RESOLVE_TITLE_ONLY = _schema({"includeDeleted": {"type": "boolean"}, "title": TITLE}, ["title"])
REMINDER_DELETE = _schema({
    "expectedVersion": {"type": "integer", "minimum": 1},
    "reminderId": {"type": "string", "maxLength": 36, "x-nonWhitespace": True},
    "reviewLabel": TITLE,
}, ["expectedVersion", "reminderId", "reviewLabel"])
SCHEMAS = {
    "reminder.create": REMINDER_CREATE, "reminder.resolve.exact": REMINDER_RESOLVE, "reminder.delete": REMINDER_DELETE,
}
OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)
CHILE = timezone(timedelta(hours=-3))
# Friday 9 October 2026, 00:40 in Chile: the r19 tanda t1, and the clock every move below is judged against.
NOW = datetime(2026, 10, 9, 0, 40, tzinfo=CHILE)
MADE_ID = "6f1c2a4e-9b7d-4c1e-8a35-2d0f6b9e7c11"
MOVE = ("notification.cancel.at", "notification.schedule")


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("own_notification_at", "retimed_notification", "moved_notification_request"):
        judged = getattr(DialogueState, name)
        monkeypatch.setattr(DialogueState, name, lambda self, *a, _judged=judged, **k: _judged(
            self, *a, **{**k, "now": NOW, "zone": CHILE}))


def _tool(operation: str) -> dict[str, Any]:
    schema = SCHEMAS.get(operation) or _schema({}, [])
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "low_reversible", "parameters": schema}}


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision | None) -> None:
        self.decision = decision

    def decide_in_context(self, *_a, **_k):
        assert self.decision is not None, "the decider was not to be asked"
        return self.decision

    def prepare_decision(self, *_a, **_k):
        return None

    def formulate_explicit_clarification_question(self, *_a, **_k):
        return "¿Cuál?"

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿Qué quieres que haga?"

    def clarify_unresolved_input(self, *_a, **_k):
        return "¿Qué quieres decir?"

    def public_lookup_requested(self, _text):
        return False

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def _verify_semantic_effect_shape(self, _text):
        return "complete", "one"

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


def _utc(day: int, hour: int, minute: int = 0) -> str:
    return datetime(2026, 10, day, hour, minute, tzinfo=CHILE).astimezone(timezone.utc).isoformat()


def _local(due: str) -> str:
    return datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(CHILE).strftime("%d %H:%M")


def _reminder_made(state: DialogueState, request: str, title: str, due: str, reminder_id: str | None) -> DialogueState:
    """The turn that made a reminder of BAXY's store, as the run's compose verified it."""

    observed: dict[str, object] = {"title": title, "details": "", "dueUtc": due, "dismissed": False,
                                   "deleted": False, "version": 1}
    if reminder_id is not None:
        observed["reminderId"] = reminder_id
    state.expect(request, ["reminder.create"])
    state.record({"kind": "operation", "operation": "reminder.create", "verified": True, "succeeded": True,
                  "observed": observed})
    return state


def _history(said: list[str]) -> list[dict[str, str]]:
    return [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(said)]


def _turn(said: list[str], decision: ContextDecision | None, state: DialogueState) -> dict:
    tools = {name: _tool(name) for name in OPERATIONS}
    return turn_decide._prepare_turn_result(
        {"id": "r19b", "text": said[-1], "history": _history(said)},
        llm=_Decider(decision), planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, dialogue_state=state,
    )


def _planned(said: list[str], result: dict, state: DialogueState, schemas: dict) -> dict[str, object]:
    objective = str(result["objective"])
    state.expect(objective, result["effectOperations"])
    moved = turn_followups._retimed_conversation_notice(state, _history(said), objective)
    assert moved is not None
    steps = plan_shape._explicit_plan_skeleton(tuple(result["effectOperations"]))["steps"]
    return {
        step["operation"]: (
            plan_shape._retimed_step_arguments(step["operation"], moved, schemas[step["operation"]])
            if step["argumentsMode"] == "literal" else step["argumentsMode"]
        )
        for step in steps
    }


T1 = ["recuérdame mañana a las 9 llamar al dentista",
      "Listo, te recordaré mañana a las 9:00 llamar al dentista.",
      "no, mejor a las nueve y media"]


def test_t1_c04_2_the_reminder_just_made_is_moved_by_its_verified_id() -> None:
    state = _reminder_made(DialogueState(), T1[0], "llamar al dentista", _utc(9, 9), MADE_ID)
    decided = ContextDecision("Cambia el recordatorio de llamar al dentista a las 9:30.", "action", MOVE, "")
    result = _turn(T1, decided, state)
    assert result["kind"] == "plan"
    assert result["effectOperations"] == ["reminder.delete", "reminder.create"]
    planned = _planned(T1, result, state, SCHEMAS)
    assert planned["reminder.resolve.exact"] == {"title": "llamar al dentista", "reminderId": MADE_ID}
    assert planned["reminder.delete"] == "after_dependencies"
    created = planned["reminder.create"]
    assert isinstance(created, dict) and created["title"] == "llamar al dentista"
    assert _local(created["dueUtc"]) == "09 09:30"


def test_the_id_is_the_last_one_made_never_an_earlier_one_of_the_same_title() -> None:
    # Two «llamar al dentista» made in this conversation: the move is of the one the turn before made.
    state = _reminder_made(DialogueState(), "recuérdame el lunes a las 8 llamar al dentista", "llamar al dentista",
                           _utc(12, 8), "0a0a0a0a-0000-4000-8000-000000000001")
    state = _reminder_made(state, T1[0], "llamar al dentista", _utc(9, 9), MADE_ID)
    state.expect("Cambia el recordatorio de llamar al dentista a las 9:30.", ["reminder.delete", "reminder.create"])
    moved = state.retimed_notification(T1[-1], moving=True)
    assert moved is not None and moved.set_id == MADE_ID
    assert plan_shape._retimed_step_arguments("reminder.resolve.exact", moved, REMINDER_RESOLVE) == {
        "title": "llamar al dentista", "reminderId": MADE_ID,
    }


def test_a_catalog_without_the_id_keeps_the_title_alone() -> None:
    state = _reminder_made(DialogueState(), T1[0], "llamar al dentista", _utc(9, 9), MADE_ID)
    decided = ContextDecision("Cambia el recordatorio de llamar al dentista a las 9:30.", "action", MOVE, "")
    result = _turn(T1, decided, state)
    planned = _planned(T1, result, state, {**SCHEMAS, "reminder.resolve.exact": REMINDER_RESOLVE_TITLE_ONLY})
    assert planned["reminder.resolve.exact"] == {"title": "llamar al dentista"}


def test_a_create_result_without_an_id_resolves_by_its_title() -> None:
    state = _reminder_made(DialogueState(), T1[0], "llamar al dentista", _utc(9, 9), None)
    state.expect("Cambia el recordatorio de llamar al dentista a las 9:30.", ["reminder.delete", "reminder.create"])
    moved = state.retimed_notification(T1[-1], moving=True)
    assert moved is not None and moved.set_id == ""
    assert plan_shape._retimed_step_arguments("reminder.resolve.exact", moved, REMINDER_RESOLVE) == {
        "title": "llamar al dentista",
    }


def test_same_titled_reminders_of_other_conversations_lend_no_id() -> None:
    # A new conversation: the reminders «llamar al dentista» of other conversations are in the store, never in it.
    state = _reminder_made(DialogueState(), T1[0], "llamar al dentista", _utc(9, 9), MADE_ID)
    state.reset()
    assert state.retimed_notification(T1[-1], deciding=True, moving=True) is None
    said = ["oye", "Dime.", T1[-1]]
    decided = ContextDecision("Cambia la alarma a las 9:30.", "action", MOVE, "")
    assert _turn(said, decided, state)["effectOperations"] == list(MOVE)


def test_borra_el_recordatorio_without_a_referent_still_asks_which() -> None:
    said = ["borra el recordatorio"]
    result = _turn(said, ContextDecision("Borra el recordatorio.", "action", ("reminder.delete",), ""),
                   DialogueState())
    assert result["kind"] == "clarify"
    assert "reminderId" not in json.dumps(result)


def test_a_plain_deletion_after_the_reminder_was_made_is_no_move() -> None:
    # M158: a cancellation is not a correction of the time; it takes no retimed arguments.
    state = _reminder_made(DialogueState(), T1[0], "llamar al dentista", _utc(9, 9), MADE_ID)
    assert state.retimed_notification("borra el recordatorio", deciding=True) is None
