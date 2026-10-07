"""Voice audit 2026-10-07: BAXY reports its own act in its own voice (first person singular, Chilean preterite, words
spelled right). Drafts are the ones the 4B composer wrote live in the v2 computer-use runs."""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm
from baxy_mind.semantic import voice_register

MISSION = {
    "kind": "operation",
    "operation": "mission.computer.use",
    "polarity": "success",
    "verified": True,
    "succeeded": True,
    "cause": "mission_completed",
    "observed": {"goal": "ir a Bluetooth y dispositivos", "reached": True, "application": "Configuración"},
}
NOTE_SAVED = {
    "kind": "operation",
    "operation": "notes.save",
    "polarity": "success",
    "verified": True,
    "succeeded": True,
}


def _defect(text: str, situation: dict, intent: str = "status", said: str = "") -> str:
    return llm.compose_visible_defect(text, intent, said, {"situation": json.dumps(situation, ensure_ascii=False)})


@pytest.mark.parametrize(
    "draft, word",
    [
        ("Abrazé a la sección de Bluetooth en la Configuración y la encontré activada.", "abrazé"),
        ("Llegé a la sección de Bluetooth.", "llegé"),
        ("Buscé Bluetooth en la Configuración.", "buscé"),
        ("Busqé Bluetooth en la Configuración.", "busqé"),
        ("Andé a Alarma y la hora que está seleccionada es 7:00.", "andé"),
    ],
)
def test_a_misspelled_own_preterite_is_found(draft: str, word: str) -> None:
    assert voice_register.misspelled_own_preterite(draft) == word


@pytest.mark.parametrize(
    "draft",
    [
        "Llegué a la sección de Bluetooth.",
        "Busqué Cuphead y lo encontré.",
        "Coloqué la ventana de Word en la mitad izquierda de la pantalla.",
        "Empecé el temporizador y te avisaré cuando esté.",
        "Abrí la Calculadora, calculé 8 por 7 y escribí 56 en el Bloc de notas.",
        "Elegí el color azul más cercano: «Azul aciano».",
        "Escribí «Abrazé» en el Bloc de notas.",
    ],
)
def test_a_right_word_is_not_misspelled(draft: str) -> None:
    assert voice_register.misspelled_own_preterite(draft) == ""


def test_a_word_the_person_said_is_theirs() -> None:
    assert voice_register.misspelled_own_preterite("Busqué andé en la tienda.", said="buscá andé en la tienda") == ""


def test_a_mission_report_in_the_plural_or_the_perfect_is_vetoed() -> None:
    assert _defect("Abrazé a la sección de Bluetooth.", MISSION) == "misspelled_act"
    assert _defect("Ya estamos en la sección de Accesibilidad.", MISSION) == "plural_own_act"
    assert _defect("Ya he entrado en la sección de Bluetooth y dispositivos.", MISSION) == "peninsular_perfect"
    assert _defect("Ya te he encontrado Spotify en la tienda.", MISSION) == "peninsular_perfect"
    assert _defect("Llegué a la sección de Bluetooth y dispositivos.", MISSION) == ""


def test_what_baxy_has_not_done_or_shares_is_no_such_claim() -> None:
    assert not voice_register.tells_own_act_in_peninsular_perfect("No lo he encontrado en la lista.")
    assert not voice_register.tells_own_act_in_peninsular_perfect("¿He entrado bien?")
    assert not voice_register.tells_own_act_in_peninsular_perfect("Escribí «he llegado» en el Bloc de notas.")
    assert not voice_register.tells_own_act_in_plural("Estamos en septiembre.")
    assert not voice_register.tells_own_act_in_plural("Estamos en la misma zona horaria.")
    assert not voice_register.tells_own_act_in_plural("Ya estamos en la semana 40.")
    assert voice_register.tells_own_act_in_plural("We're in the Apps section.")


def test_outside_a_mission_the_perfect_still_stands() -> None:
    # Older finals («He guardado la nota…») keep publishing; the perfect is vetoed where the preterite floor stands.
    assert _defect("He guardado la nota sobre tu viaje.", NOTE_SAVED) == ""
    assert _defect("Ya estamos en la carpeta de notas.", NOTE_SAVED) == "plural_own_act"
