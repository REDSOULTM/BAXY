"""Salida de voz local de BAXY.

La voz de producto es neural, español latino (Piper ``es_MX-claude-high``
vía sherpa-onnx, Apache 2.0 + pesos MIT). SAPI queda como degradación si
el modelo neural no está en disco. El objeto de salida vive en su hilo
propietario; ``speak`` y ``cancel`` solo publican órdenes acotadas.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import math
import os
import queue
import re
import threading
import time

import numpy as np
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .assets import AssetDescriptorError, resolve_asset
from .resource_policy import cpu_session_options
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


def _espeak_exe() -> Path | None:
    configured = (os.environ.get("BAXY_ESPEAK_EXE") or "").strip()
    candidates = [
        Path(configured) if configured else None,
        Path(r"C:\Program Files\eSpeak NG\espeak-ng.exe"),
        Path(r"C:\Program Files (x86)\eSpeak NG\espeak-ng.exe"),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    return None


def _espeak_data_dir() -> Path | None:
    exe = _espeak_exe()
    if exe is not None:
        data = exe.parent / "espeak-ng-data"
        if (data / "phontab").is_file():
            return data
    configured = (os.environ.get("BAXY_ESPEAK_DATA") or "").strip()
    candidates = [
        Path(configured) if configured else None,
        Path(r"C:\Program Files\eSpeak NG\espeak-ng-data"),
        Path(r"C:\Program Files (x86)\eSpeak NG\espeak-ng-data"),
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "phontab").is_file():
            return candidate
    return None


class _PiperOnnxEngine:
    """Piper VITS ONNX + eSpeak. Sherpa rejects this export (no sample_rate meta)."""

    def __init__(self, model_path: Path) -> None:
        import onnxruntime as ort

        config_path = model_path.with_suffix(".onnx.json")
        if not config_path.is_file():
            raise FileNotFoundError("piper_config_missing")
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        mapping = payload.get("phoneme_id_map")
        if not isinstance(mapping, dict):
            raise ValueError("piper_phoneme_map_invalid")
        self._id_map = {
            str(phoneme): [int(item) for item in ids]
            for phoneme, ids in mapping.items()
            if isinstance(ids, list) and ids
        }
        inference = payload.get("inference") if isinstance(payload.get("inference"), dict) else {}
        audio = payload.get("audio") if isinstance(payload.get("audio"), dict) else {}
        espeak = payload.get("espeak") if isinstance(payload.get("espeak"), dict) else {}
        self.sample_rate = int(audio.get("sample_rate") or 22050)
        self._noise_scale = float(inference.get("noise_scale") or 0.667)
        self._length_scale = float(inference.get("length_scale") or 1.0)
        self._noise_w = float(inference.get("noise_w") or 0.8)
        self._voice = str(espeak.get("voice") or "es-419")
        self._exe = _espeak_exe()
        if self._exe is None:
            raise FileNotFoundError("espeak_missing")
        options = cpu_session_options(
            ort,
            environment_name="BAXY_VOICE_TTS_THREADS",
        )
        self._session = ort.InferenceSession(
            str(model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )

    def _phonemes(self, text: str) -> str:
        import subprocess

        completed = subprocess.run(
            [str(self._exe), "-q", "-v", self._voice, "--ipa=3", text],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return " ".join(completed.stdout.split())

    def generate(self, text: str) -> np.ndarray:
        phonemes = self._phonemes(text)
        ids = list(self._id_map.get("^", [1]))
        for character in phonemes:
            ids.extend(self._id_map.get(character, []))
        ids.extend(self._id_map.get("$", [2]))
        phoneme = np.array([ids], dtype=np.int64)
        lengths = np.array([phoneme.shape[1]], dtype=np.int64)
        scales = np.array(
            [self._noise_scale, self._length_scale, self._noise_w],
            dtype=np.float32,
        )
        output = self._session.run(
            None,
            {"input": phoneme, "input_lengths": lengths, "scales": scales},
        )[0]
        audio = np.asarray(output, dtype=np.float32).reshape(-1)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 1.0:
            audio = audio / peak
        return audio


def resolve_neural_tts_model() -> Path | None:
    """Locate the Piper ONNX voice. Missing is an honest SAPI fallback."""

    configured = (os.environ.get("BAXY_NEURAL_TTS_MODEL") or "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        return candidate if candidate.is_file() else None
    try:
        resolution = resolve_asset("neural_tts_voice")
    except AssetDescriptorError:
        resolution = None
    directories: list[Path] = []
    if resolution is not None:
        if resolution.path is not None:
            directories.append(resolution.path)
        directories.extend(resolution.candidates)
    directories.append(Path.home() / ".gemma4" / "models" / "piper")
    for directory in directories:
        if not directory.is_dir():
            continue
        direct = directory / "es_MX-claude-high.onnx"
        if direct.is_file():
            return direct
        onnx_files = sorted(directory.glob("*.onnx"))
        if len(onnx_files) == 1:
            return onnx_files[0]
    return None


def neural_tts_identity(model_path: Path | None = None) -> tuple[str, str] | None:
    path = model_path or resolve_neural_tts_model()
    if path is None or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return path.name, digest.hexdigest()


class NeuralSpeechOutput:
    """Cola TTS neural cancelable; misma frontera pública que SAPI."""

    def __init__(
        self,
        on_state: Callable[[bool], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._on_state = on_state or (lambda _speaking: None)
        self._on_error = on_error or (lambda _code: None)
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

    def _report_error(self, code: str, error: BaseException) -> None:
        self.last_error = f"{code}:{type(error).__name__}"
        try:
            self._on_error(code)
        except Exception:  # noqa: BLE001 - diagnostic observer only
            logger.debug("observador TTS rechazó el error estable")

    def _run(self) -> None:
        tts = None
        sample_rate = 22050
        try:
            import sounddevice as sd

            model_path = resolve_neural_tts_model()
            if model_path is None:
                raise FileNotFoundError("neural_tts_model_missing")
            tts = _PiperOnnxEngine(model_path)
            sample_rate = tts.sample_rate
            self._model_path = model_path
            self._voice_name = model_path.stem
            self._available = True
            self.last_error = None
        except Exception as error:  # noqa: BLE001
            tts = None
            sd = None  # type: ignore[assignment]
            self._available = False
            self.last_error = f"tts_unavailable:{type(error).__name__}"
        finally:
            self._ready.set()

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
                    waveform = tts.generate(item.text)
                    if waveform.size == 0:
                        raise RuntimeError("neural_tts_empty")
                except Exception as error:  # noqa: BLE001 - device boundary
                    self._report_error("tts_generate_failed", error)
                    continue
                if self._command_cancelled(item.generation):
                    continue
                try:
                    self._set_speaking(True)
                    sd.play(waveform, samplerate=sample_rate, blocking=False)
                    deadline = time.monotonic() + min(
                        30.0, (waveform.size / float(sample_rate)) + 1.0
                    )
                    while not self._command_cancelled(item.generation):
                        if time.monotonic() >= deadline:
                            break
                        try:
                            stream = sd.get_stream()
                            active = stream is not None and bool(
                                getattr(stream, "active", False)
                            )
                        except Exception:  # noqa: BLE001
                            active = True
                        if not active:
                            break
                        remaining = remaining_seconds(
                            deadline, 30.0, now=time.monotonic()
                        )
                        self._cancel.wait(min(0.03, remaining if remaining > 0 else 0.03))
                    try:
                        sd.stop()
                    except Exception:  # noqa: BLE001
                        pass
                except Exception as error:  # noqa: BLE001 - device boundary
                    self._report_error("tts_play_failed", error)
                    try:
                        sd.stop()
                    except Exception:  # noqa: BLE001
                        pass
                finally:
                    self._set_speaking(False)
        finally:
            try:
                if sd is not None:
                    sd.stop()
            except Exception:  # noqa: BLE001
                pass
            self._available = False
            self._set_speaking(False)
            self._stopped.set()
            with self._lock:
                if self._worker is threading.current_thread():
                    self._worker = None
                    self._stopping = False


def create_speech_output(
    on_state: Callable[[bool], None] | None = None,
    on_error: Callable[[str], None] | None = None,
) -> NeuralSpeechOutput | SapiSpeechOutput:
    """Una sola salida viva: neural si el modelo está, SAPI si no."""

    if resolve_neural_tts_model() is not None and _espeak_exe() is not None:
        return NeuralSpeechOutput(on_state, on_error)
    return SapiSpeechOutput(on_state)


__all__ = [
    "NeuralSpeechOutput",
    "SapiSpeechOutput",
    "create_speech_output",
    "neural_tts_identity",
    "resolve_neural_tts_model",
]
