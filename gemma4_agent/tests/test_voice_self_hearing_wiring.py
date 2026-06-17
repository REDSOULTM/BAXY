"""Integración del anti-self-hearing + ducking, ejerciendo los CUERPOS REALES
de VoicePipeline._handle_idle / ._on_wake y VoiceRunner._handle_state — sin HW
de audio (vía __new__ + fakes mínimos, no carga VAD/wake/STT/Piper).

Cubre el flujo que el usuario reportó como "desconectado":
  - Mientras Gemma habla (tts_busy), el wake se alimenta con predict=False: el
    ring de 2 s se mantiene CALIENTE pero NO dispara (anti-eco sin hueco muerto,
    fix 2026-06-17 del bug "tras decir Baxy varias veces deja de funcionar").
  - Al despertar (wake -> LISTENING) el volumen se duckea; el wake vuelve a
    PREDECIR cuando el TTS termina.
"""
from __future__ import annotations

import unittest
from collections import deque
from threading import Lock

import numpy as np


class _FakeWake:
    def __init__(self) -> None:
        self.feeds = 0          # feeds totales (ring caliente)
        self.predict_feeds = 0  # feeds que PUEDEN disparar (predict=True)

    def feed(self, chunk, predict=True) -> None:  # noqa: ANN001
        self.feeds += 1
        if predict:
            self.predict_feeds += 1


def _idle_pipe(busy: bool):
    """VoicePipeline real (cuerpo de _handle_idle) con campos mínimos."""
    from gemma4_agent.voice.pipeline import State, VoicePipeline
    p = VoicePipeline.__new__(VoicePipeline)
    p._preroll = deque(maxlen=10)
    p._wake = _FakeWake()
    p._tts_busy_fn = (lambda: busy)
    p._wake_paused_for_tts = False
    p._state_lock = Lock()
    p._state = State.IDLE
    return p


class EchoGatePausesWake(unittest.TestCase):
    def test_wake_fed_when_tts_idle(self):
        p = _idle_pipe(busy=False)
        p._handle_idle(np.zeros(160, dtype=np.int16))
        self.assertEqual(p._wake.predict_feeds, 1, "con TTS en silencio el wake DEBE predecir")

    def test_wake_warm_but_no_predict_while_gemma_speaks(self):
        # NUEVO comportamiento: durante el TTS el ring se mantiene CALIENTE
        # (feed) pero SIN predecir/disparar (anti-eco sin hueco muerto).
        p = _idle_pipe(busy=True)
        for _ in range(5):
            p._handle_idle(np.zeros(160, dtype=np.int16))
        self.assertEqual(p._wake.feeds, 5, "el ring DEBE mantenerse caliente durante el TTS")
        self.assertEqual(p._wake.predict_feeds, 0,
                         "el wake NO debe DISPARAR mientras Gemma habla")
        self.assertTrue(p._wake_paused_for_tts)

    def test_wake_resumes_predicting_after_tts(self):
        # Empieza ocupado (caliente, sin predecir), luego se libera -> predice.
        from gemma4_agent.voice.pipeline import State, VoicePipeline
        p = VoicePipeline.__new__(VoicePipeline)
        p._preroll = deque(maxlen=10)
        p._wake = _FakeWake()
        p._state_lock = Lock()
        p._state = State.IDLE
        p._wake_paused_for_tts = False
        busy = {"v": True}
        p._tts_busy_fn = (lambda: busy["v"])
        p._handle_idle(np.zeros(160, dtype=np.int16))  # ocupado -> caliente sin predecir
        self.assertEqual(p._wake.feeds, 1)
        self.assertEqual(p._wake.predict_feeds, 0)
        busy["v"] = False
        p._handle_idle(np.zeros(160, dtype=np.int16))  # libre -> vuelve a predecir
        self.assertEqual(p._wake.predict_feeds, 1)
        self.assertFalse(p._wake_paused_for_tts)


class WakeDucksOnListening(unittest.TestCase):
    def test_on_wake_emits_listening_and_ducks(self):
        from gemma4_agent.infra.voice_runner import VoiceRunner
        from gemma4_agent.voice.pipeline import State, VoicePipeline

        runner = VoiceRunner.__new__(VoiceRunner)
        events = []

        class _D:
            def duck(self): events.append("duck")
            def restore(self): events.append("restore")
        runner._ducker = _D()
        runner._on_state = None

        p = VoicePipeline.__new__(VoicePipeline)
        p._state_lock = Lock()
        p._state = State.IDLE
        p._on_state = runner._handle_state  # pipeline -> runner (ducking real)
        p._on_wake_event = None
        p._preroll = deque(maxlen=10)

        p._on_wake("hey gemma", 0.9)

        self.assertEqual(p._state, State.CAPTURE)
        self.assertIn("duck", events, "despertar DEBE bajar el volumen (LISTENING)")

    def test_terminal_state_restores_volume(self):
        from gemma4_agent.infra.voice_runner import VoiceRunner
        runner = VoiceRunner.__new__(VoiceRunner)
        events = []

        class _D:
            def duck(self): events.append("duck")
            def restore(self): events.append("restore")
        runner._ducker = _D()
        runner._on_state = None
        runner._handle_state("TRANSCRIBING")
        self.assertIn("restore", events, "al terminar de hablar DEBE restaurar el volumen")


if __name__ == "__main__":
    unittest.main()
