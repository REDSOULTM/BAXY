"""Tests del watchdog de VRAM (investigación 6: estabilidad/no-crash).

El peligro real en vram4 es el OOM en RUNTIME: llama-server no recupera de un
OOM CUDA (queda zombie, #13085). El watchdog detecta presión de VRAM ANTES de
despachar y avisa fuerte (fail-loud). Sin GPU NVIDIA debe ser no-op (nunca
romper el turno).
"""
from __future__ import annotations

import unittest

from gemma4_agent import vram_watchdog as vw
from gemma4_agent.vram_watchdog import (
    VRAMWatchdog, VRAMSnapshot, _level_for,
    LEVEL_OK, LEVEL_WARN, LEVEL_DEGRADE, LEVEL_CRITICAL,
)


class LevelThresholdsTest(unittest.TestCase):
    def test_level_for_buckets(self):
        self.assertEqual(_level_for(5000), LEVEL_OK)
        self.assertEqual(_level_for(1000), LEVEL_WARN)      # < 1200
        self.assertEqual(_level_for(600), LEVEL_DEGRADE)    # < 800
        self.assertEqual(_level_for(300), LEVEL_CRITICAL)   # < 400

    def test_boundaries_inclusive_floor(self):
        # exactamente en el umbral NO baja de nivel (usa <)
        self.assertEqual(_level_for(1200), LEVEL_OK)
        self.assertEqual(_level_for(800), LEVEL_WARN)
        self.assertEqual(_level_for(400), LEVEL_DEGRADE)


class WatchdogNoGpuTest(unittest.TestCase):
    """Sin GPU NVIDIA (nvidia-smi falla) el watchdog es no-op total."""

    def setUp(self):
        self._orig = vw._query_nvidia_smi
        vw._query_nvidia_smi = lambda: None

    def tearDown(self):
        vw._query_nvidia_smi = self._orig

    def test_noop_when_no_gpu(self):
        wd = VRAMWatchdog()
        snap = wd.snapshot(force=True)
        self.assertFalse(snap.available)
        self.assertEqual(snap.level, LEVEL_OK)

    def test_vision_safe_true_without_evidence(self):
        # sin GPU no bloqueamos visión (no hay evidencia de presión)
        wd = VRAMWatchdog()
        self.assertTrue(wd.vision_safe())
        self.assertFalse(wd.should_degrade())

    def test_gpu_absent_not_requeried(self):
        # tras detectar ausencia, no reintenta nvidia-smi cada vez
        calls = {"n": 0}

        def _counting():
            calls["n"] += 1
            return None
        vw._query_nvidia_smi = _counting
        wd = VRAMWatchdog()
        wd.snapshot(force=True)
        wd.snapshot(force=True)
        wd.snapshot(force=True)
        self.assertEqual(calls["n"], 1)  # solo el primero consulta


class WatchdogWithGpuTest(unittest.TestCase):
    def setUp(self):
        self._orig = vw._query_nvidia_smi

    def tearDown(self):
        vw._query_nvidia_smi = self._orig

    def _fake(self, free, used=0, total=6144):
        vw._query_nvidia_smi = lambda: (free, used, total)

    def test_comfortable_vram_is_ok(self):
        self._fake(free=3000)
        wd = VRAMWatchdog()
        snap = wd.snapshot(force=True)
        self.assertTrue(snap.available)
        self.assertEqual(snap.level, LEVEL_OK)
        self.assertTrue(wd.vision_safe())  # 3000 >= 800+950
        self.assertFalse(wd.should_degrade())

    def test_critical_vram_blocks_vision(self):
        self._fake(free=300)
        wd = VRAMWatchdog()
        self.assertEqual(wd.level(), LEVEL_CRITICAL)
        self.assertFalse(wd.vision_safe())  # 300 < 800+950
        self.assertTrue(wd.should_degrade())

    def test_degrade_band_blocks_vision(self):
        self._fake(free=700)
        wd = VRAMWatchdog()
        self.assertEqual(wd.level(), LEVEL_DEGRADE)
        self.assertTrue(wd.should_degrade())

    def test_ttl_caches_sample(self):
        self._fake(free=3000)
        wd = VRAMWatchdog()
        wd.snapshot(force=True)
        # cambia la VRAM "real" pero dentro del TTL no re-muestrea
        self._fake(free=100)
        self.assertEqual(wd.snapshot().level, LEVEL_OK)  # usa el cacheado
        # force salta el TTL
        self.assertEqual(wd.snapshot(force=True).level, LEVEL_CRITICAL)

    def test_query_swallows_subprocess_failure(self):
        # si subprocess.run revienta, _query_nvidia_smi devuelve None (no
        # propaga) -> el watchdog cae a no-op, nunca rompe el turno.
        import subprocess as _sp
        orig_run = vw.subprocess.run
        vw.subprocess.run = lambda *a, **k: (_ for _ in ()).throw(
            _sp.SubprocessError("boom"))
        try:
            self.assertIsNone(vw._query_nvidia_smi())
            wd = VRAMWatchdog()
            snap = wd.snapshot(force=True)
            self.assertIsInstance(snap, VRAMSnapshot)
            self.assertFalse(snap.available)
            self.assertEqual(snap.level, LEVEL_OK)  # no-op seguro
        finally:
            vw.subprocess.run = orig_run


if __name__ == "__main__":
    unittest.main()
