"""Tests for the Sprint R2.5 fix to bench.measure_wake_recall.

The bug fixed: the old measure_wake_recall computed
`recall = fires / expected_count` with no timestamp alignment.
Random fires would score >=1.0; correct fires and totally wrong
fires both produced the same number for the same count of fires.

The new logic ports the bipartite-greedy matcher from
scripts/wake_backend_audit.py: each expected wake absorbs at
most one detection within +/- 1.0s; remaining detections are FP.

These tests exercise the matcher directly + a smoke test of the
full measure_wake_recall pipeline with a monkey-patched
WakeDetector that emits at controlled audio offsets."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def _load_bench():
    spec = importlib.util.spec_from_file_location(
        "bench",
        ROOT / "scripts" / "bench.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bench"] = mod
    spec.loader.exec_module(mod)
    return mod


class MatchDetectionsTest(unittest.TestCase):
    def test_match_perfect(self) -> None:
        m = _load_bench()
        expected = [1.0, 2.5, 5.0, 10.0]
        detections = [1.0, 2.5, 5.0, 10.0]
        tp, fp, fn = m._match_detections(detections, expected)
        self.assertEqual((tp, fp, fn), (4, 0, 0))

    def test_match_no_detections(self) -> None:
        m = _load_bench()
        expected = [1.0, 2.5, 5.0]
        tp, fp, fn = m._match_detections([], expected)
        self.assertEqual((tp, fp, fn), (0, 0, 3))

    def test_match_random_fires_dont_inflate_recall(self) -> None:
        """The critical regression. Pre-R2.5 bench computed
        recall = len(detections) / len(expected); 100 random
        fires over a non-matching grid yielded recall=2.0
        (nonsensical). The fixed matcher returns tp=0 because no
        detection falls within tolerance of an expected wake."""
        m = _load_bench()
        # 100 fires at 3.0s grid: [0, 3, 6, ..., 297]
        detections = [3.0 * i for i in range(100)]
        # 50 expected wakes at a 3.0s grid offset by 1.5s:
        # [1.5, 4.5, 7.5, ..., 148.5]. NEVER within +/-0.25s
        # of any detection.
        expected = [3.0 * i + 1.5 for i in range(50)]
        tp, fp, fn = m._match_detections(
            detections, expected, tolerance_s=0.25,
        )
        self.assertEqual(tp, 0)
        self.assertEqual(fp, 100)
        self.assertEqual(fn, 50)
        recall = tp / len(expected)
        self.assertEqual(recall, 0.0)
        # Old buggy behavior would have computed:
        #   recall = len(detections) / len(expected) = 100/50 = 2.0
        # Confirm the new metric is bounded.
        self.assertLessEqual(recall, 1.0)

    def test_match_within_tolerance(self) -> None:
        m = _load_bench()
        # 10.4s vs 10.0s expected, tolerance 1.0 -> match.
        tp, fp, fn = m._match_detections([10.4], [10.0], tolerance_s=1.0)
        self.assertEqual((tp, fp, fn), (1, 0, 0))
        # 12.0s vs 10.0s expected, tolerance 1.0 -> miss.
        tp, fp, fn = m._match_detections([12.0], [10.0], tolerance_s=1.0)
        self.assertEqual((tp, fp, fn), (0, 1, 1))

    def test_match_one_to_one_no_double_counting(self) -> None:
        """Two detections both within tolerance of the same expected
        wake. Only the closest absorbs the expected; the other is FP."""
        m = _load_bench()
        detections = [10.1, 10.2]
        expected = [10.0]
        tp, fp, fn = m._match_detections(detections, expected)
        self.assertEqual(tp, 1)
        self.assertEqual(fp, 1)
        self.assertEqual(fn, 0)


class MeasureWakeRecallSmokeTest(unittest.TestCase):
    """Integration smoke test for measure_wake_recall with a
    monkey-patched WakeDetector. We synthesize 5s of silence,
    a fake expected.json, and patch the detector to emit fires
    at controlled offsets via _last_offset[0]."""

    def _build_wav(self, duration_s: float, tmp: Path) -> Path:
        from gemma4_agent.voice.audio_io import SAMPLE_RATE
        n = int(duration_s * SAMPLE_RATE)
        data = np.zeros(n, dtype=np.int16)
        wav_path = tmp / "fake.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(data.tobytes())
        return wav_path

    def test_measure_wake_recall_emits_tp_fp_fn_in_details(self) -> None:
        m = _load_bench()

        # Build a fake WAV + expected.json in a temp dir; redirect
        # the bench's resolver to use it.
        with tempfile.TemporaryDirectory() as tmpd:
            tmp = Path(tmpd)
            wav = self._build_wav(10.0, tmp)
            expected_path = tmp / "expected.json"
            expected_path.write_text(json.dumps({
                "wakes": [
                    {"timestamp_s": 1.0, "expected": True},
                    {"timestamp_s": 3.0, "expected": True},
                    {"timestamp_s": 7.0, "expected": True},
                ]
            }), encoding="utf-8")

            # Stub WakeDetector: fires at audio offsets 1.0s, 3.0s,
            # and a phantom at 9.5s (FP). The _last_offset proxy in
            # the bench drives ordering -- emit during feed() based
            # on the offset value.

            class FakeDetector:
                last_error = None

                def __init__(self, on_wake):
                    self._on_wake = on_wake
                    self._fired = set()

                def load(self):
                    return True

                def feed(self, chunk):
                    # Use the closure variable from the bench's
                    # _last_offset to figure out the current
                    # offset. Read it via the bench's module-level
                    # introspection (via _on_wake closure).
                    offset = self._on_wake_offset()
                    for trigger_s in (1.0, 3.0, 9.5):
                        if trigger_s in self._fired:
                            continue
                        # Fire when we've JUST crossed the trigger.
                        if offset >= trigger_s:
                            self._fired.add(trigger_s)
                            self._on_wake("hey gemma", 0.0, 0.0, 0.95)

                def _on_wake_offset(self):
                    # The bench mutates _last_offset[0] in the
                    # outer scope of measure_wake_recall. We can
                    # peek at it by inspecting closure cells of
                    # the on_wake callback we received.
                    closure_cells = self._on_wake.__closure__ or ()
                    for cell in closure_cells:
                        val = cell.cell_contents
                        if isinstance(val, list) and val \
                                and isinstance(val[0], float):
                            return val[0]
                    return 0.0

            # Patch the imports that measure_wake_recall touches.
            with patch.object(m, "TEST_V2", wav), \
                 patch.object(m, "TEST_V2_EXPECTED", expected_path), \
                 patch.object(m, "TEST_FALLBACK", wav), \
                 patch(
                     "gemma4_agent.voice.wake.WakeDetector",
                     FakeDetector,
                 ):
                result = m.measure_wake_recall()

        self.assertIsNotNone(result.measured)
        self.assertIn("tp", result.details)
        self.assertIn("fp", result.details)
        self.assertIn("fn", result.details)
        self.assertIn("precision", result.details)
        self.assertIn("f1", result.details)
        # Detector fired 3 times; 2 matched (1.0s, 3.0s); 1 was
        # a phantom at 9.5s (no expected wake at 7.0+/-1.0s).
        self.assertEqual(result.details["tp"], 2)
        self.assertEqual(result.details["fp"], 1)
        self.assertEqual(result.details["fn"], 1)
        # Recall = 2 / 3 expected.
        self.assertAlmostEqual(result.measured, 2 / 3, places=3)
        # Precision = 2 / 3 fires.
        self.assertAlmostEqual(result.details["precision"], 2 / 3, places=3)


if __name__ == "__main__":
    unittest.main()
