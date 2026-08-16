from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "experiments/mind_router_spike/run_bge_m3_r207_prototype_domain_r255.py"
RESULT = ROOT / "artifacts/development/bge_m3_r207_prototype_domain_r255.json"


def test_r255_result_preserves_its_query_disjoint_split_and_rejection() -> None:
    spec = importlib.util.spec_from_file_location("r255", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = module.family_names()
    training, evaluation = module.split_rows(names)
    assert len(names) == 31
    assert len(evaluation) == 256
    assert len({label for _, label in evaluation}) == 31
    assert not ({module.normal(query) for query, _ in training} & {module.normal(query) for query, _ in evaluation})
    report = json.loads(RESULT.read_text(encoding="utf-8"))
    assert report["verdict"] == "rejected_development_family_or_oos_separation"
    assert report["constraints"]["r228_opened"] is False
