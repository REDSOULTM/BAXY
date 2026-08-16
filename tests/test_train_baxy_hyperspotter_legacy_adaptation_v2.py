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
    / "train_baxy_hyperspotter_legacy_adaptation_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_baxy_hyperspotter_legacy_adaptation_v2", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_mixed_batch_preserves_source_and_class_balance() -> None:
    selections, labels = MODULE.mixed_batch_indexes(
        synthetic_positive=[1, 2],
        synthetic_negative=[3, 4],
        human_positive=[5, 6],
        human_negative=[7, 8],
        batch_size=16,
        human_examples=8,
        rng=random.Random(3),
    )
    assert len(selections) == 16
    assert labels.count(1.0) == 8
    assert labels.count(0.0) == 8
    assert sum(source == "synthetic" for source, _ in selections) == 8
    assert sum(source == "human" for source, _ in selections) == 8


def test_conservative_threshold_covers_both_negative_sets() -> None:
    threshold = MODULE.conservative_zero_false_threshold(
        np.asarray([0.8, 0.2]),
        np.asarray([1, 0]),
        np.asarray([0.9, 0.4]),
        np.asarray([1, 0]),
    )
    assert threshold > 0.4
    assert np.nextafter(0.4, np.inf) == threshold


def test_mixed_batch_rejects_odd_human_schedule() -> None:
    with pytest.raises(ValueError, match="batch_schedule_invalid"):
        MODULE.mixed_batch_indexes(
            synthetic_positive=[1],
            synthetic_negative=[2],
            human_positive=[3],
            human_negative=[4],
            batch_size=8,
            human_examples=3,
            rng=random.Random(1),
        )
