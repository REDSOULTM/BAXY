from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_baxy_hyperspotter_human_logmel_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_baxy_hyperspotter_human_logmel_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def source_manifest() -> dict[str, object]:
    records = []
    for corpus, count in (("human_legacy", 18), ("human_expanded", 12)):
        for index in range(count):
            records.append(
                {
                    "corpus": corpus,
                    "label": "positive" if index % 2 else "negative",
                    "group": f"group_{index % 3}",
                    "relative_path": f"clip_{index}.wav",
                    "audio_sha256": "a" * 64,
                }
            )
    return {
        "schema": "baxy.wav2vec2-hidden-wake-training-features.v1",
        "blind_human_audio_accessed": False,
        "records": records,
    }


def test_human_records_preserve_partition_boundary() -> None:
    records = MODULE.human_records(source_manifest())
    assert len(records) == 30
    assert sum(record["corpus"] == "human_legacy" for record in records) == 18
    assert sum(record["corpus"] == "human_expanded" for record in records) == 12


def test_human_records_reject_blind_access_marker() -> None:
    manifest = source_manifest()
    manifest["blind_human_audio_accessed"] = True
    with pytest.raises(ValueError, match="manifest_boundary_invalid"):
        MODULE.human_records(manifest)
