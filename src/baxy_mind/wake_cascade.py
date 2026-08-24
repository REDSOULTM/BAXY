"""Attested HyperSpotter -> log-Mel -> lexical wake cascade."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import unicodedata
from typing import Any

import numpy as np

from .assets import AssetDescriptorError, resolve_asset
from .resource_policy import cpu_session_options
from .wakeword import WakeWordDetection, WakeWordRuntimeError


SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 48_000
LOGMEL_FRAMES = 300
LOGMEL_BINS = 80
MANIFEST_SCHEMA = "baxy-wake-cascade-v1"
ROUTED_MANIFEST_SCHEMA = "baxy-wake-cascade-v2"
CALIBRATION_REPORT_SCHEMA = "baxy-wake-cascade-gate-v1"
CALIBRATION_REPORT_FILENAME = "baxy-wake-cascade-gate-v1.json"
EXPECTED_ACOUSTIC_ALIASES = ("baxy", "baxi", "basi", "bakse")
EXPECTED_LEXICAL_ALIASES = frozenset(("baxy", "baxi", "boxy"))
EXPECTED_ENDPOINT_LEXICAL_ALIASES = frozenset(
    ("baxy", "baxi", "bakse", "backsy", "boxy")
)
_MAX_MANIFEST_BYTES = 64 * 1024
_MAX_REPORT_BYTES = 1024 * 1024
_MAX_GRAPH_BYTES = 64 * 1024 * 1024
_MAX_FILTER_BYTES = 256 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


class WakeCascadeConfigurationError(ValueError):
    """The cascade assets cannot receive microphone authority."""


@dataclass(frozen=True)
class WakeCascadeRoute:
    name: str
    upstream_indexes: tuple[int, ...]
    verifier_index: int
    verifier_threshold: float


@dataclass(frozen=True)
class WakeLexicalMatch:
    transcript: str
    command: str
    method: str


@dataclass(frozen=True)
class WakeCascadeConfig:
    manifest_path: Path
    upstream_graph_paths: tuple[Path, ...]
    upstream_graph_sha256: tuple[str, ...]
    mel_filters_path: Path
    mel_filters_sha256: str
    verifier_graph_path: Path
    verifier_graph_sha256: str
    verifier_graph_paths: tuple[Path, ...]
    verifier_graph_sha256s: tuple[str, ...]
    routes: tuple[WakeCascadeRoute, ...]
    phrase: str
    hop_samples: int
    history_windows: int
    debounce_seconds: float
    primary_threshold: float
    secondary_threshold: float
    rescue_alias_index: int | None
    rescue_alias_threshold: float | None
    verifier_threshold: float
    lexical_rescue_enabled: bool
    lexical_aliases: frozenset[str]
    direct_lexical_verifier_index: int | None
    direct_lexical_verifier_threshold: float | None
    direct_lexical_retry_speed_factors: tuple[float, ...]
    direct_lexical_hotwords_score: float
    direct_lexical_minimum_consecutive_hops: int
    direct_lexical_phonetic_confusion_score_gte: float | None
    endpoint_lexical_verifier_index: int | None
    endpoint_lexical_score_threshold: float | None
    endpoint_lexical_retry_speed_factors: tuple[float, ...]
    endpoint_lexical_aliases: frozenset[str]
    calibration: dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_object(path: Path, maximum: int, code: str) -> dict[str, Any]:
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= maximum:
            raise WakeCascadeConfigurationError(code)
        value = json.loads(path.read_text(encoding="utf-8"))
    except WakeCascadeConfigurationError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise WakeCascadeConfigurationError(code) from error
    if not isinstance(value, dict):
        raise WakeCascadeConfigurationError(code)
    return value


def _string(payload: Mapping[str, Any], name: str, maximum: int = 255) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
    return value.strip()


def _number(
    payload: Mapping[str, Any], name: str, minimum: float, maximum: float
) -> float:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
    return result


def _integer(payload: Mapping[str, Any], name: str, minimum: int, maximum: int) -> int:
    result = _number(payload, name, minimum, maximum)
    if not result.is_integer():
        raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
    return int(result)


def _hash(payload: Mapping[str, Any], name: str) -> str:
    value = _string(payload, name, 64).casefold()
    if not _SHA256_RE.fullmatch(value):
        raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
    return value


def _adjacent_file(
    manifest: Path,
    filename: str,
    *,
    suffixes: frozenset[str],
    maximum: int,
    code: str,
) -> Path:
    candidate = Path(filename)
    if (
        candidate.is_absolute()
        or candidate.name != filename
        or candidate.suffix.casefold() not in suffixes
    ):
        raise WakeCascadeConfigurationError(code)
    try:
        root = manifest.parent.resolve(strict=True)
        path = (root / candidate).resolve(strict=True)
        path.relative_to(root)
        if not path.is_file() or not 0 < path.stat().st_size <= maximum:
            raise WakeCascadeConfigurationError(code)
        return path
    except WakeCascadeConfigurationError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise WakeCascadeConfigurationError(code) from error


def resolve_wake_cascade_manifest() -> Path:
    configured = (os.environ.get("BAXY_VOICE_WAKE_CASCADE_MANIFEST") or "").strip()
    if configured:
        return Path(configured).expanduser()
    try:
        resolution = resolve_asset("wake_cascade_manifest")
    except AssetDescriptorError as error:
        raise WakeCascadeConfigurationError(
            "wake_cascade_asset_descriptor_invalid"
        ) from error
    if resolution.path is not None:
        return resolution.path
    return resolution.candidates[0] if resolution.candidates else Path()


def _uncalibrated_allowed() -> bool:
    return (
        os.environ.get("BAXY_VOICE_WAKE_CASCADE_ALLOW_UNCALIBRATED") or ""
    ).strip().casefold() in {"1", "true", "yes", "on"}


def _validate_calibration(
    manifest: Path, calibration: Mapping[str, Any], assets: Mapping[str, Any]
) -> dict[str, Any]:
    if calibration.get("approved") is not True:
        raise WakeCascadeConfigurationError("wake_cascade_calibration_required")
    if _string(calibration, "report", 128) != CALIBRATION_REPORT_FILENAME:
        raise WakeCascadeConfigurationError("wake_cascade_calibration_invalid")
    report_hash = _hash(calibration, "reportSha256")
    report_path = _adjacent_file(
        manifest,
        CALIBRATION_REPORT_FILENAME,
        suffixes=frozenset((".json",)),
        maximum=_MAX_REPORT_BYTES,
        code="wake_cascade_calibration_report_invalid",
    )
    if _sha256(report_path) != report_hash:
        raise WakeCascadeConfigurationError(
            "wake_cascade_calibration_report_hash_mismatch"
        )
    report = _read_object(
        report_path, _MAX_REPORT_BYTES, "wake_cascade_calibration_report_invalid"
    )
    if (
        report.get("schema") != CALIBRATION_REPORT_SCHEMA
        or report.get("role") != "validation"
        or report.get("candidateFrozen") is not True
        or report.get("corpusFrozen") is not True
        or report.get("physicalRoomValidated") is not True
        or report.get("promotable") is not True
    ):
        raise WakeCascadeConfigurationError("wake_cascade_calibration_report_invalid")
    report_assets = report.get("assets")
    metrics = report.get("metrics")
    if not isinstance(report_assets, dict) or not isinstance(metrics, dict):
        raise WakeCascadeConfigurationError("wake_cascade_calibration_report_invalid")
    if any(report_assets.get(name) != value for name, value in assets.items()):
        raise WakeCascadeConfigurationError("wake_cascade_calibration_mismatch")
    try:
        positives = int(metrics["positiveFiles"])
        positive_hits = int(metrics["positiveAcceptedFiles"])
        negatives = int(metrics["negativeFiles"])
        false_activations = int(metrics["negativeFalseActivations"])
        confidence = float(metrics["farConfidence"])
        far_upper = float(metrics["farUpperConfidencePerHour"])
    except (KeyError, TypeError, ValueError) as error:
        raise WakeCascadeConfigurationError(
            "wake_cascade_calibration_report_invalid"
        ) from error
    if (
        positives < 48
        or positive_hits != positives
        or negatives < 96
        or false_activations != 0
        or not math.isfinite(confidence)
        or confidence < 0.95
        or not math.isfinite(far_upper)
        or far_upper > 0.1
    ):
        raise WakeCascadeConfigurationError("wake_cascade_calibration_mismatch")
    return dict(calibration)


def _load_config(
    manifest_path: Path | None, *, require_calibration: bool
) -> WakeCascadeConfig:
    manifest = (manifest_path or resolve_wake_cascade_manifest()).expanduser()
    payload = _read_object(
        manifest, _MAX_MANIFEST_BYTES, "wake_cascade_manifest_missing"
    )
    if (
        payload.get("schema") not in {MANIFEST_SCHEMA, ROUTED_MANIFEST_SCHEMA}
        or payload.get("backend") != "onnxruntime-hyperspotter-logmel-cascade"
        or _integer(payload, "sampleRate", SAMPLE_RATE, SAMPLE_RATE) != SAMPLE_RATE
        or _integer(payload, "windowSamples", WINDOW_SAMPLES, WINDOW_SAMPLES)
        != WINDOW_SAMPLES
    ):
        raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
    aliases = payload.get("acousticAliases")
    lexical_aliases = payload.get("lexicalAliases")
    upstream = payload.get("upstreamModels")
    routed = payload.get("schema") == ROUTED_MANIFEST_SCHEMA
    verifier = payload.get("logmelVerifier")
    verifiers = payload.get("logmelVerifiers") if routed else [verifier]
    raw_routes = payload.get("routes") if routed else None
    direct_lexical = payload.get("directLexicalProposal") if routed else None
    endpoint_lexical = payload.get("endpointLexicalProposal") if routed else None
    rescue = payload.get("singleAliasRescue")
    if (
        aliases != list(EXPECTED_ACOUSTIC_ALIASES)
        or not isinstance(lexical_aliases, list)
        or frozenset(lexical_aliases) != EXPECTED_LEXICAL_ALIASES
        or not isinstance(upstream, list)
        or not 2 <= len(upstream) <= 4
        or not all(isinstance(item, dict) for item in upstream)
        or not isinstance(verifiers, list)
        or not 1 <= len(verifiers) <= 4
        or not all(isinstance(item, dict) for item in verifiers)
        or routed
        and not isinstance(raw_routes, list)
        or direct_lexical is not None
        and not isinstance(direct_lexical, dict)
        or endpoint_lexical is not None
        and not isinstance(endpoint_lexical, dict)
        or rescue is not None
        and not isinstance(rescue, dict)
    ):
        raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
    graphs = tuple(
        _adjacent_file(
            manifest,
            _string(item, "graph"),
            suffixes=frozenset((".onnx",)),
            maximum=_MAX_GRAPH_BYTES,
            code="wake_cascade_graph_invalid",
        )
        for item in upstream
    )
    graph_hashes = tuple(_hash(item, "graphSha256") for item in upstream)
    mel_path = _adjacent_file(
        manifest,
        _string(payload, "melFilters"),
        suffixes=frozenset((".npy",)),
        maximum=_MAX_FILTER_BYTES,
        code="wake_cascade_mel_filters_invalid",
    )
    mel_hash = _hash(payload, "melFiltersSha256")
    verifier_paths = tuple(
        _adjacent_file(
            manifest,
            _string(item, "graph"),
            suffixes=frozenset((".onnx",)),
            maximum=_MAX_GRAPH_BYTES,
            code="wake_cascade_verifier_invalid",
        )
        for item in verifiers
    )
    verifier_hashes = tuple(_hash(item, "graphSha256") for item in verifiers)
    if (
        any(_sha256(path) != expected for path, expected in zip(graphs, graph_hashes))
        or _sha256(mel_path) != mel_hash
        or any(
            _sha256(path) != expected
            for path, expected in zip(verifier_paths, verifier_hashes)
        )
    ):
        raise WakeCascadeConfigurationError("wake_cascade_asset_hash_mismatch")
    assets = {
        "upstreamGraphSha256": list(graph_hashes),
        "melFiltersSha256": mel_hash,
        "logmelVerifierSha256": (
            list(verifier_hashes) if routed else verifier_hashes[0]
        ),
    }
    raw_calibration = payload.get("calibration")
    if not require_calibration:
        calibration = dict(raw_calibration) if isinstance(raw_calibration, dict) else {}
    elif isinstance(raw_calibration, dict) and raw_calibration.get("approved") is True:
        calibration = _validate_calibration(manifest, raw_calibration, assets)
    elif _uncalibrated_allowed():
        calibration = dict(raw_calibration) if isinstance(raw_calibration, dict) else {}
    else:
        raise WakeCascadeConfigurationError("wake_cascade_calibration_required")
    rescue_alias_index = None
    rescue_alias_threshold = None
    lexical_rescue_enabled = payload.get("lexicalRescueEnabled", True)
    if not isinstance(lexical_rescue_enabled, bool):
        raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
    if isinstance(rescue, dict):
        rescue_alias = _string(rescue, "alias", 32)
        if rescue_alias not in EXPECTED_ACOUSTIC_ALIASES:
            raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
        rescue_alias_index = EXPECTED_ACOUSTIC_ALIASES.index(rescue_alias)
        rescue_alias_threshold = _number(rescue, "logitGte", -20.0, 20.0)
    if routed:
        assert isinstance(raw_routes, list)
        if not 1 <= len(raw_routes) <= 6 or not all(
            isinstance(item, dict) for item in raw_routes
        ):
            raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
        parsed_routes: list[WakeCascadeRoute] = []
        route_names: set[str] = set()
        for item in raw_routes:
            assert isinstance(item, dict)
            name = _string(item, "name", 64)
            indexes = item.get("upstreamModelIndexes")
            verifier_index = _integer(item, "verifierIndex", 0, len(verifier_paths) - 1)
            if (
                name in route_names
                or not isinstance(indexes, list)
                or not 1 <= len(indexes) <= len(graphs)
                or any(
                    isinstance(index, bool)
                    or not isinstance(index, int)
                    or not 0 <= index < len(graphs)
                    for index in indexes
                )
                or len(set(indexes)) != len(indexes)
            ):
                raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
            route_names.add(name)
            parsed_routes.append(
                WakeCascadeRoute(
                    name=name,
                    upstream_indexes=tuple(indexes),
                    verifier_index=verifier_index,
                    verifier_threshold=_number(
                        verifiers[verifier_index], "scoreGte", -20.0, 20.0
                    ),
                )
            )
        routes = tuple(parsed_routes)
    else:
        routes = (
            WakeCascadeRoute(
                name="default",
                upstream_indexes=tuple(range(len(graphs))),
                verifier_index=0,
                verifier_threshold=_number(verifiers[0], "scoreGte", -20.0, 20.0),
            ),
        )
    direct_lexical_verifier_index = None
    direct_lexical_verifier_threshold = None
    direct_lexical_retry_speed_factors: tuple[float, ...] = ()
    direct_lexical_hotwords_score = 5.0
    direct_lexical_minimum_consecutive_hops = 4
    direct_lexical_phonetic_confusion_score_gte = None
    if isinstance(direct_lexical, dict):
        direct_lexical_verifier_index = _integer(
            direct_lexical, "verifierIndex", 0, len(verifier_paths) - 1
        )
        direct_lexical_verifier_threshold = _number(
            direct_lexical, "scoreGte", -20.0, 20.0
        )
        raw_retry_factors = direct_lexical.get("retrySpeedFactors", [])
        if (
            not isinstance(raw_retry_factors, list)
            or len(raw_retry_factors) > 3
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not 0.75 <= float(value) <= 1.25
                for value in raw_retry_factors
            )
            or len({float(value) for value in raw_retry_factors})
            != len(raw_retry_factors)
        ):
            raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
        direct_lexical_retry_speed_factors = tuple(
            float(value) for value in raw_retry_factors
        )
        direct_with_defaults = dict(direct_lexical)
        direct_with_defaults.setdefault("hotwordsScore", 5.0)
        direct_lexical_hotwords_score = _number(
            direct_with_defaults, "hotwordsScore", 1.0, 20.0
        )
        direct_with_defaults.setdefault("minimumConsecutiveHops", 4)
        direct_lexical_minimum_consecutive_hops = _integer(
            direct_with_defaults, "minimumConsecutiveHops", 1, 12
        )
        if "phoneticConfusionScoreGte" in direct_lexical:
            direct_lexical_phonetic_confusion_score_gte = _number(
                direct_lexical, "phoneticConfusionScoreGte", -20.0, 20.0
            )
    endpoint_lexical_verifier_index = None
    endpoint_lexical_score_threshold = None
    endpoint_lexical_retry_speed_factors: tuple[float, ...] = ()
    endpoint_lexical_aliases: frozenset[str] = frozenset()
    if isinstance(endpoint_lexical, dict):
        if not isinstance(direct_lexical, dict):
            raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
        endpoint_lexical_verifier_index = _integer(
            endpoint_lexical, "verifierIndex", 0, len(verifier_paths) - 1
        )
        endpoint_lexical_score_threshold = _number(
            endpoint_lexical, "scoreGte", -20.0, 20.0
        )
        raw_endpoint_aliases = endpoint_lexical.get("aliases")
        raw_endpoint_retry_factors = endpoint_lexical.get("retrySpeedFactors")
        if (
            endpoint_lexical_verifier_index != direct_lexical_verifier_index
            or not isinstance(raw_endpoint_aliases, list)
            or len(raw_endpoint_aliases) != len(EXPECTED_ENDPOINT_LEXICAL_ALIASES)
            or any(not isinstance(value, str) for value in raw_endpoint_aliases)
            or frozenset(raw_endpoint_aliases) != EXPECTED_ENDPOINT_LEXICAL_ALIASES
            or not isinstance(raw_endpoint_retry_factors, list)
            or len(raw_endpoint_retry_factors) > 3
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not 0.75 <= float(value) <= 1.25
                for value in raw_endpoint_retry_factors
            )
            or len({float(value) for value in raw_endpoint_retry_factors})
            != len(raw_endpoint_retry_factors)
        ):
            raise WakeCascadeConfigurationError("wake_cascade_manifest_invalid")
        endpoint_lexical_aliases = frozenset(raw_endpoint_aliases)
        endpoint_lexical_retry_speed_factors = tuple(
            float(value) for value in raw_endpoint_retry_factors
        )
    return WakeCascadeConfig(
        manifest_path=manifest.resolve(),
        upstream_graph_paths=graphs,
        upstream_graph_sha256=graph_hashes,
        mel_filters_path=mel_path,
        mel_filters_sha256=mel_hash,
        verifier_graph_path=verifier_paths[0],
        verifier_graph_sha256=verifier_hashes[0],
        verifier_graph_paths=verifier_paths,
        verifier_graph_sha256s=verifier_hashes,
        routes=routes,
        phrase=_string(payload, "phrase", 80),
        hop_samples=_integer(payload, "hopSamples", 256, 16_000),
        history_windows=_integer(payload, "historyWindows", 1, 40),
        debounce_seconds=_number(payload, "debounceSeconds", 0.5, 10.0),
        primary_threshold=_number(payload, "primaryLogitGte", -20.0, 20.0),
        secondary_threshold=_number(payload, "secondaryLogitGte", -20.0, 20.0),
        rescue_alias_index=rescue_alias_index,
        rescue_alias_threshold=rescue_alias_threshold,
        verifier_threshold=routes[0].verifier_threshold,
        lexical_rescue_enabled=lexical_rescue_enabled,
        lexical_aliases=frozenset(str(value) for value in lexical_aliases),
        direct_lexical_verifier_index=direct_lexical_verifier_index,
        direct_lexical_verifier_threshold=direct_lexical_verifier_threshold,
        direct_lexical_retry_speed_factors=direct_lexical_retry_speed_factors,
        direct_lexical_hotwords_score=direct_lexical_hotwords_score,
        direct_lexical_minimum_consecutive_hops=(
            direct_lexical_minimum_consecutive_hops
        ),
        direct_lexical_phonetic_confusion_score_gte=(
            direct_lexical_phonetic_confusion_score_gte
        ),
        endpoint_lexical_verifier_index=endpoint_lexical_verifier_index,
        endpoint_lexical_score_threshold=endpoint_lexical_score_threshold,
        endpoint_lexical_retry_speed_factors=endpoint_lexical_retry_speed_factors,
        endpoint_lexical_aliases=endpoint_lexical_aliases,
        calibration=calibration,
    )


def load_wake_cascade_config(manifest_path: Path | None = None) -> WakeCascadeConfig:
    return _load_config(manifest_path, require_calibration=True)


def load_wake_cascade_candidate_config(
    manifest_path: Path | None = None,
) -> WakeCascadeConfig:
    return _load_config(manifest_path, require_calibration=False)


def inspect_wake_cascade_config(
    manifest_path: Path | None = None,
) -> tuple[WakeCascadeConfig | None, str | None]:
    try:
        return load_wake_cascade_config(manifest_path), None
    except WakeCascadeConfigurationError as error:
        return None, str(error)


def normalize_lexical_transcript(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text)).casefold()
    folded = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def has_strict_exact_alias(text: str, aliases: frozenset[str]) -> bool:
    return normalize_lexical_transcript(text) in aliases


def has_strict_leading_alias(text: str, aliases: frozenset[str]) -> bool:
    words = normalize_lexical_transcript(text).split()
    return bool(words) and words[0] in aliases


_BARE_PHONETIC_ALIASES = frozenset(("bakse", "backsy", "basi", "vasi", "vaxi", "waxi"))
_CONTEXT_PHONETIC_ALIASES = frozenset((*_BARE_PHONETIC_ALIASES, "waxi"))
_ACTION_OPENERS = frozenset(
    (
        "abre",
        "abrir",
        "apaga",
        "busca",
        "buscar",
        "call",
        "configura",
        "crea",
        "crear",
        "describe",
        "dime",
        "dimela",
        "enciende",
        "envia",
        "enviar",
        "lee",
        "llama",
        "llamar",
        "lower",
        "manda",
        "mandar",
        "muestra",
        "muestrame",
        "open",
        "play",
        "pon",
        "read",
        "recuerdame",
        "recordar",
        "remind",
        "reproduce",
        "search",
        "send",
        "set",
        "show",
        "tell",
        "take",
        "turn",
    )
)
_QUESTION_WORDS = frozenset(
    (
        "como",
        "cuando",
        "cuanta",
        "cuanto",
        "donde",
        "how",
        "que",
        "what",
        "when",
        "where",
    )
)
_QUESTION_TOPICS = frozenset(
    (
        "abierto",
        "active",
        "activo",
        "battery",
        "bateria",
        "hora",
        "it",
        "left",
        "open",
        "queda",
        "time",
    )
)
_CALL_WORDS = frozenset(("call", "lama", "llama", "llamar", "lamar", "mammer"))
_FUTURE_WORDS = frozenset(("manana", "manyana", "miniana", "tomorrow"))
_ENDPOINT_PHONETIC_ALIASES = frozenset(("vaxi", "waxi"))


def _command_after_words(text: str, count: int) -> str:
    matches = list(re.finditer(r"[^\W_]+", str(text), flags=re.UNICODE))
    if len(matches) < count:
        return ""
    return str(text)[matches[count - 1].end() :].lstrip(" ,.:;!?¡¿-")


def _has_bounded_command_intent(words: tuple[str, ...]) -> bool:
    values = frozenset(words)
    return bool(
        words
        and (
            words[0] in _ACTION_OPENERS
            or values & _QUESTION_WORDS
            and values & _QUESTION_TOPICS
            or values & _CALL_WORDS
            and values & _FUTURE_WORDS
        )
    )


def match_bounded_lexical_wake(
    transcripts: Iterable[str],
    aliases: frozenset[str],
    *,
    verifier_score: float | None = None,
    phonetic_confusion_score_gte: float | None = None,
) -> WakeLexicalMatch | None:
    """Confirm a direct acoustic proposal with bounded leading lexical evidence.

    Exact product aliases remain authoritative. A small set of measured ASR
    confusions is accepted only at the beginning and only when the remaining
    words still form a command/question context; ordinary mentions of BAXY or
    words such as ``basic`` elsewhere in a sentence stay rejected.
    """

    for transcript in transcripts:
        normalized = normalize_lexical_transcript(transcript)
        words = tuple(normalized.split())
        if not words:
            continue
        if words[0] in aliases:
            return WakeLexicalMatch(
                transcript=str(transcript).strip(),
                command=_command_after_words(transcript, 1),
                method="exact_leading_alias",
            )
        tail = words[1:]
        if words[0] in _BARE_PHONETIC_ALIASES and len(words) == 1:
            return WakeLexicalMatch(
                transcript=str(transcript).strip(),
                command="",
                method="bounded_bare_phonetic_alias",
            )
        if words[0] in _CONTEXT_PHONETIC_ALIASES and _has_bounded_command_intent(tail):
            return WakeLexicalMatch(
                transcript=str(transcript).strip(),
                command=_command_after_words(transcript, 1),
                method="bounded_phonetic_alias",
            )
        if words[:2] in (("va", "si"), ("vas", "y")) and _has_bounded_command_intent(
            words[2:]
        ):
            return WakeLexicalMatch(
                transcript=str(transcript).strip(),
                command=_command_after_words(transcript, 2),
                method="bounded_split_phonetic_alias",
            )
        basic_context = frozenset(tail)
        if words[0] == "basic" and (
            basic_context & _QUESTION_WORDS
            and basic_context & frozenset(("battery", "bateria"))
            or basic_context & _CALL_WORDS
            and basic_context & _FUTURE_WORDS
            or sum(word.isdigit() for word in tail) >= 2
            or tail
            and tail[0] == "lower"
            and basic_context & frozenset(("brightness", "screen", "volume"))
        ):
            return WakeLexicalMatch(
                transcript=str(transcript).strip(),
                command=_command_after_words(transcript, 1),
                method="bounded_basic_confusion",
            )
        if words[:2] == ("they", "see"):
            context = frozenset(words[2:])
            if context & _QUESTION_WORDS and "battery" in context:
                return WakeLexicalMatch(
                    transcript=str(transcript).strip(),
                    command=_command_after_words(transcript, 2),
                    method="bounded_they_see_confusion",
                )
            if (
                len(words) == 2
                and verifier_score is not None
                and phonetic_confusion_score_gte is not None
                and math.isfinite(verifier_score)
                and math.isfinite(phonetic_confusion_score_gte)
                and verifier_score >= phonetic_confusion_score_gte
            ):
                return WakeLexicalMatch(
                    transcript=str(transcript).strip(),
                    command="",
                    method="score_gated_bare_they_see_confusion",
                )
    return None


def match_suffix_independent_endpoint_wake(
    transcripts: Iterable[str],
    aliases: frozenset[str],
) -> WakeLexicalMatch | None:
    """Authorize an endpoint while excluding acoustically ambiguous Basi forms.

    Exact canonical spellings do not depend on the command suffix. Only
    measured Baxy-like ASR spellings receive a command-shape check; ``basic``,
    ``Basi``, ``vas y`` and ``they see`` require an independent acoustic route.
    """

    for transcript in transcripts:
        normalized = normalize_lexical_transcript(transcript)
        words = tuple(normalized.split())
        if not words:
            continue
        if words[0] in aliases:
            return WakeLexicalMatch(
                transcript=str(transcript).strip(),
                command=_command_after_words(transcript, 1),
                method="endpoint_exact_leading_alias",
            )
        if words[0] in _ENDPOINT_PHONETIC_ALIASES and _has_bounded_command_intent(
            words[1:]
        ):
            return WakeLexicalMatch(
                transcript=str(transcript).strip(),
                command=_command_after_words(transcript, 1),
                method="endpoint_bounded_phonetic_alias",
            )
    return None


def time_scaled_recognition_audio(audio: np.ndarray, factor: float) -> np.ndarray:
    """Create the deterministic ASR-only speed view bound by the manifest."""

    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if (
        values.size == 0
        or not np.isfinite(values).all()
        or not math.isfinite(factor)
        or not 0.75 <= factor <= 1.25
    ):
        raise ValueError("wake_lexical_retry_audio_invalid")
    positions = np.arange(0.0, float(values.size), factor, dtype=np.float64)
    return np.interp(
        positions,
        np.arange(values.size, dtype=np.float64),
        values,
    ).astype(np.float32)


def same_window_consensus(
    logits: np.ndarray, *, primary_threshold: float, secondary_threshold: float
) -> bool:
    values = np.asarray(logits, dtype=np.float32).reshape(-1)
    if len(values) < 2 or not np.isfinite(values).all():
        raise WakeWordRuntimeError("wake_cascade_upstream_output_invalid")
    ordered = np.sort(values)
    return bool(ordered[-1] >= primary_threshold and ordered[-2] >= secondary_threshold)


def upstream_logits_candidate(logits: np.ndarray, config: WakeCascadeConfig) -> bool:
    """Apply the manifest-bound upstream proposal policy to one logit row."""

    values = np.asarray(logits, dtype=np.float32).reshape(-1)
    if values.shape != (len(EXPECTED_ACOUSTIC_ALIASES),):
        raise WakeWordRuntimeError("wake_cascade_upstream_output_invalid")
    if same_window_consensus(
        values,
        primary_threshold=config.primary_threshold,
        secondary_threshold=config.secondary_threshold,
    ):
        return True
    return bool(
        config.rescue_alias_index is not None
        and config.rescue_alias_threshold is not None
        and values[config.rescue_alias_index] >= config.rescue_alias_threshold
    )


def numpy_log_mel_spectrogram(audio: np.ndarray, mel_filters: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    filters = np.asarray(mel_filters, dtype=np.float32)
    if values.shape != (WINDOW_SAMPLES,) or filters.shape != (LOGMEL_BINS, 201):
        raise WakeWordRuntimeError("wake_cascade_logmel_shape_invalid")
    padded = np.pad(values, (200, 200), mode="reflect")
    frames = np.lib.stride_tricks.sliding_window_view(padded, 400)[::160]
    window = np.hanning(401)[:-1].astype(np.float32)
    stft = np.fft.rfft(frames * window[None, :], n=400, axis=1)
    magnitudes = (np.abs(stft) ** 2).astype(np.float32).T[:, :-1]
    mel = filters @ magnitudes
    log_spec = np.log10(np.maximum(mel, np.float32(1e-10)))
    log_spec = np.maximum(log_spec, np.max(log_spec) - np.float32(8.0))
    result = ((log_spec + np.float32(4.0)) / np.float32(4.0)).T.astype(np.float32)
    if result.shape != (LOGMEL_FRAMES, LOGMEL_BINS) or not np.isfinite(result).all():
        raise WakeWordRuntimeError("wake_cascade_logmel_invalid")
    return result


class HyperspotterCascadeDetector:
    """Bounded streaming proposal detector with an in-memory log-Mel history."""

    def __init__(
        self,
        config: WakeCascadeConfig,
        *,
        upstream_sessions: tuple[Any, ...] | None = None,
        verifier_session: Any | None = None,
        verifier_sessions: tuple[Any, ...] | None = None,
    ) -> None:
        self.config = config
        try:
            mel = np.load(config.mel_filters_path, allow_pickle=False)
        except (OSError, ValueError) as error:
            raise WakeWordRuntimeError(
                "wake_cascade_mel_filters_load_failed"
            ) from error
        self._mel_filters = np.asarray(mel, dtype=np.float32)
        if self._mel_filters.shape != (LOGMEL_BINS, 201):
            raise WakeWordRuntimeError("wake_cascade_mel_filters_invalid")
        if verifier_sessions is None and verifier_session is not None:
            verifier_sessions = (verifier_session,)
        if upstream_sessions is None or verifier_sessions is None:
            try:
                import onnxruntime as ort

                options = cpu_session_options(
                    ort,
                    environment_name="BAXY_VOICE_WAKE_THREADS",
                )
                if upstream_sessions is None:
                    upstream_sessions = tuple(
                        ort.InferenceSession(
                            str(path),
                            sess_options=options,
                            providers=["CPUExecutionProvider"],
                        )
                        for path in config.upstream_graph_paths
                    )
                if verifier_sessions is None:
                    verifier_sessions = tuple(
                        ort.InferenceSession(
                            str(path),
                            sess_options=options,
                            providers=["CPUExecutionProvider"],
                        )
                        for path in config.verifier_graph_paths
                    )
            except ModuleNotFoundError as error:
                raise WakeWordRuntimeError("wake_cascade_runtime_missing") from error
            except Exception as error:  # noqa: BLE001
                raise WakeWordRuntimeError(
                    f"wake_cascade_runtime_load_failed:{type(error).__name__}"
                ) from error
        self._upstream_sessions = upstream_sessions
        self._verifier_sessions = verifier_sessions
        if len(self._upstream_sessions) != len(config.upstream_graph_paths) or len(
            self._verifier_sessions
        ) != len(config.verifier_graph_paths):
            raise WakeWordRuntimeError("wake_cascade_runtime_session_count_invalid")
        self._frames: deque[np.ndarray] = deque()
        self._frame_samples = 0
        self._samples_until_score = WINDOW_SAMPLES
        self._history: deque[np.ndarray] = deque(maxlen=config.history_windows)
        self._last_detection_at = float("-inf")
        self._inference_lock = threading.Lock()
        self.last_prediction_seconds: float | None = None
        self.last_score: float | None = None
        self._direct_lexical_pending_hops = 0

    @property
    def backend(self) -> str:
        return "hyperspotter-logmel-cascade"

    def reset(self) -> None:
        self._frames.clear()
        self._frame_samples = 0
        self._samples_until_score = WINDOW_SAMPLES
        self._history.clear()
        self._last_detection_at = float("-inf")
        self.last_prediction_seconds = None
        self.last_score = None
        self._direct_lexical_pending_hops = 0

    def _trim(self) -> None:
        while self._frames and self._frame_samples > WINDOW_SAMPLES:
            excess = self._frame_samples - WINDOW_SAMPLES
            oldest = self._frames[0]
            if len(oldest) <= excess:
                self._frames.popleft()
                self._frame_samples -= len(oldest)
            else:
                self._frames[0] = oldest[excess:]
                self._frame_samples -= excess

    def _upstream_candidates(self, logmel: np.ndarray) -> tuple[bool, ...]:
        results: list[bool] = []
        for session in self._upstream_sessions:
            output = session.run(["logits"], {"logmel": logmel[None, :, :]})[0]
            values = np.asarray(output, dtype=np.float32)
            if values.shape != (1, len(EXPECTED_ACOUSTIC_ALIASES)):
                raise WakeWordRuntimeError("wake_cascade_upstream_output_invalid")
            results.append(upstream_logits_candidate(values[0], self.config))
        return tuple(results)

    def _history_score(self, verifier_index: int) -> float:
        features = np.stack(tuple(self._history)).astype(np.float32)
        output = self._verifier_sessions[verifier_index].run(
            ["wake_logit"], {"logmel": features}
        )[0]
        scores = np.asarray(output, dtype=np.float32).reshape(-1)
        if len(scores) != len(features) or not np.isfinite(scores).all():
            raise WakeWordRuntimeError("wake_cascade_verifier_output_invalid")
        return float(np.max(scores))

    def score_endpoint_lexical(self, audio: np.ndarray) -> float:
        """Score one completed VAD turn with the manifest-bound endpoint verifier."""

        verifier_index = self.config.endpoint_lexical_verifier_index
        if verifier_index is None:
            raise WakeWordRuntimeError("wake_endpoint_lexical_not_configured")
        values = np.asarray(audio, dtype=np.float32).reshape(-1)
        if (
            values.size < 1
            or values.size > 60 * SAMPLE_RATE
            or not np.isfinite(values).all()
        ):
            raise WakeWordRuntimeError("wake_endpoint_lexical_audio_invalid")
        padded = np.pad(values, (SAMPLE_RATE, SAMPLE_RATE))
        if padded.size < WINDOW_SAMPLES:
            padded = np.pad(padded, (0, WINDOW_SAMPLES - padded.size))
        starts = list(
            range(
                0,
                padded.size - WINDOW_SAMPLES + 1,
                self.config.hop_samples,
            )
        )
        final = padded.size - WINDOW_SAMPLES
        if starts[-1] != final:
            starts.append(final)
        features = np.stack(
            [
                numpy_log_mel_spectrogram(
                    np.ascontiguousarray(padded[start : start + WINDOW_SAMPLES]),
                    self._mel_filters,
                )
                for start in starts
            ]
        ).astype(np.float32)
        try:
            with self._inference_lock:
                output = self._verifier_sessions[verifier_index].run(
                    ["wake_logit"], {"logmel": features}
                )[0]
        except Exception as error:  # noqa: BLE001
            raise WakeWordRuntimeError(
                f"wake_endpoint_lexical_score_failed:{type(error).__name__}"
            ) from error
        scores = np.asarray(output, dtype=np.float32).reshape(-1)
        if scores.size != len(features) or not np.isfinite(scores).all():
            raise WakeWordRuntimeError("wake_endpoint_lexical_score_invalid")
        return float(np.max(scores))

    def accept(
        self, frame: np.ndarray, now: float | None = None
    ) -> WakeWordDetection | None:
        audio = np.asarray(frame, dtype=np.float32).reshape(-1)
        if audio.size == 0:
            return None
        if not np.isfinite(audio).all():
            raise WakeWordRuntimeError("wake_cascade_audio_invalid")
        owned = np.ascontiguousarray(audio.copy())
        offset = 0
        while offset < len(owned):
            take = min(len(owned) - offset, self._samples_until_score)
            segment = np.ascontiguousarray(owned[offset : offset + take])
            self._frames.append(segment)
            self._frame_samples += len(segment)
            self._samples_until_score -= len(segment)
            offset += len(segment)
            self._trim()
            if self._samples_until_score:
                continue
            self._samples_until_score = self.config.hop_samples
            with self._inference_lock:
                detection = self._score_current_window(now)
            if detection is not None:
                return detection
        return None

    def _score_current_window(self, now: float | None) -> WakeWordDetection | None:
        if self._frame_samples != WINDOW_SAMPLES:
            raise WakeWordRuntimeError("wake_cascade_window_state_invalid")
        started = time.perf_counter()
        logmel = numpy_log_mel_spectrogram(
            np.concatenate(tuple(self._frames)), self._mel_filters
        )
        self._history.append(logmel)
        try:
            upstream_candidates = self._upstream_candidates(logmel)
            candidate_routes = [
                route
                for route in self.config.routes
                if any(upstream_candidates[index] for index in route.upstream_indexes)
            ]
            scores: dict[int, float] = {}
            accepted_scores: list[float] = []
            for route in candidate_routes:
                if route.verifier_index not in scores:
                    scores[route.verifier_index] = self._history_score(
                        route.verifier_index
                    )
                score = scores[route.verifier_index]
                if score >= route.verifier_threshold:
                    accepted_scores.append(score)
            direct_lexical_score = None
            direct_index = self.config.direct_lexical_verifier_index
            direct_threshold = self.config.direct_lexical_verifier_threshold
            if direct_index is not None and direct_threshold is not None:
                if direct_index not in scores:
                    scores[direct_index] = self._history_score(direct_index)
                direct_lexical_score = scores[direct_index]
        except WakeWordRuntimeError:
            raise
        except Exception as error:  # noqa: BLE001
            raise WakeWordRuntimeError(
                f"wake_cascade_predict_failed:{type(error).__name__}"
            ) from error
        self.last_prediction_seconds = time.perf_counter() - started
        if not scores:
            return None
        score = max(scores.values())
        self.last_score = score
        direct_lexical_above_threshold = bool(
            direct_lexical_score is not None
            and direct_threshold is not None
            and direct_lexical_score >= direct_threshold
        )
        if direct_lexical_above_threshold and candidate_routes:
            self._direct_lexical_pending_hops += 1
            direct_lexical_accepted = (
                self._direct_lexical_pending_hops
                >= self.config.direct_lexical_minimum_consecutive_hops
            )
        else:
            self._direct_lexical_pending_hops = 0
            direct_lexical_accepted = bool(direct_lexical_above_threshold)
        route_lexical_accepted = bool(
            candidate_routes and self.config.lexical_rescue_enabled
        )
        if (
            not accepted_scores
            and not direct_lexical_accepted
            and not route_lexical_accepted
        ):
            return None
        detected_at = time.monotonic() if now is None else now
        if (
            isinstance(detected_at, bool)
            or not isinstance(detected_at, (int, float))
            or not math.isfinite(float(detected_at))
        ):
            raise WakeWordRuntimeError("wake_cascade_timestamp_invalid")
        detected_at = float(detected_at)
        if detected_at - self._last_detection_at < self.config.debounce_seconds:
            return None
        self._last_detection_at = detected_at
        acoustic = bool(accepted_scores)
        if accepted_scores:
            score = max(accepted_scores)
        elif direct_lexical_accepted:
            assert direct_lexical_score is not None
            score = direct_lexical_score
        confidence = 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, score))))
        return WakeWordDetection(
            model_name="baxy-hyperspotter-logmel-cascade-v1",
            phrase=self.config.phrase,
            confidence=confidence,
            timestamp=detected_at,
            method=(
                "logmel_verifier"
                if acoustic
                else "direct_lexical_proposal"
                if direct_lexical_accepted
                else "strict_lexical_rescue"
            ),
            verifier_score=score,
            lexical_rescue_required=not acoustic,
        )


__all__ = [
    "CALIBRATION_REPORT_FILENAME",
    "CALIBRATION_REPORT_SCHEMA",
    "HyperspotterCascadeDetector",
    "MANIFEST_SCHEMA",
    "ROUTED_MANIFEST_SCHEMA",
    "WakeCascadeConfig",
    "WakeCascadeRoute",
    "WakeCascadeConfigurationError",
    "has_strict_exact_alias",
    "has_strict_leading_alias",
    "inspect_wake_cascade_config",
    "load_wake_cascade_candidate_config",
    "load_wake_cascade_config",
    "match_bounded_lexical_wake",
    "match_suffix_independent_endpoint_wake",
    "normalize_lexical_transcript",
    "resolve_wake_cascade_manifest",
    "same_window_consensus",
    "time_scaled_recognition_audio",
    "upstream_logits_candidate",
]
