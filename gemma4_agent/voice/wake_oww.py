"""openWakeWord backend for wake-word detection (Sprint R2 + R3).

openWakeWord is a neural wake-word detector (ONNX). Unlike Vosk
(generic STT forced to wake-detection), it's trained specifically
on wake-word vs non-wake-word audio and exposes a continuous
0..1 score per chunk.

Sprint R3 2026-05-18: this module now auto-detects a custom
"hey_gemma.onnx" model at gemma4_agent/voice/models/oww/. If
present, it's used; if not, falls back to the upstream
"hey_jarvis" model with a warning. The custom model is the output
of scripts/notebooks/train_hey_gemma.ipynb (Colab); the pipeline
to produce it lives in scripts/build_wake_dataset.py. See
docs/architecture/wake_custom_training_path.md for the runbook.

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
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .audio_io import SAMPLE_RATE

logger = logging.getLogger(__name__)


# Sprint R3: where the custom-trained "hey_gemma" ONNX lives. If the
# file is present, we use it; otherwise we fall back to the upstream
# pre-trained model. The custom model is operator-output (not in
# git); see docs/architecture/wake_custom_training_path.md.
OWW_CUSTOM_MODEL_PATH = (
    Path(__file__).resolve().parent / "models" / "oww" / "hey_gemma.onnx"
)
OWW_FALLBACK_MODEL_NAME = "hey_jarvis"

# Operator can override either name (pre-trained) or path (custom)
# via env vars. GEMMA4_OWW_MODEL takes precedence over auto-detection.
OWW_MODEL_NAME = os.environ.get("GEMMA4_OWW_MODEL", "")

# Score threshold for triggering a wake. openWakeWord scores are
# in [0, 1]; the upstream default is 0.5.
# Operator can override via GEMMA4_OWW_THRESHOLD env var.
OWW_THRESHOLD = float(os.environ.get("GEMMA4_OWW_THRESHOLD", "0.6"))

# Sprint R3.1 hotfix 2 (2026-05-19): Silero VAD gate.
# After v7 reduced silence false-positives, the operator's sessions
# 20260519_123719 and _125212 still showed 6+ false wakes with
# confidences 0.63-0.75. Inspection showed those audios had ambient
# sound (rms 0.003-0.021): fan, AC, keyboard clicks, distant TV --
# ambient that triggers the wake model's spectral pattern matcher.
#
# Pure RMS gate didn't work: operator speech at conversational
# distance ranges from rms 0.001 to 0.10 -- can't pick a single
# threshold that allows speech but rejects ambient.
#
# Solution: use Silero VAD to detect if the window contains HUMAN
# VOICE specifically (not just any energy). Silero outputs a 0-1
# speech probability per chunk; we gate at 0.3 (operator's voice
# scores 0.7-0.95 reliably, ambient scores <0.4).
#
# Override via GEMMA4_OWW_VAD_MIN env var. Set to 0 to disable.
OWW_VAD_MIN = float(os.environ.get("GEMMA4_OWW_VAD_MIN", "0.3"))

# openWakeWord expects 1280-sample (80ms at 16kHz) chunks for
# inference. The audio pipeline feeds us CHUNK_SAMPLES=512 (32ms)
# chunks, so we accumulate into a 1280-sample buffer and predict
# whenever it fills.
OWW_WINDOW_SAMPLES = 1280

# Debounce window between consecutive triggers. Sprint R3.1 calibration
# (2026-05-19): with the custom hey_gemma.onnx model, debounce sweep over
# Grabación (2).wav (105 annotated wakes) showed:
#   debounce  recall  precision  F1
#   0.05      0.819   0.869      0.843
#   0.10      0.495   0.852      0.627
#   0.30      0.190   0.833      0.310
#   0.80      0.086   1.000      0.158  (matches Vosk-era default)
# The Vosk-era default 0.8s strangled the oww model's ability to detect
# wakes that fire across multiple sliding-window positions. Lowered to
# 0.05s -- the model's own prediction smoothness (score must stay above
# threshold for several consecutive chunks) prevents pathological
# self-triggering. Operator can override via GEMMA4_OWW_DEBOUNCE_S env var.
OWW_DEBOUNCE_S = float(os.environ.get("GEMMA4_OWW_DEBOUNCE_S", "0.05"))

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
        # Sprint R3.1 hotfix 2: lazy-loaded Silero VAD model used as
        # gate in _predict_window to reject non-speech audio.
        self._vad_model: Any = None
        self._vad_failed: bool = False
        # Phrase string passed to the on_wake callback. We use a
        # canonical "hey gemma" so downstream code (recorder
        # manifests, controller state) doesn't care which model
        # actually fired underneath.
        self._matched_phrase: str = "hey gemma"
        # The key under which the loaded model exposes its score
        # in Model.predict()'s dict. Populated by load() based on
        # which model actually got loaded (custom path vs upstream
        # name). Required because scores[name] uses the basename
        # for custom .onnx loads.
        self._model_name: str = ""

    def _resolve_model_spec(self) -> tuple[Any, str]:
        """Decide what to pass to openwakeword.Model(wakeword_models=[...])
        and what key to look up in the scores dict.

        Precedence:
          1. GEMMA4_OWW_MODEL env var (operator-forced).
          2. Custom file at OWW_CUSTOM_MODEL_PATH (Sprint R3 output).
          3. Pre-trained OWW_FALLBACK_MODEL_NAME ("hey_jarvis").

        Returns (wakeword_models_arg, score_key).
        """
        if OWW_MODEL_NAME:
            # Explicit env override -- could be name or path.
            override_path = Path(OWW_MODEL_NAME)
            if override_path.exists():
                return str(override_path), override_path.stem
            return OWW_MODEL_NAME, OWW_MODEL_NAME
        if OWW_CUSTOM_MODEL_PATH.exists():
            logger.info(
                "Loading custom hey_gemma model from %s",
                OWW_CUSTOM_MODEL_PATH,
            )
            return str(OWW_CUSTOM_MODEL_PATH), OWW_CUSTOM_MODEL_PATH.stem
        logger.warning(
            "Custom hey_gemma model not found at %s -- falling back to %s. "
            "Run Sprint R3 to train it.",
            OWW_CUSTOM_MODEL_PATH, OWW_FALLBACK_MODEL_NAME,
        )
        return OWW_FALLBACK_MODEL_NAME, OWW_FALLBACK_MODEL_NAME

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
            wakeword_arg, score_key = self._resolve_model_spec()
            self._model = Model(wakeword_models=[wakeword_arg])
            self._model_name = score_key
            self._loaded = True
            self.last_error = None
            self._buf = np.zeros(0, dtype=np.int16)
            self._last_fire_at = 0.0
            logger.info(
                "OpenWakeWordDetector loaded (model=%s, threshold=%.2f)",
                self._model_name, OWW_THRESHOLD,
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
        # Sprint R3.1 hotfix 2 (2026-05-19): Silero VAD gate.
        # Reject windows that don't contain human voice. Silero is
        # specifically trained to discriminate speech from ambient,
        # unlike pure RMS which can't tell soft speech from loud noise.
        if OWW_VAD_MIN > 0.0:
            if self._vad_model is None and not self._vad_failed:
                try:
                    from silero_vad import load_silero_vad
                    import torch as _torch
                    _torch.set_num_threads(1)
                    self._vad_model = load_silero_vad(onnx=True)
                except Exception as exc:
                    logger.warning("Silero VAD load failed; disabling VAD gate: %s", exc)
                    self._vad_failed = True
            if self._vad_model is not None:
                try:
                    import torch as _torch
                    window_f = window.astype(np.float32) / 32768.0
                    # Silero expects exactly 512 samples at 16kHz per
                    # forward pass. We have 1280 (80ms) — feed two
                    # consecutive halves and take the MAX (any half
                    # with speech keeps the window).
                    HALF = 512
                    max_prob = 0.0
                    for off in (0, len(window_f) - HALF):
                        sub = window_f[off:off + HALF]
                        if sub.shape[0] != HALF:
                            continue
                        p = float(self._vad_model(_torch.from_numpy(sub), 16000).item())
                        if p > max_prob:
                            max_prob = p
                    if max_prob < OWW_VAD_MIN:
                        return  # no human voice -- skip predict
                except Exception as exc:
                    logger.debug("VAD gate failed; passing through: %s", exc)
        try:
            scores = self._model.predict(window)
        except Exception as exc:
            logger.warning("oww predict failed: %s", exc)
            return
        score = float(scores.get(self._model_name, 0.0))
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
