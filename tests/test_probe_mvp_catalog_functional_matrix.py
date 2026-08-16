from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments"
    / "mind_router_spike"
    / "probe_mvp_catalog_functional_matrix.py"
)
SPEC = importlib.util.spec_from_file_location("probe_mvp_catalog_matrix", PROGRAM)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def _audit(operations: list[str]) -> dict:
    return {
        "candidate_operations": operations,
        "raw_decision": {
            "mode": "action",
            "intent_operations": operations,
            "effect_operations": operations,
        },
        "stages": [
            {"name": name, "effect_operations": operations}
            for name in probe.EXPECTED_STAGE_NAMES
        ],
    }


def test_reviewed_matrix_has_one_scenario_per_catalog_operation() -> None:
    mind, memory = probe.load_scenarios()

    assert len(mind) == 158
    assert len(memory) == 11
    assert len({row["target_operation"] for row in (*mind, *memory)}) == 169
    assert {row["language"] for row in (*mind, *memory)} == {
        "es",
        "en",
        "spanglish",
    }


def test_exact_row_accepts_a_dependency_complete_action() -> None:
    mind, _ = probe.load_scenarios()
    case = next(row for row in mind if row["target_operation"] == "app.close")
    operations = ["window.resolve", "app.close"]
    row = probe.evaluate_row(
        case,
        {
            "kind": "action",
            "intentOperations": operations,
            "effectOperations": operations,
        },
        _audit(operations),
        0.25,
    )

    assert row["exact_turn_correct"] is True
    assert row["failure_cause"] == "none"
    assert row["unsafe_effect"] is False


def test_wrong_effect_is_reported_as_unsafe_decision_failure() -> None:
    mind, _ = probe.load_scenarios()
    case = next(row for row in mind if row["target_operation"] == "system.time")
    row = probe.evaluate_row(
        case,
        {
            "kind": "action",
            "intentOperations": ["system.power"],
            "effectOperations": ["system.power"],
        },
        _audit(["system.power"]),
        0.5,
    )

    assert row["exact_turn_correct"] is False
    assert row["failure_cause"] == "retrieval"
    assert row["unsafe_effect"] is True
