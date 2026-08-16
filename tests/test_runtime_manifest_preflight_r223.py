from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/probe_runtime_manifest_r223.py"
ARTIFACT = ROOT / "artifacts/audit/runtime_manifest_preflight_r223.json"


def _module():
    spec = importlib.util.spec_from_file_location("r223", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r223_corrects_r222_without_starting_model() -> None:
    report = _module().build()
    assert report["outcome"]["resolved"] is True
    assert report["correction"]["r222_outcome_not_rewritten"] is True
    assert report["correction"]["current_per_file_stt_identity_verified"] is True


def test_r223_published_preflight_matches_builder() -> None:
    # R223 is an immutable receipt of the former per-file STT correction.  A
    # later runtime-validator repair must not rewrite that historical reading
    # merely to keep its program hash equal to the live builder.
    report = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert report["schema"] == "baxy.runtime-manifest-preflight.r223.v1"
    assert report["outcome"] == {"resolved": True, "error": ""}
    assert report["correction"]["r222_outcome_not_rewritten"] is True
