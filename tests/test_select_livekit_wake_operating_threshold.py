from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "select_livekit_wake_operating_threshold.py"
)
SPEC = importlib.util.spec_from_file_location(
    "select_livekit_wake_operating_threshold", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_normalize_features_reshapes_general_validation_rows() -> None:
    value = np.zeros((33, 96), dtype=np.float32)

    normalized, dropped = MODULE.normalize_features(value)

    assert normalized.shape == (2, 16, 96)
    assert dropped == 1


def test_select_threshold_maximizes_recall_under_fp_ceiling() -> None:
    positives = np.asarray([0.95, 0.8, 0.55, 0.3])
    negatives = np.asarray([0.9, 0.7, 0.4, 0.1])

    result = MODULE.select_threshold(
        positives,
        negatives,
        validation_hours=10.0,
        target_fpph=0.1,
    )

    assert result["false_positives"] == 1
    assert result["fpph"] == pytest.approx(0.1)
    assert result["recall"] == pytest.approx(0.5)
    assert result["threshold"] > 0.7


def test_select_threshold_does_not_fallback_when_recall_is_low() -> None:
    positives = np.asarray([0.2, 0.1])
    negatives = np.asarray([0.9, 0.8])

    result = MODULE.select_threshold(
        positives,
        negatives,
        validation_hours=1.0,
        target_fpph=0.0,
    )

    assert result["false_positives"] == 0
    assert result["recall"] == 0.0
    assert result["meets_target_fpph"] is True


def test_normalize_features_rejects_wrong_shape() -> None:
    with pytest.raises(ValueError, match="unsupported_feature_shape"):
        MODULE.normalize_features(np.zeros((4, 12), dtype=np.float32))


def test_recall_floor_point_is_explicitly_not_a_product_threshold() -> None:
    result = MODULE.select_recall_floor_threshold(
        np.asarray([0.95, 0.8, 0.55, 0.3]),
        np.asarray([0.9, 0.7, 0.4, 0.1]),
        validation_hours=2.0,
        minimum_recall=0.75,
    )

    assert result["threshold"] == pytest.approx(0.55)
    assert result["recall"] == pytest.approx(0.75)
    assert result["false_positives"] == 2
    assert result["fpph"] == pytest.approx(1.0)
    assert result["product_operating_point"] is False
    assert result["requires_second_stage_verifier"] is True


def test_recall_floor_point_uses_exact_positive_order_statistic() -> None:
    result = MODULE.select_recall_floor_threshold(
        np.asarray([0.6, 0.6, 0.2]),
        np.asarray([0.5]),
        validation_hours=1.0,
        minimum_recall=2 / 3,
    )

    assert result["threshold"] == pytest.approx(0.6)
    assert result["true_positives"] == 2
