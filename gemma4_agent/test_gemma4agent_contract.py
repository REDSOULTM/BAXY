"""Contract tests for Gemma4Agent's public API.

The 4 user-facing surfaces (CLI chat, UI Desktop, UI Field server, MCP)
all consume the same Gemma4Agent surface. Sprint 5b is going to split
the 1 852-LOC run_content; these tests pin the contract:

  - Constructor state shape
  - clear() reset behaviour
  - set_persona / get_persona
  - run_text (smoke + tool-call flow), mocking the LLMClient so no
    llama-server is needed
  - _compute_context_budget shape
  - guard spy (post-reply hooks fire)

All LLM calls are mocked. No llama-server, no ML model loading.
"""
from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from .agent import AgentReply, Gemma4Agent, _compute_context_budget
from .config import AgentConfig


def _make_config(tmpdir: Path) -> AgentConfig:
    """Build an AgentConfig that won't touch the real ~/.gemma4 tree."""
    base = AgentConfig.from_env()
    return dataclasses.replace(
        base,
        memory_path=tmpdir / "memory.json",
        captures_dir=tmpdir / "captures",
        trace_path=tmpdir / "traces.jsonl",
        state_path=tmpdir / "state.json",
        enable_tracing=False,  # don't write trace files in the tmpdir
        enable_safety=False,
    )


def _make_agent(tmpdir: Path) -> Gemma4Agent:
    return Gemma4Agent(_make_config(tmpdir))


class TestConstructor(unittest.TestCase):
    """The 4 surfaces all reach into these attributes; the names must stay."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_agent_init_"))
        self.agent = _make_agent(self.tmp)

    def test_core_attributes_exist(self) -> None:
        for attr in ("memory", "state", "client", "tools", "experience",
                     "trace", "history", "_persona"):
            self.assertTrue(hasattr(self.agent, attr),
                            f"Gemma4Agent must expose self.{attr}")

    def test_history_starts_empty(self) -> None:
        self.assertEqual(self.agent.history, [])

    def test_tools_has_parent_agent_backref(self) -> None:
        self.assertIs(self.agent.tools.parent_agent, self.agent)

    def test_default_persona_is_default(self) -> None:
        self.assertEqual(self.agent._persona.name, "default")


class TestClear(unittest.TestCase):
    """clear() must reset every per-session field."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_agent_clear_"))
        self.agent = _make_agent(self.tmp)

    def test_clear_resets_history(self) -> None:
        self.agent.history.append({"role": "user", "content": "hola"})
        self.agent.clear()
        self.assertEqual(self.agent.history, [])

    def test_clear_resets_turn_counter(self) -> None:
        self.agent._turn_counter = 7
        self.agent.clear()
        self.assertEqual(self.agent._turn_counter, 0)

    def test_clear_resets_recent_recalls(self) -> None:
        self.agent._recent_recalls = [{"id": 1}]
        self.agent.clear()
        self.assertEqual(self.agent._recent_recalls, [])

    def test_clear_resets_cached_microagents(self) -> None:
        self.agent._cached_microagents = [object(), object()]
        self.agent.clear()
        self.assertEqual(self.agent._cached_microagents, [])

    def test_clear_resets_skills_cache_to_none(self) -> None:
        self.agent._cached_skills_menu = "stale"
        self.agent._cached_skills_critical = "stale"
        self.agent.clear()
        self.assertIsNone(self.agent._cached_skills_menu)
        self.assertIsNone(self.agent._cached_skills_critical)

    def test_clear_resets_last_turn_ts(self) -> None:
        self.agent._last_turn_ts = 1234.5
        self.agent.clear()
        self.assertIsNone(self.agent._last_turn_ts)


class TestPersona(unittest.TestCase):
    """set_persona / get_persona contract used by /agent/persona endpoint
    and the SettingsDialog. Sprint 5b must preserve this exact shape."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_agent_persona_"))
        self.agent = _make_agent(self.tmp)

    def test_get_persona_default_shape(self) -> None:
        info = self.agent.get_persona()
        self.assertEqual(info["persona"], "default")
        self.assertIn("description", info)
        self.assertIn("preferred_tools", info)
        self.assertIn("tone", info)
        self.assertIsInstance(info["preferred_tools"], list)

    def test_set_persona_to_coder_changes_state(self) -> None:
        result = self.agent.set_persona("coder")
        self.assertTrue(result["ok"])
        self.assertEqual(result["persona"], "coder")
        self.assertEqual(self.agent.get_persona()["persona"], "coder")

    def test_set_persona_rejects_unknown_name(self) -> None:
        result = self.agent.set_persona("nonexistent_xyz")
        self.assertFalse(result["ok"])
        self.assertIn("error", result)
        self.assertIn("available", result)
        # Persona is unchanged on rejection.
        self.assertEqual(self.agent.get_persona()["persona"], "default")


class TestRunTextSmoke(unittest.TestCase):
    """run_text returns AgentReply with the documented attributes. LLMClient
    is mocked end-to-end; the agent never tries to talk to llama-server."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_agent_run_"))
        self.agent = _make_agent(self.tmp)
        # Replace the chat method with a deterministic stub that returns a
        # tool-less reply, ending the turn after one LLM call.
        self.agent.client.chat = MagicMock(return_value={
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "ok",
                    "tool_calls": [],
                },
                "finish_reason": "stop",
            }],
        })

    def test_run_text_returns_AgentReply(self) -> None:
        reply = self.agent.run_text("hola")
        self.assertIsInstance(reply, AgentReply)

    def test_reply_has_expected_attributes(self) -> None:
        reply = self.agent.run_text("hola")
        # field names the 4 surfaces and the trace consume.
        self.assertTrue(hasattr(reply, "content"))
        self.assertTrue(hasattr(reply, "tool_events"))
        self.assertTrue(hasattr(reply, "error"))
        self.assertTrue(hasattr(reply, "mission"))

    def test_reply_content_propagates_from_llm(self) -> None:
        reply = self.agent.run_text("hola")
        self.assertEqual(reply.content, "ok")
        self.assertEqual(reply.tool_events, [])
        self.assertIsNone(reply.error)

    def test_history_grows_after_turn(self) -> None:
        self.agent.run_text("hola")
        # at minimum the user + assistant pair should be in history
        self.assertGreaterEqual(len(self.agent.history), 2)

    def test_turn_counter_increments(self) -> None:
        self.assertEqual(self.agent._turn_counter, 0)
        self.agent.run_text("hola")
        self.assertEqual(self.agent._turn_counter, 1)
        self.agent.run_text("y de nuevo")
        self.assertEqual(self.agent._turn_counter, 2)


class TestRunTextToolCallFlow(unittest.TestCase):
    """A more involved flow: the LLM emits a tool_call, the registry runs,
    then the LLM emits a natural reply. Both LLM calls are mocked."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_agent_toolflow_"))
        self.agent = _make_agent(self.tmp)
        # Sequence of LLM responses: first the assistant emits a tool_call,
        # then it produces the final natural-language reply.
        first = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "system",
                            "arguments": '{"action":"time"}',
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }
        second = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Listo, son las 12:00.",
                    "tool_calls": [],
                },
                "finish_reason": "stop",
            }],
        }
        self.agent.client.chat = MagicMock(side_effect=[first, second])
        # Mock the tool dispatch so no real handler runs.
        self.agent.tools.execute = MagicMock(return_value={  # type: ignore[method-assign]
            "ok": True,
            "status": "ok",
            "verified": True,
            "tool": "system",
            "now": "12:00",
        })

    def test_tool_event_recorded_in_reply(self) -> None:
        reply = self.agent.run_text("que hora es")
        self.assertEqual(len(reply.tool_events), 1)
        self.assertEqual(reply.tool_events[0].name, "system")

    def test_history_keeps_user_and_assistant_after_compaction(self) -> None:
        # Note: role="tool" rows ARE appended during the turn (agent.py:1677)
        # but _compact_completed_history() strips them as a "cheap pass"
        # before the turn returns. So the post-turn history shape is the
        # compacted view: user + assistant only. Both must be present.
        self.agent.run_text("que hora es")
        roles = [m.get("role") for m in self.agent.history]
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)

    def test_two_chat_calls_used(self) -> None:
        self.agent.run_text("que hora es")
        # one for the tool_call dispatch, one for the natural reply
        self.assertEqual(self.agent.client.chat.call_count, 2)


class TestGuardsSpy(unittest.TestCase):
    """The 6 _guard_* methods must still fire after Sprint 5b's split. We
    don't test what they do (that's the job of test_promise_guard etc.);
    we just spy that the agent invokes them post-reply."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_agent_guards_"))
        self.agent = _make_agent(self.tmp)
        self.agent.client.chat = MagicMock(return_value={
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "ok",
                    "tool_calls": [],
                },
                "finish_reason": "stop",
            }],
        })

    def test_promise_guard_is_invoked_at_least_once(self) -> None:
        with patch.object(
            self.agent, "_guard_promise_without_action",
            wraps=self.agent._guard_promise_without_action,
        ) as spy:
            self.agent.run_text("hola")
            self.assertGreaterEqual(spy.call_count, 1,
                                    "agent must invoke _guard_promise_without_action post-reply")


class TestContextBudget(unittest.TestCase):
    """_compute_context_budget shape is consumed by both the compaction
    code and any UI that displays "X / Y tokens left". The dict keys are
    part of the contract."""

    def test_dict_keys_present(self) -> None:
        out = _compute_context_budget(context_size=4096)
        for key in ("context_size", "history_tokens", "history_chars",
                    "soft_cap_messages", "hard_cap_messages",
                    "keep_tail_messages", "summarize_threshold_chars"):
            self.assertIn(key, out)

    def test_values_scale_with_context_size(self) -> None:
        small = _compute_context_budget(context_size=2048)
        large = _compute_context_budget(context_size=32768)
        self.assertGreater(large["history_tokens"], small["history_tokens"])
        self.assertGreater(large["history_chars"], small["history_chars"])

    def test_floor_at_1024_for_undersized_input(self) -> None:
        out = _compute_context_budget(context_size=256)
        self.assertGreaterEqual(out["context_size"], 1024)


if __name__ == "__main__":
    unittest.main()
