from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_openslr_librispeech_retained_parakeet.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_openslr_librispeech_retained_parakeet", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_selected_records_obeys_frozen_scan_floor() -> None:
    corpus = {
        "schema": "baxy.openslr-librispeech-negative-development.v1",
        "records": [
            {"utterance_id": "a", "relative_path": "a.flac"},
            {"utterance_id": "b", "relative_path": "b.flac"},
        ],
    }
    scan = {
        "schema": "baxy.openslr-librispeech-livekit-development-scan.v1",
        "corpus_manifest_sha256": "a" * 64,
        "blind_human_partition_accessed": False,
        "retention_threshold": 0.02,
        "records": [
            {"utterance_id": "a", "relative_path": "a.flac", "max_score": 0.02},
            {"utterance_id": "b", "relative_path": "b.flac", "max_score": 0.019},
        ],
    }

    selected = MODULE.selected_records(
        corpus, scan, corpus_manifest_sha256="a" * 64
    )

    assert [item["source"]["utterance_id"] for item in selected] == ["a"]


def test_selected_records_rejects_scan_hash_mismatch() -> None:
    with pytest.raises(ValueError, match="openslr_parakeet_corpus_hash_mismatch"):
        MODULE.selected_records(
            {
                "schema": "baxy.openslr-librispeech-negative-development.v1",
                "records": [],
            },
            {
                "schema": "baxy.openslr-librispeech-livekit-development-scan.v1",
                "corpus_manifest_sha256": "b" * 64,
            },
            corpus_manifest_sha256="a" * 64,
        )

