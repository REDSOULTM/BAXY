"""Uso real 2026-09-23 (MASSIVE es-ES replay): everyday requests to play music, add to a
list and schedule an alarm or a reminder that BAXY refused or questioned although nothing
was missing.

- A bare artist or title after a play verb is the thing to play (MUSIC1559: no provider
  named → the local YouTube player); an installed game or application said the same way
  is started, and a transport order («pon la canción anterior») is not asked what to play.
- A list entry is a local task and the list it goes on is its details (no list store in
  the catalog); a list with nothing on it asks what goes on it.
- One clock reader hears the minutes and the part of the day wherever it was said
  («a las cinco y media de la mañana», «esta tarde a las cinco», «a las diez a. m.»),
  and the day it falls on («el próximo domingo»; «de la mañana» is not tomorrow).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic.normalize import fold
from baxy_mind.semantic.patterns import resolve_explicit_effects
from baxy_mind.semantic.reading import read
from baxy_mind.semantic.temporal import spoken_clock, spoken_day

OPERATIONS = (
    "media.play.youtube", "media.play.query", "media.control", "streaming.play.named", "audio.volume",
    "game.launch", "app.open", "task.create", "task.list", "note.create", "reminder.create",
    "reminder.list", "notification.schedule", "media.status", "calendar.event.create",
)

# Exact wire schemas of the catalog operations these turns reach.
SCHEMAS = {
    "media.play.youtube": {
        "type": "object",
        "properties": {"query": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True}},
        "required": ["query"], "additionalProperties": False,
    },
    "media.control": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["next", "pause", "play", "previous", "stop", "toggle"]},
            "sourceApp": {"type": ["null", "string"], "x-maxUtf8Bytes": 256},
        },
        "required": ["action"], "additionalProperties": False,
    },
    "task.create": {
        "type": "object",
        "properties": {
            "details": {"type": "string", "x-maxUtf8Bytes": 65536},
            "due": {"type": ["null", "string"], "maxLength": 64},
            "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
        },
        "required": ["title"], "additionalProperties": False,
    },
    "reminder.create": {
        "type": "object",
        "properties": {
            "details": {"type": "string", "x-maxUtf8Bytes": 65536},
            "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
            "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
        },
        "required": ["dueUtc", "title"], "additionalProperties": False,
    },
    "notification.schedule": {
        "type": "object",
        "properties": {
            "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
            "kind": {"type": "string", "enum": ["alarm", "reminder"]},
            "recurrence": {"type": "string", "enum": ["daily", "hourly"]},
            "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
        },
        "required": ["dueUtc", "kind", "title"], "additionalProperties": False,
    },
}


# ---------------------------------------------------------------- play


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("pon rosalia", "rosalia"),
        ("puedes poner imogen heap", "imogen heap"),
        ("podrías poner la canción de michael jackson", "michael jackson"),
        ("poné Queen por favor", "Queen"),
        ("reproduce despacito", "despacito"),
        ("pon música rap", "música rap"),
    ],
)
def test_a_name_after_a_play_verb_is_played_on_youtube(text, query):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("media.play.youtube",)
    assert reading.clarification is None
    assert sidecar._ground_explicit_arguments(
        "media.play.youtube", reading.effects.evidence[0], SCHEMAS["media.play.youtube"],
    ) == {"query": query}


@pytest.mark.parametrize(
    "text",
    [
        "pon pausa", "pon mute", "pon silencio", "pon esto", "pon la radio", "pon el volumen al 50",
        "pon netflix", "pon subtítulos", "pon música ahora", "pon trece", "pon una alarma", "toca fm",
        "pon Tesla en vivo", "reproduce exactamente Beat It",
    ],
)
def test_a_control_a_setting_or_an_object_is_never_a_name_to_play_on_youtube(text):
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is None or "media.play.youtube" not in effects.operations


def test_an_installed_game_or_application_said_after_pon_is_started():
    games = (("epic", "fortnite", "Fortnite"),)
    applications = ("Obsidian",)
    assert resolve_explicit_effects("pon fortnite", OPERATIONS, applications, games).operations == ("game.launch",)
    assert resolve_explicit_effects("pon obsidian", OPERATIONS, applications, games).operations == ("app.open",)
    # The same name as the music it is about stays music.
    assert resolve_explicit_effects(
        "ponme música de fortnite", OPERATIONS, applications, games,
    ).operations == ("media.play.youtube",)


@pytest.mark.parametrize(
    ("text", "action"),
    [
        ("pon la canción anterior", "previous"),
        ("toca la canción siguiente", "next"),
        ("pon el tema anterior", "previous"),
    ],
)
def test_a_transport_order_is_not_asked_what_to_play(text, action):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is None
    assert reading.effects is not None and reading.effects.operations == ("media.control",)
    assert sidecar._ground_explicit_arguments("media.control", text, SCHEMAS["media.control"]) == {"action": action}


def test_music_with_nothing_named_still_asks_what_to_play():
    reading = read("pon música", available_operations=OPERATIONS)
    assert reading.clarification is not None and reading.clarification.missing_fields == ("query",)


# ---------------------------------------------------------------- lists


@pytest.mark.parametrize(
    ("text", "title", "details"),
    [
        ("añadir el brócoli a mi lista de la compra", "brócoli", "lista de la compra"),
        ("añadir pasta de dientes a mi lista de la compra", "pasta de dientes", "lista de la compra"),
        ("pon hamburguesa en mi lista de comestibles", "hamburguesa", "lista de comestibles"),
        ("puedes añadir huevos a mi lista de la compra", "huevos", "lista de la compra"),
        ("add milk to my shopping list", "milk", "shopping list"),
    ],
)
def test_a_list_entry_is_a_task_on_that_list(text, title, details):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("task.create",)
    assert sidecar._ground_explicit_arguments(
        "task.create", reading.effects.evidence[0], SCHEMAS["task.create"],
    ) == {"title": title, "details": details}


@pytest.mark.parametrize(
    "text",
    ["añade esta canción a mi lista de reproducción", "pon esa canción en mi lista de favoritos", "añade esto a la lista"],
)
def test_a_playlist_or_a_pointed_entry_is_not_a_task(text):
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is None or "task.create" not in effects.operations


@pytest.mark.parametrize(
    "text",
    [
        "por favor crea una nueva lista", "necesito hacer una lista", "crea una lista de la compra",
        "agregar un nuevo elemento a la lista", "puedes agregar un artículo a mi lista de compras",
    ],
)
def test_a_list_with_nothing_on_it_asks_what_goes_on_it(text):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is None
    assert reading.clarification is not None
    assert reading.clarification.operations == ("task.create",)
    assert reading.clarification.missing_fields == ("list_entries",)


def test_the_answer_puts_the_entries_on_the_list_asked_for():
    effects = resolve_explicit_effects(
        "leche y pan", OPERATIONS, previous_user_text="crea una lista de la compra",
    )
    assert effects is not None and effects.operations == ("task.create",)
    assert sidecar._ground_explicit_arguments(
        "task.create", effects.evidence[0], SCHEMAS["task.create"],
    ) == {"title": "leche y pan", "details": "lista de la compra"}
    assert resolve_explicit_effects("no, déjalo", OPERATIONS, previous_user_text="crea una lista de la compra") is None


# ---------------------------------------------------------------- clock


@pytest.mark.parametrize(
    ("text", "hour", "minute", "resolved"),
    [
        ("necesito una alarma para mañana a las cinco y media de la mañana", 5, 30, True),
        ("recuérdame empezar la cena esta tarde a las cinco", 17, 0, True),
        ("para la reunión de mañana a las diez a. m.", 10, 0, True),
        ("por favor ponga mi alarma para las cinco p. m.", 17, 0, True),
        ("alarma diez de la mañana", 10, 0, True),
        ("a las cinco menos cuarto de la tarde", 16, 45, True),
        ("a las doce de la noche", 0, 0, True),
        ("al mediodía", 12, 0, True),
        ("a las 17", 17, 0, True),
        ("a las 7:30", 7, 30, True),
        ("a las 5", 5, 0, False),
        ("a las cinco y media", 5, 30, False),
    ],
)
def test_one_clock_reader_hears_minutes_and_the_part_of_the_day(text, hour, minute, resolved):
    clock = spoken_clock(fold(text))
    assert clock is not None
    assert (clock.hour, clock.minute, clock.resolved) == (hour, minute, resolved)


@pytest.mark.parametrize("text", ["en dos horas", "a mi casa", "para diez personas", "a las dos horas"])
def test_a_duration_or_a_number_is_not_a_clock(text):
    assert spoken_clock(fold(text)) is None


@pytest.mark.parametrize(
    ("text", "day"),
    [
        ("a las nueve de la mañana", (0, 1)),
        ("mañana a las nueve de la mañana", (1, 0)),
        ("pasado mañana a las nueve", (2, 0)),
        ("el próximo domingo a las nueve de la mañana", (4, 7)),
        ("hoy a las nueve de la noche", (0, 0)),
        ("a las cinco de la mañana esta semana", None),
    ],
)
def test_the_day_a_clock_falls_on(text, day):
    # 2026-09-23 is a Wednesday (Monday = 0).
    assert spoken_day(fold(text), 2) == day


LOCAL = timezone(timedelta(hours=-3))


@pytest.mark.parametrize(
    ("value", "context", "now", "expected_local"),
    [
        # «de la mañana» is the morning of today, not tomorrow.
        ("a las nueve de la manana", "pon una alarma a las nueve de la mañana", datetime(2026, 9, 23, 6, 0), datetime(2026, 9, 23, 9, 0)),
        ("a las cinco y media de la manana", "necesito una alarma para mañana a las cinco y media de la mañana",
         datetime(2026, 9, 23, 21, 0), datetime(2026, 9, 24, 5, 30)),
        ("a las cinco", "recuérdame empezar la cena esta tarde a las cinco", datetime(2026, 9, 23, 12, 0), datetime(2026, 9, 23, 17, 0)),
        ("para las cinco p. m", "por favor ponga mi alarma para las cinco p. m.", datetime(2026, 9, 23, 12, 0), datetime(2026, 9, 23, 17, 0)),
        ("a las nueve de la manana", "poner alarma a las nueve de la mañana el próximo domingo",
         datetime(2026, 9, 23, 12, 0), datetime(2026, 9, 27, 9, 0)),
    ],
)
def test_the_due_moment_is_the_one_said(value, context, now, expected_local):
    now_local = now.replace(tzinfo=LOCAL)
    due = sidecar._canonical_due_utc(value, context, now_utc=now_local)
    assert due == expected_local.replace(tzinfo=LOCAL).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.mark.parametrize(
    ("value", "context"),
    [
        # Said for today at an hour already gone: never moved to another day.
        ("a las cinco", "recuérdame empezar la cena esta tarde a las cinco"),
        # A span is not one date.
        ("a las cinco de la manana", "despiértame a las cinco de la mañana esta semana"),
        # No part of the day for a 1–12 hour.
        ("a las cinco", "recuérdame a las cinco sacar la basura"),
    ],
)
def test_a_moment_that_is_not_one_future_instant_is_not_invented(value, context):
    now_local = datetime(2026, 9, 23, 21, 0, tzinfo=LOCAL)
    assert sidecar._canonical_due_utc(value, context, now_utc=now_local) is None


# ---------------------------------------------------------------- alarms and reminders


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("necesito una alarma para mañana a las cinco y media de la mañana", "notification.schedule"),
        ("despiértame a las seis y cuarto de la mañana", "notification.schedule"),
        ("recuérdame empezar la cena esta tarde a las cinco", "reminder.create"),
        ("dame una notificación de recordatorio para la reunión de mañana a las diez a. m.", "reminder.create"),
        ("quiero un recordatorio para la reunión a las diez de la mañana", "reminder.create"),
    ],
)
def test_a_complete_alarm_or_reminder_is_scheduled_without_a_question(text, operation):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is None
    assert reading.effects is not None and reading.effects.operations == (operation,)


@pytest.mark.parametrize("text", ["quiero una alarma a las 7", "recuérdame a las cinco y media sacar la basura"])
def test_an_hour_without_its_part_of_the_day_is_still_asked(text):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is not None
    assert reading.clarification.missing_fields == ("am_pm_or_part_of_day_for_supplied_hour",)


def test_reading_the_reminders_stays_a_read():
    assert resolve_explicit_effects("dame mis recordatorios", OPERATIONS).operations == ("reminder.list",)


@pytest.mark.parametrize(
    ("operation", "text", "due", "title"),
    [
        ("reminder.create", "dame una notificación de recordatorio para la reunión de mañana a las diez a. m.",
         "a las diez a. m.", "la reunión de mañana"),
        ("reminder.create", "recuérdame empezar la cena esta tarde a las cinco", "a las cinco", "empezar la cena esta tarde"),
        ("reminder.create", "recuérdame a las cinco y media de la tarde sacar la basura",
         "a las cinco y media de la tarde", "sacar la basura"),
        ("notification.schedule", "despiértame a las seis y cuarto de la mañana",
         "a las seis y cuarto de la manana", "despiértame a las seis y cuarto de la mañana"),
    ],
)
def test_the_literal_moment_and_title_are_kept(operation, text, due, title):
    arguments = sidecar._explicit_arguments_from_evidence(operation, text)
    assert arguments is not None
    assert arguments["dueUtc"] == due and arguments["title"] == title
