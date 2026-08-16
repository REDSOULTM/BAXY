from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_openslr_librispeech_ctc_cascade_development.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_openslr_librispeech_ctc_cascade_development", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def evidence() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    corpus = {
        "schema": "baxy.openslr-librispeech-negative-development.v1",
        "records": [
            {"utterance_id": "strong", "relative_path": "s.flac", "sha256": "1"},
            {"utterance_id": "lexical", "relative_path": "l.flac", "sha256": "2"},
            {"utterance_id": "quiet", "relative_path": "q.flac", "sha256": "3"},
        ],
    }
    scan = {
        "schema": "baxy.openslr-librispeech-livekit-development-scan.v1",
        "corpus_manifest_sha256": "a" * 64,
        "proposal_threshold": 0.05,
        "retention_threshold": 0.02,
        "blind_human_partition_accessed": False,
        "records": [
            {"utterance_id": "strong", "relative_path": "s.flac", "wav_sha256": "1", "max_score": 0.05, "proposal": True},
            {"utterance_id": "lexical", "relative_path": "l.flac", "wav_sha256": "2", "max_score": 0.02, "proposal": False},
            {"utterance_id": "quiet", "relative_path": "q.flac", "wav_sha256": "3", "max_score": 0.01, "proposal": False},
        ],
    }
    parakeet = {
        "schema": "baxy.openslr-librispeech-parakeet-development.v1",
        "corpus_manifest_sha256": "a" * 64,
        "livekit_scan_sha256": "b" * 64,
        "blind_human_partition_accessed": False,
        "records": [
            {"utterance_id": "strong", "relative_path": "s.flac", "wav_sha256": "1", "lexical_proposals": []},
            {"utterance_id": "lexical", "relative_path": "l.flac", "wav_sha256": "2", "lexical_proposals": [{"surface": "baxi"}]},
        ],
    }
    return corpus, scan, parakeet


def test_join_evidence_forms_frozen_stage1_union() -> None:
    corpus, scan, parakeet = evidence()

    joined = MODULE.join_evidence(
        corpus,
        scan,
        parakeet,
        corpus_sha256="a" * 64,
        scan_sha256="b" * 64,
        livekit_proposal_threshold=0.05,
        lexical_corroboration_threshold=0.02,
    )

    assert [record["stage1_proposed"] for record in joined] == [True, True, False]
    assert [record["lexical_corroboration"] for record in joined] == [False, True, False]


def test_join_evidence_rejects_changed_frozen_threshold() -> None:
    corpus, scan, parakeet = evidence()

    with pytest.raises(ValueError, match="proposal_threshold_mismatch"):
        MODULE.join_evidence(
            corpus,
            scan,
            parakeet,
            corpus_sha256="a" * 64,
            scan_sha256="b" * 64,
            livekit_proposal_threshold=0.06,
            lexical_corroboration_threshold=0.02,
        )
