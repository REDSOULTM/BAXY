"""Build a non-blind seen-surface diagnostic for all Core operations.

Each row is derived from one authenticated catalogue description.  The exact
description is already visible to the product model during tool selection, so
this is deliberately a development preflight for Cut A, never a blind oracle.
Every row expects selection of its exact operation.  Argument extraction is a
later protocol request and is intentionally outside this probe; required
argument names remain recorded for the later argument-fidelity oracle.  No row
grants execution authority and the paired probe sends only ``turn.decide``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
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


OUTPUT = REPO / "artifacts/development/catalog_seen_development_r1.jsonl"
MANIFEST = (
    REPO / "artifacts/development/catalog_seen_development_r1.manifest.json"
)


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _seen_text(description: str) -> str:
    body = description.strip()
    if not body:
        raise ValueError("catalogue description cannot be empty")
    return "Baxy, " + body[:1].lower() + body[1:]


def _required_arguments(capability: dict[str, Any]) -> tuple[str, ...]:
    schema = capability.get("argumentsSchema")
    if not isinstance(schema, dict):
        raise ValueError("catalogue argumentsSchema must be an object")
    required = schema.get("required") or []
    if not isinstance(required, list) or not all(
        isinstance(value, str) and value for value in required
    ):
        raise ValueError("catalogue required arguments must be strings")
    return tuple(required)


def build_rows(
    capabilities: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
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
    names = [str(capability["name"]) for capability in catalog]
    if len(names) != len(set(names)):
        raise ValueError("authenticated catalogue contains duplicate operation names")
    catalog_sha256 = _canonical_hash(catalog)
    rows: list[dict[str, Any]] = []
    for capability in catalog:
        operation = str(capability["name"])
        description = str(capability["description"])
        required = _required_arguments(capability)
        rows.append(
            {
                "schema": "baxy.catalog-seen-development.v1",
                "case_id": "catalog-seen-" + operation.replace(".", "-"),
                "text": _seen_text(description),
                "language": "es",
                "outcome": "action",
                "compatible_terminal_operation_sets": [[operation]],
                "compatible_effect_operation_sets": [[operation]],
                "required_arguments": list(required),
                "basis": "authenticated_catalog_description_seen_surface",
                "execution_authority": False,
                "blind_holdout": False,
                "catalog_sha256": catalog_sha256,
                "description_sha256": hashlib.sha256(
                    description.encode("utf-8")
                ).hexdigest(),
            }
        )
    return rows, catalog_sha256


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    payload = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--core", type=Path)
    args = parser.parse_args()

    capabilities = current_core_capabilities(
        discover_core(args.core, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    rows, catalog_sha256 = build_rows(capabilities)
    _write_jsonl(args.output, rows)
    output_sha256 = hashlib.sha256(args.output.read_bytes()).hexdigest()
    outcome_counts: dict[str, int] = {}
    for row in rows:
        outcome = str(row["outcome"])
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
    manifest = {
        "schema": "baxy.catalog-seen-development-manifest.v1",
        "authority": "development_only_no_execution_authority_not_blind",
        "blind_holdout": False,
        "catalog": {
            "operations": len(capabilities),
            "sha256": catalog_sha256,
        },
        "review": {
            "rows": len(rows),
            "outcome_counts": dict(sorted(outcome_counts.items())),
            "all_rows_explicitly_reviewed": False,
            "all_rows_derived_from_authenticated_catalog": True,
        },
        "output": {
            "path": str(args.output.resolve()),
            "bytes": args.output.stat().st_size,
            "sha256": output_sha256,
        },
    }
    write_json_atomic(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
