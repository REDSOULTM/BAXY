"""router_v2 maintains per-process counters for calibration
telemetry (hotfix H 2026-05-17).

Skips integration assertions when the e5-small model is absent
(CI without bootstrap).
"""
from __future__ import annotations

import unittest

from gemma4_agent.router_v2 import MODEL_PATH, RouterV2


@unittest.skipUnless(MODEL_PATH.exists(), "e5-small ONNX model not installed")
class RouterV2CountersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        RouterV2.reset()
        cls.router = RouterV2.get()
        if not cls.router._ensure_loaded():
            raise unittest.SkipTest(cls.router._load_error)

    @classmethod
    def tearDownClass(cls) -> None:
        RouterV2.reset()

    def setUp(self) -> None:
        # Each test starts from a clean singleton so counters are
        # deterministic.
        RouterV2.reset()
        self.__class__.router = RouterV2.get()
        self.router._ensure_loaded()

    def test_counters_increment_on_each_call(self) -> None:
        baseline = self.router._counters["calls_total"]
        self.router.route("hola")
        self.router.route("apaga la pc")
        self.assertGreaterEqual(
            self.router._counters["calls_total"], baseline + 2,
        )

    def test_summary_returns_dict_with_latency(self) -> None:
        self.router.route("hola")
        summary = self.router.session_summary()
        self.assertIn("calls_total", summary)
        self.assertIn("latency_ms_avg", summary)
        self.assertIn("latency_ms_max", summary)
        # latency_ms_max can round to 0.0 on a warmed hot path
        # (rounded to 2 decimals; warm cache hits routinely finish
        # in microseconds). Just assert the field is a float and
        # non-negative — value-zero is a legitimate observation,
        # not a regression.
        self.assertIsInstance(summary["latency_ms_max"], float)
        self.assertGreaterEqual(summary["latency_ms_max"], 0.0)
        self.assertIsInstance(summary["latency_ms_avg"], float)
        self.assertGreaterEqual(summary["latency_ms_avg"], 0.0)

    def test_source_counters_distinguish_smalltalk_vs_hybrid(self) -> None:
        self.router.route("hola")              # smalltalk
        self.router.route("abrime el steam")   # hybrid (or cache after warm)
        s = self.router.session_summary()
        self.assertGreaterEqual(s["source_smalltalk"], 1)
        self.assertGreaterEqual(
            s["source_hybrid"] + s["source_cache"], 1,
        )

    def test_empty_query_increments_empty_counter(self) -> None:
        self.router.route("")
        s = self.router.session_summary()
        self.assertGreaterEqual(s["source_empty_query"], 1)

    def test_pending_tool_injected_counter_fires(self) -> None:
        self.router.route("hola", pending_tool_hint="steam")
        s = self.router.session_summary()
        self.assertGreaterEqual(s["pending_tool_injected"], 1)


class RouterV2DisabledCounterTest(unittest.TestCase):
    """When the router can't load (model absent), source_disabled
    should accumulate per call but load_failed should be 1 (sticky).
    """

    def test_load_failed_counted_once(self) -> None:
        RouterV2.reset()
        router = RouterV2.get()
        # Force the sticky failure flag without touching the FS.
        router._load_failed = True
        router._load_error = "test-injected"
        # Three calls all hit the disabled path.
        for _ in range(3):
            router.route("hola")
        s = router.session_summary()
        self.assertGreaterEqual(s["source_disabled"], 3)
        self.assertEqual(s["load_failed"], 1,
                         "load_failed should be sticky-1, not per-call")
        RouterV2.reset()


if __name__ == "__main__":
    unittest.main()
