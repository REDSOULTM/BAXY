"""Tests for streaming URL correctness + GUI search shortcut flow.

Background (2026-05-15): user reportó que media(disney+, Daredevil)
abrio https://www.disneyplus.com/search?q=Daredevil que es 404. La URL
real de Disney+ no soporta query via parameter. Para esas plataformas
abrimos el home y usamos keyboard shortcut para abrir el search.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from .domain_tools import (
    _STREAMING_PLATFORMS,
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


class TestPlatformURLShape(unittest.TestCase):
    """Las URLs base deben coincidir con el spec real de cada plataforma."""

    def test_netflix_supports_query_param(self):
        spec = _STREAMING_PLATFORMS["netflix"]
        self.assertTrue(spec["web_search_via_url"])
        self.assertIn("netflix.com/search", spec["web_url"])
        self.assertIn("{q}", spec["web_url"])

    def test_disney_uses_home_url(self):
        # Disney+ NO soporta query via URL — devuelve 404. Usamos home.
        spec = _STREAMING_PLATFORMS["disney"]
        self.assertFalse(spec["web_search_via_url"])
        self.assertNotIn("{q}", spec["web_url"])
        self.assertIn("disneyplus.com", spec["web_url"])
        self.assertIn("home", spec["web_url"])
        # Y tiene shortcut para abrir search via GUI.
        self.assertEqual(spec["search_shortcut"], "s")

    def test_hbo_max_uses_home_url(self):
        spec = _STREAMING_PLATFORMS["hbo_max"]
        self.assertFalse(spec["web_search_via_url"])
        self.assertNotIn("{q}", spec["web_url"])
        # Max ahora redirige hbomax.com -> play.max.com cuando estas logueado.
        self.assertIn("hbomax.com", spec["web_url"])
        self.assertEqual(spec["search_shortcut"], "/")

    def test_prime_video_supports_phrase_param(self):
        spec = _STREAMING_PLATFORMS["prime_video"]
        self.assertTrue(spec["web_search_via_url"])
        self.assertIn("primevideo.com", spec["web_url"])
        # Prime usa phrase=, no q=.
        self.assertIn("phrase={q}", spec["web_url"])

    def test_spotify_has_deeplink(self):
        spec = _STREAMING_PLATFORMS["spotify"]
        self.assertEqual(spec["deeplink"], "spotify:search:{q}")
        self.assertIn("open.spotify.com", spec["web_url"])


class TestDisneyOpensHomeNotBrokenSearch(unittest.TestCase):
    """Regresion del bug: Disney+ abria /search?q= que es 404."""

    def test_disney_url_does_not_include_search_param(self):
        state = _fresh_state()
        _set_streaming_preference(state, "disney", "Ema")

        def _exec(name, args):
            if name == "gui" and args.get("action") == "click_text":
                return {"ok": True, "found": True}
            return {"ok": True}

        with patch("gemma4_agent.domain_tools.webbrowser.open",
                   return_value=True) as wb, \
             patch("time.sleep"):
            media_tool(
                {"action": "play", "provider": "disney",
                 "query": "Daredevil Born Again"},
                _exec, state,
            )
        called_url = wb.call_args.args[0]
        # CRITICAL: no debe incluir /search ni ?q=.
        self.assertNotIn("/search?q=", called_url)
        self.assertNotIn("?q=Daredevil", called_url)
        # Debe ir al home.
        self.assertIn("home", called_url)

    def test_disney_gui_flow_includes_shortcut_search(self):
        state = _fresh_state()
        _set_streaming_preference(state, "disney", "Ema")
        clicks: list[tuple] = []
        def _exec(name, args):
            clicks.append((name, dict(args)))
            if name == "gui" and args.get("action") == "click_text":
                return {"ok": True, "found": True}
            return {"ok": True}

        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True), \
             patch("time.sleep"):
            r = media_tool(
                {"action": "play", "provider": "disney", "query": "Loki"},
                _exec, state,
            )
        steps = r.get("web_auto_play_info", {}).get("steps", [])
        # El flow debe incluir keyboard shortcut "s" + type "Loki" + Enter.
        self.assertIn("pressed_search_shortcut:s", steps)
        self.assertIn("typed_query:Loki", steps)
        self.assertIn("submitted_search", steps)
        self.assertTrue(r["played"])

    def test_netflix_does_not_use_shortcut(self):
        # Netflix soporta URL con query, NO debe usar GUI shortcut.
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Ema")

        def _exec(name, args):
            if name == "gui" and args.get("action") == "click_text":
                return {"ok": True, "found": True}
            return {"ok": True}

        with patch("gemma4_agent.domain_tools.webbrowser.open",
                   return_value=True) as wb, \
             patch("time.sleep"):
            r = media_tool(
                {"action": "play", "provider": "netflix", "query": "Stranger Things"},
                _exec, state,
            )
        # URL incluye query
        self.assertIn("?q=", wb.call_args.args[0])
        # Y el GUI flow NO incluye shortcut/type/submit search.
        steps = r.get("web_auto_play_info", {}).get("steps", [])
        for s in steps:
            self.assertFalse(s.startswith("pressed_search_shortcut"),
                              f"netflix should not use shortcut, got step: {s}")
            self.assertFalse(s.startswith("typed_query"),
                              f"netflix should not type query via GUI, got: {s}")

    def test_max_uses_home_url_not_broken_search(self):
        state = _fresh_state()
        _set_streaming_preference(state, "hbo_max", "Em")
        def _exec(name, args):
            if name == "gui" and args.get("action") == "click_text":
                return {"ok": True, "found": True}
            return {"ok": True}
        with patch("gemma4_agent.domain_tools.webbrowser.open",
                   return_value=True) as wb, \
             patch("time.sleep"):
            media_tool(
                {"action": "play", "provider": "max",
                 "query": "House of Dragon"},
                _exec, state,
            )
        url = wb.call_args.args[0]
        # No debe ser www.max.com/search?q= (que es 404).
        self.assertFalse(url.startswith("https://www.max.com/search?"))


if __name__ == "__main__":
    unittest.main()
