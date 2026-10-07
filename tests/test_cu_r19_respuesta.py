"""cu-r19 (live 2026-10-07): a reached mission whose question one fact of the window answers alone is answered from
that fact; zero or several such facts leave it to the model. «Llegué a X» where X is no place of the mission is vetoed."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from baxy_mind import computer_use as cu
from baxy_mind.computer_use import fold

_PAYLOADS = json.loads(
    (Path(__file__).resolve().parent / "data" / "cu_r19_question_payloads.json").read_text(encoding="utf-8")
)


def _observed(case: str) -> dict:
    return copy.deepcopy(_PAYLOADS[case]["observed"])


@pytest.mark.parametrize(
    ("case", "final"),
    [
        ("v2-c5", "Listo: el modo está en «Oscuro»."),
        ("v2-v3", "Listo: el volumen está en 60."),
        ("v2-z10", "Listo: la zona horaria es «(UTC-04:00) Santiago»."),
    ],
)
def test_real_payloads_are_answered_from_the_one_fact(case: str, final: str) -> None:
    observed = _observed(case)
    assert cu.floor_first(observed, False, True) == final
    assert cu.floor_sentence(observed, False, True) == final


def test_english_question() -> None:
    observed = _observed("v2-c5")
    observed["goal"] = observed["goal"].replace("decime si el modo es claro u oscuro", "tell me if the mode is light or dark")
    for item in observed["screen"]["values"]:
        if item["name"] == "Oscuro":
            item["name"] = "Dark"
    assert cu.floor_first(observed, True, True) == "Done: the mode is set to «Dark»."
    volume = _observed("v2-v3")
    volume["goal"] = volume["goal"].replace("decime el volumen", "tell me the volume")
    volume["screen"]["values"][0]["name"] = "Adjust the output volume"
    assert cu.floor_first(volume, True, True) == "Done: the volume is at 60."


def test_both_options_selected_is_the_model_s() -> None:
    observed = _observed("v2-c5")
    observed["screen"]["values"].append({"name": "Claro", "state": "selected"})
    assert cu.floor_first(observed, False, True) == ""


def test_no_option_selected_is_the_model_s() -> None:
    observed = _observed("v2-c5")
    observed["screen"]["values"] = [item for item in observed["screen"]["values"] if item["name"] != "Oscuro"]
    assert cu.floor_first(observed, False, True) == ""


def test_two_values_named_by_the_noun_is_the_model_s() -> None:
    observed = _observed("v2-v3")
    observed["screen"]["values"].append({"name": "Volumen del sistema", "value": "35"})
    assert cu.floor_first(observed, False, True) == ""


def test_no_value_named_by_the_noun_is_the_model_s() -> None:
    observed = _observed("v2-v3")
    observed["goal"] = observed["goal"].replace("decime el volumen", "decime el brillo")
    assert cu.floor_first(observed, False, True) == ""


def test_two_time_zones_on_screen_is_the_model_s() -> None:
    observed = _observed("v2-z10")
    observed["screen"]["numbers"].append("(UTC-03:00) Buenos Aires")
    assert cu.floor_first(observed, False, True) == ""


def test_open_question_is_the_model_s() -> None:
    observed = _observed("v2-v3")
    observed["goal"] = observed["goal"].replace("decime el volumen", "decime cómo está el sonido")
    assert cu.floor_first(observed, False, True) == ""


def test_unreached_mission_with_a_question_is_not_answered() -> None:
    observed = _observed("v2-c5")
    observed["reached"] = False
    assert cu.floor_first(observed, False, True) == ""
    assert cu.floor_first(_observed("v2-c5"), False, False) == ""


@pytest.mark.parametrize("case", ["v2-c5", "v2-z10"])
def test_arrival_at_a_value_is_an_extra_claim(case: str) -> None:
    payload = _PAYLOADS[case]
    assert cu.mission_defect(fold(payload["draft"]), payload["seen"]) == "extra_claim"


@pytest.mark.parametrize(
    "reply",
    [
        "Llegué a Configuración, Sistema y Sonido.",
        "Llegué a la sección de Sonido.",
        "I reached Sonido in Configuración.",
    ],
)
def test_arrival_at_a_mission_place_passes(reply: str) -> None:
    assert cu._arrived_off_mission(fold(reply), _PAYLOADS["v2-v3"]["seen"]) is False
