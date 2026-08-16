from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mdtc_confusable_ctc_dual_gate.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mdtc_confusable_ctc_dual_gate", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_zero_false_rectangle_uses_both_dimensions() -> None:
    positives = np.array([[0.8, 0.8], [0.9, 0.1], [0.1, 0.9]])
    negatives = np.array([[0.85, 0.0], [0.0, 0.85]])

    result = MODULE.zero_false_rectangle(positives, negatives)
    margins = MODULE.combined_margins(positives, result)
    negative_margins = MODULE.combined_margins(negatives, result)

    assert np.count_nonzero(margins >= 0) >= 1
    assert np.count_nonzero(negative_margins >= 0) == 0


def test_zero_false_rectangle_rejects_non_finite_pairs() -> None:
    try:
        MODULE.zero_false_rectangle(
            np.array([[np.nan, 0.0]]), np.array([[0.0, 0.0]])
        )
    except ValueError as error:
        assert "values_invalid" in str(error)
    else:
        raise AssertionError("expected non-finite pair rejection")
