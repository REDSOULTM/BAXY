from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_contextual_fusion_negative_regression_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_baxy_contextual_fusion_negative_regression_v2", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_sentinel_prefilter_is_inclusive_and_order_preserving() -> None:
    records = [
        {"max_score": 0.0099, "id": 0},
        {"max_score": 0.01, "id": 1},
        {"max_score": 0.2, "id": 2},
    ]
    assert [item["id"] for item in MODULE.select_sentinel_records(records)] == [1, 2]


def test_sentinel_population_is_complete_and_bound_to_expected_count() -> None:
    records = [
        {"max_score": 0.0099, "id": 0},
        {"max_score": 0.01, "id": 1},
        {"max_score": 0.2, "id": 2},
    ]
    selected = MODULE.validated_sentinel_records(
        records,
        [{}, {}, {}],
        expected_utterances=3,
        expected_sentinel_candidates=2,
    )
    assert [item["id"] for item in selected] == [1, 2]


def test_sentinel_population_rejects_truncation_and_count_drift() -> None:
    records = [{"max_score": 0.01}, {"max_score": 0.2}]
    with pytest.raises(
        ValueError,
        match="baxy_contextual_negative_sentinel_population_invalid",
    ):
        MODULE.validated_sentinel_records(
            records,
            [{}],
            expected_utterances=2,
            expected_sentinel_candidates=2,
        )
    with pytest.raises(
        ValueError,
        match="baxy_contextual_negative_sentinel_count_invalid",
    ):
        MODULE.validated_sentinel_records(
            records,
            [{}, {}],
            expected_utterances=2,
            expected_sentinel_candidates=1,
        )


def test_screening_cache_identity_excludes_post_screening_policy() -> None:
    identities = {
        name: f"value-{index}"
        for index, name in enumerate(MODULE._SCREENING_IDENTITY_KEYS)
    }
    identities.update(
        {
            "contextualViewPolicy": "same_exact_fusion_view",
            "stt:tokens.txt": "stt-hash",
            "softCtcThreshold": "-0.25",
        }
    )
    expected = MODULE.screening_checkpoint_identities(identities)

    identities["contextualViewPolicy"] = "full_capture"
    identities["stt:tokens.txt"] = "other-stt-hash"
    identities["softCtcThreshold"] = "0.5"

    assert MODULE.screening_checkpoint_identities(identities) == expected


def test_screening_cache_identity_rejects_missing_acoustic_input() -> None:
    identities = {name: "value" for name in MODULE._SCREENING_IDENTITY_KEYS}
    del identities["stage1ModelSha256"]
    with pytest.raises(
        ValueError,
        match="baxy_contextual_negative_screening_identity_invalid",
    ):
        MODULE.screening_checkpoint_identities(identities)


class _Config:
    minimum_samples = 2
    maximum_samples = 4
    maximum_turn_samples = 20


class _Wake:
    @staticmethod
    def verification_audio(audio, **kwargs):
        start = kwargs["start_sample"]
        values = np.asarray(audio, dtype=np.float32)[start : start + 4]
        return values if len(values) >= 2 else None


def test_fixed_views_use_only_the_preregistered_offsets() -> None:
    old = MODULE._V4.FUSION_VIEW_START_SAMPLES
    MODULE._V4.FUSION_VIEW_START_SAMPLES = (2, 6)
    try:
        views = MODULE.fixed_views(np.arange(10, dtype=np.float32), _Config(), _Wake())
    finally:
        MODULE._V4.FUSION_VIEW_START_SAMPLES = old
    assert [start for start, _ in views] == [2, 6]
    assert np.array_equal(views[0][1], np.array([2, 3, 4, 5], np.float32))


def test_same_view_contextual_policy_decodes_only_exact_acoustic_views() -> None:
    old = MODULE._V4.FUSION_VIEW_START_SAMPLES
    MODULE._V4.FUSION_VIEW_START_SAMPLES = (2, 6)
    try:
        proposals = MODULE.contextual_decode_proposals(
            {3},
            {3: np.arange(10, dtype=np.float32)},
            {3: {6}},
            policy="same_exact_fusion_view",
            config=_Config(),
            wake=_Wake(),
        )
    finally:
        MODULE._V4.FUSION_VIEW_START_SAMPLES = old

    assert len(proposals) == 1
    assert proposals[0]["recordIndex"] == 3
    assert proposals[0]["startSample"] == 6
    assert np.array_equal(
        proposals[0]["capture"],
        np.array([6, 7, 8, 9], np.float32),
    )


def test_full_capture_contextual_policy_keeps_one_capture_per_record() -> None:
    capture = np.arange(10, dtype=np.float32)
    proposals = MODULE.contextual_decode_proposals(
        {3},
        {3: capture},
        {},
        policy="full_capture",
        config=_Config(),
        wake=_Wake(),
    )

    assert len(proposals) == 1
    assert proposals[0]["startSample"] is None
    assert proposals[0]["capture"] is capture


def test_opened_negative_regression_keeps_only_development_authority() -> None:
    prior = {
        "schema": "baxy.wake-verifier-negative-opened-regression.v1",
        "development_gate_passed": True,
        "negative_corpus_previously_accessed": True,
        "fresh_holdout_claim_supported": False,
        "far_certification_supported": False,
        "product_operating_point": False,
    }

    assert (
        MODULE.prior_negative_evidence_authority(prior)
        == "opened_development_regression"
    )


def test_opened_negative_regression_rejects_product_operating_point() -> None:
    prior = {
        "schema": "baxy.wake-verifier-negative-opened-regression.v1",
        "development_gate_passed": True,
        "negative_corpus_previously_accessed": True,
        "fresh_holdout_claim_supported": False,
        "far_certification_supported": False,
        "product_operating_point": True,
    }

    assert MODULE.prior_negative_evidence_authority(prior) is None


class _Stage1:
    def __init__(self) -> None:
        self.rescored: list[int] = []

    @staticmethod
    def predict_overlapping_windows(padded, ends, window_samples):
        del padded, window_samples
        return np.array([0.009, 0.00995, 0.02][: len(ends)], np.float32)

    def rescore_windows_exact(self, padded, ends, indices, window_samples):
        del padded, ends, window_samples
        self.rescored.extend(indices)
        return np.array([0.01001 for _ in indices], np.float32)


def test_stage1_screen_rescores_only_the_threshold_band() -> None:
    stage1 = _Stage1()
    result = MODULE.sentinel_streaming_scores(
        stage1,
        np.zeros(1, np.float32),
        threshold=0.01,
        exact_boundary_guard=0.0001,
        hop_samples=32_000,
        frame_samples=32_000,
    )
    assert stage1.rescored == [1]
    assert result["boundary_rescored_windows"] == 1
    assert [item["score"] for item in result["retained_windows"]] == [
        np.float32(0.01001),
        np.float32(0.02),
    ]
