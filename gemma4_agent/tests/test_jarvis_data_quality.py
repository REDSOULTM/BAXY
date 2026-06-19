"""Regresión de CALIDAD del dato del Jarvis (fixes 2026-06-03).

Diagnóstico medido sobre la DB real (~/.gemma4/behavior/usuario.db, 27.966 filas):
la cadena observar→agregar→inyectar FUNCIONA, pero los datos crudos envenenaban el
perfil que ve Gemma4. Estos tests fijan las causas-raíz arregladas:

  F1 — media_play se grababa por poll (cada ~5s), no por escucha: 267 filas = 1
       canción sonando un rato. build_profile ahora colapsa por SESIÓN.
  F5 — videos/películas (SMTC reporta cualquier reproductor) entraban como "música".
       Ahora solo lo que tiene "artista — título" cuenta como música.
  F4 — _clean_app('whatsapp.root.exe') daba "Whatsapp.root"; y el "ritmo diario"
       degeneraba a "a la tarde y a la noche... suele estar en Code" cuando una sola
       app domina todas las franjas (ruido que daña a modelos chicos).
  F2 — boot se grababa en cada construcción del agente → flood (21.4k filas).
       record_throttled() lo evita por estado de la DB (no lista hardcoded).

NO ejercita input sintético GUI (seguro). BehaviorLog temporal.
"""
import tempfile
import time
import unittest
from pathlib import Path

from ..memory_pkg.behavior_log import BehaviorLog
from ..memory_pkg.taste_profile import (
    build_profile, profile_text, _clean_app)


def _insert(log, kind, key, ts_ms, ctx):
    """Inserta una fila con ts CONTROLADO (para testear gaps de sesión)."""
    import json
    conn = log._open()
    conn.execute(
        "INSERT OR IGNORE INTO behavior_events(ts,user,kind,key,context)"
        " VALUES(?,?,?,?,?)",
        (ts_ms, log.user, kind, key.strip().lower(),
         json.dumps(ctx, ensure_ascii=False)))
    conn.commit()


class TestMediaSessionDedup(unittest.TestCase):
    """F1: contar SESIONES de escucha, no polls."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = BehaviorLog(user="t", dir_path=self.tmp)

    def test_repeated_polls_count_as_one_play(self):
        # 200 polls de la MISMA canción en 200s (lo que hace el observer real).
        base = int(time.time() * 1000)
        for i in range(200):
            _insert(self.log, "media_play", "Canserbero — Maquiavélico",
                    base + i * 1000, {"source": "ambient", "slot": "noche"})
        # +2 canciones DISTINTAS para superar el umbral _MIN_MEDIA_PLAYS=3.
        _insert(self.log, "media_play", "Canserbero — Pensando en Ti",
                base + 400_000, {"source": "ambient", "slot": "noche"})
        _insert(self.log, "media_play", "Canserbero — Es Épico",
                base + 500_000, {"source": "ambient", "slot": "noche"})
        prof = build_profile(self.log)
        plays = dict(prof.top_artists).get("canserbero")
        self.assertIsNotNone(plays, "Canserbero debe estar en top_artists")
        # 3 canciones distintas = 3 sesiones, NO 202 polls. El bug daba ~202.
        self.assertEqual(plays, 3,
                         f"top_artists debe contar SESIONES, no polls (dio {plays})")

    def test_replay_after_gap_counts_again(self):
        # misma canción, pero con un gap > 30min entre tandas = 2 escuchas reales.
        base = int(time.time() * 1000)
        for i in range(5):  # tanda 1 (polls de la misma canción)
            _insert(self.log, "media_play", "Soda — Persiana", base + i * 1000,
                    {"source": "ambient", "slot": "tarde"})
        gap = base + 5 * 1000 + 3600 * 1000  # +1h después
        for i in range(5):  # tanda 2 (re-play tras gap largo)
            _insert(self.log, "media_play", "Soda — Persiana", gap + i * 1000,
                    {"source": "ambient", "slot": "noche"})
        # +1 canción distinta del mismo artista para superar _MIN_MEDIA_PLAYS=3.
        _insert(self.log, "media_play", "Soda — Profugos", gap + 10_000,
                {"source": "ambient", "slot": "noche"})
        prof = build_profile(self.log)
        plays = dict(prof.top_artists).get("soda")
        # 3 sesiones: tanda1 + re-play tanda2 + canción distinta (NO 11 polls, NO 2).
        self.assertEqual(plays, 3,
                         f"re-play tras gap largo = nueva sesión (dio {plays})")


class TestVideoNotMusic(unittest.TestCase):
    """F5: una película en un reproductor NO es 'música'."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = BehaviorLog(user="t", dir_path=self.tmp)

    def test_video_excluded_from_music_signals(self):
        base = int(time.time() * 1000)
        # 824 polls de una peli (sin "artista — título"): NO debe contar como música.
        for i in range(50):
            _insert(self.log, "media_play",
                    "the.green.inferno.2015.1080p-dual-lat.mp4",
                    base + i * 1000, {"source": "ambient", "slot": "madrugada"})
        prof = build_profile(self.log)
        self.assertEqual(prof.top_artists, [], "una peli no es un artista")
        self.assertEqual(prof.music_slots, [],
                         "no debe afirmar 'escucha música a la madrugada' por una peli")
        self.assertEqual(prof.total_observations, 0,
                         "el video no debe inflar total_observations como música")


class TestCleanApp(unittest.TestCase):
    """F4: nombres de app legibles, estructural (sin lista por idioma)."""

    def test_strips_exe_and_qualifier(self):
        self.assertEqual(_clean_app("code.exe"), "Code")
        self.assertEqual(_clean_app("spotify.exe"), "Spotify")
        # el bug daba "Whatsapp.root"; ahora el nombre primario.
        self.assertEqual(_clean_app("whatsapp.root.exe"), "Whatsapp")
        self.assertEqual(_clean_app("opera.exe"), "Opera")


class TestRhythmNotDegenerate(unittest.TestCase):
    """F4: el 'ritmo diario' solo se emite si DISTINGUE franjas."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = BehaviorLog(user="t", dir_path=self.tmp)

    def test_single_dominant_app_no_rhythm_noise(self):
        base = int(time.time() * 1000)
        # Code domina las 4 franjas → "ritmo" sería puro ruido redundante.
        for k, slot in enumerate(("mañana", "tarde", "noche", "madrugada")):
            for i in range(5):
                _insert(self.log, "app_focus", "code.exe",
                        base + (k * 100 + i) * 1000,
                        {"source": "ambient", "slot": slot, "dwell_s": 400})
        txt = profile_text(build_profile(self.log))
        self.assertIn("Code", txt)
        self.assertNotIn("Ritmo diario", txt,
                         "una sola app dominante no debe generar frase de ritmo")

    def test_distinct_apps_per_slot_keep_rhythm(self):
        base = int(time.time() * 1000)
        # Code de día, Spotify de noche → el ritmo SÍ informa y se conserva.
        for i in range(5):
            _insert(self.log, "app_focus", "code.exe", base + i * 1000,
                    {"source": "ambient", "slot": "mañana", "dwell_s": 600})
        for i in range(5):
            _insert(self.log, "app_focus", "spotify.exe", base + (100 + i) * 1000,
                    {"source": "ambient", "slot": "noche", "dwell_s": 600})
        txt = profile_text(build_profile(self.log))
        self.assertIn("Ritmo diario", txt,
                      "franjas con apps distintas SÍ deben dar ritmo")


class TestBootThrottle(unittest.TestCase):
    """F2: el flood de boot se corta por estado de la DB, no por lista."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = BehaviorLog(user="t", dir_path=self.tmp)

    def tearDown(self):
        self.log.close()

    def test_boot_throttled_within_gap(self):
        # primer boot pasa; los siguientes dentro del gap NO (restart-loop).
        self.assertTrue(self.log.record_throttled("boot", "agent", 300))
        self.assertFalse(self.log.record_throttled("boot", "agent", 300))
        self.assertFalse(self.log.record_throttled("boot", "agent", 300))
        boots = [e for e in self.log.events() if e["kind"] == "boot"]
        self.assertEqual(len(boots), 1, "restart-loop no debe floodear boots")

    def test_boot_recorded_after_gap(self):
        # con gap 0, un boot real (sesión nueva) sí se registra.
        self.assertTrue(self.log.record_throttled("boot", "agent", 0))
        self.assertTrue(self.log.record_throttled("boot", "agent", 0))
        boots = [e for e in self.log.events() if e["kind"] == "boot"]
        self.assertGreaterEqual(len(boots), 1)

    def test_last_event_ts_helper(self):
        self.assertIsNone(self.log.last_event_ts("boot", "agent"))
        self.log.record("boot", "agent")
        self.assertIsNotNone(self.log.last_event_ts("boot", "agent"))
        # key distinta no colisiona
        self.assertIsNone(self.log.last_event_ts("boot", "pc"))


if __name__ == "__main__":
    unittest.main()
