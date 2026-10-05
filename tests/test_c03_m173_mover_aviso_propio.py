"""M173 (2026-10-05, DEV-F/DEV-I v5a–v5c): moving the notice BAXY just set in this conversation.

When the person corrected the alarm or reminder BAXY had just set, the decider planned the move right (cancel + set
again), and the product lost it:

- I-w04-t2 «actually make it half three» after «could you set a reminder for Friday at 4 to ring the dentist…» → set
  with ``reminder.create`` → the plan's ``notification.cancel.at`` had no kind nor hour → «¿A qué hora exacta y qué
  tipo de notificación…?». F-w55-t2 «no, mejor media hora antes, una hora es mucho» → the same question: BAXY's own
  store reminder is in no Task Scheduler, and the dialogue state kept only notices set by ``notification.schedule``.
- I-w40-t2 «hmm, push it to 6:45 instead» (alarm at 6:30) and I-w12-t5 «uh no, correla a 30 min antes del partido…»
  (alarm at 18:30, an hour before the 19:30 match BAXY told) → ``notification.cancel.at`` at the old clock, which the run's
  store held more than once → «I couldn't cancel the alarm or reminder.» / «No pude cancelar el aviso.» M145 did not
  apply: the restatements («Change the 6:30 alarm to 6:45…», «Correla la alarma … a las 19:00.») gave it no old clock,
  or the new one.

A planned move of the notice the last turn set moves THAT one, by how it was set: the latest of its kind cancelled and
set again (while it is the last one of its kind this conversation set and still to ring), or the reminder of the store
deleted by its exact title (``reminder.resolve.exact`` → ``reminder.delete``) and made again (``reminder.create``). Its
new time is read from what was said: «half three» is 15:30 next to 16:00 (D61), «30 min antes del partido» counts from
the match BAXY told, «media hora antes» from the moment the first count was made from. Nothing else changes: no notice
set the turn before, another notice named by its clock, one already rung, a plain cancellation (M158). No test reads
the machine's clock (M108).
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import temporal
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


CANCEL_AT = _schema({
    "hour": {"type": "integer", "minimum": 0, "maximum": 23}, "kind": {"type": "string", "enum": ["alarm", "reminder"]},
    "minute": {"type": "integer", "minimum": 0, "maximum": 59}, "period": {"type": "string", "enum": ["am", "pm"]},
}, ["hour", "kind"])
CANCEL_LATEST = _schema({"kind": {"type": "string", "enum": ["alarm", "reminder"]}}, ["kind"])
SCHEDULE = _schema({
    "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
    "kind": {"type": "string", "enum": ["alarm", "reminder"]},
    "recurrence": {"type": "string", "enum": ["daily", "hourly"]},
    "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
}, ["dueUtc", "kind", "title"])
REMINDER_CREATE = _schema({
    "details": {"type": "string", "x-maxUtf8Bytes": 65536},
    "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
    "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
}, ["dueUtc", "title"])
REMINDER_RESOLVE = _schema({
    "includeDeleted": {"type": "boolean"},
    "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
}, ["title"])
SCHEMAS = {
    "notification.cancel.at": CANCEL_AT, "notification.cancel.latest": CANCEL_LATEST,
    "notification.schedule": SCHEDULE, "reminder.create": REMINDER_CREATE, "reminder.resolve.exact": REMINDER_RESOLVE,
}
OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)
CHILE = timezone(timedelta(hours=-3))
# Monday 5 October 2026, 18:30 in Chile: the v5c DEV-I run, and the clock every move below is judged against.
NOW = datetime(2026, 10, 5, 18, 30, tzinfo=CHILE)


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    # The product passes ``now=None, zone=None`` on (the machine's clock and zone); here they are always NOW and Chile.
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
        self.asked = False

    def decide_in_context(self, *_a, **_k):
        self.asked = True
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


def _alarm_set(state: DialogueState, request: str, kind: str, title: str, due: str, task: str) -> DialogueState:
    """The turn that set an alarm or reminder of the Task Scheduler, as the run's compose verified it."""

    state.expect(request, ["notification.schedule"])
    state.record({"kind": "operation", "operation": "notification.schedule", "verified": True, "succeeded": True,
                  "observed": {"version": 1, "kind": kind, "title": title, "dueUtc": due, "taskName": task,
                               "state": "Ready", "authority": "windows_task_scheduler_postread"}})
    return state


def _reminder_made(state: DialogueState, request: str, title: str, due: str, *, deleted: bool = False) -> DialogueState:
    """The turn that made a reminder of BAXY's store (``reminder.create``), as the run's compose verified it."""

    state.expect(request, ["reminder.create"])
    state.record({"kind": "operation", "operation": "reminder.create", "verified": True, "succeeded": True,
                  "observed": {"reminderId": "2062b659-6ef7-4109-8d99-c932580db43d", "title": title, "details": "",
                               "dueUtc": due, "dismissed": False, "deleted": deleted, "version": 1}})
    return state


def _history(said: list[str]) -> list[dict[str, str]]:
    return [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(said)]


def _turn(said: list[str], decision: ContextDecision | None, state: DialogueState) -> dict:
    """``said``: the conversation as lived, user first and alternating, ending in the person's message."""

    tools = {name: _tool(name) for name in OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "m173", "text": said[-1], "history": _history(said)},
        llm=_Decider(decision), planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, dialogue_state=state,
    )


def _planned(said: list[str], result: dict, state: DialogueState) -> dict[str, object]:
    """The plan's literal steps as the plan request fills them (``_retimed_conversation_notice``), after ``expect``."""

    objective = str(result["objective"])
    state.expect(objective, result["effectOperations"])
    moved = sidecar._retimed_conversation_notice(state, _history(said), objective)
    assert moved is not None
    steps = sidecar._explicit_plan_skeleton(tuple(result["effectOperations"]))["steps"]
    return {
        step["operation"]: (
            sidecar._retimed_step_arguments(step["operation"], moved, SCHEMAS[step["operation"]])
            if step["argumentsMode"] == "literal" else step["argumentsMode"]
        )
        for step in steps
    }


MOVE = ("notification.cancel.at", "notification.schedule")


# ------------------------------------------------------------------ the rows, with the conversation as lived (v5c)

W04 = ["could you set a reminder for Friday at 4 to ring the dentist about my crown?",
       "I have set the reminder for Friday, October 9, 2026, at 16:00 to ring the dentist about your crown.",
       "actually make it half three"]


def test_i_w04_t2_a_reminder_of_the_store_is_deleted_and_made_again_at_half_three() -> None:
    state = _reminder_made(DialogueState(), W04[0], "ring the dentist about my crown", _utc(9, 16))
    decided = ContextDecision("Change the dentist reminder to 3:30 PM on Friday.", "action", MOVE, "")
    result = _turn(W04, decided, state)
    assert result["kind"] == "plan"
    assert result["effectOperations"] == ["reminder.delete", "reminder.create"]
    planned = _planned(W04, result, state)
    assert planned["reminder.resolve.exact"] == {"title": "ring the dentist about my crown"}
    assert planned["reminder.delete"] == "after_dependencies"
    created = planned["reminder.create"]
    assert isinstance(created, dict) and created["title"] == "ring the dentist about my crown"
    assert _local(created["dueUtc"]) == "09 15:30"  # «half three» next to 16:00 (D61), on the same Friday


W40 = ["would you mind setting an alarm for 6:30 tomorrow morning? I've got the dentist early",
       "The alarm for 6:30 tomorrow morning has been scheduled.",
       "hmm, push it to 6:45 instead"]


def test_i_w40_t2_the_alarm_just_set_is_the_latest_one_cancelled_whatever_else_rings_at_6_30() -> None:
    state = _alarm_set(DialogueState(), "Set an alarm for 6:30 tomorrow morning.", "alarm",
                       "alarm for 6:30 tomorrow morning", _utc(6, 6, 30), "BAXY-Alarm-29e54ef35f6344338010f6fdceddf344")
    decided = ContextDecision("Change the 6:30 alarm to 6:45 tomorrow morning.", "action", MOVE, "")
    result = _turn(W40, decided, state)
    assert result["effectOperations"] == ["notification.cancel.latest", "notification.schedule"]
    planned = _planned(W40, result, state)
    assert planned["notification.cancel.latest"] == {"kind": "alarm"}
    scheduled = planned["notification.schedule"]
    assert isinstance(scheduled, dict) and scheduled["kind"] == "alarm" and _local(scheduled["dueUtc"]) == "06 06:45"


W12 = ["che como salio boca anoche?", "Boca Juniors ganó 3-0 a Unión (Santa Fe) en La Bombonera.",
       "quien hizo los goels", "Lozano y Merentiel marcaron los goles de Boca en el partido contra San Lorenzo.",
       "y cuando jeuga de nuevo",
       "El próximo partido de Boca Juniors es contra Instituto (Córdoba) el viernes 9 de octubre de 2026 a las 19:30 "
       "hora local en Monumental Presidente Perón.",
       "ponem una alarma una hora antes", "He programado la alarma para el viernes 9 de octubre de 2026 a las 18:30.",
       "uh no, correla a 30 min antes del partido asi llego del laburo"]


def _w12_state() -> DialogueState:
    return _alarm_set(DialogueState(), "ponem una alarma el viernes 9 de octubre de 2026 a las 18:30", "alarm",
                      "alarma el viernes 9 de octubre de 2026 a las 18:30", _utc(9, 18, 30),
                      "BAXY-Alarm-e98f074df09445b3b01105eb4b2622f8")


@pytest.mark.parametrize("restated", ["Correla la alarma del partido de Boca a las 19:00.", "Correla la alarma del partido."])
def test_i_w12_t5_thirty_minutes_before_the_match_baxy_told(restated: str) -> None:
    # With the restatement's clock or with none: the new time is the count from the 19:30 BAXY said.
    state = _w12_state()
    result = _turn(W12, ContextDecision(restated, "action", MOVE, ""), state)
    assert result["effectOperations"] == ["notification.cancel.latest", "notification.schedule"]
    planned = _planned(W12, result, state)
    assert planned["notification.cancel.latest"] == {"kind": "alarm"}
    scheduled = planned["notification.schedule"]
    assert isinstance(scheduled, dict) and _local(scheduled["dueUtc"]) == "09 19:00"


W55 = ["mañana a las 10 tengo turno con el dentista en Palermo, recordámelo una hora antes así no salgo a las corridas",
       'Te he programado una alarma para mañana a las 09:00 con el título "turno con el dentista en Palermo".',
       "no, mejor media hora antes, una hora es mucho"]


def test_f_w55_t2_half_an_hour_before_moves_the_reminder_of_the_store_to_9_30() -> None:
    state = _reminder_made(DialogueState(), W55[0], "turno con el dentista en Palermo", _utc(6, 9))
    # The move is read before the decider (M102): «media hora antes» of the 10:00 the first count was made from.
    result = _turn(W55, None, state)
    assert result["kind"] == "plan"
    assert result["effectOperations"] == ["reminder.delete", "reminder.create"]
    assert result["objective"] == (
        "borra el recordatorio «turno con el dentista en Palermo» de las 09:00 y vuelve a ponerlo a las 09:30"
    )
    planned = _planned(W55, result, state)
    assert planned["reminder.resolve.exact"] == {"title": "turno con el dentista en Palermo"}
    created = planned["reminder.create"]
    assert isinstance(created, dict) and created["title"] == "turno con el dentista en Palermo"
    assert _local(created["dueUtc"]) == "06 09:30"


# ------------------------------------------------------------------ the same move in other words

def test_other_words_move_a_reminder_of_the_store() -> None:
    # English: a reminder made for tomorrow at 5 pm, moved «to half five».
    said = ["remind me tomorrow at 5pm to call mum", "Done, tomorrow at 17:00: call mum.", "oh wait, move it to half five"]
    state = _reminder_made(DialogueState(), said[0], "call mum", _utc(6, 17))
    result = _turn(said, ContextDecision("Move the call mum reminder to 5:30 PM tomorrow.", "action", MOVE, ""), state)
    assert result["effectOperations"] == ["reminder.delete", "reminder.create"]
    created = _planned(said, result, state)["reminder.create"]
    assert isinstance(created, dict) and created["title"] == "call mum" and _local(created["dueUtc"]) == "06 17:30"
    # Spanish: a reminder made for Thursday at 4, «cámbialo a las 5».
    said = ["recuérdame el jueves a las 4 pagar el gas", "Listo, el jueves a las 16:00: pagar el gas.",
            "uy, mejor cámbialo para las 5 que salgo tarde"]
    state = _reminder_made(DialogueState(), said[0], "pagar el gas", _utc(8, 16))
    result = _turn(said, ContextDecision("Cambia el recordatorio del gas a las 17:00.", "action", MOVE, ""), state)
    assert result["effectOperations"] == ["reminder.delete", "reminder.create"]
    created = _planned(said, result, state)["reminder.create"]
    assert isinstance(created, dict) and created["title"] == "pagar el gas" and _local(created["dueUtc"]) == "08 17:00"


def test_other_words_move_an_alarm_just_set() -> None:
    said = ["ponme una alarma a las 7 para el gimnasio", "He programado la alarma para las 19:00: gimnasio.",
            "no, muévela a las 7 y media"]
    state = _alarm_set(DialogueState(), "Pon una alarma a las 19:00 para el gimnasio.", "alarm", "gimnasio",
                       _utc(5, 19), "BAXY-Alarm-" + "a" * 32)
    result = _turn(said, ContextDecision("Cambia la alarma del gimnasio a las 19:30.", "action", MOVE, ""), state)
    assert result["effectOperations"] == ["notification.cancel.latest", "notification.schedule"]
    scheduled = _planned(said, result, state)["notification.schedule"]
    assert isinstance(scheduled, dict) and scheduled["title"] == "gimnasio" and _local(scheduled["dueUtc"]) == "05 19:30"
    said = ["set an alarm for 8 tomorrow morning, gym", "Alarm set for 8:00 tomorrow: gym.", "make that 8:15 instead"]
    state = _alarm_set(DialogueState(), "Set an alarm for 8 am tomorrow for the gym.", "alarm", "gym",
                       _utc(6, 8), "BAXY-Alarm-" + "b" * 32)
    result = _turn(said, ContextDecision("Change the gym alarm to 8:15 tomorrow.", "action", MOVE, ""), state)
    assert result["effectOperations"] == ["notification.cancel.latest", "notification.schedule"]


# ------------------------------------------------------------------ what does not change


def test_m158_a_cancellation_named_by_its_clock_stays_the_one_at_that_clock() -> None:
    said = ["qué alarmas tengo", "Tienes 11 alarmas y recordatorios: …", "cancela la de las 7 que mañana no trabajo"]
    state = DialogueState()
    state.expect("qué alarmas tengo", ["notification.list"])
    decided = ContextDecision("Cancela la alarma de las 7.", "action", ("notification.cancel.at",), "")
    assert _turn(said, decided, state)["effectOperations"] == ["notification.cancel.at"]


@pytest.mark.parametrize("state", [
    DialogueState(),  # nothing set in this conversation
    # The reminder was made two turns ago: a turn in between (the weather) is not the one being corrected. (An alarm of
    # the Task Scheduler set by this conversation is M145's, at any distance.)
    (lambda s: (s.expect("¿qué tiempo hace?", ["weather.current"]), s)[1])(
        _reminder_made(DialogueState(), "Recuérdame a las 7 sacar la basura.", "sacar la basura", _utc(6, 7))),
])
def test_without_a_notice_set_the_turn_before_a_move_stays_as_decided(state: DialogueState) -> None:
    said = ["oye", "Dime.", "mejor a las 6"]
    decided = ContextDecision("Cambia la alarma de las 7 a las 6.", "action", MOVE, "")
    assert _turn(said, decided, state)["effectOperations"] == list(MOVE)


def test_another_notice_named_by_its_clock_is_not_the_one_just_set() -> None:
    state = _alarm_set(DialogueState(), "Pon una alarma a las 6:30.", "alarm", "alarma", _utc(6, 6, 30),
                       "BAXY-Alarm-" + "d" * 32)
    said = ["ponme una alarma a las 6:30", "Listo, alarma a las 6:30.", "y la de las 7 pásala a las 8"]
    for restated in ("Cambia la alarma de las 7 a las 8.", "Mueve esa alarma a las 8."):
        decided = ContextDecision(restated, "action", MOVE, "")
        assert _turn(said, decided, state)["effectOperations"] == list(MOVE), restated
    said = ["set an alarm for 6:30", "Alarm set for 6:30.", "and move the 7 o'clock one to 8"]
    decided = ContextDecision("Move the 7:00 alarm to 8:00.", "action", MOVE, "")
    assert _turn(said, decided, state)["effectOperations"] == list(MOVE)


def test_the_old_and_the_new_clock_are_the_notice_s_own() -> None:
    old, new = datetime(2026, 10, 6, 6, 30, tzinfo=CHILE), datetime(2026, 10, 6, 6, 45, tzinfo=CHILE)
    assert not temporal.names_another_notice("Change the 6:30 alarm to 6:45 tomorrow morning.", old, new)
    assert not temporal.names_another_notice("Pon la alarma a las 6:45.", old, new)
    assert not temporal.names_another_notice("hmm, push it to 6:45 instead", old, new)
    assert temporal.names_another_notice("y la de las 7 pásala a las 8", old, new)
    assert temporal.names_another_notice("the 7 one, make it 8", old, new)
    evening = datetime(2026, 10, 9, 18, 30, tzinfo=CHILE)
    assert not temporal.names_another_notice("Cambia la alarma de las 18:30 a las 19:00.", evening)
    assert temporal.names_another_notice("Cambia la alarma de las 6:30 de la mañana a las 7.", evening)
    # «la de las N», «the N o'clock one» say which one is meant: the new clock is not it.
    assert temporal.names_another_notice("y la de las 6:45 ponla a las 7", old, new)
    assert temporal.names_another_notice("move the 6:45 alarm to 7", old, new)


def test_an_alarm_already_rung_is_not_the_latest_to_cancel() -> None:
    said = ["ponme una alarma a las 6", "Listo, alarma a las 6:00.", "no, mejor a las 6:30"]
    state = _alarm_set(DialogueState(), "Pon una alarma a las 6.", "alarm", "alarma", _utc(5, 6),
                       "BAXY-Alarm-" + "e" * 32)
    decided = ContextDecision("Cambia la alarma de las 6:00 a las 6:30.", "action", MOVE, "")
    assert _turn(said, decided, state)["effectOperations"] == list(MOVE)


def test_a_reminder_of_the_store_never_takes_a_task_scheduler_cancel() -> None:
    state = _reminder_made(DialogueState(), W04[0], "ring the dentist about my crown", _utc(9, 16))
    state.expect("Change the dentist reminder to 3:30 PM on Friday.", list(MOVE))
    moved = state.retimed_notification("actually make it half three", moving=True)
    assert moved is not None and moved.set_by == "reminder.create"
    assert sidecar._retimed_step_arguments("notification.cancel.at", moved, CANCEL_AT) is None
    assert sidecar._retimed_step_arguments("notification.cancel.latest", moved, CANCEL_LATEST) is None
    assert sidecar._retimed_step_arguments("notification.schedule", moved, SCHEDULE) is None


def test_a_deleted_or_undated_reminder_result_is_no_notice() -> None:
    state = _reminder_made(DialogueState(), W04[0], "ring the dentist about my crown", _utc(9, 16), deleted=True)
    assert state.retimed_notification("actually make it half three", deciding=True, moving=True) is None
    state = DialogueState()
    state.expect(W04[0], ["reminder.create"])
    state.record({"kind": "operation", "operation": "reminder.create", "verified": True, "succeeded": True,
                  "observed": {"reminderId": "r", "title": "ring the dentist", "dueUtc": None, "version": 1}})
    assert state.retimed_notification("actually make it half three", deciding=True, moving=True) is None
