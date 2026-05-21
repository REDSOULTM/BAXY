"""STT.transcribe defensive guards: never hand Whisper an empty/degenerate
buffer (undefined behaviour / wasted decode), and never crash on a missing
model. No real Whisper model loaded — we stub _model to assert it isn't touched
when the guards should short-circuit."""
from __future__ import annotations

import unittest

import numpy as np

from gemma4_agent.voice.stt import STT, SAMPLE_RATE


class _ExplodingModel:
    """Any call means a guard failed to short-circuit."""

    def transcribe(self, *a, **k):
        raise AssertionError("model.transcribe must not be called for this input")


def _stt_with_model(model):
    s = STT.__new__(STT)
    s._loaded = True
    s._model = model
    return s


class TestSttGuards(unittest.TestCase):
    def test_not_loaded_returns_empty(self):
        s = STT.__new__(STT)
        s._loaded = False
        s._model = None
        self.assertEqual(s.transcribe(np.ones(SAMPLE_RATE, dtype=np.int16)), "")

    def test_empty_audio_short_circuits(self):
        s = _stt_with_model(_ExplodingModel())
        self.assertEqual(s.transcribe(np.zeros(0, dtype=np.int16)), "")

    def test_subfloor_audio_short_circuits(self):
        # < 80 ms must not reach the model.
        s = _stt_with_model(_ExplodingModel())
        short = np.ones(int(0.04 * SAMPLE_RATE), dtype=np.int16)
        self.assertEqual(s.transcribe(short), "")

    def test_transcribe_exception_returns_empty(self):
        class _Raises:
            def transcribe(self, *a, **k):
                raise RuntimeError("decode blew up")

        s = _stt_with_model(_Raises())
        # > 80ms so it passes the empty guard and reaches the try/except.
        audio = np.ones(int(0.5 * SAMPLE_RATE), dtype=np.int16)
        self.assertEqual(s.transcribe(audio), "")


if __name__ == "__main__":
    unittest.main()
