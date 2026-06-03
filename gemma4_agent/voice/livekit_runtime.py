"""Pure-onnxruntime LiveKit wake-word inference for Python 3.10.

The trained LiveKit model lives as 3 ONNX graphs. The
`livekit-wakeword` PyPI package requires Python 3.11, but
the Gemma 4 runtime is 3.10. This module reimplements LiveKit's
inference pipeline using ONLY onnxruntime + numpy, so it loads in 3.10.

Pipeline (mirrors livekit.wakeword.inference.WakeWordModel exactly):
  audio (16 kHz, ~2 s) -> melspectrogram.onnx -> (T, 32) dB mel
                       -> mel/10 + 2  (openWakeWord normalization)
                       -> 76-frame windows, stride 8 -> embedding.onnx
                       -> (96,) per window
                       -> last 16 embeddings -> hey_gemma.onnx -> score

Models expected under models_dir:
  melspectrogram.onnx   (bundled, copied from livekit package)
  embedding_model.onnx  (bundled, copied from livekit package)
  hey_gemma.onnx        (our trained classifier)

Threading: we cap onnxruntime to a small thread count and disable
busy-wait spinning so live mic inference does not saturate the CPU
(see scripts/_ort_throttle.py for the lesson learned during eval).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
EMBEDDING_WINDOW = 76   # mel frames per embedding
EMBEDDING_STRIDE = 8    # mel frames between embeddings
MIN_EMBEDDINGS = 16     # classifier input length
# A 2 s window at 16 kHz yields exactly 16 embeddings.
WINDOW_SAMPLES = 32000

# Keep inference light so it never starves the foreground app.
INTRA_OP_THREADS = 2


class LiveKitWakeRuntime:
    """Stateless LiveKit wake-word scorer (pure onnxruntime).

    Usage:
        rt = LiveKitWakeRuntime(models_dir, classifier="hey_gemma")
        rt.load()
        score = rt.predict(audio_2s_int16)  # float 0..1
    """

    def __init__(self, models_dir: Path, classifier_stem: str = "hey_gemma") -> None:
        self._dir = Path(models_dir)
        self._classifier_stem = classifier_stem
        self._mel: Any = None
        self._mel_input: str = ""
        self._emb: Any = None
        self._emb_input: str = ""
        self._clf: Any = None
        self._clf_input: str = ""
        self._loaded = False
        self.last_error: str | None = None

    def _make_session(self, path: Path) -> Any:
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = INTRA_OP_THREADS
        so.inter_op_num_threads = 1
        so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        try:
            so.add_session_config_entry("session.intra_op.allow_spinning", "0")
        except Exception:
            pass
        return ort.InferenceSession(
            str(path), sess_options=so, providers=["CPUExecutionProvider"],
        )

    def load(self) -> bool:
        if self._loaded:
            return True
        mel_p = self._dir / "melspectrogram.onnx"
        emb_p = self._dir / "embedding_model.onnx"
        clf_p = self._dir / f"{self._classifier_stem}.onnx"
        for p in (mel_p, emb_p, clf_p):
            if not p.exists():
                self.last_error = f"missing ONNX: {p}"
                logger.error(self.last_error)
                return False
        try:
            self._mel = self._make_session(mel_p)
            self._mel_input = self._mel.get_inputs()[0].name
            self._emb = self._make_session(emb_p)
            self._emb_input = self._emb.get_inputs()[0].name
            self._clf = self._make_session(clf_p)
            self._clf_input = self._clf.get_inputs()[0].name
            self._loaded = True
            logger.info(
                "LiveKitWakeRuntime loaded (classifier=%s)",
                self._classifier_stem,
            )
            return True
        except Exception as exc:
            self.last_error = f"LiveKitWakeRuntime load failed: {exc}"
            logger.error(self.last_error)
            return False

    def _mel_features(self, audio_f32: np.ndarray) -> np.ndarray:
        """audio (samples,) float32 -> (T, 32) normalized mel."""
        inp = audio_f32[np.newaxis, :].astype(np.float32)
        out = self._mel.run(None, {self._mel_input: inp})[0]
        # (batch, time, 32) or (batch, 1, time, 32)
        if out.ndim == 4:
            out = out[:, 0, :, :]
        mel = out[0]  # (T, 32)
        # openWakeWord normalization (matches LiveKit feature_extractor).
        return mel / 10.0 + 2.0

    def predict(self, audio_chunk: np.ndarray) -> float:
        """Score a ~2 s audio chunk. Returns float 0..1.

        Accepts int16 or float32. Shorter-than-window chunks return 0.0.
        """
        if not self._loaded:
            return 0.0
        if audio_chunk.dtype == np.int16:
            audio = audio_chunk.astype(np.float32) / 32768.0
        else:
            audio = audio_chunk.astype(np.float32)
        audio = audio.flatten()

        mel = self._mel_features(audio)
        if mel.shape[0] < EMBEDDING_WINDOW:
            return 0.0

        embeddings = []
        for start in range(0, mel.shape[0] - EMBEDDING_WINDOW + 1, EMBEDDING_STRIDE):
            window = mel[start : start + EMBEDDING_WINDOW]  # (76, 32)
            inp = window[np.newaxis, :, :, np.newaxis].astype(np.float32)  # (1,76,32,1)
            emb = self._emb.run(None, {self._emb_input: inp})[0]
            embeddings.append(emb.squeeze())  # (96,)

        if len(embeddings) < MIN_EMBEDDINGS:
            return 0.0

        emb_seq = np.stack(embeddings[-MIN_EMBEDDINGS:], axis=0)
        clf_in = emb_seq[np.newaxis, :, :].astype(np.float32)  # (1,16,96)
        out = self._clf.run(None, {self._clf_input: clf_in})[0]
        return float(out[0, 0])
