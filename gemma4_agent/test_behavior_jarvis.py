"""Tests del Jarvis proactivo (investigación 5): behavior_log + pattern_miner.

Base del asistente que aprende patrones del usuario y ofrece automatizarlos.
La minería es código DETERMINISTA (cabe en vram4); el LLM solo conversa.
"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from gemma4_agent.behavior_log import BehaviorLog, ALLOWED_KINDS
from gemma4_agent.pattern_miner import mine_simple_patterns, PatternCandidate


class BehaviorLogTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.bl = BehaviorLog(user="t", dir_path=self.dir)

    def tearDown(self):
        self.bl.close()

    def test_records_valid_events(self):
        self.assertTrue(self.bl.record("boot", "pc"))
        self.assertTrue(self.bl.record("app_close", "Discord.exe"))
        evs = self.bl.events()
        self.assertEqual(len(evs), 2)
        # normaliza a lowercase
        self.assertTrue(any(e["key"] == "discord.exe" for e in evs))

    def test_anti_poison_whitelist(self):
        # kind fuera de la whitelist -> NO se guarda (evita contaminación)
        self.assertFalse(self.bl.record("test_junk", "basura"))
        self.assertFalse(self.bl.record("random", "x"))
        self.assertEqual(self.bl.events(), [])

    def test_empty_key_rejected(self):
        self.assertFalse(self.bl.record("app_open", ""))
        self.assertFalse(self.bl.record("app_open", "   "))

    def test_per_user_isolation(self):
        self.bl.record("boot", "pc")
        other = BehaviorLog(user="otro", dir_path=self.dir)
        try:
            self.assertEqual(other.events(), [])  # otro usuario no ve los eventos
        finally:
            other.close()

    def test_allowed_kinds_are_stable_signals(self):
        # la whitelist debe ser acotada (no un cajón de sastre)
        self.assertLessEqual(len(ALLOWED_KINDS), 8)
        self.assertIn("boot", ALLOWED_KINDS)
        self.assertIn("app_close", ALLOWED_KINDS)


class PatternMinerTest(unittest.TestCase):
    def _events_red_case(self, days=10, close_n=8):
        """Caso de RED: cada arranque cierra Discord (close_n de days veces)."""
        now = int(time.time() * 1000)
        day = 86400 * 1000
        evs = []
        for d in range(days):
            base = now - (days - d) * day
            evs.append({"ts": base, "kind": "boot", "key": "pc", "context": {}})
            if d < close_n:
                evs.append({"ts": base + 30000, "kind": "app_close",
                            "key": "discord.exe", "context": {}})
        return sorted(evs, key=lambda e: e["ts"])

    def test_detects_reds_close_discord_on_boot(self):
        pats = mine_simple_patterns(self._events_red_case())
        match = [p for p in pats if p.target_key == "discord.exe"
                 and p.target_kind == "app_close"]
        self.assertTrue(match, "debería detectar 'cerrar Discord al arrancar'")
        p = match[0]
        self.assertEqual(p.count, 8)
        self.assertGreaterEqual(p.consistency, 0.6)

    def test_maps_to_routine_trigger(self):
        pats = mine_simple_patterns(self._events_red_case())
        p = [p for p in pats if p.target_key == "discord.exe"][0]
        r = p.to_routine_trigger()
        self.assertIsNotNone(r)
        self.assertEqual(r["action"]["tool"], "app")
        self.assertEqual(r["action"]["args"]["action"], "close")

    def test_conservative_below_thresholds(self):
        # solo 3 de 10 -> consistencia 0.3 < 0.6 -> NO sugiere
        pats = mine_simple_patterns(self._events_red_case(days=10, close_n=3))
        match = [p for p in pats if p.target_key == "discord.exe"]
        self.assertFalse(match, "0.3 consistencia no debe disparar (conservador)")

    def test_insufficient_window_no_suggestion(self):
        # solo 2 días de datos -> no sugerir aunque haya repeticiones
        pats = mine_simple_patterns(self._events_red_case(days=2, close_n=2))
        self.assertEqual(pats, [])

    def test_empty_events(self):
        self.assertEqual(mine_simple_patterns([]), [])


if __name__ == "__main__":
    unittest.main()


class SuggestionQueueTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        from gemma4_agent.suggestion_queue import SuggestionQueue
        self.q = SuggestionQueue(user="t", dir_path=Path(tempfile.mkdtemp()))
        self.c1 = PatternCandidate("boot", "pc", "app_close", "discord.exe", 8, 0.8, 30.0)
        self.c2 = PatternCandidate("boot", "pc", "app_open", "chrome.exe", 10, 1.0, 50.0)
        self.now = time.time()

    def test_offers_best_candidate_first(self):
        s = self.q.next_suggestion([self.c2, self.c1], now=self.now)
        self.assertIsNotNone(s)

    def test_rate_limit_one_per_hour(self):
        self.assertIsNotNone(self.q.next_suggestion([self.c1], now=self.now))
        self.assertIsNone(self.q.next_suggestion([self.c2], now=self.now + 60))
        self.assertIsNotNone(self.q.next_suggestion([self.c2], now=self.now + 3601))

    def test_rejected_pattern_silenced(self):
        self.q.mark_rejected(self.c1, now=self.now)
        self.assertIsNone(self.q.next_suggestion([self.c1], now=self.now + 3601))

    def test_accepted_never_reoffered(self):
        self.q.mark_accepted(self.c2)
        self.assertIsNone(self.q.next_suggestion([self.c2], now=self.now + 10 * 3600))

    def test_rejected_reoffered_if_count_doubles(self):
        self.q.mark_rejected(self.c1, now=self.now)
        # count subió de 8 a 16 (duplicó) -> se puede re-ofrecer aunque < 30d
        stronger = PatternCandidate("boot", "pc", "app_close", "discord.exe", 16, 0.9, 30.0)
        self.assertIsNotNone(self.q.next_suggestion([stronger], now=self.now + 3601))


class PendingSuggestionHandlerTest(unittest.TestCase):
    def _agent(self):
        from gemma4_agent.agent import Gemma4Agent
        ag = Gemma4Agent.__new__(Gemma4Agent)
        class _T:
            def execute(self, name, args):
                self.last = (name, args); return {"ok": True}
        ag.tools = _T()
        ag._pending_suggestion = PatternCandidate(
            "boot", "agent", "app_close", "discord.exe", 8, 0.8, 30.0)
        return ag

    def test_yes_creates_routine(self):
        ag = self._agent()
        r = ag._handle_pending_suggestion("sí dale")
        self.assertIsNotNone(r)
        self.assertIn("automatic", r.content.lower())
        self.assertEqual(ag.tools.last[0], "routine")
        self.assertEqual(ag.tools.last[1]["action"], "create")
        self.assertEqual(ag.tools.last[1]["steps"][0]["args"]["action"], "close")
        self.assertIsNone(ag._pending_suggestion)  # consumida

    def test_no_declines(self):
        ag = self._agent()
        r = ag._handle_pending_suggestion("no, mejor no")
        self.assertIsNotNone(r)
        self.assertIn("no lo automatizo", r.content.lower())
        self.assertIsNone(ag._pending_suggestion)

    def test_ambiguous_does_not_consume(self):
        ag = self._agent()
        r = ag._handle_pending_suggestion("qué hora es")
        self.assertIsNone(r)  # sigue el turno normal
        self.assertIsNotNone(ag._pending_suggestion)  # oferta sigue viva

    def test_no_pending_returns_none(self):
        ag = self._agent()
        ag._pending_suggestion = None
        self.assertIsNone(ag._handle_pending_suggestion("sí"))

    def test_yes_no_multilingual(self):
        # Principio universal: la app la usa cualquier hablante. El sí/no a la
        # oferta de Jarvis se entiende en varios idiomas (vocabulario cerrado).
        for yes in ("yes", "oui", "ja", "sim", "sì", "vale", "okay"):
            ag = self._agent()
            r = ag._handle_pending_suggestion(yes)
            self.assertIsNotNone(r, yes)
            self.assertIn("automatic", r.content.lower(), yes)
        for no in ("no", "nein", "não", "non", "nope", "nah"):
            ag = self._agent()
            r = ag._handle_pending_suggestion(no)
            self.assertIsNotNone(r, no)
            self.assertIn("no lo automatizo", r.content.lower(), no)

    def test_non_latin_script_not_erased(self):
        # bug previo: el sub(r'[^a-záéíóúñ ]') borraba cirílico/CJK -> sí/no de
        # esos idiomas quedaba vacío. Ahora se tokeniza Unicode. Un texto no
        # reconocido NO se consume (cae a None), pero NO debe crashear.
        ag = self._agent()
        r = ag._handle_pending_suggestion("да")  # 'sí' en ruso (no en el set)
        self.assertIsNone(r)  # no reconocido -> turno normal (miss benigno)
        self.assertIsNotNone(ag._pending_suggestion)  # oferta sigue viva
