"""Regression test for the ANTI-HALLUCINATION rule in core.md.

User session 2026-05-17 16:45-16:56 surfaced 4 bugs of the same
shape: the LLM answered a tool-answerable question from training
memory instead of calling the tool. The fix added an explicit
ANTI-HALLUCINATION block listing the most common tool-answerable
questions. This test pins the contract on the rule text.
"""
from __future__ import annotations

import unittest

from gemma4_agent.agent_core.agent_prompt import CORE_PROMPT


class CorePromptAntiHallucTest(unittest.TestCase):
    def test_has_anti_hallucination_section(self) -> None:
        self.assertIn("ANTI-HALLUCINATION", CORE_PROMPT)

    def test_mentions_system_time_routing(self) -> None:
        # "qué hora es" → system.time
        self.assertIn("system(action='time')", CORE_PROMPT)

    def test_mentions_system_disk_routing(self) -> None:
        self.assertIn("system(action='disk')", CORE_PROMPT)

    def test_forbids_invented_no_access_excuses(self) -> None:
        # The honest-fallback clause must be present.
        self.assertIn("DO NOT invent", CORE_PROMPT)


if __name__ == "__main__":
    unittest.main()
