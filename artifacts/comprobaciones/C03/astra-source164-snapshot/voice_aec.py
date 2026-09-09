"""Frontend acústico local: loopback WASAPI y ducking reversible.

Recupera las piezas medibles de los BAXY anteriores sin depender del wake ni
del TTS históricos. La referencia es exactamente lo que Windows reproduce.
Cuando el backend o el endpoint no están disponibles, la voz continúa con el
micrófono crudo y lo reporta en capacidades; nunca simula que hubo AEC.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from contextlib import contextmanager
from math import gcd
from typing import Iterator

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
_RING_SECONDS = 4


def _resample(audio: np.ndarray, source_rate: int) -> np.ndarray:
    mono = np.asarray(audio, dtype=np.float64).reshape(-1)
    if mono.size == 0 or source_rate == SAMPLE_RATE:
        return mono.astype(np.int16)
    try:
        from scipy.signal import resample_poly

        divisor = gcd(int(source_rate), SAMPLE_RATE)
        return resample_poly(
            mono,
            SAMPLE_RATE // divisor,
            int(source_rate) // divisor,
        ).astype(np.int16)
    except Exception:  # noqa: BLE001 - interpolación es fallback explícito
        count = max(1, int(round(mono.size * SAMPLE_RATE / source_rate)))
        positions = np.linspace(0, mono.size - 1, count)
        return np.interp(positions, np.arange(mono.size), mono).astype(np.int16)


def prepare_resampler() -> None:
    """Initialize native DSP before the sidecar starts reading redirected stdin.

    On Windows, cold SciPy/BLAS loading can stall while another thread blocks
    on that pipe. Warm the existing resampling path without opening audio.
    """
    _resample(np.zeros(48, dtype=np.int16), 48_000)


class LoopbackReference:
    """WASAPI reference ring indexed by samples from its first native ADC timestamp."""

    def __init__(self) -> None:
        self._backend = None
        self._stream = None
        self._ring = np.zeros(SAMPLE_RATE * _RING_SECONDS, dtype=np.int16)
        self._condition = threading.Condition()
        self._written = 0
        self._origin_time: float | None = None
        self._stopped = False
        self.last_error: str | None = None

    @property
    def active(self) -> bool:
        return self._stream is not None

    def _append(self, block: np.ndarray, adc_time: float) -> None:
        if not math.isfinite(adc_time) or adc_time <= 0:
            raise RuntimeError("loopback_adc_clock_unavailable")
        if block.size > self._ring.size:
            raise RuntimeError("loopback_block_too_large")
        with self._condition:
            if self._stopped:
                return
            if self._origin_time is None:
                self._origin_time = adc_time
            start = self._written % self._ring.size
            first = min(block.size, self._ring.size - start)
            self._ring[start : start + first] = block[:first]
            self._ring[: block.size - first] = block[first:]
            self._written += block.size
            self._condition.notify_all()

    def start(self) -> bool:
        if self._stream is not None:
            return True
        with self._condition:
            self._ring.fill(0)
            self._written = 0
            self._origin_time = None
            self._stopped = False
            self.last_error = None
        try:
            import pyaudiowpatch as pyaudio

            backend = pyaudio.PyAudio()
            self._backend = backend
            loopback = backend.get_default_wasapi_loopback()
            source_rate = int(loopback["defaultSampleRate"])
            channels = int(loopback["maxInputChannels"])
            # Load resampling code before starting the real-time callback.
            _resample(np.zeros(int(source_rate * 0.032)), source_rate)

            def callback(data, _frames, timing, status):
                try:
                    if status:
                        raise RuntimeError("loopback_callback_overflow")
                    block = np.frombuffer(data, dtype=np.int16)
                    if channels > 1:
                        block = block.reshape(-1, channels).mean(axis=1)
                    block = _resample(block, source_rate)
                    self._append(block, float(timing["input_buffer_adc_time"]))
                except Exception as error:  # noqa: BLE001 - callback never propagates
                    with self._condition:
                        self.last_error = str(error) or type(error).__name__
                        self._condition.notify_all()
                    return (None, pyaudio.paAbort)
                return (None, pyaudio.paContinue)

            self._stream = backend.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=source_rate,
                input=True,
                input_device_index=int(loopback["index"]),
                frames_per_buffer=max(128, int(source_rate * 0.032)),
                stream_callback=callback,
                start=False,
            )
            self._stream.start_stream()
            return True
        except Exception as error:  # noqa: BLE001 - optional capability
            self.last_error = f"loopback_unavailable:{type(error).__name__}"
            self.stop()
            return False

    def _check_wait(self, stop_event: threading.Event, deadline: float) -> None:
        if stop_event.is_set():
            raise InterruptedError("loopback_read_cancelled")
        if self._stopped:
            raise RuntimeError("loopback_stopped")
        if self.last_error is not None:
            raise RuntimeError(self.last_error)
        if time.monotonic() >= deadline:
            raise RuntimeError("loopback_reference_timeout")

    def sample_index(
        self, adc_time: float, stop_event: threading.Event, *, timeout: float = 0.25
    ) -> int:
        """Anchor a consumer once; it advances its own cursor by samples thereafter."""
        if not math.isfinite(adc_time) or adc_time <= 0:
            raise ValueError("capture_adc_clock_unavailable")
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._origin_time is None:
                self._check_wait(stop_event, deadline)
                self._condition.wait(min(0.02, max(0, deadline - time.monotonic())))
            self._check_wait(stop_event, deadline)
            return round((adc_time - self._origin_time) * SAMPLE_RATE)

    def _window(self, end: int, samples: int) -> np.ndarray:
        start = end - samples
        available_start = max(0, self._written - self._ring.size)
        if max(0, start) < available_start:
            raise RuntimeError("loopback_reader_overrun")
        result = np.zeros(samples, dtype=np.int16)
        first = max(0, start)
        last = max(first, end)
        if last > first:
            index = first % self._ring.size
            count = last - first
            prefix = min(count, self._ring.size - index)
            offset = first - start
            result[offset : offset + prefix] = self._ring[index : index + prefix]
            result[offset + prefix : offset + count] = self._ring[: count - prefix]
        return result

    def window_at(
        self, end: int, samples: int, stop_event: threading.Event,
        *, timeout: float = 0.25,
    ) -> np.ndarray:
        if samples < 0 or samples > self._ring.size:
            raise ValueError("loopback_window_size_invalid")
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._written < end:
                self._check_wait(stop_event, deadline)
                self._condition.wait(min(0.02, max(0, deadline - time.monotonic())))
            self._check_wait(stop_event, deadline)
            return self._window(end, samples)

    def latest(self, samples: int) -> np.ndarray:
        count = max(0, min(self._ring.size, int(samples)))
        with self._condition:
            return self._window(self._written, count)

    def stop(self) -> bool:
        with self._condition:
            self._stopped = True
            self._condition.notify_all()
        stream, backend = self._stream, self._backend
        complete = True
        if stream is not None:
            try:
                stream.stop_stream()
            except Exception:  # noqa: BLE001
                complete = False
            try:
                stream.close()
            except Exception:  # noqa: BLE001
                complete = False
        if backend is not None:
            try:
                backend.terminate()
            except Exception:  # noqa: BLE001
                complete = False
        self._stream = None
        self._backend = None
        return complete


@contextmanager
def _com_apartment() -> Iterator[None]:
    initialized = False
    try:
        import comtypes

        comtypes.CoInitialize()
        initialized = True
        yield
    finally:
        if initialized:
            try:
                comtypes.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass


class AudioDucker:
    """Reduce y restaura exactamente el volumen master; idempotente."""

    def __init__(self, target: float = 0.20) -> None:
        self._target = max(0.0, min(1.0, target))
        self._previous: float | None = None
        self._lock = threading.RLock()

    @staticmethod
    def _endpoint():
        from pycaw.pycaw import AudioUtilities

        device = AudioUtilities.GetSpeakers()
        return getattr(device, "EndpointVolume", None) if device is not None else None

    def duck(self) -> bool:
        with self._lock:
            if self._previous is not None:
                return True
            try:
                with _com_apartment():
                    endpoint = self._endpoint()
                    if endpoint is None:
                        return False
                    self._previous = float(endpoint.GetMasterVolumeLevelScalar())
                    endpoint.SetMasterVolumeLevelScalar(
                        min(self._previous, self._target),
                        None,
                    )
                    return True
            except Exception as error:  # noqa: BLE001
                logger.debug("ducking no disponible: %s", type(error).__name__)
                self._previous = None
                return False

    def restore(self) -> bool:
        with self._lock:
            previous = self._previous
            if previous is None:
                return True
            try:
                with _com_apartment():
                    endpoint = self._endpoint()
                    if endpoint is None:
                        return False
                    endpoint.SetMasterVolumeLevelScalar(previous, None)
                    self._previous = None
                    return True
            except Exception as error:  # noqa: BLE001
                logger.warning("no se pudo restaurar ducking: %s", type(error).__name__)
                return False


__all__ = ["AudioDucker", "LoopbackReference"]
