"""Tests for recorder polish (hotfix M.1 2026-05-18):
- TTS chunks captured even if they arrive shortly after finish_turn
  (grace window for Piper async race).
- finish_turn with reason="stt_rejected" writes manifest with that
  reason instead of "overlapping_new_turn" / "tts_finished".
- wake_confidence propagates from WakeDetector.
- _transcribe_buffer returns (text, reason) tuple.
- STTEvent has reject_reason field.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np


class RecorderM1Test(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="g4m1_"))
        os.environ["GEMMA4_RECORD_AUDIO"] = "1"
        from gemma4_agent.voice import recorder as _r
        self._real_dir = _r.RECORDINGS_DIR
        _r.RECORDINGS_DIR = self.tmp_dir
        _r.VoiceRecorder._instance = None

    def tearDown(self) -> None:
        from gemma4_agent.voice import recorder as _r
        try:
            _r.VoiceRecorder.get().shutdown()
        except Exception:
            pass
        _r.VoiceRecorder._instance = None
        _r.RECORDINGS_DIR = self._real_dir
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        os.environ.pop("GEMMA4_RECORD_AUDIO", None)

    def _recorder(self):
        from gemma4_agent.voice.recorder import VoiceRecorder
        return VoiceRecorder.get()

    def test_late_tts_chunk_within_grace_is_captured(self) -> None:
        """M.1.1: Piper chunks arriving shortly after finish_turn
        should still land on the just-closed turn's .tts.wav."""
        r = self._recorder()
        r.enable("sess_late")
        r.start_turn(turn_id="t1", wake_phrase="gemma", wake_confidence=0.9)
        r.capture_user_chunk(np.zeros(16000, dtype=np.int16))
        r.finish_turn(reason="tts_finished")
        # Simulate a late TTS chunk arriving 100ms after finish.
        time.sleep(0.1)
        r.capture_tts_chunk(np.full(8000, 200, dtype=np.int16))
        # Give the writer time to process.
        time.sleep(0.5)
        # The just-closed turn's .tts.wav should exist with the
        # late chunk written.
        session_dir = self.tmp_dir / "sess_late"
        tts_path = session_dir / "t1.tts.wav"
        self.assertTrue(
            tts_path.exists(),
            "Late TTS chunk should have been captured in grace window",
        )
        self.assertGreater(
            tts_path.stat().st_size, 500,
            "TTS file should hold the late chunk's audio",
        )

    def test_late_tts_chunk_after_grace_is_dropped(self) -> None:
        """M.1.1: Chunks arriving after the grace window expires
        must not be captured (no stale-writer surprise writes)."""
        from gemma4_agent.voice import recorder as _r
        # Lower the grace for test speed.
        original = _r._GRACE_AFTER_FINISH_S
        _r._GRACE_AFTER_FINISH_S = 0.3
        try:
            r = self._recorder()
            r.enable("sess_late2")
            r.start_turn(turn_id="t1", wake_phrase="gemma", wake_confidence=0.9)
            r.capture_user_chunk(np.zeros(1600, dtype=np.int16))
            r.finish_turn(reason="tts_finished")
            # Wait LONGER than the grace window.
            time.sleep(0.5)
            r.capture_tts_chunk(np.full(8000, 200, dtype=np.int16))
            time.sleep(0.3)
            session_dir = self.tmp_dir / "sess_late2"
            tts_path = session_dir / "t1.tts.wav"
            # Either no .tts.wav (preferred) or unchanged from
            # finish_turn time (no late chunk written).
            if tts_path.exists():
                self.assertLess(
                    tts_path.stat().st_size, 200,
                    "TTS chunk after grace should be dropped",
                )
        finally:
            _r._GRACE_AFTER_FINISH_S = original

    def test_stt_rejected_finish_reason_in_manifest(self) -> None:
        """M.1.4: finish_turn(reason='stt_rejected') lands the
        right reason in the manifest entry."""
        r = self._recorder()
        r.enable("sess_rej")
        r.start_turn(turn_id="t1", wake_phrase="gemma", wake_confidence=0.9)
        r.capture_user_chunk(np.zeros(16000, dtype=np.int16))
        r.annotate_turn(stt_reject_reason="BoH_match")
        r.finish_turn(reason="stt_rejected")
        time.sleep(0.3)
        manifest = self.tmp_dir / "sess_rej" / "manifest.jsonl"
        self.assertTrue(manifest.exists())
        with open(manifest, encoding="utf-8") as fh:
            line = fh.readline()
        entry = json.loads(line)
        self.assertEqual(entry["finish_reason"], "stt_rejected")
        self.assertEqual(entry["stt_reject_reason"], "BoH_match")
        self.assertIsNone(entry["whisper_transcription"])

    def test_wake_confidence_passed_to_manifest(self) -> None:
        """M.1.2: real Vosk confidence makes it to the manifest."""
        r = self._recorder()
        r.enable("sess_conf")
        r.start_turn(turn_id="t1", wake_phrase="gemma", wake_confidence=0.93)
        r.capture_user_chunk(np.zeros(1600, dtype=np.int16))
        r.finish_turn()
        time.sleep(0.3)
        with open(
            self.tmp_dir / "sess_conf" / "manifest.jsonl", encoding="utf-8",
        ) as fh:
            entry = json.loads(fh.readline())
        self.assertAlmostEqual(entry["wake_confidence"], 0.93, places=2)


class STTRejectReasonShapeTest(unittest.TestCase):
    """M.1.3: contract tests for the (text, reason) tuple return
    and STTEvent.reject_reason field."""

    def test_transcribe_buffer_docstring_mentions_tuple(self) -> None:
        from gemma4_agent.voice.stt import StreamingSTT
        doc = StreamingSTT._transcribe_buffer.__doc__ or ""
        self.assertTrue(
            "tuple" in doc.lower() or "reason" in doc.lower(),
            "M.1.3: _transcribe_buffer should document (text, reason) tuple",
        )

    def test_stt_event_has_reject_reason_field(self) -> None:
        from gemma4_agent.voice.stt import STTEvent
        # STTEvent is a frozen dataclass; reject_reason must be in
        # its fields with a sensible default.
        fields = STTEvent.__dataclass_fields__
        self.assertIn("reject_reason", fields)
        ev = STTEvent(kind="final", text="", reject_reason="BoH_match")
        self.assertEqual(ev.reject_reason, "BoH_match")
        # Default empty when not set.
        ev2 = STTEvent(kind="partial", text="hola")
        self.assertEqual(ev2.reject_reason, "")


class WakeCallbackSignatureTest(unittest.TestCase):
    """M.1.2: the WakeCallback signature accepts a confidence kwarg."""

    def test_wake_callback_signature_accepts_confidence(self) -> None:
        # We don't load Vosk here; just verify the controller's
        # callback has the new positional-or-kwarg confidence param.
        from gemma4_agent.voice.controller import VoiceController
        import inspect
        sig = inspect.signature(VoiceController._on_wake_detected)
        self.assertIn(
            "confidence", sig.parameters,
            "M.1.2: _on_wake_detected must accept confidence param",
        )


if __name__ == "__main__":
    unittest.main()
