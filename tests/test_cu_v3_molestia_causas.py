"""Review of fable/cu-v3-molestia2 (v3 point 0, fix 3): two stops of a leased flow that were never said.

- ``input_window_changed``: the leased window lost the front with no input of the person (a toast, a popup) and the
  flow stopped before its next key. A mission's final says it from the floor data (``computerUse.causes``); a direct
  act from its cause fact.
- ``message_draft_left_after_interruption``: a message stopped between its first character and Enter may sit unsent
  in that chat's box, where the person's next Enter would send it. Said whole from ``failures`` (mind and App floor),
  never as a bare «stopped halfway», never with the code or «operación»."""

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
from baxy_mind import visible_defect
from baxy_mind import compose_situation

DRAFT_LEFT = "message_draft_left_after_interruption"


def test_a_mission_stopped_by_another_window_says_why() -> None:
    causes = operation_floor.floor_data()["computerUse"]["causes"]
    assert set(causes["input_window_changed"]) == {"es", "en"}
    for language in ("es", "en"):
        seen = cu_projection.project_seen(
            {"goal": "escribir hola", "stoppedBy": "input_window_changed", "steps": []}, language)
        said = str(seen["stoppedBecause"])
        assert said == causes["input_window_changed"][language]
        assert "_" not in said and "operaci" not in said.lower() and "operation" not in said.lower()


@pytest.mark.parametrize("code", ["input_window_changed", DRAFT_LEFT])
def test_a_direct_act_has_a_cause_fact_and_never_the_code(code: str) -> None:
    said = compose_situation._cause_in_prose(code, "es")
    assert compose_situation._has_cause_fact(code)
    assert "_" not in said and "operation" not in said


@pytest.mark.parametrize(
    ("language", "words", "asked"),
    [("es", "sin enviar", "mándale hola a Lucas"), ("en", "unsent", "send hi to Lucas")],
)
def test_a_message_left_in_the_box_is_said_whole(language: str, words: str, asked: str) -> None:
    situation = {
        "kind": "operation",
        "operation": "message.send",
        "polarity": "failure",
        "verified": False,
        "succeeded": False,
        "error": DRAFT_LEFT,
        "operationAttempted": True,
    }
    final = deterministic_finals._told_result_final(situation, {}, asked, language)

    assert final == operation_floor.failure_sentences()[DRAFT_LEFT][0 if language == "es" else 1]
    assert words in final and "Enter" in final
    assert "_" not in final and "operaci" not in final.lower()
    assert visible_defect.compose_visible_defect(final, "error", asked, {"situation": json.dumps(situation)}) == ""


def test_contracase_a_plain_interruption_is_not_said_as_a_message_left() -> None:
    # The person's interruption with the composer as it was keeps its own cause: nothing was left in the box.
    situation = {
        "kind": "operation",
        "operation": "message.send",
        "polarity": "failure",
        "verified": False,
        "succeeded": False,
        "error": "input_user_interrupted",
        "operationAttempted": True,
    }
    final = deterministic_finals._told_result_final(situation, {}, "mándale hola a Lucas", "es")

    assert "sin enviar" not in final
