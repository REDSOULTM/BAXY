from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/attest_officebench_word_source_r259.py"
RESULT = ROOT / "artifacts/audit/officebench_word_source_r259.json"


def test_r259_rejects_file_oriented_word_tasks_without_inventing_operation_labels() -> (
    None
):
    spec = importlib.util.spec_from_file_location("r259", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert (
        report["verdict"]
        == "rejected_preexecution_file_backend_and_state_verification_mismatch"
    )
    assert report["source"]["license"] == "Apache-2.0"
    assert report["source"]["task_files"] == 300
    assert (
        report["observed_surface"]["document_backend"]
        == "python-docx Document file manipulation"
    )
    assert report["observed_surface"]["microsoft_word_com_identifiers_present"] is False
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["r228_opened"] is False


def test_r259_result_keeps_the_external_source_without_admitting_labels() -> None:
    report = json.loads(RESULT.read_text(encoding="utf-8"))
    assert (
        report["verdict"]
        == "rejected_preexecution_file_backend_and_state_verification_mismatch"
    )
    assert report["source"]["commit"] == "b978b808667c32b52ce19a67ce1def1de9ae02b7"
    assert report["source"]["task_files"] == 300
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["model_started"] is False
