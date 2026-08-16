from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "build_wav2vec2_qbyt_rir_candidate_v3.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_qbyt_rir_builder", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_room_impulse_convolution_preserves_direct_path_and_adds_tail() -> None:
    builder = _module()
    audio = np.zeros(160, dtype=np.float32)
    audio[20] = 1.0
    impulse = np.zeros(80, dtype=np.float32)
    impulse[5] = 1.0
    impulse[25] = 0.25

    augmented = builder.apply_room_impulse_response(audio, impulse)

    assert augmented.shape == (239,)
    assert int(np.argmax(np.abs(augmented))) == 25
    assert abs(float(augmented[45])) > 0.1
    assert np.isfinite(augmented).all()


def test_view_metrics_requires_every_positive_and_zero_negative() -> None:
    builder = _module()
    metrics = builder._view_metrics(
        np.asarray([0.8, 0.7, 0.2, 0.1]),
        np.asarray([1, 1, 0, 0]),
        0.5,
    )

    assert metrics["positiveAccepted"] == 2
    assert metrics["negativeFalseAccepts"] == 0
    assert metrics["gatePassed"] is True


def test_multiview_fit_accepts_clean_and_rir_alignment_per_positive() -> None:
    builder = _module()
    direction, threshold, scores, metrics = builder.fit_multiview_candidate(
        aligned_positive_vectors=np.asarray(
            [[1.0, 0.0], [0.9, 0.1], [1.0, 0.05], [0.85, 0.15]]
        ),
        product_vectors=[
            np.asarray([[1.0, 0.0], [0.9, 0.1]]),
            np.asarray([[0.95, 0.05]]),
            np.asarray([[0.0, 1.0], [0.2, 0.8]]),
            np.asarray([[0.1, 0.9]]),
        ],
        labels=np.asarray([1, 1, 0, 0]),
    )

    assert direction.shape == (2,)
    assert threshold > max(scores[2:])
    assert metrics["alignedViewsPerPositive"] == 2
    assert metrics["developmentFitGatePassed"] is True
