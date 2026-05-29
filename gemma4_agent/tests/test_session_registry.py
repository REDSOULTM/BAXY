"""Tests for F-013: encapsulating Playwright + browser sessions in a
registry singleton so tests can reset state cleanly between runs.

The legacy globals `_BROWSER_SESSIONS` and `_PW` remain importable as
aliases for backwards compatibility.
"""
from __future__ import annotations

import unittest

from gemma4_agent.tools_pkg import ops_tools



class TestSessionRegistry(unittest.TestCase):

    def test_registry_exists(self):
        self.assertTrue(hasattr(ops_tools, "_SESSIONS"))
        reg = ops_tools._SESSIONS
        self.assertTrue(hasattr(reg, "sessions"))
        self.assertTrue(hasattr(reg, "pw"))
        self.assertTrue(callable(getattr(reg, "reset", None)))

    def test_sessions_alias_points_to_registry(self):
        # _BROWSER_SESSIONS must be the SAME dict object as the registry's.
        self.assertIs(ops_tools._BROWSER_SESSIONS, ops_tools._SESSIONS.sessions)

    def test_registry_reset_clears_sessions(self):
        reg = ops_tools._SESSIONS
        snapshot = dict(reg.sessions)
        try:
            reg.sessions["sid_test"] = {"browser": None, "context": None}
            self.assertIn("sid_test", reg.sessions)
            self.assertIn("sid_test", ops_tools._BROWSER_SESSIONS)
            reg.reset()
            self.assertEqual(len(reg.sessions), 0)
            self.assertIsNone(reg.pw)
        finally:
            reg.sessions.clear()
            reg.sessions.update(snapshot)

    def test_registry_starts_with_pw_none(self):
        # Fresh registry has no playwright handle yet (lazy init in _playwright()).
        reg = ops_tools._SessionRegistry()
        self.assertIsNone(reg.pw)
        self.assertEqual(reg.sessions, {})

    def test_legacy_globals_still_importable(self):
        # backwards-compat: these names must remain importable.
        from gemma4_agent.tools_pkg.ops_tools import _BROWSER_SESSIONS, _PW  # noqa: F401
        self.assertIsInstance(_BROWSER_SESSIONS, dict)


if __name__ == "__main__":
    unittest.main()
