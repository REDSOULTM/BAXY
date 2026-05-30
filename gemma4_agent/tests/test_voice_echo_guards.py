"""Tests for the 2026-05-20 self-hearing / silence-hallucination fixes.

Diagnosed from ~/.gemma4/logs/_pre_session/full.log (session 21:41-21:45):
the agent's TTS reply was re-transcribed as the next "command" (self-hearing),
and Whisper hallucinated "¡Suscríbete!"/"hola" on near-silence after a profile
swap. These guards are pure functions on the captured buffer + transcript, so
they're testable without audio hardware or the Whisper/Piper models.
"""
from __future__ import annotations

import unittest

import numpy as np

from gemma4_agent.voice.pipeline import (
    MIN_CAPTURE_RMS,
    _buffer_rms,
    _is_silence_hallucination,
)
from gemma4_agent.voice import tts as tts_mod


class TestBufferRms(unittest.TestCase):
    def test_empty_is_zero(self):
        self.assertEqual(_buffer_rms(np.zeros(0, dtype=np.int16)), 0.0)

    def test_silence_below_floor(self):
        # Pure silence + tiny dither stays well under the floor.
        buf = (np.random.randn(16000) * 5).astype(np.int16)
        self.assertLess(_buffer_rms(buf), MIN_CAPTURE_RMS)

    def test_speech_level_above_floor(self):
        # A ~3000-amplitude tone is clearly above the speech floor.
        t = np.arange(16000)
        buf = (3000 * np.sin(2 * np.pi * 200 * t / 16000)).astype(np.int16)
        self.assertGreater(_buffer_rms(buf), MIN_CAPTURE_RMS)


class TestSilenceHallucination(unittest.TestCase):
    def test_known_artifacts_flagged(self):
        for txt in (
            "¡Suscríbete!", "Suscríbete", "Gracias por ver",
            "Gracias por ver el video", "Subtítulos realizados por la comunidad de Amara.org",
            "Thanks for watching", "Subscribe", "you",
        ):
            self.assertTrue(_is_silence_hallucination(txt), f"missed: {txt!r}")

    def test_accents_and_case_insensitive(self):
        self.assertTrue(_is_silence_hallucination("SUSCRÍBETE"))
        self.assertTrue(_is_silence_hallucination("gracias por ver el video."))

    def test_real_commands_not_flagged(self):
        for txt in (
            "abre Steam", "pon el volumen al 30", "hey gemma abre la calculadora",
            "gracias, ahora pon música",  # "gracias" as substring of a real cmd
            "suscríbete a este canal de YouTube",  # real multi-word request
            "reproduce la siguiente canción",
        ):
            self.assertFalse(_is_silence_hallucination(txt), f"false positive: {txt!r}")

    def test_empty_not_flagged(self):
        self.assertFalse(_is_silence_hallucination(""))
        self.assertFalse(_is_silence_hallucination("   "))


class TestTtsBusyGrace(unittest.TestCase):
    """is_busy() must stay True across synth+play and through the tail grace,
    not flip to False the instant the queue drains."""

    def _fresh_tts(self):
        t = tts_mod.StreamingTTS.__new__(tts_mod.StreamingTTS)
        # Minimal field init without loading Piper.
        t._running = True
        t._muted = False
        from queue import Queue
        t._queue = Queue()
        t._synthesizing = False
        t._last_audio_ts = 0.0
        t._streaming = False
        t._last_feed_ts = 0.0
        return t

    def test_busy_while_streaming_even_if_queue_empty(self):
        import time
        t = self._fresh_tts()
        t._streaming = True
        t._last_feed_ts = time.monotonic()
        self.assertTrue(t._queue.empty() and not t._synthesizing)
        self.assertTrue(t.is_busy(), "busy mientras streamea: puentea el hueco entre frases")

    def test_not_busy_when_streaming_stale(self):
        import time
        t = self._fresh_tts()
        t._streaming = True
        t._last_feed_ts = time.monotonic() - (tts_mod.STREAM_STALE_S + 1.0)
        self.assertFalse(t.is_busy(), "stale-guard: una respuesta colgada NO mutea para siempre")

    def test_busy_while_synthesizing_even_if_queue_empty(self):
        t = self._fresh_tts()
        self.assertTrue(t._queue.empty())
        t._synthesizing = True
        self.assertTrue(t.is_busy(), "must be busy while synthesizing")

    def test_busy_during_tail_grace(self):
        import time
        t = self._fresh_tts()
        t._synthesizing = False
        t._last_audio_ts = time.monotonic()  # just finished
        self.assertTrue(t.is_busy(), "must be busy during tail grace")

    def test_idle_after_grace(self):
        import time
        t = self._fresh_tts()
        t._synthesizing = False
        t._last_audio_ts = time.monotonic() - (tts_mod.TTS_TAIL_GRACE_S + 0.2)
        self.assertFalse(t.is_busy(), "should be idle after grace elapsed")

    def test_not_busy_when_stopped(self):
        t = self._fresh_tts()
        t._running = False
        t._synthesizing = True
        self.assertFalse(t.is_busy())


class TestStreamingFirstChunk(unittest.TestCase):
    """Streaming first-audio (2026-05-20 latency): the opening clause must flush
    to the synth queue BEFORE the sentence closes, so Piper starts speaking ~1-2s
    sooner. After the first chunk, full-sentence chunking resumes."""

    def _fresh(self):
        from queue import Queue
        t = tts_mod.StreamingTTS.__new__(tts_mod.StreamingTTS)
        t._loaded = True
        t._muted = False
        t._buffer = ""
        t._queue = Queue()
        t._first_chunk_done = False
        return t

    def _drain(self, t):
        out = []
        while not t._queue.empty():
            out.append(t._queue.get())
        return out

    def test_opening_clause_flushes_early(self):
        t = self._fresh()
        seq = []
        for tok in ["Listo", ", ", "abrí ", "Steam ", "y ", "busqué ", "gatos."]:
            if t.feed_text(tok):
                seq += self._drain(t)
        seq += self._drain(t)
        t.flush()
        seq += self._drain(t)
        # First queued chunk is the opening clause, not the whole sentence.
        self.assertTrue(seq, "nothing queued")
        self.assertEqual(seq[0], "Listo,")
        # The rest comes as a sentence chunk, in order, nothing lost.
        self.assertIn("Steam", " ".join(seq))
        self.assertIn("gatos", " ".join(seq))

    def test_only_first_chunk_uses_clause_path(self):
        # After the first clause flush, a later comma must NOT fragment.
        t = self._fresh()
        seq = []
        for tok in ["Bien", ", ", "ahora ", "subo ", "el ", "volumen, ", "ok."]:
            if t.feed_text(tok):
                seq += self._drain(t)
        t.flush()
        seq += self._drain(t)
        self.assertEqual(seq[0], "Bien,")
        # "volumen, ok." stays together (not split at the 2nd comma).
        self.assertTrue(any("volumen" in c and "ok" in c for c in seq[1:]),
                        f"second clause was fragmented: {seq}")

    def test_short_reply_no_clause_flushes_on_flush(self):
        t = self._fresh()
        self.assertEqual(t.feed_text("Hola"), 0)  # nothing closed yet
        self.assertEqual(t.flush(), 1)
        self.assertEqual(self._drain(t), ["Hola"])

    def test_first_chunk_rearmed_after_flush(self):
        t = self._fresh()
        for tok in ["Listo", ", ", "hecho."]:
            t.feed_text(tok)
        t.flush(); self._drain(t)
        # Next utterance: first-chunk fast path must be armed again.
        self.assertFalse(t._first_chunk_done)
        seq = []
        for tok in ["Vale", ", ", "abro."]:
            if t.feed_text(tok):
                seq += self._drain(t)
        self.assertEqual(seq[0], "Vale,")

    def test_full_reply_fed_at_once_preserves_all_text(self):
        # agent_runner.py feeds the WHOLE reply in one feed_tts() then flush_tts()
        # (not token-by-token). The first-chunk path must still emit the opening
        # clause early AND preserve every word in order (nothing dropped/dup'd).
        import re
        t = self._fresh()
        reply = "Listo, abrí Spotify y puse tu playlist. ¿Algo más?"
        t.feed_text(reply)
        t.flush()
        seq = self._drain(t)
        self.assertEqual(seq[0], "Listo,", "opening clause must flush first")
        words = lambda s: re.findall(r"\w+", s.lower())
        self.assertEqual(words(" ".join(seq)), words(reply),
                         "every word of the reply must survive, in order")


if __name__ == "__main__":
    unittest.main()
