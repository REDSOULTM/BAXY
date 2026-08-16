from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT
    / "experiments/mind_router_spike/preregister_fresh_independent_cut_b_recogniser_r266.py"
)
RUNNER = ROOT / "experiments/mind_router_spike/run_fresh_independent_cut_b_recogniser_r266.py"


def module():
    spec = importlib.util.spec_from_file_location("r266_preregistration", PREREGISTRATION)
    assert spec and spec.loader
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    return candidate


def test_r266_records_the_pre_recogniser_r265_failure_and_freezes_a_corrected_runner() -> None:
    report = module().build()

    assert report["predecessor"]["r265_output_created"] is False
    assert report["predecessor"]["r265_failure"] == (
        "KeyError: runner_sha256 during preflight before recogniser import"
    )
    assert report["scoring"]["runner"] == (
        "experiments/mind_router_spike/run_fresh_independent_cut_b_recogniser_r266.py"
    )
    assert report["scoring"]["runner_sha256"]
    assert report["scoring"]["runner_hash_location_validated"] == (
        "scoring.runner_sha256"
    )
    assert report["constraints"]["recogniser_measured"] is False
    assert report["constraints"]["model_started"] is False


def test_r266_validates_the_preregistered_runner_hash_before_importing_recogniser() -> None:
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
    assert 'r266["scoring"]["runner_sha256"]' in source
    assert direct_call_names.index("validate_inputs") < direct_call_names.index(
        "recogniser"
    )
    assert "subprocess" not in source
    assert "torch" not in source
