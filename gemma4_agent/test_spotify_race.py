"""Regression tests for the Spotify already-open race condition.

Discovered 2026-05-17: when Spotify was already open showing the player,
`auto_play_wait=1.8s` was too short — Enter fired before search results
rendered, playing whatever was in the queue. Fix bumps the wait to >=3.5s
when a Spotify window is detected pre-deeplink, and verifies the
now-playing title against the query post-keypress.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from gemma4_agent.domain_tools import (
    _detect_spotify_already_running,
    _spotify_auto_play,
    media_tool,
)


class DetectSpotifyOpenTest(unittest.TestCase):
    def test_returns_true_when_window_list_contains_spotify(self) -> None:
        executor = MagicMock(return_value={"windows": [
            {"title": "Spotify - Free"},
            {"title": "Notepad"},
        ]})
        self.assertTrue(_detect_spotify_already_running(executor))

    def test_returns_true_with_items_key(self) -> None:
        executor = MagicMock(return_value={"items": [
            {"title": "Spotify Premium"},
        ]})
        self.assertTrue(_detect_spotify_already_running(executor))

    def test_returns_true_for_plain_string_items(self) -> None:
        executor = MagicMock(return_value={"windows": ["Spotify", "Chrome"]})
        self.assertTrue(_detect_spotify_already_running(executor))

    def test_returns_false_when_no_spotify_window(self) -> None:
        executor = MagicMock(return_value={"windows": [{"title": "Notepad"}]})
        self.assertFalse(_detect_spotify_already_running(executor))

    def test_returns_false_when_executor_raises(self) -> None:
        executor = MagicMock(side_effect=RuntimeError("test"))
        self.assertFalse(_detect_spotify_already_running(executor))

    def test_returns_false_when_windows_key_missing(self) -> None:
        executor = MagicMock(return_value={})
        self.assertFalse(_detect_spotify_already_running(executor))

    def test_returns_false_when_response_not_dict(self) -> None:
        executor = MagicMock(return_value="not a dict")
        self.assertFalse(_detect_spotify_already_running(executor))

    def test_case_insensitive_match(self) -> None:
        executor = MagicMock(return_value={"windows": [
            {"title": "SPOTIFY - Now Playing"},
        ]})
        self.assertTrue(_detect_spotify_already_running(executor))


class SpotifyPostPlayTitleVerifyTest(unittest.TestCase):
    """post-keypress, the auto_play helper should compare the now-playing
    title against the query and set query_match accordingly.
    """

    def _make_executor(self, now_playing_title: str):
        def _exec(name, args):
            if name == "window" and args.get("action") == "focus":
                return {"ok": True}
            if name == "window" and args.get("action") == "active":
                return {"ok": True, "active": {"title": now_playing_title}}
            if name == "gui" and args.get("action") == "keypress":
                return {"ok": True}
            return {"ok": True}
        return MagicMock(side_effect=_exec)

    def test_query_match_true_when_title_contains_query_word(self) -> None:
        # Spotify after playing MJ: title like "Billie Jean • Michael Jackson"
        executor = self._make_executor("Spotify - Billie Jean • Michael Jackson")
        with patch("time.sleep"):
            result = _spotify_auto_play(executor, 1.8, query="Michael Jackson")
        self.assertTrue(result["played"])
        self.assertTrue(result["query_match"])

    def test_query_match_false_when_title_unrelated(self) -> None:
        # Bug scenario: user asked MJ, Spotify played whatever was queued.
        executor = self._make_executor("Spotify - Some Random Track • Random Artist")
        with patch("time.sleep"):
            result = _spotify_auto_play(executor, 1.8, query="Michael Jackson")
        self.assertTrue(result["played"])
        self.assertFalse(result["query_match"])

    def test_query_match_none_when_no_query_passed(self) -> None:
        executor = self._make_executor("Spotify")
        with patch("time.sleep"):
            result = _spotify_auto_play(executor, 1.8, query=None)
        self.assertTrue(result["played"])
        self.assertIsNone(result["query_match"])

    def test_query_match_none_when_query_has_no_long_words(self) -> None:
        # All query words <4 chars -> heuristica no aplica, retorna None.
        executor = self._make_executor("Spotify - Hi Song")
        with patch("time.sleep"):
            result = _spotify_auto_play(executor, 1.8, query="hi ok")
        self.assertTrue(result["played"])
        self.assertIsNone(result["query_match"])


class SpotifyAutoPlayWaitBumpTest(unittest.TestCase):
    """When Spotify is already open, the wait passed to _spotify_auto_play
    MUST be >= 3.5s (regression for the 2026-05-17 warm-cache race).
    """

    @patch("gemma4_agent.domain_tools.subprocess.Popen")
    @patch("gemma4_agent.domain_tools._spotify_auto_play")
    @patch("gemma4_agent.domain_tools._detect_spotify_already_running")
    @patch("gemma4_agent.domain_tools._find_streaming_app")
    def test_wait_bumped_when_spotify_already_open(
        self, mock_find_app, mock_detect, mock_autoplay, mock_popen,
    ):
        mock_find_app.return_value = {"kind": "exe",
                                       "launch_target": r"C:\Spotify.exe"}
        mock_detect.return_value = True
        mock_autoplay.return_value = {
            "played": True, "focus_verified": True,
            "abort_reason": None, "wait_seconds": 3.5,
            "query_match": True,
        }
        executor = MagicMock()
        result = media_tool(
            {"action": "play", "provider": "spotify",
             "query": "Michael Jackson",
             "auto_play": True, "auto_play_wait": 1.8},
            executor,
        )
        self.assertTrue(result.get("ok"), f"expected ok=True, got {result}")
        # _spotify_auto_play must have been called with wait >= 3.5
        args, kwargs = mock_autoplay.call_args
        wait_arg = args[1] if len(args) >= 2 else kwargs.get("wait_seconds")
        self.assertGreaterEqual(
            wait_arg, 3.5,
            f"wait should be bumped to >=3.5s when Spotify is open, got {wait_arg}",
        )

    @patch("gemma4_agent.domain_tools.subprocess.Popen")
    @patch("gemma4_agent.domain_tools._spotify_auto_play")
    @patch("gemma4_agent.domain_tools._detect_spotify_already_running")
    @patch("gemma4_agent.domain_tools._find_streaming_app")
    def test_wait_not_bumped_when_spotify_closed(
        self, mock_find_app, mock_detect, mock_autoplay, mock_popen,
    ):
        mock_find_app.return_value = {"kind": "exe",
                                       "launch_target": r"C:\Spotify.exe"}
        mock_detect.return_value = False
        mock_autoplay.return_value = {
            "played": True, "focus_verified": True,
            "abort_reason": None, "wait_seconds": 1.8,
            "query_match": True,
        }
        executor = MagicMock()
        media_tool(
            {"action": "play", "provider": "spotify",
             "query": "Michael Jackson",
             "auto_play": True, "auto_play_wait": 1.8},
            executor,
        )
        args, kwargs = mock_autoplay.call_args
        wait_arg = args[1] if len(args) >= 2 else kwargs.get("wait_seconds")
        # Cold-launch keeps the default 1.8s.
        self.assertAlmostEqual(wait_arg, 1.8, places=2)


class SpotifyCompletionStatusTest(unittest.TestCase):
    """Wire-up: the new completion_status values must surface through
    _launch_streaming so the LLM sees them.
    """

    @patch("gemma4_agent.domain_tools.subprocess.Popen")
    @patch("gemma4_agent.domain_tools._spotify_auto_play")
    @patch("gemma4_agent.domain_tools._detect_spotify_already_running")
    @patch("gemma4_agent.domain_tools._find_streaming_app")
    def test_wrong_track_status_propagates(
        self, mock_find_app, mock_detect, mock_autoplay, mock_popen,
    ):
        mock_find_app.return_value = {"kind": "exe",
                                       "launch_target": r"C:\Spotify.exe"}
        mock_detect.return_value = True
        mock_autoplay.return_value = {
            "played": True, "focus_verified": True,
            "abort_reason": None, "wait_seconds": 3.5,
            "query_match": False,  # <- mismatch detected
        }
        executor = MagicMock()
        result = media_tool(
            {"action": "play", "provider": "spotify",
             "query": "Michael Jackson",
             "auto_play": True, "auto_play_wait": 1.8},
            executor,
        )
        self.assertEqual(result.get("completion_status"), "media_playing_wrong_track")
        # verified=False when query_match=False (even though played=True).
        self.assertFalse(result.get("verified"))
        self.assertIs(result.get("query_match"), False)

    @patch("gemma4_agent.domain_tools.subprocess.Popen")
    @patch("gemma4_agent.domain_tools._spotify_auto_play")
    @patch("gemma4_agent.domain_tools._detect_spotify_already_running")
    @patch("gemma4_agent.domain_tools._find_streaming_app")
    def test_match_status_propagates(
        self, mock_find_app, mock_detect, mock_autoplay, mock_popen,
    ):
        mock_find_app.return_value = {"kind": "exe",
                                       "launch_target": r"C:\Spotify.exe"}
        mock_detect.return_value = False
        mock_autoplay.return_value = {
            "played": True, "focus_verified": True,
            "abort_reason": None, "wait_seconds": 1.8,
            "query_match": True,
        }
        executor = MagicMock()
        result = media_tool(
            {"action": "play", "provider": "spotify",
             "query": "Michael Jackson",
             "auto_play": True, "auto_play_wait": 1.8},
            executor,
        )
        self.assertEqual(result.get("completion_status"), "media_playing_match")
        self.assertTrue(result.get("verified"))


if __name__ == "__main__":
    unittest.main()
