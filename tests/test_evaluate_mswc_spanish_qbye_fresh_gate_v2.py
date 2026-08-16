from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_qbye_fresh_gate_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_qbye_fresh_gate_v2", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


THRESHOLDS = {
    "minimum_top1_accuracy": 0.94,
    "minimum_pair_auc": 0.997,
    "maximum_equal_error_rate": 0.025,
    "minimum_true_pair_recall_at_zero_false_pairs": 0.20,
    "minimum_top1_delta_over_reference": -0.005,
    "minimum_pair_auc_delta_over_reference": -0.0005,
    "maximum_equal_error_rate_delta_over_reference": 0.005,
    "minimum_zero_false_recall_delta_over_reference": 0.0,
}


def metrics(top1: float, auc: float, eer: float, zero: int) -> dict[str, object]:
    return {
        "top1_accuracy": top1,
        "pair_auc": auc,
        "equal_error_rate": eer,
        "true_pairs_accepted_at_zero_false_pairs": zero,
        "true_pairs": 2400,
    }


def test_fresh_gate_requires_absolute_and_non_regression_checks() -> None:
    reference = metrics(0.944, 0.9974, 0.020, 480)
    candidate = metrics(0.945, 0.9975, 0.019, 500)
    passed, checks = MODULE.gate_passes(candidate, reference, THRESHOLDS)
    assert passed
    assert all(checks.values())
    candidate["true_pairs_accepted_at_zero_false_pairs"] = 470
    passed, checks = MODULE.gate_passes(candidate, reference, THRESHOLDS)
    assert not passed
    assert not checks["minimum_zero_false_recall_delta_over_reference"]
