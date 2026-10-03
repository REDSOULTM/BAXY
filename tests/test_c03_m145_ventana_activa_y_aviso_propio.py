"""M145 (2026-10-03, DEV-G/DEV-H v4p): two general product gaps the decider got right and the product lost (D58).

1. «Esta ventana», the window in front. G-s041 «pasame esta ventana a la mitad izquierda», G-s082 «snap this to the
   left», G-s102 «acomodame esta ventana al lado izquierdo de la pantalla», H-s028 «¿Me haces el favor de pegar esta
   ventana a la derecha de la pantalla?»: the decider chose ``window.snap`` and restated «Coloca la ventana activa en la
   mitad izquierda de la pantalla.» / «Snap the active window to the left.»; the plan added ``window.resolve`` before it,
   which had no application to look for, and the App answered «no se pudo determinar cómo hacerlo en este PC»
   (plan_incomplete). A change that loses nothing (snap, move, maximize, minimize, restore) of the window the request
   names as the one in front now reads that window with ``window.active`` — as «maximizá esta ventana» already did
   (ARRANGE1229) — and the snap's side is the one half the request says. Closing keeps its own rules (M118).
2. The alarm this conversation set. H-w29-t2 «no espera, mejor a las 7:30» (moving the alarm just set at 19:00) and
   H-w45-t4 «cancel the 7 one» failed with «varias alarmas o recordatorios a esa misma hora… no se pudieron distinguir»:
   the run's shared store also held alarms of other conversations at 19:00. When the clock a cancellation (or a move)
   names is that of the alarm, timer or reminder this conversation set and verified, and it is the last one it set of
   that kind, the cancellation is of that one: ``notification.cancel.latest``. Without one of its own there, nothing
   changes. H-w29-t2's own words were already taken by M144 (the move of the one just set); M145 covers the same move
   decided by the decider and a plain cancellation. H-w45-t4 itself stays as it was: that conversation set no alarm at
   7 (only the dentist's reminder), so the two foreign alarms at 19:00 are still told apart by asking.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog, normalize_grounded_arguments
from baxy_mind.semantic.apps import names_the_window_in_front
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.windows import said_snap_side

SNAP = {"type": "object", "properties": {"side": {"type": "string", "enum": ["left", "right"]},
                                         "windowId": {"type": "string", "maxLength": 36}},
        "required": ["side", "windowId"], "additionalProperties": False}
WINDOW_ID = {"type": "object", "properties": {"windowId": {"type": "string", "maxLength": 36}},
             "required": ["windowId"], "additionalProperties": False}
CANCEL_AT = {"type": "object", "properties": {
    "hour": {"type": "integer", "minimum": 0, "maximum": 23}, "kind": {"type": "string", "enum": ["alarm", "reminder"]},
    "minute": {"type": "integer", "minimum": 0, "maximum": 59}, "period": {"type": "string", "enum": ["am", "pm"]}},
    "required": ["hour", "kind"], "additionalProperties": False}
CANCEL_LATEST = {"type": "object", "properties": {"kind": {"type": "string", "enum": ["alarm", "reminder"]}},
                 "required": ["kind"], "additionalProperties": False}
FRONT_ID = "win_3f2a9c0d8e7b4a6f9c1d2e3f4a5b6c7d"


def _tool(operation: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


def _plan(operation: str, objective: str) -> list[tuple[str, str, list[str]]]:
    """The steps of the plan the App asks for after the decider decided ``operation`` with ``objective``."""

    return [(step["operation"], step["argumentsMode"], step["dependsOn"])
            for step in sidecar._explicit_plan_skeleton((operation,), (objective,))["steps"]]


def _front(objective: str) -> dict[str, Any] | None:
    """The snap's arguments grounded on a verified ``window.active`` (the window in front), as ``plan.ground`` does."""

    observations = [{"stepId": "step_1", "operation": "window.active", "verified": True, "status": "completed",
                     "result": {"version": 1, "windows": [
                         {"windowId": FRONT_ID, "processId": 4242, "state": "normal", "foreground": True}]}}]
    arguments = sidecar._verified_dependency_identity_arguments(
        "window.snap", objective, observations, _tool("window.snap", SNAP), purpose=objective)
    if arguments is None:
        return None
    return normalize_grounded_arguments(
        arguments, SNAP, sidecar.trusted_plan_grounding_source(objective, observations))


FRONT_STEPS = [("window.active", "literal", []), ("window.snap", "after_dependencies", ["step_1"])]


# ------------------------------------------------------------------ 1. the window in front


@pytest.mark.parametrize(
    ("said", "decided", "side"),
    [
        ("pasame esta ventana a la mitad izquierda", "Coloca la ventana activa en la mitad izquierda de la pantalla.",
         "left"),  # G-s041
        ("snap this to the left", "Snap the active window to the left.", "left"),  # G-s082
        ("acomodame esta ventana al lado izquierdo de la pantalla",
         "Coloca la ventana activa en la mitad izquierda de la pantalla.", "left"),  # G-s102
        ("¿Me haces el favor de pegar esta ventana a la derecha de la pantalla?",
         "Coloca la ventana activa en la mitad derecha de la pantalla.", "right"),  # H-s028
    ],
)
def test_the_rows_snap_the_window_in_front(said: str, decided: str, side: str) -> None:
    # The App plans the decider's restatement; it reads the window in front, then snaps it to the half said.
    assert _plan("window.snap", decided) == FRONT_STEPS
    assert _front(decided) == {"side": side, "windowId": FRONT_ID}
    if said != "snap this to the left":  # a bare «this» is the decider's to read (it may have an antecedent)
        assert _plan("window.snap", said) == FRONT_STEPS
        assert _front(said) == {"side": side, "windowId": FRONT_ID}


@pytest.mark.parametrize(
    ("operation", "objective"),
    [
        ("window.snap", "put this window on the right half"),
        ("window.snap", "pon la ventana actual a la izquierda"),
        ("window.maximize", "maximize this window"),
        ("window.minimize", "Minimiza la ventana actual."),
        ("window.restore", "Restore the current window."),
        ("window.move", "Mueve esta ventana más arriba."),
    ],
)
def test_other_words_and_other_changes_read_the_window_in_front(operation: str, objective: str) -> None:
    assert _plan(operation, objective) == [("window.active", "literal", []),
                                           (operation, "after_dependencies", ["step_1"])]


def test_the_half_said_is_read_once() -> None:
    assert said_snap_side("put this window on the right half") == "right"
    assert said_snap_side("ponla a la izquierda y la otra a la derecha") is None
    assert said_snap_side("snap the active window") is None
    # «right» that is not a side of the screen is no side.
    assert said_snap_side("move this window right now") is None


@pytest.mark.parametrize(
    ("operation", "objective"),
    [
        # A named window keeps its resolution by name.
        ("window.snap", "pon chrome a la izquierda"),
        ("window.snap", "Coloca la ventana de Word en la mitad derecha."),
        ("window.minimize", "minimiza esta ventana de chrome"),
        # A bare pronoun or «esa/that ventana» may point back («abre chrome» → «ponla a la izquierda»): never the
        # window in front.
        ("window.snap", "ponla a la izquierda"),
        ("window.snap", "snap it to the left"),
        ("window.snap", "pon esa ventana a la izquierda"),
        ("window.snap", "put that window on the right"),
    ],
)
def test_a_named_window_or_a_pronoun_is_not_the_window_in_front(operation: str, objective: str) -> None:
    assert _plan(operation, objective)[0][0] == "window.resolve"


def test_closing_is_not_one_of_these_changes() -> None:
    # The changes that read the window in front lose nothing; a close keeps its own rule and its confirmation.
    assert "app.close" not in sidecar._FRONT_WINDOW_CHANGES
    assert "window.focus" not in sidecar._FRONT_WINDOW_CHANGES
    assert _plan("app.close", "Cierra la ventana de Chrome.")[0][0] == "window.resolve"
    assert names_the_window_in_front("cierra esta ventana") and not names_the_window_in_front("ciérrala")


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


def test_a_close_by_pronoun_is_still_never_the_window_in_front() -> None:
    # M118 unchanged: «cierra aquello» with nothing before it, restated as the active window, is asked.
    chat = [{"role": "user", "content": "explícame qué es un router, una frase"},
            {"role": "assistant", "content": "Un router reparte la conexión entre tus equipos."}]
    tools = [_tool(name) for name in ("app.close", "window.active", "window.snap", "window.resolve")]
    for text, restated in (("cierra aquello", "Cierra la ventana activa."), ("close that one", "Close the active window.")):
        result = sidecar._context_decided_result(
            {"id": "m145", "text": text, "history": [*chat, {"role": "user", "content": text}]},
            llm=_Decider(ContextDecision(restated, "action", ("app.close",), "")), planner_catalog=PlannerCatalog(tools),
        )
        assert result["kind"] == "clarify" and result["effectOperations"] == [], text


# ------------------------------------------------------------------ 2. the alarm this conversation set

OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)


LOCAL = timezone(timedelta(hours=-3))
# Saturday 3 October 2026, 11:00 in Chile (UTC-3): the clock every cancellation below is judged against.
NOW = datetime(2026, 10, 3, 11, 0, tzinfo=LOCAL)


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    judged = DialogueState.own_notification_at
    monkeypatch.setattr(DialogueState, "own_notification_at",
                        lambda self, *args, **kwargs: judged(self, *args, **{"now": NOW, "zone": LOCAL, **kwargs}))


def _due(hour: int, minute: int = 0, days: int = 1) -> str:
    """A local clock ``days`` from NOW's day, as the Core reports a notification's dueUtc."""

    local = (NOW + timedelta(days=days)).replace(hour=hour, minute=minute)
    return local.astimezone(timezone.utc).isoformat()


def _set(state: DialogueState, request: str, kind: str, title: str, due: str, task: str) -> None:
    state.expect(request, ["notification.schedule"])
    state.record({"kind": "operation", "operation": "notification.schedule", "verified": True, "succeeded": True,
                  "observed": {"version": 1, "kind": kind, "title": title, "dueUtc": due, "taskName": task}})


def _talked(state: DialogueState, request: str) -> None:
    state.expect(request, [])


def _turn(said: list[str], decision: ContextDecision, state: DialogueState) -> dict:
    """``said``: the conversation, user first and alternating, ending in the person's message."""

    history = [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(said)]
    tools = {name: _tool(name) for name in OPERATIONS}
    tools["notification.cancel.at"] = _tool("notification.cancel.at", CANCEL_AT)
    tools["notification.cancel.latest"] = _tool("notification.cancel.latest", CANCEL_LATEST)
    return sidecar._prepare_turn_result(
        {"id": "m145", "text": said[-1], "history": history},
        llm=_Decider(decision), planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, dialogue_state=state,
    )


CLASSES = ["las clases me quedan lejos, ¿me pones una alarma a las 7 porfa?",
           "He programado la alarma para las 19:00 con el título Clases.",
           "jaja gracias", "De nada."]


def _classes_state() -> DialogueState:
    state = DialogueState()
    _set(state, "Pon una alarma a las 7 para las clases.", "alarm", "Clases", _due(19), "BAXY-Alarm-" + "a" * 32)
    _talked(state, "jaja gracias")
    return state


MOVE = ContextDecision("Cambia la alarma de las 7 a las 7:30.", "action",
                       ("notification.cancel.at", "notification.schedule"), "")


def test_h_w29_t2_moving_the_alarm_this_conversation_set_moves_that_one() -> None:
    # The move decided by the decider (not right after setting it, where M144's move already reads it).
    result = _turn([*CLASSES, "no espera, mejor a las 7:30"], MOVE, _classes_state())
    assert result["kind"] == "plan"
    assert result["effectOperations"] == ["notification.cancel.latest", "notification.schedule"]


@pytest.mark.parametrize(
    ("said", "decision"),
    [
        ("cancel the 7 one", ContextDecision("Cancel the alarm at 7.", "action", ("notification.cancel.at",), "")),
        ("quítame la de las 7, ya no voy",
         ContextDecision("Cancela la alarma de las 7.", "action", ("notification.cancel.at",), "")),
        ("mejor bórrala, la de las siete de la tarde",
         ContextDecision("Cancela la alarma de las 7 de la tarde.", "action", ("notification.cancel.at",), "")),
    ],
)
def test_cancelling_at_the_clock_of_the_alarm_this_conversation_set_cancels_that_one(
        said: str, decision: ContextDecision) -> None:
    result = _turn([*CLASSES, said], decision, _classes_state())
    assert result["kind"] == "action" and result["operation"] == "notification.cancel.latest"
    assert result["effectOperations"] == ["notification.cancel.latest"]


def test_a_move_naming_no_clock_is_of_the_last_one_set() -> None:
    state = DialogueState()
    _set(state, "Ponme un recordatorio el jueves a las 4:30 para mi cita con el dentista.", "reminder",
         "Cita con el dentista", _due(16, 30, days=3), "BAXY-Reminder-" + "b" * 32)
    _talked(state, "gracias")
    decision = ContextDecision("Cambia el recordatorio del dentista para el jueves a las 15:30.", "action",
                               ("notification.cancel.at", "notification.schedule"), "")
    said = ["tengo dentista el jueves a las 4:30, so ponme un reminder", "Listo.", "gracias", "De nada.",
            "actually ponlo una hora antes de eso"]
    assert _turn(said, decision, state)["effectOperations"] == ["notification.cancel.latest", "notification.schedule"]


def test_the_plan_takes_the_kind_of_the_one_cancelled_from_the_request() -> None:
    assert sidecar._ground_explicit_arguments(
        "notification.cancel.latest", "Cambia la alarma de las 7:00 a las 7:15.", CANCEL_LATEST) == {"kind": "alarm"}


CANCEL_7 = ContextDecision("Cancela la alarma de las 7:00.", "action", ("notification.cancel.at",), "")


def test_h_w45_t4_with_no_alarm_of_its_own_at_7_stays_as_decided() -> None:
    # The conversation set only the dentist's reminder; the two alarms at 19:00 are other conversations'.
    state = DialogueState()
    _set(state, "Ponme un recordatorio el jueves a las 3:30.", "reminder", "Cita con el dentista",
         _due(3, 30, days=5), "BAXY-Reminder-" + "c" * 32)
    _talked(state, "which alarms tengo")
    result = _turn(["tengo dentista el jueves", "Listo.", "which alarms tengo", "Tienes 11.", "cancel the 7 one"],
                   CANCEL_7, state)
    assert result["effectOperations"] == ["notification.cancel.at"]


def test_what_is_not_the_last_one_of_its_own_stays_as_decided() -> None:
    said = [*CLASSES, "cancela la de las 7"]
    # No notification set in this conversation.
    assert _turn(said, CANCEL_7, DialogueState())["effectOperations"] == ["notification.cancel.at"]
    # Another alarm set after it: the latest is not the one at 7.
    state = _classes_state()
    _set(state, "Pon otra alarma a las 8.", "alarm", "Otra", _due(20), "BAXY-Alarm-" + "d" * 32)
    _talked(state, "ok")
    assert _turn(said, CANCEL_7, state)["effectOperations"] == ["notification.cancel.at"]
    # Already cancelled by this conversation.
    state = _classes_state()
    state.expect("Cancela la alarma de las 7.", ["notification.cancel.at"])
    state.record({"kind": "operation", "operation": "notification.cancel.at", "verified": True, "succeeded": True,
                  "observed": {"kind": "alarm", "hour": 7, "minute": 0, "taskName": "BAXY-Alarm-" + "a" * 32,
                               "canceled": True}})
    assert _turn(said, CANCEL_7, state)["effectOperations"] == ["notification.cancel.at"]
    # Already rung.
    state = DialogueState()
    _set(state, "Pon una alarma a las 7.", "alarm", "Clases", _due(19, days=-1), "BAXY-Alarm-" + "e" * 32)
    _talked(state, "gracias")
    assert _turn(said, CANCEL_7, state)["effectOperations"] == ["notification.cancel.at"]
    # Another clock: 7 in the morning is not the one at 19:00.
    morning = ContextDecision("Cancela la alarma de las 7 de la mañana.", "action", ("notification.cancel.at",), "")
    assert _turn(said, morning, _classes_state())["effectOperations"] == ["notification.cancel.at"]
    # Another kind.
    reminder = ContextDecision("Cancela el recordatorio de las 7.", "action", ("notification.cancel.at",), "")
    assert _turn(said, reminder, _classes_state())["effectOperations"] == ["notification.cancel.at"]


def test_a_plan_s_steps_are_what_this_conversation_set_and_cancelled() -> None:
    # A move done as a plan (its steps in one composed situation) leaves the new one as the conversation's own.
    state = _classes_state()
    state.expect("Cambia la alarma de las 7 a las 7:30.", ["notification.cancel.at", "notification.schedule"])
    steps = [
        {"kind": "operation", "operation": "notification.cancel.at", "verified": True, "succeeded": True,
         "observed": {"kind": "alarm", "hour": 7, "minute": 0, "taskName": "BAXY-Alarm-" + "a" * 32, "canceled": True}},
        {"kind": "operation", "operation": "notification.schedule", "verified": True, "succeeded": True,
         "observed": {"kind": "alarm", "title": "Clases", "dueUtc": _due(19, 30), "taskName": "BAXY-Alarm-" + "f" * 32}},
    ]
    state.record({"kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 2,
                  "steps": [json.dumps(step) for step in steps]})
    assert not state.own_notification_at("alarm", 7)
    assert state.own_notification_at("alarm", 7, 30)
    assert state.own_notification_at("alarm", 19, 30)
    assert not state.own_notification_at("alarm", 7, 30, "am")
