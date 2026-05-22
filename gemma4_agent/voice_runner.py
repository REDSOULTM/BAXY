"""Voice runner — single entry point that wires VoicePipeline + TTS into
the agent.

Sprint 2 of the voice redesign. Replaces the previous voice_runner.py
(deleted in the clean-slate commit b098e22) with a thin wrapper that:

  - Owns the VoicePipeline (mic → VAD → wake → STT → corrector).
  - Owns the StreamingTTS (Piper output).
  - Exposes a singleton VOICE for server.py / agent_runner.py /
    main_window.py.
  - Mutes the wake detector while TTS is playing (software barge-in
    avoidance per research report C.6 plan A).

Public API (preserved from the deleted voice_runner.py shape, so
server.py and agent_runner.py call sites don't need a second rewrite):

  VOICE.enable()                  → bool, idempotent boot
  VOICE.disable()                 → idempotent shutdown
  VOICE.status()                  → dict (UI consumes)
  VOICE.trigger_manual()          → push-to-talk (synthesises a wake)
  VOICE.feed_tts(text_chunk)      → LLM streams TTS through us
  VOICE.set_on_command(callback)  → register where transcribed commands go
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from .voice.pipeline import VoicePipeline
from .voice.tts import StreamingTTS

logger = logging.getLogger(__name__)


CommandCallback = Callable[[str], None]


class VoiceRunner:
    """Singleton. Owns the pipeline + TTS + their inter-coupling."""

    _instance: "VoiceRunner | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "VoiceRunner":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self) -> None:
        self._pipeline: VoicePipeline | None = None
        self._tts: StreamingTTS | None = None
        self._on_command: CommandCallback | None = None
        self._on_state: Callable[[str], None] | None = None
        self._on_wake_event: Callable[[], None] | None = None
        self._enabled: bool = False
        self._loading: bool = False
        self.last_error: str | None = None

    # ------ lifecycle -------------------------------------------------

    def enable(self) -> bool:
        """Load + start the pipeline. Idempotent. Blocking (1-3s)."""
        if self._enabled:
            return True
        if self._loading:
            # Another thread is loading; wait quickly.
            return False
        self._loading = True
        try:
            # TTS first (cheap to load; doesn't open mic).
            if self._tts is None:
                self._tts = StreamingTTS()
                if not self._tts.load():
                    logger.warning(
                        "TTS load failed (voice will work without speech "
                        "output): %s", self._tts.last_error,
                    )
                else:
                    self._tts.start()
            elif self._tts.is_loaded():
                # Re-enable after a disable(): disable() called _tts.stop()
                # which killed the worker thread. start() is idempotent (no-ops
                # if already running) — without this call the TTS queue is never
                # consumed again and the agent goes MUTE on every voice off/on
                # cycle. (Sibling of the 'TTS mudo sin flush' lifecycle gap.)
                self._tts.start()
            # Pipeline (loads VAD, wake, STT models; ~1-3s blocking).
            if self._pipeline is None:
                self._pipeline = VoicePipeline(
                    on_command=self._handle_command,
                    on_state=self._handle_state,
                    on_wake_event=self._handle_wake_event,
                )
                # Wire TTS-busy signal so the wake detector pauses
                # while Piper is speaking (echo avoidance).
                self._pipeline.set_tts_busy_fn(self._is_tts_busy)
            if not self._pipeline.load():
                self.last_error = self._pipeline.last_error
                logger.error("Pipeline load failed: %s", self.last_error)
                return False
            if not self._pipeline.start():
                self.last_error = self._pipeline.last_error
                logger.error("Pipeline start failed: %s", self.last_error)
                return False
            self._enabled = True
            logger.info("VoiceRunner enabled")
            return True
        finally:
            self._loading = False

    def disable(self) -> None:
        """Idempotent shutdown."""
        if self._pipeline is not None:
            self._pipeline.stop()
        if self._tts is not None:
            try:
                self._tts.stop()
            except Exception:
                pass
        self._enabled = False
        logger.info("VoiceRunner disabled")

    # ------ status (UI) -----------------------------------------------

    def status(self) -> dict[str, Any]:
        """Shape compatible with the old runner so server.py doesn't change."""
        if self._pipeline is None:
            wake_label = "not_loaded"
        else:
            wake_label = "custom_hey_gemma" if (
                self._pipeline._wake.using_custom_model
            ) else "stock_hey_jarvis"
        return {
            "enabled": self._enabled,
            "running": self._enabled,
            "wake_loaded": self._pipeline is not None and self._pipeline._wake._loaded,
            "stt_loaded": self._pipeline is not None and self._pipeline._stt._loaded,
            "tts_loaded": self._tts is not None and self._tts.is_loaded(),
            "wake_model": wake_label,
            "state": self._pipeline.state.value if self._pipeline else "off",
            "last_error": self.last_error,
        }

    # ------ command path (mic → text → callback) ----------------------

    def set_on_command(self, cb: CommandCallback) -> None:
        """Register where transcribed commands go (the agent runner sets
        this to enqueue a turn)."""
        self._on_command = cb

    def set_on_state(self, cb: Callable[[str], None] | None) -> None:
        """Register a UI callback fired on every pipeline state change
        (IDLE_LISTENING / LISTENING / TRANSCRIBING). Lets the HUD animate."""
        self._on_state = cb

    def set_on_wake_event(self, cb: Callable[[], None] | None) -> None:
        """Register a UI callback fired the instant the wake word triggers
        (used for the beep / visual 'I heard you' feedback)."""
        self._on_wake_event = cb

    def _handle_state(self, state: str) -> None:
        cb = getattr(self, "_on_state", None)
        if cb is None:
            return
        try:
            cb(state)
        except Exception as exc:
            logger.debug("on_state callback raised: %s", exc)

    def _handle_wake_event(self) -> None:
        cb = getattr(self, "_on_wake_event", None)
        if cb is None:
            return
        try:
            cb()
        except Exception as exc:
            logger.debug("on_wake_event callback raised: %s", exc)

    def _handle_command(self, text: str, audio_secs: float, raw_text: str) -> None:
        """Pipeline callback. Dispatches to the registered on_command."""
        logger.info(
            "voice command: %r (audio=%.2fs, raw=%r)",
            text, audio_secs, raw_text[:80],
        )
        cb = self._on_command
        if cb is None:
            logger.warning("voice command received but no on_command registered")
            return
        try:
            cb(text)
        except Exception as exc:
            logger.exception("on_command callback raised: %s", exc)

    def trigger_manual(self) -> None:
        """Push-to-talk: simulate a wake. NOT YET IMPLEMENTED in v2 — the
        new state machine doesn't expose a clean injection point yet.
        Returns silently; UI will see no state change."""
        logger.info("trigger_manual: not implemented in v2 pipeline yet")

    # ------ TTS path (agent reply → speech) ---------------------------

    def feed_tts(self, text_chunk: str) -> int:
        """Feed an LLM token/chunk to the TTS queue.

        Mutes the wake detector implicitly because the TTS audio comes
        out the same speakers the mic listens to. Without echo
        cancellation, hearing 'gemma' in the TTS would self-trigger.
        For v1 we do simple software-mute: while is_busy(), the
        pipeline's wake detector pauses (wired via set_tts_busy_fn in
        enable()).
        """
        if self._tts is None or not self._tts.is_loaded():
            return 0
        return self._tts.feed_text(text_chunk)

    def flush_tts(self) -> int:
        """Force any buffered partial sentence to be spoken. The agent's
        reply often doesn't end in . ? ! so feed_text leaves it in the
        buffer; call this at end-of-reply so the tail is never dropped."""
        if self._tts is None or not self._tts.is_loaded():
            return 0
        try:
            return self._tts.flush()
        except Exception:
            return 0

    def _is_tts_busy(self) -> bool:
        """Pipeline polls this to decide whether to pause wake
        detection. Returns True while the Piper queue has unspoken
        text OR while a sentence is being synthesised."""
        if self._tts is None:
            return False
        try:
            return bool(self._tts.is_busy())
        except Exception:
            return False


# Module-level singleton matching the old API.
VOICE = VoiceRunner.get()
