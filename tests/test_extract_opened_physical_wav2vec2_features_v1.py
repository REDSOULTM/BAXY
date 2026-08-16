from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments"
    / "wake_validation"
    / "extract_opened_physical_wav2vec2_features_v1.py"
)
SPEC = importlib.util.spec_from_file_location("opened_wav2vec2", PROGRAM)
assert SPEC is not None and SPEC.loader is not None
EXTRACTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXTRACTOR)


def test_feature_offsets_are_monotonic_and_exact() -> None:
    offsets = EXTRACTOR.feature_offsets([4, 7, 2])

    assert offsets.dtype == np.int64
    assert offsets.tolist() == [0, 4, 11, 13]


@pytest.mark.parametrize("lengths", [[], [0], [True], [3, -1]])
def test_feature_offsets_reject_invalid_lengths(lengths: list[int]) -> None:
    with pytest.raises(ValueError, match="frame_lengths_invalid"):
        EXTRACTOR.feature_offsets(lengths)


def test_v17_paths_are_forbidden() -> None:
    with pytest.raises(ValueError, match="physical_v17_forbidden"):
        EXTRACTOR.forbid_v17([Path("D:/sealed/physical_v17")])


def test_safe_corpus_path_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="path_escape"):
        EXTRACTOR.safe_corpus_path(tmp_path, "../escape.wav")
