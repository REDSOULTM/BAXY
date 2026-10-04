"""M158 (2026-10-04, DEV-I v4u/v4v): «cancelar la de las 7» cancels the one at 7, never another one.

I-w26-t4 «cancela la de las 7 que mañana no trabajo»: BAXY had just listed eleven alarms and reminders of the week (set
by other conversations of the same run), one of them an alarm at 7:00. The decider chose
``notification.cancel.latest``, restated «cancela la última alarma», and BAXY answered «He cancelado la última
alarma.»: it cancelled the last one set, which was not the one at 7. The isolated decider and the gold say
``notification.cancel.at``. An effect on something the person did not ask for, so a safety exception to D58 (as M155
with the send): when the decider cancels the latest one and the message names the alarm or reminder by its clock, the
cancellation is ``notification.cancel.at`` at that clock (``semantic.temporal.clock_named_cancellation``). When the last
one this conversation set is the one at that clock, M145 makes it the latest again (F-w35-t4 accepts both). A move
(cancel.latest + schedule), a cancellation that names no clock («cancela la alarma», «scratch the garlic knots one») and
D39's plural stay as they were.
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
from baxy_mind.semantic.temporal import clock_named_cancellation

CANCEL_AT = {"type": "object", "properties": {
    "hour": {"type": "integer", "minimum": 0, "maximum": 23}, "kind": {"type": "string", "enum": ["alarm", "reminder"]},
    "minute": {"type": "integer", "minimum": 0, "maximum": 59}, "period": {"type": "string", "enum": ["am", "pm"]}},
    "required": ["hour", "kind"], "additionalProperties": False}
CANCEL_LATEST = {"type": "object", "properties": {"kind": {"type": "string", "enum": ["alarm", "reminder"]}},
                 "required": ["kind"], "additionalProperties": False}
OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)
LOCAL = timezone(timedelta(hours=-3))
# Sunday 4 October 2026, 11:00 in Chile (UTC-3): the clock every own notification below is judged against (M108).
NOW = datetime(2026, 10, 4, 11, 0, tzinfo=LOCAL)


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    judged = DialogueState.own_notification_at
    monkeypatch.setattr(DialogueState, "own_notification_at",
                        lambda self, *args, **kwargs: judged(self, *args, **{"now": NOW, "zone": LOCAL, **kwargs}))


def _due(hour: int, minute: int = 0, days: int = 1) -> str:
    return (NOW + timedelta(days=days)).replace(hour=hour, minute=minute).astimezone(timezone.utc).isoformat()


def _set(state: DialogueState, request: str, kind: str, title: str, due: str, task: str) -> None:
    state.expect(request, ["notification.schedule"])
    state.record({"kind": "operation", "operation": "notification.schedule", "verified": True, "succeeded": True,
                  "observed": {"version": 1, "kind": kind, "title": title, "dueUtc": due, "taskName": task}})


def _tool(operation: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_a, **_k):
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


def _turn(said: list[str], decision: ContextDecision, state: DialogueState | None = None) -> dict:
    """``said``: the conversation, user first and alternating, ending in the person's message."""

    history = [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(said)]
    tools = {name: _tool(name) for name in OPERATIONS}
    tools["notification.cancel.at"] = _tool("notification.cancel.at", CANCEL_AT)
    tools["notification.cancel.latest"] = _tool("notification.cancel.latest", CANCEL_LATEST)
    return sidecar._prepare_turn_result(
        {"id": "m158", "text": said[-1], "history": history},
        llm=_Decider(decision), planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, dialogue_state=state or DialogueState(),
    )


def _cancelled_at(result: dict) -> dict | None:
    """The arguments ``notification.cancel.at`` takes from the turn's objective, as the arguments step grounds them."""

    return sidecar._ground_explicit_arguments("notification.cancel.at", result["objective"], CANCEL_AT)


LATEST_ALARM = ContextDecision("cancela la última alarma", "action", ("notification.cancel.latest",), "")

# I-w26-t4 as the App lived it in v4v (the search failed, the reminder was asked about, the list read eleven).
LIVED_W26 = [
    "a que hora juega chile el martes",
    "No pude comprobarlo; de memoria, puede no ser exacto: la hora de los partidos de Chile depende del día "
    "específico del mes y de la hora local de la liga.",
    "recuerdame una hora antes de eso",
    "¿Qué día del mes es el partido de Chile?",
    "muestrame todas las alarmas y recordatorios q tengo pa esta semana",
    'Tienes 11 alarmas y recordatorios programados para esta semana: "Chipá en el horno (20 min)" a las 09:30, '
    '"Sacar la ropa de la lavadora" a las 10:09, "Turno en la clínica" a las 18:00, una alarma a las 19:30, '
    '"Reunión a las 9:00" a las 20:45, "Serie" a las 21:00, "Alarma a las 6:15" a las 06:15 mañana, "Alarma mañana '
    'a las 7" a las 07:00 mañana, "alarma" a las 08:00 mañana, "Pay the gas bill" a las 09:00 mañana y "alarm for '
    'half six tomorrow" a las 18:30 mañana.',
    "cancela la de las 7 que mañana no trabajo",
]
# The same turn with DEV-I's written history.
WRITTEN_W26 = [
    "a que hora juega chile el martes",
    "Chile juega el martes a las 21:00 contra Perú en el Estadio Nacional.",
    "recuerdame una hora antes de eso",
    "Listo, te recuerdo el martes a las 20:00 que juega Chile.",
    "muestrame todas las alarmas y recordatorios q tengo pa esta semana",
    "Tienes una alarma mañana a las 7:00 y el recordatorio del partido el martes a las 20:00.",
    "cancela la de las 7 que mañana no trabajo",
]


@pytest.mark.parametrize("said", [LIVED_W26, WRITTEN_W26], ids=["lived", "written"])
def test_i_w26_t4_the_one_named_by_its_clock_is_cancelled_at_that_clock(said: list[str]) -> None:
    state = DialogueState()
    if said is WRITTEN_W26:
        # The match reminder this conversation set: the last one it set, but not the one at 7.
        _set(state, "recuérdame el martes a las 20:00 que juega Chile", "reminder", "Juega Chile", _due(20, days=2),
             "BAXY-Reminder-" + "a" * 32)
    result = _turn(said, LATEST_ALARM, state)
    assert result["kind"] == "action" and result["operation"] == "notification.cancel.at"
    assert result["effectOperations"] == ["notification.cancel.at"]
    assert _cancelled_at(result) == {"hour": 7, "kind": "alarm"}


@pytest.mark.parametrize(
    ("said", "decision", "arguments"),
    [
        # Spanish, a reminder named with its minutes in words.
        (["ponme un recordatorio a las 5 y 10 para sacar la basura", "Listo, a las 17:10.",
          "y una alarma a las 9 para la reunión", "Hecho, alarma a las 9:00.",
          "quítame el recordatorio de las 5 y 10, ya la saqué"],
         ContextDecision("Cancela el último recordatorio.", "action", ("notification.cancel.latest",), ""),
         {"hour": 5, "minute": 10, "kind": "reminder"}),
        # English, «the 7 o'clock one», the kind only in the decider's restatement.
        (["what alarms have I got", "You have an alarm at 6:00 and one at 7:00 tomorrow.",
          "delete the 7 o'clock one, I'm off tomorrow"],
         ContextDecision("Delete the last alarm.", "action", ("notification.cancel.latest",), ""),
         {"hour": 7, "kind": "alarm"}),
        # English, the part of the day said is kept.
        (["what alarms have I got", "You have alarms at 6:30 am and 6:30 pm.", "kill my 6:30 pm alarm"],
         ContextDecision("Cancel the latest alarm.", "action", ("notification.cancel.latest",), ""),
         {"hour": 6, "minute": 30, "period": "pm", "kind": "alarm"}),
    ],
)
def test_other_words_and_the_other_language_cancel_at_the_clock_named(
        said: list[str], decision: ContextDecision, arguments: dict) -> None:
    result = _turn(said, decision)
    assert result["effectOperations"] == ["notification.cancel.at"]
    assert _cancelled_at(result) == arguments


def test_the_one_this_conversation_just_set_at_that_clock_stays_the_latest() -> None:
    # F-w35-t4: the last alarm this conversation set is the one at 5:10; the latest is that one (M145).
    state = DialogueState()
    _set(state, "a las 4 y 50", "alarm", "Vuelo a Cartagena", _due(4, 50), "BAXY-Alarm-" + "b" * 32)
    _set(state, "y otra a las 5 y 10 por si las moscas", "alarm", "Vuelo a Cartagena", _due(5, 10),
         "BAXY-Alarm-" + "c" * 32)
    said = ["baxy, ponme una alarma pa mañana que tengo vuelo a Cartagena tempranito",
            "¿Para qué hora la quieres mañana, con lo del vuelo?", "a las 4 y 50", "Listo, alarma mañana a las 4:50 a. m.",
            "y otra a las 5 y 10 por si las moscas", "Hecho, otra alarma a las 5:10 a. m.",
            "mmm pensándolo bien quítame la de las 5 y 10, con una me basta"]
    for decision in (
        ContextDecision("Cancela la alarma de las 5:10.", "action", ("notification.cancel.at",), ""),
        ContextDecision("Cancela la última alarma.", "action", ("notification.cancel.latest",), ""),
    ):
        assert _turn(said, decision, state)["effectOperations"] == ["notification.cancel.latest"]


def test_the_4_50_one_is_not_the_latest_even_when_the_decider_says_latest() -> None:
    state = DialogueState()
    _set(state, "a las 4 y 50", "alarm", "Vuelo", _due(4, 50), "BAXY-Alarm-" + "b" * 32)
    _set(state, "y otra a las 5 y 10", "alarm", "Vuelo", _due(5, 10), "BAXY-Alarm-" + "c" * 32)
    said = ["ponme una alarma a las 4 y 50", "Listo.", "y otra a las 5 y 10", "Hecho.", "quítame la de las 4 y 50"]
    result = _turn(said, ContextDecision("Cancela la última alarma.", "action", ("notification.cancel.latest",), ""),
                   state)
    assert result["effectOperations"] == ["notification.cancel.at"]
    assert _cancelled_at(result) == {"hour": 4, "minute": 50, "kind": "alarm"}


def test_a_move_of_the_one_just_set_stays_cancel_latest_and_schedule() -> None:
    # G-w11-t2 «no espera, mejor a las 6:30» after an alarm at 6, decided by the decider as a move.
    state = DialogueState()
    _set(state, "despiértame a las 6 de la mañana", "alarm", "alarma", _due(6), "BAXY-Alarm-" + "d" * 32)
    said = ["oye baxy, despiértame a las 6 de la mañana que mañana madrugo para la universidad",
            "Listo, puse la alarma para las 6:00 de la mañana.", "no espera, mejor a las 6:30"]
    move = ContextDecision("Cambia la alarma de mañana a las 6:30.", "action",
                           ("notification.cancel.latest", "notification.schedule"), "")
    assert _turn(said, move, state)["effectOperations"] == ["notification.cancel.latest", "notification.schedule"]


def test_what_names_no_clock_stays_as_decided() -> None:
    # F-w45-t4: the timer just set, taken back by what it is for (M113).
    said = ["pizza just went in, gimme a 25 minute countdown", "Timer set: 25 minutes for the pizza.",
            "and one for the garlic knots", "How long for the garlic knots?",
            "go with 12, the bag says 10 to 12 but my oven runs cold", "Done, 12-minute timer for the garlic knots.",
            "ugh wait, scratch the garlic knots one, I'll just watch them"]
    assert _turn(said, ContextDecision("cancel the last timer", "action", ("notification.cancel.latest",), ""))[
        "effectOperations"] == ["notification.cancel.latest"]
    # «cancela la alarma» with no clock, and a length said twice (D-s097), keep the decider's latest.
    for said in (["pon una alarma a las 8", "Listo, alarma a las 8:00.", "cancela la alarma"],
                 ["hola", "Hola.", "Quiero retomar el entrenamiento de glúteo en 2 , no espera en 3 minutos"]):
        assert _turn(said, LATEST_ALARM)["effectOperations"] == ["notification.cancel.latest"], said[-1]


@pytest.mark.parametrize(
    "text",
    [
        "cancela la alarma",
        "cancela la reunión de las 7",
        "cancela las alarmas de las 7",
        "cambia la alarma de las 7 a las 8",
        "cancela la de las 6 y ponme la alarma a las 7",
        "no espera, mejor a las 6:30",
        "ugh wait, scratch the garlic knots one, I'll just watch them",
        "pon una alarma a las 7",
        "set an alarm for 7 o'clock",
    ],
)
def test_the_reader_names_no_clock_cancellation_in_neighbouring_requests(text: str) -> None:
    assert clock_named_cancellation(text, "cancela la última alarma") is None


@pytest.mark.parametrize(
    ("text", "restated", "said"),
    [
        ("cancela la de las 7 que mañana no trabajo", "cancela la última alarma", "cancela la alarma de las 7:00"),
        ("¿sabes qué? quítame la de las 6:40, con la otra basta", "Cancela la última alarma.",
         "cancela la alarma de las 6:40"),
        ("mejor bórrala, la de las siete de la tarde", "Cancela la última alarma.", "cancela la alarma de las 19:00"),
        ("cancela el recordatorio de la una", "", "cancela el recordatorio de la 1:00"),
        ("cancel the 7 one", "Cancel the last reminder.", "cancel the reminder at 7:00"),
        ("get rid of the alarm at 7:15 pm", "", "cancel the alarm at 7:15 pm"),
        # Neither the message nor the restatement says the kind: the message is the request, read as it was said.
        ("cancel the 7 one", "Cancel the last one.", "cancel the 7 one"),
    ],
)
def test_the_reader_says_the_cancellation_at_the_clock_named(text: str, restated: str, said: str) -> None:
    assert clock_named_cancellation(text, restated) == said
