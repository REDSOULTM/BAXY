from __future__ import annotations

import importlib.util
from pathlib import Path
import random


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_mswc_hyperspotter_spanish_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_mswc_hyperspotter_spanish_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_sample_examples_is_balanced_and_never_uses_same_negative_word() -> None:
    words = ["casa", "cosa", "mundo"]
    indexes = {word: [index * 2, index * 2 + 1] for index, word in enumerate(words)}
    hard = {"casa": ["cosa"], "cosa": ["casa"], "mundo": ["casa"]}
    audio_indexes, keywords, targets = MODULE.sample_examples(
        words=words,
        indexes_by_word=indexes,
        hard_negatives=hard,
        count=20,
        hard_negative_probability=1.0,
        rng=random.Random(1),
    )
    assert len(audio_indexes) == len(keywords) == len(targets) == 20
    assert int(targets.sum()) == 10
    for audio_index, keyword, target in zip(
        audio_indexes, keywords, targets, strict=True
    ):
        spoken_word = words[audio_index // 2]
        assert (keyword == spoken_word) == bool(target)
