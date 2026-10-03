"""M144 (D61/D61b, 2026-10-03, DEV-H run v4p): alarms, reminders and tasks along a conversation; nothing given is asked.

Rows of DEV-H where the isolated decider was right and the product asked or erred:

1. H-w38-t2 «half three» answering «what time shall I set that for?»: British English half past three was no clock, so
   the decider's «…at 3:30 PM» was judged a clock nobody said and the turn asked. ``temporal`` reads «half three».
2. H-w38-t3 «and set another one for the day after, same time» restated «Set another dentist reminder for tomorrow at
   3:30pm.»: «another» and the English noun before «reminder» («a dentist reminder») were read by no reminder reader.
3. H-w13-t2 «pa el quince, tipo ocho am…» restated «…el 15 de octubre a las 8:00…»: a day of the month said alone was
   no date said, so the person's words were the objective and «¿Cuándo es el quince?» was asked.
4. H-w32-t4 «no era eso, quería que me lo pongas de recordatorio el jueves»: the reminder with its day and no hour asks
   only the hour, as the same request said first does (no «día y hora»).
5. H-w45-t1 «tengo dentista el jueves a las 4:30, so ponme un reminder» → 04:30: a clock written on the dial keeps the
   part of the day the decider read (16:30 for a dentist, 04:50 for an alarm before a flight).
6. H-w30-t2 «mejor ponlo para mañana» after «Anotado: pagar la luz.»: the day said of the task just made is its new day.
7. H-w06-t4 «a las 3» after «recuérdame comprar tinto para la oficina», which BAXY answered by noting a task: a clock
   alone after a reminder asked without its hour is that hour, asked for or not.
8. H-w44-t2 «remind me twenty minutes before that» after «Kick-off is at 8pm.»: the count from the conversation agreed
   with the decider's moment and still replaced its request («remind me at 19:40», titled «remind me»).
9. H-w29-t2 «no espera, mejor a las 7:30» after an alarm at 19:00: «7:30» was 07:30 (past), so the move of the alarm
   just set was not read. The cancel that failed in the App was the environment: the run's shared store held another
   alarm at 19:00 («Alarma de las 7.», another conversation), and ``notification.cancel.at`` refuses two at one time.
10. H-w45-t2 (seen on the way): «Cambia el recordatorio del dentista para el jueves a las 15:30.» moved it to today.

H-w13-t3 «y ponme otro dos días antes de eso, a la misma hora» already holds with the written history (the App lost it
after t2 failed). Every phrasing beyond the rows is our own; clocks are fixed where the result depends on them.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import arguments, decider, notes, temporal
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState

LOCAL = timezone(timedelta(hours=-3))
# Saturday 3 October 2026, 11:00 in Chile (UTC-3).
NOW = datetime(2026, 10, 3, 11, 0, tzinfo=LOCAL)

OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)
SCHEDULE = {"type": "object", "properties": {
    "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
    "kind": {"type": "string", "enum": ["alarm", "reminder"]},
    "recurrence": {"type": "string", "enum": ["daily", "hourly"]},
    "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True}},
    "required": ["dueUtc", "kind", "title"], "additionalProperties": False}
TASK_UPDATE = {"type": "object", "properties": {
    "details": {"type": "string", "x-maxUtf8Bytes": 65536}, "due": {"type": ["null", "string"], "maxLength": 64},
    "expectedVersion": {"type": "integer", "minimum": 1}, "taskId": {"type": "string", "maxLength": 36},
    "title": {"type": "string", "x-maxUtf8Bytes": 1024}},
    "required": ["details", "due", "expectedVersion", "taskId", "title"], "additionalProperties": False}


def _tool(operation: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision
        self.formulated: list[tuple] = []

    def decide_in_context(self, *_a, **_k):
        return self.decision

    def prepare_decision(self, *_a, **_k):
        return None

    def formulate_explicit_clarification_question(self, objective, operations, missing):
        self.formulated.append((objective, operations, missing))
        return "What time should it ring?" if objective.startswith("Set") else "¿A qué hora te lo recuerdo?"

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿Qué quieres que haga?"

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


class _NoExtraction:
    """The arguments step must not need the model."""

    def extract_direct_arguments(self, *_a, **_k):
        raise AssertionError("the readers had the arguments")

    def formulate_missing_argument_question(self, *_a, **_k):
        raise AssertionError("nothing is to be asked")


def _turn(said: list[str], decision: ContextDecision) -> tuple[dict, _Decider]:
    """``said``: the conversation, user first and alternating, ending in the person's message."""

    history = [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(said)]
    tools = {name: _tool(name) for name in OPERATIONS}
    model = _Decider(decision)
    result = sidecar._prepare_turn_result(
        {"id": "m144", "text": said[-1], "history": history},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (), tool_by_name=tools,
        dialogue_state=DialogueState(),
    )
    return result, model


def _arguments(operation: str, objective: str, said: list[str], decided: dict[str, Any] | None = None,
               schema: dict[str, Any] = SCHEDULE, state: DialogueState | None = None) -> tuple[dict | None, str]:
    if decided is not None:
        sidecar._remember_decided_arguments(objective, (operation,), tuple(decided.items()))
    history = [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(said)]
    return sidecar._direct_arguments_result(
        {"operation": operation, "text": objective, "history": history},
        llm=_NoExtraction(), tool=_tool(operation, schema), dialogue_state=state or DialogueState(),
    )


def _local(due: str) -> datetime:
    return datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone()


# ------------------------------------------------------------------ 1. «half three»


@pytest.mark.parametrize(
    ("text", "hour", "minute", "resolved"),
    [
        ("half three", 3, 30, False),  # DEV-H H-w38-t2
        ("half seven tonight", 19, 30, True),
        ("at half nine in the morning", 9, 30, True),
        ("half past three", 3, 30, False),  # unchanged
        ("quarter to five", 4, 45, False),  # unchanged
    ],
)
def test_half_an_hour_word_is_half_past_it(text: str, hour: int, minute: int, resolved: bool) -> None:
    clocks = temporal.spoken_clocks(temporal._fold(text))
    assert [(clock.hour, clock.minute, clock.resolved) for clock in clocks] == [(hour, minute, resolved)]


def test_half_three_alone_is_only_a_clock() -> None:
    assert temporal.said_only_a_clock("half three")
    assert temporal.said_only_a_clock("half seven.")


@pytest.mark.parametrize("text", ["half one of them is broken", "cut it in half", "give me half an hour",
                                  "half the team is out", "half a dozen eggs"])
def test_half_of_something_is_no_clock(text: str) -> None:
    assert temporal.spoken_clocks(temporal._fold(text)) == ()
    assert not temporal.said_only_a_clock(text)


W38 = ["could you set a reminder for the dentist", "Of course — what time shall I set that for?"]


def test_h_w38_t2_half_three_sets_the_reminder_the_decider_read() -> None:
    restated = "Set a reminder for the dentist at 3:30 PM."
    fidelity = decider.faithful_request(restated, "half three", W38, now=NOW.replace(tzinfo=None))
    assert fidelity.kind == "kept"
    result, _ = _turn([*W38, "half three"], ContextDecision(restated, "action", ("notification.schedule",), ""))
    assert result["kind"] == "action" and result["operation"] == "notification.schedule"
    arguments_, question = _arguments("notification.schedule", restated, [*W38, "half three"])
    assert question == "" and (_local(arguments_["dueUtc"]).hour, _local(arguments_["dueUtc"]).minute) == (15, 30)


# ------------------------------------------------------------------ 2. «another», «a dentist reminder»


@pytest.mark.parametrize(
    ("objective", "title", "weekday", "clock"),
    [
        ("Set another dentist reminder for tomorrow at 3:30pm.", "dentist", None, (15, 30)),  # DEV-H H-w38-t3
        ("Set a gym reminder on Friday at 7pm.", "gym", 4, (19, 0)),
        ("Set one more reminder to call mom tomorrow at 6pm.", "call mom", None, (18, 0)),
        ("Ponme otro recordatorio para pagar el arriendo el 13 de octubre a las 8:00.", "pagar el arriendo", None,
         (8, 0)),
    ],
)
def test_another_reminder_and_its_noun_are_read(objective: str, title: str, weekday: int | None,
                                                 clock: tuple[int, int]) -> None:
    arguments_, question = _arguments("notification.schedule", objective, [objective])
    assert question == "" and arguments_["kind"] == "reminder" and arguments_["title"] == title
    due = _local(arguments_["dueUtc"])
    assert (due.hour, due.minute) == clock
    if weekday is not None:
        assert due.weekday() == weekday


@pytest.mark.parametrize("objective", ["Set a reminder at 5pm.", "Set another reminder at 5pm.",
                                       "Set a new reminder at 5pm."])
def test_a_reminder_for_nothing_named_still_has_no_title(objective: str) -> None:
    assert arguments._explicit_relative_reminder_arguments(objective) is None


# ------------------------------------------------------------------ 3. «el quince»

W13 = ["Baxy, ¿me pones un recordatorio para pagar el arriendo, por fa?",
       "Va, ¿en qué fecha y a qué hora te aviso lo del arriendo?"]


@pytest.mark.parametrize(
    ("text", "restated"),
    [
        ("pa el quince, tipo ocho am antes de salir pa la oficina",  # DEV-H H-w13-t2
         "Ponme un recordatorio el 15 de octubre a las 8:00 para pagar el arriendo."),
        ("el 20 a las 9 de la mañana", "Ponme un recordatorio el 20 de octubre a las 9:00 para pagar el arriendo."),
        ("on the 2nd, around 8 am", "Set a reminder on November 2 at 8:00 to pay the rent."),
        ("el día 13 a las 8", "Ponme un recordatorio el día 13 a las 8:00 para pagar el arriendo."),
    ],
)
def test_a_day_of_the_month_said_alone_is_the_next_one(text: str, restated: str) -> None:
    assert decider.faithful_request(restated, text, W13, now=NOW.replace(tzinfo=None)).kind == "kept"


@pytest.mark.parametrize(
    ("text", "restated"),
    [
        ("pa el quince, tipo ocho am", "Ponme un recordatorio el 16 de octubre a las 8:00 para pagar el arriendo."),
        ("tipo ocho am", "Ponme un recordatorio el día 15 a las 8:00 para pagar el arriendo."),
    ],
)
def test_another_day_than_the_one_said_is_still_introduced(text: str, restated: str) -> None:
    assert decider.faithful_request(restated, text, W13, now=NOW.replace(tzinfo=None)).kind != "kept"


def test_h_w13_t2_the_reminder_is_the_15th_at_8() -> None:
    restated = "Ponme un recordatorio el 15 de octubre a las 8:00 para pagar el arriendo."
    arguments_, question = _arguments("notification.schedule", restated, [*W13, "pa el quince, tipo ocho am"])
    due = _local(arguments_["dueUtc"])
    assert question == "" and (due.month, due.day, due.hour) == (10, 15, 8)
    assert arguments_["title"] == "pagar el arriendo"


# ------------------------------------------------------------------ 4. a day and no hour asks only the hour

W32 = ["anotame en pendientes inscribirme a eso", "Listo, anoté «inscribirme a las Jornadas de Ingeniería» en pendientes."]
W32_EN = ["put signing up for the Engineering Days on my to-do list",
          "Done, I added «sign up for the Engineering Days» to your tasks."]


@pytest.mark.parametrize(
    ("before", "said", "restated"),
    [
        (W32, "no era eso, quería que me lo pongas de recordatorio el jueves",  # DEV-H H-w32-t4
         "Ponme un recordatorio el jueves para inscribirme a las Jornadas de Ingeniería."),
        (W32, "mejor ponme un recordatorio para mañana", "Recuérdame mañana inscribirme a las Jornadas de Ingeniería."),
        (W32_EN, "no, I meant a reminder on Friday", "Set a reminder on Friday to sign up for the Engineering Days."),
    ],
)
def test_a_reminder_with_its_day_and_no_hour_asks_the_hour(before: list[str], said: str, restated: str) -> None:
    result, model = _turn([*before, said], ContextDecision(restated, "action", ("notification.schedule",), "",
                                                            (("dueUtc", "2025-10-16T00:00:00Z"),)))
    assert result["kind"] == "clarify" and result["question"] in {"¿A qué hora te lo recuerdo?", "What time should it ring?"}
    assert result["objective"] == restated and result["intentOperations"] == ["notification.schedule"]
    assert model.formulated == [(restated, ("notification.schedule",), ("due_time",))]


@pytest.mark.parametrize(
    ("said", "restated", "arguments_"),
    [
        # The hour is said, in the message or in the restatement.
        ("ponlo el jueves a las 5", "Ponme un recordatorio el jueves a las 5 para inscribirme.", ()),
        ("el jueves a las 5 de la tarde", "Ponme un recordatorio el jueves a las 17:00 para inscribirme.", ()),
        # The decider's moment has an hour of its own («a la misma hora»).
        ("y otro el jueves, a la misma hora", "Ponme otro recordatorio el jueves para inscribirme.",
         (("dueUtc", "2026-10-08T17:00:00Z"),)),
    ],
)
def test_a_reminder_with_its_hour_is_not_asked(said: str, restated: str, arguments_: tuple) -> None:
    result, _ = _turn([*W32, said], ContextDecision(restated, "action", ("notification.schedule",), "", arguments_))
    assert result["kind"] == "action"


# ------------------------------------------------------------------ 5. the dial clock keeps the decider's part of day


@pytest.mark.parametrize(
    ("objective", "decided_due", "clock"),
    [
        ("Ponme un recordatorio el jueves a las 4:30 para mi cita con el dentista.",  # DEV-H H-w45-t1
         "2025-09-11T16:30:00Z", (16, 30)),
        ("Remind me on Thursday at 4:30 about the dentist.", "2025-09-11T16:30:00", (16, 30)),
        # The decider's morning stays the morning (DEV-F F-w35-t2, F-w12-t1).
        ("Pon una alarma mañana a las 4:50.", "2025-09-12T04:50:00Z", (4, 50)),
        ("Pon una alarma mañana a las 6:40.", "2025-09-12T06:40:00Z", (6, 40)),
        # No decider value: as written.
        ("Ponme un recordatorio el jueves a las 4:30 para el dentista.", None, (4, 30)),
    ],
)
def test_a_dial_clock_takes_the_deciders_part_of_the_day(objective: str, decided_due: str | None,
                                                         clock: tuple[int, int]) -> None:
    decided = None if decided_due is None else {"dueUtc": decided_due, "kind": "reminder", "title": "dentista"}
    arguments_, question = _arguments("notification.schedule", objective, [objective], decided)
    due = _local(arguments_["dueUtc"])
    assert question == "" and (due.hour, due.minute) == clock


def test_a_clock_with_its_part_of_the_day_is_never_moved() -> None:
    objective = "Ponme un recordatorio el jueves a las 4:30 de la tarde para el dentista."
    arguments_, _ = _arguments("notification.schedule", objective, [objective],
                               {"dueUtc": "2025-09-11T04:30:00Z", "kind": "reminder", "title": "dentista"})
    assert _local(arguments_["dueUtc"]).hour == 16


# ------------------------------------------------------------------ 6. the day of the task just made


@pytest.mark.parametrize(
    ("text", "days"),
    [
        ("mejor ponlo para mañana", 1),  # DEV-H H-w30-t2
        ("pásalo para pasado mañana", 2),
        ("actually make it due tomorrow", 1),
    ],
)
def test_the_day_said_of_the_task_just_made_is_its_new_day(text: str, days: int) -> None:
    assert notes.task_change(text, "pagar la luz", today=NOW.date()) == {
        "due": (NOW.date() + timedelta(days=days)).isoformat()}


@pytest.mark.parametrize(
    ("text", "changed"),
    [
        ("change it to call mom on monday", {"title": "call mom on monday"}),
        ("Add to the Walmart list.", {"details": "Walmart list"}),
        ("mejor a las 5 de la tarde", {}),
    ],
)
def test_a_name_a_list_or_a_clock_is_no_new_day(text: str, changed: dict) -> None:
    assert notes.task_change(text, "pagar la luz", today=NOW.date()) == changed


def test_h_w30_t2_the_task_moves_to_tomorrow_keeping_the_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notes, "task_due_date", lambda value, today=None: temporal.task_due_date(value, today=NOW.date()))
    state = DialogueState()
    state.expect("anota en mis pendientes pagar la luz", ["task.create"])
    state.record({"operation": "task.create", "verified": True, "succeeded": True, "observed": {
        "taskId": "0fd37d83-6f96-4b82-a1c6-9de123985517", "title": "pagar la luz", "details": "", "version": 1}})
    state.expect("Cambia la fecha de la tarea «pagar la luz» a mañana.", ["task.update"])
    said = ["anota en mis pendientes pagar la luz", "Anotado: pagar la luz.", "mejor ponlo para mañana"]
    arguments_, question = _arguments("task.update", "Cambia la fecha de la tarea «pagar la luz» a mañana.", said,
                                      schema=TASK_UPDATE, state=state)
    assert question == "" and arguments_ == {"taskId": "0fd37d83-6f96-4b82-a1c6-9de123985517", "expectedVersion": 1,
                                             "title": "pagar la luz", "details": "", "due": "2026-10-04"}


# ------------------------------------------------------------------ 7. a clock after a reminder asked without one


@pytest.mark.parametrize(
    ("said", "restated"),
    [
        (["recuérdame comprar tinto para la oficina", "Añadí «Comprar tinto para la oficina.».", "a las 3"],
         "Recuérdame comprar tinto para la oficina a las 3."),  # DEV-H H-w06-t4, the App's history
        (["remind me to call mom", "Added «Call mom» to your tasks.", "at 5"], "Remind me to call mom at 5."),
        (["ponme una alarma", "Listo.", "a las siete y media"], "Pon una alarma a las 7:30."),
    ],
)
def test_a_clock_alone_completes_the_reminder_asked_just_before(said: list[str], restated: str) -> None:
    result, _ = _turn(said, ContextDecision(restated, "action", ("notification.schedule",), ""))
    assert result["kind"] == "action" and result["operation"] == "notification.schedule"


@pytest.mark.parametrize(
    "said",
    [
        ["¿cómo le va a Rappi en México?", "Le va bien, sigue arriba en usuarios.", "las dos menos cuarto"],
        ["recuérdame a las 5 llamar a mamá", "Listo, te aviso a las 17:00.", "a las 3"],
    ],
)
def test_a_clock_alone_after_anything_else_is_asked(said: list[str]) -> None:
    result, _ = _turn(said, ContextDecision("Pon una alarma a las 3.", "action", ("notification.schedule",), ""))
    assert result["kind"] == "clarify"


# ------------------------------------------------------------------ 8. the count agrees with the decider

W44 = ["what time does the arsenal match kick off tonight", "Kick-off is at 8pm."]


def test_h_w44_t2_the_deciders_request_stands_when_its_moment_is_the_count() -> None:
    restated = "Remind me at 7:40pm tonight about the Arsenal match."
    result, _ = _turn([*W44, "remind me twenty minutes before that"],
                      ContextDecision(restated, "action", ("notification.schedule",), ""))
    assert result["objective"] == restated and result["operation"] == "notification.schedule"


@pytest.mark.parametrize("restated", ["Remind me at 7:20pm tonight about the Arsenal match.",
                                      "Remind me tomorrow at 7:40pm about the Arsenal match."])
def test_a_moment_the_count_does_not_confirm_is_the_counts(restated: str) -> None:
    result, _ = _turn([*W44, "remind me twenty minutes before that"],
                      ContextDecision(restated, "action", ("notification.schedule",), ""))
    assert result["objective"] != restated and "19:40" in result["objective"]


# ------------------------------------------------------------------ 9. «mejor a las 7:30» after an alarm at 19:00


def _alarm_state(due_utc: str, request: str) -> DialogueState:
    state = DialogueState()
    state.expect(request, ["notification.schedule"])
    state.record({"operation": "notification.schedule", "verified": True, "succeeded": True,
                  "observed": {"kind": "alarm", "title": "Clases", "dueUtc": due_utc}})
    return state


@pytest.mark.parametrize(
    ("text", "moved"),
    [
        ("no espera, mejor a las 7:30", "cancela la alarma «Clases» de las 19:00 y vuelve a ponerla a las 19:30"),
        ("no wait, make it 7:30", "cancel the alarm «Clases» set for 19:00 and set it again at 19:30"),
        ("mejor a las 19:15", "cancela la alarma «Clases» de las 19:00 y vuelve a ponerla a las 19:15"),
    ],
)
def test_a_dial_clock_moves_the_alarm_just_set_in_its_part_of_the_day(text: str, moved: str) -> None:
    now = datetime(2026, 10, 3, 10, 50, tzinfo=LOCAL)
    state = _alarm_state("2026-10-03T22:00:00Z", "¿me pones una alarma a las 7 porfa?")
    assert state.moved_notification_request(text, now=now, zone=LOCAL) == moved


def test_a_morning_alarm_moved_by_a_dial_clock_stays_in_the_morning() -> None:
    now = datetime(2026, 10, 3, 22, 0, tzinfo=LOCAL)
    state = _alarm_state("2026-10-04T09:45:00Z", "set an alarm for 6:45 tomorrow morning")
    assert state.moved_notification_request("Actually, make it 6:30.", now=now, zone=LOCAL) == (
        "cancel the alarm «Clases» set for 06:45 and set it again at 06:30"
    )


# ------------------------------------------------------------------ 10. the day of a moved reminder


@pytest.mark.parametrize(
    ("text", "title", "day"),
    [
        ("Cambia el recordatorio del dentista para el jueves a las 15:30.", "del dentista", "el jueves"),
        ("Cambia la alarma para mañana a las 6.", "", "mañana"),
        # Unchanged: no day said, a day after «de» is what it is for, and English says the day after «to».
        ("Cambia la alarma de las 7 a las 7:30.", "", ""),
        ("Cambia el recordatorio del cumple de mañana a las 10.", "del cumple de mañana", ""),
        ("Move the reminder to pack the rain jackets to Friday at 7:15 pm.", "to pack the rain jackets", "Friday"),
    ],
)
def test_the_day_before_the_new_time_is_the_new_moments(text: str, title: str, day: str) -> None:
    change = temporal.notification_change(text)
    assert change is not None and (change.title, change.day) == (title, day)
