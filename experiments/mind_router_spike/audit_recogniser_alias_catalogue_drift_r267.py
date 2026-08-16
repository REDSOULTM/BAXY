"""Bind the proposal-only alias asset to the authenticated current catalogue."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
ALIASES = REPO / "src" / "baxy_mind" / "data" / "catalog_operation_aliases.v1.json"
CATALOGUE = REPO / "artifacts" / "development" / "current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts" / "audit" / "recogniser_alias_catalogue_drift_r267.json"

WORD_LIFECYCLE_OPERATIONS = (
    "office.word.append",
    "office.word.close",
    "office.word.discard",
    "office.word.save",
    "office.word.start",
    "office.word.status",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def audit() -> dict[str, Any]:
    alias_asset = _load_object(ALIASES)
    snapshot = _load_object(CATALOGUE)
    rows = alias_asset.get("aliases")
    catalogue = snapshot.get("catalogue")
    if not isinstance(rows, list) or not isinstance(catalogue, dict):
        raise ValueError("alias asset or R219 catalogue has an invalid shape")

    capability_rows = catalogue.get("capabilities")
    if not isinstance(capability_rows, list):
        raise ValueError("R219 capabilities are missing")
    catalogue_operations = tuple(
        row["name"]
        for row in capability_rows
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    )
    if (
        len(catalogue_operations) != len(capability_rows)
        or len(catalogue_operations) != len(set(catalogue_operations))
        or catalogue.get("operations") != len(catalogue_operations)
        or catalogue.get("operation_names_sha256")
        != _canonical_sha256(list(catalogue_operations))
    ):
        raise ValueError("R219 catalogue identity is invalid")

    target_operations: list[str] = []
    all_alias_operations: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("alias row is not an object")
        target = row.get("target_operation")
        operations = row.get("operations")
        if (
            not isinstance(target, str)
            or not isinstance(operations, list)
            or not operations
            or not all(isinstance(operation, str) for operation in operations)
            or operations[-1] != target
        ):
            raise ValueError("alias row has an invalid operation binding")
        target_operations.append(target)
        all_alias_operations.update(operations)
    if len(target_operations) != len(set(target_operations)):
        raise ValueError("each alias target must be represented once")
    if alias_asset.get("alias_count") != len(rows):
        raise ValueError("alias asset count does not match its rows")

    catalogue_set = set(catalogue_operations)
    target_set = set(target_operations)
    excluded_memory = tuple(alias_asset.get("excluded_app_memory_operations", ()))
    excluded_memory_set = set(excluded_memory)
    missing_targets = tuple(sorted(catalogue_set - target_set))
    missing_word = tuple(
        operation for operation in WORD_LIFECYCLE_OPERATIONS if operation in missing_targets
    )
    if (
        alias_asset.get("schema") != "baxy.catalog-operation-aliases.v1"
        or alias_asset.get("authority")
        != "proposal_only_authenticated_catalog_intersection"
        or alias_asset.get("catalog_operations") != len(catalogue_operations)
        or alias_asset.get("catalog_sha256") != catalogue.get("operation_names_sha256")
        or not all_alias_operations <= catalogue_set
        or not excluded_memory_set <= catalogue_set
        or excluded_memory_set & target_set
        or set(missing_word) != set(WORD_LIFECYCLE_OPERATIONS)
        or set(missing_targets) != excluded_memory_set | set(WORD_LIFECYCLE_OPERATIONS)
    ):
        raise ValueError("alias asset is not bound to the current catalogue contract")

    return {
        "schema": "baxy.recogniser-alias-catalogue-drift-r267.v1",
        "authority": "read_only_current_catalogue_alias_contract_audit_not_recogniser_or_model_measurement",
        "verdict": "passed_current_catalogue_binding_without_manual_word_grammar_expansion",
        "catalogue_binding": {
            "catalogue_operations": len(catalogue_operations),
            "catalogue_operation_names_sha256": catalogue["operation_names_sha256"],
            "alias_rows": len(rows),
            "alias_target_operations": len(target_set),
            "all_alias_operations_are_current": True,
            "retired_alias_target_operations": [],
        },
        "unaliased_current_operations": {
            "total": len(missing_targets),
            "intentional_private_memory_operations": sorted(excluded_memory_set),
            "word_lifecycle_operations_without_aliases": list(missing_word),
            "manual_word_aliases_added": False,
            "requires_published_human_word_com_lifecycle_source": True,
        },
        "interpretation": {
            "repaired": [
                "removed retired notification.cancel.at alias",
                "rebound alias metadata from the 169-operation snapshot to R219",
            ],
            "not_measured": [
                "recogniser reach",
                "retrieval",
                "model decision",
                "vetoes",
                "visible text",
                "latency",
                "providers",
                "external effects",
            ],
            "does_not_authorize": [
                "manual Word grammar expansion",
                "R264/R266 rerun or tuning",
                "R228, CLINC test/OOS test, or V9 access",
                "runtime promotion",
            ],
        },
        "constraints": {
            "model_started": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "r228_opened": False,
            "clinc_opened": False,
            "public_holdout_opened": False,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "identities": {
            "program_sha256": _sha256(Path(__file__)),
            "alias_asset_sha256": _sha256(ALIASES),
            "r219_catalogue_snapshot_sha256": _sha256(CATALOGUE),
        },
    }


def main() -> int:
    result = audit()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(
        (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "catalogue_binding": result["catalogue_binding"],
                "unaliased_current_operations": result["unaliased_current_operations"],
                "output": str(OUTPUT.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
