from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_wake_verifier_negative_holdout_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_wake_verifier_negative_holdout_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _EnergyVad:
    def reset(self) -> None:
        return None

    def process(self, frame: np.ndarray) -> float:
        return float(np.max(np.abs(frame)) > 0.5)


def test_capture_keeps_five_second_history_and_caps_long_mission() -> None:
    audio = np.arange(40 * 16_000, dtype=np.float32)

    captured, source_start = MODULE.capture_audio(
        audio,
        hit_end_seconds=8.0,
        pre_roll_seconds=5.0,
        maximum_turn_samples=30 * 16_000,
    )

    assert source_start == 8 * 16_000 - 156 * 512
    assert len(captured) == 30 * 16_000
    np.testing.assert_array_equal(captured[:100], audio[source_start : source_start + 100])


def test_capture_left_pads_when_hit_precedes_full_history() -> None:
    audio = np.ones(2 * 16_000, np.float32)

    captured, source_start = MODULE.capture_audio(
        audio,
        hit_end_seconds=1.0,
        pre_roll_seconds=5.0,
        maximum_turn_samples=30 * 16_000,
    )

    assert source_start == 0
    leading = 156 * 512 - 16_000
    assert np.count_nonzero(captured[:leading]) == 0
    assert np.all(captured[leading : leading + 2 * 16_000] == 1.0)


def test_selected_records_uses_first_causal_broad_hit() -> None:
    corpus = {
        "records": [
            {"utterance_id": "1", "relative_path": "a.flac"}
        ]
    }
    scan = {
        "records": [
            {
                "utterance_id": "1",
                "relative_path": "a.flac",
                "retained_windows": [
                    {"window_end_seconds": 1.0, "score": 0.021},
                    {"window_end_seconds": 2.0, "score": 0.9},
                ],
            }
        ]
    }

    selected = MODULE.selected_records(corpus, scan)

    assert selected[0]["hit"]["score"] == 0.021


def test_activity_verification_start_skips_silent_history() -> None:
    capture = np.concatenate(
        (np.zeros(4 * 16_000, np.float32), np.ones(16_000, np.float32))
    )

    start = MODULE.activity_verification_start(
        capture,
        pre_roll_seconds=5.0,
        threshold=0.1,
        alignment_samples=320,
        default_start_sample=64_000,
        vad=_EnergyVad(),
    )

    assert start == 4.0 * 16_000


def test_checkpoint_preserves_runtime_across_resume(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    selected = [
        {
            "source": {"utterance_id": "1", "relative_path": "a.flac"},
            "hit": {"window_end_seconds": 1.0, "score": 0.02},
        }
    ]
    records = [
        {
            "utterance_id": "1",
            "relative_path": "a.flac",
            "hit_window_end_seconds": 1.0,
            "stage1_confidence": 0.02,
        }
    ]

    MODULE._checkpoint(
        path,
        preregistration_sha256="a" * 64,
        scan_sha256="b" * 64,
        evaluation_seconds=12.5,
        records=records,
    )
    restored, seconds = MODULE._load_checkpoint(
        path,
        preregistration_sha256="a" * 64,
        scan_sha256="b" * 64,
        selected=selected,
    )

    assert restored == records
    assert seconds == pytest.approx(12.5)


def test_opened_holdout_is_forced_to_development_authority() -> None:
    corpus = {"schema": "baxy.openslr-librispeech-negative-holdout.v1"}
    preregistration = {
        "schema": "baxy.wake-verifier-negative-holdout-preregistration.v1",
        "negative_corpus_previously_accessed": True,
        "fresh_holdout_claim_supported": False,
        "far_certification_supported": False,
        "product_operating_point": False,
    }

    assert MODULE.opened_negative_regression_authority(
        corpus,
        preregistration,
        preregistration_supplied=True,
    )


def test_opened_holdout_cannot_regain_authority_by_changing_one_claim() -> None:
    corpus = {"schema": "baxy.openslr-librispeech-negative-holdout.v1"}
    preregistration = {
        "schema": "baxy.wake-verifier-negative-holdout-preregistration.v1",
        "negative_corpus_previously_accessed": True,
        "fresh_holdout_claim_supported": False,
        "far_certification_supported": True,
        "product_operating_point": False,
    }

    assert not MODULE.opened_negative_regression_authority(
        corpus,
        preregistration,
        preregistration_supplied=True,
    )
