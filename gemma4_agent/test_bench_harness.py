"""Tests for the production-readiness bench harness shape.

These don't load Whisper/Vosk/torch — pure unit tests against the
ThresholdResult dataclass + writer logic + comparator.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "bench",
        ROOT / "scripts" / "bench.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bench"] = mod
    spec.loader.exec_module(mod)
    return mod


class ThresholdsTest(unittest.TestCase):
    def test_five_thresholds_defined(self) -> None:
        b = _load_module()
        self.assertEqual(set(b.THRESHOLDS.keys()), {
            "wake_recall", "wake_fp_rate", "stt_wer_mean",
            "stt_latency_p95", "voice_e2e_p95",
        })

    def test_thresholds_match_production_ready_doc(self) -> None:
        # If you change values here, update docs/PRODUCTION_READY.md.
        b = _load_module()
        self.assertEqual(b.THRESHOLDS["wake_recall"]["target"], 0.70)
        self.assertEqual(b.THRESHOLDS["wake_fp_rate"]["target"], 1.0)
        self.assertEqual(b.THRESHOLDS["stt_wer_mean"]["target"], 0.20)
        self.assertEqual(b.THRESHOLDS["stt_latency_p95"]["target"], 1.2)
        self.assertEqual(b.THRESHOLDS["voice_e2e_p95"]["target"], 5.0)


class ComparatorTest(unittest.TestCase):
    def test_greater_equal(self) -> None:
        b = _load_module()
        self.assertTrue(b._compare(0.75, 0.70, ">="))
        self.assertFalse(b._compare(0.65, 0.70, ">="))

    def test_less_than(self) -> None:
        b = _load_module()
        self.assertTrue(b._compare(0.15, 0.20, "<"))
        self.assertFalse(b._compare(0.20, 0.20, "<"))


class WriterTest(unittest.TestCase):
    def test_output_shape(self) -> None:
        b = _load_module()
        results = [
            b.ThresholdResult(
                name="wake_recall", measured=0.85, target=0.70,
                op=">=", passed=True, note="test",
            ),
            b.ThresholdResult(
                name="wake_fp_rate", measured=None, target=1.0,
                op="<=", passed=None, note="skipped",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            json_path, md_path = b._write_outputs(results, Path(tmp))
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(data["summary"]["total"], 2)
            self.assertEqual(data["summary"]["passed"], 1)
            self.assertEqual(data["summary"]["skipped"], 1)
            self.assertFalse(data["summary"]["production_ready"])
            md = md_path.read_text(encoding="utf-8")
            self.assertIn("wake_recall", md)
            self.assertIn("PASS", md)
            self.assertIn("SKIPPED", md)

    def test_all_passed_says_production_ready(self) -> None:
        b = _load_module()
        results = [
            b.ThresholdResult(name=k, measured=v["target"],
                              target=v["target"], op=v["op"],
                              passed=True, note="ok")
            for k, v in b.THRESHOLDS.items()
        ]
        with tempfile.TemporaryDirectory() as tmp:
            json_path, _ = b._write_outputs(results, Path(tmp))
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertTrue(data["summary"]["production_ready"])


if __name__ == "__main__":
    unittest.main()
