from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT
    / "experiments/mind_router_spike/preregister_fresh_independent_cut_b_recogniser_r265.py"
)
RUNNER = ROOT / "experiments/mind_router_spike/run_fresh_independent_cut_b_recogniser_r265.py"


def module():
    spec = importlib.util.spec_from_file_location("r265_preregistration", PREREGISTRATION)
    assert spec and spec.loader
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    return candidate


def test_r265_freezes_one_read_only_recogniser_scorer_before_execution() -> None:
    report = module().build()

    assert report["source"]["r264_rows"] == 114
    assert report["scoring"] == {
        "runner": "experiments/mind_router_spike/run_fresh_independent_cut_b_recogniser_r265.py",
        "runner_sha256": report["scoring"]["runner_sha256"],
        "expected_operation_match": "resolve_explicit_effects operations equal the complete expected_operations tuple",
        "outcomes": ["resolved_expected", "resolved_other", "unresolved"],
        "cuts": ["overall", "family", "language", "expected_operation"],
        "recogniser_majority_limit": 0.5,
        "alias_surface_reported": True,
    }
    assert report["constraints"]["recogniser_measured"] is False
    assert report["constraints"]["model_started"] is False
    assert report["constraints"]["r228_opened"] is False


def test_r265_runner_writes_once_and_has_no_model_or_provider_path() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    main = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    names = {node.id for node in ast.walk(main) if isinstance(node, ast.Name)}

    assert "OUTPUT" in names
    assert "subprocess" not in source
    assert "torch" not in source
    assert "providers_enabled" in source
    assert "resolve_explicit_effects" in source
