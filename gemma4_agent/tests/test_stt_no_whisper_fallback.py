"""Invariante de la reescritura Parakeet-only (2026-06-17): Whisper está
ELIMINADO del pipeline de voz. No hay fallback, ni rescate LID, ni selección de
motor por env. `_build_stt()` devuelve siempre ParakeetSTT y el código del
pipeline no importa ni referencia Whisper/STT.

Este test es un gate de NO-REGRESIÓN: si alguien re-introduce Whisper en el
pipeline de voz, falla acá.
"""
from __future__ import annotations

import inspect
import unittest

from gemma4_agent.voice import pipeline
from gemma4_agent.voice.pipeline import VoicePipeline


class TestParakeetOnly(unittest.TestCase):
    def test_build_stt_returns_parakeet(self):
        stt = VoicePipeline._build_stt()
        self.assertEqual(type(stt).__name__, "ParakeetSTT")

    def test_no_whisper_fallback_api_remains(self):
        # Las APIs del fallback a Whisper fueron eliminadas.
        for attr in ("_whisper_disabled", "_lid_rescue", "_whisper_rescue_stt",
                     "_rescue_via_subprocess"):
            self.assertFalse(hasattr(VoicePipeline, attr),
                             f"{attr} debería estar eliminado")

    def test_pipeline_source_has_no_whisper_import(self):
        src = inspect.getsource(pipeline)
        # No imports/usos de Whisper STT en el pipeline de voz.
        self.assertNotIn("from .stt import", src)
        self.assertNotIn("_SILENCE_HALLUCINATIONS", src)
        # El módulo voice.stt ya no debe existir (Whisper eliminado del repo).
        import importlib.util
        self.assertIsNone(importlib.util.find_spec("gemma4_agent.voice.stt"),
                          "voice/stt.py (Whisper) debería estar eliminado")


if __name__ == "__main__":
    unittest.main()
