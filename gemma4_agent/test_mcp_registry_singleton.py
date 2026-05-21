"""mcp_server._get_registry builds a heavy ToolRegistry (AppResolver +
KnowledgeStore) lazily. The build must happen exactly once even if concurrent
callers race (e.g. if run_http is ever switched to ThreadingHTTPServer).
Double-checked locking, same pattern as the other lazy loaders."""
from __future__ import annotations

import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from gemma4_agent import mcp_server
from gemma4_agent import tools as tools_mod


class TestRegistrySingleton(unittest.TestCase):
    def setUp(self):
        self._orig = tools_mod.ToolRegistry
        mcp_server._REGISTRY = None
        self.builds = {"n": 0}
        outer = self

        class _Counting(self._orig):
            def __init__(self, *a, **k):
                outer.builds["n"] += 1
                time.sleep(0.05)  # widen the race window
                super().__init__(*a, **k)

        tools_mod.ToolRegistry = _Counting

    def tearDown(self):
        tools_mod.ToolRegistry = self._orig
        mcp_server._REGISTRY = None

    def test_built_once_under_contention(self):
        with ThreadPoolExecutor(max_workers=8) as ex:
            regs = [f.result() for f in [ex.submit(mcp_server._get_registry)
                                         for _ in range(8)]]
        self.assertEqual(self.builds["n"], 1,
                         "ToolRegistry must build exactly once under contention")
        self.assertTrue(all(r is regs[0] for r in regs),
                        "all callers must get the same registry instance")

    def test_fast_path_after_build(self):
        first = mcp_server._get_registry()
        n_after_first = self.builds["n"]
        second = mcp_server._get_registry()
        self.assertIs(first, second)
        self.assertEqual(self.builds["n"], n_after_first, "must not rebuild")


if __name__ == "__main__":
    unittest.main()
