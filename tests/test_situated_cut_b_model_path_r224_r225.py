from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from sealed_evidence import assert_sealed


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT / "experiments/mind_router_spike/preregister_situated_cut_b_model_path_r224.py"
)
PREREGISTRATION_SEAL = (
    "4879797b570a6692564dd4ef703e9cc61fe440c42b46326504c46bfc9bdca03e"
)


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r224_freezes_corrected_runtime_and_current_catalogue() -> None:
    report = _module("r224", PREREGISTRATION).build()
    assert report["population"]["rows"] == 93
    assert (
        report["candidate"]["runtime"]
        == "registered_manifest_and_corrected_per_file_STT_verifier"
    )
    assert report["measurement"]["one_shot"] is True
    assert report["constraints"]["effects_executed"] == 0


def test_r224_published_preregistration_matches_builder() -> None:
    # The builder still runs — that is the test above. Its published
    # preregistration binds the catalogue snapshot it froze, which has since
    # moved, so the artifact is audited by its seal (§7).
    artifact = (
        ROOT
        / "artifacts/holdout/situated_cut_b_r215.model_path_r224.preregistration.json"
    )
    assert_sealed(artifact, PREREGISTRATION_SEAL)


def test_r225_reads_the_sealed_population_without_model_start() -> None:
    # R225's runner guard (`_load`) also binds `runtime_manifest_sha256`, the
    # hash of %LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json — a file outside
    # the repository that differs per machine, so the guard can never pass on
    # another one. The campaign is consumed; what stays checkable from the tree
    # is that the sealed preregistration and its corpus still agree.
    campaign = _module("r224_population", PREREGISTRATION)
    preregistration = json.loads(campaign.OUTPUT.read_text(encoding="utf-8"))
    rows = [
        line
        for line in campaign.CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert preregistration["population"]["rows"] == len(rows) == 93


def test_r225_published_result_keeps_the_rejection_and_hard_zero_evidence() -> None:
    result = json.loads(
        (ROOT / "artifacts/audit/situated_cut_b_r215_model_path_r225.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (
            ROOT / "artifacts/audit/situated_cut_b_r215_model_path_r225.consumed.json"
        ).read_text(encoding="utf-8")
    )

    assert result["status"] == "failed"
    assert result["scoring"]["diagnostic_partition"]["partition_total"] == 90
    assert result["scoring"]["safety"]["unsolicited_effect_count"] == 2
    assert result["execution"]["effects_executed"] == 0
    assert receipt["opened_exactly_once"] is True
    assert receipt["retry_allowed"] is False
