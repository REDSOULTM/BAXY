from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from sealed_evidence import assert_sealed


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_bge_m3_retrieval_r231.py"
ARTIFACT = ROOT / "artifacts/holdout/situated_cut_b_r228.bge_m3_r231.preregistration.json"
ARTIFACT_SHA256 = (
    "2623d7f37086df63ba06c1387a9ccb22a36c13f2cdefb6af959d506e39b67a80"
)

# R231 binds `registered_runtime_manifest_sha256`, the hash of
# `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`: a file outside the
# repository that differs on every machine, and that goal 03 changed when it
# promoted the decider to Qwen3-4B. R232 and R233 both refuse to build unless
# R231 regenerates identically, so all three inherit it. This is the R225 case
# of `documentacion/base/00_COMPUERTA.md` §6, and §7 applies: the sealed
# artifact is audited by the integrity of its seal, not by regeneration from
# the present tree. Everything the artifact concluded is still asserted.



def _module():
    spec = importlib.util.spec_from_file_location("r231", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r231_is_an_acquisition_preregistration_not_a_model_runner() -> None:
    assert_sealed(ARTIFACT, ARTIFACT_SHA256)
    report = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert report["authority"] == "sealed_before_external_weight_acquisition_or_model_start"
    assert report["candidate"]["runtime_integration"] == "none"
    assert report["candidate"]["ranking"]["top_k"] == 8
    assert report["constraints"]["model_started"] is False
    assert report["required_before_opening_r228"]["fresh_oos_population"] is True
    assert "sentence_transformers" not in SOURCE.read_text(encoding="utf-8")
