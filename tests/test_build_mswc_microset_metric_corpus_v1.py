from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_mswc_microset_metric_corpus_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_mswc_microset_metric_corpus_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_safe_link_accepts_only_word_and_opus_name() -> None:
    assert MODULE.safe_link("hello/clip.opus") == "hello/clip.opus"
    for value in ("../clip.opus", "hello/nested/clip.opus", "C:/clip.opus", "hello/clip.wav"):
        with pytest.raises(ValueError):
            MODULE.safe_link(value)


def test_deterministic_select_is_stable_and_bounded() -> None:
    values = [f"word/{index}.opus" for index in range(20)]
    first = MODULE.deterministic_select(values, limit=5, material="seed")
    second = MODULE.deterministic_select(values, limit=5, material="seed")
    assert first == second
    assert len(first) == 5
    assert set(first) <= set(values)
