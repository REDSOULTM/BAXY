"""Tests del Jarvis PROACTIVO (sugerencia sin turno del user):
- notifier: gate OFF, anti-molestia (do-not-disturb), emisión con toaster mock.
- orquestador: disparo en vivo detecta patrón completado -> ofrece.
- reversibilidad: created_by=jarvis se persiste y se puede filtrar/apagar.

NO ejercita input GUI ni toasts/TTS reales (mocks). Seguro.
"""
import os
import tempfile
import time
import unittest
from pathlib import Path

from ..memory_pkg.behavior_log import BehaviorLog
from ..memory_pkg.pattern_miner import PatternCandidate
from ..memory_pkg import proactive_notifier as notifier


class _MockToaster:
    def __init__(self):
        self.shown = []
        self.last_accept = None
        self.last_reject = None

    def show(self, body, cand, on_accept, on_reject):
        self.shown.append(body)
        self.last_accept = on_accept
        self.last_reject = on_reject


_CAND = PatternCandidate("app_open", "steam.exe", "app_open", "discord.exe", 8, 0.8, 30.0)


class NotifierTest(unittest.TestCase):
    def setUp(self):
        # limpiar gates entre tests
        for k in ("GEMMA4_JARVIS_PROACTIVE", "GEMMA4_JARVIS_PROACTIVE_TTS"):
            os.environ.pop(k, None)

    def test_off_by_default(self):
        # sin el gate, NO emite (default OFF, no sorprende al user)
        tm = _MockToaster()
        self.assertFalse(notifier.notify_suggestion(_CAND, toaster=tm))
        self.assertEqual(tm.shown, [])

    def test_emits_when_enabled(self):
        os.environ["GEMMA4_JARVIS_PROACTIVE"] = "1"
        tm = _MockToaster()
        ok = notifier.notify_suggestion(_CAND, foreground_proc="notepad.exe", toaster=tm)
        self.assertTrue(ok)
        self.assertEqual(len(tm.shown), 1)
        self.assertIn("discord", tm.shown[0].lower())

    def test_do_not_disturb_in_call(self):
        # en una videollamada (discord/zoom en foco) NO molesta
        os.environ["GEMMA4_JARVIS_PROACTIVE"] = "1"
        tm = _MockToaster()
        ok = notifier.notify_suggestion(_CAND, foreground_proc="zoom.exe", toaster=tm)
        self.assertFalse(ok)
        self.assertEqual(tm.shown, [])

    def test_accept_reject_callbacks_wired(self):
        os.environ["GEMMA4_JARVIS_PROACTIVE"] = "1"
        tm = _MockToaster()
        accepted, rejected = [], []
        notifier.notify_suggestion(_CAND, foreground_proc="notepad.exe", toaster=tm,
                                   on_accept=lambda c: accepted.append(c),
                                   on_reject=lambda c: rejected.append(c))
        tm.last_accept(_CAND)
        tm.last_reject(_CAND)
        self.assertEqual(accepted, [_CAND])
        self.assertEqual(rejected, [_CAND])


class OrchestratorTest(unittest.TestCase):
    def setUp(self):
        os.environ["GEMMA4_JARVIS_PROACTIVE"] = "1"
        self.tmp = Path(tempfile.mkdtemp())
        self.log = BehaviorLog(user="t", dir_path=self.tmp)

    def tearDown(self):
        os.environ.pop("GEMMA4_JARVIS_PROACTIVE", None)

    def _insert(self, ts_ms, kind, key):
        # record() usa ts=ahora; para sembrar HISTÓRICO insertamos directo (la PK
        # es (ts,user,kind,key); ts único por evento).
        conn = self.log._open()
        conn.execute("INSERT OR IGNORE INTO behavior_events(ts,user,kind,key,context) "
                     "VALUES(?,?,?,?,?)", (ts_ms, "t", kind, key, "{}"))
        conn.commit()

    def _seed_pattern(self):
        # sembrar 8 días de "abro steam, ~30s después abro discord" -> patrón sólido
        base = int(time.time() * 1000) - 8 * 86400 * 1000
        for d in range(8):
            t0 = base + d * 86400 * 1000
            self._insert(t0, "app_open", "steam.exe")
            self._insert(t0 + 30_000, "app_open", "discord.exe")

    def test_live_trigger_offers(self):
        from ..memory_pkg.jarvis_proactive import make_transition_handler
        self._seed_pattern()
        # simular: acabo de abrir steam, y AHORA abro discord (completa el patrón)
        now = time.time()
        self._insert(int(now * 1000) - 20_000, "app_open", "steam.exe")
        offered = []
        # interceptar el notifier para no abrir un toast real
        import gemma4_agent.memory_pkg.proactive_notifier as _n
        _orig = _n.notify_suggestion
        _n.notify_suggestion = lambda cand, **kw: (offered.append(cand), True)[1]
        try:
            from ..memory_pkg.suggestion_queue import SuggestionQueue
            q = SuggestionQueue(user="t", dir_path=self.tmp)  # cola aislada (no global)
            h = make_transition_handler(self.log, create_routine=lambda c: True, queue=q)
            h("discord.exe", "discord.exe", now)
        finally:
            _n.notify_suggestion = _orig
        self.assertTrue(offered, "debió ofrecer al completar el patrón steam->discord en vivo")
        self.assertEqual(offered[0].target_key, "discord.exe")


class ReversibilityTest(unittest.TestCase):
    def test_created_by_persisted_and_filterable(self):
        # el create guarda created_by; list lo filtra (reusa el routine_tool real
        # sería costoso -> verificamos el contrato del metadata directamente).
        from ..memory_pkg.jarvis_proactive import build_routine_from_candidate

        class _Tools:
            def __init__(self): self.calls = []
            def execute(self, name, args):
                self.calls.append((name, args)); return {"ok": True}
        t = _Tools()
        ok = build_routine_from_candidate(t, _CAND)
        self.assertTrue(ok)
        name, args = t.calls[0]
        self.assertEqual(name, "routine")
        self.assertEqual(args["action"], "create")
        self.assertEqual(args["created_by"], "jarvis")   # marca de origen
        self.assertTrue(args["name"].startswith("jarvis:"))


if __name__ == "__main__":
    unittest.main()
