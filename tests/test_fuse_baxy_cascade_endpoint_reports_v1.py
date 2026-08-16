from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "experiments" / "voice_latency" / "fuse_baxy_cascade_endpoint_reports_v1.py"
)
SPEC = importlib.util.spec_from_file_location("fuse_wake_reports", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _group(hits: tuple[bool, ...], field: str) -> dict:
    return {
        "records": [
            {"record": index, "audioSha256": str(index) * 64, field: hit}
            for index, hit in enumerate(hits)
        ]
    }


def test_fusion_reports_union_and_intersection() -> None:
    result = MODULE.fuse_group(
        _group((True, False, True), "accepted"),
        _group((False, True, True), "hit"),
    )

    assert result["policies"]["cascadeOrEndpoint"]["hits"] == 3
    assert result["policies"]["cascadeAndEndpoint"]["hits"] == 1


def test_fusion_rejects_identity_mismatch() -> None:
    endpoint = _group((True,), "hit")
    endpoint["records"][0]["audioSha256"] = "x" * 64

    with pytest.raises(ValueError, match="wake_fusion_record_identity_mismatch"):
        MODULE.fuse_group(_group((True,), "accepted"), endpoint)
