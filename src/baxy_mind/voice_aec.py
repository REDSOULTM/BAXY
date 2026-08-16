"""Frontend acústico local: loopback WASAPI, AEC NLMS y ducking reversible.

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
CHUNK = 512
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


class EchoCanceller:
    """Cancelador NLMS offline con estimación acotada de retardo."""

    def __init__(self, filter_samples: int = 1_024, learning_rate: float = 0.35) -> None:
        self._filter_samples = filter_samples
        self._learning_rate = learning_rate

    @staticmethod
    def _estimate_delay(microphone: np.ndarray, reference: np.ndarray) -> int:
        length = min(microphone.size, reference.size, SAMPLE_RATE * 2)
        if length < SAMPLE_RATE // 4:
            return 0
        mic = microphone[-length:].astype(np.float64)
        ref = reference[-length:].astype(np.float64)
        if np.sqrt(np.mean(ref * ref)) < 25.0:
            return 0
        mic /= np.sqrt(np.mean(mic * mic)) + 1e-9
        ref /= np.sqrt(np.mean(ref * ref)) + 1e-9
        best_delay, best_score = 0, 0.0
        for delay in range(0, int(0.25 * SAMPLE_RATE), 16):
            if delay >= length - 256:
                break
            score = abs(float(np.dot(mic[delay:], ref[: length - delay]))) / (
                length - delay
            )
            if score > best_score:
                best_delay, best_score = delay, score
        return best_delay if best_score >= 0.04 else 0

    def process(self, microphone: np.ndarray, reference: np.ndarray) -> np.ndarray:
        mic = np.asarray(microphone, dtype=np.float64).reshape(-1)
        ref = np.asarray(reference, dtype=np.float64).reshape(-1)
        if mic.size == 0 or ref.size == 0:
            return mic.astype(np.float32) / 32768.0
        count = min(mic.size, ref.size)
        mic, ref = mic[-count:], ref[-count:]
        delay = self._estimate_delay(mic, ref)
        aligned = np.zeros_like(ref)
        if delay:
            aligned[delay:] = ref[:-delay]
        else:
            aligned[:] = ref

        # Retira primero el camino directo (ganancia + retardo), que suele
        # dominar en parlantes de escritorio. NLMS aprende después las
        # reflexiones/multipath restantes. El clip completo da una estimación
        # más estable que intentar adivinar la ganancia bloque a bloque.
        reference_power = float(np.dot(aligned, aligned)) + 1e-9
        direct_gain = float(np.dot(mic, aligned)) / reference_power
        direct_gain = max(-4.0, min(4.0, direct_gain))
        residual = mic - direct_gain * aligned

        taps = self._filter_samples
        weights = np.zeros(taps, dtype=np.float64)
        history = np.zeros(taps, dtype=np.float64)
        output = np.empty(count, dtype=np.float64)
        adapted_samples = 0
        for start in range(0, count, CHUNK):
            mic_block = residual[start : start + CHUNK]
            ref_block = aligned[start : start + CHUNK]
            for index, sample in enumerate(ref_block):
                history[1:] = history[:-1]
                history[0] = sample
                predicted = float(np.dot(weights, history))
                error = mic_block[index] - predicted
                output[start + index] = error
                power = float(np.dot(history, history)) + 1e5
                # Freeze-on-double-talk: no aprender la voz cercana como eco.
                if adapted_samples < SAMPLE_RATE // 2 or abs(error) < 4.0 * (
                    abs(predicted) + 80.0
                ):
                    weights += self._learning_rate * error * history / power
                adapted_samples += 1
        return np.clip(output / 32768.0, -1.0, 1.0).astype(np.float32)


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
        with self._lock, _com_apartment():
            if self._previous is not None:
                return True
            try:
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
            with _com_apartment():
                try:
                    endpoint = self._endpoint()
                    if endpoint is None:
                        return False
                    endpoint.SetMasterVolumeLevelScalar(previous, None)
                    self._previous = None
                    return True
                except Exception as error:  # noqa: BLE001
                    logger.warning("no se pudo restaurar ducking: %s", type(error).__name__)
                    return False


__all__ = ["AudioDucker", "EchoCanceller", "LoopbackReference"]
