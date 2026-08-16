from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_baxy_hyperspotter_physical_logmel_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_baxy_hyperspotter_physical_logmel_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def source_manifest(label: str, audio_hash: str) -> dict[str, object]:
    return {
        "schema": "baxy.voxcpm2-ipa-filtered-wake-corpus.v1",
        "class_label": label,
        "records": [
            {
                "class_label": label,
                "persona_id": f"{label}_voice",
                "phrase_id": f"{label}_phrase",
                "wav": {
                    "sample_rate": 16000,
                    "channels": 1,
                    "sha256": audio_hash,
                },
            }
        ],
    }


def physical_manifest() -> dict[str, object]:
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
                "output": "positive/clip.wav",
                "outputSha256": "c" * 64,
                "capturedSnrDb": 18.0,
            },
            {
                "recordId": "negative/000000",
                "sourceSha256": "b" * 64,
                "output": "negative/clip.wav",
                "outputSha256": "d" * 64,
                "capturedSnrDb": 17.0,
            },
        ],
    }


def test_physical_records_join_source_metadata_without_transcript() -> None:
    metadata = MODULE.source_metadata(
        source_manifest("positive", "a" * 64),
        source_manifest("adversarial_negative", "b" * 64),
    )
    records = MODULE.physical_records(physical_manifest(), metadata)
    assert [record["label"] for record in records] == [
        "positive",
        "adversarial_negative",
    ]
    assert records[0]["persona_id"] == "positive_voice"
    assert records[0]["audio_sha256"] == "c" * 64
    assert "phrase_text" not in records[0]


def test_physical_records_reject_unmapped_source_hash() -> None:
    metadata = MODULE.source_metadata(
        source_manifest("positive", "a" * 64),
        source_manifest("adversarial_negative", "e" * 64),
    )
    with pytest.raises(ValueError, match="source_hash_unmapped"):
        MODULE.physical_records(physical_manifest(), metadata)


def test_physical_records_reject_non_raw_capture() -> None:
    manifest = physical_manifest()
    manifest["physicalPath"]["captureTransport"] = "wavein"
    with pytest.raises(ValueError, match="capture_boundary_invalid"):
        MODULE.physical_records(manifest, {})
