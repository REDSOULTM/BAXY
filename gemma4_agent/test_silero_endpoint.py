"""P.2: transcribe_stream uses Silero VAD for chunk-level
endpoint detection. Falls back to RMS when Silero unavailable."""
from __future__ import annotations

import os
import subprocess
import sys
import unittest

import numpy as np


class SileroPredictChunkTest(unittest.TestCase):
    def test_predict_chunk_returns_float_in_unit_range(self) -> None:
        from gemma4_agent.voice.stt import _SileroVAD
        vad = _SileroVAD()
        # Without loading: returns 0.0.
        chunk = np.zeros(512, dtype=np.int16)
        prob = vad.predict_chunk(chunk)
        self.assertIsInstance(prob, float)
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)

    def test_predict_chunk_handles_failure_gracefully(self) -> None:
        from gemma4_agent.voice.stt import _SileroVAD
        vad = _SileroVAD()
        # Pass an invalid chunk size; should not raise.
        bad_chunk = np.zeros(100, dtype=np.int16)
        prob = vad.predict_chunk(bad_chunk)
        self.assertIsInstance(prob, float)
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)

    def test_predict_chunk_unloaded_returns_zero(self) -> None:
        from gemma4_agent.voice.stt import _SileroVAD
        vad = _SileroVAD()
        # Not loaded -> hard 0.0 contract.
        prob = vad.predict_chunk(np.zeros(512, dtype=np.int16))
        self.assertEqual(prob, 0.0)


class VadSilenceEnvOverrideTest(unittest.TestCase):
    """The env override path is read once at module-load time.
    Reloading stt.py in-process touches a lot of global state (BoH
    list, model caches, etc.) and risks cross-test contamination.
    Run the assertion in a clean subprocess instead."""

    def test_vad_silence_ms_default_is_500(self) -> None:
        from gemma4_agent.voice.stt import VAD_SILENCE_MS
        # Default in the test process (no env var set).
        self.assertEqual(VAD_SILENCE_MS, 500)

    def test_vad_silence_ms_env_override_in_subprocess(self) -> None:
        env = os.environ.copy()
        env["GEMMA4_VOICE_SILENCE_MS"] = "800"
        # Strip pytest plugins that grab stderr — bare python is enough.
        proc = subprocess.run(
            [sys.executable, "-c",
             "from gemma4_agent.voice.stt import VAD_SILENCE_MS;"
             "print(VAD_SILENCE_MS)"],
            env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0,
                         f"subprocess failed: {proc.stderr}")
        self.assertEqual(proc.stdout.strip(), "800",
                         f"override not picked up: stdout={proc.stdout!r}")


if __name__ == "__main__":
    unittest.main()
