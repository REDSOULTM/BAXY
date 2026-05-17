"""Regression test for the Playwright thread-affinity bug (2026-05-16 21:11).

Symptom: `media play disney` returned `cdp_unavailable_reason: "error:
cannot switch to a different thread (which happens to have exited)"`.
Root cause: the watchdog wrapper `_run_with_timeout` runs each tool call
in a fresh ThreadPoolExecutor thread. Playwright sync API is NOT
thread-safe — the runtime is bound to the thread that called
`sync_playwright().start()`. Subsequent calls from worker threads fail.

Fix: dispatchers run thread-affine tools (browser_real, media, browser)
INLINE without the watchdog. Other tools keep their watchdog.
"""
from __future__ import annotations

import inspect
import unittest


class TestSequentialDispatcherBypassesWatchdog(unittest.TestCase):

    def test_sequential_dispatcher_has_thread_affine_list(self):
        from gemma4_agent.agent import Gemma4Agent
        src = inspect.getsource(Gemma4Agent._execute_calls_sequential)
        self.assertIn("_THREAD_AFFINE_TOOLS", src)
        self.assertIn('"browser_real"', src)
        self.assertIn('"media"', src)

    def test_sequential_dispatcher_runs_affine_inline(self):
        """For thread-affine tools, the dispatcher must NOT use
        _run_with_timeout (which spawns a new thread)."""
        from gemma4_agent.agent import Gemma4Agent
        src = inspect.getsource(Gemma4Agent._execute_calls_sequential)
        # The affine branch must call self.tools.execute directly.
        # Find the conditional block.
        idx = src.find("_THREAD_AFFINE_TOOLS")
        snippet = src[idx:idx + 600]
        self.assertIn("self.tools.execute(name, args)", snippet,
                      "affine branch must call execute() inline")


class TestParallelDispatcherSeparatesAffine(unittest.TestCase):

    def test_parallel_dispatcher_separates_affine_and_pool(self):
        from gemma4_agent.agent import Gemma4Agent
        src = inspect.getsource(Gemma4Agent._execute_calls_parallel)
        self.assertIn("_THREAD_AFFINE_TOOLS", src)
        # affine_preps and pool_preps split
        self.assertIn("affine_preps", src)
        self.assertIn("pool_preps", src)


if __name__ == "__main__":
    unittest.main()
