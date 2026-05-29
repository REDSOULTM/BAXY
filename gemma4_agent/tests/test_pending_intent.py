"""Cross-turn pending intent rescue (hotfix F 2026-05-17).

The intent is set when a tool result returns status='needs_user'
(structural signal), and consumed by the next turn's router as a
tool hint. NO user text matching is involved.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class AgentStatePendingIntentTest(unittest.TestCase):
    def setUp(self) -> None:
        from gemma4_agent.memory_pkg.state import AgentState
        fd, name = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        self.tmp_path = Path(name)
        self.tmp_path.write_text("{}", encoding="utf-8")
        self.state = AgentState(self.tmp_path)

    def tearDown(self) -> None:
        try:
            self.tmp_path.unlink()
        except Exception:
            pass

    def test_set_get_clear(self) -> None:
        self.state.set_pending_intent(
            tool="steam",
            args={"action": "install", "query": "Doom Eternal"},
            asks_for="ownership_confirmation",
            current_turn=1,
        )
        pi = self.state.get_pending_intent(current_turn=2)
        self.assertIsNotNone(pi)
        self.assertEqual(pi["tool"], "steam")
        self.assertEqual(pi["asks_for"], "ownership_confirmation")
        self.assertEqual(pi["args"]["query"], "Doom Eternal")
        self.state.clear_pending_intent()
        self.assertIsNone(self.state.get_pending_intent(current_turn=2))

    def test_expires_after_ttl(self) -> None:
        self.state.set_pending_intent(
            tool="steam", args={}, asks_for="x",
            current_turn=1, ttl_turns=3,
        )
        self.assertIsNone(self.state.get_pending_intent(current_turn=10))

    def test_get_returns_none_when_unset(self) -> None:
        self.assertIsNone(self.state.get_pending_intent(current_turn=1))

    def test_clear_is_idempotent(self) -> None:
        # Calling clear on an empty slot should not raise.
        self.state.clear_pending_intent()
        self.state.clear_pending_intent()

    def test_persists_across_state_instances(self) -> None:
        from gemma4_agent.memory_pkg.state import AgentState
        self.state.set_pending_intent(
            tool="whatsapp", args={"action": "send_message"},
            asks_for="message_body", current_turn=5,
        )
        fresh = AgentState(self.tmp_path)
        pi = fresh.get_pending_intent(current_turn=6)
        self.assertIsNotNone(pi)
        self.assertEqual(pi["tool"], "whatsapp")


# NOTE: the RouterV2PendingHintTest class was removed 2026-05-21 with router_v2
# itself. The pending-intent hint behaviour it covered is now handled by the
# planner (see PlannerPendingIntentInjectionTest below) and the abstain gate's
# pending_intent escape.


class PlannerPendingIntentInjectionTest(unittest.TestCase):
    """The v1 planner must inject the parked tool even when THIS reply is
    smalltalk-shaped (empty keyword/semantic match). 2026-05-20 bug: media
    asked for the Disney profile, the user replied "Mi perfil es Ema" (no
    keyword → names empty), and the early-return dropped the pending intent
    BEFORE injection → infinite "need disney profile" loop."""

    def _has(self, q: str, tool: str, pi: dict | None) -> bool:
        from gemma4_agent.routing.planner import select_tool_names, plan_mission
        return tool in set(select_tool_names(
            q, plan_mission(q), safety_enabled=True, pending_intent=pi))

    def test_smalltalk_reply_keeps_pending_media(self):
        pi = {"tool": "media", "args": {"action": "play", "provider": "disney"},
              "asks_for": "profile"}
        for q in ["Mi perfil es Ema", "mi perfil es Emmanuel", "Ema"]:
            # Without the pending intent these route to nothing useful...
            self.assertFalse(self._has(q, "media", None), q)
            # ...but WITH it parked, media must be injected so the reply
            # reaches the tool that asked.
            self.assertTrue(self._has(q, "media", pi), q)

    def test_no_pending_means_no_injection(self):
        # Sanity: a bare reply with no parked intent stays tool-free.
        self.assertFalse(self._has("Mi perfil es Ema", "media", None))


if __name__ == "__main__":
    unittest.main()
