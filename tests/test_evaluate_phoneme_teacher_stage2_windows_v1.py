from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_phoneme_teacher_stage2_windows_v1.py"
)
SPEC = importlib.util.spec_from_file_location("stage2_windows", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_proposal_window_matches_livekit_padding_contract() -> None:
    audio = np.arange(48_000, dtype=np.float32)
    window = MODULE.proposal_window(
        audio, proposal_end_seconds=1.0, postroll_seconds=0.0
    )
    assert window.shape == (32_000,)
    np.testing.assert_array_equal(window[:16_000], np.zeros(16_000, np.float32))
    np.testing.assert_array_equal(window[16_000:], audio[:16_000])


def test_proposal_window_postroll_is_causal() -> None:
    audio = np.arange(48_000, dtype=np.float32)
    window = MODULE.proposal_window(
        audio, proposal_end_seconds=1.0, postroll_seconds=0.5
    )
    np.testing.assert_array_equal(window[:8_000], np.zeros(8_000, np.float32))
    np.testing.assert_array_equal(window[8_000:], audio[:24_000])


def test_parse_postrolls_rejects_negative_values() -> None:
    with pytest.raises(Exception):
        MODULE.parse_postrolls("0,-.25")


def test_stage1_proposal_prefers_broad_threshold_hit() -> None:
    broad = {"window_end_seconds": 0.75}
    primary = {"window_end_seconds": 1.5}
    proposal, source = MODULE.stage1_proposal(
        {
            "lexical_acoustic_corroboration": broad,
            "livekit_proposal": primary,
        }
    )
    assert proposal is broad
    assert source == "livekit_broad_threshold"
