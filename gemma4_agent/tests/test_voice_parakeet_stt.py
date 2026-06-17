"""Tests del motor Parakeet-STT y las mejoras del corrector (noche 2026-05-23).

Protege contra regresión:
  - ParakeetSTT: interfaz drop-in de stt.STT (load/transcribe), graceful si
    faltan deps/modelo.
  - Spanish Metaphone: codificación ES acerca anglicismos fonetizados.
  - Gate de longitud: enunciados largos (habla declarativa) NO se corrigen.
  - Number-words protegidas en la stop-list.

NO requiere GPU. El test de transcripción real corre solo si el modelo está
descargado (skip si no).
"""
from __future__ import annotations

import unittest
from pathlib import Path

from gemma4_agent.voice.corrector import FuzzyCorrector, MAX_COMMAND_TOKENS
from gemma4_agent.voice.phonetic_es import spanish_metaphone


class SpanishMetaphoneTest(unittest.TestCase):
    def test_basic_codes(self):
        # No vacío para palabras reales
        self.assertTrue(spanish_metaphone("chrome"))
        self.assertTrue(spanish_metaphone("netflix"))
        # vacío para entrada trivial
        self.assertEqual(spanish_metaphone(""), "")
        self.assertEqual(spanish_metaphone("123"), "")

    def test_seseo_and_digraphs(self):
        # C ante e/i -> S (seseo); CH -> X; LL -> Y; QU -> K
        self.assertEqual(spanish_metaphone("casa"), spanish_metaphone("kasa"))
        self.assertTrue(spanish_metaphone("queso").startswith("K"))

    def test_acercamiento_anglicismos(self):
        # blc->vlc y netflis->netflix deben quedar fonéticamente CERCA en ES
        from rapidfuzz import fuzz
        self.assertGreaterEqual(
            fuzz.ratio(spanish_metaphone("blc"), spanish_metaphone("vlc")), 80)
        self.assertGreaterEqual(
            fuzz.ratio(spanish_metaphone("netflis"), spanish_metaphone("netflix")), 90)


class CorrectorLengthGateTest(unittest.TestCase):
    def setUp(self):
        self.corr = FuzzyCorrector({
            "verbs": ["abre"], "apps": ["Chrome", "Counter-Strike 2", "OBS"],
            "music_artists": [], "music_songs": [], "wake_words": [],
        })

    def test_short_command_is_corrected(self):
        # Comando corto en posición de argumento -> se corrige
        out = self.corr.correct("abre crome")
        self.assertIn("chrome", out.lower())

    def test_long_declarative_untouched(self):
        # Enunciado largo (>MAX_COMMAND_TOKENS) = habla declarativa -> intacto.
        # Sin el gate, "dos"/"obs" o palabras sueltas se corromperían.
        long_text = ("esto parece tener sentido ya que en la tierra no se "
                     "percibe su movimiento porque somos parte de ella")
        self.assertGreater(len(long_text.split()), MAX_COMMAND_TOKENS)
        self.assertEqual(self.corr.correct(long_text), long_text)

    def test_number_words_protected(self):
        # 'treinta' no debe volverse un nombre propio (Counter-Strike/Torrent)
        out = self.corr.correct("treinta y cinco")
        self.assertIn("treinta", out.lower())


class ParakeetSTTInterfaceTest(unittest.TestCase):
    def test_optimal_threads_bounded(self):
        from gemma4_agent.voice.parakeet_stt import _optimal_threads
        n = _optimal_threads()
        self.assertGreaterEqual(n, 1)
        self.assertLessEqual(n, 4)

    def test_graceful_without_model(self):
        from gemma4_agent.voice.parakeet_stt import ParakeetSTT
        stt = ParakeetSTT(model_dir="/nonexistent/path/xyz")
        self.assertFalse(stt.load())
        self.assertIsNotNone(stt.last_error)
        # transcribe sobre no-cargado devuelve "" (no crashea)
        import numpy as np
        self.assertEqual(stt.transcribe(np.zeros(16000, dtype=np.int16)), "")

    def test_real_transcription_if_model_present(self):
        from gemma4_agent.voice.parakeet_stt import ParakeetSTT, DEFAULT_MODEL_DIR
        if not (Path(DEFAULT_MODEL_DIR) / "encoder.int8.onnx").exists():
            self.skipTest("modelo Parakeet no descargado")
        stt = ParakeetSTT()
        self.assertTrue(stt.load())
        # buffer de silencio -> no debe crashear (puede dar "" o algo corto)
        import numpy as np
        out = stt.transcribe(np.zeros(int(0.5 * 16000), dtype=np.int16))
        self.assertIsInstance(out, str)


class EngineSelectionTest(unittest.TestCase):
    """Parakeet es el ÚNICO motor (reescritura Parakeet-only 2026-06-17).
    Whisper se eliminó: no hay selección por env ni fallback."""

    def test_only_engine_is_parakeet(self):
        from gemma4_agent.voice.pipeline import VoicePipeline
        stt = VoicePipeline._build_stt()
        self.assertEqual(type(stt).__name__, "ParakeetSTT")

    def test_prod_model_dir_under_gemma4_home(self):
        from gemma4_agent.voice.parakeet_stt import PROD_MODEL_DIR
        self.assertIn(".gemma4", str(PROD_MODEL_DIR))
        self.assertIn("models", str(PROD_MODEL_DIR))


if __name__ == "__main__":
    unittest.main()
