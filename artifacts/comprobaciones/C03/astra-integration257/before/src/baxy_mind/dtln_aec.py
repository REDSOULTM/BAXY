"""Session-owned DTLN512 acoustic echo cancellation, CPU only.

Streaming overlap-add follows breizhn/DTLN-aec run_aec.py (MIT), revision
9d24e128b4f409db18227b8babb343016625921f. Models and license are pinned below.
Copyright and permission notice: licenses/DTLN-aec.txt.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import threading

import numpy as np

from .assets import AssetDescriptorError, resolve_asset

SAMPLE_RATE = 16_000
FRAME_SAMPLES = 512
REFERENCE_SAMPLES = FRAME_SAMPLES + SAMPLE_RATE // 4
_HOP_SAMPLES = 128
_DELAY_SAMPLES = FRAME_SAMPLES - _HOP_SAMPLES
SOURCE_URL = (
    "https://raw.githubusercontent.com/breizhn/DTLN-aec/"
    "9d24e128b4f409db18227b8babb343016625921f"
)
MODEL_HASHES = {
    "dtln_aec_512_1.tflite": "569f7c3cfac96b1e093229c3ca10b5d892f5b1906105b644e457f8245b4f7383",
    "dtln_aec_512_2.tflite": "fb423d867ab25d5f4716bd369c7126b6c84926175c019b832e71bf21de0e9907",
}
LICENSE_SHA256 = "aa95acd8c8a7341bfcdb2823694dcbb27a2a4143e860bb52db1ff0f29c85e5a1"


def resolve_echo_canceller_directory() -> Path | None:
    try:
        return resolve_asset("echo_canceller").path
    except AssetDescriptorError:
        return None


def _validate_tensors(details: list[dict], shapes: tuple[tuple[int, ...], ...]) -> None:
    if len(details) != len(shapes) or any(
        tuple(detail["shape"]) != shape or detail["dtype"] != np.float32
        for detail, shape in zip(details, shapes)
    ):
        raise RuntimeError("echo_canceller_tensor_schema_invalid")


class EchoCanceller:
    """Two recurrent model stages and one audio history per capture thread."""

    def __init__(self) -> None:
        self._owner = threading.get_ident()
        self._models = []
        path = resolve_echo_canceller_directory()
        if path is None:
            raise RuntimeError("echo_canceller_models_missing")
        self.model_directory = path
        for name, expected in {**MODEL_HASHES, "LICENSE": LICENSE_SHA256}.items():
            with (path / name).open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != expected:
                raise RuntimeError(f"echo_canceller_asset_hash_mismatch:{name}")
        self.sha256 = hashlib.sha256("".join(MODEL_HASHES.values()).encode("ascii")).hexdigest()

        from ai_edge_litert.interpreter import Interpreter

        try:
            for name in MODEL_HASHES:
                model = Interpreter(model_path=str(path / name), num_threads=1)
                self._models.append(model)
                model.allocate_tensors()
            self._inputs = [model.get_input_details() for model in self._models]
            self._outputs = [model.get_output_details() for model in self._models]
            state_shape = (1, 2, 512, 2)
            for stage, width in enumerate((257, 512)):
                audio_shape = (1, 1, width)
                _validate_tensors(self._inputs[stage], (audio_shape, state_shape, audio_shape))
                _validate_tensors(self._outputs[stage], (audio_shape, state_shape))
            self._states = [np.zeros(state_shape, np.float32) for _ in self._models]
            self._near = np.zeros(FRAME_SAMPLES, np.float32)
            self._far = np.zeros(FRAME_SAMPLES, np.float32)
            self._out = np.zeros(FRAME_SAMPLES, np.float32)
            self._mic_delay = np.zeros(_DELAY_SAMPLES, np.float32)
            self._previous_reference = None
            # The author's three leading zero hops are discarded, not emitted.
            for _ in range(3):
                self._hop(np.zeros(_HOP_SAMPLES, np.float32), np.zeros(_HOP_SAMPLES, np.float32))
        except Exception:
            self.close()
            raise

    def _check_owner(self) -> None:
        if threading.get_ident() != self._owner:
            raise RuntimeError("echo_canceller_wrong_thread")

    def _hop(self, near: np.ndarray, far: np.ndarray) -> np.ndarray:
        self._near[:-_HOP_SAMPLES] = self._near[_HOP_SAMPLES:]
        self._near[-_HOP_SAMPLES:] = near
        self._far[:-_HOP_SAMPLES] = self._far[_HOP_SAMPLES:]
        self._far[-_HOP_SAMPLES:] = far
        spectrum = np.fft.rfft(self._near).astype("complex64")
        magnitude = np.abs(spectrum).reshape(1, 1, -1).astype("float32")
        far_spectrum = np.fft.rfft(self._far).astype("complex64")
        far_magnitude = np.abs(far_spectrum).reshape(1, 1, -1).astype("float32")
        one, two = self._models
        one.set_tensor(self._inputs[0][0]["index"], magnitude)
        one.set_tensor(self._inputs[0][2]["index"], far_magnitude)
        one.set_tensor(self._inputs[0][1]["index"], self._states[0])
        one.invoke()
        mask = one.get_tensor(self._outputs[0][0]["index"])
        self._states[0] = one.get_tensor(self._outputs[0][1]["index"])
        estimated = np.fft.irfft(spectrum * mask).reshape(1, 1, -1).astype("float32")
        two.set_tensor(self._inputs[1][1]["index"], self._states[1])
        two.set_tensor(self._inputs[1][0]["index"], estimated)
        two.set_tensor(self._inputs[1][2]["index"], self._far.reshape(1, 1, -1).astype("float32"))
        two.invoke()
        block = two.get_tensor(self._outputs[1][0]["index"])
        self._states[1] = two.get_tensor(self._outputs[1][1]["index"])
        self._out[:-_HOP_SAMPLES] = self._out[_HOP_SAMPLES:]
        self._out[-_HOP_SAMPLES:] = 0
        self._out += np.squeeze(block)
        return self._out[:_HOP_SAMPLES].copy()

    def process(
        self, microphone: np.ndarray, reference: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return normalized clean audio and the matching raw PCM16-scale pair.

        DTLN delays audio by 384 samples. Delay both microphone and the complete
        reference history equally so the interruption guard compares one instant.
        """
        self._check_owner()
        if not self._models:
            raise RuntimeError("echo_canceller_closed")
        near = np.asarray(microphone, dtype=np.float32).reshape(-1)
        history = np.asarray(reference, dtype=np.float32).reshape(-1)
        if near.size != FRAME_SAMPLES or history.size != REFERENCE_SAMPLES:
            raise ValueError("echo_canceller_frame_size_invalid")
        if not np.isfinite(near).all() or not np.isfinite(history).all():
            raise ValueError("echo_canceller_nonfinite_audio")
        far = history[-FRAME_SAMPLES:] / 32768
        clean = np.concatenate([
            self._hop(near[i:i + _HOP_SAMPLES], far[i:i + _HOP_SAMPLES])
            for i in range(0, FRAME_SAMPLES, _HOP_SAMPLES)
        ])
        if not np.isfinite(clean).all() or np.max(np.abs(clean)) > 1:
            raise RuntimeError("echo_canceller_output_invalid")
        raw = np.r_[self._mic_delay, near]
        if self._previous_reference is None:
            self._previous_reference = np.r_[np.zeros(FRAME_SAMPLES, np.float32), history[:-FRAME_SAMPLES]]
        paired_history = np.r_[self._previous_reference, history[-FRAME_SAMPLES:]][:-_DELAY_SAMPLES][-REFERENCE_SAMPLES:]
        self._mic_delay = raw[FRAME_SAMPLES:].copy()
        self._previous_reference = history.copy()
        return clean, raw[:FRAME_SAMPLES] * 32768, paired_history

    def close(self) -> None:
        self._check_owner()
        self._models.clear()
