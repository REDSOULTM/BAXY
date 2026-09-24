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
- «i want you to set alarms for 2pm and 3pm» was asked «What time…?»: several alarms said with their times are each
  scheduled, whether each time carries its own half of the day or one said last is shared, asked as a wish or as an
  order («one at…, one at…», «una a las…, otra a las…»). «pon alarmas a las 7 y a las 8 de la mañana» used to play a
  YouTube video: the plural «alarmas» is not a title either.

The phrases here are not the literals of the real window; they are other ways of saying the same things, with
controls that must keep their own reading.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import __main__ as mind
from baxy_mind.llm import compose_visible_defect
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


# --- 5. several alarms, each with its time -----------------------------------------------------------------------

_ALARMS = AVAILABLE + ("notification.schedule", "reminder.create")


@pytest.mark.parametrize(
    ("text", "evidence"),
    [
        ("i need you to set alarms for 6am and 7am", ("alarm at 6 am", "alarm at 7 am")),
        ("set two alarms, one at 5pm and one at 6pm", ("alarm at 5 pm", "alarm at 6 pm")),
        ("set an alarm for 2pm and another for 3:30pm", ("alarm at 2 pm", "alarm at 3:30 pm")),
        ("set alarms for 2 and 3 p.m.", ("alarm at 2 p.m.", "alarm at 3 p.m.")),
        (
            "pon alarmas a las 7 y a las 8 de la mañana",
            ("alarma a las 7 de la manana", "alarma a las 8 de la manana"),
        ),
        ("quiero que me pongas alarmas a las 6 am y a las 6:30 am", ("alarma a las 6 am", "alarma a las 6:30 am")),
        (
            "programa dos alarmas, una a las 5 de la tarde y otra a las 6 de la tarde",
            ("alarma a las 5 de la tarde", "alarma a las 6 de la tarde"),
        ),
    ],
)
def test_several_alarms_with_their_times_are_each_scheduled(text: str, evidence: tuple[str, ...]) -> None:
    effects = resolve_explicit_effects(text, _ALARMS)
    assert effects is not None, text
    assert effects.operations == ("notification.schedule",) * len(evidence)
    assert effects.evidence == evidence
    for said in effects.evidence:
        arguments = mind._explicit_arguments_from_evidence("notification.schedule", said, (), ())
        assert arguments is not None and arguments["kind"] == "alarm", said


@pytest.mark.parametrize(
    "text",
    [
        # A time whose half of the day was never said is asked, not guessed; the same time twice is one alarm;
        # a repeating alarm is not a finite list.
        "set alarms for 5pm and 7",
        "set alarms for 2pm and 2pm",
        "set repeating alarms for 7am and 8am",
    ],
)
def test_alarms_with_an_unsaid_period_or_a_repetition_are_not_expanded(text: str) -> None:
    effects = resolve_explicit_effects(text, _ALARMS)
    assert effects is None or effects.operations.count("notification.schedule") < 2


# --- 6. the unmute told from its observed baseline ----------------------------------------------------------------

_UNMUTED_FROM_MUTED = json.dumps(
    {
        "kind": "operation", "operation": "audio.mute", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {
            "operation": "audio.mute", "targetId": "default_output",
            "baseline": {"volumePercent": 0, "muted": True}, "final": {"volumePercent": 0, "muted": False},
            "applied": True, "reconciled": False,
        },
    }
)
_UNMUTED_FROM_UNMUTED = _UNMUTED_FROM_MUTED.replace('"volumePercent": 0, "muted": true}, "final"', '"volumePercent": 0, "muted": false}, "final"')


@pytest.mark.parametrize(
    ("draft", "said"),
    [
        ("El altavoz estaba silenciado y ahora está activo, con el volumen en 0%.", "reactiva los parlantes"),
        ("The speaker was muted; it is on now, at 0% volume.", "turn the speakers back on"),
        ("El speaker está activo y su volumen es 0%.", "reactiva los parlantes"),
    ],
)
def test_the_unmute_may_tell_the_mute_it_undid(draft: str, said: str) -> None:
    assert compose_visible_defect(draft, "status", said, {"situation": _UNMUTED_FROM_MUTED}) == ""


def test_the_unmute_still_may_not_claim_the_sound_is_muted() -> None:
    assert compose_visible_defect(
        "El altavoz está silenciado.", "status", "reactiva los parlantes", {"situation": _UNMUTED_FROM_MUTED},
    ) == "reversed_mute"
    # A mute that never was is not a baseline to tell.
    assert compose_visible_defect(
        "El altavoz estaba silenciado y ahora está activo.", "status", "reactiva los parlantes",
        {"situation": _UNMUTED_FROM_UNMUTED},
    ) == "reversed_mute"
