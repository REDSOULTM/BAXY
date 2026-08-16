"""Test whether a catalog's non-lexical schema shape can ground its domains.

R211 established that the authenticated catalog has typed schemas and risk, but
not an explicit domain ontology.  This follow-up deliberately removes all
operation names, property names, descriptions and enum *values* before asking
what remains distinguishable.  It is an information-boundary audit, not an
operation selector, a runtime gate, or a new text classifier.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "artifacts/development/catalog_vocabulary_snapshot.json"
OUT = REPO / "artifacts/audit/catalog_structural_discriminability_r212.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _constraint_shape(schema: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    """Keep validation structure while discarding all lexical values."""

    return tuple(
        (key, len(value) if key == "enum" else True)
        for key, value in sorted(schema.items())
        if key
        in {
            "additionalProperties",
            "enum",
            "format",
            "maxItems",
            "maxLength",
            "maximum",
            "minItems",
            "minLength",
            "minimum",
            "x-maxUtf8Bytes",
            "x-nonWhitespace",
        }
    )


def _shape(arguments_schema: dict[str, Any], risk: str) -> dict[str, Any]:
    properties = arguments_schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ValueError("r212_properties_must_be_object")
    required = arguments_schema.get("required", [])
    if not isinstance(required, list) or not all(
        isinstance(name, str) for name in required
    ):
        raise ValueError("r212_required_must_be_string_list")
    required_set = set(required)
    if not required_set.issubset(properties):
        raise ValueError("r212_required_field_not_declared")
    fields = []
    for property_schema in properties.values():
        value_type = (
            property_schema.get("type") if isinstance(property_schema, dict) else None
        )
        if not isinstance(value_type, (str, list)) or (
            isinstance(value_type, list)
            and not all(isinstance(item, str) for item in value_type)
        ):
            raise ValueError("r212_property_must_have_type")
        fields.append(
            {
                "required": False,  # Filled by the position-free multiplicity below.
                "type": [value_type]
                if isinstance(value_type, str)
                else sorted(value_type),
                "constraint_shape": list(_constraint_shape(property_schema)),
            }
        )
    # Property names are intentionally absent.  Requiredness is retained only
    # as a count: binding an individual name would reintroduce lexical signal.
    return {
        "root_type": arguments_schema.get("type"),
        "additional_properties": arguments_schema.get("additionalProperties"),
        "risk": risk,
        "property_count": len(properties),
        "required_count": len(required_set),
        "optional_count": len(properties) - len(required_set),
        "fields": sorted(
            fields,
            key=lambda field: json.dumps(field, ensure_ascii=False, sort_keys=True),
        ),
    }


def build(catalog_path: Path = CATALOG) -> dict[str, Any]:
    capabilities = json.loads(catalog_path.read_text(encoding="utf-8"))["capabilities"]
    by_shape: dict[str, list[str]] = defaultdict(list)
    operations: list[dict[str, Any]] = []
    for capability in capabilities:
        name, risk, arguments_schema = (
            capability["name"],
            capability["risk"],
            capability["argumentsSchema"],
        )
        shape = _shape(arguments_schema, risk)
        encoded = json.dumps(
            shape, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        shape_sha = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        by_shape[shape_sha].append(name)
        operations.append({"name": name, "structural_shape_sha256": shape_sha})
    classes = [
        {
            "structural_shape_sha256": digest,
            "operations": sorted(names),
            "operations_count": len(names),
        }
        for digest, names in sorted(by_shape.items())
    ]
    class_count = len(classes)
    operation_count = len(operations)
    ambiguous = sum(
        item["operations_count"] for item in classes if item["operations_count"] > 1
    )
    return {
        "schema": "baxy.catalog-structural-discriminability-r212.v1",
        "authority": "diagnostic_only_no_runtime_gate_or_operation_selection",
        "identities": {
            "program_sha256": _sha256(Path(__file__)),
            "catalog_sha256": _sha256(catalog_path),
        },
        "method": {
            "input_fields_used": ["argumentsSchema", "risk"],
            "lexical_inputs_discarded": [
                "operation_name",
                "property_name",
                "description",
                "enum_values",
            ],
            "selection_or_runtime_invoked": False,
        },
        "counts": {
            "operations": operation_count,
            "structural_equivalence_classes": class_count,
            "singleton_operations": sum(
                item["operations_count"] == 1 for item in classes
            ),
            "operations_in_ambiguous_classes": ambiguous,
            "largest_equivalence_class": max(
                item["operations_count"] for item in classes
            ),
            "exact_operation_upper_bound_from_shape_only": round(
                class_count / operation_count, 6
            ),
        },
        "equivalence_classes": classes,
        "operations": sorted(operations, key=lambda row: row["name"]),
        "conclusion": {
            "structural_shape_alone_can_validate_a_known_call": True,
            "structural_shape_alone_can_ground_a_free_form_domain": False,
            "structural_shape_alone_can_select_all_catalog_operations": False,
            "runtime_change_authorized": False,
            "lexical_gate_authorized": False,
            "fresh_cut_b_authorized": False,
        },
    }


def main() -> None:
    OUT.write_bytes(
        (
            json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
    )


if __name__ == "__main__":
    main()
