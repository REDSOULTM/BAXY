"""M113 (2026-10-01): DEV-F v4d items left by M110–M112, fixed in general and tested in our own phrasings.

Evidence: the official-window DEV-F run v4d (%LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v4d-devF) and its
offline replays (recorded decider decisions, no model).

1. w18-t1 «Right, can you pull up my Downloads folder? I'm after the council tax letter I saved last week…», w39-t1
   «dónde quedó el apunte.pdf? lo bajé ayer…»: closed as a past or hypothetical state. A past-tense sentence beside a
   sentence that asks for an act now is that request's context.
2. s035 «Could you open up Paint.NET for me, would you?» → navigated to paint.net. A dotted name built on an installed
   application's name is no plain domain, and an opening that names an installed application is no missing game.
3. w45-t4 «scratch the garlic knots one» after «Done, 12-minute timer for the garlic knots.» → task.delete. The
   notification BAXY just reported setting, taken back by what it is for, is the latest one.
4. w08, w59: «pimientos del piquillo, aceite y dos barras de pan» was one task, so «Tacha el aceite» found nothing.
   Each entry enumerated for a list is a task of its own.
5. w36-t2, w60-t2 «la otra, la de estudio / la del disco»: Spotify looked for «Estudio». The studio or album version
   is the song's own title.
6. w18-t3 «Remind me the day before the first one's due, nine in the morning» after «…the first one due on 1
   November.» → tomorrow at 9:00. Days are counted from the date said earlier; «the first one» is no day.
7. w55-t2 «no, mejor media hora antes, una hora es mucho» after a reminder «una hora antes» of 10:00: the reminder
   moves by the difference (to 9:30), cancelled and set again.
No test reads the machine's date or hour.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic import notes, temporal
from baxy_mind.semantic.conversation import catalog_unavailable, stable_no_effect
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.grammar import past_or_hypothetical_message
from baxy_mind.semantic.catalog import build_game_catalog_index
from baxy_mind.semantic.patterns import resolve_explicit_effects
from baxy_mind.semantic.web import bare_domain_names_an_application

OPERATIONS = (
    "app.open", "app.installed", "browser.navigate", "filesystem.folder.open", "notification.cancel.latest",
    "notification.schedule", "task.create", "task.complete", "task.delete", "task.resolve.exact", "web.search",
)


# ------------------------------------------------------------------ 1. a past sentence beside a request


@pytest.mark.parametrize("text", [
    "Could you open my Documents folder? I put the lease contract there yesterday, I think.",
    "¿me abres la carpeta de imágenes? ayer pasé las fotos del viaje ahí",
    "dónde quedó el informe_final.docx? lo guardé anoche y no aparece",
])
def test_a_past_sentence_beside_a_request_is_its_context(text: str) -> None:
    assert not past_or_hypothetical_message(sidecar.effect_intent._fold(text))
    assert stable_no_effect(text, [{"role": "user", "content": text}]) is None


@pytest.mark.parametrize("text", [
    "¿cuánta batería tenía ayer a esta hora?",
    "Ayer abrí Chrome y se colgó. ¿Por qué?",
    "Supongamos que tuviera 64 GB. ¿Podrías abrir veinte pestañas?",
])
def test_a_story_or_a_hypothesis_stays_past_or_hypothetical(text: str) -> None:
    assert past_or_hypothetical_message(sidecar.effect_intent._fold(text))


# ------------------------------------------------------------------ 2. a dotted application name


def test_a_dotted_name_built_on_an_installed_application_is_no_domain() -> None:
    assert bare_domain_names_an_application("abreme krita.org porfa", ["Krita"])
    assert bare_domain_names_an_application("open battle.net", ["Battle.net"])
    assert not bare_domain_names_an_application("abre github.com", ["Krita"])
    assert not bare_domain_names_an_application("abre www.krita.org", ["Krita"])
    read = resolve_explicit_effects("Would you open up Krita.org for me?", OPERATIONS, ["Krita"])
    assert read is None or "browser.navigate" not in read.operations
    # A site whose name no application has keeps its navigation.
    assert resolve_explicit_effects("abre wikipedia.org", OPERATIONS, ["Krita"]).operations == ("browser.navigate",)


def test_an_opening_that_names_an_installed_application_is_no_missing_game() -> None:
    games = build_game_catalog_index(())
    assert not catalog_unavailable("Would you open up Krita.org for me?", None, ["Krita"], games)
    assert catalog_unavailable("open Hollow Knight", None, ["Krita"], games)
    # M123 (D58): an opening that names a folder, a reminder or music is no missing game; the decider reads it.
    for text in ("abre la carpeta de proyectos", "open my reminder about the dentist", "let's play some chill music"):
        assert not catalog_unavailable(text, None, ["Krita"], games)


# ------------------------------------------------------------------ 3. the notification just set, taken back


@pytest.mark.parametrize(("text", "reply", "canonical"), [
    ("nah, drop the lasagna one, I'll keep an eye on it", "Done, 40-minute timer for the lasagna.",
     "cancel the last timer"),
    ("uy no, quita el del arroz", "Listo, temporizador de 18 minutos para el arroz.", "cancela el último temporizador"),
    ("cancel that alarm", "Alarm set for 6:30 tomorrow: gym.", "cancel the last alarm"),
])
def test_the_notification_just_set_is_taken_back_by_what_it_is_for(text: str, reply: str, canonical: str) -> None:
    assert temporal.cancelled_notification_just_set(text, reply) == canonical
    assert resolve_explicit_effects(canonical, OPERATIONS).operations == ("notification.cancel.latest",)


@pytest.mark.parametrize(("text", "reply"), [
    ("drop the pasta one", "Done, 40-minute timer for the lasagna."),
    ("quita el del arroz", "¿Cuánto tiempo para el arroz?"),
    ("quita el del arroz", "Cancelé el temporizador del arroz."),
    ("añade arroz a la lista", "Listo, temporizador de 18 minutos para el arroz."),
])
def test_nothing_is_taken_back_unless_it_names_what_was_just_set(text: str, reply: str) -> None:
    assert temporal.cancelled_notification_just_set(text, reply) is None


# ------------------------------------------------------------------ 4. each entry of a list is a task


def test_each_entry_enumerated_for_a_list_is_a_task_of_its_own() -> None:
    text = "apunta en la lista del súper tomates, cebolla morada y arroz"
    read = resolve_explicit_effects(text, OPERATIONS)
    assert read.operations == ("task.create",) * 3
    schema = {"type": "object", "properties": {"title": {"type": "string"}, "details": {"type": "string"}},
              "required": ["title"], "additionalProperties": False}
    titles = [sidecar._ground_explicit_arguments("task.create", clause, schema, (), build_game_catalog_index(()))
              for clause in read.evidence]
    assert [arguments["title"] for arguments in titles] == ["tomates", "cebolla morada", "arroz"]
    assert {arguments["details"] for arguments in titles} == {"lista del súper"}


def test_a_single_entry_a_repeated_one_or_a_decimal_comma_keep_their_shape() -> None:
    assert notes.list_entries("add oat milk to my shopping list") == (("oat milk",), "shopping list")
    assert notes.list_entries("pon leche y leche y pan en la lista de la compra") == (("leche", "pan"), "lista de la compra")
    assert notes.list_entries("añade 2,5 kilos de papas a la lista de la compra") == (
        ("2,5 kilos de papas",), "lista de la compra")
    assert resolve_explicit_effects("add oat milk to my shopping list", OPERATIONS).operations == ("task.create",)


# ------------------------------------------------------------------ 5. the studio version is the song


EXACT = {"type": "object", "properties": {"provider": {"type": "string", "enum": ["spotify"]},
                                          "title": {"type": "string"}},
         "required": ["provider", "title"], "additionalProperties": False}


def test_the_studio_or_album_version_is_the_song_as_recorded() -> None:
    games = build_game_catalog_index(())
    for restated in ("Pon la versión de estudio de «Gracias a la vida».",
                     "Play the album version of «Fake Plastic Trees».",
                     "Pon la versión del disco de «Lamento boliviano»."):
        grounded = sidecar._ground_explicit_arguments("media.play.exact", restated, EXACT, (), games)
        assert grounded is not None and grounded["title"] in restated
        assert grounded["title"] not in {"Estudio", "estudio"}
    # A live or acoustic version is no title; it stays with the extraction.
    assert sidecar._ground_explicit_arguments(
        "media.play.exact", "Pon la versión en vivo de «Gracias a la vida».", EXACT, (), games) is None


# ------------------------------------------------------------------ 6. days counted from a date said earlier


TODAY = date(2027, 2, 10)


def test_the_day_before_a_date_said_earlier_is_that_day() -> None:
    reply = "Your passport appointment is confirmed for 4 March at the consulate."
    assert temporal.anchored_day_request(
        "remind me the day before the appointment, eight in the morning", reply, [], today=TODAY,
    ) == "set a reminder on 3 March at 08:00 for the appointment"
    assert temporal.anchored_day_request(
        "avísame dos días antes del examen a las 7 de la tarde", "Anotado.",
        ["El examen de física es el 1 de marzo."], today=TODAY,
    ) == "ponme un recordatorio el 27 de febrero a las 19:00 para el examen"
    # A date of another year than the next coming one says its year.
    assert temporal.anchored_day_request(
        "ponme una alarma el día antes de eso a las 6 de la mañana", "Tu vuelo sale el 1 de enero de 2029.", [],
        today=TODAY,
    ) == "ponme una alarma el 31 de diciembre de 2028 a las 06:00"


def test_no_day_is_counted_without_a_dated_thing_or_a_clock() -> None:
    reply = "Your passport appointment is confirmed for 4 March at the consulate."
    assert temporal.anchored_day_request("remind me the day before the appointment", reply, [], today=TODAY) is None
    assert temporal.anchored_day_request(
        "remind me the day before the party, at 9am", reply, [], today=TODAY) is None
    assert temporal.anchored_day_request(
        "remind me the day before the appointment at 9am", "It is on 4 March or 5 March.", [], today=TODAY) is None


def test_the_first_one_counts_things_not_days() -> None:
    said = temporal.spoken_date("set a reminder on 3 march at 08:00 for the first one")
    assert said is not None and (said.day, said.month) == (3, 3)


# ------------------------------------------------------------------ 7. a new count from the same moment


CHILE = timezone(timedelta(hours=-3))
NOW = datetime(2027, 2, 10, 15, 0, tzinfo=CHILE)
SET_WITH_A_COUNT = "el viernes a las 11 tengo la revisión técnica, recuérdamelo una hora antes"


def _set(due: datetime, request: str) -> DialogueState:
    state = DialogueState()
    state.expect(request, ["notification.schedule"])
    state.record({
        "kind": "operation", "operation": "notification.schedule", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"version": 1, "kind": "reminder", "title": "revisión técnica",
                     "dueUtc": due.astimezone(timezone.utc).isoformat(), "taskName": "BAXY-Reminder-m113"},
    })
    return state


def test_a_new_count_from_the_same_moment_moves_the_reminder_by_the_difference() -> None:
    assert temporal.offset_retiming("no, mejor media hora antes, una hora es demasiado", SET_WITH_A_COUNT) == 30
    assert temporal.offset_retiming("actually make it two hours before", "remind me an hour before the match") == -60
    due = (NOW + timedelta(days=2)).replace(hour=10, minute=0)
    state = _set(due, SET_WITH_A_COUNT)
    request = state.moved_notification_request("no, mejor media hora antes, una hora es demasiado", now=NOW, zone=CHILE)
    assert request == "cancela el recordatorio «revisión técnica» de las 10:00 y vuelve a ponerlo a las 10:30"


def test_a_count_with_nothing_to_move_from_moves_nothing() -> None:
    assert temporal.offset_retiming("media hora antes", SET_WITH_A_COUNT) is None
    assert temporal.offset_retiming("no, mejor media hora antes", "recuérdame a las 10 la revisión") is None
    due = (NOW + timedelta(days=2)).replace(hour=10, minute=0)
    state = _set(due, "recuérdame el viernes a las 10 la revisión técnica")
    assert state.moved_notification_request("no, mejor media hora antes", now=NOW, zone=CHILE) is None
