from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/attest_windowsworld_word_source_r268.py"
RESULT = ROOT / "artifacts/audit/windowsworld_word_source_r268.json"


def _module():
    spec = importlib.util.spec_from_file_location("r268", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r268_rejects_windowsworld_before_model_or_relabelling() -> None:
    report = _module().build()

    assert report["verdict"] == (
        "rejected_preexecution_non_com_multistep_and_language_coverage_mismatch"
    )
    assert report["source"]["license"] == "Apache-2.0"
    assert report["source"]["published_task_rows"] == 181
    assert report["source"]["published_word_task_rows"] == 40
    assert report["source"]["published_spanish_instruction_rows"] == 0
    assert report["source"]["published_spanglish_instruction_rows"] == 0
    assert report["observed_surface"]["word_task_lifecycle_keyword_rows"][
        "office.word.close"
    ] == 0
    assert report["observed_surface"]["word_task_lifecycle_keyword_rows"][
        "office.word.discard"
    ] == 0
    assert report["observed_surface"]["word_task_lifecycle_keyword_rows"][
        "office.word.status"
    ] == 0
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["model_started"] is False


def test_r268_published_receipt_keeps_the_rejection_boundary() -> None:
    report = json.loads(RESULT.read_text(encoding="utf-8"))

    assert report["source"]["commit"] == "fbccd464f94fec9e284e139f97bf96d0b192f580"
    assert report["observed_surface"]["native_microsoft_word_com_tokens_present"] is False
    assert report["observed_surface"]["word_process_checkpoint_mentions"] is True
    assert report["observed_surface"]["evaluation_has_native_word_saved_dirty_verifier"] is False
    assert report["observed_surface"]["evaluation_binds_discard_to_confirmation"] is False
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["effects_executed"] == 0


def test_r268_source_does_not_load_baxy_model_or_runtime() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    for forbidden in ("LlmRuntime", "resolve_runtime", "discover_core", "turn.decide"):
        assert forbidden not in source
