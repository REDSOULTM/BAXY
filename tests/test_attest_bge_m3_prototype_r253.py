from __future__ import annotations

import importlib.util
from pathlib import Path

from local_evidence import require_runtime_turn_evidence


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/attest_bge_m3_prototype_r253.py"


def test_r253_rejects_incomplete_fresh_family_coverage_before_model_import() -> None:
    # The R243 population this attestation counts is drawn from the private
    # runtime corpus.
    require_runtime_turn_evidence(ROOT)
    spec = importlib.util.spec_from_file_location("r253_attest", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert report["verdict"] == "rejected_preexecution_insufficient_fresh_inside_family_coverage"
    assert report["observed"]["available_families"] < report["observed"]["required_families"]
    assert report["constraints"]["model_started"] is False
