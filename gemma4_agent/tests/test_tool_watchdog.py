"""Regression test for the tool watchdog (Bug observed 2026-05-16 19:18):

`media play disney` hung 9+ minutes because Playwright's connect_over_cdp
was called without timeout. The agent's tool execution path now wraps every
tool call in `_run_with_timeout` so no tool can block the turn forever.
"""
from __future__ import annotations

import os
import time
import unittest
from unittest.mock import MagicMock, patch

from gemma4_agent.agent_core.agent import _run_with_timeout


class TestRunWithTimeout(unittest.TestCase):
    """The watchdog mechanism returns control even when the task hangs."""

    def test_fast_function_returns_normally(self):
        def fast():
            return {"ok": True, "data": "fast"}
        out = _run_with_timeout(fast, timeout_s=2.0)
        self.assertFalse(out["_timed_out"])
        self.assertEqual(out["result"], {"ok": True, "data": "fast"})

    def test_slow_function_times_out(self):
        def slow():
            time.sleep(5.0)
            return {"ok": True}
        t0 = time.time()
        out = _run_with_timeout(slow, timeout_s=0.3)
        elapsed = time.time() - t0
        # Watchdog must abort in ~timeout_s, NOT wait for the slow function.
        self.assertLess(elapsed, 1.0,
                        f"watchdog must abort fast; took {elapsed:.2f}s")
        self.assertTrue(out["_timed_out"])
        self.assertIsNone(out["result"])

    def test_function_exception_propagated_as_error(self):
        def boom():
            raise RuntimeError("intentional")
        out = _run_with_timeout(boom, timeout_s=2.0)
        self.assertFalse(out["_timed_out"])
        self.assertIn("intentional", out.get("_error", ""))


class TestAgentToolExecutionWrapsTimeout(unittest.TestCase):
    """The sequential and parallel tool dispatchers must call the watchdog.

    Dispatcher bodies live in gemma4_agent.agent_dispatch.execute_calls_*.
    The watchdog wiring (run_with_timeout for sequential,
    concurrent.futures.TimeoutError handling for parallel) lives there.
    """

    def test_sequential_dispatcher_uses_run_with_timeout(self):
        import inspect
        from gemma4_agent.agent_core import agent_dispatch

        src = inspect.getsource(agent_dispatch.execute_calls_sequential)
        # The pure function takes run_with_timeout as a callable parameter,
        # so the literal name in the source is `run_with_timeout` (the
        # function uses it via the parameter, not the agent's module-level
        # private alias).
        self.assertIn("run_with_timeout", src,
                      "sequential dispatcher must wrap execute() in watchdog")
        self.assertIn("tool_hard_timeout", src,
                      "must emit tool_hard_timeout trace on watchdog fire")

    def test_parallel_dispatcher_has_timeout(self):
        import inspect
        from gemma4_agent.agent_core import agent_dispatch

        src = inspect.getsource(agent_dispatch.execute_calls_parallel)
        self.assertIn("TimeoutError", src,
                      "parallel dispatcher must handle concurrent.futures.TimeoutError")
        self.assertIn("tool_hard_timeout", src)


class TestConnectCDPHasTimeout(unittest.TestCase):
    """ops_tools._connect_cdp_session must pass timeout= to Playwright."""

    def test_connect_cdp_passes_timeout(self):
        import inspect
        from gemma4_agent.tools_pkg import ops_tools

        src = inspect.getsource(ops_tools._connect_cdp_session)
        # Must call connect_over_cdp WITH timeout kwarg.
        self.assertIn("connect_over_cdp", src)
        self.assertIn("timeout=", src,
                      "connect_over_cdp must be called with explicit timeout")


if __name__ == "__main__":
    unittest.main()
