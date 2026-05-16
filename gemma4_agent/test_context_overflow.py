"""Tests for the context-overflow detector and history compaction.

Background: on 2026-05-12 four turns hit llama-server with prompts >16k tokens
(`exceed_context_size_error`). Commit eec95c5 added `_looks_like_context_overflow`
+ `_compact_active_history_for_retry` so the agent can retry once with a smaller
subset + shorter history. These tests pin that detection wording and prove the
compaction actually shrinks `self.history`.
"""
from __future__ import annotations

import unittest

from .agent import _looks_like_context_overflow


class TestLooksLikeContextOverflow(unittest.TestCase):

    def test_real_llama_server_message_matches(self):
        # Exact wording seen 4x in traces.jsonl on 2026-05-12.
        msg = (
            "llm_http_error 400: {\"error\":{\"code\":400,"
            "\"message\":\"request (16489 tokens) exceeds the available "
            "context size (16384 tokens), try increasing it\","
            "\"type\":\"exceed_context_size_error\","
            "\"n_prompt_tokens\":16489,\"n_ctx\":16384}}"
        )
        self.assertTrue(_looks_like_context_overflow(msg))

    def test_error_type_alone_matches(self):
        # If only the JSON error.type is surfaced (alt llama-server builds).
        self.assertTrue(_looks_like_context_overflow("exceed_context_size_error"))

    def test_case_insensitive(self):
        self.assertTrue(
            _looks_like_context_overflow("EXCEEDS THE AVAILABLE CONTEXT SIZE (16384)")
        )

    def test_generic_pairing_matches(self):
        # Future llama-server builds may rephrase the message; pair detector.
        self.assertTrue(
            _looks_like_context_overflow("prompt exceeded the model's context size")
        )

    def test_unrelated_error_does_not_match(self):
        self.assertFalse(_looks_like_context_overflow("llm_timeout: 60s"))
        self.assertFalse(
            _looks_like_context_overflow("invalid tool arguments: unknown field")
        )
        # Important: a generic "size limit" message should NOT trigger overflow
        # recovery (could mask other bugs).
        self.assertFalse(_looks_like_context_overflow("output size limit reached"))

    def test_empty_string(self):
        self.assertFalse(_looks_like_context_overflow(""))


class _StubAgentForCompaction:
    """Minimal duck-typed stand-in for Agent used by the compaction helper."""

    def __init__(self, history: list[dict], context_size: int = 16384):
        self.history = list(history)
        # Only the attribute the helper reads.
        class _Cfg:
            pass
        self.config = _Cfg()
        self.config.context_size = context_size


class TestCompactActiveHistoryForRetry(unittest.TestCase):

    def test_shrinks_long_history_and_drops_leading_tool_messages(self):
        # Build a 50-message history with alternating roles + one long tool result.
        history: list[dict] = []
        for i in range(20):
            history.append({"role": "user", "content": f"user message {i}"})
            history.append({"role": "assistant", "content": "ok " * 200})
            history.append({
                "role": "tool",
                "tool_call_id": f"call_{i}",
                "content": "X" * 5000,
            })
        stub = _StubAgentForCompaction(history)

        # Run the bound method against the stub. Importing the unbound function
        # via the class avoids needing a real Agent instance.
        from .agent import Gemma4Agent
        Gemma4Agent._compact_active_history_for_retry(stub)  # type: ignore[arg-type]

        # 1) Result is strictly shorter than the input.
        self.assertLess(len(stub.history), len(history))
        # 2) No leading tool message (would orphan from a missing assistant call).
        if stub.history:
            self.assertNotEqual(stub.history[0].get("role"), "tool")
        # 3) Long tool contents have been ellipsized (no raw 5000-char content
        #    survives untouched).
        for msg in stub.history:
            if msg.get("role") == "tool":
                self.assertLess(len(msg.get("content") or ""), 5000)

    def test_empty_history_is_safe(self):
        stub = _StubAgentForCompaction([])
        from .agent import Gemma4Agent
        Gemma4Agent._compact_active_history_for_retry(stub)  # type: ignore[arg-type]
        self.assertEqual(stub.history, [])


if __name__ == "__main__":
    unittest.main()
