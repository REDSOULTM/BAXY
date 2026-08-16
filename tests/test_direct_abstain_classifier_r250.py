from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "artifacts/development/direct_abstain_classifier_r250.json"


def test_r250_publishes_its_gpu_rejection_without_opening_blind_holdouts() -> None:
    report = json.loads(RESULT.read_text(encoding="utf-8"))
    assert report["verdict"] == "rejected_development_family_or_oos_separation"
    assert report["candidate"]["device"] == "cuda_bf16"
    assert report["observed"]["inside_family_mismatches"] == 256
    assert report["observed"]["outside_zero_candidates"] == 4
    assert report["constraints"]["r228_opened"] is False
    assert report["constraints"]["opened_v9"] is False
