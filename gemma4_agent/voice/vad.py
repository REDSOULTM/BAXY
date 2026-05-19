"""Silero VAD — voice activity detection gate.

Used twice in the pipeline:
  1. Before openWakeWord: reject non-speech chunks so the wake model
     doesn't fire on fan/AC/keyboard ambient noise.
  2. After wake (during command capture): detect end-of-speech via a
     trailing silence window (default 700 ms).

Silero v5 expects EXACTLY 512 samples at 16 kHz per forward pass.
Output is a single float in [0, 1] = P(speech in this chunk).
Latency on CPU: < 1 ms per chunk per thread.

References:
  - Silero VAD: https://github.com/snakers4/silero-vad
  - openWakeWord uses Silero internally for the same gating pattern.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
SILERO_FRAME_SAMPLES = 512  # MANDATORY for v5; other sizes degrade


class SileroVAD:
    """Lazy-loaded Silero VAD ONNX model. Thread-safe for read-only use.

    Designed to fail gracefully: if torch / silero_vad are not installed,
    `load()` returns False and `is_speech()` returns True (gate-open
    fallback so the pipeline still works without VAD).
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._torch: Any = None
        self._loaded: bool = False
        self._failed: bool = False
        self.last_error: str | None = None

    def load(self) -> bool:
        if self._loaded:
            return True
        if self._failed:
            return False
        try:
            import torch  # noqa: F401
            from silero_vad import load_silero_vad
        except Exception as exc:
            self._failed = True
            self.last_error = f"silero-vad unavailable: {exc}"
            logger.warning(self.last_error)
            return False
        try:
            import torch as _torch
            # silero-vad CPU profile: pinning to a single thread avoids
            # GIL contention with the rest of the voice pipeline.
            _torch.set_num_threads(1)
            self._model = load_silero_vad(onnx=True)
            self._torch = _torch
            self._loaded = True
            logger.info("SileroVAD loaded (onnx)")
            return True
        except Exception as exc:
            self._failed = True
            self.last_error = f"silero-vad init failed: {exc}"
            logger.warning(self.last_error)
            return False

    def speech_prob(self, chunk: np.ndarray) -> float:
        """Return P(speech in chunk) ∈ [0, 1].

        chunk must be int16 mono at SAMPLE_RATE. Length must be 512 samples
        for v5 — other sizes raise or degrade. The caller (audio_io) gives
        us 512-sample chunks by design.
        """
        if not self._loaded:
            # Gate-open fallback: report "definitely speech" so downstream
            # doesn't get stuck if VAD is unavailable.
            return 1.0
        if chunk.shape[0] != SILERO_FRAME_SAMPLES:
            # Pad or trim to expected size. We log once at INFO so the
            # operator notices if the wiring drifts.
            if chunk.shape[0] < SILERO_FRAME_SAMPLES:
                chunk = np.pad(chunk, (0, SILERO_FRAME_SAMPLES - chunk.shape[0]))
            else:
                chunk = chunk[:SILERO_FRAME_SAMPLES]
        try:
            audio_f = chunk.astype(np.float32) / 32768.0
            t = self._torch.from_numpy(audio_f)
            return float(self._model(t, SAMPLE_RATE).item())
        except Exception as exc:
            logger.debug("silero forward failed: %s", exc)
            return 1.0  # gate open on error

    def is_speech(self, chunk: np.ndarray, threshold: float = 0.5) -> bool:
        """Boolean wrapper around speech_prob.

        Default threshold 0.5 = Silero's recommended operating point.
        Use 0.3 for the wake gate (we want speech to PASS easily) and
        0.5 for end-of-speech detection (we want silence to be clear).
        """
        return self.speech_prob(chunk) >= threshold

    def reset(self) -> None:
        """Reset the internal RNN state. Call between commands."""
        if not self._loaded or self._model is None:
            return
        try:
            self._model.reset_states()
        except Exception:
            pass
