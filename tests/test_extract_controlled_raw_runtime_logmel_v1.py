from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_controlled_raw_runtime_logmel_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_controlled_raw_runtime_logmel_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def manifest() -> dict[str, object]:
    return {
        "schema": "baxy.controlled-physical-wake-corpus.v1",
        "blindHumanPartitionAccessed": False,
        "developmentOnly": True,
        "physicalPath": {"captureTransport": "wasapi_raw_iaudioclient2"},
        "counts": {"positive": 1, "negative": 1},
        "records": [
            {
                "recordId": "positive/000000",
                "sourceSha256": "a" * 64,
                "output": "positive/a.wav",
                "outputSha256": "b" * 64,
            },
            {
                "recordId": "negative/000000",
                "sourceSha256": "c" * 64,
                "output": "negative/c.wav",
                "outputSha256": "d" * 64,
            },
        ],
    }


def test_controlled_records_preserve_label_and_source_group() -> None:
    records = MODULE.controlled_records(manifest())
    assert [record["label"] for record in records] == [
        "positive",
        "adversarial_negative",
    ]
    assert records[0]["persona_id"] == "controlled_source_aaaaaaaaaaaaaaaa"


def test_controlled_records_reject_count_mismatch() -> None:
    value = manifest()
    value["counts"]["negative"] = 2
    with pytest.raises(ValueError, match="counts_invalid"):
        MODULE.controlled_records(value)


def test_human_provenance_keeps_three_variants_in_one_speaker_group() -> None:
    source = {
        "schema": "baxy.ccby-wake-holdout-corpus.v1",
        "records": [
            {
                "partition": "development",
                "label": "positive",
                "source_id": "speaker-source",
                "speaker_group": "speaker_one",
                "language": "es",
                "wav": {"sha256": "f" * 64},
            }
        ],
    }
    augmented = [
        (f"clip_{index:06d}.wav", str(index + 1) * 64)
        for index in range(3)
    ]
    provenance = MODULE.human_positive_provenance(source, augmented)
    assert len(provenance) == 3
    assert {value["persona_id"] for value in provenance.values()} == {
        "real_human_speaker_one"
    }
    assert {
        value["human_augmentation_variant"] for value in provenance.values()
    } == {0, 1, 2}


def test_controlled_records_use_real_human_speaker_not_variant_hash() -> None:
    value = manifest()
    provenance = {
        "a" * 64: {
            "persona_id": "real_human_speaker_one",
            "human_speaker_group": "speaker_one",
        }
    }
    records = MODULE.controlled_records(
        value, positive_provenance=provenance
    )
    assert records[0]["persona_id"] == "real_human_speaker_one"
    assert records[1]["persona_id"] == "controlled_source_cccccccccccccccc"


def test_positive_window_evidence_is_bound_to_exact_corpus() -> None:
    report = {
        "schema": "baxy.raw-rolling-multialias-wake-corpus-development.v2",
        "corpusManifestSha256": "a" * 64,
        "blindHumanPartitionAccessed": False,
        "positive": {
            "records": [
                {
                    "audioSha256": "b" * 64,
                    "accepted": True,
                    "firstAcceptedWindowIndex": 3,
                }
            ]
        },
    }
    assert MODULE.positive_window_evidence(
        report, corpus_manifest_sha256="a" * 64
    ) == {"b" * 64: 3}
    with pytest.raises(ValueError, match="evidence_boundary_invalid"):
        MODULE.positive_window_evidence(
            report, corpus_manifest_sha256="c" * 64
        )


def test_cascade_candidate_time_selects_the_matching_runtime_window() -> None:
    report = {
        "schema": "baxy.wake-cascade-runtime-raw-development.v1",
        "corpusManifestSha256": "a" * 64,
        "blindHumanPartitionAccessed": False,
        "positive": {
            "records": [
                {
                    "audioSha256": "b" * 64,
                    "upstreamCandidate": True,
                    "candidateAvailableAtStreamSeconds": 3.008,
                }
            ]
        },
    }
    assert MODULE.positive_window_evidence(
        report, corpus_manifest_sha256="a" * 64
    ) == {"b" * 64: 0}
