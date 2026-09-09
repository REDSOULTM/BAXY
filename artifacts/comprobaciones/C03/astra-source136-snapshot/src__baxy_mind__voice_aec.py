"""Frontend acústico local: loopback WASAPI y ducking reversible.

Recupera las piezas medibles de los BAXY anteriores sin depender del wake ni
del TTS históricos. La referencia es exactamente lo que Windows reproduce.
Cuando el backend o el endpoint no están disponibles, la voz continúa con el
micrófono crudo y lo reporta en capacidades; nunca simula que hubo AEC.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from math import gcd
from typing import Iterator

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
_RING_SECONDS = 35


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


class LoopbackReference:
    """Ring thread-safe del output predeterminado capturado por WASAPI."""

    def __init__(self) -> None:
        self._backend = None
        self._stream = None
        self._ring = np.zeros(SAMPLE_RATE * _RING_SECONDS, dtype=np.int16)
        self._lock = threading.Lock()
        self.last_error: str | None = None

    @property
    def active(self) -> bool:
        return self._stream is not None

    def start(self) -> bool:
        if self._stream is not None:
            return True
        try:
            import pyaudiowpatch as pyaudio

            backend = pyaudio.PyAudio()
            wasapi = backend.get_host_api_info_by_type(pyaudio.paWASAPI)
            output = backend.get_device_info_by_index(
                int(wasapi["defaultOutputDevice"])
            )
            loopback = next(
                (
                    backend.get_device_info_by_index(index)
                    for index in range(backend.get_device_count())
                    if backend.get_device_info_by_index(index).get("isLoopbackDevice")
                    and str(output["name"])
                    in str(backend.get_device_info_by_index(index)["name"])
                ),
                None,
            )
            if loopback is None:
                backend.terminate()
                self.last_error = "loopback_device_unavailable"
                return False
            source_rate = int(loopback["defaultSampleRate"])
            channels = int(loopback["maxInputChannels"])

            def callback(data, _frame_count, _time_info, _status):
                try:
                    block = np.frombuffer(data, dtype=np.int16)
                    if channels > 1:
                        block = block.reshape(-1, channels).mean(axis=1)
                    block = _resample(block, source_rate)
                    with self._lock:
                        size = min(block.size, self._ring.size)
                        if size:
                            self._ring = np.concatenate((
                                self._ring[size:],
                                block[-size:].astype(np.int16),
                            ))
                except Exception:  # noqa: BLE001 - callback nunca propaga
                    pass
                return (None, pyaudio.paContinue)

            stream = backend.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=source_rate,
                input=True,
                input_device_index=int(loopback["index"]),
                frames_per_buffer=max(128, int(source_rate * 0.032)),
                stream_callback=callback,
            )
            stream.start_stream()
            self._backend = backend
            self._stream = stream
            self.last_error = None
            return True
        except Exception as error:  # noqa: BLE001 - capa opcional
            self.last_error = f"loopback_unavailable:{type(error).__name__}"
            self.stop()
            return False

    def latest(self, samples: int) -> np.ndarray:
        count = max(0, min(self._ring.size, int(samples)))
        with self._lock:
            return self._ring[-count:].copy()

    def stop(self) -> bool:
        stream, backend = self._stream, self._backend
        complete = True
        if stream is not None:
            try:
                stream.stop_stream()
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
