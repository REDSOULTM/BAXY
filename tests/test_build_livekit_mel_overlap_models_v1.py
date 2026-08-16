from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_livekit_mel_overlap_models_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_livekit_mel_overlap_models_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_runtime_ends_preserve_initial_frame_quantization_and_steady_hop() -> None:
    ends = MODULE.runtime_ends(30 * 16_000)

    assert ends[0] == 32_256
    assert ends[1] - ends[0] == 1_024
    assert ends[2] - ends[1] == 2_560
    assert set(b - a for a, b in zip(ends[1:-1], ends[2:], strict=True)) == {
        2_560
    }
