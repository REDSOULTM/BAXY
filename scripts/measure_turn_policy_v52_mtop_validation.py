"""Development-only v5.2 turn cascade on MTOP validation.

The runner accepts only the hash-bound MTOP development corpus. It trains on
``train``, calibrates and samples disjoint mission groups from ``validation``,
and rejects any other split before inference. Parallel EN/ES rows share a
mission group and can never cross calibration/evaluation or appear twice in
the measured sample. Projections marked ``contract_structure_mismatch`` are
quarantined from trigger training and every measured pool because a supported
intent with missing human arguments should reach grounding/clarification, not
teach the trigger that no effect exists.

No operation is dispatched. Corpus projections are advisory labels only:

    conformal trigger
      -> family selector
      -> adaptive in-family retrieval (cap 8)
      -> exact operation selector
      -> argument-agnostic pair verifier
      -> candidate-free pragmatic veto (deny only)
      -> independent schema grounder (action or clarify)

Artifacts contain hashes, public labels, operation names, stage decisions, and
timings, but no utterance text, grounded values, or raw model response text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
SCRIPTS = REPO / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import measure_turn_policy_v5_validation_cascade as common  # noqa: E402
import run_turn_policy_gate as gate  # noqa: E402
from baxy_mind.planner import (  # noqa: E402
    PlannerCatalog,
    PlannerTool,
    normalize_grounded_arguments,
)
from baxy_mind.router import IntentRouter  # noqa: E402
from baxy_mind.turn_evidence import DEFAULT_ENCODER_IDENTITY  # noqa: E402
from run_turn_evidence_encoder_gate import (  # noqa: E402
    file_sha256,
    macro_f1,
)
from run_turn_linear_probe_gate import configured_cache  # noqa: E402


DEVELOPMENT_CORPUS = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "BAXYRuntime"
    / "datasets"
    / "mtop-v1"
    / "derived"
    / "mtop_development.v1.jsonl"
)
MANIFEST = REPO / "artifacts" / "product" / "mtop_development_manifest.json"
OUTPUT = (
    REPO
    / "artifacts"
    / "validation"
    / "turn_policy_v52_mtop_validation_pilot_64x2.json"
)
EMBEDDING_CACHE = DEVELOPMENT_CORPUS.with_name(
    "mtop_development.v1.multilingual-e5-small.npy"
)
EMBEDDING_METADATA = EMBEDDING_CACHE.with_suffix(".json")
ROUTER_CACHE = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "BAXYRuntime"
    / "turn-evidence"
)
SEED = "baxy-turn-policy-v52-mtop-validation-v1"
ALPHA = 0.05
ROW_SCHEMA = "baxy.mtop-development-row.v1"
MANIFEST_SCHEMA = "baxy.mtop-development-manifest.v1"
EXPECTED_CORPUS_SHA256 = (
    "ed1871262bdb78a53e219ac6ebd7b995879c60eba29ec5d9203217480a142802"
)
EXPECTED_MANIFEST_SHA256 = (
    "3accbab239b1f431f7696203b6e7efabf7176615cbbf17cdbc98d249efe9815d"
)
EXPECTED_MAP_SHA256 = (
    "b13baef00c362ae10d130f359f94d28e0105987db17337795c79d2ea8a951c5d"
)
MAX_OPERATION_CANDIDATES = 8
ADAPTIVE_OPERATION_MASS = 0.98
QUARANTINED_PROJECTION_REASONS = frozenset(
    {"contract_structure_mismatch"}
)
CANDIDATE_DISPOSITIONS = frozenset(
    {"candidate", "candidate_missing_information"}
)


@dataclass(frozen=True)
class FileIdentity:
    path: Path
    bytes: int
    sha256: str


@dataclass(frozen=True)
class DevelopmentInputIdentity:
    corpus: FileIdentity
    manifest: FileIdentity

FAMILY_SELECTOR_PROMPT = (
    "Choose exactly one candidate operation family only when it contains the "
    "kind of operation requested by the user's single digital or external "
    "effect. Return __none__ for conversation, a merely unsupported effect, "
    "multiple independent effects, or ambiguity between families. Current "
    "external information can require an effect. Missing argument values do "
    "not change the operation family because grounding happens later. Never "
    "invent context, effects, or capabilities."
)
OPERATION_SELECTOR_PROMPT = (
    "Within the selected family, choose exactly one candidate operation whose "
    "described effect is the exact semantic match for the user's single "
    "requested effect. Return __none__ for conversation, an unsupported or "
    "adjacent effect, multiple independent effects, or ambiguity. Ignore "
    "whether argument values are missing; a separate schema grounder handles "
    "that later. Never invent context, arguments, or operations."
)
PAIR_VERIFIER_PROMPT = (
    "Judge only the current request and the one proposed operation. Do not "
    "select or suggest alternatives. Treat every human-supplied argument as an "
    "abstract placeholder: missing, ambiguous, or non-canonical argument "
    "values must never make semantic entailment or effect coverage false. "
    "entailed_operation_kind is true only when the request explicitly asks "
    "for this kind of operation. covers_entire_atomic_effect is true only when "
    "this operation kind covers the whole requested atomic effect rather than "
    "an adjacent, preparatory, or partial effect. effect_count is zero, one, "
    "or multiple according to independently requested effects. Never judge "
    "argument completeness and never invent context."
)
PRAGMATIC_VETO_PROMPT = (
    "Classify only the primary speech act of the current utterance without "
    "seeing candidate capabilities. speech_act is request_or_question for a "
    "direct request, command, or information question; assertion_only when "
    "the speaker merely states or discloses something without asking the "
    "assistant to do or answer anything; and other only when neither applies. "
    "explicit_effect_request is true only when the speaker explicitly asks to "
    "read, create, change, or control a current digital or external state or "
    "result. Ignore support and missing arguments. effect_count is zero when "
    "no effect is explicitly requested, one for one atomic effect, and "
    "multiple for two or more independent effects. Never infer a request from "
    "a possible future action and never invent context."
)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _rank(seed: str, identity: str) -> bytes:
    return hashlib.sha256((seed + "\0" + identity).encode("utf-8")).digest()


def _class_label(row: dict[str, Any]) -> str:
    return (
        "candidate"
        if row["projection"]["disposition"] in CANDIDATE_DISPOSITIONS
        else "no_effect"
    )


def _single_operation(row: dict[str, Any]) -> str | None:
    operations = row["projection"]["candidate_operations"]
    return str(operations[0]) if len(operations) == 1 else None


def _is_quarantined_projection(row: dict[str, Any]) -> bool:
    return (
        str(row["projection"]["reason"])
        in QUARANTINED_PROJECTION_REASONS
    )


def _capture_file(path: Path) -> tuple[bytes, FileIdentity]:
    resolved = path.resolve(strict=True)
    payload = resolved.read_bytes()
    return (
        payload,
        FileIdentity(
            path=resolved,
            bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        ),
    )


def _assert_input_identity_stable(
    identity: DevelopmentInputIdentity,
) -> None:
    for label, expected in (
        ("corpus", identity.corpus),
        ("manifest", identity.manifest),
    ):
        try:
            size = expected.path.stat().st_size
            sha256 = file_sha256(expected.path)
        except OSError as error:
            raise RuntimeError(
                f"MTOP {label} disappeared during measurement"
            ) from error
        if size != expected.bytes or sha256 != expected.sha256:
            raise RuntimeError(
                f"MTOP {label} changed during measurement"
            )


def _load_development(
    corpus_path: Path,
    manifest_path: Path,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    DevelopmentInputIdentity,
]:
    manifest_bytes, manifest_identity = _capture_file(manifest_path)
    corpus_bytes, corpus_identity = _capture_file(corpus_path)
    identity = DevelopmentInputIdentity(
        corpus=corpus_identity,
        manifest=manifest_identity,
    )
    manifest = json.loads(manifest_bytes)
    actual_sha256 = corpus_identity.sha256
    output = manifest.get("output") if isinstance(manifest, dict) else None
    source = manifest.get("source") if isinstance(manifest, dict) else None
    constraints = (
        manifest.get("constraints") if isinstance(manifest, dict) else None
    )
    if (
        manifest.get("schema") != MANIFEST_SCHEMA
        or manifest_identity.sha256 != EXPECTED_MANIFEST_SHA256
        or not isinstance(output, dict)
        or output.get("sha256") != actual_sha256
        or actual_sha256 != EXPECTED_CORPUS_SHA256
        or output.get("bytes") != corpus_identity.bytes
        or output.get("file_name") != corpus_identity.path.name
        or not isinstance(source, dict)
        or source.get("map_sha256") != EXPECTED_MAP_SHA256
        or not isinstance(constraints, dict)
        or constraints.get("development_files_only") is not True
        or constraints.get("test_content_read") is not False
        or constraints.get("execution_authority") is not False
        or constraints.get("mission_split_overlap") != 0
        or constraints.get("normalized_text_split_overlap") != 0
    ):
        raise ValueError("MTOP development identity or boundary is invalid")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(corpus_bytes.splitlines(), 1):
        row = json.loads(line)
        projection = row.get("projection") if isinstance(row, dict) else None
        semantic = row.get("semantic") if isinstance(row, dict) else None
        source_id = row.get("source_id") if isinstance(row, dict) else None
        if (
            row.get("schema") != ROW_SCHEMA
            or row.get("split") not in {"train", "validation"}
            or row.get("locale") not in {"en", "es"}
            or not isinstance(row.get("mission_id"), str)
            or not isinstance(source_id, str)
            or source_id in seen
            or not isinstance(row.get("text"), str)
            or not row["text"].strip()
            or not isinstance(projection, dict)
            or projection.get("disposition")
            not in {
                *CANDIDATE_DISPOSITIONS,
                "conversation_no_effect",
                "ood_no_effect",
            }
            or projection.get("execution_authority") is not False
            or not isinstance(
                projection.get("candidate_operations"),
                list,
            )
            or not isinstance(projection.get("reason"), str)
            or not isinstance(semantic, dict)
        ):
            raise ValueError(
                f"invalid MTOP development row at line {line_number}"
            )
        if (
            projection["disposition"] in CANDIDATE_DISPOSITIONS
            and not projection["candidate_operations"]
        ) or (
            projection["disposition"] not in CANDIDATE_DISPOSITIONS
            and projection["candidate_operations"]
        ):
            raise ValueError("MTOP candidate/no-effect projection mismatch")
        seen.add(source_id)
        rows.append(row)
    if len(rows) != output.get("rows"):
        raise ValueError("MTOP development row count changed")
    split_counts = Counter(str(row["split"]) for row in rows)
    if split_counts != {"train": 26_220, "validation": 3_756}:
        raise ValueError("MTOP development splits are unexpected")
    return rows, manifest, identity


def _group_validation(
    validation_rows: Sequence[dict[str, Any]],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    list[str],
]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in validation_rows:
        groups[str(row["mission_id"])].append(row)
    strata: dict[tuple[str, tuple[str, ...]], list[str]] = defaultdict(list)
    conflicts: list[str] = []
    for mission_id, group in groups.items():
        signatures = {
            (
                _class_label(row),
                tuple(row["projection"]["candidate_operations"]),
            )
            for row in group
        }
        if len(signatures) != 1:
            conflicts.append(mission_id)
            continue
        if any(_is_quarantined_projection(row) for row in group):
            continue
        label, operations = next(iter(signatures))
        strata[(label, operations)].append(mission_id)

    calibration_ids: set[str] = set()
    evaluation_ids: set[str] = set()
    for stratum, mission_ids in sorted(strata.items()):
        ranked = sorted(
            mission_ids,
            key=lambda mission_id: (
                _rank(
                    SEED + "\0validation-group\0" + repr(stratum),
                    mission_id,
                ),
                mission_id,
            ),
        )
        cut = max(1, len(ranked) // 2)
        calibration_ids.update(ranked[:cut])
        evaluation_ids.update(ranked[cut:])
    if calibration_ids & evaluation_ids:
        raise ValueError("parallel MTOP groups crossed calibration/evaluation")
    return (
        {key: groups[key] for key in sorted(calibration_ids)},
        {key: groups[key] for key in sorted(evaluation_ids)},
        sorted(conflicts),
    )


def _allocate_quotas(
    capacities: dict[str, int],
    total: int,
) -> dict[str, int]:
    capacities = {key: value for key, value in capacities.items() if value > 0}
    if total > sum(capacities.values()):
        raise ValueError("sample quota exceeds eligible rows")
    keys = sorted(capacities)
    quotas = {key: 0 for key in keys}
    if total >= len(keys):
        for key in keys:
            quotas[key] = 1
        remaining = total - len(keys)
    else:
        for key in keys[:total]:
            quotas[key] = 1
        return quotas
    while remaining:
        spare = {
            key: capacities[key] - quotas[key]
            for key in keys
        }
        spare_total = sum(spare.values())
        ideals = {
            key: remaining * spare[key] / spare_total
            for key in keys
            if spare[key] > 0
        }
        additions = {
            key: min(spare[key], int(math.floor(ideals.get(key, 0.0))))
            for key in keys
        }
        added = sum(additions.values())
        for key, count in additions.items():
            quotas[key] += count
        remaining -= added
        if not remaining:
            break
        ranked = sorted(
            (
                key
                for key in keys
                if quotas[key] < capacities[key]
            ),
            key=lambda key: (
                ideals.get(key, 0.0)
                - math.floor(ideals.get(key, 0.0)),
                spare[key],
                key,
            ),
            reverse=True,
        )
        for key in ranked:
            if not remaining:
                break
            quotas[key] += 1
            remaining -= 1
    return quotas


def _sample_class_locale(
    evaluation_groups: dict[str, list[dict[str, Any]]],
    *,
    wanted_class: str,
    locale: str,
    count: int,
    occupied_missions: set[str],
) -> list[dict[str, Any]]:
    by_stratum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for mission_id, group in evaluation_groups.items():
        if mission_id in occupied_missions:
            continue
        row = next(
            (
                candidate
                for candidate in group
                if candidate["locale"] == locale
            ),
            None,
        )
        if row is None or _class_label(row) != wanted_class:
            continue
        operation = _single_operation(row)
        if wanted_class == "candidate":
            if operation is None:
                continue
            stratum = operation
        else:
            stratum = str(row["projection"]["reason"])
        by_stratum[stratum].append(row)
    quotas = _allocate_quotas(
        {key: len(values) for key, values in by_stratum.items()},
        count,
    )
    selected: list[dict[str, Any]] = []
    for stratum in sorted(by_stratum):
        ranked = sorted(
            by_stratum[stratum],
            key=lambda row: (
                _rank(
                    SEED
                    + "\0sample\0"
                    + wanted_class
                    + "\0"
                    + locale
                    + "\0"
                    + stratum,
                    str(row["mission_id"]),
                ),
                str(row["source_id"]),
            ),
        )
        taken = 0
        for row in ranked:
            mission_id = str(row["mission_id"])
            if mission_id in occupied_missions:
                continue
            selected.append(row)
            occupied_missions.add(mission_id)
            taken += 1
            if taken >= quotas[stratum]:
                break
        if taken != quotas[stratum]:
            raise ValueError("parallel-group exclusion exhausted a sample stratum")
    if len(selected) != count:
        raise ValueError("stratified MTOP sample did not reach its quota")
    return selected


def _sample_evaluation(
    evaluation_groups: dict[str, list[dict[str, Any]]],
    per_class: int,
) -> list[dict[str, Any]]:
    if per_class % 2:
        raise ValueError("per-class sample must split evenly EN/ES")
    occupied: set[str] = set()
    selected: list[dict[str, Any]] = []
    locale_quota = per_class // 2
    for wanted_class in ("candidate", "no_effect"):
        for locale in ("en", "es"):
            selected.extend(
                _sample_class_locale(
                    evaluation_groups,
                    wanted_class=wanted_class,
                    locale=locale,
                    count=locale_quota,
                    occupied_missions=occupied,
                )
            )
    selected.sort(
        key=lambda row: (
            _rank(SEED + "\0sample-order", str(row["mission_id"])),
            str(row["source_id"]),
        )
    )
    if (
        len(selected) != per_class * 2
        or len({row["mission_id"] for row in selected}) != len(selected)
    ):
        raise ValueError("MTOP sample is not mission-group independent")
    return selected


def _embedding_cache_identity(
    corpus_sha256: str,
    rows: int,
) -> dict[str, Any]:
    return {
        "schema": "baxy.mtop-e5-development-cache.v1",
        "contains_text": False,
        "corpus_sha256": corpus_sha256,
        "rows": rows,
        "encoder_identity": DEFAULT_ENCODER_IDENTITY,
        "dimensions": 384,
    }


def _load_or_encode(
    router: IntentRouter,
    rows: Sequence[dict[str, Any]],
    corpus_sha256: str,
    cache_path: Path,
    metadata_path: Path,
) -> tuple[np.ndarray, dict[str, Any], float]:
    expected = _embedding_cache_identity(corpus_sha256, len(rows))
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (
            all(metadata.get(key) == value for key, value in expected.items())
            and metadata.get("vectors_sha256") == file_sha256(cache_path)
        ):
            vectors = np.load(cache_path, allow_pickle=False)
            if vectors.shape == (len(rows), 384):
                return vectors.astype(np.float32, copy=False), metadata, 0.0
    except (OSError, ValueError, json.JSONDecodeError):
        pass

    batches: list[np.ndarray] = []
    started = time.perf_counter()
    for start in range(0, len(rows), 64):
        texts = [
            str(row["text"])
            for row in rows[start : start + 64]
        ]
        matrix = np.asarray(router.encode(texts), dtype=np.float32)
        if matrix.shape != (len(texts), 384):
            raise ValueError("MTOP E5 batch has an unexpected shape")
        batches.append(matrix)
    vectors = np.concatenate(batches, axis=0)
    encode_seconds = time.perf_counter() - started

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_name(
        f".{cache_path.name}.{os.getpid()}.tmp"
    )
    try:
        with temporary.open("wb") as handle:
            np.save(handle, vectors, allow_pickle=False)
        os.replace(temporary, cache_path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)
    metadata = {
        **expected,
        "vectors_sha256": file_sha256(cache_path),
    }
    gate.write_json_atomic(metadata_path, metadata)
    return vectors, metadata, encode_seconds


def _fit_models(
    rows: Sequence[dict[str, Any]],
    vectors: np.ndarray,
) -> tuple[Any, Any, Any]:
    from sklearn.linear_model import LogisticRegression

    train_indices = [
        index
        for index, row in enumerate(rows)
        if row["split"] == "train"
        and not _is_quarantined_projection(row)
    ]
    train_vectors = vectors[train_indices]
    mode_labels = [_class_label(rows[index]) for index in train_indices]
    mode_model = LogisticRegression(
        C=1.0,
        class_weight="balanced",
        solver="lbfgs",
        max_iter=1_000,
        random_state=0,
    )
    mode_model.fit(train_vectors, mode_labels)

    single_indices = [
        index
        for index in train_indices
        if _single_operation(rows[index]) is not None
    ]
    single_vectors = vectors[single_indices]
    operations = [
        str(_single_operation(rows[index]))
        for index in single_indices
    ]
    families = [operation.split(".", 1)[0] for operation in operations]
    family_model = LogisticRegression(
        C=4.0,
        class_weight="balanced",
        solver="lbfgs",
        max_iter=1_000,
        random_state=0,
    )
    family_model.fit(single_vectors, families)
    operation_model = LogisticRegression(
        C=4.0,
        class_weight="balanced",
        solver="lbfgs",
        max_iter=1_000,
        random_state=0,
    )
    operation_model.fit(single_vectors, operations)
    return mode_model, family_model, operation_model


def _mode_quantiles(
    model: Any,
    rows: Sequence[dict[str, Any]],
    vectors: np.ndarray,
    calibration_groups: dict[str, list[dict[str, Any]]],
    row_index: dict[str, int],
) -> dict[str, float]:
    classes = [str(value) for value in model.classes_]
    quantiles: dict[str, float] = {}
    for label in ("candidate", "no_effect"):
        class_index = classes.index(label)
        group_scores: list[float] = []
        for group in calibration_groups.values():
            if _class_label(group[0]) != label:
                continue
            indices = [row_index[str(row["source_id"])] for row in group]
            probabilities = model.predict_proba(vectors[indices])
            group_scores.append(
                max(
                    1.0 - float(probability[class_index])
                    for probability in probabilities
                )
            )
        quantiles[label] = common._conformal_quantile(
            group_scores,
            ALPHA,
        )
    return quantiles


def _mode_set(
    model: Any,
    vector: np.ndarray,
    quantiles: dict[str, float],
) -> tuple[tuple[str, ...], dict[str, float]]:
    classes = [str(value) for value in model.classes_]
    probabilities = model.predict_proba(vector.reshape(1, -1))[0]
    distribution = {
        label: float(probabilities[index])
        for index, label in enumerate(classes)
    }
    prediction_set = tuple(
        label
        for label in ("candidate", "no_effect")
        if 1.0 - distribution[label] <= quantiles[label]
    )
    return prediction_set, distribution


def _top_families(
    model: Any,
    vector: np.ndarray,
    limit: int = 5,
) -> tuple[str, ...]:
    classes = [str(value) for value in model.classes_]
    probabilities = model.predict_proba(vector.reshape(1, -1))[0]
    order = sorted(
        range(len(classes)),
        key=lambda index: (
            float(probabilities[index]),
            classes[index],
        ),
        reverse=True,
    )
    return tuple(classes[index] for index in order[:limit])


def _adaptive_candidates(
    text: str,
    vector: np.ndarray,
    families: Sequence[str],
    operation_model: Any,
    catalog: PlannerCatalog,
) -> dict[str, tuple[PlannerTool, ...]]:
    operation_classes = [
        str(value) for value in operation_model.classes_
    ]
    probabilities = operation_model.predict_proba(
        vector.reshape(1, -1)
    )[0]
    probability_by_operation = {
        operation: float(probabilities[index])
        for index, operation in enumerate(operation_classes)
    }
    semantic = catalog.shortlist(
        text,
        preferred_families=families,
        restrict_to_preferred=True,
    )
    result: dict[str, tuple[PlannerTool, ...]] = {}
    for family in families:
        ranked = sorted(
            (
                (operation, probability)
                for operation, probability in probability_by_operation.items()
                if operation.split(".", 1)[0] == family
                and catalog.get(operation) is not None
            ),
            key=lambda item: (item[1], item[0]),
            reverse=True,
        )
        total_mass = sum(probability for _, probability in ranked)
        selected: list[PlannerTool] = []
        cumulative = 0.0
        for operation, probability in ranked:
            tool = catalog.get(operation)
            if tool is None:
                continue
            selected.append(tool)
            cumulative += probability
            within_family_mass = (
                cumulative / total_mass if total_mass > 0.0 else 1.0
            )
            if (
                len(selected) >= 2
                and within_family_mass >= ADAPTIVE_OPERATION_MASS
            ) or len(selected) >= MAX_OPERATION_CANDIDATES:
                break
        selected_names = {tool.name for tool in selected}
        for tool in semantic:
            if (
                tool.family == family
                and tool.name not in selected_names
                and len(selected) < MAX_OPERATION_CANDIDATES
            ):
                selected.append(tool)
                selected_names.add(tool.name)
        if selected:
            result[family] = tuple(
                selected[:MAX_OPERATION_CANDIDATES]
            )
    return result


def _family_selector(
    runtime: Any,
    text: str,
    candidates: dict[str, tuple[PlannerTool, ...]],
) -> dict[str, Any]:
    families = list(candidates)
    lines = [
        family
        + " | "
        + "; ".join(
            f"{tool.name}: {tool.description}"
            for tool in candidates[family]
        )
        for family in families
    ]
    return runtime._post_schema_object(
        {
            "messages": [
                {"role": "system", "content": FAMILY_SELECTOR_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Current request:\n{text}\n\n"
                        "Candidate families:\n"
                        + "\n".join(lines)
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_v52_family_selector",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "family": {
                                "type": "string",
                                "enum": ["__none__", *families],
                            }
                        },
                        "required": ["family"],
                        "additionalProperties": False,
                    },
                },
            },
            "temperature": 0.0,
            "max_tokens": 40,
            "seed": 61,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "the v5.2 family selector",
    )


def _operation_selector(
    runtime: Any,
    text: str,
    family: str,
    candidates: Sequence[PlannerTool],
    catalog: PlannerCatalog,
) -> dict[str, Any]:
    names = [tool.name for tool in candidates]
    return runtime._post_schema_object(
        {
            "messages": [
                {"role": "system", "content": OPERATION_SELECTOR_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Current request:\n{text}\n\n"
                        f"Selected family:\n{family}\n\n"
                        "Candidate operations:\n"
                        + catalog.compact_prompt(candidates)
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_v52_exact_operation_selector",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "operation": {
                                "type": "string",
                                "enum": ["__none__", *names],
                            }
                        },
                        "required": ["operation"],
                        "additionalProperties": False,
                    },
                },
            },
            "temperature": 0.0,
            "max_tokens": 48,
            "seed": 67,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "the v5.2 exact operation selector",
    )


def _pair_verifier(
    runtime: Any,
    text: str,
    tool: PlannerTool,
) -> dict[str, Any]:
    return runtime._post_schema_object(
        {
            "messages": [
                {"role": "system", "content": PAIR_VERIFIER_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Current request:\n{text}\n\n"
                        f"Proposed operation:\n{tool.name}\n\n"
                        f"Operation effect description:\n{tool.description}"
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_v52_argument_agnostic_pair_verifier",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "entailed_operation_kind": {
                                "type": "boolean"
                            },
                            "covers_entire_atomic_effect": {
                                "type": "boolean"
                            },
                            "effect_count": {
                                "type": "string",
                                "enum": ["zero", "one", "multiple"],
                            },
                        },
                        "required": [
                            "entailed_operation_kind",
                            "covers_entire_atomic_effect",
                            "effect_count",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "temperature": 0.0,
            "max_tokens": 72,
            "seed": 71,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "the v5.2 argument-agnostic pair verifier",
    )


def _pragmatic_veto(runtime: Any, text: str) -> dict[str, Any]:
    return runtime._post_schema_object(
        {
            "messages": [
                {"role": "system", "content": PRAGMATIC_VETO_PROMPT},
                {
                    "role": "user",
                    "content": f"Current utterance:\n{text}",
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_v52_pragmatic_contradiction_veto",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "speech_act": {
                                "type": "string",
                                "enum": [
                                    "request_or_question",
                                    "assertion_only",
                                    "other",
                                ],
                            },
                            "explicit_effect_request": {
                                "type": "boolean"
                            },
                            "effect_count": {
                                "type": "string",
                                "enum": ["zero", "one", "multiple"],
                            },
                        },
                        "required": [
                            "speech_act",
                            "explicit_effect_request",
                            "effect_count",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "temperature": 0.0,
            "max_tokens": 64,
            "seed": 73,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "the v5.2 pragmatic contradiction veto",
    )


def _tool_dictionary(
    tools: Sequence[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        str(tool["function"]["canonical_name"]): tool
        for tool in tools
    }


def _metrics(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    candidate_rows = [
        record
        for record in records
        if record["expected_class"] == "candidate"
    ]
    no_effect_rows = [
        record
        for record in records
        if record["expected_class"] == "no_effect"
    ]
    outputs = [
        record
        for record in records
        if record["final_mode"] in {"action", "clarify"}
    ]
    exact_outputs = [
        record
        for record in outputs
        if record["expected_class"] == "candidate"
        and record["selected_operation"] == record["expected_operation"]
    ]
    final_exact = [
        record
        for record in candidate_rows
        if record["final_mode"] in {"action", "clarify"}
        and record["selected_operation"] == record["expected_operation"]
    ]
    false_actions = [
        record
        for record in no_effect_rows
        if record["final_mode"] == "action"
    ]
    false_intents = [
        record
        for record in no_effect_rows
        if record["final_mode"] in {"action", "clarify"}
    ]
    expected_binary = [
        "candidate"
        if record["expected_class"] == "candidate"
        else "no_effect"
        for record in records
    ]
    predicted_binary = [
        "candidate"
        if record["final_mode"] in {"action", "clarify"}
        else "no_effect"
        for record in records
    ]
    latencies = [float(record["latency_seconds"]) for record in records]

    def ratio(numerator: int, denominator: int) -> float:
        return round(numerator / denominator if denominator else 0.0, 6)

    retrieval_hits = sum(
        record["expected_operation"]
        in set(record["operation_candidates"])
        for record in candidate_rows
    )
    selected_exact = sum(
        record["selected_operation"] == record["expected_operation"]
        for record in candidate_rows
    )
    return {
        "rows": len(records),
        "binary_accuracy": ratio(
            sum(
                expected == predicted
                for expected, predicted in zip(
                    expected_binary,
                    predicted_binary,
                    strict=True,
                )
            ),
            len(records),
        ),
        "binary_macro_f1": round(
            macro_f1(expected_binary, predicted_binary),
            6,
        ),
        "exact_operation_retrieval_coverage": ratio(
            retrieval_hits,
            len(candidate_rows),
        ),
        "exact_operation_retrieval_one_sided_95": (
            common._one_sided_interval(
                retrieval_hits,
                len(candidate_rows),
            )
        ),
        "exact_operation_selection_recall": ratio(
            selected_exact,
            len(candidate_rows),
        ),
        "action_or_clarify_exact_recall": ratio(
            len(final_exact),
            len(candidate_rows),
        ),
        "action_or_clarify_exact_recall_one_sided_95": (
            common._one_sided_interval(
                len(final_exact),
                len(candidate_rows),
            )
        ),
        "exact_intent_precision": ratio(
            len(exact_outputs),
            len(outputs),
        ),
        "exact_intent_precision_one_sided_95": (
            common._one_sided_interval(
                len(exact_outputs),
                len(outputs),
            )
        ),
        "false_effect_authority_on_no_effect": ratio(
            len(false_actions),
            len(no_effect_rows),
        ),
        "false_effect_authority_one_sided_95": (
            common._one_sided_interval(
                len(false_actions),
                len(no_effect_rows),
            )
        ),
        "false_effect_intent_on_no_effect": ratio(
            len(false_intents),
            len(no_effect_rows),
        ),
        "false_effect_intent_one_sided_95": (
            common._one_sided_interval(
                len(false_intents),
                len(no_effect_rows),
            )
        ),
        "final_mode_counts": dict(
            sorted(
                Counter(
                    str(record["final_mode"])
                    for record in records
                ).items()
            )
        ),
        "candidate_grounding_counts": dict(
            sorted(
                Counter(
                    str(record["final_mode"])
                    for record in candidate_rows
                    if record["selected_operation"]
                    == record["expected_operation"]
                ).items()
            )
        ),
        "exceptions": sum(
            record["exception"] is not None for record in records
        ),
        "latency_seconds": {
            "mean": round(statistics.fmean(latencies), 4),
            "p50": round(common._percentile(latencies, 0.50), 4),
            "p95": round(common._percentile(latencies, 0.95), 4),
            "p99": round(common._percentile(latencies, 0.99), 4),
            "max": round(max(latencies), 4),
        },
    }


def measure(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    corpus_path = args.development_corpus.resolve(strict=True)
    manifest_path = args.manifest.resolve(strict=True)
    rows, manifest, input_identity = _load_development(
        corpus_path,
        manifest_path,
    )
    validation_rows = [
        row for row in rows if row["split"] == "validation"
    ]
    quarantined_rows = [
        row for row in rows if _is_quarantined_projection(row)
    ]
    calibration_groups, evaluation_groups, conflicts = _group_validation(
        validation_rows
    )
    sample = _sample_evaluation(evaluation_groups, args.per_class)
    if any(_is_quarantined_projection(row) for row in sample):
        raise ValueError("quarantined MTOP projection entered the sample")
    row_index = {
        str(row["source_id"]): index
        for index, row in enumerate(rows)
    }

    router = IntentRouter(device="cpu")
    with configured_cache(ROUTER_CACHE.resolve(strict=True)):
        vectors, cache_identity, encode_seconds = _load_or_encode(
            router,
            rows,
            input_identity.corpus.sha256,
            args.embedding_cache.resolve(),
            args.embedding_metadata.resolve(),
        )
    mode_model, family_model, operation_model = _fit_models(rows, vectors)
    quantiles = _mode_quantiles(
        mode_model,
        rows,
        vectors,
        calibration_groups,
        row_index,
    )

    evaluation_rows = [
        row
        for group in evaluation_groups.values()
        for row in group
    ]
    evaluation_diagnostics: dict[str, dict[str, Any]] = {}
    for row in evaluation_rows:
        index = row_index[str(row["source_id"])]
        prediction_set, distribution = _mode_set(
            mode_model,
            vectors[index],
            quantiles,
        )
        evaluation_diagnostics[str(row["source_id"])] = {
            "mode_set": prediction_set,
            "candidate_probability": distribution["candidate"],
        }

    manifest_runtime = gate.read_runtime_manifest(args.runtime_manifest)
    common._configure_llm(manifest_runtime)
    capabilities = gate.core_capabilities(args.core)
    tool_list = common._tool_catalog(capabilities)
    tool_by_name = _tool_dictionary(tool_list)
    catalog = PlannerCatalog(tool_list, encoder=router.encode)
    from baxy_mind.llm import LlmRuntime

    runtime = LlmRuntime()
    runtime.begin_request(args.startup_budget)
    try:
        runtime._ensure_started()
    finally:
        runtime.end_request()
    original_post = runtime._post
    raw_calls: list[dict[str, Any]] = []

    def traced_post(
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        call_started = time.perf_counter()
        try:
            response = original_post(payload, timeout)
        except Exception as error:
            raw_calls.append(
                {
                    "seconds": time.perf_counter() - call_started,
                    "error": type(error).__name__,
                }
            )
            raise
        raw_calls.append(
            {
                "seconds": time.perf_counter() - call_started,
                "error": None,
            }
        )
        return response

    runtime._post = traced_post
    logical_calls = 0
    records: list[dict[str, Any]] = []
    try:
        for row in sample:
            case_started = time.perf_counter()
            source_id = str(row["source_id"])
            text = str(row["text"])
            index = row_index[source_id]
            expected_class = _class_label(row)
            expected_operation = _single_operation(row)
            if expected_class == "candidate" and expected_operation is None:
                raise ValueError("sample includes a non-single candidate")
            diagnostic = evaluation_diagnostics[source_id]
            prediction_set = tuple(diagnostic["mode_set"])
            top_families: tuple[str, ...] = ()
            family_candidates: dict[
                str,
                tuple[PlannerTool, ...],
            ] = {}
            family_result: dict[str, Any] | None = None
            operation_result: dict[str, Any] | None = None
            pair_result: dict[str, Any] | None = None
            veto_result: dict[str, Any] | None = None
            selected_family: str | None = None
            selected_operation: str | None = None
            final_mode = "no_effect"
            grounded = False
            missing_fields: tuple[str, ...] = ()
            exception: str | None = None
            runtime.begin_request(args.request_budget)
            try:
                if "candidate" in prediction_set:
                    top_families = _top_families(
                        family_model,
                        vectors[index],
                    )
                    family_candidates = _adaptive_candidates(
                        text,
                        vectors[index],
                        top_families,
                        operation_model,
                        catalog,
                    )
                    if family_candidates:
                        logical_calls += 1
                        family_result = _family_selector(
                            runtime,
                            text,
                            family_candidates,
                        )
                        raw_family = family_result.get("family")
                        if raw_family in family_candidates:
                            selected_family = str(raw_family)
                            candidates = family_candidates[selected_family]
                            logical_calls += 1
                            operation_result = _operation_selector(
                                runtime,
                                text,
                                selected_family,
                                candidates,
                                catalog,
                            )
                            raw_operation = operation_result.get("operation")
                            allowed = {tool.name for tool in candidates}
                            if raw_operation in allowed:
                                selected_operation = str(raw_operation)
                                selected_tool = catalog.get(
                                    selected_operation
                                )
                                if (
                                    selected_tool is None
                                    or selected_tool.family
                                    != selected_family
                                ):
                                    raise ValueError(
                                        "v5.2 selector broke family coherence"
                                    )
                                logical_calls += 1
                                pair_result = _pair_verifier(
                                    runtime,
                                    text,
                                    selected_tool,
                                )
                                pair_accepted = (
                                    pair_result.get(
                                        "entailed_operation_kind"
                                    )
                                    is True
                                    and pair_result.get(
                                        "covers_entire_atomic_effect"
                                    )
                                    is True
                                    and pair_result.get("effect_count")
                                    == "one"
                                )
                                if pair_accepted:
                                    logical_calls += 1
                                    veto_result = _pragmatic_veto(
                                        runtime,
                                        text,
                                    )
                                    contradicted = (
                                        veto_result.get("speech_act")
                                        == "assertion_only"
                                        and veto_result.get(
                                            "explicit_effect_request"
                                        )
                                        is False
                                        and veto_result.get("effect_count")
                                        == "zero"
                                    )
                                    if not contradicted:
                                        tool_contract = tool_by_name[
                                            selected_operation
                                        ]
                                        logical_calls += 1
                                        extracted = runtime.extract_arguments(
                                            text,
                                            tool_contract,
                                        )
                                        schema = tool_contract["function"][
                                            "parameters"
                                        ]
                                        grounded_arguments = (
                                            normalize_grounded_arguments(
                                                extracted,
                                                schema,
                                                text,
                                            )
                                            if extracted is not None
                                            else None
                                        )
                                        grounded = (
                                            grounded_arguments is not None
                                        )
                                        missing_fields = tuple(
                                            str(field)
                                            for field in schema.get(
                                                "required",
                                                [],
                                            )
                                            if not isinstance(
                                                grounded_arguments,
                                                dict,
                                            )
                                            or field
                                            not in grounded_arguments
                                        )
                                        final_mode = (
                                            "action"
                                            if grounded
                                            else "clarify"
                                        )
            except Exception as error:  # noqa: BLE001 - fail closed
                exception = type(error).__name__
                final_mode = "no_effect"
                grounded = False
            finally:
                runtime.end_request()

            operation_candidates = tuple(
                tool.name
                for tools in family_candidates.values()
                for tool in tools
                if (
                    selected_family is None
                    or tool.family == selected_family
                )
            )
            records.append(
                {
                    "source_id": source_id,
                    "mission_id_sha256": hashlib.sha256(
                        str(row["mission_id"]).encode("utf-8")
                    ).hexdigest(),
                    "text_sha256": hashlib.sha256(
                        text.encode("utf-8")
                    ).hexdigest(),
                    "locale": row["locale"],
                    "expected_class": expected_class,
                    "expected_operation": expected_operation,
                    "expected_family": (
                        expected_operation.split(".", 1)[0]
                        if expected_operation
                        else None
                    ),
                    "candidate_probability": round(
                        float(diagnostic["candidate_probability"]),
                        8,
                    ),
                    "mode_set": prediction_set,
                    "triggered": "candidate" in prediction_set,
                    "top_families": top_families,
                    "family_candidates": {
                        family: tuple(tool.name for tool in tools)
                        for family, tools in family_candidates.items()
                    },
                    "selected_family": selected_family,
                    "operation_candidates": operation_candidates,
                    "selected_operation": selected_operation,
                    "pair_verifier": pair_result,
                    "pragmatic_veto": veto_result,
                    "grounded": grounded,
                    "missing_schema_fields": missing_fields,
                    "final_mode": final_mode,
                    "exception": exception,
                    "latency_seconds": round(
                        time.perf_counter() - case_started,
                        4,
                    ),
                }
            )
    finally:
        runtime.close()

    sample_metrics = _metrics(records)
    eval_candidate = [
        diagnostic
        for row in evaluation_rows
        if _class_label(row) == "candidate"
        for diagnostic in [evaluation_diagnostics[str(row["source_id"])]]
    ]
    eval_no_effect = [
        diagnostic
        for row in evaluation_rows
        if _class_label(row) == "no_effect"
        for diagnostic in [evaluation_diagnostics[str(row["source_id"])]]
    ]
    candidate_triggered = sum(
        "candidate" in diagnostic["mode_set"]
        for diagnostic in eval_candidate
    )
    no_effect_triggered = sum(
        "candidate" in diagnostic["mode_set"]
        for diagnostic in eval_no_effect
    )
    stagewise: dict[str, dict[str, int]] = {}
    for label in ("candidate", "no_effect"):
        selected = [
            record
            for record in records
            if record["expected_class"] == label
        ]
        stagewise[label] = {
            "rows": len(selected),
            "triggered": sum(record["triggered"] for record in selected),
            "expected_family_in_top5": sum(
                record["expected_family"] in set(record["top_families"])
                for record in selected
                if record["expected_family"] is not None
            ),
            "expected_family_selected": sum(
                record["selected_family"] == record["expected_family"]
                for record in selected
                if record["expected_family"] is not None
            ),
            "expected_operation_retrieved": sum(
                record["expected_operation"]
                in set(record["operation_candidates"])
                for record in selected
                if record["expected_operation"] is not None
            ),
            "expected_operation_selected": sum(
                record["selected_operation"]
                == record["expected_operation"]
                for record in selected
                if record["expected_operation"] is not None
            ),
            "pair_accepted": sum(
                isinstance(record["pair_verifier"], dict)
                and record["pair_verifier"].get(
                    "entailed_operation_kind"
                )
                is True
                and record["pair_verifier"].get(
                    "covers_entire_atomic_effect"
                )
                is True
                and record["pair_verifier"].get("effect_count") == "one"
                for record in selected
            ),
            "pragmatic_vetoes": sum(
                isinstance(record["pragmatic_veto"], dict)
                and record["pragmatic_veto"].get("speech_act")
                == "assertion_only"
                and record["pragmatic_veto"].get(
                    "explicit_effect_request"
                )
                is False
                and record["pragmatic_veto"].get("effect_count") == "zero"
                for record in selected
            ),
            "final_action": sum(
                record["final_mode"] == "action" for record in selected
            ),
            "final_clarify": sum(
                record["final_mode"] == "clarify" for record in selected
            ),
        }

    raw_latencies = [float(call["seconds"]) for call in raw_calls]
    report = {
        "schema": "baxy.turn-policy-v52-mtop-validation-pilot.v1",
        "status": "development_only_not_a_release_gate",
        "contains_text": False,
        "authority": "read_only_no_operation_dispatch",
        "data_boundary": {
            "used_corpus": "mtop_development.v1.jsonl",
            "used_splits": ["train", "validation"],
            "test_or_reserve_opened": False,
            "public_test_or_v4_opened": False,
            "validation_parallel_grouping": "mission_id",
            "parallel_groups_crossing_calibration_evaluation": 0,
            "sample_parallel_duplicates": 0,
        },
        "inputs": {
            "development_corpus_bytes": input_identity.corpus.bytes,
            "development_corpus_sha256": input_identity.corpus.sha256,
            "development_manifest_bytes": input_identity.manifest.bytes,
            "development_manifest_sha256": (
                input_identity.manifest.sha256
            ),
            "map_sha256": manifest["source"]["map_sha256"],
            "catalog_sha256": manifest["catalog"]["sha256"],
            "seed": SEED,
            "alpha": ALPHA,
            "adaptive_operation_mass": ADAPTIVE_OPERATION_MASS,
            "operation_candidate_cap": MAX_OPERATION_CANDIDATES,
            "mode_model": (
                "balanced_logreg_C1_lbfgs_train_only_quarantine_excluded"
            ),
            "family_model": "balanced_logreg_C4_lbfgs_train_single_op",
            "operation_model": (
                "balanced_logreg_C4_lbfgs_train_single_op"
            ),
            "embedding_cache": cache_identity,
        },
        "partition": {
            "train_rows": sum(row["split"] == "train" for row in rows),
            "validation_rows": len(validation_rows),
            "mode_train_rows": sum(
                row["split"] == "train"
                and not _is_quarantined_projection(row)
                for row in rows
            ),
            "calibration_groups": len(calibration_groups),
            "evaluation_groups": len(evaluation_groups),
            "conflicting_parallel_groups_excluded": len(conflicts),
            "conflicting_group_ids_sha256": _canonical_sha256(conflicts),
        },
        "label_quarantine": {
            "policy": (
                "excluded_from_mode_training_calibration_evaluation_sample"
            ),
            "reasons": sorted(QUARANTINED_PROJECTION_REASONS),
            "rows": len(quarantined_rows),
            "split_counts": dict(
                sorted(
                    Counter(
                        str(row["split"]) for row in quarantined_rows
                    ).items()
                )
            ),
            "locale_counts": dict(
                sorted(
                    Counter(
                        str(row["locale"]) for row in quarantined_rows
                    ).items()
                )
            ),
            "validation_mission_groups": len(
                {
                    str(row["mission_id"])
                    for row in quarantined_rows
                    if row["split"] == "validation"
                }
            ),
            "source_ids_sha256": _canonical_sha256(
                sorted(str(row["source_id"]) for row in quarantined_rows)
            ),
        },
        "calibration": {
            "method": (
                "class_conditional_group_max_nonconformity_1_minus_p"
            ),
            "finite_sample_rule": "ceil((n+1)*(1-alpha)), higher",
            "quantiles": {
                key: round(value, 8)
                for key, value in sorted(quantiles.items())
            },
        },
        "evaluation_pool": {
            "candidate_rows": len(eval_candidate),
            "candidate_trigger_recall": round(
                candidate_triggered / len(eval_candidate),
                6,
            ),
            "candidate_trigger_one_sided_95": (
                common._one_sided_interval(
                    candidate_triggered,
                    len(eval_candidate),
                )
            ),
            "no_effect_rows": len(eval_no_effect),
            "no_effect_trigger_rate": round(
                no_effect_triggered / len(eval_no_effect),
                6,
            ),
            "no_effect_trigger_one_sided_95": (
                common._one_sided_interval(
                    no_effect_triggered,
                    len(eval_no_effect),
                )
            ),
        },
        "sample": {
            "rows": len(records),
            "per_class": args.per_class,
            "class_locale_counts": {
                f"{label}:{locale}": sum(
                    record["expected_class"] == label
                    and record["locale"] == locale
                    for record in records
                )
                for label in ("candidate", "no_effect")
                for locale in ("en", "es")
            },
            "unique_mission_groups": len(
                {record["mission_id_sha256"] for record in records}
            ),
            "candidate_operation_counts": dict(
                sorted(
                    Counter(
                        str(record["expected_operation"])
                        for record in records
                        if record["expected_class"] == "candidate"
                    ).items()
                )
            ),
            "no_effect_reason_counts": dict(
                sorted(
                    Counter(
                        str(
                            next(
                                row["projection"]["reason"]
                                for row in sample
                                if row["source_id"] == record["source_id"]
                            )
                        )
                        for record in records
                        if record["expected_class"] == "no_effect"
                    ).items()
                )
            ),
            "metrics": sample_metrics,
            "stagewise": stagewise,
        },
        "llm": {
            "logical_calls": logical_calls,
            "raw_schema_calls": len(raw_calls),
            "schema_recovery_calls": max(
                0,
                len(raw_calls) - logical_calls,
            ),
            "raw_call_errors": sum(
                call["error"] is not None for call in raw_calls
            ),
            "raw_latency_seconds": {
                "mean": round(
                    statistics.fmean(raw_latencies)
                    if raw_latencies
                    else 0.0,
                    4,
                ),
                "p50": round(
                    common._percentile(raw_latencies, 0.50),
                    4,
                ),
                "p95": round(
                    common._percentile(raw_latencies, 0.95),
                    4,
                ),
                "max": round(max(raw_latencies, default=0.0), 4),
            },
        },
        "timing": {
            "embedding_encode_seconds": round(encode_seconds, 4),
            "total_seconds": round(time.perf_counter() - started, 4),
        },
        "records": records,
    }
    _assert_input_identity_stable(input_identity)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--development-corpus",
        type=Path,
        default=DEVELOPMENT_CORPUS,
    )
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument(
        "--embedding-cache",
        type=Path,
        default=EMBEDDING_CACHE,
    )
    parser.add_argument(
        "--embedding-metadata",
        type=Path,
        default=EMBEDDING_METADATA,
    )
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        default=gate.DEFAULT_RUNTIME_MANIFEST,
    )
    parser.add_argument("--core", type=Path, default=gate.DEFAULT_CORE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--per-class", type=int, default=64)
    parser.add_argument("--request-budget", type=float, default=20.0)
    parser.add_argument("--startup-budget", type=float, default=240.0)
    args = parser.parse_args()
    if not 16 <= args.per_class <= 128 or args.per_class % 2:
        parser.error("--per-class must be even and in [16, 128]")
    if not 5.0 <= args.request_budget <= 55.0:
        parser.error("--request-budget must be in [5, 55]")
    return args


def _reported_input_identity(
    args: argparse.Namespace,
    report: dict[str, Any],
) -> DevelopmentInputIdentity:
    inputs = report["inputs"]
    return DevelopmentInputIdentity(
        corpus=FileIdentity(
            path=args.development_corpus.resolve(strict=True),
            bytes=int(inputs["development_corpus_bytes"]),
            sha256=str(inputs["development_corpus_sha256"]),
        ),
        manifest=FileIdentity(
            path=args.manifest.resolve(strict=True),
            bytes=int(inputs["development_manifest_bytes"]),
            sha256=str(inputs["development_manifest_sha256"]),
        ),
    )


def main() -> int:
    args = parse_args()
    report = measure(args)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    _assert_input_identity_stable(_reported_input_identity(args, report))
    gate.write_json_atomic(output, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "evaluation_pool": report["evaluation_pool"],
                "sample": report["sample"],
                "llm": report["llm"],
                "timing": report["timing"],
                "output": gate.repo_relative(output),
                "sha256": file_sha256(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
