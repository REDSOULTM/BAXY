"""B3b — earcon de progreso (voice/earcon.py).

Testea la lógica (gate, generación de tono, throttle, best-effort, set de tools
lentas) mockeando sounddevice (sin audio real). La NATURALIDAD del sonido la valida
el usuario por escucha (físico). El hook en agent.py (dispara earcon antes de una
tool lenta) es un best-effort gated; su no-regresión la cubre la suite full.
"""
import os
import sys
import unittest
from unittest import mock

from ..voice import earcon


class TestEarconGate(unittest.TestCase):
    def test_default_off_optin_on(self):
        prev = os.environ.pop("GEMMA4_PROGRESS_EARCON", None)
        try:
            self.assertFalse(earcon.progress_earcon_enabled())
            os.environ["GEMMA4_PROGRESS_EARCON"] = "1"
            self.assertTrue(earcon.progress_earcon_enabled())
            os.environ["GEMMA4_PROGRESS_EARCON"] = "0"
            self.assertFalse(earcon.progress_earcon_enabled())
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_PROGRESS_EARCON", None)
            else:
                os.environ["GEMMA4_PROGRESS_EARCON"] = prev


class TestToneGeneration(unittest.TestCase):
    def test_generate_tone_shape_and_volume(self):
        import numpy as np
        tone, sr = earcon._generate_tone()
        self.assertEqual(sr, 22050)
        self.assertGreater(len(tone), 0)
        self.assertEqual(str(tone.dtype), "float32")
        # volumen bajo (no molesto, sin clip): |amplitud| <= 0.2
        self.assertLessEqual(float(np.max(np.abs(tone))), 0.2)


class TestPlayEarcon(unittest.TestCase):
    def setUp(self):
        earcon.reset_throttle()
        self._prev = os.environ.get("GEMMA4_PROGRESS_EARCON")

    def tearDown(self):
        earcon.reset_throttle()
        if self._prev is None:
            os.environ.pop("GEMMA4_PROGRESS_EARCON", None)
        else:
            os.environ["GEMMA4_PROGRESS_EARCON"] = self._prev

    def test_gated_off_does_not_play(self):
        os.environ.pop("GEMMA4_PROGRESS_EARCON", None)
        fake_sd = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"sounddevice": fake_sd}):
            self.assertFalse(earcon.play_progress_earcon(force=True))
        fake_sd.play.assert_not_called()

    def test_gated_on_plays_nonblocking(self):
        os.environ["GEMMA4_PROGRESS_EARCON"] = "1"
        fake_sd = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"sounddevice": fake_sd}):
            self.assertTrue(earcon.play_progress_earcon(force=True))
        fake_sd.play.assert_called_once()  # non-blocking sd.play

    def test_throttle_blocks_rapid_second(self):
        os.environ["GEMMA4_PROGRESS_EARCON"] = "1"
        fake_sd = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"sounddevice": fake_sd}):
            self.assertTrue(earcon.play_progress_earcon())   # primero dispara
            self.assertFalse(earcon.play_progress_earcon())  # throttled
        self.assertEqual(fake_sd.play.call_count, 1)

    def test_best_effort_swallows_audio_error(self):
        os.environ["GEMMA4_PROGRESS_EARCON"] = "1"
        fake_sd = mock.MagicMock()
        fake_sd.play.side_effect = RuntimeError("no audio device")
        with mock.patch.dict(sys.modules, {"sounddevice": fake_sd}):
            # no debe lanzar; devuelve False
            self.assertFalse(earcon.play_progress_earcon(force=True))


class TestSlowToolsSet(unittest.TestCase):
    def test_network_heavy_tools_trigger_earcon(self):
        for t in ("web", "vision", "browser_real", "computer_use", "document", "file_process"):
            self.assertIn(t, earcon.SLOW_TOOLS, t)

    def test_fast_tools_do_not_trigger_earcon(self):
        for t in ("audio", "window", "system", "session", "memory", "clipboard"):
            self.assertNotIn(t, earcon.SLOW_TOOLS, t)


if __name__ == "__main__":
    unittest.main()
