from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest


def _module():
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "combine_controlled_raw_runtime_logmel_v1.py"
    )
    spec = importlib.util.spec_from_file_location("combine_controlled_raw", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _store(root: Path, records: list[tuple[str, int, str, float]]) -> Path:
    root.mkdir()
    features = np.concatenate(
        [np.full((300, 80), score, dtype=np.float16) for *_, score in records]
    )
    np.save(root / "features.npy", features)
    np.save(root / "offsets.npy", np.arange(len(records) + 1) * 300)
    manifest = {
        "schema": "baxy.controlled-raw-runtime-logmel.v1",
        "sources": {"physical_manifest_sha256": root.name},
        "contract": {
            "role": "opened_development_training_only",
            "sample_rate": 16000,
            "mel_bins": 80,
            "runtime_window_samples": 48000,
            "side_padding_samples": 16000,
            "hop_samples": 4000,
            "filenames_or_transcripts_retained": False,
            "positive_window_selection": "all_runtime_windows",
        },
        "files": {
            "logmel": "features.npy",
            "logmel_sha256": _sha(root / "features.npy"),
            "offsets": "offsets.npy",
            "offsets_sha256": _sha(root / "offsets.npy"),
        },
        "records": [
            {
                "label": label,
                "persona_id": f"persona-{audio_hash}",
                "record_id": f"record-{audio_hash}",
                "source_audio_sha256": f"source-{audio_hash}",
                "audio_sha256": audio_hash,
                "runtime_window_index": window,
                "feature_start": index * 300,
                "feature_end": (index + 1) * 300,
                "feature_frames": 300,
            }
            for index, (audio_hash, window, label, _) in enumerate(records)
        ],
        "runtime_seconds": 1.0,
        "human_development_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "development_only": True,
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_combine_preserves_both_labels_and_deduplicates_windows(tmp_path: Path) -> None:
    module = _module()
    first = _store(
        tmp_path / "first",
        [("a", 0, "positive", 1.0), ("b", 1, "adversarial_negative", 2.0)],
    )
    second = _store(
        tmp_path / "second",
        [("a", 0, "positive", 9.0), ("c", 2, "positive", 3.0)],
    )

    report = module.combine([first, second], tmp_path / "combined")

    assert report["counts"] == {
        "positive": 2,
        "adversarial_negative": 1,
        "source_records": 3,
        "records": 3,
        "frames": 900,
    }
    values = np.load(tmp_path / "combined" / "logmel.f16.npy")
    assert values[:, 0].reshape(3, 300)[:, 0].tolist() == [1.0, 2.0, 3.0]
    assert len({record["record_id"] for record in report["records"]}) == 3
    assert {record["source_record_id"] for record in report["records"]} == {
        "record-a",
        "record-b",
        "record-c",
    }


def test_combine_rejects_conflicting_labels_for_same_window(tmp_path: Path) -> None:
    module = _module()
    first = _store(tmp_path / "first", [("a", 0, "positive", 1.0)])
    second = _store(
        tmp_path / "second", [("a", 0, "adversarial_negative", 2.0)]
    )

    with pytest.raises(ValueError, match="label_conflict"):
        module.combine([first, second], tmp_path / "combined")
