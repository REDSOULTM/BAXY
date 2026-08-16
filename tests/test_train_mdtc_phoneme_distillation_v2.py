from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "voice_latency"))

from phoneme_student_vocabulary_v2 import BLANK_ID, CATEGORY_NAMES  # noqa: E402
from train_mdtc_phoneme_distillation_v2 import (  # noqa: E402
    balanced_word_class_weights,
    build_model,
    category_weights,
    ctc_sequence_metrics,
    ctc_target_arrays,
    frame_metrics,
    local_ctc_viterbi_alignment,
    load_word_alignment_cache,
    transformed_external_spans,
    word_sequence_metrics,
    word_class_ids,
    word_target_arrays,
    write_word_alignment_cache,
)

import torch


def test_category_weights_raise_rare_speech_without_exploding() -> None:
    counts = [1000] + [100] * (len(CATEGORY_NAMES) - 2) + [500]
    counts[CATEGORY_NAMES.index("R_TAP")] = 1

    values = category_weights(counts)

    assert values[CATEGORY_NAMES.index("R_TAP")] == pytest.approx(8.0)
    assert values[0] == pytest.approx(1.0)
    assert values[-1] == pytest.approx(0.5)


def test_frame_metrics_respects_explicit_causal_delay() -> None:
    teacher = np.zeros((1, 4, len(CATEGORY_NAMES)), np.float32)
    teacher[:, :, 0] = 1.0
    teacher[0, 1, :] = 0.0
    teacher[0, 1, CATEGORY_NAMES.index("B")] = 1.0
    student = np.zeros_like(teacher)
    student[:, :, 0] = 1.0
    student[0, 2, :] = 0.0
    student[0, 2, CATEGORY_NAMES.index("B")] = 1.0

    metrics = frame_metrics(student, teacher, delay_frames=1)

    assert metrics["all_frame_accuracy"] == pytest.approx(1.0)
    assert metrics["nonblank_frame_accuracy"] == pytest.approx(1.0)


def test_external_locator_is_shifted_into_the_product_window() -> None:
    record = {
        "verifier_locators": [
            {
                "source": "parakeet_lexical_proposal",
                "locator_start_seconds": 1.04,
                "locator_end_seconds": 1.52,
                "multiword_non_target_veto": False,
            }
        ]
    }

    lexical, veto = transformed_external_spans(record, window_end_seconds=1.75)

    assert lexical == ((64, 89, "parakeet_lexical_proposal"),)
    assert veto == ()


def test_bidirectional_gru_preserves_the_99_frame_contract() -> None:
    model = build_model(
        torch,
        None,
        architecture_type="bidirectional_gru",
        hidden_dimension=16,
        stack_count=1,
        stack_size=1,
        kernel_size=3,
        recurrent_layers=2,
    )

    output = model(torch.zeros((2, 198, 80)))

    assert output.shape == (2, 99, len(CATEGORY_NAMES))
    assert model.causal is False


def test_ctc_targets_collapse_repeats_and_remove_blank() -> None:
    values = np.zeros((1, 7, len(CATEGORY_NAMES)), np.float32)
    path = [0, 1, 1, 0, 6, 6, 0]
    for frame, category in enumerate(path):
        values[0, frame, category] = 1.0

    targets, lengths = ctc_target_arrays(values)

    assert lengths.tolist() == [2]
    assert targets[0, :2].tolist() == [1, 6]


def test_ctc_sequence_metric_allows_temporal_realignment() -> None:
    teacher = np.zeros((1, 7, len(CATEGORY_NAMES)), np.float32)
    student = np.zeros_like(teacher)
    for frame, category in enumerate([0, 1, 1, 0, 6, 6, 0]):
        teacher[0, frame, category] = 1.0
    for frame, category in enumerate([0, 0, 1, 1, 0, 6, 0]):
        student[0, frame, category] = 1.0
    targets, lengths = ctc_target_arrays(teacher)

    metrics = ctc_sequence_metrics(student, targets, lengths)

    assert metrics["token_error_rate"] == pytest.approx(0.0)
    assert metrics["exact_sequence_rate"] == pytest.approx(1.0)


def test_word_targets_upweight_explicit_vaxi() -> None:
    records = [
        {"phrase_id": "target"},
        {"phrase_id": "vaxi"},
        {"phrase_id": "boxing"},
    ]
    targets, lengths, weights = word_target_arrays(
        records, np.asarray([1, 0, 0]), confusable_weight=16.0
    )

    assert lengths.tolist() == [5, 5, 0]
    assert weights.tolist() == [1.0, 16.0, 0.0]
    assert targets[0, 0] == CATEGORY_NAMES.index("B")
    assert targets[1, 0] == CATEGORY_NAMES.index("V")


def test_balanced_word_weights_equalize_every_explicit_class() -> None:
    records = [
        {"phrase_id": "target"},
        {"phrase_id": "target"},
        {"phrase_id": "vaxi"},
        {"phrase_id": "faxi"},
        {"phrase_id": "paxi"},
        {"phrase_id": "bakshi"},
        {"phrase_id": "boxing"},
    ]
    labels = np.asarray([1, 1, 0, 0, 0, 0, 0])

    classes = word_class_ids(records, labels)
    weights, report = balanced_word_class_weights(classes)

    assert classes.tolist() == [1, 1, 2, 3, 4, 5, 0]
    totals = [float(weights[classes == class_id].sum()) for class_id in range(1, 6)]
    assert totals == pytest.approx([7 / 5] * 5)
    assert report["counts"] == {
        "baxy": 2,
        "vaxi": 1,
        "faxi": 1,
        "paxi": 1,
        "bakshi": 1,
    }


def test_local_ctc_alignment_ignores_speech_outside_the_word() -> None:
    vocabulary = len(CATEGORY_NAMES)
    values = np.full((14, vocabulary), -20.0, dtype=np.float64)
    values[:, BLANK_ID] = -0.1
    values[0:3, CATEGORY_NAMES.index("other")] = 0.0
    sequence = tuple(
        CATEGORY_NAMES.index(name) for name in ("B", "A", "K", "S", "I")
    )
    for frame, token in zip((4, 5, 7, 9, 11), sequence, strict=True):
        values[frame, token] = 0.0
    values[12:, CATEGORY_NAMES.index("other")] = 0.0

    score, selected, start, end = local_ctc_viterbi_alignment(
        values, (sequence,), blank_id=BLANK_ID
    )

    assert np.isfinite(score)
    assert selected == sequence
    assert (start, end) == (4, 12)


def test_word_alignment_cache_round_trips_and_binds_sources(tmp_path: Path) -> None:
    path = tmp_path / "alignment.npz"
    train = (
        np.ones((2, 6), dtype=np.int64),
        np.ones(2, dtype=np.int64),
        np.zeros(2, dtype=np.int64),
        np.ones(2, dtype=np.int64),
    )
    development = tuple(value[:1] for value in train)
    report = {"strategy": "test"}

    write_word_alignment_cache(
        path,
        feature_manifest_sha256="features",
        teacher_manifest_sha256="teacher",
        train_values=train,
        development_values=development,
        report=report,
    )
    loaded_train, loaded_development, loaded_report = load_word_alignment_cache(
        path,
        feature_manifest_sha256="features",
        teacher_manifest_sha256="teacher",
        train_count=2,
        development_count=1,
    )

    for actual, expected in zip(loaded_train, train, strict=True):
        np.testing.assert_array_equal(actual, expected)
    for actual, expected in zip(loaded_development, development, strict=True):
        np.testing.assert_array_equal(actual, expected)
    assert loaded_report == report


def test_word_sequence_metrics_require_the_expected_rival() -> None:
    records = [{"phrase_id": "target"}, {"phrase_id": "vaxi"}]
    labels = np.asarray([1, 0])
    targets, lengths, _ = word_target_arrays(
        records, labels, confusable_weight=16.0
    )
    probabilities = np.zeros((2, 11, len(CATEGORY_NAMES)), np.float32)
    for row in range(2):
        probabilities[row, :, BLANK_ID] = 1.0
        for offset, category in enumerate(targets[row, : lengths[row]]):
            probabilities[row, 1 + 2 * offset, :] = 0.0
            probabilities[row, 1 + 2 * offset, category] = 1.0

    metrics = word_sequence_metrics(probabilities, targets, lengths, labels)

    assert metrics["positive_sequence_recall"] == pytest.approx(1.0)
    assert metrics["confusable_sequence_recall"] == pytest.approx(1.0)
    assert metrics["minimum_word_sequence_recall"] == pytest.approx(1.0)
    assert metrics["recall_by_word_class"] == {"baxy": 1.0, "vaxi": 1.0}
    assert metrics["minimum_word_class_recall"] == pytest.approx(1.0)


def test_word_sequence_metrics_groups_allowed_baxy_variants() -> None:
    variant = tuple(
        CATEGORY_NAMES.index(name) for name in ("BETA", "A", "R_TAP", "K", "S", "I")
    )
    targets = np.zeros((1, len(variant)), dtype=np.int64)
    targets[0] = variant
    probabilities = np.zeros((1, 13, len(CATEGORY_NAMES)), np.float32)
    probabilities[:, :, BLANK_ID] = 1.0
    for offset, category in enumerate(variant):
        probabilities[0, 1 + 2 * offset, :] = 0.0
        probabilities[0, 1 + 2 * offset, category] = 1.0

    metrics = word_sequence_metrics(
        probabilities, targets, np.asarray([len(variant)]), np.asarray([1])
    )

    assert metrics["recall_by_word_class"] == {"baxy": 1.0}
