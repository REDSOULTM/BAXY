from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT
    / "experiments/mind_router_spike/preregister_independent_clarification_cut_b_recogniser_r271.py"
)
RUNNER = (
    ROOT
    / "experiments/mind_router_spike/run_independent_clarification_cut_b_recogniser_r272.py"
)
ARTIFACT = (
    ROOT
    / "artifacts/development/independent_clarification_cut_b_r271.recogniser.preregistration.json"
)


def _module():
    spec = importlib.util.spec_from_file_location("r271_preregistration", PREREGISTRATION)
    assert spec and spec.loader
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    return candidate


def _sealed_report():
    candidate = _module()
    candidate.MEASUREMENT_OUTPUT = ROOT / "artifacts/audit/r272-output-must-be-absent.json"
    return candidate.build()


def test_r271_seals_the_first_r270_recogniser_measurement() -> None:
    report = _sealed_report()

    assert report["authority"] == "sealed_before_first_r270_recogniser_measurement"
    assert report["source"]["r270_rows"] == 93
    assert report["source"]["r270_semantic_cases"] == 31
    assert report["scoring"]["available_operations"] == (
        "all_current_r219_catalogue_operation_names"
    )
    assert report["scoring"]["recogniser_effect_reach"] == "resolved_any / rows"
    assert report["scoring"]["recogniser_effect_reach_limit"] == 0.5
    assert report["scoring"]["request_texts_retained"] is False
    assert report["constraints"]["recogniser_measured"] is False
    assert report["constraints"]["model_started"] is False


def test_r272_validates_the_sealed_runner_before_importing_the_recogniser() -> None:
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
    assert 'r271["scoring"]["runner_sha256"]' in source
    assert direct_call_names.index("validate_inputs") < direct_call_names.index(
        "recogniser"
    )
    assert "subprocess" not in source
    assert "torch" not in source


def test_r272_declares_all_effect_resolutions_unsafe_and_hides_request_text() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert '"resolved_any"' in source
    assert '"resolved_intended"' in source
    assert '"resolved_other"' in source
    assert '"request_texts_retained": False' in source
    assert '"request_identifiers_retained": False' in source
    assert '"recogniser_effect_reach": reach' in source
    assert "if observed:" in source


def test_r271_artifact_matches_the_current_sealed_contract() -> None:
    assert json.loads(ARTIFACT.read_text(encoding="utf-8")) == _sealed_report()
