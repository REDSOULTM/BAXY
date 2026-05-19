"""openWakeWord backend for wake-word detection (Sprint R2 2026-05-18).

openWakeWord is a neural wake-word detector (ONNX). Unlike Vosk
(generic STT forced to wake-detection), it's trained specifically
on wake-word vs non-wake-word audio and exposes a continuous
0..1 score per chunk.

No "hey gemma" pre-trained model exists upstream. This module uses
`hey_jarvis` as a phonetic surrogate. Custom training to a real
"hey gemma" model is documented in
docs/architecture/wake_custom_training_path.md (when applicable).

Public surface mirrors VoskWakeDetector:
  - OpenWakeWordDetector(on_wake)
  - .load() -> bool
  - .feed(chunk: np.ndarray)
  - .is_loaded() -> bool
  - .reset()
  - .unload()
  - .last_error

The orchestrator in wake.py picks between this and Vosk.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any, Callable

import numpy as np

from .audio_io import SAMPLE_RATE

logger = logging.getLogger(__name__)


# Model name from the upstream pre-trained set. This is a surrogate;
# custom "hey gemma" training is the follow-up sprint.
OWW_MODEL_NAME = os.environ.get("GEMMA4_OWW_MODEL", "hey_jarvis")

# Score threshold for triggering a wake. openWakeWord scores are
# in [0, 1]; the upstream default is 0.5. We expose this via env
# var so the operator can sweep it without recompiling.
OWW_THRESHOLD = float(os.environ.get("GEMMA4_OWW_THRESHOLD", "0.5"))

# openWakeWord expects 1280-sample (80ms at 16kHz) chunks for
# inference. The audio pipeline feeds us CHUNK_SAMPLES=512 (32ms)
# chunks, so we accumulate into a 1280-sample buffer and predict
# whenever it fills.
OWW_WINDOW_SAMPLES = 1280

# Debounce window between consecutive triggers (same value as Vosk
# for consistency in operator UX; spec says NOT to retune for oww).
OWW_DEBOUNCE_S = 0.8

# Heuristic tail used for the post-wake snapshot. Vosk computes
# this from word timestamps in the result; oww doesn't expose
# that, so we use a small constant. The controller's downstream
# logic clamps tail to a reasonable window anyway.
OWW_TAIL_S_HEURISTIC = 0.3


WakeCallback = Callable[[str, float, float, float], None]


def _ensure_openwakeword():
    """Import openwakeword; install on demand (operator install-auth
    granted per project memory)."""
    try:
        import openwakeword  # type: ignore
        return openwakeword
    except ImportError:
        logger.info("Installing openwakeword (one-time)...")
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "openwakeword"]
        )
        import openwakeword  # type: ignore
        return openwakeword


class OpenWakeWordDetector:
    """openWakeWord wake-word backend.

    NOT used directly by the controller -- the WakeDetector
    orchestrator in wake.py composes it alongside the Vosk
    fallback.
    """

    def __init__(self, on_wake: WakeCallback) -> None:
        self._on_wake = on_wake
        self._model: Any = None
        self._loaded: bool = False
        self.last_error: str | None = None
        self._last_fire_at: float = 0.0
        # Accumulator for the 80ms windows openWakeWord wants.
        self._buf: np.ndarray = np.zeros(0, dtype=np.int16)
        # Phrase string passed to the on_wake callback. We use a
        # canonical "hey gemma" so downstream code (recorder
        # manifests, controller state) doesn't care which model
        # actually fired underneath.
        self._matched_phrase: str = "hey gemma"

    def load(self) -> bool:
        """Try to import openwakeword and instantiate the model.

        Downloads models on first use (~10MB) via
        openwakeword.utils.download_models(). Subsequent loads use
        the cached files.
        """
        try:
            _ensure_openwakeword()
            # Import after the install side-effect above.
            from openwakeword.model import Model  # type: ignore
            from openwakeword.utils import download_models  # type: ignore
        except Exception as exc:
            self.last_error = f"openwakeword unavailable: {exc}"
            logger.warning(self.last_error)
            return False

        try:
            # Idempotent; first call downloads, subsequent are no-op.
            download_models()
        except Exception as exc:
            # Non-fatal -- maybe the cache already has them.
            logger.debug("openwakeword download_models() raised: %s", exc)

        try:
            self._model = Model(wakeword_models=[OWW_MODEL_NAME])
            self._loaded = True
            self.last_error = None
            self._buf = np.zeros(0, dtype=np.int16)
            self._last_fire_at = 0.0
            logger.info(
                "OpenWakeWordDetector loaded (model=%s, threshold=%.2f)",
                OWW_MODEL_NAME, OWW_THRESHOLD,
            )
            return True
        except Exception as exc:
            self.last_error = f"openwakeword init failed: {type(exc).__name__}: {exc}"
            logger.error(self.last_error)
            self._model = None
            self._loaded = False
            return False

    def is_loaded(self) -> bool:
        return self._loaded

    def feed(self, chunk: np.ndarray) -> None:
        """Append `chunk` (int16, mono, 16kHz) to the rolling buffer
        and run the predictor on every full 80ms window.

        On a score >= OWW_THRESHOLD and outside the debounce window,
        invokes the configured callback with the canonical phrase
        "hey gemma".
        """
        if not self._loaded or self._model is None:
            return
        # Accept any sensible chunk size; oww only needs the
        # accumulated 1280 samples to be 16-bit mono 16kHz.
        try:
            chunk_i16 = np.asarray(chunk, dtype=np.int16)
        except Exception as exc:
            logger.warning("oww feed: chunk coercion failed: %s", exc)
            return
        if chunk_i16.size == 0:
            return
        self._buf = np.concatenate([self._buf, chunk_i16])
        while self._buf.size >= OWW_WINDOW_SAMPLES:
            window = self._buf[:OWW_WINDOW_SAMPLES]
            self._buf = self._buf[OWW_WINDOW_SAMPLES:]
            self._predict_window(window)

    def _predict_window(self, window: np.ndarray) -> None:
        try:
            scores = self._model.predict(window)
        except Exception as exc:
            logger.warning("oww predict failed: %s", exc)
            return
        score = float(scores.get(OWW_MODEL_NAME, 0.0))
        if score < OWW_THRESHOLD:
            return
        now = time.monotonic()
        if now - self._last_fire_at < OWW_DEBOUNCE_S:
            return
        self._last_fire_at = now
        # Privacy-safe wake_word_accepted event (same shape as
        # Vosk's emit at H/M.1 sprints).
        logger.warning(
            "wake_word_accepted confidence=%.3f threshold=%.3f tail_s=%.3f",
            score, OWW_THRESHOLD, OWW_TAIL_S_HEURISTIC,
        )
        try:
            self._on_wake(
                self._matched_phrase, now,
                OWW_TAIL_S_HEURISTIC, score,
            )
        except Exception as exc:
            logger.warning("on_wake callback raised: %s", exc)

    def reset(self) -> None:
        """Clear the rolling buffer and debounce timestamp. The
        oww model itself maintains internal state; we ask the
        upstream wrapper to reset it where supported."""
        self._buf = np.zeros(0, dtype=np.int16)
        self._last_fire_at = 0.0
        if self._model is not None:
            # Newer versions expose reset(); older don't. Be defensive.
            reset_fn = getattr(self._model, "reset", None)
            if callable(reset_fn):
                try:
                    reset_fn()
                except Exception as exc:
                    logger.debug("oww model.reset() raised: %s", exc)

    def unload(self) -> None:
        """Drop the model from RAM. Called when transitioning to
        LIGHT/STANDBY power modes."""
        self._model = None
        self._loaded = False
        self._buf = np.zeros(0, dtype=np.int16)
        self._last_fire_at = 0.0
