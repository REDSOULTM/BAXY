"""Fase 3.5: the reading gate returns one Reading for a message.

The turn consumes it instead of calling the readers one by one: the explicit effects (and which
form read them), a recognized effect that lacks a value, and talk that asks nothing.
"""

from __future__ import annotations

import pytest

from baxy_mind.semantic.reading import Reading, read

OPERATIONS = ("app.open", "media.play.youtube", "audio.volume", "audio.volume.adjust")


@pytest.mark.parametrize(
    ("text", "operations", "source"),
    [
        ("abrí la calculadora", ("app.open",), "pattern"),
        ("qué lindo día, che, poné música de Brasil en youtube", ("media.play.youtube",), "order_with_talk"),
        ("en YouTube poné una canción de cuna", ("media.play.youtube",), "fronted_place"),
        ("quiero escuchar música de Brasil", ("media.play.youtube",), "desired_media"),
    ],
)
def test_the_effects_and_the_form_that_read_them(text, operations, source):
    reading = read(text, available_operations=OPERATIONS)
    assert isinstance(reading, Reading)
    assert reading.effects is not None and reading.effects.operations == operations
    assert reading.source == source
    assert reading.talk is None


def test_a_recognized_effect_without_its_value_is_a_clarification():
    reading = read("subí el volumen", available_operations=OPERATIONS)
    assert reading.effects is None
    assert reading.clarification is not None and reading.clarification.missing_fields == ("amount",)
    assert reading.talk is None


@pytest.mark.parametrize(("text", "talk"), [("ayer me quedé leyendo hasta tarde", "statement"), ("otra vez te trabaste", None)])
def test_talk_that_asks_nothing(text, talk):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is None and reading.clarification is None
    assert reading.talk == talk
