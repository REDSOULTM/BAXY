from __future__ import annotations

import importlib.util
from pathlib import Path
import wave

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_mdtc_hard_negative_livekit_features.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_mdtc_hard_negative_livekit_features", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_records_by_split_preserves_manifest_order() -> None:
    manifest = {
        "records": [
            {"split": "train", "id": 1},
            {"split": "development", "id": 2},
            {"split": "train", "id": 3},
        ]
    }

    assert [record["id"] for record in MODULE.records_by_split(manifest, "train")] == [1, 3]


def test_records_by_split_rejects_unknown_split() -> None:
    with pytest.raises(ValueError, match="split_invalid"):
        MODULE.records_by_split({"records": []}, "blind")


def test_read_window_enforces_exact_product_contract(tmp_path: Path) -> None:
    path = tmp_path / "window.wav"
    with wave.open(str(path), "wb") as destination:
        destination.setnchannels(1)
        destination.setsampwidth(2)
        destination.setframerate(16_000)
        destination.writeframes(np.zeros(32_000, dtype="<i2").tobytes())

    audio = MODULE.read_window(path)

    assert audio.shape == (32_000,)
    assert audio.dtype == np.float32
