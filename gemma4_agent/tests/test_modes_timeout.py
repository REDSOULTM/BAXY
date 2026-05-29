"""Per-mode LLM timeout: a hung/slow call must fail fast, not block up to the
global 180s * max_agent_turns. The deadline is derived from the mode's token
budget (AgentMode.request_timeout_s)."""
from __future__ import annotations

import unittest

from gemma4_agent.support.modes import (
    _MAX_CALL_TIMEOUT_S,
    _MIN_CALL_TIMEOUT_S,
    choose_mode,
)


class TestModeRequestTimeout(unittest.TestCase):
    def _mode(self, name):
        return choose_mode("x", name, 1280)

    def test_all_modes_bounded(self):
        for name in ("fast_action", "quick_action", "deep_action",
                     "vision_action", "audio_mode", "research"):
            t = self._mode(name).request_timeout_s
            self.assertGreaterEqual(t, _MIN_CALL_TIMEOUT_S)
            self.assertLessEqual(t, _MAX_CALL_TIMEOUT_S)

    def test_fast_action_is_short(self):
        # Smalltalk ("hola") must not be able to hang for minutes.
        self.assertLessEqual(self._mode("fast_action").request_timeout_s, 30.0)

    def test_heavier_modes_get_more_time(self):
        # A research/deep turn legitimately generates more tokens -> more time
        # than a conversational reply, so we don't kill a real long answer.
        fast = self._mode("fast_action").request_timeout_s
        research = self._mode("research").request_timeout_s
        deep = self._mode("deep_action").request_timeout_s
        self.assertGreater(research, fast)
        self.assertGreater(deep, fast)

    def test_timeout_scales_with_token_budget(self):
        # Monotonic in (max_tokens + thinking_budget): more budget -> >= time.
        modes = sorted(
            (self._mode(n) for n in ("fast_action", "quick_action", "deep_action")),
            key=lambda m: m.max_tokens + max(0, m.thinking_budget),
        )
        times = [m.request_timeout_s for m in modes]
        self.assertEqual(times, sorted(times))

    def test_never_reaches_global_default(self):
        # The global request_timeout_s default is 180s; every mode must cap below.
        for name in ("fast_action", "quick_action", "deep_action",
                     "vision_action", "audio_mode", "research"):
            self.assertLess(self._mode(name).request_timeout_s, 180.0)


if __name__ == "__main__":
    unittest.main()
