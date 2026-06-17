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
import os
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
SILERO_FRAME_SAMPLES = 512  # MANDATORY for v5; other sizes degrade
SILERO_CONTEXT = 64         # v5 @16k prepende 64 samples de contexto a cada frame


def _vad_onnx_enabled() -> bool:
    """VAD en onnxruntime CRUDO (sin torch) en vez del paquete silero_vad (que importa
    torch ~174 MB). Gated GEMMA4_VAD_ONNX (default OFF). El modelo corre igual en ONNX en
    ambos caminos; la diferencia es que el crudo NO trae torch -> en modo voz se suelta torch
    por completo (junto con el encoder→ONNX). Paridad de speech_prob VERIFICADA exacta
    (max abs-diff 0.0, scripts/_ab_vad_onnx.py). Fallback seguro al wrapper torch ante fallo."""
    return (os.environ.get("GEMMA4_VAD_ONNX") or "0").strip().casefold() in {"1", "true", "yes", "on"}


def _find_silero_onnx() -> str | None:
    """Ubica silero_vad.onnx del paquete instalado SIN importarlo (find_spec NO ejecuta el
    módulo -> no trae torch). Override: GEMMA4_VAD_ONNX_MODEL apunta a un modelo copiado."""
    env = (os.environ.get("GEMMA4_VAD_ONNX_MODEL") or "").strip()
    if env and os.path.isfile(env):
        return env
    try:
        import importlib.util
        from pathlib import Path
        spec = importlib.util.find_spec("silero_vad")
        for loc in (spec.submodule_search_locations or []) if spec else []:
            cands = list(Path(loc).rglob("silero_vad.onnx"))
            if cands:
                return str(cands[0])
    except Exception:
        pass
    return None


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
        # Backend onnxruntime crudo (sin torch). Si _raw_sess != None, speech_prob/reset
        # usan este camino; si no, el wrapper torch (_model).
        self._raw_sess: Any = None
        self._raw_in: set[str] = set()
        self._raw_state: np.ndarray | None = None
        self._raw_ctx: np.ndarray | None = None

    def load(self) -> bool:
        if self._loaded:
            return True
        if self._failed:
            return False
        # Camino ONNX crudo (sin torch), gated. Ante cualquier fallo cae al wrapper torch.
        if _vad_onnx_enabled() and self._load_raw_onnx():
            return True
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

    def _load_raw_onnx(self) -> bool:
        """Carga el modelo Silero en onnxruntime CRUDO (sin torch). Replica el OnnxWrapper
        de silero_vad: estado LSTM [2,1,128] + contexto de 64 samples prepended por frame
        (paridad exacta verificada). Best-effort: False -> el caller cae al wrapper torch."""
        model = _find_silero_onnx()
        if not model:
            self.last_error = "VAD ONNX model no encontrado (silero_vad.onnx)"
            return False
        try:
            import onnxruntime as ort
            so = ort.SessionOptions()
            so.intra_op_num_threads = 1
            so.inter_op_num_threads = 1
            self._raw_sess = ort.InferenceSession(
                model, sess_options=so, providers=["CPUExecutionProvider"])
            self._raw_in = {i.name for i in self._raw_sess.get_inputs()}
            self._raw_state = np.zeros((2, 1, 128), dtype=np.float32)
            self._raw_ctx = np.zeros((1, SILERO_CONTEXT), dtype=np.float32)
            self._loaded = True
            logger.info("SileroVAD loaded (raw onnxruntime, sin torch)")
            return True
        except Exception as exc:
            self._raw_sess = None
            self.last_error = f"VAD raw-onnx init failed: {exc}"
            logger.warning(self.last_error)
            return False

    def _raw_prob(self, chunk: np.ndarray) -> float:
        """Forward del Silero en onnxruntime crudo (replica OnnxWrapper.__call__)."""
        audio_f = (chunk.astype(np.float32) / 32768.0).reshape(1, -1)
        x = np.concatenate([self._raw_ctx, audio_f], axis=1).astype(np.float32)  # (1, 64+512)
        feed: dict[str, Any] = {"input": x, "state": self._raw_state}
        if "sr" in self._raw_in:
            feed["sr"] = np.array(SAMPLE_RATE, dtype=np.int64)
        out, new_state = self._raw_sess.run(None, feed)
        self._raw_state = new_state
        self._raw_ctx = x[:, -SILERO_CONTEXT:]
        return float(np.asarray(out).reshape(-1)[0])

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
            if self._raw_sess is not None:
                return self._raw_prob(chunk)
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

    def trim_silence(
        self,
        audio: np.ndarray,
        threshold: float = 0.5,
        pad_ms: int = 100,
    ) -> np.ndarray | None:
        """Recorta silencio lateral de `audio` (int16) usando Silero por frames.

        STT Tier-1 (2026-05-22): la causa #1 de alucinación de Whisper en clips
        cortos es el silencio al inicio/final (el encoder paddea a 30s con ceros
        y el decoder fabrica texto). Recortar agresivo el silencio lateral ANTES
        de Whisper lo elimina. La investigación (faster-whisper VAD §5.3) usa
        speech_pad_ms=100, NO los 400 default que agregan latencia.

        Devuelve:
          - El buffer recortado [primer_frame_speech .. ultimo_frame_speech]
            + `pad_ms` de margen a cada lado.
          - None si NO se detectó NADA de speech (rechazar -> no invocar Whisper,
            cero alucinaciones en falsos positivos del wake).
          - El audio ORIGINAL intacto si el VAD no está cargado (fallback) o si
            algo falla — nunca rompe el pipeline.
        """
        if audio is None or audio.size == 0:
            return None
        if not self._loaded:
            return audio  # gate-open fallback: sin VAD, no recortamos
        f = SILERO_FRAME_SAMPLES
        try:
            n_frames = audio.size // f
            if n_frames == 0:
                return audio  # más corto que un frame: dejar pasar tal cual
            first = last = -1
            for k in range(n_frames):
                frame = audio[k * f:(k + 1) * f]
                if self.speech_prob(frame) >= threshold:
                    if first < 0:
                        first = k
                    last = k
            if first < 0:
                return None  # ningún frame con speech -> rechazar
            pad = int(pad_ms * SAMPLE_RATE / 1000)
            start = max(0, first * f - pad)
            end = min(audio.size, (last + 1) * f + pad)
            return audio[start:end]
        except Exception as exc:
            logger.debug("trim_silence failed, passing audio through: %s", exc)
            return audio

    def reset(self) -> None:
        """Reset the internal RNN state. Call between commands."""
        if not self._loaded:
            return
        try:
            if self._raw_sess is not None:
                # Backend crudo: estado LSTM + contexto a ceros (= OnnxWrapper.reset_states).
                self._raw_state = np.zeros((2, 1, 128), dtype=np.float32)
                self._raw_ctx = np.zeros((1, SILERO_CONTEXT), dtype=np.float32)
            elif self._model is not None:
                self._model.reset_states()
        except Exception:
            pass
