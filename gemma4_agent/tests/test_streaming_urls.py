"""Tests for streaming URL correctness + CDP-first playback flow.

Background (compass research 2026-05-16): the prior implementation tried to
type into the page via OS-level keystrokes after a 's' shortcut. Research
confirmed no platform has a documented 's' search hotkey, and OCR on poster
images is unreliable. Current design:

  1. URLs come from research (Disney+ /es-419/search, HBO Max
     play.hbomax.com/search, Netflix /search?q=, Prime ?phrase=).
  2. Playback uses CDP attach to Chrome (port 9222) + Playwright selectors.
  3. If CDP unavailable -> webbrowser.open as honest fallback (no Tab nav,
     no fake auto-play).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ..domain_tools import (
    _STREAMING_PLATFORMS,
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


class TestPlatformURLShape(unittest.TestCase):
    """Las URLs base deben coincidir con el spec real de cada plataforma."""

    def test_netflix_supports_query_param(self):
        spec = _STREAMING_PLATFORMS["netflix"]
        self.assertTrue(spec["web_search_via_url"])
        self.assertIn("netflix.com/search", spec["web_url"])
        self.assertIn("{q}", spec["web_url"])

    def test_disney_uses_search_page_no_query_param(self):
        # Disney+ NO tiene `?q=` documentado (compass research 2026-05-16).
        # Vamos a /es-419/search (LATAM locale) y el agente teclea en el input.
        spec = _STREAMING_PLATFORMS["disney"]
        self.assertFalse(spec["web_search_via_url"])
        self.assertNotIn("{q}", spec["web_url"])
        self.assertIn("disneyplus.com", spec["web_url"])
        self.assertIn("search", spec["web_url"])

    def test_hbo_max_uses_play_hbomax(self):
        # Rebrand back to HBO Max on 9 July 2025. SPA at play.hbomax.com.
        # CDP probe 2026-05-16 verified: ?q= works on play.hbomax.com/search.
        spec = _STREAMING_PLATFORMS["hbo_max"]
        self.assertTrue(spec["web_search_via_url"])
        self.assertIn("{q}", spec["web_url"])
        self.assertIn("hbomax.com", spec["web_url"])

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


class TestPlaybackSelectors(unittest.TestCase):
    """Cada plataforma debe tener selectores DOM para search/result/play."""

    def test_netflix_has_data_uia_selectors(self):
        pb = _STREAMING_PLATFORMS["netflix"]["playback"]
        # Netflix usa data-uia (CDP probe 2026-05-16).
        self.assertTrue(any("data-uia" in s for s in pb["search_input"]))
        # Result cards: a[data-uia='search-gallery-video-card'].
        self.assertTrue(any("data-uia" in s and "video-card" in s
                              for s in pb["result_card"]))
        # Play button: [data-uia='play-button'].
        self.assertTrue(any("data-uia" in s and "play" in s
                              for s in pb["play_button"]))

    def test_disney_has_aria_selectors(self):
        pb = _STREAMING_PLATFORMS["disney"]["playback"]
        # Disney+ usa aria-label + data-testid.
        self.assertTrue(pb["search_input"])
        self.assertTrue(pb["result_card"])
        self.assertTrue(any("data-testid" in s for s in pb["play_button"]))

    def test_hbo_max_has_testid_selectors(self):
        pb = _STREAMING_PLATFORMS["hbo_max"]["playback"]
        self.assertTrue(any("data-testid" in s for s in pb["search_input"]))
        self.assertTrue(pb["result_card"])
        self.assertTrue(any("data-testid" in s for s in pb["play_button"]))

    def test_prime_video_has_automation_selectors(self):
        pb = _STREAMING_PLATFORMS["prime_video"]["playback"]
        self.assertTrue(pb["result_card"])
        # Prime usa data-automation-id.
        self.assertTrue(any("data-automation-id" in s for s in pb["play_button"]))


class TestDisneyURLDoesNotInclude404SearchParam(unittest.TestCase):
    """Regresion del bug original: /search?q= en Disney+ era 404."""

    def test_disney_url_does_not_include_q_param(self):
        state = _fresh_state()
        _set_streaming_preference(state, "disney", "Ema")

        # Sin CDP disponible -> fallback a webbrowser.open con la URL del spec.
        def _exec(name, args):
            if name == "browser_real" and args.get("action") == "connect_cdp":
                return {"ok": False, "error": "no chrome on 9222"}
            return {"ok": True}

        with patch("gemma4_agent.domain_tools.webbrowser.open",
                   return_value=True) as wb:
            media_tool(
                {"action": "play", "provider": "disney",
                 "query": "Daredevil Born Again"},
                _exec, state,
            )
        called_url = wb.call_args.args[0]
        # CRITICAL: no debe incluir /search?q= (404 en Disney+).
        self.assertNotIn("/search?q=", called_url)
        self.assertNotIn("?q=Daredevil", called_url)
        # Debe ir a /es-419/search (la search page real).
        self.assertIn("disneyplus.com", called_url)
        self.assertIn("search", called_url)

    def test_max_url_does_not_use_max_com_search(self):
        # Bug previo: usabamos www.max.com/search?q= que es 404.
        state = _fresh_state()
        _set_streaming_preference(state, "hbo_max", "Em")

        def _exec(name, args):
            if name == "browser_real" and args.get("action") == "connect_cdp":
                return {"ok": False, "error": "no chrome on 9222"}
            return {"ok": True}

        with patch("gemma4_agent.domain_tools.webbrowser.open",
                   return_value=True) as wb:
            media_tool(
                {"action": "play", "provider": "max",
                 "query": "House of Dragon"},
                _exec, state,
            )
        url = wb.call_args.args[0]
        # No debe ser max.com/search (404). Debe ser hbomax.com.
        self.assertFalse(url.startswith("https://www.max.com/search"))
        self.assertIn("hbomax.com", url)


class TestCDPFallbackBehavior(unittest.TestCase):
    """Cuando CDP no esta disponible, caemos a webbrowser.open honestamente.

    Sin Tab nav ciega, sin fake auto-play. attempted_play y played son False.
    """

    def test_disney_no_cdp_falls_back_to_webbrowser(self):
        state = _fresh_state()
        _set_streaming_preference(state, "disney", "Ema")

        def _exec(name, args):
            if name == "browser_real" and args.get("action") == "connect_cdp":
                return {"ok": False, "error": "no chrome"}
            return {"ok": True}

        with patch("gemma4_agent.domain_tools.webbrowser.open",
                   return_value=True) as wb:
            r = media_tool(
                {"action": "play", "provider": "disney", "query": "Loki"},
                _exec, state,
            )
        # webbrowser.open llamado con la URL del spec.
        self.assertTrue(wb.called)
        # Sin CDP, no decimos played/attempted_play=True (seria mentira).
        self.assertFalse(r.get("played"))
        self.assertFalse(r.get("attempted_play"))
        self.assertFalse(r.get("via_cdp"))

    def test_netflix_no_cdp_falls_back_to_webbrowser(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Emmanuel")

        def _exec(name, args):
            if name == "browser_real" and args.get("action") == "connect_cdp":
                return {"ok": False, "error": "no chrome"}
            return {"ok": True}

        with patch("gemma4_agent.domain_tools.webbrowser.open",
                   return_value=True) as wb:
            r = media_tool(
                {"action": "play", "provider": "netflix",
                 "query": "Stranger Things"},
                _exec, state,
            )
        # Netflix URL incluye ?q=
        self.assertIn("?q=", wb.call_args.args[0])
        self.assertFalse(r.get("played"))
        self.assertFalse(r.get("via_cdp"))


class TestCDPHappyPath(unittest.TestCase):
    """Cuando CDP funciona, usamos selectores Playwright para auto-play."""

    def setUp(self):
        # These tests assert the CDP-AVAILABLE path. CDP availability is
        # decided by _ensure_cdp_browser(), which does a REAL Chrome probe /
        # auto-launch on port 9222 — nondeterministic in CI (it was flaking,
        # making "fill"/"click" never run when no real Chrome was up). Mock it
        # to deterministically-available so we test the play flow, not the
        # environment. The CDP-UNAVAILABLE fallback is covered by the
        # *_no_cdp_falls_back_to_webbrowser tests above.
        self._cdp_patch = patch(
            "gemma4_agent.domain_tools._ensure_cdp_browser",
            return_value={"cdp_ok": True, "reason": None,
                          "browser_key": "chrome", "action": "already_running"},
        )
        self._cdp_patch.start()
        self.addCleanup(self._cdp_patch.stop)

    def test_netflix_cdp_navigates_and_clicks_play(self):
        state = _fresh_state()
        _set_streaming_preference(state, "netflix", "Emmanuel")

        calls: list[tuple[str, dict]] = []

        def _exec(name, args):
            calls.append((name, dict(args)))
            if name == "browser_real":
                action = args.get("action")
                if action == "connect_cdp":
                    return {"ok": True}
                if action == "goto":
                    return {"ok": True}
                if action == "click":
                    # primer selector matchea
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
        # Debe haber llamado browser_real connect_cdp + goto + click.
        actions_called = [
            args.get("action") for name, args in calls if name == "browser_real"
        ]
        self.assertIn("connect_cdp", actions_called)
        self.assertIn("goto", actions_called)
        self.assertIn("click", actions_called)
        # via_cdp en el resultado.
        self.assertTrue(r.get("via_cdp"))
        # Y player_started=True (porque click play fue ok).
        self.assertTrue(r.get("played") or r.get("attempted_play"))

    def test_disney_cdp_fills_search_input_then_clicks_result(self):
        state = _fresh_state()
        _set_streaming_preference(state, "disney", "Ema")

        calls: list[tuple[str, dict]] = []

        def _exec(name, args):
            calls.append((name, dict(args)))
            if name == "browser_real":
                action = args.get("action")
                if action == "connect_cdp":
                    return {"ok": True}
                if action == "goto":
                    return {"ok": True}
                if action == "fill":
                    return {"ok": True}
                if action == "click":
                    return {"ok": True}
                if action == "active_tab":
                    return {"ok": True, "active_tab": {"url": "https://www.disneyplus.com/es-419/series/loki/abc"}}
            return {"ok": True}

        with patch("time.sleep"):
            r = media_tool(
                {"action": "play", "provider": "disney", "query": "Loki"},
                _exec, state,
            )
        actions_called = [
            args.get("action") for name, args in calls if name == "browser_real"
        ]
        # Disney+ NO tiene ?q=, asi que necesita fill.
        self.assertIn("fill", actions_called)
        self.assertIn("click", actions_called)
        self.assertTrue(r.get("via_cdp"))


if __name__ == "__main__":
    unittest.main()
