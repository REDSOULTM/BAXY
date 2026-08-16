from __future__ import annotations

import importlib.util
from pathlib import Path
import random

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_baxy_logmel_closed_set_verifier_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_baxy_logmel_closed_set_verifier_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _FakeParameter:
    def __init__(self) -> None:
        self.requires_grad = True


class _FakeLayer:
    def __init__(self, parameters: list[_FakeParameter]) -> None:
        self._parameters = parameters

    def parameters(self) -> list[_FakeParameter]:
        return list(self._parameters)


class _FakeOutput(_FakeLayer):
    def __init__(self) -> None:
        self.first = [_FakeParameter(), _FakeParameter()]
        self.final = [_FakeParameter(), _FakeParameter()]
        super().__init__([*self.first, *self.final])

    def __getitem__(self, index: int) -> _FakeLayer:
        assert index == -1
        return _FakeLayer(self.final)


class _FakeModel:
    def __init__(self) -> None:
        self.backbone = [_FakeParameter(), _FakeParameter()]
        self.output = _FakeOutput()

    def parameters(self) -> list[_FakeParameter]:
        return [*self.backbone, *self.output.parameters()]


@pytest.mark.parametrize(
    ("scope", "expected"), (("all", 6), ("head", 4), ("final", 2))
)
def test_trainable_scope_freezes_every_unselected_parameter(
    scope: str, expected: int
) -> None:
    model = _FakeModel()
    selected = MODULE.select_trainable_parameters(model, scope)
    assert len(selected) == expected
    assert sum(parameter.requires_grad for parameter in model.parameters()) == expected


def test_trainable_scope_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="trainable_scope"):
        MODULE.select_trainable_parameters(_FakeModel(), "unknown")


def test_balanced_batch_preserves_domain_and_class() -> None:
    pools = {
        "synthetic_positive": [[1]],
        "synthetic_negative": [[2]],
        "physical_positive": [[3]],
        "physical_negative": [[4]],
        "auxiliary_positive": [[5]],
        "auxiliary_negative": [[6]],
    }
    selected, labels, domains = MODULE.balanced_batch(
        pools,
        batch_size=8,
        auxiliary_probability=1.0,
        rng=random.Random(4),
    )
    assert len(selected) == len(labels) == len(domains) == 8
    assert labels.count(1.0) == labels.count(0.0) == 4
    assert domains.count("synthetic") == domains.count("auxiliary") == 4


def test_source_reduction_uses_maximum_window() -> None:
    records = [
        {"record_id": "positive/1", "label": "positive"},
        {"record_id": "positive/1", "label": "positive"},
        {"record_id": "negative/1", "label": "adversarial_negative"},
    ]
    labels, scores = MODULE.reduce_source_scores(
        "physical", records, [0, 1, 2], np.asarray([0.2, 0.8, 0.5])
    )
    assert labels.tolist() == [0, 1]
    assert scores.tolist() == pytest.approx([0.5, 0.8])


def test_candidate_rank_is_safety_first() -> None:
    synthetic = {
        "false_acceptances_at_deployment_threshold": 0,
        "true_positive_recall_at_deployment_threshold": 1.0,
        "zero_false_positive_recall": 1.0,
        "auc": 1.0,
    }
    safer = {
        "false_acceptances_at_deployment_threshold": 0,
        "true_positive_recall_at_deployment_threshold": 1.0,
        "zero_false_positive_recall": 1.0,
        "auc": 0.9,
        "equal_error_rate": 0.1,
    }
    weaker = {
        "false_acceptances_at_deployment_threshold": 0,
        "true_positive_recall_at_deployment_threshold": 0.9,
        "zero_false_positive_recall": 0.9,
        "auc": 1.0,
        "equal_error_rate": 0.0,
    }
    safe_calibration = {
        "physical_recall": 1.0,
        "human_recall": 1.0,
        "score_threshold": 3.1,
    }
    weak_calibration = {
        "physical_recall": 0.9,
        "human_recall": 0.9,
        "score_threshold": 3.0,
    }
    assert MODULE.candidate_rank(
        safer, safer, synthetic, safe_calibration
    ) > MODULE.candidate_rank(
        weaker, weaker, synthetic, weak_calibration
    )


def test_calibrated_recall_precedes_legacy_fixed_threshold_count() -> None:
    perfect = {
        "false_acceptances_at_deployment_threshold": 0,
        "true_positive_recall_at_deployment_threshold": 1.0,
        "zero_false_positive_recall": 1.0,
        "auc": 1.0,
        "equal_error_rate": 0.0,
    }
    imperfect = {
        "false_acceptances_at_deployment_threshold": 0,
        "true_positive_recall_at_deployment_threshold": 0.8,
        "zero_false_positive_recall": 0.8,
        "auc": 0.8,
        "equal_error_rate": 0.2,
    }
    assert MODULE.candidate_rank(
        perfect,
        perfect,
        perfect,
        {
            "physical_recall": 1.0,
            "human_recall": 1.0,
            "score_threshold": 3.0,
        },
        {"false_acceptances_at_threshold": 1},
    ) > MODULE.candidate_rank(
        imperfect,
        imperfect,
        imperfect,
        {
            "physical_recall": 0.8,
            "human_recall": 0.8,
            "score_threshold": 3.0,
        },
        {"false_acceptances_at_threshold": 0},
    )


def test_balanced_batch_can_mix_human_without_dropping_classes() -> None:
    pools = {
        "synthetic_positive": [[1]],
        "synthetic_negative": [[2]],
        "physical_positive": [[3]],
        "physical_negative": [[4]],
        "human_positive": [[5]],
        "human_negative": [[6]],
    }
    _, labels, domains = MODULE.balanced_batch(
        pools,
        batch_size=8,
        auxiliary_probability=0.0,
        human_probability=1.0,
        rng=random.Random(5),
    )
    assert labels.count(1.0) == labels.count(0.0) == 4
    assert domains.count("human") == 4


def test_balanced_batch_can_replace_every_negative_with_hard_negative() -> None:
    pools = {
        "synthetic_positive": [[1]],
        "synthetic_negative": [[2]],
        "physical_positive": [[3]],
        "physical_negative": [[4]],
        "hard_negative": [[7]],
    }
    selected, labels, domains = MODULE.balanced_batch(
        pools,
        batch_size=8,
        auxiliary_probability=0.0,
        hard_negative_probability=1.0,
        rng=random.Random(7),
    )
    assert len(selected) == len(labels) == len(domains) == 8
    assert domains.count("hard_negative") == 4
    assert all(
        domain == "hard_negative"
        for domain, label in zip(domains, labels)
        if label == 0.0
    )


def test_balanced_batch_can_focus_a_fraction_of_hard_negatives() -> None:
    pools = {
        "synthetic_positive": [[1]],
        "synthetic_negative": [[2]],
        "physical_positive": [[3]],
        "physical_negative": [[4]],
        "hard_negative": [[7]],
        "hard_negative_focus": [[8]],
    }
    selected, labels, domains = MODULE.balanced_batch(
        pools,
        batch_size=8,
        auxiliary_probability=0.0,
        hard_negative_probability=1.0,
        hard_negative_focus_probability=1.0,
        rng=random.Random(7),
    )
    assert domains.count("hard_negative_focus") == 4
    assert all(
        selection == ("hard_negative_focus", 8)
        for selection, label in zip(selected, labels)
        if label == 0.0
    )


def test_candidate_hashes_keep_only_frozen_acceptances() -> None:
    report = {
        "schema": MODULE.CANDIDATE_REPORT_SCHEMA,
        "corpusManifestSha256": "corpus",
        "blindHumanPartitionAccessed": False,
        "positive": {
            "records": [
                {"audioSha256": "A", "accepted": True},
                {"audioSha256": "B", "accepted": False},
            ]
        },
        "negative": {
            "records": [{"audioSha256": "C", "accepted": True}]
        },
    }
    assert MODULE.candidate_audio_hashes(
        report, physical_manifest_sha256="corpus"
    ) == {"a", "c"}
    with pytest.raises(ValueError, match="candidate_boundary"):
        MODULE.candidate_audio_hashes(
            report, physical_manifest_sha256="different"
        )


def test_controlled_hard_negative_schema_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "features.manifest.v1.json"
    path.write_text(
        '{"schema":"baxy.controlled-hard-negative-logmel.v1"}',
        encoding="utf-8",
    )
    assert MODULE.hard_negative_manifest_schema(path) == (
        MODULE.CONTROLLED_HARD_NEGATIVE_SCHEMA
    )


def test_cascade_candidate_hashes_keep_every_upstream_proposal() -> None:
    report = {
        "schema": MODULE.CASCADE_REPORT_SCHEMA,
        "corpusManifestSha256": "corpus",
        "blindHumanPartitionAccessed": False,
        "positive": {
            "records": [
                {"audioSha256": "A", "upstreamCandidate": True},
                {"audioSha256": "B", "upstreamCandidate": False},
            ]
        },
        "negative": {
            "records": [
                {"audioSha256": "C", "upstreamCandidate": True}
            ]
        },
    }
    assert MODULE.candidate_audio_hashes(
        report, physical_manifest_sha256="corpus"
    ) == {"a", "c"}


def test_physical_persona_split_is_label_stratified_and_disjoint() -> None:
    records = [
        {"persona_id": f"positive_{index}", "label": "positive"}
        for index in range(4)
    ] + [
        {
            "persona_id": f"negative_{index}",
            "label": "adversarial_negative",
        }
        for index in range(5)
    ]
    training, validation = MODULE.stratified_persona_split(
        records, seed=17, validation_personas_per_label=2
    )
    assert training.isdisjoint(validation)
    assert training | validation == {
        str(record["persona_id"]) for record in records
    }
    labels = {
        str(record["persona_id"]): str(record["label"]) for record in records
    }
    assert sum(labels[persona] == "positive" for persona in validation) == 2
    assert sum(
        labels[persona] == "adversarial_negative" for persona in validation
    ) == 2


def test_physical_persona_split_rejects_cross_label_speaker_leakage() -> None:
    records = [
        {"persona_id": "same", "label": "positive"},
        {"persona_id": "same", "label": "adversarial_negative"},
        {"persona_id": "positive_two", "label": "positive"},
        {"persona_id": "negative_two", "label": "adversarial_negative"},
    ]
    with pytest.raises(ValueError, match="persona_label_drift"):
        MODULE.stratified_persona_split(
            records, seed=17, validation_personas_per_label=1
        )
