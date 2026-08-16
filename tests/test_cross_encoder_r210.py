from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_r210_rejects_r209_for_exactness_and_oos() -> None:
    spec = importlib.util.spec_from_file_location("r210", ROOT / "experiments/mind_router_spike/audit_cross_encoder_r210.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    audit = module.build()
    assert audit["verdict"] == "reject_candidate"
    assert audit["reason"]["exact_measured"] == 16
    assert audit["reason"]["oos_zero_candidates_measured"] == 5
    assert audit["constraints"]["runtime_modified"] is False
