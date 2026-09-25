"""Tandas 7b and 8 (2026-09-25, official window): single-message vocabulary and form gaps.

Each gap was classified before it was fixed (PROPUESTA_METODO_COMPRENSION_2026-09-25, step 4). The words of a form
the readers already own are data added to that reader, in ``semantic/``; nothing reads the literal sentence.

- «can you skip this song», «go passed the song now» → «What song would you like to skip?»: skipping, jumping or
  going past the song that plays is the next one. Owner: semantic/media._media_transport_action.
- «the screen is way too bright» → «Do you mean the screen is too bright for your current environment…?»: a
  complaint about the screen's light is the brightness down (or up), without an amount, so it asks how much (owner
  rule H0027), like the loudness complaint. Owner: semantic/levels._complaint.
- «apúntame en la lista de la compra huevos, leche y pan de molde» → «¿Qué contenido y título quieres que tenga la
  nota…?»: the list named before its entries is the same list entry as «apunta huevos en la lista de la compra».
  Owner: semantic/notes.list_entry_request.

The phrasings below are paraphrases (es/en/spanglish, dialects, typos) the fixes do not name, with negative controls.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic import levels
from baxy_mind.semantic.notes import list_entry_request
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


# ------------------------------------------------------------------ a complaint about the screen's light


@pytest.mark.parametrize(
    ("text", "direction"),
    [
        ("the screen is way too bright", "down"),
        ("my screen is so bright", "down"),
        ("the monitor is too bright", "down"),
        ("la pantalla está demasiado brillante", "down"),
        ("mi pantalla está re brillante", "down"),
        ("la pantalla está súper clara", "down"),
        ("la pantalla brilla demasiado", "down"),
        ("hay demasiado brillo", "down"),
        ("el brillo está muy alto", "down"),
        ("the brightness is way too high", "down"),
        ("está muy oscura la pantalla", "up"),
        ("no se ve nada, la pantalla está muy oscura", "up"),
        ("the display is too dim", "up"),
        ("screen's too dark", "up"),
        ("el brillo está demasiado bajo", "up"),
    ],
)
def test_a_complaint_about_the_screens_light_asks_how_much_brightness(text: str, direction: str) -> None:
    assert levels.read(text) == levels.Level(levels.BRIGHTNESS, direction, None, None)
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is None
    assert reading.clarification is not None and reading.clarification.operation == "system.settings.adjust"


@pytest.mark.parametrize(
    "text",
    [
        "¿por qué la pantalla está tan brillante?",
        "quiero la pantalla muy brillante",
        "la pantalla no está muy brillante",
        "ayer la pantalla estaba muy oscura",
        "the sun is too bright",
        "esta película es muy oscura",
        "la pantalla está muy alta",
        "la pantalla del celular está muy brillante",
        "la música está muy fuerte y la pantalla muy brillante",
    ],
)
def test_other_remarks_about_light_are_not_a_brightness_complaint(text: str) -> None:
    level = levels.read(text)
    assert level is None or level.setting != levels.BRIGHTNESS


def test_the_loudness_complaint_still_asks_how_much_volume() -> None:
    assert levels.read("está muy fuerte la música") == levels.Level(levels.VOLUME, "down", None, None)
    assert levels.read("the music is too loud") == levels.Level(levels.VOLUME, "down", None, None)


# ------------------------------------------------------------------ the list named before its entries


@pytest.mark.parametrize(
    ("text", "entry", "listed"),
    [
        ("apúntame en la lista de la compra huevos, leche y pan de molde", "huevos, leche y pan de molde",
         "lista de la compra"),
        ("añade a la lista de la compra leche y pan", "leche y pan", "lista de la compra"),
        ("agrega a mi lista del súper tortillas y frijoles", "tortillas y frijoles", "lista del súper"),
        ("poné en la lista del super yerba y facturas", "yerba y facturas", "lista del super"),
        ("anota en la lista de compras palta y marraqueta", "palta y marraqueta", "lista de compras"),
        ("añádeme a la lista de la compra dos barras de pan", "dos barras de pan", "lista de la compra"),
        ("add to my shopping list eggs and milk", "eggs and milk", "shopping list"),
        ("put on my grocery list bananas", "bananas", "grocery list"),
        ("agrega a la lista de pendientes llamar al dentista", "llamar al dentista", "lista de pendientes"),
        ("add to the to do list call mom", "call mom", "to do list"),
    ],
)
def test_a_list_named_before_its_entries_is_a_list_entry(text: str, entry: str, listed: str) -> None:
    assert list_entry_request(text) == (entry, listed)
    assert _effects(text) == ("task.create",)


@pytest.mark.parametrize(
    "text",
    [
        "pon en la lista de la compra",
        "añade a la lista de la compra esto",
        "agrega a la lista de reproducción esta canción",
        "añade a mi lista de contactos a Juan",
    ],
)
def test_a_list_named_first_with_no_entry_to_add_is_not_one(text: str) -> None:
    assert list_entry_request(text) is None


def test_the_entry_said_first_still_reads_as_before() -> None:
    assert list_entry_request("apunta huevos en la lista de la compra") == ("huevos", "lista de la compra")
