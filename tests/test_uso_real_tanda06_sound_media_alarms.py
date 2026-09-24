"""Uso real tanda 6 (2026-09-24, official window): sound, media, alarms and reminders said in Spanglish.

- «Dale up al Sonido» was asked «¿Cuánto y en qué dirección…?»: the direction was said. In Spanglish the English
  particle takes a Spanish light verb with its clitic («dale up», «ponle down», «métele up»); the particle is the
  direction, so only the amount is asked (owner rule H0027: no default step, and a direction said is never asked
  again).

The phrases here are not the literals of the real window; they are other ways of saying the same things, with
controls that must keep their own reading.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind.semantic import levels
from baxy_mind.semantic.patterns import resolve_explicit_clarification_intent, resolve_explicit_effects

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
