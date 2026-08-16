from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_mdtc_ctc_fbank_features.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_mdtc_ctc_fbank_features", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_extract_fbank_has_fixed_product_shape() -> None:
    features = MODULE.extract_fbank(np.zeros(MODULE.WINDOW_SAMPLES, np.float32))

    assert features.shape == (MODULE.FEATURE_FRAMES, MODULE.FEATURE_DIMENSION)
    assert np.isfinite(features).all()


def test_extract_fbank_rejects_non_product_window() -> None:
    with pytest.raises(ValueError, match="audio_window_invalid"):
        MODULE.extract_fbank(np.zeros(100, np.float32))
