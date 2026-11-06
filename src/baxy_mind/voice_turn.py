"""Whether the person finished their turn, from the sound of it: Pipecat's Smart Turn v3.2 (BSD 2-Clause, Daily;
https://github.com/pipecat-ai/smart-turn), a Whisper Tiny encoder with a linear head, int8 ONNX (8.7 MB), 23
languages with Spanish and English, run by onnxruntime on one CPU thread. The repository keeps no model:
scripts/voice/instalar_fin_de_turno.ps1 downloads the published file into the runtime's assets and checks its SHA-256.

It hears up to the last TURN_S seconds of the request, as Pipecat's LocalSmartTurnAnalyzerV3 gives them (the end kept,
zeros before a shorter request), and says how likely the turn is complete. It reads intonation and rhythm, not words: a
voice that falls at the end of an order against one left in the air before a pause («abre el… bloc de notas»).

Features: Whisper's log-mel (80 bins, 25 ms windows every 10 ms, 8 s), as transformers' WhisperFeatureExtractor
(chunk_length=8, do_normalize=True) computes them; the same math as Pipecat's numpy copy (_whisper_features.py).
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

RATE = 16000
TURN_S = 8                      # the model hears the last 8 s (input_features [1, 80, 800])
MODEL_NAME = "smart-turn-v3.2-cpu.onnx"  # https://huggingface.co/pipecat-ai/smart-turn-v3, 8 679 182 bytes
MODEL_SHA256 = "2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f"
_N_FFT, _HOP, _N_MELS = 400, 160, 80


def _hz_to_mel(f: np.ndarray) -> np.ndarray:
    """Slaney's mel scale (librosa's default, Whisper's)."""
    f = np.asarray(f, np.float64)
    return np.where(f >= 1000.0, 15.0 + np.log(np.maximum(f, 1e-9) / 1000.0) * (27.0 / np.log(6.4)), 3.0 * f / 200.0)


def _mel_to_hz(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, np.float64)
    return np.where(m >= 15.0, 1000.0 * np.exp((np.log(6.4) / 27.0) * (m - 15.0)), 200.0 * m / 3.0)


def _filters() -> np.ndarray:
    """Slaney-normalized triangular filters, (N_FFT // 2 + 1, N_MELS)."""
    hz = _mel_to_hz(np.linspace(_hz_to_mel(0.0), _hz_to_mel(RATE / 2), _N_MELS + 2))
    bins = np.linspace(0, RATE // 2, _N_FFT // 2 + 1)
    slopes = hz[None, :] - bins[:, None]
    diff = np.diff(hz)
    tri = np.maximum(0.0, np.minimum(-slopes[:, :-2] / diff[:-1], slopes[:, 2:] / diff[1:]))
    return tri * (2.0 / (hz[2:] - hz[:-2]))[None, :]


_WINDOW = np.hanning(_N_FFT + 1)[:-1]  # periodic Hann, torch.hann_window's
_MEL = _filters()


def features(audio: np.ndarray) -> np.ndarray:
    """Whisper's log-mel of the last TURN_S seconds of ``audio`` (16 kHz), zeros before a shorter one: (80, 800)."""
    n = TURN_S * RATE
    x = np.asarray(audio, np.float32)[-n:]
    x = np.concatenate([np.zeros(n - len(x), np.float32), x])
    x = (x - x.mean()) / np.sqrt(x.var() + 1e-7)
    padded = np.pad(x.astype(np.float64), _N_FFT // 2, mode="reflect")
    frames = np.lib.stride_tricks.sliding_window_view(padded, _N_FFT)[::_HOP]
    power = np.abs(np.fft.rfft(frames * _WINDOW, axis=-1)) ** 2
    log = np.log10(np.maximum(1e-10, power @ _MEL)).T[:, :-1]
    log = np.maximum(log, log.max() - 8.0)
    return ((log + 4.0) / 4.0).astype(np.float32)


class Turn:
    """Smart Turn on one CPU thread: ~10-60 ms per call (Daily's figures: 9 ms on a c7a.2xlarge, 57 ms on a
    c8g.medium), plus the features."""

    def __init__(self, model: Path) -> None:
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.inter_op_num_threads = options.intra_op_num_threads = 1
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session: Any = ort.InferenceSession(str(model), sess_options=options, providers=["CPUExecutionProvider"])

    def complete(self, audio: np.ndarray) -> float:
        """How likely the turn ``audio`` ends is complete (0-1; Pipecat calls it complete over 0.5)."""
        out = self._session.run(None, {"input_features": features(audio)[None]})[0]
        return float(np.asarray(out).reshape(-1)[0])


def default_path() -> Path:
    """Where scripts/voice/instalar_fin_de_turno.ps1 puts the model: beside BAXY's voice in the runtime's assets."""
    return Path(os.environ.get("LOCALAPPDATA", "")) / "BAXYRuntime" / "assets" / "voice" / "smart-turn" / MODEL_NAME


def model_path() -> Path | None:
    """BAXY_RENEW_TURN: «0» turns the model off (the request then closes as before uso-74: hanging words). The model is
    BAXY_RENEW_TURN_MODEL, or default_path(); None when it is off, missing or not the published file (MODEL_SHA256)."""
    if os.environ.get("BAXY_RENEW_TURN", "").strip().lower() in {"0", "off"}:
        return None
    path = Path(os.environ.get("BAXY_RENEW_TURN_MODEL", "") or default_path())
    if not path.is_file():
        return None
    if hashlib.sha256(path.read_bytes()).hexdigest() != MODEL_SHA256:
        sys.stderr.write(f"baxy_mind_renew_voice: turn model {path} is not {MODEL_NAME} as published\n")
        sys.stderr.flush()
        return None
    return path
