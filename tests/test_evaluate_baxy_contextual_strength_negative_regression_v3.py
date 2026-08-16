from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_contextual_strength_negative_regression_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_baxy_contextual_strength_negative_regression_v3", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_bind_report_records_selected_score_and_preserves_result() -> None:
    inner = {
        "schema": "baxy.contextual-hyperspotter-fusion-negative-regression.v2",
        "sources": {"asset": "hash"},
        "contract": {"freshHoldoutClaimSupported": False},
        "metrics": {"guardedNegativeFalseActivations": 0},
        "regressionPassed": True,
    }
    report = MODULE.bind_report(
        inner,
        inner_report_sha256="inner",
        strength_report_sha256="strength",
    )
    assert report["schema"] == "baxy.contextual-strength-negative-regression.v3"
    assert report["contract"]["contextualHotwordScore"] == 4.0
    assert report["contract"]["scoreSelectedBeforeThisRegression"] is True
    assert report["regressionPassed"] is True
    assert report["sources"]["innerV2ReportSha256"] == "inner"


def test_bind_report_rejects_wrong_inner_schema() -> None:
    try:
        MODULE.bind_report(
            {"schema": "wrong"},
            inner_report_sha256="inner",
            strength_report_sha256="strength",
        )
    except ValueError as error:
        assert str(error) == "baxy_contextual_strength_negative_inner_invalid"
    else:
        raise AssertionError("wrong schema was accepted")
