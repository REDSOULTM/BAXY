"""No-orphan-resource guard (eje: FIABILIDAD). The audit's recurring bug class
was resources leaked on teardown (Playwright driver — ronda 5; llama-server log
handles + the server process itself — ronda 11). This consolidates the durable
guarantee: opening and closing the managed resources leaves NOTHING behind, and
the atexit cleanup handlers stay wired.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock


class _FakeProc:
    pid = 99
    def __init__(self): self._alive = True
    def poll(self): return None if self._alive else 0
    def terminate(self): self._alive = False
    def kill(self): self._alive = False
    def wait(self, timeout=None): self._alive = False; return 0


class TestLlamaServerLeavesNoOpenHandles(unittest.TestCase):
    """A full start()->stop() cycle must leave the process's open-file count at
    baseline — the round-11 log-handle fix, verified at the OS level."""

    def test_open_files_return_to_baseline(self):
        try:
            import psutil
        except ImportError:
            self.skipTest("psutil not available")
        from gemma4_agent.infra.llama_server import LlamaServerManager
        from gemma4_agent.infra.profiles import PROFILES
        proc = psutil.Process()
        nfiles = lambda: len(proc.open_files())
        mgr = LlamaServerManager()
        baseline = nfiles()
        with mock.patch("gemma4_agent.llama_server.router_mode_enabled", return_value=False), \
             mock.patch("gemma4_agent.llama_server.port_in_use", return_value=False), \
             mock.patch("gemma4_agent.llama_server.check_llama_build", return_value={}), \
             mock.patch.object(Path, "exists", lambda s: True), \
             mock.patch.object(Path, "is_file", lambda s: True), \
             mock.patch("gemma4_agent.llama_server.subprocess.Popen",
                        side_effect=lambda *a, **k: _FakeProc()), \
             mock.patch.object(mgr, "_wait_for_health", return_value=True):
            for _ in range(10):
                mgr.restart(PROFILES["vram4"])  # único perfil (era vram8)
            peak = nfiles()
            mgr.stop()
        after = nfiles()
        self.assertLessEqual(peak, baseline + 2, "no handle accumulation across restarts")
        self.assertLessEqual(after, baseline + 1, "stop() releases the handles")
        self.assertEqual(mgr._log_handles, [])


class TestAtexitHandlersWired(unittest.TestCase):
    """The teardown handlers that prevent orphans must stay registered."""

    def test_browser_cleanup_registered(self):
        import inspect
        from gemma4_agent.tools_pkg import ops_tools

        self.assertIn("atexit.register(_cleanup_all_browser_sessions)",
                      inspect.getsource(ops_tools))

    def test_llama_server_atexit_registered_on_shared_manager(self):
        # C7 (2026-05-29): get_shared_manager registra DOS handlers atexit:
        #   1. el del singleton (_atexit_stop_shared_manager), redundante pero
        #      inofensivo (atexit acepta el mismo callback varias veces);
        #   2. el POR INSTANCIA (_atexit_stop_self), que el __init__ registra para
        #      cubrir TODAS las rutas de instanciación (no solo el singleton).
        # El singleton handler debe seguir presente (back-compat).
        from gemma4_agent.infra import llama_server as ls

        ls._SHARED_MANAGER = None
        ls._ATEXIT_REGISTERED = False
        try:
            with mock.patch("atexit.register") as reg:
                ls.get_shared_manager()
                self.assertEqual(reg.call_count, 2)
                registered = [c[0][0] for c in reg.call_args_list]
                self.assertIn(ls._atexit_stop_shared_manager, registered)
                # y un handler de instancia (_atexit_stop_self ligado al mgr)
                self.assertTrue(
                    any(getattr(f, "__name__", "") == "_atexit_stop_self"
                        for f in registered),
                    "falta el atexit por-instancia (C7)")
        finally:
            ls._SHARED_MANAGER = None


if __name__ == "__main__":
    unittest.main()
