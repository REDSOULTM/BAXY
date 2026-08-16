from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments"
    / "wake_validation"
    / "train_baxy_phonetic_auxiliary_domain_loco_v2.py"
)
SPEC = importlib.util.spec_from_file_location("phonetic_auxiliary", PROGRAM)
assert SPEC is not None and SPEC.loader is not None
TRAINER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRAINER)


def records() -> list[dict[str, object]]:
    return [
        {
            "trainingDomain": domain,
            "label": label,
            "audioSha256": f"{domain}-{label}-{index}",
        }
        for domain in ("physical_a", "physical_b", "synthetic")
        for label in ("positive", "negative")
        for index in range(4)
    ]


def test_balanced_epoch_has_equal_domain_label_cells() -> None:
    sample = records()
    selected = TRAINER.balanced_domain_epoch_indexes(
        sample,
        list(range(len(sample))),
        np.random.default_rng(7),
        target_per_cell=6,
    )

    assert len(selected) == 36
    counts = {}
    for index in selected:
        key = (sample[index]["trainingDomain"], sample[index]["label"])
        counts[key] = counts.get(key, 0) + 1
    assert set(counts.values()) == {6}


def test_balanced_epoch_is_deterministic_for_seed() -> None:
    sample = records()
    first = TRAINER.balanced_domain_epoch_indexes(
        sample, list(range(len(sample))), np.random.default_rng(11), 5
    )
    second = TRAINER.balanced_domain_epoch_indexes(
        sample, list(range(len(sample))), np.random.default_rng(11), 5
    )

    assert first == second


def test_balanced_epoch_rejects_empty_cell() -> None:
    sample = [record for record in records() if record["label"] == "positive"]
    with pytest.raises(ValueError, match="domain_label_cell_empty"):
        TRAINER.balanced_domain_epoch_indexes(
            sample, list(range(len(sample))), np.random.default_rng(1), 3
        )


def test_multi_store_batch_rejects_hidden_size_mismatch() -> None:
    sample = [
        {
            "store": "a",
            "featureStart": 0,
            "featureEnd": 2,
        },
        {
            "store": "b",
            "featureStart": 0,
            "featureEnd": 2,
        },
    ]
    stores = {
        "a": np.zeros((2, 3), dtype=np.float16),
        "b": np.zeros((2, 4), dtype=np.float16),
    }
    with pytest.raises(ValueError, match="hidden_size_mismatch"):
        TRAINER.make_multi_store_batch(object(), stores, sample, [0, 1])


def test_component_loader_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="component_invalid"):
        TRAINER.load_component(tmp_path / "missing.py", "missing_component")
