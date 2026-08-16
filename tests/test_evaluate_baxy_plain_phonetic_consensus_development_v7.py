from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_plain_phonetic_consensus_development_v7.py"
)
SPEC = importlib.util.spec_from_file_location("plain_phonetic_v7", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WakeStub:
    @staticmethod
    def has_exact_lexical_target(transcript: str) -> bool:
        return "baxi" in transcript.casefold().split()

    @staticmethod
    def lexical_words(transcript: str) -> tuple[str, ...]:
        return tuple(transcript.casefold().split())


WAKE = WakeStub()


def test_levenshtein_distance_handles_insertions_substitutions_and_identity() -> None:
    assert MODULE.levenshtein_distance("baxy", "baxy") == 0
    assert MODULE.levenshtein_distance("baxi", "basi") == 1
    assert MODULE.levenshtein_distance("bakse", "base") == 1
    assert MODULE.levenshtein_distance("baxy", "otra") == 4


def test_plain_near_evidence_is_token_bounded_and_accent_normalized() -> None:
    assert MODULE.has_plain_near_wake_evidence("hola báxi abre música", WAKE)
    assert MODULE.has_plain_near_wake_evidence("dijo baksi", WAKE)
    assert MODULE.has_plain_near_wake_evidence("dijo baxu", WAKE)
    assert not MODULE.has_plain_near_wake_evidence("baxylarguisimo", WAKE)
    assert not MODULE.has_plain_near_wake_evidence("abre el calendario", WAKE)


def test_minimum_distance_returns_none_without_eligible_words() -> None:
    assert MODULE.minimum_plain_wake_distance("a y") is None


def test_span_phonetic_distance_handles_spanish_renderings() -> None:
    assert MODULE.spanish_phonetic_key("Baxy") == "baksi"
    assert MODULE.spanish_phonetic_key("vaksi") == "baksi"
    assert MODULE.minimum_plain_wake_distance("paz y") == 2
