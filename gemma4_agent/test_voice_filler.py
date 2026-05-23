"""Two-track TTS filler (informe thinking-latencia): confirmación corta mientras
el LLM piensa, para bajar la latencia PERCIBIDA en comandos de voz de acción.

Garantías:
  - Solo dispara en COMANDOS de acción (no preguntas info ni smalltalk).
  - Es additivo: el comando SIEMPRE se despacha (el filler no bloquea).
  - Best-effort: sin TTS o con fallo, no rompe el turno.
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.voice_runner import VoiceRunner


class _FakeTTS:
    def __init__(self):
        self.spoke = []
    def is_loaded(self):
        return True
    def feed_text(self, t):
        self.spoke.append(t); return 1
    def flush(self):
        return 1


class FillerPickTest(unittest.TestCase):
    def test_action_commands_get_filler(self):
        for cmd in ("abre Steam", "pon música en Spotify",
                    "mandale un mensaje a Juan", "sube el volumen"):
            self.assertIsNotNone(VoiceRunner._pick_filler(cmd), cmd)

    def test_questions_no_filler(self):
        for q in ("¿qué hora es?", "quién es Messi", "qué día es hoy"):
            self.assertIsNone(VoiceRunner._pick_filler(q), q)

    def test_smalltalk_short_no_filler(self):
        for s in ("hola", "pausa", "gracias"):
            self.assertIsNone(VoiceRunner._pick_filler(s), s)


class FillerDispatchTest(unittest.TestCase):
    def setUp(self):
        self.vr = VoiceRunner.__new__(VoiceRunner)
        self.got = []
        self.vr._on_command = self.got.append
        os.environ.pop("GEMMA4_VOICE_FILLER", None)

    def test_command_dispatched_after_filler(self):
        self.vr._tts = _FakeTTS()
        self.vr._handle_command("abre Steam", 1.0, "abre Steam")
        self.assertEqual(self.got, ["abre Steam"])
        self.assertTrue(self.vr._tts.spoke)  # habló el filler

    def test_no_tts_does_not_break_dispatch(self):
        self.vr._tts = None
        self.vr._handle_command("pon música", 1.0, "pon música")
        self.assertEqual(self.got, ["pon música"])

    def test_question_dispatched_without_filler(self):
        self.vr._tts = _FakeTTS()
        self.vr._handle_command("¿qué hora es?", 1.0, "¿qué hora es?")
        self.assertEqual(self.got, ["¿qué hora es?"])
        self.assertFalse(self.vr._tts.spoke)  # NO habló filler

    def test_flag_off_disables_filler(self):
        os.environ["GEMMA4_VOICE_FILLER"] = "0"
        try:
            self.vr._tts = _FakeTTS()
            self.vr._handle_command("abre Steam", 1.0, "abre Steam")
            self.assertEqual(self.got, ["abre Steam"])
            self.assertFalse(self.vr._tts.spoke)
        finally:
            os.environ.pop("GEMMA4_VOICE_FILLER", None)


if __name__ == "__main__":
    unittest.main()
