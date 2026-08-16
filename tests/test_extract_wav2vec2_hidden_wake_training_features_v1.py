from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_wav2vec2_hidden_wake_training_features_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_wav2vec2_hidden_wake_training_features_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_normalize_wave_matches_product_preprocessing() -> None:
    values = MODULE.normalize_wave(np.asarray([1.0, 2.0, 4.0], np.float32))
    assert float(values.mean()) == pytest.approx(0.0, abs=1e-6)
    assert float(values.var()) == pytest.approx(1.0, abs=1e-5)


def test_normalize_wave_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="audio_invalid"):
        MODULE.normalize_wave(np.asarray([], np.float32))


def test_dataset_records_merges_expanded_known_speaker(tmp_path: Path) -> None:
    synthetic = {
        "records": [
            {
                "persona_id": "p",
                "output_file": "x.wav",
                "wav": {"sha256": "a" * 64},
            }
        ]
    }
    legacy = {"records": []}
    expanded = {
        "records": [
            {
                "partition": "development",
                "label": "positive",
                "source_id": "Axgc6aHutvw",
                "speaker_group": "uploader",
                "output_relative_path": "x.wav",
                "wav": {"sha256": "b" * 64},
            }
        ]
    }
    records = MODULE.dataset_records(
        positive_manifest=synthetic,
        negative_manifest=synthetic,
        legacy_manifest=legacy,
        expanded_manifest=expanded,
        roots={
            "synthetic_positive": tmp_path,
            "synthetic_negative": tmp_path,
            "human_legacy": tmp_path,
            "human_expanded": tmp_path,
        },
    )
    assert records[-1]["group"] == "jesus_marcos"
