"""The wake detector ran the conv-attention ONNX model on the 2s window EVERY
32ms chunk (~31 Hz) while idle-listening — the dominant idle CPU of the wake
stage (ONNX-without-throttle froze the PC in earlier sprints). It now scores the
rolling window only every Nth chunk (~8 Hz), keeping the buffer fresh so
detection quality is unchanged. These tests pin the throttle + buffer freshness.

Uses a fake model that counts predict() calls — no real ONNX / audio device."""
from __future__ import annotations

import unittest

import numpy as np

from gemma4_agent.voice.audio_io import CHUNK_SAMPLES
from gemma4_agent.voice.wake import (
    LIVEKIT_PREDICT_EVERY_N_CHUNKS,
    LIVEKIT_WINDOW_SAMPLES,
    WakeDetector,
)


class _CountingModel:
    def __init__(self):
        self.calls = 0

    def predict(self, ring):
        self.calls += 1
        return 0.0


def _detector():
    w = WakeDetector.__new__(WakeDetector)
    w._lk_ring = np.zeros(0, dtype=np.int16)
    w._lk_chunk_count = 0
    w._livekit_model = _CountingModel()
    w._evaluate_score = lambda *a, **k: None  # ignore scoring
    return w


def _fill(w, chunk):
    # Feed enough chunks to fill the 2s window.
    for _ in range(LIVEKIT_WINDOW_SAMPLES // CHUNK_SAMPLES + 1):
        w._feed_livekit(chunk)


class TestWakePredictThrottle(unittest.TestCase):
    def test_predict_is_decimated(self):
        w = _detector()
        chunk = np.ones(CHUNK_SAMPLES, dtype=np.int16)
        _fill(w, chunk)
        w._livekit_model.calls = 0
        n = 100
        for _ in range(n):
            w._feed_livekit(chunk)
        expected = n // LIVEKIT_PREDICT_EVERY_N_CHUNKS
        self.assertLessEqual(abs(w._livekit_model.calls - expected), 1,
                             f"predict should run ~{expected}x for {n} chunks")
        self.assertLess(w._livekit_model.calls, n,
                        "throttle must reduce predict calls below 1-per-chunk")

    def test_buffer_stays_at_window_size(self):
        # Detection quality depends on always scoring a fresh full window.
        w = _detector()
        chunk = np.ones(CHUNK_SAMPLES, dtype=np.int16)
        _fill(w, chunk)
        for _ in range(50):
            w._feed_livekit(chunk)
        self.assertEqual(w._lk_ring.size, LIVEKIT_WINDOW_SAMPLES)

    def test_no_predict_before_window_full(self):
        w = _detector()
        chunk = np.ones(CHUNK_SAMPLES, dtype=np.int16)
        # One chunk only — far from a full 2s window.
        w._feed_livekit(chunk)
        self.assertEqual(w._livekit_model.calls, 0)

    def test_reset_clears_counter(self):
        w = _detector()
        chunk = np.ones(CHUNK_SAMPLES, dtype=np.int16)
        _fill(w, chunk)
        # reset() touches several fields; give it the ones it needs.
        w._oww_buf = np.zeros(0, dtype=np.int16)
        w._last_fire_at = 0.0
        w._last_partial_at = 0.0
        w._oww_model = None
        w.reset()
        self.assertEqual(w._lk_chunk_count, 0)
        self.assertEqual(w._lk_ring.size, 0)


if __name__ == "__main__":
    unittest.main()
