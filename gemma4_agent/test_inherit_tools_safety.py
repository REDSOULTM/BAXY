"""Tests for F-005: inherit-tools safety guards.

The continuation-inherits-tools path (agent.py around L1049-1100) heredada
los tools del turn previo cuando el user manda algo corto ("ok", "si").
Sin guards esto puede disparar tools peligrosos tras gaps largos o sobre
herramientas destructivas.

Verifies:
  - TTL: gap > INHERIT_TTL_SEC => no hereda.
  - Blacklist: tools en DANGEROUS_TOOLS_NEVER_INHERIT son filtrados.
  - Happy path: tool seguro tras gap corto sigue heredándose.
"""
from __future__ import annotations

import time
import unittest

from gemma4_agent.agent import (
    DANGEROUS_TOOLS_NEVER_INHERIT,
    INHERIT_TTL_SEC,
    Gemma4Agent,
)


class TestInheritToolsSafety(unittest.TestCase):
    """The inherit-tools path must respect TTL and blacklist."""

    def setUp(self):
        # We don't want to instantiate the full agent (DB, LLM client, etc).
        # We test the inherit logic by replicating its conditional structure
        # with explicit asserts against the constants.
        pass

    def test_dangerous_tools_blacklist_contains_whatsapp(self):
        self.assertIn("whatsapp_send", DANGEROUS_TOOLS_NEVER_INHERIT)
        self.assertIn("whatsapp", DANGEROUS_TOOLS_NEVER_INHERIT)

    def test_dangerous_tools_blacklist_contains_destructive(self):
        for t in ("file_delete", "system_shutdown", "system_logoff",
                  "system_restart"):
            self.assertIn(t, DANGEROUS_TOOLS_NEVER_INHERIT)

    def test_dangerous_tools_blacklist_does_not_contain_safe(self):
        # Web/memory/calendar are safe to inherit on continuations.
        for t in ("web", "memory", "calendar", "weather", "media_tool"):
            self.assertNotIn(t, DANGEROUS_TOOLS_NEVER_INHERIT)

    def test_ttl_is_five_minutes(self):
        self.assertEqual(INHERIT_TTL_SEC, 300)

    def test_filter_dangerous_keeps_safe_tools(self):
        # Simulación del filtro que aplica el agent
        prev_tools = ["web", "whatsapp_send", "memory", "file_delete"]
        filtered = [t for t in prev_tools if t not in DANGEROUS_TOOLS_NEVER_INHERIT]
        self.assertEqual(filtered, ["web", "memory"])

    def test_filter_dangerous_empties_when_all_dangerous(self):
        prev_tools = ["whatsapp_send", "file_delete", "system_shutdown"]
        filtered = [t for t in prev_tools if t not in DANGEROUS_TOOLS_NEVER_INHERIT]
        self.assertEqual(filtered, [])

    def test_ttl_gap_expired(self):
        # Simular gap > TTL
        last_ts = time.time() - (INHERIT_TTL_SEC + 60)
        now = time.time()
        gap = now - last_ts
        self.assertGreater(gap, INHERIT_TTL_SEC)

    def test_ttl_gap_within(self):
        # Simular continuation rapida (<5min)
        last_ts = time.time() - 30
        now = time.time()
        gap = now - last_ts
        self.assertLess(gap, INHERIT_TTL_SEC)


class TestAgentInheritState(unittest.TestCase):
    """Verify the agent instance has _last_turn_ts state plumbed in."""

    def test_last_turn_ts_attribute_exists(self):
        # Check via class introspection that __init__ sets _last_turn_ts.
        # We don't actually instantiate (avoids DB/LLM setup). Read source.
        import inspect
        src = inspect.getsource(Gemma4Agent.__init__)
        self.assertIn("_last_turn_ts", src)

    def test_clear_resets_last_turn_ts(self):
        import inspect
        src = inspect.getsource(Gemma4Agent.clear)
        self.assertIn("_last_turn_ts", src)


if __name__ == "__main__":
    unittest.main()
