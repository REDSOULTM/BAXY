from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_baxy_hyperspotter_physical_runtime_logmel_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_baxy_hyperspotter_physical_runtime_logmel_v2", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_short_clip_is_left_padded_to_exact_runtime_view() -> None:
    audio = np.ones(8_000, dtype=np.float32)
    windows = MODULE.continuous_runtime_windows(audio)
    assert len(windows) == 1
    start, window = windows[0]
    assert start == 0
    assert window.shape == (48_000,)
    assert np.count_nonzero(window[:16_000]) == 0
    assert np.all(window[16_000:24_000] == 1.0)


def test_longer_clip_uses_frozen_hop_and_exact_final_window() -> None:
    audio = np.ones(30_000, dtype=np.float32)
    windows = MODULE.continuous_runtime_windows(audio)
    starts = [start for start, _ in windows]
    assert starts == [0, 4_000, 8_000, 12_000, 14_000]
    assert all(window.shape == (48_000,) for _, window in windows)


def test_runtime_windows_reject_empty_audio() -> None:
    with pytest.raises(ValueError, match="audio_invalid"):
        MODULE.continuous_runtime_windows(np.empty(0, dtype=np.float32))
