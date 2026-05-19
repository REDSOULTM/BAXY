"""Tests for the WakeDetector orchestrator + openWakeWord backend
(Sprint R2 2026-05-18).

The orchestrator tests use unittest.mock to avoid actually loading
Vosk or openWakeWord. The backend tests run against the real
openWakeWord (SKIP if not installed)."""
from __future__ import annotations

import inspect
import os
import unittest
from unittest.mock import patch

import numpy as np


# Backend-name strings used by GEMMA4_WAKE_BACKEND.
_OWW = "oww"
_VOSK = "vosk"


def _noop_callback(phrase, ts, tail_s=0.0, confidence=0.0):
    pass


class OrchestratorTest(unittest.TestCase):
    """Backend-selection behavior of wake.WakeDetector."""

    def setUp(self) -> None:
        # Ensure the env var isn't leaking from another test.
        self._saved_env = os.environ.pop("GEMMA4_WAKE_BACKEND", None)

    def tearDown(self) -> None:
        if self._saved_env is not None:
            os.environ["GEMMA4_WAKE_BACKEND"] = self._saved_env
        else:
            os.environ.pop("GEMMA4_WAKE_BACKEND", None)

    def test_orchestrator_prefers_oww_when_loaded(self) -> None:
        # Sprint R2 default is "vosk" (no custom oww model yet);
        # this test exercises the auto path explicitly.
        from gemma4_agent.voice.wake import WakeDetector
        with patch(
            "gemma4_agent.voice.wake_oww.OpenWakeWordDetector.load",
            return_value=True,
        ):
            det = WakeDetector(on_wake=_noop_callback, backend="auto")
            self.assertTrue(det.load())
        self.assertEqual(det.backend, "oww")

    def test_orchestrator_falls_back_to_vosk_on_oww_fail(self) -> None:
        from gemma4_agent.voice.wake import WakeDetector
        with patch(
            "gemma4_agent.voice.wake_oww.OpenWakeWordDetector.load",
            return_value=False,
        ), patch(
            "gemma4_agent.voice.wake_vosk.VoskWakeDetector.load",
            return_value=True,
        ):
            det = WakeDetector(on_wake=_noop_callback, backend="auto")
            self.assertTrue(det.load())
        self.assertEqual(det.backend, "vosk")

    def test_default_backend_is_vosk(self) -> None:
        # Sprint R2 outcome B: default stays Vosk until a custom
        # 'hey gemma' oww model exists. See docs/architecture/
        # wake_custom_training_path.md.
        from gemma4_agent.voice.wake import WakeDetector
        with patch(
            "gemma4_agent.voice.wake_oww.OpenWakeWordDetector.load",
        ) as oww_load, patch(
            "gemma4_agent.voice.wake_vosk.VoskWakeDetector.load",
            return_value=True,
        ):
            det = WakeDetector(on_wake=_noop_callback)
            self.assertTrue(det.load())
        oww_load.assert_not_called()
        self.assertEqual(det.backend, "vosk")

    def test_env_var_forces_vosk(self) -> None:
        from gemma4_agent.voice.wake import WakeDetector
        os.environ["GEMMA4_WAKE_BACKEND"] = _VOSK
        with patch(
            "gemma4_agent.voice.wake_oww.OpenWakeWordDetector.load",
        ) as oww_load, patch(
            "gemma4_agent.voice.wake_vosk.VoskWakeDetector.load",
            return_value=True,
        ):
            det = WakeDetector(on_wake=_noop_callback)
            self.assertTrue(det.load())
        oww_load.assert_not_called()
        self.assertEqual(det.backend, "vosk")

    def test_env_var_forces_oww_no_fallback(self) -> None:
        """If GEMMA4_WAKE_BACKEND=oww and oww fails, do NOT fall
        back -- the operator opted out of Vosk explicitly."""
        from gemma4_agent.voice.wake import WakeDetector
        os.environ["GEMMA4_WAKE_BACKEND"] = _OWW
        with patch(
            "gemma4_agent.voice.wake_oww.OpenWakeWordDetector.load",
            return_value=False,
        ), patch(
            "gemma4_agent.voice.wake_vosk.VoskWakeDetector.load",
        ) as vosk_load:
            det = WakeDetector(on_wake=_noop_callback)
            self.assertFalse(det.load())
        vosk_load.assert_not_called()


class OpenWakeWordBackendTest(unittest.TestCase):
    """Behavior of OpenWakeWordDetector itself. Most of these need
    the real model loaded; they SKIP cleanly if oww isn't installed."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            import openwakeword  # noqa: F401
        except ImportError:
            cls.skipTest = lambda *a, **kw: None  # type: ignore[assignment]
            raise unittest.SkipTest("openwakeword not installed")

    def test_oww_threshold_smoke_silence_below_threshold(self) -> None:
        """Loaded model should NOT fire on a window of pure
        silence (zero score) -- catches the case where the loader
        accidentally inverts a sign or returns NaN."""
        from gemma4_agent.voice.wake_oww import OpenWakeWordDetector
        fires: list = []

        def on_wake(phrase, ts, tail, conf):
            fires.append((phrase, conf))

        det = OpenWakeWordDetector(on_wake=on_wake)
        if not det.load():
            self.skipTest(f"oww load failed: {det.last_error}")
        # Feed several 80ms windows of silence.
        for _ in range(20):
            det.feed(np.zeros(1280, dtype=np.int16))
        self.assertEqual(fires, [])

    def test_oww_chunk_buffering_accumulates_short_chunks(self) -> None:
        """The pipeline feeds 512-sample chunks; openWakeWord wants
        1280-sample windows. The buffer must accumulate."""
        from gemma4_agent.voice.wake_oww import (
            OpenWakeWordDetector, OWW_WINDOW_SAMPLES,
        )
        det = OpenWakeWordDetector(on_wake=_noop_callback)
        if not det.load():
            self.skipTest(f"oww load failed: {det.last_error}")
        # Track how many times the model was actually asked to
        # predict.
        calls = []
        orig_predict = det._model.predict

        def counting_predict(window):
            calls.append(window.shape[0] if hasattr(window, "shape") else len(window))
            return orig_predict(window)

        det._model.predict = counting_predict
        # Feed 3 chunks of 512 = 1536 samples. That's enough for
        # exactly one full window (1280) with 256 left over.
        for _ in range(3):
            det.feed(np.zeros(512, dtype=np.int16))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], OWW_WINDOW_SAMPLES)
        # Buffer should now hold the leftover 256 samples.
        self.assertEqual(det._buf.size, 1536 - OWW_WINDOW_SAMPLES)


class CallbackSignatureTest(unittest.TestCase):
    """The orchestrator's callback signature must match the
    pre-R2 Vosk signature (phrase, ts, tail_s, confidence) so the
    controller and recorder don't break."""

    def test_wake_callback_signature_preserved(self) -> None:
        from gemma4_agent.voice.wake import WakeCallback
        # WakeCallback is a Callable type alias; we inspect it
        # via the in-tree consumer (VoiceController._on_wake_detected
        # is the production signature). Here we just check the
        # type alias documents 4 args.
        from gemma4_agent.voice import wake_vosk
        sig = inspect.getsource(wake_vosk)
        # The signature comment near the top must still list the
        # 4 expected args.
        self.assertIn("matched_phrase", sig)
        self.assertIn("tail_s", sig)
        self.assertIn("confidence", sig)


class ReexportTest(unittest.TestCase):
    """Existing imports from gemma4_agent.voice.wake must keep
    resolving after the R2 split."""

    def test_match_wake_phrase_still_importable_from_wake(self) -> None:
        from gemma4_agent.voice.wake import match_wake_phrase
        self.assertEqual(match_wake_phrase("hey gemma"), "hey gemma")

    def test_vosk_constants_still_importable_from_wake(self) -> None:
        from gemma4_agent.voice.wake import (
            VOSK_MODEL_DIR, VOSK_MODEL_NAME, VOSK_MODEL_URL,
            WAKE_DEBOUNCE_S, WAKE_MIN_CONFIDENCE,
        )
        self.assertTrue(str(VOSK_MODEL_DIR))
        self.assertIn("vosk-model", VOSK_MODEL_NAME)
        self.assertTrue(VOSK_MODEL_URL.endswith(".zip"))
        self.assertGreater(WAKE_DEBOUNCE_S, 0.0)
        self.assertGreaterEqual(WAKE_MIN_CONFIDENCE, 0.5)


if __name__ == "__main__":
    unittest.main()
