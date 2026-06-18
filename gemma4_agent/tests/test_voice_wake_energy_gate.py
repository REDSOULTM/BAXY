"""Gate de energía anti-falso-wake (2026-06-07).

El wake-word recibe TODOS los chunks sin gate (para no perder recall) y su
threshold 0.25 a veces dispara en SILENCIO/ruido (bug medido: Baxy transcribió
'Yeah'/'We've got' sin que el user hablara). Decir "Baxy" SIEMPRE produce energía;
el silencio NUNCA. _on_wake valida que el preroll (que contiene la frase de wake)
tenga energía sobre el piso calibrado; si no, RECHAZA el wake (sigue en IDLE).
Este test fija: silencio -> rechazado (sigue IDLE); voz -> aceptado (-> CAPTURE).
"""
from __future__ import annotations

import threading
import unittest
from collections import deque

import numpy as np

from gemma4_agent.voice.pipeline import State, VoicePipeline, SAMPLE_RATE


def _silence(seconds):
    return np.zeros(int(seconds * SAMPLE_RATE), dtype=np.int16)


def _speech(seconds, amp=3000, freq=200):
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def _make_pipeline(preroll_audio):
    p = VoicePipeline.__new__(VoicePipeline)
    p._state = State.IDLE
    p._state_lock = threading.RLock()
    # preroll en chunks de 512 (como el ring real)
    chunks = [preroll_audio[i:i + 512] for i in range(0, len(preroll_audio), 512)]
    p._preroll = deque(c for c in chunks if c.size)
    p._capture_buf = []
    p._capture_start_ts = 0.0
    p._eos_silence_count = 0
    p._wake = type("W", (), {"reset": lambda self: None})()
    p._manual_rms_override = True   # usa el gate fijo MIN_CAPTURE_RMS (350)
    p._noise_cal = None
    p._on_wake_event = None
    p.states = []
    p._on_state = lambda s: p.states.append(s)
    return p


class WakeEnergyGateTest(unittest.TestCase):
    def test_silent_preroll_rejects_wake(self):
        # preroll SILENCIO -> falso positivo del wake -> NO debe pasar a CAPTURE.
        p = _make_pipeline(_silence(0.6))
        p._on_wake("baxy", 0.30)
        self.assertEqual(p._state, State.IDLE)   # rechazado, sigue escuchando

    def test_voiced_preroll_accepts_wake(self):
        # preroll con energía de voz -> wake real -> transiciona a CAPTURE.
        p = _make_pipeline(_speech(0.6, amp=3000))
        p._on_wake("baxy", 0.30)
        self.assertEqual(p._state, State.CAPTURE)

    def test_calibration_raises_gate_for_noisy_mic(self):
        # En un mic RUIDOSO la calibración SUBE el gate por encima del default:
        # un sonido de ~424 RMS (que pasaría el 350 fijo) es RECHAZADO si el
        # ruido del mic calibró el gate a 600.
        p = _make_pipeline(_speech(0.6, amp=600))   # RMS ≈ 424
        p._manual_rms_override = False
        p._noise_cal = type("C", (), {"threshold": 600.0})()
        p._on_wake("baxy", 0.30)
        self.assertEqual(p._state, State.IDLE)      # 424 < 600 -> rechazado

    def test_calibration_below_default_is_floored(self):
        # 2026-06-18: la calibración NUNCA baja el gate por debajo del piso
        # seguro (MIN_CAPTURE_RMS=350). En cuarto silencioso calibraba a ~20 y
        # dejaba pasar ambiente de bajo nivel (~134 RMS) que Parakeet alucina
        # como "Yeah"/"Thank you". Con el piso, ese ambiente se RECHAZA aunque
        # la calibración lo pusiera en 20. (Mics de muy baja ganancia: usar
        # GEMMA4_VOICE_MIN_CAPTURE_RMS manual, que setea override y evita el piso.)
        p = _make_pipeline(_speech(0.6, amp=190))   # RMS ≈ 134 (como el FP real)
        p._manual_rms_override = False
        p._noise_cal = type("C", (), {"threshold": 20.0})()
        p._on_wake("baxy", 0.30)
        self.assertEqual(p._state, State.IDLE)      # 134 < piso 350 -> rechazado


if __name__ == "__main__":
    unittest.main()
