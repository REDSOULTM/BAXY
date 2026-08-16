from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "export_baxy_hyperspotter_fusion_candidate_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "export_baxy_hyperspotter_fusion_candidate_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def policy_report() -> dict[str, object]:
    return {
        "schema": "baxy.baxy-hyperspotter-ctc-continuous-development.v4",
        "blind_human_audio_accessed": False,
        "policy_selection": {
            "selected": {
                "feature": "full_clip_margin",
                "feature_center": 1.0,
                "feature_scale": 2.0,
                "beta": 1.0,
                "threshold": 3.0,
            }
        },
        "legacy_selection_metrics": {
            "fixed_positive_hits": 14,
            "fixed_false_hits": 0,
        },
        "expanded_independent_metrics": {
            "fixed_positive_hits": 4,
            "fixed_false_hits": 0,
        },
        "fixed_policy_ctc_fusion": {
            "fused_positive_hits": 18,
            "fused_false_hits": 0,
        },
    }


def test_policy_requires_complete_human_development_gate() -> None:
    policy = MODULE.policy_from_report(policy_report())
    assert policy == {
        "ctc_feature": "full_clip_margin",
        "ctc_center": 1.0,
        "ctc_scale": 2.0,
        "ctc_weight": 1.0,
        "decision_threshold": 3.0,
    }
    rejected = policy_report()
    rejected["expanded_independent_metrics"]["fixed_positive_hits"] = 3
    with pytest.raises(ValueError, match="policy_evidence_invalid"):
        MODULE.policy_from_report(rejected)


def test_numpy_logmel_has_fixed_product_shape() -> None:
    filters = np.ones((80, 201), dtype=np.float32) * np.float32(1e-3)
    result = MODULE.numpy_log_mel_spectrogram(
        np.zeros(48_000, dtype=np.float32), filters
    )
    assert result.shape == (300, 80)
    assert result.dtype == np.float32
    assert np.isfinite(result).all()
