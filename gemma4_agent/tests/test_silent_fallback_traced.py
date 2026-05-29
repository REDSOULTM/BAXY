"""When a known optional component fails, the agent must emit a
`silent_fallback` trace event instead of silently degrading.

Hotfix H 2026-05-17. The full integration test would require a
heavy AgentRunner ctor; here we smoke-check that the event name
is wired in agent.py at the expected component sites. Manual
inspection of the post-fix code is the actual audit.
"""
from __future__ import annotations

import inspect
import unittest


class SilentFallbackImportTest(unittest.TestCase):
    def test_agent_module_imports(self) -> None:
        from gemma4_agent.agent_core.agent import Gemma4Agent  # noqa: F401
        self.assertTrue(True)

    def test_silent_fallback_event_name_is_used(self) -> None:
        # Source-level grep: the event name must exist somewhere
        # in agent.py post-fix. Catches accidental removal.
        import gemma4_agent.agent_core.agent as _agent
        src = inspect.getsource(_agent)
        self.assertIn(
            "silent_fallback", src,
            "silent_fallback event name not found — H1 regressed?",
        )

    def test_critical_components_are_traced(self) -> None:
        # Each critical silent-fallback path declares a `component=`
        # tag so trace consumers can bucket by failure mode. Confirm
        # the headline components have their tags wired up.
        import gemma4_agent.agent_core.agent as _agent
        src = inspect.getsource(_agent)
        expected_components = [
            "microagents",
            "skills_registry",
            "planner_keyword_hits",
            "semantic_router",
        ]
        for comp in expected_components:
            self.assertIn(
                f'component="{comp}"', src,
                f"component={comp!r} silent_fallback tag missing — H1 regressed?",
            )


if __name__ == "__main__":
    unittest.main()
