"""Perf-budget regression guards (eje: LATENCIA). Turns the measured numbers in
bench/overnight_validation.md + bench/latency_microagents_cache.md into
ASSERTIONS, so a future change that silently regresses latency FAILS here instead
of slipping through.

Budgets are the measured baseline + a generous margin (these run on arbitrary,
possibly-loaded hardware, so they must catch a STRUCTURAL regression — e.g. the
wake throttle removed, the microagent cache removed — not micro-jitter). Marked
@pytest.mark.slow because the wake probe loads the real ONNX model (~seconds).

Baselines measured 2026-05-21 (this session, CPU):
  - wake N=4 throttle: ~3.33s CPU / 15s audio (~22% of one core).
  - wake N=1 (no throttle): ~4x that -> the guard asserts the throttle still bites.
  - compaction 10MB: ~2.7ms.
  - _system_message warm: ~1.06ms (with microagent cache; was 2.08ms without).
"""
from __future__ import annotations

import time
import unittest

import pytest

import numpy as np


pytestmark = pytest.mark.slow


class TestCompactionBudget(unittest.TestCase):
    def test_compaction_10mb_under_budget(self):
        """A 10MB history must compact in well under 50ms (measured 2.7ms).
        Guards the round-7 middle_ellipsis fix against an accidental O(n^2)."""
        from gemma4_agent.agent_compaction import compact_history_content
        big = ("La capital de Francia es Paris. ") * 320000  # ~10MB
        t0 = time.perf_counter()
        out = compact_history_content(big)
        dt = time.perf_counter() - t0
        self.assertLess(dt, 0.050, f"compaction took {dt*1000:.1f}ms (budget 50ms)")
        self.assertLess(len(out), len(big), "compaction must shrink the input")


class TestThinkingGatingBudget(unittest.TestCase):
    """LATENCIA (sprint 2026-05-22): info/factual questions must route to a
    thinking-OFF mode. Thinking ON on knowledge questions was measured as pure
    latency cost AND often worse quality (empty replies): cx5 "RAM vs disco"
    48.2s->1.1s, corpus median 4.0s->1.9s once gated. This guards the routing
    that delivered the win — a regression that re-enables thinking on these
    fails here (deterministic, no server needed)."""

    def test_info_and_factual_questions_do_not_think(self):
        from gemma4_agent.modes import choose_mode
        for q in ["explica que es la fotosintesis",
                  "cual es la diferencia entre RAM y disco",
                  "cuando salio GTA 5", "quien escribio el Quijote",
                  "por que el cielo es azul", "cual es la capital de Francia"]:
            m = choose_mode(q, "auto", 512)
            self.assertFalse(m.enable_thinking,
                             f"{q!r} ({m.name}) must NOT think — measured pure latency cost")

    def test_actions_still_think_for_reliable_tool_calls(self):
        # The win must NOT have broken action tool-calling (thinking ON needed).
        from gemma4_agent.modes import choose_mode
        m = choose_mode("abre Chrome", "auto", 512)
        self.assertTrue(m.enable_thinking, "actions need thinking for reliable tool-calls")


class TestSystemMessageBudget(unittest.TestCase):
    def test_system_message_warm_under_budget(self):
        """_system_message runs every turn. Budget 5ms (measured ~1.06ms with the
        microagent cache; ~2.08ms without). A jump past 5ms means the per-turn
        disk-read regression (microagent cache removed) is back."""
        from gemma4_agent.config import AgentConfig
        from gemma4_agent.agent import Gemma4Agent
        agent = Gemma4Agent(AgentConfig.from_env())
        agent._system_message(user_text="abre Steam")  # warm caches
        N = 100
        t0 = time.perf_counter()
        for _ in range(N):
            agent._system_message(user_text="abre Steam")
        per = (time.perf_counter() - t0) / N
        self.assertLess(per, 0.005, f"_system_message {per*1000:.3f}ms/turn (budget 5ms)")


class TestWakeThrottleBudget(unittest.TestCase):
    @pytest.mark.gpu  # loads the real ONNX wake model (CPU ORT, but heavy)
    def test_wake_throttle_still_bites(self):
        """The wake predict-throttle (round 8) must keep idle CPU well below the
        unthrottled cost. We feed the same audio at N=1 and N=4 and assert N=4
        uses < 60% of N=1's CPU (measured ~26%). Catches a removed/broken throttle."""
        import importlib
        from gemma4_agent.voice import wake as wake_mod

        def _cpu_for(every_n: int) -> float:
            import os
            os.environ["GEMMA4_WAKE_PREDICT_EVERY_N"] = str(every_n)
            importlib.reload(wake_mod)
            det = wake_mod.WakeDetector(on_wake=lambda *a, **k: None)
            if not det.load() or getattr(det, "_backend", "") != "livekit":
                self.skipTest("LiveKit wake model unavailable")
            rng = np.random.default_rng(0)
            chunks = [(rng.standard_normal(512) * 300).astype(np.int16) for _ in range(300)]
            for c in chunks[:70]:
                det.feed(c)
            t0 = time.process_time()
            for c in chunks:
                det.feed(c)
            return time.process_time() - t0

        try:
            cpu_n1 = _cpu_for(1)
            cpu_n4 = _cpu_for(4)
        finally:
            import os
            os.environ.pop("GEMMA4_WAKE_PREDICT_EVERY_N", None)
            importlib.reload(wake_mod)
        self.assertGreater(cpu_n1, 0, "sanity: unthrottled run took measurable CPU")
        ratio = cpu_n4 / cpu_n1
        self.assertLess(ratio, 0.60,
                        f"throttle weak: N=4 used {ratio*100:.0f}% of N=1 CPU "
                        f"(expected <60%; measured ~26%)")


if __name__ == "__main__":
    unittest.main()
