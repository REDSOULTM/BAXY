"""The mission-outcome footer is post-reply ENRICHMENT (cosmetic metadata).
A bug in compute_mission_outcome / mission_footer / build_tool_records — or in
MissionGoal.from_user_text — must NEVER destroy a reply the LLM already produced.
These tests force those to raise and assert the reply still comes back.

LLMClient is mocked end-to-end; no llama-server, no ML models."""
from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gemma4_agent.agent_core.agent import AgentReply, Gemma4Agent
from gemma4_agent.infra.config import AgentConfig


def _make_agent(tmpdir: Path) -> Gemma4Agent:
    base = AgentConfig.from_env()
    cfg = dataclasses.replace(
        base,
        memory_path=tmpdir / "memory.json",
        captures_dir=tmpdir / "captures",
        trace_path=tmpdir / "traces.jsonl",
        state_path=tmpdir / "state.json",
        enable_tracing=False,
        enable_safety=False,
    )
    agent = Gemma4Agent(cfg)
    agent.client.chat = MagicMock(return_value={
        "choices": [{
            "message": {"role": "assistant", "content": "ok", "tool_calls": []},
            "finish_reason": "stop",
        }],
    })
    return agent


class TestMissionFooterResilience(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_mission_resil_"))
        self.agent = _make_agent(self.tmp)

    def test_reply_survives_compute_mission_outcome_raising(self):
        with patch("gemma4_agent.mission_outcome.compute_mission_outcome",
                   side_effect=RuntimeError("boom")):
            reply = self.agent.run_text("hola")
        self.assertIsInstance(reply, AgentReply)
        self.assertIn("ok", reply.content,
                      "the LLM reply must survive a footer-computation crash")

    def test_reply_survives_mission_footer_raising(self):
        with patch("gemma4_agent.mission_outcome.mission_footer",
                   side_effect=RuntimeError("boom")):
            reply = self.agent.run_text("abre Steam")
        self.assertIsInstance(reply, AgentReply)
        self.assertIn("ok", reply.content)

    def test_reply_survives_from_user_text_raising(self):
        with patch("gemma4_agent.mission_goal.MissionGoal.from_user_text",
                   side_effect=RuntimeError("boom")):
            reply = self.agent.run_text("hola")
        self.assertIsInstance(reply, AgentReply)
        self.assertIn("ok", reply.content,
                      "a crash BEFORE the LLM call must not kill the turn")


if __name__ == "__main__":
    unittest.main()
