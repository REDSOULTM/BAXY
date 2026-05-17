"""Tests for F-008: system prompt callsites must be scoped.

The legacy `build_system_prompt(None)` returns the FULL prompt (~25K chars
/ ~6400 tokens). It's expensive to send each turn. Currently:

  - `build_system_prompt(None)` is called EXACTLY once at module import
    (agent.py:~590) to populate the `SYSTEM_PROMPT` module variable for
    display-only consumers (server /agent/system_prompt endpoint, UI
    settings panel).
  - All RUNTIME callsites must pass a `selected_tool_names` subset, so the
    LLM only receives rules for the tools it actually has access to.

These tests fail-fast if a future change re-introduces a runtime call
without subset, or imports the heavy legacy variable into runtime hot path.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path


AGENT_PY = Path(__file__).parent / "agent.py"
SERVER_PY = Path(__file__).parent / "server.py"


class TestSystemPromptScope(unittest.TestCase):

    def setUp(self):
        self.agent_src = AGENT_PY.read_text(encoding="utf-8")
        if SERVER_PY.exists():
            self.server_src = SERVER_PY.read_text(encoding="utf-8")
        else:
            self.server_src = ""

    def test_only_one_call_to_build_without_subset(self):
        # `build_system_prompt()` (no args) or `build_system_prompt(None)`
        # may appear at most once: the precompute of SYSTEM_PROMPT.
        # Other callsites must pass an explicit list.
        pattern = re.compile(r"build_system_prompt\s*\(\s*(?:None\s*)?\)")
        matches = pattern.findall(self.agent_src)
        self.assertLessEqual(
            len(matches), 1,
            f"Expected at most 1 call to build_system_prompt() without "
            f"subset; found {len(matches)}: {matches}",
        )

    def test_system_prompt_module_variable_exists(self):
        # The module-level SYSTEM_PROMPT must remain importable for
        # backwards-compat with server.py and UI.
        from gemma4_agent.agent import SYSTEM_PROMPT
        self.assertIsInstance(SYSTEM_PROMPT, str)
        self.assertGreater(len(SYSTEM_PROMPT), 1000)

    def test_runtime_path_uses_subset(self):
        # The agent's hot path (around line 726) must pass selected_tool_names.
        # We check the substring `build_system_prompt(selected_tool_names)` is
        # present.
        self.assertIn(
            "build_system_prompt(selected_tool_names)", self.agent_src,
            "Runtime callsite must pass selected_tool_names subset.",
        )

    def test_server_endpoint_uses_legacy_variable(self):
        if not self.server_src:
            self.skipTest("server.py not present in this checkout")
        # The server endpoint may import SYSTEM_PROMPT (the precomputed
        # variable) for display — that's fine. But it should NOT call
        # build_system_prompt(None) directly.
        pattern = re.compile(r"build_system_prompt\s*\(\s*(?:None\s*)?\)")
        matches = pattern.findall(self.server_src)
        self.assertEqual(
            len(matches), 0,
            f"server.py should not call build_system_prompt() directly; "
            f"use the precomputed SYSTEM_PROMPT variable. Found: {matches}",
        )


if __name__ == "__main__":
    unittest.main()
