from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_livekit_negative_ctc_cascade_development.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_livekit_negative_ctc_cascade_development", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_validate_parakeet_audit_is_hash_and_scope_bound(tmp_path: Path) -> None:
    paths = [tmp_path / "clip_000001_r0.wav"]
    audit = {
        "schema": "baxy.livekit-negative-parakeet-development.v1",
        "blind_human_partition_accessed": False,
        "independent_holdout": False,
        "feature_sha256": "a" * 64,
        "records": [{"file": paths[0].name}],
    }

    assert MODULE.validate_parakeet_audit(
        audit, feature_sha256="a" * 64, paths=paths
    )[paths[0].name]["file"] == paths[0].name
    with pytest.raises(ValueError, match="negative_cascade_feature_hash_mismatch"):
        MODULE.validate_parakeet_audit(
            audit, feature_sha256="b" * 64, paths=paths
        )


def test_validate_parakeet_audit_rejects_blind_marker(tmp_path: Path) -> None:
    with pytest.raises(
        ValueError, match="negative_cascade_blind_boundary_is_not_clean"
    ):
        MODULE.validate_parakeet_audit(
            {
                "schema": "baxy.livekit-negative-parakeet-development.v1",
                "blind_human_partition_accessed": True,
            },
            feature_sha256="a" * 64,
            paths=[tmp_path / "clip_000001_r0.wav"],
        )

