from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_bge_m3_r207_prototype_domain_r254.py"


def test_r254_seals_query_disjoint_r207_prototypes_and_clinc_roles() -> None:
    spec = importlib.util.spec_from_file_location("r254", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert report["selection"]["families_required"] == 31
    assert report["development_evaluation"]["outside"] == "CLINC oos_val only (100 rows)"
    assert report["constraints"]["r228_opened"] is False
