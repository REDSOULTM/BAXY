"""Audit exact operation coverage of BAXY's language oracles.

This audit does not score the product and grants no execution authority.  It
compares every operation named by the reviewed development corpus, the latest
opened generalization holdout, and the frozen historical corpus with the
authenticated catalogue emitted by the current Core.  Legacy family labels,
language metadata repairs, reminder/notification alternatives, and operations
missing from the evaluation union remain explicit instead of being counted as
coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    current_core_capabilities,
    discover_core,
    write_json_atomic,
)


CURRENT_REVIEW = (
    REPO / "artifacts/development/current_catalog_review_development.v1.jsonl"
)
GENERALIZATION_HOLDOUT = (
    REPO / "artifacts/holdout/generalization_product_holdout_v19.jsonl"
)
HISTORICAL_CORPUS = REPO / "tests/data/historical_messages.jsonl"
OUTPUT = REPO / "artifacts/audit/catalog_oracle_coverage_r52.json"
PRODUCT_LANGUAGES = frozenset({"es", "en", "spanglish"})


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: JSONL row must be an object")
            rows.append(value)
    if not rows:
        raise ValueError(f"{path}: corpus is empty")
    return rows


def _operation_sets(
    rows: Iterable[dict[str, Any]],
    field: str,
) -> tuple[set[str], int]:
    operations: set[str] = set()
    rows_with_operations = 0
    for row in rows:
        value = row.get(field)
        if not isinstance(value, list):
            continue
        row_operations: set[str] = set()
        for operation_set in value:
            if not isinstance(operation_set, list):
                raise ValueError(f"{field} must contain operation arrays")
            for operation in operation_set:
                if not isinstance(operation, str) or not operation:
                    raise ValueError(f"{field} contains an invalid operation")
                row_operations.add(operation)
        if row_operations:
            rows_with_operations += 1
            operations.update(row_operations)
    return operations, rows_with_operations


def _historical_operations(
    rows: Iterable[dict[str, Any]],
) -> tuple[set[str], Counter[str], int]:
    operations: set[str] = set()
    counts: Counter[str] = Counter()
    rows_with_operations = 0
    for row in rows:
        value = row.get("operations")
        if not isinstance(value, list):
            continue
        row_operations = {
            operation
            for operation in value
            if isinstance(operation, str) and operation
        }
        if row_operations:
            rows_with_operations += 1
            operations.update(row_operations)
            counts.update(row_operations)
    return operations, counts, rows_with_operations


def _language_counts(rows: Iterable[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(
        sorted(
            Counter(str(row.get(field) or "missing") for row in rows).items()
        )
    )


def _source_summary(
    *,
    path: Path,
    rows: list[dict[str, Any]],
    operations: set[str],
    rows_with_operations: int,
    catalog_names: set[str],
    blind_holdout: bool,
    language_field: str,
) -> dict[str, Any]:
    exact = sorted(operations & catalog_names)
    foreign = sorted(operations - catalog_names)
    return {
        "path": str(path.relative_to(REPO)),
        "sha256": _file_sha256(path),
        "rows": len(rows),
        "rows_with_operations": rows_with_operations,
        "blind_holdout": blind_holdout,
        "language_counts": _language_counts(rows, language_field),
        "exact_catalog_operations": exact,
        "exact_catalog_operation_count": len(exact),
        "foreign_or_legacy_labels": foreign,
        "foreign_or_legacy_label_count": len(foreign),
    }


def build_audit(
    capabilities: Iterable[dict[str, Any]],
    current_rows: list[dict[str, Any]],
    holdout_rows: list[dict[str, Any]],
    historical_rows: list[dict[str, Any]],
    *,
    current_path: Path = CURRENT_REVIEW,
    holdout_path: Path = GENERALIZATION_HOLDOUT,
    historical_path: Path = HISTORICAL_CORPUS,
    include_file_hashes: bool = True,
) -> dict[str, Any]:
    catalog = sorted(
        (
            {
                key: capability[key]
                for key in ("name", "description", "argumentsSchema", "risk")
            }
            for capability in capabilities
        ),
        key=lambda capability: str(capability["name"]),
    )
    catalog_names = {str(capability["name"]) for capability in catalog}
    if len(catalog_names) != len(catalog):
        raise ValueError("authenticated catalogue contains duplicate operation names")

    current_operations, current_operation_rows = _operation_sets(
        current_rows,
        "compatible_terminal_operation_sets",
    )
    holdout_operations, holdout_operation_rows = _operation_sets(
        holdout_rows,
        "compatible_terminal_operation_sets",
    )
    historical_operations, historical_counts, historical_operation_rows = (
        _historical_operations(historical_rows)
    )

    def source_summary(
        *,
        path: Path,
        rows: list[dict[str, Any]],
        operations: set[str],
        rows_with_operations: int,
        blind_holdout: bool,
        language_field: str,
    ) -> dict[str, Any]:
        if include_file_hashes:
            return _source_summary(
                path=path,
                rows=rows,
                operations=operations,
                rows_with_operations=rows_with_operations,
                catalog_names=catalog_names,
                blind_holdout=blind_holdout,
                language_field=language_field,
            )
        exact = sorted(operations & catalog_names)
        foreign = sorted(operations - catalog_names)
        return {
            "path": str(path),
            "rows": len(rows),
            "rows_with_operations": rows_with_operations,
            "blind_holdout": blind_holdout,
            "language_counts": _language_counts(rows, language_field),
            "exact_catalog_operations": exact,
            "exact_catalog_operation_count": len(exact),
            "foreign_or_legacy_labels": foreign,
            "foreign_or_legacy_label_count": len(foreign),
        }

    current_summary = source_summary(
        path=current_path,
        rows=current_rows,
        operations=current_operations,
        rows_with_operations=current_operation_rows,
        blind_holdout=False,
        language_field="language",
    )
    holdout_summary = source_summary(
        path=holdout_path,
        rows=holdout_rows,
        operations=holdout_operations,
        rows_with_operations=holdout_operation_rows,
        blind_holdout=True,
        language_field="language",
    )
    historical_summary = source_summary(
        path=historical_path,
        rows=historical_rows,
        operations=historical_operations,
        rows_with_operations=historical_operation_rows,
        blind_holdout=False,
        language_field="language",
    )

    evaluation_union = (current_operations | holdout_operations) & catalog_names
    blind_coverage = holdout_operations & catalog_names
    missing_evaluation = sorted(catalog_names - evaluation_union)
    missing_blind = sorted(catalog_names - blind_coverage)
    families = {name.split(".", maxsplit=1)[0] for name in catalog_names}
    covered_families = {
        name.split(".", maxsplit=1)[0] for name in evaluation_union
    }
    blind_families = {name.split(".", maxsplit=1)[0] for name in blind_coverage}

    language_repairs = sum(
        str(row.get("language") or "")
        != str(row.get("source_declared_language") or "")
        for row in current_rows
    )
    outside_product_language_rows = sum(
        str(row.get("language") or "") not in PRODUCT_LANGUAGES
        for row in current_rows
    )
    reminder_notification_alternatives = sum(
        {
            "reminder.create",
            "notification.schedule",
        }
        <= {
            operation
            for operation_set in row.get("compatible_terminal_operation_sets")
            or []
            if isinstance(operation_set, list)
            for operation in operation_set
            if isinstance(operation, str)
        }
        for row in current_rows
    )
    legacy_labels = sorted(historical_operations - catalog_names)
    legacy_rows = sum(
        count for operation, count in historical_counts.items() if operation in legacy_labels
    )

    return {
        "schema": "baxy.catalog-oracle-coverage-audit.v1",
        "authority": "diagnostic_only_no_execution_authority_not_a_release_oracle",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "catalog": {
            "source": "authenticated_current_core_hello",
            "operations": len(catalog),
            "sha256": _canonical_hash(catalog),
            "families": sorted(families),
            "family_count": len(families),
        },
        "sources": {
            "current_review_development": current_summary,
            "generalization_holdout_r19": holdout_summary,
            "historical_frozen": historical_summary,
        },
        "conflicts": {
            "historical_legacy_abstract_labels": legacy_labels,
            "historical_legacy_abstract_label_count": len(legacy_labels),
            "historical_rows_naming_legacy_labels": legacy_rows,
            "current_review_language_metadata_repairs": language_repairs,
            "current_review_rows_outside_product_language_scope": (
                outside_product_language_rows
            ),
            "current_review_reminder_notification_alternative_rows": (
                reminder_notification_alternatives
            ),
        },
        "coverage": {
            "evaluation_union_exact_operations": sorted(evaluation_union),
            "evaluation_union_exact_operation_count": len(evaluation_union),
            "evaluation_union_missing_operations": missing_evaluation,
            "evaluation_union_missing_operation_count": len(missing_evaluation),
            "evaluation_union_covered_families": sorted(covered_families),
            "evaluation_union_missing_families": sorted(families - covered_families),
            "blind_exact_operations": sorted(blind_coverage),
            "blind_exact_operation_count": len(blind_coverage),
            "blind_missing_operations": missing_blind,
            "blind_missing_operation_count": len(missing_blind),
            "blind_covered_families": sorted(blind_families),
            "blind_missing_families": sorted(families - blind_families),
        },
        "verdict": {
            "catalog_exact_operation_coverage_complete": not missing_evaluation,
            "blind_catalog_exact_operation_coverage_complete": not missing_blind,
            "historical_corpus_is_current_exact_operation_oracle": not legacy_labels,
            "fresh_cuts_a_to_d_still_required": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-review", type=Path, default=CURRENT_REVIEW)
    parser.add_argument("--holdout", type=Path, default=GENERALIZATION_HOLDOUT)
    parser.add_argument("--historical", type=Path, default=HISTORICAL_CORPUS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--core", type=Path)
    args = parser.parse_args()

    capabilities = current_core_capabilities(
        discover_core(args.core, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    audit = build_audit(
        capabilities,
        _read_jsonl(args.current_review),
        _read_jsonl(args.holdout),
        _read_jsonl(args.historical),
        current_path=args.current_review.resolve(),
        holdout_path=args.holdout.resolve(),
        historical_path=args.historical.resolve(),
    )
    write_json_atomic(args.output, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
