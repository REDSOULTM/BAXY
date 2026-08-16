from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_ccby_wake_development_faster_whisper_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_ccby_wake_development_faster_whisper_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_select_development_records_never_selects_blind() -> None:
    development = [
        {"partition": "development", "label": "positive"} for _ in range(18)
    ]
    blind = [{"partition": "blind", "label": "positive"}]
    corpus = {
        "schema": "baxy.ccby-wake-holdout-corpus.v1",
        "blind_partition_was_not_scored": True,
        "records": development + blind,
    }

    assert MODULE.select_development_records(corpus) == development


def test_select_development_records_fails_closed_on_boundary() -> None:
    corpus = {
        "schema": "baxy.ccby-wake-holdout-corpus.v1",
        "blind_partition_was_not_scored": False,
        "records": [],
    }
    with pytest.raises(ValueError, match="development_boundary_invalid"):
        MODULE.select_development_records(corpus)


def test_summary_keeps_positive_recall_and_negative_errors_separate() -> None:
    records = [
        {"label": "positive", "exact_lexical_target": True},
        {"label": "positive", "exact_lexical_target": False},
        {"label": "hard_negative", "exact_lexical_target": False},
    ]
    metrics = MODULE.summarize(records)
    assert metrics["positive_exact_lexical_rate"] == 0.5
    assert metrics["hard_negative_exact_lexical_false"] == 0


def test_sha256_tree_is_name_and_content_bound(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "a").write_bytes(b"one")
    (second / "b").write_bytes(b"one")

    assert MODULE.sha256_tree(first) != MODULE.sha256_tree(second)
