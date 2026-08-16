from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_mswc_spanish_qbye_sequence_features_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_mswc_spanish_qbye_sequence_features_v3", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_collapse_ctc_path_removes_blanks_and_repeated_frames() -> None:
    values = np.asarray([0, 4, 4, 0, 4, 7, 7, 0, 7], dtype=np.int64)
    assert MODULE.collapse_ctc_path(values, blank_id=0) == [4, 4, 7, 7]
