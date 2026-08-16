from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_mswc_wav2vec2_hidden_features_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_mswc_wav2vec2_hidden_features_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_normalize_wave_matches_product_contract() -> None:
    output = MODULE.normalize_wave(np.asarray([1.0, 2.0, 3.0], dtype=np.float32))
    assert float(output.mean()) == pytest.approx(0.0, abs=1e-6)
    assert float(output.var()) == pytest.approx(1.0, abs=1e-5)


def test_normalize_wave_rejects_nonfinite_audio() -> None:
    with pytest.raises(ValueError):
        MODULE.normalize_wave(np.asarray([0.0, np.nan], dtype=np.float32))
