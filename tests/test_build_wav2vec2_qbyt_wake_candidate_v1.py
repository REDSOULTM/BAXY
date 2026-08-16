from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "build_wav2vec2_qbyt_wake_candidate_v1.py"
)
SPEC = importlib.util.spec_from_file_location("baxy_qbyt_builder", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_fit_candidate_sets_strict_zero_false_threshold() -> None:
    direction, threshold, scores, metrics = MODULE.fit_candidate(
        aligned_positive_vectors=np.asarray([[1.0, 0.0], [0.9, 0.1]]),
        product_vectors=[
            np.asarray([[1.0, 0.0], [0.8, 0.2]]),
            np.asarray([[0.9, 0.1]]),
            np.asarray([[0.0, 1.0], [0.2, 0.8]]),
            np.asarray([[0.1, 0.9]]),
        ],
        labels=np.asarray([1, 1, 0, 0]),
    )
    assert direction.shape == (2,)
    assert threshold > max(scores[2:])
    assert metrics["positiveAccepted"] == 2
    assert metrics["negativeFalseAccepts"] == 0
    assert metrics["developmentFitGatePassed"] is True
