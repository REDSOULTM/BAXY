"""v3 point 0, fix 3: an act that needs the real mouse or keyboard waits for a pause of the person
(input_user_not_paused when none comes) and stops when they act during it (input_user_interrupted). Both codes reach
the mind and are said with their cause in the person's words: a mission's final from the floor data
(operation_floor.v1.json «computerUse.causes»; twins cu-failed-person-* in tests/data/cu_floor_twins.json), a
direct act from the cause facts. Never the code, never «operación»."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import operation_floor
from baxy_mind import cu_projection
from baxy_mind import deterministic_finals
from baxy_mind import compose_situation

CODES = ("input_user_not_paused", "input_user_interrupted")
TWINS = {case["id"]: case for case in json.loads(
    (ROOT / "tests" / "data" / "cu_floor_twins.json").read_text(encoding="utf-8"))["cases"]}


@pytest.mark.parametrize("code", CODES)
def test_a_mission_stopped_by_the_person_says_why_in_their_words(code: str) -> None:
    causes = operation_floor.floor_data()["computerUse"]["causes"]
    assert set(causes[code]) == {"es", "en"}
    for language in ("es", "en"):
        seen = cu_projection.project_seen({"goal": "escribir hola", "stoppedBy": code, "steps": []}, language)
        said = str(seen["stoppedBecause"])
        assert said == causes[code][language]
        assert "_" not in said and "operaci" not in said.lower() and "operation" not in said.lower()


@pytest.mark.parametrize("case_id", ["cu-failed-person-busy", "cu-failed-person-interrupted"])
def test_the_final_names_the_person_and_not_the_code(case_id: str) -> None:
    case = TWINS[case_id]
    for language in ("es", "en"):
        final = deterministic_finals._deterministic_final(case["situation"], {}, "", language)
        assert final == case[language]
        assert "input" not in final and "operaci" not in final.lower()


@pytest.mark.parametrize("code", CODES)
def test_a_direct_act_has_a_cause_fact_and_never_the_code(code: str) -> None:
    said = compose_situation._cause_in_prose(code, "es")
    assert compose_situation._has_cause_fact(code)
    assert "_" not in said and "person" in said


def test_contracase_an_unknown_input_code_has_no_invented_cause() -> None:
    # Only the two typed codes are said as the person's doing; another input_* code keeps no such fact.
    assert not compose_situation._has_cause_fact("input_window_changed_by_nobody")
    assert "input_window_changed_by_nobody" not in operation_floor.floor_data()["computerUse"]["causes"]
