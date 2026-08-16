from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_qbye_ssl_baseline_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_qbye_ssl_baseline_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_qbye_metrics_recovers_separable_unseen_classes() -> None:
    enrollment = np.asarray(
        [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9]], dtype=np.float32
    )
    queries = np.asarray([[0.95, 0.05], [0.05, 0.95]], dtype=np.float32)
    metrics, breakdown = MODULE.qbye_metrics(
        enrollment_embeddings=enrollment,
        enrollment_classes=["alpha", "alpha", "beta", "beta"],
        query_embeddings=queries,
        query_classes=["alpha", "beta"],
    )
    assert metrics["top1_accuracy"] == 1.0
    assert metrics["positive_margin_queries"] == 2
    assert all(item["top1_correct"] for item in breakdown)


def test_mean_std_pooling_preserves_both_statistics() -> None:
    frames = np.asarray([[1.0, 2.0], [3.0, 6.0]], dtype=np.float32)
    result = MODULE.pooled_embedding(frames, "mean_std")
    np.testing.assert_allclose(result, [2.0, 4.0, 1.0, 2.0])


def test_open_word_split_is_disjoint_complete_and_deterministic() -> None:
    words = {f"word{index:03d}" for index in range(200)}
    tuning, selection = MODULE.split_open_words(words, seed=9107)
    repeated = MODULE.split_open_words(set(reversed(sorted(words))), seed=9107)
    assert (tuning, selection) == repeated
    assert len(tuning) == len(selection) == 100
    assert not tuning.intersection(selection)
    assert tuning.union(selection) == words
