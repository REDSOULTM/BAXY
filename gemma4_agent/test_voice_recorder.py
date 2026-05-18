"""VoiceRecorder lifecycle tests (hotfix L 2026-05-17).

These exercise the module in isolation with synthetic numpy
chunks. They do NOT depend on a live microphone or Piper voice
files — pure unit tests against the recorder's public API.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
import wave
from pathlib import Path

import numpy as np


class VoiceRecorderTest(unittest.TestCase):
    def setUp(self) -> None:
        # Force an isolated recordings dir for each test so we
        # never touch the real ~/.gemma4/recordings.
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="g4rec_"))
        os.environ["GEMMA4_RECORD_AUDIO"] = "1"
        from gemma4_agent.voice import recorder as _rec_mod
        self._real_dir = _rec_mod.RECORDINGS_DIR
        _rec_mod.RECORDINGS_DIR = self.tmp_dir
        # Force fresh singleton.
        _rec_mod.VoiceRecorder._instance = None

    def tearDown(self) -> None:
        from gemma4_agent.voice import recorder as _rec_mod
        try:
            _rec_mod.VoiceRecorder.get().shutdown()
        except Exception:
            pass
        _rec_mod.VoiceRecorder._instance = None
        _rec_mod.RECORDINGS_DIR = self._real_dir
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        os.environ.pop("GEMMA4_RECORD_AUDIO", None)

    def _recorder(self):
        from gemma4_agent.voice.recorder import VoiceRecorder
        return VoiceRecorder.get()

    def test_disabled_via_env(self) -> None:
        os.environ["GEMMA4_RECORD_AUDIO"] = "0"
        r = self._recorder()
        self.assertFalse(r.enable("sess_x"))

    def test_enable_creates_session_dir(self) -> None:
        r = self._recorder()
        self.assertTrue(r.enable("sess_1"))
        self.assertTrue((self.tmp_dir / "sess_1").is_dir())

    def test_turn_lifecycle_produces_wav_and_manifest(self) -> None:
        r = self._recorder()
        r.enable("sess_2")
        r.start_turn(
            turn_id="t1",
            wake_phrase="gemma",
            wake_confidence=0.92,
        )
        # Fake 1 second of mic audio (16000 samples int16).
        mic = np.zeros(16000, dtype=np.int16)
        mic[::100] = 5000  # any non-silence
        r.capture_user_chunk(mic)
        # Fake 0.5s of TTS audio.
        tts = np.zeros(8000, dtype=np.int16)
        r.capture_tts_chunk(tts)
        r.annotate_turn(whisper_transcription="hola")
        r.finish_turn(reason="tts_finished")
        # Wait for writer to drain.
        time.sleep(0.5)

        session_dir = self.tmp_dir / "sess_2"
        self.assertTrue((session_dir / "t1.user.wav").exists())
        self.assertTrue((session_dir / "t1.tts.wav").exists())
        self.assertTrue((session_dir / "manifest.jsonl").exists())

        with open(session_dir / "manifest.jsonl", encoding="utf-8") as fh:
            line = fh.readline()
        entry = json.loads(line)
        self.assertEqual(entry["turn_id"], "t1")
        self.assertEqual(entry["wake_phrase"], "gemma")
        self.assertAlmostEqual(entry["wake_confidence"], 0.92, places=2)
        self.assertEqual(entry["whisper_transcription"], "hola")
        self.assertEqual(entry["manual_correction"], "")
        self.assertEqual(entry["user_samples"], 16000)
        self.assertEqual(entry["tts_samples"], 8000)
        self.assertEqual(entry["finish_reason"], "tts_finished")

    def test_capture_with_no_turn_active_is_noop(self) -> None:
        r = self._recorder()
        r.enable("sess_3")
        # No start_turn - capture should be silent.
        r.capture_user_chunk(np.zeros(1600, dtype=np.int16))
        r.capture_tts_chunk(np.zeros(1600, dtype=np.int16))
        time.sleep(0.2)
        # No WAV files should exist.
        session_dir = self.tmp_dir / "sess_3"
        if session_dir.exists():
            wavs = list(session_dir.glob("*.wav"))
            self.assertEqual(wavs, [])

    def test_tts_only_turn_omits_user_wav(self) -> None:
        # A turn with TTS chunks but no mic chunks should produce
        # only the .tts.wav (no empty .user.wav stub).
        r = self._recorder()
        r.enable("sess_4")
        r.start_turn(turn_id="t1", wake_phrase="", wake_confidence=0.0)
        r.capture_tts_chunk(np.zeros(8000, dtype=np.int16))
        r.finish_turn()
        time.sleep(0.5)
        session_dir = self.tmp_dir / "sess_4"
        self.assertTrue((session_dir / "t1.tts.wav").exists())
        self.assertFalse((session_dir / "t1.user.wav").exists())

    def test_pre_wake_tail_included(self) -> None:
        r = self._recorder()
        r.enable("sess_5")
        tail = np.full(8000, 100, dtype=np.int16)  # 0.5s pre-wake
        r.start_turn(
            turn_id="t1",
            pre_wake_audio=tail,
            wake_phrase="gemma",
            wake_confidence=0.9,
        )
        r.capture_user_chunk(np.full(16000, 200, dtype=np.int16))
        r.finish_turn()
        time.sleep(0.5)
        # The user wav should hold tail + 1s = ~24000 samples.
        with wave.open(str(self.tmp_dir / "sess_5" / "t1.user.wav"), "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1)
            self.assertEqual(wf.getframerate(), 16000)
            self.assertGreaterEqual(wf.getnframes(), 23000)

    def test_manifest_appends_multiple_turns(self) -> None:
        r = self._recorder()
        r.enable("sess_6")
        for i in range(3):
            r.start_turn(turn_id=f"t{i}", wake_phrase="gemma", wake_confidence=0.9)
            r.capture_user_chunk(np.zeros(1600, dtype=np.int16))
            r.finish_turn()
            time.sleep(0.2)
        with open(self.tmp_dir / "sess_6" / "manifest.jsonl", encoding="utf-8") as fh:
            lines = fh.readlines()
        self.assertEqual(len(lines), 3)

    def test_overlapping_start_closes_previous(self) -> None:
        r = self._recorder()
        r.enable("sess_7")
        r.start_turn(turn_id="t1", wake_phrase="gemma", wake_confidence=0.9)
        r.capture_user_chunk(np.zeros(1600, dtype=np.int16))
        # No finish_turn - start a new one. Should auto-close t1.
        r.start_turn(turn_id="t2", wake_phrase="gemma", wake_confidence=0.9)
        r.capture_user_chunk(np.zeros(1600, dtype=np.int16))
        r.finish_turn()
        time.sleep(0.5)
        with open(self.tmp_dir / "sess_7" / "manifest.jsonl", encoding="utf-8") as fh:
            lines = fh.readlines()
        # Both turns should be in the manifest.
        self.assertEqual(len(lines), 2)
        t1 = json.loads(lines[0])
        self.assertEqual(t1["turn_id"], "t1")
        self.assertEqual(t1["finish_reason"], "overlapping_new_turn")

    def test_stt_reject_reason_recorded_when_text_empty(self) -> None:
        # When STT returns empty, the controller calls
        # annotate_turn(stt_reject_reason=...). Verify that path
        # makes it into the manifest entry.
        r = self._recorder()
        r.enable("sess_8")
        r.start_turn(turn_id="t1", wake_phrase="gemma", wake_confidence=0.85)
        r.capture_user_chunk(np.zeros(1600, dtype=np.int16))
        r.annotate_turn(stt_reject_reason="stt_empty_or_vad_reject")
        r.finish_turn(reason="tts_finished")
        time.sleep(0.3)
        with open(self.tmp_dir / "sess_8" / "manifest.jsonl", encoding="utf-8") as fh:
            entry = json.loads(fh.readline())
        self.assertEqual(entry["stt_reject_reason"], "stt_empty_or_vad_reject")
        self.assertIsNone(entry["whisper_transcription"])


if __name__ == "__main__":
    unittest.main()
