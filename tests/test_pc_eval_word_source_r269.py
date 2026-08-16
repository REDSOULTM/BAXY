from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/attest_pc_eval_word_source_r269.py"
RESULT = ROOT / "artifacts/audit/pc_eval_word_source_r269.json"


def _module():
    spec = importlib.util.spec_from_file_location("r269", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r269_rejects_instruction_only_pc_eval_before_model_or_relabelling() -> None:
    report = _module().build()

    assert report["verdict"] == (
        "rejected_preexecution_instruction_only_no_com_or_lifecycle_verifier"
    )
    assert report["source"]["license"] == "Apache-2.0"
    assert report["source"]["published_instruction_rows"] == 27
    assert report["source"]["distinct_normalized_instruction_rows"] == 26
    assert report["source"]["instruction_stream_is_json_array"] is False
    assert report["source"]["published_word_instruction_rows"] == 7
    assert report["source"]["published_spanish_instruction_rows"] == 0
    assert report["source"]["published_spanglish_instruction_rows"] == 0
    assert report["observed_surface"]["word_lifecycle_keyword_rows"] == {
        "office.word.append": 0,
        "office.word.close": 0,
        "office.word.discard": 0,
        "office.word.save": 2,
        "office.word.start": 4,
        "office.word.status": 0,
    }
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["model_started"] is False


def test_r269_published_receipt_keeps_the_no_trace_boundary() -> None:
    report = json.loads(RESULT.read_text(encoding="utf-8"))

    assert report["source"]["commit"] == "39317b7d903e5bbdf72c16069a9bbded67b31b21"
    assert report["observed_surface"]["published_execution_or_verifier_source_files"] == []
    assert report["observed_surface"]["published_microsoft_word_com_trace"] is False
    assert report["observed_surface"]["published_saved_dirty_verifier"] is False
    assert report["admission"]["admitted_baxy_operations"] == []
    assert report["constraints"]["effects_executed"] == 0


def test_r269_source_does_not_load_baxy_model_or_runtime() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    for forbidden in ("LlmRuntime", "resolve_runtime", "discover_core", "turn.decide"):
        assert forbidden not in source
