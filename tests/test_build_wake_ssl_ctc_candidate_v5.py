from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_wake_ssl_ctc_candidate_v5.py"
)
SPEC = importlib.util.spec_from_file_location("build_wake_ssl_ctc_candidate_v5", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_threshold_metrics_keeps_safety_explicit() -> None:
    metrics = MODULE.threshold_metrics(
        np.asarray([0.9, 0.7, 0.5, 0.2]), np.asarray([1, 1, 0, 0]), 0.6
    )
    assert metrics == {
        "threshold": 0.6,
        "positive_accepted": 2,
        "positive_total": 2,
        "negative_false_accepts": 0,
        "negative_total": 2,
    }


def test_fit_prototype_separates_simple_sequences() -> None:
    positive_a = np.tile(np.asarray([[2.0, 0.1]], dtype=np.float32), (60, 1))
    positive_b = np.tile(np.asarray([[1.8, 0.2]], dtype=np.float32), (60, 1))
    negative_a = np.tile(np.asarray([[0.1, 2.0]], dtype=np.float32), (60, 1))
    negative_b = np.tile(np.asarray([[0.2, 1.8]], dtype=np.float32), (60, 1))
    features = np.concatenate([positive_a, positive_b, negative_a, negative_b])
    offsets = np.asarray([0, 60, 120, 180, 240])
    records = [
        {"label": "positive", "target_onset_seconds": 0.1},
        {"label": "positive", "target_onset_seconds": 0.1},
        {"label": "negative", "target_onset_seconds": None},
        {"label": "negative", "target_onset_seconds": None},
    ]
    _, _, direction, threshold, scores = MODULE.fit_prototype(
        features=features,
        offsets=offsets,
        records=records,
        duration_seconds=0.35,
        offset_seconds=0.0,
        pooling="mean",
    )
    assert direction.shape == (2,)
    assert np.all(scores[:2] >= threshold)
    assert np.all(scores[2:] < threshold)


def test_fallback_threshold_excludes_only_prior_confusable_vetoes() -> None:
    threshold = MODULE.fallback_threshold(
        np.asarray([0.9, 0.8, 0.7, 0.2]),
        np.asarray([1, 1, 0, 0]),
        np.asarray([False, False, True, False]),
    )
    assert threshold > 0.2
    assert threshold < 0.7
