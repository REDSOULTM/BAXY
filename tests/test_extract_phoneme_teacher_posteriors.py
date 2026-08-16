from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest
import torch


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_phoneme_teacher_posteriors.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_phoneme_teacher_posteriors", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_category_ids_are_disjoint_and_cover_teacher_vocabulary() -> None:
    vocabulary = {
        "<pad>": 0,
        "b": 1,
        "β": 2,
        "v": 3,
        "f": 4,
        "p": 5,
        "a": 6,
        "æ": 7,
        "ɑ": 8,
        "ʌ": 9,
        "k": 10,
        "s": 11,
        "sʲ": 12,
        "ʃ": 13,
        "i": 14,
        "ɪ": 15,
        "x": 16,
    }

    result = MODULE.resolve_category_ids(vocabulary, 0)

    flattened = [value for ids in result.values() for value in ids]
    assert sorted(flattened) == list(range(17))
    assert len(flattened) == len(set(flattened))


def test_category_aggregation_preserves_probability_mass() -> None:
    vocabulary = {
        "<pad>": 0,
        "b": 1,
        "β": 2,
        "v": 3,
        "f": 4,
        "p": 5,
        "a": 6,
        "æ": 7,
        "ɑ": 8,
        "ʌ": 9,
        "k": 10,
        "s": 11,
        "sʲ": 12,
        "ʃ": 13,
        "i": 14,
        "ɪ": 15,
        "x": 16,
    }
    category_ids = MODULE.resolve_category_ids(vocabulary, 0)
    probabilities = torch.softmax(torch.randn(2, 3, len(vocabulary)), dim=-1)

    result = MODULE.aggregate_categories(torch, probabilities, category_ids)

    assert result.shape == (2, 3, len(MODULE.CATEGORY_NAMES))
    assert np.allclose(result.sum(dim=-1).numpy(), 1.0, atol=1e-6)


def test_category_ids_reject_missing_required_phoneme() -> None:
    with pytest.raises(ValueError, match="vocabulary_missing"):
        MODULE.resolve_category_ids({"<pad>": 0}, 0)
