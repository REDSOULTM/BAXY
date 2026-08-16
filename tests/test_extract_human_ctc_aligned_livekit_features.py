from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_human_ctc_aligned_livekit_features.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_human_ctc_aligned_livekit_features", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_containment_requires_full_target_inside_two_second_window() -> None:
    assert MODULE.contains_target(
        2.0, target_start_seconds=1.2, target_end_seconds=1.5
    )
    assert not MODULE.contains_target(
        1.4, target_start_seconds=1.2, target_end_seconds=1.5
    )
    assert not MODULE.contains_target(
        3.25, target_start_seconds=1.2, target_end_seconds=1.5
    )
    assert MODULE.contains_target(
        1.5, target_start_seconds=-0.5, target_end_seconds=1.5
    )


def test_containment_rejects_invalid_teacher_span() -> None:
    with pytest.raises(ValueError, match="alignment_invalid"):
        MODULE.contains_target(
            2.0, target_start_seconds=1.5, target_end_seconds=1.2
        )
