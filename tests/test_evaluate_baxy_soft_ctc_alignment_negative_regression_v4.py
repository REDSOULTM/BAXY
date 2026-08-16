from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_soft_ctc_alignment_negative_regression_v4.py"
)
SPEC = importlib.util.spec_from_file_location("soft_ctc_negative_v4", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def checkpoint_fixture() -> tuple[dict[str, object], dict[str, object]]:
    identities = {"fusionManifestSha256": "a" * 64}
    checkpoint = {
        "schema": "baxy.hyperspotter-fusion-negative-regression-checkpoint.v1",
        "identities": identities,
        "completedRecords": 28_139,
        "recordMaximumMargins": [-1.0] * 28_139,
        "nearViews": [
            {
                "recordIndex": index,
                "startSample": 40_000 if index % 2 == 0 else 64_000,
                "hyperScore": 0.1,
            }
            for index in range(36)
        ],
        "viewCount": 56_278,
    }
    regression = {
        "schema": "baxy.contextual-strength-negative-regression.v3",
        "sources": identities,
        "metrics": {
            "sentinelCandidates": 28_139,
            "verificationViews": 56_278,
            "cpuRescoredViews": 36,
            "rawFusionFalseActivations": 34,
            "guardedNegativeFalseActivations": 1,
        },
        "regressionPassed": False,
        "blindHumanAudioAccessed": False,
        "recordsTranscriptsOrFilenamesRetained": False,
    }
    return checkpoint, regression


def test_completed_checkpoint_contract_accepts_only_the_full_campaign() -> None:
    checkpoint, regression = checkpoint_fixture()
    near, identities = MODULE.validate_checkpoint_contract(checkpoint, regression)
    assert len(near) == 36
    assert identities["fusionManifestSha256"] == "a" * 64


def test_completed_checkpoint_contract_rejects_partial_or_unbound_evidence() -> None:
    checkpoint, regression = checkpoint_fixture()
    checkpoint["completedRecords"] = 28_138
    try:
        MODULE.validate_checkpoint_contract(checkpoint, regression)
    except ValueError as error:
        assert str(error) == "baxy_soft_ctc_negative_checkpoint_invalid"
    else:
        raise AssertionError("partial checkpoint must be rejected")

    checkpoint, regression = checkpoint_fixture()
    regression["sources"] = {"fusionManifestSha256": "b" * 64}
    try:
        MODULE.validate_checkpoint_contract(checkpoint, regression)
    except ValueError as error:
        assert str(error) == "baxy_soft_ctc_negative_checkpoint_identity_invalid"
    else:
        raise AssertionError("unbound checkpoint must be rejected")


def test_percentile_summary_is_aggregate_only() -> None:
    summary = MODULE.percentile_summary([1.0, 2.0, 3.0])
    assert summary == {
        "minimum": 1.0,
        "p50": 2.0,
        "p95": 2.9,
        "maximum": 3.0,
        "mean": 2.0,
    }
    assert MODULE.percentile_summary([]) is None
