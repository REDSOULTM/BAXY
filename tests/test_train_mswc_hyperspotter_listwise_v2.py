from __future__ import annotations

import importlib.util
from pathlib import Path
import random


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_mswc_hyperspotter_listwise_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_mswc_hyperspotter_listwise_v2", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_sample_listwise_examples_keeps_positive_first_and_negatives_unique() -> None:
    words = ["casa", "cosa", "masa", "mundo", "vaso", "paso"]
    indexes = {word: [index] for index, word in enumerate(words)}
    hard = {
        word: [candidate for candidate in words if candidate != word][:3]
        for word in words
    }
    audio, spoken, candidates = MODULE.sample_listwise_examples(
        words=words,
        indexes_by_word=indexes,
        hard_negatives=hard,
        count=12,
        hard_candidates=2,
        random_candidates=1,
        rng=random.Random(3),
    )
    assert len(audio) == len(spoken) == len(candidates) == 12
    for index, word, row in zip(audio, spoken, candidates, strict=True):
        assert words[index] == word
        assert row[0] == word
        assert len(row) == len(set(row)) == 4


def test_validation_schedule_is_balanced_before_reusing_a_word() -> None:
    words = ["casa", "mundo"]
    indexes = {"casa": [0, 1], "mundo": [2, 3]}
    hard = {"casa": ["mundo"], "mundo": ["casa"]}
    audio, spoken, candidates = MODULE.validation_schedule(
        words=words,
        indexes_by_word=indexes,
        hard_negatives=hard,
        examples=4,
        negative_candidates=1,
        seed=7,
    )
    assert set(audio) == {0, 1, 2, 3}
    assert spoken.count("casa") == spoken.count("mundo") == 2
    assert all(row[0] == word for row, word in zip(candidates, spoken, strict=True))
