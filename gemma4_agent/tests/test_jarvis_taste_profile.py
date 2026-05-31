"""Tests de la capa viva (R-Jarvis 2026-05-30): observador ambiente, perfil de
gustos (reflexión determinista) y detección de intención de privacidad.

NO ejercita input sintético GUI (seguro). Usa una BehaviorLog temporal.
"""
import tempfile
import time
import unittest
from pathlib import Path

from ..memory_pkg.behavior_log import BehaviorLog
from ..memory_pkg.taste_profile import (
    build_profile, profile_text, build_profile_block, inspect_text, forget)


def _seed(log, kind, key, slot, **ctx):
    log.record(kind, key, context={"source": "ambient", "slot": slot, **ctx})
    time.sleep(0.001)  # ts únicos (PK incluye ts)


class TestTasteProfile(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = BehaviorLog(dir_path=self.tmp)

    def test_empty_profile_when_no_data(self):
        self.assertTrue(build_profile(self.log).is_empty())
        self.assertEqual(build_profile_block(self.log), "")

    def test_learns_apps_and_music(self):
        for _ in range(20):
            _seed(self.log, "app_focus", "code.exe", "mañana", dwell_s=400)
        for _ in range(10):
            _seed(self.log, "app_focus", "spotify.exe", "noche", dwell_s=300)
        for s in ("Soda Stereo — A", "Soda Stereo — B", "Soda Stereo — C"):
            _seed(self.log, "media_play", s, "noche")
        prof = build_profile(self.log)
        apps = {a for a, _ in prof.top_apps}
        self.assertIn("code.exe", apps)
        self.assertIn("spotify.exe", apps)
        artists = {a for a, _ in prof.top_artists}
        self.assertIn("soda stereo", artists)
        block = build_profile_block(self.log)
        self.assertIn("Code", block)
        self.assertIn("Soda Stereo", block)  # capitalizado
        self.assertIn("NO lo menciones", block)  # anti-parroting

    def test_min_thresholds_block_noise(self):
        # 1 sola observación de cada cosa NO debe inventar un perfil.
        _seed(self.log, "app_focus", "rare.exe", "tarde", dwell_s=30)
        _seed(self.log, "media_play", "Unknown — X", "tarde")
        self.assertTrue(build_profile(self.log).is_empty())

    def test_ignores_non_ambient_events(self):
        # eventos del AGENTE (sin source=ambient) no cuentan para el perfil.
        for _ in range(20):
            self.log.record("app_open", "agentapp.exe", context={"foo": "bar"})
            time.sleep(0.001)
        self.assertTrue(build_profile(self.log).is_empty())

    def test_forget_clears_and_inspect_reports(self):
        for _ in range(20):
            _seed(self.log, "app_focus", "code.exe", "mañana", dwell_s=400)
        self.assertFalse(build_profile(self.log).is_empty())
        self.assertIn("aprendí", inspect_text(self.log))
        n = forget(self.log)
        self.assertGreater(n, 0)
        self.assertTrue(build_profile(self.log).is_empty())
        self.assertIn("Todavía no", inspect_text(self.log))

    def test_forget_does_not_touch_agent_events(self):
        # forget borra app_focus/media_play (ambient), NO boot/app_open del agente.
        self.log.record("boot", "agent")
        for _ in range(10):
            _seed(self.log, "app_focus", "code.exe", "mañana", dwell_s=400)
        forget(self.log)
        boots = [e for e in self.log.events() if e["kind"] == "boot"]
        self.assertEqual(len(boots), 1, "forget no debe borrar el boot del agente")


class TestProfileIntent(unittest.TestCase):
    """Detección por embeddings de inspect/forget. Requiere encoder; si no carga,
    el detector devuelve None (fallback seguro) y estos tests se auto-skipean."""

    @classmethod
    def setUpClass(cls):
        from ..memory_pkg.profile_intent import detect_profile_intent, _ensure_centroids
        cls.detect = staticmethod(detect_profile_intent)
        cls.ready = _ensure_centroids()

    def test_inspect_detected(self):
        if not self.ready:
            self.skipTest("encoder no disponible")
        for q in ("qué sabés de mí?", "qué aprendiste de mí", "what do you know about me"):
            self.assertEqual(self.detect(q), "inspect", f"esperaba inspect en {q!r}")

    def test_forget_detected(self):
        if not self.ready:
            self.skipTest("encoder no disponible")
        for q in ("olvidate de lo que sabés de mí", "borrá mis datos de comportamiento"):
            self.assertEqual(self.detect(q), "forget", f"esperaba forget en {q!r}")

    def test_normal_use_not_detected(self):
        if not self.ready:
            self.skipTest("encoder no disponible")
        # incluyendo los hard-negatives medidos (borrar ARCHIVOS != borrar perfil;
        # TIPEAR "mi nombre"/mis datos en una app != preguntar por el perfil).
        for q in ("qué sabés de python", "qué hora es", "abrí spotify",
                  "borrá estos archivos", "recomendame música", "hola",
                  "en notepad poné mi nombre", "poné mi nombre en el word",
                  "escribí mi nombre en el bloc de notas", "write my name in notepad"):
            self.assertIsNone(self.detect(q), f"falso positivo en {q!r}")


if __name__ == "__main__":
    unittest.main()
