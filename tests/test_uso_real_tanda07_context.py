"""Uso real tanda 7 (2026-09-25, official window): a conversation is one message after another.

Half of the tanda were conversations where each message depends on the one before («¿y el finde?», «actually
make it 9», «y quién fue el top scorer», «cómo se llama esta?»), and a third of those follow-ups were understood.
The owner's method of the same day (artifacts/comprobaciones/C03/PROPUESTA_METODO_COMPRENSION_2026-09-25.md)
answers it with one mechanism, not a rule per phrase. One owner per rule:

1. A clock said with its minutes is read by its hour («remind me at 7:30 to call grandma» was asked «when and
   what?»: the 30 was read as the hour). Owner: semantic/patterns._incomplete_scheduled_request (the hour digits).
5. No inventing: a place said only through a person («at my sister's») is asked, never read as this PC's town
   (owner: semantic/system.weather_place_known_only_through_someone); a search whose results are about something
   else than the subject asked is reported as not found (owner: llm._search_report_off_subject).
6. «cancel the last timer» cancels the last scheduled alarm like «cancel the last alarm» (owner:
   semantic/notes, the notification cancel reader).

Every list mixes Spanish, English and Spanglish and holds phrasings never seen in a run.
"""

from __future__ import annotations

import pytest

from baxy_mind import llm
from baxy_mind.semantic.reading import read

OPERATIONS = (
    "audio.volume", "audio.volume.adjust", "audio.mute", "system.settings.set", "system.settings.adjust",
    "media.control", "media.play.query", "media.play.youtube", "media.status", "weather.current", "web.search",
    "notification.schedule", "notification.cancel.latest", "notification.cancel.at", "notification.list",
    "reminder.create", "reminder.list", "system.time", "calendar.event.list", "app.open",
)


# ---------------------------------------------------------------- 1. a clock with its minutes


@pytest.mark.parametrize(
    "text",
    [
        "remind me at 7:30 to call grandma",  # tanda 7 t24 (after «and»)
        "remind me to water the plants at 19:45",
        "recuérdame a las 7:30 llamar a la abuela",
        "avísame a las 8:15 que saque la ropa",
        "recordame a las 21:05 sacar la basura",
    ],
)
def test_a_clock_with_minutes_is_read_by_its_hour(text):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("reminder.create",)
    assert reading.clarification is None


@pytest.mark.parametrize("text", ["recuérdame a las 99 comprar pan", "remind me at 13 pm to call mom"])
def test_an_hour_no_day_has_is_still_asked(text):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is not None


# ---------------------------------------------------------------- 5. no inventing


@pytest.mark.parametrize(
    "text",
    [
        "¿Va a llover tomorrow at my sister's?",  # tanda 7 t26
        "va a llover en casa de mi hermana mañana",
        "qué tiempo hace en lo de mi vieja",
        "is it going to rain where my dad lives",
        "will it be cold at my mom's house tomorrow",
    ],
)
def test_a_place_known_only_through_someone_is_asked(text):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is not None
    assert reading.clarification.operations == ("weather.current",)
    assert reading.clarification.missing_fields == ("location",)


@pytest.mark.parametrize(
    "text",
    ["va a llover en casa de mi hermana en Lima", "qué clima hace en mi casa", "will it rain at my place", "va a llover mañana"],
)
def test_a_named_town_or_here_is_read(text):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("weather.current",)
    assert reading.clarification is None


def _search_payload(*snippets: str) -> dict:
    return {
        "operation": "web.search",
        "seen": {
            "query": "top scorer",
            "results": [
                {"title": f"Resultado {index}", "url": f"https://example{index}.org/a", "snippet": snippet}
                for index, snippet in enumerate(snippets)
            ],
        },
    }


def test_a_search_about_something_else_is_reported_as_not_found():
    user = "quién fue el top scorer del game de los Lakers anoche"
    payload = _search_payload("Raphinha es el máximo goleador de LaLiga con 12 goles.", "Tabla de goleadores 2026/27.")
    assert llm._payload_fact_defect("Raphinha fue el top scorer con 12 goles.", payload, user) == "search_report_off_subject"
    assert llm._payload_fact_defect("No encontré quién fue el goleador de ese partido.", payload, user) == ""
    answered = _search_payload("Luka Doncic fue el top scorer de los Lakers anoche con 34 puntos.")
    assert llm._payload_fact_defect("Luka Doncic fue el top scorer con 34 puntos.", answered, user) != (
        "search_report_off_subject"
    )


def test_a_question_without_a_name_is_not_judged_by_its_subject():
    payload = _search_payload("El arcoíris tiene siete colores: rojo, naranja, amarillo, verde, azul, añil y violeta.")
    assert llm._search_report_off_subject("Tiene siete colores.", payload, "cuáles son los colores del arcoíris") is False


# ---------------------------------------------------------------- 6. the last timer cancelled


@pytest.mark.parametrize(
    "text", ["cancel the last timer", "cancela el último temporizador", "quita el último temporizador", "delete the last timer"],
)
def test_the_last_timer_is_cancelled_like_the_last_alarm(text):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("notification.cancel.latest",)


def test_all_the_timers_are_not_the_last_one():
    assert read("borra los temporizadores", available_operations=OPERATIONS).effects is None
