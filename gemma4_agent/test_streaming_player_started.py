"""Tests for F-001: `_streaming_cdp_play` must NOT report player_started=True
when no explicit play button was clicked, unless the platform's spec declares
`click_card_starts_playback=True` (Prime).

Reaches the `detail_page_reached_no_explicit_play_button` branch by making
ALL play-button selectors fail on click — only the result_card click succeeds.
"""
from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from gemma4_agent.domain_tools import _streaming_cdp_play, _STREAMING_PLATFORMS


def _make_executor(spec: dict[str, Any]):
    """Returns executor that simulates: goto ok, fill ok, FIRST click ok
    (the result_card), every subsequent click FAILS (play button selectors).

    For platforms with click_card_starts_playback=True, the function returns
    BEFORE the play_button click step, so this still works.
    """
    play_button_selectors = set(
        spec.get("playback", {}).get("play_button") or []
    )

    def executor(tool: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool != "browser_real":
            return {"ok": True}
        action = args.get("action")
        selector = args.get("selector", "")
        if action == "goto":
            return {"ok": True}
        if action == "active_tab":
            return {
                "ok": True,
                "active_tab": {"url": "https://example.com/detail/xyz"},
            }
        if action == "fill":
            return {"ok": True}
        if action == "click":
            # Any selector listed in play_button -> fail. Otherwise ok.
            if selector in play_button_selectors:
                return {"ok": False, "error": "selector not found"}
            return {"ok": True}
        return {"ok": True}

    return executor


class TestPlayerStartedHonest(unittest.TestCase):
    """`player_started` in the no-play-button branch must reflect spec."""

    def _run_for_platform(self, canonical: str) -> dict[str, Any]:
        spec = _STREAMING_PLATFORMS[canonical]
        executor = _make_executor(spec)
        # Patch time.sleep to skip the 20+s of waits inside _streaming_cdp_play.
        with patch("time.sleep", lambda *_a, **_k: None):
            result = _streaming_cdp_play(
                executor=executor,
                canonical=canonical,
                spec=spec,
                query="Loki",
                profile_name="Ema",
                web_url=spec.get("web_url", "https://example.com/search"),
                web_search_via_url=False,
                cached_url=None,
                state=None,
            )
        return result

    def test_disney_returns_false_when_no_play_button(self):
        spec = _STREAMING_PLATFORMS["disney"]
        click_starts = spec.get("playback", {}).get("click_card_starts_playback", False)
        self.assertFalse(click_starts)
        result = self._run_for_platform("disney")
        self.assertIn(
            "detail_page_reached_no_explicit_play_button",
            result.get("steps", []),
        )
        # player_started must be False: spec does NOT declare auto-playback.
        self.assertFalse(result.get("player_started"))
        self.assertTrue(result.get("attempted_play"))

    def test_hbo_returns_false_when_no_play_button(self):
        spec = _STREAMING_PLATFORMS["hbo_max"]
        click_starts = spec.get("playback", {}).get("click_card_starts_playback", False)
        self.assertFalse(click_starts)
        result = self._run_for_platform("hbo_max")
        self.assertIn(
            "detail_page_reached_no_explicit_play_button",
            result.get("steps", []),
        )
        self.assertFalse(result.get("player_started"))
        self.assertTrue(result.get("attempted_play"))

    def test_netflix_returns_false_when_no_play_button(self):
        # Netflix has click_card_starts_playback=False; same honest behavior.
        spec = _STREAMING_PLATFORMS["netflix"]
        click_starts = spec.get("playback", {}).get("click_card_starts_playback", False)
        self.assertFalse(click_starts)
        result = self._run_for_platform("netflix")
        self.assertIn(
            "detail_page_reached_no_explicit_play_button",
            result.get("steps", []),
        )
        self.assertFalse(result.get("player_started"))
        self.assertTrue(result.get("attempted_play"))

    def test_prime_returns_true_via_card_click_shortcircuit(self):
        # Prime is the ONLY platform with click_card_starts_playback=True, so
        # the function returns at step 6 (BEFORE attempting play_button).
        # player_started=True is the honest answer per spec.
        spec = _STREAMING_PLATFORMS["prime_video"]
        self.assertTrue(spec.get("playback", {}).get("click_card_starts_playback", False))
        result = self._run_for_platform("prime_video")
        self.assertTrue(result.get("player_started"))
        self.assertTrue(result.get("attempted_play"))


if __name__ == "__main__":
    unittest.main()
