"""Tests for the pre-transcription silence gate (Whisper hallucinates on
silence — e.g. '¡Suscríbete!'). Validates peak_window_rms and that the
default threshold separates silence/ambient from speech-level audio.

Pure-numpy; no audio hardware, no models. Safe to run anywhere."""
from __future__ import annotations

import unittest

import numpy as np

from gemma4_agent.voice.pipeline import (
    MIN_CAPTURE_RMS,
    SAMPLE_RATE,
    _RMS_WINDOW_S,
    peak_window_rms,
)

_WIN = int(_RMS_WINDOW_S * SAMPLE_RATE)


def _silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SAMPLE_RATE), dtype=np.int16)


def _noise(seconds: float, rms: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    # Gaussian noise scaled to a target RMS, clipped to int16 range.
    x = rng.normal(0.0, rms, int(seconds * SAMPLE_RATE))
    return np.clip(x, -32768, 32767).astype(np.int16)


def _tone(seconds: float, amp: float, freq: float = 200.0) -> np.ndarray:
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.int16)


class TestPeakWindowRms(unittest.TestCase):
    def test_empty_is_zero(self):
        self.assertEqual(peak_window_rms(np.zeros(0, dtype=np.int16), _WIN), 0.0)
        self.assertEqual(peak_window_rms(None, _WIN), 0.0)

    def test_pure_silence_is_zero(self):
        self.assertEqual(peak_window_rms(_silence(2.0), _WIN), 0.0)

    def test_quiet_room_below_threshold(self):
        # Room/fan noise ~ rms 120 -> below the 350 default floor.
        a = _noise(2.0, rms=120, seed=1)
        self.assertLess(peak_window_rms(a, _WIN), MIN_CAPTURE_RMS)

    def test_speech_level_above_threshold(self):
        # A ~0.4s "word" at speech amplitude embedded in 1.4s trailing silence.
        word = _tone(0.4, amp=3000)
        clip = np.concatenate([_silence(0.3), word, _silence(1.4)]).astype(np.int16)
        peak = peak_window_rms(clip, _WIN)
        self.assertGreater(peak, MIN_CAPTURE_RMS,
                           f"speech peak {peak:.0f} should exceed floor {MIN_CAPTURE_RMS}")

    def test_short_word_not_diluted_by_trailing_silence(self):
        # The whole-clip RMS of one short word + long silence would be tiny;
        # peak-window must still catch the word. Contrast the two measures.
        word = _tone(0.25, amp=2500)
        clip = np.concatenate([word, _silence(2.0)]).astype(np.int16)
        whole_rms = float(np.sqrt(np.mean(clip.astype(np.float64) ** 2)))
        peak = peak_window_rms(clip, _WIN)
        self.assertGreater(peak, MIN_CAPTURE_RMS)
        self.assertGreater(peak, whole_rms,
                           "peak-window must exceed diluted whole-clip RMS")

    def test_no_int16_overflow(self):
        # Full-scale tone: naive int16 squaring overflows; float64 must not.
        loud = _tone(0.5, amp=32000)
        peak = peak_window_rms(loud, _WIN)
        self.assertGreater(peak, 10000)
        self.assertTrue(np.isfinite(peak))


if __name__ == "__main__":
    unittest.main()
