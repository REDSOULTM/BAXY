"""Estabilización L, rama 1: los límites de partida que esta rama deja dichos.

- Lo que depende de un dispositivo que el equipo no tiene (live n5: Wi-Fi sin adaptador): la mente marca el lugar del
  dispositivo (``steps[].requires``), la App lo lee y para, y el suelo lo dice con la causa verificada y lo que hizo
  antes (``cu_finals.limit_final``), nunca el modelo («no encontré el cuadro de búsqueda»).
- Arrastrar y dibujar: el contrato de «sin operación» (tests/test_cu_v3_arrastre.py, test_cu_r24_arrastre_y_dibujo.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from baxy_mind import operation_floor
from baxy_mind import cu_finals
from baxy_mind.semantic import limits
from baxy_mind.semantic.drag import asks_to_drag

_CASES = Path(__file__).resolve().parent.parent / "scripts" / "cu_live" / "cases"


@pytest.mark.parametrize(
    ("goal", "device"),
    [
        ("ir a wi-fi", "wifi"),
        ("ir a Wi-Fi", "wifi"),
        ("go to wifi", "wifi"),
        # Review of L, H8b: the place said with its settings.
        ("go to Wi-Fi settings", "wifi"),
        ("abrir la configuración de wifi", "wifi"),
        ("activar el bluetooth", "bluetooth"),
        # Contracases: a section that only mentions the device exists without it; a text about it is no place.
        ("ir a bluetooth y dispositivos", None),
        ("go to Bluetooth & devices", None),
        ("ir a red e internet", None),
        ("escribir wifi", None),
    ],
)
def test_a_place_that_is_a_device_requires_it_and_a_section_that_mentions_it_does_not(goal: str, device: str | None) -> None:
    assert limits.required_device(goal) == device


def test_a_chain_marks_the_place_of_the_device_and_an_unmarked_mission_comes_back_as_it_was() -> None:
    n5 = {"goal": "ir a red e internet; luego ir a wi-fi", "application": "Configuración", "steps": [
        {"goal": "ir a red e internet", "application": "Configuración", "successCheck": "title:red e internet"},
        {"goal": "ir a wi-fi", "application": "Configuración", "successCheck": "title:wi-fi"},
    ]}
    marked = limits.with_declared_limits(n5)
    assert [step.get("requires") for step in marked["steps"]] == [None, "wifi"]
    assert "requires" not in n5["steps"][1], "the arguments given are not changed in place"
    s03 = {"goal": "ir a bluetooth y dispositivos", "application": "Configuración", "successCheck": "title:bluetooth"}
    assert limits.with_declared_limits(s03) is s03


def test_a_single_goal_that_needs_a_device_is_its_one_marked_step() -> None:
    single = {"goal": "ir a wi-fi", "application": "Configuración", "successCheck": None}
    assert limits.with_declared_limits(single)["steps"] == [
        {"goal": "ir a wi-fi", "application": "Configuración", "successCheck": None, "requires": "wifi"}]


def _n5(subgoal_reached: bool = True) -> dict:
    return {
        "goal": "ir a red e internet; luego ir a wi-fi", "application": "Configuración", "reached": False,
        "stoppedBy": "computer_use_limit_device", "absentDevice": "wifi",
        "steps": [{"step": 1, "operation": "input.visible.click", "ok": True, "label": "Red e Internet",
                   "name": "Red e Internet", "subgoal": 0}] if subgoal_reached else [],
        "subgoals": [
            {"goal": "ir a red e internet", "application": "Configuración", "reached": subgoal_reached,
             "arrivedAs": "Red e Internet", "acted": subgoal_reached},
            {"goal": "ir a wi-fi", "application": "Configuración", "reached": False},
        ],
    }


def test_n5_says_the_computer_has_no_wifi_and_what_it_did_before() -> None:
    assert cu_finals.floor_first(_n5(), english=False, succeeded=False) == (
        "Llegué a «Red e Internet», pero no puedo ir a «Wi-Fi»: este equipo no tiene adaptador Wi-Fi.")
    assert cu_finals.floor_first(_n5(), english=True, succeeded=False) == (
        "I got to «Red e Internet», but I can't go to «Wi-Fi»: this computer has no Wi-Fi adapter.")


def test_n5_with_nothing_done_before_says_only_the_cause() -> None:
    final = cu_finals.floor_first(_n5(subgoal_reached=False), english=False, succeeded=False)
    assert final == "No puedo ir a «Wi-Fi»: este equipo no tiene adaptador Wi-Fi."
    assert "búsqueda" not in final


def test_the_device_floor_says_nothing_for_another_stop() -> None:
    elevated = {"goal": "ir a rendimiento", "application": "Administrador de tareas", "reached": False, "steps": [],
                "stoppedBy": "computer_use_window_elevated"}
    assert cu_finals.limit_final(elevated, english=False) == ""
    # s06 keeps its own floor sentence.
    assert "corre como administrador" in cu_finals.floor_first(elevated, english=False, succeeded=False)


def test_the_device_cause_reads_well_in_both_languages() -> None:
    # Review of L, H8a: the English cause was ungrammatical.
    cause = operation_floor.floor_data()["computerUse"]["causes"]["computer_use_limit_device"]
    assert cause["en"] == "this computer does not have the device it needs" and cause["es"]
    for device in limits.limits_data()["devices"].values():
        assert device["es"] and device["en"] and device["read"] and device["absent"]


def test_no_request_of_bank_b_asks_to_drag_and_n5_marks_its_device() -> None:
    bank = (_CASES / "BANCO_72.txt").read_text(encoding="utf-8").split()
    said = [
        line for case in bank for line in (_CASES / f"{case}.turns").read_text(encoding="utf-8").splitlines()
        if line.strip() and line.strip() not in {"no", "sí", "si"}
    ]
    assert len(bank) == 72
    assert [line for line in said if asks_to_drag(line)] == []
