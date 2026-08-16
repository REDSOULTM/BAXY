from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_raw_denoiser_rolling_wake_v1.py"
)
SPEC = importlib.util.spec_from_file_location("raw_denoiser_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _Verifier:
    def score(self, audio: np.ndarray) -> float:
        return float(np.sum(audio))


def test_rolling_windows_are_fixed_and_cover_nine_offsets() -> None:
    audio = np.zeros(MODULE.WINDOW_SAMPLES, dtype=np.float32)
    audio[0] = 1.0
    windows = MODULE.rolling_windows(audio)

    assert len(windows) == 9
    assert all(window.shape == (MODULE.WINDOW_SAMPLES,) for window in windows)
    assert windows[0][MODULE.SIDE_PADDING_SAMPLES] == 1.0
    assert windows[4][0] == 1.0
    assert float(np.sum(windows[5])) == 0.0


def test_best_rolling_candidate_returns_argmax_window() -> None:
    audio = np.ones(MODULE.WINDOW_SAMPLES, dtype=np.float32)
    window, score, index = MODULE.best_rolling_candidate(_Verifier(), audio)

    assert index == 4
    assert score == pytest.approx(float(MODULE.WINDOW_SAMPLES))
    assert np.array_equal(window, MODULE.rolling_windows(audio)[4])


def test_denoise_candidate_pads_short_output() -> None:
    class _Output:
        sample_rate = MODULE.SAMPLE_RATE
        samples = np.ones(MODULE.WINDOW_SAMPLES - 128, dtype=np.float32)

    class _Denoiser:
        def __call__(self, samples: np.ndarray, sample_rate: int) -> _Output:
            assert samples.shape == (MODULE.WINDOW_SAMPLES,)
            assert sample_rate == MODULE.SAMPLE_RATE
            return _Output()

    result = MODULE.denoise_candidate(
        _Denoiser(), np.zeros(MODULE.WINDOW_SAMPLES, dtype=np.float32)
    )
    assert result.shape == (MODULE.WINDOW_SAMPLES,)
    assert np.all(result[-128:] == 0.0)
