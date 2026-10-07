"""The final voice of a computer-use mission, round 15 (live 2026-10-07, cu-universal v2 blind batch a).

Three finals of reached missions misstated the facts: v2-a2 put Configuración's «Aplicaciones» «dentro de la app Reloj»,
v2-a4 put «Descargas dentro de Documentos», and v2-a12 said «ahora está activado» after only searching «Bluetooth». The
facts only say which application each place was reached in, and a search toggles nothing. Every seen here is our own
shape of those runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import computer_use  # noqa: E402
from baxy_mind.semantic.missions import fold  # noqa: E402

CLOCK_THEN_SETTINGS = {
    "goal": "ir a temporizador; luego ir a aplicaciones",
    "reached": True,
    "stepsDone": ["trajo la aplicación al frente", "clic en «Temporizador»", "trajo la aplicación al frente",
                  "clic en «Aplicaciones»"],
    "windowTitle": "Configuración",
    "joined": False,
    "application": "Reloj",
    "subgoals": [
        {"goal": "ir a temporizador", "application": "Reloj", "reached": True},
        {"goal": "ir a aplicaciones", "application": "Configuración", "reached": True},
    ],
}
TWO_FOLDERS = {
    "goal": "ir a documentos; luego ir a descargas",
    "reached": True,
    "stepsDone": ["clic en «documentos»", "trajo la aplicación al frente", "clic en «Downloads»"],
    "windowTitle": "Downloads - Explorador de archivos",
    "joined": False,
    "application": "Explorador de archivos",
    "subgoals": [
        {"goal": "ir a documentos", "application": "Explorador de archivos", "reached": True},
        {"goal": "ir a descargas", "application": "Explorador de archivos", "reached": True},
    ],
}
SEARCH = {
    "goal": "buscar Bluetooth",
    "reached": True,
    "stepsDone": ["trajo la aplicación al frente", "escribió el texto", "tecla enter"],
    "windowTitle": "Configuración",
    "joined": False,
    "application": "Configuración",
    "screen": {"title": "Configuración", "values": [{"name": "Bluetooth", "state": "on"}]},
}
SWITCH = {**SEARCH, "goal": "activar Bluetooth", "stepsDone": ["clic en «Bluetooth»"]}


def _defect(text: str, seen: dict) -> str | None:
    return computer_use.mission_defect(fold(text), seen)


@pytest.mark.parametrize("draft, seen", [
    ("Estoy en Configuración de Aplicaciones dentro de la app Reloj.", CLOCK_THEN_SETTINGS),
    ("Ya estoy en Aplicaciones dentro del Reloj.", CLOCK_THEN_SETTINGS),
    ("Ya estoy en Temporizador dentro de Configuración.", CLOCK_THEN_SETTINGS),
    ("I'm in Aplicaciones inside Reloj.", CLOCK_THEN_SETTINGS),
    ("Estoy en la carpeta de Descargas dentro de Documentos.", TWO_FOLDERS),
    ("Ya estoy en Documentos dentro de Descargas.", TWO_FOLDERS),
])
def test_a_place_is_never_put_inside_another_place_or_another_app(draft: str, seen: dict) -> None:
    assert _defect(draft, seen) == "extra_claim"


@pytest.mark.parametrize("draft, seen", [
    ("Estoy en Aplicaciones de Configuración.", CLOCK_THEN_SETTINGS),
    ("Ya estoy en Aplicaciones dentro de Configuración.", CLOCK_THEN_SETTINGS),
    ("Fui a Temporizador en el Reloj y ahora estoy en Aplicaciones en Configuración.", CLOCK_THEN_SETTINGS),
    ("Ya estoy en Descargas.", TWO_FOLDERS),
    ("Pasé por Documentos y ya estoy en Descargas en el Explorador de archivos.", TWO_FOLDERS),
])
def test_a_place_in_its_own_application_passes(draft: str, seen: dict) -> None:
    assert _defect(draft, seen) is None


@pytest.mark.parametrize("draft", [
    "Ya busqué Bluetooth en Configuración y ahora está activado.",
    "Busqué Bluetooth y ahora el Bluetooth está encendido.",
    "Busqué Bluetooth; quedó ahora activado.",
    "I searched for Bluetooth and now it's on.",
])
def test_a_search_never_says_what_a_switch_is_now(draft: str) -> None:
    assert _defect(draft, SEARCH) == "extra_claim"


def test_the_screen_state_without_now_and_a_real_switch_pass() -> None:
    assert _defect("Ya busqué Bluetooth en Configuración; Bluetooth está activado.", SEARCH) is None
    assert _defect("Ya busqué Bluetooth en Configuración.", SEARCH) is None
    assert _defect("Listo, ahora Bluetooth está activado.", SWITCH) is None
