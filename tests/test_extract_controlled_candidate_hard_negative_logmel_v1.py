from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_controlled_candidate_hard_negative_logmel_v1.py"
)
SPEC = importlib.util.spec_from_file_location("controlled_hard_negative", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_extracts_only_candidate_triggered_negative_windows(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    features = np.arange(900 * 80, dtype=np.float16).reshape(900, 80)
    offsets = np.asarray([0, 300, 600, 900], dtype=np.int64)
    np.save(source / "logmel.f16.npy", features)
    np.save(source / "offsets.i64.npy", offsets)
    manifest = {
        "schema": "baxy.controlled-raw-runtime-logmel.v1",
        "sources": {"physical_manifest_sha256": "corpus"},
        "contract": {"hop_samples": 4000},
        "files": {
            "logmel": "logmel.f16.npy",
            "logmel_sha256": MODULE._BASE.sha256(source / "logmel.f16.npy"),
            "offsets": "offsets.i64.npy",
            "offsets_sha256": MODULE._BASE.sha256(source / "offsets.i64.npy"),
        },
        "records": [
            {"label": "positive", "persona_id": "p", "audio_sha256": "a"},
            {
                "label": "adversarial_negative",
                "persona_id": "n1",
                "audio_sha256": "b",
            },
            {
                "label": "adversarial_negative",
                "persona_id": "n2",
                "audio_sha256": "c",
            },
        ],
        "human_development_audio_accessed": True,
        "blind_human_audio_accessed": False,
        "development_only": True,
    }
    manifest_path = source / "features.manifest.v1.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    candidate = tmp_path / "candidate.json"
    candidate.write_text(
        json.dumps(
            {
                "schema": "baxy.wake-cascade-runtime-raw-development.v1",
                "corpusManifestSha256": "corpus",
                "blindHumanPartitionAccessed": False,
                "positive": {
                    "records": [
                        {"audioSha256": "a", "upstreamCandidate": True}
                    ]
                },
                "negative": {
                    "records": [
                        {"audioSha256": "b", "upstreamCandidate": True},
                        {"audioSha256": "c", "upstreamCandidate": False},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"
    report = MODULE.extract(
        source_manifest_path=manifest_path,
        candidate_report_paths=[candidate],
        output=output,
    )
    assert report["schema"] == MODULE.SCHEMA
    assert report["counts"] == {"source_records": 1, "records": 1, "frames": 300}
    assert report["human_development_audio_accessed"] is True
    assert report["records"][0]["audio_sha256"] == "b"
