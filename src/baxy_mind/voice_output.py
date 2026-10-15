"""Salida de voz local de BAXY.

La voz de producto usa Piper local y una voz por idioma. El proveedor completo
conserva el contrato de fonemas y oraciones; SAPI queda como degradación si
los activos neurales no están disponibles. El objeto de salida vive en su hilo
propietario; ``speak`` y ``cancel`` solo publican órdenes acotadas.
"""

from __future__ import annotations

import html
import logging
import math
import os
import queue
import re
import threading
import time

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .piper_tts import (
    PiperEngine,
    neural_tts_identity,
    resolve_neural_tts_model,
    resolve_piper_executable,
)
from .semantic.request import spoken_language
from .time_budget import remaining_seconds

logger = logging.getLogger(__name__)

_MAX_TEXT_CHARS = 8_192
_MAX_QUEUE_ITEMS = 16
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# SpeechVoiceSpeakFlags from sapi.h.
_SPF_ASYNC = 1
_SPF_PURGEBEFORESPEAK = 2
_SPF_IS_XML = 8

_SPANISH_LANGUAGES = ("c0a", "80a", "40a", "2c0a")
_FEMININE_VOICE_HINTS = ("sabina", "helena", "laura", "sofia", "elena", "zira")


@dataclass(frozen=True, slots=True)
class _SpeechCommand:
    generation: int
    text: str


def _tail_grace_seconds() -> float:
    try:
        value = float(os.environ.get("BAXY_VOICE_TTS_TAIL_GRACE_S", "0.55"))
    except (TypeError, ValueError):
        return 0.55
    if not math.isfinite(value):
        return 0.55
    return max(0.0, min(2.0, value))


def _bounded_wait_seconds(value: float) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(timeout):
        return 0.0
    return max(0.0, min(10.0, timeout))


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(_CONTROL_CHARACTERS.sub(" ", value).split())[:_MAX_TEXT_CHARS]


def _bounded_int_environment(name: str, default: int, minimum: int, maximum: int) -> int:
    """Lee un ajuste de SAPI sin permitir valores fuera de su contrato."""

    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _speech_markup(text: str) -> str:
    """Da a SAPI una entrega serena sin interpretar el texto del modelo.

    SAPI 5 no utiliza el elemento SSML ``prosody``: su dialecto documentado
    expone ``rate``, ``pitch`` y ``volume`` por separado. Usarlo evita depender
    de una interpretación tolerante de XML que puede cambiar entre voces.
    """

    rate = _bounded_int_environment("BAXY_VOICE_RATE", -1, -5, 5)
    pitch = _bounded_int_environment("BAXY_VOICE_PITCH", 0, -10, 10)
    volume = _bounded_int_environment("BAXY_VOICE_VOLUME", 100, 0, 100)
    escaped = html.escape(text, quote=False)
    return (
        f'<rate absspeed="{rate}"><pitch absmiddle="{pitch}">'
        f'<volume level="{volume}">{escaped}</volume></pitch></rate>'
    )


def _voice_rank(description: str, language: str, gender: str, preferred: str) -> tuple[int, int, str]:
    """Ordena voces para que BAXY nunca elija una masculina por accidente."""

    folded_description = description.casefold()
    is_spanish = any(code in language.casefold() for code in _SPANISH_LANGUAGES)
    is_feminine = gender.casefold() == "female" or any(
        hint in folded_description for hint in _FEMININE_VOICE_HINTS
    )
    if preferred and preferred in folded_description:
        return (0, 0, folded_description)
    if is_spanish and is_feminine:
        return (1, 0, folded_description)
    if is_spanish:
        return (2, 0, folded_description)
    if is_feminine:
        return (3, 0, folded_description)
    return (4, 0, folded_description)


class SapiSpeechOutput:
    """Cola TTS local, cancelable y con un único propietario del dispositivo."""

    def __init__(self, on_state: Callable[[bool], None] | None = None) -> None:
        self._on_state = on_state or (lambda _speaking: None)
        self._queue: queue.Queue[_SpeechCommand] = queue.Queue(_MAX_QUEUE_ITEMS)
        self._cancel = threading.Event()
        self._shutdown = threading.Event()
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._generation = 0
        self._stopping = False
        self._available = False
        self._speaking = False
        self.last_error: str | None = None

    @property
    def available(self) -> bool:
        return self._available

    @property
    def speaking(self) -> bool:
        return self._speaking

    def start(self, timeout: float = 5.0) -> bool:
        with self._lock:
            if self._worker is not None and not self._worker.is_alive():
                self._worker = None
                self._stopping = False
            if self._stopping:
                return False
            if self._worker is None:
                self._discard_pending()
                self._cancel.clear()
                self._shutdown.clear()
                self._stopped.clear()
                self._ready.clear()
                self._worker = threading.Thread(
                    target=self._run,
                    name="baxy-sapi-output",
                    daemon=True,
                )
                self._worker.start()
        self._ready.wait(timeout=_bounded_wait_seconds(timeout))
        with self._lock:
            return (
                self._available
                and not self._stopping
                and self._worker is not None
                and self._worker.is_alive()
            )

    def speak(self, text: str) -> bool:
        cleaned = _clean_text(text)
        if not cleaned or not self.start():
            return False
        with self._lock:
            if self._stopping or self._worker is None:
                return False
            try:
                self._queue.put_nowait(_SpeechCommand(self._generation, cleaned))
                return True
            except queue.Full:
                self.last_error = "tts_queue_full"
                return False

    def cancel(self) -> None:
        with self._lock:
            self._generation += 1
            self._cancel.set()
            self._discard_pending()

    def _discard_pending(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def stop(self, timeout: float = 5.0) -> bool:
        with self._lock:
            worker = self._worker
            if worker is None:
                return True
            self._stopping = True
            self._generation += 1
            self._cancel.set()
            self._shutdown.set()
            self._discard_pending()
        worker.join(timeout=_bounded_wait_seconds(timeout))
        stopped = not worker.is_alive() and self._stopped.is_set()
        with self._lock:
            if stopped and self._worker is worker:
                self._worker = None
                self._stopping = False
        return stopped

    def _command_cancelled(self, generation: int) -> bool:
        if self._shutdown.is_set() or self._cancel.is_set():
            return True
        with self._lock:
            return self._stopping or generation != self._generation

    def _set_speaking(self, value: bool) -> None:
        if self._speaking == value:
            return
        self._speaking = value
        try:
            self._on_state(value)
        except Exception:  # noqa: BLE001 - un observador nunca rompe el audio
            logger.debug("observador TTS rechazó el cambio de estado")

    @staticmethod
    def _select_spanish_voice(voice) -> None:
        preferred = (os.environ.get("BAXY_VOICE_SAPI_VOICE") or "").casefold()
        candidates = []
        for token in voice.GetVoices():
            try:
                description = str(token.GetDescription())
                language = str(token.GetAttribute("Language"))
            except Exception:  # noqa: BLE001 - tokens SAPI de terceros
                continue
            try:
                gender = str(token.GetAttribute("Gender"))
            except Exception:  # noqa: BLE001 - atributo opcional de SAPI
                gender = ""
            candidates.append((_voice_rank(description, language, gender, preferred), token))
        if candidates:
            candidates.sort(key=lambda item: item[0])
            voice.Voice = candidates[0][1]

    def _run(self) -> None:
        pythoncom = None
        voice = None
        try:
            import pythoncom as _pythoncom
            import win32com.client

            pythoncom = _pythoncom
            pythoncom.CoInitialize()
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            self._select_spanish_voice(voice)
            self._available = True
            self.last_error = None
        except Exception as error:  # noqa: BLE001 - frontera COM degradable
            self._available = False
            self.last_error = f"tts_unavailable:{type(error).__name__}"
        finally:
            self._ready.set()

        try:
            while (
                self._available
                and voice is not None
                and not self._shutdown.is_set()
            ):
                try:
                    item = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if not isinstance(item, _SpeechCommand):
                    continue
                with self._lock:
                    if (
                        self._stopping
                        or self._shutdown.is_set()
                        or item.generation != self._generation
                    ):
                        continue
                    self._cancel.clear()
                self._set_speaking(True)
                try:
                    voice.Speak(
                        _speech_markup(item.text),
                        _SPF_ASYNC | _SPF_PURGEBEFORESPEAK | _SPF_IS_XML,
                    )
                    while not bool(voice.WaitUntilDone(50)):
                        if self._command_cancelled(item.generation):
                            voice.Speak("", _SPF_ASYNC | _SPF_PURGEBEFORESPEAK)
                            break
                    if not self._command_cancelled(item.generation):
                        maximum_tail_grace = _tail_grace_seconds()
                        deadline = time.monotonic() + maximum_tail_grace
                        while not self._command_cancelled(item.generation):
                            remaining = remaining_seconds(
                                deadline,
                                maximum_tail_grace,
                                now=time.monotonic(),
                            )
                            if remaining <= 0.0:
                                break
                            self._cancel.wait(min(0.025, remaining))
                except Exception as error:  # noqa: BLE001 - dispositivo removible
                    self.last_error = f"tts_failed:{type(error).__name__}"
                finally:
                    self._set_speaking(False)
        finally:
            if voice is not None:
                try:
                    voice.Speak("", _SPF_ASYNC | _SPF_PURGEBEFORESPEAK)
                except Exception:  # noqa: BLE001
                    pass
            self._available = False
            self._set_speaking(False)
            if pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:  # noqa: BLE001
                    pass
            self._stopped.set()
            with self._lock:
                if self._worker is threading.current_thread():
                    self._worker = None
                    self._stopping = False


class NeuralSpeechOutput:
    """Cola TTS neural cancelable; misma frontera pública que SAPI."""

    def __init__(self, on_state: Callable[[bool], None] | None = None) -> None:
        self._on_state = on_state or (lambda _speaking: None)
        self._queue: queue.Queue[_SpeechCommand] = queue.Queue(_MAX_QUEUE_ITEMS)
        self._cancel = threading.Event()
        self._shutdown = threading.Event()
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._generation = 0
        self._stopping = False
        self._available = False
        self._speaking = False
        self._model_path: Path | None = None
        self._voice_name = "es_MX-claude-high"
        self._voice_sha256: str | None = None
        self.last_error: str | None = None

    @property
    def available(self) -> bool:
        return self._available

    @property
    def speaking(self) -> bool:
        return self._speaking

    @property
    def voice_name(self) -> str:
        return self._voice_name

    @property
    def voice_sha256(self) -> str | None:
        return self._voice_sha256

    def start(self, timeout: float = 8.0) -> bool:
        with self._lock:
            if self._worker is not None and not self._worker.is_alive():
                self._worker = None
                self._stopping = False
            if self._stopping:
                return False
            if self._worker is None:
                self._discard_pending()
                self._cancel.clear()
                self._shutdown.clear()
                self._stopped.clear()
                self._ready.clear()
                self._worker = threading.Thread(
                    target=self._run,
                    name="baxy-neural-output",
                    daemon=True,
                )
                self._worker.start()
        self._ready.wait(timeout=_bounded_wait_seconds(timeout))
        with self._lock:
            return (
                self._available
                and not self._stopping
                and self._worker is not None
                and self._worker.is_alive()
            )

    def speak(self, text: str) -> bool:
        cleaned = _clean_text(text)
        if not cleaned or not self.start():
            return False
        with self._lock:
            if self._stopping or self._worker is None:
                return False
            try:
                self._queue.put_nowait(_SpeechCommand(self._generation, cleaned))
                return True
            except queue.Full:
                self.last_error = "tts_queue_full"
                return False

    def cancel(self) -> None:
        with self._lock:
            self._generation += 1
            self._cancel.set()
            self._discard_pending()

    def _discard_pending(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def stop(self, timeout: float = 5.0) -> bool:
        with self._lock:
            worker = self._worker
            if worker is None:
                return True
            self._stopping = True
            self._generation += 1
            self._cancel.set()
            self._shutdown.set()
            self._discard_pending()
        worker.join(timeout=_bounded_wait_seconds(timeout))
        stopped = not worker.is_alive() and self._stopped.is_set()
        with self._lock:
            if stopped and self._worker is worker:
                self._worker = None
                self._stopping = False
        return stopped

    def _command_cancelled(self, generation: int) -> bool:
        if self._shutdown.is_set() or self._cancel.is_set():
            return True
        with self._lock:
            return self._stopping or generation != self._generation

    def _set_speaking(self, value: bool) -> bool:
        if self._speaking == value:
            return False
        self._speaking = value
        try:
            self._on_state(value)
        except Exception:  # noqa: BLE001
            logger.debug("observador TTS rechazó el cambio de estado")
        return True

    def _run(self) -> None:
        tts = None
        sample_rate = 22050
        try:
            import sounddevice as sd

            model_path = resolve_neural_tts_model()
            if model_path is None:
                raise FileNotFoundError("neural_tts_model_missing")
            tts = PiperEngine(model_path)
            sample_rate = tts.sample_rate
            self._model_path = model_path
            self._voice_name = model_path.stem
            self._voice_sha256 = (tts.identity or (None, None))[1]
            self._available = True
            self.last_error = None
        except Exception as error:  # noqa: BLE001
            tts = None
            sd = None  # type: ignore[assignment]
            self._available = False
            self.last_error = f"tts_unavailable:{type(error).__name__}"
        finally:
            self._ready.set()

        engines = {"es": tts}
        try:
            while self._available and tts is not None and not self._shutdown.is_set():
                try:
                    item = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if not isinstance(item, _SpeechCommand):
                    continue
                with self._lock:
                    if (
                        self._stopping
                        or self._shutdown.is_set()
                        or item.generation != self._generation
                    ):
                        continue
                    self._cancel.clear()
                try:
                    language = spoken_language(item.text)
                    selected = engines.get(language)
                    if selected is None:
                        selected_path = resolve_neural_tts_model(language)
                        if selected_path is None:
                            raise FileNotFoundError("tts_language_voice_missing")
                        selected = PiperEngine(selected_path)
                        engines[language] = selected
                    sample_rate = selected.sample_rate
                    self._model_path = selected.model_path
                    self._voice_name = self._model_path.stem
                    self._voice_sha256 = (selected.identity or (None, None))[1]
                    waveform = selected.generate(
                        item.text, cancelled=lambda: self._command_cancelled(item.generation)
                    )
                    if waveform.size == 0:
                        raise RuntimeError("neural_tts_empty")
                    if self._command_cancelled(item.generation):
                        continue
                    self._set_speaking(True)
                    # Keep device I/O on this worker. The global play() helper
                    # drops its CFFI callbacks from inside the native finished
                    # callback; it cannot own this long-lived product stream.
                    block_frames = max(1, int(sample_rate * 0.03))
                    deadline = time.monotonic() + min(
                        30.0, (waveform.size / float(sample_rate)) + 1.0
                    )
                    with sd.OutputStream(
                        samplerate=sample_rate,
                        channels=1,
                        dtype="float32",
                        blocksize=block_frames,
                    ) as stream:
                        for offset in range(0, waveform.size, block_frames):
                            if self._command_cancelled(item.generation):
                                stream.abort()
                                break
                            if time.monotonic() >= deadline:
                                stream.abort()
                                raise TimeoutError("tts_playback_deadline")
                            stream.write(waveform[offset : offset + block_frames])
                    self.last_error = None
                except InterruptedError:
                    if not self._command_cancelled(item.generation):
                        self.last_error = "tts_failed:InterruptedError"
                except Exception as error:  # noqa: BLE001
                    self.last_error = f"tts_failed:{type(error).__name__}"
                finally:
                    self._set_speaking(False)
        finally:
            self._available = False
            self._set_speaking(False)
            self._stopped.set()
            with self._lock:
                if self._worker is threading.current_thread():
                    self._worker = None
                    self._stopping = False


def create_speech_output(
    on_state: Callable[[bool], None] | None = None,
) -> NeuralSpeechOutput | SapiSpeechOutput:
    """Una sola salida viva: neural si el modelo está, SAPI si no."""

    if resolve_neural_tts_model() is not None and resolve_piper_executable() is not None:
        return NeuralSpeechOutput(on_state)
    return SapiSpeechOutput(on_state)


__all__ = [
    "NeuralSpeechOutput",
    "SapiSpeechOutput",
    "create_speech_output",
    "neural_tts_identity",
    "resolve_neural_tts_model",
]
