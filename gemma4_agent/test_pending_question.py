"""pending_question slot for multi-turn slot-filling.

Hotfix I 2026-05-17. Triggered when a tool result has
clarification_needed or partial_reason — structural signal.
Separate from pending_intent because the semantics differ
(ran-but-partial vs about-to-run).
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class PendingQuestionStateTest(unittest.TestCase):
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

    def test_set_get_clear_pending_question(self) -> None:
        self.state.set_pending_question(
            tool="email",
            question_topic="which_account",
            last_args={"action": "send"},
            current_turn=1,
        )
        pq = self.state.get_pending_question(current_turn=2)
        self.assertIsNotNone(pq)
        self.assertEqual(pq["tool"], "email")
        self.assertEqual(pq["question_topic"], "which_account")
        self.assertEqual(pq["last_args"]["action"], "send")
        self.state.clear_pending_question()
        self.assertIsNone(self.state.get_pending_question(current_turn=2))

    def test_pending_question_expires_faster(self) -> None:
        # ttl=2 by default — should expire by turn 10.
        self.state.set_pending_question(
            tool="email", question_topic="x", last_args={},
            current_turn=1,
        )
        # Still valid at turn 3 (delta=2 ≤ ttl=2).
        self.assertIsNotNone(self.state.get_pending_question(current_turn=3))
        # Expired by turn 10.
        self.assertIsNone(self.state.get_pending_question(current_turn=10))

    def test_get_returns_none_when_unset(self) -> None:
        self.assertIsNone(self.state.get_pending_question(current_turn=1))

    def test_clear_is_idempotent(self) -> None:
        self.state.clear_pending_question()
        self.state.clear_pending_question()

    def test_persists_across_state_instances(self) -> None:
        from gemma4_agent.state import AgentState
        self.state.set_pending_question(
            tool="whatsapp",
            question_topic="recipient_phone",
            last_args={"action": "send_message"},
            current_turn=5,
        )
        fresh = AgentState(self.tmp_path)
        pq = fresh.get_pending_question(current_turn=6)
        self.assertIsNotNone(pq)
        self.assertEqual(pq["tool"], "whatsapp")
        self.assertEqual(pq["question_topic"], "recipient_phone")

    def test_pending_question_independent_from_pending_intent(self) -> None:
        # The two slots must not stomp each other.
        self.state.set_pending_intent(
            tool="steam", args={"action": "install"},
            asks_for="ownership_confirmation", current_turn=1,
        )
        self.state.set_pending_question(
            tool="email", question_topic="account",
            last_args={}, current_turn=1,
        )
        pi = self.state.get_pending_intent(current_turn=2)
        pq = self.state.get_pending_question(current_turn=2)
        self.assertIsNotNone(pi)
        self.assertIsNotNone(pq)
        self.assertEqual(pi["tool"], "steam")
        self.assertEqual(pq["tool"], "email")
        # Clearing one must not clear the other.
        self.state.clear_pending_intent()
        self.assertIsNone(self.state.get_pending_intent(current_turn=2))
        self.assertIsNotNone(self.state.get_pending_question(current_turn=2))


if __name__ == "__main__":
    unittest.main()
