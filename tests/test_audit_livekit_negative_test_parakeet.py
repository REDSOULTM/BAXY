from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_livekit_negative_test_parakeet.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_livekit_negative_test_parakeet", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_augmented_wavs_excludes_clean_sources(tmp_path: Path) -> None:
    (tmp_path / "clip_000001.wav").write_bytes(b"clean")
    (tmp_path / "clip_000001_r0.wav").write_bytes(b"augmented")
    (tmp_path / "other.wav").write_bytes(b"other")

    assert [path.name for path in MODULE.augmented_wavs(tmp_path)] == [
        "clip_000001_r0.wav"
    ]


def test_checkpoint_is_bound_to_feature_and_wav_set(tmp_path: Path) -> None:
    checkpoint = tmp_path / "audit.partial.json"
    paths = [tmp_path / "clip_000001_r0.wav"]
    MODULE.write_checkpoint(
        checkpoint,
        feature_sha256="a" * 64,
        ordered_wav_set_sha256="b" * 64,
        records=[{"file": paths[0].name}],
    )

    assert MODULE.load_checkpoint(
        checkpoint,
        feature_sha256="a" * 64,
        ordered_wav_set_sha256="b" * 64,
        paths=paths,
    ) == [{"file": paths[0].name}]
    with pytest.raises(
        ValueError, match="negative_parakeet_checkpoint_feature_mismatch"
    ):
        MODULE.load_checkpoint(
            checkpoint,
            feature_sha256="c" * 64,
            ordered_wav_set_sha256="b" * 64,
            paths=paths,
        )

