"""Tests del audio ducking (baja el volumen mientras Gemma escucha).

Comportamiento tipo Alexa: LISTENING -> baja el volumen; al dejar de hablar ->
restaura el valor EXACTO. Robusto: restaura siempre ante fallo (no deja el PC
mudo), idempotente, no-op sin endpoint de audio.
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.voice.ducking import AudioDucker


class _FakeEndpoint:
    """Simula IAudioEndpointVolume con un escalar en memoria."""
    def __init__(self, scalar=0.80, explode_on_set=False):
        self._s = scalar
        self._explode = explode_on_set
        self.set_calls = []

    def GetMasterVolumeLevelScalar(self):
        return self._s

    def SetMasterVolumeLevelScalar(self, v, _ctx):
        self.set_calls.append(v)
        if self._explode:
            raise RuntimeError("boom")
        self._s = v


def _ducker_with(ep):
    d = AudioDucker()
    d._endpoint = lambda: ep  # type: ignore[method-assign]
    return d


class DuckRestoreTest(unittest.TestCase):
    def setUp(self):
        os.environ["GEMMA4_VOICE_DUCKING"] = "1"
        os.environ["GEMMA4_VOICE_DUCK_LEVEL"] = "0.20"

    def test_duck_lowers_and_restore_returns_exact(self):
        ep = _FakeEndpoint(scalar=0.80)
        d = _ducker_with(ep)
        d.duck()
        self.assertAlmostEqual(ep._s, 0.20, places=3)
        d.restore()
        self.assertAlmostEqual(ep._s, 0.80, places=3)  # valor EXACTO previo

    def test_duck_is_idempotent(self):
        ep = _FakeEndpoint(scalar=0.80)
        d = _ducker_with(ep)
        d.duck()
        d.duck()  # segundo duck no re-guarda 0.20 como "previo"
        d.restore()
        self.assertAlmostEqual(ep._s, 0.80, places=3)

    def test_does_not_raise_volume_if_already_low(self):
        # si ya estás por debajo del target, NO subimos el volumen
        ep = _FakeEndpoint(scalar=0.10)
        d = _ducker_with(ep)
        d.duck()
        self.assertAlmostEqual(ep._s, 0.10, places=3)  # sin cambio
        d.restore()
        self.assertAlmostEqual(ep._s, 0.10, places=3)

    def test_restore_without_duck_is_noop(self):
        ep = _FakeEndpoint(scalar=0.55)
        d = _ducker_with(ep)
        d.restore()  # nunca duckeó
        self.assertAlmostEqual(ep._s, 0.55, places=3)

    def test_restore_always_runs_even_if_set_explodes_midway(self):
        # si el SetVolume del duck explota, no debe quedar en estado raro
        ep = _FakeEndpoint(scalar=0.80, explode_on_set=True)
        d = _ducker_with(ep)
        d.duck()  # explota dentro -> intenta restaurar, no lanza
        # tras un duck fallido, restore no debe lanzar y deja estado limpio
        d.restore()
        self.assertFalse(d._ducked)

    def test_gate_off_is_noop(self):
        os.environ["GEMMA4_VOICE_DUCKING"] = "0"
        try:
            ep = _FakeEndpoint(scalar=0.80)
            d = _ducker_with(ep)
            d.duck()
            self.assertAlmostEqual(ep._s, 0.80, places=3)  # no tocó nada
        finally:
            os.environ["GEMMA4_VOICE_DUCKING"] = "1"

    def test_no_endpoint_is_noop(self):
        d = AudioDucker()
        d._endpoint = lambda: None  # type: ignore[method-assign]
        d.duck()      # no debe lanzar
        d.restore()   # no debe lanzar
        self.assertFalse(d._ducked)

    def test_custom_level_env(self):
        os.environ["GEMMA4_VOICE_DUCK_LEVEL"] = "0.35"
        try:
            ep = _FakeEndpoint(scalar=0.90)
            d = _ducker_with(ep)
            d.duck()
            self.assertAlmostEqual(ep._s, 0.35, places=3)
        finally:
            os.environ["GEMMA4_VOICE_DUCK_LEVEL"] = "0.20"


class HandleStateWiringTest(unittest.TestCase):
    """voice_runner._handle_state debe duckear en LISTENING y restaurar al fin."""

    def _runner(self):
        from gemma4_agent.voice_runner import VoiceRunner
        r = VoiceRunner.__new__(VoiceRunner)
        calls = []

        class _D:
            def duck(self): calls.append("duck")
            def restore(self): calls.append("restore")
        r._ducker = _D()
        r._on_state = None
        return r, calls

    def test_listening_ducks(self):
        r, calls = self._runner()
        r._handle_state("LISTENING")
        self.assertIn("duck", calls)

    def test_terminal_states_restore(self):
        for st in ("TRANSCRIBING", "NO_SPEECH", "IDLE_LISTENING", "COOLDOWN", "IDLE"):
            r, calls = self._runner()
            r._handle_state(st)
            self.assertIn("restore", calls, st)


if __name__ == "__main__":
    unittest.main()
