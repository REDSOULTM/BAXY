from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_mswc_hyperspotter_teacher_distillation_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_mswc_hyperspotter_teacher_distillation_v3", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_validation_rows_holds_out_exact_count_per_word() -> None:
    words = ["uno"] * 6 + ["dos"] * 6
    hashes = [f"{index:02d}" for index in range(12)]
    training, validation = MODULE.validation_rows(
        words, hashes, validation_per_word=2
    )
    assert training.tolist() == [0, 1, 2, 3, 6, 7, 8, 9]
    assert validation.tolist() == [4, 5, 10, 11]


def test_checkpoint_rank_prioritizes_top1() -> None:
    stronger_top1 = {
        "hard_candidate_top1_accuracy": 0.91,
        "pair_auc": 0.99,
        "equal_error_rate": 0.03,
        "true_pairs_accepted_at_zero_false_pairs": 10,
        "true_pairs": 100,
    }
    stronger_tail = {
        "hard_candidate_top1_accuracy": 0.90,
        "pair_auc": 1.0,
        "equal_error_rate": 0.0,
        "true_pairs_accepted_at_zero_false_pairs": 100,
        "true_pairs": 100,
    }
    assert MODULE.checkpoint_rank(stronger_top1) > MODULE.checkpoint_rank(
        stronger_tail
    )
