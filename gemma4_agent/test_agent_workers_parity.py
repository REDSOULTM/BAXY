"""Contract tests for AgentRunner (threading) and AgentWorker (PyQt6).

Sprint 5b is going to collapse both workers onto a shared
AgentSerialWorker base. Without these parity tests, a change to one
worker's submit/stop semantics would silently desync the other.

What we DO test here:
  - submit() enqueues without blocking and does NOT launch the agent.
  - stop() sets the running flag to False and injects the sentinel
    needed to unblock `queue.Queue.get()`.
  - restart() drops references to the in-flight agent.
  - The singleton RUNNER (module-level) is consistent across imports.
  - The two classes share the critical public surface: `submit`,
    `stop`. Each may have extra methods (Qt slots etc) — only the
    common surface is asserted.
  - AgentWorker headless smoke test: instantiation + signal attrs
    exist (requires QApplication, runs offscreen).

What we DON'T test here:
  - The full `_build_agent` path (would autostart llama-server / load
    the LLM client / sentence-transformers).
  - The worker loop (`_run` / `run`) running real turns — that's
    TestRunTextToolCallFlow's job in test_gemma4agent_contract.

If PyQt6 cannot offscreen-init, the AgentWorker class is skipped with
a clear reason. AgentRunner tests do not need Qt and always run.
"""
from __future__ import annotations

import os
import threading
import time
import unittest

# Force PyQt6 to use the offscreen platform for headless test runners.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_available() -> tuple[bool, str]:
    """Return (ok, reason). True iff a QApplication can be instantiated."""
    try:
        from PyQt6.QtWidgets import QApplication  # type: ignore[import-not-found]
    except ImportError as exc:
        return False, f"PyQt6 not installed: {exc}"
    try:
        # Reuse an existing app if some other test created one.
        app = QApplication.instance() or QApplication([])
        del app
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"QApplication init failed: {exc}"


_QT_OK, _QT_REASON = _qt_available()


class TestAgentRunnerSubmit(unittest.TestCase):
    """submit() must enqueue without blocking and without starting the agent."""

    def setUp(self) -> None:
        # Use a fresh AgentRunner (not the module singleton) so we don't
        # accidentally leak a started worker thread across tests.
        from .agent_runner import AgentRunner
        self.runner = AgentRunner()

    def test_submit_enqueues_one_item(self) -> None:
        self.assertEqual(self.runner._inbox.qsize(), 0)
        # Since `submit` lazy-starts via .start(), patch start to a no-op
        # for this assertion (we don't want the worker thread to drain
        # the inbox concurrently).
        self.runner.start = lambda: None  # type: ignore[method-assign]
        self.runner.submit("hola")
        self.assertEqual(self.runner._inbox.qsize(), 1)

    def test_submit_returns_quickly(self) -> None:
        # Without an actual worker draining, submit() must still return
        # in < 100 ms because queue.put is non-blocking for an unbounded
        # queue and lazy-start is a no-op on subsequent calls.
        self.runner.start = lambda: None  # type: ignore[method-assign]
        t0 = time.perf_counter()
        self.runner.submit("hola")
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 0.1, f"submit took {elapsed:.3f}s, expected <0.1s")

    def test_submit_passes_images_and_audios(self) -> None:
        self.runner.start = lambda: None  # type: ignore[method-assign]
        self.runner.submit("hola", images=["/a.png"], audios=["/b.wav"])
        req = self.runner._inbox.get_nowait()
        self.assertEqual(req.text, "hola")
        self.assertEqual(req.images, ["/a.png"])
        self.assertEqual(req.audios, ["/b.wav"])


class TestAgentRunnerStop(unittest.TestCase):
    """stop() must set _running=False AND inject the queue sentinel so the
    worker loop, if started, can unblock and exit."""

    def setUp(self) -> None:
        from .agent_runner import AgentRunner
        self.runner = AgentRunner()

    def test_stop_sets_running_false(self) -> None:
        self.assertTrue(self.runner._running)
        self.runner.stop()
        self.assertFalse(self.runner._running)

    def test_stop_sets_stop_event(self) -> None:
        self.runner.stop()
        self.assertTrue(self.runner._stop_event.is_set())

    def test_stop_injects_sentinel(self) -> None:
        # Without an inbox drainer, the sentinel ends up in the queue.
        self.runner.stop()
        self.assertGreaterEqual(self.runner._inbox.qsize(), 1)
        req = self.runner._inbox.get_nowait()
        self.assertEqual(req.text, "__stop__")


class TestAgentRunnerRestart(unittest.TestCase):
    """restart() must drop the agent ref + clear the warmup latch."""

    def setUp(self) -> None:
        from .agent_runner import AgentRunner
        self.runner = AgentRunner()

    def test_restart_clears_agent_and_warmup(self) -> None:
        # Simulate a built/warm runner.
        self.runner._agent = object()
        self.runner._warmed_up = True
        self.assertTrue(self.runner.is_warmed_up())
        self.assertTrue(self.runner.agent_ready())

        # Patch _build_agent so restart()'s background thread doesn't
        # actually build a new agent.
        self.runner._build_agent = lambda: None  # type: ignore[method-assign]
        self.runner.restart()

        self.assertIsNone(self.runner._agent)
        self.assertFalse(self.runner._warmed_up)
        self.assertFalse(self.runner.is_warmed_up())
        self.assertFalse(self.runner.agent_ready())


class TestRunnerSingleton(unittest.TestCase):
    """The module-level RUNNER is a process-wide singleton. Re-importing
    must yield the same object."""

    def test_runner_is_same_across_two_imports(self) -> None:
        from .agent_runner import RUNNER as r1
        from gemma4_agent.agent_runner import RUNNER as r2
        self.assertIs(r1, r2)

    def test_runner_is_AgentRunner_instance(self) -> None:
        from .agent_runner import RUNNER, AgentRunner
        self.assertIsInstance(RUNNER, AgentRunner)


class TestAPIParity(unittest.TestCase):
    """The minimal public surface both workers share. Sprint 5b's
    AgentSerialWorker base must keep these reachable from both."""

    @unittest.skipUnless(_QT_OK, _QT_REASON)
    def test_submit_and_stop_in_both(self) -> None:
        from .agent_runner import AgentRunner
        from .ui.agent_thread import AgentWorker

        runner_methods = {m for m in dir(AgentRunner) if not m.startswith("_")}
        worker_methods = {m for m in dir(AgentWorker) if not m.startswith("_")}
        common = runner_methods & worker_methods

        self.assertIn("submit", common,
                      "Both workers must expose `submit` (consumed by CLI/server/UI)")
        self.assertIn("stop", common,
                      "Both workers must expose `stop` (consumed by shutdown paths)")

    @unittest.skipUnless(_QT_OK, _QT_REASON)
    def test_submit_signature_compatible(self) -> None:
        """Both submit() methods accept text + keyword images + keyword audios."""
        import inspect
        from .agent_runner import AgentRunner
        from .ui.agent_thread import AgentWorker

        sig_runner = inspect.signature(AgentRunner.submit)
        sig_worker = inspect.signature(AgentWorker.submit)
        for sig in (sig_runner, sig_worker):
            params = sig.parameters
            self.assertIn("text", params)
            self.assertIn("images", params)
            self.assertIn("audios", params)


class TestAgentWorkerHeadless(unittest.TestCase):
    """Headless smoke test for the PyQt6 worker — instantiation +
    signal attribute presence. We deliberately do NOT call .start();
    that would spin up _build_agent against a non-existent llama-server."""

    @classmethod
    def setUpClass(cls) -> None:
        if not _QT_OK:
            raise unittest.SkipTest(_QT_REASON)
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])  # type: ignore[attr-defined]

    def test_instantiates_without_crashing(self) -> None:
        from .ui.agent_thread import AgentWorker
        w = AgentWorker()
        self.addCleanup(w.deleteLater)
        # Signals are pyqtSignal descriptors at class level; on the
        # instance they expose `.emit` / `.connect`.
        for sig_name in ("state_changed", "progress", "log", "reply_ready",
                         "llm_error", "connection_changed", "health_status"):
            self.assertTrue(hasattr(w, sig_name),
                            f"AgentWorker must expose `{sig_name}` signal")
            sig = getattr(w, sig_name)
            self.assertTrue(hasattr(sig, "emit"),
                            f"`{sig_name}` must be a pyqtSignal (has .emit)")
            self.assertTrue(hasattr(sig, "connect"),
                            f"`{sig_name}` must be a pyqtSignal (has .connect)")

    def test_submit_enqueues_without_starting_thread(self) -> None:
        from .ui.agent_thread import AgentWorker
        w = AgentWorker()
        self.addCleanup(w.deleteLater)
        self.assertEqual(w._inbox.qsize(), 0)
        w.submit("hola")
        self.assertEqual(w._inbox.qsize(), 1)

    def test_stop_sets_running_false(self) -> None:
        from .ui.agent_thread import AgentWorker
        w = AgentWorker()
        self.addCleanup(w.deleteLater)
        self.assertTrue(w._running)
        w.stop()
        self.assertFalse(w._running)
        self.assertTrue(w._stop_event.is_set())


if __name__ == "__main__":
    unittest.main()
