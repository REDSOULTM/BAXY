from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "adapt_wav2vec2_hidden_wake_human_group_cv_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "adapt_wav2vec2_hidden_wake_human_group_cv_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_human_group_folds_never_share_a_group() -> None:
    records = [
        {"group": "a", "label": "positive"},
        {"group": "a", "label": "negative"},
        {"group": "b", "label": "positive"},
        {"group": "c", "label": "negative"},
    ]
    folds = MODULE.human_group_folds(records, list(range(len(records))))
    assert [fold[0] for fold in folds] == ["a", "b", "c"]
    for held_group, training, held in folds:
        assert {records[index]["group"] for index in held} == {held_group}
        assert held_group not in {records[index]["group"] for index in training}


def test_calibrated_margin_uses_strictly_above_max_negative() -> None:
    assert MODULE.calibrated_margin(0.6, np.asarray([0.1, 0.5])) > 0.0
    assert MODULE.calibrated_margin(0.5, np.asarray([0.1, 0.5])) < 0.0


def test_aggregate_metrics_and_rank_prioritize_safety() -> None:
    safe = MODULE.aggregate_metrics(
        np.asarray([0.8, 0.2, -0.1, -0.2]), np.asarray([1, 1, 0, 0])
    )
    unsafe = MODULE.aggregate_metrics(
        np.asarray([0.8, -0.2, 0.1, -0.1]), np.asarray([1, 1, 0, 0])
    )
    assert safe["positive_accepted"] == 2
    assert safe["negative_false_accepts"] == 0
    assert MODULE.adaptation_rank(safe) > MODULE.adaptation_rank(unsafe)
