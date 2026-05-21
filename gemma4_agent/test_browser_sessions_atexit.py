"""Tests for F-006: _BROWSER_SESSIONS must be cleaned up at process exit
to avoid lingering Chromium handles/sockets in long runs.
"""
from __future__ import annotations

import atexit
import unittest
from unittest.mock import MagicMock

from gemma4_agent import ops_tools


class TestBrowserSessionsAtexitCleanup(unittest.TestCase):

    def setUp(self):
        # Snapshot the dict so we can restore it.
        self._snapshot = dict(ops_tools._BROWSER_SESSIONS)
        ops_tools._BROWSER_SESSIONS.clear()

    def tearDown(self):
        ops_tools._BROWSER_SESSIONS.clear()
        ops_tools._BROWSER_SESSIONS.update(self._snapshot)

    def test_cleanup_function_exists(self):
        self.assertTrue(hasattr(ops_tools, "_cleanup_all_browser_sessions"))
        self.assertTrue(callable(ops_tools._cleanup_all_browser_sessions))

    def test_cleanup_clears_sessions(self):
        # Fake sessions with mocked browser/context that record .close() calls
        mock_browser_1 = MagicMock()
        mock_browser_2 = MagicMock()
        ops_tools._BROWSER_SESSIONS["sid1"] = {
            "browser": mock_browser_1,
            "context": MagicMock(),
            "pages": [],
            "active": 0,
        }
        ops_tools._BROWSER_SESSIONS["sid2"] = {
            "browser": mock_browser_2,
            "context": MagicMock(),
            "pages": [],
            "active": 0,
        }
        self.assertEqual(len(ops_tools._BROWSER_SESSIONS), 2)
        ops_tools._cleanup_all_browser_sessions()
        # Both popped.
        self.assertEqual(len(ops_tools._BROWSER_SESSIONS), 0)
        # Close was attempted on each browser.
        mock_browser_1.close.assert_called()
        mock_browser_2.close.assert_called()

    def test_cleanup_swallows_close_exceptions(self):
        # _close_browser_session already accumulates errors silently, but
        # if it raises (unexpected), _cleanup_all_browser_sessions should
        # NOT propagate.
        broken = MagicMock()
        broken.close.side_effect = RuntimeError("boom")
        ops_tools._BROWSER_SESSIONS["sidbroken"] = {
            "browser": broken,
            "context": MagicMock(),
            "pages": [],
            "active": 0,
        }
        # Must not raise.
        ops_tools._cleanup_all_browser_sessions()
        self.assertNotIn("sidbroken", ops_tools._BROWSER_SESSIONS)

    def test_cleanup_stops_playwright_handle(self):
        # The Playwright handle spawns a node.js driver subprocess; closing the
        # browser sessions does NOT stop it. Cleanup must call pw.stop() so the
        # driver isn't orphaned on shutdown.
        mock_pw = MagicMock()
        ops_tools._SESSIONS.pw = mock_pw
        try:
            ops_tools._cleanup_all_browser_sessions()
            mock_pw.stop.assert_called_once()
            self.assertIsNone(ops_tools._SESSIONS.pw,
                              "pw handle must be cleared after stop")
        finally:
            ops_tools._SESSIONS.pw = None

    def test_cleanup_swallows_pw_stop_exception(self):
        mock_pw = MagicMock()
        mock_pw.stop.side_effect = RuntimeError("driver already dead")
        ops_tools._SESSIONS.pw = mock_pw
        try:
            ops_tools._cleanup_all_browser_sessions()  # must not raise
            self.assertIsNone(ops_tools._SESSIONS.pw)
        finally:
            ops_tools._SESSIONS.pw = None

    def test_cleanup_no_pw_is_noop(self):
        # No Playwright handle started -> cleanup must not crash.
        ops_tools._SESSIONS.pw = None
        ops_tools._cleanup_all_browser_sessions()  # must not raise
        self.assertIsNone(ops_tools._SESSIONS.pw)

    def test_cleanup_handler_registered(self):
        # The cleanup function must be wired to atexit. We can't introspect
        # the registry directly across pythons, but we can verify the call
        # was made by checking atexit._exithandlers in CPython.
        # Fall back: check the function is at least defined in the module
        # source as `atexit.register(...)`.
        import inspect
        src = inspect.getsource(ops_tools)
        self.assertIn("atexit.register(_cleanup_all_browser_sessions)", src)


if __name__ == "__main__":
    unittest.main()
