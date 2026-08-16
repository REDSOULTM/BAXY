from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_bge_m3_retrieval_r231.py"


def _module():
    spec = importlib.util.spec_from_file_location("r231", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r231_is_an_acquisition_preregistration_not_a_model_runner() -> None:
    report = _module().build()
    assert report["authority"] == "sealed_before_external_weight_acquisition_or_model_start"
    assert report["candidate"]["runtime_integration"] == "none"
    assert report["candidate"]["ranking"]["top_k"] == 8
    assert report["constraints"]["model_started"] is False
    assert report["required_before_opening_r228"]["fresh_oos_population"] is True
    assert "sentence_transformers" not in SOURCE.read_text(encoding="utf-8")


def test_r231_published_preregistration_matches_builder() -> None:
    module = _module()
    output = ROOT / "artifacts/holdout/situated_cut_b_r228.bge_m3_r231.preregistration.json"
    assert json.loads(output.read_text(encoding="utf-8")) == module.build()
