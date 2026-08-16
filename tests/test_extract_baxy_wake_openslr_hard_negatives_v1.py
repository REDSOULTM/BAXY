from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "extract_baxy_wake_openslr_hard_negatives_v1.py"
    )
    spec = importlib.util.spec_from_file_location(
        "baxy_wake_openslr_hard_negatives", script
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_selected_records_requires_complete_unique_hash_coverage() -> None:
    module = _module()
    corpus = {
        "schema": module.CORPUS_SCHEMA,
        "records": [
            {"sha256": "a", "utterance_id": "one"},
            {"sha256": "b", "utterance_id": "two"},
        ],
    }
    report = {
        "schema": module.REPORT_SCHEMA,
        "falseActivationAudioSha256": ["b"],
    }
    assert module.selected_records(corpus, report) == [corpus["records"][1]]
    report["falseActivationAudioSha256"] = ["missing"]
    with pytest.raises(ValueError, match="hash_coverage"):
        module.selected_records(corpus, report)
