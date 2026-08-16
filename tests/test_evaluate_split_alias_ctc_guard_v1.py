from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "wake_validation"))

from evaluate_split_alias_ctc_guard_v1 import (  # noqa: E402
    DECISION_MARGIN,
    SPLIT_METHOD,
    guard_accepts,
    split_records,
    summarize,
)


@dataclass
class Decision:
    accepted: bool
    method: str
    margin: float | None


def _record(audio: str, label: str, accepted: bool) -> dict[str, object]:
    return {
        "corpus": "endpoint_confusable",
        "label": label,
        "audioSha256": audio,
        "guardAccepted": accepted,
    }


def test_guard_requires_exact_ctc_and_published_margin() -> None:
    assert guard_accepts(Decision(True, "ctc_exact", DECISION_MARGIN))
    assert not guard_accepts(Decision(True, "ctc_lexical_anchor", 4.0))
    assert not guard_accepts(Decision(True, "ctc_exact", DECISION_MARGIN - 0.01))
    assert not guard_accepts(Decision(False, "ctc_exact", 4.0))


def test_split_records_selects_only_the_localized_route() -> None:
    report = {
        "positive": {
            "records": [
                {"record": 0, "method": SPLIT_METHOD, "audioSha256": "p"},
                {"record": 1, "method": "exact_leading_alias", "audioSha256": "x"},
            ]
        },
        "negative": {
            "records": [
                {"record": 0, "method": SPLIT_METHOD, "audioSha256": "n"},
            ]
        },
    }

    selected = split_records(report)

    assert [(item["label"], item["audioSha256"]) for item in selected] == [
        ("positive", "p"),
        ("negative", "n"),
    ]


def test_summary_passes_only_with_complete_preservation_and_zero_false_activations() -> (
    None
):
    metrics = summarize(
        [_record("p", "positive", True), _record("n", "negative", False)],
        current_confusable_positive_hashes=frozenset({"p"}),
        current_confusable_negative_hashes=frozenset({"n"}),
    )

    assert metrics["developmentGatePassed"] is True
    assert metrics["splitPositiveAccepted"] == metrics["splitPositiveTotal"] == 1
    assert metrics["splitNegativeFalseActivations"] == 0


def test_summary_rejects_one_lost_positive() -> None:
    metrics = summarize(
        [_record("p", "positive", False), _record("n", "negative", False)],
        current_confusable_positive_hashes=frozenset({"p"}),
        current_confusable_negative_hashes=frozenset({"n"}),
    )

    assert metrics["developmentGatePassed"] is False
    assert metrics["currentCascadeSplitPositivePreserved"] is False


def test_summary_rejects_one_false_activation() -> None:
    metrics = summarize(
        [_record("p", "positive", True), _record("n", "negative", True)],
        current_confusable_positive_hashes=frozenset({"p"}),
        current_confusable_negative_hashes=frozenset({"n"}),
    )

    assert metrics["developmentGatePassed"] is False
    assert metrics["currentCascadeSplitNegativeRemaining"] == 1
