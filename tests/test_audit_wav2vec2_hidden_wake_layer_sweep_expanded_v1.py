from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_wav2vec2_hidden_wake_layer_sweep_expanded_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_wav2vec2_hidden_wake_layer_sweep_expanded_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_normalize_rows_produces_unit_vectors() -> None:
    values = MODULE.normalize_rows(np.asarray([[3.0, 4.0], [0.0, 2.0]]))
    np.testing.assert_allclose(np.linalg.norm(values, axis=1), np.ones(2))


def test_product_margins_hold_out_complete_groups() -> None:
    aligned = np.asarray(
        [[1.0, 0.0], [0.9, 0.1], [0.0, 0.0], [0.0, 0.0], [1.0, 0.0], [0.0, 0.0]]
    )
    scans = [
        np.asarray([[1.0, 0.0]]),
        np.asarray([[0.9, 0.1]]),
        np.asarray([[0.0, 1.0]]),
        np.asarray([[0.0, 1.0]]),
        np.asarray([[1.0, 0.0]]),
        np.asarray([[0.0, 1.0]]),
    ]
    labels = np.asarray([1, 1, 0, 0, 1, 0])
    groups = ["a", "b", "a", "b", "c", "c"]
    margins, _, folds = MODULE.speaker_held_out_product_margins(
        aligned_positive_vectors=aligned,
        product_vectors=scans,
        labels=labels,
        groups=groups,
    )
    assert np.all(margins[labels == 1] > 0.0)
    assert np.all(margins[labels == 0] < 0.0)
    assert {fold["held_group"] for fold in folds} == {"a", "b", "c"}


def test_config_rank_prioritizes_false_accept_safety() -> None:
    safe = {"negative_false_accepts": 0, "positive_accepted": 1, "speaker_held_out_auc": 0.7}
    unsafe = {"negative_false_accepts": 1, "positive_accepted": 10, "speaker_held_out_auc": 0.9}
    assert MODULE.config_rank(safe) > MODULE.config_rank(unsafe)
