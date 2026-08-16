from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "score_ccby_wake_holdout.py"
)
SPEC = importlib.util.spec_from_file_location("score_ccby_wake_holdout", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PeakPredictor:
    def predict(self, audio_chunk: np.ndarray) -> dict[str, float]:
        return {"candidate": float(np.max(audio_chunk))}


def test_streaming_windows_recover_keyword_near_start_of_three_second_clip() -> None:
    audio = np.zeros(3 * 16_000, dtype=np.float32)
    audio[round(0.56 * 16_000) : round(0.72 * 16_000)] = 0.9

    score, end_seconds, count = MODULE.streaming_max_score(PeakPredictor(), audio)

    assert score == pytest.approx(0.9)
    assert 0.56 <= end_seconds <= 2.56
    assert count > 15


def test_blind_freeze_rejects_model_hash_mismatch() -> None:
    freeze = {
        "schema": "baxy.wake-candidate-freeze.v1",
        "model_sha256": "a" * 64,
        "threshold": 0.42,
        "preregistration_sha256": "b" * 64,
        "development_only_evidence": True,
    }

    with pytest.raises(ValueError, match="blind_model_hash_mismatch"):
        MODULE.validate_blind_freeze(
            freeze=freeze,
            model_sha256="c" * 64,
            threshold=0.42,
            preregistration_sha256="b" * 64,
        )


def test_blind_freeze_requires_development_only_evidence() -> None:
    freeze = {
        "schema": "baxy.wake-candidate-freeze.v1",
        "model_sha256": "a" * 64,
        "threshold": 0.42,
        "preregistration_sha256": "b" * 64,
        "development_only_evidence": False,
    }

    with pytest.raises(
        ValueError, match="candidate_was_not_frozen_from_development_only_evidence"
    ):
        MODULE.validate_blind_freeze(
            freeze=freeze,
            model_sha256="a" * 64,
            threshold=0.42,
            preregistration_sha256="b" * 64,
        )
