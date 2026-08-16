from __future__ import annotations

import importlib.util
from pathlib import Path
import random

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_baxy_hyperspotter_physical_adaptation_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_baxy_hyperspotter_physical_adaptation_v3", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_mixed_batch_has_equal_domain_and_class_quarters() -> None:
    selections, labels = MODULE.mixed_domain_batch_indexes(
        synthetic_positive=[1],
        synthetic_negative=[2],
        physical_positive=[3],
        physical_negative=[4],
        batch_size=8,
        rng=random.Random(7),
    )
    assert len(selections) == len(labels) == 8
    assert sum(domain == "synthetic" for domain, _ in selections) == 4
    assert sum(domain == "physical" for domain, _ in selections) == 4
    assert labels.count(1.0) == labels.count(0.0) == 4


def test_partition_indexes_preserves_persona_boundary() -> None:
    records = [
        {"persona_id": "train"},
        {"persona_id": "validation"},
        {"persona_id": "train"},
    ]
    training, validation = MODULE.partition_indexes(
        records,
        training_personas={"train"},
        validation_personas={"validation"},
    )
    assert training == [0, 2]
    assert validation == [1]


def test_partition_indexes_rejects_unknown_persona() -> None:
    with pytest.raises(ValueError, match="outside_split"):
        MODULE.partition_indexes(
            [{"persona_id": "unknown"}],
            training_personas={"train"},
            validation_personas={"validation"},
        )


def test_candidate_rank_prioritizes_zero_false_physical_recall() -> None:
    safer = {
        "zero_false_positive_recall": 1.0,
        "auc": 0.9,
        "equal_error_rate": 0.1,
    }
    prettier = {
        "zero_false_positive_recall": 0.9,
        "auc": 1.0,
        "equal_error_rate": 0.0,
    }
    synthetic = {
        "zero_false_positive_recall": 1.0,
        "auc": 1.0,
        "equal_error_rate": 0.0,
    }
    assert MODULE.candidate_rank(safer, synthetic) > MODULE.candidate_rank(
        prettier, synthetic
    )


def test_auxiliary_replacement_preserves_labels() -> None:
    selections = [("physical", 1), ("physical", 2), ("synthetic", 3)]
    replaced = MODULE.replace_physical_with_auxiliary(
        selections,
        [1.0, 0.0, 1.0],
        auxiliary_positive=[10],
        auxiliary_negative=[20],
        probability=1.0,
        rng=random.Random(1),
    )
    assert replaced == [("auxiliary", 10), ("auxiliary", 20), ("synthetic", 3)]
