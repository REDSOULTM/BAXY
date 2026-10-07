"""Live 2026-10-07 (cu-r20): the follow-up «ahora ponela en modo científica» (reader goal «activar modo cientifico», in
the Calculadora) ended «Llegué a la Calculadora y elegí la Científica Calculadora.»: the model's words, the control's
raw name with the application's. A mode reached by choosing it is now told from the facts first, like «ir a
cientifica»: «Listo, estoy en «Científica».», the mode as the window writes it without the application's name
(computer_use._mode_chosen, data «computerUse.parts.mode»). A switch keeps its path. The App's twins are
tests/data/cu_floor_twins.json («cu-parts-mode-*»)."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import computer_use, llm  # noqa: E402

TWINS = {case["id"]: case for case in json.loads(
    (ROOT / "tests" / "data" / "cu_floor_twins.json").read_text(encoding="utf-8"))["cases"]}


@pytest.mark.parametrize("case_id", ["cu-parts-mode-chosen", "cu-parts-mode-chosen-english"])
@pytest.mark.parametrize("language", ["es", "en"])
def test_a_mode_chosen_is_told_as_the_window_writes_it_without_the_app(case_id: str, language: str) -> None:
    situation = TWINS[case_id]["situation"]
    assert llm._computer_use_floor_first(situation, language) == TWINS[case_id][language]
    assert computer_use.floor_sentence(situation["observed"], language == "en", True) == TWINS[case_id][language]


def test_the_other_gender_of_the_mode_is_the_same_mode() -> None:
    situation = copy.deepcopy(TWINS["cu-parts-mode-chosen"]["situation"])
    situation["observed"]["goal"] = "activar modo cientifica"
    assert llm._computer_use_floor_first(situation, "es") == "Listo, estoy en «Científica»."


def test_a_mode_set_by_a_switch_keeps_its_path() -> None:
    situation = copy.deepcopy(TWINS["cu-parts-mode-chosen"]["situation"])
    situation["observed"]["steps"][-1]["kind"] = "ToggleButton"
    assert llm._computer_use_floor_first(situation, "es") == ""


def test_a_mode_no_click_chose_is_left_to_the_model() -> None:
    situation = copy.deepcopy(TWINS["cu-parts-mode-chosen"]["situation"])
    situation["observed"]["goal"] = "activar modo programador"
    assert llm._computer_use_floor_first(situation, "es") == ""


def test_a_real_switch_goal_is_not_a_mode() -> None:
    situation = copy.deepcopy(TWINS["cu-parts-mode-chosen"]["situation"])
    observed = situation["observed"]
    observed.update(goal="activar bluetooth", application="Configuración")
    observed["steps"] = [{
        "step": 1, "operation": "input.visible.click", "label": "Bluetooth", "ok": True, "name": "Bluetooth",
        "kind": "Button", "state": "on", "changed": True,
    }]
    assert llm._computer_use_floor_first(situation, "es") == ""
