from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/attest_bge_m3_acquisition_r232.py"


def _module():
    spec = importlib.util.spec_from_file_location("r232", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r232_attests_files_without_importing_candidate_model() -> None:
    report = _module().build()
    assert report["candidate"]["file_count"] > 0
    assert report["candidate"]["total_bytes"] > 1_000_000_000
    assert len(report["candidate"]["content_merkle_sha256"]) == 64
    assert report["constraints"]["model_imported"] is False
    assert report["constraints"]["registered_runtime_modified"] is False


def test_r232_published_attestation_matches_builder() -> None:
    module = _module()
    output = ROOT / "artifacts/audit/bge_m3_acquisition_r232.json"
    assert json.loads(output.read_text(encoding="utf-8")) == module.build()
