from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "voice_latency" / "evaluate_baxy_direct_logmel_lexical_raw_v1.py"
SPEC = importlib.util.spec_from_file_location("evaluate_direct_logmel_lexical", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_stream_windows_cover_short_and_tail_audio() -> None:
    short = MODULE.stream_windows(np.ones(8_000, np.float32), 4_000)
    long = MODULE.stream_windows(np.ones(60_001, np.float32), 4_000)

    assert len(short) == 1
    assert all(window.shape == (48_000,) for window in long)
    assert np.all(long[-1][-16_000:] == 0.0)


@pytest.mark.parametrize("hop", [0, 48_001])
def test_stream_windows_reject_invalid_hop(hop: int) -> None:
    with pytest.raises(ValueError, match="direct_logmel_window_invalid"):
        MODULE.stream_windows(np.ones(100, np.float32), hop)


def test_summarize_counts_boolean_policy() -> None:
    result = MODULE.summarize([{"hit": True}, {"hit": False}], "hit")

    assert result == {"hits": 1, "files": 2, "rate": 0.5}
