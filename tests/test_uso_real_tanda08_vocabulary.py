"""Tandas 7b and 8 (2026-09-25, official window): single-message vocabulary and form gaps.

Each gap was classified before it was fixed (PROPUESTA_METODO_COMPRENSION_2026-09-25, step 4). The words of a form
the readers already own are data added to that reader, in ``semantic/``; nothing reads the literal sentence.

- «can you skip this song», «go passed the song now» → «What song would you like to skip?»: skipping, jumping or
  going past the song that plays is the next one. Owner: semantic/media._media_transport_action.

The phrasings below are paraphrases (es/en/spanglish, dialects, typos) the fixes do not name, with negative controls.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic.reading import read

OPERATIONS = (
    "audio.mute", "audio.volume", "audio.volume.adjust", "audio.status", "media.control", "media.play.query",
    "media.play.youtube", "media.status", "system.settings.adjust", "system.settings.set", "system.settings.status",
    "task.create", "task.search", "task.list", "note.create", "web.search", "web.news.headlines", "weather.current",
    "system.time",
)


def _effects(text: str) -> tuple[str, ...]:
    reading = read(text, available_operations=OPERATIONS)
    return tuple(reading.effects.operations) if reading.effects is not None else ()


# ------------------------------------------------------------------ the song that plays, skipped, is the next one


@pytest.mark.parametrize(
    "text",
    [
        "can you skip this song",
        "go passed the song now",
        "skip the song please",
        "please skip the current song",
        "skipp this track",
        "go past this song",
        "salta esta canción",
        "sáltate este tema porfa",
        "pasá este tema",
        "cámbiale de canción",
        "cambia la canción porfa",
        "skipea esta canción",
        "dale skip a esta canción",
        "skip esta song",
    ],
)
def test_the_song_that_plays_skipped_is_the_next_track(text: str) -> None:
    assert _effects(text) == ("media.control",)
    assert sidecar._explicit_media_control_arguments(text) == {"action": "next"}


@pytest.mark.parametrize(
    "text",
    [
        "skip the intro",
        "salta la cuerda",
        "cambia la canción a Bohemian Rhapsody",
        "pasa la canción a mi celular",
        "go past the store",
        "no quiero saltar esta canción",
    ],
)
def test_other_skips_and_changes_are_not_the_next_track(text: str) -> None:
    assert "media.control" not in _effects(text)
