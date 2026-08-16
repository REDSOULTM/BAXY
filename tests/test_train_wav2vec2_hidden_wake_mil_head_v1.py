from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_wav2vec2_hidden_wake_mil_head_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_wav2vec2_hidden_wake_mil_head_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_validation_groups_is_deterministic_and_disjoint() -> None:
    groups = {f"speaker_{index}" for index in range(20)}
    first = MODULE.validation_groups(groups)
    second = MODULE.validation_groups(groups)
    assert first == second
    assert first
    assert first < groups


def test_metrics_from_scores_reports_zero_false_recall() -> None:
    metrics = MODULE.metrics_from_scores(
        np.asarray([0.9, 0.8, 0.2, -0.1]), np.asarray([1, 1, 0, 0])
    )
    assert metrics["zero_false_positive_accepted"] == 2
    assert metrics["zero_false_positive_rate"] == 1.0


def test_threshold_metrics_keeps_false_accepts_explicit() -> None:
    metrics = MODULE.threshold_metrics(
        np.asarray([0.9, 0.4, 0.5, -0.1]), np.asarray([1, 1, 0, 0]), 0.45
    )
    assert metrics["positive_accepted"] == 1
    assert metrics["negative_false_accepts"] == 1
