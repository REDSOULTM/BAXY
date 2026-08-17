from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from sealed_evidence import assert_sealed


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/audit_bge_m3_r233.py"
ARTIFACT = ROOT / "artifacts/audit/bge_m3_r233_structural_abstention_rejection.json"
ARTIFACT_SHA256 = (
    "4bec261e7ade045f6d8bb034a48d0cc44b052622ce838e8b758c0caf4d175356"
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
    spec = importlib.util.spec_from_file_location("r233", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r233_rejects_fixed_top_k_without_opening_the_model() -> None:
    assert_sealed(ARTIFACT, ARTIFACT_SHA256)
    report = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert report["deduction"]["contradiction"] is True
    assert report["deduction"]["candidates_per_query"] == 8
    assert report["verdict"] == "rejected_before_model_import_or_r228_opening"
    assert report["constraints"]["model_started"] is False
    assert report["constraints"]["r228_opened"] is False
