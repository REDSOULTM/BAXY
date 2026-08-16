from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_r208_preregistration_freezes_binary_all_operation_abstention() -> None:
    spec = importlib.util.spec_from_file_location("r208", ROOT / "experiments/mind_router_spike/preregister_cross_encoder_r208.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build(ROOT)
    assert report["candidate"]["decision"] == {"compatible_label": "compatible", "candidate_probability_threshold": 0.5, "all_170_labels_scored": True, "threshold_calibrated_on_r186": False}
    assert report["data_contract"]["r186_evaluation_only"] is True
    assert report["constraints"]["no_lexical_gate"] is True
    assert report["constraints"]["no_posthoc_threshold"] is True
    assert report["evaluation"]["model_owned_rows"] == 77
    assert report["evaluation"]["oos_controls"] == 9
