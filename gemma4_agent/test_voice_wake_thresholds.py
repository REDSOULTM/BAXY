"""Tests for Sprint 5 threshold/partial-wake calibration.

Verifies the wake detector's threshold logic without needing the
actual openwakeword model — we mock the predict() call.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import numpy as np


class WakeThresholdTest(unittest.TestCase):
    """Unit tests for WakeDetector._predict_window threshold logic."""

    def _make_detector_with_mocked_model(self, score_returned: float):
        """Construct a WakeDetector whose OWW model.predict returns the
        given score, and capture wake fires.

        Sprint 7: the WakeDetector now supports two backends; we force
        the OWW path by setting _backend='oww_custom' and mocking the
        OWW slots.
        """
        from gemma4_agent.voice import wake
        fires: list[tuple[str, float]] = []
        det = wake.WakeDetector(on_wake=lambda p, s: fires.append((p, s)))
        det._oww_model = MagicMock()
        det._oww_model.predict.return_value = {"hey_gemma": score_returned}
        det._oww_score_key = "hey_gemma"
        det._backend = "oww_custom"
        det._loaded = True
        det.using_custom_model = True
        return det, fires

    def test_score_below_partial_threshold_no_log(self):
        # Score very low — neither fire nor partial event.
        det, fires = self._make_detector_with_mocked_model(0.05)
        from gemma4_agent.voice.wake import OWW_WINDOW_SAMPLES
        det.feed(np.zeros(OWW_WINDOW_SAMPLES, dtype=np.int16))
        self.assertEqual(fires, [])

    def test_score_in_partial_band_does_not_fire(self):
        # Between PARTIAL (0.15) and THRESHOLD (0.3): partial only,
        # no fire.
        det, fires = self._make_detector_with_mocked_model(0.22)
        from gemma4_agent.voice.wake import OWW_WINDOW_SAMPLES
        det.feed(np.zeros(OWW_WINDOW_SAMPLES, dtype=np.int16))
        self.assertEqual(
            fires, [],
            "score 0.22 between partial and threshold must NOT fire wake",
        )

    def test_score_above_threshold_fires(self):
        det, fires = self._make_detector_with_mocked_model(0.45)
        from gemma4_agent.voice.wake import OWW_WINDOW_SAMPLES
        det.feed(np.zeros(OWW_WINDOW_SAMPLES, dtype=np.int16))
        self.assertEqual(len(fires), 1)
        phrase, score = fires[0]
        self.assertEqual(phrase, "hey gemma")
        self.assertAlmostEqual(score, 0.45, places=2)

    def test_same_phrase_cooldown_blocks_immediate_refire(self):
        det, fires = self._make_detector_with_mocked_model(0.5)
        from gemma4_agent.voice.wake import OWW_WINDOW_SAMPLES
        # Two immediate consecutive windows: only the first should fire.
        det.feed(np.zeros(OWW_WINDOW_SAMPLES, dtype=np.int16))
        det.feed(np.zeros(OWW_WINDOW_SAMPLES, dtype=np.int16))
        self.assertEqual(
            len(fires), 1,
            f"Expected exactly 1 fire under cooldown, got {len(fires)}",
        )

    def test_reset_clears_cooldowns(self):
        det, fires = self._make_detector_with_mocked_model(0.5)
        from gemma4_agent.voice.wake import OWW_WINDOW_SAMPLES
        det.feed(np.zeros(OWW_WINDOW_SAMPLES, dtype=np.int16))
        self.assertEqual(len(fires), 1)
        det.reset()
        # After reset, a fresh fire should be allowed immediately.
        det._oww_model.predict.return_value = {"hey_gemma": 0.5}
        det.feed(np.zeros(OWW_WINDOW_SAMPLES, dtype=np.int16))
        self.assertEqual(len(fires), 2)


class ThresholdConstantsTest(unittest.TestCase):
    """The defaults documented in the comments must match the actual
    runtime values. If someone changes one without updating the other,
    this test catches it.
    """

    def test_default_threshold_is_03(self):
        from gemma4_agent.voice.wake import OWW_THRESHOLD
        self.assertEqual(
            OWW_THRESHOLD, 0.3,
            "Sprint 5 calibration: default threshold should be 0.3 "
            "(was 0.5 before, lowered to recover ~40% recall)",
        )

    def test_partial_threshold_below_main(self):
        from gemma4_agent.voice.wake import (
            OWW_THRESHOLD, OWW_PARTIAL_THRESHOLD,
        )
        self.assertLess(OWW_PARTIAL_THRESHOLD, OWW_THRESHOLD)
        self.assertGreater(OWW_PARTIAL_THRESHOLD, 0.0)

    def test_cooldown_under_200ms(self):
        from gemma4_agent.voice.wake import SAME_PHRASE_COOLDOWN_S
        # Sprint 5 lowered cooldown so repeated tries aren't gated.
        self.assertLess(SAME_PHRASE_COOLDOWN_S, 0.20)


if __name__ == "__main__":
    unittest.main()
