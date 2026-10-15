"""Live 2026-10-07 (r21): «en Configuración andá a Personalización y decime qué tema está activo».

The mission reader read the closing question, but the typed readers read the question alone as a status of the PC
(«tema» → media.status) and that reading beat the mission: the final said «no hay nada reproduciéndose». A status
that only the closing question reads is the question the mission answers from the window it reached.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind.effect_intent import resolve_explicit_effects
from baxy_mind.semantic import missions

ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = tuple(
    json.loads((ROOT / "src/baxy_mind/data/decider_catalog.es.v1.json").read_text(encoding="utf-8"))["operations"]
) + ("mission.computer.use",)
APPS = ("Configuración", "Settings", "Discord", "Steam", "Bloc de notas")


@pytest.mark.parametrize(
    ("text", "goal"),
    [
        ("en Configuración andá a Personalización y decime qué tema está activo",
         "ir a personalizacion" + missions.QUESTION_MARK + "decime qué tema está activo"),
        ("en Configuración andá a Pantalla y decime cuál es la resolución",
         "ir a pantalla" + missions.QUESTION_MARK + "decime cuál es la resolución"),
        ("en Configuración andá a Almacenamiento y decime cuánto espacio queda",
         "ir a almacenamiento" + missions.QUESTION_MARK + "decime cuánto espacio queda"),
        ("en Configuración andá a Sonido y decime el volumen",
         "ir a sonido" + missions.QUESTION_MARK + "decime el volumen"),
        ("in Settings go to Personalization and tell me which theme is active",
         "ir a personalization" + missions.QUESTION_MARK + "tell me which theme is active"),
    ],
)
def test_a_closing_question_after_an_in_app_place_is_the_missions_question(text: str, goal: str) -> None:
    mission = missions.mission_request(text, APPS)
    assert mission is not None and mission.goal == goal
    assert resolve_explicit_effects(text, OPERATIONS, application_names=APPS).operations == ("mission.computer.use",)


def test_a_question_inside_a_dictated_text_is_no_question() -> None:
    mission = missions.mission_request("en el bloc de notas escribí: decime qué tema está activo", APPS)
    assert mission is not None and missions.QUESTION_MARK not in mission.goal


def test_a_status_question_without_an_application_keeps_its_typed_reading() -> None:
    read = resolve_explicit_effects("decime el volumen", OPERATIONS, application_names=APPS)
    assert read is not None and read.operations == ("audio.status",)
