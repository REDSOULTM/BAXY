"""Tests for scripts/session_report.py.

All tests use tempfile to write fake manifest.jsonl fixtures.
No coupling to ~/.gemma4/recordings (Path.home is patched where
the resolver path is exercised)."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "session_report",
        ROOT / "scripts" / "session_report.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["session_report"] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_manifest(dirpath: Path, lines: list[dict]) -> Path:
    p = dirpath / "manifest.jsonl"
    with open(p, "w", encoding="utf-8") as fh:
        for e in lines:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    return p


def _turn(
    turn_id: str = "001",
    duration_s: float = 3.0,
    wake_phrase: str = "hey gemma",
    wake_confidence: float = 0.91,
    tts_samples: int = 32000,
    whisper_transcription: str | None = "pon musica",
    whisper_raw_text: str | None = "pon musica",
    stt_reject_reason: str | None = None,
) -> dict:
    return {
        "session_id": "test",
        "turn_id": turn_id,
        "started_at": 0.0,
        "finished_at": duration_s,
        "duration_s": duration_s,
        "wake_phrase": wake_phrase,
        "wake_confidence": wake_confidence,
        "user_wav": f"{turn_id}.user.wav",
        "user_samples": 48000,
        "tts_wav": f"{turn_id}.tts.wav" if tts_samples > 0 else None,
        "tts_samples": tts_samples,
        "finish_reason": "tts_finished",
        "whisper_transcription": whisper_transcription,
        "whisper_raw_text": whisper_raw_text,
        "stt_reject_reason": stt_reject_reason,
        "manual_correction": "",
        "extra": {},
    }


class EmptyManifestTest(unittest.TestCase):
    def test_load_empty_manifest(self) -> None:
        sr = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_manifest(Path(tmp), [])
            rep = sr.build_report(p)
        self.assertEqual(rep.turn_count, 0)
        self.assertIsNone(rep.wake_confidence_p50)
        self.assertIsNone(rep.wake_confidence_p95)
        self.assertIsNone(rep.tts_duration_p50)
        self.assertIsNone(rep.e2e_p50)
        self.assertIsNone(rep.e2e_p95)
        self.assertIsNone(rep.e2e_max)
        self.assertEqual(rep.transcribed_count, 0)
        self.assertEqual(rep.rejected_count, 0)


class SingleTurnTest(unittest.TestCase):
    def test_load_single_turn(self) -> None:
        sr = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_manifest(Path(tmp), [_turn(duration_s=3.4)])
            rep = sr.build_report(p)
        self.assertEqual(rep.turn_count, 1)
        self.assertEqual(rep.transcribed_count, 1)
        self.assertEqual(rep.replied_count, 1)
        self.assertEqual(rep.happy_path_eligible, 1)
        self.assertAlmostEqual(rep.e2e_p95, 3.4, places=3)
        self.assertAlmostEqual(rep.e2e_p50, 3.4, places=3)
        self.assertAlmostEqual(rep.e2e_max, 3.4, places=3)


class RejectedExcludedTest(unittest.TestCase):
    def test_rejected_turns_excluded_from_e2e(self) -> None:
        sr = _load_module()
        turns = [
            _turn(turn_id="001", duration_s=10.0,
                  whisper_transcription=None,
                  stt_reject_reason="ngram_repetition"),
            _turn(turn_id="002", duration_s=12.0,
                  whisper_transcription=None,
                  stt_reject_reason="no_speech"),
            _turn(turn_id="003", duration_s=3.2),  # happy
        ]
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_manifest(Path(tmp), turns)
            rep = sr.build_report(p)
        self.assertEqual(rep.turn_count, 3)
        self.assertEqual(rep.rejected_count, 2)
        self.assertEqual(rep.happy_path_eligible, 1)
        self.assertAlmostEqual(rep.e2e_p95, 3.2, places=3)
        # The 10s and 12s rejected turns MUST NOT bleed into latency.
        self.assertLess(rep.e2e_max, 5.0)


class RejectReasonHistogramTest(unittest.TestCase):
    def test_reject_reason_histogram(self) -> None:
        sr = _load_module()
        turns = [
            _turn(turn_id="001", whisper_transcription=None,
                  stt_reject_reason="ngram_repetition"),
            _turn(turn_id="002", whisper_transcription=None,
                  stt_reject_reason="ngram_repetition"),
            _turn(turn_id="003", whisper_transcription=None,
                  stt_reject_reason="no_speech"),
            _turn(turn_id="004", whisper_transcription=None,
                  stt_reject_reason="low_logprob"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_manifest(Path(tmp), turns)
            rep = sr.build_report(p)
        self.assertEqual(rep.reject_reasons, {
            "ngram_repetition": 2,
            "no_speech": 1,
            "low_logprob": 1,
        })


class LowConfidenceTest(unittest.TestCase):
    def test_low_confidence_count(self) -> None:
        sr = _load_module()
        turns = [
            _turn(turn_id="001", wake_confidence=0.91),
            _turn(turn_id="002", wake_confidence=0.83),
            _turn(turn_id="003", wake_confidence=0.92),
            _turn(turn_id="004", wake_confidence=0.79),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_manifest(Path(tmp), turns)
            rep = sr.build_report(p)
        self.assertEqual(rep.wake_low_confidence_count, 2)


class PathResolutionTest(unittest.TestCase):
    def test_path_resolution_by_session_id(self) -> None:
        sr = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            fake_home = Path(tmp) / "home"
            recordings = fake_home / ".gemma4" / "recordings" / "20260518_193600"
            recordings.mkdir(parents=True)
            _write_manifest(recordings, [_turn()])
            with patch.object(sr, "RECORDINGS_DIR",
                              fake_home / ".gemma4" / "recordings"):
                resolved = sr._resolve_manifest("20260518_193600")
            self.assertEqual(resolved, recordings / "manifest.jsonl")

    def test_path_resolution_full_path(self) -> None:
        sr = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_manifest(Path(tmp), [_turn()])
            resolved = sr._resolve_manifest(str(p))
            self.assertEqual(resolved, p)


class BenchCompatBlockTest(unittest.TestCase):
    def test_bench_compat_block_present(self) -> None:
        sr = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_manifest(Path(tmp), [
                _turn(turn_id="001", duration_s=2.5),
                _turn(turn_id="002", duration_s=4.1),
            ])
            rep = sr.build_report(p)
            payload = sr.report_to_json(rep)
        self.assertIn("bench_compat", payload)
        bc = payload["bench_compat"]
        self.assertEqual(bc["voice_e2e_p95_eligible_turns"], 2)
        self.assertIsNotNone(bc["voice_e2e_p95"])
        self.assertGreater(bc["voice_e2e_p95"], 2.5)
        self.assertLessEqual(bc["voice_e2e_p95"], 4.1)


if __name__ == "__main__":
    unittest.main()
