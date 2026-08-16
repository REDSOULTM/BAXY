from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_wake_verifier_expanded_development_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_wake_verifier_expanded_development_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_select_records_accepts_only_exact_development_contract() -> None:
    records = [
        {"partition": "development", "label": "positive", "id": index}
        for index in range(4)
    ] + [
        {"partition": "development", "label": "matched_negative", "id": index}
        for index in range(8)
    ]
    corpus = {
        "schema": "baxy.ccby-wake-v5-development-corpus.v1",
        "scope": "development_only",
        "blind_human_audio_accessed": False,
        "records": records,
    }
    assert MODULE.select_records(corpus) == records


def test_summarize_keeps_false_accepts_explicit() -> None:
    records = [
        {"label": "positive", "detected": True},
        {"label": "positive", "detected": False},
        {"label": "matched_negative", "detected": True},
        {"label": "matched_negative", "detected": False},
    ]
    metrics = MODULE.summarize(records)
    assert metrics["positive_accepted"] == 1
    assert metrics["matched_negative_false_accepts"] == 1
    assert metrics["development_gate_passed"] is False
