from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_faster_whisper_tuning_v8.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_faster_whisper_tuning_v8", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _Segment:
    def __init__(self, text: str, words: list[object] | None = None) -> None:
        self.text = text
        self.words = words


class _Word:
    def __init__(self, start: float, end: float, word: str) -> None:
        self.start = start
        self.end = end
        self.word = word


def test_join_segment_texts_strips_and_joins_nonempty_hypotheses() -> None:
    assert MODULE.join_segment_texts(
        [_Segment(" hola "), _Segment("mundo")]
    ) == "hola mundo"


def test_slot_transcripts_assigns_words_by_timestamp_midpoint() -> None:
    transcripts = MODULE.slot_transcripts(
        segments=[
            _Segment(
                "ignored",
                [_Word(0.2, 0.8, " casa"), _Word(2.1, 2.7, "mundo")],
            )
        ],
        slots=3,
        slot_seconds=2.0,
    )
    assert transcripts == ["casa", "mundo", ""]


def test_write_score_cache_aligns_exact_candidate_matches(tmp_path: Path) -> None:
    path = tmp_path / "scores.npz"
    MODULE.write_score_cache(
        path=path,
        whole_scores=np.asarray([[1.0, 0.5], [0.2, 1.0]]),
        token_scores=np.asarray([[1.0, 0.7], [0.4, 1.0]]),
        transcripts=["casa", "mundo"],
        candidate_words=[["casa", "cosa"], ["casa", "mundo"]],
        query_audio_sha256=["a" * 64, "b" * 64],
        query_words=["casa", "mundo"],
    )
    with np.load(path) as cache:
        assert cache["schema"].tolist() == [
            "baxy.mswc-faster-whisper-score-cache.v1"
        ]
        assert cache["exact_candidate_match"].tolist() == [[1, 0], [0, 1]]
