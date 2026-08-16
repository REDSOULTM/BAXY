from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT / "experiments/mind_router_spike/preregister_situated_cut_b_model_path_r220.py"
)
RUNNER = ROOT / "experiments/mind_router_spike/run_situated_cut_b_model_path_r221.py"


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, PREREGISTRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r220_freezes_the_current_174_operation_candidate() -> None:
    report = _module("r220").build()

    assert report["population"]["rows"] == 93
    assert report["population"]["recogniser_reach"] < 0.5
    assert (
        report["candidate"]["catalogue"]
        == "current_Core_must_match_R219_174_operation_snapshot"
    )
    assert report["measurement"]["one_shot"] is True
    assert report["constraints"]["effects_executed"] == 0


def test_r220_published_preregistration_matches_frozen_builder() -> None:
    artifact = (
        ROOT
        / "artifacts/holdout/situated_cut_b_r215.model_path_r220.preregistration.json"
    )
    assert (
        json.loads(artifact.read_text(encoding="utf-8"))
        == _module("r220_artifact").build()
    )


def test_r221_accepts_sealed_r220_identities_without_starting_model() -> None:
    spec = importlib.util.spec_from_file_location("r221", RUNNER)
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    preregistration, rows = runner._load()
    assert preregistration["population"]["rows"] == len(rows) == 93
