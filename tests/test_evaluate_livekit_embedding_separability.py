from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_livekit_embedding_separability.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_livekit_embedding_separability", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_representation_preserves_shape_contract() -> None:
    features = np.arange(2 * 16 * 96, dtype=np.float32).reshape(2, 16, 96)

    assert MODULE.representation(features, "flat").shape == (2, 1536)
    assert MODULE.representation(features, "statistics").shape == (2, 384)


def test_weighted_cosine_prototypes_separate_simple_classes() -> None:
    train = np.array([[1.0, 0.0], [0.8, 0.0], [0.0, 1.0], [0.0, 0.8]])
    labels = np.array([1, 1, 0, 0])
    scores = MODULE.weighted_cosine_prototype_scores(
        train, labels, np.ones(4), np.array([[1.0, 0.0], [0.0, 1.0]])
    )

    assert scores[0] > 0
    assert scores[1] < 0


def test_aggregate_clips_uses_maximum_runtime_window() -> None:
    records = [
        {"output_relative_path": "x.wav", "speaker_group": "g", "clip_label": "positive"},
        {"output_relative_path": "x.wav", "speaker_group": "g", "clip_label": "positive"},
    ]
    result = MODULE.aggregate_clips(
        records, np.array([0.1, 0.8]), calibration_threshold=0.5
    )

    assert result[0]["score"] == pytest.approx(0.8)
    assert result[0]["calibrated_margin"] == pytest.approx(0.3)


def test_aggregate_clips_accepts_versioned_relative_path_field() -> None:
    records = [
        {"relative_path": "x.wav", "speaker_group": "g", "clip_label": "positive"}
    ]

    result = MODULE.aggregate_clips(
        records, np.array([0.7]), calibration_threshold=0.5
    )

    assert result[0]["output_relative_path"] == "x.wav"
