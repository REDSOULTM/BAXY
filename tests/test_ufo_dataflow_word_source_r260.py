from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/attest_ufo_dataflow_word_source_r260.py"
RESULT = ROOT / "artifacts/audit/ufo_dataflow_word_source_r260.json"


def test_r260_rejects_a_wincom_harness_without_a_versioned_request_source() -> None:
    spec = importlib.util.spec_from_file_location("r260", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert (
        report["verdict"]
        == "rejected_preexecution_unversioned_input_and_forced_save_quit_semantics"
    )
    assert report["source"]["license"] == "MIT"
    assert report["source"]["versioned_task_rows"] == 0
    assert report["source"]["versioned_result_rows"] == 0
    assert (
        report["observed_surface"]["word_execution_backend"]
        == "Windows WinCOMReceiverBasic"
    )
    assert report["observed_surface"]["completion_path_forces_save_then_quit"] is True
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["r228_opened"] is False


def test_r260_result_keeps_the_external_harness_without_creating_labels() -> None:
    report = json.loads(RESULT.read_text(encoding="utf-8"))
    assert (
        report["verdict"]
        == "rejected_preexecution_unversioned_input_and_forced_save_quit_semantics"
    )
    assert report["source"]["commit"] == "96983c73ed09e884a5f1d7ff8936c953b234b684"
    assert report["source"]["versioned_task_rows"] == 0
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["model_started"] is False
