"""M110 (2026-10-01, DEV-F run v4d, window/v4d-devF): the arguments of alarms, timers, reminders and the clock.

The failures of the run in this scope lost the datum at one of these places, each fixed here in general:

1. The clock reader: «pa las 6 y 40» (no lead), «quarter past nine» (English minutes before the hour), «a las 6 y
   cuarto … temprano» (early is the morning; the question asked instead died in composition).
2. The fidelity check: «Tokyo» restated «Tokio» was trimmed as a name nobody said, and the clock of here was read.
3. The reminder readers: the day said beside the clock («el jueves a las 10:00») went into the title and the reminder
   rang the next day; «en una hora más» left «más» in the title; a reminder asked as notification.schedule was read as
   a timed task («yeah sure mañana», today); «recuérdame eso» was titled «eso».
4. A countdown («a 25-minute countdown») was no timer.
5. The record of a verified effect: a cancelled alarm went to the composer without its time («Cancelé la alarma.»), and
   a timer set by its length without the length (only its clock).
6. The follow-up: a moment counted from a thing named further back («una hora antes de la junta», «before kick-off»),
   a yes to BAXY's offer («Shall I move the alarm to 17:00?» → «Yeah, go on»), the length answering «How long…?»
   («go with 12»), a move said with its day («…to Friday at 7:15 pm») or what it is for after the new time.
7. The decision: the due read for what is still to ring, and a time only the decider wrote.

Every phrasing below is our own. The clock is fixed in every test (no test reads the machine's date or hour).
"""

from __future__ import annotations

from datetime import datetime as real_datetime, timedelta, timezone

import pytest

from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import arguments, decider
from baxy_mind.semantic.patterns import _fold, resolve_explicit_effects
from baxy_mind.semantic.temporal import (
    accepted_notification_offer,
    anchored_offset_request,
    answered_timer_length,
    notification_change,
    said_durations,
    spoken_clocks,
    timed_task,
)
from baxy_mind import context_decision
from baxy_mind import compose_situation
from baxy_mind import clock_checks
from baxy_mind import agenda_facts
from baxy_mind import weather_facts
from baxy_mind import reply_claims
from baxy_mind import deterministic_finals
from baxy_mind import conversation_contract
from baxy_mind import clock_facts


# Every mind module whose code reads this PC's clock: the clock is patched in each one.
_CLOCK_READERS = (
    agenda_facts, clock_checks, clock_facts, compose_situation, conversation_contract, deterministic_finals,
    reply_claims, weather_facts,
)

# Thursday 1 October 2026, 12:30 in Chile (UTC-3).
LOCAL = timezone(timedelta(hours=-3))
NOW = real_datetime(2026, 10, 1, 12, 30, tzinfo=LOCAL)


def _clock(text: str) -> tuple[int, int, bool]:
    clocks = spoken_clocks(_fold(text))
    assert len(clocks) == 1, clocks
    return clocks[0].hour, clocks[0].minute, clocks[0].resolved


def _local_due(literal: str, context: str = "") -> real_datetime:
    due = arguments._canonical_due_utc(literal, context or literal, now_utc=NOW)
    assert due is not None, literal
    return real_datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(LOCAL)


# ------------------------------------------------------------------ 1. the clock reader


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ponme la alarma pa las 7 y 20", (7, 20, False)),
        ("remind me at quarter past eight in the evening", (20, 15, True)),
        ("wake me at half past five in the morning", (5, 30, True)),
        ("the meeting is at ten to four pm", (15, 50, True)),
        ("at a quarter to one am", (0, 45, True)),
        ("despiértame a las 5 y media bien temprano", (5, 30, True)),
        ("I need to be up early, alarm at 6", (6, 0, True)),
    ],
)
def test_clocks_said_every_way_are_read(text: str, expected: tuple[int, int, bool]) -> None:
    assert _clock(text) == expected


@pytest.mark.parametrize("text", ["the box says 10 to 12 minutes", "between 10 to 12", "dame diez minutos"])
def test_numbers_that_are_no_clock_stay_none(text: str) -> None:
    assert spoken_clocks(_fold(text)) == ()


def test_early_does_not_move_an_evening_clock() -> None:
    assert _clock("llego temprano, a las 8 de la noche") == (20, 0, True)


# ------------------------------------------------------------------ 2. a name spelled with «i» for «y»


@pytest.mark.parametrize(
    ("text", "restated"),
    [("qué hora es en Kyoto ahora", "¿Qué hora es ahora en Kioto?"), ("time in Sydney please", "What time is it in Sidney?")],
)
def test_a_name_spelled_with_i_for_y_is_the_name_said(text: str, restated: str) -> None:
    kept = decider.faithful_request(restated, text, [], now=NOW.replace(tzinfo=None))
    assert kept.kind == "kept" and kept.request == restated


def test_a_different_name_is_still_introduced() -> None:
    assert decider.faithful_request("¿Qué hora es en Lima?", "qué hora es en Kyoto", [], now=NOW.replace(tzinfo=None)).kind != "kept"


# ------------------------------------------------------------------ 3. the reminder readers


@pytest.mark.parametrize(
    ("text", "title", "due"),
    [
        ("Recuérdame el viernes a las 18:00 llamar al plomero", "llamar al plomero", "el viernes a las 18:00"),
        ("recuérdame llamar al plomero a las 18:00 el viernes", "llamar al plomero", "a las 18:00 el viernes"),
        ("remind me to water the plants tomorrow at 7:30 pm", "water the plants", "tomorrow at 7:30 pm"),
        ("Recuérdame el sábado 3 de octubre a las 10:00 que pase por la tintorería", "pase por la tintorería",
         "el sábado 3 de octubre a las 10:00"),
        ("recuérdame regar las plantas en dos horas más", "regar las plantas", "en dos horas más"),
        # A day after «de» names the thing; it stays in what it is for.
        ("recuérdame la cena de mañana a las 20:00", "la cena de mañana", "a las 20:00"),
    ],
)
def test_the_day_beside_the_clock_is_the_due_never_the_title(text: str, title: str, due: str) -> None:
    task = timed_task(text)
    assert task is not None and (task.title, task.due) == (title, due)


def test_the_day_said_rings_that_day() -> None:
    friday = _local_due("el viernes a las 18:00")
    assert (friday.date().isoformat(), friday.hour, friday.minute) == ("2026-10-02", 18, 0)
    # Thursday at 10:00 already passed on Thursday at 12:30: the next one.
    assert _local_due("el jueves a las 10:00").date().isoformat() == "2026-10-08"
    # A weekday and a date that disagree hold no one moment.
    assert arguments._canonical_due_utc("el domingo 2 de octubre a las 15:00", "", now_utc=NOW) is None


def test_more_after_a_length_belongs_to_the_length() -> None:
    assert _local_due("en dos horas más") - NOW == timedelta(hours=2)
    task = timed_task("avísame en 10 minutos más o menos para sacar el pan")
    assert task is None or "más o menos" not in task.due


@pytest.mark.parametrize(
    "text",
    ["ok dale, recuérdame eso mañana a las 9:00", "sí, claro, mañana a las 9:00", "yes sure, tomorrow at 9 pm"],
)
def test_an_answer_word_or_a_pointer_is_no_title(text: str) -> None:
    assert timed_task(text) is None


def test_a_reminder_asked_as_a_notification_is_read_as_a_reminder() -> None:
    read = arguments._explicit_arguments_from_evidence(
        "notification.schedule", "Crea un recordatorio para pagar la luz mañana a las 8:00",
    )
    assert read is not None and read["kind"] == "reminder" and read["title"] == "pagar la luz"
    assert "8:00" in read["dueUtc"]


# ------------------------------------------------------------------ 4. a countdown is a timer


@pytest.mark.parametrize(
    ("text", "minutes"),
    [("start a 40-minute countdown for the bread", 40), ("pon una cuenta regresiva de 5 minutos", 5)],
)
def test_a_countdown_is_a_timer_of_its_length(text: str, minutes: int) -> None:
    read = arguments._explicit_notification_schedule_arguments(text)
    assert read is not None and read["kind"] == "alarm"
    assert _local_due(str(read["dueUtc"])) - NOW == timedelta(minutes=minutes)


# ------------------------------------------------------------------ 5. what the composer is given


def test_the_lengths_the_person_wrote_are_read_as_written() -> None:
    assert said_durations("avísame en 15 minutos y en una hora más") == (("15 minutos", 15), ("una hora", 60))
    assert said_durations("a 40-minute countdown") == (("40-minute", 40),)


@pytest.mark.parametrize(
    ("user_text", "after", "language", "expected"),
    [
        ("avísame en 20 minutos para sacar la ropa", timedelta(minutes=19, seconds=50), "es", "20 minutos"),
        ("set a timer, go with 9", timedelta(minutes=8, seconds=55), "en", "9 minutes"),
        ("en una hora", timedelta(minutes=59, seconds=40), "es", "una hora"),
        ("ponle 90", timedelta(minutes=90), "es", "1 hora y 30 minutos"),
        ("recuérdame a las 13:00 la reunión", timedelta(minutes=30), "es", None),
        ("mañana", timedelta(hours=20), "es", None),
    ],
)
def test_a_timer_set_by_its_length_is_told_with_it(
    monkeypatch: pytest.MonkeyPatch, user_text: str, after: timedelta, language: str, expected: str | None,
) -> None:
    for module in _CLOCK_READERS:
        monkeypatch.setattr(module, "_local_now", lambda: NOW)
    due = (NOW + after).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    observed = {"version": 1, "kind": "alarm", "title": "temporizador", "dueUtc": due, "nextRunUtc": due}
    situation = {"operation": "notification.schedule", "verified": True, "succeeded": True, "observed": observed}
    seen = agenda_facts._project_scheduled_notification(observed, situation, language, user_text)
    assert seen.get("ringsIn") == expected


def test_a_cancelled_alarm_is_told_by_its_time(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in _CLOCK_READERS:
        monkeypatch.setattr(module, "_local_now", lambda: NOW)
    tomorrow = real_datetime(2026, 10, 2, 7, 5, tzinfo=LOCAL).astimezone(timezone.utc).isoformat()
    observed = {"version": 1, "kind": "alarm", "hour": 7, "minute": 5, "expectedNextRunUtc": tomorrow,
                "taskName": "BAXY-Alarm-x", "canceled": True}
    situation = {"operation": "notification.cancel.at", "verified": True, "succeeded": True, "observed": observed}
    assert agenda_facts._project_cancelled_notification(observed, situation, "es") == {
        "canceled": True, "kind": "alarma", "time": "07:05", "day": "mañana",
    }
    # The time it was told by is no invented clock in the reply.
    assert "07:05" in agenda_facts._observed_local_clocks(situation)
    bare = {"kind": "reminder", "hour": 21, "minute": 0}
    assert agenda_facts._project_cancelled_notification(bare, {}, "en") == {"kind": "reminder", "time": "21:00"}


# ------------------------------------------------------------------ 6. the follow-up


def test_a_moment_counted_from_a_thing_named_further_back() -> None:
    earlier = [
        "Listo, se lo dije a Rodrigo.",
        "dile a rodrigo que llego tarde",
        "La reunión de directorio es el martes a las 16:00 en la sala 3.",
    ]
    assert anchored_offset_request("y avísame media hora antes de la reunión", earlier[0], earlier) == (
        "avísame el martes a las 15:30 para la reunión"
    )
    assert anchored_offset_request(
        "ping me ten minutes before boarding", "Your flight to Lima starts boarding at 21:10.",
    ) == "ping me at 21:00 for the boarding"


@pytest.mark.parametrize(
    ("text", "reply"),
    [
        ("avísame 10 minutos antes de que llegue", "El bus llega a las 18:00."),
        ("avísame media hora antes de la cena", "La reunión es a las 16:00."),
    ],
)
def test_a_count_from_nothing_named_is_not_anchored(text: str, reply: str) -> None:
    assert anchored_offset_request(text, reply, [reply]) is None


def test_a_yes_to_the_offer_of_a_notification_is_that_notification() -> None:
    offered = accepted_notification_offer("sí, porfa", "Tu vuelo sale a las 7:00. ¿Te pongo una alarma a las 5:00?")
    assert offered == "pon la alarma a las 05:00"
    assert resolve_explicit_effects(offered, ("notification.schedule",)) is not None
    assert accepted_notification_offer("sure, go on", "The match is on Sunday at 18:00. Want me to set a reminder for "
                                                      "17:30?") == "set the reminder on sunday at 17:30"
    assert accepted_notification_offer("no", "¿Te pongo una alarma a las 5:00?") is None
    assert accepted_notification_offer("sí", "El vuelo sale a las 7:00. ¿Algo más?") is None


def test_the_length_that_answers_how_long_is_the_timer() -> None:
    assert answered_timer_length(
        "unos 8, que me gustan blandos", "¿Cuántos minutos le pongo al temporizador para los huevos?", [],
    ) == "pon un temporizador de 8 minutos para los huevos"
    assert answered_timer_length(
        "make it 20", "How long for the rice?", ["and another one for the rice", "Timer set: 10 minutes for the beans."],
    ) == "set a 20 minute timer for the rice"
    # Nothing in the conversation was a timer, or the answer opens with no length.
    assert answered_timer_length("20", "How long is the film?", ["what film is on tonight?"]) is None
    assert answered_timer_length("una para mí", "¿Cuántos minutos le pongo al temporizador?", []) is None


def test_a_move_keeps_its_day_and_what_it_is_for() -> None:
    moved = notification_change("Cambia el recordatorio de las 9:00 a las 9:30 para la reunión con Ana")
    assert moved is not None and moved.schedule_arguments() == {
        "dueUtc": "a las 9:30", "kind": "reminder", "title": "recordatorio para la reunión con Ana",
    }
    moved = notification_change("Move the alarm to Monday at 6:45 am")
    assert moved is not None and moved.schedule_arguments()["dueUtc"] == "Monday at 6:45 am"
    assert _local_due("Monday at 6:45 am").date().isoformat() == "2026-10-05"


# ------------------------------------------------------------------ 7. the decision


class _Decider:
    """A contextual decider that answers one recorded decision."""

    def __init__(self, request: str, decision: str, operations: tuple[str, ...] = ()) -> None:
        self.decided = decider.ContextDecision(request=request, decision=decision, operations=operations, question="")
        self.decisions = 0

    def decide_in_context(self, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        self.decisions += 1
        return self.decided

    @staticmethod
    def chat(*_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        return "Vale.", []

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
        return "¿A qué hora la pongo?"


TOOLS = ("notification.schedule", "reminder.create", "notification.list", "notification.list.due",
         "notification.cancel.at", "calendar.event.create", "system.time", "web.search")


def _decided(text: str, history: list[tuple[str, str]], model: _Decider) -> dict[str, object]:
    tools = [
        {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                          "description": f"Operación {name}.", "parameters": {
                                              "type": "object", "properties": {}, "required": []}}}
        for name in TOOLS
    ]
    turns = [{"role": role, "content": content} for role, content in history]
    return context_decision._context_decided_result(
        {"id": "m110", "text": text, "history": [*turns, {"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(tools),
    )


def test_the_yes_to_an_offered_alarm_is_decided_without_the_decider() -> None:
    model = _Decider("¿Qué alarma?", "clarify")
    history = [("user", "a qué hora sale mi vuelo"), ("assistant", "Sale a las 7:00. ¿Te pongo una alarma a las 5:00?")]
    result = _decided("dale, sí", history, model)
    assert result["kind"] == "action" and result["operation"] == "notification.schedule"
    assert result["objective"] == "pon la alarma a las 05:00" and model.decisions == 0


def test_what_is_still_to_ring_is_read_from_the_scheduled_list() -> None:
    model = _Decider("How long until the tea timer rings?", "action", ("notification.list.due",))
    result = _decided("how long till the tea is ready?", [("assistant", "Timer set: 4 minutes for the tea.")], model)
    assert result["operation"] == "notification.list"
    overdue = _Decider("¿Qué recordatorios vencidos tengo?", "action", ("notification.list.due",))
    assert _decided("qué recordatorios vencidos tengo", [], overdue)["operation"] == "notification.list.due"


def test_a_time_only_the_decider_wrote_is_asked() -> None:
    model = _Decider("Pon una alarma el sábado 3 de octubre a las 6:00.", "action", ("notification.schedule",))
    history = [("user", "¿cómo estará el clima en Curicó el sábado?"), ("assistant", "El sábado: 15 °C y nublado.")]
    result = _decided("ya, ponme una alarma para ese día tempranito", history, model)
    assert result["kind"] == "clarify" and result["effectOperations"] == []


def test_a_moment_counted_from_the_named_thing_is_decided_by_the_readers() -> None:
    model = _Decider("Pon un recordatorio antes de la reunión.", "clarify")
    history = [
        ("assistant", "La reunión de directorio es el martes a las 16:00 en la sala 3."),
        ("user", "dile a rodrigo que llego tarde"),
        ("assistant", "Listo, se lo dije a Rodrigo."),
    ]
    result = _decided("y avísame media hora antes de la reunión", history, model)
    assert result["kind"] == "action" and result["objective"] == "avísame el martes a las 15:30 para la reunión"
