"""Per-turn voice session recorder.

Hotfix L 2026-05-17. The operator wants every voice session
persisted to disk as a future training set (Whisper fine-tuning,
wake detector calibration, e2e latency analysis).

Capture model (option B, agreed in design):
  - START: when wake-word is detected. Includes a 500ms pre-wake
    tail from the mic ring buffer (lets us audit false wakes).
  - END: when TTS playback finishes for the same turn. Captures
    user speech, VAD silence, agent reply synth.
  - Two files per turn:
      <session>/<turn>.user.wav  - raw mic, full window.
      <session>/<turn>.tts.wav   - Piper synth output (only if
                                   TTS ran; otherwise absent).
  - One manifest entry per turn appended to
    <session>/manifest.jsonl.

Format:
  - WAV PCM 16-bit, 16 kHz, mono. No compression. Whisper and
    every other STT toolchain reads it directly.

Privacy / opt-out:
  - Default ON. Disable per-process with GEMMA4_RECORD_AUDIO=0
    or =false or =off.
  - Failure-tolerant: if the recordings dir can't be created
    (disk full, permission), log a warning and disable for the
    rest of the process. NEVER raise into the voice pipeline.

Threading:
  - All disk I/O happens on a single background writer thread
    per recorder instance. The mic callback / TTS playback only
    enqueue (np.ndarray, key) tuples; the writer drains the
    queue and appends to the appropriate file.
  - If the queue saturates (writer too slow), DROP chunks and
    log a warning. The voice pipeline must never block.
"""
from __future__ import annotations

import json
import logging
import os
import queue as _queue
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .audio_io import SAMPLE_RATE

logger = logging.getLogger(__name__)

RECORDINGS_DIR = Path.home() / ".gemma4" / "recordings"

# Drop chunks if the writer queue grows past this many entries.
# At 16 kHz mono int16, 32ms chunks: ~1024 bytes/chunk. 2000
# pending = ~2 MB lag tolerance, ~64 sec of audio queued.
_MAX_QUEUE = 2000

# Pre-wake tail capture window. The mic ring buffer is short
# (audio_io.RING_BUFFER_CHUNKS) so we don't try to read more
# than it actually holds.
PRE_WAKE_TAIL_S = 0.5


@dataclass
class _ActiveTurn:
    """In-flight recording state for one turn."""
    session_id: str
    turn_id: str
    started_at: float
    wake_phrase: str
    wake_confidence: float
    user_path: Path
    tts_path: Path
    manifest_path: Path
    # Open WAV writers. Lazy-created on first chunk so we don't
    # produce 44-byte empty WAVs for turns that get cancelled.
    user_writer: Any = None
    tts_writer: Any = None
    user_samples_written: int = 0
    tts_samples_written: int = 0
    extra_metadata: dict[str, Any] = field(default_factory=dict)


def is_enabled() -> bool:
    """True iff recording is opt-in / on by default and not
    explicitly disabled."""
    raw = (os.environ.get("GEMMA4_RECORD_AUDIO") or "").strip().lower()
    return raw not in {"0", "false", "no", "off"}


class VoiceRecorder:
    """Per-process voice session recorder. Thread-safe.

    Lifecycle:
      enable()                - create recordings dir, start
                                writer thread. Idempotent.
      start_turn(...)         - open a new turn for capture.
                                Pre-wake tail is captured here.
      capture_user_chunk(...) - enqueue a mic chunk for the
                                active turn (no-op if no turn).
      capture_tts_chunk(...)  - enqueue a TTS chunk.
      finish_turn(...)        - close writers, append manifest
                                entry, drop active turn.
      shutdown()              - finish active turn (if any),
                                stop writer thread.
    """
    _instance: "VoiceRecorder | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "VoiceRecorder":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self) -> None:
        self._session_id: str | None = None
        self._active_turn: _ActiveTurn | None = None
        self._enabled = False
        self._init_failed = False
        self._writer_queue: _queue.Queue[tuple[str, np.ndarray | None]] = _queue.Queue(maxsize=_MAX_QUEUE)
        self._writer_thread: threading.Thread | None = None
        self._writer_lock = threading.Lock()
        self._dropped_chunks = 0

    def enable(self, session_id: str | None = None) -> bool:
        """Idempotent. Creates RECORDINGS_DIR if needed and starts
        the writer thread. Returns True if enabled, False if
        disabled or init failed.
        """
        if not is_enabled():
            return False
        if self._init_failed:
            return False
        try:
            RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("voice_recorder_init_failed dir=%s error=%s",
                           RECORDINGS_DIR, exc)
            self._init_failed = True
            return False
        if session_id:
            self._session_id = session_id
        elif self._session_id is None:
            self._session_id = time.strftime("%Y%m%d_%H%M%S")
        # Per-session subdirectory.
        try:
            (RECORDINGS_DIR / self._session_id).mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("voice_recorder_session_dir_failed error=%s", exc)
            self._init_failed = True
            return False
        # Writer thread (singleton).
        if self._writer_thread is None or not self._writer_thread.is_alive():
            self._writer_thread = threading.Thread(
                target=self._writer_loop,
                name="voice-recorder-writer",
                daemon=True,
            )
            self._writer_thread.start()
        self._enabled = True
        return True

    def start_turn(
        self,
        turn_id: str,
        wake_phrase: str = "",
        wake_confidence: float = 0.0,
        pre_wake_audio: np.ndarray | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Open a new turn for capture. Closes any in-flight turn
        first (defensive: should not normally happen)."""
        if not self._enabled:
            return
        if self._active_turn is not None:
            logger.warning("voice_recorder_turn_overlap previous=%s new=%s",
                           self._active_turn.turn_id, turn_id)
            self.finish_turn(reason="overlapping_new_turn")
        if self._session_id is None:
            return
        session_dir = RECORDINGS_DIR / self._session_id
        turn = _ActiveTurn(
            session_id=self._session_id,
            turn_id=turn_id,
            started_at=time.time(),
            wake_phrase=wake_phrase,
            wake_confidence=float(wake_confidence),
            user_path=session_dir / f"{turn_id}.user.wav",
            tts_path=session_dir / f"{turn_id}.tts.wav",
            manifest_path=session_dir / "manifest.jsonl",
            extra_metadata=dict(extra_metadata or {}),
        )
        with self._writer_lock:
            self._active_turn = turn
        # Pre-wake tail goes in as the first chunks.
        if pre_wake_audio is not None and pre_wake_audio.size > 0:
            self.capture_user_chunk(pre_wake_audio)

    def capture_user_chunk(self, chunk: np.ndarray) -> None:
        """Enqueue a mic chunk for the active turn. No-op if
        recording is off or no turn is active."""
        if not self._enabled or self._active_turn is None:
            return
        try:
            self._writer_queue.put_nowait(("user", chunk))
        except _queue.Full:
            self._dropped_chunks += 1
            if self._dropped_chunks % 100 == 1:
                logger.warning(
                    "voice_recorder_queue_full dropped_chunks=%d",
                    self._dropped_chunks,
                )

    def capture_tts_chunk(self, chunk: np.ndarray) -> None:
        """Enqueue a TTS chunk for the active turn."""
        if not self._enabled or self._active_turn is None:
            return
        try:
            self._writer_queue.put_nowait(("tts", chunk))
        except _queue.Full:
            self._dropped_chunks += 1

    def annotate_turn(self, **fields: Any) -> None:
        """Attach arbitrary key/value metadata to the active turn.
        Goes into the manifest entry on finish_turn. Caller is
        responsible for using JSON-serializable values.
        """
        if not self._enabled or self._active_turn is None:
            return
        with self._writer_lock:
            if self._active_turn is not None:
                self._active_turn.extra_metadata.update(fields)

    def finish_turn(self, reason: str = "tts_finished") -> None:
        """Close writers and append manifest entry for the active
        turn. Safe to call when no turn is active."""
        if not self._enabled:
            return
        with self._writer_lock:
            turn = self._active_turn
            self._active_turn = None
        if turn is None:
            return
        # Drain by waiting briefly for the queue. We close writers
        # from here because the writer thread doesn't keep file
        # handles per turn after the active_turn is gone.
        deadline = time.time() + 2.0
        while not self._writer_queue.empty() and time.time() < deadline:
            time.sleep(0.05)
        # Close writers (if any chunks made them open).
        for writer in (turn.user_writer, turn.tts_writer):
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass
        # Append manifest.
        try:
            entry = {
                "session_id": turn.session_id,
                "turn_id": turn.turn_id,
                "started_at": turn.started_at,
                "finished_at": time.time(),
                "duration_s": time.time() - turn.started_at,
                "wake_phrase": turn.wake_phrase,
                "wake_confidence": turn.wake_confidence,
                "user_wav": turn.user_path.name if turn.user_samples_written > 0 else None,
                "user_samples": turn.user_samples_written,
                "tts_wav": turn.tts_path.name if turn.tts_samples_written > 0 else None,
                "tts_samples": turn.tts_samples_written,
                "finish_reason": reason,
                "whisper_transcription": turn.extra_metadata.pop(
                    "whisper_transcription", None),
                "stt_reject_reason": turn.extra_metadata.pop(
                    "stt_reject_reason", None),
                # Empty field for later manual correction in review.
                "manual_correction": "",
                "extra": turn.extra_metadata,
            }
            with open(turn.manifest_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("voice_recorder_manifest_write_failed error=%s", exc)

    def shutdown(self) -> None:
        """Stop the writer thread cleanly. Idempotent."""
        if self._active_turn is not None:
            self.finish_turn(reason="shutdown")
        if self._writer_thread is not None:
            try:
                self._writer_queue.put_nowait(("__stop__", None))
            except _queue.Full:
                pass
            self._writer_thread.join(timeout=2.0)
            self._writer_thread = None
        self._enabled = False

    def _writer_loop(self) -> None:
        """Drain the queue, opening WAV files lazily as chunks
        arrive. Runs until shutdown."""
        while True:
            try:
                item = self._writer_queue.get(timeout=0.5)
            except _queue.Empty:
                continue
            kind, chunk = item
            if kind == "__stop__":
                return
            with self._writer_lock:
                turn = self._active_turn
            if turn is None or chunk is None:
                continue
            try:
                if kind == "user":
                    if turn.user_writer is None:
                        turn.user_writer = self._open_wav(turn.user_path)
                    if turn.user_writer is not None:
                        self._write_chunk(turn.user_writer, chunk)
                        turn.user_samples_written += int(chunk.size)
                elif kind == "tts":
                    if turn.tts_writer is None:
                        turn.tts_writer = self._open_wav(turn.tts_path)
                    if turn.tts_writer is not None:
                        self._write_chunk(turn.tts_writer, chunk)
                        turn.tts_samples_written += int(chunk.size)
            except Exception as exc:
                logger.warning(
                    "voice_recorder_write_failed kind=%s error=%s",
                    kind, exc,
                )

    @staticmethod
    def _open_wav(path: Path) -> Any:
        """Open a WAV writer at SAMPLE_RATE, mono, 16-bit PCM."""
        try:
            w = wave.open(str(path), "wb")
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            return w
        except Exception as exc:
            logger.warning("voice_recorder_open_wav_failed path=%s error=%s",
                           path, exc)
            return None

    @staticmethod
    def _write_chunk(writer: Any, chunk: np.ndarray) -> None:
        if chunk.dtype != np.int16:
            chunk = chunk.astype(np.int16, copy=False)
        writer.writeframes(chunk.tobytes())
