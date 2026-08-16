from __future__ import annotations

import importlib
import json

import numpy as np

from baxy_mind.family_classifier import FamilyPrediction


class _FakePipeline:
    classes_ = np.asarray(["audio", "note", "wifi"], dtype=object)

    def __init__(self, scores: tuple[float, float, float]) -> None:
        self._scores = np.asarray([scores], dtype=np.float64)

    def decision_function(self, texts: list[str]) -> np.ndarray:
        assert texts == ["request"]
        return self._scores


def _candidate_module():
    return importlib.import_module(
        "experiments.mind_router_spike.measure_mtop_family_recovery"
    )


def test_candidate_classifier_respects_available_families() -> None:
    candidate = _candidate_module()
    classifier = candidate.CandidateFamilyClassifier(
        _FakePipeline((0.9, 0.8, 0.1)),
        minimum_margin=0.05,
    )

    prediction = classifier.predict("request", {"note", "wifi"})

    assert prediction.family == "note"
    assert np.isclose(prediction.margin, 0.7)


def test_candidate_classifier_abstains_below_existing_margin() -> None:
    candidate = _candidate_module()
    classifier = candidate.CandidateFamilyClassifier(
        _FakePipeline((0.2, 0.18, 0.1)),
        minimum_margin=0.05,
    )

    assert classifier.predict("request", {"audio", "note", "wifi"}) is None


def test_fallback_addition_never_removes_existing_candidates() -> None:
    candidate = _candidate_module()

    augmented = candidate.fallback_additive_candidates(
        baseline=("system.time", "system.status"),
        existing_prediction=None,
        candidate_prediction=FamilyPrediction("note", 0.8),
        tools_by_family={
            "note": ("note.create", "note.list", "note.read"),
        },
        limit=4,
    )

    assert augmented == (
        "system.time",
        "system.status",
        "note.create",
        "note.list",
    )


def test_fallback_addition_does_not_change_closed_existing_prediction() -> None:
    candidate = _candidate_module()
    baseline = ("audio.status", "audio.mute")

    augmented = candidate.fallback_additive_candidates(
        baseline=baseline,
        existing_prediction=FamilyPrediction("audio", 0.2),
        candidate_prediction=FamilyPrediction("note", 0.8),
        tools_by_family={"note": ("note.create", "note.list")},
        limit=28,
    )

    assert augmented == baseline


def test_already_incomplete_expected_set_is_not_a_true_loss() -> None:
    candidate = _candidate_module()

    delta = candidate.classify_retrieval_delta(
        baseline=("vision.describe",),
        candidate=("vision.describe",),
        expected=("capture.screenshot", "vision.describe"),
    )

    assert delta.dropped_recalled_operations == ()
    assert delta.instrument_false_loss is True
    assert delta.newly_complete is False


def test_dropping_a_recalled_expected_operation_is_a_true_loss() -> None:
    candidate = _candidate_module()

    delta = candidate.classify_retrieval_delta(
        baseline=("vision.describe", "capture.screenshot"),
        candidate=("web.search",),
        expected=("capture.screenshot", "vision.describe"),
    )

    assert delta.dropped_recalled_operations == (
        "capture.screenshot",
        "vision.describe",
    )
    assert delta.instrument_false_loss is False


def test_completing_an_expected_set_is_a_gain() -> None:
    candidate = _candidate_module()

    delta = candidate.classify_retrieval_delta(
        baseline=("message.send",),
        candidate=("message.send", "message.recipient.resolve"),
        expected=("message.send", "message.recipient.resolve"),
    )

    assert delta.dropped_recalled_operations == ()
    assert delta.newly_complete is True
    assert delta.newly_recalled_operations == ("message.recipient.resolve",)


def test_published_loss_audit_separates_instrument_false_losses(
    tmp_path,
) -> None:
    candidate = _candidate_module()
    baseline_path = tmp_path / "baseline.json"
    published_path = tmp_path / "published.json"
    output_path = tmp_path / "audit.json"
    baseline_path.write_text(
        json.dumps(
            {
                "row_counterfactuals": [
                    {
                        "population": "generalization_product_current_tree_r28",
                        "row_id": "vision-01",
                        "expected_operations": [
                            "capture.screenshot",
                            "vision.describe",
                        ],
                        "outside_catalogue": False,
                    },
                    {
                        "population": "veto_reach_v1",
                        "row_id": "v1-cat-01",
                        "expected_operations": ["system.time"],
                        "outside_catalogue": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    published_path.write_text(
        json.dumps(
            {
                "verdict": "rejected_regression",
                "family_validation": {
                    "primary_existing": {"correct": 106},
                    "primary_candidate": {"correct": 98},
                },
                "retrieval": {
                    "baseline": {
                        "outside_catalogue_false_candidate_entries": 1663
                    }
                },
                "replacement_variant": {"verdict": "rejected_regression"},
                "fallback_additive_variant": {
                    "baseline_recalled_rows_lost": [
                        "generalization_product_current_tree_r28:vision-01"
                    ],
                    "previously_missing_rows_gained": [],
                    "metrics": {
                        "outside_catalogue_false_candidate_entries": 1691
                    },
                    "rows": [
                        {
                            "population": "generalization_product_current_tree_r28",
                            "row_id": "vision-01",
                            "baseline_candidates": ["vision.describe"],
                            "candidate_candidates": ["vision.describe"],
                            "existing_family": "capture",
                            "candidate_family": "vision",
                        },
                        {
                            "population": "veto_reach_v1",
                            "row_id": "v1-cat-01",
                            "baseline_candidates": ["task.search"],
                            "candidate_candidates": ["task.search"],
                            "existing_family": "task",
                            "candidate_family": "system",
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    report = candidate.audit_published_loss_criterion(
        candidate_path=published_path,
        baseline_path=baseline_path,
        output=output_path,
    )

    assert report["corrected_additive_verdict"] == "rejected_no_target_gain"
    assert report["additive"]["true_dropped_recalled_rows"] == []
    assert report["additive"]["instrument_false_loss_rows"] == [
        "generalization_product_current_tree_r28:vision-01"
    ]
    assert report["v1_v7_serviceable_baseline_misses"][
        "existing_classifier_wrong_family"
    ] == ["veto_reach_v1:v1-cat-01"]
