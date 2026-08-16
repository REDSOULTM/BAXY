from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "filter_voxcpm2_wake_corpus.py"
)
SPEC = importlib.util.spec_from_file_location("filter_voxcpm2_wake_corpus", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NonZeroVad:
    def is_speech(self, payload: bytes, sample_rate: int) -> bool:
        assert sample_rate == MODULE.SAMPLE_RATE
        return bool(np.any(np.frombuffer(payload, dtype="<i2")))


class NeverVad:
    def is_speech(self, payload: bytes, sample_rate: int) -> bool:
        return False


def test_remove_silence_keeps_prefix_and_voiced_frames() -> None:
    prefix = np.ones(MODULE.VAD_MIN_START_SAMPLES, dtype=np.int16)
    silence = np.zeros(480, dtype=np.int16)
    speech = np.full(480, 1000, dtype=np.int16)
    audio = np.concatenate(
        [prefix, silence, *([speech, silence] * 6), silence]
    )

    result = MODULE.remove_silence(audio, vad=NonZeroVad())

    assert len(result) == len(prefix) + 6 * len(speech)
    assert np.array_equal(result[: len(prefix)], prefix)
    assert np.all(result[len(prefix) :] == 1000)


def test_remove_silence_falls_back_when_too_aggressive() -> None:
    audio = np.arange(5_000, dtype=np.int16)

    result = MODULE.remove_silence(audio, vad=NeverVad())

    assert np.array_equal(result, audio)


def test_inspect_pcm_reports_exact_contract() -> None:
    audio = np.asarray([1000, -1000] * 8_000, dtype=np.int16)

    result = MODULE.inspect_pcm(audio)

    assert result["sample_rate"] == 16_000
    assert result["duration_seconds"] == 1.0
    assert result["peak"] == 1000 / 32768
    assert result["rms"] == 1000 / 32768


def test_positive_phoneme_rule_requires_exact_full_target() -> None:
    assert MODULE.ipa_rejection_reason({"target_edit_distance": 0}, "positive") is None
    assert (
        MODULE.ipa_rejection_reason({"target_edit_distance": 1}, "positive")
        == "ipa_not_exact"
    )


def test_context_positive_rule_requires_embedded_exact_target() -> None:
    policy = "exact_target_subsequence"
    assert (
        MODULE.ipa_rejection_reason(
            {"target_edit_distance": 9, "exact_target_subsequence": True},
            "positive",
            policy,
        )
        is None
    )
    assert (
        MODULE.ipa_rejection_reason(
            {"target_edit_distance": 9, "exact_target_subsequence": False},
            "positive",
            policy,
        )
        == "ipa_target_subsequence_missing"
    )


def test_negative_phoneme_rule_rejects_embedded_target() -> None:
    assert (
        MODULE.ipa_rejection_reason(
            {"target_edit_distance": 4, "exact_target_subsequence": False},
            "adversarial_negative",
        )
        is None
    )
    assert (
        MODULE.ipa_rejection_reason(
            {"target_edit_distance": 4, "exact_target_subsequence": True},
            "adversarial_negative",
        )
        == "exact_target_subsequence_collision"
    )


def test_negative_phoneme_rule_fails_closed_without_subsequence_audit() -> None:
    with pytest.raises(
        ValueError, match="negative_audit_missing_exact_target_subsequence"
    ):
        MODULE.ipa_rejection_reason(
            {"target_edit_distance": 4}, "adversarial_negative"
        )
