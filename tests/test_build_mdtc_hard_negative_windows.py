from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_mdtc_hard_negative_windows.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_mdtc_hard_negative_windows", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_development_speakers_is_deterministic_and_disjoint() -> None:
    speakers = {str(index) for index in range(10)}

    first = MODULE.development_speakers(speakers, salt="fixed", count=3)
    second = MODULE.development_speakers(speakers, salt="fixed", count=3)

    assert first == second
    assert len(first) == 3
    assert set(first) < speakers


def test_extract_window_reproduces_leading_zero_product_padding() -> None:
    audio = np.arange(8000, dtype=np.float32)

    window = MODULE.extract_window(audio, 0.5)

    assert window.shape == (32000,)
    assert np.count_nonzero(window[:24000]) == 0
    np.testing.assert_array_equal(window[24000:], audio)


def test_extract_window_rejects_negative_timeline() -> None:
    with pytest.raises(ValueError, match="audio_invalid"):
        MODULE.extract_window(np.ones(10, np.float32), -0.1)
