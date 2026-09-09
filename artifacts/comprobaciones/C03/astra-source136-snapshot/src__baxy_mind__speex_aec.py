"""Session-owned, local streaming acoustic echo cancellation."""

from __future__ import annotations

import ctypes
import hashlib
from pathlib import Path
import threading

import numpy as np

from .assets import AssetDescriptorError, resolve_asset

SAMPLE_RATE = 16_000
FRAME_SAMPLES = 512
REFERENCE_SAMPLES = FRAME_SAMPLES + SAMPLE_RATE // 4
_FILTER_SAMPLES = SAMPLE_RATE // 5


def resolve_echo_canceller_library() -> Path | None:
    try:
        return resolve_asset("echo_canceller").path
    except AssetDescriptorError:
        return None


class EchoCanceller:
    """One native filter and residual suppressor, owned by the capture thread."""

    def __init__(self) -> None:
        path = resolve_echo_canceller_library()
        if path is None:
            raise RuntimeError("echo_canceller_library_missing")
        self.library_path = path
        self.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        self._owner = threading.get_ident()
        self._state = None
        self._preprocessor = None
        self._library = ctypes.CDLL(str(path))
        self._pointer = ctypes.POINTER(ctypes.c_int16)
        signatures = (
            ("speex_echo_state_init", [ctypes.c_int, ctypes.c_int], ctypes.c_void_p),
            ("speex_echo_state_destroy", [ctypes.c_void_p], None),
            (
                "speex_echo_cancellation",
                [ctypes.c_void_p, self._pointer, self._pointer, self._pointer],
                None,
            ),
            (
                "speex_echo_ctl",
                [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p], ctypes.c_int,
            ),
            (
                "speex_preprocess_state_init",
                [ctypes.c_int, ctypes.c_int], ctypes.c_void_p,
            ),
            ("speex_preprocess_state_destroy", [ctypes.c_void_p], None),
            ("speex_preprocess_run", [ctypes.c_void_p, self._pointer], ctypes.c_int),
            (
                "speex_preprocess_ctl",
                [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p], ctypes.c_int,
            ),
        )
        for name, arguments, result in signatures:
            function = getattr(self._library, name)
            function.argtypes, function.restype = arguments, result
        try:
            self._state = self._library.speex_echo_state_init(
                FRAME_SAMPLES, _FILTER_SAMPLES
            )
            if not self._state:
                raise RuntimeError("echo_canceller_initialization_failed")
            self._preprocessor = self._library.speex_preprocess_state_init(
                FRAME_SAMPLES, SAMPLE_RATE
            )
            if not self._preprocessor:
                raise RuntimeError("echo_preprocessor_initialization_failed")
            rate = ctypes.c_int(SAMPLE_RATE)
            if (
                self._library.speex_echo_ctl(self._state, 24, ctypes.byref(rate))
                != 0
                or self._library.speex_preprocess_ctl(
                    self._preprocessor, 24, self._state
                ) != 0
            ):
                raise RuntimeError("echo_canceller_configuration_failed")
        except Exception:
            self.close()
            raise
        self._previous_microphone = np.zeros(FRAME_SAMPLES, dtype=np.float32)
        self._previous_reference = np.zeros(REFERENCE_SAMPLES, dtype=np.int16)

    def _check_owner(self) -> None:
        if threading.get_ident() != self._owner:
            raise RuntimeError("echo_canceller_wrong_thread")

    def process(
        self, microphone: np.ndarray, reference: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return clean audio and its corresponding raw echo-comparison pair.

        Microphone and output are normalized floats; reference uses signed PCM16.
        The upstream preprocessor delays output by one frame. Preserve that same
        delay for the raw pair used by the barge-in guard.
        """
        self._check_owner()
        if self._state is None or self._preprocessor is None:
            raise RuntimeError("echo_canceller_closed")
        mic = np.asarray(microphone, dtype=np.float32).reshape(-1)
        ref = np.asarray(reference).reshape(-1)
        if mic.size != FRAME_SAMPLES or ref.size != REFERENCE_SAMPLES:
            raise ValueError("echo_canceller_frame_size_invalid")
        if not np.isfinite(mic).all() or not np.isfinite(ref).all():
            raise ValueError("echo_canceller_nonfinite_audio")
        recorded = np.clip(mic * 32768.0, -32768, 32767).astype(np.int16)
        history = np.clip(ref, -32768, 32767).astype(np.int16)
        played = np.ascontiguousarray(history[-FRAME_SAMPLES:])
        clean = np.empty(FRAME_SAMPLES, dtype=np.int16)
        self._library.speex_echo_cancellation(
            self._state, recorded.ctypes.data_as(self._pointer),
            played.ctypes.data_as(self._pointer), clean.ctypes.data_as(self._pointer),
        )
        # Keep the upstream defaults: disabling denoise also disables residual
        # echo gain. AGC is off by default; no gain or threshold is tuned here.
        self._library.speex_preprocess_run(
            self._preprocessor, clean.ctypes.data_as(self._pointer)
        )
        pair = self._previous_microphone, self._previous_reference
        self._previous_microphone = mic.copy() * 32768.0
        self._previous_reference = history
        return clean.astype(np.float32) / 32768.0, *pair

    def close(self) -> None:
        self._check_owner()
        try:
            if self._preprocessor is not None:
                self._library.speex_preprocess_state_destroy(self._preprocessor)
        finally:
            self._preprocessor = None
            if self._state is not None:
                try:
                    self._library.speex_echo_state_destroy(self._state)
                finally:
                    self._state = None
