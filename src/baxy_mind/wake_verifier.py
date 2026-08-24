"""Attested phoneme-CTC authority for a permissive acoustic wake proposal."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import unicodedata
from typing import Any

import numpy as np

from .assets import AssetDescriptorError, resolve_asset
from .resource_policy import cpu_session_options


SAMPLE_RATE = 16_000
MANIFEST_SCHEMA = "baxy-wake-verifier-v1"
CALIBRATION_REPORT_SCHEMA = "baxy-wake-verifier-gate-v1"
CALIBRATION_REPORT_FILENAME = "baxy-wake-verifier-gate-v1.json"
_MAX_MANIFEST_BYTES = 32 * 1024
_MAX_REPORT_BYTES = 512 * 1024
_MAX_GRAPH_BYTES = 64 * 1024 * 1024
_MAX_GRAPH_DATA_BYTES = 2 * 1024 * 1024 * 1024
_MAX_VOCAB_BYTES = 64 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)

CATEGORY_TOKENS: dict[str, tuple[str, ...]] = {
    "blank": (),
    "B": ("b",),
    "BETA": ("\u03b2",),
    "V": ("v",),
    "F": ("f",),
    "P": ("p",),
    "A": ("a",),
    "AE": ("\u00e6",),
    "AA": ("\u0251",),
    "UH": ("\u028c",),
    "K": ("k",),
    "S": ("s",),
    "S_PAL": ("s\u02b2",),
    "SH": ("\u0283",),
    "I": ("i",),
    "IH": ("\u026a",),
    "R_TAP": ("\u027e",),
    "other": (),
}
CATEGORY_NAMES = tuple(CATEGORY_TOKENS)
BLANK_ID = CATEGORY_NAMES.index("blank")
TARGET_CATEGORY_SEQUENCES: tuple[tuple[str, ...], ...] = (
    ("B", "A", "K", "S", "I"),
    ("B", "AE", "K", "S", "I"),
    ("B", "AE", "K", "S", "IH"),
    ("B", "AA", "K", "S", "I"),
    ("B", "A", "K", "S_PAL", "I"),
    ("B", "AA", "K", "S_PAL", "I"),
    ("B", "UH", "K", "S_PAL", "I"),
    ("B", "A", "R_TAP", "K", "S", "I"),
    ("BETA", "A", "K", "S", "I"),
    ("BETA", "A", "R_TAP", "K", "S", "I"),
)
_EXACT_LEXICAL_TARGETS = frozenset(
    {
        "baxy",
        "baxi",
        "basi",
        "bakse",
        "baxiferrol",
        "maxiferror",
        "maxiferron",
        "\u0431\u0430\u043a\u0441\u0438",
        "\u0431\u0430\u043a\u0441\u0435",
        "\u0431\u0430\u043a\u0441\u0438\u043d",
    }
)
_EXACT_LEXICAL_PHRASES = frozenset(
    {
        ("maxi", "ferrol"),
        ("maxi", "ferror"),
        ("maxi", "ferron"),
    }
)


def _confusable_category_sequences() -> tuple[tuple[str, ...], ...]:
    values: list[tuple[str, ...]] = []
    for initial in ("V", "F", "P"):
        for vowel in ("A", "AE", "AA", "UH"):
            for sibilant in ("S", "S_PAL"):
                for ending in ("I", "IH"):
                    values.append((initial, vowel, "K", sibilant, ending))
    for initial in ("B", "BETA"):
        for vowel in ("A", "AE", "AA", "UH"):
            for ending in ("I", "IH"):
                values.append((initial, vowel, "K", "SH", ending))
    return tuple(values)


def _encode_category_sequences(
    sequences: Iterable[Sequence[str]],
) -> tuple[tuple[int, ...], ...]:
    ids = {name: index for index, name in enumerate(CATEGORY_NAMES)}
    return tuple(tuple(ids[name] for name in sequence) for sequence in sequences)


TARGET_IDS = _encode_category_sequences(TARGET_CATEGORY_SEQUENCES)
CONFUSABLE_IDS = _encode_category_sequences(_confusable_category_sequences())


class WakeVerifierConfigurationError(ValueError):
    """The verifier asset cannot authorize an acoustic proposal."""


class WakeVerifierRuntimeError(RuntimeError):
    """The attested verifier failed while loading or evaluating."""


@dataclass(frozen=True)
class WakeVerifierConfig:
    manifest_path: Path
    graph_path: Path
    graph_data_path: Path
    vocabulary_path: Path
    graph_sha256: str
    graph_data_sha256: str
    vocabulary_sha256: str
    stage1_model_sha256: str
    stage1_phrase: str
    stage1_hop_samples: int
    stage1_debounce_seconds: float
    stage1_pre_roll_seconds: float
    primary_view_start_samples: int
    activity_lookback_samples: int
    activity_alignment_samples: int
    activity_vad_threshold: float
    minimum_samples: int
    maximum_samples: int
    maximum_turn_samples: int
    broad_threshold: float
    strong_threshold: float
    decision_margin: float
    anchor_margin: float
    calibration: dict[str, Any]


@dataclass(frozen=True)
class WakeVerifierDecision:
    accepted: bool
    method: str
    margin: float | None
    stage1_eligible: bool


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_object(path: Path, maximum: int, code: str) -> dict[str, Any]:
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= maximum:
            raise WakeVerifierConfigurationError(code)
        value = json.loads(path.read_text(encoding="utf-8"))
    except WakeVerifierConfigurationError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise WakeVerifierConfigurationError(code) from error
    if not isinstance(value, dict):
        raise WakeVerifierConfigurationError(code)
    return value


def _required_string(payload: Mapping[str, Any], name: str, maximum: int = 255) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise WakeVerifierConfigurationError("wake_verifier_manifest_invalid")
    return value.strip()


def _required_number(
    payload: Mapping[str, Any], name: str, minimum: float, maximum: float
) -> float:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WakeVerifierConfigurationError("wake_verifier_manifest_invalid")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise WakeVerifierConfigurationError("wake_verifier_manifest_invalid")
    return result


def _required_integer(
    payload: Mapping[str, Any], name: str, minimum: int, maximum: int
) -> int:
    value = _required_number(payload, name, minimum, maximum)
    result = int(value)
    if result != value:
        raise WakeVerifierConfigurationError("wake_verifier_manifest_invalid")
    return result


def _adjacent_file(
    manifest_path: Path,
    name: str,
    *,
    suffix: str,
    maximum: int,
    code: str,
) -> Path:
    candidate = Path(name)
    if candidate.is_absolute() or candidate.name != name or candidate.suffix.casefold() != suffix:
        raise WakeVerifierConfigurationError(code)
    try:
        root = manifest_path.parent.resolve(strict=True)
        path = (root / candidate).resolve(strict=True)
        path.relative_to(root)
        if not path.is_file() or not 0 < path.stat().st_size <= maximum:
            raise WakeVerifierConfigurationError(code)
        return path
    except WakeVerifierConfigurationError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise WakeVerifierConfigurationError(code) from error


def _required_hash(payload: Mapping[str, Any], name: str) -> str:
    value = _required_string(payload, name, 64).casefold()
    if not _SHA256_RE.fullmatch(value):
        raise WakeVerifierConfigurationError("wake_verifier_manifest_invalid")
    return value


def _uncalibrated_allowed() -> bool:
    return (os.environ.get("BAXY_VOICE_WAKE_VERIFIER_ALLOW_UNCALIBRATED") or "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def resolve_wake_verifier_manifest() -> Path:
    configured = (os.environ.get("BAXY_VOICE_WAKE_VERIFIER_MANIFEST") or "").strip()
    if configured:
        return Path(configured).expanduser()
    try:
        resolution = resolve_asset("wake_verifier_manifest")
    except AssetDescriptorError as error:
        raise WakeVerifierConfigurationError("wake_verifier_asset_descriptor_invalid") from error
    if resolution.path is not None:
        return resolution.path
    return resolution.candidates[0] if resolution.candidates else Path()


def _validate_calibration(
    manifest_path: Path,
    calibration: Mapping[str, Any],
    identities: Mapping[str, Any],
) -> dict[str, Any]:
    if calibration.get("approved") is not True:
        raise WakeVerifierConfigurationError("wake_verifier_calibration_required")
    report_name = _required_string(calibration, "report", 128)
    if report_name != CALIBRATION_REPORT_FILENAME:
        raise WakeVerifierConfigurationError("wake_verifier_calibration_invalid")
    report_hash = _required_hash(calibration, "reportSha256")
    report_path = _adjacent_file(
        manifest_path,
        report_name,
        suffix=".json",
        maximum=_MAX_REPORT_BYTES,
        code="wake_verifier_calibration_report_invalid",
    )
    if _sha256(report_path) != report_hash:
        raise WakeVerifierConfigurationError("wake_verifier_calibration_report_hash_mismatch")
    report = _read_object(
        report_path, _MAX_REPORT_BYTES, "wake_verifier_calibration_report_invalid"
    )
    if (
        report.get("schema") != CALIBRATION_REPORT_SCHEMA
        or report.get("promotable") is not True
        or report.get("candidate_frozen") is not True
        or report.get("product_operating_point") is not True
        or report.get("blind_human_partition_accessed") is not True
    ):
        raise WakeVerifierConfigurationError("wake_verifier_calibration_report_invalid")
    report_assets = report.get("assets")
    metrics = report.get("metrics")
    if not isinstance(report_assets, dict) or not isinstance(metrics, dict):
        raise WakeVerifierConfigurationError("wake_verifier_calibration_report_invalid")
    if any(report_assets.get(name) != value for name, value in identities.items()):
        raise WakeVerifierConfigurationError("wake_verifier_calibration_mismatch")
    try:
        recall = float(metrics["human_recall"])
        false_activations = int(metrics["negative_false_activations"])
        confidence = float(metrics["far_confidence"])
        far_upper = float(metrics["far_upper_confidence_per_hour"])
    except (KeyError, TypeError, ValueError) as error:
        raise WakeVerifierConfigurationError("wake_verifier_calibration_report_invalid") from error
    if recall < 0.99 or false_activations != 0 or confidence < 0.95 or far_upper > 0.1:
        raise WakeVerifierConfigurationError("wake_verifier_calibration_mismatch")
    return dict(calibration)


def _load_wake_verifier_config(
    manifest_path: Path | None, *, require_calibration: bool
) -> WakeVerifierConfig:
    manifest = (manifest_path or resolve_wake_verifier_manifest()).expanduser()
    payload = _read_object(manifest, _MAX_MANIFEST_BYTES, "wake_verifier_manifest_missing")
    if payload.get("schema") != MANIFEST_SCHEMA or payload.get("backend") != "onnxruntime-phoneme-ctc":
        raise WakeVerifierConfigurationError("wake_verifier_manifest_invalid")
    graph_path = _adjacent_file(
        manifest,
        _required_string(payload, "graph"),
        suffix=".onnx",
        maximum=_MAX_GRAPH_BYTES,
        code="wake_verifier_graph_invalid",
    )
    graph_data_path = _adjacent_file(
        manifest,
        _required_string(payload, "graphData"),
        suffix=".data",
        maximum=_MAX_GRAPH_DATA_BYTES,
        code="wake_verifier_graph_data_invalid",
    )
    vocabulary_path = _adjacent_file(
        manifest,
        _required_string(payload, "vocabulary"),
        suffix=".json",
        maximum=_MAX_VOCAB_BYTES,
        code="wake_verifier_vocabulary_invalid",
    )
    graph_hash = _required_hash(payload, "graphSha256")
    graph_data_hash = _required_hash(payload, "graphDataSha256")
    vocabulary_hash = _required_hash(payload, "vocabularySha256")
    stage1_model_hash = _required_hash(payload, "stage1ModelSha256")
    stage1_phrase = _required_string(payload, "stage1Phrase", 80)
    stage1_hop = _required_integer(payload, "stage1HopSamples", 256, 24_000)
    stage1_debounce = _required_number(
        payload, "stage1DebounceSeconds", 0.5, 10.0
    )
    stage1_pre_roll = _required_number(
        payload, "stage1PreRollSeconds", 2.0, 10.0
    )
    pre_roll_samples = round(stage1_pre_roll * SAMPLE_RATE)
    primary_view_start = _required_integer(
        payload, "primaryViewStartSamples", 0, pre_roll_samples
    )
    activity_lookback = _required_integer(
        payload, "activityLookbackSamples", 0, SAMPLE_RATE
    )
    activity_alignment = _required_integer(
        payload, "activityAlignmentSamples", 1, 1_024
    )
    activity_vad_threshold = _required_number(
        payload, "activityVadThreshold", 0.01, 0.99
    )
    if (
        _sha256(graph_path) != graph_hash
        or _sha256(graph_data_path) != graph_data_hash
        or _sha256(vocabulary_path) != vocabulary_hash
    ):
        raise WakeVerifierConfigurationError("wake_verifier_asset_hash_mismatch")
    if int(_required_number(payload, "sampleRate", SAMPLE_RATE, SAMPLE_RATE)) != SAMPLE_RATE:
        raise WakeVerifierConfigurationError("wake_verifier_model_incompatible")
    minimum_samples = _required_integer(
        payload, "minimumSamples", SAMPLE_RATE, 48_000
    )
    maximum_samples = _required_integer(
        payload, "maximumSamples", 48_000, SAMPLE_RATE * 10
    )
    maximum_turn_samples = _required_integer(
        payload, "maximumTurnSamples", maximum_samples, SAMPLE_RATE * 30
    )
    if minimum_samples >= maximum_samples:
        raise WakeVerifierConfigurationError("wake_verifier_model_incompatible")
    broad = _required_number(payload, "broadThreshold", 0.001, 0.999)
    strong = _required_number(payload, "strongThreshold", broad, 0.999)
    decision = _required_number(payload, "decisionMargin", -20.0, 20.0)
    anchor = _required_number(payload, "anchorMargin", decision, 20.0)
    identities = {
        "graph_sha256": graph_hash,
        "graph_data_sha256": graph_data_hash,
        "vocabulary_sha256": vocabulary_hash,
        "stage1_model_sha256": stage1_model_hash,
        "stage1_phrase": stage1_phrase,
        "stage1_hop_samples": stage1_hop,
        "stage1_debounce_seconds": stage1_debounce,
        "stage1_pre_roll_seconds": stage1_pre_roll,
        "primary_view_start_samples": primary_view_start,
        "activity_lookback_samples": activity_lookback,
        "activity_alignment_samples": activity_alignment,
        "activity_vad_threshold": activity_vad_threshold,
        "sample_rate": SAMPLE_RATE,
        "minimum_samples": minimum_samples,
        "maximum_samples": maximum_samples,
        "maximum_turn_samples": maximum_turn_samples,
        "broad_threshold": broad,
        "strong_threshold": strong,
        "decision_margin": decision,
        "anchor_margin": anchor,
    }
    raw_calibration = payload.get("calibration")
    if not require_calibration:
        calibration = (
            dict(raw_calibration) if isinstance(raw_calibration, dict) else {}
        )
    elif isinstance(raw_calibration, dict) and raw_calibration.get("approved") is True:
        calibration = _validate_calibration(manifest, raw_calibration, identities)
    elif _uncalibrated_allowed():
        calibration = dict(raw_calibration) if isinstance(raw_calibration, dict) else {}
    else:
        raise WakeVerifierConfigurationError("wake_verifier_calibration_required")
    return WakeVerifierConfig(
        manifest_path=manifest.resolve(),
        graph_path=graph_path,
        graph_data_path=graph_data_path,
        vocabulary_path=vocabulary_path,
        graph_sha256=graph_hash,
        graph_data_sha256=graph_data_hash,
        vocabulary_sha256=vocabulary_hash,
        stage1_model_sha256=stage1_model_hash,
        stage1_phrase=stage1_phrase,
        stage1_hop_samples=stage1_hop,
        stage1_debounce_seconds=stage1_debounce,
        stage1_pre_roll_seconds=stage1_pre_roll,
        primary_view_start_samples=primary_view_start,
        activity_lookback_samples=activity_lookback,
        activity_alignment_samples=activity_alignment,
        activity_vad_threshold=activity_vad_threshold,
        minimum_samples=minimum_samples,
        maximum_samples=maximum_samples,
        maximum_turn_samples=maximum_turn_samples,
        broad_threshold=broad,
        strong_threshold=strong,
        decision_margin=decision,
        anchor_margin=anchor,
        calibration=calibration,
    )


def load_wake_verifier_config(
    manifest_path: Path | None = None,
) -> WakeVerifierConfig:
    """Load a verifier only after its combined product gate is attested."""

    return _load_wake_verifier_config(manifest_path, require_calibration=True)


def load_wake_verifier_candidate_config(
    manifest_path: Path | None = None,
) -> WakeVerifierConfig:
    """Validate candidate provenance without granting runtime authority."""

    return _load_wake_verifier_config(manifest_path, require_calibration=False)


def inspect_wake_verifier_config(
    manifest_path: Path | None = None,
) -> tuple[WakeVerifierConfig | None, str | None]:
    try:
        return load_wake_verifier_config(manifest_path), None
    except WakeVerifierConfigurationError as error:
        return None, str(error)


def inspect_wake_verifier_candidate_config(
    manifest_path: Path | None = None,
) -> tuple[WakeVerifierConfig | None, str | None]:
    try:
        return load_wake_verifier_candidate_config(manifest_path), None
    except WakeVerifierConfigurationError as error:
        return None, str(error)


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def lexical_words(transcript: str) -> tuple[str, ...]:
    return tuple(_fold(match.group(0)) for match in _WORD_RE.finditer(transcript))


def has_exact_lexical_target(transcript: str) -> bool:
    words = lexical_words(transcript)
    return any(word in _EXACT_LEXICAL_TARGETS for word in words) or any(
        words[index : index + len(phrase)] == phrase
        for phrase in _EXACT_LEXICAL_PHRASES
        for index in range(len(words) - len(phrase) + 1)
    )


def has_liberal_lexical_proposal(transcript: str) -> bool:
    return any(
        any(word.startswith(prefix) for prefix in _EXACT_LEXICAL_TARGETS)
        for word in lexical_words(transcript)
    )


def stage1_eligible(
    confidence: float,
    transcript: str,
    *,
    broad_threshold: float,
    strong_threshold: float,
) -> bool:
    return confidence >= broad_threshold and (
        confidence >= strong_threshold
        or has_exact_lexical_target(transcript)
        or not lexical_words(transcript)
    )


def resolve_category_ids(vocabulary: Mapping[str, int], blank_id: int) -> dict[str, tuple[int, ...]]:
    values: dict[str, tuple[int, ...]] = {"blank": (int(blank_id),)}
    used = {int(blank_id)}
    for category, tokens in CATEGORY_TOKENS.items():
        if category in {"blank", "other"}:
            continue
        if any(token not in vocabulary for token in tokens):
            raise WakeVerifierConfigurationError("wake_verifier_vocabulary_incompatible")
        ids = tuple(sorted({int(vocabulary[token]) for token in tokens}))
        if used.intersection(ids):
            raise WakeVerifierConfigurationError("wake_verifier_vocabulary_incompatible")
        values[category] = ids
        used.update(ids)
    values["other"] = tuple(
        index for index in range(max(vocabulary.values()) + 1) if index not in used
    )
    if not values["other"]:
        raise WakeVerifierConfigurationError("wake_verifier_vocabulary_incompatible")
    return values


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if values.size == 0 or not np.isfinite(values).all():
        raise WakeVerifierRuntimeError("wake_verifier_audio_invalid")
    mean = np.mean(values)
    variance = np.var(values)
    return np.ascontiguousarray(
        ((values - mean) / np.sqrt(variance + np.float32(1e-7)))[None, :],
        dtype=np.float32,
    )


def verification_audio(
    audio: np.ndarray,
    *,
    minimum_samples: int,
    maximum_samples: int,
    maximum_turn_samples: int,
    start_sample: int = 0,
) -> np.ndarray | None:
    """Keep the wake-bearing prefix while allowing a longer spoken mission."""

    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if (
        isinstance(start_sample, bool)
        or not isinstance(start_sample, int)
        or start_sample < 0
        or not np.isfinite(values).all()
    ):
        raise WakeVerifierRuntimeError("wake_verifier_audio_invalid")
    if not minimum_samples <= len(values) <= maximum_turn_samples:
        return None
    if start_sample >= len(values):
        return None
    return np.ascontiguousarray(values[start_sample:][:maximum_samples])


def verification_view_starts(
    *,
    primary_start_sample: int,
    activity_start_sample: int,
    activity_lookback_samples: int,
) -> tuple[int, ...]:
    values = (
        primary_start_sample,
        max(0, activity_start_sample - activity_lookback_samples),
        activity_start_sample,
    )
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise WakeVerifierRuntimeError("wake_verifier_audio_invalid")
    if any(value < 0 for value in values):
        raise WakeVerifierRuntimeError("wake_verifier_audio_invalid")
    return tuple(dict.fromkeys(values))


def compress_category_logits_numpy(
    logits: np.ndarray, category_ids: Mapping[str, tuple[int, ...]]
) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float32)
    if values.ndim != 3 or values.shape[0] != 1:
        raise WakeVerifierRuntimeError("wake_verifier_logits_invalid")
    reduced = np.stack(
        [values[:, :, list(category_ids[name])].max(axis=-1) for name in CATEGORY_NAMES],
        axis=-1,
    )
    reduced -= reduced.max(axis=-1, keepdims=True)
    probabilities = np.exp(reduced)
    probabilities /= probabilities.sum(axis=-1, keepdims=True)
    if not np.isfinite(probabilities).all():
        raise WakeVerifierRuntimeError("wake_verifier_logits_invalid")
    return probabilities[0]


def _collapse_path(token_ids: Sequence[int]) -> tuple[tuple[int, int, int], ...]:
    spans: list[list[int]] = []
    previous: int | None = None
    for frame, raw_token in enumerate(token_ids):
        token = int(raw_token)
        if token != previous:
            if token != BLANK_ID:
                spans.append([token, frame, frame + 1])
            previous = token
        elif token != BLANK_ID and spans and spans[-1][0] == token:
            spans[-1][2] = frame + 1
    return tuple((token, start, end) for token, start, end in spans)


def _exact_spans(
    collapsed: Sequence[tuple[int, int, int]],
) -> tuple[tuple[int, int], ...]:
    tokens = tuple(item[0] for item in collapsed)
    matches = []
    for sequence in TARGET_IDS:
        for start in range(len(tokens) - len(sequence) + 1):
            if tokens[start : start + len(sequence)] == sequence:
                matches.append((collapsed[start][1], collapsed[start + len(sequence) - 1][2]))
    return tuple(matches)


def _ctc_log_probability(
    log_probabilities: np.ndarray, sequence: Sequence[int]
) -> float:
    states: list[int] = [BLANK_ID]
    for token in sequence:
        states.extend((int(token), BLANK_ID))
    previous = np.full(len(states), -math.inf, dtype=np.float64)
    previous[0] = log_probabilities[0, BLANK_ID]
    previous[1] = log_probabilities[0, int(sequence[0])]
    for frame in range(1, len(log_probabilities)):
        current = np.full(len(states), -math.inf, dtype=np.float64)
        for state, token in enumerate(states):
            total = previous[state]
            if state > 0:
                total = float(np.logaddexp(total, previous[state - 1]))
            if state > 1 and token != BLANK_ID and token != states[state - 2]:
                total = float(np.logaddexp(total, previous[state - 2]))
            current[state] = total + log_probabilities[frame, token]
        previous = current
    return float(np.logaddexp(previous[-1], previous[-2]))


def _best_sequence_score(
    segment: np.ndarray, sequences: Sequence[Sequence[int]]
) -> float:
    return max(_ctc_log_probability(segment, sequence) for sequence in sequences)


def _margin_for_span(
    log_probabilities: np.ndarray, start: int, end: int, context: int = 10
) -> float:
    segment = log_probabilities[max(0, start - context) : min(len(log_probabilities), end + context)]
    return _best_sequence_score(segment, TARGET_IDS) - _best_sequence_score(
        segment, CONFUSABLE_IDS
    )


def _has_adjacent_confusable_prefix(
    collapsed: Sequence[tuple[int, int, int]],
    span_start: int,
    *,
    maximum_gap_frames: int = 6,
) -> bool:
    """Reject a target hallucinated immediately after its V/F/P confusable."""

    index = next(
        (
            position
            for position, (_, start, _) in enumerate(collapsed)
            if start == span_start
        ),
        None,
    )
    if index is None or index == 0:
        return False
    previous_token, _, previous_end = collapsed[index - 1]
    confusable_prefixes = {
        CATEGORY_NAMES.index("V"),
        CATEGORY_NAMES.index("F"),
        CATEGORY_NAMES.index("P"),
    }
    return (
        previous_token in confusable_prefixes
        and span_start - previous_end <= maximum_gap_frames
    )


def decide_category_probabilities(
    probabilities: np.ndarray,
    transcript: str,
    *,
    decision_margin: float,
    anchor_margin: float,
) -> WakeVerifierDecision:
    values = np.asarray(probabilities, dtype=np.float64)
    if (
        values.ndim != 2
        or values.shape[1] != len(CATEGORY_NAMES)
        or values.shape[0] == 0
        or not np.isfinite(values).all()
        or not np.allclose(values.sum(axis=1), 1.0, atol=2e-5)
    ):
        raise WakeVerifierRuntimeError("wake_verifier_probabilities_invalid")
    log_probabilities = np.log(np.maximum(values, 1e-12))
    collapsed = _collapse_path(np.argmax(values, axis=1))
    lexical_target = has_exact_lexical_target(transcript)
    exact_spans = _exact_spans(collapsed)
    if not lexical_target:
        exact_spans = tuple(
            (start, end)
            for start, end in exact_spans
            if not _has_adjacent_confusable_prefix(collapsed, start)
        )
    exact = [
        _margin_for_span(log_probabilities, start, end)
        for start, end in exact_spans
    ]
    if exact:
        margin = max(exact)
        if margin >= decision_margin:
            return WakeVerifierDecision(True, "ctc_exact", margin, True)
    if not lexical_target:
        return WakeVerifierDecision(False, "rejected", max(exact) if exact else None, True)
    initials = {sequence[0] for sequence in TARGET_IDS}
    endings = {sequence[-1] for sequence in TARGET_IDS}
    anchors = []
    for index, (token, start, _) in enumerate(collapsed):
        if token not in initials:
            continue
        for ending, _, end in collapsed[index + 1 :]:
            span = end - start
            if span > 40:
                break
            if ending in endings and span >= 8:
                anchors.append(_margin_for_span(log_probabilities, start, end))
    margin = max(anchors) if anchors else None
    return WakeVerifierDecision(
        margin is not None and margin >= anchor_margin,
        "ctc_lexical_anchor" if margin is not None else "rejected",
        margin,
        True,
    )


class OnnxWakeVerifier:
    """One warm CPU session; every result is derived from a complete VAD turn."""

    def __init__(self, config: WakeVerifierConfig, session: Any | None = None) -> None:
        self.config = config
        vocabulary_payload = _read_object(
            config.vocabulary_path, _MAX_VOCAB_BYTES, "wake_verifier_vocabulary_invalid"
        )
        if not all(isinstance(key, str) and isinstance(value, int) for key, value in vocabulary_payload.items()):
            raise WakeVerifierConfigurationError("wake_verifier_vocabulary_invalid")
        self._category_ids = resolve_category_ids(vocabulary_payload, 0)
        if session is None:
            try:
                import onnxruntime as ort

                options = cpu_session_options(
                    ort,
                    environment_name="BAXY_VOICE_WAKE_THREADS",
                )
                session = ort.InferenceSession(
                    str(config.graph_path),
                    sess_options=options,
                    providers=["CPUExecutionProvider"],
                )
            except ModuleNotFoundError as error:
                raise WakeVerifierRuntimeError("wake_verifier_runtime_missing") from error
            except Exception as error:  # noqa: BLE001
                raise WakeVerifierRuntimeError(
                    f"wake_verifier_runtime_load_failed:{type(error).__name__}"
                ) from error
        self._session = session

    def verify(
        self,
        audio: np.ndarray,
        transcript: str,
        stage1_confidence: float,
        *,
        verification_start_sample: int = 0,
    ) -> WakeVerifierDecision:
        if not math.isfinite(stage1_confidence):
            raise WakeVerifierRuntimeError("wake_verifier_confidence_invalid")
        eligible = stage1_eligible(
            stage1_confidence,
            transcript,
            broad_threshold=self.config.broad_threshold,
            strong_threshold=self.config.strong_threshold,
        )
        if not eligible:
            return WakeVerifierDecision(False, "stage1_rejected", None, False)
        starts = verification_view_starts(
            primary_start_sample=self.config.primary_view_start_samples,
            activity_start_sample=verification_start_sample,
            activity_lookback_samples=self.config.activity_lookback_samples,
        )
        rejected_margins: list[float] = []
        evaluated = False
        try:
            for start in starts:
                values = verification_audio(
                    audio,
                    minimum_samples=self.config.minimum_samples,
                    maximum_samples=self.config.maximum_samples,
                    maximum_turn_samples=self.config.maximum_turn_samples,
                    start_sample=start,
                )
                if values is None:
                    continue
                evaluated = True
                if len(values) < self.config.maximum_samples:
                    values = np.pad(
                        values,
                        (0, self.config.maximum_samples - len(values)),
                        mode="constant",
                    )
                logits = self._session.run(
                    ["logits"], {"input_values": normalize_audio(values)}
                )[0]
                probabilities = compress_category_logits_numpy(
                    logits, self._category_ids
                )
                decision = decide_category_probabilities(
                    probabilities,
                    transcript,
                    decision_margin=self.config.decision_margin,
                    anchor_margin=self.config.anchor_margin,
                )
                if decision.accepted:
                    return decision
                if decision.margin is not None:
                    rejected_margins.append(decision.margin)
            if not evaluated:
                return WakeVerifierDecision(
                    False, "turn_length_rejected", None, True
                )
            return WakeVerifierDecision(
                False,
                "rejected",
                max(rejected_margins) if rejected_margins else None,
                True,
            )
        except WakeVerifierRuntimeError:
            raise
        except Exception as error:  # noqa: BLE001
            raise WakeVerifierRuntimeError(
                f"wake_verifier_runtime_predict_failed:{type(error).__name__}"
            ) from error


__all__ = [
    "CALIBRATION_REPORT_FILENAME",
    "CALIBRATION_REPORT_SCHEMA",
    "CATEGORY_NAMES",
    "MANIFEST_SCHEMA",
    "OnnxWakeVerifier",
    "SAMPLE_RATE",
    "WakeVerifierConfig",
    "WakeVerifierConfigurationError",
    "WakeVerifierDecision",
    "WakeVerifierRuntimeError",
    "decide_category_probabilities",
    "has_exact_lexical_target",
    "has_liberal_lexical_proposal",
    "inspect_wake_verifier_candidate_config",
    "inspect_wake_verifier_config",
    "load_wake_verifier_candidate_config",
    "load_wake_verifier_config",
    "normalize_audio",
    "stage1_eligible",
    "verification_audio",
    "verification_view_starts",
]
