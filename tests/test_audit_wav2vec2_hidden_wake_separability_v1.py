from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_wav2vec2_hidden_wake_separability_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_wav2vec2_hidden_wake_separability_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_select_development_records_never_selects_blind() -> None:
    development = [{"partition": "development"} for _ in range(18)]
    corpus = {
        "schema": "baxy.ccby-wake-holdout-corpus.v1",
        "records": development + [{"partition": "blind"}],
    }
    assert MODULE.select_development_records(corpus) == development


def test_frame_mask_uses_wav2vec2_frame_centers() -> None:
    mask = MODULE.frame_mask(
        149,
        onset_seconds=1.0,
        offset_seconds=0.0,
        duration_seconds=0.35,
    )
    centers = (
        np.arange(149) * MODULE.FEATURE_STRIDE_SAMPLES
        + MODULE.FEATURE_RECEPTIVE_FIELD_SAMPLES / 2
    ) / MODULE.SAMPLE_RATE
    assert np.all(centers[mask] >= 1.0)
    assert np.all(centers[mask] < 1.35)
    assert mask.sum() in {17, 18}


def test_normalize_audio_matches_product_contract() -> None:
    normalized = MODULE.normalize_audio(np.asarray([1.0, 2.0, 4.0], np.float32))
    assert float(normalized.mean()) == pytest.approx(0.0, abs=1e-6)
    assert float(normalized.var()) == pytest.approx(1.0, abs=1e-5)


def test_pool_hidden_rejects_unknown_method() -> None:
    with pytest.raises(ValueError, match="pooling_invalid"):
        MODULE.pool_hidden(np.ones((2, 3)), np.asarray([True, False]), "median")


def test_speaker_held_out_scores_preserve_record_count() -> None:
    features = np.asarray(
        [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9]],
        dtype=np.float64,
    )
    labels = np.asarray([1, 1, 0, 0])
    groups = ["p1", "p2", "n1", "n2"]
    scores = MODULE.speaker_held_out_scores(features, labels, groups)
    assert scores.shape == (4,)
    assert np.all(np.isfinite(scores))


def test_score_metrics_reports_zero_false_recall() -> None:
    scores = np.asarray([0.9, 0.8, 0.2, -0.1])
    labels = np.asarray([1, 1, 0, 0])
    metrics = MODULE.score_metrics(scores, labels)
    assert metrics["diagnostic_zero_false_positive_accepted"] == 2
    assert metrics["diagnostic_zero_false_positive_rate"] == 1.0
