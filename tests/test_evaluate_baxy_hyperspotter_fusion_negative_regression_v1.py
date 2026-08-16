from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_hyperspotter_fusion_negative_regression_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_baxy_hyperspotter_fusion_negative_regression_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def parity(drift: float) -> dict[str, object]:
    return {
        "schema": "baxy.phoneme-teacher-cuda-product-parity.v1",
        "parityPassed": True,
        "blindHumanAudioAccessed": False,
        "equivalence": {"maximumNormalizedFusionScoreDrift": drift},
        "contract": {
            "cudaPermittedForFreshProductGate": False,
            "cudaPermittedForPreviouslyOpenedRegressionScreen": True,
        },
    }


def test_screening_belt_is_over_one_hundred_times_measured_drift() -> None:
    result = MODULE.screening_contract(parity(0.0018))
    assert result["cpuRescoringBelt"] == 0.25
    assert result["empiricalSafetyMultiplier"] > 100.0


def test_screening_belt_rejects_weak_parity_evidence() -> None:
    with pytest.raises(ValueError, match="screening_belt_invalid"):
        MODULE.screening_contract(parity(0.003))


def test_capture_reconstruction_matches_attested_fields() -> None:
    audio = np.arange(20, dtype=np.float32) / 20.0
    record = {
        "hit_window_end_seconds": 0.0005,
        "capture_source_start_sample": 3,
    }
    expected = np.concatenate((audio[3:], np.zeros(2, np.float32)))[:12]
    record["capture_samples"] = len(expected)
    record["capture_sha256"] = MODULE.bytes_sha256(expected)
    actual = MODULE.reconstruct_capture(
        audio,
        record,
        pre_roll_samples=5,
        trailing_silence_samples=2,
        maximum_turn_samples=12,
    )
    assert np.array_equal(actual, expected)
