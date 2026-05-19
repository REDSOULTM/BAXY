"""Voice pipeline orchestrator.

Composes audio_io → VAD → wake → state machine → STT → corrector
into a working voice-mode loop. Single state machine, single thread
(the AudioPump from audio_io.py).

States:
  IDLE      — listening for wake. VAD-gated wake detector runs.
  CAPTURE   — wake fired. Buffering command audio until end-of-speech.
  TRANSCRIBE— audio buffer being transcribed (blocking; brief).
  COOLDOWN  — small wait after transcribe to avoid immediate re-wake.

Callback API (on_command):
  on_command(text: str, audio_secs: float, raw_text: str) — called when
  a command is fully captured + transcribed + corrected. text is the
  final corrected version, raw_text is the pre-corrector Whisper output
  for debugging/observability.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from enum import Enum
from typing import Callable

import numpy as np

from .audio_io import AudioCapture, CHUNK_SAMPLES, SAMPLE_RATE
from .corrector import FuzzyCorrector
from .inventory import build_initial_prompt, get_inventory
from .stt import STT
from .vad import SileroVAD
from .wake import WakeDetector

logger = logging.getLogger(__name__)


# Default state machine timings.
PREROLL_SECONDS = 0.5            # audio kept before the wake event
COMMAND_TIMEOUT_S = 6.0          # hard cap on command length
END_OF_SPEECH_SILENCE_S = 0.7    # silence required to end CAPTURE
COOLDOWN_S = 0.4                 # post-transcribe wait

# VAD thresholds.
WAKE_GATE_THRESHOLD = 0.3        # let speech-y audio reach wake; reject ambient
EOS_VAD_THRESHOLD = 0.5          # stricter for end-of-speech


class State(Enum):
    IDLE = "idle"
    CAPTURE = "capture"
    TRANSCRIBE = "transcribe"
    COOLDOWN = "cooldown"


CommandCallback = Callable[[str, float, str], None]


class VoicePipeline:
    """Voice-mode loop.

    Usage:
        pipe = VoicePipeline(on_command=lambda text, dur, raw: print(text))
        pipe.start()        # blocks until pipe.stop() called elsewhere
        ...
        pipe.stop()
    """

    def __init__(self, on_command: CommandCallback) -> None:
        self._on_command = on_command
        self._vad = SileroVAD()
        self._wake = WakeDetector(on_wake=self._on_wake)
        self._stt = STT()
        inv = get_inventory()
        self._corrector = FuzzyCorrector(inv)
        self._initial_prompt = build_initial_prompt(inv)
        self._audio: AudioCapture | None = None

        # State machine state.
        self._state: State = State.IDLE
        self._state_lock = threading.Lock()

        # Optional: callable that returns True while the agent is
        # speaking (TTS busy). When set and returns True, wake detection
        # is paused to avoid self-triggering on Piper output going out
        # of the same speaker as the mic input. Research report C.6
        # plan A — software-mute path, no AEC dependency.
        self._tts_busy_fn: Callable[[], bool] | None = None

        # Pre-wake ring buffer (PREROLL_SECONDS worth of chunks).
        preroll_chunks = int(PREROLL_SECONDS * SAMPLE_RATE / CHUNK_SAMPLES)
        self._preroll: deque[np.ndarray] = deque(maxlen=preroll_chunks)

        # Command capture buffer (cleared on each capture start).
        self._capture_buf: list[np.ndarray] = []
        self._capture_start_ts: float = 0.0

        # End-of-speech detector: trailing silence accumulator.
        self._eos_silence_chunks_needed = int(
            END_OF_SPEECH_SILENCE_S * SAMPLE_RATE / CHUNK_SAMPLES
        )
        self._eos_silence_count: int = 0

        # Cooldown timer (set when entering COOLDOWN state).
        self._cooldown_until: float = 0.0

        self._loaded: bool = False
        self.last_error: str | None = None

    # ----- public API --------------------------------------------------

    def load(self) -> bool:
        if self._loaded:
            return True
        logger.info("VoicePipeline: loading components")
        if not self._vad.load():
            self.last_error = f"VAD load failed: {self._vad.last_error}"
            logger.warning(self.last_error)
            # Continue: VAD is optional (gate falls open if unavailable).
        if not self._wake.load():
            self.last_error = f"Wake load failed: {self._wake.last_error}"
            logger.error(self.last_error)
            return False
        if not self._stt.load():
            self.last_error = f"STT load failed: {self._stt.last_error}"
            logger.error(self.last_error)
            return False
        self._loaded = True
        logger.info(
            "VoicePipeline ready: wake=%s, model=%s",
            "custom" if self._wake.using_custom_model else "stock_hey_jarvis",
            self._stt._model_size,
        )
        return True

    def start(self) -> bool:
        if not self._loaded:
            if not self.load():
                return False
        self._audio = AudioCapture(on_chunk=self._on_chunk)
        ok = self._audio.start()
        if not ok:
            self.last_error = f"Audio start failed: {self._audio.last_error}"
            return False
        logger.info("VoicePipeline started (state=IDLE)")
        return True

    def stop(self) -> None:
        if self._audio is not None:
            self._audio.stop()
            self._audio = None
        logger.info("VoicePipeline stopped")

    @property
    def state(self) -> State:
        return self._state

    def set_tts_busy_fn(self, fn: Callable[[], bool] | None) -> None:
        """Register a callable that returns True while TTS is playing.
        The wake detector pauses while this returns True (software-mute
        echo avoidance, per research report C.6 plan A).
        """
        self._tts_busy_fn = fn

    # ----- audio chunk handler (runs in AudioPump thread) -------------

    def _on_chunk(self, chunk: np.ndarray) -> None:
        """Single entry point from audio_io. Dispatches based on state."""
        with self._state_lock:
            st = self._state
        try:
            if st == State.IDLE:
                self._handle_idle(chunk)
            elif st == State.CAPTURE:
                self._handle_capture(chunk)
            elif st == State.COOLDOWN:
                self._handle_cooldown(chunk)
            # TRANSCRIBE: do nothing here; the transcribe runs synchronously
            # in the same thread before transitioning out.
        except Exception as exc:
            logger.exception("on_chunk handler crashed: %s", exc)

    def _handle_idle(self, chunk: np.ndarray) -> None:
        """In IDLE, keep preroll updated and run wake detection.

        Sprint 5 fix (2026-05-19): the wake detector accumulates
        80 ms windows internally; if we drop chunks via a VAD gate
        upstream, we destroy that continuity and the wake never sees
        a complete window. Empirically this took recall from 7/105 to
        0/105 on Grabación (2).wav.

        Conclusion: feed wake EVERY chunk. The wake model's own
        threshold + the same_phrase_cooldown handle ambient-noise
        FP rejection adequately for v9. The VAD is still used DOWN-
        stream (end-of-speech detection during CAPTURE) where it
        belongs.
        """
        self._preroll.append(chunk)
        # Software-mute: pause wake detection while TTS is speaking.
        # Without echo cancellation, hearing 'gemma' in TTS output
        # would self-trigger via the mic.
        if self._tts_busy_fn is not None:
            try:
                if self._tts_busy_fn():
                    return
            except Exception:
                pass
        # Feed wake unconditionally — no VAD gate. See docstring.
        self._wake.feed(chunk)

    def _handle_capture(self, chunk: np.ndarray) -> None:
        """In CAPTURE, buffer audio. Detect end-of-speech via VAD silence."""
        self._capture_buf.append(chunk)
        # Hard timeout check.
        elapsed = time.monotonic() - self._capture_start_ts
        if elapsed > COMMAND_TIMEOUT_S:
            logger.info("command capture timeout @ %.2fs", elapsed)
            self._finish_capture(reason="timeout")
            return
        # End-of-speech via trailing silence.
        is_speech = self._vad.is_speech(chunk, threshold=EOS_VAD_THRESHOLD)
        if not is_speech:
            self._eos_silence_count += 1
            if self._eos_silence_count >= self._eos_silence_chunks_needed:
                logger.info(
                    "command end-of-speech detected after %.2fs",
                    elapsed,
                )
                self._finish_capture(reason="eos_silence")
        else:
            self._eos_silence_count = 0

    def _handle_cooldown(self, chunk: np.ndarray) -> None:
        """In COOLDOWN, just keep preroll updated. No wake detection."""
        self._preroll.append(chunk)
        if time.monotonic() >= self._cooldown_until:
            self._reset_to_idle("cooldown_done")

    # ----- state transitions ------------------------------------------

    def _on_wake(self, phrase: str, score: float) -> None:
        """Wake fired. Transition IDLE -> CAPTURE.

        Runs inside _handle_idle via wake._predict_window; we hold no
        lock here (the caller is single-threaded by design).
        """
        with self._state_lock:
            if self._state != State.IDLE:
                logger.debug("wake during state=%s, ignoring", self._state.value)
                return
            self._state = State.CAPTURE
        self._capture_start_ts = time.monotonic()
        self._eos_silence_count = 0
        # Seed capture buffer with preroll (so we don't lose the wake
        # phrase itself + any tail leakage).
        self._capture_buf = list(self._preroll)
        logger.info(
            "wake -> CAPTURE (phrase=%s score=%.3f preroll_chunks=%d)",
            phrase, score, len(self._capture_buf),
        )

    def _finish_capture(self, reason: str) -> None:
        """Transition CAPTURE -> TRANSCRIBE -> COOLDOWN."""
        with self._state_lock:
            if self._state != State.CAPTURE:
                return
            self._state = State.TRANSCRIBE
        audio = (np.concatenate(self._capture_buf)
                 if self._capture_buf else np.zeros(0, dtype=np.int16))
        dur = audio.size / SAMPLE_RATE
        self._capture_buf = []
        logger.info(
            "TRANSCRIBE start (reason=%s dur=%.2fs)", reason, dur,
        )
        t0 = time.time()
        raw_text = self._stt.transcribe(
            audio, initial_prompt=self._initial_prompt,
        )
        # Strip wake phrase + fuzzy correct.
        stripped = self._corrector.strip_wake_phrase(raw_text)
        corrected = self._corrector.correct(stripped)
        elapsed = time.time() - t0
        logger.info(
            "TRANSCRIBE done in %.2fs: raw=%r -> final=%r",
            elapsed, raw_text[:80], corrected[:80],
        )
        # Enter cooldown BEFORE the callback so a fast re-wake from the
        # LLM/TTS path doesn't race us.
        self._cooldown_until = time.monotonic() + COOLDOWN_S
        with self._state_lock:
            self._state = State.COOLDOWN
        # Reset wake buffer so leftover audio doesn't immediately re-fire.
        self._wake.reset()
        self._vad.reset()
        # Emit the command (callback may do heavy work; we're already
        # in COOLDOWN so re-wakes are gated until it completes).
        try:
            if corrected.strip():
                self._on_command(corrected, dur, raw_text)
            else:
                logger.info("empty transcript, no command emitted")
        except Exception as exc:
            logger.exception("on_command callback raised: %s", exc)

    def _reset_to_idle(self, reason: str) -> None:
        with self._state_lock:
            self._state = State.IDLE
        self._preroll.clear()
        self._capture_buf = []
        self._eos_silence_count = 0
        logger.debug("-> IDLE (%s)", reason)
