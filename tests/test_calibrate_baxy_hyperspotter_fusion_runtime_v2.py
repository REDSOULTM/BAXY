from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "calibrate_baxy_hyperspotter_fusion_runtime_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "calibrate_baxy_hyperspotter_fusion_runtime_v2", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_runtime_threshold_adds_observed_shift_and_fixed_guard() -> None:
    result = MODULE.select_runtime_threshold(
        base_threshold=3.0,
        maximum_legacy_negative_margin=0.006,
        minimum_legacy_positive_margin=0.15,
    )
    assert result["calibratedDecisionThreshold"] == pytest.approx(3.056)
    assert result["expectedMaximumLegacyNegativeMargin"] == pytest.approx(-0.05)
    assert result["expectedMinimumLegacyPositiveMargin"] == pytest.approx(0.094)


def test_runtime_threshold_rejects_insufficient_positive_headroom() -> None:
    with pytest.raises(ValueError, match="headroom_insufficient"):
        MODULE.select_runtime_threshold(
            base_threshold=3.0,
            maximum_legacy_negative_margin=0.02,
            minimum_legacy_positive_margin=0.08,
        )


def test_calibration_uses_only_legacy_partition() -> None:
    base = {
        "schema": "baxy-hyperspotter-fusion-v1",
        "approved": False,
        "blindHumanAudioAccessed": False,
        "policy": {
            "ctc_feature": "full_clip_margin",
            "decision_threshold": 3.0,
        },
    }
    audit = {
        "schema": "baxy.hyperspotter-fusion-product-runtime-audit.v1",
        "sources": {"fusionManifestSha256": "a" * 64},
        "humanDevelopmentAudioAccessed": True,
        "blindHumanAudioAccessed": False,
        "developmentOnly": True,
        "legacyDevelopment": {
            "positiveTotal": 14,
            "negativeTotal": 4,
            "positiveHits": 14,
            "falseHits": 1,
            "maximumNegativeDecisionMargin": 0.006,
            "minimumPositiveDecisionMargin": 0.15,
        },
        # Deliberately poor values: the expanded partition is contract-checked
        # for cardinality but cannot influence the selected threshold.
        "expandedIndependentDevelopment": {
            "positiveTotal": 4,
            "negativeTotal": 8,
            "positiveHits": 0,
            "falseHits": 8,
        },
    }
    result = MODULE.calibration_from_audit(
        base_manifest=base,
        base_manifest_sha256="a" * 64,
        audit_report=audit,
    )
    assert result["calibratedDecisionThreshold"] == pytest.approx(3.056)
    assert result["expandedPartitionUsedForSelection"] is False
