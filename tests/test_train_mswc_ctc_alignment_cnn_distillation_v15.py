from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_mswc_ctc_alignment_cnn_distillation_v15.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_mswc_ctc_alignment_cnn_distillation_v15", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_pair_matrix_preserves_time_and_token_axes() -> None:
    probabilities = np.full((5, 4), 0.01, dtype=np.float64)
    probabilities[:, 0] = 0.80
    probabilities[1, 1] = 0.90
    probabilities[3, 2] = 0.90
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    matrix = MODULE.pair_matrix(
        log_probabilities=np.log(probabilities),
        sequence=[1, 2],
        blank_id=0,
        maximum_frames=8,
        maximum_tokens=4,
    )
    assert matrix.shape == (MODULE.INPUT_CHANNELS, 8, 4)
    assert np.isfinite(matrix).all()
    assert matrix[7, :5, :2].tolist() == np.ones((5, 2)).tolist()
    assert not matrix[7, 5:, :].any()
    assert not matrix[7, :, 2:].any()


def test_make_model_scores_one_value_per_pair() -> None:
    import torch

    model = MODULE.make_model(torch, manual_features=3)
    scores = model(torch.zeros(2, MODULE.INPUT_CHANNELS, 8, 4), torch.zeros(2, 3))
    assert tuple(scores.shape) == (2,)
