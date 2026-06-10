"""Deshabilitar Whisper: SOLO Parakeet.

GEMMA4_STT_NO_FALLBACK (o GEMMA4_DISABLE_WHISPER) apaga el fallback a Whisper en
VoicePipeline: si Parakeet no carga, la voz falla limpio en vez de caer a Whisper.
Este test fija el detector del flag (no carga modelos reales).
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.voice.pipeline import VoicePipeline


class TestWhisperDisabledFlag(unittest.TestCase):
    def setUp(self):
        self._saved = {
            k: os.environ.get(k)
            for k in ("GEMMA4_STT_NO_FALLBACK", "GEMMA4_DISABLE_WHISPER")
        }
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_default_allows_whisper_fallback(self):
        # sin el flag, el fallback a Whisper sigue disponible (comportamiento previo).
        self.assertFalse(VoicePipeline._whisper_disabled())

    def test_flag_disables_whisper(self):
        for val in ("1", "true", "on", "yes"):
            os.environ["GEMMA4_STT_NO_FALLBACK"] = val
            self.assertTrue(VoicePipeline._whisper_disabled(), f"flag={val!r}")
            os.environ.pop("GEMMA4_STT_NO_FALLBACK", None)

    def test_alias_disable_whisper(self):
        os.environ["GEMMA4_DISABLE_WHISPER"] = "1"
        self.assertTrue(VoicePipeline._whisper_disabled())

    def test_falsey_values_keep_fallback(self):
        for val in ("0", "false", "off", ""):
            os.environ["GEMMA4_STT_NO_FALLBACK"] = val
            self.assertFalse(VoicePipeline._whisper_disabled(), f"flag={val!r}")


if __name__ == "__main__":
    unittest.main()
