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
    / "train_baxy_openwakeword_closed_set_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_baxy_openwakeword_closed_set_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_balanced_batch_contains_each_domain_and_class() -> None:
    pools = {
        "synthetic_positive": [[1], [2]],
        "synthetic_negative": [[3]],
        "physical_positive": [[4]],
        "physical_negative": [[5], [6]],
    }
    indexes, labels, domains = MODULE.balanced_domain_batch(
        pools, batch_size=8, rng=random.Random(9)
    )
    assert len(indexes) == len(labels) == len(domains) == 8
    assert sum(label == 1.0 for label in labels) == 4
    assert domains.count("synthetic") == domains.count("physical") == 4


def test_group_reduction_uses_maximum_rolling_window() -> None:
    records = [
        {
            "domain": "wasapi_raw_physical",
            "record_id": "positive/1",
            "label": "positive",
        },
        {
            "domain": "wasapi_raw_physical",
            "record_id": "positive/1",
            "label": "positive",
        },
        {
            "domain": "wasapi_raw_physical",
            "record_id": "negative/1",
            "label": "adversarial_negative",
        },
    ]
    labels, scores = MODULE.reduce_group_scores(
        records, [0, 1, 2], np.asarray([0.1, 0.8, 0.6])
    )
    assert labels.tolist() == [0, 1]
    assert scores.tolist() == pytest.approx([0.6, 0.8])


def test_group_drift_is_rejected() -> None:
    records = [
        {
            "domain": "synthetic_clean",
            "source_index": 1,
            "label": "positive",
            "persona_id": "a",
        },
        {
            "domain": "synthetic_clean",
            "source_index": 1,
            "label": "positive",
            "persona_id": "b",
        },
    ]
    with pytest.raises(ValueError, match="group_drift"):
        MODULE.grouped_indexes(records, [0, 1])


def test_candidate_rank_prefers_zero_false_physical_recall() -> None:
    synthetic = {"zero_false_positive_recall": 1.0, "auc": 1.0}
    safer = {
        "zero_false_positive_recall": 0.9,
        "auc": 0.95,
        "equal_error_rate": 0.1,
    }
    prettier = {
        "zero_false_positive_recall": 0.8,
        "auc": 1.0,
        "equal_error_rate": 0.0,
    }
    assert MODULE.candidate_rank(safer, synthetic) > MODULE.candidate_rank(
        prettier, synthetic
    )
