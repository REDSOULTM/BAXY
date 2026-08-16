"""Train and evaluate a text-free, development-only E5 turn policy.

This tool is deliberately outside the BAXY runtime.  It consumes only explicit
train/validation JSONL inputs, keeps multilingual paraphrases mission-disjoint,
fits linear heads on individual frozen multilingual-E5-small embeddings with
one weighted vote per mission, calibrates worst-utterance split-conformal
abstention by mission, and evaluates the runtime unit: one utterance.

It never reads a sealed/final/test/v4 source, never writes utterance text to a
cache or artifact, and never grants execution authority.  MTOP candidate
operations remain advisory retrieval labels which must still pass the normal
LLM selection, schema grounding, risk, confirmation, and core verification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


RUNTIME_ROW_SCHEMA = "baxy.turn-evidence-record.v1"
MTOP_ROW_SCHEMA = "baxy.mtop-development-row.v1"
MTOP_MAP_SCHEMA = "baxy.mtop-source-map.v1"
CACHE_SCHEMA = "baxy.turn-policy-e5-embedding-cache.v1"
ARTIFACT_SCHEMA = "baxy.turn-policy-e5-development.v2"

# The policy is hierarchical.  The first head asks only whether a supported
# BAXY effect exists.  A second head distinguishes genuine conversation from an
# unsupported/OOD request when no supported effect is present.  Collapsing
# those two outcomes would let an OOD command authorize the fast chat path.
TRIGGER_NEGATIVE = "no_effect"
TRIGGER_POSITIVE = "supported_effect"
TRIGGER_CLASSES = (TRIGGER_NEGATIVE, TRIGGER_POSITIVE)
OUTCOME_CONVERSATION = "conversation_no_effect"
OUTCOME_UNSUPPORTED = "unsupported_ood"
OUTCOME_SUPPORTED = TRIGGER_POSITIVE
NO_EFFECT_CLASSES = (OUTCOME_CONVERSATION, OUTCOME_UNSUPPORTED)
OUTCOME_CLASSES = (
    OUTCOME_CONVERSATION,
    OUTCOME_UNSUPPORTED,
    OUTCOME_SUPPORTED,
)

# Cache v1 included the old conflated trigger label in its row fingerprint.
# Embeddings do not depend on that label, so the v2 trainer preserves this
# wire identity while binding the new disposition to the pinned source/map
# hashes and to the artifact's group fingerprints.
_CACHE_V1_NEGATIVE_TRIGGER = "conversation_ood"

_ALLOWED_SPLITS = frozenset({"train", "validation"})
_ACTION_MODES = frozenset({"action", "plan"})
_CONVERSATION_MODES = frozenset({"conversation"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OPERATION = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+$")
_FAMILY = re.compile(r"^[a-z][a-z0-9_]*$")
_MTOP_INTENT = re.compile(r"^IN:[A-Z][A-Z0-9_]*$")
_SAFE_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_FORBIDDEN_INPUT_TOKENS = frozenset(
    {"test", "seal", "sealed", "reserve", "final", "v4"}
)
_MAX_INPUT_BYTES = 512 * 1024 * 1024
_MAX_ROWS = 500_000
_MAX_TEXT_CHARS = 4_096


@dataclass(frozen=True, slots=True)
class DevelopmentExample:
    dataset: str
    split: str
    mission_id: str
    source_id: str
    text: str
    trigger: str
    no_effect_disposition: str | None
    families: tuple[str, ...]
    operations: tuple[str, ...]
    locale: str

    @property
    def text_sha256(self) -> str:
        return hashlib.sha256(_normalized_text(self.text).encode("utf-8")).hexdigest()

    @property
    def target_signature(
        self,
    ) -> tuple[str, str | None, tuple[str, ...], tuple[str, ...]]:
        return (
            self.trigger,
            self.no_effect_disposition,
            self.families,
            self.operations,
        )


@dataclass(frozen=True, slots=True)
class LoadResult:
    examples: tuple[DevelopmentExample, ...]
    exclusions: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class MtopIntentPolicy:
    source_sha256: str
    dispositions: Mapping[str, str]
    operation_options: Mapping[str, tuple[tuple[str, ...], ...]]
    ood_intents: frozenset[str]


@dataclass(frozen=True, slots=True)
class GroupExample:
    mission_id: str
    split: str
    trigger: str
    no_effect_disposition: str | None
    families: tuple[str, ...]
    operations: tuple[str, ...]
    datasets: tuple[str, ...]
    vector: np.ndarray
    member_vectors: tuple[np.ndarray, ...]
    member_locales: tuple[str, ...]

    @property
    def outcome(self) -> str:
        if self.trigger == TRIGGER_POSITIVE and self.no_effect_disposition is None:
            return OUTCOME_SUPPORTED
        if (
            self.trigger == TRIGGER_NEGATIVE
            and self.no_effect_disposition in NO_EFFECT_CLASSES
        ):
            return str(self.no_effect_disposition)
        raise ValueError("mission group has an invalid hierarchical target")


@dataclass(frozen=True, slots=True)
class LinearHead:
    kind: str
    classes: tuple[str, ...]
    coefficients: np.ndarray
    intercepts: np.ndarray

    def __post_init__(self) -> None:
        coefficients = np.asarray(self.coefficients)
        intercepts = np.asarray(self.intercepts)
        if (
            self.kind not in {"softmax", "one_vs_rest"}
            or not self.classes
            or len(set(self.classes)) != len(self.classes)
            or coefficients.ndim != 2
            or coefficients.shape[0] != len(self.classes)
            or intercepts.shape != (len(self.classes),)
            or not np.isfinite(coefficients).all()
            or not np.isfinite(intercepts).all()
        ):
            raise ValueError("invalid linear head")

    @property
    def dimensions(self) -> int:
        return int(self.coefficients.shape[1])

    def probabilities(self, vectors: np.ndarray) -> np.ndarray:
        matrix = _finite_matrix(vectors, dimensions=self.dimensions)
        logits = matrix @ self.coefficients.T + self.intercepts
        if self.kind == "softmax":
            logits = logits - logits.max(axis=1, keepdims=True)
            exponentials = np.exp(logits)
            return exponentials / exponentials.sum(axis=1, keepdims=True)
        return 1.0 / (1.0 + np.exp(-np.clip(logits, -60.0, 60.0)))

    def safe_dict(self) -> dict[str, Any]:
        body = {
            "kind": self.kind,
            "classes": list(self.classes),
            "dimensions": self.dimensions,
            "coefficients": self.coefficients.astype(np.float64).tolist(),
            "intercepts": self.intercepts.astype(np.float64).tolist(),
        }
        return {
            **body,
            "weights_sha256": _sha256_bytes(_canonical_json_bytes(body)),
        }


def _canonical_json_bytes(value: object, *, pretty: bool = False) -> bytes:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return (payload + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_atomic(path: Path, value: object) -> None:
    _write_bytes_atomic(path, _canonical_json_bytes(value, pretty=True))


def _normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _bounded_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("example text is not a string")
    text = " ".join(unicodedata.normalize("NFC", value).split())
    if (
        not text
        or len(text) > _MAX_TEXT_CHARS
        or any(unicodedata.category(character) in {"Cc", "Cs"} for character in text)
    ):
        raise ValueError("example text is empty, oversized, or contains controls")
    return text


def _safe_identity(value: object, field: str, maximum: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(unicodedata.category(character) in {"Cc", "Cs"} for character in value)
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _string_tuple(
    value: object,
    field: str,
    pattern: re.Pattern[str],
) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or len(value) > 256
        or any(not isinstance(item, str) or pattern.fullmatch(item) is None for item in value)
    ):
        raise ValueError(f"{field} is invalid")
    result = tuple(sorted(set(value)))
    if len(result) != len(value):
        raise ValueError(f"{field} contains duplicates or is not canonical")
    return result


def _assert_development_input_path(path: Path) -> None:
    """Reject forbidden sources before stat/open can touch their contents."""

    parts = tuple(part.casefold() for part in path.parts)
    tokens = {
        token
        for part in parts
        for token in re.split(r"[^a-z0-9]+", part)
        if token
    }
    basename_tokens = {
        token
        for token in re.split(r"[^a-z0-9]+", path.name.casefold())
        if token
    }
    # The repository's official held-out material lives below tests/data.
    # Synthetic unit fixtures below tests/fixtures remain admissible.
    official_test_directory = any(
        left == "tests" and right == "data"
        for left, right in zip(parts, parts[1:])
    )
    forbidden_ancestor_tokens = _FORBIDDEN_INPUT_TOKENS - {"test"}
    exact_test_directory = "test" in parts
    if (
        basename_tokens & _FORBIDDEN_INPUT_TOKENS
        or "tests" in basename_tokens
        or tokens & forbidden_ancestor_tokens
        or exact_test_directory
    ):
        raise ValueError("sealed, final, test, reserve, and v4 inputs are forbidden")
    if official_test_directory:
        raise ValueError("official tests/data inputs are forbidden")


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    _assert_development_input_path(path)
    resolved = path.resolve(strict=True)
    _assert_development_input_path(resolved)
    if not resolved.is_file() or resolved.stat().st_size > _MAX_INPUT_BYTES:
        raise ValueError("development input is not a bounded regular file")
    count = 0
    with resolved.open("r", encoding="utf-8", newline="") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            count += 1
            if count > _MAX_ROWS:
                raise ValueError("development input has too many rows")
            try:
                value = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL at line {line_number}") from error
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row {line_number} is not an object")
            yield value


def load_mtop_intent_policy(
    path: Path,
    allowed_operations: frozenset[str],
) -> MtopIntentPolicy:
    """Load the reviewed MTOP intent partition without importing its builder."""

    _assert_development_input_path(path)
    resolved = path.resolve(strict=True)
    _assert_development_input_path(resolved)
    source_sha256 = _sha256_file(resolved)
    try:
        mapping = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("MTOP projection map is unreadable") from error
    if (
        not isinstance(mapping, dict)
        or mapping.get("schema") != MTOP_MAP_SCHEMA
        or not allowed_operations
    ):
        raise ValueError("MTOP projection map identity is invalid")
    policy = mapping.get("policy")
    intents = mapping.get("intents")
    raw_ood = mapping.get("ood_intents")
    if (
        not isinstance(policy, dict)
        or policy.get("candidate_is_advisory_only") is not True
        or policy.get("execution_authority") is not False
        or policy.get("require_independent_llm_selection") is not True
        or policy.get("require_contract_grounding_and_verification") is not True
        or policy.get("development_must_explicitly_classify_every_observed_intent")
        is not True
        or not isinstance(intents, dict)
        or not isinstance(raw_ood, list)
    ):
        raise ValueError("MTOP projection policy is not development-safe")
    ood_intents = _string_tuple(raw_ood, "MTOP ood_intents", _MTOP_INTENT)
    dispositions: dict[str, str] = {}
    operation_options: dict[str, tuple[tuple[str, ...], ...]] = {}
    for intent, entry in sorted(intents.items()):
        if (
            not isinstance(intent, str)
            or _MTOP_INTENT.fullmatch(intent) is None
            or not isinstance(entry, dict)
        ):
            raise ValueError("MTOP supported intent entry is invalid")
        disposition = entry.get("disposition")
        variants = entry.get("variants")
        if disposition not in {"candidate", "conversation"} or not isinstance(
            variants, list
        ) or not variants:
            raise ValueError("MTOP supported intent policy is invalid")
        options: set[tuple[str, ...]] = set()
        variant_ids: set[str] = set()
        for variant in variants:
            if not isinstance(variant, dict):
                raise ValueError("MTOP intent variant is invalid")
            variant_id = variant.get("id")
            if (
                not isinstance(variant_id, str)
                or _SAFE_NAME.fullmatch(variant_id) is None
                or variant_id in variant_ids
            ):
                raise ValueError("MTOP intent variant id is invalid")
            variant_ids.add(variant_id)
            operations = _string_tuple(
                variant.get("operations"),
                "MTOP intent variant operations",
                _OPERATION,
            )
            if set(operations) - allowed_operations:
                raise ValueError("MTOP intent map expands the public BAXY catalog")
            if (disposition == "candidate") != bool(operations):
                raise ValueError("MTOP intent disposition/operations disagree")
            options.add(operations)
        dispositions[intent] = str(disposition)
        operation_options[intent] = tuple(sorted(options))
    if set(dispositions) & set(ood_intents):
        raise ValueError("MTOP supported/OOD intent partitions overlap")
    if _sha256_file(resolved) != source_sha256:
        raise ValueError("MTOP projection map changed while it was loaded")
    return MtopIntentPolicy(
        source_sha256=source_sha256,
        dispositions=dict(sorted(dispositions.items())),
        operation_options=dict(sorted(operation_options.items())),
        ood_intents=frozenset(ood_intents),
    )


def load_runtime_development(path: Path, expected_split: str) -> LoadResult:
    """Load one public runtime split without consulting a combined holdout."""

    if expected_split not in _ALLOWED_SPLITS:
        raise ValueError("runtime split must be train or validation")
    examples: list[DevelopmentExample] = []
    exclusions: Counter[str] = Counter()
    for row in _iter_jsonl(path):
        if row.get("schema") != RUNTIME_ROW_SCHEMA:
            raise ValueError("runtime row schema is not supported")
        split = row.get("split")
        if split != expected_split:
            raise ValueError("runtime input contains a split outside its declared file")
        mode = row.get("mode")
        if mode == "clarify":
            # Clarify can mean a supported effect missing one human value. It
            # is not a sound negative label for the supported-effect trigger.
            exclusions["runtime_clarify_without_effect_target"] += 1
            continue
        if mode not in _ACTION_MODES | _CONVERSATION_MODES:
            raise ValueError("runtime mode is not eligible for this policy")
        families = _string_tuple(row.get("families"), "runtime families", _FAMILY)
        trigger = TRIGGER_POSITIVE if mode in _ACTION_MODES else TRIGGER_NEGATIVE
        if (trigger == TRIGGER_POSITIVE) != bool(families):
            raise ValueError("runtime effect/family target is inconsistent")
        no_effect_disposition = (
            OUTCOME_CONVERSATION if trigger == TRIGGER_NEGATIVE else None
        )
        provenance = row.get("provenance")
        locale = ""
        if isinstance(provenance, dict) and provenance.get("locale") in {"en", "es"}:
            locale = str(provenance["locale"])
        examples.append(
            DevelopmentExample(
                dataset="runtime_public",
                split=expected_split,
                mission_id=_safe_identity(row.get("mission_id"), "mission_id"),
                source_id=_safe_identity(row.get("source_id"), "source_id"),
                text=_bounded_text(row.get("text")),
                trigger=trigger,
                no_effect_disposition=no_effect_disposition,
                families=families,
                operations=(),
                locale=locale,
            )
        )
    if not examples:
        raise ValueError("runtime development input has no eligible rows")
    return LoadResult(tuple(examples), dict(sorted(exclusions.items())))


def load_mtop_development(
    path: Path,
    allowed_operations: frozenset[str],
    intent_policy: MtopIntentPolicy,
) -> LoadResult:
    """Load MTOP train/validation while excluding ambiguous slot mismatches."""

    if not allowed_operations or any(
        _OPERATION.fullmatch(operation) is None for operation in allowed_operations
    ):
        raise ValueError("allowed operation catalog is invalid")
    examples: list[DevelopmentExample] = []
    exclusions: Counter[str] = Counter()
    for row in _iter_jsonl(path):
        if row.get("schema") != MTOP_ROW_SCHEMA:
            raise ValueError("MTOP row schema is not supported")
        split = row.get("split")
        if split not in _ALLOWED_SPLITS:
            raise ValueError("MTOP development contains a forbidden split")
        locale = row.get("locale")
        if locale not in {"en", "es"}:
            raise ValueError("MTOP locale is not EN/ES")
        projection = row.get("projection")
        if not isinstance(projection, dict) or projection.get("execution_authority") is not False:
            raise ValueError("MTOP projection could grant execution authority")
        semantic = row.get("semantic")
        intent = semantic.get("intent") if isinstance(semantic, dict) else None
        if not isinstance(intent, str) or _MTOP_INTENT.fullmatch(intent) is None:
            raise ValueError("MTOP semantic intent is invalid")
        disposition = projection.get("disposition")
        reason = projection.get("reason")
        operations = _string_tuple(
            projection.get("candidate_operations"),
            "MTOP candidate_operations",
            _OPERATION,
        )
        families = _string_tuple(projection.get("families"), "MTOP families", _FAMILY)
        if set(operations) - allowed_operations:
            raise ValueError("MTOP projection expands the public BAXY catalog")
        if families != tuple(sorted({item.split(".", 1)[0] for item in operations})):
            raise ValueError("MTOP operation and family projections disagree")

        reviewed_disposition = intent_policy.dispositions.get(intent)
        reviewed_options = intent_policy.operation_options.get(intent, ())
        if reason in {
            "contract_structure_mismatch",
            "contract_ambiguous_missing_information",
        }:
            if reviewed_disposition is None:
                raise ValueError("an unreviewed MTOP intent has an ambiguous projection")
            # The current upstream projection conflates at least two meanings:
            # missing required slots (usually a supported effect that should
            # clarify later) and extra/nested structure (OOD). Training either
            # label would add systematic noise, so these rows are excluded
            # until the adapter emits a decomposed reason.
            exclusion = (
                "mtop_contract_structure_mismatch_ambiguous"
                if reason == "contract_structure_mismatch"
                else "mtop_contract_ambiguous_missing_information"
            )
            exclusions[exclusion] += 1
            continue
        if disposition == "candidate":
            if (
                reason != "contract_covered_structure"
                or reviewed_disposition != "candidate"
                or operations not in reviewed_options
                or projection.get("grounding_status") != "complete"
                or projection.get("expected_turn")
                != ("plan" if len(operations) > 1 else "action")
            ):
                raise ValueError("MTOP candidate lacks reviewed contract coverage")
            trigger = TRIGGER_POSITIVE
            no_effect_disposition = None
        elif disposition == "candidate_missing_information":
            missing_required = projection.get("missing_required_slots")
            missing_any = projection.get("missing_any_slot_groups")
            if (
                reason != "contract_supported_missing_information"
                or reviewed_disposition != "candidate"
                or operations not in reviewed_options
                or projection.get("grounding_status")
                != "missing_required_information"
                or projection.get("expected_turn") != "clarify"
                or projection.get("turn_label_source")
                != "baxy_contract_projection"
                or not (
                    isinstance(missing_required, list)
                    and isinstance(missing_any, list)
                    and (missing_required or missing_any)
                )
            ):
                raise ValueError(
                    "MTOP missing-information candidate is not a corrected projection"
                )
            # It is evidence of a supported effect, not OOD. The operation is
            # still advisory; grounding must ask for the missing human value.
            trigger = TRIGGER_POSITIVE
            no_effect_disposition = None
        elif disposition == "conversation_no_effect":
            if (
                reason != "contract_covered_structure"
                or reviewed_disposition != "conversation"
                or operations
                or families
                or projection.get("grounding_status") != "complete"
                or projection.get("expected_turn") != "conversation"
            ):
                raise ValueError("MTOP conversation projection is inconsistent")
            trigger = TRIGGER_NEGATIVE
            no_effect_disposition = OUTCOME_CONVERSATION
        elif disposition == "ood_no_effect":
            if (
                reason != "mapped_unsupported_intent"
                or intent not in intent_policy.ood_intents
                or reviewed_disposition is not None
                or operations
                or families
                or projection.get("grounding_status") != "not_applicable"
                or projection.get("expected_turn") != "conversation"
            ):
                raise ValueError("MTOP OOD projection is not explicitly reviewed")
            trigger = TRIGGER_NEGATIVE
            no_effect_disposition = OUTCOME_UNSUPPORTED
        else:
            raise ValueError("MTOP disposition is not eligible for development")
        examples.append(
            DevelopmentExample(
                dataset="mtop_official",
                split=str(split),
                mission_id=_safe_identity(row.get("mission_id"), "mission_id"),
                source_id=_safe_identity(row.get("source_id"), "source_id"),
                text=_bounded_text(row.get("text")),
                trigger=trigger,
                no_effect_disposition=no_effect_disposition,
                families=families,
                operations=operations,
                locale=str(locale),
            )
        )
    if not examples:
        raise ValueError("MTOP development input has no eligible rows")
    return LoadResult(tuple(examples), dict(sorted(exclusions.items())))


def validate_development_examples(
    examples: Sequence[DevelopmentExample],
    *,
    allowed_families: frozenset[str],
) -> None:
    """Enforce mission grouping and exact-text decontamination across splits."""

    if not examples:
        raise ValueError("development examples are empty")
    source_ids: set[str] = set()
    mission_splits: dict[str, set[str]] = defaultdict(set)
    mission_targets: dict[
        str,
        set[tuple[str, str | None, tuple[str, ...], tuple[str, ...]]],
    ] = defaultdict(set)
    text_splits: dict[str, set[str]] = defaultdict(set)
    for example in examples:
        if example.source_id in source_ids:
            raise ValueError("development source_id is duplicated")
        source_ids.add(example.source_id)
        if example.split not in _ALLOWED_SPLITS:
            raise ValueError("development split is forbidden")
        if set(example.families) - allowed_families:
            raise ValueError("development family expands the public catalog")
        if (
            example.trigger == TRIGGER_POSITIVE
            and example.no_effect_disposition is not None
        ) or (
            example.trigger == TRIGGER_NEGATIVE
            and example.no_effect_disposition not in NO_EFFECT_CLASSES
        ):
            raise ValueError("development hierarchical target is inconsistent")
        mission_splits[example.mission_id].add(example.split)
        mission_targets[example.mission_id].add(example.target_signature)
        text_splits[example.text_sha256].add(example.split)
    if any(len(splits) != 1 for splits in mission_splits.values()):
        raise ValueError("mission_id crosses train and validation")
    if any(len(targets) != 1 for targets in mission_targets.values()):
        raise ValueError("translations/paraphrases in one mission disagree on target")
    if any(len(splits) != 1 for splits in text_splits.values()):
        raise ValueError("normalized text crosses train and validation")


def decontaminate_cross_source_development(
    sources: Mapping[str, LoadResult],
) -> dict[str, LoadResult]:
    """Protect validation when authentic datasets repeat exact wording.

    A matching train mission is removed as a whole, including its translated
    variants. If the same wording has incompatible targets, every involved
    mission is quarantined. Source files remain immutable and every exclusion
    is counted in the aggregate artifact.
    """

    if not sources:
        raise ValueError("development sources are empty")
    entries = [
        (source_name, example)
        for source_name, result in sources.items()
        for example in result.examples
    ]
    mission_splits: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_text: dict[
        str,
        list[tuple[str, DevelopmentExample]],
    ] = defaultdict(list)
    for source_name, example in entries:
        mission_key = (example.dataset, example.mission_id)
        mission_splits[mission_key].add(example.split)
        by_text[example.text_sha256].append((source_name, example))
    if any(len(splits) != 1 for splits in mission_splits.values()):
        raise ValueError("mission_id crosses train and validation")

    removed: dict[
        tuple[str, str],
        str,
    ] = {}
    for variants in by_text.values():
        splits = {example.split for _, example in variants}
        if len(splits) <= 1:
            continue
        signatures = {
            example.target_signature for _, example in variants
        }
        if len(signatures) > 1:
            for _, example in variants:
                removed[(example.dataset, example.mission_id)] = (
                    "cross_split_conflicting_exact_text"
                )
            continue
        for _, example in variants:
            if example.split == "train":
                removed[(example.dataset, example.mission_id)] = (
                    "cross_split_exact_text_train"
                )

    filtered: dict[str, LoadResult] = {}
    for source_name, result in sources.items():
        exclusions = Counter(result.exclusions)
        kept: list[DevelopmentExample] = []
        removed_missions: set[tuple[str, str]] = set()
        for example in result.examples:
            mission_key = (example.dataset, example.mission_id)
            reason = removed.get(mission_key)
            if reason is None:
                kept.append(example)
                continue
            exclusions[f"{reason}_rows_removed"] += 1
            removed_missions.add(mission_key)
        for mission_key in removed_missions:
            reason = removed[mission_key]
            exclusions[f"{reason}_missions_removed"] += 1
        if not kept:
            raise ValueError(
                f"cross-source decontamination emptied {source_name}"
            )
        filtered[source_name] = LoadResult(
            tuple(kept),
            dict(sorted(exclusions.items())),
        )
    return filtered


def examples_fingerprint(examples: Sequence[DevelopmentExample]) -> str:
    """Bind v1 embedding-row identity without serializing utterance text.

    The v2 hierarchical disposition is intentionally absent because it cannot
    alter an embedding.  It is instead bound by the pinned source/projection-map
    hashes and by the v2 group fingerprints in the resulting artifact.
    """

    rows = [
        {
            "dataset": example.dataset,
            "split": example.split,
            "mission_id_sha256": _sha256_bytes(example.mission_id.encode("utf-8")),
            "source_id_sha256": _sha256_bytes(example.source_id.encode("utf-8")),
            "text_sha256": example.text_sha256,
            # Preserve the content-addressed v1 embedding cache.  The new
            # no-effect disposition is a training label, not an encoder input.
            "trigger": (
                _CACHE_V1_NEGATIVE_TRIGGER
                if example.trigger == TRIGGER_NEGATIVE
                else example.trigger
            ),
            "families": list(example.families),
            "operations": list(example.operations),
            "locale": example.locale,
        }
        for example in sorted(
            examples,
            key=lambda item: (item.split, item.mission_id, item.source_id),
        )
    ]
    return _sha256_bytes(_canonical_json_bytes(rows))


def _finite_matrix(value: np.ndarray, *, dimensions: int | None = None) -> np.ndarray:
    matrix = np.asarray(value, dtype=np.float64)
    if (
        matrix.ndim != 2
        or matrix.shape[0] < 1
        or matrix.shape[1] < 1
        or (dimensions is not None and matrix.shape[1] != dimensions)
        or not np.isfinite(matrix).all()
    ):
        raise ValueError("embedding matrix is invalid")
    return matrix


def _cache_key(
    dataset_name: str,
    source_sha256: str,
    row_fingerprint: str,
    encoder_identity: Mapping[str, Any],
) -> str:
    if (
        _SAFE_NAME.fullmatch(dataset_name) is None
        or _SHA256.fullmatch(source_sha256) is None
        or _SHA256.fullmatch(row_fingerprint) is None
    ):
        raise ValueError("cache identity is invalid")
    return _sha256_bytes(
        _canonical_json_bytes(
            {
                "dataset": dataset_name,
                "source_sha256": source_sha256,
                "row_fingerprint": row_fingerprint,
                "encoder": encoder_identity,
            }
        )
    )


def write_embedding_cache_atomic(
    cache_directory: Path,
    *,
    dataset_name: str,
    source_sha256: str,
    examples: Sequence[DevelopmentExample],
    encoder_identity: Mapping[str, Any],
    vectors: np.ndarray,
) -> Path:
    """Write a content-addressed vector cache whose manifest contains no text."""

    matrix = _finite_matrix(vectors)
    if matrix.shape[0] != len(examples):
        raise ValueError("cache vector/example count differs")
    row_fingerprint = examples_fingerprint(examples)
    key = _cache_key(
        dataset_name,
        source_sha256,
        row_fingerprint,
        encoder_identity,
    )
    cache_directory.mkdir(parents=True, exist_ok=True)
    array_path = cache_directory / f"{dataset_name}-{key}.npz"
    manifest_path = cache_directory / f"{dataset_name}-{key}.json"
    temporary = array_path.with_name(f".{array_path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as handle:
            np.savez_compressed(handle, vectors=matrix.astype(np.float32))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, array_path)
    finally:
        temporary.unlink(missing_ok=True)
    manifest = {
        "schema": CACHE_SCHEMA,
        "dataset": dataset_name,
        "key": key,
        "contains_text": False,
        "contains_source_ids": False,
        "contains_mission_ids": False,
        "contains_derived_embeddings": True,
        "privacy_class": "sensitive_derived_embeddings",
        "source_sha256": source_sha256,
        "row_fingerprint_sha256": row_fingerprint,
        "rows": len(examples),
        "dimensions": int(matrix.shape[1]),
        "dtype": "float32",
        "encoder": dict(encoder_identity),
        "array": {
            "file_name": array_path.name,
            "sha256": _sha256_file(array_path),
        },
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest_path


def load_embedding_cache(
    manifest_path: Path,
    *,
    dataset_name: str,
    source_sha256: str,
    examples: Sequence[DevelopmentExample],
    encoder_identity: Mapping[str, Any],
) -> np.ndarray:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("embedding cache manifest is unreadable") from error
    row_fingerprint = examples_fingerprint(examples)
    expected_key = _cache_key(
        dataset_name,
        source_sha256,
        row_fingerprint,
        encoder_identity,
    )
    array = manifest.get("array") if isinstance(manifest, dict) else None
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != CACHE_SCHEMA
        or manifest.get("dataset") != dataset_name
        or manifest.get("key") != expected_key
        or manifest.get("contains_text") is not False
        or manifest.get("contains_source_ids") is not False
        or manifest.get("contains_mission_ids") is not False
        or manifest.get("contains_derived_embeddings") is not True
        or manifest.get("privacy_class") != "sensitive_derived_embeddings"
        or manifest.get("source_sha256") != source_sha256
        or manifest.get("row_fingerprint_sha256") != row_fingerprint
        or manifest.get("rows") != len(examples)
        or manifest.get("dtype") != "float32"
        or manifest.get("encoder") != dict(encoder_identity)
        or not isinstance(array, dict)
        or not isinstance(array.get("file_name"), str)
        or not isinstance(array.get("sha256"), str)
    ):
        raise ValueError("embedding cache identity is invalid")
    expected_array_name = f"{dataset_name}-{expected_key}.npz"
    if (
        array["file_name"] != expected_array_name
        or Path(str(array["file_name"])).name != array["file_name"]
        or _SHA256.fullmatch(str(array["sha256"])) is None
    ):
        raise ValueError("embedding cache array reference is invalid")
    array_path = manifest_path.parent / expected_array_name
    if _sha256_file(array_path) != array["sha256"]:
        raise ValueError("embedding cache array hash differs")
    try:
        with np.load(array_path, allow_pickle=False) as bundle:
            if set(bundle.files) != {"vectors"}:
                raise ValueError("embedding cache contains unexpected arrays")
            vectors = np.asarray(bundle["vectors"])
    except (OSError, ValueError) as error:
        raise ValueError("embedding cache array is invalid") from error
    if _sha256_file(array_path) != array["sha256"]:
        raise ValueError("embedding cache array changed while it was loaded")
    dimensions = manifest.get("dimensions")
    if not isinstance(dimensions, int):
        raise ValueError("embedding cache dimensions are invalid")
    matrix = _finite_matrix(vectors, dimensions=dimensions)
    if matrix.shape[0] != len(examples) or vectors.dtype != np.float32:
        raise ValueError("embedding cache shape or dtype differs")
    return vectors


def _public_catalog_operations(catalog_path: Path) -> frozenset[str]:
    text = catalog_path.read_text(encoding="utf-8")
    blocks = re.finditer(
        r'Descriptor\(\s*"(?P<operation>[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+)"'
        r"(?P<body>.*?)(?=\n        Descriptor\(|\n    \];)",
        text,
        flags=re.DOTALL,
    )
    operations: set[str] = set()
    discovered = 0
    for block in blocks:
        discovered += 1
        exposure = re.search(r"ToolExposure\.(Public|Internal)", block.group("body"))
        if exposure is None:
            raise ValueError("catalog exposure is incomplete")
        if exposure.group(1) == "Public":
            operations.add(block.group("operation"))
    if discovered < 100 or not operations:
        raise ValueError("public product catalog could not be reconstructed")
    return frozenset(operations)


def aggregate_mission_vectors(
    examples: Sequence[DevelopmentExample],
    vectors: np.ndarray,
) -> list[GroupExample]:
    """Average translations/paraphrases so each mission has one statistical vote."""

    matrix = _finite_matrix(vectors)
    if matrix.shape[0] != len(examples):
        raise ValueError("vector/example count differs")
    indices: dict[str, list[int]] = defaultdict(list)
    for index, example in enumerate(examples):
        indices[example.mission_id].append(index)
    grouped: list[GroupExample] = []
    for mission_id, positions in sorted(indices.items()):
        members = [examples[index] for index in positions]
        signatures = {member.target_signature for member in members}
        splits = {member.split for member in members}
        if len(signatures) != 1 or len(splits) != 1:
            raise ValueError("mission group target or split is inconsistent")
        member_matrix = matrix[positions]
        member_norms = np.linalg.norm(member_matrix, axis=1)
        if (
            not np.isfinite(member_norms).all()
            or np.any(member_norms <= 0)
        ):
            raise ValueError("mission member embedding has zero/invalid norm")
        normalized_members = member_matrix / member_norms[:, None]
        vector = normalized_members.mean(axis=0)
        norm = float(np.linalg.norm(vector))
        if not math.isfinite(norm) or norm <= 0:
            raise ValueError("mission embedding has zero/invalid norm")
        trigger, no_effect_disposition, families, operations = next(iter(signatures))
        grouped.append(
            GroupExample(
                mission_id=mission_id,
                split=members[0].split,
                trigger=trigger,
                no_effect_disposition=no_effect_disposition,
                families=families,
                operations=operations,
                datasets=tuple(sorted({member.dataset for member in members})),
                vector=(vector / norm).astype(np.float64),
                member_vectors=tuple(
                    row.astype(np.float64) for row in normalized_members
                ),
                member_locales=tuple(member.locale or "und" for member in members),
            )
        )
    return grouped


def flatten_group_members(
    groups: Sequence[GroupExample],
    targets: Sequence[Any],
    *,
    balance_targets: Sequence[Any] | None = None,
) -> tuple[np.ndarray, list[Any], np.ndarray]:
    """Expand utterances while keeping one balanced statistical vote per mission.

    Every mission first receives equal mass inside its target/source stratum;
    that mass is then divided across its translations and paraphrases.  This
    prevents multilingual missions from being duplicated while fitting the
    classifier on the same unit it will see at runtime: one utterance.
    """

    balancing = targets if balance_targets is None else balance_targets
    if (
        not groups
        or len(groups) != len(targets)
        or len(groups) != len(balancing)
    ):
        raise ValueError("group/target training inputs are inconsistent")
    strata = Counter(
        (str(balance_target), group.datasets)
        for group, balance_target in zip(groups, balancing)
    )
    if not strata:
        raise ValueError("group-balanced training has no strata")
    vectors: list[np.ndarray] = []
    row_targets: list[Any] = []
    weights: list[float] = []
    for group, target, balance_target in zip(groups, targets, balancing):
        members = group.member_vectors
        if not members or len(members) != len(group.member_locales):
            raise ValueError("mission has no aligned utterance members")
        stratum_size = strata[(str(balance_target), group.datasets)]
        group_mass = 1.0 / (len(strata) * stratum_size)
        member_mass = group_mass / len(members)
        for vector in members:
            row = np.asarray(vector, dtype=np.float64)
            if (
                row.ndim != 1
                or row.shape != np.asarray(group.vector).shape
                or not np.isfinite(row).all()
            ):
                raise ValueError("mission member vector is invalid")
            vectors.append(row)
            row_targets.append(target)
            weights.append(member_mass)
    matrix = _finite_matrix(np.vstack(vectors))
    sample_weights = np.asarray(weights, dtype=np.float64)
    if (
        sample_weights.shape != (matrix.shape[0],)
        or not np.isfinite(sample_weights).all()
        or np.any(sample_weights <= 0)
    ):
        raise ValueError("mission-balanced sample weights are invalid")
    # Scaling does not change the relative group mass and keeps regularization
    # C interpretable at the conventional mean sample weight of one.
    sample_weights *= matrix.shape[0] / float(sample_weights.sum())
    return matrix, row_targets, sample_weights


def _fit_binary_softmax(
    vectors: np.ndarray,
    labels: Sequence[str],
    *,
    negative: str,
    positive: str,
    regularization_c: float,
    sample_weights: Sequence[float] | None = None,
) -> LinearHead:
    from sklearn.linear_model import LogisticRegression

    matrix = _finite_matrix(vectors)
    if len(labels) != matrix.shape[0] or set(labels) != {negative, positive}:
        raise ValueError("binary training requires both canonical classes")
    weights = (
        None
        if sample_weights is None
        else np.asarray(sample_weights, dtype=np.float64)
    )
    if weights is not None and (
        weights.shape != (matrix.shape[0],)
        or not np.isfinite(weights).all()
        or np.any(weights <= 0)
    ):
        raise ValueError("binary sample weights are invalid")
    targets = np.asarray([int(label == positive) for label in labels], dtype=np.int64)
    model = LogisticRegression(
        C=regularization_c,
        class_weight=None if weights is not None else "balanced",
        max_iter=2_000,
        random_state=0,
        solver="lbfgs",
        tol=1e-7,
    )
    model.fit(matrix, targets, sample_weight=weights)
    coefficient = np.asarray(model.coef_[0], dtype=np.float64)
    intercept = float(model.intercept_[0])
    # Two symmetric softmax rows preserve the exact binary logit difference.
    return LinearHead(
        "softmax",
        (negative, positive),
        np.vstack((-0.5 * coefficient, 0.5 * coefficient)),
        np.asarray((-0.5 * intercept, 0.5 * intercept), dtype=np.float64),
    )


def _fit_one_vs_rest(
    vectors: np.ndarray,
    targets: Sequence[tuple[str, ...]],
    *,
    regularization_c: float,
    sample_weights: Sequence[float] | None = None,
) -> LinearHead:
    from sklearn.linear_model import LogisticRegression

    matrix = _finite_matrix(vectors)
    if len(targets) != matrix.shape[0]:
        raise ValueError("multilabel target/vector count differs")
    weights = (
        None
        if sample_weights is None
        else np.asarray(sample_weights, dtype=np.float64)
    )
    if weights is not None and (
        weights.shape != (matrix.shape[0],)
        or not np.isfinite(weights).all()
        or np.any(weights <= 0)
    ):
        raise ValueError("multilabel sample weights are invalid")
    classes = tuple(sorted({label for labels in targets for label in labels}))
    if not classes:
        raise ValueError("multilabel training has no positive class")
    coefficients: list[np.ndarray] = []
    intercepts: list[float] = []
    for label in classes:
        binary = np.asarray([int(label in labels) for labels in targets], dtype=np.int64)
        if binary.min() == binary.max():
            raise ValueError(f"multilabel class {label} lacks positive/negative examples")
        model = LogisticRegression(
            C=regularization_c,
            class_weight="balanced",
            max_iter=2_000,
            random_state=0,
            solver="lbfgs",
            tol=1e-7,
        )
        model.fit(matrix, binary, sample_weight=weights)
        coefficients.append(np.asarray(model.coef_[0], dtype=np.float64))
        intercepts.append(float(model.intercept_[0]))
    return LinearHead(
        "one_vs_rest",
        classes,
        np.vstack(coefficients),
        np.asarray(intercepts, dtype=np.float64),
    )


def conformal_quantile(scores: Sequence[float], alpha: float) -> float:
    """Finite-sample split-conformal quantile with the +1 correction."""

    if not 0.0 < alpha < 1.0 or not scores:
        raise ValueError("conformal alpha/scores are invalid")
    ordered = sorted(float(score) for score in scores)
    if any(not math.isfinite(score) or not 0.0 <= score <= 1.0 for score in ordered):
        raise ValueError("conformal scores must be finite probabilities")
    rank = math.ceil((len(ordered) + 1) * (1.0 - alpha))
    # If the finite-sample corrected rank is n+1, the conformal quantile is
    # +infinity. Scores are bounded by one here, so 1.0 is the equivalent safe
    # threshold and produces the full prediction set instead of overstating
    # coverage from an under-sized calibration sample.
    return 1.0 if rank > len(ordered) else ordered[rank - 1]


def conformal_classification_set(
    probabilities: Sequence[float],
    classes: Sequence[str],
    threshold: float,
) -> tuple[str, ...]:
    if (
        len(probabilities) != len(classes)
        or len(set(classes)) != len(classes)
        or not 0.0 <= threshold <= 1.0
        or any(
            not math.isfinite(float(probability))
            or not 0.0 <= float(probability) <= 1.0
            for probability in probabilities
        )
    ):
        raise ValueError("classification-set inputs are invalid")
    return tuple(
        label
        for label, probability in zip(classes, probabilities)
        if 1.0 - float(probability) <= threshold
    )


def conformal_label_conditional_set(
    probabilities: Sequence[float],
    classes: Sequence[str],
    thresholds: Mapping[str, Any],
) -> tuple[str, ...]:
    """Prediction set with one split-conformal quantile per trigger class."""

    if len(probabilities) != len(classes) or set(thresholds) != set(classes):
        raise ValueError("label-conditional thresholds are incomplete")
    selected: list[str] = []
    for label, probability in zip(classes, probabilities):
        threshold = thresholds[label]
        member = conformal_classification_set(
            [probability],
            [label],
            threshold,
        )
        selected.extend(member)
    return tuple(selected)


def conformal_multilabel_set(
    probabilities: Sequence[float],
    classes: Sequence[str],
    threshold: float,
    *,
    maximum_size: int,
) -> tuple[str, ...]:
    if not isinstance(maximum_size, int) or isinstance(maximum_size, bool) or maximum_size < 1:
        raise ValueError("maximum conformal shortlist size is invalid")
    selected = conformal_classification_set(probabilities, classes, threshold)
    if not selected or len(selected) > maximum_size:
        return ()
    return selected


def _true_class_scores(
    probabilities: np.ndarray,
    classes: Sequence[str],
    labels: Sequence[str],
) -> list[float]:
    lookup = {label: index for index, label in enumerate(classes)}
    return [
        1.0 - float(probabilities[row, lookup[label]])
        if label in lookup
        else 1.0
        for row, label in enumerate(labels)
    ]


def _true_multilabel_scores(
    probabilities: np.ndarray,
    classes: Sequence[str],
    labels: Sequence[tuple[str, ...]],
) -> list[float]:
    lookup = {label: index for index, label in enumerate(classes)}
    scores: list[float] = []
    for row, true_labels in enumerate(labels):
        if not true_labels:
            raise ValueError("supported multilabel calibration row has no labels")
        minimum = min(
            float(probabilities[row, lookup[label]]) if label in lookup else 0.0
            for label in true_labels
        )
        scores.append(1.0 - minimum)
    return scores


def _group_member_probabilities(
    groups: Sequence[GroupExample],
    head: LinearHead,
) -> list[np.ndarray]:
    probabilities: list[np.ndarray] = []
    for group in groups:
        if not group.member_vectors:
            raise ValueError("mission group has no runtime utterance vectors")
        matrix = _finite_matrix(
            np.vstack(group.member_vectors),
            dimensions=head.dimensions,
        )
        probabilities.append(head.probabilities(matrix))
    return probabilities


def group_worst_true_class_scores(
    probabilities: Sequence[np.ndarray],
    classes: Sequence[str],
    labels: Sequence[str],
) -> list[float]:
    """Return one worst-utterance nonconformity score per mission."""

    if not probabilities or len(probabilities) != len(labels):
        raise ValueError("grouped class calibration inputs are inconsistent")
    lookup = {label: index for index, label in enumerate(classes)}
    scores: list[float] = []
    for group_probabilities, label in zip(probabilities, labels):
        matrix = _finite_matrix(group_probabilities, dimensions=len(classes))
        if label not in lookup:
            raise ValueError("grouped class label is absent from the head")
        scores.append(1.0 - float(matrix[:, lookup[label]].min()))
    return scores


def group_worst_true_multilabel_scores(
    probabilities: Sequence[np.ndarray],
    classes: Sequence[str],
    labels: Sequence[tuple[str, ...]],
) -> list[float]:
    """Return one worst-utterance multilabel score per mission."""

    if not probabilities or len(probabilities) != len(labels):
        raise ValueError("grouped multilabel calibration inputs are inconsistent")
    lookup = {label: index for index, label in enumerate(classes)}
    scores: list[float] = []
    for group_probabilities, true_labels in zip(probabilities, labels):
        matrix = _finite_matrix(group_probabilities, dimensions=len(classes))
        if not true_labels:
            raise ValueError("supported mission has no shortlist labels")
        if any(label not in lookup for label in true_labels):
            scores.append(1.0)
            continue
        minimum = min(
            float(matrix[:, lookup[label]].min()) for label in true_labels
        )
        scores.append(1.0 - minimum)
    return scores


def strict_guard_threshold(
    mission_scores: Sequence[float],
    *,
    delta: float,
) -> dict[str, float | int]:
    """Calibrate a one-sided, zero-acceptance tolerance guard by mission.

    The runtime comparator is strictly greater than the maximum calibration
    score.  Under exchangeable missions, the returned Wilks tolerance bound is
    the one-sided upper rate at confidence ``1-delta``.  Calibration uses each
    mission's worst utterance, so multilingual variants do not get extra votes.
    """

    ordered = [float(score) for score in mission_scores]
    if (
        not ordered
        or not 0.0 < delta < 1.0
        or any(
            not math.isfinite(score) or not 0.0 <= score <= 1.0
            for score in ordered
        )
    ):
        raise ValueError("selective guard calibration inputs are invalid")
    trials = len(ordered)
    return {
        "threshold": max(ordered),
        "calibration_missions": trials,
        "calibration_false_accepts": 0,
        "tolerance_delta": float(delta),
        "wilks_upper_rate": 1.0 - math.pow(delta, 1.0 / trials),
    }


def _stable_rank(seed: str, mission_id: str) -> bytes:
    return hashlib.sha256((seed + "\0" + mission_id).encode("utf-8")).digest()


def split_validation_groups(
    groups: Sequence[GroupExample],
    seed: str,
) -> tuple[list[GroupExample], list[GroupExample]]:
    """Split validation by mission within outcome/source/stage strata.

    Mission grouping prevents paraphrase/translation leakage.  Source-aware
    strata keep runtime conversation and MTOP OOD evidence represented on both
    sides instead of letting an aggregate label hide domain shortcutting.
    """

    strata: dict[tuple[str, str, tuple[str, ...]], list[GroupExample]] = (
        defaultdict(list)
    )
    for group in groups:
        if group.split != "validation":
            raise ValueError("calibration/evaluation input is not validation")
        stage = "operation" if group.operations else "no_operation"
        strata[(group.outcome, stage, group.datasets)].append(group)
    calibration: list[GroupExample] = []
    evaluation: list[GroupExample] = []
    splittable: list[
        tuple[tuple[str, str, tuple[str, ...]], list[GroupExample]]
    ] = []
    rare: dict[tuple[str, str], list[GroupExample]] = defaultdict(list)
    for stratum, members in sorted(strata.items()):
        if len(members) >= 2:
            splittable.append((stratum, members))
        else:
            rare[(stratum[0], stratum[1])].extend(members)
    for coarse, members in sorted(rare.items()):
        splittable.append(((coarse[0], coarse[1], ("rare_source_pool",)), members))
    for stratum, members in splittable:
        if len(members) < 2:
            raise ValueError(
                "validation outcome/stage has only one mission and cannot be split"
            )
        ranked = sorted(
            members,
            key=lambda item: (
                _stable_rank(
                    seed
                    + "\0"
                    + stratum[0]
                    + "|"
                    + stratum[1]
                    + "|"
                    + ",".join(stratum[2]),
                    item.mission_id,
                ),
                item.mission_id,
            ),
        )
        cut = max(1, len(ranked) // 2)
        calibration.extend(ranked[:cut])
        evaluation.extend(ranked[cut:])
    if (
        not calibration
        or not evaluation
        or {group.outcome for group in calibration} != set(OUTCOME_CLASSES)
        or {group.outcome for group in evaluation} != set(OUTCOME_CLASSES)
        or not any(group.operations for group in calibration)
    ):
        raise ValueError(
            "validation lacks disjoint trigger/operation calibration evidence"
        )
    return calibration, evaluation


def _group_matrix(groups: Sequence[GroupExample]) -> np.ndarray:
    if not groups:
        raise ValueError("group matrix is empty")
    return np.vstack([group.vector for group in groups]).astype(np.float64)


def _group_fingerprint(groups: Sequence[GroupExample]) -> str:
    safe_rows = [
        {
            "mission_id_sha256": _sha256_bytes(group.mission_id.encode("utf-8")),
            "split": group.split,
            "trigger": group.trigger,
            "no_effect_disposition": group.no_effect_disposition,
            "outcome": group.outcome,
            "families": list(group.families),
            "operations": list(group.operations),
            "datasets": list(group.datasets),
        }
        for group in sorted(groups, key=lambda item: item.mission_id)
    ]
    return _sha256_bytes(_canonical_json_bytes(safe_rows))


def _evaluate(
    groups: Sequence[GroupExample],
    effect_head: LinearHead,
    no_effect_head: LinearHead,
    family_head: LinearHead,
    operation_head: LinearHead,
    *,
    effect_thresholds: Mapping[str, float],
    no_effect_thresholds: Mapping[str, float],
    family_threshold: float,
    operation_threshold: float,
    selective_guards: Mapping[str, Mapping[str, Any]],
    maximum_families: int,
    maximum_operations: int,
) -> dict[str, Any]:
    if not groups:
        raise ValueError("evaluation groups are empty")
    guard_names = {"supported_effect", "conversation_fast_path"}
    if set(selective_guards) != guard_names:
        raise ValueError("selective guard set is incomplete")
    guard_thresholds: dict[str, float] = {}
    for name in sorted(guard_names):
        guard = selective_guards[name]
        threshold = guard.get("threshold") if isinstance(guard, Mapping) else None
        if (
            not isinstance(threshold, (int, float))
            or isinstance(threshold, bool)
            or not math.isfinite(float(threshold))
            or not 0.0 <= float(threshold) <= 1.0
        ):
            raise ValueError("selective guard threshold is invalid")
        guard_thresholds[name] = float(threshold)

    effect_probabilities = _group_member_probabilities(groups, effect_head)
    no_effect_probabilities = _group_member_probabilities(groups, no_effect_head)
    family_probabilities = _group_member_probabilities(groups, family_head)
    operation_probabilities = _group_member_probabilities(groups, operation_head)
    effect_lookup = {label: index for index, label in enumerate(effect_head.classes)}
    no_effect_lookup = {
        label: index for index, label in enumerate(no_effect_head.classes)
    }

    utterances = 0
    selected = correct = 0
    effect_covered = effect_singleton_correct = 0
    no_effect_trials = no_effect_covered = no_effect_singleton_correct = 0
    unsafe_false_supported = 0
    unsafe_conversation_as_supported = 0
    unsafe_ood_as_supported = 0
    unsafe_supported_as_conversation = 0
    unsafe_ood_as_conversation = 0
    outcome_trials: Counter[str] = Counter()
    outcome_selected: Counter[str] = Counter()
    outcome_correct: Counter[str] = Counter()
    family_trials = family_covered = family_abstained = 0
    operation_trials = operation_covered = operation_abstained = 0
    locale_buckets: dict[str, Counter[str]] = defaultdict(Counter)
    dataset_buckets: dict[str, Counter[str]] = defaultdict(Counter)
    mission_all_correct = mission_any_selected = mission_any_unsafe = 0
    effect_mission_all_covered = no_effect_mission_all_covered = 0
    no_effect_missions = 0

    for group_index, group in enumerate(groups):
        true_outcome = group.outcome
        member_predictions: list[str | None] = []
        member_effect_covered: list[bool] = []
        member_no_effect_covered: list[bool] = []
        dataset_key = (
            group.datasets[0] if len(group.datasets) == 1 else "mixed_source"
        )
        matrices = (
            effect_probabilities[group_index],
            no_effect_probabilities[group_index],
            family_probabilities[group_index],
            operation_probabilities[group_index],
        )
        if any(matrix.shape[0] != len(group.member_vectors) for matrix in matrices):
            raise ValueError("evaluation probability/member count differs")

        for member_index, locale in enumerate(group.member_locales):
            utterances += 1
            outcome_trials[true_outcome] += 1
            locale_key = locale if _SAFE_NAME.fullmatch(locale) else "und"
            locale_buckets[locale_key]["trials"] += 1
            dataset_buckets[dataset_key]["trials"] += 1

            effect_row = effect_probabilities[group_index][member_index]
            no_effect_row = no_effect_probabilities[group_index][member_index]
            family_row = family_probabilities[group_index][member_index]
            operation_row = operation_probabilities[group_index][member_index]
            effect_set = conformal_label_conditional_set(
                effect_row,
                effect_head.classes,
                effect_thresholds,
            )
            effect_is_covered = group.trigger in effect_set
            member_effect_covered.append(effect_is_covered)
            effect_covered += int(effect_is_covered)
            effect_singleton_correct += int(effect_set == (group.trigger,))

            no_effect_set: tuple[str, ...] = ()
            if group.trigger == TRIGGER_NEGATIVE:
                no_effect_trials += 1
                no_effect_set = conformal_label_conditional_set(
                    no_effect_row,
                    no_effect_head.classes,
                    no_effect_thresholds,
                )
                disposition = str(group.no_effect_disposition)
                disposition_is_covered = disposition in no_effect_set
                member_no_effect_covered.append(disposition_is_covered)
                no_effect_covered += int(disposition_is_covered)
                no_effect_singleton_correct += int(
                    no_effect_set == (disposition,)
                )

            family_set = conformal_multilabel_set(
                family_row,
                family_head.classes,
                family_threshold,
                maximum_size=maximum_families,
            )
            prediction: str | None = None
            if effect_set == (TRIGGER_POSITIVE,):
                support_score = float(
                    effect_row[effect_lookup[TRIGGER_POSITIVE]]
                    * float(np.max(family_row))
                )
                if (
                    family_set
                    and support_score
                    > guard_thresholds["supported_effect"]
                ):
                    prediction = OUTCOME_SUPPORTED
            elif effect_set == (TRIGGER_NEGATIVE,):
                if no_effect_set == (OUTCOME_CONVERSATION,):
                    conversation_score = float(
                        effect_row[effect_lookup[TRIGGER_NEGATIVE]]
                        * no_effect_row[
                            no_effect_lookup[OUTCOME_CONVERSATION]
                        ]
                    )
                    if (
                        conversation_score
                        > guard_thresholds["conversation_fast_path"]
                    ):
                        prediction = OUTCOME_CONVERSATION
                elif no_effect_set == (OUTCOME_UNSUPPORTED,):
                    prediction = OUTCOME_UNSUPPORTED
            member_predictions.append(prediction)

            is_selected = prediction is not None
            is_correct = prediction == true_outcome
            selected += int(is_selected)
            correct += int(is_correct)
            outcome_selected[true_outcome] += int(is_selected)
            outcome_correct[true_outcome] += int(is_correct)
            locale_buckets[locale_key]["selected"] += int(is_selected)
            locale_buckets[locale_key]["correct"] += int(is_correct)
            dataset_buckets[dataset_key]["selected"] += int(is_selected)
            dataset_buckets[dataset_key]["correct"] += int(is_correct)

            false_supported = (
                true_outcome != OUTCOME_SUPPORTED
                and prediction == OUTCOME_SUPPORTED
            )
            supported_as_conversation = (
                true_outcome == OUTCOME_SUPPORTED
                and prediction == OUTCOME_CONVERSATION
            )
            ood_as_conversation = (
                true_outcome == OUTCOME_UNSUPPORTED
                and prediction == OUTCOME_CONVERSATION
            )
            unsafe_false_supported += int(false_supported)
            unsafe_conversation_as_supported += int(
                true_outcome == OUTCOME_CONVERSATION
                and prediction == OUTCOME_SUPPORTED
            )
            unsafe_ood_as_supported += int(
                true_outcome == OUTCOME_UNSUPPORTED
                and prediction == OUTCOME_SUPPORTED
            )
            unsafe_supported_as_conversation += int(supported_as_conversation)
            unsafe_ood_as_conversation += int(ood_as_conversation)
            unsafe_any = (
                false_supported
                or supported_as_conversation
                or ood_as_conversation
            )
            locale_buckets[locale_key]["unsafe"] += int(unsafe_any)
            dataset_buckets[dataset_key]["unsafe"] += int(unsafe_any)

            if group.trigger == TRIGGER_POSITIVE:
                family_trials += 1
                family_abstained += int(not family_set)
                family_covered += int(
                    set(group.families) <= set(family_set)
                )
                if group.operations:
                    operation_trials += 1
                    operation_set = conformal_multilabel_set(
                        operation_row,
                        operation_head.classes,
                        operation_threshold,
                        maximum_size=maximum_operations,
                    )
                    operation_abstained += int(not operation_set)
                    operation_covered += int(
                        set(group.operations) <= set(operation_set)
                    )

        mission_all_correct += int(
            bool(member_predictions)
            and all(prediction == true_outcome for prediction in member_predictions)
        )
        mission_any_selected += int(
            any(prediction is not None for prediction in member_predictions)
        )
        mission_unsafe = (
            any(
                prediction == OUTCOME_SUPPORTED
                for prediction in member_predictions
            )
            if true_outcome != OUTCOME_SUPPORTED
            else any(
                prediction == OUTCOME_CONVERSATION
                for prediction in member_predictions
            )
        )
        mission_any_unsafe += int(mission_unsafe)
        effect_mission_all_covered += int(all(member_effect_covered))
        if group.trigger == TRIGGER_NEGATIVE:
            no_effect_missions += 1
            no_effect_mission_all_covered += int(
                bool(member_no_effect_covered)
                and all(member_no_effect_covered)
            )

    def ratio(numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 8) if denominator else 0.0

    def bucket_metrics(bucket: Mapping[str, int]) -> dict[str, Any]:
        trials = int(bucket.get("trials", 0))
        bucket_selected = int(bucket.get("selected", 0))
        return {
            "utterances": trials,
            "selection_rate": ratio(bucket_selected, trials),
            "accuracy_when_selected": ratio(
                int(bucket.get("correct", 0)),
                bucket_selected,
            ),
            "unsafe_directional_errors": int(bucket.get("unsafe", 0)),
        }

    locale_metrics = {
        locale: bucket_metrics(bucket)
        for locale, bucket in sorted(locale_buckets.items())
    }
    dataset_metrics = {
        dataset: bucket_metrics(bucket)
        for dataset, bucket in sorted(dataset_buckets.items())
    }
    worst_locale = {
        "selection_rate": min(
            float(metric["selection_rate"])
            for metric in locale_metrics.values()
        ),
        "accuracy_when_selected": min(
            float(metric["accuracy_when_selected"])
            for metric in locale_metrics.values()
        ),
        "maximum_directional_errors": max(
            int(metric["unsafe_directional_errors"])
            for metric in locale_metrics.values()
        ),
    }

    return {
        "groups": len(groups),
        "utterances": utterances,
        "effect_gate": {
            "utterance_coverage": ratio(effect_covered, utterances),
            "utterance_singleton_accuracy": ratio(
                effect_singleton_correct,
                utterances,
            ),
            "mission_all_variants_coverage": ratio(
                effect_mission_all_covered,
                len(groups),
            ),
        },
        "no_effect_disposition": {
            "utterances": no_effect_trials,
            "utterance_coverage": ratio(no_effect_covered, no_effect_trials),
            "utterance_singleton_accuracy": ratio(
                no_effect_singleton_correct,
                no_effect_trials,
            ),
            "mission_all_variants_coverage": ratio(
                no_effect_mission_all_covered,
                no_effect_missions,
            ),
        },
        "selective_outcome": {
            "selection_rate": ratio(selected, utterances),
            "abstention_rate": ratio(utterances - selected, utterances),
            "accuracy_when_selected": ratio(correct, selected),
            "correct_utterance_rate": ratio(correct, utterances),
            "per_class": {
                label: {
                    "utterances": outcome_trials[label],
                    "selection_rate": ratio(
                        outcome_selected[label],
                        outcome_trials[label],
                    ),
                    "correct_utterance_rate": ratio(
                        outcome_correct[label],
                        outcome_trials[label],
                    ),
                }
                for label in OUTCOME_CLASSES
            },
            "directional_safety": {
                "unsafe_false_supported": unsafe_false_supported,
                "unsafe_false_supported_rate": ratio(
                    unsafe_false_supported,
                    outcome_trials[OUTCOME_CONVERSATION]
                    + outcome_trials[OUTCOME_UNSUPPORTED],
                ),
                "unsafe_conversation_as_supported": (
                    unsafe_conversation_as_supported
                ),
                "unsafe_conversation_as_supported_rate": ratio(
                    unsafe_conversation_as_supported,
                    outcome_trials[OUTCOME_CONVERSATION],
                ),
                "unsafe_ood_as_supported": unsafe_ood_as_supported,
                "unsafe_ood_as_supported_rate": ratio(
                    unsafe_ood_as_supported,
                    outcome_trials[OUTCOME_UNSUPPORTED],
                ),
                "unsafe_supported_as_conversation": (
                    unsafe_supported_as_conversation
                ),
                "unsafe_supported_as_conversation_rate": ratio(
                    unsafe_supported_as_conversation,
                    outcome_trials[OUTCOME_SUPPORTED],
                ),
                "unsafe_ood_as_conversation": unsafe_ood_as_conversation,
                "unsafe_ood_as_conversation_rate": ratio(
                    unsafe_ood_as_conversation,
                    outcome_trials[OUTCOME_UNSUPPORTED],
                ),
            },
        },
        "mission_level": {
            "missions": len(groups),
            "all_variants_correct": ratio(mission_all_correct, len(groups)),
            "any_variant_selected": ratio(mission_any_selected, len(groups)),
            "missions_with_directional_error": mission_any_unsafe,
        },
        "family_shortlist": {
            "trials": family_trials,
            "coverage": ratio(family_covered, family_trials),
            "abstention_rate": ratio(family_abstained, family_trials),
            "maximum_size": maximum_families,
        },
        "operation_shortlist": {
            "trials": operation_trials,
            "coverage": ratio(operation_covered, operation_trials),
            "abstention_rate": ratio(operation_abstained, operation_trials),
            "maximum_size": maximum_operations,
        },
        "per_locale": locale_metrics,
        "worst_locale": worst_locale,
        "per_dataset": dataset_metrics,
    }


def _validate_aggregate_mapping(value: Mapping[str, Any], field: str) -> None:
    for key, item in value.items():
        if not isinstance(key, str) or _SAFE_NAME.fullmatch(key) is None:
            raise ValueError(f"{field} contains an unsafe key")
        if isinstance(item, Mapping):
            _validate_aggregate_mapping(item, field)
        elif isinstance(item, bool):
            continue
        elif isinstance(item, int):
            if item < 0:
                raise ValueError(f"{field} contains a negative count")
        elif isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError(f"{field} contains a non-finite metric")
        else:
            raise ValueError(f"{field} contains a non-aggregate value")


def build_text_free_artifact(
    *,
    sources: Sequence[Mapping[str, Any]],
    catalog_identity: Mapping[str, Any],
    encoder_identity: Mapping[str, Any],
    training_identity: Mapping[str, Any],
    train_groups: Sequence[GroupExample],
    calibration_groups: Sequence[GroupExample],
    evaluation_groups: Sequence[GroupExample],
    effect_head: LinearHead,
    no_effect_head: LinearHead,
    family_head: LinearHead,
    operation_head: LinearHead,
    thresholds: Mapping[str, Any],
    alpha: float,
    exclusions: Mapping[str, int],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    effect_thresholds = thresholds.get("effect")
    no_effect_thresholds = thresholds.get("no_effect_disposition")
    selective_guards = thresholds.get("selective_guards")
    scalar_thresholds = (
        thresholds.get("family"),
        thresholds.get("operation"),
    )
    if (
        set(thresholds)
        != {
            "effect",
            "no_effect_disposition",
            "family",
            "operation",
            "selective_guards",
        }
        or not isinstance(effect_thresholds, Mapping)
        or set(effect_thresholds) != set(effect_head.classes)
        or not isinstance(no_effect_thresholds, Mapping)
        or set(no_effect_thresholds) != set(no_effect_head.classes)
        or not isinstance(selective_guards, Mapping)
        or set(selective_guards)
        != {"supported_effect", "conversation_fast_path"}
        or not 0.0 < alpha < 1.0
        or any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or not 0.0 <= float(value) <= 1.0
            for value in (
                *effect_thresholds.values(),
                *no_effect_thresholds.values(),
                *scalar_thresholds,
            )
        )
        or effect_head.dimensions != no_effect_head.dimensions
        or effect_head.dimensions != family_head.dimensions
        or effect_head.dimensions != operation_head.dimensions
    ):
        raise ValueError("artifact thresholds are incomplete")
    for guard in selective_guards.values():
        if not isinstance(guard, Mapping):
            raise ValueError("artifact selective guard is invalid")
        _validate_aggregate_mapping(guard, "selective_guard")
        if (
            guard.get("calibration_false_accepts") != 0
            or not isinstance(guard.get("calibration_missions"), int)
            or int(guard["calibration_missions"]) < 1
            or not isinstance(guard.get("threshold"), (int, float))
            or isinstance(guard.get("threshold"), bool)
            or not 0.0 <= float(guard["threshold"]) <= 1.0
        ):
            raise ValueError("artifact selective guard is not fail-closed")
    partitions = (
        ("train", train_groups, {"train"}),
        ("calibration", calibration_groups, {"validation"}),
        ("evaluation", evaluation_groups, {"validation"}),
    )
    mission_partitions: dict[str, str] = {}
    for partition_name, groups, allowed_splits in partitions:
        if not groups or {group.split for group in groups} - allowed_splits:
            raise ValueError("artifact group partition is invalid")
        for group in groups:
            previous = mission_partitions.setdefault(group.mission_id, partition_name)
            if previous != partition_name:
                raise ValueError("mission_id crosses artifact partitions")
    safe_sources: list[dict[str, Any]] = []
    for source in sources:
        if (
            set(source)
            != {
                "name",
                "sha256",
                "rows",
                "row_fingerprint_sha256",
                "contains_test",
                "embedding_cache_manifest_sha256",
                "embedding_array_sha256",
            }
            or _SAFE_NAME.fullmatch(str(source.get("name"))) is None
            or _SHA256.fullmatch(str(source.get("sha256"))) is None
            or _SHA256.fullmatch(str(source.get("row_fingerprint_sha256"))) is None
            or _SHA256.fullmatch(
                str(source.get("embedding_cache_manifest_sha256"))
            )
            is None
            or _SHA256.fullmatch(str(source.get("embedding_array_sha256")))
            is None
            or not isinstance(source.get("rows"), int)
            or isinstance(source.get("rows"), bool)
            or int(source["rows"]) < 1
            or source.get("contains_test") is not False
        ):
            raise ValueError("artifact source identity is unsafe")
        safe_sources.append(dict(source))
    if (
        set(training_identity)
        != {
            "fit_unit",
            "linear_solver",
            "sample_weight",
            "effect_c",
            "no_effect_c",
            "family_c",
            "operation_c",
            "maximum_families",
            "maximum_operations",
            "validation_seed_sha256",
            "selective_guard_delta",
        }
        or training_identity.get("fit_unit")
        != "utterance_l2_normalized_mission_disjoint"
        or training_identity.get("linear_solver") != "lbfgs"
        or training_identity.get("sample_weight")
        != "equal_head_target_source_mass_then_inverse_mission_variants"
        or any(
            not isinstance(training_identity.get(name), (int, float))
            or isinstance(training_identity.get(name), bool)
            or not math.isfinite(float(training_identity[name]))
            or float(training_identity[name]) <= 0.0
            for name in (
                "effect_c",
                "no_effect_c",
                "family_c",
                "operation_c",
                "selective_guard_delta",
            )
        )
        or any(
            not isinstance(training_identity.get(name), int)
            or isinstance(training_identity.get(name), bool)
            or int(training_identity[name]) < 1
            for name in ("maximum_families", "maximum_operations")
        )
        or _SHA256.fullmatch(
            str(training_identity.get("validation_seed_sha256"))
        )
        is None
        or not 0.0
        < float(training_identity.get("selective_guard_delta", 0.0))
        < 1.0
    ):
        raise ValueError("artifact training identity is unsafe")
    _validate_aggregate_mapping(metrics, "metrics")
    _validate_aggregate_mapping(exclusions, "exclusions")
    artifact = {
        "schema": ARTIFACT_SCHEMA,
        "status": "development_only_not_runtime_authority",
        "privacy": {
            "contains_text": False,
            "contains_source_ids": False,
            "contains_mission_ids": False,
            "contains_model_responses": False,
            "contains_derived_model_parameters": True,
        },
        "constraints": {
            "used_splits": ["train", "validation"],
            "sealed_final_test_reserve_opened": False,
            "v4_opened": False,
            "mtop_candidate_is_advisory_only": True,
            "execution_authority": False,
            "requires_independent_llm_selection": True,
            "requires_schema_grounding_risk_confirmation_and_core_verification": True,
            "grouped_by_mission_id_before_fit_and_evaluation": True,
            "utterance_level_fit_and_evaluation": True,
            "mission_disjoint_calibration_and_evaluation": True,
            "ood_can_authorize_fast_chat": False,
            "selective_signal_can_authorize_execution": False,
            "normalized_text_split_overlap": 0,
        },
        "sources": safe_sources,
        "catalog": dict(catalog_identity),
        "encoder": dict(encoder_identity),
        "training": dict(training_identity),
        "protocol": {
            "outcome_classes": list(OUTCOME_CLASSES),
            "effect_classes": list(TRIGGER_CLASSES),
            "no_effect_classes": list(NO_EFFECT_CLASSES),
            "hierarchy": "effect_gate_then_no_effect_disposition",
            "conformal_alpha": alpha,
            "conformal_calibration": (
                "label_conditional_worst_utterance_per_mission"
            ),
            "calibration_split": (
                "validation_mission_partition_by_outcome_source_stage"
            ),
            "evaluation_split": (
                "disjoint_validation_missions_evaluated_per_utterance"
            ),
            "selective_guard_comparator": "strictly_greater_than",
            "conversation_fast_path_requires": (
                "effect_no_effect_singleton_and_conversation_singleton_and_guard"
            ),
            "unsupported_ood_fast_path": "forbidden",
            "hierarchical_disposition_binding": (
                "pinned_source_projection_map_and_v2_group_fingerprint"
            ),
            "embedding_cache_v1_reuse": (
                "encoder_rows_only_disposition_cannot_change_embeddings"
            ),
            "ambiguous_mtop_contract_structure_mismatch": "excluded",
            "corrected_missing_information": "supported_effect_requires_clarify",
            "mtop_ood_negative_requires": "mapped_intent_in_reviewed_ood_partition",
        },
        "groups": {
            "train": len(train_groups),
            "calibration": len(calibration_groups),
            "evaluation": len(evaluation_groups),
            "train_fingerprint_sha256": _group_fingerprint(train_groups),
            "calibration_fingerprint_sha256": _group_fingerprint(calibration_groups),
            "evaluation_fingerprint_sha256": _group_fingerprint(evaluation_groups),
        },
        "heads": {
            "effect_gate": effect_head.safe_dict(),
            "no_effect_disposition": no_effect_head.safe_dict(),
            "family_shortlist": family_head.safe_dict(),
            "operation_shortlist": operation_head.safe_dict(),
        },
        "conformal": {
            "effect_gate": {
                "nonconformity": "mission_max_over_utterances_of_1-p_true",
                "calibration": "label_conditional_by_mission",
                "thresholds": {
                    label: float(effect_thresholds[label])
                    for label in effect_head.classes
                },
            },
            "no_effect_disposition": {
                "nonconformity": "mission_max_over_utterances_of_1-p_true",
                "calibration": "label_conditional_by_mission",
                "thresholds": {
                    label: float(no_effect_thresholds[label])
                    for label in no_effect_head.classes
                },
            },
            "family": {
                "nonconformity": (
                    "mission_max_over_utterances_of_1-min_true_probability"
                ),
                "threshold": float(thresholds["family"]),
            },
            "operation": {
                "nonconformity": (
                    "mission_max_over_utterances_of_1-min_true_probability"
                ),
                "threshold": float(thresholds["operation"]),
            },
        },
        "selective_guards": {
            key: dict(value)
            for key, value in sorted(selective_guards.items())
        },
        "exclusions": dict(sorted((str(key), int(value)) for key, value in exclusions.items())),
        "metrics": dict(metrics),
    }
    policy_payload = {
        key: artifact[key]
        for key in (
            "constraints",
            "catalog",
            "encoder",
            "training",
            "protocol",
            "heads",
            "conformal",
            "selective_guards",
        )
    }
    evidence_payload = {
        key: artifact[key]
        for key in ("sources", "groups", "exclusions", "metrics")
    }
    artifact["integrity"] = {
        "algorithm": "sha256_canonical_json_utf8_lf",
        "policy_payload_sha256": _sha256_bytes(
            _canonical_json_bytes(policy_payload)
        ),
        "evidence_payload_sha256": _sha256_bytes(
            _canonical_json_bytes(evidence_payload)
        ),
    }
    # Canonical serialization is also a validation pass for NaN/Infinity.
    _canonical_json_bytes(artifact)
    return artifact


class FrozenE5Encoder:
    """Lazy, local-only encoder used only when a verified cache misses."""

    def __init__(self, device: str) -> None:
        from baxy_mind.router import (
            MODEL_NAME,
            MODEL_REVISION,
            QUERY_PREFIX,
            verified_encoder_snapshot_identity,
        )
        from sentence_transformers import SentenceTransformer

        self.identity = {
            **verified_encoder_snapshot_identity(),
            "query_prefix": QUERY_PREFIX,
            "normalize_embeddings": True,
        }
        self._prefix = QUERY_PREFIX
        self._model = SentenceTransformer(
            MODEL_NAME,
            revision=MODEL_REVISION,
            local_files_only=True,
            device=device,
        )

    def encode(self, examples: Sequence[DevelopmentExample], batch_size: int) -> np.ndarray:
        vectors = self._model.encode(
            [self._prefix + example.text for example in examples],
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        return _finite_matrix(np.asarray(vectors, dtype=np.float32)).astype(np.float32)


def _encoder_identity_without_loading_model() -> dict[str, Any]:
    from baxy_mind.router import QUERY_PREFIX, verified_encoder_snapshot_identity

    return {
        **verified_encoder_snapshot_identity(),
        "query_prefix": QUERY_PREFIX,
        "normalize_embeddings": True,
    }


def _cache_manifest_path(
    cache_directory: Path,
    *,
    dataset_name: str,
    source_sha256: str,
    examples: Sequence[DevelopmentExample],
    encoder_identity: Mapping[str, Any],
) -> Path:
    key = _cache_key(
        dataset_name,
        source_sha256,
        examples_fingerprint(examples),
        encoder_identity,
    )
    return cache_directory / f"{dataset_name}-{key}.json"


def _vectors_for_source(
    *,
    cache_directory: Path,
    dataset_name: str,
    source_path: Path,
    examples: Sequence[DevelopmentExample],
    encoder_identity: Mapping[str, Any],
    encoder_holder: list[FrozenE5Encoder],
    device: str,
    batch_size: int,
) -> tuple[np.ndarray, dict[str, str]]:
    source_sha256 = _sha256_file(source_path)
    manifest_path = _cache_manifest_path(
        cache_directory,
        dataset_name=dataset_name,
        source_sha256=source_sha256,
        examples=examples,
        encoder_identity=encoder_identity,
    )
    if not manifest_path.is_file():
        if not encoder_holder:
            encoder_holder.append(FrozenE5Encoder(device))
            if encoder_holder[0].identity != dict(encoder_identity):
                raise ValueError("loaded E5 identity differs from cache identity")
        vectors = encoder_holder[0].encode(examples, batch_size)
        manifest_path = write_embedding_cache_atomic(
            cache_directory,
            dataset_name=dataset_name,
            source_sha256=source_sha256,
            examples=examples,
            encoder_identity=encoder_identity,
            vectors=vectors,
        )
    manifest_sha256 = _sha256_file(manifest_path)
    vectors = load_embedding_cache(
        manifest_path,
        dataset_name=dataset_name,
        source_sha256=source_sha256,
        examples=examples,
        encoder_identity=encoder_identity,
    )
    manifest_bytes = manifest_path.read_bytes()
    if _sha256_bytes(manifest_bytes) != manifest_sha256:
        raise ValueError("embedding cache manifest changed while it was loaded")
    manifest = json.loads(manifest_bytes)
    array = manifest.get("array")
    if (
        not isinstance(array, dict)
        or _SHA256.fullmatch(str(array.get("sha256"))) is None
    ):
        raise ValueError("embedding cache lineage is invalid")
    return vectors, {
        "embedding_cache_manifest_sha256": manifest_sha256,
        "embedding_array_sha256": str(array["sha256"]),
    }


def run_training(args: argparse.Namespace) -> dict[str, Any]:
    for source_path in (
        args.runtime_train,
        args.runtime_validation,
        args.mtop_development,
        args.mtop_map,
        args.product_catalog,
    ):
        _assert_development_input_path(source_path)
    _assert_development_input_path(args.output)
    _assert_development_input_path(args.cache_directory / "development-cache")
    development_paths = {
        "runtime_train": args.runtime_train.resolve(strict=True),
        "runtime_validation": args.runtime_validation.resolve(strict=True),
        "mtop_development": args.mtop_development.resolve(strict=True),
    }
    mtop_map_path = args.mtop_map.resolve(strict=True)
    _assert_development_input_path(mtop_map_path)
    product_catalog_path = args.product_catalog.resolve(strict=True)
    _assert_development_input_path(product_catalog_path)
    for source_path in development_paths.values():
        _assert_development_input_path(source_path)
    output_path = args.output.resolve(strict=False)
    protected_paths = {
        *development_paths.values(),
        product_catalog_path,
        mtop_map_path,
    }
    if output_path in protected_paths or args.output.suffix.casefold() != ".json":
        raise ValueError("development artifact output is unsafe")
    source_hashes = {
        name: _sha256_file(source_path)
        for name, source_path in development_paths.items()
    }
    expected_source_hashes = {
        "runtime_train": args.expected_runtime_train_sha256,
        "runtime_validation": args.expected_runtime_validation_sha256,
        "mtop_development": args.expected_mtop_development_sha256,
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("development source hash differs from its explicit pin")
    catalog_sha256 = _sha256_file(product_catalog_path)
    if catalog_sha256 != args.expected_product_catalog_sha256:
        raise ValueError("product catalog hash differs from its explicit pin")
    allowed_operations = _public_catalog_operations(product_catalog_path)
    if _sha256_file(product_catalog_path) != catalog_sha256:
        raise ValueError("product catalog changed while it was loaded")
    allowed_families = frozenset(
        operation.split(".", 1)[0] for operation in allowed_operations
    )
    if _sha256_file(mtop_map_path) != args.expected_mtop_map_sha256:
        raise ValueError("MTOP projection map hash differs from its explicit pin")
    intent_policy = load_mtop_intent_policy(mtop_map_path, allowed_operations)
    if intent_policy.source_sha256 != args.expected_mtop_map_sha256:
        raise ValueError("MTOP projection map changed after pin verification")
    runtime_train = load_runtime_development(
        development_paths["runtime_train"],
        "train",
    )
    runtime_validation = load_runtime_development(
        development_paths["runtime_validation"],
        "validation",
    )
    mtop = load_mtop_development(
        development_paths["mtop_development"],
        allowed_operations,
        intent_policy,
    )
    decontaminated = decontaminate_cross_source_development(
        {
            "runtime_train": runtime_train,
            "runtime_validation": runtime_validation,
            "mtop_development": mtop,
        }
    )
    runtime_train = decontaminated["runtime_train"]
    runtime_validation = decontaminated["runtime_validation"]
    mtop = decontaminated["mtop_development"]
    ordered_sources = (
        ("runtime_train", development_paths["runtime_train"], runtime_train),
        (
            "runtime_validation",
            development_paths["runtime_validation"],
            runtime_validation,
        ),
        ("mtop_development", development_paths["mtop_development"], mtop),
    )
    examples = tuple(
        example
        for _, _, result in ordered_sources
        for example in result.examples
    )
    validate_development_examples(examples, allowed_families=allowed_families)
    encoder_identity = _encoder_identity_without_loading_model()
    encoder_holder: list[FrozenE5Encoder] = []
    vectors_by_source: list[np.ndarray] = []
    safe_sources: list[dict[str, Any]] = []
    exclusions: Counter[str] = Counter()
    for dataset_name, source_path, result in ordered_sources:
        source_sha256 = source_hashes[dataset_name]
        if _sha256_file(source_path) != source_sha256:
            raise ValueError("development source changed after validation")
        source_vectors, cache_lineage = _vectors_for_source(
            cache_directory=args.cache_directory,
            dataset_name=dataset_name,
            source_path=source_path,
            examples=result.examples,
            encoder_identity=encoder_identity,
            encoder_holder=encoder_holder,
            device=args.device,
            batch_size=args.batch_size,
        )
        vectors_by_source.append(source_vectors)
        if _sha256_file(source_path) != source_sha256:
            raise ValueError("development source changed while it was encoded")
        exclusions.update(result.exclusions)
        safe_sources.append(
            {
                "name": dataset_name,
                "sha256": source_sha256,
                "rows": len(result.examples),
                "row_fingerprint_sha256": examples_fingerprint(result.examples),
                "contains_test": False,
                **cache_lineage,
            }
        )
    all_vectors = np.vstack(vectors_by_source)
    groups = aggregate_mission_vectors(examples, all_vectors)
    train_groups = [group for group in groups if group.split == "train"]
    validation_groups = [group for group in groups if group.split == "validation"]
    calibration_groups, evaluation_groups = split_validation_groups(
        validation_groups,
        args.validation_seed,
    )

    effect_matrix, effect_labels, effect_weights = flatten_group_members(
        train_groups,
        [group.trigger for group in train_groups],
    )
    effect_head = _fit_binary_softmax(
        effect_matrix,
        effect_labels,
        negative=TRIGGER_NEGATIVE,
        positive=TRIGGER_POSITIVE,
        regularization_c=args.effect_c,
        sample_weights=effect_weights,
    )
    no_effect_train = [
        group for group in train_groups if group.trigger == TRIGGER_NEGATIVE
    ]
    (
        no_effect_matrix,
        no_effect_labels,
        no_effect_weights,
    ) = flatten_group_members(
        no_effect_train,
        [str(group.no_effect_disposition) for group in no_effect_train],
    )
    no_effect_head = _fit_binary_softmax(
        no_effect_matrix,
        no_effect_labels,
        negative=OUTCOME_CONVERSATION,
        positive=OUTCOME_UNSUPPORTED,
        regularization_c=args.no_effect_c,
        sample_weights=no_effect_weights,
    )
    supported_train = [
        group for group in train_groups if group.trigger == TRIGGER_POSITIVE
    ]
    family_matrix, family_targets, family_weights = flatten_group_members(
        supported_train,
        [group.families for group in supported_train],
        balance_targets=[OUTCOME_SUPPORTED for _ in supported_train],
    )
    family_head = _fit_one_vs_rest(
        family_matrix,
        family_targets,
        regularization_c=args.family_c,
        sample_weights=family_weights,
    )
    operation_train = [group for group in supported_train if group.operations]
    (
        operation_matrix,
        operation_targets,
        operation_weights,
    ) = flatten_group_members(
        operation_train,
        [group.operations for group in operation_train],
        balance_targets=[OUTCOME_SUPPORTED for _ in operation_train],
    )
    operation_head = _fit_one_vs_rest(
        operation_matrix,
        operation_targets,
        regularization_c=args.operation_c,
        sample_weights=operation_weights,
    )

    effect_calibration_probabilities = _group_member_probabilities(
        calibration_groups,
        effect_head,
    )
    effect_calibration_labels = [
        group.trigger for group in calibration_groups
    ]
    effect_calibration_scores = group_worst_true_class_scores(
        effect_calibration_probabilities,
        effect_head.classes,
        effect_calibration_labels,
    )
    effect_thresholds = {
        label: conformal_quantile(
            [
                score
                for score, true_label in zip(
                    effect_calibration_scores,
                    effect_calibration_labels,
                )
                if true_label == label
            ],
            args.alpha,
        )
        for label in effect_head.classes
    }
    no_effect_calibration = [
        group for group in calibration_groups if group.trigger == TRIGGER_NEGATIVE
    ]
    no_effect_calibration_probabilities = _group_member_probabilities(
        no_effect_calibration,
        no_effect_head,
    )
    no_effect_calibration_labels = [
        str(group.no_effect_disposition) for group in no_effect_calibration
    ]
    no_effect_calibration_scores = group_worst_true_class_scores(
        no_effect_calibration_probabilities,
        no_effect_head.classes,
        no_effect_calibration_labels,
    )
    no_effect_thresholds = {
        label: conformal_quantile(
            [
                score
                for score, true_label in zip(
                    no_effect_calibration_scores,
                    no_effect_calibration_labels,
                )
                if true_label == label
            ],
            args.alpha,
        )
        for label in no_effect_head.classes
    }
    supported_calibration = [
        group for group in calibration_groups if group.trigger == TRIGGER_POSITIVE
    ]
    family_calibration_probabilities = _group_member_probabilities(
        supported_calibration,
        family_head,
    )
    family_threshold = conformal_quantile(
        group_worst_true_multilabel_scores(
            family_calibration_probabilities,
            family_head.classes,
            [group.families for group in supported_calibration],
        ),
        args.alpha,
    )
    operation_calibration = [
        group for group in supported_calibration if group.operations
    ]
    operation_calibration_probabilities = _group_member_probabilities(
        operation_calibration,
        operation_head,
    )
    operation_threshold = conformal_quantile(
        group_worst_true_multilabel_scores(
            operation_calibration_probabilities,
            operation_head.classes,
            [group.operations for group in operation_calibration],
        ),
        args.alpha,
    )
    all_family_calibration_probabilities = _group_member_probabilities(
        calibration_groups,
        family_head,
    )
    effect_lookup = {
        label: index for index, label in enumerate(effect_head.classes)
    }
    no_effect_lookup = {
        label: index for index, label in enumerate(no_effect_head.classes)
    }
    all_no_effect_calibration_probabilities = _group_member_probabilities(
        calibration_groups,
        no_effect_head,
    )
    support_guard_scores = [
        float(
            np.max(
                effect_rows[:, effect_lookup[TRIGGER_POSITIVE]]
                * np.max(family_rows, axis=1)
            )
        )
        for group, effect_rows, family_rows in zip(
            calibration_groups,
            effect_calibration_probabilities,
            all_family_calibration_probabilities,
        )
        if group.outcome != OUTCOME_SUPPORTED
    ]
    conversation_guard_scores = [
        float(
            np.max(
                effect_rows[:, effect_lookup[TRIGGER_NEGATIVE]]
                * no_effect_rows[
                    :, no_effect_lookup[OUTCOME_CONVERSATION]
                ]
            )
        )
        for group, effect_rows, no_effect_rows in zip(
            calibration_groups,
            effect_calibration_probabilities,
            all_no_effect_calibration_probabilities,
        )
        if group.outcome != OUTCOME_CONVERSATION
    ]
    selective_guards = {
        "supported_effect": strict_guard_threshold(
            support_guard_scores,
            delta=args.selective_guard_delta,
        ),
        "conversation_fast_path": strict_guard_threshold(
            conversation_guard_scores,
            delta=args.selective_guard_delta,
        ),
    }
    thresholds = {
        "effect": effect_thresholds,
        "no_effect_disposition": no_effect_thresholds,
        "family": family_threshold,
        "operation": operation_threshold,
        "selective_guards": selective_guards,
    }
    metrics = _evaluate(
        evaluation_groups,
        effect_head,
        no_effect_head,
        family_head,
        operation_head,
        effect_thresholds=effect_thresholds,
        no_effect_thresholds=no_effect_thresholds,
        family_threshold=family_threshold,
        operation_threshold=operation_threshold,
        selective_guards=selective_guards,
        maximum_families=args.maximum_families,
        maximum_operations=args.maximum_operations,
    )
    catalog_identity = {
        "sha256": catalog_sha256,
        "public_operations": len(allowed_operations),
        "families": len(allowed_families),
        "mtop_projection_map": {
            "sha256": intent_policy.source_sha256,
            "supported_intents": len(intent_policy.dispositions),
            "ood_intents": len(intent_policy.ood_intents),
        },
    }
    artifact = build_text_free_artifact(
        sources=safe_sources,
        catalog_identity=catalog_identity,
        encoder_identity=encoder_identity,
        training_identity={
            "fit_unit": "utterance_l2_normalized_mission_disjoint",
            "linear_solver": "lbfgs",
            "sample_weight": (
                "equal_head_target_source_mass_then_inverse_mission_variants"
            ),
            "effect_c": args.effect_c,
            "no_effect_c": args.no_effect_c,
            "family_c": args.family_c,
            "operation_c": args.operation_c,
            "maximum_families": args.maximum_families,
            "maximum_operations": args.maximum_operations,
            "validation_seed_sha256": _sha256_bytes(
                args.validation_seed.encode("utf-8")
            ),
            "selective_guard_delta": args.selective_guard_delta,
        },
        train_groups=train_groups,
        calibration_groups=calibration_groups,
        evaluation_groups=evaluation_groups,
        effect_head=effect_head,
        no_effect_head=no_effect_head,
        family_head=family_head,
        operation_head=operation_head,
        thresholds=thresholds,
        alpha=args.alpha,
        exclusions=exclusions,
        metrics=metrics,
    )
    _write_json_atomic(args.output, artifact)
    return artifact


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-train", type=Path, required=True)
    parser.add_argument("--expected-runtime-train-sha256", required=True)
    parser.add_argument("--runtime-validation", type=Path, required=True)
    parser.add_argument("--expected-runtime-validation-sha256", required=True)
    parser.add_argument("--mtop-development", type=Path, required=True)
    parser.add_argument("--expected-mtop-development-sha256", required=True)
    parser.add_argument(
        "--product-catalog",
        type=Path,
        default=ROOT / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs",
    )
    parser.add_argument("--expected-product-catalog-sha256", required=True)
    parser.add_argument(
        "--mtop-map",
        type=Path,
        default=ROOT / "src" / "baxy_mind" / "data" / "mtop_turn_evidence_map.v1.json",
    )
    parser.add_argument("--expected-mtop-map-sha256", required=True)
    parser.add_argument("--cache-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument(
        "--effect-c",
        "--trigger-c",
        dest="effect_c",
        type=float,
        default=1.0,
    )
    parser.add_argument("--no-effect-c", type=float, default=1.0)
    parser.add_argument("--family-c", type=float, default=4.0)
    parser.add_argument("--operation-c", type=float, default=4.0)
    parser.add_argument("--maximum-families", type=int, default=8)
    parser.add_argument("--maximum-operations", type=int, default=24)
    parser.add_argument("--selective-guard-delta", type=float, default=0.05)
    parser.add_argument(
        "--validation-seed",
        default="baxy-turn-policy-e5-development-validation-v2",
    )
    args = parser.parse_args(argv)
    if (
        args.batch_size < 1
        or not 0.0 < args.alpha < 1.0
        or not 0.0 < args.selective_guard_delta < 1.0
        or min(
            args.effect_c,
            args.no_effect_c,
            args.family_c,
            args.operation_c,
        )
        <= 0.0
        or not 1 <= args.maximum_families <= 32
        or not 1 <= args.maximum_operations <= 169
        or not args.validation_seed
        or any(
            _SHA256.fullmatch(value) is None
            for value in (
                args.expected_runtime_train_sha256,
                args.expected_runtime_validation_sha256,
                args.expected_mtop_development_sha256,
                args.expected_product_catalog_sha256,
                args.expected_mtop_map_sha256,
            )
        )
    ):
        parser.error("training/calibration parameters are outside safe bounds")
    for input_path in (
        args.runtime_train,
        args.runtime_validation,
        args.mtop_development,
        args.mtop_map,
        args.product_catalog,
        args.output,
    ):
        _assert_development_input_path(input_path)
    _assert_development_input_path(args.cache_directory / "development-cache")
    if args.output.suffix.casefold() != ".json":
        parser.error("development artifact output must be JSON")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    artifact = run_training(parse_args(argv))
    print(
        json.dumps(
            {
                "schema": artifact["schema"],
                "status": artifact["status"],
                "output_contains_text": artifact["privacy"]["contains_text"],
                "evaluation": artifact["metrics"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
