from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT
    / "experiments/mind_router_spike/preregister_independent_clarification_cut_b_entry_path_r273.py"
)
RUNNER = (
    ROOT
    / "experiments/mind_router_spike/measure_independent_clarification_cut_b_entry_path_r274.py"
)
ARTIFACT = (
    ROOT
    / "artifacts/development/independent_clarification_cut_b_r273.entry-path.preregistration.json"
)


def _module():
    spec = importlib.util.spec_from_file_location("r273_preregistration", PREREGISTRATION)
    assert spec and spec.loader
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    return candidate


def _sealed_report():
    candidate = _module()
    candidate.MEASUREMENT_OUTPUT = ROOT / "artifacts/audit/r274-output-must-be-absent.json"
    return candidate.build()


def test_r273_seals_the_omitted_early_clarification_gate_before_model_start() -> None:
    report = _sealed_report()

    assert report["authority"] == (
        "sealed_before_model_start_and_before_r270_entry_path_measurement"
    )
    assert report["source"]["r270_rows"] == 93
    assert report["source"]["catalogue_operations"] == 174
    assert report["scoring"]["ordered_gates"] == [
        "resolve_explicit_clarification_intent",
        "resolve_explicit_effects",
    ]
    assert report["scoring"]["model_decision_candidate_reach_limit"] == 0.5
    assert report["constraints"]["model_started"] is False


def test_r274_validates_its_sealed_identity_before_importing_recogniser() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    validate = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "validate_inputs"
    )
    names = {node.id for node in ast.walk(validate) if isinstance(node, ast.Name)}
    build = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build"
    )
    direct_call_names = []
    for statement in build.body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                direct_call_names.append(node.func.id)

    assert "sha256" in names
    assert 'r273["scoring"]["runner_sha256"]' in source
    assert direct_call_names.index("validate_inputs") < direct_call_names.index(
        "recogniser"
    )
    assert "subprocess" not in source
    assert "torch" not in source
    assert "llm" not in source.casefold()


def test_r274_uses_the_actual_order_and_never_retains_requests() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert source.index("resolve_explicit_clarification_intent") < source.index(
        "resolve_explicit_effects"
    )
    assert '"request_texts_retained": False' in source
    assert '"request_identifiers_retained": False' in source
    assert '"model_started": False' in source


def test_r273_artifact_matches_the_current_sealed_contract() -> None:
    assert json.loads(ARTIFACT.read_text(encoding="utf-8")) == _sealed_report()
