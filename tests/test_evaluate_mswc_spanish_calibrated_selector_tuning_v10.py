from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_calibrated_selector_tuning_v10.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_calibrated_selector_tuning_v10", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_word_group_folds_keep_each_word_in_one_fold() -> None:
    folds = MODULE.word_group_folds(
        ["casa", "casa", "mundo", "mundo"], seed=12301, fold_count=5
    )
    assert folds[0] == folds[1]
    assert folds[2] == folds[3]


def test_apply_selector_choices_changes_only_required_winner() -> None:
    scores = MODULE.apply_selector_choices(
        base_scores=np.asarray([[3.0, 2.0], [1.0, 4.0]]),
        selected_candidates=np.asarray([1, 1]),
    )
    assert scores.argmax(axis=1).tolist() == [1, 1]
    assert scores[0, 0] == 3.0
    assert scores[1].tolist() == [1.0, 4.0]
