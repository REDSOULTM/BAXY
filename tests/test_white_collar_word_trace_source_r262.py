from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/attest_white_collar_word_trace_source_r262.py"
RESULT = ROOT / "artifacts/audit/white_collar_word_trace_source_r262.json"


def test_r262_rejects_technical_word_traces_without_requests_or_lifecycle_coverage() -> None:
    spec = importlib.util.spec_from_file_location("r262", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert (
        report["verdict"]
        == "rejected_preexecution_technical_trace_without_request_or_full_lifecycle_coverage"
    )
    assert report["source"]["license"] == "MIT"
    assert report["source"]["published_machine_plan_files"] == 5
    assert report["source"]["machine_plan_request_fields"] == []
    assert report["observed_surface"]["word_execution_backend"] == (
        "Microsoft Word COM finite semantic adapter"
    )
    assert report["observed_surface"]["word_com_close_operation_present"] is False
    assert report["observed_surface"]["word_com_discard_operation_present"] is False
    assert report["observed_surface"]["real_word_witnesses"]["save_asserts_document_saved"] is True
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["r228_opened"] is False


def test_r262_result_keeps_the_external_trace_without_inventing_requests() -> None:
    report = json.loads(RESULT.read_text(encoding="utf-8"))
    assert (
        report["verdict"]
        == "rejected_preexecution_technical_trace_without_request_or_full_lifecycle_coverage"
    )
    assert report["source"]["commit"] == "6c1c9056e800bc357eb07bfc66963c6462b927a4"
    assert report["source"]["machine_plan_request_fields"] == []
    assert report["observed_surface"]["real_word_matrix_case_rows"] == 72
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["model_started"] is False
