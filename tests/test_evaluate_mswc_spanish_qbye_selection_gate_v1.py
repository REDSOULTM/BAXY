from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_qbye_selection_gate_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_qbye_selection_gate_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


THRESHOLDS = {
    "minimum_top1_accuracy": 0.90,
    "minimum_pair_auc": 0.99,
    "maximum_equal_error_rate": 0.05,
    "minimum_true_pair_recall_at_zero_false_pairs": 0.20,
    "minimum_top1_delta_over_frozen_ssl_baseline": 0.0,
}


def test_selection_gate_requires_every_preregistered_check() -> None:
    baseline = {"top1_accuracy": 0.91}
    candidate = {
        "top1_accuracy": 0.92,
        "pair_auc": 0.995,
        "equal_error_rate": 0.04,
        "true_pairs_accepted_at_zero_false_pairs": 250,
        "true_pairs": 1000,
    }
    passed, checks = MODULE.gate_passes(candidate, baseline, THRESHOLDS)
    assert passed
    assert all(checks.values())
    candidate["equal_error_rate"] = 0.051
    passed, checks = MODULE.gate_passes(candidate, baseline, THRESHOLDS)
    assert not passed
    assert not checks["maximum_equal_error_rate"]
