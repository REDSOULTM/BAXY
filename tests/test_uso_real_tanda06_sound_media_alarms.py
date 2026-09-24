"""Uso real tanda 6 (2026-09-24, official window): sound, media, alarms and reminders said in Spanglish.

- «Dale up al Sonido» was asked «¿Cuánto y en qué dirección…?»: the direction was said. In Spanglish the English
  particle takes a Spanish light verb with its clitic («dale up», «ponle down», «métele up»); the particle is the
  direction, so only the amount is asked (owner rule H0027: no default step, and a direction said is never asked
  again).
- «Quiero el sound de nuevo please» was answered «No lo hago: no reparto sonidos antiguos»: the sound wanted, asked
  for or given back again is the sound coming back (audio.mute, state false), in Spanish, English or both; with
  «dame»/«necesito» in front it is that order, not a request to observe the audio.
- «recuerda me a las ocho de la tarde que tengo que tomar mi medicamento» was saved in the private memory as the
  datum «me a las ocho…» and read back: the App's memory parser (NaturalMemoryRequestParser.ReminderPattern) did
  not know the clitic the ear writes apart. It now leaves the turn to the mind, which reads the reminder with its
  moment and its title (pinned here; the App side in NaturalMemoryRequestParserTests).
- «ponme barcelona por queen» was described instead of played: «<title> por <performer>» names the song and who
  sings it, like «by» and «de»; both sides must be names said alone, so «por» as a time, a way or a channel plays
  nothing.

The phrases here are not the literals of the real window; they are other ways of saying the same things, with
controls that must keep their own reading.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind.semantic import levels
from baxy_mind.semantic.patterns import resolve_explicit_clarification_intent, resolve_explicit_effects
from baxy_mind.semantic.reading import read

AVAILABLE = (
    "audio.volume", "audio.volume.adjust", "audio.mute", "audio.status", "system.settings.adjust",
    "system.settings.set", "media.control", "media.play.query", "media.play.youtube", "app.open",
)

_ADJUST_SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": "integer", "minimum": 1, "maximum": 100},
        "direction": {"type": "string", "enum": ["down", "up"]},
    },
    "required": ["amount", "direction"],
    "additionalProperties": False,
}


# --- 1. a direction said with a light verb and an English particle ----------------------------------------------


@pytest.mark.parametrize(
    ("text", "direction"),
    [
        ("dale up al volumen", "up"),
        ("ponle up al sound please", "up"),
        ("métele up al audio un poco", "up"),
        ("dale down al volume", "down"),
        ("ponle down al sonido", "down"),
    ],
)
def test_a_light_verb_with_a_particle_asks_only_the_amount(text: str, direction: str) -> None:
    assert resolve_explicit_effects(text, AVAILABLE) is None
    asked = resolve_explicit_clarification_intent(text, AVAILABLE)
    assert asked is not None
    assert asked.operations == ("audio.volume.adjust",)
    assert asked.missing_fields == ("amount",)
    assert levels.direction_of(text) == direction
    # On the model path the question for the rest never asks the direction again.
    assert mind._stated_argument_fields("audio.volume.adjust", text, _ADJUST_SCHEMA) == ("direction",)


def test_a_light_verb_with_a_particle_and_an_amount_acts() -> None:
    level = levels.read("dale up al volumen un 20%")
    assert level == levels.Level(levels.VOLUME, "up", 20, None)


def test_a_light_verb_with_a_particle_on_the_brightness_is_the_brightness() -> None:
    asked = resolve_explicit_clarification_intent("dale up al brillo", AVAILABLE)
    assert asked is not None and asked.operations == ("system.settings.adjust",)


@pytest.mark.parametrize("text", ["dale up", "dale play", "dale up al video", "dale, sube a la azotea"])
def test_a_light_verb_without_a_level_object_is_not_a_level(text: str) -> None:
    assert levels.read(text) is None


# --- 2. the sound wanted back is the sound unmuted ----------------------------------------------------------------


def _unmute_arguments(text: str) -> dict[str, object] | None:
    effects = resolve_explicit_effects(text, AVAILABLE)
    assert effects is not None and effects.operations == ("audio.mute",), (text, effects)
    return mind._explicit_arguments_from_evidence("audio.mute", effects.evidence[0], (), ())


@pytest.mark.parametrize(
    "text",
    [
        "quiero el sonido de nuevo",
        "necesito el audio otra vez, porfa",
        "dame el sonido de vuelta",
        "quiero de vuelta el sonido",
        "I want my sound back",
        "can I have the audio back please?",
        "bring back the sound",
        "give me the sound back",
        "i need the sound again",
    ],
)
def test_the_sound_wanted_back_is_unmuted(text: str) -> None:
    assert _unmute_arguments(text) == {"state": False}


@pytest.mark.parametrize(
    "text",
    [
        # A level, another sound, or listening to something again: never the unmute.
        "quiero el sonido más alto",
        "quiero el sonido de las notificaciones de nuevo",
        "quiero escuchar el sonido de nuevo",
        "I want the sound back at 50",
    ],
)
def test_the_sound_with_something_else_is_not_the_unmute(text: str) -> None:
    effects = resolve_explicit_effects(text, AVAILABLE)
    assert effects is None or "audio.mute" not in effects.operations


@pytest.mark.parametrize("text", ["dame el estado del audio", "necesito saber el volumen"])
def test_observing_the_audio_is_still_a_read(text: str) -> None:
    effects = resolve_explicit_effects(text, AVAILABLE)
    assert effects is not None and effects.operations == ("audio.status",)


# --- 3. a reminder whose clitic the ear wrote apart --------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("recuerda me a las nueve de la noche que tengo que sacar la basura", "tengo que sacar la basura"),
        ("recuérda me en 10 minutos revisar el horno", "revisar el horno"),
    ],
)
def test_a_split_clitic_reminder_keeps_its_title_without_the_clitic(text: str, title: str) -> None:
    reading = read(text, available_operations=("reminder.create", "notification.schedule", "task.create"))
    assert reading.effects is not None and reading.effects.operations == ("reminder.create",)
    arguments = mind._explicit_arguments_from_evidence("reminder.create", reading.effects.evidence[0], (), ())
    assert arguments is not None and arguments["title"] == title


# --- 4. a song «por» its performer is played -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("toca hotel california por eagles", "hotel california por eagles"),
        ("pon la bamba por los lobos", "la bamba por los lobos"),
        ("play bohemian rhapsody por queen", "bohemian rhapsody por queen"),
        ("reproduce la bamba por ritchie valens por favor", "la bamba por ritchie valens"),
    ],
)
def test_a_song_by_its_performer_plays_in_the_local_player(text: str, query: str) -> None:
    # MUSIC1559: music named without a provider plays from YouTube in the local player.
    effects = resolve_explicit_effects(text, AVAILABLE)
    assert effects is not None and effects.operations == ("media.play.youtube",), (text, effects)
    assert mind._explicit_arguments_from_evidence("media.play.youtube", effects.evidence[0], (), ()) == {
        "query": query
    }


@pytest.mark.parametrize(
    "text",
    [
        # «por» as a time, a way, a channel or a courtesy never names a performer.
        "pon todo por escrito",
        "pon la tele por el canal 5",
        "pon la lavadora por la noche",
        "pon los platos por orden",
        "pon eso por el parlante",
    ],
)
def test_por_without_a_performer_plays_nothing(text: str) -> None:
    effects = resolve_explicit_effects(text, AVAILABLE)
    assert effects is None or not {"media.play.youtube", "media.play.query"} & set(effects.operations)
