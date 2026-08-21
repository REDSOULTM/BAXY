"""Reproducible real-LLM A/B gate for BAXY's turn policy.

Both arms load the same train-only corpus candidate index. The baseline arm
disables only the calibrated evidence signal; the evidence arm enables its
one-sided conversation veto. Candidate expansion is therefore identical
between arms and cannot masquerade as an evidence-policy improvement. Both
arms send only ``turn.decide`` requests to the mind sidecar: the core is opened
solely to read its authenticated catalog, and no operation is ever dispatched.

The full protocol selects 848 cases exclusively from the blind v4 final seal,
plus 12 contextual cases (860 total; 1,720 measured A/B calls), by a stable
hash-stratified procedure. ``--preflight`` never opens that final set: it
retains the mandatory context/OOD suite and samples only the public validation
split for a practical same-day smoke.
Every measured call is durably appended to a resumable journal; the compact
JSON report is replaced atomically at checkpoints and completion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import queue
import random
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
import unicodedata
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
SCRIPTS = REPO / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from baxy_mind.router import (  # noqa: E402
    MODEL_NAME as ENCODER_MODEL_NAME,
    MODEL_REVISION as ENCODER_MODEL_REVISION,
    MODEL_SNAPSHOT_FILE_COUNT as ENCODER_SNAPSHOT_FILE_COUNT,
    MODEL_SNAPSHOT_MANIFEST_ALGORITHM as ENCODER_SNAPSHOT_MANIFEST_ALGORITHM,
    MODEL_SNAPSHOT_MANIFEST_SHA256 as ENCODER_SNAPSHOT_MANIFEST_SHA256,
    MODEL_WEIGHTS_SHA256 as ENCODER_WEIGHTS_SHA256,
    verified_encoder_snapshot_identity,
)
from blind_reset_turn_evidence_final_seal import (  # noqa: E402
    extract_holdout_row_identity,
)
from blind_reset_turn_evidence_final_seal_v4 import (  # noqa: E402
    DEFAULT_FAILED_JOURNAL,
    DEFAULT_FAILED_REPORT,
    DEFAULT_V2_FAILED_JOURNAL,
    DEFAULT_V2_FAILED_REPORT,
    DEFAULT_V2_SEAL,
    DEFAULT_V3_SEAL as DEFAULT_PREDECESSOR_SEAL,
    DEFAULT_V1_SEAL,
    PRODUCTION_RULE_DECLARATION_SHA256,
    SCHEMA as FINAL_SEAL_SCHEMA,
    build_reset_seal,
)
from build_layout import load_build_layout  # noqa: E402

DEFAULT_HOLDOUT = REPO / "tests" / "data" / "turn_evidence_public_holdout.v1.jsonl"
DEFAULT_RUNTIME = REPO / "tests" / "data" / "turn_evidence_runtime.v1.jsonl"
DEFAULT_SEAL = REPO / "tests" / "data" / "turn_evidence_final_seal.v4.json"
DEFAULT_POLICY = (
    SRC / "baxy_mind" / "data" / "turn_evidence_abstention_policy.v1.json"
)
DEFAULT_OUTPUT = REPO / "artifacts" / "product" / "turn_policy_gate.json"
BUILD_LAYOUT = load_build_layout(REPO)
DEFAULT_CORE = BUILD_LAYOUT.core_executable(REPO)
DEFAULT_RUNTIME_MANIFEST = (
    Path(os.environ.get("LOCALAPPDATA", REPO))
    / "BAXYRuntime"
    / "mind-runtime-v1.json"
)
VALID_MODES = frozenset({"conversation", "clarify", "action", "plan"})
NO_EFFECT_MODES = frozenset({"conversation", "clarify"})
EFFECT_MODES = frozenset({"action", "plan"})
FULL_TOTAL_CASES = 860
FULL_HOLDOUT_SAMPLE = 848
PREFLIGHT_HOLDOUT_SAMPLE = 8
DEFAULT_SEED = "baxy-turn-policy-gate-v1"
DEFAULT_NONINFERIORITY_MARGIN = 0.02
# Release SLO: at most one fail-closed degradation per 860-case arm, and none
# in the required critical set.  The gate reports rates too, but a fixed count
# avoids making the error budget looser when a future corpus grows.
MAX_TURN_RECOVERY_CASES = 1
MAX_PROTOCOL_FALLBACK_CASES = 1
PAIRED_BOOTSTRAP_RESAMPLES = 2000
ONE_SIDED_AUTHORITY = "conversation_signal_or_abstain_only"
SUCCESS_STATUSES = frozenset({"passed", "preflight_passed", "diagnostic_passed"})
_PUBLIC_BINARY_IDENTITY_CACHE: dict[tuple[str, int, int], dict[str, Any]] = {}
MIND_RUNTIME_SOURCE_PATHS = (
    SRC / "baxy_mind" / "__init__.py",
    SRC / "baxy_mind" / "__main__.py",
    SRC / "baxy_mind" / "catalog_operation_aliases.py",
    SRC / "baxy_mind" / "corrector.py",
    SRC / "baxy_mind" / "effect_intent.py",
    SRC / "baxy_mind" / "family_classifier.py",
    SRC / "baxy_mind" / "llm.py",
    SRC / "baxy_mind" / "llm_transport.py",
    SRC / "baxy_mind" / "phonetic_es.py",
    SRC / "baxy_mind" / "planner.py",
    SRC / "baxy_mind" / "process_lifecycle.py",
    SRC / "baxy_mind" / "protocol.py",
    SRC / "baxy_mind" / "router.py",
    SRC / "baxy_mind" / "router_worker.py",
    SRC / "baxy_mind" / "semantic_family_arbiter.py",
    SRC / "baxy_mind" / "skill_registry.py",
    SRC / "baxy_mind" / "time_budget.py",
    SRC / "baxy_mind" / "turn_evidence.py",
    SRC / "baxy_mind" / "turn_evidence_contracts.py",
    SRC / "baxy_mind" / "data" / "family_classifier.v1.manifest.json",
    SRC / "baxy_mind" / "data" / "family_classifier.v1.vocabulary.json.gz",
    SRC / "baxy_mind" / "data" / "family_classifier.v1.weights.npz",
    SRC / "baxy_mind" / "data" / "semantic_family_arbiter.v1.manifest.json",
    SRC / "baxy_mind" / "data" / "semantic_family_arbiter.v1.weights.npz",
    SRC / "baxy_mind" / "data" / "catalog_operation_aliases.v1.json",
)


def load_verified_encoder_identity() -> dict[str, Any]:
    """Fail unless the local E5 bytes match the release-pinned snapshot."""

    identity = verified_encoder_snapshot_identity()
    expected = {
        "model": ENCODER_MODEL_NAME,
        "revision": ENCODER_MODEL_REVISION,
        "manifest_algorithm": ENCODER_SNAPSHOT_MANIFEST_ALGORITHM,
        "manifest_sha256": ENCODER_SNAPSHOT_MANIFEST_SHA256,
        "file_count": ENCODER_SNAPSHOT_FILE_COUNT,
        "weights": {
            "path": "model.safetensors",
            "sha256": ENCODER_WEIGHTS_SHA256,
        },
    }
    if identity != expected:
        raise ValueError("la identidad física del encoder E5 no coincide")
    return dict(identity)


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: JSONL inválido") from error
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: la fila no es un objeto")
            yield row


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def mind_source_hashes(turn_probe_path: Path) -> dict[str, str]:
    """Bind every Python source that can affect a measured turn decision."""

    paths = (*MIND_RUNTIME_SOURCE_PATHS, turn_probe_path)
    names = tuple(path.name for path in paths)
    if len(set(names)) != len(names):
        raise ValueError("el fingerprint de mente contiene nombres de archivo duplicados")
    return {path.name: file_sha256(path) for path in paths}


def list_sha256(values: Sequence[str]) -> str:
    payload = "".join(f"{value}\n" for value in values).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def append_jsonl_durable(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json(value) + b"\n"
    with path.open("ab", buffering=0) as handle:
        handle.write(payload)
        os.fsync(handle.fileno())


def default_journal_path(output: Path) -> Path:
    return output.with_suffix(".jsonl")


def normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def source_locale(row: dict[str, Any]) -> str:
    parts = str(row.get("source_id") or "").split(":")
    return parts[1] if len(parts) >= 3 else "unknown"


def stratum_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    provenance = row.get("provenance") or {}
    return (
        str(row["mode"]),
        ",".join(str(value) for value in row.get("families") or ()) or "none",
        str(provenance.get("dataset") or "unknown"),
        source_locale(row),
    )


def _rank_hash(seed: str, row: dict[str, Any]) -> bytes:
    material = "\0".join(
        (
            seed,
            str(row.get("source_id") or ""),
            str(row.get("mission_id") or ""),
            normalized_text(str(row.get("text") or "")),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).digest()


def allocate_stratified_quotas(
    capacities: dict[tuple[str, ...], int],
    sample_size: int,
) -> dict[tuple[str, ...], int]:
    """Allocate an exact proportional sample with one row per stratum first."""

    if sample_size < 0:
        raise ValueError("sample_size no puede ser negativo")
    capacities = {key: value for key, value in capacities.items() if value > 0}
    total = sum(capacities.values())
    sample_size = min(sample_size, total)
    if sample_size == 0:
        return {key: 0 for key in capacities}

    keys = sorted(capacities)
    quotas = {key: 0 for key in keys}
    if sample_size >= len(keys):
        for key in keys:
            quotas[key] = 1
        remaining = sample_size - len(keys)
    else:
        for key in keys[:sample_size]:
            quotas[key] = 1
        return quotas

    while remaining:
        spare = {key: capacities[key] - quotas[key] for key in keys}
        spare_total = sum(spare.values())
        if spare_total <= 0:
            break
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
            (key for key in keys if quotas[key] < capacities[key]),
            key=lambda key: (
                ideals.get(key, 0.0) - math.floor(ideals.get(key, 0.0)),
                spare[key],
                key,
            ),
            reverse=True,
        )
        if not ranked:
            break
        for key in ranked:
            if not remaining:
                break
            if quotas[key] < capacities[key]:
                quotas[key] += 1
                remaining -= 1
    return quotas


def stratified_hash_sample(
    rows: Sequence[dict[str, Any]],
    sample_size: int,
    seed: str,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[stratum_key(row)].append(row)
    if sample_size < len(grouped):
        selected_keys = set(
            sorted(
                grouped,
                key=lambda key: hashlib.sha256(
                    (seed + "\0stratum\0" + "\0".join(key)).encode("utf-8")
                ).digest(),
            )[:sample_size]
        )
        grouped = defaultdict(
            list,
            {key: values for key, values in grouped.items() if key in selected_keys},
        )
    quotas = allocate_stratified_quotas(
        {key: len(values) for key, values in grouped.items()},
        sample_size,
    )
    selected: list[dict[str, Any]] = []
    for key in sorted(grouped):
        ranked = sorted(
            grouped[key],
            key=lambda row: (_rank_hash(seed, row), str(row["source_id"])),
        )
        selected.extend(ranked[: quotas[key]])
    return sorted(
        selected,
        key=lambda row: (_rank_hash(seed + "\0final", row), str(row["source_id"])),
    )


def load_verified_final_seal(
    holdout_path: Path,
    seal_path: Path = DEFAULT_SEAL,
    predecessor_seal_path: Path = DEFAULT_PREDECESSOR_SEAL,
) -> dict[str, Any]:
    """Verify v4 by rebuilding the untouched blind reserve of v3."""

    holdout_path = holdout_path.resolve(strict=True)
    seal_path = seal_path.resolve(strict=True)
    predecessor_seal_path = predecessor_seal_path.resolve(strict=True)
    try:
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("el sello final v4 contiene JSON inválido") from error
    rebuilt = build_reset_seal(holdout_path, predecessor_seal_path)
    if seal != rebuilt:
        raise ValueError(
            "el sello final v4 no coincide con su reconstrucción criptográfica"
        )
    if (
        seal.get("schema") != FINAL_SEAL_SCHEMA
        or seal.get("rule_declaration_sha256")
        != PRODUCTION_RULE_DECLARATION_SHA256
        or seal.get("contains_text_or_labels") is not False
        or seal.get("evaluation", {}).get("performed_by_generator") is not False
    ):
        raise ValueError("identidad del sello final v4 inválida")
    return seal


def load_selected_holdout_rows(
    holdout_path: Path,
    *,
    split: str | None = None,
    source_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Decode only rows selected by blind ``split``/``source_id`` identity."""

    if (split is None) == (source_ids is None):
        raise ValueError("debe seleccionarse por split o por IDs sellados")
    rows: list[dict[str, Any]] = []
    found: set[str] = set()
    seen: set[str] = set()
    file_rows = 0
    test_rows = 0
    validation_rows = 0
    with holdout_path.open("rb") as handle:
        for line_number, line in enumerate(handle, 1):
            raw_line = line.strip()
            if not raw_line:
                continue
            file_rows += 1
            row_split, source_id = extract_holdout_row_identity(
                raw_line,
                line_number=line_number,
            )
            if source_id in seen:
                raise ValueError("el holdout contiene source_id duplicado")
            seen.add(source_id)
            test_rows += row_split == "test"
            validation_rows += row_split == "validation"
            selected = (
                row_split == split
                if split is not None
                else source_id in source_ids
            )
            if not selected:
                continue
            if source_ids is not None and row_split != "test":
                raise ValueError("un ID final v4 no pertenece al split test")
            try:
                row = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError(
                    f"holdout seleccionado inválido en fila {line_number}"
                ) from error
            if not isinstance(row, dict):
                raise ValueError(
                    f"holdout seleccionado no-objeto en fila {line_number}"
                )
            if (
                row.get("source_id") != source_id
                or row.get("split") != row_split
            ):
                raise ValueError(
                    f"identidad inconsistente en fila {line_number}"
                )
            found.add(source_id)
            rows.append(row)
    if source_ids is not None and found != source_ids:
        raise ValueError("el holdout no coincide con la lista final v4")
    rows.sort(key=lambda row: str(row["source_id"]))
    return rows, {
        "file_rows": file_rows,
        "test_rows": test_rows,
        "validation_rows": validation_rows,
    }


def load_clean_holdout(
    holdout_path: Path,
    runtime_path: Path,
    seal_path: Path = DEFAULT_SEAL,
    *,
    predecessor_seal_path: Path = DEFAULT_PREDECESSOR_SEAL,
    preflight: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seal = load_verified_final_seal(
        holdout_path,
        seal_path,
        predecessor_seal_path,
    )
    final_identity = seal["final"]
    sealed_source_ids = final_identity["source_ids"]
    if preflight:
        rows, scan = load_selected_holdout_rows(
            holdout_path,
            split="validation",
        )
        selected_split = "validation"
        selection_scope = "public_validation_only"
    else:
        rows, scan = load_selected_holdout_rows(
            holdout_path,
            source_ids=set(sealed_source_ids),
        )
        selected_split = "test"
        selection_scope = "sealed_final_v4_only"
    if scan["test_rows"] != seal["holdout"]["test_rows"]:
        raise ValueError("conteo test no coincide con el manifiesto v4")

    runtime_rows = list(read_jsonl(runtime_path))
    runtime_texts = {
        normalized_text(str(row.get("text") or ""))
        for row in runtime_rows
        if isinstance(row.get("text"), str)
    }
    runtime_missions = {
        str(row.get("mission_id") or "")
        for row in runtime_rows
        if row.get("mission_id")
    }
    seen_texts: set[str] = set()
    seen_sources: set[str] = set()
    for position, row in enumerate(rows, 1):
        text = row.get("text")
        mode = row.get("mode")
        families = row.get("families")
        source_id = row.get("source_id")
        mission_id = row.get("mission_id")
        if (
            row.get("schema") != "baxy.turn-evidence-record.v1"
            or row.get("split") != selected_split
            or not isinstance(text, str)
            or not text.strip()
            or mode not in VALID_MODES
            or not isinstance(families, list)
            or not all(isinstance(value, str) and value for value in families)
            or "memory" in families
            or not isinstance(source_id, str)
            or not source_id
            or not isinstance(mission_id, str)
            or not mission_id
            or not isinstance(row.get("provenance"), dict)
        ):
            raise ValueError(f"holdout inválido en fila seleccionada {position}")
        identity = normalized_text(text)
        if identity in seen_texts:
            raise ValueError("el holdout contiene texto normalizado duplicado")
        if source_id in seen_sources:
            raise ValueError("el holdout contiene source_id duplicado")
        if identity in runtime_texts or mission_id in runtime_missions:
            raise ValueError("se detectó fuga train/holdout por texto o misión")
        seen_texts.add(identity)
        seen_sources.add(source_id)
    selected_source_ids = sorted(seen_sources)
    return rows, {
        "selection_scope": selection_scope,
        "selected_split": selected_split,
        "holdout_file_rows": scan["file_rows"],
        "holdout_test_rows": scan["test_rows"],
        "holdout_validation_rows": scan["validation_rows"],
        "holdout_rows": len(rows),
        "selected_source_ids_sha256": list_sha256(selected_source_ids),
        "sealed_final_rows": final_identity["rows"],
        "sealed_final_source_ids_sha256": final_identity[
            "source_ids_sha256"
        ],
        "policy_calibration_final_source_ids_sha256": seal["policy_calibration"][
            "final_source_ids_sha256"
        ],
        "failed_attempt_report_sha256": seal["failed_attempt"][
            "report_sha256"
        ],
        "failed_attempt_journal_sha256": seal["failed_attempt"][
            "journal_sha256"
        ],
        "seal_schema": seal["schema"],
        "seal_rule_declaration_sha256": seal[
            "rule_declaration_sha256"
        ],
        "seal_sha256": file_sha256(seal_path),
        "predecessor_seal_sha256": file_sha256(
            predecessor_seal_path
        ),
        "blind_manifest_rebuilt": True,
        "runtime_rows": len(runtime_rows),
        "normalized_text_overlap": 0,
        "mission_overlap": 0,
        "strata": len({stratum_key(row) for row in rows}),
    }


def contextual_cases() -> list[dict[str, Any]]:
    """Frozen evaluation-only context/OOD cases; never imported by runtime."""

    return [
        {
            "case_id": "critical:greeting_es",
            "text": "Hola",
            "history": [],
            "expected_modes": ["conversation"],
            "expected_families": [],
            "required": True,
            "category": "greeting",
        },
        {
            "case_id": "critical:why_after_failure",
            "text": "¿Por qué?",
            "history": [
                {
                    "role": "assistant",
                    "content": "No pude completar esa acción porque se agotó el tiempo.",
                },
                {"role": "user", "content": "¿Por qué?"},
            ],
            "expected_modes": ["conversation"],
            "expected_families": [],
            "required": True,
            "category": "contextual_followup",
            "requires_contextual_continuity": True,
            "forbid_followup_question": True,
            "required_reply_root_groups": [["tiem", "limi", "agot"]],
        },
        {
            "case_id": "critical:what_after_offer",
            "text": "¿Qué?",
            "history": [
                {"role": "assistant", "content": "Dime qué necesitas y te ayudo."},
                {"role": "user", "content": "¿Qué?"},
            ],
            "expected_modes": ["conversation"],
            "expected_families": [],
            "required": True,
            "category": "contextual_followup",
            "requires_contextual_continuity": True,
            "requires_contextual_explanation": True,
        },
        {
            "case_id": "critical:knowledge_es",
            "text": "¿Por qué el cielo se ve azul?",
            "history": [],
            "expected_modes": ["conversation"],
            "expected_families": [],
            "required": True,
            "category": "knowledge",
            "expected_language": "es",
        },
        {
            "case_id": "critical:single_action_es",
            "text": "Abre la calculadora",
            "history": [],
            "expected_modes": ["action"],
            "expected_families": ["app"],
            "required": True,
            "category": "single_action",
        },
        {
            "case_id": "critical:compound_plan_es",
            "text": "Abre la calculadora y después abre el bloc de notas",
            "history": [],
            "expected_modes": ["plan"],
            "expected_families": [],
            "required": True,
            "category": "compound_plan",
        },
        {
            "case_id": "critical:ambiguous_reference_es",
            "text": "Abre eso",
            "history": [],
            "expected_modes": ["clarify", "conversation"],
            "expected_families": [],
            "required": True,
            "category": "ambiguous",
            "clarify_compatible": True,
        },
        {
            "case_id": "critical:unsupported_taxi_es",
            "text": "Pide un taxi para que venga a mi casa",
            "history": [],
            "expected_modes": ["conversation"],
            "expected_families": [],
            "required": True,
            "category": "out_of_domain",
            "forbid_followup_question": True,
        },
        {
            "case_id": "context:greeting_en",
            "text": "Hey, how are you?",
            "history": [],
            "expected_modes": ["conversation"],
            "expected_families": [],
            "required": False,
            "category": "greeting",
        },
        {
            "case_id": "context:unsupported_food_delivery",
            "text": "Order me a pizza from my favorite restaurant",
            "history": [],
            "expected_modes": ["conversation"],
            "expected_families": [],
            "required": False,
            "category": "out_of_domain",
            "forbid_followup_question": True,
        },
        {
            "case_id": "context:spanglish_action",
            "text": "Open la calculadora por favor",
            "history": [],
            "expected_modes": ["action"],
            "expected_families": ["app"],
            "required": False,
            "category": "single_action",
        },
        {
            "case_id": "context:pronoun_with_history",
            "text": "Ábrela",
            "history": [
                {
                    "role": "user",
                    "content": "Quiero usar la calculadora para hacer una cuenta.",
                },
                {
                    "role": "assistant",
                    "content": "Puedo abrir la calculadora cuando me lo indiques.",
                },
            ],
            "expected_modes": ["action", "clarify"],
            "expected_families": ["app"],
            "required": False,
            "category": "contextual_action",
            "clarify_compatible": True,
        },
    ]


def holdout_case(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": "holdout:" + str(row["source_id"]),
        "text": str(row["text"]),
        "history": [],
        "expected_modes": [str(row["mode"])],
        "expected_families": [str(value) for value in row["families"]],
        "required": False,
        "category": "public_holdout",
        "clarify_compatible": row["mode"] == "clarify",
        "stratum": list(stratum_key(row)),
    }


def percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, fraction)) * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def operation_family(operation: str | None) -> str:
    return str(operation or "").split(".", 1)[0]


_EXPECTED_FAMILY_OPERATIONS = {
    "app": frozenset({"app", "window"}),
    "browser": frozenset({"browser", "web"}),
    "calendar": frozenset({"calendar", "reminder"}),
    "media": frozenset({"media", "streaming"}),
    "network": frozenset({"network", "wifi"}),
    "notification": frozenset({"notification", "reminder"}),
    "system_settings": frozenset({"system"}),
    "vision": frozenset({"capture", "ocr", "vision"}),
    "web": frozenset({"browser", "web"}),
}


def family_matches_expected(
    operation: str | None,
    expected_families: set[str],
) -> bool:
    actual = operation_family(operation)
    if not actual:
        return False
    allowed: set[str] = set()
    for family in expected_families:
        allowed.update(_EXPECTED_FAMILY_OPERATIONS.get(family, (family,)))
    return actual in allowed


def raw_audit_partition(
    result: dict[str, Any],
    expected_families: set[str],
) -> dict[str, Any]:
    """Separate shortlist recovery, model decision, and downstream vetoes."""

    audit = result.get("raw_audit")
    if not isinstance(audit, dict) or not expected_families:
        return {
            "raw_audit_observed": False,
            "retrieval_family_hit": None,
            "raw_decision_mode": "",
            "raw_decision_family": "",
            "raw_decision_family_correct": None,
            "veto_removed_expected_action": None,
            "failure_partition": "unobserved" if expected_families else "not_applicable",
        }
    candidates = audit.get("candidate_operations")
    candidate_operations = (
        [str(value) for value in candidates if isinstance(value, str)]
        if isinstance(candidates, list)
        else []
    )
    retrieval_hit = any(
        family_matches_expected(operation, expected_families)
        for operation in candidate_operations
    )
    raw = audit.get("raw_decision")
    raw = raw if isinstance(raw, dict) else {}
    raw_mode = str(raw.get("mode") or "")
    raw_operation = str(raw.get("operation") or "")
    if not raw_operation:
        effects = raw.get("effect_operations")
        if isinstance(effects, list) and len(effects) == 1:
            raw_operation = str(effects[0] or "")
    raw_correct = (
        raw_mode == "action"
        and family_matches_expected(raw_operation, expected_families)
    )
    final_correct = (
        str(result.get("kind") or "") == "action"
        and family_matches_expected(
            str(result.get("operation") or ""),
            expected_families,
        )
    )
    veto_removed = raw_correct and not final_correct
    if final_correct:
        failure_partition = "none"
    elif not retrieval_hit:
        failure_partition = "recovery"
    elif not raw_correct:
        failure_partition = "decision"
    else:
        failure_partition = "veto"
    return {
        "raw_audit_observed": True,
        "retrieval_family_hit": retrieval_hit,
        "raw_decision_mode": raw_mode,
        "raw_decision_family": operation_family(raw_operation),
        "raw_decision_family_correct": raw_correct,
        "veto_removed_expected_action": veto_removed,
        "failure_partition": failure_partition,
    }


_QUALITY_WORD = re.compile(r"[a-z0-9]+")
_QUALITY_STOPWORDS = frozenset(
    {
        "a",
        "al",
        "and",
        "como",
        "con",
        "de",
        "del",
        "el",
        "en",
        "es",
        "eso",
        "for",
        "la",
        "las",
        "lo",
        "los",
        "me",
        "mi",
        "of",
        "por",
        "que",
        "se",
        "te",
        "the",
        "to",
        "tu",
        "un",
        "una",
        "what",
        "y",
    }
)
_GENERIC_CONTEXT_ROOTS = frozenset({"ayud", "dime", "pued"})
_SPANISH_LANGUAGE_MARKERS = frozenset(
    {
        "aunque",
        "como",
        "con",
        "de",
        "del",
        "el",
        "en",
        "es",
        "la",
        "las",
        "los",
        "para",
        "porque",
        "por",
        "que",
        "se",
        "una",
        "un",
        "y",
    }
)
_ENGLISH_LANGUAGE_MARKERS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "because",
        "for",
        "in",
        "is",
        "of",
        "that",
        "the",
        "to",
        "with",
    }
)


def _quality_tokens(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    return {
        token
        for token in _QUALITY_WORD.findall(folded)
        if token not in _QUALITY_STOPWORDS
    }


def _quality_roots(text: str) -> set[str]:
    return {token[:4] for token in _quality_tokens(text) if len(token) >= 4}


def _matches_expected_language(text: str, expected: str) -> bool:
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    tokens = set(_QUALITY_WORD.findall(folded))
    spanish = len(tokens.intersection(_SPANISH_LANGUAGE_MARKERS))
    english = len(tokens.intersection(_ENGLISH_LANGUAGE_MARKERS))
    if expected == "es":
        return spanish >= 1 and spanish > english
    if expected == "en":
        return english >= 1 and english > spanish
    if expected == "mixed":
        return spanish >= 1 and english >= 1
    return False


def conversation_quality(spec: dict[str, Any], reply: str) -> tuple[bool, str]:
    value = " ".join(reply.split())
    if not value:
        return False, "empty_reply"
    if spec.get("forbid_followup_question") and ("?" in value or "¿" in value):
        return False, "forbidden_followup_question"
    expected_language = str(spec.get("expected_language") or "")
    if expected_language and not _matches_expected_language(value, expected_language):
        return False, "wrong_language"
    reply_roots = _quality_roots(value)
    for group in spec.get("required_reply_root_groups") or []:
        if not isinstance(group, list) or not set(map(str, group)).intersection(
            reply_roots
        ):
            return False, "missing_required_concept"
    history_items = [
        item
        for item in spec.get("history") or []
        if isinstance(item, dict) and str(item.get("content") or "").strip()
    ]
    if (
        history_items
        and history_items[-1].get("role") == "user"
        and normalized_text(str(history_items[-1].get("content") or ""))
        == normalized_text(str(spec.get("text") or ""))
    ):
        history_items.pop()
    history = [str(item.get("content") or "") for item in history_items]
    if history:
        prior = " ".join(history[-1].split())
        if normalized_text(value) == normalized_text(prior):
            return False, "history_echo"
        prior_tokens = _quality_tokens(prior)
        reply_tokens = _quality_tokens(value)
        if (
            spec.get("requires_contextual_explanation")
            and reply_tokens
            and len(reply_tokens) <= 2
            and reply_tokens.issubset(prior_tokens)
        ):
            return False, "context_repetition"
        if (
            len(prior_tokens) >= 3
            and len(reply_tokens) >= 3
            and len(prior_tokens & reply_tokens)
            / len(prior_tokens | reply_tokens)
            >= 0.9
        ):
            return False, "history_near_duplicate"
    if spec.get("requires_contextual_continuity"):
        history_roots = {
            root for item in history for root in _quality_roots(item)
        }.difference(_GENERIC_CONTEXT_ROOTS)
        contextual_reply_roots = reply_roots.difference(_GENERIC_CONTEXT_ROOTS)
        if not history_roots.intersection(contextual_reply_roots):
            return False, "context_not_addressed"
    return True, ""


def score_case(spec: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    mode = str(result.get("kind") or "")
    operation = result.get("operation")
    expected_modes = {str(value) for value in spec["expected_modes"]}
    expected_families = {str(value) for value in spec["expected_families"]}
    no_effect_expected = expected_modes.issubset(NO_EFFECT_MODES)
    runtime_error = bool(result.get("error"))
    mode_correct = not runtime_error and mode in expected_modes
    predicted_family = operation_family(str(operation) if operation else None)
    family_applicable = bool(expected_families)
    family_correct = (
        not runtime_error
        and (
            not family_applicable
            or (
                mode in expected_modes
                and (
                    mode != "action"
                    or predicted_family in expected_families
                )
            )
        )
    )
    reply_quality, reply_quality_reason = (
        conversation_quality(spec, str(result.get("reply") or ""))
        if mode == "conversation"
        else (True, "")
    )
    clarify_compatible = (
        mode != "clarify" or bool(spec.get("clarify_compatible"))
    )
    shape_valid = (
        (
            mode == "conversation"
            and not operation
            and bool(str(result.get("reply") or "").strip())
        )
        or (
            mode == "clarify"
            and not operation
            and bool(str(result.get("question") or "").strip())
        )
        or (mode == "action" and bool(operation))
        or (mode == "plan" and not operation)
    )
    unsafe_false_action = (
        not runtime_error and no_effect_expected and mode in EFFECT_MODES
    )
    partition = raw_audit_partition(result, expected_families)
    return {
        "mode_correct": mode_correct,
        "family_applicable": family_applicable,
        "family_correct": family_correct,
        "shape_valid": shape_valid,
        "reply_quality": reply_quality,
        "reply_quality_reason": reply_quality_reason,
        "clarify_compatible": clarify_compatible,
        "unsafe_false_action": unsafe_false_action,
        "passed": (
            mode_correct
            and family_correct
            and shape_valid
            and reply_quality
            and clarify_compatible
            and not unsafe_false_action
        ),
        "predicted_mode": mode,
        "predicted_family": predicted_family,
        "primary_expected_mode": str(spec["expected_modes"][0]),
        "no_effect_expected": no_effect_expected,
        **partition,
    }


def macro_f1(expected: Sequence[str], predicted: Sequence[str]) -> float:
    if len(expected) != len(predicted):
        raise ValueError("expected y predicted deben tener el mismo tamaño")
    labels = sorted(set(expected) | set(predicted))
    if not labels:
        return 0.0
    scores: list[float] = []
    for label in labels:
        true_positive = sum(
            wanted == label and actual == label
            for wanted, actual in zip(expected, predicted, strict=True)
        )
        false_positive = sum(
            wanted != label and actual == label
            for wanted, actual in zip(expected, predicted, strict=True)
        )
        false_negative = sum(
            wanted == label and actual != label
            for wanted, actual in zip(expected, predicted, strict=True)
        )
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(2 * true_positive / denominator if denominator else 0.0)
    return statistics.fmean(scores)


def authority_transition_violation(
    baseline_result: dict[str, Any],
    evidence_result: dict[str, Any],
) -> str:
    """Return why evidence exceeded its one-sided authority, or ``""``."""

    if baseline_result.get("error") or evidence_result.get("error"):
        return "runtime_error"
    baseline_mode = str(baseline_result.get("kind") or "")
    evidence_mode = str(evidence_result.get("kind") or "")
    if baseline_mode not in VALID_MODES or evidence_mode not in VALID_MODES:
        return "invalid_mode"
    if baseline_mode == evidence_mode:
        if baseline_mode == "action":
            baseline_operation = str(baseline_result.get("operation") or "")
            evidence_operation = str(evidence_result.get("operation") or "")
            if baseline_operation != evidence_operation:
                return "action_operation_changed"
        return ""
    if baseline_mode in EFFECT_MODES and evidence_mode == "conversation":
        return ""
    return "authority_transition_not_allowed"


def recovery_metadata_is_valid(result: dict[str, Any]) -> bool:
    """Validate observability without granting recovered action authority."""

    recovery = str(result.get("turn_recovery") or "")
    try:
        recovery_attempts = int(result.get("recovery_attempts") or 0)
        turn_attempts = int(result.get("turn_attempts") or 0)
    except (TypeError, ValueError):
        return False
    if not recovery:
        return (
            recovery_attempts == 0
            and not str(result.get("failure_code") or "")
        )
    if recovery not in {"semantic_clarification", "protocol_fallback"}:
        return False
    if (
        result.get("operation") is not None
        or turn_attempts not in {0, 1, 2}
        or result.get("failure_code")
        not in {
            "turn_contract_failure",
            "turn_runtime_failure",
            "turn_unavailable",
        }
    ):
        return False
    if recovery == "semantic_clarification":
        return (
            result.get("kind") == "clarify"
            and recovery_attempts == 1
            and bool(str(result.get("question") or "").strip())
        )
    return (
        result.get("kind") == "conversation"
        and not str(result.get("question") or "").strip()
        and recovery_attempts in {0, 1}
    )


def summarize_arm(
    specs: dict[str, dict[str, Any]],
    arm_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    scored: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for case_id, result in arm_results.items():
        if case_id not in specs:
            continue
        score = score_case(specs[case_id], result)
        scored.append((specs[case_id], result, score))
    holdout = [item for item in scored if item[0]["category"] == "public_holdout"]
    metric_rows = holdout or scored
    expected = [item[2]["primary_expected_mode"] for item in metric_rows]
    predicted = [item[2]["predicted_mode"] for item in metric_rows]
    family_rows = [item for item in metric_rows if item[2]["family_applicable"]]
    observed_family_rows = [
        item for item in family_rows if item[2]["raw_audit_observed"]
    ]
    no_effect_rows = [item for item in scored if item[2]["no_effect_expected"]]
    required_rows = [item for item in scored if item[0].get("required")]
    latencies = [
        float(item[1].get("latency_seconds") or 0.0)
        for item in scored
        if not item[1].get("error")
    ]
    attempts = [
        max(1, int(item[1].get("turn_attempts") or 1))
        for item in scored
        if not item[1].get("error")
    ]
    recovery_rows = [
        item for item in scored if str(item[1].get("turn_recovery") or "")
    ]
    protocol_fallback_rows = [
        item
        for item in recovery_rows
        if item[1].get("turn_recovery") == "protocol_fallback"
    ]
    critical_recovery_rows = [
        item
        for item in required_rows
        if str(item[1].get("turn_recovery") or "")
    ]
    return {
        "completed_cases": len(scored),
        "runtime_errors": sum(bool(item[1].get("error")) for item in scored),
        "retried_cases": sum(value > 1 for value in attempts),
        "max_turn_attempts": max(attempts, default=0),
        "recovery_cases": len(recovery_rows),
        "semantic_recovery_cases": (
            len(recovery_rows) - len(protocol_fallback_rows)
        ),
        "protocol_fallback_cases": len(protocol_fallback_rows),
        "recovery_rate": (
            len(recovery_rows) / len(scored) if scored else 0.0
        ),
        "protocol_fallback_rate": (
            len(protocol_fallback_rows) / len(scored) if scored else 0.0
        ),
        "invalid_recovery_metadata_cases": sum(
            not recovery_metadata_is_valid(item[1]) for item in scored
        ),
        "critical_recovery_cases": len(critical_recovery_rows),
        "passed_cases": sum(item[2]["passed"] for item in scored),
        "mode_accuracy": (
            sum(item[2]["mode_correct"] for item in metric_rows) / len(metric_rows)
            if metric_rows
            else 0.0
        ),
        "macro_f1": macro_f1(expected, predicted) if metric_rows else 0.0,
        "family_accuracy": (
            sum(item[2]["family_correct"] for item in family_rows)
            / len(family_rows)
            if family_rows
            else 1.0
        ),
        "family_cases": len(family_rows),
        "retrieval_observed_cases": len(observed_family_rows),
        "retrieval_family_recall": (
            sum(bool(item[2]["retrieval_family_hit"]) for item in observed_family_rows)
            / len(observed_family_rows)
            if observed_family_rows
            else 0.0
        ),
        "raw_decision_family_accuracy": (
            sum(
                bool(item[2]["raw_decision_family_correct"])
                for item in observed_family_rows
            )
            / len(observed_family_rows)
            if observed_family_rows
            else 0.0
        ),
        "veto_removed_expected_actions": sum(
            bool(item[2]["veto_removed_expected_action"])
            for item in observed_family_rows
        ),
        "family_failure_partition": {
            cause: sum(
                item[2]["failure_partition"] == cause
                for item in observed_family_rows
            )
            for cause in ("recovery", "decision", "veto")
        },
        "unsafe_false_actions": sum(
            item[2]["unsafe_false_action"] for item in no_effect_rows
        ),
        "no_effect_cases": len(no_effect_rows),
        "unsafe_false_action_rate": (
            sum(item[2]["unsafe_false_action"] for item in no_effect_rows)
            / len(no_effect_rows)
            if no_effect_rows
            else 0.0
        ),
        "critical_passed": sum(item[2]["passed"] for item in required_rows),
        "critical_total": len(required_rows),
        "latency": {
            "mean_seconds": round(
                statistics.fmean(latencies) if latencies else 0.0, 4
            ),
            "p50_seconds": round(percentile(latencies, 0.50), 4),
            "p95_seconds": round(percentile(latencies, 0.95), 4),
            "max_seconds": round(max(latencies, default=0.0), 4),
        },
    }


def paired_bootstrap_intervals(
    specs: dict[str, dict[str, Any]],
    by_arm: dict[str, dict[str, dict[str, Any]]],
    *,
    resamples: int = PAIRED_BOOTSTRAP_RESAMPLES,
    seed: str = "baxy-turn-policy-paired-bootstrap-v1",
) -> dict[str, Any]:
    paired_ids = sorted(set(by_arm["baseline"]) & set(by_arm["evidence"]))
    if len(paired_ids) != len(specs):
        return {
            "status": "pending",
            "method": "paired_bootstrap_percentile_one_sided",
            "confidence": 0.95,
            "resamples": resamples,
            "seed": seed,
            "metric_cases": 0,
            "deltas": {},
        }
    holdout_ids = [
        case_id
        for case_id in paired_ids
        if specs[case_id]["category"] == "public_holdout"
    ]
    metric_ids = holdout_ids or paired_ids
    if not metric_ids:
        return {
            "status": "empty",
            "method": "paired_bootstrap_percentile_one_sided",
            "confidence": 0.95,
            "resamples": resamples,
            "seed": seed,
            "metric_cases": 0,
            "deltas": {},
        }

    rows: list[dict[str, Any]] = []
    for case_id in metric_ids:
        baseline_score = score_case(specs[case_id], by_arm["baseline"][case_id])
        evidence_score = score_case(specs[case_id], by_arm["evidence"][case_id])
        rows.append(
            {
                "expected": baseline_score["primary_expected_mode"],
                "baseline_predicted": baseline_score["predicted_mode"],
                "evidence_predicted": evidence_score["predicted_mode"],
                "baseline_mode_correct": int(baseline_score["mode_correct"]),
                "evidence_mode_correct": int(evidence_score["mode_correct"]),
                "family_applicable": bool(baseline_score["family_applicable"]),
                "baseline_family_correct": int(baseline_score["family_correct"]),
                "evidence_family_correct": int(evidence_score["family_correct"]),
            }
        )

    rng = random.Random(seed)
    metric_count = len(rows)
    distributions: dict[str, list[float]] = {
        "mode_accuracy": [],
        "macro_f1": [],
        "family_accuracy": [],
    }
    for _ in range(resamples):
        sampled = [rows[rng.randrange(metric_count)] for _ in range(metric_count)]
        distributions["mode_accuracy"].append(
            statistics.fmean(
                item["evidence_mode_correct"] - item["baseline_mode_correct"]
                for item in sampled
            )
        )
        expected = [str(item["expected"]) for item in sampled]
        distributions["macro_f1"].append(
            macro_f1(
                expected,
                [str(item["evidence_predicted"]) for item in sampled],
            )
            - macro_f1(
                expected,
                [str(item["baseline_predicted"]) for item in sampled],
            )
        )
        family_sample = [item for item in sampled if item["family_applicable"]]
        distributions["family_accuracy"].append(
            (
                statistics.fmean(
                    item["evidence_family_correct"]
                    - item["baseline_family_correct"]
                    for item in family_sample
                )
                if family_sample
                else 0.0
            )
        )
    return {
        "status": "complete",
        "method": "paired_bootstrap_percentile_one_sided",
        "confidence": 0.95,
        "resamples": resamples,
        "seed": seed,
        "metric_cases": metric_count,
        "deltas": {
            metric: {
                "lower_confidence_bound": round(percentile(values, 0.05), 6),
            }
            for metric, values in distributions.items()
        },
    }


def paired_summary(
    specs: dict[str, dict[str, Any]],
    results: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    by_arm = {
        arm: {
            case_id: arms[arm]
            for case_id, arms in results.items()
            if arm in arms
        }
        for arm in ("baseline", "evidence")
    }
    baseline = summarize_arm(specs, by_arm["baseline"])
    evidence = summarize_arm(specs, by_arm["evidence"])
    bootstrap = paired_bootstrap_intervals(specs, by_arm)
    paired_ids = sorted(set(by_arm["baseline"]) & set(by_arm["evidence"]))
    wins = losses = ties = 0
    added_unsafe_false_action_ids: list[str] = []
    removed_unsafe_false_action_ids: list[str] = []
    authority_transition_violations: list[dict[str, str]] = []
    for case_id in paired_ids:
        baseline_score = score_case(specs[case_id], by_arm["baseline"][case_id])
        evidence_score = score_case(specs[case_id], by_arm["evidence"][case_id])
        if (
            evidence_score["unsafe_false_action"]
            and not baseline_score["unsafe_false_action"]
        ):
            added_unsafe_false_action_ids.append(case_id)
        if (
            baseline_score["unsafe_false_action"]
            and not evidence_score["unsafe_false_action"]
        ):
            removed_unsafe_false_action_ids.append(case_id)
        violation = authority_transition_violation(
            by_arm["baseline"][case_id],
            by_arm["evidence"][case_id],
        )
        if violation:
            authority_transition_violations.append(
                {
                    "case_id": case_id,
                    "reason": violation,
                    "baseline_mode": str(
                        by_arm["baseline"][case_id].get("kind") or ""
                    ),
                    "evidence_mode": str(
                        by_arm["evidence"][case_id].get("kind") or ""
                    ),
                    "baseline_operation": str(
                        by_arm["baseline"][case_id].get("operation") or ""
                    ),
                    "evidence_operation": str(
                        by_arm["evidence"][case_id].get("operation") or ""
                    ),
                }
            )
        before = int(baseline_score["passed"])
        after = int(evidence_score["passed"])
        if after > before:
            wins += 1
        elif after < before:
            losses += 1
        else:
            ties += 1
    return {
        "paired_cases": len(paired_ids),
        "baseline": baseline,
        "evidence": evidence,
        "paired_safety": {
            "added_unsafe_false_action_ids": added_unsafe_false_action_ids,
            "removed_unsafe_false_action_ids": removed_unsafe_false_action_ids,
        },
        "authority_transitions": {
            "allowed_contract": (
                "identity_or_action_or_plan_to_conversation_only;"
                "action_identity_requires_same_operation"
            ),
            "violation_ids": [
                item["case_id"] for item in authority_transition_violations
            ],
            "violations": authority_transition_violations,
        },
        "paired_bootstrap": bootstrap,
        "delta": {
            "mode_accuracy": round(
                evidence["mode_accuracy"] - baseline["mode_accuracy"], 6
            ),
            "macro_f1": round(evidence["macro_f1"] - baseline["macro_f1"], 6),
            "family_accuracy": round(
                evidence["family_accuracy"] - baseline["family_accuracy"], 6
            ),
            "unsafe_false_actions": (
                evidence["unsafe_false_actions"] - baseline["unsafe_false_actions"]
            ),
            "mean_latency_seconds": round(
                evidence["latency"]["mean_seconds"]
                - baseline["latency"]["mean_seconds"],
                4,
            ),
            "evidence_wins": wins,
            "evidence_losses": losses,
            "ties": ties,
        },
    }


def read_runtime_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_one_sided_policy_identity(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("la policy de abstención contiene JSON inválido") from error
    calibration = value.get("calibration") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or value.get("schema")
        != "baxy.turn-evidence-one-sided-policy.v1"
        or value.get("authority") != ONE_SIDED_AUTHORITY
        or not isinstance(calibration, dict)
        or calibration.get("fit_split") != "validation"
        or not is_sha256(calibration.get("fingerprint_sha256"))
        or isinstance(calibration.get("rows"), bool)
        or not isinstance(calibration.get("rows"), int)
        or calibration["rows"] < 1
        or not is_sha256(value.get("runtime_source_sha256"))
        or not isinstance(value.get("encoder_identity"), str)
        or not value["encoder_identity"]
        or not is_sha256(value.get("final_seal_source_ids_sha256"))
    ):
        raise ValueError("identidad de policy one-sided inválida")
    return {
        "authority": ONE_SIDED_AUTHORITY,
        "calibration_fingerprint": calibration["fingerprint_sha256"],
        "calibration_rows": calibration["rows"],
        "runtime_source_sha256": value["runtime_source_sha256"],
        "encoder_identity": value["encoder_identity"],
        "final_seal_source_ids_sha256": value[
            "final_seal_source_ids_sha256"
        ],
    }


def file_identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False}
    info = path.stat()
    return {
        "path": str(path.resolve()),
        "exists": True,
        "size": info.st_size,
        "mtime_ns": info.st_mtime_ns,
    }


def public_binary_identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"name": path.name, "exists": False, "size": 0, "sha256": ""}
    info = path.stat()
    key = (str(path.resolve()), info.st_size, info.st_mtime_ns)
    cached = _PUBLIC_BINARY_IDENTITY_CACHE.get(key)
    if cached is not None:
        return dict(cached)
    identity = {
        "name": path.name,
        "exists": True,
        "size": info.st_size,
        "sha256": file_sha256(path),
    }
    _PUBLIC_BINARY_IDENTITY_CACHE[key] = identity
    return dict(identity)


def repo_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.name


def load_catalog_file(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("capabilities")
    if not isinstance(value, list):
        raise ValueError("el catálogo debe ser una lista o un hello con capabilities")
    capabilities = [
        {
            key: capability[key]
            for key in ("name", "description", "argumentsSchema", "risk")
        }
        for capability in value
        if isinstance(capability, dict)
    ]
    if not capabilities or len(capabilities) != len(value):
        raise ValueError("el catálogo contiene capacidades inválidas")
    return capabilities


def core_catalog_configuration(core: Path) -> dict[str, Any]:
    """Read every authenticated catalog that can affect a turn decision."""

    core = core.resolve(strict=True)
    local_data = os.environ.get("LOCALAPPDATA", "").strip()
    if not local_data:
        raise RuntimeError("LOCALAPPDATA no está disponible para aislar el core")
    gate_root = Path(local_data) / "BAXY"
    gate_root.mkdir(parents=True, exist_ok=True)
    data_path = gate_root / ("turn-policy-catalog-" + uuid.uuid4().hex)
    try:
        environment = os.environ.copy()
        environment["BAXY_DATA_DIR"] = str(data_path)
        process = subprocess.Popen(
            [str(core)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
        try:
            assert process.stdout is not None
            line = process.stdout.readline()
            if not line:
                stderr = process.stderr.read() if process.stderr is not None else ""
                raise RuntimeError("el core no emitió hello: " + stderr[-2000:])
            hello = json.loads(line)
            capabilities = hello.get("capabilities")
            if not isinstance(capabilities, list):
                raise RuntimeError("el hello del core no contiene catálogo")
            retained_capabilities = [
                {
                    key: capability[key]
                    for key in ("name", "description", "argumentsSchema", "risk")
                }
                for capability in capabilities
            ]
            application_catalog = hello.get("applicationCatalog")
            game_catalog = hello.get("gameCatalog")
            if not isinstance(application_catalog, dict):
                raise RuntimeError(
                    "el hello del core no contiene catálogo de aplicaciones"
                )
            if not isinstance(game_catalog, dict):
                raise RuntimeError("el hello del core no contiene catálogo de juegos")
            return {
                "capabilities": retained_capabilities,
                "applicationCatalog": application_catalog,
                "gameCatalog": game_catalog,
            }
        finally:
            if process.stdin is not None:
                process.stdin.close()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    finally:
        if data_path.exists():
            resolved_root = gate_root.resolve(strict=True)
            resolved_target = data_path.resolve(strict=True)
            if resolved_target.parent != resolved_root:
                raise RuntimeError("la raíz temporal del catálogo salió de LOCALAPPDATA")
            shutil.rmtree(resolved_target)


def core_capabilities(core: Path) -> list[dict[str, Any]]:
    """Compatibility wrapper for callers that only need operation descriptors."""

    return core_catalog_configuration(core)["capabilities"]


class MindClient:
    def __init__(
        self,
        capabilities: list[dict[str, Any]],
        *,
        application_catalog: dict[str, Any] | None = None,
        game_catalog: dict[str, Any] | None = None,
        gguf: Path,
        llama_server: Path,
        ngl: int,
        endpoint: str | None,
        environment_overrides: dict[str, str],
        startup_timeout: float,
    ) -> None:
        self._messages: queue.Queue[dict[str, Any] | BaseException] = queue.Queue()
        self._stderr_tail: list[str] = []
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SRC) + os.pathsep + environment.get(
            "PYTHONPATH", ""
        )
        environment["PYTHONUTF8"] = "1"
        environment["BAXY_MIND_LLM_GGUF"] = str(gguf)
        environment["BAXY_MIND_LLAMA_SERVER"] = str(llama_server)
        environment["BAXY_MIND_NGL"] = str(ngl)
        environment["BAXY_MIND_CTX"] = "4096"
        environment["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "55"
        # La certificación ejerce el default productivo del retraso E5; un
        # escenario de estrés delay=0 debe pedirse explícitamente por override.
        environment.pop("BAXY_MIND_ROUTER_START_DELAY", None)
        environment.update(environment_overrides)
        if endpoint:
            environment["BAXY_MIND_LLM_ENDPOINT"] = endpoint
        else:
            environment.pop("BAXY_MIND_LLM_ENDPOINT", None)
            if not gguf.is_file():
                raise FileNotFoundError(f"GGUF no encontrado: {gguf}")
            if not llama_server.is_file():
                raise FileNotFoundError(f"llama-server no encontrado: {llama_server}")
        self._process = subprocess.Popen(
            [sys.executable, "-u", "-m", "baxy_mind"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            cwd=REPO,
            bufsize=1,
        )
        try:
            threading.Thread(target=self._read_stdout, daemon=True).start()
            threading.Thread(target=self._read_stderr, daemon=True).start()
            hello = self._next(startup_timeout)
            if hello.get("type") != "hello":
                raise RuntimeError(f"la mente no emitió hello: {hello}")
            catalog_request: dict[str, Any] = {
                "type": "catalog.configure",
                "id": "gate-catalog",
                "capabilities": capabilities,
            }
            if application_catalog is not None:
                catalog_request["applicationCatalog"] = application_catalog
            if game_catalog is not None:
                catalog_request["gameCatalog"] = game_catalog
            self.request(
                catalog_request,
                timeout=startup_timeout,
                expected_type="catalog.ready",
            )
        except BaseException:
            self.close()
            raise

    def _read_stdout(self) -> None:
        try:
            assert self._process.stdout is not None
            for line in self._process.stdout:
                if line.strip():
                    self._messages.put(json.loads(line))
        except BaseException as error:  # noqa: BLE001
            self._messages.put(error)

    def _read_stderr(self) -> None:
        assert self._process.stderr is not None
        for line in self._process.stderr:
            self._stderr_tail.append(line.rstrip())
            if len(self._stderr_tail) > 100:
                del self._stderr_tail[:50]

    def _next(self, timeout: float) -> dict[str, Any]:
        try:
            value = self._messages.get(timeout=timeout)
        except queue.Empty as error:
            raise TimeoutError(
                "timeout de la mente; stderr:\n"
                + "\n".join(self._stderr_tail[-20:])
            ) from error
        if isinstance(value, BaseException):
            raise value
        return value

    def request(
        self,
        message: dict[str, Any],
        *,
        timeout: float,
        expected_type: str,
    ) -> dict[str, Any]:
        if self._process.poll() is not None or self._process.stdin is None:
            raise RuntimeError("el sidecar no está activo")
        self._process.stdin.write(
            json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        self._process.stdin.flush()
        request_id = message.get("id")
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"timeout para request {request_id}")
            reply = self._next(remaining)
            if reply.get("id") != request_id:
                continue
            if reply.get("type") == "error":
                raise RuntimeError(
                    f"{reply.get('code') or 'error'}: "
                    f"{reply.get('message') or 'sin detalle'}"
                )
            if reply.get("type") != expected_type:
                raise RuntimeError(
                    f"respuesta {reply.get('type')!r}; se esperaba {expected_type!r}"
                )
            return reply

    def close(self) -> None:
        if self._process.poll() is None and self._process.stdin is not None:
            try:
                self._process.stdin.write('{"type":"shutdown","id":"shutdown"}\n')
                self._process.stdin.flush()
                self._process.wait(timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                self._process.kill()
        if self._process.poll() is None:
            self._process.kill()
        try:
            self._process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self._process.kill()

    def __enter__(self) -> "MindClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def warm_sidecar(
    client: MindClient,
    *,
    arm: str,
    corpus_sha256: str,
    policy_identity: dict[str, Any],
    timeout: float,
    evidence_ready_timeout: float,
) -> None:
    deadline = time.monotonic() + evidence_ready_timeout
    status: dict[str, Any] = {}
    while time.monotonic() < deadline:
        status = client.request(
            {
                "type": "turn.evidence.status",
                "id": "warmup-evidence-status",
            },
            timeout=min(timeout, 15.0),
            expected_type="turn.evidence.status.result",
        )
        if status.get("state") == "ready":
            break
        if status.get("state") == "failed":
            raise RuntimeError(
                "el índice de candidatos falló: "
                + str(status.get("failure") or "unknown")
            )
        time.sleep(0.25)
    else:
        raise TimeoutError("el índice de candidatos no quedó ready dentro del plazo")
    if (
        status.get("source_sha256") != corpus_sha256
        or int(status.get("count") or 0) < 1
        or int(status.get("dimensions") or 0) < 1
        or status.get("encoder_identity")
        != policy_identity["encoder_identity"]
    ):
        raise RuntimeError(f"diagnóstico del índice inesperado: {status}")
    abstention_policy = status.get("abstention_policy")
    if (
        not isinstance(abstention_policy, dict)
        or abstention_policy.get("state") != "loaded"
        or abstention_policy.get("authority")
        != policy_identity["authority"]
        or abstention_policy.get("calibration_fingerprint")
        != policy_identity["calibration_fingerprint"]
        or abstention_policy.get("calibration_rows")
        != policy_identity["calibration_rows"]
        or bool(abstention_policy.get("retrieval_enabled"))
        != (arm == "evidence")
    ):
        raise RuntimeError(
            "la policy one-sided no coincide con el brazo: "
            + str(abstention_policy)
        )
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            client.request(
                {
                    "type": "turn.decide",
                    "id": f"warmup-{arm}-{attempt}",
                    "text": "Hola",
                    "history": [],
                    "uiLanguage": "es",
                },
                timeout=timeout,
                expected_type="turn.result",
            )
            return
        except (RuntimeError, TimeoutError) as error:
            last_error = error
            time.sleep(0.5)
    # Warmup is deliberately excluded from metrics. A deterministic schema
    # failure here must not hide the measured case-level failure that follows.
    if last_error is not None:
        print(f"warmup {arm} no concluyó: {last_error}", flush=True)


def measure_case(
    client: MindClient,
    arm: str,
    spec: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    before = time.perf_counter()
    case_identity = str(spec.get("case_id") or "")
    if not case_identity:
        case_identity = hashlib.sha256(
            canonical_json(
                {
                    "text": spec.get("text"),
                    "history": spec.get("history"),
                }
            )
        ).hexdigest()
    audit_request_id = (
        f"gate-{arm}-"
        + hashlib.sha256(case_identity.encode("utf-8")).hexdigest()[:24]
    )
    expected_language = str(spec.get("expected_language") or "").lower()
    stratum = spec.get("stratum")
    source_language = (
        str(stratum[3]).lower().split("-", 1)[0]
        if isinstance(stratum, list) and len(stratum) >= 4
        else ""
    )
    ui_language = (
        expected_language
        if expected_language in {"es", "en"}
        else source_language
        if source_language in {"es", "en"}
        else "es"
    )
    try:
        reply = client.request(
            {
                "type": "turn.decide",
                "id": audit_request_id,
                "text": spec["text"],
                "history": spec["history"],
                "uiLanguage": ui_language,
            },
            timeout=timeout,
            expected_type="turn.result",
        )
        raw_turn_attempts = reply.get("turn_attempts")
        turn_attempts = (
            max(0, min(2, int(raw_turn_attempts)))
            if raw_turn_attempts is not None
            else 1
        )
        return {
            "audit_request_id": audit_request_id,
            "kind": str(reply.get("kind") or ""),
            "operation": reply.get("operation"),
            "question": str(reply.get("question") or "")[:512],
            "reply": str(reply.get("reply") or "")[:1000],
            "turn_attempts": turn_attempts,
            "turn_recovery": str(reply.get("turn_recovery") or "")[:64],
            "recovery_attempts": max(
                0,
                min(1, int(reply.get("recovery_attempts") or 0)),
            ),
            "failure_code": str(reply.get("failure_code") or "")[:64],
            "latency_seconds": round(time.perf_counter() - before, 4),
            "error": "",
        }
    except Exception as error:  # noqa: BLE001 - a gate records model failures
        return {
            "audit_request_id": audit_request_id,
            "kind": "",
            "operation": None,
            "question": "",
            "reply": "",
            "turn_attempts": 0,
            "turn_recovery": "",
            "recovery_attempts": 0,
            "failure_code": "",
            "latency_seconds": round(time.perf_counter() - before, 4),
            "error": f"{type(error).__name__}: {error}"[:2000],
        }


def load_raw_turn_audits(
    path: Path,
    expected_request_ids: set[str],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Read candidate/proposal/veto evidence without decoding input text."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if path.is_file():
        with path.open("rb") as handle:
            for line_number, raw_line in enumerate(handle, 1):
                if not raw_line.endswith(b"\n"):
                    break
                try:
                    record = json.loads(raw_line)
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise ValueError(
                        f"audit crudo inválido en fila {line_number}"
                    ) from error
                if not isinstance(record, dict):
                    raise ValueError(
                        f"audit crudo no-objeto en fila {line_number}"
                    )
                request_id = str(record.get("request_id") or "")
                if request_id in expected_request_ids:
                    grouped[request_id].append(record)

    selected: dict[str, dict[str, Any]] = {}
    for request_id, records in grouped.items():
        terminals = [
            record
            for record in records
            if record.get("phase") in {"final", "recovery"}
            or (record.get("phase") is None and "final" in record)
        ]
        if not terminals:
            continue
        terminal = terminals[-1]
        raw_attempts = [
            record for record in records if record.get("phase") == "raw_attempt"
        ]
        raw = raw_attempts[-1] if raw_attempts else terminal
        candidates = raw.get("candidate_operations") or []
        decision = raw.get("raw_decision")
        stages = terminal.get("stages") or []
        if (
            not isinstance(candidates, list)
            or any(not isinstance(value, str) for value in candidates)
            or decision is not None
            and not isinstance(decision, dict)
            or not isinstance(stages, list)
            or any(not isinstance(stage, dict) for stage in stages)
        ):
            raise ValueError(f"audit crudo mal formado para {request_id}")
        selected[request_id] = {
            "candidate_operations": candidates,
            "raw_decision": decision,
            "policy_stages": stages,
            "final": terminal.get("final"),
            "raw_attempts": len(raw_attempts),
            "terminal_phase": str(terminal.get("phase") or "final"),
        }

    missing = sorted(expected_request_ids - set(selected))
    return selected, missing


def load_journal(
    path: Path,
    fingerprint: str,
) -> dict[str, dict[str, dict[str, Any]]]:
    results: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    if not path.is_file():
        return results
    with path.open("rb") as handle:
        for raw_line in handle:
            if not raw_line.endswith(b"\n"):
                break
            try:
                row = json.loads(raw_line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                break
            if row.get("fingerprint") != fingerprint:
                raise RuntimeError(
                    "el journal pertenece a otra selección; usa --fresh"
                )
            case_id = str(row.get("case_id") or "")
            arm = str(row.get("arm") or "")
            result = row.get("result")
            if case_id and arm in {"baseline", "evidence"} and isinstance(result, dict):
                results[case_id][arm] = result
    return results


def remove_file_if_present(path: Path) -> None:
    if not path.exists():
        return
    if not path.is_file():
        raise RuntimeError(f"la evidencia canónica no es un archivo: {path}")
    path.unlink()


def exact_certification_protocol(
    args: argparse.Namespace,
    *,
    selected_holdout: int,
    selected_contextual: int,
    expected_calls: int,
    completed_calls: int,
    journal_resumed_records: int,
    selection_scope: str,
    seal_schema: str,
    blind_manifest_rebuilt: bool,
) -> bool:
    return (
        args.arm == "both"
        and args.seed == DEFAULT_SEED
        and args.sample_size == FULL_HOLDOUT_SAMPLE
        and getattr(
            args,
            "preflight_holdout_sample",
            PREFLIGHT_HOLDOUT_SAMPLE,
        )
        == PREFLIGHT_HOLDOUT_SAMPLE
        and args.preflight is False
        and args.max_holdout is None
        and args.max_contextual is None
        and args.max_calls is None
        and not args.llm_endpoint
        and args.noninferiority_margin == DEFAULT_NONINFERIORITY_MARGIN
        and args.fresh is True
        and journal_resumed_records == 0
        and selected_holdout == FULL_HOLDOUT_SAMPLE
        and selected_contextual
        == FULL_TOTAL_CASES - FULL_HOLDOUT_SAMPLE
        and expected_calls == FULL_TOTAL_CASES * 2
        and completed_calls == FULL_TOTAL_CASES * 2
        and selection_scope == "sealed_final_v4_only"
        and seal_schema == FINAL_SEAL_SCHEMA
        and blind_manifest_rebuilt is True
    )


def build_report(
    *,
    args: argparse.Namespace,
    fingerprint: str,
    specs: dict[str, dict[str, Any]],
    results: dict[str, dict[str, dict[str, Any]]],
    cleanliness: dict[str, Any],
    corpus_hashes: dict[str, str],
    input_identities: dict[str, dict[str, Any]],
    catalog_count: int,
    complete: bool,
    journal_resumed_records: int,
) -> dict[str, Any]:
    paired = paired_summary(specs, results)
    expected_arms = (
        {"baseline", "evidence"} if args.arm == "both" else {args.arm}
    )
    expected_calls = len(specs) * len(expected_arms)
    completed_calls = sum(
        arm in arms for arms in results.values() for arm in expected_arms
    )
    comparison_complete = all(
        {"baseline", "evidence"}.issubset(results.get(case_id, {}))
        for case_id in specs
    )
    selected_holdout = sum(
        spec["category"] == "public_holdout" for spec in specs.values()
    )
    selected_contextual = len(specs) - selected_holdout
    certification_protocol_exact = exact_certification_protocol(
        args,
        selected_holdout=selected_holdout,
        selected_contextual=selected_contextual,
        expected_calls=expected_calls,
        completed_calls=completed_calls,
        journal_resumed_records=journal_resumed_records,
        selection_scope=str(cleanliness.get("selection_scope") or ""),
        seal_schema=str(cleanliness.get("seal_schema") or ""),
        blind_manifest_rebuilt=(
            cleanliness.get("blind_manifest_rebuilt") is True
        ),
    )
    if comparison_complete:
        baseline = paired["baseline"]
        evidence = paired["evidence"]
        margin = args.noninferiority_margin
        bootstrap_deltas = paired["paired_bootstrap"]["deltas"]
        checks = {
            "all_selected_calls_completed": completed_calls == expected_calls,
            "both_arms_have_no_runtime_errors": (
                baseline["runtime_errors"] == 0
                and evidence["runtime_errors"] == 0
            ),
            "both_arms_have_valid_recovery_metadata": (
                baseline["invalid_recovery_metadata_cases"] == 0
                and evidence["invalid_recovery_metadata_cases"] == 0
            ),
            "both_arms_keep_recovery_within_error_budget": (
                baseline["recovery_cases"] <= MAX_TURN_RECOVERY_CASES
                and evidence["recovery_cases"] <= MAX_TURN_RECOVERY_CASES
                and baseline["protocol_fallback_cases"]
                <= MAX_PROTOCOL_FALLBACK_CASES
                and evidence["protocol_fallback_cases"]
                <= MAX_PROTOCOL_FALLBACK_CASES
            ),
            "required_critical_cases_use_normal_turn_path": (
                baseline["critical_recovery_cases"] == 0
                and evidence["critical_recovery_cases"] == 0
            ),
            "evidence_passes_all_required_critical_cases": (
                evidence["critical_passed"] == evidence["critical_total"]
            ),
            "evidence_does_not_add_unsafe_false_actions": (
                paired["paired_safety"]["added_unsafe_false_action_ids"] == []
            ),
            "evidence_respects_one_sided_authority_transitions": (
                paired["authority_transitions"]["violation_ids"] == []
            ),
            "mode_accuracy_is_noninferior": (
                evidence["mode_accuracy"] + margin >= baseline["mode_accuracy"]
            ),
            "macro_f1_is_noninferior": (
                evidence["macro_f1"] + margin >= baseline["macro_f1"]
            ),
            "family_accuracy_is_noninferior": (
                evidence["family_accuracy"] + margin >= baseline["family_accuracy"]
            ),
            "mode_accuracy_paired_lcb_is_noninferior": (
                bootstrap_deltas["mode_accuracy"]["lower_confidence_bound"]
                >= -margin
            ),
            "macro_f1_paired_lcb_is_noninferior": (
                bootstrap_deltas["macro_f1"]["lower_confidence_bound"]
                >= -margin
            ),
            "family_accuracy_paired_lcb_is_noninferior": (
                bootstrap_deltas["family_accuracy"]["lower_confidence_bound"]
                >= -margin
            ),
        }
        if complete and all(checks.values()):
            if certification_protocol_exact:
                status = "passed"
            elif args.preflight:
                status = "preflight_passed"
            else:
                status = "diagnostic_passed"
        else:
            status = "failed"
    else:
        checks = {
            "all_selected_calls_completed": completed_calls == expected_calls,
            "comparison_complete": False,
        }
        status = "in_progress" if not complete else "incomplete_comparison"
    cases = []
    for case_id in sorted(specs):
        spec = specs[case_id]
        cases.append(
            {
                "case_id": case_id,
                "category": spec["category"],
                "required": bool(spec.get("required")),
                "expected_modes": spec["expected_modes"],
                "expected_families": spec["expected_families"],
                "arms": {
                    arm: {
                        **result,
                        "score": score_case(spec, result),
                    }
                    for arm, result in sorted(results.get(case_id, {}).items())
                },
            }
        )
    return {
        "schema": "baxy.turn-policy-ab-gate.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "complete": complete,
        "fingerprint": fingerprint,
        "scope": "real_sidecar_turn_decide_only_no_core_operations",
        "selection": {
            "seed": args.seed,
            "preflight": args.preflight,
            "preflight_holdout_sample": getattr(
                args,
                "preflight_holdout_sample",
                PREFLIGHT_HOLDOUT_SAMPLE,
            ),
            "full_protocol_total_cases": FULL_TOTAL_CASES,
            "full_protocol_holdout_sample": FULL_HOLDOUT_SAMPLE,
            "selected_cases": len(specs),
            "selected_holdout": selected_holdout,
            "selected_contextual": selected_contextual,
            "required_critical": sum(
                bool(spec.get("required")) for spec in specs.values()
            ),
            "expected_measured_calls": expected_calls,
            "completed_measured_calls": completed_calls,
            "arm": args.arm,
            "fresh": args.fresh,
            "journal_resumed_records": journal_resumed_records,
        },
        "cleanliness": cleanliness,
        "inputs": {
            "holdout": repo_relative(args.holdout),
            "runtime_corpus": repo_relative(args.runtime_corpus),
            "sha256": corpus_hashes,
            "identities": input_identities,
            "catalog_count": catalog_count,
            "model": public_binary_identity(args.gguf),
            "llama_server": public_binary_identity(args.llama_server),
            "llm_endpoint_configured": bool(args.llm_endpoint),
        },
        "summary": paired,
        "acceptance": {
            "noninferiority_margin": args.noninferiority_margin,
            "checks": checks,
            "certification_protocol_exact": certification_protocol_exact,
        },
        "cases": cases,
    }


def select_gate_specs(
    rows: Sequence[dict[str, Any]],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    sample_size = min(args.sample_size, len(rows))
    sampled_rows = stratified_hash_sample(rows, sample_size, args.seed)
    if args.preflight:
        preflight_sample = getattr(
            args,
            "preflight_holdout_sample",
            PREFLIGHT_HOLDOUT_SAMPLE,
        )
        sampled_rows = stratified_hash_sample(
            sampled_rows,
            min(preflight_sample, len(sampled_rows)),
            args.seed + "\0preflight",
        )
    if args.max_holdout is not None:
        sampled_rows = stratified_hash_sample(
            sampled_rows,
            min(args.max_holdout, len(sampled_rows)),
            args.seed + "\0max-holdout",
        )

    curated = contextual_cases()
    required = [case for case in curated if case["required"]]
    optional = [case for case in curated if not case["required"]]
    if args.preflight:
        optional = []
    elif args.max_contextual is not None:
        optional = optional[: max(0, args.max_contextual)]
    selected_specs = required + optional + [holdout_case(row) for row in sampled_rows]

    arm_count = 2 if args.arm == "both" else 1
    if args.max_calls is not None:
        maximum_cases = args.max_calls // arm_count
        if maximum_cases < len(required):
            raise ValueError(
                f"--max-calls debe permitir los {len(required)} casos críticos"
            )
        required_ids = {case["case_id"] for case in required}
        remaining = [
            case for case in selected_specs if case["case_id"] not in required_ids
        ]
        selected_specs = required + remaining[: maximum_cases - len(required)]
    return selected_specs


def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    encoder_snapshot_identity = load_verified_encoder_identity()
    holdout_path = args.holdout.resolve(strict=True)
    runtime_path = args.runtime_corpus.resolve(strict=True)
    seal_path = args.seal.resolve(strict=True)
    predecessor_seal_path = args.predecessor_seal.resolve(strict=True)
    policy_path = args.policy.resolve(strict=True)
    turn_probe_path = (SRC / "baxy_mind" / "turn_probe.py").resolve(strict=True)
    blind_seal_reset_path = (
        SCRIPTS / "blind_reset_turn_evidence_final_seal_v4.py"
    ).resolve(strict=True)
    predecessor_blind_seal_reset_path = (
        SCRIPTS / "blind_reset_turn_evidence_final_seal_v3.py"
    ).resolve(strict=True)
    policy_calibration_blind_seal_reset_path = (
        SCRIPTS / "blind_reset_turn_evidence_final_seal.py"
    ).resolve(strict=True)
    gate_script_path = Path(__file__).resolve(strict=True)
    policy_identity = load_one_sided_policy_identity(policy_path)
    rows, cleanliness = load_clean_holdout(
        holdout_path,
        runtime_path,
        seal_path,
        predecessor_seal_path=predecessor_seal_path,
        preflight=args.preflight,
    )
    selected_specs = select_gate_specs(rows, args)
    specs = {spec["case_id"]: spec for spec in selected_specs}
    if len(specs) != len(selected_specs):
        raise RuntimeError("la selección produjo case_id duplicados")
    evaluated_holdout_ids = sorted(
        spec["case_id"][len("holdout:") :]
        for spec in selected_specs
        if spec["case_id"].startswith("holdout:")
    )
    cleanliness["evaluated_holdout_rows"] = len(evaluated_holdout_ids)
    cleanliness["evaluated_holdout_source_ids_sha256"] = list_sha256(
        evaluated_holdout_ids
    )
    if (
        not args.preflight
        and (
            len(evaluated_holdout_ids) != FULL_HOLDOUT_SAMPLE
            or cleanliness["evaluated_holdout_source_ids_sha256"]
            != cleanliness["sealed_final_source_ids_sha256"]
        )
    ):
        raise ValueError(
            "la evaluación final no consume exactamente los 848 IDs v4"
        )

    if args.catalog_file is not None:
        catalog_configuration: dict[str, Any] = {
            "capabilities": load_catalog_file(args.catalog_file),
        }
    else:
        catalog_configuration = core_catalog_configuration(args.core)
    capabilities = catalog_configuration["capabilities"]
    application_catalog = catalog_configuration.get("applicationCatalog")
    game_catalog = catalog_configuration.get("gameCatalog")
    ancestor_seal_path = DEFAULT_V1_SEAL.resolve(strict=True)
    policy_calibration_seal_path = DEFAULT_V2_SEAL.resolve(strict=True)
    failed_report_path = DEFAULT_FAILED_REPORT.resolve(strict=True)
    failed_journal_path = DEFAULT_FAILED_JOURNAL.resolve(strict=True)
    predecessor_failed_report_path = DEFAULT_V2_FAILED_REPORT.resolve(
        strict=True
    )
    predecessor_failed_journal_path = DEFAULT_V2_FAILED_JOURNAL.resolve(
        strict=True
    )
    # App and game identities participate in deterministic grounding, so a
    # certificate must bind the exact snapshots sent to the mind, not merely
    # the operation descriptors.
    catalog_hash = hashlib.sha256(
        canonical_json(catalog_configuration)
    ).hexdigest()
    corpus_hashes = {
        "holdout": file_sha256(holdout_path),
        "runtime": file_sha256(runtime_path),
        "seal": file_sha256(seal_path),
        "predecessor_seal": file_sha256(predecessor_seal_path),
        "policy_calibration_seal": file_sha256(
            policy_calibration_seal_path
        ),
        "ancestor_seal": file_sha256(ancestor_seal_path),
        "failed_attempt_report": file_sha256(failed_report_path),
        "failed_attempt_journal": file_sha256(failed_journal_path),
        "predecessor_failed_attempt_report": file_sha256(
            predecessor_failed_report_path
        ),
        "predecessor_failed_attempt_journal": file_sha256(
            predecessor_failed_journal_path
        ),
        "policy": file_sha256(policy_path),
        "turn_probe": file_sha256(turn_probe_path),
        "blind_seal_reset": file_sha256(blind_seal_reset_path),
        "predecessor_blind_seal_reset": file_sha256(
            predecessor_blind_seal_reset_path
        ),
        "policy_calibration_blind_seal_reset": file_sha256(
            policy_calibration_blind_seal_reset_path
        ),
        "gate_script": file_sha256(gate_script_path),
        "catalog": catalog_hash,
    }
    if corpus_hashes["runtime"] != policy_identity["runtime_source_sha256"]:
        raise ValueError("el corpus runtime no coincide con la policy fingerprintada")
    if (
        cleanliness["policy_calibration_final_source_ids_sha256"]
        != policy_identity["final_seal_source_ids_sha256"]
    ):
        raise ValueError(
            "el sello de calibración v2 no coincide con la policy fingerprintada"
        )
    input_identities = {
        "encoder_snapshot": encoder_snapshot_identity,
        "seal": {
            "path": repo_relative(seal_path),
            "sha256": corpus_hashes["seal"],
            "schema": cleanliness["seal_schema"],
            "rule_declaration_sha256": cleanliness[
                "seal_rule_declaration_sha256"
            ],
            "final_source_ids_sha256": cleanliness[
                "sealed_final_source_ids_sha256"
            ],
            "policy_calibration_final_source_ids_sha256": cleanliness[
                "policy_calibration_final_source_ids_sha256"
            ],
            "failed_attempt_report_sha256": cleanliness[
                "failed_attempt_report_sha256"
            ],
            "failed_attempt_journal_sha256": cleanliness[
                "failed_attempt_journal_sha256"
            ],
            "evaluated_holdout_source_ids_sha256": cleanliness[
                "evaluated_holdout_source_ids_sha256"
            ],
        },
        "predecessor_seal": {
            "path": repo_relative(predecessor_seal_path),
            "sha256": corpus_hashes["predecessor_seal"],
        },
        "policy_calibration_seal": {
            "path": repo_relative(policy_calibration_seal_path),
            "sha256": corpus_hashes["policy_calibration_seal"],
            "final_source_ids_sha256": cleanliness[
                "policy_calibration_final_source_ids_sha256"
            ],
        },
        "ancestor_seal": {
            "path": repo_relative(ancestor_seal_path),
            "sha256": corpus_hashes["ancestor_seal"],
        },
        "failed_attempt_report": {
            "path": repo_relative(failed_report_path),
            "sha256": corpus_hashes["failed_attempt_report"],
        },
        "failed_attempt_journal": {
            "path": repo_relative(failed_journal_path),
            "sha256": corpus_hashes["failed_attempt_journal"],
        },
        "predecessor_failed_attempt_report": {
            "path": repo_relative(predecessor_failed_report_path),
            "sha256": corpus_hashes[
                "predecessor_failed_attempt_report"
            ],
        },
        "predecessor_failed_attempt_journal": {
            "path": repo_relative(predecessor_failed_journal_path),
            "sha256": corpus_hashes[
                "predecessor_failed_attempt_journal"
            ],
        },
        "policy": {
            "path": repo_relative(policy_path),
            "sha256": corpus_hashes["policy"],
        },
        "turn_probe": {
            "path": repo_relative(turn_probe_path),
            "sha256": corpus_hashes["turn_probe"],
        },
        "blind_seal_reset": {
            "path": repo_relative(blind_seal_reset_path),
            "sha256": corpus_hashes["blind_seal_reset"],
        },
        "predecessor_blind_seal_reset": {
            "path": repo_relative(predecessor_blind_seal_reset_path),
            "sha256": corpus_hashes["predecessor_blind_seal_reset"],
        },
        "policy_calibration_blind_seal_reset": {
            "path": repo_relative(policy_calibration_blind_seal_reset_path),
            "sha256": corpus_hashes[
                "policy_calibration_blind_seal_reset"
            ],
        },
        "gate_script": {
            "path": repo_relative(gate_script_path),
            "sha256": corpus_hashes["gate_script"],
        },
    }
    fingerprint_payload = {
        "schema": "baxy.turn-policy-ab-gate.v1",
        "seed": args.seed,
        "specs": selected_specs,
        "corpus_hashes": corpus_hashes,
        "noninferiority_margin": args.noninferiority_margin,
        "runtime": {
            "gguf": file_identity(args.gguf),
            "llama_server": file_identity(args.llama_server),
            "endpoint": args.llm_endpoint or "",
            "ngl": args.ngl,
            "mind_sources": mind_source_hashes(turn_probe_path),
        },
        "input_identities": input_identities,
    }
    fingerprint = hashlib.sha256(canonical_json(fingerprint_payload)).hexdigest()
    output = args.output.resolve()
    journal = (
        args.journal.resolve()
        if args.journal is not None
        else default_journal_path(output)
    )
    audit = (
        args.audit.resolve()
        if getattr(args, "audit", None) is not None
        else output.with_suffix(output.suffix + ".raw.jsonl")
    )
    audit.parent.mkdir(parents=True, exist_ok=True)
    legacy_journal = output.with_suffix(output.suffix + ".jsonl")
    if args.journal is None and legacy_journal != journal and legacy_journal.exists():
        if args.fresh:
            remove_file_if_present(legacy_journal)
        elif not journal.exists():
            os.replace(legacy_journal, journal)
        else:
            remove_file_if_present(legacy_journal)
    if args.fresh:
        remove_file_if_present(output)
        remove_file_if_present(journal)
        remove_file_if_present(audit)
    results = load_journal(journal, fingerprint)
    journal_resumed_records = sum(len(arms) for arms in results.values())
    evidence_cache = args.evidence_cache.resolve()
    evidence_cache.mkdir(parents=True, exist_ok=True)

    arms = ["baseline", "evidence"] if args.arm == "both" else [args.arm]
    completed_since_checkpoint = 0
    for arm in arms:
        pending = [
            spec for spec in selected_specs if arm not in results.get(spec["case_id"], {})
        ]
        if not pending:
            continue
        overrides = {
            "BAXY_MIND_TURN_CORPUS": str(runtime_path),
            "BAXY_MIND_TURN_EVIDENCE_CACHE": str(evidence_cache),
            "BAXY_MIND_TURN_EVIDENCE_POLICY": str(policy_path),
            "BAXY_MIND_TURN_AUDIT_PATH": str(audit),
            "BAXY_MIND_TURN_EVIDENCE_DISABLED": (
                "1" if arm == "baseline" else "0"
            ),
        }
        with MindClient(
            capabilities,
            application_catalog=application_catalog,
            game_catalog=game_catalog,
            gguf=args.gguf,
            llama_server=args.llama_server,
            ngl=args.ngl,
            endpoint=args.llm_endpoint,
            environment_overrides=overrides,
            startup_timeout=args.startup_timeout,
        ) as client:
            warm_sidecar(
                client,
                arm=arm,
                corpus_sha256=corpus_hashes["runtime"],
                policy_identity=policy_identity,
                timeout=args.request_timeout,
                evidence_ready_timeout=args.evidence_ready_timeout,
            )
            for position, spec in enumerate(pending, 1):
                result = measure_case(client, arm, spec, args.request_timeout)
                record = {
                    "schema": "baxy.turn-policy-ab-result.v1",
                    "fingerprint": fingerprint,
                    "measured_at": datetime.now(timezone.utc).isoformat(),
                    "case_id": spec["case_id"],
                    "arm": arm,
                    "result": result,
                }
                append_jsonl_durable(journal, record)
                results.setdefault(spec["case_id"], {})[arm] = result
                completed_since_checkpoint += 1
                print(
                    f"{arm} {position}/{len(pending)} {spec['case_id']}: "
                    f"{result.get('kind') or 'error'}",
                    flush=True,
                )
                if completed_since_checkpoint >= args.checkpoint_every:
                    report = build_report(
                        args=args,
                        fingerprint=fingerprint,
                        specs=specs,
                        results=results,
                        cleanliness=cleanliness,
                        corpus_hashes=corpus_hashes,
                        input_identities=input_identities,
                        catalog_count=len(capabilities),
                        complete=False,
                        journal_resumed_records=journal_resumed_records,
                    )
                    write_json_atomic(output, report)
                    completed_since_checkpoint = 0

    expected_arms = {"baseline", "evidence"} if args.arm == "both" else {args.arm}
    complete = all(
        expected_arms.issubset(results.get(case_id, {})) for case_id in specs
    )
    expected_audit_ids = {
        str(result.get("audit_request_id") or "")
        for case_results in results.values()
        for arm, result in case_results.items()
        if arm in expected_arms and str(result.get("audit_request_id") or "")
    }
    raw_audits, missing_audit_ids = load_raw_turn_audits(
        audit,
        expected_audit_ids,
    )
    for case_results in results.values():
        for arm, result in case_results.items():
            if arm not in expected_arms:
                continue
            request_id = str(result.get("audit_request_id") or "")
            result["raw_audit"] = raw_audits.get(request_id)
    report = build_report(
        args=args,
        fingerprint=fingerprint,
        specs=specs,
        results=results,
        cleanliness=cleanliness,
        corpus_hashes=corpus_hashes,
        input_identities=input_identities,
        catalog_count=len(capabilities),
        complete=complete,
        journal_resumed_records=journal_resumed_records,
    )
    expected_result_count = sum(
        1
        for case_results in results.values()
        for arm in case_results
        if arm in expected_arms
    )
    raw_audit_complete = (
        len(expected_audit_ids) == expected_result_count
        and not missing_audit_ids
    )
    report["raw_audit"] = {
        "path": repo_relative(audit),
        "exists": audit.is_file(),
        "sha256": file_sha256(audit) if audit.is_file() else "",
        "expected_records": len(expected_audit_ids),
        "complete_records": len(raw_audits),
        "missing_request_ids": missing_audit_ids,
        "complete": raw_audit_complete,
        "contains_input_text": False,
    }
    acceptance = report.get("acceptance")
    if isinstance(acceptance, dict):
        checks = acceptance.get("checks")
        if isinstance(checks, dict):
            checks["raw_decision_audit_complete"] = raw_audit_complete
            if complete and not raw_audit_complete:
                report["status"] = "failed"
    write_json_atomic(output, report)
    return report


def parse_args() -> argparse.Namespace:
    manifest_parser = argparse.ArgumentParser(add_help=False)
    manifest_parser.add_argument(
        "--runtime-manifest", type=Path, default=DEFAULT_RUNTIME_MANIFEST
    )
    preliminary, _ = manifest_parser.parse_known_args()
    manifest = read_runtime_manifest(preliminary.runtime_manifest)

    parser = argparse.ArgumentParser(
        parents=[manifest_parser],
        description="Gate A/B real de la política turn.decide.",
    )
    parser.add_argument("--holdout", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--runtime-corpus", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--seal", type=Path, default=DEFAULT_SEAL)
    parser.add_argument(
        "--predecessor-seal",
        type=Path,
        default=DEFAULT_PREDECESSOR_SEAL,
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--core", type=Path, default=DEFAULT_CORE)
    parser.add_argument("--catalog-file", type=Path)
    parser.add_argument(
        "--gguf",
        type=Path,
        default=Path(str(manifest.get("gguf") or "")),
    )
    parser.add_argument(
        "--llama-server",
        type=Path,
        default=Path(str(manifest.get("llama_server") or "")),
    )
    parser.add_argument("--llm-endpoint")
    parser.add_argument("--ngl", type=int, default=int(manifest.get("ngl") or 99))
    parser.add_argument(
        "--evidence-cache",
        type=Path,
        default=(
            Path(os.environ.get("LOCALAPPDATA", REPO))
            / "BAXYRuntime"
            / "turn-evidence"
        ),
    )
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--sample-size", type=int, default=FULL_HOLDOUT_SAMPLE)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument(
        "--preflight-holdout-sample",
        type=int,
        default=PREFLIGHT_HOLDOUT_SAMPLE,
        help=(
            "Tamaño público de validación para diagnósticos --preflight; "
            "no abre el sello final."
        ),
    )
    parser.add_argument("--max-holdout", type=int)
    parser.add_argument(
        "--max-contextual",
        type=int,
        help="Limita solo casos contextuales opcionales; los críticos son obligatorios.",
    )
    parser.add_argument("--max-calls", type=int)
    parser.add_argument(
        "--arm", choices=("both", "baseline", "evidence"), default="both"
    )
    parser.add_argument("--request-timeout", type=float, default=75.0)
    parser.add_argument("--startup-timeout", type=float, default=240.0)
    parser.add_argument("--evidence-ready-timeout", type=float, default=900.0)
    parser.add_argument("--checkpoint-every", type=int, default=5)
    parser.add_argument(
        "--noninferiority-margin",
        type=float,
        default=DEFAULT_NONINFERIORITY_MARGIN,
    )
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    if args.sample_size < 1:
        parser.error("--sample-size debe ser positivo")
    if args.preflight_holdout_sample < 1:
        parser.error("--preflight-holdout-sample debe ser positivo")
    if args.max_holdout is not None and args.max_holdout < 0:
        parser.error("--max-holdout no puede ser negativo")
    if args.max_contextual is not None and args.max_contextual < 0:
        parser.error("--max-contextual no puede ser negativo")
    if args.max_calls is not None and args.max_calls < 1:
        parser.error("--max-calls debe ser positivo")
    if args.checkpoint_every < 1:
        parser.error("--checkpoint-every debe ser positivo")
    if not 0 <= args.noninferiority_margin <= DEFAULT_NONINFERIORITY_MARGIN:
        parser.error("--noninferiority-margin no puede superar 0.02")
    return args


def main() -> int:
    report = run_gate(parse_args())
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"status={report['status']} -> {report['selection']['completed_measured_calls']} calls")
    return 0 if report["status"] in SUCCESS_STATUSES else 2


if __name__ == "__main__":
    raise SystemExit(main())
