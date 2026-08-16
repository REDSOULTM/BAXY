from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "merge_controlled_physical_wake_features_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_merge_physical", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_merge_arrays_preserves_source_order(tmp_path: Path) -> None:
    gate = _module()
    first = tmp_path / "first.npy"
    second = tmp_path / "second.npy"
    np.save(first, np.full((2, 16, 96), 1.0, dtype=np.float32))
    np.save(second, np.full((3, 16, 96), 2.0, dtype=np.float32))

    merged = gate.merge_arrays([first, second])

    assert merged.shape == (5, 16, 96)
    assert np.all(merged[:2] == 1.0)
    assert np.all(merged[2:] == 2.0)
