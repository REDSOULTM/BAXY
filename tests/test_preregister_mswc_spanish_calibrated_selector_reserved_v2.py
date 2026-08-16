from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "preregister_mswc_spanish_calibrated_selector_reserved_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "preregister_mswc_spanish_calibrated_selector_reserved_v2", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_report() -> dict[str, object]:
    return {
        "schema": "baxy.mswc-spanish-calibrated-selector-tuning.v10",
        "accepted": True,
        "research_reserved_examples_scored": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
        "contract": {
            "quality_floor": MODULE.QUALITY_FLOOR,
            "silence_prior_weight": 0.63,
            "calibrated_fusion_weight": 0.60,
        },
        "metrics": {
            "hard_candidate_top1_accuracy": 0.95,
            "pair_auc": 0.995,
            "equal_error_rate": 0.03,
        },
        "zero_false_true_pair_recall": 0.4,
    }


def test_validate_tuning_report_accepts_locked_green_gate() -> None:
    MODULE.validate_tuning_report(valid_report())


def test_validate_tuning_report_rejects_changed_calibration() -> None:
    report = valid_report()
    report["contract"]["silence_prior_weight"] = 0.64
    with pytest.raises(ValueError, match="tuning_gate_invalid"):
        MODULE.validate_tuning_report(report)
