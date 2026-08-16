"""Build the explicit natural seen-scenario corpus for all Core operations."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.catalog_seen_scenarios_v1 import SEEN_UTTERANCES  # noqa: E402
from baxy_mind.planner import required_predecessors  # noqa: E402
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    current_core_capabilities,
    discover_core,
    write_json_atomic,
)


OUTPUT = REPO / "artifacts/development/catalog_seen_scenarios_r1.jsonl"
MANIFEST = REPO / "artifacts/development/catalog_seen_scenarios_r1.manifest.json"
ALLOWED_LANGUAGES = frozenset({"es", "en", "spanglish"})


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


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
    names = {str(capability["name"]) for capability in catalog}
    if len(names) != len(catalog):
        raise ValueError("authenticated catalogue contains duplicate operation names")
    if names != set(SEEN_UTTERANCES):
        raise ValueError(
            "seen scenario coverage mismatch; "
            f"missing={sorted(names - set(SEEN_UTTERANCES))}, "
            f"stale={sorted(set(SEEN_UTTERANCES) - names)}"
        )
    catalog_sha256 = _canonical_hash(catalog)
    rows: list[dict[str, Any]] = []
    for capability in catalog:
        operation = str(capability["name"])
        language, text = SEEN_UTTERANCES[operation]
        if language not in ALLOWED_LANGUAGES or not text.strip():
            raise ValueError(f"invalid seen scenario for {operation}")
        owner = "app_memory_parser" if operation.startswith("memory.") else "mind_sidecar"
        predecessors = required_predecessors(operation)
        plan = (*predecessors[:1], operation)
        if not set(plan) <= names:
            raise ValueError(f"seen scenario dependency left the catalogue: {operation}")
        rows.append(
            {
                "schema": "baxy.catalog-seen-scenario.development.v1",
                "case_id": "catalog-seen-natural-" + operation.replace(".", "-"),
                "text": text,
                "language": language,
                "owner": owner,
                "outcome": "action",
                "compatible_terminal_operation_sets": [list(plan)],
                "compatible_effect_operation_sets": [list(plan)],
                "target_operation": operation,
                "basis": "explicit_human_reviewed_seen_operation_scenario",
                "execution_authority": False,
                "blind_holdout": False,
                "catalog_sha256": catalog_sha256,
                "scenario_sha256": _canonical_hash(
                    {"operation": operation, "language": language, "text": text}
                ),
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
    language_counts = Counter(str(row["language"]) for row in rows)
    owner_counts = Counter(str(row["owner"]) for row in rows)
    manifest = {
        "schema": "baxy.catalog-seen-scenario-manifest.development.v1",
        "authority": "development_only_no_execution_authority_not_blind",
        "blind_holdout": False,
        "catalog": {
            "operations": len(capabilities),
            "sha256": catalog_sha256,
        },
        "review": {
            "rows": len(rows),
            "outcome_counts": {"action": len(rows)},
            "language_counts": dict(sorted(language_counts.items())),
            "owner_counts": dict(sorted(owner_counts.items())),
            "all_rows_explicitly_reviewed": True,
            "all_rows_derived_from_authenticated_catalog": False,
        },
        "output": {
            "path": str(args.output.resolve()),
            "bytes": args.output.stat().st_size,
            "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        },
    }
    write_json_atomic(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
