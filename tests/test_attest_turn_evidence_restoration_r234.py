from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from local_evidence import require_runtime_turn_evidence


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/attest_turn_evidence_restoration_r234.py"


def _module():
    spec = importlib.util.spec_from_file_location("r234", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r234_attests_canonical_input_without_measuring_a_model() -> None:
    require_runtime_turn_evidence(ROOT)
    report = _module().build()
    assert report["runtime_corpus"]["rows"] == 25_156
    assert report["runtime_corpus"]["sha256"] == report["sources"]["policy_runtime_source_sha256"]
    assert report["public_holdout"]["used_for_calibration"] is False
    assert report["constraints"]["model_started"] is False


def test_r234_published_attestation_matches_builder() -> None:
    require_runtime_turn_evidence(ROOT)
    module = _module()
    output = ROOT / "artifacts/audit/turn_evidence_restoration_r234.json"
    assert json.loads(output.read_text(encoding="utf-8")) == module.build()
