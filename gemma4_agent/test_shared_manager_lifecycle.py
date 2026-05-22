"""get_shared_manager() owns the process-wide llama-server. Two invariants:

1. ARQUITECTURA: it must build exactly ONE manager even when several boot
   threads race (launcher main, agent_runner boot daemon, profile-swap daemon).
   A double-build would start two servers and orphan one.
2. FIABILIDAD: the managed llama-server must be stopped on interpreter exit,
   else the child is orphaned on Windows holding the full ~6 GB VRAM budget and
   the next launch sees it as 'external' and refuses to manage it.

These pin the singleton-under-contention behavior and the atexit teardown."""
from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from gemma4_agent import llama_server as ls


class TestSharedManagerSingleton(unittest.TestCase):
    def setUp(self):
        ls._SHARED_MANAGER = None
        self.builds = {"n": 0}
        orig = ls.LlamaServerManager
        outer = self

        class _Counting(orig):
            def __init__(self, *a, **k):
                outer.builds["n"] += 1
                import time
                time.sleep(0.03)  # widen the race window
                super().__init__(*a, **k)

        self._orig = orig
        ls.LlamaServerManager = _Counting

    def tearDown(self):
        ls.LlamaServerManager = self._orig
        ls._SHARED_MANAGER = None

    def test_built_once_under_contention(self):
        with ThreadPoolExecutor(max_workers=8) as ex:
            mgrs = [f.result() for f in [ex.submit(ls.get_shared_manager)
                                         for _ in range(8)]]
        self.assertEqual(self.builds["n"], 1, "manager must build exactly once")
        self.assertTrue(all(m is mgrs[0] for m in mgrs))


class TestAtexitStop(unittest.TestCase):
    def tearDown(self):
        ls._SHARED_MANAGER = None

    def test_atexit_stops_managed_server(self):
        fake = mock.MagicMock()
        ls._SHARED_MANAGER = fake
        ls._atexit_stop_shared_manager()
        fake.stop.assert_called_once()

    def test_atexit_noop_without_manager(self):
        ls._SHARED_MANAGER = None
        # Must not raise when nothing was ever started.
        ls._atexit_stop_shared_manager()

    def test_atexit_swallows_stop_errors(self):
        fake = mock.MagicMock()
        fake.stop.side_effect = RuntimeError("boom")
        ls._SHARED_MANAGER = fake
        # Teardown must never let an error escape at interpreter exit.
        ls._atexit_stop_shared_manager()

    def test_get_shared_manager_registers_atexit_once(self):
        ls._SHARED_MANAGER = None
        ls._ATEXIT_REGISTERED = False
        # atexit is imported inside get_shared_manager; patch the stdlib symbol.
        with mock.patch("atexit.register") as reg:
            ls.get_shared_manager()
            first_calls = reg.call_count
            self.assertEqual(first_calls, 1, "registers once on first build")
            # second build path must NOT re-register
            ls._SHARED_MANAGER = None
            ls.get_shared_manager()
            self.assertEqual(reg.call_count, first_calls,
                             "atexit handler registered at most once per process")
        self.assertTrue(ls._ATEXIT_REGISTERED)


if __name__ == "__main__":
    unittest.main()
