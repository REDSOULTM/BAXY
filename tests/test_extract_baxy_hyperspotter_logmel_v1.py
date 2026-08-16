from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_baxy_hyperspotter_logmel_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_baxy_hyperspotter_logmel_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def record(label: str, index: int) -> dict[str, object]:
    return {
        "class_label": label,
        "output_file": f"clip_{index:06d}.wav",
        "persona_id": f"voice_{index % 2}",
        "phrase_id": f"phrase_{index}",
        "wav": {
            "sample_rate": 16000,
            "channels": 1,
            "sha256": "a" * 64,
        },
    }


def manifest(label: str, count: int = 2) -> dict[str, object]:
    return {
        "schema": "baxy.voxcpm2-ipa-filtered-wake-corpus.v1",
        "class_label": label,
        "records": [record(label, index) for index in range(count)],
    }


def test_selected_records_preserve_binary_and_speaker_contract() -> None:
    records = MODULE.selected_records(
        manifest("positive"), manifest("adversarial_negative")
    )
    assert [value["label"] for value in records] == [
        "positive",
        "positive",
        "adversarial_negative",
        "adversarial_negative",
    ]
    assert records[0]["persona_id"] == "voice_0"
    assert records[0]["relative_path"] == "clip_000000.wav"
    assert records[0]["audio_sha256"] == "a" * 64


def test_selected_records_reject_cross_labeled_manifest() -> None:
    bad = manifest("positive")
    bad["records"][0]["class_label"] = "adversarial_negative"
    with pytest.raises(ValueError, match="record_invalid"):
        MODULE.selected_records(bad, manifest("adversarial_negative"))
