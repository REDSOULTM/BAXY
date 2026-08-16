r"""Pila de voz local de BAXY para Windows.

Recorrido efectivo:

    micrófono -> KWS acústico dedicado -> Silero VAD -> ASR parcial/final
                                  \-> pre-roll -> AEC/ducking -> Parakeet
                                                                  -> SAPI TTS

Hay dos modos explícitos. ``direct`` conserva el botón de micrófono y acepta
cada locución; ``wake`` escucha de forma continua mediante un clasificador
acústico ONNX dedicado. Un manifiesto calibrado puede sumar una segunda ruta:
al final de una locución exige simultáneamente evidencia acústica independiente
y un nombre canónico al principio del texto local. Un wake sin comando abre
una ventana corta para la locución siguiente. Cuando no hay un modelo acústico
calibrado, la compatibilidad léxica se habilita únicamente con una variable
explícita; no se presenta como KWS.

La captura, decodificación y salida tienen propietarios separados y acotados.
Todos los efectos degradan de forma honesta: sin loopback se informa AEC=false;
sin SAPI sigue funcionando STT; un error de voz nunca tumba el sidecar.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, replace
import json
import logging
import math
import os
import queue
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .assets import AssetDescriptorError, resolve_asset
from .time_budget import remaining_seconds
from .voice_aec import AudioDucker, EchoCanceller, LoopbackReference
from .voice_output import SapiSpeechOutput
from .wakeword import (
    AcousticWakeDetector,
    WakeWordDetection,
    WakeWordRuntimeError,
    inspect_wakeword_candidate_config,
    inspect_wakeword_config,
)
from .wake_cascade import (
    HyperspotterCascadeDetector,
    WakeCascadeConfig,
    has_strict_leading_alias,
    inspect_wake_cascade_config,
    match_bounded_lexical_wake,
    match_suffix_independent_endpoint_wake,
    time_scaled_recognition_audio,
)
from .wake_verifier import (
    OnnxWakeVerifier,
    WakeVerifierConfigurationError,
    WakeVerifierRuntimeError,
    inspect_wake_verifier_config,
)

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
VAD_WINDOW_SAMPLES = 512
TRAILING_SILENCE_S = 0.7
MIN_UTTERANCE_S = 0.3
MAX_UTTERANCE_S = 30.0
SPEECH_THRESHOLD = 0.5
WAKE_COMMAND_WINDOW_S = 8.0
PRE_ROLL_S = 0.256
STREAMING_PARTIAL_INTERVAL_S = 0.20
_DECODE_QUEUE_SIZE = 4
_DECODE_STOP = object()
_STREAMING_QUEUE_SIZE = 96
_STREAMING_STOP = object()
_ACOUSTIC_WAKE_QUEUE_SIZE = 64
_ACOUSTIC_WAKE_STOP = object()
_ACOUSTIC_WAKE_PRE_ROLL_S = 5.0
_CONTEXTUAL_HOTWORD_SCORE = 5.0
_MAX_CONTEXTUAL_HOTWORDS = 64
_CLEANUP_JOIN_SLICE_SECONDS = 0.05

STREAMING_STT_BUNDLE = (
    "sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-int8-2026-06-11"
)
_STT_REQUIRED_FILES = (
    "encoder.int8.onnx",
    "decoder.int8.onnx",
    "joiner.int8.onnx",
    "tokens.txt",
)

_LEADING_POLITENESS = {"hey", "hola", "oye", "ok", "okay", "ey"}
_DEFAULT_WAKE_ALIASES = {"baxy", "baxi", "boxy"}
_WORD_RE = re.compile(r"[\wáéíóúüñ]+", re.IGNORECASE)


def _missing_stt_files(stt_dir: Path) -> list[str]:
    return [name for name in _STT_REQUIRED_FILES if not (stt_dir / name).is_file()]


def _complete_stt_bundle(stt_dir: Path | None) -> bool:
    return stt_dir is not None and not _missing_stt_files(stt_dir)


def _registered_stt_directory() -> Path | None:
    """Read only the registered STT location, never the rest of the runtime.

    The desktop shell normally exports ``BAXY_MIND_STT_DIR`` before launching
    the sidecar. Development and diagnostic launchers do not always do so,
    therefore the voice layer has the same safe fallback as the shell. An
    incomplete or malformed registration is ignored instead of becoming an
    implicit path supplied by untrusted JSON.
    """

    local_data = os.environ.get("LOCALAPPDATA")
    if not local_data:
        return None
    manifest = Path(local_data) / "BAXYRuntime" / "mind-runtime-v1.json"
    try:
        if not manifest.is_file() or manifest.stat().st_size > 16 * 1024:
            return None
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("schema") != "baxy-mind-runtime-v1":
            return None
        candidate = Path(str(data.get("stt_dir") or ""))
        return (
            candidate
            if candidate.is_absolute() and _complete_stt_bundle(candidate)
            else None
        )
    except (OSError, TypeError, ValueError):
        return None


def resolve_stt_directory() -> Path:
    """Resolve Parakeet deterministically, with an explicit path taking priority."""

    configured = os.environ.get("BAXY_MIND_STT_DIR")
    if configured:
        return Path(configured).expanduser()
    registered = _registered_stt_directory()
    if registered is not None:
        return registered
    try:
        resolution = resolve_asset("stt_parakeet")
    except AssetDescriptorError:
        return Path()
    if resolution.path is not None:
        return resolution.path
    return resolution.candidates[0] if resolution.candidates else Path()


DEFAULT_STT_DIR = Path()


def resolve_streaming_stt_directory(offline_stt_dir: Path | None = None) -> Path | None:
    """Find the optional, local Nemotron Streaming bundle without downloading.

    BAXY intentionally keeps the offline Parakeet bundle as the mandatory
    final verifier. The streaming bundle is a sibling optional acceleration:
    it supplies only low-latency partials after an authorized turn and cannot
    silently replace the final AEC-aware decode without an A/B promotion gate.
    """

    configured = os.environ.get("BAXY_VOICE_STREAMING_STT_DIR")
    if configured:
        candidate = Path(configured).expanduser()
        return candidate if _complete_stt_bundle(candidate) else None
    candidates: list[Path] = []
    if offline_stt_dir is not None:
        candidates.append(offline_stt_dir.parent / STREAMING_STT_BUNDLE)
    try:
        resolution = resolve_asset("stt_nemotron_streaming")
    except AssetDescriptorError:
        resolution = None
    if resolution is not None:
        candidates.extend(resolution.candidates)
    for candidate in candidates:
        if _complete_stt_bundle(candidate):
            return candidate
    return None


def _streaming_stt_enabled() -> bool:
    # A newer model must win an A/B gate before it consumes memory/CPU in the
    # default voice path. ``on`` deliberately requires an explicit rollout;
    # the Parakeet final verifier remains the validated baseline otherwise.
    value = (os.environ.get("BAXY_VOICE_STREAMING_STT") or "off").strip().casefold()
    return value in {"1", "true", "on", "yes", "enabled"}


def _lexical_wake_fallback_enabled() -> bool:
    """Allow the legacy STT-prefix path only as an explicit migration mode."""

    value = (
        (os.environ.get("BAXY_VOICE_LEXICAL_WAKE_FALLBACK") or "off").strip().casefold()
    )
    return value in {"1", "true", "on", "yes", "enabled"}


def _streaming_language() -> str:
    value = (os.environ.get("BAXY_VOICE_STREAMING_LANGUAGE") or "auto").strip()
    # Nemotron accepts a documented locale or ``auto``. Keep an invalid value
    # from breaking a microphone session; users can choose an explicit locale
    # such as es-ES or en-US when their corpus has measured that advantage.
    return (
        value if re.fullmatch(r"(?:auto|[a-z]{2}(?:-[A-Za-z]{2})?)", value) else "auto"
    )


def _stt_model_name(stt_dir: Path | None) -> str | None:
    if stt_dir is None:
        return None
    name = stt_dir.name.casefold()
    if "nemotron-3.5-asr-streaming" in name:
        return "nemotron-3.5-asr-streaming-0.6b-560ms-int8"
    if "parakeet-tdt-0.6b-v3" in name:
        return "parakeet-tdt-0.6b-v3-int8"
    return stt_dir.name


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character for character in normalized if not unicodedata.combining(character)
    )


def _compile_contextual_hotwords(
    tokens_path: Path,
    terms: Iterable[str],
) -> str:
    """Encode authenticated closed entities into Parakeet BPE token paths.

    sherpa-onnx accepts in-memory hotwords as token sequences for transducers.
    Keeping this derived from ``tokens.txt`` avoids a brand list, a downloaded
    tokenizer, or unverified free-form prompt text.
    """

    try:
        lines = tokens_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return ""
    by_initial: dict[str, list[str]] = {}
    for line in lines:
        try:
            piece, token_id = line.rsplit(" ", 1)
        except ValueError:
            continue
        if (
            not token_id.isdigit()
            or not piece
            or piece.startswith("<")
            or any(character.isspace() for character in piece)
        ):
            continue
        by_initial.setdefault(piece[0], []).append(piece)
    for candidates in by_initial.values():
        candidates.sort(key=len, reverse=True)

    encoded: list[str] = []
    seen: set[str] = set()
    for raw in terms:
        if len(encoded) >= _MAX_CONTEXTUAL_HOTWORDS or not isinstance(raw, str):
            break
        words = [
            "".join(character for character in word if character.isalnum())
            for word in _fold(raw.replace("_", " ")).split()
        ]
        words = [word for word in words if word]
        if not words:
            continue
        surface = "▁" + "▁".join(words)
        best: list[list[str] | None] = [None] * (len(surface) + 1)
        best[0] = []
        for index in range(len(surface)):
            if best[index] is None:
                continue
            for piece in by_initial.get(surface[index], ()):
                if not surface.startswith(piece, index):
                    continue
                end = index + len(piece)
                candidate = [*best[index], piece]
                if best[end] is None or len(candidate) < len(best[end]):
                    best[end] = candidate
        if best[-1] is None:
            continue
        sequence = " ".join(best[-1])
        if sequence not in seen:
            seen.add(sequence)
            encoded.append(sequence)
    return "/".join(encoded)


class WakePhraseMatcher:
    """Normaliza un prefijo ya autorizado; nunca es un detector acústico."""

    def __init__(self, aliases: set[str] | None = None) -> None:
        configured = {
            _fold(item.strip())
            for item in (os.environ.get("BAXY_VOICE_WAKE_ALIASES") or "").split(",")
            if _WORD_RE.fullmatch(item.strip())
        }
        self._aliases = configured or {
            _fold(item) for item in (aliases or _DEFAULT_WAKE_ALIASES)
        }

    @property
    def aliases(self) -> tuple[str, ...]:
        """Return the configured wake protocol vocabulary, deterministically."""

        return tuple(sorted(self._aliases))

    def strip(self, transcript: str) -> tuple[bool, str]:
        matches = list(_WORD_RE.finditer(transcript))
        if not matches:
            return False, transcript.strip()
        index = 0
        if _fold(matches[0].group(0)) in _LEADING_POLITENESS:
            index = 1
        if index >= len(matches) or _fold(matches[index].group(0)) not in self._aliases:
            return False, transcript.strip()
        return True, transcript[matches[index].end() :].lstrip(" ,.:;!?¡¿-")


@dataclass(frozen=True)
class _DecodeRequest:
    """Audio listo para ASR con la autoridad que abrió el turno."""

    audio: np.ndarray
    reference: np.ndarray
    origin: str
    session_epoch: int | None = None
    wake_confidence: float | None = None
    wake_verification_start_sample: int = 0
    wake_method: str | None = None
    wake_verifier_score: float | None = None
    wake_lexical_rescue_required: bool = False


class SileroVad:
    """Adaptador pequeño a Silero VAD 6.x oficial, ONNX/CPU."""

    window_size_samples = VAD_WINDOW_SAMPLES

    def __init__(self) -> None:
        import torch
        from silero_vad import load_silero_vad

        self._torch = torch
        self._model = load_silero_vad(onnx=True)

    def process(self, frame: np.ndarray) -> float:
        tensor = self._torch.from_numpy(np.asarray(frame, dtype=np.float32))
        return float(self._model(tensor, SAMPLE_RATE).item())

    def reset(self) -> None:
        self._model.reset_states()


def _rms(frame: np.ndarray) -> float:
    array = np.asarray(frame, dtype=np.float64)
    return float(np.sqrt(np.mean(array * array))) if array.size else 0.0


def _looks_like_echo(microphone: np.ndarray, reference: np.ndarray) -> bool:
    """Correlación normalizada y tolerante al retardo para el barge-in."""

    mic = np.asarray(microphone, dtype=np.float64).reshape(-1)
    ref = np.asarray(reference, dtype=np.float64).reshape(-1)
    if mic.size < 128 or ref.size < mic.size or _rms(ref) < 20.0:
        return False
    mic = mic - mic.mean()
    mic_norm = np.linalg.norm(mic)
    if mic_norm < 1e-6:
        return False
    best = 0.0
    maximum_delay = min(int(0.25 * SAMPLE_RATE), ref.size - mic.size)
    for delay in range(0, maximum_delay + 1, 128):
        end = ref.size - delay
        candidate = ref[end - mic.size : end].astype(np.float64)
        candidate -= candidate.mean()
        denominator = mic_norm * np.linalg.norm(candidate)
        if denominator > 1e-6:
            best = max(best, abs(float(np.dot(mic, candidate))) / denominator)
    return best >= 0.55


def _decode_offline_text(
    recognizer: Any,
    audio: np.ndarray,
    *,
    hotwords: str = "",
) -> str:
    stream = (
        recognizer.create_stream(hotwords=hotwords)
        if hotwords
        else recognizer.create_stream()
    )
    stream.accept_waveform(SAMPLE_RATE, np.asarray(audio, dtype=np.float32))
    recognizer.decode_stream(stream)
    return (stream.result.text or "").strip()


def _wake_turn_start_sample(
    speech_flags: Iterable[bool],
    *,
    frame_samples: int = VAD_WINDOW_SAMPLES,
    silence_frames: int | None = None,
) -> int:
    """Locate the last VAD turn in KWS history without consulting its text."""

    flags = tuple(bool(value) for value in speech_flags)
    if frame_samples <= 0:
        raise ValueError("wake_turn_frame_samples_invalid")
    trailing = silence_frames or max(
        1, round(TRAILING_SILENCE_S * SAMPLE_RATE / frame_samples)
    )
    speech_indices = [index for index, value in enumerate(flags) if value]
    if not speech_indices:
        return 0
    start = speech_indices[-1]
    silence = 0
    for index in range(start - 1, -1, -1):
        if flags[index]:
            start = index
            silence = 0
        else:
            silence += 1
            if silence >= trailing:
                break
    context_frames = max(1, round(PRE_ROLL_S * SAMPLE_RATE / frame_samples))
    return max(0, start - context_frames) * frame_samples


def _wake_frame_count(
    duration_seconds: float,
    *,
    frame_samples: int = VAD_WINDOW_SAMPLES,
) -> int:
    """Quantize one positive duration exactly as the microphone capture loop."""

    if (
        not math.isfinite(duration_seconds)
        or duration_seconds <= 0.0
        or frame_samples <= 0
    ):
        raise ValueError("wake_frame_count_contract_invalid")
    return max(1, int(duration_seconds * SAMPLE_RATE / frame_samples))


def _wake_activity_onset_sample(
    probabilities: Iterable[float],
    *,
    threshold: float,
    frame_samples: int = VAD_WINDOW_SAMPLES,
    alignment_samples: int = 320,
    default_start_sample: int = 0,
) -> int:
    """Locate low-energy wake activity and align it to the CTC convolution stride."""

    values = tuple(float(value) for value in probabilities)
    if (
        not 0.0 < threshold < 1.0
        or frame_samples <= 0
        or alignment_samples <= 0
        or default_start_sample < 0
        or any(not math.isfinite(value) for value in values)
    ):
        raise ValueError("wake_activity_onset_contract_invalid")
    index = next(
        (position for position, value in enumerate(values) if value >= threshold),
        None,
    )
    if index is None:
        return default_start_sample
    sample = index * frame_samples
    return round(sample / alignment_samples) * alignment_samples


@dataclass(slots=True)
class _VoiceCleanupJob:
    """One retained teardown owner for a microphone-session generation."""

    sequence: int
    expected_session: int | None
    done: threading.Event
    launch_done: threading.Event
    thread: threading.Thread | None = None
    shutdown_requested: bool = False
    output_stop_attempted: bool = False
    output_stopped: bool = False
    timeout_observed: bool = False
    timeout_reported: bool = False
    applied: bool = False
    success: bool = False
    speech_epoch: int = 0
    request_version: int = 0


class VoiceEngine:
    """Wake/direct capture, VAD, AEC, STT, TTS and barge-in orchestration."""

    def __init__(
        self,
        on_transcript: Callable[[str], None],
        on_event: Callable[[dict[str, Any]], None] | None = None,
        *,
        correction_terms: Iterable[str] = (),
    ) -> None:
        self._on_transcript = on_transcript
        self._on_event = on_event or (lambda _event: None)
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        # This lock only publishes cleanup ownership. It is never held across
        # device I/O, worker joins or the lifecycle lock.
        self._cleanup_lock = threading.Lock()
        self._cleanup_condition = threading.Condition(self._cleanup_lock)
        self._cleanup_job: _VoiceCleanupJob | None = None
        self._cleanup_sequence = 0
        self._shutdown_requested = False
        self._speech_inflight = 0
        self._speech_epoch = 0
        self._stop_event = threading.Event()
        self._capture_worker: threading.Thread | None = None
        self._decode_worker: threading.Thread | None = None
        self._streaming_worker: threading.Thread | None = None
        self._acoustic_wake_worker: threading.Thread | None = None
        self._decode_queue: queue.Queue[object] = queue.Queue(_DECODE_QUEUE_SIZE)
        self._streaming_queue: queue.Queue[object] = queue.Queue(_STREAMING_QUEUE_SIZE)
        self._acoustic_wake_queue: queue.Queue[object] = queue.Queue(
            _ACOUSTIC_WAKE_QUEUE_SIZE
        )
        self._acoustic_wake_hits: queue.Queue[tuple[int, WakeWordDetection]] = (
            queue.Queue(8)
        )
        # ASR and KWS work carry this generation so late workers cannot cross
        # a stop/start boundary into a new microphone session.
        self._session_epoch = 0
        self._wake_epoch = 0
        self._failure_stop_requested = False
        self._capture_ready_event = threading.Event()
        self._lifecycle_state = "off"
        self._streaming_session = 0
        self._recognizer = None
        self._streaming_recognizer = None
        self._acoustic_wake_detector: (
            AcousticWakeDetector | HyperspotterCascadeDetector | None
        ) = None
        self._wake_verifier: OnnxWakeVerifier | None = None
        self._wake_cascade_config: WakeCascadeConfig | None = None
        self._stt_directory: Path | None = None
        self._streaming_stt_directory: Path | None = None
        self._streaming_error: str | None = None
        self._wake_backend = "unavailable"
        self._wake_model_name: str | None = None
        self._wake_phrase: str | None = None
        self._wake_error: str | None = None
        self._wake_verifier_error: str | None = None
        self._vad: SileroVad | None = None
        self._corrector = None
        self._correction_terms = tuple(correction_terms)
        self._contextual_hotwords = ""
        self._wake_hotwords = ""
        self._mode = "off"
        self._armed_until = 0.0
        self._loopback = LoopbackReference()
        self._ducker = AudioDucker()
        self._output = SapiSpeechOutput(self._on_tts_state)
        self._wake = WakePhraseMatcher()
        self._input_device_name = ""
        self.last_error: str | None = None

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    @property
    def speaking(self) -> bool:
        return self._output.speaking

    def _emit(self, event: str, **fields: Any) -> None:
        payload = {"event": event, **fields}
        try:
            self._on_event(payload)
        except Exception:  # noqa: BLE001 - protocolo observador degradable
            logger.debug("observador de voz rechazó evento %s", event)

    @classmethod
    def probe(cls) -> dict[str, Any]:
        stt_dir = resolve_stt_directory()
        missing = _missing_stt_files(stt_dir)
        streaming_dir = (
            resolve_streaming_stt_directory(stt_dir)
            if _streaming_stt_enabled()
            else None
        )
        dependencies: dict[str, bool] = {}
        for module in (
            "sherpa_onnx",
            "sounddevice",
            "silero_vad",
            "win32com.client",
            "livekit.wakeword",
            "onnxruntime",
        ):
            try:
                __import__(module, fromlist=["*"])
                dependencies[module] = True
            except Exception:  # noqa: BLE001
                dependencies[module] = False
        cascade_config, cascade_error = inspect_wake_cascade_config()
        wake_config, wake_error = inspect_wakeword_config()
        verifier_config, verifier_error = inspect_wake_verifier_config()
        wake_backend = (
            "acoustic"
            if cascade_config is not None and dependencies.get("onnxruntime", False)
            else "acoustic"
            if wake_config is not None and dependencies.get("livekit.wakeword", False)
            else "lexical_fallback"
            if _lexical_wake_fallback_enabled()
            else "unavailable"
        )
        if cascade_config is not None and not dependencies.get("onnxruntime", False):
            cascade_error = "wake_cascade_runtime_missing"
        if wake_config is not None and not dependencies.get("livekit.wakeword", False):
            wake_error = "wake_word_runtime_missing"
        input_available = False
        try:
            import sounddevice as sd

            default_input = sd.query_devices(kind="input")
            input_available = int(default_input["max_input_channels"]) > 0
        except Exception:  # noqa: BLE001
            pass
        available = (
            not missing
            and input_available
            and dependencies.get("sherpa_onnx", False)
            and dependencies.get("sounddevice", False)
            and dependencies.get("silero_vad", False)
        )
        return {
            "available": available,
            "input": input_available,
            "stt": not missing and dependencies.get("sherpa_onnx", False),
            "vad": dependencies.get("silero_vad", False),
            "tts": dependencies.get("win32com.client", False),
            "aec": _module_available("pyaudiowpatch"),
            "ducking": _module_available("pycaw"),
            "missing": missing,
            "sttModel": _stt_model_name(stt_dir) if not missing else None,
            "streamingStt": bool(
                streaming_dir and dependencies.get("sherpa_onnx", False)
            ),
            "streamingSttModel": _stt_model_name(streaming_dir),
            "wakeWord": wake_backend == "acoustic",
            "wakeBackend": wake_backend,
            "wakeWordModel": (
                "baxy-hyperspotter-logmel-cascade-v1"
                if cascade_config is not None
                else wake_config.model_name
                if wake_config
                else None
            ),
            "wakeWordPhrase": (
                cascade_config.phrase
                if cascade_config is not None
                else wake_config.phrase
                if wake_config
                else None
            ),
            "wakeWordError": cascade_error
            if cascade_config is not None
            else wake_error,
            "wakeCascadeError": cascade_error,
            "wakeVerifier": bool(
                cascade_config is not None
                or verifier_config is not None
                and dependencies.get("onnxruntime", False)
            ),
            "wakeVerifierError": verifier_error,
            "wakeEndpoint": bool(
                cascade_config is not None
                and cascade_config.endpoint_lexical_verifier_index is not None
            ),
            "lexicalWakeFallback": _lexical_wake_fallback_enabled(),
        }

    def load(self) -> None:
        if self._recognizer is not None:
            # A transient KWS failure must not require rebuilding Parakeet just
            # to attempt a later explicit wake start.
            if self._acoustic_wake_detector is None:
                self._load_acoustic_wake_detector()
            return
        import sherpa_onnx

        stt_dir = resolve_stt_directory()
        for required in _missing_stt_files(stt_dir):
            raise FileNotFoundError(f"Falta {required} en {stt_dir}")
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(stt_dir / "encoder.int8.onnx"),
            decoder=str(stt_dir / "decoder.int8.onnx"),
            joiner=str(stt_dir / "joiner.int8.onnx"),
            tokens=str(stt_dir / "tokens.txt"),
            num_threads=max(2, min(6, (os.cpu_count() or 4) // 2)),
            model_type="nemo_transducer",
            decoding_method="modified_beam_search",
            max_active_paths=8,
            hotwords_score=_CONTEXTUAL_HOTWORD_SCORE,
        )
        self._stt_directory = stt_dir
        self._contextual_hotwords = _compile_contextual_hotwords(
            stt_dir / "tokens.txt",
            self._correction_terms,
        )
        self._wake_hotwords = _compile_contextual_hotwords(
            stt_dir / "tokens.txt",
            self._wake.aliases,
        )
        self._vad = SileroVad()
        try:
            from .corrector import FuzzyCorrector

            self._corrector = FuzzyCorrector(
                {
                    "wake_words": self._wake.aliases,
                    "catalog_entities": self._correction_terms,
                }
            )
        except Exception:  # noqa: BLE001 - mejora opcional
            self._corrector = None
        stream = self._recognizer.create_stream()
        stream.accept_waveform(
            SAMPLE_RATE, np.zeros(SAMPLE_RATE // 2, dtype=np.float32)
        )
        self._recognizer.decode_stream(stream)
        self._load_acoustic_wake_detector()
        self._load_streaming_recognizer(sherpa_onnx, stt_dir)
        self._output.start()

    def _load_acoustic_wake_detector(self) -> None:
        """Load only a calibrated KWS model; STT is never its substitute."""

        self._acoustic_wake_detector = None
        self._wake_verifier = None
        self._wake_cascade_config = None
        self._wake_model_name = None
        self._wake_phrase = None
        self._wake_verifier_error = None
        cascade_config, cascade_error = inspect_wake_cascade_config()
        if cascade_config is not None:
            if (
                cascade_config.direct_lexical_verifier_index is not None
                and not math.isclose(
                    cascade_config.direct_lexical_hotwords_score,
                    _CONTEXTUAL_HOTWORD_SCORE,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
            ):
                self._wake_error = "wake_cascade_hotwords_score_mismatch"
                self._wake_backend = "unavailable"
                return
            try:
                cascade_detector = HyperspotterCascadeDetector(cascade_config)
            except WakeWordRuntimeError as runtime_error:
                self._wake_error = str(runtime_error)
                self._wake_backend = (
                    "lexical_fallback"
                    if _lexical_wake_fallback_enabled()
                    else "unavailable"
                )
                logger.warning("Cascado wake no se pudo cargar: %s", runtime_error)
                return
            self._acoustic_wake_detector = cascade_detector
            self._wake_cascade_config = cascade_config
            self._wake_backend = "acoustic"
            self._wake_model_name = "baxy-hyperspotter-logmel-cascade-v1"
            self._wake_phrase = cascade_config.phrase
            self._wake_error = None
            return
        direct_config, direct_error = inspect_wakeword_config()
        candidate_config, candidate_error = inspect_wakeword_candidate_config()
        config = direct_config
        detector_config = direct_config
        verifier = None
        verifier_config, verifier_error = inspect_wake_verifier_config()
        if verifier_config is None:
            self._wake_verifier_error = verifier_error
        elif candidate_config is None:
            self._wake_verifier_error = candidate_error
        elif not math.isclose(
            candidate_config.threshold,
            verifier_config.strong_threshold,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            self._wake_verifier_error = "wake_verifier_stage1_threshold_mismatch"
        elif (
            verifier_config.stage1_model_sha256 != candidate_config.model_sha256
            or verifier_config.stage1_phrase != candidate_config.phrase
            or verifier_config.stage1_hop_samples != candidate_config.hop_samples
            or not math.isclose(
                verifier_config.stage1_pre_roll_seconds,
                _ACOUSTIC_WAKE_PRE_ROLL_S,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            or not math.isclose(
                verifier_config.stage1_debounce_seconds,
                candidate_config.debounce_seconds,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            self._wake_verifier_error = "wake_verifier_stage1_contract_mismatch"
        else:
            try:
                verifier = OnnxWakeVerifier(verifier_config)
            except (
                WakeVerifierConfigurationError,
                WakeVerifierRuntimeError,
            ) as runtime_error:
                self._wake_verifier_error = str(runtime_error)
                logger.warning("Verificador wake no se pudo cargar: %s", runtime_error)
            else:
                config = candidate_config
                detector_config = replace(
                    candidate_config,
                    threshold=verifier_config.broad_threshold,
                )
        if config is None or detector_config is None:
            self._wake_error = (
                self._wake_verifier_error
                or direct_error
                or candidate_error
                or cascade_error
                or "wake_word_calibration_required"
            )
            self._wake_backend = (
                "lexical_fallback"
                if _lexical_wake_fallback_enabled()
                else "unavailable"
            )
            return
        try:
            detector = AcousticWakeDetector(detector_config)
        except WakeWordRuntimeError as runtime_error:
            self._wake_error = str(runtime_error)
            self._wake_backend = (
                "lexical_fallback"
                if _lexical_wake_fallback_enabled()
                else "unavailable"
            )
            logger.warning("KWS acústico no se pudo cargar: %s", runtime_error)
            return
        self._acoustic_wake_detector = detector
        self._wake_verifier = verifier
        self._wake_backend = "acoustic"
        self._wake_model_name = config.model_name
        self._wake_phrase = config.phrase
        self._wake_error = None

    def _endpoint_wake_available(self) -> bool:
        config = self._wake_cascade_config
        return bool(
            isinstance(self._acoustic_wake_detector, HyperspotterCascadeDetector)
            and config is not None
            and config.endpoint_lexical_verifier_index is not None
            and config.endpoint_lexical_score_threshold is not None
            and config.endpoint_lexical_aliases
            and self._wake_hotwords
        )

    def _load_streaming_recognizer(
        self, sherpa_onnx: Any, offline_stt_dir: Path
    ) -> None:
        """Load the optional native-streaming first pass without risking STT.

        The primary final decode remains Parakeet because it is the path that
        has passed BAXY's AEC, entity-repair and command-routing gates. A
        missing, incompatible or resource-constrained streaming export only
        disables partial hypotheses; it never prevents the microphone from
        starting.
        """

        self._streaming_recognizer = None
        self._streaming_stt_directory = None
        self._streaming_error = None
        if not _streaming_stt_enabled():
            self._streaming_error = "streaming_stt_disabled"
            return
        stt_dir = resolve_streaming_stt_directory(offline_stt_dir)
        if stt_dir is None:
            self._streaming_error = "streaming_stt_bundle_missing"
            return
        try:
            recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
                encoder=str(stt_dir / "encoder.int8.onnx"),
                decoder=str(stt_dir / "decoder.int8.onnx"),
                joiner=str(stt_dir / "joiner.int8.onnx"),
                tokens=str(stt_dir / "tokens.txt"),
                num_threads=max(2, min(6, (os.cpu_count() or 4) // 2)),
                model_type="nemo_transducer",
                decoding_method="greedy_search",
                enable_endpoint_detection=False,
                provider="cpu",
            )
            # Run a harmless warm-up before live capture, so the first spoken
            # word does not pay allocator/session initialization latency.
            stream = recognizer.create_stream()
            stream.set_option("language", _streaming_language())
            stream.accept_waveform(
                SAMPLE_RATE, np.zeros(SAMPLE_RATE // 2, dtype=np.float32)
            )
            while recognizer.is_ready(stream):
                recognizer.decode_stream(stream)
            self._streaming_recognizer = recognizer
            self._streaming_stt_directory = stt_dir
        except Exception as error:  # noqa: BLE001 - optional acceleration only
            self._streaming_error = f"streaming_stt_unavailable:{type(error).__name__}"
            logger.warning(
                "Nemotron Streaming no se pudo cargar: %s", type(error).__name__
            )

    def start(self, mode: str = "direct") -> bool:
        """Start one serialized microphone session."""

        if mode not in {"direct", "wake"}:
            raise ValueError("voice_mode_invalid")
        if self._cleanup_blocks_start():
            return self._reject_start_during_cleanup()
        with self._lifecycle_lock:
            # A stop can be published after the optimistic precheck but before
            # this lifecycle owner is acquired.
            if self._cleanup_blocks_start():
                return self._reject_start_during_cleanup()
            return self._start(mode)

    def _cleanup_blocks_start(self) -> bool:
        """Reap a completed owner or report an active/failed cleanup barrier."""

        with self._cleanup_lock:
            if self._shutdown_requested:
                return True
            job = self._cleanup_job
            if job is None:
                return False
            thread = job.thread
            if (
                not job.done.is_set()
                or thread is None
                or thread.is_alive()
                or not job.success
            ):
                return True
            self._cleanup_job = None
            return False

    def _reject_start_during_cleanup(self) -> bool:
        self.last_error = "voice_session_still_stopping"
        self._emit("error", code=self.last_error)
        self._emit(
            "state",
            mode="off",
            listening=False,
            speaking=self.speaking,
        )
        return False

    def _start(self, mode: str) -> bool:
        rejected = False
        existing_mode = "off"
        reused_session = False
        session_epoch: int | None = None
        capture_ready_event: threading.Event | None = None
        with self._lock:
            for name in (
                "_capture_worker",
                "_decode_worker",
                "_streaming_worker",
                "_acoustic_wake_worker",
            ):
                worker = getattr(self, name)
                if worker is not None and not worker.is_alive():
                    setattr(self, name, None)
            live_workers = any(
                worker is not None
                for worker in (
                    self._capture_worker,
                    self._decode_worker,
                    self._streaming_worker,
                    self._acoustic_wake_worker,
                )
            )
            if live_workers and self._lifecycle_state != "ready":
                rejected = True
                self.last_error = "voice_session_still_stopping"
                existing_mode = "off"
            if rejected:
                pass
            elif self._capture_worker is not None:
                if mode == "wake" and self._wake_backend == "unavailable":
                    rejected = True
                    existing_mode = self._mode
                else:
                    previous_mode = self._mode
                    self._mode = mode
                    if previous_mode != mode:
                        self._reset_acoustic_wake()
                    reused_session = True
            else:
                self.load()
                if mode == "wake" and self._wake_backend == "unavailable":
                    self._mode = "off"
                    self._lifecycle_state = "off"
                    self.last_error = self._wake_error or "wake_word_unavailable"
                    rejected = True
                else:
                    self._mode = mode
                    self._lifecycle_state = "starting"
                    self._session_epoch += 1
                    session_epoch = self._session_epoch
                    self._wake_epoch += 1
                    self._failure_stop_requested = False
                    self._capture_ready_event = threading.Event()
                    capture_ready_event = self._capture_ready_event
                    # Each generation owns a new event.  A worker that missed a
                    # timed join remains cancelled even after a later restart.
                    self._stop_event = threading.Event()
                    stop_event = self._stop_event
                    self._decode_queue = queue.Queue(_DECODE_QUEUE_SIZE)
                    self._streaming_queue = queue.Queue(_STREAMING_QUEUE_SIZE)
                    self._acoustic_wake_queue = queue.Queue(_ACOUSTIC_WAKE_QUEUE_SIZE)
                    self._acoustic_wake_hits = queue.Queue(8)
                    decode_queue = self._decode_queue
                    streaming_queue = self._streaming_queue
                    acoustic_wake_queue = self._acoustic_wake_queue
                    acoustic_wake_hits = self._acoustic_wake_hits
                    self._loopback.start()
                    self._decode_worker = threading.Thread(
                        target=self._decode_loop,
                        args=(decode_queue, session_epoch, stop_event),
                        name="baxy-voice-decode",
                        daemon=True,
                    )
                    if self._streaming_recognizer is not None:
                        self._streaming_worker = threading.Thread(
                            target=self._streaming_loop,
                            args=(streaming_queue, session_epoch, stop_event),
                            name="baxy-voice-streaming",
                            daemon=True,
                        )
                    if self._acoustic_wake_detector is not None:
                        self._acoustic_wake_worker = threading.Thread(
                            target=self._acoustic_wake_loop,
                            args=(
                                acoustic_wake_queue,
                                acoustic_wake_hits,
                                self._acoustic_wake_detector,
                                session_epoch,
                                stop_event,
                            ),
                            name="baxy-voice-wakeword",
                            daemon=True,
                        )
                    self._capture_worker = threading.Thread(
                        target=self._capture_loop,
                        args=(
                            session_epoch,
                            stop_event,
                            decode_queue,
                            streaming_queue,
                            acoustic_wake_queue,
                            acoustic_wake_hits,
                            capture_ready_event,
                        ),
                        name="baxy-voice-capture",
                        daemon=True,
                    )
                    self._decode_worker.start()
                    if self._streaming_worker is not None:
                        self._streaming_worker.start()
                    if self._acoustic_wake_worker is not None:
                        self._acoustic_wake_worker.start()
                    self._capture_worker.start()
        if rejected:
            self._emit(
                "error",
                code=self.last_error or self._wake_error or "wake_word_unavailable",
            )
            if existing_mode:
                self._emit(
                    "state",
                    mode=existing_mode,
                    listening=existing_mode != "off",
                    speaking=self.speaking,
                )
            return False
        if reused_session:
            self._emit("state", mode=mode, listening=True, speaking=self.speaking)
            return True
        if capture_ready_event is None or session_epoch is None:
            return False
        if not capture_ready_event.wait(5.0):
            self._fail_capture_session("capture_start_timeout", session_epoch)
        with self._lock:
            return (
                self._session_epoch == session_epoch
                and self._lifecycle_state == "ready"
                and self._mode == mode
                and self._capture_worker is not None
                and self._capture_worker.is_alive()
            )

    def stop(self, timeout: float = 10.0) -> bool:
        """Stop the current session before allowing a new one to begin."""

        return self._stop(timeout=timeout)

    @staticmethod
    def _cleanup_timeout(timeout: float) -> float:
        try:
            maximum_timeout = float(timeout)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(maximum_timeout):
            return 0.0
        return max(0.0, min(30.0, maximum_timeout))

    def _stop(
        self,
        timeout: float = 10.0,
        *,
        expected_session: int | None = None,
        shutdown: bool = False,
    ) -> bool:
        """Join one retained cleanup owner inside this caller's own budget."""

        maximum_timeout = self._cleanup_timeout(timeout)
        deadline = time.monotonic() + maximum_timeout
        job = self._request_cleanup(
            expected_session=expected_session,
            shutdown=shutdown,
        )
        if not job.done.is_set() and not job.launch_done.is_set():
            job.launch_done.wait(
                timeout=remaining_seconds(
                    deadline,
                    maximum_timeout,
                    now=time.monotonic(),
                )
            )
        thread = job.thread
        if (
            job.launch_done.is_set()
            and thread is not None
            and thread is not threading.current_thread()
            and thread.is_alive()
        ):
            thread.join(
                timeout=remaining_seconds(
                    deadline,
                    maximum_timeout,
                    now=time.monotonic(),
                )
            )
        with self._cleanup_lock:
            if job.done.is_set():
                return job.success
            job.timeout_observed = True
        # Do not invoke observers here: they are user code and cannot be
        # allowed to extend this caller's completed timeout.
        self.last_error = self.last_error or "voice_stop_timeout"
        return False

    def _request_cleanup(
        self,
        *,
        expected_session: int | None = None,
        shutdown: bool = False,
    ) -> _VoiceCleanupJob:
        """Publish or reuse the sole cleanup owner without lifecycle I/O."""

        with self._cleanup_lock:
            if shutdown:
                self._shutdown_requested = True
            current = self._cleanup_job
            if current is not None and not current.done.is_set():
                updated_expected_session = current.expected_session
                if expected_session is None or (
                    current.expected_session is not None
                    and expected_session != current.expected_session
                ):
                    updated_expected_session = None
                if updated_expected_session != current.expected_session:
                    current.expected_session = updated_expected_session
                    current.request_version += 1
                if shutdown:
                    current.shutdown_requested = True
                return current
            if current is not None:
                reusable = (
                    current.applied
                    and current.success
                    and self._speech_inflight == 0
                    and current.speech_epoch == self._speech_epoch
                    and (not shutdown or current.output_stopped)
                )
                if reusable:
                    return current
            self._cleanup_sequence += 1
            job = _VoiceCleanupJob(
                sequence=self._cleanup_sequence,
                expected_session=expected_session,
                shutdown_requested=shutdown,
                done=threading.Event(),
                launch_done=threading.Event(),
                speech_epoch=self._speech_epoch,
            )
            thread = threading.Thread(
                target=self._run_cleanup,
                args=(job,),
                name=f"baxy-voice-cleanup-{job.sequence}",
                daemon=True,
            )
            job.thread = thread
            self._cleanup_job = job
        try:
            thread.start()
        except BaseException:  # noqa: BLE001 - retain failed ownership
            with self._lock:
                self.last_error = "voice_cleanup_start_failed"
                self._mode = "off"
                self._lifecycle_state = "failed"
                self._failure_stop_requested = True
            with self._cleanup_lock:
                job.timeout_observed = True
                job.success = False
                job.launch_done.set()
                job.done.set()
            return job
        job.launch_done.set()
        return job

    @staticmethod
    def _signal_cleanup_queue(
        target: queue.Queue[object],
        sentinel: object,
    ) -> None:
        try:
            target.put_nowait(sentinel)
        except queue.Full:
            try:
                target.get_nowait()
                target.put_nowait(sentinel)
            except (queue.Empty, queue.Full):
                pass

    def _stop_output_if_requested(
        self,
        job: _VoiceCleanupJob,
        attempt: Callable[[Callable[[], Any]], bool],
    ) -> bool:
        """Apply a terminal output upgrade once, independently of mic workers."""

        with self._cleanup_lock:
            if not job.shutdown_requested:
                return True
            if job.output_stop_attempted:
                return job.output_stopped
            job.output_stop_attempted = True

        speech_drained = attempt(self._wait_for_admitted_speech)
        output_stopped = attempt(self._output.stop)
        with self._cleanup_lock:
            job.output_stopped = output_stopped
            job.speech_epoch = self._speech_epoch
        return speech_drained and output_stopped

    def _retire_cleanup_workers(
        self,
        job: _VoiceCleanupJob,
        workers: dict[str, threading.Thread | None],
        attempt: Callable[[Callable[[], Any]], bool],
    ) -> bool:
        """Retain live workers while polling late shutdown upgrades."""

        pending = [
            (name, worker) for name, worker in workers.items() if worker is not None
        ]
        cleanup_succeeded = True
        current_worker = threading.current_thread()
        while pending:
            if not self._stop_output_if_requested(job, attempt):
                cleanup_succeeded = False
            survivors: list[tuple[str, threading.Thread]] = []
            for name, worker in pending:
                if worker is current_worker:
                    cleanup_succeeded = False
                    continue
                try:
                    worker.join(timeout=_CLEANUP_JOIN_SLICE_SECONDS)
                    alive = worker.is_alive()
                except BaseException:  # noqa: BLE001 - retain failed ownership
                    cleanup_succeeded = False
                    continue
                if alive:
                    survivors.append((name, worker))
                    continue
                with self._lock:
                    if getattr(self, name) is worker:
                        setattr(self, name, None)
            pending = survivors
        if not self._stop_output_if_requested(job, attempt):
            cleanup_succeeded = False
        return cleanup_succeeded

    def _run_cleanup(self, job: _VoiceCleanupJob) -> None:
        """Own every potentially blocking teardown effect for one generation."""

        cleanup_failed = False

        def attempt(callback: Callable[[], Any]) -> bool:
            try:
                return callback() is not False
            except BaseException:  # noqa: BLE001 - finish every cleanup step
                return False

        while True:
            workers: dict[str, threading.Thread | None] = {}
            with self._cleanup_lock:
                observed_request_version = job.request_version
            try:
                with self._lifecycle_lock:
                    with self._cleanup_lock:
                        expected_session = job.expected_session
                        observed_request_version = job.request_version
                    with self._lock:
                        stale_request = (
                            expected_session is not None
                            and self._session_epoch != expected_session
                        )
                        if stale_request:
                            stop_event = None
                            capture_ready_event = None
                            decode_queue = None
                            streaming_queue = None
                            acoustic_wake_queue = None
                        else:
                            workers = {
                                "_capture_worker": self._capture_worker,
                                "_decode_worker": self._decode_worker,
                                "_streaming_worker": self._streaming_worker,
                                "_acoustic_wake_worker": (self._acoustic_wake_worker),
                            }
                            stop_event = self._stop_event
                            capture_ready_event = self._capture_ready_event
                            decode_queue = self._decode_queue
                            streaming_queue = self._streaming_queue
                            acoustic_wake_queue = self._acoustic_wake_queue
                            self._mode = "off"
                            self._lifecycle_state = "stopping"
                            self._armed_until = 0.0
                            self._session_epoch += 1
                            self._wake_epoch += 1
                            job.applied = True

                    if not stale_request:
                        cleanup_failed |= not attempt(capture_ready_event.set)
                        cleanup_failed |= not attempt(stop_event.set)
                        cleanup_failed |= not attempt(
                            lambda: self._signal_cleanup_queue(
                                decode_queue,
                                _DECODE_STOP,
                            )
                        )
                        cleanup_failed |= not attempt(
                            lambda: self._signal_cleanup_queue(
                                streaming_queue,
                                _STREAMING_STOP,
                            )
                        )
                        cleanup_failed |= not attempt(
                            lambda: self._signal_cleanup_queue(
                                acoustic_wake_queue,
                                _ACOUSTIC_WAKE_STOP,
                            )
                        )

                        # These calls can enter COM or native audio code. They
                        # live only here so callers can time out without
                        # abandoning ownership or duplicating an effect.
                        cleanup_failed |= not attempt(self._wait_for_admitted_speech)
                        cleanup_failed |= not attempt(self.cancel_speech)
                        with self._cleanup_lock:
                            job.speech_epoch = self._speech_epoch
                        cleanup_failed |= not attempt(self._ducker.restore)
                        cleanup_failed |= not attempt(self._loopback.stop)
                        cleanup_failed |= not self._retire_cleanup_workers(
                            job,
                            workers,
                            attempt,
                        )
            except BaseException:  # noqa: BLE001 - retain cleanup ownership
                cleanup_failed = True

            try:
                finished, report_incomplete = self._finish_cleanup(
                    job,
                    cleanup_failed,
                    attempt,
                    observed_request_version,
                )
            except BaseException:  # noqa: BLE001 - last-resort ownership seal
                cleanup_failed = True
                with self._cleanup_lock:
                    retry = (
                        not job.applied
                        and job.request_version != observed_request_version
                    )
                if retry:
                    continue
                try:
                    with self._lock:
                        if job.applied:
                            self.last_error = self.last_error or "voice_stop_timeout"
                            self._lifecycle_state = "failed"
                except BaseException:  # noqa: BLE001
                    pass
                with self._cleanup_lock:
                    if (
                        not job.applied
                        and job.request_version != observed_request_version
                    ):
                        continue
                    job.success = False
                    job.done.set()
                    return
            if not finished:
                continue
            if job.applied:
                self._emit(
                    "state",
                    mode="off",
                    listening=False,
                    speaking=self.speaking,
                )
            if report_incomplete:
                self._emit("error", code="voice_stop_timeout")
            return

    def _finish_cleanup(
        self,
        job: _VoiceCleanupJob,
        cleanup_failed: bool,
        attempt: Callable[[Callable[[], Any]], bool],
        observed_request_version: int,
    ) -> tuple[bool, bool]:
        """Seal state before any potentially blocking observer notification."""

        while True:
            with self._cleanup_lock:
                if not job.applied and job.request_version != observed_request_version:
                    return False, False
            cleanup_failed |= not self._stop_output_if_requested(job, attempt)

            success = not cleanup_failed
            if job.applied:
                try:
                    with self._lock:
                        if success:
                            self._failure_stop_requested = False
                            self._lifecycle_state = "off"
                        else:
                            self.last_error = self.last_error or "voice_stop_timeout"
                            self._lifecycle_state = "failed"
                except BaseException:  # noqa: BLE001
                    cleanup_failed = True
                    success = False

            report_incomplete = False
            with self._cleanup_lock:
                if not job.applied and job.request_version != observed_request_version:
                    return False, False
                if job.shutdown_requested and not job.output_stop_attempted:
                    continue
                job.success = success
                if (job.timeout_observed or not success) and not job.timeout_reported:
                    job.timeout_reported = True
                    report_incomplete = True
                job.done.set()
                return True, report_incomplete

    def shutdown(self) -> None:
        self._stop(shutdown=True)

    def _wait_for_admitted_speech(self) -> None:
        """Wait in the cleanup daemon until earlier TTS admission resolves."""

        with self._cleanup_condition:
            while self._speech_inflight:
                self._cleanup_condition.wait()

    def speak(self, text: str) -> bool:
        with self._cleanup_condition:
            cleanup_job = self._cleanup_job
            cleanup_thread = cleanup_job.thread if cleanup_job is not None else None
            cleanup_active = cleanup_job is not None and (
                not cleanup_job.done.is_set()
                or cleanup_thread is None
                or cleanup_thread.is_alive()
                or not cleanup_job.success
            )
            if self._shutdown_requested or cleanup_active:
                rejected = True
            else:
                rejected = False
                self._speech_inflight += 1
        if rejected:
            code = (
                "voice_session_still_stopping"
                if cleanup_active
                else self._output.last_error or "tts_unavailable"
            )
            self._emit("error", code=code)
            return False
        accepted = False
        try:
            accepted = self._output.speak(text)
        finally:
            with self._cleanup_condition:
                if accepted:
                    self._speech_epoch += 1
                self._speech_inflight -= 1
                self._cleanup_condition.notify_all()
        if not accepted:
            self._emit("error", code=self._output.last_error or "tts_unavailable")
        return accepted

    def cancel_speech(self) -> None:
        self._output.cancel()

    def status(self) -> dict[str, Any]:
        health = self.probe()
        with self._lock:
            listening = (
                self._lifecycle_state == "ready"
                and self._mode != "off"
                and self._capture_worker is not None
                and self._capture_worker.is_alive()
            )
        health.update(
            {
                "mode": self.mode,
                "listening": listening,
                "speaking": self.speaking,
                "ttsReady": self._output.available,
                "loopbackActive": self._loopback.active,
                "inputDevice": self._input_device_name,
                "sttModel": _stt_model_name(self._stt_directory)
                or health.get("sttModel"),
                "streamingStt": self._streaming_recognizer is not None,
                "streamingSttModel": _stt_model_name(self._streaming_stt_directory),
                "streamingSttError": self._streaming_error,
                "wakeWord": self._acoustic_wake_detector is not None,
                "wakeBackend": self._wake_backend,
                "wakeWordModel": self._wake_model_name,
                "wakeWordPhrase": self._wake_phrase,
                "wakeWordError": self._wake_error,
                "wakeVerifier": (
                    self._wake_verifier is not None
                    or self._wake_cascade_config is not None
                ),
                "wakeVerifierError": self._wake_verifier_error,
                "wakeEndpoint": self._endpoint_wake_available(),
                "lexicalWakeFallback": _lexical_wake_fallback_enabled(),
                "lastError": self.last_error,
            }
        )
        return health

    def _on_tts_state(self, speaking: bool) -> None:
        with self._lock:
            listening = (
                self._lifecycle_state == "ready"
                and self._mode != "off"
                and self._capture_worker is not None
                and self._capture_worker.is_alive()
            )
        self._emit("state", mode=self.mode, listening=listening, speaking=speaking)

    def _session_is_current(self, session_epoch: int | None) -> bool:
        """Whether a worker still belongs to the active microphone session."""

        if session_epoch is None:
            return True
        with self._lock:
            return self._session_epoch == session_epoch

    def _enqueue_acoustic_wake(
        self,
        frame: np.ndarray,
        *,
        wake_queue: queue.Queue[object] | None = None,
        session_epoch: int | None = None,
        stop_event: threading.Event | None = None,
    ) -> bool:
        """Pass microphone frames to KWS without ever stalling sounddevice."""

        with self._lock:
            if session_epoch is not None and self._session_epoch != session_epoch:
                return False
            worker = self._acoustic_wake_worker
            queue_owner = wake_queue or self._acoustic_wake_queue
            event = stop_event or self._stop_event
            wake_epoch = self._wake_epoch
        if worker is None or event.is_set():
            return False
        frame_copy = np.ascontiguousarray(frame.copy())
        try:
            queue_owner.put_nowait((wake_epoch, frame_copy))
            return True
        except queue.Full:
            # Preserve newest audio over stale audio.  A discontinuity resets
            # the KWS window in its owner thread, avoiding a fabricated mix of
            # samples that never occurred contiguously at the microphone.
            try:
                queue_owner.get_nowait()
                with self._lock:
                    if (
                        session_epoch is not None
                        and self._session_epoch != session_epoch
                    ):
                        return False
                    self._wake_epoch += 1
                    wake_epoch = self._wake_epoch
                queue_owner.put_nowait((wake_epoch, frame_copy))
            except queue.Empty:
                pass
            self._emit("warning", code="wake_word_queue_full")
            return False

    def _reset_acoustic_wake(self, *, session_epoch: int | None = None) -> None:
        """Invalidate queued KWS work and reset its rolling window on next use."""

        with self._lock:
            if session_epoch is not None and self._session_epoch != session_epoch:
                return
            self._wake_epoch += 1
            hit_queue = self._acoustic_wake_hits
        while True:
            try:
                hit_queue.get_nowait()
            except queue.Empty:
                return

    def _take_acoustic_wake_hit(
        self,
        *,
        hit_queue: queue.Queue[tuple[int, WakeWordDetection]] | None = None,
        session_epoch: int | None = None,
    ) -> WakeWordDetection | None:
        """Return the newest KWS hit; older hits cannot open parallel turns."""

        hit: WakeWordDetection | None = None
        queue_owner = hit_queue or self._acoustic_wake_hits
        while True:
            try:
                hit_epoch, candidate = queue_owner.get_nowait()
            except queue.Empty:
                return hit
            with self._lock:
                current = hit_epoch == self._wake_epoch and (
                    session_epoch is None
                    or (
                        self._session_epoch == session_epoch
                        and self._mode == "wake"
                        and self._wake_backend == "acoustic"
                    )
                )
            if current:
                hit = candidate

    def _acoustic_wake_loop(
        self,
        wake_queue: queue.Queue[object] | None = None,
        hit_queue: queue.Queue[tuple[int, WakeWordDetection]] | None = None,
        detector: AcousticWakeDetector | None = None,
        session_epoch: int | None = None,
        stop_event: threading.Event | None = None,
    ) -> None:
        """Own CPU KWS inference away from the real-time microphone thread."""

        queue_owner = wake_queue or self._acoustic_wake_queue
        hit_owner = hit_queue or self._acoustic_wake_hits
        detector = detector or self._acoustic_wake_detector
        event = stop_event or self._stop_event
        if detector is None:
            return
        active_epoch: int | None = None
        while True:
            try:
                item = queue_owner.get(timeout=0.2)
            except queue.Empty:
                if event.is_set() or not self._session_is_current(session_epoch):
                    return
                continue
            if item is _ACOUSTIC_WAKE_STOP:
                return
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], int)
                or not isinstance(item[1], np.ndarray)
            ):
                continue
            item_epoch, audio = item
            with self._lock:
                current = item_epoch == self._wake_epoch and (
                    session_epoch is None
                    or (
                        self._session_epoch == session_epoch
                        and self._mode == "wake"
                        and self._wake_backend == "acoustic"
                    )
                )
            if not current:
                continue
            if active_epoch != item_epoch:
                detector.reset()
                active_epoch = item_epoch
            try:
                hit = detector.accept(audio)
            except WakeWordRuntimeError as error:
                self._disable_acoustic_wake(error, session_epoch)
                return
            if hit is None:
                continue
            with self._lock:
                current = item_epoch == self._wake_epoch and (
                    session_epoch is None
                    or (
                        self._session_epoch == session_epoch
                        and self._mode == "wake"
                        and self._wake_backend == "acoustic"
                    )
                )
            if not current:
                continue
            try:
                hit_owner.put_nowait((item_epoch, hit))
            except queue.Full:
                try:
                    hit_owner.get_nowait()
                    hit_owner.put_nowait((item_epoch, hit))
                except queue.Empty:
                    pass

    def _disable_acoustic_wake(
        self,
        error: WakeWordRuntimeError,
        session_epoch: int | None,
    ) -> None:
        """Fail closed if the dedicated KWS backend fails while listening."""

        with self._lock:
            if (
                session_epoch is not None and self._session_epoch != session_epoch
            ) or self._failure_stop_requested:
                return
            self._acoustic_wake_detector = None
            self._wake_error = str(error)
            self._wake_backend = "unavailable"
            self._wake_epoch += 1
            self._mode = "off"
            self._lifecycle_state = "failed"
            self._armed_until = 0.0
            self.last_error = self._wake_error
            self._failure_stop_requested = True
            failed_session = self._session_epoch
        self._emit("error", code=self._wake_error)
        self._emit("state", mode="off", listening=False, speaking=self.speaking)
        logger.warning("KWS acústico se deshabilitó: %s", error)
        self._request_cleanup(expected_session=failed_session)

    def _fail_capture_session(self, error_code: str, session_epoch: int) -> None:
        """Publish a failed capture atomically and retire only its generation."""

        with self._lock:
            if self._session_epoch != session_epoch or self._failure_stop_requested:
                return
            self.last_error = error_code
            self._mode = "off"
            self._lifecycle_state = "failed"
            self._armed_until = 0.0
            self._failure_stop_requested = True
            self._capture_ready_event.set()
        self._emit("error", code=error_code)
        self._emit("state", mode="off", listening=False, speaking=self.speaking)
        self._request_cleanup(expected_session=session_epoch)

    def _create_streaming_stream(self) -> Any | None:
        """Create an isolated ASR partial stream for an already opened turn.

        It is intentionally skipped while BAXY is speaking. The final
        Parakeet pass can apply full-utterance AEC to barge-in audio; feeding
        that raw overlap to the partial recognizer would create misleading
        text feedback. This method has no activation responsibility.
        """

        recognizer = self._streaming_recognizer
        if recognizer is None or self.speaking:
            return None
        try:
            stream = recognizer.create_stream()
            stream.set_option("language", _streaming_language())
            return stream
        except Exception as error:  # noqa: BLE001 - partials are optional
            self._streaming_error = (
                f"streaming_stt_stream_failed:{type(error).__name__}"
            )
            logger.debug("No se pudo crear stream parcial: %s", type(error).__name__)
            return None

    def _streaming_accept(self, stream: Any, audio: np.ndarray) -> str:
        """Feed one audio block and return the best non-authoritative partial."""

        recognizer = self._streaming_recognizer
        if recognizer is None:
            return ""
        try:
            stream.accept_waveform(SAMPLE_RATE, np.asarray(audio, dtype=np.float32))
            decoded = False
            while recognizer.is_ready(stream):
                recognizer.decode_stream(stream)
                decoded = True
            if not decoded:
                return ""
            try:
                result = recognizer.get_result_all(stream)
                return str(getattr(result, "text", "") or "").strip()
            except Exception:  # noqa: BLE001 - compatibility seam for a mock
                result = getattr(stream, "result", None)
                return str(getattr(result, "text", "") or "").strip()
        except Exception as error:  # noqa: BLE001 - preserve final STT
            self._streaming_error = (
                f"streaming_stt_decode_failed:{type(error).__name__}"
            )
            logger.debug("HipÃ³tesis streaming descartada: %s", type(error).__name__)
            return ""

    def _enqueue_streaming(
        self,
        item: tuple[object, ...],
        *,
        streaming_queue: queue.Queue[object] | None = None,
        session_epoch: int | None = None,
        stop_event: threading.Event | None = None,
    ) -> bool:
        """Keep audio capture real-time if the optional first pass falls behind."""

        with self._lock:
            if session_epoch is not None and self._session_epoch != session_epoch:
                return False
            worker = self._streaming_worker
            queue_owner = streaming_queue or self._streaming_queue
            event = stop_event or self._stop_event
        if worker is None or event.is_set():
            return False
        try:
            queue_owner.put_nowait(item)
            return True
        except queue.Full:
            # Dropping an entire optional session is safer than blocking
            # sounddevice's capture thread and losing final command audio.
            self._emit("warning", code="streaming_queue_full")
            return False

    def _streaming_loop(
        self,
        streaming_queue: queue.Queue[object] | None = None,
        session_epoch: int | None = None,
        stop_event: threading.Event | None = None,
    ) -> None:
        """Own Nemotron's CPU work outside the real-time microphone thread."""

        queue_owner = streaming_queue or self._streaming_queue
        event = stop_event or self._stop_event
        active_id: int | None = None
        active_stream: Any | None = None
        started_at = 0.0
        last_partial = ""
        last_partial_at = 0.0

        def observe_partial(partial: str) -> None:
            nonlocal last_partial, last_partial_at
            if (
                not self._session_is_current(session_epoch)
                or not partial
                or partial == last_partial
            ):
                return
            last_partial = partial
            now = time.monotonic()
            if now - last_partial_at >= STREAMING_PARTIAL_INTERVAL_S:
                self._emit(
                    "partial",
                    hasText=True,
                    model=_stt_model_name(self._streaming_stt_directory),
                    seconds=round(now - started_at, 3),
                )
                last_partial_at = now

        while True:
            try:
                item = queue_owner.get(timeout=0.2)
            except queue.Empty:
                if event.is_set() or not self._session_is_current(session_epoch):
                    return
                continue
            if item is _STREAMING_STOP:
                return
            if event.is_set() or not self._session_is_current(session_epoch):
                return
            if not isinstance(item, tuple) or not item:
                continue
            kind = item[0]
            if kind == "start" and len(item) == 4:
                _, session_id, pre_roll, input_started_at = item
                if (
                    not isinstance(session_id, int)
                    or not isinstance(pre_roll, tuple)
                    or not isinstance(input_started_at, (int, float))
                ):
                    continue
                active_id = session_id
                started_at = float(input_started_at)
                active_stream = self._create_streaming_stream()
                last_partial = ""
                last_partial_at = 0.0
                if active_stream is not None:
                    for audio in pre_roll:
                        if isinstance(audio, np.ndarray):
                            observe_partial(
                                self._streaming_accept(active_stream, audio)
                            )
            elif kind == "audio" and len(item) == 3:
                _, session_id, audio = item
                if (
                    active_stream is not None
                    and session_id == active_id
                    and isinstance(audio, np.ndarray)
                ):
                    observe_partial(self._streaming_accept(active_stream, audio))
            elif kind == "finish" and len(item) == 2 and item[1] == active_id:
                # Avoid a final blocking flush. Parakeet owns final text and
                # applies AEC; this stream is intentionally one-way preview.
                active_id = None
                active_stream = None

    def _capture_loop(
        self,
        session_epoch: int | None = None,
        stop_event: threading.Event | None = None,
        decode_queue: queue.Queue[object] | None = None,
        streaming_queue: queue.Queue[object] | None = None,
        wake_queue: queue.Queue[object] | None = None,
        wake_hits: queue.Queue[tuple[int, WakeWordDetection]] | None = None,
        capture_ready_event: threading.Event | None = None,
    ) -> None:
        event = stop_event or self._stop_event
        decode_owner = decode_queue or self._decode_queue
        streaming_owner = streaming_queue or self._streaming_queue
        wake_owner = wake_queue or self._acoustic_wake_queue
        hit_owner = wake_hits or self._acoustic_wake_hits
        ready_event = capture_ready_event or self._capture_ready_event
        vad = self._vad
        utterance: list[np.ndarray] = []
        references: list[np.ndarray] = []
        vad_pre_roll: deque[tuple[np.ndarray, np.ndarray]] = deque(
            maxlen=_wake_frame_count(PRE_ROLL_S)
        )
        acoustic_pre_roll_seconds = (
            self._wake_verifier.config.stage1_pre_roll_seconds
            if self._wake_verifier is not None
            else _ACOUSTIC_WAKE_PRE_ROLL_S
        )
        acoustic_pre_roll: deque[tuple[np.ndarray, np.ndarray]] = deque(
            maxlen=_wake_frame_count(acoustic_pre_roll_seconds)
        )
        acoustic_activity: deque[float] = deque(maxlen=acoustic_pre_roll.maxlen)
        silence_frames = 0
        speech_started = False
        speech_started_at = 0.0
        barge_frames = 0
        noise_floor = 0.002
        live_stream_id: int | None = None
        active_origin = "direct"
        active_wake_confidence: float | None = None
        active_wake_verification_start_sample = 0
        active_wake_detection: WakeWordDetection | None = None
        endpoint_wake_enabled = self._endpoint_wake_available()
        frames_per_silence = _wake_frame_count(TRAILING_SILENCE_S)
        max_frames = max(1, int(MAX_UTTERANCE_S * SAMPLE_RATE / VAD_WINDOW_SAMPLES))

        def wake_state() -> tuple[str, bool, str]:
            now = time.monotonic()
            with self._lock:
                if self._armed_until and self._armed_until < now:
                    self._armed_until = 0.0
                return self._mode, self._armed_until >= now, self._wake_backend

        def begin_utterance(
            origin: str,
            cached: tuple[tuple[np.ndarray, np.ndarray], ...],
            wake_detection: WakeWordDetection | None = None,
            wake_verification_start_sample: int = 0,
            *,
            authorized: bool = True,
            retain_acoustic_history: bool = False,
        ) -> None:
            nonlocal speech_started, speech_started_at, silence_frames
            nonlocal live_stream_id, active_origin, active_wake_confidence
            nonlocal active_wake_verification_start_sample
            nonlocal active_wake_detection
            if speech_started:
                return
            if authorized:
                self._ducker.duck()
            speech_started = True
            active_origin = origin
            active_wake_confidence = (
                wake_detection.confidence if wake_detection is not None else None
            )
            active_wake_verification_start_sample = wake_verification_start_sample
            silence_frames = 0
            speech_started_at = time.monotonic()
            cached_audio = tuple(item[0] for item in cached)
            active_wake_detection = wake_detection
            if authorized:
                self._streaming_session += 1
                candidate_stream_id = self._streaming_session
                if self._enqueue_streaming(
                    ("start", candidate_stream_id, cached_audio, speech_started_at),
                    streaming_queue=streaming_owner,
                    session_epoch=session_epoch,
                    stop_event=event,
                ):
                    live_stream_id = candidate_stream_id
                else:
                    live_stream_id = None
            else:
                live_stream_id = None
            for cached_audio, cached_reference in cached:
                utterance.append(cached_audio)
                references.append(cached_reference)
            vad_pre_roll.clear()
            if not retain_acoustic_history:
                acoustic_pre_roll.clear()
                acoustic_activity.clear()

        def authorize_provisional_wake(
            wake_detection: WakeWordDetection,
            wake_verification_start_sample: int,
        ) -> bool:
            nonlocal live_stream_id, active_origin, active_wake_confidence
            nonlocal active_wake_verification_start_sample
            nonlocal active_wake_detection
            if not speech_started or active_origin != "endpoint_wake_candidate":
                return False
            self._ducker.duck()
            active_origin = "acoustic_wake"
            active_wake_confidence = wake_detection.confidence
            active_wake_verification_start_sample = wake_verification_start_sample
            active_wake_detection = wake_detection
            self._streaming_session += 1
            candidate_stream_id = self._streaming_session
            if self._enqueue_streaming(
                (
                    "start",
                    candidate_stream_id,
                    tuple(utterance),
                    speech_started_at,
                ),
                streaming_queue=streaming_owner,
                session_epoch=session_epoch,
                stop_event=event,
            ):
                live_stream_id = candidate_stream_id
            else:
                live_stream_id = None
            acoustic_pre_roll.clear()
            acoustic_activity.clear()
            return True

        def finish_utterance() -> None:
            nonlocal utterance, references, silence_frames, speech_started
            nonlocal speech_started_at, barge_frames, live_stream_id, active_origin
            nonlocal active_wake_confidence
            nonlocal active_wake_verification_start_sample
            nonlocal active_wake_detection
            audio = np.concatenate(utterance) if utterance else np.empty(0, np.float32)
            reference = (
                np.concatenate(references) if references else np.empty(0, np.int16)
            )
            origin = active_origin
            wake_confidence = active_wake_confidence
            wake_verification_start_sample = active_wake_verification_start_sample
            wake_detection = active_wake_detection
            utterance, references = [], []
            vad_pre_roll.clear()
            acoustic_pre_roll.clear()
            silence_frames = 0
            speech_started = False
            speech_started_at = 0.0
            barge_frames = 0
            active_origin = "direct"
            active_wake_confidence = None
            active_wake_verification_start_sample = 0
            active_wake_detection = None
            if live_stream_id is not None:
                self._enqueue_streaming(
                    ("finish", live_stream_id),
                    streaming_queue=streaming_owner,
                    session_epoch=session_epoch,
                    stop_event=event,
                )
            live_stream_id = None
            vad.reset()
            if origin in {"acoustic_wake", "endpoint_wake_candidate"}:
                self._reset_acoustic_wake(session_epoch=session_epoch)
            if audio.size < MIN_UTTERANCE_S * SAMPLE_RATE:
                self._ducker.restore()
                return
            try:
                if event.is_set() or not self._session_is_current(session_epoch):
                    self._ducker.restore()
                    return
                decode_owner.put_nowait(
                    _DecodeRequest(
                        audio,
                        reference,
                        origin,
                        session_epoch,
                        wake_confidence,
                        wake_verification_start_sample,
                        wake_detection.method if wake_detection is not None else None,
                        (
                            wake_detection.verifier_score
                            if wake_detection is not None
                            else None
                        ),
                        bool(
                            wake_detection is not None
                            and wake_detection.lexical_rescue_required
                        ),
                    )
                )
            except queue.Full:
                self.last_error = "decode_queue_full"
                self._emit("error", code=self.last_error)
                self._ducker.restore()

        try:
            import sounddevice as sd

            if vad is None:
                raise RuntimeError("voice_vad_unavailable")
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=VAD_WINDOW_SAMPLES,
            ) as stream:
                try:
                    device = sd.query_devices(stream.device, kind="input")
                    self._input_device_name = str(device["name"])[:120]
                except Exception:  # noqa: BLE001
                    self._input_device_name = "predeterminado"
                if event.is_set() or not self._session_is_current(session_epoch):
                    return
                with self._lock:
                    if (
                        session_epoch is not None
                        and self._session_epoch == session_epoch
                        and not event.is_set()
                    ):
                        self._lifecycle_state = "ready"
                self._emit("ready", **self.status())
                self._emit(
                    "state",
                    mode=self.mode,
                    listening=True,
                    speaking=self.speaking,
                )
                ready_event.set()
                while not event.is_set() and self._session_is_current(session_epoch):
                    frame, overflowed = stream.read(VAD_WINDOW_SAMPLES)
                    if overflowed:
                        self._emit("warning", code="input_overflow")
                    mono = frame.reshape(-1).astype(np.float32)
                    reference = self._loopback.latest(VAD_WINDOW_SAMPLES)
                    probability = vad.process(mono)
                    energy = _rms(mono)
                    if probability < SPEECH_THRESHOLD:
                        noise_floor = 0.98 * noise_floor + 0.02 * energy

                    speech = probability >= SPEECH_THRESHOLD
                    if speech and self.speaking:
                        history = self._loopback.latest(
                            VAD_WINDOW_SAMPLES + int(0.25 * SAMPLE_RATE)
                        )
                        echo = _looks_like_echo(mono * 32768.0, history)
                        if echo:
                            speech = False
                            barge_frames = 0
                        elif energy >= max(0.004, noise_floor * 1.8):
                            barge_frames += 1
                            if barge_frames >= 3:
                                self.cancel_speech()
                                self._emit("barge_in")
                        else:
                            barge_frames = 0

                    mode, armed, backend = wake_state()
                    acoustic_monitoring = (
                        mode == "wake"
                        and backend == "acoustic"
                        and not armed
                        and (
                            not speech_started
                            or active_origin == "endpoint_wake_candidate"
                        )
                    )
                    frame_already_captured = False
                    if acoustic_monitoring:
                        # Never let BAXY's own speaker output become a wake
                        # sample. Barge-in is handled by VAD above; KWS resumes
                        # after output actually stops.
                        if self.speaking:
                            acoustic_pre_roll.clear()
                            acoustic_activity.clear()
                            self._reset_acoustic_wake(session_epoch=session_epoch)
                        else:
                            acoustic_pre_roll.append((mono, reference))
                            acoustic_activity.append(probability)
                            self._enqueue_acoustic_wake(
                                mono,
                                wake_queue=wake_owner,
                                session_epoch=session_epoch,
                                stop_event=event,
                            )
                            hit = self._take_acoustic_wake_hit(
                                hit_queue=hit_owner,
                                session_epoch=session_epoch,
                            )
                            if hit is not None:
                                verifier_config = (
                                    self._wake_verifier.config
                                    if self._wake_verifier is not None
                                    else None
                                )
                                verification_start = (
                                    _wake_activity_onset_sample(
                                        acoustic_activity,
                                        threshold=(
                                            verifier_config.activity_vad_threshold
                                        ),
                                        alignment_samples=(
                                            verifier_config.activity_alignment_samples
                                        ),
                                        default_start_sample=(
                                            verifier_config.primary_view_start_samples
                                        ),
                                    )
                                    if verifier_config is not None
                                    else 0
                                )
                                upgraded = authorize_provisional_wake(
                                    hit,
                                    verification_start,
                                )
                                if not upgraded:
                                    begin_utterance(
                                        "acoustic_wake",
                                        tuple(acoustic_pre_roll),
                                        hit,
                                        verification_start,
                                    )
                                    frame_already_captured = True
                                self._reset_acoustic_wake(session_epoch=session_epoch)
                                self._emit(
                                    "wake_proposed"
                                    if (
                                        self._wake_verifier is not None
                                        or hit.lexical_rescue_required
                                    )
                                    else "wake_detected",
                                    backend="acoustic",
                                    model=hit.model_name,
                                    confidence=round(hit.confidence, 3),
                                )
                    elif not speech_started and not speech:
                        vad_pre_roll.append((mono, reference))

                    can_segment = (
                        mode == "direct"
                        or mode == "wake"
                        and (armed or backend == "lexical_fallback")
                        or mode == "wake"
                        and backend == "acoustic"
                        and not armed
                        and endpoint_wake_enabled
                        or speech_started
                    )
                    if speech and can_segment:
                        if not speech_started:
                            origin = (
                                "direct"
                                if mode == "direct"
                                else "acoustic_wake"
                                if armed
                                else "lexical_fallback"
                                if backend == "lexical_fallback"
                                else "endpoint_wake_candidate"
                            )
                            if origin == "endpoint_wake_candidate":
                                cached = tuple(acoustic_pre_roll)[
                                    -vad_pre_roll.maxlen :
                                ]
                                begin_utterance(
                                    origin,
                                    cached,
                                    authorized=False,
                                    retain_acoustic_history=True,
                                )
                                frame_already_captured = bool(cached)
                            else:
                                begin_utterance(origin, tuple(vad_pre_roll))
                        silence_frames = 0
                        if not frame_already_captured:
                            utterance.append(mono)
                            references.append(reference)
                            if (
                                live_stream_id is not None
                                and not self._enqueue_streaming(
                                    ("audio", live_stream_id, mono),
                                    streaming_queue=streaming_owner,
                                    session_epoch=session_epoch,
                                    stop_event=event,
                                )
                            ):
                                live_stream_id = None
                    elif speech_started:
                        if not frame_already_captured:
                            utterance.append(mono)
                            references.append(reference)
                            if (
                                live_stream_id is not None
                                and not self._enqueue_streaming(
                                    ("audio", live_stream_id, mono),
                                    streaming_queue=streaming_owner,
                                    session_epoch=session_epoch,
                                    stop_event=event,
                                )
                            ):
                                live_stream_id = None
                        silence_frames += 1
                        if silence_frames >= frames_per_silence:
                            finish_utterance()
                    if len(utterance) >= max_frames:
                        finish_utterance()
        except Exception as error:  # noqa: BLE001 - voz nunca tumba la mente
            if self._session_is_current(session_epoch):
                error_code = f"capture_failed:{type(error).__name__}"
                self._fail_capture_session(
                    error_code,
                    self._session_epoch if session_epoch is None else session_epoch,
                )
                logger.error("captura de voz interrumpida: %s", type(error).__name__)
        finally:
            if speech_started:
                finish_utterance()
            if self._session_is_current(session_epoch):
                self._ducker.restore()
            ready_event.set()

    def _decode_loop(
        self,
        decode_queue: queue.Queue[object] | None = None,
        session_epoch: int | None = None,
        stop_event: threading.Event | None = None,
    ) -> None:
        queue_owner = decode_queue or self._decode_queue
        event = stop_event or self._stop_event
        while True:
            try:
                item = queue_owner.get(timeout=0.2)
            except queue.Empty:
                if event.is_set() or not self._session_is_current(session_epoch):
                    return
                continue
            if item is _DECODE_STOP:
                return
            if event.is_set() or not self._session_is_current(session_epoch):
                return
            if isinstance(item, _DecodeRequest):
                request = item
            elif isinstance(item, tuple) and len(item) == 2:
                # Compatibility seam for old diagnostic callers. Runtime
                # capture always carries an explicit origin now.
                request = _DecodeRequest(item[0], item[1], "direct")
            else:
                continue
            try:
                self._decode_utterance(
                    request.audio,
                    request.reference,
                    request.origin,
                    request.session_epoch
                    if request.session_epoch is not None
                    else session_epoch,
                    request.wake_confidence,
                    request.wake_verification_start_sample,
                    request.wake_method,
                    request.wake_verifier_score,
                    request.wake_lexical_rescue_required,
                )
            except Exception as error:  # noqa: BLE001
                if self._session_is_current(session_epoch):
                    self.last_error = f"decode_failed:{type(error).__name__}"
                    self._emit("error", code=self.last_error)
            finally:
                self._ducker.restore()

    def _decode_utterance(
        self,
        audio: np.ndarray,
        reference: np.ndarray,
        origin: str = "direct",
        session_epoch: int | None = None,
        wake_confidence: float | None = None,
        wake_verification_start_sample: int = 0,
        wake_method: str | None = None,
        wake_verifier_score: float | None = None,
        wake_lexical_rescue_required: bool = False,
    ) -> None:
        if not self._session_is_current(session_epoch):
            return
        recognizer = self._recognizer
        if recognizer is None:
            return
        clean = np.asarray(audio, dtype=np.float32)
        aec_applied = False
        if reference.size >= clean.size and _rms(reference) >= 80.0:
            clean = EchoCanceller().process(clean * 32768.0, reference[-clean.size :])
            aec_applied = True
        started = time.perf_counter()
        endpoint_candidate = origin == "endpoint_wake_candidate"
        raw = "" if endpoint_candidate else _decode_offline_text(recognizer, clean)
        latency = round(time.perf_counter() - started, 3)
        if not self._session_is_current(session_epoch):
            return
        lexical_command: str | None = None
        if endpoint_candidate:
            config = self._wake_cascade_config
            detector = self._acoustic_wake_detector
            if (
                not self._endpoint_wake_available()
                or config is None
                or not isinstance(detector, HyperspotterCascadeDetector)
                or config.endpoint_lexical_score_threshold is None
            ):
                self._emit(
                    "ignored",
                    reason="wake_endpoint_not_configured",
                    backend="acoustic_endpoint",
                )
                return
            try:
                endpoint_score = detector.score_endpoint_lexical(clean)
            except WakeWordRuntimeError as error:
                self.last_error = str(error)
                self._emit("error", code=self.last_error)
                self._emit(
                    "ignored",
                    reason="wake_endpoint_score_failed",
                    backend="acoustic_endpoint",
                )
                return
            if endpoint_score < config.endpoint_lexical_score_threshold:
                self._emit(
                    "ignored",
                    reason="wake_endpoint_acoustic_rejected",
                    backend="acoustic_endpoint",
                )
                return
            endpoint_match = None
            try:
                for factor in (
                    1.0,
                    *config.endpoint_lexical_retry_speed_factors,
                ):
                    view = (
                        clean
                        if factor == 1.0
                        else time_scaled_recognition_audio(clean, factor)
                    )
                    transcript = _decode_offline_text(
                        recognizer,
                        view,
                        hotwords=self._wake_hotwords,
                    )
                    endpoint_match = match_suffix_independent_endpoint_wake(
                        (transcript,), config.endpoint_lexical_aliases
                    )
                    if endpoint_match is not None:
                        break
            except Exception as error:  # noqa: BLE001 - endpoint fails closed
                logger.debug(
                    "Endpoint lexical wake unavailable: %s",
                    type(error).__name__,
                )
                endpoint_match = None
            if endpoint_match is None:
                self._emit(
                    "ignored",
                    reason="wake_endpoint_lexical_rejected",
                    backend="acoustic_endpoint",
                )
                return
            raw = endpoint_match.transcript
            lexical_command = endpoint_match.command
            wake_verifier_score = endpoint_score
            wake_method = f"score_gated_{endpoint_match.method}"
            latency = round(time.perf_counter() - started, 3)
            self._emit(
                "wake_detected",
                backend="acoustic_endpoint",
                model=self._wake_model_name,
                method=wake_method,
                verifierScore=round(endpoint_score, 3),
            )
        cascade_method = wake_method in {
            "logmel_verifier",
            "strict_lexical_rescue",
            "direct_lexical_proposal",
        }
        if origin == "acoustic_wake" and cascade_method:
            method = str(wake_method)
            if wake_lexical_rescue_required:
                if self._wake_cascade_config is None:
                    self._emit(
                        "ignored",
                        reason="wake_cascade_config_missing",
                        backend="acoustic_cascade",
                    )
                    return
                if wake_method == "direct_lexical_proposal":
                    lexical_transcripts: list[str] = []
                    try:
                        lexical_transcripts.append(
                            _decode_offline_text(
                                recognizer,
                                clean,
                                hotwords=self._wake_hotwords,
                            )
                            if self._wake_hotwords
                            else raw
                        )
                        lexical_match = match_bounded_lexical_wake(
                            lexical_transcripts,
                            self._wake_cascade_config.lexical_aliases,
                            verifier_score=wake_verifier_score,
                            phonetic_confusion_score_gte=(
                                getattr(
                                    self._wake_cascade_config,
                                    "direct_lexical_phonetic_confusion_score_gte",
                                    None,
                                )
                            ),
                        )
                        for factor in (
                            self._wake_cascade_config.direct_lexical_retry_speed_factors
                        ):
                            if lexical_match is not None:
                                break
                            lexical_transcripts.append(
                                _decode_offline_text(
                                    recognizer,
                                    time_scaled_recognition_audio(clean, factor),
                                    hotwords=self._wake_hotwords,
                                )
                            )
                            lexical_match = match_bounded_lexical_wake(
                                lexical_transcripts[-1:],
                                self._wake_cascade_config.lexical_aliases,
                                verifier_score=wake_verifier_score,
                                phonetic_confusion_score_gte=(
                                    getattr(
                                        self._wake_cascade_config,
                                        "direct_lexical_phonetic_confusion_score_gte",
                                        None,
                                    )
                                ),
                            )
                    except Exception as error:  # noqa: BLE001 - fail closed
                        logger.debug(
                            "Direct lexical wake confirmation unavailable: %s",
                            type(error).__name__,
                        )
                        lexical_match = None
                    if lexical_match is not None:
                        raw = lexical_match.transcript
                        lexical_command = lexical_match.command
                        method = lexical_match.method
                else:
                    lexical_match = (
                        raw
                        if has_strict_leading_alias(
                            raw,
                            self._wake_cascade_config.lexical_aliases,
                        )
                        else None
                    )
                if lexical_match is None:
                    self._emit(
                        "ignored",
                        reason="wake_cascade_lexical_rejected",
                        backend="acoustic_cascade",
                    )
                    return
                if wake_method != "direct_lexical_proposal":
                    method = "strict_lexical_rescue"
                latency = round(time.perf_counter() - started, 3)
            self._emit(
                "wake_detected",
                backend="acoustic_cascade",
                model=self._wake_model_name,
                confidence=(
                    round(wake_confidence, 3) if wake_confidence is not None else None
                ),
                method=method,
                verifierScore=(
                    round(wake_verifier_score, 3)
                    if wake_verifier_score is not None
                    else None
                ),
            )
        elif (
            origin == "acoustic_wake"
            and wake_confidence is not None
            and self._wake_verifier is not None
        ):
            verifier_started = time.perf_counter()
            try:
                decision = self._wake_verifier.verify(
                    clean,
                    raw,
                    wake_confidence,
                    verification_start_sample=(wake_verification_start_sample),
                )
            except WakeVerifierRuntimeError as error:
                self.last_error = str(error)
                self._emit("error", code=self.last_error)
                self._emit(
                    "ignored",
                    reason="wake_verifier_failed",
                    backend="acoustic_verified",
                )
                return
            if not decision.accepted:
                self._emit(
                    "ignored",
                    reason="wake_verifier_rejected",
                    backend="acoustic_verified",
                )
                return
            self._emit(
                "wake_detected",
                backend="acoustic_verified",
                model=self._wake_model_name,
                confidence=round(wake_confidence, 3),
                method=decision.method,
                verifierSeconds=round(time.perf_counter() - verifier_started, 3),
            )
        self._emit(
            "recognized",
            hasText=bool(raw),
            seconds=latency,
            aec=aec_applied,
            model=_stt_model_name(self._stt_directory) or "parakeet-tdt-0.6b-v3-int8",
            origin=origin,
        )
        with self._lock:
            if session_epoch is not None and self._session_epoch != session_epoch:
                return
            mode = self._mode
            armed = self._armed_until >= time.monotonic()
        if mode == "off":
            return
        wake_matched, command = self._wake.strip(raw)
        if lexical_command is not None:
            wake_matched, command = True, lexical_command
        text = raw
        if mode == "wake" and origin == "lexical_fallback":
            if not wake_matched and not armed:
                self._emit(
                    "ignored", reason="wake_not_present", backend="lexical_fallback"
                )
                return
            text = command if wake_matched else raw
            bare_wake = wake_matched and not text
        elif mode == "wake" and origin not in {
            "acoustic_wake",
            "endpoint_wake_candidate",
        }:
            # A queued direct request must not become a command merely because
            # the UI switched modes while Parakeet was decoding it.
            self._emit(
                "ignored", reason="turn_not_authorized", backend=self._wake_backend
            )
            return
        elif mode == "wake":
            # An acoustic hit, not text, opened this turn. Parakeet may retain
            # the phrase from pre-roll or may start directly at the command.
            # The fuzzy cleaner is safe here because it is post-KWS only.
            text = command if wake_matched else raw
            if not wake_matched and self._corrector is not None:
                text = self._corrector.strip_wake_phrase(raw)
            bare_wake = not text.strip()
        else:
            bare_wake = False

        if mode == "wake" and bare_wake:
            with self._lock:
                if session_epoch is not None and self._session_epoch != session_epoch:
                    return
                self._armed_until = time.monotonic() + WAKE_COMMAND_WINDOW_S
            self._emit(
                "wake",
                backend=(
                    "acoustic"
                    if origin == "acoustic_wake"
                    else "acoustic_endpoint"
                    if origin == "endpoint_wake_candidate"
                    else "lexical_fallback"
                ),
                armedSeconds=WAKE_COMMAND_WINDOW_S,
            )
            self.speak("Sí.")
            return

        if self._corrector is not None:
            alternatives: tuple[str, ...] = ()
            if self._contextual_hotwords and self._corrector.needs_contextual_support(
                text
            ):
                try:
                    contextual_stream = recognizer.create_stream(
                        hotwords=self._contextual_hotwords
                    )
                    contextual_stream.accept_waveform(SAMPLE_RATE, clean)
                    recognizer.decode_stream(contextual_stream)
                    contextual = (contextual_stream.result.text or "").strip()
                    if contextual and contextual != text:
                        alternatives = (contextual,)
                except Exception as error:  # noqa: BLE001 - primary decode remains authoritative
                    logger.debug(
                        "Contextual ASR pass unavailable: %s",
                        type(error).__name__,
                    )
            text = self._corrector.correct(text, alternatives=alternatives)
        text = text.strip()
        if not text:
            return
        with self._lock:
            if session_epoch is not None and self._session_epoch != session_epoch:
                return
            self._armed_until = 0.0
        if not self._session_is_current(session_epoch):
            return
        self._on_transcript(text)


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:  # noqa: BLE001
        return False


__all__ = [
    "DEFAULT_STT_DIR",
    "MIN_UTTERANCE_S",
    "PRE_ROLL_S",
    "SAMPLE_RATE",
    "SPEECH_THRESHOLD",
    "STREAMING_STT_BUNDLE",
    "TRAILING_SILENCE_S",
    "SileroVad",
    "VoiceEngine",
    "WakePhraseMatcher",
    "resolve_stt_directory",
    "resolve_streaming_stt_directory",
]
