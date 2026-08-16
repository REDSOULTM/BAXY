from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_mswc_spanish_qbye_similarity_cnn_v4.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_mswc_spanish_qbye_similarity_cnn_v4", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_metric_word_split_is_disjoint_and_complete() -> None:
    words = {f"word{i}" for i in range(10)}
    training, validation = MODULE.split_metric_words(
        words, seed=1, validation_classes=3
    )
    assert len(training) == 7
    assert len(validation) == 3
    assert not training & validation
    assert training | validation == words


def test_normalized_word_distance_prefers_phonetic_neighbor_spelling() -> None:
    assert MODULE.normalized_word_distance("casa", "cosa") < MODULE.normalized_word_distance(
        "casa", "mundo"
    )


def test_pair_metrics_accept_perfect_separation() -> None:
    metrics = MODULE.pair_metrics(
        np.asarray([0, 0, 1, 1]), np.asarray([-2.0, -1.0, 1.0, 2.0])
    )
    assert metrics["pair_auc"] == 1.0
    assert metrics["equal_error_rate"] == 0.0
    assert metrics["accuracy_at_zero_logit"] == 1.0
