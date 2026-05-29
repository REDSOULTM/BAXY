"""tool_call_skipped_when_expected emits when the subset had a
domain tool but no tool_call was made.

Hotfix I 2026-05-17. The _domain_subset helper is pure and lives
at module level for testability; the wiring is verified by source
grep.
"""
from __future__ import annotations

import inspect
import unittest

from gemma4_agent.agent_core.agent import _domain_subset


class DomainSubsetFilterTest(unittest.TestCase):
    def test_only_session_filters_to_empty(self) -> None:
        self.assertEqual(_domain_subset(["session"]), [])

    def test_meta_only_filters_to_empty(self) -> None:
        self.assertEqual(
            _domain_subset(["session", "state", "verify", "safety"]),
            [],
        )

    def test_steam_plus_session_keeps_steam(self) -> None:
        self.assertEqual(_domain_subset(["steam", "session"]), ["steam"])

    def test_multiple_domain_tools_preserved(self) -> None:
        self.assertEqual(
            _domain_subset(["system", "media", "state"]),
            ["system", "media"],
        )

    def test_ordering_preserved(self) -> None:
        # _domain_subset is a filter — order must match input.
        self.assertEqual(
            _domain_subset(["media", "session", "system", "state"]),
            ["media", "system"],
        )

    def test_subagent_and_skill_load_treated_as_meta(self) -> None:
        self.assertEqual(
            _domain_subset(["subagent", "skill_load"]),
            [],
        )


class ToolSkippedEventNameTest(unittest.TestCase):
    def test_event_name_present_in_agent_source(self) -> None:
        # Catches accidental removal of the wiring.
        import gemma4_agent.agent_core.agent as _agent
        src = inspect.getsource(_agent)
        self.assertIn("tool_call_skipped_when_expected", src)

    def test_reply_preview_is_capped(self) -> None:
        # The wiring slices assistant_content to 200 chars to
        # bound trace size + protect privacy. Pin that constant.
        import gemma4_agent.agent_core.agent as _agent
        src = inspect.getsource(_agent)
        self.assertIn(
            'assistant_content or "")[:200]', src,
            "reply_preview should be capped at 200 chars",
        )


if __name__ == "__main__":
    unittest.main()
