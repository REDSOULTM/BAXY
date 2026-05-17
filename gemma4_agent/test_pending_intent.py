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
        from gemma4_agent.state import AgentState
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
        from gemma4_agent.state import AgentState
        self.state.set_pending_intent(
            tool="whatsapp", args={"action": "send_message"},
            asks_for="message_body", current_turn=5,
        )
        fresh = AgentState(self.tmp_path)
        pi = fresh.get_pending_intent(current_turn=6)
        self.assertIsNotNone(pi)
        self.assertEqual(pi["tool"], "whatsapp")


_MODEL_PATH = __import__(
    "gemma4_agent.router_v2", fromlist=["MODEL_PATH"],
).MODEL_PATH


@unittest.skipUnless(_MODEL_PATH.exists(), "e5-small ONNX model not installed")
class RouterV2PendingHintTest(unittest.TestCase):
    """When pending_tool_hint is passed, the router injects that
    tool into the subset regardless of retrieval scores."""

    @classmethod
    def setUpClass(cls) -> None:
        from gemma4_agent.router_v2 import RouterV2
        RouterV2.reset()
        cls.router = RouterV2.get()
        if not cls.router._ensure_loaded():
            raise unittest.SkipTest(cls.router._load_error)

    @classmethod
    def tearDownClass(cls) -> None:
        from gemma4_agent.router_v2 import RouterV2
        RouterV2.reset()

    def setUp(self) -> None:
        # Force fresh cache so prior tests don't pollute.
        from gemma4_agent.router_v2 import RouterV2
        RouterV2.reset()
        self.__class__.router = RouterV2.get()
        self.router._ensure_loaded()

    def test_hint_injected_on_smalltalk_reply(self) -> None:
        # 'sí' fires smalltalk; the hint should inject steam anyway.
        from gemma4_agent.router_v2 import route_v2
        subset, telemetry = route_v2("sí", pending_tool_hint="steam")
        self.assertIn("steam", subset)
        self.assertEqual(telemetry.get("pending_tool_injected"), "steam")

    def test_hint_injected_on_empty_query(self) -> None:
        from gemma4_agent.router_v2 import route_v2
        subset, telemetry = route_v2("", pending_tool_hint="steam")
        self.assertIn("steam", subset)
        self.assertEqual(telemetry.get("pending_tool_injected"), "steam")

    def test_hint_not_duplicated_when_already_present(self) -> None:
        from gemma4_agent.router_v2 import route_v2
        subset, _ = route_v2("abrime el steam", pending_tool_hint="steam")
        self.assertEqual(subset.count("steam"), 1)

    def test_hint_none_means_no_injection(self) -> None:
        from gemma4_agent.router_v2 import route_v2
        subset, telemetry = route_v2("hola", pending_tool_hint=None)
        self.assertNotIn("pending_tool_injected", telemetry)

    def test_multiple_language_confirmations_all_get_steam(self) -> None:
        from gemma4_agent.router_v2 import route_v2, RouterV2
        for q in ["sí", "yes", "oui", "ya lo tengo"]:
            RouterV2.reset()
            self.router = RouterV2.get()
            self.router._ensure_loaded()
            subset, _ = route_v2(q, pending_tool_hint="steam")
            self.assertIn("steam", subset,
                          f"{q!r}: steam missing despite hint")


if __name__ == "__main__":
    unittest.main()
