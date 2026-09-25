"""Uso real tanda 7 (2026-09-25, official window): a conversation is one message after another.

Half of the tanda were conversations where each message depends on the one before («¿y el finde?», «actually
make it 9», «y quién fue el top scorer», «cómo se llama esta?»). One owner per rule:

1. A clock said with its minutes is read by its hour («remind me at 7:30 to call grandma» was asked «when and
   what?»: the 30 was read as the hour). Owner: semantic/patterns._incomplete_scheduled_request (the hour digits).

Every list mixes Spanish, English and Spanglish and holds phrasings never seen in a run.
"""

from __future__ import annotations

import pytest

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
