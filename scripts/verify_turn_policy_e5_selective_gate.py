"""Verify the already-produced E5 selective-development evidence chain.

This verifier is intentionally incapable of training or promotion.  It reads
only aggregate, text-free evidence plus the small manifests and source files
whose hashes were frozen before the run.  It never opens a corpus, holdout,
sealed reserve, embedding cache, or installed runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREGISTRATION = (
    ROOT
    / "artifacts"
    / "development"
    / "turn_policy_e5_selective_v3_preregistration.json"
)
DEFAULT_EVALUATION = (
    ROOT
    / "artifacts"
    / "development"
    / "turn_policy_e5_selective_v3_development.json"
)
DEFAULT_PRIOR_REJECTION = (
    ROOT
    / "artifacts"
    / "development"
    / "turn_policy_e5_development.rejection.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts"
    / "development"
    / "turn_policy_e5_selective_v3_gate.json"
)

# These pins bind the command-line default to the single v3 run that was
# preregistered and already executed.  A synthetic or future chain must supply
# its own explicit pins; silently accepting a different file would make the
# verification self-referential.
DEFAULT_PREREGISTRATION_SHA256 = (
    "8422e33cccf5608089e051d1356e23c811f056a0730260f60d0716cf013fec16"
)
DEFAULT_EVALUATION_SHA256 = (
    "920fd8cdf1fab2b70f095f0b399c70fc207f19f62504e6e8f42d4e5a77b20484"
)
DEFAULT_PRIOR_REJECTION_SHA256 = (
    "685c1c012f4ba8b0587b32aeaa7d83279cd4c5267f6ef817de4566e1f27fd2f4"
)

GATE_SCHEMA = "baxy.turn-policy-e5-selective-development-gate.v2"
PREREGISTRATION_SCHEMA = "baxy.turn-policy-e5-selective-preregistration.v1"
EVALUATION_SCHEMA = "baxy.turn-policy-e5-development.v2"
REJECTION_SCHEMA = "baxy.turn-policy-development-rejection.v1"
RUNTIME_MANIFEST_SCHEMA = "baxy.turn-policy-runtime-development-manifest.v1"
MTOP_MANIFEST_SCHEMA = "baxy.mtop-development-manifest.v1"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_LABEL = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_OPERATION = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+$")
_MAX_AGGREGATE_BYTES = 8 * 1024 * 1024
_MAX_SOURCE_SCAN_BYTES = 16 * 1024 * 1024


class VerificationError(ValueError):
    """The aggregate evidence chain is malformed, unbound, or unsafe."""


@dataclass(slots=True)
class PrivacyStats:
    containers: int = 0
    scalar_values: int = 0
    maximum_depth: int = 0


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: object, *, pretty: bool = False) -> bytes:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return (payload + "\n").encode("utf-8")


def write_json_atomic(path: Path, value: object) -> None:
    payload = canonical_json_bytes(value, pretty=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def report_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return resolved.name


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise VerificationError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_aggregate_json(path: Path, expected_schema: str) -> dict[str, Any]:
    size = path.stat().st_size
    if size < 2 or size > _MAX_AGGREGATE_BYTES:
        raise VerificationError(f"aggregate artifact has unsafe size: {path.name}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda token: (_ for _ in ()).throw(
                VerificationError(f"non-finite JSON number: {token}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read aggregate JSON: {path.name}") from error
    if not isinstance(value, dict) or value.get("schema") != expected_schema:
        raise VerificationError(f"unexpected schema in {path.name}")
    return value


def _require_mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise VerificationError(f"{field} must be an object")
    return value


def _require_list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise VerificationError(f"{field} must be an array")
    return value


def _require_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise VerificationError(f"{field} must be a lowercase SHA-256")
    return value


def _repo_file(root: Path, declared: object, field: str) -> Path:
    if not isinstance(declared, str) or not declared:
        raise VerificationError(f"{field} must be a repository path")
    pure = Path(*declared.replace("\\", "/").split("/"))
    if pure.is_absolute() or ".." in pure.parts:
        raise VerificationError(f"{field} escapes the repository")
    candidate = (root / pure).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise VerificationError(f"{field} escapes the repository") from error
    if not candidate.is_file():
        raise VerificationError(f"declared file is absent: {field}")
    return candidate


# The v2 result is allowed to contain only this recursively enumerated,
# aggregate schema.  Unknown fields are rejected even when the top-level
# privacy flags claim that text is absent.
_OBJECT_KEYS: dict[tuple[str, ...], frozenset[str]] = {
    (): frozenset(
        {
            "catalog",
            "conformal",
            "constraints",
            "encoder",
            "exclusions",
            "groups",
            "heads",
            "integrity",
            "metrics",
            "privacy",
            "protocol",
            "schema",
            "selective_guards",
            "sources",
            "status",
            "training",
        }
    ),
    ("privacy",): frozenset(
        {
            "contains_derived_model_parameters",
            "contains_mission_ids",
            "contains_model_responses",
            "contains_source_ids",
            "contains_text",
        }
    ),
    ("constraints",): frozenset(
        {
            "execution_authority",
            "grouped_by_mission_id_before_fit_and_evaluation",
            "mission_disjoint_calibration_and_evaluation",
            "mtop_candidate_is_advisory_only",
            "normalized_text_split_overlap",
            "ood_can_authorize_fast_chat",
            "requires_independent_llm_selection",
            "requires_schema_grounding_risk_confirmation_and_core_verification",
            "sealed_final_test_reserve_opened",
            "selective_signal_can_authorize_execution",
            "used_splits",
            "utterance_level_fit_and_evaluation",
            "v4_opened",
        }
    ),
    ("sources", "[]"): frozenset(
        {
            "contains_test",
            "embedding_array_sha256",
            "embedding_cache_manifest_sha256",
            "name",
            "row_fingerprint_sha256",
            "rows",
            "sha256",
        }
    ),
    ("catalog",): frozenset(
        {"families", "mtop_projection_map", "public_operations", "sha256"}
    ),
    ("catalog", "mtop_projection_map"): frozenset(
        {"ood_intents", "sha256", "supported_intents"}
    ),
    ("encoder",): frozenset(
        {
            "file_count",
            "manifest_algorithm",
            "manifest_sha256",
            "model",
            "normalize_embeddings",
            "query_prefix",
            "revision",
            "weights",
        }
    ),
    ("encoder", "weights"): frozenset({"path", "sha256"}),
    ("training",): frozenset(
        {
            "effect_c",
            "family_c",
            "fit_unit",
            "linear_solver",
            "maximum_families",
            "maximum_operations",
            "no_effect_c",
            "operation_c",
            "sample_weight",
            "selective_guard_delta",
            "validation_seed_sha256",
        }
    ),
    ("protocol",): frozenset(
        {
            "ambiguous_mtop_contract_structure_mismatch",
            "calibration_split",
            "conformal_alpha",
            "conformal_calibration",
            "conversation_fast_path_requires",
            "corrected_missing_information",
            "effect_classes",
            "embedding_cache_v1_reuse",
            "evaluation_split",
            "hierarchical_disposition_binding",
            "hierarchy",
            "mtop_ood_negative_requires",
            "no_effect_classes",
            "outcome_classes",
            "selective_guard_comparator",
            "unsupported_ood_fast_path",
        }
    ),
    ("groups",): frozenset(
        {
            "calibration",
            "calibration_fingerprint_sha256",
            "evaluation",
            "evaluation_fingerprint_sha256",
            "train",
            "train_fingerprint_sha256",
        }
    ),
    ("heads",): frozenset(
        {
            "effect_gate",
            "family_shortlist",
            "no_effect_disposition",
            "operation_shortlist",
        }
    ),
    ("heads", "*"): frozenset(
        {
            "classes",
            "coefficients",
            "dimensions",
            "intercepts",
            "kind",
            "weights_sha256",
        }
    ),
    ("conformal",): frozenset(
        {"effect_gate", "family", "no_effect_disposition", "operation"}
    ),
    ("conformal", "effect_gate"): frozenset(
        {"calibration", "nonconformity", "thresholds"}
    ),
    ("conformal", "effect_gate", "thresholds"): frozenset(
        {"no_effect", "supported_effect"}
    ),
    ("conformal", "no_effect_disposition"): frozenset(
        {"calibration", "nonconformity", "thresholds"}
    ),
    ("conformal", "no_effect_disposition", "thresholds"): frozenset(
        {"conversation_no_effect", "unsupported_ood"}
    ),
    ("conformal", "family"): frozenset({"nonconformity", "threshold"}),
    ("conformal", "operation"): frozenset({"nonconformity", "threshold"}),
    ("selective_guards",): frozenset(
        {"conversation_fast_path", "supported_effect"}
    ),
    ("selective_guards", "*"): frozenset(
        {
            "calibration_false_accepts",
            "calibration_missions",
            "threshold",
            "tolerance_delta",
            "wilks_upper_rate",
        }
    ),
    ("exclusions",): frozenset(
        {
            "cross_split_conflicting_exact_text_missions_removed",
            "cross_split_conflicting_exact_text_rows_removed",
            "mtop_contract_structure_mismatch_ambiguous",
        }
    ),
    ("metrics",): frozenset(
        {
            "effect_gate",
            "family_shortlist",
            "groups",
            "mission_level",
            "no_effect_disposition",
            "operation_shortlist",
            "per_dataset",
            "per_locale",
            "selective_outcome",
            "utterances",
            "worst_locale",
        }
    ),
    ("metrics", "effect_gate"): frozenset(
        {
            "mission_all_variants_coverage",
            "utterance_coverage",
            "utterance_singleton_accuracy",
        }
    ),
    ("metrics", "family_shortlist"): frozenset(
        {"abstention_rate", "coverage", "maximum_size", "trials"}
    ),
    ("metrics", "mission_level"): frozenset(
        {
            "all_variants_correct",
            "any_variant_selected",
            "missions",
            "missions_with_directional_error",
        }
    ),
    ("metrics", "no_effect_disposition"): frozenset(
        {
            "mission_all_variants_coverage",
            "utterance_coverage",
            "utterance_singleton_accuracy",
            "utterances",
        }
    ),
    ("metrics", "operation_shortlist"): frozenset(
        {"abstention_rate", "coverage", "maximum_size", "trials"}
    ),
    ("metrics", "per_dataset"): frozenset({"mtop_official", "runtime_public"}),
    ("metrics", "per_locale"): frozenset({"en", "es", "und"}),
    ("metrics", "slice"): frozenset(
        {
            "accuracy_when_selected",
            "selection_rate",
            "unsafe_directional_errors",
            "utterances",
        }
    ),
    ("metrics", "selective_outcome"): frozenset(
        {
            "abstention_rate",
            "accuracy_when_selected",
            "correct_utterance_rate",
            "directional_safety",
            "per_class",
            "selection_rate",
        }
    ),
    ("metrics", "selective_outcome", "directional_safety"): frozenset(
        {
            "unsafe_conversation_as_supported",
            "unsafe_conversation_as_supported_rate",
            "unsafe_false_supported",
            "unsafe_false_supported_rate",
            "unsafe_ood_as_conversation",
            "unsafe_ood_as_conversation_rate",
            "unsafe_ood_as_supported",
            "unsafe_ood_as_supported_rate",
            "unsafe_supported_as_conversation",
            "unsafe_supported_as_conversation_rate",
        }
    ),
    ("metrics", "selective_outcome", "per_class"): frozenset(
        {"conversation_no_effect", "supported_effect", "unsupported_ood"}
    ),
    ("metrics", "class"): frozenset(
        {"correct_utterance_rate", "selection_rate", "utterances"}
    ),
    ("metrics", "worst_locale"): frozenset(
        {"accuracy_when_selected", "maximum_directional_errors", "selection_rate"}
    ),
    ("integrity",): frozenset(
        {"algorithm", "evidence_payload_sha256", "policy_payload_sha256"}
    ),
}

_HEAD_NAMES = frozenset(
    {"effect_gate", "family_shortlist", "no_effect_disposition", "operation_shortlist"}
)
_GUARD_NAMES = frozenset({"conversation_fast_path", "supported_effect"})
_SLICE_PARENTS = frozenset({"per_dataset", "per_locale"})
_CLASS_NAMES = frozenset(
    {"conversation_no_effect", "supported_effect", "unsupported_ood"}
)


def _shape_key(path: tuple[str, ...]) -> tuple[str, ...]:
    if len(path) == 2 and path[0] == "heads" and path[1] in _HEAD_NAMES:
        return ("heads", "*")
    if (
        len(path) == 2
        and path[0] == "selective_guards"
        and path[1] in _GUARD_NAMES
    ):
        return ("selective_guards", "*")
    if (
        len(path) == 3
        and path[0] == "metrics"
        and path[1] in _SLICE_PARENTS
    ):
        return ("metrics", "slice")
    if (
        len(path) == 4
        and path[:3] == ("metrics", "selective_outcome", "per_class")
        and path[3] in _CLASS_NAMES
    ):
        return ("metrics", "class")
    return path


def _is_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _validate_string_leaf(value: str, path: tuple[str, ...]) -> None:
    joined = ".".join(path)
    if path[-1].endswith("sha256") or path[-1] == "revision":
        expected = 40 if path[-1] == "revision" else 64
        if len(value) != expected or re.fullmatch(r"[0-9a-f]+", value) is None:
            raise VerificationError(f"privacy allowlist rejected {joined}")
        return
    if path == ("schema",) and value == EVALUATION_SCHEMA:
        return
    if path == ("status",) and value == "development_only_not_runtime_authority":
        return
    if path == ("integrity", "algorithm") and value == "sha256_canonical_json_utf8_lf":
        return
    if path == ("encoder", "model") and value == "intfloat/multilingual-e5-small":
        return
    if path == ("encoder", "query_prefix") and value == "query: ":
        return
    if path == ("encoder", "weights", "path") and value == "model.safetensors":
        return
    if path == ("encoder", "manifest_algorithm"):
        if (
            value
            == "sha256(UTF-8/LF/final-LF lines: model, revision, then every file "
            "sorted by relative POSIX path UTF-8 bytes as "
            "path<TAB>size<TAB>sha256)"
        ):
            return
    if len(path) == 3 and path[:2] == ("heads", path[1]) and path[2] == "kind":
        if value in {"softmax", "one_vs_rest"}:
            return
    if len(path) == 4 and path[:1] == ("heads",) and path[2] == "classes":
        head = path[1]
        if head == "operation_shortlist" and _OPERATION.fullmatch(value):
            return
        if head == "family_shortlist" and _SAFE_LABEL.fullmatch(value):
            return
        if head == "effect_gate" and value in {"no_effect", "supported_effect"}:
            return
        if head == "no_effect_disposition" and value in {
            "conversation_no_effect",
            "unsupported_ood",
        }:
            return
    if len(path) == 3 and path == ("sources", "[]", "name"):
        if value in {"runtime_train", "runtime_validation", "mtop_development"}:
            return
    exact_atoms: dict[tuple[str, ...], frozenset[str]] = {
        ("constraints", "used_splits", "[]"): frozenset({"train", "validation"}),
        ("protocol", "effect_classes", "[]"): frozenset(
            {"no_effect", "supported_effect"}
        ),
        ("protocol", "no_effect_classes", "[]"): frozenset(
            {"conversation_no_effect", "unsupported_ood"}
        ),
        ("protocol", "outcome_classes", "[]"): frozenset(
            {"conversation_no_effect", "unsupported_ood", "supported_effect"}
        ),
        ("training", "fit_unit"): frozenset(
            {"utterance_l2_normalized_mission_disjoint"}
        ),
        ("training", "linear_solver"): frozenset({"lbfgs"}),
        ("training", "sample_weight"): frozenset(
            {"equal_head_target_source_mass_then_inverse_mission_variants"}
        ),
        ("conformal", "effect_gate", "calibration"): frozenset(
            {"label_conditional_by_mission"}
        ),
        ("conformal", "effect_gate", "nonconformity"): frozenset(
            {"mission_max_over_utterances_of_1-p_true"}
        ),
        ("conformal", "no_effect_disposition", "calibration"): frozenset(
            {"label_conditional_by_mission"}
        ),
        ("conformal", "no_effect_disposition", "nonconformity"): frozenset(
            {"mission_max_over_utterances_of_1-p_true"}
        ),
        ("conformal", "family", "nonconformity"): frozenset(
            {"mission_max_over_utterances_of_1-min_true_probability"}
        ),
        ("conformal", "operation", "nonconformity"): frozenset(
            {"mission_max_over_utterances_of_1-min_true_probability"}
        ),
        ("protocol", "ambiguous_mtop_contract_structure_mismatch"): frozenset(
            {"excluded"}
        ),
        ("protocol", "calibration_split"): frozenset(
            {"validation_mission_partition_by_outcome_source_stage"}
        ),
        ("protocol", "conformal_calibration"): frozenset(
            {"label_conditional_worst_utterance_per_mission"}
        ),
        ("protocol", "conversation_fast_path_requires"): frozenset(
            {"effect_no_effect_singleton_and_conversation_singleton_and_guard"}
        ),
        ("protocol", "corrected_missing_information"): frozenset(
            {"supported_effect_requires_clarify"}
        ),
        ("protocol", "embedding_cache_v1_reuse"): frozenset(
            {"encoder_rows_only_disposition_cannot_change_embeddings"}
        ),
        ("protocol", "evaluation_split"): frozenset(
            {"disjoint_validation_missions_evaluated_per_utterance"}
        ),
        ("protocol", "hierarchical_disposition_binding"): frozenset(
            {"pinned_source_projection_map_and_v2_group_fingerprint"}
        ),
        ("protocol", "hierarchy"): frozenset(
            {"effect_gate_then_no_effect_disposition"}
        ),
        ("protocol", "mtop_ood_negative_requires"): frozenset(
            {"mapped_intent_in_reviewed_ood_partition"}
        ),
        ("protocol", "selective_guard_comparator"): frozenset(
            {"strictly_greater_than"}
        ),
        ("protocol", "unsupported_ood_fast_path"): frozenset({"forbidden"}),
    }
    if value in exact_atoms.get(path, frozenset()):
        return
    raise VerificationError(f"privacy allowlist rejected {joined}")


def validate_privacy_allowlist(artifact: Mapping[str, Any]) -> dict[str, Any]:
    stats = PrivacyStats()

    def visit(value: object, path: tuple[str, ...], depth: int) -> None:
        if depth > 12:
            raise VerificationError("privacy allowlist maximum depth exceeded")
        stats.maximum_depth = max(stats.maximum_depth, depth)
        if isinstance(value, dict):
            stats.containers += 1
            allowed = _OBJECT_KEYS.get(_shape_key(path))
            if allowed is None:
                raise VerificationError(
                    f"privacy allowlist has no object rule for {'.'.join(path)}"
                )
            actual = frozenset(value)
            if actual != allowed:
                unknown = sorted(actual - allowed)
                missing = sorted(allowed - actual)
                detail = unknown[0] if unknown else f"missing:{missing[0]}"
                raise VerificationError(
                    f"privacy allowlist rejected {'.'.join(path) or '<root>'}.{detail}"
                )
            for key in sorted(value):
                visit(value[key], (*path, key), depth + 1)
            return
        if isinstance(value, list):
            stats.containers += 1
            if len(value) > 4096:
                raise VerificationError(
                    f"privacy allowlist oversized array at {'.'.join(path)}"
                )
            if path == ("sources",):
                for item in value:
                    visit(item, ("sources", "[]"), depth + 1)
                return
            if path in {
                ("constraints", "used_splits"),
                ("protocol", "effect_classes"),
                ("protocol", "no_effect_classes"),
                ("protocol", "outcome_classes"),
            }:
                for item in value:
                    visit(item, (*path, "[]"), depth + 1)
                return
            if len(path) == 3 and path[0] == "heads" and path[2] in {
                "classes",
                "coefficients",
                "intercepts",
            }:
                for item in value:
                    visit(item, (*path, "[]"), depth + 1)
                return
            if len(path) == 4 and path[0] == "heads" and path[2] == "coefficients":
                for item in value:
                    visit(item, (*path, "[]"), depth + 1)
                return
            raise VerificationError(
                f"privacy allowlist rejected array at {'.'.join(path)}"
            )
        stats.scalar_values += 1
        if value is None:
            raise VerificationError(
                f"privacy allowlist rejected null at {'.'.join(path)}"
            )
        if isinstance(value, str):
            _validate_string_leaf(value, path)
        elif isinstance(value, bool):
            return
        elif not _is_number(value):
            raise VerificationError(
                f"privacy allowlist rejected scalar at {'.'.join(path)}"
            )

    visit(dict(artifact), (), 0)
    privacy = _require_mapping(artifact.get("privacy"), "privacy")
    expected_privacy = {
        "contains_text": False,
        "contains_source_ids": False,
        "contains_mission_ids": False,
        "contains_model_responses": False,
        "contains_derived_model_parameters": True,
    }
    if dict(privacy) != expected_privacy:
        raise VerificationError("artifact privacy declarations are not fail-closed")
    return {
        "recursive_allowlist": True,
        "unknown_paths": 0,
        "containers_checked": stats.containers,
        "scalar_values_checked": stats.scalar_values,
        "maximum_depth": stats.maximum_depth,
        "contains_text": False,
        "contains_source_ids": False,
        "contains_mission_ids": False,
        "contains_model_responses": False,
    }


def _resolve_path(value: Mapping[str, Any], declared: str) -> tuple[bool, Any]:
    if not declared or any(not segment for segment in declared.split(".")):
        return False, None
    current: Any = value
    for segment in declared.split("."):
        if not isinstance(current, dict) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _numeric(value: object, field: str) -> float:
    if not _is_number(value):
        raise VerificationError(f"{field} is not a finite number")
    return float(value)


def evaluate_preregistered_criteria(
    preregistration: Mapping[str, Any],
    evaluation: Mapping[str, Any],
) -> dict[str, Any]:
    acceptance = _require_mapping(preregistration.get("acceptance"), "acceptance")
    exact_paths = _require_list(acceptance.get("exact_zero_counts"), "exact_zero_counts")
    minimums = _require_mapping(acceptance.get("minimums"), "minimums")
    maximums = _require_mapping(acceptance.get("maximums"), "maximums")
    constraints = _require_mapping(
        acceptance.get("required_constraints"), "required_constraints"
    )
    if not exact_paths or not minimums or not maximums or not constraints:
        raise VerificationError("preregistered acceptance criteria cannot be empty")

    missing_paths: list[str] = []
    groups: dict[str, list[dict[str, Any]]] = {
        "exact_zero_counts": [],
        "minimums": [],
        "maximums": [],
        "required_constraints": [],
    }

    for raw_path in exact_paths:
        if not isinstance(raw_path, str):
            raise VerificationError("exact-zero path must be a string")
        resolved, observed = _resolve_path(evaluation, raw_path)
        passed = resolved and _is_number(observed) and float(observed) == 0.0
        if not resolved:
            missing_paths.append(raw_path)
        groups["exact_zero_counts"].append(
            {
                "path": raw_path,
                "resolved": resolved,
                "expected": 0,
                "observed": observed if resolved and _is_number(observed) else None,
                "passed": passed,
            }
        )

    for name, declared_group, comparator in (
        ("minimums", minimums, "at_least"),
        ("maximums", maximums, "at_most"),
    ):
        for raw_path in sorted(declared_group):
            threshold = _numeric(declared_group[raw_path], f"{name}.{raw_path}")
            resolved, observed = _resolve_path(evaluation, raw_path)
            if not resolved:
                missing_paths.append(raw_path)
                passed = False
                observed_output = None
            elif not _is_number(observed):
                passed = False
                observed_output = None
            else:
                observed_output = float(observed)
                passed = (
                    observed_output >= threshold
                    if comparator == "at_least"
                    else observed_output <= threshold
                )
            groups[name].append(
                {
                    "path": raw_path,
                    "resolved": resolved,
                    "comparator": comparator,
                    "threshold": threshold,
                    "observed": observed_output,
                    "passed": passed,
                }
            )

    for raw_path in sorted(constraints):
        expected = constraints[raw_path]
        if not isinstance(expected, (bool, int, float, str)) or expected is None:
            raise VerificationError("constraint expectation must be scalar")
        resolved, observed = _resolve_path(evaluation, raw_path)
        if not resolved:
            missing_paths.append(raw_path)
        groups["required_constraints"].append(
            {
                "path": raw_path,
                "resolved": resolved,
                "expected": expected,
                "observed": observed if resolved else None,
                "passed": resolved
                and type(observed) is type(expected)
                and observed == expected,
            }
        )

    all_checks = [entry for entries in groups.values() for entry in entries]
    return {
        "criteria": groups,
        "declared_paths": len(all_checks),
        "missing_paths": sorted(set(missing_paths)),
        "all_paths_resolve": not missing_paths,
        "all_criteria_pass": all(entry["passed"] for entry in all_checks),
        "failed_paths": sorted(
            entry["path"] for entry in all_checks if not entry["passed"]
        ),
    }


def _verify_internal_integrity(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    heads = _require_mapping(evaluation.get("heads"), "heads")
    head_checks: dict[str, bool] = {}
    for name in sorted(_HEAD_NAMES):
        head = dict(_require_mapping(heads.get(name), f"heads.{name}"))
        declared = _require_sha256(
            head.pop("weights_sha256", None), f"heads.{name}.weights_sha256"
        )
        head_checks[name] = hashlib.sha256(canonical_json_bytes(head)).hexdigest() == declared

        classes = _require_list(head.get("classes"), f"heads.{name}.classes")
        coefficients = _require_list(
            head.get("coefficients"), f"heads.{name}.coefficients"
        )
        intercepts = _require_list(head.get("intercepts"), f"heads.{name}.intercepts")
        dimensions = head.get("dimensions")
        if (
            not isinstance(dimensions, int)
            or isinstance(dimensions, bool)
            or dimensions < 1
            or len(classes) != len(coefficients)
            or len(classes) != len(intercepts)
            or not all(
                isinstance(row, list)
                and len(row) == dimensions
                and all(_is_number(value) for value in row)
                for row in coefficients
            )
            or not all(_is_number(value) for value in intercepts)
        ):
            raise VerificationError(f"heads.{name} has inconsistent dimensions")

    integrity = _require_mapping(evaluation.get("integrity"), "integrity")
    if integrity.get("algorithm") != "sha256_canonical_json_utf8_lf":
        raise VerificationError("unsupported internal integrity algorithm")
    policy_payload = {
        key: evaluation[key]
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
        key: evaluation[key]
        for key in ("sources", "groups", "exclusions", "metrics")
    }
    policy_matches = hashlib.sha256(canonical_json_bytes(policy_payload)).hexdigest() == (
        _require_sha256(
            integrity.get("policy_payload_sha256"),
            "integrity.policy_payload_sha256",
        )
    )
    evidence_matches = hashlib.sha256(
        canonical_json_bytes(evidence_payload)
    ).hexdigest() == _require_sha256(
        integrity.get("evidence_payload_sha256"),
        "integrity.evidence_payload_sha256",
    )
    if not all(head_checks.values()) or not policy_matches or not evidence_matches:
        raise VerificationError("evaluation internal integrity mismatch")
    return {
        "head_weight_payloads": head_checks,
        "policy_payload": policy_matches,
        "evidence_payload": evidence_matches,
    }


def _verify_declared_files(
    root: Path,
    preregistration: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    frozen = _require_mapping(
        preregistration.get("frozen_inputs"), "frozen_inputs"
    )
    declared_file_names = (
        "runtime_development_manifest",
        "mtop_development_manifest",
        "mtop_projection_map",
        "product_catalog",
        "trainer",
        "unit_tests",
    )
    checks: dict[str, Any] = {}
    resolved: dict[str, Path] = {}
    for name in declared_file_names:
        entry = _require_mapping(frozen.get(name), f"frozen_inputs.{name}")
        path = _repo_file(root, entry.get("repo_path"), f"frozen_inputs.{name}.repo_path")
        declared_hash = _require_sha256(
            entry.get("sha256"), f"frozen_inputs.{name}.sha256"
        )
        actual_hash = file_sha256(path)
        matches = actual_hash == declared_hash
        checks[name] = {
            "repo_path": report_path(path, root),
            "declared_sha256": declared_hash,
            "actual_sha256": actual_hash,
            "matches": matches,
        }
        resolved[name] = path
    # ProductCatalog.cs may move after this consumed development seal. Artifact
    # cross-binds still require the frozen catalog hash to agree with the
    # evaluation and MTOP manifests; the live file is historical evidence.
    live_blocking = (
        name
        for name, check in checks.items()
        if name != "product_catalog" and not check["matches"]
    )
    if any(True for _ in live_blocking):
        raise VerificationError("a preregistered repository file hash changed")

    runtime_manifest = load_aggregate_json(
        resolved["runtime_development_manifest"], RUNTIME_MANIFEST_SCHEMA
    )
    mtop_manifest = load_aggregate_json(
        resolved["mtop_development_manifest"], MTOP_MANIFEST_SCHEMA
    )
    return checks, runtime_manifest, mtop_manifest


def _cross_bind_sources(
    preregistration: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    rejection: Mapping[str, Any],
    runtime_manifest: Mapping[str, Any],
    mtop_manifest: Mapping[str, Any],
) -> dict[str, bool]:
    frozen = _require_mapping(preregistration.get("frozen_inputs"), "frozen_inputs")

    def frozen_sha(name: str) -> str:
        return _require_sha256(
            _require_mapping(frozen.get(name), f"frozen_inputs.{name}").get("sha256"),
            f"frozen_inputs.{name}.sha256",
        )

    runtime_outputs = _require_mapping(runtime_manifest.get("outputs"), "runtime outputs")
    runtime_train = _require_mapping(runtime_outputs.get("train"), "runtime train")
    runtime_validation = _require_mapping(
        runtime_outputs.get("validation"), "runtime validation"
    )
    mtop_output = _require_mapping(mtop_manifest.get("output"), "mtop output")
    mtop_catalog = _require_mapping(mtop_manifest.get("catalog"), "mtop catalog")
    mtop_source = _require_mapping(mtop_manifest.get("source"), "mtop source")

    source_rows = _require_list(evaluation.get("sources"), "evaluation.sources")
    sources: dict[str, Mapping[str, Any]] = {}
    for raw in source_rows:
        source = _require_mapping(raw, "evaluation source")
        name = source.get("name")
        if not isinstance(name, str) or name in sources:
            raise VerificationError("evaluation source names are invalid")
        sources[name] = source
    if set(sources) != {"runtime_train", "runtime_validation", "mtop_development"}:
        raise VerificationError("evaluation source set changed")

    evaluation_catalog = _require_mapping(evaluation.get("catalog"), "catalog")
    evaluation_map = _require_mapping(
        evaluation_catalog.get("mtop_projection_map"), "mtop_projection_map"
    )
    iteration = _require_mapping(
        preregistration.get("iteration_control"), "iteration_control"
    )
    rejection_artifact = _require_mapping(rejection.get("artifact"), "rejection.artifact")
    rejection_constraints = _require_mapping(
        rejection.get("constraints"), "rejection.constraints"
    )

    bindings = {
        "runtime_train_preregistration_to_manifest": (
            frozen_sha("runtime_train")
            == _require_sha256(runtime_train.get("sha256"), "runtime train sha256")
        ),
        "runtime_validation_preregistration_to_manifest": (
            frozen_sha("runtime_validation")
            == _require_sha256(
                runtime_validation.get("sha256"), "runtime validation sha256"
            )
        ),
        "mtop_development_preregistration_to_manifest": (
            frozen_sha("mtop_development")
            == _require_sha256(mtop_output.get("sha256"), "mtop output sha256")
        ),
        "runtime_train_evaluation_source": (
            frozen_sha("runtime_train")
            == _require_sha256(sources["runtime_train"].get("sha256"), "source sha")
        ),
        "runtime_validation_evaluation_source": (
            frozen_sha("runtime_validation")
            == _require_sha256(
                sources["runtime_validation"].get("sha256"), "source sha"
            )
        ),
        "mtop_development_evaluation_source": (
            frozen_sha("mtop_development")
            == _require_sha256(sources["mtop_development"].get("sha256"), "source sha")
        ),
        "all_evaluation_sources_exclude_test": all(
            source.get("contains_test") is False for source in sources.values()
        ),
        "catalog_manifest_to_preregistration": (
            frozen_sha("product_catalog")
            == _require_sha256(mtop_catalog.get("sha256"), "mtop catalog sha")
        ),
        "catalog_evaluation_to_preregistration": (
            frozen_sha("product_catalog")
            == _require_sha256(evaluation_catalog.get("sha256"), "catalog sha")
        ),
        "projection_map_manifest_to_preregistration": (
            frozen_sha("mtop_projection_map")
            == _require_sha256(mtop_source.get("map_sha256"), "mtop map sha")
        ),
        "projection_map_evaluation_to_preregistration": (
            frozen_sha("mtop_projection_map")
            == _require_sha256(evaluation_map.get("sha256"), "evaluation map sha")
        ),
        "prior_rejection_to_preregistered_iteration": (
            _require_sha256(rejection_artifact.get("sha256"), "rejection artifact sha")
            == _require_sha256(
                iteration.get("prior_binary_artifact_sha256"),
                "prior binary artifact sha",
            )
        ),
        "prior_rejection_not_runtime_authority": (
            rejection.get("status") == "rejected_not_runtime_authority"
            and rejection_constraints.get("runtime_loaded") is False
            and rejection_constraints.get("execution_authority") is False
            and rejection_constraints.get("sealed_final_test_opened") is False
            and rejection_constraints.get("mtop_official_test_opened") is False
        ),
    }
    if not all(bindings.values()):
        raise VerificationError("aggregate evidence source binding mismatch")
    return bindings


def _scan_runtime_promotion_references(
    root: Path,
    evaluation_path: Path,
    evaluation_sha256: str,
) -> dict[str, Any]:
    source_root = root / "src"
    if not source_root.is_dir():
        raise VerificationError("runtime source root is absent")
    relative = report_path(evaluation_path, root)
    needles = {
        relative.encode("utf-8"),
        evaluation_path.name.encode("utf-8"),
        evaluation_sha256.encode("ascii"),
        EVALUATION_SCHEMA.encode("ascii"),
    }
    scanned = 0
    hits: list[str] = []
    manifest_lines: list[str] = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in {
            ".cs",
            ".json",
            ".py",
            ".toml",
            ".yaml",
            ".yml",
        }:
            continue
        if path.is_symlink() or path.stat().st_size > _MAX_SOURCE_SCAN_BYTES:
            raise VerificationError("runtime promotion scan encountered unsafe file")
        payload = path.read_bytes()
        scanned += 1
        manifest_lines.append(
            f"{report_path(path, root)}\t{len(payload)}\t{hashlib.sha256(payload).hexdigest()}"
        )
        if any(needle in payload for needle in needles):
            hits.append(report_path(path, root))
    if hits:
        raise VerificationError("development candidate is referenced by runtime source")
    return {
        "source_files_scanned": scanned,
        "source_manifest_sha256": hashlib.sha256(
            ("\n".join(manifest_lines) + "\n").encode("utf-8")
        ).hexdigest(),
        "candidate_reference_hits": [],
        "candidate_reference_absent": True,
    }


def _selection_count(rate: float, utterances: int) -> int:
    estimate = rate * utterances
    nearest = round(estimate)
    # The trainer rounds aggregate rates to eight decimal places.
    if abs(estimate - nearest) > utterances * 0.5e-8 + 1e-12:
        raise VerificationError("selection rate is inconsistent with an integer count")
    return int(nearest)


def build_gate_report(
    *,
    root: Path,
    preregistration_path: Path,
    evaluation_path: Path,
    prior_rejection_path: Path,
    expected_preregistration_sha256: str,
    expected_evaluation_sha256: str,
    expected_prior_rejection_sha256: str,
) -> dict[str, Any]:
    pins = {
        "preregistration": (
            preregistration_path,
            _require_sha256(
                expected_preregistration_sha256, "expected preregistration SHA-256"
            ),
        ),
        "evaluation": (
            evaluation_path,
            _require_sha256(expected_evaluation_sha256, "expected evaluation SHA-256"),
        ),
        "prior_rejection": (
            prior_rejection_path,
            _require_sha256(
                expected_prior_rejection_sha256,
                "expected prior rejection SHA-256",
            ),
        ),
    }
    chain: dict[str, Any] = {}
    for name, (path, expected) in pins.items():
        actual = file_sha256(path)
        if actual != expected:
            raise VerificationError(f"{name} does not match its external pin")
        chain[name] = {
            "repo_path": report_path(path, root),
            "sha256": actual,
            "external_pin_matches": True,
        }

    preregistration = load_aggregate_json(
        preregistration_path, PREREGISTRATION_SCHEMA
    )
    evaluation = load_aggregate_json(evaluation_path, EVALUATION_SCHEMA)
    rejection = load_aggregate_json(prior_rejection_path, REJECTION_SCHEMA)
    if (
        preregistration.get("state") != "locked"
        or evaluation.get("status") != "development_only_not_runtime_authority"
    ):
        raise VerificationError("development evidence state is not locked and non-runtime")

    prereg_output = _require_mapping(preregistration.get("output"), "output")
    declared_evaluation = _repo_file(
        root, prereg_output.get("repo_path"), "output.repo_path"
    )
    if declared_evaluation != evaluation_path.resolve():
        raise VerificationError("evaluation path differs from preregistered output")

    privacy = validate_privacy_allowlist(evaluation)
    internal_integrity = _verify_internal_integrity(evaluation)
    file_checks, runtime_manifest, mtop_manifest = _verify_declared_files(
        root, preregistration
    )
    bindings = _cross_bind_sources(
        preregistration,
        evaluation,
        rejection,
        runtime_manifest,
        mtop_manifest,
    )
    criteria = evaluate_preregistered_criteria(preregistration, evaluation)

    constraints = _require_mapping(evaluation.get("constraints"), "constraints")
    no_promotion_constraints = {
        "development_status": (
            evaluation.get("status") == "development_only_not_runtime_authority"
        ),
        "execution_authority_false": constraints.get("execution_authority") is False,
        "selective_signal_cannot_authorize_execution": (
            constraints.get("selective_signal_can_authorize_execution") is False
        ),
        "independent_llm_selection_required": (
            constraints.get("requires_independent_llm_selection") is True
        ),
        "sealed_final_test_reserve_unopened": (
            constraints.get("sealed_final_test_reserve_opened") is False
        ),
        "v4_unopened": constraints.get("v4_opened") is False,
        "preregistered_run_forbids_official_test": (
            _require_mapping(
                preregistration.get("iteration_control"), "iteration_control"
            ).get("official_mtop_test_may_be_opened_by_this_run")
            is False
        ),
        "preregistered_run_forbids_sealed_holdout": (
            _require_mapping(
                preregistration.get("iteration_control"), "iteration_control"
            ).get("sealed_public_holdout_may_be_opened_by_this_run")
            is False
        ),
    }
    if not all(no_promotion_constraints.values()):
        raise VerificationError("development candidate contains promotion authority")
    promotion_scan = _scan_runtime_promotion_references(
        root, evaluation_path, chain["evaluation"]["sha256"]
    )

    supported_path = (
        "metrics.selective_outcome.per_class.supported_effect.selection_rate"
    )
    supported_rows_path = (
        "metrics.selective_outcome.per_class.supported_effect.utterances"
    )
    rate_found, raw_rate = _resolve_path(evaluation, supported_path)
    rows_found, raw_rows = _resolve_path(evaluation, supported_rows_path)
    if (
        not rate_found
        or not rows_found
        or not _is_number(raw_rate)
        or not isinstance(raw_rows, int)
        or isinstance(raw_rows, bool)
        or raw_rows < 1
    ):
        raise VerificationError("supported-effect selection aggregate is malformed")
    supported_rate = float(raw_rate)
    supported_rows = int(raw_rows)
    supported_selected = _selection_count(supported_rate, supported_rows)

    failed_paths = set(criteria["failed_paths"])
    if supported_path not in failed_paths:
        raise VerificationError(
            "the pinned candidate no longer demonstrates the preregistered "
            "supported-effect selection failure"
        )
    if criteria["all_criteria_pass"]:
        raise VerificationError("pinned rejected candidate unexpectedly passes")

    verifier_path = Path(__file__).resolve()
    return {
        "schema": GATE_SCHEMA,
        "status": "failed_no_runtime_promotion",
        "verifier": {
            "repo_path": report_path(verifier_path, root),
            "sha256": file_sha256(verifier_path),
            "trainer_executed": False,
            "corpus_or_holdout_opened": False,
            "runtime_modified": False,
        },
        "chain": chain,
        "declared_repository_files": file_checks,
        "source_bindings": bindings,
        "internal_integrity": internal_integrity,
        "privacy": privacy,
        "preregistered_evaluation": criteria,
        "observed": {
            "groups": evaluation["metrics"]["groups"],
            "utterances": evaluation["metrics"]["utterances"],
            "supported_effect": {
                "selected": supported_selected,
                "utterances": supported_rows,
                "selection_rate": supported_rate,
                "minimum_preregistered": 0.02,
                "passed": False,
            },
        },
        "promotion_boundary": {
            "constraints": no_promotion_constraints,
            "runtime_source_scan": promotion_scan,
            "runtime_policy_published": False,
            "fast_conversation_path_enabled": False,
            "supported_signal_enabled": False,
            "development_weights_may_authorize_execution": False,
            "official_mtop_test_opened": False,
            "sealed_public_holdout_opened": False,
        },
        "checks": {
            "externally_pinned_aggregate_chain": True,
            "declared_repository_hashes_match": True,
            "manifest_and_source_hashes_cross_bound": True,
            "internal_payload_hashes_match": True,
            "recursive_privacy_allowlist_passed": True,
            "preregistered_paths_resolve": criteria["all_paths_resolve"],
            "preregistered_acceptance_passed": False,
            "supported_selection_rate_at_least_0_02": False,
            "runtime_policy_promotion_reference_absent": True,
        },
        "decision": {
            "reason": "preregistered_acceptance_failed",
            "fallback": "existing_llm_decision_with_one_sided_advisory_evidence",
            "post_evaluation_preregistration_repair_allowed": False,
            "runtime_policy_published": False,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--evaluation", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--prior-rejection", type=Path, default=DEFAULT_PRIOR_REJECTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--expected-preregistration-sha256",
        default=DEFAULT_PREREGISTRATION_SHA256,
    )
    parser.add_argument(
        "--expected-evaluation-sha256",
        default=DEFAULT_EVALUATION_SHA256,
    )
    parser.add_argument(
        "--expected-prior-rejection-sha256",
        default=DEFAULT_PRIOR_REJECTION_SHA256,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_gate_report(
            root=ROOT,
            preregistration_path=args.preregistration.resolve(),
            evaluation_path=args.evaluation.resolve(),
            prior_rejection_path=args.prior_rejection.resolve(),
            expected_preregistration_sha256=args.expected_preregistration_sha256,
            expected_evaluation_sha256=args.expected_evaluation_sha256,
            expected_prior_rejection_sha256=args.expected_prior_rejection_sha256,
        )
        write_json_atomic(args.output.resolve(), report)
    except (OSError, VerificationError) as error:
        print(f"E5 selective gate verification failed: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "output": report_path(args.output, ROOT),
                "supported_selected": report["observed"]["supported_effect"]["selected"],
                "supported_utterances": report["observed"]["supported_effect"][
                    "utterances"
                ],
                "missing_preregistered_paths": report["preregistered_evaluation"][
                    "missing_paths"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
