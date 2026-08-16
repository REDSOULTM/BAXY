from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/attest_windows_agent_arena_office_source_r258.py"
RESULT = ROOT / "artifacts/audit/windows_agent_arena_office_source_r258.json"


def test_r258_rejects_writer_tasks_without_inventing_word_operation_labels() -> None:
    spec = importlib.util.spec_from_file_location("r258", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert report["verdict"] == "rejected_preexecution_application_and_operation_semantic_mismatch"
    assert report["source"]["license"] == "MIT"
    assert report["source"]["task_files"] == 19
    assert report["admission"]["observed_task_snapshot"] == "libreoffice_writer"
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["r228_opened"] is False


def test_r258_result_keeps_the_external_source_without_admitting_labels() -> None:
    report = json.loads(RESULT.read_text(encoding="utf-8"))
    assert report["verdict"] == "rejected_preexecution_application_and_operation_semantic_mismatch"
    assert report["source"]["commit"] == "6d39ed88c545a0d40a7a02e39b928e278df7332b"
    assert report["source"]["task_files"] == 19
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["model_started"] is False
