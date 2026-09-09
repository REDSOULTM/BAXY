"""Session-owned AEC3: aligned recognition, confirmation and raw echo signals.

The native package is pinned in the runtime lock. Its build recipe and linear
output patch live in scripts/build_webrtc_runtime.py and runtime_wheels/.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
from pathlib import Path
import threading
from typing import NamedTuple

import numpy as np

SAMPLE_RATE = 16_000
FRAME_SAMPLES = 512
REFERENCE_SAMPLES = FRAME_SAMPLES + SAMPLE_RATE // 4
_NATIVE_SAMPLES = 160
_DELAY_SAMPLES = 256
RUNTIME_VERSION = "0.2.0+baxy.1"
NATIVE_SHA256 = "3679265e7761c1a77e51f598ebb33e819f11e9a6e53a4d0f95b0da6f83382ef2"


def _native_runtime():
    distribution = importlib.metadata.distribution("pywebrtc-audio")
    if distribution.version != RUNTIME_VERSION:
        raise RuntimeError("echo_canceller_runtime_version_mismatch")
    path = Path(distribution.locate_file("pywebrtc_audio/_webrtc_audio.cp312-win_amd64.pyd"))
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != NATIVE_SHA256:
        raise RuntimeError("echo_canceller_native_hash_mismatch")
    module = importlib.import_module("pywebrtc_audio._webrtc_audio")
    if Path(module.__file__).resolve() != path.resolve():
        raise RuntimeError("echo_canceller_import_path_mismatch")
    return module.EchoCanceller


def echo_canceller_available() -> bool:
    try:
        _native_runtime()
        return True
    except (ImportError, OSError, RuntimeError, ValueError):
        return False


class EchoFrame(NamedTuple):
    """All four signals refer to the same time, delayed by 256 samples."""

    recognition: np.ndarray
    confirmation: np.ndarray
    microphone: np.ndarray
    reference: np.ndarray


class EchoCanceller:
    """One native AEC and its causal 160-to-512 bridge per capture thread."""

    def __init__(self) -> None:
        self._owner = threading.get_ident()
        self._native = _native_runtime()(SAMPLE_RATE, 1, 0)
        self.sha256 = NATIVE_SHA256
        self._near = np.empty(0, np.float32)
        self._far = np.empty(0, np.float32)
        # max(n*512 mod160)=128. Native delays are64(linear) and128(final).
        # These prefixes make every block causal and both outputs align at256.
        self._linear = np.zeros(192, np.float32)
        self._final = np.zeros(128, np.float32)
        self._mic_delay = np.zeros(_DELAY_SAMPLES, np.float32)
        self._previous_reference: np.ndarray | None = None

    def _check_owner(self) -> None:
        if threading.get_ident() != self._owner:
            raise RuntimeError("echo_canceller_wrong_thread")

    @staticmethod
    def _output(value: np.ndarray) -> np.ndarray:
        audio = np.asarray(value, dtype=np.float32)
        if audio.shape != (_NATIVE_SAMPLES,) or not np.isfinite(audio).all() or np.max(np.abs(audio)) > 1:
            raise RuntimeError("echo_canceller_output_invalid")
        return audio

    def process(self, microphone: np.ndarray, reference: np.ndarray) -> EchoFrame:
        """Return two normalized views and the aligned raw PCM16-scale pair."""
        self._check_owner()
        if self._native is None:
            raise RuntimeError("echo_canceller_closed")
        near = np.asarray(microphone, dtype=np.float32).reshape(-1)
        history = np.asarray(reference, dtype=np.float32).reshape(-1)
        if near.size != FRAME_SAMPLES or history.size != REFERENCE_SAMPLES:
            raise ValueError("echo_canceller_frame_size_invalid")
        if not np.isfinite(near).all() or not np.isfinite(history).all():
            raise ValueError("echo_canceller_nonfinite_audio")
        self._near = np.r_[self._near, near]
        self._far = np.r_[self._far, history[-FRAME_SAMPLES:] / 32768]
        while self._near.size >= _NATIVE_SAMPLES:
            final = self._output(self._native.process(
                np.ascontiguousarray(self._near[:_NATIVE_SAMPLES]),
                np.ascontiguousarray(self._far[:_NATIVE_SAMPLES]),
            ))
            linear = self._output(self._native.last_linear_frame())
            self._final = np.r_[self._final, final]
            self._linear = np.r_[self._linear, linear]
            self._near = self._near[_NATIVE_SAMPLES:]
            self._far = self._far[_NATIVE_SAMPLES:]
        recognition, self._linear = self._linear[:FRAME_SAMPLES].copy(), self._linear[FRAME_SAMPLES:]
        confirmation, self._final = self._final[:FRAME_SAMPLES].copy(), self._final[FRAME_SAMPLES:]
        raw = np.r_[self._mic_delay, near]
        if self._previous_reference is None:
            self._previous_reference = np.r_[np.zeros(FRAME_SAMPLES, np.float32), history[:-FRAME_SAMPLES]]
        paired_history = np.r_[self._previous_reference, history[-FRAME_SAMPLES:]][:-_DELAY_SAMPLES][-REFERENCE_SAMPLES:]
        self._mic_delay = raw[FRAME_SAMPLES:].copy()
        self._previous_reference = history.copy()
        return EchoFrame(recognition, confirmation, raw[:FRAME_SAMPLES] * 32768, paired_history)

    def close(self) -> None:
        self._check_owner()
        self._native = None
        self._near = self._far = self._linear = self._final = self._mic_delay = np.empty(0, np.float32)
        self._previous_reference = None
