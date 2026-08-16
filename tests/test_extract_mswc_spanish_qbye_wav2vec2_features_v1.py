from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "extract_mswc_spanish_qbye_wav2vec2_features_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "extract_mswc_spanish_qbye_wav2vec2_features_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_layers_must_be_sorted_unique_and_nonnegative() -> None:
    assert MODULE.validate_layers([2, 16]) == [2, 16]
    for invalid in ([], [16, 2], [2, 2], [-1, 2]):
        with pytest.raises(ValueError, match="layers_invalid"):
            MODULE.validate_layers(invalid)


def test_record_path_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="relative_path_invalid"):
        MODULE.resolve_record_path(
            {
                "relative_path": "../escape.opus",
                "audio_bytes": 1,
                "audio_sha256": "0" * 64,
            },
            corpus_root=tmp_path,
        )
