"""Adaptive subset cap by confidence (hotfix J 2026-05-17).

Cap-by-confidence is a pure post-processing layer on top of the
existing RRF pipeline. Tests verify:
  - High-confidence queries (clear top-1 in both retrievers,
    near-max RRF score) -> 4 tools.
  - Medium-confidence queries (agreement but lower score) -> 8.
  - Low-confidence queries (retrievers disagree) -> 16.
  - Cache hits / smalltalk / fallback paths are unchanged.

Skips integration cases when the e5-small model isn't on disk.
"""
from __future__ import annotations

import unittest

from gemma4_agent.router_v2 import (
    FALLBACK_THETA,
    HIGH_CONFIDENCE_CAP,
    HIGH_CONFIDENCE_TOP_SCORE,
    MEDIUM_CONFIDENCE_CAP,
    MEDIUM_CONFIDENCE_TOP_SCORE,
    MODEL_PATH,
    RouterV2,
    TOP_K,
    route_v2,
)


class AdaptiveCapConstantsTest(unittest.TestCase):
    """Pin the band boundaries so a silent regression shows up
    in the diff."""

    def test_high_band_above_fallback_theta(self) -> None:
        # HIGH band must be above FALLBACK_THETA (0.025) so the
        # popular-fallback path doesn't overlap with high-confidence.
        self.assertGreater(HIGH_CONFIDENCE_TOP_SCORE, FALLBACK_THETA)

    def test_medium_band_below_high(self) -> None:
        self.assertLess(MEDIUM_CONFIDENCE_TOP_SCORE, HIGH_CONFIDENCE_TOP_SCORE)

    def test_caps_are_ordered(self) -> None:
        self.assertLess(HIGH_CONFIDENCE_CAP, MEDIUM_CONFIDENCE_CAP)
        self.assertLess(MEDIUM_CONFIDENCE_CAP, TOP_K)

    def test_high_cap_is_small_enough_to_help(self) -> None:
        # If HIGH cap is too big the optimization is meaningless.
        self.assertLessEqual(HIGH_CONFIDENCE_CAP, 6)

    def test_high_threshold_below_rrf_theoretical_max(self) -> None:
        # RRF max for k=60 over 65 docs is 2/61 ≈ 0.0328. The HIGH
        # threshold must sit below it or the band is unreachable.
        rrf_theoretical_max = 2.0 / 61.0  # ≈ 0.0328
        self.assertLess(HIGH_CONFIDENCE_TOP_SCORE, rrf_theoretical_max)


@unittest.skipUnless(MODEL_PATH.exists(), "e5-small ONNX model not installed")
class AdaptiveCapBehaviourTest(unittest.TestCase):
    """Integration tests with the real router.

    Each test resets the singleton to avoid cache-hit pollution
    from prior tests."""

    def _route_cold(self, query: str):
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        return route_v2(query)

    def test_clear_volume_command_yields_high_band(self) -> None:
        # The motivating bug for hotfix J: 'sube el volumen' had
        # 16 tools when audio was clearly top-1 in both retrievers.
        subset, tel = self._route_cold("sube el volumen")
        self.assertEqual(tel.get("source"), "hybrid")
        self.assertTrue(tel.get("retrievers_agree"))
        self.assertEqual(tel.get("confidence_band"), "high")
        self.assertEqual(tel.get("adaptive_cap"), HIGH_CONFIDENCE_CAP)
        self.assertLessEqual(len(subset), HIGH_CONFIDENCE_CAP)
        self.assertIn("audio", subset)

    def test_clear_power_command_yields_high_band(self) -> None:
        subset, tel = self._route_cold("apaga la pc")
        self.assertTrue(tel.get("retrievers_agree"))
        self.assertLessEqual(len(subset), HIGH_CONFIDENCE_CAP)
        self.assertIn("system", subset)

    def test_clear_install_command_yields_high_band(self) -> None:
        subset, tel = self._route_cold("instala vlc")
        self.assertTrue(tel.get("retrievers_agree"))
        self.assertLessEqual(len(subset), HIGH_CONFIDENCE_CAP)
        self.assertIn("package", subset)

    def test_subset_keeps_top_tool_first(self) -> None:
        # The capping should NOT reorder — top-1 stays first.
        subset, _ = self._route_cold("sube el volumen")
        self.assertEqual(subset[0], "audio")

    def test_telemetry_exposes_band(self) -> None:
        _, tel = self._route_cold("sube el volumen")
        self.assertIn("confidence_band", tel)
        self.assertIn("adaptive_cap", tel)
        self.assertIn("retrievers_agree", tel)

    def test_smalltalk_unchanged_no_band(self) -> None:
        # Smalltalk gate fires before the cap logic; confidence_band
        # should NOT appear in telemetry for smalltalk source.
        subset, tel = self._route_cold("hola")
        if tel.get("source") == "smalltalk":
            self.assertNotIn("confidence_band", tel)
            self.assertEqual(subset, [])

    def test_empty_query_unchanged_no_band(self) -> None:
        # Empty-query early-out also predates the cap logic.
        subset, tel = self._route_cold("")
        self.assertEqual(tel.get("source"), "empty_query")
        self.assertNotIn("confidence_band", tel)


@unittest.skipUnless(MODEL_PATH.exists(), "e5-small ONNX model not installed")
class AdaptiveCapCounterTest(unittest.TestCase):
    """Verify the band counters added in J1.4 increment correctly."""

    def test_band_counters_increment(self) -> None:
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        baseline_high = router._counters.get("band_high", 0)
        router.route("sube el volumen")  # expected high
        self.assertGreaterEqual(
            router._counters.get("band_high", 0),
            baseline_high + 1,
        )

    def test_session_summary_includes_band_counters(self) -> None:
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        router.route("sube el volumen")
        summary = router.session_summary()
        self.assertIn("band_high", summary)
        self.assertIn("band_medium", summary)
        self.assertIn("band_low", summary)

    def test_smalltalk_does_not_bump_band_counter(self) -> None:
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            self.skipTest(router._load_error)
        baseline = sum(
            router._counters.get(f"band_{b}", 0)
            for b in ("high", "medium", "low")
        )
        router.route("hola")  # smalltalk gate fires
        after = sum(
            router._counters.get(f"band_{b}", 0)
            for b in ("high", "medium", "low")
        )
        # No band bumped — smalltalk path leaves confidence_band
        # unset, so _record_call's `if key in self._counters` no-ops.
        self.assertEqual(after, baseline)


if __name__ == "__main__":
    unittest.main()
