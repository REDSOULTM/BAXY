"""Build contract-bounded MTOP evidence without turning corpus labels into authority.

There are two deliberately separate development commands:

* ``build-development`` reads only the official EN/ES train and eval files.
* ``seal-test`` hashes the official EN/ES test members as bytes.  It never
  decodes a test line or inspects its columns.

The official test has no materialization command.  A frozen gate must call
``evaluate_test_once``: it acquires a machine-local, archive-derived claim
before opening test, keeps rows in memory, emits only an aggregate report and
leaves an irreversible local receipt even if evaluation fails.  The
``materialize_test`` helper is retained solely for synthetic unit fixtures and
rejects the official archive.

The adapter preserves MTOP's semantic intent/slot structure only to reject
requests whose constraints exceed BAXY's existing public operation contracts.
It does not add operations, live phrase rules, or model weights.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, BinaryIO, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP = ROOT / "src" / "baxy_mind" / "data" / "mtop_turn_evidence_map.v1.json"
DEFAULT_CATALOG = ROOT / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs"
DEFAULT_SEAL = ROOT / "tests" / "data" / "mtop_test_seal.v1.json"

MAP_SCHEMA = "baxy.mtop-source-map.v1"
ROW_SCHEMA = "baxy.mtop-development-row.v1"
MANIFEST_SCHEMA = "baxy.mtop-development-manifest.v1"
SEAL_SCHEMA = "baxy.mtop-test-byte-seal.v1"
PREREGISTRATION_SCHEMA = "baxy.mtop-test-preregistration.v1"
RECEIPT_SCHEMA = "baxy.mtop-test-materialization-receipt.v1"
EVALUATION_RECEIPT_SCHEMA = "baxy.mtop-test-evaluation-receipt.v1"
EVALUATION_LEDGER_SCHEMA = "baxy.mtop-test-evaluation-ledger.v1"
MAX_AGGREGATE_REPORT_BYTES = 512 * 1024

_INTENT_PATTERN = re.compile(r"IN:[A-Z0-9_]+")
_SLOT_PATTERN = re.compile(r"SL:[A-Z0-9_]+")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_SPLIT_ORDER = {"train": 0, "validation": 1, "test": 2}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_path(path: Path) -> str:
    """Describe an input without serializing a workstation-specific path."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return f"external/{resolved.name}"


def _canonical_json_bytes(value: object, *, pretty: bool = False) -> bytes:
    if pretty:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    else:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    return (payload + "\n").encode("utf-8")


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_atomic(path: Path, value: object) -> None:
    _write_bytes_atomic(path, _canonical_json_bytes(value, pretty=True))


def _write_json_create_new(path: Path, value: object) -> None:
    """Durably reserve a one-shot identity without a check/write race."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(_canonical_json_bytes(value, pretty=True))
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        # fdopen owns the descriptor after it succeeds.  A failed reservation
        # deliberately remains on disk: a crash must fail closed, not permit a
        # second look at the same official test.
        raise


def _load_json(path: Path, description: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"no se pudo leer {description}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{description} no es un objeto JSON")
    return value


def _public_catalog_operations(catalog_path: Path) -> frozenset[str]:
    """Read operation identities and their declared exposure from the catalog."""

    text = catalog_path.read_text(encoding="utf-8")
    blocks = re.finditer(
        r'Descriptor\(\s*"(?P<operation>[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+)"'
        r"(?P<body>.*?)(?=\n        Descriptor\(|\n    \];)",
        text,
        flags=re.DOTALL,
    )
    public: set[str] = set()
    discovered = 0
    for block in blocks:
        discovered += 1
        exposure = re.search(r"ToolExposure\.(Public|Internal)", block.group("body"))
        if exposure is None:
            raise ValueError(
                f"el catalogo no declara exposicion para {block.group('operation')}"
            )
        if exposure.group(1) == "Public":
            public.add(block.group("operation"))
    if discovered < 100 or not public:
        raise ValueError("no se pudo reconstruir el catalogo publico de BAXY")
    return frozenset(public)


def _string_list(value: object, field: str, prefix: str | None = None) -> list[str]:
    if (
        not isinstance(value, list)
        or not all(isinstance(item, str) and item for item in value)
        or len(value) != len(set(value))
    ):
        raise ValueError(f"{field} debe ser una lista de strings unicos")
    if prefix is not None and any(not item.startswith(prefix) for item in value):
        raise ValueError(f"{field} contiene una identidad con prefijo invalido")
    return value


def load_source_map(
    source_map_path: Path,
    catalog_path: Path = DEFAULT_CATALOG,
) -> dict[str, Any]:
    """Validate the complete declarative boundary before any corpus is read."""

    mapping = _load_json(source_map_path, "el mapa MTOP")
    if mapping.get("schema") != MAP_SCHEMA:
        raise ValueError("el mapa MTOP tiene un schema desconocido")
    source = mapping.get("source")
    selection = mapping.get("selection")
    policy = mapping.get("policy")
    intents = mapping.get("intents")
    if not all(isinstance(value, dict) for value in (source, selection, policy, intents)):
        raise ValueError("el mapa MTOP esta incompleto")
    assert isinstance(source, dict)
    assert isinstance(selection, dict)
    assert isinstance(policy, dict)
    assert isinstance(intents, dict)
    archive_hash = source.get("archive_sha256")
    development_members = source.get("development_members")
    if (
        source.get("license") != "CC-BY-SA-4.0"
        or not isinstance(source.get("download_url"), str)
        or not isinstance(archive_hash, str)
        or _SHA256_PATTERN.fullmatch(archive_hash) is None
        or not isinstance(development_members, dict)
        or set(development_members)
        != {
            "en/train.txt",
            "en/eval.txt",
            "es/train.txt",
            "es/eval.txt",
        }
    ):
        raise ValueError("la licencia o procedencia MTOP no esta congelada")
    for member_name, identity in development_members.items():
        if (
            not isinstance(identity, dict)
            or set(identity) != {"sha256", "bytes", "rows"}
            or not isinstance(identity.get("sha256"), str)
            or _SHA256_PATTERN.fullmatch(identity["sha256"]) is None
            or not isinstance(identity.get("bytes"), int)
            or isinstance(identity.get("bytes"), bool)
            or identity["bytes"] <= 0
            or not isinstance(identity.get("rows"), int)
            or isinstance(identity.get("rows"), bool)
            or identity["rows"] <= 0
        ):
            raise ValueError(
                f"la identidad oficial de desarrollo es invalida: {member_name}"
            )
    locales = selection.get("locales")
    development_splits = selection.get("development_splits")
    maximum_characters = selection.get("maximum_text_characters")
    if (
        not isinstance(locales, dict)
        or locales != {"en": "en_XX", "es": "es_XX"}
        or not isinstance(development_splits, dict)
        or development_splits != {"train": "train", "eval": "validation"}
        or not isinstance(maximum_characters, int)
        or not 1 <= maximum_characters <= 4096
    ):
        raise ValueError("la seleccion MTOP no coincide con el protocolo EN/ES")
    if (
        policy.get("unlisted_intent") != "ood_no_effect"
        or policy.get("candidate_is_advisory_only") is not True
        or policy.get("execution_authority") is not False
        or policy.get("require_independent_llm_selection") is not True
        or policy.get("require_contract_grounding_and_verification") is not True
        or policy.get("development_must_explicitly_classify_every_observed_intent")
        is not True
    ):
        raise ValueError("la politica MTOP podria otorgar autoridad o permitir fuga")
    ood_intents = _string_list(mapping.get("ood_intents"), "ood_intents", "IN:")
    if set(ood_intents) & set(intents):
        raise ValueError("un intent MTOP aparece como candidato y OOD")
    public_operations = _public_catalog_operations(catalog_path)
    for intent, entry in intents.items():
        if not isinstance(intent, str) or not intent.startswith("IN:"):
            raise ValueError("el mapa contiene un intent invalido")
        if not isinstance(entry, dict):
            raise ValueError(f"el intent {intent} no tiene una proyeccion")
        disposition = entry.get("disposition")
        variants = entry.get("variants")
        if disposition not in {"candidate", "conversation"}:
            raise ValueError(f"el intent {intent} tiene una disposicion invalida")
        if not isinstance(variants, list) or not variants:
            raise ValueError(f"el intent {intent} no tiene variantes")
        variant_ids: set[str] = set()
        for variant in variants:
            if not isinstance(variant, dict):
                raise ValueError(f"el intent {intent} contiene una variante invalida")
            variant_id = variant.get("id")
            if (
                not isinstance(variant_id, str)
                or not variant_id
                or variant_id in variant_ids
            ):
                raise ValueError(f"el intent {intent} repite una variante")
            variant_ids.add(variant_id)
            operations = _string_list(
                variant.get("operations"),
                f"{intent}.{variant_id}.operations",
            )
            unsupported = sorted(set(operations) - public_operations)
            if unsupported:
                raise ValueError(
                    f"{intent}.{variant_id} introduce operaciones no publicas: "
                    + ", ".join(unsupported)
                )
            if disposition == "candidate" and not operations:
                raise ValueError(f"{intent}.{variant_id} no propone una operacion")
            if disposition == "conversation" and operations:
                raise ValueError(f"{intent}.{variant_id} da tools a una conversacion")
            allowed = set(
                _string_list(
                    variant.get("allowed_slots"),
                    f"{intent}.{variant_id}.allowed_slots",
                    "SL:",
                )
            )
            required = set(
                _string_list(
                    variant.get("required_slots"),
                    f"{intent}.{variant_id}.required_slots",
                    "SL:",
                )
            )
            required_any = set(
                _string_list(
                    variant.get("required_any_slots"),
                    f"{intent}.{variant_id}.required_any_slots",
                    "SL:",
                )
            )
            if not required <= allowed or not required_any <= allowed:
                raise ValueError(f"{intent}.{variant_id} exige slots no permitidos")
            if variant.get("allow_nested_intents") is not False:
                raise ValueError(
                    f"{intent}.{variant_id} debe abstenerse ante composicion anidada"
                )
    return mapping


def _normal_text(value: str, maximum_characters: int) -> str:
    text = " ".join(unicodedata.normalize("NFC", value).split())
    if (
        not text
        or len(text) > maximum_characters
        or any(ord(character) < 32 for character in text)
    ):
        raise ValueError("MTOP contiene una utterance invalida")
    return text


def _variant_shape(
    variant: dict[str, Any],
    slots: frozenset[str],
    nested_intents: tuple[str, ...],
) -> tuple[str, tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """Classify contract shape without confusing missing data with OOD.

    Extra constraints and unsupported composition are outside the mapped
    contract.  Missing human-supplied fields are different: the effect is
    supported, but the runtime must ground it or ask one clarification.
    """

    allowed = frozenset(variant["allowed_slots"])
    required = frozenset(variant["required_slots"])
    required_any = frozenset(variant["required_any_slots"])
    if not slots <= allowed:
        return "unsupported", (), ()
    if nested_intents and variant["allow_nested_intents"] is not True:
        return "unsupported", (), ()
    missing_required = tuple(sorted(required - slots))
    missing_any = (
        (tuple(sorted(required_any)),)
        if required_any and slots.isdisjoint(required_any)
        else ()
    )
    if missing_required or missing_any:
        return "missing", missing_required, missing_any
    return "complete", (), ()


def _projection(
    *,
    disposition: str,
    variant: str | None,
    operations: list[str],
    reason: str,
    grounding_status: str,
    missing_required_slots: tuple[str, ...] = (),
    missing_any_slot_groups: tuple[tuple[str, ...], ...] = (),
) -> dict[str, Any]:
    if disposition == "candidate_missing_information":
        expected_turn = "clarify"
    elif disposition == "candidate":
        expected_turn = "plan" if len(operations) > 1 else "action"
    else:
        expected_turn = "conversation"
    return {
        "disposition": disposition,
        "variant": variant,
        "candidate_operations": operations,
        "families": sorted(
            {operation.split(".", 1)[0] for operation in operations}
        ),
        "reason": reason,
        "grounding_status": grounding_status,
        "missing_required_slots": list(missing_required_slots),
        "missing_any_slot_groups": [
            list(group) for group in missing_any_slot_groups
        ],
        "expected_turn": expected_turn,
        "turn_label_source": "baxy_contract_projection",
        "execution_authority": False,
    }


def _project(
    mapping: dict[str, Any],
    intent: str,
    slots: frozenset[str],
    nested_intents: tuple[str, ...],
    *,
    require_explicit_intent: bool,
) -> dict[str, Any]:
    entry = mapping["intents"].get(intent)
    if entry is None:
        if intent in mapping["ood_intents"]:
            reason = "mapped_unsupported_intent"
        elif require_explicit_intent:
            raise ValueError(
                f"el desarrollo contiene un intent sin revision explicita: {intent}"
            )
        else:
            reason = "sealed_test_unlisted_intent"
        return _projection(
            disposition="ood_no_effect",
            variant=None,
            operations=[],
            reason=reason,
            grounding_status="not_applicable",
        )
    incomplete: list[
        tuple[
            dict[str, Any],
            tuple[str, ...],
            tuple[tuple[str, ...], ...],
        ]
    ] = []
    for variant in entry["variants"]:
        shape, missing_required, missing_any = _variant_shape(
            variant,
            slots,
            nested_intents,
        )
        if shape == "unsupported":
            continue
        if shape == "missing":
            incomplete.append((variant, missing_required, missing_any))
            continue
        operations = list(variant["operations"])
        disposition = entry["disposition"]
        return _projection(
            disposition=(
                "candidate"
                if disposition == "candidate"
                else "conversation_no_effect"
            ),
            variant=variant["id"],
            operations=operations,
            reason="contract_covered_structure",
            grounding_status="complete",
        )
    if incomplete and entry["disposition"] == "candidate":
        ranked = sorted(
            incomplete,
            key=lambda item: (
                len(item[1]) + len(item[2]),
                len(item[1]),
                str(item[0]["id"]),
            ),
        )
        best_score = (
            len(ranked[0][1]) + len(ranked[0][2]),
            len(ranked[0][1]),
        )
        best = [
            item
            for item in ranked
            if (
                len(item[1]) + len(item[2]),
                len(item[1]),
            )
            == best_score
        ]
        operation_sequences = {
            tuple(str(operation) for operation in item[0]["operations"])
            for item in best
        }
        if len(operation_sequences) == 1:
            variant, missing_required, missing_any = best[0]
            return _projection(
                disposition="candidate_missing_information",
                variant=str(variant["id"]),
                operations=list(variant["operations"]),
                reason="contract_supported_missing_information",
                grounding_status="missing_required_information",
                missing_required_slots=missing_required,
                missing_any_slot_groups=missing_any,
            )
    return _projection(
        disposition="ood_no_effect",
        variant=None,
        operations=[],
        reason=(
            "contract_ambiguous_missing_information"
            if incomplete
            else "contract_structure_mismatch"
        ),
        grounding_status="not_applicable",
    )


def _parse_row(
    raw_line: str,
    *,
    language: str,
    split: str,
    mapping: dict[str, Any],
    require_explicit_intent: bool,
    opaque_test_id: str | None = None,
) -> dict[str, Any]:
    columns = raw_line.rstrip("\r\n").split("\t")
    if len(columns) != 8:
        raise ValueError("MTOP no conserva las ocho columnas TSV esperadas")
    upstream_id, intent, _flat_slots, utterance, domain, locale, tree, _tokens = columns
    expected_locale = mapping["selection"]["locales"][language]
    if (
        not upstream_id
        or locale != expected_locale
        or _INTENT_PATTERN.fullmatch(intent) is None
        or not domain
    ):
        raise ValueError("MTOP contiene identidad, locale o intent invalido")
    tree_intents = _INTENT_PATTERN.findall(tree)
    if not tree_intents or tree_intents[0] != intent:
        raise ValueError("el arbol semantico MTOP no coincide con su intent superior")
    nested_intents = tuple(tree_intents[1:])
    slots = frozenset(_SLOT_PATTERN.findall(tree))
    projection = _project(
        mapping,
        intent,
        slots,
        nested_intents,
        require_explicit_intent=require_explicit_intent,
    )
    if opaque_test_id is None:
        source_id = f"mtop-official-v2:{language}:{upstream_id}"
        mission_id = f"mtop-official-v2:{upstream_id}"
    else:
        source_id = f"mtop-official-v2:test:{language}:{opaque_test_id}"
        parallel_digest = hashlib.sha256(
            b"baxy.mtop.test-parallel-group.v1\0"
            + upstream_id.encode("utf-8")
        ).hexdigest()
        mission_id = f"mtop-official-v2:test-group:{parallel_digest}"
    return {
        "schema": ROW_SCHEMA,
        "text": _normal_text(
            utterance,
            mapping["selection"]["maximum_text_characters"],
        ),
        "locale": language,
        "split": split,
        "mission_id": mission_id,
        "source_id": source_id,
        "semantic": {
            "domain": domain,
            "intent": intent,
            "slots": sorted(slots),
            "nested_intents": list(nested_intents),
        },
        "projection": projection,
        "provenance": {
            "dataset": mapping["source"]["name"],
            "license": mapping["source"]["license"],
            "adapter_version": mapping["source"]["adapter_version"],
        },
    }


def _development_source_files(
    dataset_root: Path,
    mapping: dict[str, Any],
) -> Iterable[tuple[str, str, Path]]:
    for language in sorted(mapping["selection"]["locales"]):
        for source_split, output_split in mapping["selection"][
            "development_splits"
        ].items():
            yield language, output_split, dataset_root / language / f"{source_split}.txt"


def _normalized_text_identity(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def _decontaminate_development(
    records: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Remove exact-text leakage and conflicts without consulting test.

    Official multilingual IDs must never cross train/validation.  Exact text
    can still repeat under distinct IDs, so validation wins over train, one
    deterministic row wins within a split, and conflicting behavioral labels
    are removed entirely.
    """

    candidates = list(records)
    mission_splits: dict[str, set[str]] = {}
    by_text: dict[str, list[dict[str, Any]]] = {}
    for record in candidates:
        mission_splits.setdefault(record["mission_id"], set()).add(record["split"])
        by_text.setdefault(
            _normalized_text_identity(record["text"]),
            [],
        ).append(record)
    crossing_missions = sorted(
        mission_id
        for mission_id, splits in mission_splits.items()
        if len(splits) > 1
    )
    if crossing_missions:
        raise ValueError(
            "MTOP contiene IDs multilingues que cruzan train/validation"
        )
    accepted: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for variants in by_text.values():
        signatures = {
            (
                row["projection"]["disposition"],
                tuple(row["projection"]["candidate_operations"]),
            )
            for row in variants
        }
        if len(signatures) > 1:
            counts["ambiguous_exact_text_groups_removed"] += 1
            counts["ambiguous_exact_text_rows_removed"] += len(variants)
            continue
        splits = {row["split"] for row in variants}
        if "validation" in splits:
            pool = [row for row in variants if row["split"] == "validation"]
            if len(splits) > 1:
                counts["cross_split_exact_text_groups"] += 1
                counts["cross_split_train_rows_removed"] += sum(
                    row["split"] == "train" for row in variants
                )
        else:
            pool = variants
        accepted.append(
            min(
                pool,
                key=lambda row: (
                    row["locale"],
                    row["source_id"],
                ),
            )
        )
        counts["same_split_exact_duplicates_removed"] += len(pool) - 1
    return accepted, dict(sorted(counts.items()))


def build_development(
    dataset_root: Path,
    source_map_path: Path,
    catalog_path: Path,
    output_path: Path,
    manifest_path: Path,
    test_seal_path: Path | None,
) -> dict[str, Any]:
    mapping = load_source_map(source_map_path, catalog_path)
    records: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    observed_intents: set[str] = set()
    for language, split, path in _development_source_files(dataset_root, mapping):
        path = path.resolve(strict=True)
        source_name = (
            f"{language}/"
            f"{'train.txt' if split == 'train' else 'eval.txt'}"
        )
        expected_source = mapping["source"]["development_members"][source_name]
        if (
            path.stat().st_size != expected_source["bytes"]
            or _sha256(path) != expected_source["sha256"]
        ):
            raise ValueError(
                f"la fuente de desarrollo no coincide con MTOP oficial: {source_name}"
            )
        rows = 0
        with path.open("r", encoding="utf-8", newline="") as handle:
            for raw_line in handle:
                if not raw_line.strip():
                    continue
                record = _parse_row(
                    raw_line,
                    language=language,
                    split=split,
                    mapping=mapping,
                    require_explicit_intent=True,
                )
                records.append(record)
                observed_intents.add(record["semantic"]["intent"])
                rows += 1
        if rows != expected_source["rows"]:
            raise ValueError(
                f"el recuento de desarrollo no coincide con MTOP oficial: {source_name}"
            )
        sources.append(
            {
                "repo_independent_path": source_name,
                "sha256": expected_source["sha256"],
                "bytes": path.stat().st_size,
                "rows": rows,
            }
        )
    source_rows = len(records)
    identities = [record["source_id"] for record in records]
    if len(identities) != len(set(identities)):
        raise ValueError("MTOP repite una identidad dentro de development")
    records, decontamination = _decontaminate_development(records)
    records.sort(
        key=lambda row: (
            _SPLIT_ORDER[row["split"]],
            row["mission_id"],
            row["locale"],
            row["source_id"],
        )
    )
    payload = b"".join(_canonical_json_bytes(record) for record in records)
    _write_bytes_atomic(output_path, payload)
    dispositions = Counter(
        record["projection"]["disposition"] for record in records
    )
    reasons = Counter(record["projection"]["reason"] for record in records)
    operations = Counter(
        operation
        for record in records
        for operation in record["projection"]["candidate_operations"]
    )
    seal_identity: dict[str, Any] | None = None
    if test_seal_path is not None:
        seal = _load_json(test_seal_path, "el sello opaco de test")
        seal_source = seal.get("source")
        if (
            seal.get("schema") != SEAL_SCHEMA
            or not isinstance(seal_source, dict)
            or seal_source.get("source_map_sha256")
            != _sha256(source_map_path)
        ):
            raise ValueError(
                "el sello opaco de test no coincide con el mapa MTOP actual"
            )
        seal_identity = {
            "repo_path": _portable_path(test_seal_path),
            "sha256": _sha256(test_seal_path),
        }
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "source": {
            **mapping["source"],
            "map_repo_path": _portable_path(source_map_path),
            "map_sha256": _sha256(source_map_path),
        },
        "catalog": {
            "repo_path": _portable_path(catalog_path),
            "sha256": _sha256(catalog_path),
            "public_operations": len(_public_catalog_operations(catalog_path)),
        },
        "constraints": {
            "development_files_only": True,
            "test_content_read": False,
            "candidate_is_advisory_only": True,
            "execution_authority": False,
            "candidate_operations_exist_in_public_catalog": True,
            "slot_projection_uses_reviewed_source_map": True,
            "slot_to_argument_schema_not_automatically_derived": True,
            "mission_split_overlap": 0,
            "normalized_text_split_overlap": 0,
            "unlisted_test_intent_policy": "ood_no_effect",
        },
        "development_sources": sources,
        "test_seal": seal_identity,
        "output": {
            "file_name": output_path.name,
            "sha256": _sha256(output_path),
            "bytes": output_path.stat().st_size,
            "rows": len(records),
        },
        "counts": {
            "source_rows": source_rows,
            "accepted_rows": len(records),
            "observed_intents": len(observed_intents),
            "dispositions": dict(sorted(dispositions.items())),
            "reasons": dict(sorted(reasons.items())),
            "candidate_operations": dict(sorted(operations.items())),
            "splits": dict(
                sorted(Counter(record["split"] for record in records).items())
            ),
            "locales": dict(
                sorted(Counter(record["locale"] for record in records).items())
            ),
            "nested_semantic_rows": sum(
                bool(record["semantic"]["nested_intents"]) for record in records
            ),
            "decontamination": decontamination,
        },
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _opaque_test_member_identity(
    handle: BinaryIO,
    language: str,
) -> dict[str, Any]:
    """Hash test records using bytes only; this function intentionally cannot decode."""

    member_digest = hashlib.sha256()
    record_ids_digest = hashlib.sha256()
    rows = 0
    member_bytes = 0
    for raw_line in handle:
        member_digest.update(raw_line)
        member_bytes += len(raw_line)
        line = raw_line.rstrip(b"\r\n")
        if not line:
            continue
        rows += 1
        line_digest = hashlib.sha256(line).digest()
        record_id = hashlib.sha256(
            b"baxy.mtop.test-record.v1\0"
            + language.encode("ascii")
            + b"\0"
            + str(rows).encode("ascii")
            + b"\0"
            + line_digest
        ).digest()
        record_ids_digest.update(record_id)
    return {
        "bytes": member_bytes,
        "rows": rows,
        "member_sha256": member_digest.hexdigest(),
        "record_ids_sha256": record_ids_digest.hexdigest(),
    }


def build_test_seal(
    archive_path: Path,
    source_map_path: Path,
    catalog_path: Path = DEFAULT_CATALOG,
) -> dict[str, Any]:
    """Create a deterministic, text-free seal over official test member bytes."""

    mapping = load_source_map(source_map_path, catalog_path)
    archive_path = archive_path.resolve(strict=True)
    archive_sha256 = _sha256(archive_path)
    if archive_sha256 != mapping["source"]["archive_sha256"]:
        raise ValueError("el ZIP MTOP no coincide con el hash oficial congelado")
    members: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(archive_path) as bundle:
            for language in sorted(mapping["selection"]["locales"]):
                member_name = f"mtop/{language}/test.txt"
                info = bundle.getinfo(member_name)
                with bundle.open(info, "r") as handle:
                    identity = _opaque_test_member_identity(handle, language)
                if identity["bytes"] != info.file_size:
                    raise ValueError("el test MTOP cambio durante el sellado")
                members[language] = {
                    "archive_member": member_name,
                    "compressed_bytes": info.compress_size,
                    "crc32": f"{info.CRC:08x}",
                    **identity,
                }
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ValueError("no se pudo sellar el test MTOP oficial") from error
    aggregate = hashlib.sha256()
    for language in sorted(members):
        aggregate.update(language.encode("ascii"))
        aggregate.update(b"\0")
        aggregate.update(bytes.fromhex(members[language]["record_ids_sha256"]))
    return {
        "schema": SEAL_SCHEMA,
        "source": {
            "name": mapping["source"]["name"],
            "license": mapping["source"]["license"],
            "archive_file_name": mapping["source"]["archive_file_name"],
            "archive_sha256": archive_sha256,
            "archive_bytes": archive_path.stat().st_size,
            "source_map_sha256": _sha256(source_map_path),
        },
        "protocol": {
            "content_decoded": False,
            "columns_inspected": False,
            "record_id_algorithm": (
                "sha256(domain || NUL || locale || NUL || ordinal || NUL || "
                "sha256(raw_line_without_eol))"
            ),
            "record_id_domain": "baxy.mtop.test-record.v1",
            "aggregate_algorithm": (
                "sha256(locale || NUL || binary(record_ids_sha256), locale-sorted)"
            ),
        },
        "members": members,
        "record_ids_aggregate_sha256": aggregate.hexdigest(),
        "rows": sum(member["rows"] for member in members.values()),
    }


def _validate_preregistration(
    preregistration_path: Path,
    seal_path: Path,
    source_map_path: Path,
    archive_path: Path,
) -> dict[str, Any]:
    preregistration = _load_json(preregistration_path, "el prerregistro MTOP")
    if (
        preregistration.get("schema") != PREREGISTRATION_SCHEMA
        or preregistration.get("state") != "locked"
        or preregistration.get("test_seal_sha256") != _sha256(seal_path)
        or preregistration.get("source_map_sha256") != _sha256(source_map_path)
        or preregistration.get("archive_sha256") != _sha256(archive_path)
        or not isinstance(preregistration.get("run_id"), str)
        or not preregistration["run_id"]
    ):
        raise ValueError("el prerregistro no enlaza exactamente el test sellado")
    protocol = preregistration.get("protocol")
    if not isinstance(protocol, dict):
        raise ValueError("el prerregistro no congela un protocolo")
    metrics = protocol.get("metrics")
    floors = protocol.get("absolute_floors")
    ceilings = protocol.get("absolute_ceilings", {})
    maximum_recoveries = protocol.get("maximum_recoveries")
    frozen_artifacts = protocol.get("frozen_artifacts")
    sample_protocol = protocol.get("sample_protocol")
    if (
        protocol.get("architecture_frozen") is not True
        or protocol.get("single_final_evaluation") is not True
        or protocol.get("test_content_unseen_when_locked") is not True
        or protocol.get("test_rows_used_for_training") is not False
        or protocol.get("gate_report_contains_text") is not False
        or not isinstance(metrics, list)
        or not metrics
        or not all(isinstance(metric, str) and metric for metric in metrics)
        or len(metrics) != len(set(metrics))
        or not isinstance(floors, dict)
        or not floors
        or not set(floors) <= set(metrics)
        or not all(
            isinstance(name, str)
            and name
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for name, value in floors.items()
        )
        or not isinstance(ceilings, dict)
        or not set(ceilings) <= set(metrics)
        or not all(
            isinstance(name, str)
            and name
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for name, value in ceilings.items()
        )
        or not isinstance(maximum_recoveries, int)
        or isinstance(maximum_recoveries, bool)
        or maximum_recoveries < 0
        or not isinstance(frozen_artifacts, dict)
        or len(frozen_artifacts) < 3
        or not all(
            isinstance(name, str)
            and name
            and isinstance(identity, dict)
            and set(identity) == {"repo_path", "sha256"}
            and isinstance(identity.get("repo_path"), str)
            and bool(identity["repo_path"])
            and isinstance(identity.get("sha256"), str)
            and _SHA256_PATTERN.fullmatch(identity["sha256"]) is not None
            for name, identity in frozen_artifacts.items()
        )
        or not isinstance(sample_protocol, dict)
        or not sample_protocol
    ):
        raise ValueError(
            "el prerregistro no fija arquitectura, muestra, metricas, pisos "
            "y recuperaciones"
        )
    for name, identity in frozen_artifacts.items():
        relative = Path(identity["repo_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(
                f"el artefacto congelado {name} no tiene una ruta repo segura"
            )
        candidate = (ROOT / relative).resolve()
        if (
            not candidate.is_relative_to(ROOT.resolve())
            or not candidate.is_file()
            or _sha256(candidate) != identity["sha256"]
        ):
            raise ValueError(
                f"el artefacto congelado {name} no coincide con sus bytes"
            )
    return preregistration


def _opaque_record_id(raw_line: bytes, language: str, ordinal: int) -> str:
    line_digest = hashlib.sha256(raw_line.rstrip(b"\r\n")).digest()
    return hashlib.sha256(
        b"baxy.mtop.test-record.v1\0"
        + language.encode("ascii")
        + b"\0"
        + str(ordinal).encode("ascii")
        + b"\0"
        + line_digest
    ).hexdigest()


def _test_usage_identity(seal: dict[str, Any]) -> str:
    source = seal.get("source")
    aggregate = seal.get("record_ids_aggregate_sha256")
    if (
        seal.get("schema") != SEAL_SCHEMA
        or not isinstance(source, dict)
        or not isinstance(source.get("archive_sha256"), str)
        or _SHA256_PATTERN.fullmatch(source["archive_sha256"]) is None
        or not isinstance(aggregate, str)
        or _SHA256_PATTERN.fullmatch(aggregate) is None
    ):
        raise ValueError("el sello no permite derivar una identidad one-shot")
    return hashlib.sha256(
        b"baxy.mtop.official-test-usage.v1\0"
        + bytes.fromhex(source["archive_sha256"])
        + bytes.fromhex(aggregate)
    ).hexdigest()


def _default_usage_ledger_path(seal: dict[str, Any]) -> Path:
    local_data = os.environ.get("LOCALAPPDATA", "").strip()
    if not local_data:
        raise ValueError("LOCALAPPDATA no esta disponible para el ledger one-shot")
    return (
        Path(local_data)
        / "BAXYRuntime"
        / "gates"
        / "mtop-test-v1"
        / f"{_test_usage_identity(seal)}.json"
    )


def _machine_fingerprint() -> str:
    """Return only a domain-separated hash of the local machine identity."""

    raw_identity = ""
    try:
        import winreg  # type: ignore[import-not-found]

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
        if isinstance(value, str):
            raw_identity = value.strip()
    except (ImportError, OSError):
        raw_identity = ""
    if not raw_identity:
        raw_identity = "\u241f".join(
            (
                os.environ.get("COMPUTERNAME", "").strip(),
                os.environ.get("PROCESSOR_IDENTIFIER", "").strip(),
            )
        )
    if not raw_identity.strip("\u241f"):
        raise ValueError("no se pudo derivar la identidad local del ledger")
    return hashlib.sha256(
        b"baxy.machine-fingerprint.v1\0" + raw_identity.encode("utf-8")
    ).hexdigest()


def _default_evaluation_ledger_directory(seal: dict[str, Any]) -> Path:
    local_data = os.environ.get("LOCALAPPDATA", "").strip()
    if not local_data:
        raise ValueError(
            "LOCALAPPDATA no esta disponible para el ledger de evaluacion"
        )
    return (
        Path(local_data)
        / "BAXYRuntime"
        / "evaluation-ledger"
        / "mtop-v1"
        / _machine_fingerprint()
        / _test_usage_identity(seal)
    )


def _official_archive_sha256() -> str:
    mapping = _load_json(DEFAULT_MAP, "el mapa MTOP oficial")
    source = mapping.get("source")
    value = source.get("archive_sha256") if isinstance(source, dict) else None
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError("el mapa MTOP oficial no fija el archive")
    return value


def _read_test_records(
    archive_path: Path,
    mapping: dict[str, Any],
    expected_seal: dict[str, Any],
) -> list[dict[str, Any]]:
    """Decode sealed rows only inside an already-claimed evaluation process."""

    records: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(archive_path) as bundle:
            for language in sorted(mapping["selection"]["locales"]):
                member_name = f"mtop/{language}/test.txt"
                with bundle.open(member_name, "r") as handle:
                    ordinal = 0
                    for raw_line in handle:
                        if not raw_line.strip():
                            continue
                        ordinal += 1
                        opaque_id = _opaque_record_id(
                            raw_line,
                            language,
                            ordinal,
                        )
                        try:
                            decoded = raw_line.decode("utf-8")
                        except UnicodeDecodeError as error:
                            raise ValueError(
                                "MTOP test no es UTF-8 valido"
                            ) from error
                        records.append(
                            _parse_row(
                                decoded,
                                language=language,
                                split="test",
                                mapping=mapping,
                                require_explicit_intent=False,
                                opaque_test_id=opaque_id,
                            )
                        )
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ValueError(
            "no se pudo leer el test MTOP dentro del gate reservado"
        ) from error
    if len(records) != expected_seal.get("rows"):
        raise ValueError("el gate no conserva el recuento test sellado")
    return records


def _safe_report_path(preregistration: dict[str, Any]) -> Path:
    protocol = preregistration["protocol"]
    relative_value = protocol.get("report_repo_path")
    if not isinstance(relative_value, str) or not relative_value:
        raise ValueError("el prerregistro no fija la ruta del reporte final")
    relative = Path(relative_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("la ruta del reporte final no es segura")
    report_path = (ROOT / relative).resolve()
    if (
        not report_path.is_relative_to(ROOT.resolve())
        or report_path.suffix.casefold() != ".json"
    ):
        raise ValueError("el reporte final debe ser JSON dentro del repositorio")
    return report_path


def _report_has_forbidden_structure(value: object) -> bool:
    forbidden = {
        "example",
        "examples",
        "intent",
        "mission_id",
        "record",
        "records",
        "row_results",
        "semantic",
        "slots",
        "source_id",
        "text",
        "utterance",
    }
    if isinstance(value, dict):
        return any(
            str(key).casefold() in forbidden
            or _report_has_forbidden_structure(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_report_has_forbidden_structure(child) for child in value)
    return False


def _validated_aggregate_report(
    raw_report: object,
    *,
    records: list[dict[str, Any]],
    preregistration: dict[str, Any],
    preregistration_sha256: str,
    seal_path: Path,
) -> dict[str, Any]:
    if not isinstance(raw_report, dict):
        raise ValueError("el evaluador no devolvio un reporte agregado")
    report = dict(raw_report)
    metrics = report.get("metrics")
    recoveries = report.get("recoveries")
    evaluated_rows = report.get("evaluated_rows")
    protocol = preregistration["protocol"]
    declared_metrics = protocol["metrics"]
    floors = protocol["absolute_floors"]
    ceilings = protocol.get("absolute_ceilings", {})
    if (
        report.get("contains_text") is not False
        or report.get("execution_authority") is not False
        or report.get("authority") != "read_only_no_operation_dispatch"
        or _report_has_forbidden_structure(report)
        or not isinstance(metrics, dict)
        or not all(name in metrics for name in declared_metrics)
        or not all(
            isinstance(metrics[name], (int, float))
            and not isinstance(metrics[name], bool)
            and math.isfinite(float(metrics[name]))
            for name in declared_metrics
        )
        or not isinstance(recoveries, int)
        or isinstance(recoveries, bool)
        or recoveries < 0
        or evaluated_rows != len(records)
        or not isinstance(ceilings, dict)
        or not all(
            isinstance(name, str)
            and name in declared_metrics
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for name, value in ceilings.items()
        )
    ):
        raise ValueError(
            "el reporte final contiene detalle test o no respeta el contrato"
        )
    checks = {
        f"{name}_floor": float(metrics[name]) >= float(value)
        for name, value in floors.items()
    }
    checks.update(
        {
            f"{name}_ceiling": float(metrics[name]) <= float(value)
            for name, value in ceilings.items()
        }
    )
    checks["maximum_recoveries"] = (
        recoveries <= protocol["maximum_recoveries"]
    )
    report["preregistered_checks"] = dict(sorted(checks.items()))
    report["status"] = (
        "passed"
        if report.get("status") != "failed" and all(checks.values())
        else "failed"
    )
    report["preregistration"] = {
        "run_id": preregistration["run_id"],
        "sha256": preregistration_sha256,
        "test_seal_sha256": _sha256(seal_path),
    }
    payload = _canonical_json_bytes(report, pretty=True)
    if len(payload) > MAX_AGGREGATE_REPORT_BYTES:
        raise ValueError("el reporte agregado supera el limite")
    serialized = payload.decode("utf-8")
    for record in records:
        text = str(record.get("text") or "")
        if len(text) >= 12 and text in serialized:
            raise ValueError("el reporte agregado intento persistir texto test")
        for identity_name in ("source_id", "mission_id"):
            identity = str(record.get(identity_name) or "")
            if identity and identity in serialized:
                raise ValueError(
                    "el reporte agregado intento persistir una identidad test"
                )
    return report


def evaluate_test_once(
    archive_path: Path,
    source_map_path: Path,
    catalog_path: Path,
    seal_path: Path,
    preregistration_path: Path,
    evaluator: Callable[[list[dict[str, Any]]], object],
    *,
    synthetic_report_path: Path | None = None,
    synthetic_ledger_directory: Path | None = None,
) -> dict[str, Any]:
    """Run a frozen, aggregate-only test gate after an irreversible claim.

    Official rows exist only in this process.  The caller receives the final
    aggregate report, never the decoded records.  Override paths are accepted
    only for non-official synthetic fixtures.
    """

    preregistration = _validate_preregistration(
        preregistration_path,
        seal_path,
        source_map_path,
        archive_path,
    )
    mapping = load_source_map(source_map_path, catalog_path)
    expected_seal = _load_json(seal_path, "el sello opaco de test")
    archive_sha256 = _sha256(archive_path)
    official = archive_sha256 == _official_archive_sha256()
    if official and (
        synthetic_report_path is not None
        or synthetic_ledger_directory is not None
    ):
        raise ValueError("el test oficial no acepta rutas alternativas")
    report_path = (
        synthetic_report_path.resolve()
        if synthetic_report_path is not None
        else _safe_report_path(preregistration)
    )
    ledger_directory = (
        synthetic_ledger_directory.resolve()
        if synthetic_ledger_directory is not None
        else _default_evaluation_ledger_directory(expected_seal).resolve()
    )
    if report_path.exists():
        raise FileExistsError(
            "el reporte final ya existe; el test no puede ejecutarse otra vez"
        )
    usage_identity = _test_usage_identity(expected_seal)
    preregistration_sha256 = _sha256(preregistration_path)
    reservation = {
        "schema": EVALUATION_LEDGER_SCHEMA,
        "state": "claimed",
        "usage_identity": usage_identity,
        "machine_fingerprint": _machine_fingerprint(),
        "archive_sha256": archive_sha256,
        "test_seal_sha256": _sha256(seal_path),
        "source_map_sha256": _sha256(source_map_path),
        "preregistration_sha256": preregistration_sha256,
        "run_id": preregistration["run_id"],
        "claimed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    claim_path = ledger_directory / "claim.json"
    try:
        _write_json_create_new(claim_path, reservation)
    except FileExistsError as error:
        raise FileExistsError(
            "el test MTOP ya fue reclamado o evaluado en esta maquina"
        ) from error
    try:
        actual_seal = build_test_seal(
            archive_path,
            source_map_path,
            catalog_path,
        )
        if (
            _canonical_json_bytes(expected_seal)
            != _canonical_json_bytes(actual_seal)
        ):
            raise ValueError(
                "los bytes test no coinciden con el sello congelado"
            )
        records = _read_test_records(
            archive_path,
            mapping,
            expected_seal,
        )
        raw_report = evaluator(records)
        report = _validated_aggregate_report(
            raw_report,
            records=records,
            preregistration=preregistration,
            preregistration_sha256=preregistration_sha256,
            seal_path=seal_path,
        )
        _write_json_atomic(report_path, report)
        receipt = {
            **reservation,
            "schema": EVALUATION_RECEIPT_SCHEMA,
            "state": "completed",
            "completed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "report_repo_path": (
                _portable_path(report_path)
                if report_path.is_relative_to(ROOT.resolve())
                else f"synthetic/{report_path.name}"
            ),
            "report_sha256": _sha256(report_path),
            "status": report["status"],
            "contains_test_text": False,
        }
        _write_json_create_new(ledger_directory / "receipt.json", receipt)
        return report
    except BaseException as error:
        failure = {
            **reservation,
            "schema": EVALUATION_RECEIPT_SCHEMA,
            "state": "failed",
            "failed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "failure_type": type(error).__name__,
            "contains_test_text": False,
        }
        try:
            _write_json_create_new(ledger_directory / "failure.json", failure)
        except (FileExistsError, OSError):
            pass
        raise


def materialize_test(
    archive_path: Path,
    source_map_path: Path,
    catalog_path: Path,
    seal_path: Path,
    preregistration_path: Path,
    output_path: Path,
    receipt_path: Path,
    usage_ledger_path: Path | None = None,
) -> dict[str, Any]:
    """Materialize only a synthetic fixture; official test must stay in memory."""

    for path, description in (
        (output_path, "la salida test"),
        (receipt_path, "el recibo test"),
    ):
        if path.exists():
            raise FileExistsError(f"{description} ya existe; el uso es de una sola vez")
    # This authorization check intentionally precedes opening the test archive.
    preregistration = _validate_preregistration(
        preregistration_path,
        seal_path,
        source_map_path,
        archive_path,
    )
    mapping = load_source_map(source_map_path, catalog_path)
    expected_seal = _load_json(seal_path, "el sello opaco de test")
    if _sha256(archive_path) == _official_archive_sha256():
        raise ValueError(
            "el test oficial no se materializa; use el gate integrado one-shot"
        )
    usage_identity = _test_usage_identity(expected_seal)
    usage_ledger = (
        usage_ledger_path.resolve()
        if usage_ledger_path is not None
        else _default_usage_ledger_path(expected_seal).resolve()
    )
    preregistration_sha256 = _sha256(preregistration_path)
    reservation = {
        "schema": "baxy.mtop-test-usage-ledger.v1",
        "state": "reserved",
        "usage_identity": usage_identity,
        "archive_sha256": _sha256(archive_path),
        "test_seal_sha256": _sha256(seal_path),
        "preregistration_sha256": preregistration_sha256,
        "run_id": preregistration["run_id"],
    }
    try:
        _write_json_create_new(usage_ledger, reservation)
    except FileExistsError as error:
        raise FileExistsError(
            "el test MTOP oficial ya fue reservado o usado; no puede "
            "materializarse con otra ruta, salida o prerregistro"
        ) from error
    actual_seal = build_test_seal(archive_path, source_map_path, catalog_path)
    if (
        expected_seal.get("schema") != SEAL_SCHEMA
        or _canonical_json_bytes(expected_seal) != _canonical_json_bytes(actual_seal)
    ):
        raise ValueError("los bytes de test ya no coinciden con el sello congelado")
    records: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(archive_path) as bundle:
            for language in sorted(mapping["selection"]["locales"]):
                member_name = f"mtop/{language}/test.txt"
                with bundle.open(member_name, "r") as handle:
                    ordinal = 0
                    for raw_line in handle:
                        if not raw_line.strip():
                            continue
                        ordinal += 1
                        opaque_id = _opaque_record_id(raw_line, language, ordinal)
                        try:
                            decoded = raw_line.decode("utf-8")
                        except UnicodeDecodeError as error:
                            raise ValueError("MTOP test no es UTF-8 valido") from error
                        records.append(
                            _parse_row(
                                decoded,
                                language=language,
                                split="test",
                                mapping=mapping,
                                require_explicit_intent=False,
                                opaque_test_id=opaque_id,
                            )
                        )
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ValueError("no se pudo materializar el test MTOP sellado") from error
    if len(records) != expected_seal["rows"]:
        raise ValueError("el test materializado no conserva el recuento sellado")
    records.sort(key=lambda row: (row["locale"], row["source_id"]))
    _write_bytes_atomic(
        output_path,
        b"".join(_canonical_json_bytes(record) for record in records),
    )
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "run_id": preregistration["run_id"],
        "usage_identity": usage_identity,
        "preregistration_sha256": preregistration_sha256,
        "test_seal_sha256": _sha256(seal_path),
        "source_map_sha256": _sha256(source_map_path),
        "archive_sha256": _sha256(archive_path),
        "output": {
            "file_name": output_path.name,
            "sha256": _sha256(output_path),
            "bytes": output_path.stat().st_size,
            "rows": len(records),
        },
        "execution_authority": False,
    }
    _write_json_atomic(receipt_path, receipt)
    _write_json_atomic(
        usage_ledger,
        {
            **reservation,
            "state": "materialized",
            "output_sha256": receipt["output"]["sha256"],
            "output_rows": receipt["output"]["rows"],
            "receipt_sha256": _sha256(receipt_path),
        },
    )
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    development = subparsers.add_parser(
        "build-development",
        help="Construye solo train/eval EN/ES; nunca abre test.",
    )
    development.add_argument("--dataset-root", required=True, type=Path)
    development.add_argument("--output", required=True, type=Path)
    development.add_argument("--manifest", required=True, type=Path)
    development.add_argument("--source-map", type=Path, default=DEFAULT_MAP)
    development.add_argument("--product-catalog", type=Path, default=DEFAULT_CATALOG)
    development.add_argument("--test-seal", type=Path, default=DEFAULT_SEAL)

    seal = subparsers.add_parser(
        "seal-test",
        help="Sella test como bytes sin decodificar contenido ni columnas.",
    )
    seal.add_argument("--archive", required=True, type=Path)
    seal.add_argument("--output", type=Path, default=DEFAULT_SEAL)
    seal.add_argument("--source-map", type=Path, default=DEFAULT_MAP)
    seal.add_argument("--product-catalog", type=Path, default=DEFAULT_CATALOG)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "build-development":
        result = build_development(
            args.dataset_root,
            args.source_map,
            args.product_catalog,
            args.output,
            args.manifest,
            args.test_seal,
        )
    elif args.command == "seal-test":
        result = build_test_seal(
            args.archive,
            args.source_map,
            args.product_catalog,
        )
        _write_json_atomic(args.output, result)
    else:  # pragma: no cover - argparse enforces the closed command set.
        raise AssertionError("comando MTOP desconocido")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileExistsError, OSError, ValueError) as error:
        print(f"MTOP gate: {error}", file=sys.stderr)
        raise SystemExit(2)
