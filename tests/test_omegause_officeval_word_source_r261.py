from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "experiments/mind_router_spike/attest_omegause_officeval_word_source_r261.py"
)
RESULT = ROOT / "artifacts/audit/omegause_officeval_word_source_r261.json"


def test_r261_rejects_final_artifact_tasks_without_word_lifecycle_labels() -> None:
    spec = importlib.util.spec_from_file_location("r261", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert (
        report["verdict"]
        == "rejected_preexecution_final_artifact_only_lifecycle_mismatch"
    )
    assert report["source"]["license"] == "Apache-2.0"
    assert report["source"]["merged_english_task_rows"] == 100
    assert (
        report["observed_surface"]["evaluation_target"]
        == "final delivered artifact, not execution trajectory"
    )
    assert report["observed_surface"]["evaluation_observes_saved_dirty_state"] is False
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["r228_opened"] is False


def test_r261_result_keeps_the_external_source_without_admitting_labels() -> None:
    report = json.loads(RESULT.read_text(encoding="utf-8"))
    assert (
        report["verdict"]
        == "rejected_preexecution_final_artifact_only_lifecycle_mismatch"
    )
    assert report["source"]["commit"] == "cd6ba6d8fb83b3fb551e24eebc20e1fb0bd154a5"
    assert report["source"]["merged_english_task_rows"] == 100
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["model_started"] is False
