"""When a capture is dropped (silence below RMS floor, or a non-lexical filler),
the pipeline must emit a NO_SPEECH state so the UI can tell the user "no te
entendí" instead of silently dropping back to idle ("the mic ignored me" — see
memory project_voice_silent_rejects).

NOTA (Parakeet-only 2026-06-17): el drop por "alucinación de silencio" (lista de
artefactos de Whisper) se ELIMINÓ con Whisper. Parakeet no alucina texto en
silencio, así que un texto que antes era artefacto ("¡Suscríbete!") ahora es una
palabra REAL del usuario y debe llegar al LLM. Solo se filtran silencio (gate de
energía) y vocalizaciones no-léxicas ("Mm-mm").

Drives _finish_capture directly with stubbed STT/corrector; no audio hardware."""
from __future__ import annotations

import threading
import unittest

import numpy as np

from gemma4_agent.voice.pipeline import State, VoicePipeline, SAMPLE_RATE


class _StubSTT:
    def __init__(self, text):
        self._text = text

    def transcribe(self, audio, initial_prompt=None, language=None, hotwords=None):
        return self._text


class _StubCorrector:
    def strip_wake_phrase(self, t):
        return t

    def correct(self, t):
        return t


def _make_pipeline(stt_text, capture_audio):
    p = VoicePipeline.__new__(VoicePipeline)
    p._state = State.CAPTURE
    p._state_lock = threading.RLock()
    p._capture_buf = [capture_audio]
    p._stt = _StubSTT(stt_text)
    p._corrector = _StubCorrector()
    p._initial_prompt = ""
    p._hotwords = ""  # _finish_capture pasa hotwords a transcribe (igual que prod)
    from gemma4_agent.voice.lang_profiles import get_profile
    p._lang_profile = get_profile("es")
    p._cooldown_until = 0.0
    p._wake = type("W", (), {"reset": lambda self: None})()
    # Fake VAD: reset no-op + trim_silence pasa el audio intacto (gate-open).
    p._vad = type("V", (), {
        "reset": lambda self: None,
        "trim_silence": lambda self, audio, *a, **k: audio,
    })()
    p.states = []
    p.commands = []
    p._on_state = lambda s: p.states.append(s)
    p._on_command = lambda text, dur, raw: p.commands.append(text)
    return p


def _silence(seconds):
    return np.zeros(int(seconds * SAMPLE_RATE), dtype=np.int16)


def _speech(seconds, amp=3000, freq=200):
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.int16)


class TestNoSpeechFeedback(unittest.TestCase):
    def test_silence_gate_emits_no_speech(self):
        # Pure silence -> below RMS floor -> NO_SPEECH, no command, no transcribe.
        p = _make_pipeline("should not be used", _silence(1.5))
        p._finish_capture(reason="eos_silence")
        self.assertIn("NO_SPEECH", p.states)
        self.assertEqual(p.commands, [])

    def test_former_whisper_artifact_now_emitted(self):
        # Parakeet-only: el ex-artefacto de Whisper ("¡Suscríbete!") ya NO se
        # dropea — Parakeet no alucina en silencio, así que con energía real es
        # una palabra del usuario y debe llegar al LLM (no NO_SPEECH).
        p = _make_pipeline("¡Suscríbete!", _speech(0.8))
        p._finish_capture(reason="eos_silence")
        self.assertEqual(p.commands, ["¡Suscríbete!"])
        self.assertNotIn("NO_SPEECH", p.states)

    def test_filler_only_emits_no_speech(self):
        # Real energy but STT returns a non-lexical vocalization -> drop.
        p = _make_pipeline("Mm-mm.", _speech(0.8))
        p._finish_capture(reason="eos_silence")
        self.assertIn("NO_SPEECH", p.states)
        self.assertEqual(p.commands, [])

    def test_real_command_emits_command_not_no_speech(self):
        p = _make_pipeline("abre Steam", _speech(0.8))
        p._finish_capture(reason="eos_silence")
        self.assertEqual(p.commands, ["abre Steam"])
        self.assertNotIn("NO_SPEECH", p.states)

    def test_command_containing_artifact_word_not_dropped(self):
        # "suscríbete a este canal" contains the artifact word but is a real cmd.
        p = _make_pipeline("suscríbete a este canal", _speech(0.8))
        p._finish_capture(reason="eos_silence")
        self.assertEqual(p.commands, ["suscríbete a este canal"])
        self.assertNotIn("NO_SPEECH", p.states)


if __name__ == "__main__":
    unittest.main()
