from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_qbye_sequence_tuning_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_qbye_sequence_tuning_v3", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_edit_similarity_is_normalized_and_symmetric() -> None:
    assert MODULE.edit_similarity([1, 2, 3], [1, 2, 3]) == 1.0
    assert MODULE.edit_similarity([1, 2, 3], [1, 4, 3]) == pytest.approx(2 / 3)
    assert MODULE.edit_similarity([1, 4, 3], [1, 2, 3]) == pytest.approx(2 / 3)


def test_score_metrics_counts_zero_false_true_pairs() -> None:
    values = np.asarray([[0.9, 0.1], [0.2, 0.8]], dtype=np.float64)
    metrics = MODULE.score_metrics(
        scores=values,
        class_names=["a", "b"],
        query_classes=["a", "b"],
    )
    assert metrics["top1_accuracy"] == 1.0
    assert metrics["true_pairs_accepted_at_zero_false_pairs"] == 2


def test_research_split_is_disjoint_and_complete() -> None:
    words = {f"word{i}" for i in range(6)}
    tuning, reserved = MODULE.split_research_words(words, seed=1, tuning_classes=4)
    assert len(tuning) == 4
    assert len(reserved) == 2
    assert not tuning & reserved
    assert tuning | reserved == words
