from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_explicit_confusable_negative_regression_v7.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_baxy_explicit_confusable_negative_regression_v7", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _Wake:
    CATEGORY_NAMES = ("blank", "b", "a", "f", "x")
    TARGET_IDS = ((1, 2),)
    CONFUSABLE_IDS = ((3, 4),)

    @staticmethod
    def _collapse_path(path):
        result = []
        previous = None
        for frame, token in enumerate(path):
            value = int(token)
            if value != 0 and value != previous:
                result.append((value, frame, frame + 1))
            previous = value
        return tuple(result)


def _probabilities(tokens: list[int]) -> np.ndarray:
    values = np.full((len(tokens), len(_Wake.CATEGORY_NAMES)), 0.01, np.float64)
    values[np.arange(len(tokens)), tokens] = 0.96
    return values


def test_exact_target_has_authority_over_confusable_veto() -> None:
    assert MODULE.explicit_confusable_guard(
        _probabilities([1, 2, 0, 3, 4]), _Wake()
    )


def test_exact_confusable_is_vetoed_without_target() -> None:
    assert not MODULE.explicit_confusable_guard(
        _probabilities([0, 3, 4, 0]), _Wake()
    )


def test_unrelated_sequence_is_preserved() -> None:
    assert MODULE.explicit_confusable_guard(
        _probabilities([0, 1, 4, 0]), _Wake()
    )


def _evidence() -> dict[str, object]:
    records = [
        {"label": "positive", "ctc_greedy_exact_confusable": False}
        for _ in range(18)
    ]
    records.extend(
        {"label": "hard_negative", "ctc_greedy_exact_confusable": True}
        for _ in range(3)
    )
    records.extend(
        {"label": "matched_negative", "ctc_greedy_exact_confusable": False}
        for _ in range(9)
    )
    return {
        "schema": "baxy.wake-ssl-ctc-ensemble-development.v1",
        "metrics": {
            "positive_accepted": 18,
            "positive_total": 18,
            "negative_false_accepts": 0,
            "negative_total": 12,
            "development_gate_passed": True,
        },
        "records": records,
    }


def test_ensemble_evidence_binds_human_and_confusable_counts() -> None:
    assert MODULE.validate_ensemble_evidence(_evidence()) == {
        "positiveTotal": 18,
        "positiveExplicitConfusables": 0,
        "negativeTotal": 12,
        "negativeExplicitConfusables": 3,
    }


def test_ensemble_evidence_rejects_positive_confusable() -> None:
    evidence = _evidence()
    evidence["records"][0]["ctc_greedy_exact_confusable"] = True
    with pytest.raises(
        ValueError,
        match="baxy_explicit_confusable_evidence_invalid",
    ):
        MODULE.validate_ensemble_evidence(evidence)
