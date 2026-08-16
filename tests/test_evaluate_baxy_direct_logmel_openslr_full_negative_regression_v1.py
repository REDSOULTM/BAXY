from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_direct_logmel_openslr_full_negative_regression_v1.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("_direct_openslr_v1", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stream_audio_matches_runtime_left_and_right_context() -> None:
    module = _module()
    short = module.stream_audio(np.ones(16_000, dtype=np.float32))
    assert short.shape == (48_000,)
    assert np.all(short[:16_000] == 0.0)
    assert np.all(short[16_000:32_000] == 1.0)
    assert np.all(short[32_000:] == 0.0)

    long = module.stream_audio(np.ones(48_000, dtype=np.float32))
    assert long.shape == (80_000,)
    assert len(module.window_views(long, 4_000)) == 9


@pytest.mark.parametrize("hop", [0, 48_001])
def test_window_views_rejects_an_invalid_hop(hop: int) -> None:
    module = _module()
    with pytest.raises(ValueError, match="direct_logmel_openslr_hop_invalid"):
        module.window_views(np.zeros(48_000, dtype=np.float32), hop)


def test_stream_audio_rejects_empty_or_nonfinite_audio() -> None:
    module = _module()
    with pytest.raises(ValueError, match="direct_logmel_openslr_audio_invalid"):
        module.stream_audio(np.empty(0, dtype=np.float32))
    with pytest.raises(ValueError, match="direct_logmel_openslr_audio_invalid"):
        module.stream_audio(np.asarray([np.nan], dtype=np.float32))
