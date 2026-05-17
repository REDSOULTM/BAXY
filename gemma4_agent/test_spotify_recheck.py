"""Tests for F-010: Spotify auto-play must re-check the active window
immediately before pressing Enter, to avoid sending the keypress to a
different app if the user switched windows in the ~300ms gap.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestSpotifyAutoPlayRecheck(unittest.TestCase):
    """Race window: first 'active' check returns Spotify, but the user
    clicks another window before the keypress fires. The recheck must
    catch that and abort.
    """

    def setUp(self):
        self._sleep = patch("time.sleep")
        self._sleep.start()

    def tearDown(self):
        self._sleep.stop()

    def test_recheck_aborts_when_window_changes(self):
        from .domain_tools import _spotify_auto_play
        call_count = {"active": 0}

        def _exec(name, args):
            if name == "window" and args.get("action") == "focus":
                return {"ok": True}
            if name == "window" and args.get("action") == "active":
                call_count["active"] += 1
                if call_count["active"] == 1:
                    return {"ok": True, "active": {"title": "Spotify Premium"}}
                # 2nd call (recheck) — user switched to VS Code
                return {"ok": True, "active": {"title": "agent.py - VS Code"}}
            if name == "gui" and args.get("action") == "keypress":
                return {"ok": True}
            return {"ok": False}

        executor = MagicMock(side_effect=_exec)
        result = _spotify_auto_play(executor, wait_seconds=0.1)
        self.assertFalse(result["played"])
        self.assertIn("window changed before keypress",
                      result.get("abort_reason", ""))
        # Keypress must NOT have been called.
        kp_calls = [c for c in executor.call_args_list
                    if c.args[0] == "gui"
                    and c.args[1].get("action") == "keypress"]
        self.assertEqual(len(kp_calls), 0)

    def test_recheck_proceeds_when_window_still_spotify(self):
        from .domain_tools import _spotify_auto_play

        def _exec(name, args):
            if name == "window" and args.get("action") == "focus":
                return {"ok": True}
            if name == "window" and args.get("action") == "active":
                return {"ok": True, "active": {"title": "Spotify Premium"}}
            if name == "gui" and args.get("action") == "keypress":
                return {"ok": True}
            return {"ok": False}

        executor = MagicMock(side_effect=_exec)
        result = _spotify_auto_play(executor, wait_seconds=0.1)
        self.assertTrue(result["played"])
        # Recheck means TWO active calls now (vs one previously).
        active_calls = [c for c in executor.call_args_list
                        if c.args[0] == "window"
                        and c.args[1].get("action") == "active"]
        self.assertEqual(len(active_calls), 2)


if __name__ == "__main__":
    unittest.main()
