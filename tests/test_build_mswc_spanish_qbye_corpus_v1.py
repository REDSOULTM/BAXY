from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_mswc_spanish_qbye_corpus_v1.py"
)
SPEC = importlib.util.spec_from_file_location("build_mswc_spanish_qbye_corpus_v1", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_target_neighborhood_is_excluded_without_banning_unrelated_words() -> None:
    for word in ("baxy", "baxi", "baksi", "faxi", "vaxi", "bakshi", "taxi"):
        assert MODULE.target_neighborhood_excluded(word)
    assert not MODULE.target_neighborhood_excluded("casa")
    assert not MODULE.target_neighborhood_excluded("computador")


def test_distinct_speaker_selection_is_deterministic() -> None:
    rows = [
        {"WORD": "casa", "SPEAKER": "speaker-a", "LINK": "casa/a.opus"},
        {"WORD": "casa", "SPEAKER": "speaker-a", "LINK": "casa/b.opus"},
        {"WORD": "casa", "SPEAKER": "speaker-b", "LINK": "casa/c.opus"},
        {"WORD": "casa", "SPEAKER": "speaker-c", "LINK": "casa/d.opus"},
    ]
    first = MODULE.select_distinct_speakers(rows, count=3, seed=7, role="train")
    second = MODULE.select_distinct_speakers(list(reversed(rows)), count=3, seed=7, role="train")
    assert first == second
    assert len({row["SPEAKER"] for row in first}) == 3


def test_word_ranking_is_input_order_independent() -> None:
    first = MODULE.rank_words(["casa", "perro", "gato"], seed=11, role="eval")
    second = MODULE.rank_words(["gato", "casa", "perro"], seed=11, role="eval")
    assert first == second
