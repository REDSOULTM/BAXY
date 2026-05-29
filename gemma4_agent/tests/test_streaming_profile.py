"""Tests for streaming web auto-play with profile picker (Netflix/Disney/HBO/Prime).

Post compass-research 2026-05-16: playback usa CDP attach + Playwright selectors.
Cuando CDP NO esta disponible -> fallback honesto a webbrowser.open (sin Tab nav
ciega que causaba clicks accidentales).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ..domain_tools import (
    _get_streaming_preference,
    _set_streaming_preference,
    media_tool,
)
from ..memory_pkg.state import AgentState


def _fresh_state() -> AgentState:
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    p = Path(tmp.name)
    p.unlink(missing_ok=True)
    return AgentState(path=p)


def _no_cdp_exec(name, args):
    """Executor que simula CDP no disponible — fuerza fallback a webbrowser."""
    if name == "browser_real" and args.get("action") == "connect_cdp":
        return {"ok": False, "error": "no chrome on 9222"}
    return {"ok": True}


class TestStreamingPreferenceStore(unittest.TestCase):

    def test_get_returns_none_when_not_set(self):
        state = _fresh_state()
        self.assertIsNone(_get_streaming_preference(state, "netflix"))

    def test_set_then_get(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Emmanuel")
        self.assertEqual(_get_streaming_preference(state, "netflix"), "Emmanuel")

    def test_set_updates_existing(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Emmanuel")
        _set_streaming_preference(state, "netflix", "Bea")
        self.assertEqual(_get_streaming_preference(state, "netflix"), "Bea")

    def test_different_providers_independent(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Emmanuel")
        _set_streaming_preference(state, "disney", "Kids")
        self.assertEqual(_get_streaming_preference(state, "netflix"), "Emmanuel")
        self.assertEqual(_get_streaming_preference(state, "disney"), "Kids")
        self.assertIsNone(_get_streaming_preference(state, "hbo_max"))

    def test_none_state_safe(self):
        # Sin state, todo devuelve None / no crash.
        self.assertIsNone(_get_streaming_preference(None, "netflix"))
        self.assertIsNone(_set_streaming_preference(None, "netflix", "X"))


class TestStreamingFirstTimeAsksProfile(unittest.TestCase):
    """Cuando no hay perfil guardado, returna needs_user con asks_for."""

    def test_netflix_first_time_asks_profile(self):
        state = _fresh_state()
        executor = MagicMock(return_value={"ok": True})
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True):
            r = media_tool(
                {"action": "play", "provider": "netflix", "query": "Stranger Things"},
                executor, state,
            )
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        self.assertEqual(r["asks_for"], "streaming_profile")
        self.assertEqual(r["provider"], "netflix")

    def test_disney_first_time_asks_profile(self):
        state = _fresh_state()
        executor = MagicMock(return_value={"ok": True})
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True):
            r = media_tool(
                {"action": "play", "provider": "disney", "query": "Loki"},
                executor, state,
            )
        self.assertEqual(r["asks_for"], "streaming_profile")

    def test_hbo_max_first_time_asks_profile(self):
        state = _fresh_state()
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True):
            r = media_tool(
                {"action": "play", "provider": "max", "query": "House of Dragon"},
                MagicMock(return_value={"ok": True}), state,
            )
        self.assertEqual(r["asks_for"], "streaming_profile")

    def test_prime_first_time_asks_profile(self):
        state = _fresh_state()
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True):
            r = media_tool(
                {"action": "play", "provider": "prime", "query": "The Boys"},
                MagicMock(return_value={"ok": True}), state,
            )
        self.assertEqual(r["asks_for"], "streaming_profile")

    def test_spotify_does_not_ask_profile(self):
        # Spotify no tiene profile picker.
        state = _fresh_state()
        def exec_spotify(name, args):
            if name == "window" and args.get("action") == "active":
                return {"ok": True, "active": {"title": "Spotify"}}
            return {"ok": True}
        with patch("gemma4_agent.domain_tools._find_streaming_app",
                   return_value={"kind": "exe", "launch_target": "X"}), \
             patch("gemma4_agent.domain_tools.subprocess.Popen"), \
             patch("time.sleep"):
            r = media_tool(
                {"action": "play", "provider": "spotify", "query": "test"},
                exec_spotify, state,
            )
        self.assertTrue(r["ok"])
        self.assertNotEqual(r.get("status"), "needs_user")


class TestStreamingProfileSavedAndReused(unittest.TestCase):

    def test_first_call_with_profile_saves_it(self):
        state = _fresh_state()
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True), \
             patch("time.sleep"):
            media_tool(
                {"action": "play", "provider": "netflix",
                 "query": "Stranger Things", "profile": "Emmanuel"},
                _no_cdp_exec, state,
            )
        # Verificar que quedo guardado.
        self.assertEqual(_get_streaming_preference(state, "netflix"), "Emmanuel")

    def test_second_call_reuses_saved_profile(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Bea")

        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True), \
             patch("time.sleep"):
            r = media_tool(
                {"action": "play", "provider": "netflix", "query": "Loki"},
                _no_cdp_exec, state,
            )
        self.assertTrue(r["ok"])
        self.assertEqual(r["profile_name"], "Bea")

    def test_explicit_profile_overrides_saved(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "OldName")

        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True), \
             patch("time.sleep"):
            r = media_tool(
                {"action": "play", "provider": "netflix",
                 "query": "X", "profile": "NewName"},
                _no_cdp_exec, state,
            )
        self.assertEqual(r["profile_name"], "NewName")
        # Y se actualiza el saved.
        self.assertEqual(_get_streaming_preference(state, "netflix"), "NewName")


class TestCDPFallbackIsHonest(unittest.TestCase):
    """Sin CDP, NO afirmamos played/attempted (seria falso)."""

    def test_no_cdp_no_played_no_attempted(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Emmanuel")
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True), \
             patch("time.sleep"):
            r = media_tool(
                {"action": "play", "provider": "netflix",
                 "query": "Stranger Things"},
                _no_cdp_exec, state,
            )
        # Honestidad: sin CDP no podemos automatizar el play.
        self.assertFalse(r["played"])
        self.assertFalse(r["attempted_play"])
        self.assertFalse(r.get("via_cdp"))
        # Pero si abrimos la pagina.
        self.assertTrue(r["opened"])
        self.assertEqual(r["completion_status"], "opened_search_results_pending_play")

    def test_no_cdp_includes_unavailable_reason(self):
        # El info de auto-play debe incluir por que CDP no estaba disponible
        # (para debug del user — "ah, necesito Chrome con --remote-debugging-port").
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Emmanuel")
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True), \
             patch("time.sleep"):
            r = media_tool(
                {"action": "play", "provider": "netflix", "query": "X"},
                _no_cdp_exec, state,
            )
        info = r.get("web_auto_play_info") or {}
        self.assertIn("cdp_unavailable_reason", info)
        self.assertFalse(info.get("via_cdp"))


class TestCDPHappyPath(unittest.TestCase):
    """Cuando CDP funciona, auto-play via Playwright selectors."""

    def test_cdp_success_marks_played(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Emmanuel")

        def _exec(name, args):
            if name == "browser_real":
                action = args.get("action")
                if action == "connect_cdp":
                    return {"ok": True}
                if action == "goto":
                    return {"ok": True}
                if action == "click":
                    return {"ok": True}
                if action == "fill":
                    return {"ok": True}
                if action == "active_tab":
                    return {"ok": True, "active_tab": {"url": "https://www.netflix.com/watch/12345"}}
            return {"ok": True}

        with patch("time.sleep"):
            r = media_tool(
                {"action": "play", "provider": "netflix",
                 "query": "Stranger Things"},
                _exec, state,
            )
        self.assertTrue(r.get("via_cdp"))
        # CDP click play succeeded -> played True.
        self.assertTrue(r["played"])

    def test_auto_play_false_skips_cdp_attempt(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Emmanuel")
        executor = MagicMock(return_value={"ok": True})
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True):
            r = media_tool(
                {"action": "play", "provider": "netflix",
                 "query": "X", "auto_play": False},
                executor, state,
            )
        self.assertTrue(r["ok"])
        self.assertFalse(r["played"])
        # Con auto_play=False, NO debemos haber llamado browser_real.connect_cdp.
        cdp_calls = [c for c in executor.call_args_list
                     if c.args[0] == "browser_real"
                     and c.args[1].get("action") == "connect_cdp"]
        self.assertEqual(len(cdp_calls), 0)


if __name__ == "__main__":
    unittest.main()
