"""Inventory typed catalog signal before attempting any domain-grounding change."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "artifacts/development/catalog_vocabulary_snapshot.json"
OUT = REPO / "artifacts/audit/catalog_structural_signal_r211.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(catalog_path: Path = CATALOG) -> dict[str, object]:
    capabilities = json.loads(catalog_path.read_text(encoding="utf8"))["capabilities"]
    rows: list[dict[str, object]] = []
    families: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for capability in capabilities:
        schema = capability["argumentsSchema"]
        properties = schema.get("properties", {})
        required = tuple(sorted(schema.get("required", ())))
        row = {"name": capability["name"], "family": capability["name"].split(".", 1)[0], "risk": capability["risk"], "required_fields": required, "property_fields": tuple(sorted(properties)), "description_sha256": hashlib.sha256(capability["description"].encode()).hexdigest()}
        rows.append(row)
        families[row["family"]].append(row)
    family_rows = {family: {"operations": len(items), "operations_with_required_fields": sum(bool(item["required_fields"]) for item in items), "risks": dict(sorted(Counter(item["risk"] for item in items).items())), "required_fields": sorted({field for item in items for field in item["required_fields"]})} for family, items in sorted(families.items())}
    return {"schema": "baxy.catalog-structural-signal-r211.v1", "authority": "diagnostic_only_no_runtime_gate_or_operation_selection", "identities": {"program_sha256": sha(Path(__file__)), "catalog_sha256": sha(catalog_path)}, "counts": {"operations": len(rows), "families": len(family_rows), "operations_with_required_fields": sum(bool(row["required_fields"]) for row in rows), "operations_without_required_fields": sum(not row["required_fields"] for row in rows)}, "families": family_rows, "operations": sorted(rows, key=lambda row: row["name"]), "conclusion": {"schema_carries_typed_argument_and_risk_signal": True, "schema_carries_no_explicit_domain_ontology": True, "runtime_change_authorized": False, "lexical_gate_authorized": False}}


def main() -> None:
    OUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


if __name__ == "__main__":
    main()
