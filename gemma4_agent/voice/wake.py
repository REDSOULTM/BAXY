"""Wake-word detection via openWakeWord.

Sprint VoiceRedesign (2026-05-19): clean rebuild of the wake stack
after the v1-v7 fine-tune chain failed in production (false-positives
on ambient noise, single-voice overfit).

This module wraps openWakeWord with two specific operating modes:

  (1) STOCK: load openWakeWord's pretrained "hey_jarvis" model. Used as
      a working placeholder until the custom "hey_gemma" model is
      trained (planned Sprint 4 with Piper-synthesised dataset).
      The pretrained "hey_jarvis" has documented metrics:
        - 200k synthetic clips training set (LibriTTS + WAVEGLOW)
        - 0.187 false accepts/hr on Dinner Party Corpus
        - generalises to unseen voices (no per-user training needed)

  (2) CUSTOM: load `~/.gemma4/models/oww/hey_gemma.onnx` if present.
      The build pipeline (Sprint 4) will synthesise 100k+ Hispanic-
      pronounced "hey gemma" samples via Piper Spanish voices,
      merge with English negatives, and train a small head on the
      frozen Google speech embedding backbone.

API contract (matches AudioCapture.on_chunk):
  - feed(chunk: np.ndarray) — int16, mono, 16 kHz; ANY size accepted.
    Internal buffer accumulates to openWakeWord's 1280-sample (80 ms)
    window.
  - on_wake callback signature: (phrase: str, score: float).

Design vs the deleted v1:
  - NO debounce inside the wake detector. End-of-command is detected
    by Silero VAD downstream, not by post-fire silence wait.
  - NO env-var threshold default 0.7. Default is 0.5 (openWakeWord's
    own default). The cascade VAD + verifier provides robustness;
    threshold tuning is a band-aid.
  - NO duplicate firings within 240 ms (single physical cooldown to
    prevent the same utterance triggering twice during the same
    speech segment; smaller than the old 0.8s "debounce" hack).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np

logger = logging.getLogger(__name__)

# openWakeWord internal window size at 16 kHz: 80 ms = 1280 samples.
OWW_WINDOW_SAMPLES = 1280

# Score above which we fire. openWakeWord upstream default = 0.5.
# Operator can override via env var; not exposed as constructor arg
# because the env override applies process-wide.
import os
OWW_THRESHOLD = float(os.environ.get("GEMMA4_OWW_THRESHOLD", "0.5"))

# Minimum gap between two fires of the SAME phrase. Smaller than the
# old debounce because the upstream VAD gate + state-machine CAPTURE
# state already provide back-pressure. This is just to avoid the SAME
# wake utterance firing 3-4 times across consecutive 80 ms windows.
SAME_PHRASE_COOLDOWN_S = 0.24

# Where the custom-trained model goes once Sprint 4 produces it.
CUSTOM_MODEL_PATH = (
    Path(__file__).resolve().parent / "models" / "oww" / "hey_gemma.onnx"
)
# Stock model name in openWakeWord's bundled catalog (the model with
# the best documented FA/hr on benchmark sets).
STOCK_MODEL_NAME = "hey_jarvis"


WakeCallback = Callable[[str, float], None]


class WakeDetector:
    """openWakeWord wrapper. Prefers custom model, falls back to stock.

    Lifecycle:
        det = WakeDetector(on_wake=fn)
        ok = det.load()      # loads model, downloads if needed
        det.feed(chunk)      # call from AudioPump for each 512-sample chunk
        det.reset()          # clear buffer when starting fresh
    """

    def __init__(self, on_wake: WakeCallback) -> None:
        self._on_wake = on_wake
        self._model: Any = None
        self._model_score_key: str = ""
        self._loaded: bool = False
        self._buf: np.ndarray = np.zeros(0, dtype=np.int16)
        self._last_fire_at: float = 0.0
        self.last_error: str | None = None
        self.using_custom_model: bool = False

    # ----- lifecycle ---------------------------------------------------

    def load(self) -> bool:
        if self._loaded:
            return True
        try:
            from openwakeword import Model
            from openwakeword.utils import download_models
        except Exception as exc:
            self.last_error = f"openwakeword unavailable: {exc}"
            logger.error(self.last_error)
            return False

        # Try custom model first.
        try:
            if CUSTOM_MODEL_PATH.exists():
                logger.info(
                    "WakeDetector: loading custom model %s",
                    CUSTOM_MODEL_PATH,
                )
                self._model = Model(
                    wakeword_models=[str(CUSTOM_MODEL_PATH)],
                    inference_framework="onnx",
                )
                # Custom model exports use the file stem as key.
                self._model_score_key = CUSTOM_MODEL_PATH.stem  # "hey_gemma"
                self.using_custom_model = True
                self._loaded = True
                logger.info("WakeDetector ready (custom hey_gemma)")
                return True
        except Exception as exc:
            logger.warning(
                "Custom model load failed, falling back to stock: %s",
                exc,
            )

        # Fall back to stock hey_jarvis.
        try:
            # Ensure the stock models are downloaded.
            download_models()
            self._model = Model(
                wakeword_models=[STOCK_MODEL_NAME],
                inference_framework="onnx",
            )
            self._model_score_key = STOCK_MODEL_NAME
            self.using_custom_model = False
            self._loaded = True
            logger.warning(
                "WakeDetector ready (FALLBACK to stock '%s'). "
                "Train custom hey_gemma.onnx for production. "
                "See docs/architecture/voice_pipeline_redesign_research_report.md",
                STOCK_MODEL_NAME,
            )
            return True
        except Exception as exc:
            self.last_error = f"WakeDetector init failed: {type(exc).__name__}: {exc}"
            logger.error(self.last_error)
            self._model = None
            self._loaded = False
            return False

    def reset(self) -> None:
        """Clear the rolling buffer and cooldown. Call between sessions."""
        self._buf = np.zeros(0, dtype=np.int16)
        self._last_fire_at = 0.0
        if self._model is not None:
            try:
                self._model.reset()
            except Exception:
                pass

    # ----- inference ---------------------------------------------------

    def feed(self, chunk: np.ndarray) -> None:
        """Append `chunk` (int16, mono, 16 kHz, any size) and predict
        on every full 80 ms (1280-sample) window."""
        if not self._loaded or self._model is None:
            return
        try:
            chunk_i16 = np.asarray(chunk, dtype=np.int16)
        except Exception as exc:
            logger.warning("WakeDetector.feed: coercion failed: %s", exc)
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
            logger.warning("openwakeword predict failed: %s", exc)
            return
        score = float(scores.get(self._model_score_key, 0.0))
        if score < OWW_THRESHOLD:
            return
        now = time.monotonic()
        if now - self._last_fire_at < SAME_PHRASE_COOLDOWN_S:
            return
        self._last_fire_at = now
        phrase = "hey gemma" if self.using_custom_model else "hey jarvis"
        logger.info(
            "wake_word_fired phrase=%s score=%.3f threshold=%.3f "
            "model=%s",
            phrase, score, OWW_THRESHOLD,
            "custom" if self.using_custom_model else "stock",
        )
        try:
            self._on_wake(phrase, score)
        except Exception as exc:
            logger.warning("on_wake callback raised: %s", exc)
