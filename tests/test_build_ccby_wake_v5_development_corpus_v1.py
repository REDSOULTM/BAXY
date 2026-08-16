from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_ccby_wake_v5_development_corpus_v1.py"
)
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location(
    "build_ccby_wake_v5_development_corpus_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_target_words_uses_frozen_lexical_policy() -> None:
    record = {
        "lexical_candidates": [
            {
                "words": [
                    {"word": "Baxi", "start_seconds": 1.0},
                    {"word": "Bakshi", "start_seconds": 2.0},
                ]
            }
        ]
    }
    assert [word["word"] for word in MODULE.target_words(record)] == ["Baxi"]


def test_choose_negative_centers_avoids_target_context() -> None:
    record = {
        "source_id": "source",
        "segments": [
            {"start_seconds": 0.0, "end_seconds": 2.0, "text": "hello"},
            {"start_seconds": 10.0, "end_seconds": 12.0, "text": "Baxi"},
            {"start_seconds": 20.0, "end_seconds": 22.0, "text": "world"},
        ],
    }
    assert MODULE.choose_negative_centers(record, [11.0], 2) == [1.0, 21.0]


def test_choose_negative_centers_fails_closed_when_insufficient() -> None:
    record = {
        "source_id": "source",
        "segments": [
            {"start_seconds": 0.0, "end_seconds": 2.0, "text": "Baxi"}
        ],
    }
    with pytest.raises(ValueError, match="negative_context_insufficient"):
        MODULE.choose_negative_centers(record, [1.0], 1)
