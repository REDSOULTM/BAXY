from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_mswc_spanish_ctc_temporal_features_v13.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_mswc_spanish_ctc_temporal_features_v13", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def synthetic_log_probabilities() -> np.ndarray:
    probabilities = np.full((5, 4), 0.01, dtype=np.float64)
    probabilities[:, 0] = 0.80
    probabilities[1, 1] = 0.90
    probabilities[3, 2] = 0.90
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    return np.log(probabilities)


def test_monotonic_score_rewards_correct_token_order() -> None:
    values = synthetic_log_probabilities()
    assert MODULE.monotonic_token_score(
        values, [1, 2]
    ) > MODULE.monotonic_token_score(values, [2, 1])


def test_temporal_features_are_finite_and_named() -> None:
    features = MODULE.temporal_candidate_features(
        log_probabilities=synthetic_log_probabilities(),
        sequence=[1, 2],
        candidate_characters=4,
        forward_score_per_frame=-1.5,
        blank_id=0,
    )
    assert features.shape == (len(MODULE.FEATURE_NAMES),)
    assert np.isfinite(features).all()
    assert features[MODULE.FEATURE_NAMES.index("greedy_edit_similarity")] == 1.0
