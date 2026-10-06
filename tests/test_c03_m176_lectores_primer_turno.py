"""M176 (2026-10-05): what the first-turn readers decide alone, probed with ~400 requests of our own (es-CL/AR/MX/CO/ES,
en, spanglish) through ``_prepare_turn_result`` with a decider that only asks. Each class below had at least three
phrasings the readers got wrong; every phrasing here is our own.

1. Music the readers send to a Spotify search with no query grounded («pon música clásica para concentrarme», «play
   jazz for dinner», «play the beatles») asked what to play: no reader grounds the query and the provider grounds only
   on a music noun, so even the extraction's query was asked again. When the extraction gives nothing that grounds, the
   words the person named it with are the query (``patterns.said_music_query`` in ``_direct_arguments_result``).
3. A pendiente or the person's to-do written down («anota de pendiente ir al notario», «anota en mi to-do: pagar
   netflix») became a note (beside the task, or alone): the person's task store is named (owner D59).
4. A length with its half or quarter («en una hora y media» → one hour, titled «y media …»), a quarter of an hour and
   «an hour» (asked when) are read whole (``grammar._RELATIVE_DURATION_PATTERN``,
   ``arguments.relative_duration_minutes``).
5. «a las 12 del día», «at 12 noon» rang at midnight; «del día» is the daytime and «noon» noon (``temporal``).
6. English minutes before the hour («quarter to eight», «half six») asked when, though the clock reader hears them
   (``notes._reminder_has_actionable_due``).
7. «ponle bluey a la nena en disney» asked «¿Necesitas algo?» (text with nowhere to go), and the wish to watch something
   on a service («i feel like watching the witcher on netflix», «tengo ganas de ver coco en disney+») was talk or left
   to the decider: it is the order to put it on (``reading._wished_viewing_request``).

The clock is fixed (M108): no test reads the machine's date or hour.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.llm import DirectArgumentExtraction
from baxy_mind.semantic import arguments
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.patterns import (
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
    said_music_query,
)
from baxy_mind.semantic.reading import read
from baxy_mind.semantic.temporal import spoken_clocks

OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)
# Tuesday 6 October 2026, 10:00 in Chile (UTC-3).
LOCAL = timezone(timedelta(hours=-3))
NOW = datetime(2026, 10, 6, 10, 0, tzinfo=LOCAL)


SPOTIFY = {"type": "object", "properties": {
    "provider": {"type": "string", "enum": ["spotify"]},
    "query": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
}, "required": ["provider", "query"], "additionalProperties": False}


class _AbstainingExtraction:
    """The arguments step's model: the extraction gives ``extracted`` (nothing by default); a question is recorded."""

    def __init__(self, extracted: dict[str, object] | None = None) -> None:
        self.extracted = extracted
        self.calls: list[str] = []

    def extract_direct_arguments(self, *_args: object, **_kwargs: object) -> DirectArgumentExtraction:
        self.calls.append("extract")
        return DirectArgumentExtraction(self.extracted, (), "")

    def formulate_missing_argument_question(
        self, _objective: str, _said: str, _tool: object, fields: tuple[str, ...] = (), **_kwargs: object,
    ) -> str:
        self.calls.append("ask:" + ",".join(fields))
        return "¿Qué quieres escuchar?"


def _arguments_step(operation: str, text: str, model: _AbstainingExtraction) -> tuple[object, str]:
    tool = {"function": {"canonical_name": operation, "name": operation.replace(".", "_"), "parameters": SPOTIFY}}
    return sidecar._direct_arguments_result(
        {"operation": operation, "text": text, "history": [{"role": "user", "content": text}]},
        llm=model, tool=tool, dialogue_state=DialogueState(),
    )


def _effects(text: str) -> tuple[str, ...] | None:
    reading = read(text, available_operations=OPERATIONS)
    return reading.effects.operations if reading.effects is not None else None


def _due_local(literal: str, context: str) -> datetime:
    due = arguments._canonical_due_utc(literal, context, now_utc=NOW)
    assert due is not None, (literal, context)
    return datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(LOCAL)


# ------------------------------------------------------------------ 1. music named in any words is the query


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("pon música clásica para concentrarme", "música clásica para concentrarme"),
        ("quiero oír música andina para cocinar", "música andina para cocinar"),
        ("play jazz for dinner", "jazz for dinner"),
        ("play the beatles", "the beatles"),
        ("play something chill for cooking", "chill for cooking"),
        ("reproduce jazz para estudiar", "jazz para estudiar"),
    ],
)
def test_music_the_readers_search_on_spotify_carries_the_words_it_was_named_with(text: str, query: str) -> None:
    assert _effects(text) == ("media.play.query",), text
    model = _AbstainingExtraction()
    assert _arguments_step("media.play.query", text, model) == ({"provider": "spotify", "query": query}, "")


@pytest.mark.parametrize("text", ["play the beatles", "play jazz for dinner"])
def test_a_query_the_provider_left_ungrounded_is_the_persons_words(text: str) -> None:
    # The provider «spotify» grounds only on a music noun, so the extraction's own query was asked again.
    model = _AbstainingExtraction({"provider": "spotify", "query": text.removeprefix("play ")})
    assert _arguments_step("media.play.query", text, model) == (
        {"provider": "spotify", "query": text.removeprefix("play ")}, "",
    )


def test_a_query_the_extraction_grounded_stays() -> None:
    model = _AbstainingExtraction({"provider": "spotify", "query": "música clásica"})
    assert _arguments_step("media.play.query", "pon música clásica para concentrarme", model) == (
        {"provider": "spotify", "query": "música clásica"}, "",
    )


def test_a_bare_order_still_asks_in_the_arguments_step() -> None:
    model = _AbstainingExtraction()
    assert _arguments_step("media.play.query", "pon música", model) == (None, "¿Qué quieres escuchar?")


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("pon algo alegre que ando triste", "alegre"),  # why it is wanted is not what to play
        ("ponme algo de bad bunny porfa", "bad bunny"),
        ("poné algo de cumbia che", "cumbia"),
    ],
)
def test_the_query_leaves_out_the_partitive_the_reason_and_the_vocative(text: str, query: str) -> None:
    assert said_music_query(text) == query


@pytest.mark.parametrize(
    "text",
    ["pon música", "ponme música", "play some music", "pon música en spotify", "pon algo", "play something to relax",
     "pon un video de gatos"],
)
def test_music_with_nothing_named_still_names_no_query(text: str) -> None:
    assert said_music_query(text) is None


@pytest.mark.parametrize("text", ["pon música", "ponme música", "pon música en spotify", "pon algo", "pon algo nuevo"])
def test_a_bare_order_to_play_still_asks_what_to_play(text: str) -> None:
    clarification = resolve_explicit_clarification_intent(text, OPERATIONS)
    assert clarification is not None and clarification.operations == ("media.play.query",), text


def test_what_is_playing_is_still_read() -> None:
    assert _effects("qué está sonando") == ("media.status",)


# ------------------------------------------------------------------ 3. the person's task store, never a note


@pytest.mark.parametrize(
    "text",
    ["anota de pendiente ir al notario", "anótame de pendiente pagar el dividendo",
     "apunta como pendiente llamar a la isapre", "anota pendiente llamar al contador"],
)
def test_a_pendiente_written_down_is_a_task_alone(text: str) -> None:
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is not None and effects.operations == ("task.create",), text


@pytest.mark.parametrize(
    "text",
    ["anota en mi to-do: pagar netflix", "anota en mis to-dos llamar al seguro", "jot down buy stamps on my to-do",
     "anota en mi to do pagar el internet"],
)
def test_the_persons_to_do_is_never_a_note(text: str) -> None:
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is None or "note.create" not in effects.operations, text


@pytest.mark.parametrize(
    "text",
    [
        "anota llamar al dentista",  # reviewed literal H0056
        "anotá que tengo que llamar al dentista",  # reviewed literal H0599 (a note, TASK_NOTE_REPAIR986)
        "anota todo lo que te dije",  # «todo» is Spanish «everything»
        "anota en una nota que la clave es 1234",
        "crea una nota llamada ideas que diga comprar un dron",
    ],
)
def test_a_note_still_is_a_note(text: str) -> None:
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is not None and effects.operations == ("note.create",), text


# ------------------------------------------------------------------ 4. lengths with their half or quarter


@pytest.mark.parametrize(
    ("said", "minutes"),
    [
        ("una hora y media", 90), ("hora y cuarto", 75), ("dos horas y media", 150), ("un minuto y medio", 1.5),
        ("un cuarto de hora", 15), ("tres cuartos de hora", 45), ("an hour", 60), ("an hour and a half", 90),
        ("20 minutitos", 20), ("10 minutos", 10), ("2h", 120), ("25-minute", 25), ("media hora", 30),
        ("half an hour", 30), ("3 dias", 3 * 24 * 60),
    ],
)
def test_every_length_the_pattern_reads_has_its_minutes(said: str, minutes: float) -> None:
    assert arguments.relative_duration_minutes(said) == minutes


@pytest.mark.parametrize("said", ["a las 5", "hora", "y media", "una", "las 7 y media", "0 minutos"])
def test_what_is_no_length_has_no_minutes(said: str) -> None:
    assert arguments.relative_duration_minutes(said) is None


@pytest.mark.parametrize(
    ("text", "minutes", "title"),
    [
        ("avisame en una hora y media que tengo que salir", 90, "tengo que salir"),
        ("recuérdame en dos horas y media llamar a mi papá", 150, "llamar a mi papá"),
        ("recuérdame en una hora y cuarto ir a buscar a la vale", 75, "ir a buscar a la vale"),
        ("recuérdame en un cuarto de hora apagar el horno", 15, "apagar el horno"),
        ("remind me in an hour and a half to call", 90, "call"),
        ("remind me in an hour to take my pills", 60, "take my pills"),
        ("recuérdame en 10 min revisar la olla", 10, "revisar la olla"),
    ],
)
def test_a_reminder_rings_after_the_whole_length_and_keeps_only_what_it_is_for(
    text: str, minutes: int, title: str,
) -> None:
    assert _effects(text) == ("reminder.create",), text
    read_arguments = arguments._explicit_relative_reminder_arguments(text)
    assert read_arguments is not None and read_arguments["title"] == title
    assert _due_local(str(read_arguments["dueUtc"]), text) - NOW == timedelta(minutes=minutes)


@pytest.mark.parametrize(
    ("text", "minutes"),
    [("pon un timer de un cuarto de hora", 15), ("pon una alarma en una hora y media", 90),
     ("timer de un minuto y medio", 1.5), ("pon un temporizador de 10 minutos para los huevos", 10)],
)
def test_a_timer_runs_the_whole_length(text: str, minutes: float) -> None:
    assert _effects(text) == ("notification.schedule",), text
    read_arguments = arguments._explicit_notification_schedule_arguments(text)
    assert read_arguments is not None
    assert _due_local(str(read_arguments["dueUtc"]), text) - NOW == timedelta(minutes=minutes)


def test_a_length_counted_from_another_moment_is_still_not_from_now() -> None:
    assert arguments._canonical_due_utc("media hora", "ponme una alarma media hora antes de eso", now_utc=NOW) is None


# ------------------------------------------------------------------ 5. «del día» and «noon»


@pytest.mark.parametrize(
    ("said", "hour", "minute"),
    [("a las 12 del dia", 12, 0), ("a las doce del dia", 12, 0), ("a las 12 y media del dia", 12, 30),
     ("at 12 noon", 12, 0), ("a las 10 del dia", 10, 0), ("a las 3 del dia", 15, 0)],
)
def test_the_daytime_and_noon_are_said_parts_of_the_day(said: str, hour: int, minute: int) -> None:
    (clock,) = spoken_clocks(said)
    assert (clock.hour, clock.minute, clock.resolved) == (hour, minute, True)


@pytest.mark.parametrize(
    ("said", "hour", "resolved"),
    [("a las 12 de la noche", 0, True), ("a las 5 del dia siguiente", 5, False), ("a las 7 de la manana", 7, True)],
)
def test_other_parts_of_the_day_are_unchanged(said: str, hour: int, resolved: bool) -> None:
    clock = spoken_clocks(said)[0]
    assert (clock.hour, clock.resolved) == (hour, resolved)


@pytest.mark.parametrize("text", ["ponme una alarma a las 12 del día", "alarm at 12 noon"])
def test_an_alarm_at_noon_rings_at_noon(text: str) -> None:
    read_arguments = arguments._explicit_notification_schedule_arguments(text)
    assert read_arguments is not None
    due = _due_local(str(read_arguments["dueUtc"]), text)
    assert (due.hour, due.minute) == (12, 0)


def test_a_reminder_at_noon_keeps_only_what_it_is_for() -> None:
    read_arguments = arguments._explicit_relative_reminder_arguments("recuérdame a las 12 del día almorzar")
    assert read_arguments is not None and read_arguments["title"] == "almorzar"


# ------------------------------------------------------------------ 6. English minutes before the hour


@pytest.mark.parametrize(
    ("text", "hour", "minute"),
    [("set an alarm for quarter to eight", 7, 45), ("set an alarm for quarter past six", 6, 15),
     ("wake me up at half six", 6, 30)],
)
def test_minutes_before_the_hour_are_a_moment_said(text: str, hour: int, minute: int) -> None:
    assert resolve_explicit_clarification_intent(text, OPERATIONS) is None, text
    assert _effects(text) == ("notification.schedule",), text
    read_arguments = arguments._explicit_notification_schedule_arguments(text)
    assert read_arguments is not None
    due = _due_local(str(read_arguments["dueUtc"]), text)
    assert (due.hour % 12, due.minute) == (hour, minute)


@pytest.mark.parametrize(
    ("text", "missing"),
    [("pon una alarma", ("alarm_time",)), ("recuérdame sacar la basura", ("due_time",))],
)
def test_a_notice_with_no_moment_still_asks_when(text: str, missing: tuple[str, ...]) -> None:
    clarification = resolve_explicit_clarification_intent(text, OPERATIONS)
    assert clarification is not None and clarification.missing_fields == missing, text


# ------------------------------------------------------------------ 7. a show put on a service, wished or for someone


@pytest.mark.parametrize(
    ("text", "service", "title"),
    [
        ("ponle bluey a la nena en disney", "disney_plus", "bluey"),
        ("ponle peppa pig a los niños en netflix", "netflix", "peppa pig"),
        ("ponle frozen a mi hija en disney plus", "disney_plus", "frozen"),
    ],
)
def test_a_show_put_on_a_service_for_someone_is_no_text_with_nowhere_to_go(
    text: str, service: str, title: str,
) -> None:
    assert sidecar._unresolved_input_kind(text, ()) is None
    assert _effects(text) == ("streaming.play.named",)
    assert arguments._explicit_arguments_from_evidence("streaming.play.named", text) == {
        "service": service, "title": title,
    }


@pytest.mark.parametrize("text", ["ponle hola", "ponle un saludo"])
def test_text_to_put_with_nowhere_named_is_still_asked_where(text: str) -> None:
    assert sidecar._unresolved_input_kind(text, ()) == "deictic_text"


@pytest.mark.parametrize(
    ("text", "service", "title"),
    [
        ("i feel like watching the witcher on netflix", "netflix", "the witcher"),
        ("i feel like some bluey on disney plus", "disney_plus", "bluey"),
        ("i'm in the mood to watch wednesday on netflix", "netflix", "wednesday"),
        ("tengo ganas de ver coco en disney+", "disney_plus", "coco"),
        ("me tinca ver la serie bridgerton en netflix", "netflix", "bridgerton"),
        ("se me antoja ver toy story en disney", "disney_plus", "toy story"),
    ],
)
def test_the_wish_to_watch_something_on_a_service_is_the_order_to_put_it_on(
    text: str, service: str, title: str,
) -> None:
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("streaming.play.named",), text
    assert reading.source == "wished_viewing"
    assert arguments._explicit_arguments_from_evidence("streaming.play.named", reading.effects.evidence[0]) == {
        "service": service, "title": title,
    }


@pytest.mark.parametrize(
    "text",
    ["i feel like crying", "tengo ganas de ver a mi abuela", "me encanta netflix", "i feel like some jazz",
     "tengo ganas de ver una peli en netflix"],
)
def test_a_wish_with_no_show_on_a_service_is_not_put_on(text: str) -> None:
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is None or reading.effects.operations != ("streaming.play.named",), text
