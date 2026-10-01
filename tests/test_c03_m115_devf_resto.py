"""M115 (2026-10-01): DEV-F v4e2 items left after M113–M114, fixed in general and tested in our own phrasings.

Evidence: the official-window DEV-F run v4e2 (%LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v4e2-devF, code a1739b28)
and its offline replays (recorded decider decisions, no model).

1. w12-t2 «no, cachai que mejor a las 6 y cuarto…», w15-t4 «…till 7:15, push it there», w07-t4 «…: córrelo a las 6 y
   cuarto»: the decider planned cancel + set again, and the plan asked «¿A qué hora y qué tipo…?» or cancelled an alarm
   when a reminder had been set. Once the plan moves the notification just set, its new time is the one clock said
   anywhere in the message; the kind, title and old time are those verified.
2. w43-t3 «adelantala un minuto que la intro es eterna» → «¿Cuántos segundos…?». Seconds said as minutes are said.
3. s022 «…renovar el passport antes del 15 de noviembre…» → the task kept no date. A task's day is written as the store
   reads it (YYYY-MM-DD), and that day written so is said when the person named it.
4. w47-t2 «Contéstale por WhatsApp que sí, que me viene genial…» → drafted to «me». A pronoun is no recipient.
5. w36-t1 «ponme llueve sobre la ciudad de los bunkers q esta nublao y me bajo la nostalgia» → a poem. Why the person
   wants it, said after what to play, is not what to play.
6. w26-t2 «…con un resultado de 2-1 frente a Junior» vetoed as the search shown. A match's score is no search result.
No test reads the machine's date or hour.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.llm import _search_report_shows_the_search
from baxy_mind.planner import validate_argument_grounding
from baxy_mind.semantic import patterns, temporal
from baxy_mind.semantic.arguments import partial_explicit_arguments
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.messaging import pronoun_recipient


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


SCHEDULE = _schema(
    {
        "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
        "kind": {"type": "string", "enum": ["alarm", "reminder"]},
        "recurrence": {"type": "string", "enum": ["daily", "hourly"]},
        "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
    },
    ["dueUtc", "kind", "title"],
)
CANCEL_AT = _schema(
    {
        "hour": {"type": "integer", "minimum": 0, "maximum": 23},
        "kind": {"type": "string", "enum": ["alarm", "reminder"]},
        "minute": {"type": "integer", "minimum": 0, "maximum": 59},
        "period": {"type": "string", "enum": ["am", "pm"]},
    },
    ["hour", "kind"],
)
SEEK = _schema({"seconds": {"type": "integer", "minimum": -3600, "maximum": 3600}}, ["seconds"])
TASK_CREATE = _schema(
    {
        "details": {"type": "string", "x-maxUtf8Bytes": 65536},
        "due": {"type": ["null", "string"], "maxLength": 64},
        "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
    },
    ["title"],
)
DRAFT = _schema(
    {
        "channel": {"type": "string", "enum": ["whatsapp", "discord"]},
        "recipient": {"type": "string", "x-maxUtf8Bytes": 256},
        "text": {"type": "string", "x-maxUtf8Bytes": 4096},
    },
    ["channel", "recipient", "text"],
)
CHILE = timezone(timedelta(hours=-3))
NOW = datetime(2027, 3, 3, 15, 0, tzinfo=CHILE)


# ------------------------------------------------------------------ 1. the plan that moves the notification just set


def _set(kind: str, title: str, due: datetime, request: str) -> DialogueState:
    state = DialogueState()
    state.expect(request, ["notification.schedule"])
    state.record({
        "kind": "operation", "operation": "notification.schedule", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"version": 1, "kind": kind, "title": title, "dueUtc": due.astimezone(timezone.utc).isoformat(),
                     "taskName": "BAXY-Reminder-m115"},
    })
    state.expect("…", ["notification.cancel.at", "notification.schedule"])
    return state


@pytest.mark.parametrize(
    ("kind", "title", "old", "said", "cancel", "due"),
    [
        # A reminder at 18:30 moved «a las 6 y cuarto» with what happened in between: the reminder is cancelled, never an
        # alarm, and set again at 18:15 (the part of the day nearer the old time).
        ("reminder", "llevar el chubasquero", (18, 30), "uy no, espera, que antes tengo que pasar al banco: muévelo a las 6 y cuarto",
         {"hour": 18, "minute": 30, "kind": "reminder"}, "2027-03-04T21:15:00Z"),
        # A clock said in the middle, the change at the end; «7:15» says no part of the day.
        ("reminder", "water the plants", (18, 0), "hmm no, I won't be back till 7:15, push it there",
         {"hour": 18, "kind": "reminder"}, "2027-03-04T22:15:00Z"),
        # An alarm early in the morning moved earlier, the reason after it.
        ("alarm", "alarma", (6, 50), "no, oye, mejor a las 6 y cuarto, que el bus pasa antes",
         {"hour": 6, "minute": 50, "period": "am", "kind": "alarm"}, "2027-03-04T09:15:00Z"),
    ],
)
def test_a_planned_move_takes_the_one_clock_said_and_what_was_verified(
    kind: str, title: str, old: tuple[int, int], said: str, cancel: dict, due: str,
) -> None:
    moment = datetime(2027, 3, 4, old[0], old[1], tzinfo=CHILE)
    state = _set(kind, title, moment, "ponlo para mañana")
    moved = state.retimed_notification(said, now=NOW, zone=CHILE, moving=True)
    assert moved is not None
    assert sidecar._retimed_step_arguments("notification.cancel.at", moved, CANCEL_AT) == cancel
    assert sidecar._retimed_step_arguments("notification.schedule", moved, SCHEDULE) == {
        "dueUtc": due, "kind": kind, "title": title,
    }


def test_without_a_planned_move_the_message_must_open_with_the_change() -> None:
    moment = datetime(2027, 3, 4, 18, 30, tzinfo=CHILE)
    state = _set("reminder", "llevar el chubasquero", moment, "ponlo para mañana")
    said = "uy no, espera, que antes tengo que pasar al banco: muévelo a las 6 y cuarto"
    assert state.retimed_notification(said, now=NOW, zone=CHILE) is None


def test_a_planned_move_with_no_single_new_clock_moves_nothing() -> None:
    old = datetime(2027, 3, 4, 18, 30, tzinfo=CHILE)
    assert temporal.moved_to_clock("no, mejor más tarde", old) is None
    assert temporal.moved_to_clock("entre las 7 y las 8, no sé", old) is None
    assert temporal.moved_to_clock("ponla en 20 minutos a las 7", old) is None
    # The old time said back is not the new one: «de las 18:30 a las 18:15» moves it to 18:15.
    moved = temporal.moved_to_clock("Cambia la alarma de las 18:30 a las 18:15.", old)
    assert moved is not None and (moved.hour, moved.minute) == (18, 15)


# ------------------------------------------------------------------ 2. seconds said as minutes


def test_seconds_said_as_minutes_are_said() -> None:
    assert validate_argument_grounding({"seconds": 60}, SEEK, "Adelanta un minuto la canción.")
    assert validate_argument_grounding({"seconds": -120}, SEEK, "atrásala dos minutos")
    assert not validate_argument_grounding({"seconds": 30}, SEEK, "Adelanta un minuto la canción.")
    assert partial_explicit_arguments("media.seek.relative", "córrela un minuto hacia adelante, la intro es larga", SEEK) == {
        "seconds": 60,
    }
    assert partial_explicit_arguments("media.seek.relative", "rewind it two minutes", SEEK) == {"seconds": -120}
    # Which way is not said: nothing is known.
    assert partial_explicit_arguments("media.seek.relative", "muévela un minuto", SEEK) == {}


# ------------------------------------------------------------------ 3. the day of a task


def test_a_tasks_day_is_written_as_the_store_reads_it() -> None:
    today = date(2027, 3, 3)  # a Wednesday
    assert temporal.task_due_date("15 de noviembre", today=today) == "2027-11-15"
    assert temporal.task_due_date("el viernes", today=today) == "2027-03-05"
    assert temporal.task_due_date("mañana", today=today) == "2027-03-04"
    assert temporal.task_due_date("2027-11-15", today=today) == "2027-11-15"
    assert temporal.task_due_date("pronto", today=today) is None
    request = "añade a pendientes: sacar el pasaporte antes del 15 de noviembre, que viajo en diciembre"
    assert temporal.iso_day_said("2027-11-15", request, today=today)
    assert not temporal.iso_day_said("2027-12-15", request, today=today)
    assert not temporal.iso_day_said("15 de noviembre", request, today=today)


def test_a_task_day_nobody_can_tell_is_left_out_and_one_said_is_kept() -> None:
    now = datetime(2027, 3, 3, 18, 0, tzinfo=timezone.utc)
    kept = sidecar._normalize_grounded_operation_arguments(
        "task.create", {"title": "Hacer los ejercicios", "due": "el viernes"}, "anota hacer los ejercicios para el viernes",
        now_utc=now,
    )
    assert kept == {"title": "Hacer los ejercicios", "due": "2027-03-05"}
    dropped = sidecar._normalize_grounded_operation_arguments(
        "task.create", {"title": "Comprar pan", "due": "pronto"}, "anota comprar pan pronto", now_utc=now,
    )
    assert dropped == {"title": "Comprar pan"}


# ------------------------------------------------------------------ 4. a pronoun is no recipient


def test_a_pronoun_is_no_recipient() -> None:
    assert pronoun_recipient("me") and pronoun_recipient("Le") and pronoun_recipient("him")
    assert not pronoun_recipient("Paula")
    said = "Respóndele por WhatsApp que sí, que me va perfecto, pero no lo mandes"
    assert not validate_argument_grounding(
        {"channel": "whatsapp", "recipient": "me", "text": "sí, me va perfecto"}, DRAFT, said,
    )
    assert validate_argument_grounding(
        {"channel": "whatsapp", "recipient": "Paula", "text": "llego tarde"}, DRAFT,
        "déjale escrito a Paula por WhatsApp que llego tarde",
    )


# ------------------------------------------------------------------ 5. why it is wanted is not what to play


def test_the_reason_after_a_long_title_is_not_the_title() -> None:
    query = patterns._desired_music_query(
        "ponme lamento boliviano de los enanitos verdes q hace frío afuera y me dio la nostalgia de los 90",
    )
    assert query is not None and query.casefold() == "lamento boliviano de los enanitos verdes"
    # A short request keeps its reading as it was.
    assert patterns._desired_music_query("ponme lamento boliviano") is not None


# ------------------------------------------------------------------ 6. a match's score is no search result


def test_a_score_is_no_search_result() -> None:
    payload = {
        "operation": "web.search",
        "seen": {
            "query": "cómo quedó colo colo ayer",
            "count": 1,
            "results": [{"title": "Colo-Colo venció a la U", "url": "https://www.example-deportes.cl/futbol/colo-colo",
                         "snippet": "Colo-Colo venció 3-1 a la U en el Monumental."}],
        },
    }
    assert not _search_report_shows_the_search(
        "Colo-Colo ganó en el Monumental con un resultado de 3-1 frente a la U.", payload, "cómo quedó colo colo ayer",
    )
    assert _search_report_shows_the_search(
        "Un resultado dice que Colo-Colo ganó, pero otro dice que empató.", payload, "cómo quedó colo colo ayer",
    )
