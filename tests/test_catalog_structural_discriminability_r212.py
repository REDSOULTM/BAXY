from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_r212_proves_shape_is_not_a_domain_ontology() -> None:
    source = (
        ROOT
        / "experiments/mind_router_spike/audit_catalog_structural_discriminability_r212.py"
    )
    spec = importlib.util.spec_from_file_location("r212", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    report = module.build()

    assert report["counts"]["operations"] == 169
    assert report["counts"]["structural_equivalence_classes"] < 169
    assert report["counts"]["operations_in_ambiguous_classes"] > 0
    assert report["counts"]["largest_equivalence_class"] > 1
    assert report["method"]["lexical_inputs_discarded"] == [
        "operation_name",
        "property_name",
        "description",
        "enum_values",
    ]
    assert report["conclusion"] == {
        "structural_shape_alone_can_validate_a_known_call": True,
        "structural_shape_alone_can_ground_a_free_form_domain": False,
        "structural_shape_alone_can_select_all_catalog_operations": False,
        "runtime_change_authorized": False,
        "lexical_gate_authorized": False,
        "fresh_cut_b_authorized": False,
    }


def test_r212_attested_artifact_matches_the_current_instrument() -> None:
    source = (
        ROOT
        / "experiments/mind_router_spike/audit_catalog_structural_discriminability_r212.py"
    )
    spec = importlib.util.spec_from_file_location("r212_artifact", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    artifact = ROOT / "artifacts/audit/catalog_structural_discriminability_r212.json"
    assert json.loads(artifact.read_text(encoding="utf-8")) == module.build()
