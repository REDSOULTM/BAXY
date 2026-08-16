from __future__ import annotations

import importlib.util
from pathlib import Path
import random

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_baxy_hyperspotter_binary_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_baxy_hyperspotter_binary_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_persona_split_is_deterministic_complete_and_disjoint() -> None:
    personas = {f"voice_{index}" for index in range(12)}
    first = MODULE.split_personas(personas, seed=97, validation_personas=3)
    second = MODULE.split_personas(personas, seed=97, validation_personas=3)
    assert first == second
    training, validation = first
    assert len(training) == 9
    assert len(validation) == 3
    assert not training & validation
    assert training | validation == personas


def test_balanced_batch_contains_equal_classes() -> None:
    indexes, labels = MODULE.balanced_batch_indexes(
        positive_indexes=[1, 2],
        negative_indexes=[8, 9],
        batch_size=8,
        rng=random.Random(4),
    )
    assert len(indexes) == 8
    assert labels.count(1.0) == 4
    assert labels.count(0.0) == 4
    assert all(
        index in ({1, 2} if label else {8, 9})
        for index, label in zip(indexes, labels, strict=True)
    )


def test_binary_metrics_report_zero_false_recall() -> None:
    metrics = MODULE.binary_metrics(
        np.asarray([1, 1, 0, 0]), np.asarray([0.9, 0.3, 0.2, -0.1])
    )
    assert metrics["auc"] == 1.0
    assert metrics["positive_accepted_at_zero_false"] == 2
    assert metrics["zero_false_positive_recall"] == 1.0


def test_persona_split_rejects_empty_side() -> None:
    with pytest.raises(ValueError, match="persona_schedule_invalid"):
        MODULE.split_personas({"a", "b"}, seed=1, validation_personas=2)
