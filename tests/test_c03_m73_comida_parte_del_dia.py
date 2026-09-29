"""Fase 3.5b M73: a meal said in the request is the part of the day of a bare 1–12 hour.

Reserve v3j es8765 «poner mi cena en langosta roja en el calendario de hoy a las nueve» was asked «¿a las nueve de la
mañana o de la tarde?». Dinner is at night, breakfast in the morning, lunch in the afternoon; a meeting at six still
asks, and a part of the day said wins over the meal.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind.semantic.temporal import spoken_clock  # noqa: E402


@pytest.mark.parametrize(
    ("text", "hour"),
    [
        ("poner mi cena en langosta roja en el calendario de hoy a las nueve", 21),
        ("recuerdame la cena a las ocho", 20),
        ("remind me about dinner at seven", 19),
        ("el desayuno con ana a las ocho", 8),
        ("breakfast meeting at nine", 9),
        ("el almuerzo es a la una", 13),
        ("lunch with the team at twelve", 12),
    ],
)
def test_a_meal_resolves_the_part_of_the_day(text: str, hour: int) -> None:
    clock = spoken_clock(text)
    assert clock is not None and clock.resolved and clock.hour == hour


@pytest.mark.parametrize(
    "text",
    ["recuerdame la reunion de manana a las seis", "remind me about the meeting tomorrow at six"],
)
def test_without_a_meal_or_part_of_the_day_the_hour_still_asks(text: str) -> None:
    clock = spoken_clock(text)
    assert clock is not None and not clock.resolved


def test_a_part_of_the_day_said_wins_over_the_meal() -> None:
    clock = spoken_clock("la cena de manana a las nueve de la manana")
    assert clock is not None and clock.resolved and clock.hour == 9


def test_a_clock_with_minutes_stays_on_the_24_hour_reading() -> None:
    clock = spoken_clock("la cena a las 7:30")
    assert clock is not None and clock.hour == 7
