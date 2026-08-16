from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "diagnose_baxy_contextual_false_activations_v1.py"
)
SPEC = importlib.util.spec_from_file_location("baxy_contextual_diagnostic", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_summarize_transcripts_counts_only_accepted_normalized_values() -> None:
    result = MODULE.summarize_transcripts(
        ["  BAXI ", "ordinary text", "baxi"], [True, False, True]
    )
    assert result == {
        "decodedCaptures": 3,
        "lexicalEvidenceCaptures": 2,
        "distinctDecodedTranscripts": 2,
        "distinctLexicalEvidenceTranscripts": 1,
        "lexicalEvidenceTranscriptCounts": {"baxi": 2},
    }


def test_summarize_transcripts_rejects_misalignment() -> None:
    with pytest.raises(
        ValueError, match="baxy_contextual_diagnostic_alignment_invalid"
    ):
        MODULE.summarize_transcripts(["baxi"], [])
