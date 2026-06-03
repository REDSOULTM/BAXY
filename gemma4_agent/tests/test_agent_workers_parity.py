"""Contract tests for AgentRunner (el worker de la UI web ui_field).

2026-06-03: la GUI vieja PyQt6 (gemma4_agent/ui/) y su AgentWorker se
eliminaron; quedó SOLO el AgentRunner (threading, consumido por server/CLI/
web UI). Antes este archivo verificaba la PARIDAD entre ambos workers — ya no
hay dos, así que se quitaron las clases TestAPIParity y TestAgentWorkerHeadless
(dependían de ..ui.agent_thread.AgentWorker, ahora inexistente).

What we DO test here:
  - submit() enqueues without blocking and does NOT launch the agent.
  - stop() sets the running flag to False and injects the sentinel
    needed to unblock `queue.Queue.get()`.
  - restart() drops references to the in-flight agent.
  - The singleton RUNNER (module-level) is consistent across imports.

What we DON'T test here:
  - The full `_build_agent` path (would autostart llama-server / load
    the LLM client / sentence-transformers).
  - The worker loop (`_run`) running real turns — that's
    TestRunTextToolCallFlow's job in test_gemma4agent_contract.
"""
from __future__ import annotations

import time
import unittest


class TestAgentRunnerSubmit(unittest.TestCase):
    """submit() must enqueue without blocking and without starting the agent."""

    def setUp(self) -> None:
        # Use a fresh AgentRunner (not the module singleton) so we don't
        # accidentally leak a started worker thread across tests.
        from ..agent_core.agent_runner import AgentRunner
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
        from ..agent_core.agent_runner import AgentRunner
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
        from ..agent_core.agent_runner import AgentRunner
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
        from ..agent_core.agent_runner import RUNNER as r1
        from gemma4_agent.agent_core.agent_runner import RUNNER as r2
        self.assertIs(r1, r2)

    def test_runner_is_AgentRunner_instance(self) -> None:
        from ..agent_core.agent_runner import RUNNER, AgentRunner
        self.assertIsInstance(RUNNER, AgentRunner)


if __name__ == "__main__":
    unittest.main()
