from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments"
    / "wake_validation"
    / "evaluate_prosody_spectral_loco_diagnostic_v1.py"
)
SPEC = importlib.util.spec_from_file_location("prosody_loco", PROGRAM)
assert SPEC is not None and SPEC.loader is not None
DIAGNOSTIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIAGNOSTIC)


def test_features_are_finite_and_amplitude_invariant() -> None:
    sample_rate = 16_000
    time = np.arange(sample_rate, dtype=np.float32) / sample_rate
    waveform = (
        0.6 * np.sin(2 * np.pi * 155 * time) + 0.2 * np.sin(2 * np.pi * 310 * time)
    ).astype(np.float32)

    first = DIAGNOSTIC.extract_features(waveform, sample_rate)
    second = DIAGNOSTIC.extract_features(waveform * 0.25, sample_rate)

    assert first.shape == (DIAGNOSTIC.FEATURE_DIMENSION,)
    assert np.all(np.isfinite(first))
    assert second == pytest.approx(first, abs=2e-4)


def test_threshold_is_strictly_above_training_negatives() -> None:
    scores = np.asarray([0.2, 0.9, 0.4, 0.5])
    labels = np.asarray([0, 1, 0, 1])

    threshold = DIAGNOSTIC.threshold_above_training_negatives(scores, labels)

    assert threshold > 0.4
    assert np.sum(scores[labels == 0] >= threshold) == 0


def test_threshold_requires_negative_examples() -> None:
    with pytest.raises(ValueError, match="training_negatives_required"):
        DIAGNOSTIC.threshold_above_training_negatives(
            np.asarray([0.1]), np.asarray([1])
        )


def test_v17_paths_are_forbidden() -> None:
    with pytest.raises(ValueError, match="physical_v17_forbidden"):
        DIAGNOSTIC.forbid_v17([Path("D:/sealed/physical_v17")])
