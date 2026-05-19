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


class CustomModelLoadingTest(unittest.TestCase):
    """Sprint R3: OpenWakeWordDetector auto-detects a custom
    'hey_gemma.onnx' under voice/models/oww/. If present, use it;
    if not, fall back to the upstream 'hey_jarvis' surrogate."""

    def setUp(self) -> None:
        self._saved_env = os.environ.pop("GEMMA4_OWW_MODEL", None)

    def tearDown(self) -> None:
        if self._saved_env is not None:
            os.environ["GEMMA4_OWW_MODEL"] = self._saved_env
        else:
            os.environ.pop("GEMMA4_OWW_MODEL", None)

    def test_custom_model_loaded_when_exists(self) -> None:
        """When OWW_CUSTOM_MODEL_PATH exists, the loader passes
        the absolute path to openwakeword and uses the file's stem
        as the score-dict key."""
        from gemma4_agent.voice import wake_oww
        # _resolve_model_spec() returns (arg_to_wakeword_models,
        # score_dict_key). Test the resolver directly to avoid
        # network/model download.
        det = wake_oww.OpenWakeWordDetector(on_wake=_noop_callback)
        with patch.object(
            type(wake_oww.OWW_CUSTOM_MODEL_PATH), "exists",
            lambda self: True,
        ):
            arg, key = det._resolve_model_spec()
        # arg should be an absolute path string containing the
        # repo-relative location.
        self.assertIn("hey_gemma.onnx", arg)
        self.assertEqual(key, "hey_gemma")

    def test_fallback_to_jarvis_when_custom_missing(self) -> None:
        """When the custom .onnx is absent, fall back to
        OWW_FALLBACK_MODEL_NAME and log a warning that names
        Sprint R3."""
        from gemma4_agent.voice import wake_oww
        det = wake_oww.OpenWakeWordDetector(on_wake=_noop_callback)
        with patch.object(
            type(wake_oww.OWW_CUSTOM_MODEL_PATH), "exists",
            lambda self: False,
        ), self.assertLogs("gemma4_agent.voice.wake_oww",
                           level="WARNING") as log_ctx:
            arg, key = det._resolve_model_spec()
        self.assertEqual(arg, wake_oww.OWW_FALLBACK_MODEL_NAME)
        self.assertEqual(key, wake_oww.OWW_FALLBACK_MODEL_NAME)
        # The fallback warning must mention Sprint R3 so the operator
        # has a breadcrumb to the training pipeline.
        self.assertTrue(
            any("Sprint R3" in record for record in log_ctx.output),
            f"warning did not mention Sprint R3: {log_ctx.output}",
        )

    def test_env_var_overrides_auto_detection(self) -> None:
        """GEMMA4_OWW_MODEL=<name> forces the loader to use the
        given pre-trained model name, even if the custom .onnx
        exists. This is the escape hatch for A/B benchmarking."""
        from gemma4_agent.voice import wake_oww
        # Reload module to pick up the env var (it's read at import time).
        import importlib
        os.environ["GEMMA4_OWW_MODEL"] = "alexa"
        importlib.reload(wake_oww)
        try:
            det = wake_oww.OpenWakeWordDetector(on_wake=_noop_callback)
            # Even with the custom model file present, the env
            # override wins.
            with patch.object(
                type(wake_oww.OWW_CUSTOM_MODEL_PATH), "exists",
                lambda self: True,
            ):
                arg, key = det._resolve_model_spec()
            self.assertEqual(arg, "alexa")
            self.assertEqual(key, "alexa")
        finally:
            os.environ.pop("GEMMA4_OWW_MODEL", None)
            importlib.reload(wake_oww)


if __name__ == "__main__":
    unittest.main()
