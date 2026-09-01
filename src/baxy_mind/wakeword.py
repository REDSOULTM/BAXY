"""Wake-word acústico local y verificable para BAXY.

El detector no transcribe ni posee el micrófono: recibe frames PCM 16 kHz del
motor de voz, mantiene una ventana rodante y devuelve un hit acústico.  El
modelo ONNX y su manifiesto viven fuera del repositorio para que un release no
pueda afirmar que reconoce «Baxy» sin conocer exactamente qué peso y qué
calibración lo habilitaron.

El backend actual es ``livekit-wakeword``.  Su API de inferencia es local y
stateless; este adaptador aporta el estado de ventana, umbral y antirrebote que
necesita BAXY.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any

import numpy as np

from .assets import AssetDescriptorError, resolve_asset
from .onnx_runtime import create_with_power_efficient_onnx

SAMPLE_RATE = 16_000
WINDOW_SAMPLES = SAMPLE_RATE * 2
# The reference listener scores every 80 ms. On BAXY's measured CPU that can
# exceed the predictor's p95 and backlog; 250 ms leaves useful headroom while
# retaining a responsive activation path. Calibration records the exact hop.
DEFAULT_HOP_SAMPLES = 4_000
DEFAULT_DEBOUNCE_S = 2.0
MANIFEST_SCHEMA = "baxy-wakeword-v1"
CALIBRATION_SCHEMA = "baxy-wake-calibration-v1"
CALIBRATION_REPORT_SCHEMA = "baxy-wake-corpus-gate-v3"
CALIBRATION_REPORT_FILENAME = "baxy-wake-corpus-gate-v3.json"
_MAX_MANIFEST_BYTES = 16 * 1024
_MAX_MODEL_BYTES = 64 * 1024 * 1024
_MAX_CALIBRATION_REPORT_BYTES = 128 * 1024
_MODEL_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_MIN_CALIBRATION_CONFIDENCE = 0.95
_MAX_PRODUCT_FALSE_REJECT_RATE = 0.05
_MAX_PRODUCT_FALSE_ACTIVATIONS_PER_HOUR = 0.1


class WakeWordConfigurationError(ValueError):
    """El activo KWS no es apto para habilitar la escucha continua."""


class WakeWordRuntimeError(RuntimeError):
    """El backend KWS no se pudo cargar o evaluar de forma segura."""


@dataclass(frozen=True)
class WakeWordModelConfig:
    """Contrato inmutable de un modelo KWS habilitado para runtime."""

    manifest_path: Path
    model_path: Path
    model_name: str
    phrase: str
    threshold: float
    hop_samples: int
    debounce_seconds: float
    model_sha256: str
    calibration: dict[str, Any]

    @property
    def window_samples(self) -> int:
        return WINDOW_SAMPLES


@dataclass(frozen=True)
class WakeWordDetection:
    """Hit acústico, sin texto ni audio para preservar privacidad."""

    model_name: str
    phrase: str
    confidence: float
    timestamp: float
    method: str = "stage1"
    verifier_score: float | None = None
    lexical_rescue_required: bool = False


def _truthy_environment(name: str) -> bool:
    return (os.environ.get(name) or "").strip().casefold() in {
        "1",
        "true",
        "on",
        "yes",
        "enabled",
    }


def resolve_wakeword_manifest() -> Path:
    """Resolve an explicit manifest first, then BAXY's external asset store."""

    configured = (os.environ.get("BAXY_VOICE_WAKE_MANIFEST") or "").strip()
    if configured:
        return Path(configured).expanduser()
    try:
        resolution = resolve_asset("wake_manifest")
    except AssetDescriptorError as error:
        raise WakeWordConfigurationError("asset_descriptor_invalid") from error
    if resolution.path is not None:
        return resolution.path
    return resolution.candidates[0] if resolution.candidates else Path()


DEFAULT_WAKE_MANIFEST = Path()


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file() or path.stat().st_size > _MAX_MANIFEST_BYTES:
            raise WakeWordConfigurationError("wake_word_manifest_missing")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except WakeWordConfigurationError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise WakeWordConfigurationError("wake_word_manifest_invalid") from error
    if not isinstance(payload, dict) or payload.get("schema") != MANIFEST_SCHEMA:
        raise WakeWordConfigurationError("wake_word_manifest_invalid")
    return payload


def _required_string(payload: dict[str, Any], name: str, maximum: int) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise WakeWordConfigurationError("wake_word_manifest_invalid")
    return value.strip()


def _required_number(
    payload: dict[str, Any],
    name: str,
    minimum: float,
    maximum: float,
) -> float:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WakeWordConfigurationError("wake_word_manifest_invalid")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise WakeWordConfigurationError("wake_word_manifest_invalid")
    return number


def _required_integer(
    payload: dict[str, Any],
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    number = _required_number(payload, name, minimum, maximum)
    if not number.is_integer():
        raise WakeWordConfigurationError("wake_word_manifest_invalid")
    return int(number)


def _resolve_model_path(manifest_path: Path, relative_model: str) -> Path:
    candidate = Path(relative_model)
    if candidate.is_absolute() or candidate.name != relative_model:
        raise WakeWordConfigurationError("wake_word_model_path_invalid")
    try:
        manifest_root = manifest_path.parent.resolve(strict=True)
        model_path = (manifest_root / candidate).resolve(strict=True)
        model_path.relative_to(manifest_root)
    except (OSError, RuntimeError, ValueError) as error:
        raise WakeWordConfigurationError("wake_word_model_path_invalid") from error
    if model_path.suffix.casefold() != ".onnx" or not model_path.is_file():
        raise WakeWordConfigurationError("wake_word_model_missing")
    try:
        size = model_path.stat().st_size
    except OSError as error:
        raise WakeWordConfigurationError("wake_word_model_missing") from error
    if size <= 0 or size > _MAX_MODEL_BYTES:
        raise WakeWordConfigurationError("wake_word_model_invalid")
    return model_path


def _resolve_calibration_report_path(manifest_path: Path, relative_report: str) -> Path:
    """Resolve only BAXY's adjacent, immutable calibration evidence."""

    if relative_report != CALIBRATION_REPORT_FILENAME:
        raise WakeWordConfigurationError("wake_word_calibration_invalid")
    candidate = Path(relative_report)
    if candidate.is_absolute() or candidate.name != relative_report:
        raise WakeWordConfigurationError("wake_word_calibration_invalid")
    try:
        manifest_root = manifest_path.parent.resolve(strict=True)
        report_path = (manifest_root / candidate).resolve(strict=True)
        report_path.relative_to(manifest_root)
    except (OSError, RuntimeError, ValueError) as error:
        raise WakeWordConfigurationError("wake_word_calibration_report_missing") from error
    if report_path.suffix.casefold() != ".json" or not report_path.is_file():
        raise WakeWordConfigurationError("wake_word_calibration_report_missing")
    try:
        size = report_path.stat().st_size
    except OSError as error:
        raise WakeWordConfigurationError("wake_word_calibration_report_missing") from error
    if size <= 0 or size > _MAX_CALIBRATION_REPORT_BYTES:
        raise WakeWordConfigurationError("wake_word_calibration_report_invalid")
    return report_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _calibration_string(payload: dict[str, Any], name: str, maximum: int) -> str:
    try:
        return _required_string(payload, name, maximum)
    except WakeWordConfigurationError as error:
        raise WakeWordConfigurationError("wake_word_calibration_invalid") from error


def _calibration_number(
    payload: dict[str, Any],
    name: str,
    minimum: float,
    maximum: float,
) -> float:
    try:
        return _required_number(payload, name, minimum, maximum)
    except WakeWordConfigurationError as error:
        raise WakeWordConfigurationError("wake_word_calibration_invalid") from error


def _calibration_integer(
    payload: dict[str, Any],
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    try:
        return _required_integer(payload, name, minimum, maximum)
    except WakeWordConfigurationError as error:
        raise WakeWordConfigurationError("wake_word_calibration_invalid") from error


def _calibration_timestamp(payload: dict[str, Any], name: str) -> str:
    value = _calibration_string(payload, name, 64)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise WakeWordConfigurationError("wake_word_calibration_invalid") from error
    if parsed.tzinfo is None:
        raise WakeWordConfigurationError("wake_word_calibration_invalid")
    return value


def _same_number(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1e-12)


def _read_calibration_report(path: Path, expected_hash: str) -> dict[str, Any]:
    try:
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise WakeWordConfigurationError("wake_word_calibration_report_hash_mismatch")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except WakeWordConfigurationError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise WakeWordConfigurationError("wake_word_calibration_report_invalid") from error
    if not isinstance(payload, dict):
        raise WakeWordConfigurationError("wake_word_calibration_report_invalid")
    return payload


def _validate_calibration(
    manifest_path: Path,
    calibration: dict[str, Any],
    *,
    model_name: str,
    phrase: str,
    model_sha256: str,
    threshold: float,
    hop_samples: int,
    debounce_seconds: float,
) -> dict[str, Any]:
    """Require a signed-by-hash held-out evaluation for product activation.

    A SHA alone proves byte identity, not suitability.  Therefore the adjacent
    report must also bind that exact ONNX and every decision parameter to an
    acoustic, held-out, one-sided-FAR approval.  The report stays in the
    runtime asset directory so the provenance remains auditable after install.
    """

    if calibration.get("approved") is not True:
        raise WakeWordConfigurationError("wake_word_calibration_required")
    if calibration.get("schema") != CALIBRATION_SCHEMA:
        raise WakeWordConfigurationError("wake_word_calibration_invalid")
    if calibration.get("gate_schema") != CALIBRATION_REPORT_SCHEMA:
        raise WakeWordConfigurationError("wake_word_calibration_invalid")
    if calibration.get("corpus_sufficient") is not True:
        raise WakeWordConfigurationError("wake_word_calibration_invalid")
    report_name = _calibration_string(calibration, "report", 128)
    report_sha256 = _calibration_string(calibration, "report_sha256", 64).casefold()
    report_model_sha256 = _calibration_string(
        calibration,
        "report_model_sha256",
        64,
    ).casefold()
    if not _SHA256_RE.fullmatch(report_sha256) or not _SHA256_RE.fullmatch(report_model_sha256):
        raise WakeWordConfigurationError("wake_word_calibration_invalid")
    if report_model_sha256 != model_sha256:
        raise WakeWordConfigurationError("wake_word_calibration_mismatch")
    measured_at = _calibration_timestamp(calibration, "measured_at")
    calibration_frr = _calibration_number(calibration, "false_reject_rate", 0.0, 1.0)
    calibration_confidence = _calibration_number(
        calibration,
        "far_confidence",
        _MIN_CALIBRATION_CONFIDENCE,
        0.999999,
    )
    calibration_far_upper = _calibration_number(
        calibration,
        "far_upper_confidence_per_hour",
        0.0,
        1_000_000.0,
    )
    report_path = _resolve_calibration_report_path(manifest_path, report_name)
    report = _read_calibration_report(report_path, report_sha256)
    if (
        report.get("schema") != CALIBRATION_REPORT_SCHEMA
        or report.get("mode") != "acoustic"
        or report.get("promotable") is not True
        or report.get("corpus_sufficient") is not True
    ):
        raise WakeWordConfigurationError("wake_word_calibration_report_invalid")
    try:
        report_measured_at = _calibration_timestamp(report, "measured_at")
        report_model = report["model"]
        report_far = report["far"]
        criteria = report["promotion_criteria"]
        if (
            not isinstance(report_model, dict)
            or not isinstance(report_far, dict)
            or not isinstance(criteria, dict)
        ):
            raise WakeWordConfigurationError("wake_word_calibration_report_invalid")
        if (
            report_model.get("backend") != "livekit-wakeword"
            or _calibration_string(report_model, "model", 64) != model_name
            or _calibration_string(report_model, "phrase", 80) != phrase
            or _calibration_string(report_model, "model_sha256", 64).casefold() != model_sha256
            or _calibration_integer(report_model, "sample_rate", SAMPLE_RATE, SAMPLE_RATE)
            != SAMPLE_RATE
            or _calibration_integer(report_model, "window_samples", WINDOW_SAMPLES, WINDOW_SAMPLES)
            != WINDOW_SAMPLES
            or _calibration_integer(report_model, "hop_samples", 256, WINDOW_SAMPLES)
            != hop_samples
            or not _same_number(
                _calibration_number(report_model, "threshold", 0.001, 0.999),
                threshold,
            )
            or not _same_number(
                _calibration_number(report_model, "debounce_seconds", 0.5, 10.0),
                debounce_seconds,
            )
        ):
            raise WakeWordConfigurationError("wake_word_calibration_mismatch")
        report_frr = _calibration_number(report, "false_reject_rate", 0.0, 1.0)
        report_confidence = _calibration_number(
            report_far,
            "confidence",
            _MIN_CALIBRATION_CONFIDENCE,
            0.999999,
        )
        report_far_upper = _calibration_number(
            report_far,
            "upper_confidence_per_hour",
            0.0,
            1_000_000.0,
        )
        if report_far.get("method") != "poisson_one_sided_upper_exact":
            raise WakeWordConfigurationError("wake_word_calibration_report_invalid")
        maximum_frr = _calibration_number(
            criteria,
            "false_reject_rate_lte",
            0.0,
            _MAX_PRODUCT_FALSE_REJECT_RATE,
        )
        maximum_far = _calibration_number(
            criteria,
            "false_activations_per_hour_lte",
            0.000001,
            _MAX_PRODUCT_FALSE_ACTIVATIONS_PER_HOUR,
        )
        required_confidence = _calibration_number(
            criteria,
            "far_confidence_gte",
            _MIN_CALIBRATION_CONFIDENCE,
            0.999999,
        )
    except KeyError as error:
        raise WakeWordConfigurationError("wake_word_calibration_report_invalid") from error
    if (
        measured_at != report_measured_at
        or not _same_number(calibration_frr, report_frr)
        or not _same_number(calibration_confidence, report_confidence)
        or not _same_number(calibration_far_upper, report_far_upper)
        or report_frr > maximum_frr
        or report_far_upper > maximum_far
        or report_confidence < required_confidence
    ):
        raise WakeWordConfigurationError("wake_word_calibration_mismatch")
    return dict(calibration)


def _load_wakeword_config(
    manifest_path: Path | None, *, require_direct_calibration: bool
) -> WakeWordModelConfig:
    """Validate one stage-one asset with the requested authority boundary.

    Candidate mode validates every runtime field and byte hash but grants no
    authority by itself; only an independently attested combined verifier may
    consume it. Direct mode still requires the held-out FAR/FRR report (or the
    deliberately named development override).
    """

    manifest = (manifest_path or resolve_wakeword_manifest()).expanduser()
    payload = _read_manifest(manifest)
    if (
        _required_integer(payload, "sampleRate", SAMPLE_RATE, SAMPLE_RATE) != SAMPLE_RATE
        or _required_integer(payload, "windowSamples", WINDOW_SAMPLES, WINDOW_SAMPLES)
        != WINDOW_SAMPLES
    ):
        raise WakeWordConfigurationError("wake_word_model_incompatible")
    model_name = _required_string(payload, "modelName", 64)
    if not _MODEL_NAME_RE.fullmatch(model_name):
        raise WakeWordConfigurationError("wake_word_manifest_invalid")
    phrase = _required_string(payload, "phrase", 80)
    model_path = _resolve_model_path(manifest, _required_string(payload, "model", 255))
    expected_hash = _required_string(payload, "sha256", 64).casefold()
    if not _SHA256_RE.fullmatch(expected_hash) or _sha256(model_path) != expected_hash:
        raise WakeWordConfigurationError("wake_word_model_hash_mismatch")
    hop = _required_integer(payload, "hopSamples", 256, WINDOW_SAMPLES)
    debounce = _required_number(payload, "debounceSeconds", 0.5, 10.0)
    threshold = _required_number(payload, "threshold", 0.001, 0.999)
    raw_calibration = payload.get("calibration")
    if not require_direct_calibration:
        calibration = (
            dict(raw_calibration) if isinstance(raw_calibration, dict) else {}
        )
    elif isinstance(raw_calibration, dict) and raw_calibration.get("approved") is True:
        calibration = _validate_calibration(
            manifest,
            raw_calibration,
            model_name=model_name,
            phrase=phrase,
            model_sha256=expected_hash,
            threshold=threshold,
            hop_samples=hop,
            debounce_seconds=debounce,
        )
    elif _truthy_environment("BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED"):
        # The explicit development seam deliberately cannot turn malformed
        # "approved" evidence into a product-calibrated configuration.
        calibration = (
            dict(raw_calibration) if isinstance(raw_calibration, dict) else {}
        )
    else:
        raise WakeWordConfigurationError("wake_word_calibration_required")
    return WakeWordModelConfig(
        manifest_path=manifest.resolve(),
        model_path=model_path,
        model_name=model_name,
        phrase=phrase,
        threshold=threshold,
        hop_samples=hop,
        debounce_seconds=debounce,
        model_sha256=expected_hash,
        calibration=calibration,
    )


def load_wakeword_config(manifest_path: Path | None = None) -> WakeWordModelConfig:
    """Load a stage-one model that independently owns activation authority."""

    return _load_wakeword_config(
        manifest_path, require_direct_calibration=True
    )


def load_wakeword_candidate_config(
    manifest_path: Path | None = None,
) -> WakeWordModelConfig:
    """Load only model provenance; a combined verifier must grant authority."""

    return _load_wakeword_config(
        manifest_path, require_direct_calibration=False
    )


def inspect_wakeword_config(
    manifest_path: Path | None = None,
) -> tuple[WakeWordModelConfig | None, str | None]:
    """Return a non-throwing configuration result suitable for health probes."""

    try:
        return load_wakeword_config(manifest_path), None
    except WakeWordConfigurationError as error:
        return None, str(error)


def inspect_wakeword_candidate_config(
    manifest_path: Path | None = None,
) -> tuple[WakeWordModelConfig | None, str | None]:
    """Return a hash-valid stage-one proposal model without granting authority."""

    try:
        return load_wakeword_candidate_config(manifest_path), None
    except WakeWordConfigurationError as error:
        return None, str(error)


class AcousticWakeDetector:
    """Stateful window/debounce wrapper around LiveKit's stateless predictor.

    ``accept`` must run off the audio-capture thread.  It returns at most one
    detection per debounce interval and never persists the ring buffer.
    """

    def __init__(self, config: WakeWordModelConfig, predictor: Any | None = None) -> None:
        self.config = config
        if predictor is None:
            try:
                from livekit.wakeword import WakeWordModel

                def load_predictor() -> Any:
                    loaded = WakeWordModel()
                    loaded.load_model(config.model_path, config.model_name)
                    return loaded

                predictor = create_with_power_efficient_onnx(load_predictor)
            except ModuleNotFoundError as error:
                raise WakeWordRuntimeError("wake_word_runtime_missing") from error
            except Exception as error:  # noqa: BLE001 - backend errors stay contained
                raise WakeWordRuntimeError(
                    f"wake_word_runtime_load_failed:{type(error).__name__}"
                ) from error
        self._predictor = predictor
        self._frames: deque[np.ndarray] = deque()
        self._frame_samples = 0
        self._samples_since_score = 0
        self._last_detection_at = float("-inf")
        self.scored_last_frame = False
        self.last_prediction_seconds: float | None = None
        self.last_score: float | None = None

    @property
    def backend(self) -> str:
        return "livekit-wakeword"

    def reset(self) -> None:
        self._frames.clear()
        self._frame_samples = 0
        self._samples_since_score = 0
        self._last_detection_at = float("-inf")
        self.scored_last_frame = False
        self.last_prediction_seconds = None
        self.last_score = None

    def accept(self, frame: np.ndarray, now: float | None = None) -> WakeWordDetection | None:
        """Consume PCM/float mono audio and return a qualifying acoustic hit."""

        self.scored_last_frame = False
        audio = np.asarray(frame, dtype=np.float32).reshape(-1)
        if audio.size == 0:
            return None
        # Sounddevice can reuse a backing buffer.  Own the slice before it
        # crosses into the worker's rolling window.
        audio = np.ascontiguousarray(audio.copy())
        self._frames.append(audio)
        self._frame_samples += audio.size
        self._samples_since_score += audio.size
        self._trim_to_window()
        if self._frame_samples < WINDOW_SAMPLES or self._samples_since_score < self.config.hop_samples:
            return None
        self._samples_since_score %= self.config.hop_samples
        try:
            started = time.perf_counter()
            scores = self._predictor.predict(np.concatenate(tuple(self._frames)))
            self.last_prediction_seconds = time.perf_counter() - started
            self.scored_last_frame = True
        except Exception as error:  # noqa: BLE001 - worker reports a stable code
            raise WakeWordRuntimeError(
                f"wake_word_runtime_predict_failed:{type(error).__name__}"
            ) from error
        if not isinstance(scores, Mapping) or self.config.model_name not in scores:
            raise WakeWordRuntimeError("wake_word_runtime_model_score_missing")
        raw_score = scores[self.config.model_name]
        if isinstance(raw_score, bool):
            raise WakeWordRuntimeError("wake_word_runtime_invalid_score")
        try:
            score = float(raw_score)
        except (TypeError, ValueError) as error:
            raise WakeWordRuntimeError("wake_word_runtime_invalid_score") from error
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise WakeWordRuntimeError("wake_word_runtime_invalid_score")
        self.last_score = score
        detected_at = time.monotonic() if now is None else now
        if not isinstance(detected_at, (int, float)) or isinstance(detected_at, bool):
            raise WakeWordRuntimeError("wake_word_runtime_invalid_timestamp")
        detected_at = float(detected_at)
        if not math.isfinite(detected_at):
            raise WakeWordRuntimeError("wake_word_runtime_invalid_timestamp")
        if (
            score < self.config.threshold
            or detected_at - self._last_detection_at < self.config.debounce_seconds
        ):
            return None
        self._last_detection_at = detected_at
        return WakeWordDetection(
            model_name=self.config.model_name,
            phrase=self.config.phrase,
            confidence=score,
            timestamp=detected_at,
        )

    def _trim_to_window(self) -> None:
        while self._frames and self._frame_samples > WINDOW_SAMPLES:
            excess = self._frame_samples - WINDOW_SAMPLES
            oldest = self._frames[0]
            if oldest.size <= excess:
                self._frames.popleft()
                self._frame_samples -= oldest.size
            else:
                self._frames[0] = oldest[excess:]
                self._frame_samples -= excess


__all__ = [
    "AcousticWakeDetector",
    "CALIBRATION_REPORT_FILENAME",
    "CALIBRATION_REPORT_SCHEMA",
    "CALIBRATION_SCHEMA",
    "DEFAULT_WAKE_MANIFEST",
    "DEFAULT_HOP_SAMPLES",
    "MANIFEST_SCHEMA",
    "SAMPLE_RATE",
    "WINDOW_SAMPLES",
    "WakeWordConfigurationError",
    "WakeWordDetection",
    "WakeWordModelConfig",
    "WakeWordRuntimeError",
    "inspect_wakeword_candidate_config",
    "inspect_wakeword_config",
    "load_wakeword_candidate_config",
    "load_wakeword_config",
    "resolve_wakeword_manifest",
]
