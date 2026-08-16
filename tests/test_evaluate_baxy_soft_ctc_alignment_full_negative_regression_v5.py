from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_soft_ctc_alignment_full_negative_regression_v5.py"
)
SPEC = importlib.util.spec_from_file_location("soft_ctc_full_v5", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def evidence_fixture() -> tuple[dict[str, object], dict[str, object]]:
    development = {
        "schema": "baxy.soft-ctc-alignment-development.v8",
        "softCtcDevelopmentGatePassed": True,
        "selectedSoftCtcPolicy": {"threshold": -0.25},
        "policy": {
            "guardRequiresSameFusionPassingView": True,
            "contextualHotwordScore": 4.0,
            "selectionPerformedBeforeAnyNewLongNegativeRegression": True,
        },
        "blindHumanAudioAccessed": False,
        "audioTranscriptsOrFilenamesRetained": False,
    }
    regression = {
        "schema": "baxy.contextual-strength-negative-regression.v3",
        "regressionPassed": False,
        "metrics": {"guardedNegativeFalseActivations": 1},
        "blindHumanAudioAccessed": False,
    }
    return development, regression


def test_development_binding_returns_only_the_preregistered_threshold() -> None:
    development, regression = evidence_fixture()
    assert MODULE.validate_development_binding(development, regression) == -0.25


def test_development_binding_rejects_posthoc_or_cross_view_selection() -> None:
    development, regression = evidence_fixture()
    development["policy"]["guardRequiresSameFusionPassingView"] = False
    try:
        MODULE.validate_development_binding(development, regression)
    except ValueError as error:
        assert str(error) == "baxy_soft_ctc_full_evidence_invalid"
    else:
        raise AssertionError("cross-view evidence must be rejected")

    development, regression = evidence_fixture()
    development["policy"]["selectionPerformedBeforeAnyNewLongNegativeRegression"] = False
    try:
        MODULE.validate_development_binding(development, regression)
    except ValueError as error:
        assert str(error) == "baxy_soft_ctc_full_evidence_invalid"
    else:
        raise AssertionError("posthoc selection must be rejected")
