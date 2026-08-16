from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "artifacts/development/bge_reranker_r241_development.json"


def test_r241_publishes_the_gpu_rejection_without_opening_r228() -> None:
    report = json.loads(RESULT.read_text(encoding="utf-8"))
    assert report["verdict"] == "rejected_development_oos_separation"
    assert report["candidate"]["device"] == "cuda"
    assert report["observed"]["inside_rows_lost"] == 0
    assert report["observed"]["outside_zero_candidates"] == 2
    assert report["constraints"]["r228_opened"] is False
    assert report["constraints"]["opened_v9"] is False
