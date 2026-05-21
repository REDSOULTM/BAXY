"""LlamaServerManager opens two parent-side file objects (stdout/stderr) per
start() and hands their fds to the child via Popen. The PARENT copies must be
closed once the child has them — otherwise every restart (profile switch /
vision recycle) leaks two file objects in this always-on process.

EJE del norte rector: FIABILIDAD (handle leak en proceso always-on, en el path
de restart/teardown — el mismo patrón lifecycle de las 21 rondas previas).

These pin: (1) handles close on stop(), (2) no accumulation across N restarts,
(3) a spawn failure (OSError) closes the just-opened handles."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from gemma4_agent.llama_server import LlamaServerManager
from gemma4_agent.profiles import PROFILES


def _fake_profile():
    # A real registered profile (server_running=True so start() proceeds).
    return PROFILES["vram8"]


class _FakeProc:
    """Stand-in for Popen: poll() returns None (alive) until killed."""
    def __init__(self) -> None:
        self.pid = 4321
        self._alive = True

    def poll(self):
        return None if self._alive else 0

    def terminate(self):
        self._alive = False

    def kill(self):
        self._alive = False

    def wait(self, timeout=None):
        self._alive = False
        return 0


class TestLogHandleLifecycle(unittest.TestCase):
    def setUp(self):
        self.mgr = LlamaServerManager()
        # Force the classic (non-router) single-model path with files "present".
        self._patches = [
            mock.patch("gemma4_agent.llama_server.router_mode_enabled", return_value=False),
            mock.patch("gemma4_agent.llama_server.port_in_use", return_value=False),
            mock.patch("gemma4_agent.llama_server.check_llama_build", return_value={}),
            mock.patch.object(Path, "exists", lambda self: True),
            mock.patch.object(Path, "is_file", lambda self: True),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_parent_handles_closed_on_stop(self):
        opened = []

        def _tracking_open(self, *a, **k):
            fh = mock.MagicMock(name=f"fh:{self}")
            opened.append(fh)
            return fh

        with mock.patch.object(Path, "open", _tracking_open), \
                mock.patch("gemma4_agent.llama_server.subprocess.Popen",
                           return_value=_FakeProc()), \
                mock.patch.object(self.mgr, "_wait_for_health", return_value=True):
            self.assertEqual(self.mgr.start(_fake_profile(), timeout_s=1), "started")
            self.assertEqual(len(opened), 2, "start opens stdout+stderr")
            for fh in opened:
                fh.close.assert_not_called()  # still alive while child runs
            self.mgr.stop()
            for fh in opened:
                fh.close.assert_called()  # released after child dies

    def test_no_handle_accumulation_across_restarts(self):
        opened = []

        def _tracking_open(self, *a, **k):
            fh = mock.MagicMock()
            opened.append(fh)
            return fh

        with mock.patch.object(Path, "open", _tracking_open), \
                mock.patch("gemma4_agent.llama_server.subprocess.Popen",
                           side_effect=lambda *a, **k: _FakeProc()), \
                mock.patch.object(self.mgr, "_wait_for_health", return_value=True):
            for _ in range(5):
                self.mgr.restart(_fake_profile())
            # 5 restarts -> 10 opens, and at most ONE pair held live at a time.
            self.assertEqual(len(opened), 10)
            self.assertLessEqual(len(self.mgr._log_handles), 2)
            closed = sum(1 for fh in opened if fh.close.called)
            self.assertGreaterEqual(closed, 8, "previous pairs must be closed")
            self.mgr.stop()
            self.assertEqual(len(self.mgr._log_handles), 0)

    def test_spawn_failure_closes_handles(self):
        opened = []

        def _tracking_open(self, *a, **k):
            fh = mock.MagicMock()
            opened.append(fh)
            return fh

        with mock.patch.object(Path, "open", _tracking_open), \
                mock.patch("gemma4_agent.llama_server.subprocess.Popen",
                           side_effect=OSError("exe vanished")):
            result = self.mgr.start(_fake_profile(), timeout_s=1)
            self.assertEqual(result, "missing_files")
            self.assertEqual(len(opened), 2)
            for fh in opened:
                fh.close.assert_called()  # spawn failed -> no leak


if __name__ == "__main__":
    unittest.main()
