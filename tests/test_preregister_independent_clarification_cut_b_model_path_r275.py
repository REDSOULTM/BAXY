from __future__ import annotations

import ast
import json
from pathlib import Path

from sealed_evidence import assert_sealed


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT
    / "experiments/mind_router_spike/preregister_independent_clarification_cut_b_model_path_r275.py"
)
RUNNER = (
    ROOT
    / "experiments/mind_router_spike/run_independent_clarification_cut_b_model_path_r276.py"
)
SCORER = (
    ROOT
    / "experiments/mind_router_spike/score_independent_clarification_cut_b_model_path_r276.py"
)
ARTIFACT = (
    ROOT
    / "artifacts/development/independent_clarification_cut_b_r275.model-path.preregistration.json"
)
ARTIFACT_SEAL = "5e819988a23ff12357581e557f2329932a1e2c3f87a00b7be8f394b583a8544c"


def _sealed_report() -> dict[str, object]:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_r275_seals_the_registered_no_dispatch_model_path_after_r274() -> None:
    # R275 is a consumed preregistration. Its registered no-wake runtime was
    # sealed by hash before R276; rebuilding it from today's product manifest
    # would replace historical evidence with mutable machine state.
    report = _sealed_report()

    assert report["authority"] == "sealed_before_registered_local_model_start_or_product_turn"
    assert report["source"]["all_r270_rows"] == 93
    assert report["source"]["model_decision_candidate_rows"] == 79
    assert report["acceptance"]["natural_missing_fact_clarification_minimum"] == 0.95
    assert report["measurement"]["one_shot"] is True
    assert report["measurement"]["dispatch"] == "not_called"
    assert report["constraints"]["model_started"] is False
    assert report["constraints"]["effects_executed"] == 0


def test_r276_validates_before_runtime_or_sidecar_start() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    measure = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "measure"
    )
    direct_call_names = []
    for statement in measure.body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                direct_call_names.append(node.func.id)

    assert direct_call_names.index("validate_inputs") < direct_call_names.index(
        "resolve_runtime"
    )
    assert direct_call_names.index("validate_inputs") < direct_call_names.index(
        "JsonLineProcess"
    )
    assert '"turn.execute"' not in source
    assert '"providers_enabled": False' in source
    assert '"effects_executed": 0' in source


def test_r276_scorer_requires_an_effect_free_natural_missing_fact_clarification() -> None:
    source = SCORER.read_text(encoding="utf-8")

    assert "_question_obtains_missing_fact" in source
    assert 'row.get("kind") == "clarify"' in source
    assert "and not final" in source
    assert "manual_visible_text_review_required" in source
    assert "fixed_visible_reply_count" in source


def test_r275_artifact_matches_the_current_sealed_contract() -> None:
    # The builder still runs and still states the sealed contract — that is the
    # first test above. The published artifact also records the catalogue it
    # sealed, which has since moved, so it is audited by its seal (§7).
    assert_sealed(ARTIFACT, ARTIFACT_SEAL)
