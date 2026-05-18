"""Shape contract for the Sprint N ground truth outputs.

These tests do NOT run Whisper-large — they validate that IF the
script produced an output, it has the right structure. Integration
testing (does Whisper-large actually run?) is a manual smoke step.

If the JSON outputs don't exist yet, all tests skip cleanly.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GT_DIR = ROOT / "voice" / "tests"
FULL = GT_DIR / "testaudio_groundtruth_full.json"
ALIGNED = GT_DIR / "testaudio_groundtruth_aligned.json"


class GroundTruthFullShapeTest(unittest.TestCase):
    @unittest.skipUnless(FULL.exists(), f"{FULL} not yet generated")
    def test_full_has_required_top_level_fields(self) -> None:
        with open(FULL, encoding="utf-8") as fh:
            d = json.load(fh)
        for k in [
            "source_file", "model", "language_detected",
            "language_probability", "total_duration_s",
            "segments", "manual_correction", "generated_at",
        ]:
            self.assertIn(k, d, f"missing field: {k}")

    @unittest.skipUnless(FULL.exists(), f"{FULL} not yet generated")
    def test_full_segments_have_required_fields(self) -> None:
        with open(FULL, encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertGreater(len(d["segments"]), 0, "no segments produced")
        for s in d["segments"][:5]:
            for k in ["id", "start", "end", "text",
                      "avg_logprob", "no_speech_prob"]:
                self.assertIn(k, s, f"segment missing field: {k}")
            self.assertIsInstance(s["text"], str)
            self.assertGreaterEqual(s["end"], s["start"])

    @unittest.skipUnless(FULL.exists(), f"{FULL} not yet generated")
    def test_full_model_is_large(self) -> None:
        with open(FULL, encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertIn("large", d["model"].lower(),
                      f"model should be a large variant, got {d['model']!r}")


class GroundTruthAlignedShapeTest(unittest.TestCase):
    @unittest.skipUnless(ALIGNED.exists(), f"{ALIGNED} not yet generated")
    def test_aligned_has_required_top_level_fields(self) -> None:
        with open(ALIGNED, encoding="utf-8") as fh:
            d = json.load(fh)
        for k in ["source_file", "alignment_source",
                  "wake_count", "turns"]:
            self.assertIn(k, d, f"missing field: {k}")

    @unittest.skipUnless(ALIGNED.exists(), f"{ALIGNED} not yet generated")
    def test_aligned_turns_have_required_fields(self) -> None:
        with open(ALIGNED, encoding="utf-8") as fh:
            d = json.load(fh)
        for t in d["turns"]:
            for k in ["k", "wake_ts_s", "small_raw_text",
                      "small_reject_reason", "large_text", "verdict"]:
                self.assertIn(k, t, f"turn missing field: {k}")

    @unittest.skipUnless(ALIGNED.exists(), f"{ALIGNED} not yet generated")
    def test_aligned_verdicts_are_valid(self) -> None:
        valid = {
            "agree", "small_overproduced", "small_underproduced",
            "small_rejected_legit", "small_rejected_false_positive",
            "undetermined",
        }
        with open(ALIGNED, encoding="utf-8") as fh:
            d = json.load(fh)
        for t in d["turns"]:
            self.assertIn(t["verdict"], valid,
                          f"unexpected verdict: {t['verdict']!r}")


class WerCerTest(unittest.TestCase):
    """The script auto-installs jiwer if missing (per operator
    install-authorization memory). After running the script once,
    jiwer should be importable and WER/CER should produce numeric
    results for non-empty references."""

    def test_compute_wer_cer_perfect_match_is_zero(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "testaudio_groundtruth",
            ROOT.parent / "scripts" / "testaudio_groundtruth.py",
        )
        if spec is None or spec.loader is None:
            self.skipTest("script not importable")
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            self.skipTest(f"script imports failed: {exc}")
        wer, cer = mod._compute_wer_cer("hello world", "hello world")
        self.assertIsNotNone(wer, "jiwer should auto-install on demand")
        self.assertEqual(wer, 0.0)
        self.assertEqual(cer, 0.0)

    def test_compute_wer_cer_empty_reference_is_none(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "testaudio_groundtruth",
            ROOT.parent / "scripts" / "testaudio_groundtruth.py",
        )
        if spec is None or spec.loader is None:
            self.skipTest("script not importable")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        wer, cer = mod._compute_wer_cer("", "anything")
        self.assertIsNone(wer)
        self.assertIsNone(cer)


if __name__ == "__main__":
    unittest.main()
