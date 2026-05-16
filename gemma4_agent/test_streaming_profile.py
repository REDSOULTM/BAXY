"""Tests for streaming web auto-play with profile picker (Netflix/Disney/HBO/Prime)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from .domain_tools import (
    _get_streaming_preference,
    _set_streaming_preference,
    media_tool,
)
from .state import AgentState


def _fresh_state() -> AgentState:
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    p = Path(tmp.name)
    p.unlink(missing_ok=True)
    return AgentState(path=p)


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
        def _exec(name, args):
            if name == "gui" and args.get("action") == "click_text":
                return {"ok": True, "found": True}
            return {"ok": True}
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True), \
             patch("time.sleep"):
            media_tool(
                {"action": "play", "provider": "netflix",
                 "query": "Stranger Things", "profile": "Emmanuel"},
                _exec, state,
            )
        # Verificar que quedo guardado.
        self.assertEqual(_get_streaming_preference(state, "netflix"), "Emmanuel")

    def test_second_call_reuses_saved_profile(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Bea")

        def _exec(name, args):
            if name == "gui" and args.get("action") == "click_text":
                return {"ok": True, "found": True}
            return {"ok": True}
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True), \
             patch("time.sleep"):
            r = media_tool(
                {"action": "play", "provider": "netflix", "query": "Loki"},
                _exec, state,
            )
        self.assertTrue(r["ok"])
        self.assertEqual(r["profile_name"], "Bea")

    def test_explicit_profile_overrides_saved(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "OldName")

        def _exec(name, args):
            if name == "gui" and args.get("action") == "click_text":
                return {"ok": True, "found": True}
            return {"ok": True}
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True), \
             patch("time.sleep"):
            r = media_tool(
                {"action": "play", "provider": "netflix",
                 "query": "X", "profile": "NewName"},
                _exec, state,
            )
        self.assertEqual(r["profile_name"], "NewName")
        # Y se actualiza el saved.
        self.assertEqual(_get_streaming_preference(state, "netflix"), "NewName")


class TestStreamingWebGuiFlow(unittest.TestCase):
    """El flujo GUI: profile click -> title click -> play click."""

    def test_full_flow_uses_tab_navigation(self):
        # Post 2026-05-16: OCR del title era fragil. Flow nuevo usa Tab
        # navigation + Enter. Marca attempted_play=True (best-effort) en
        # vez de played=True (que requeriria verificacion visual).
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Emmanuel")
        calls: list[tuple[str, str]] = []
        def _exec(name, args):
            calls.append((name, args.get("action") or ""))
            if name == "gui" and args.get("action") == "click_text":
                # Solo el perfil sigue usando OCR; success.
                return {"ok": True, "found": True}
            return {"ok": True}
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True), \
             patch("time.sleep"):
            r = media_tool(
                {"action": "play", "provider": "netflix", "query": "Stranger Things"},
                _exec, state,
            )
        # Best-effort: attempted_play=True, played=False (no verification).
        self.assertTrue(r["attempted_play"])
        self.assertFalse(r["played"])
        self.assertEqual(r["completion_status"], "playback_attempted_unverified")
        # Debe haber tab + enter calls.
        tab_calls = [c for c in calls if c == ("gui", "keypress")]
        # Al menos 6 tabs (titulo) + 3 tabs (play) + 2 enters
        self.assertGreaterEqual(len(tab_calls), 10)

    def test_flow_completes_even_if_title_not_in_ocr(self):
        # Nuevo flow no usa click_text para el titulo — usa Tab navigation.
        # Asi que NO depende de OCR para encontrar el titulo. Esto previene
        # la regresion del log 13:10 donde OCR no encontraba "Daredevil".
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Emmanuel")
        def _exec(name, args):
            if name == "gui" and args.get("action") == "click_text":
                # Solo el perfil. Resto NO se llama (usamos Tab nav).
                if args.get("target") == "Emmanuel":
                    return {"ok": True, "found": True}
                return {"ok": True, "found": False}
            return {"ok": True}
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True), \
             patch("time.sleep"):
            r = media_tool(
                {"action": "play", "provider": "netflix", "query": "Cualquier Cosa"},
                _exec, state,
            )
        # Aunque OCR del titulo fallara, el flow completa via Tab nav.
        self.assertTrue(r["attempted_play"])
        self.assertIsNone(r["web_auto_play_info"]["abort_reason"])

    def test_auto_play_false_skips_gui_flow(self):
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
        # Executor NO debe haberse llamado para click_text.
        click_calls = [c for c in executor.call_args_list
                       if c.args[0] == "gui" and c.args[1].get("action") == "click_text"]
        self.assertEqual(len(click_calls), 0)


if __name__ == "__main__":
    unittest.main()
