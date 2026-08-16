from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_hyperspotter_stage1_calibration_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_baxy_hyperspotter_stage1_calibration_v3", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_adjusted_scores_penalize_only_excess() -> None:
    values = MODULE.adjusted_scores(
        np.asarray([2.0, 2.0, 2.0]),
        np.asarray([0.0, MODULE.STAGE1_REFERENCE, 0.1175]),
        10.0,
    )
    assert np.allclose(values, [2.0, 2.0, 1.0])


def test_policy_selection_uses_zero_false_legacy_threshold() -> None:
    policy = MODULE.select_policy(
        labels=np.asarray([1, 1, 0, 0]),
        hyper_scores=np.asarray([3.0, 2.0, 2.5, 1.0]),
        stage1_scores=np.asarray([0.02, 0.02, 0.30, 0.02]),
    )
    selected = policy["selected"]
    assert selected["positive_hits"] == 2
    assert selected["false_hits"] == 0
    assert selected["alpha"] > 0.0


def test_alpha_grid_is_fixed_and_includes_no_penalty_baseline() -> None:
    assert MODULE.ALPHA_GRID[0] == 0.0
    assert tuple(sorted(MODULE.ALPHA_GRID)) == MODULE.ALPHA_GRID
