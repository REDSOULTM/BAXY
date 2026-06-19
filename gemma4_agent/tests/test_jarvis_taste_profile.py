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
    build_profile, build_profile_block, inspect_text, forget)


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

    def test_forget_borra_todo_el_comportamiento(self):
        # PRIVACIDAD (fix auditoría 2026-06-07): "olvidate de todo" debe borrar TODO
        # el comportamiento observado del usuario — incluido app_open/app_close/boot.
        # Antes solo borraba app_focus/media_play y el pattern_miner SEGUÍA minando
        # rutinas del user tras un olvido confirmado (viola privacidad + honestidad).
        self.log.record("boot", "agent")
        self.log.record("app_open", "spotify.exe", context={"source": "agent"})
        self.log.record("app_close", "chrome.exe", context={"source": "agent"})
        for _ in range(10):
            _seed(self.log, "app_focus", "code.exe", "mañana", dwell_s=400)
        n = forget(self.log)
        self.assertGreater(n, 0)
        remaining = self.log.events()
        self.assertEqual(len(remaining), 0,
                         f"forget debe borrar TODO el comportamiento, quedaron: {remaining}")


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

    def test_capability_identity_chat_not_detected(self):
        """BUG real (cacería tanda 2/3, cluster A5 ~22): el short-circuit de perfil
        sobre-disparaba ante preguntas de CAPACIDAD/IDENTIDAD/PANTALLA/CHARLA y ante
        intención de GUARDAR un dato — todas mencionan 'me/yo/mí' pero NO piden ver el
        perfil de gustos. Deben seguir el turno normal (el LLM responde)."""
        if not self.ready:
            self.skipTest("encoder no disponible")
        for q in ("what does my screen show", "quién soy yo", "quién soy",
                  "me estás escuchando siempre?", "me estás viendo?",
                  "sé honesto conmigo", "qué significa hecho para ti?",
                  "tenés algún meme?", "quiero que me recuerdes como red",
                  "qué tengo en mi pc ahora mismo?", "qué puedo pedirte",
                  "qué no podés hacer", "tenés sentimientos?",
                  # identidad del asistente / capacidad / system query (t4)
                  "quién eres", "háblame de ti", "presentate ante mí",
                  "qué puedes hacer por mí", "cuánta vram tengo", "qué juegos tengo",
                  "who created you",
                  # charla emocional/filosófica multilingüe (t5) — incl. malestar
                  "Você acha que sou uma boa pessoa?", "Acho que vou desistir de tudo",
                  "Denkst du manchmal über mich nach?", "Je suis fier de moi",
                  "estoy muy triste hoy"):
            self.assertIsNone(self.detect(q), f"falso positivo (A5) en {q!r}")

    def test_genuine_memory_questions_still_detected(self):
        """No sobre-corregir: las preguntas REALES de inspección de memoria deben
        seguir disparando inspect."""
        if not self.ready:
            self.skipTest("encoder no disponible")
        for q in ("qué datos míos guardas?", "qué recuerdas sobre mis preferencias?",
                  "mostrame mi perfil"):
            self.assertEqual(self.detect(q), "inspect", f"esperaba inspect en {q!r}")


if __name__ == "__main__":
    unittest.main()
