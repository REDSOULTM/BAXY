from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_mswc_wake_scaf_embedding_v1.py"
)
SPEC = importlib.util.spec_from_file_location("train_mswc_wake_scaf_embedding_v1", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_split_positions_is_disjoint_and_maps_classes() -> None:
    records = [
        {"class_name": "en:one", "split": "train"},
        {"class_name": "es:uno", "split": "train"},
        {"class_name": "en:one", "split": "development"},
        {"class_name": "es:uno", "split": "development"},
    ]
    training, development, labels = MODULE.split_positions(
        records, ["en:one", "es:uno"]
    )
    assert training == [0, 1]
    assert development == [2, 3]
    assert labels.tolist() == [0, 1, 0, 1]
