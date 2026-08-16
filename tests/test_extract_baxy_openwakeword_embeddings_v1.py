from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_baxy_openwakeword_embeddings_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_baxy_openwakeword_embeddings_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_runtime_windows_match_three_second_rolling_contract() -> None:
    audio = np.ones(30_000, dtype=np.float32)
    windows = MODULE.continuous_runtime_windows(audio)
    assert [start for start, _ in windows] == [0, 4_000, 8_000, 12_000, 14_000]
    assert all(window.shape == (48_000,) for _, window in windows)


def test_short_clip_starts_after_one_second_of_side_padding() -> None:
    audio = np.ones(8_000, dtype=np.float32)
    [(start, window)] = MODULE.continuous_runtime_windows(audio)
    assert start == 0
    assert np.count_nonzero(window[:16_000]) == 0
    assert np.all(window[16_000:24_000] == 1.0)


def test_pcm16_is_finite_clipped_and_deterministic() -> None:
    values = MODULE.pcm16(np.asarray([-2.0, -1.0, 0.0, 1.0, 2.0]))
    assert values.dtype == np.int16
    assert values.tolist() == [-32767, -32767, 0, 32767, 32767]
    with pytest.raises(ValueError, match="pcm_invalid"):
        MODULE.pcm16(np.asarray([np.nan], dtype=np.float32))


def test_physical_runtime_boundary_rejects_source_drift() -> None:
    runtime = {
        "schema": MODULE.RUNTIME_SCHEMA,
        "blind_human_audio_accessed": False,
        "development_only": True,
        "sources": {"physical_manifest_sha256": "different"},
        "contract": {
            "runtime_window_samples": MODULE.WINDOW_SAMPLES,
            "side_padding_samples": MODULE.SIDE_PADDING_SAMPLES,
            "hop_samples": MODULE.HOP_SAMPLES,
        },
        "records": [],
    }
    with pytest.raises(ValueError, match="runtime_boundary_invalid"):
        MODULE.physical_window_records(runtime, physical_manifest_sha256="expected")
