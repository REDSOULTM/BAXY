"""Tests for scripts/stt_filter_audit.py (Sprint O).

The aggregation, comparator, and JSON-shape logic do not require
Whisper or audio fixtures -- those run independently. Tests
construct turn dicts directly and exercise the aggregator."""
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
        "stt_filter_audit",
        ROOT / "scripts" / "stt_filter_audit.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["stt_filter_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


class FilterAuditAggregateTest(unittest.TestCase):
    def test_filter_audit_runs_on_empty_input(self) -> None:
        m = _load_module()
        out = m._aggregate([])
        self.assertEqual(out["n_turns"], 0)
        self.assertIsNone(out["pre_wer_mean"])
        self.assertIsNone(out["post_wer_mean"])
        self.assertIsNone(out["delta_post_minus_pre"])
        self.assertEqual(out["gate_reject_counts"], {})

    def test_filter_audit_pre_post_consistent_when_no_rejection(self) -> None:
        # If no turn is rejected, post == raw, so pre_wer == post_wer.
        m = _load_module()
        turns = [
            {"k": 0, "wer_pre": 0.20, "wer_post": 0.20, "reason": "ok"},
            {"k": 1, "wer_pre": 0.35, "wer_post": 0.35, "reason": "ok"},
        ]
        out = m._aggregate(turns)
        self.assertAlmostEqual(out["pre_wer_mean"], out["post_wer_mean"])
        self.assertAlmostEqual(out["delta_post_minus_pre"], 0.0)

    def test_filter_audit_reject_increases_wer_when_text_was_good(self) -> None:
        # Force one turn rejected: raw_text WER was 0.10, but
        # post-filter the text is empty -> post WER 1.0.
        m = _load_module()
        turns = [
            {"k": 0, "wer_pre": 0.10, "wer_post": 1.0,
             "reason": "ngram_repetition"},
            {"k": 1, "wer_pre": 0.20, "wer_post": 0.20, "reason": "ok"},
        ]
        out = m._aggregate(turns)
        self.assertLess(out["pre_wer_mean"], out["post_wer_mean"])
        self.assertGreater(out["delta_post_minus_pre"], 0.0)

    def test_filter_audit_json_output_shape(self) -> None:
        m = _load_module()
        out = m._aggregate([
            {"k": 0, "wer_pre": 0.10, "wer_post": 0.10, "reason": "ok"},
        ])
        for key in ("n_turns", "pre_wer_mean", "post_wer_mean",
                    "gate_reject_counts", "turns"):
            self.assertIn(key, out)

    def test_gate_reject_counts_normalize_reason_string(self) -> None:
        """The reason string from _quality_check may include a
        parenthesized value, e.g. 'low_logprob (-1.23)'. The
        histogram should group by the gate name, not the literal
        string."""
        m = _load_module()
        out = m._aggregate([
            {"k": 0, "reason": "low_logprob (-1.23)", "wer_pre": 0.5,
             "wer_post": 1.0},
            {"k": 1, "reason": "low_logprob (-0.99)", "wer_pre": 0.4,
             "wer_post": 1.0},
            {"k": 2, "reason": "ok", "wer_pre": 0.1, "wer_post": 0.1},
        ])
        self.assertEqual(out["gate_reject_counts"]["low_logprob"], 2)
        self.assertEqual(out["gate_reject_counts"]["ok"], 1)


if __name__ == "__main__":
    unittest.main()
