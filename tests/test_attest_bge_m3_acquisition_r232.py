from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from sealed_evidence import assert_sealed


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/attest_bge_m3_acquisition_r232.py"
ARTIFACT = ROOT / "artifacts/audit/bge_m3_acquisition_r232.json"
ARTIFACT_SHA256 = (
    "d6462c8c964887a99b5b6ad82f92606fe206c8b850c7d0e6f084180a0c64bb2c"
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
    spec = importlib.util.spec_from_file_location("r232", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r232_attests_files_without_importing_candidate_model() -> None:
    assert_sealed(ARTIFACT, ARTIFACT_SHA256)
    report = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert report["candidate"]["file_count"] > 0
    assert report["candidate"]["total_bytes"] > 1_000_000_000
    assert len(report["candidate"]["content_merkle_sha256"]) == 64
    assert report["constraints"]["model_imported"] is False
    assert report["constraints"]["registered_runtime_modified"] is False
    assert "sentence_transformers" not in SOURCE.read_text(encoding="utf-8")
