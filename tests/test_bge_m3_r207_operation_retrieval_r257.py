from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "experiments/mind_router_spike/run_bge_m3_r207_operation_retrieval_r257.py"
RESULT = ROOT / "artifacts/development/bge_m3_r207_operation_retrieval_r257.json"


def test_r257_prepares_a_query_disjoint_operation_level_population() -> None:
    spec = importlib.util.spec_from_file_location("r257", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    operations = module.catalogue_operations()
    training, evaluation, missing, excluded = module.split_rows(operations)
    assert len(operations) == 174
    assert len(evaluation) == 256
    assert len({operation for _, operation in evaluation}) == 168
    assert not ({module.normal(query) for query, _ in training} & {module.normal(query) for query, _ in evaluation})
    assert len(missing) == 6
    assert excluded == ["__no_action__", "notification.cancel.at"]


def test_r257_result_keeps_the_raw_retrieval_scope_and_coverage_limit() -> None:
    report = json.loads(RESULT.read_text(encoding="utf-8"))
    assert report["verdict"] == "development_retrieval_signal_only_catalogue_coverage_incomplete"
    assert report["development_population"]["query_disjoint"] is True
    assert report["development_population"]["operations_with_r207_exemplars"] == 168
    assert len(report["development_population"]["catalogue_operations_without_r207_exemplar"]) == 6
    assert report["observed"]["recall_top_1"] == 0.98828125
    assert report["observed"]["recall_top_2"] == 1.0
    assert report["observed"]["recall_top_5"] == 1.0
    assert report["observed"]["recall_top_8"] == 1.0
    assert report["constraints"]["r228_opened"] is False
