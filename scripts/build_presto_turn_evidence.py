"""Promote licensed PRESTO utterances into BAXY turn-evidence artifacts.

The input archive is obtained separately from its official source. This script
never downloads silently, never retains PRESTO context/metadata, and only maps
reviewed PRESTO semantic labels to families that already exist in BAXY's product
catalog. It does not add capabilities, operation names, phrase rules or model
weights.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind.public_turn_corpus import (  # noqa: E402
    PUBLIC_RECORD_SCHEMA_VERSION,
    build_massive_records,
    build_presto_records,
    deduplicate_public_records,
    load_source_map,
)
from baxy_mind.turn_evidence import load_private_corpus  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_path(path: Path) -> str:
    """Return a stable repository-relative identity without leaking a home path."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError as error:
        raise ValueError(f"el artefacto versionable esta fuera del repositorio: {path}") from error


def _external_file_identity(path: Path, sha256: str) -> dict[str, str]:
    """Describe a separately obtained source without persisting its local path."""

    return {"file_name": path.name, "sha256": sha256}


def _product_families(catalog: Path) -> frozenset[str]:
    text = catalog.read_text(encoding="utf-8")
    operations = re.findall(
        r'Descriptor\(\s*"([a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+)"',
        text,
    )
    if not operations:
        raise ValueError("no se encontraron operaciones en el catalogo BAXY")
    return frozenset(operation.split(".", 1)[0] for operation in operations)


def _validate_mapping_families(mapping_families: Iterable[str], catalog: Path) -> None:
    available = _product_families(catalog)
    unsupported = sorted(set(mapping_families) - available)
    if unsupported:
        raise ValueError(
            "el mapa intenta introducir familias fuera del catalogo BAXY: "
            + ", ".join(unsupported)
        )


def _private_record(record: Any) -> dict[str, Any]:
    return {
        "schema": PUBLIC_RECORD_SCHEMA_VERSION,
        "text": record.text,
        "mode": record.mode,
        "families": list(record.families),
        "mission_id": record.mission_id,
        "source_id": record.source_id,
        "split": record.split,
        "provenance": {
            "dataset": "BAXY historical evidence (privacy-screened)",
            "license": "private-local",
        },
    }


def _deduplicate_runtime_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    """Apply the same exact-text conflict rule before the runtime sees a file."""

    by_text: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        text = row["text"]
        by_text.setdefault(" ".join(str(text).casefold().split()), []).append(row)
    accepted: list[dict[str, Any]] = []
    ambiguous = 0
    duplicates = 0
    for variants in by_text.values():
        signatures = {(row["mode"], tuple(row["families"])) for row in variants}
        if len(signatures) != 1:
            ambiguous += len(variants)
            continue
        duplicates += len(variants) - 1
        accepted.append(
            min(
                variants,
                key=lambda row: (
                    0 if row["provenance"].get("license") == "private-local" else 1,
                    str(row["source_id"]),
                ),
            )
        )
    accepted.sort(key=lambda row: (str(row["mission_id"]), str(row["source_id"])))
    return accepted, ambiguous, duplicates


def _normalized_text_identity(value: object) -> str:
    return " ".join(str(value).casefold().split())


def _exclude_runtime_overlap(
    runtime_rows: Iterable[dict[str, Any]],
    holdout_rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Keep evaluation text strictly unseen by the runtime evidence index.

    Public splits are deduplicated before historical evidence is merged. A
    common short request can still occur independently in the private corpus,
    so the final promotion boundary must be enforced after that merge.
    """

    candidates = list(holdout_rows)
    runtime_texts = {
        _normalized_text_identity(row.get("text"))
        for row in runtime_rows
    }
    accepted = [
        row
        for row in candidates
        if _normalized_text_identity(row.get("text")) not in runtime_texts
    ]
    accepted.sort(key=lambda row: (str(row["split"]), str(row["source_id"])))
    return accepted, len(candidates) - len(accepted)


def _write_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    payload = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )
    try:
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path, help="ZIP PRESTO v1 oficial descargado localmente.")
    parser.add_argument("--massive-archive", required=True, type=Path, help="TAR.GZ MASSIVE v1.1 oficial descargado localmente.")
    parser.add_argument(
        "--source-map",
        type=Path,
        default=ROOT / "src" / "baxy_mind" / "data" / "presto_turn_evidence_map.v1.json",
    )
    parser.add_argument(
        "--massive-source-map",
        type=Path,
        default=ROOT / "src" / "baxy_mind" / "data" / "massive_turn_evidence_map.v1.json",
    )
    parser.add_argument(
        "--historical",
        type=Path,
        default=ROOT / "tests" / "data" / "historical_messages.jsonl",
    )
    parser.add_argument(
        "--product-catalog",
        type=Path,
        default=ROOT / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs",
    )
    parser.add_argument(
        "--runtime-output",
        type=Path,
        default=ROOT / "tests" / "data" / "turn_evidence_runtime.v1.jsonl",
    )
    parser.add_argument(
        "--holdout-output",
        type=Path,
        default=ROOT / "tests" / "data" / "turn_evidence_public_holdout.v1.jsonl",
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=ROOT / "tests" / "data" / "turn_evidence_public_manifest.v1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_map = load_source_map(args.source_map)
    massive_source_map = load_source_map(args.massive_source_map)
    _validate_mapping_families(
        (family for _mode, families in source_map.labels.values() for family in families),
        args.product_catalog,
    )
    _validate_mapping_families(
        (family for _mode, families in massive_source_map.labels.values() for family in families),
        args.product_catalog,
    )
    historical_records, historical_report = load_private_corpus(args.historical)
    presto_train, train_report = build_presto_records(args.archive, source_map, "train")
    presto_validation, validation_report = build_presto_records(args.archive, source_map, "validation")
    presto_test, test_report = build_presto_records(args.archive, source_map, "test")
    massive_train, massive_train_report = build_massive_records(
        args.massive_archive, massive_source_map, "train"
    )
    massive_validation, massive_validation_report = build_massive_records(
        args.massive_archive, massive_source_map, "validation"
    )
    massive_test, massive_test_report = build_massive_records(
        args.massive_archive, massive_source_map, "test"
    )

    public_records = deduplicate_public_records(
        [
            *presto_train,
            *presto_validation,
            *presto_test,
            *massive_train,
            *massive_validation,
            *massive_test,
        ]
    )
    runtime_rows, runtime_ambiguous, runtime_duplicates = _deduplicate_runtime_rows(
        [
            *(_private_record(record) for record in historical_records),
            *(row for row in public_records if row["split"] == "train"),
        ]
    )
    holdout_rows, runtime_holdout_overlap = _exclude_runtime_overlap(
        runtime_rows,
        [row for row in public_records if row["split"] in {"validation", "test"}],
    )

    if len(runtime_rows) < 20_000:
        raise RuntimeError(
            f"el corpus runtime quedo en {len(runtime_rows)} filas; no alcanza el minimo de 20.000"
        )
    _write_atomic(args.runtime_output, runtime_rows)
    _write_atomic(args.holdout_output, holdout_rows)
    manifest = {
        "schema": "baxy.turn-evidence-promotion-manifest.v1",
        "runtime_schema": PUBLIC_RECORD_SCHEMA_VERSION,
        "sources": {
            "presto": {
                "source_map": {
                    "repo_path": _repo_path(args.source_map),
                    "sha256": _sha256(args.source_map),
                    **source_map.source,
                },
                "archive": _external_file_identity(
                    args.archive, train_report.archive_sha256
                ),
            },
            "massive": {
                "source_map": {
                    "repo_path": _repo_path(args.massive_source_map),
                    "sha256": _sha256(args.massive_source_map),
                    **massive_source_map.source,
                },
                "archive": _external_file_identity(
                    args.massive_archive, massive_train_report.archive_sha256
                ),
            },
        },
        "constraints": {
            "presto_locales": sorted(source_map.locales),
            "massive_locales": sorted(massive_source_map.locales),
            "presto_no_context": source_map.require_empty_previous_turns,
            "massive_minimum_localized_judgments": massive_source_map.minimum_localized_judgments,
            "no_new_capabilities": True,
            "public_train_only_at_runtime": True,
        },
        "historical": asdict(historical_report),
        "presto": {
            "train": asdict(train_report),
            "validation": asdict(validation_report),
            "test": asdict(test_report),
        },
        "massive": {
            "train": asdict(massive_train_report),
            "validation": asdict(massive_validation_report),
            "test": asdict(massive_test_report),
        },
        "outputs": {
            "runtime": {
                "repo_path": _repo_path(args.runtime_output),
                "rows": len(runtime_rows),
                "exact_text_ambiguous_removed": runtime_ambiguous,
                "exact_text_duplicates_removed": runtime_duplicates,
            },
            "heldout": {
                "repo_path": _repo_path(args.holdout_output),
                "rows": len(holdout_rows),
                "runtime_exact_text_overlap_removed": runtime_holdout_overlap,
            },
        },
        "public_after_cross_split_dedup": len(public_records),
        "runtime_modes": dict(sorted(Counter(str(row["mode"]) for row in runtime_rows).items())),
        "runtime_families": dict(sorted(
            Counter(family for row in runtime_rows for family in row["families"]).items()
        )),
    }
    _write_json_atomic(args.manifest_output, manifest)
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
