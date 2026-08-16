from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np


def _module():
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "combine_baxy_wake_hard_negative_logmel_v1.py"
    )
    spec = importlib.util.spec_from_file_location("combine_wake_hard", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _store(root: Path, records: list[tuple[str, int, float]]) -> Path:
    root.mkdir()
    values = np.concatenate(
        [np.full((300, 80), score, dtype=np.float16) for _, _, score in records]
    )
    np.save(root / "features.npy", values)
    np.save(root / "offsets.npy", np.arange(len(records) + 1) * 300)
    manifest = {
        "schema": "baxy.openslr-wake-hard-negative-logmel.v1",
        "contract": {"hop_samples": 4000, "frames": 300, "mel_bins": 80},
        "files": {
            "logmel": "features.npy",
            "logmel_sha256": _sha(root / "features.npy"),
            "offsets": "offsets.npy",
            "offsets_sha256": _sha(root / "offsets.npy"),
        },
        "records": [
            {
                "label": "adversarial_negative",
                "persona_id": f"speaker-{audio_hash}",
                "audio_sha256": audio_hash,
                "window_index": window,
                "feature_start": index * 300,
                "feature_end": (index + 1) * 300,
                "feature_frames": 300,
            }
            for index, (audio_hash, window, _) in enumerate(records)
        ],
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_combine_keeps_a_stable_unique_audio_window_union(tmp_path: Path) -> None:
    module = _module()
    first = _store(tmp_path / "first", [("a", 1, 1.0), ("b", 2, 2.0)])
    second = _store(tmp_path / "second", [("a", 1, 9.0), ("a", 3, 3.0)])
    output = tmp_path / "combined"

    report = module.combine([first, second], output)

    assert report["counts"] == {"source_records": 2, "records": 3, "frames": 900}
    values = np.load(output / "logmel.f16.npy")
    assert values[:, 0].reshape(3, 300)[:, 0].tolist() == [1.0, 2.0, 3.0]


def test_combine_propagates_controlled_human_provenance(tmp_path: Path) -> None:
    module = _module()
    first = _store(tmp_path / "first", [("a", 1, 1.0)])
    second = _store(tmp_path / "second", [("b", 2, 2.0)])
    payload = json.loads(second.read_text(encoding="utf-8"))
    payload["schema"] = module.CONTROLLED_SCHEMA
    payload["human_development_audio_accessed"] = True
    second.write_text(json.dumps(payload), encoding="utf-8")

    report = module.combine([first, second], tmp_path / "combined")

    assert report["schema"] == module.CONTROLLED_SCHEMA
    assert report["human_development_audio_accessed"] is True
