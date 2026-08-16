from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT / "experiments/mind_router_spike/preregister_situated_cut_b_model_path_r217.py"
)
SCORER = ROOT / "experiments/mind_router_spike/score_situated_cut_b_model_path_r218.py"


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r217_freezes_current_model_path_before_opening() -> None:
    module = _module("r217", PREREGISTRATION)
    report = module.build()

    assert report["population"]["rows"] == 93
    assert report["population"]["recogniser_reach"] < 0.5
    assert report["candidate"]["path"] == "unmodified_baxy_mind_turn_decide"
    assert report["constraints"]["effects_executed"] == 0
    assert report["constraints"]["opened_v9"] is False
    assert report["measurement"]["one_shot"] is True


def test_r217_published_preregistration_matches_frozen_builder() -> None:
    module = _module("r217_artifact", PREREGISTRATION)
    artifact = (
        ROOT
        / "artifacts/holdout/situated_cut_b_r215.model_path_r217.preregistration.json"
    )
    assert json.loads(artifact.read_text(encoding="utf-8")) == module.build()


def test_r218_scores_retrieval_decision_and_veto_separately() -> None:
    scorer = _module("r218_score", SCORER)
    rows = [
        {
            "case_id": "retrieval",
            "expected_operations": ["a"],
            "candidate_operations": [],
            "raw_proposal": {"effect_operations": []},
            "stages": [],
            "effect_operations": [],
            "intent_operations": [],
            "kind": "conversation",
            "reply_text": "",
            "question": "",
            "raw_visible_proposals": [],
            "seconds": 0.2,
        },
        {
            "case_id": "decision",
            "expected_operations": ["a"],
            "candidate_operations": ["a"],
            "raw_proposal": {"effect_operations": ["b"]},
            "stages": [],
            "effect_operations": ["b"],
            "intent_operations": [],
            "kind": "action",
            "reply_text": "",
            "question": "",
            "raw_visible_proposals": [],
            "seconds": 0.4,
        },
        {
            "case_id": "veto",
            "expected_operations": ["a"],
            "candidate_operations": ["a"],
            "raw_proposal": {"effect_operations": ["a"]},
            "stages": [{"name": "grounding", "effect_operations": []}],
            "effect_operations": [],
            "intent_operations": [],
            "kind": "conversation",
            "reply_text": "",
            "question": "",
            "raw_visible_proposals": [],
            "seconds": 0.6,
        },
        {
            "case_id": "accepted",
            "expected_operations": ["a"],
            "candidate_operations": ["a"],
            "raw_proposal": {"effect_operations": ["a"]},
            "stages": [],
            "effect_operations": ["a"],
            "intent_operations": ["a"],
            "kind": "action",
            "reply_text": "",
            "question": "",
            "raw_visible_proposals": [],
            "seconds": 0.8,
        },
    ]
    result = scorer.score_rows(rows)

    assert result["diagnostic_partition"] == {
        "retrieval": ["retrieval"],
        "decision": ["decision"],
        "veto": ["veto"],
        "partition_total": 3,
    }
    assert result["raw_decision"]["exact_rate"] == 0.5
    assert result["decision"]["exact_or_useful_clarification_rate"] == 0.25
