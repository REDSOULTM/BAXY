"""cu-r16: every word of a computer-use final is grounded in the turn's facts or in BAXY's own vocabulary.

Lines from the voice audit of 2026-10-07 (v2-* live runs): the seen of each case is trimmed to the fields the words
come from; the drafts are the 4B's own.
"""

from __future__ import annotations

import pytest

from baxy_mind import computer_use
from baxy_mind.llm import compose_visible_defect
from baxy_mind.semantic.normalize import _accent_folded_with_punctuation as folded

BLUETOOTH = {
    "goal": "ir a bluetooth y dispositivos",
    "reached": True,
    "stepsDone": ["trajo la aplicación al frente", "clic en «Bluetooth y dispositivos»"],
    "windowTitle": "Configuración",
    "application": "Configuración",
    "screen": {
        "title": "Configuración",
        "values": [{"name": "Bluetooth y dispositivos", "state": "selected"}],
        "lines": ["Xbox Wireless Controller", "Emparejado", "SLEVE EVO", "Emparejado", "Bluetooth", "Activado"],
    },
}
APPS = {
    "goal": "ir a aplicaciones",
    "reached": True,
    "stepsDone": ["clic en «Aplicaciones»"],
    "windowTitle": "Configuración",
    "application": "Configuración",
    "screen": {"values": [{"name": "Cuadro de búsqueda, Buscar una opción", "value": "wi-fi"}]},
}
CALC = {
    "goal": "calcular 37 × 12",
    "reached": True,
    "stepsDone": ["trajo la aplicación al frente", "escribió el texto", "tecla enter"],
    "windowTitle": "Calculadora",
    "application": "Calculadora",
    "screen": {"numbers": ["La pantalla muestra 444"]},
}
DOWNLOADS = {
    "goal": "ir a descargas",
    "reached": True,
    "stepsDone": ["clic en «Descargas»"],
    "windowTitle": "Descargas - Explorador de archivos",
    "application": "Explorador de archivos",
}


@pytest.mark.parametrize(
    ("seen", "said", "draft", "word"),
    [
        (BLUETOOTH, "en Configuración andá a Bluetooth", "Abrazé a la sección de Bluetooth en la Configuración.", "abraze"),
        (APPS, "y después a Aplicaciones", "Estoy en Configuración de Aplicaciones, donde busco la opción de Wi-Fi.", "busco"),
        (BLUETOOTH, "en Configuración andá a Bluetooth", "Ya estamos en la sección de Bluetooth y dispositivos.", "estamos"),
        (BLUETOOTH, "en Configuración andá a Bluetooth", "Ya he entrado en la sección de Bluetooth y dispositivos.", "he"),
        (
            BLUETOOTH,
            "en Configuración andá a Bluetooth",
            "Ya estoy en la sección de Bluetooth y dispositivos, donde aparecen mis controladores emparejados.",
            "mis",
        ),
        (DOWNLOADS, "in File Explorer go to Downloads", "I'm already in the Downloads folder.", "already"),
    ],
)
def test_a_word_from_neither_the_facts_nor_baxys_vocabulary_is_named(seen, said, draft, word) -> None:
    assert computer_use.ungrounded_word(folded(draft), seen, said) == word


@pytest.mark.parametrize(
    ("seen", "said", "draft"),
    [
        (CALC, "abrí la calculadora y calculá 37 por 12", "Ya calculé 37 por 12 y la pantalla muestra 444."),
        (
            BLUETOOTH,
            "en Configuración andá a Bluetooth",
            "Ya estoy en la sección de Bluetooth y dispositivos, donde veo que el Xbox Wireless Controller y el "
            "SLEVE EVO están emparejados.",
        ),
        (DOWNLOADS, "en el Explorador de archivos andá a Descargas", "Ya estoy en la carpeta de Descargas."),
        (DOWNLOADS, "in File Explorer go to Downloads", "I'm in the Downloads folder."),
        (APPS, "y después a Aplicaciones", "Llegué a Aplicaciones en Configuración."),
    ],
)
def test_a_final_built_from_the_facts_and_baxys_words_is_grounded(seen, said, draft) -> None:
    assert computer_use.ungrounded_word(folded(draft), seen, said) is None


def _situation(seen: dict) -> dict:
    observed = {
        "goal": seen["goal"],
        "reached": seen["reached"],
        "steps": [],
        "window": {"title": seen["windowTitle"]},
        "application": seen["application"],
        "screen": seen.get("screen") or {},
    }
    return {
        "kind": "operation",
        "operation": computer_use.OPERATION,
        "outcome": "completed",
        "verified": True,
        "succeeded": True,
        "observed": observed,
    }


def test_the_composer_gate_vetoes_an_ungrounded_mission_final() -> None:
    facts = {"situation": _situation(BLUETOOTH)}
    said = "en Configuración andá a Bluetooth"
    assert compose_visible_defect("Abrazé a la sección de Bluetooth.", "status", said, facts) == "unknown_word"
    assert compose_visible_defect("Llegué a Bluetooth y dispositivos.", "status", said, facts) != "unknown_word"
