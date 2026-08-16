from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_hyperspotter_spanish_tuning_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_hyperspotter_spanish_tuning_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_candidate_matrix_places_true_word_first_and_unique_hard_words_after() -> None:
    class_names = ["casa", "cosa", "masa", "mundo"]
    matrix = MODULE.candidate_matrix(
        query_words=["casa", "mundo"],
        class_names=class_names,
        hard_negatives={
            "casa": ["cosa", "masa"],
            "mundo": ["cosa", "casa"],
        },
        negative_candidates=2,
    )
    assert matrix.tolist() == [[0, 1, 2], [3, 1, 0]]


def test_hard_pair_metrics_reports_rank_auc_and_zero_false_recall() -> None:
    metrics = MODULE.hard_pair_metrics(
        scores=np.asarray(
            [
                [4.0, 1.0, 0.0],
                [3.0, 2.0, 1.0],
                [0.5, 1.5, -1.0],
                [2.5, 0.5, 0.0],
            ],
            dtype=np.float32,
        ),
        query_words=["casa", "casa", "mundo", "mundo"],
    )
    assert metrics["hard_candidate_top1_accuracy"] == 0.75
    assert metrics["macro_word_hard_candidate_top1_accuracy"] == 0.75
    assert metrics["positive_margin_queries"] == 3
    assert metrics["true_pairs"] == 4
    assert metrics["hard_negative_pairs"] == 8
    assert metrics["true_pairs_accepted_at_zero_false_pairs"] == 3
    assert 0.0 <= metrics["pair_auc"] <= 1.0
    assert 0.0 <= metrics["equal_error_rate"] <= 1.0


def test_binary_auc_eer_handles_ties_without_sklearn() -> None:
    auc, eer, threshold = MODULE.binary_auc_eer(
        targets=np.asarray([0, 0, 1, 1]),
        scores=np.asarray([0.0, 0.5, 0.5, 1.0]),
    )
    assert auc == 0.875
    assert 0.0 <= eer <= 0.5
    assert np.isfinite(threshold)
