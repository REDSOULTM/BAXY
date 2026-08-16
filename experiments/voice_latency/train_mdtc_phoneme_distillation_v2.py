"""Train and evaluate a causal tiny verifier from the lossless v2 teacher head."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evaluate_phoneme_teacher_category_oracle_v2 import (  # noqa: E402
    score_category_probabilities,
)
from phoneme_student_vocabulary_v2 import (  # noqa: E402
    BLANK_ID,
    CATEGORY_NAMES,
    CONFUSABLE_IDS,
    TARGET_IDS,
)
from train_mdtc_livekit_verifier_student import (  # noqa: E402
    read_json,
    roc_auc,
    sha256,
)
from train_mdtc_phonetic_ctc_group_cv import load_partition  # noqa: E402


FRAME_SECONDS = 0.02
WINDOW_SECONDS = 2.0


def load_teacher_partition(
    manifest: dict[str, object], name: str, expected_count: int
) -> np.ndarray:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("mdtc_distillation_v2_teacher_outputs_missing")
    value = outputs.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"mdtc_distillation_v2_teacher_partition_missing:{name}")
    path = Path(str(value.get("path"))).resolve(strict=True)
    if sha256(path) != value.get("sha256"):
        raise ValueError(f"mdtc_distillation_v2_teacher_hash_mismatch:{name}")
    probabilities = np.load(path, allow_pickle=False)
    shape = (expected_count, 99, len(CATEGORY_NAMES))
    if probabilities.shape != shape:
        raise ValueError(f"mdtc_distillation_v2_teacher_shape_invalid:{name}")
    values = np.asarray(probabilities, dtype=np.float32)
    if not np.isfinite(values).all() or not np.allclose(
        values.sum(axis=-1), 1.0, atol=2e-3
    ):
        raise ValueError(f"mdtc_distillation_v2_teacher_values_invalid:{name}")
    return values


def build_model(
    torch: object,
    mdtc_type: object | None,
    *,
    architecture_type: str,
    hidden_dimension: int,
    stack_count: int,
    stack_size: int,
    kernel_size: int,
    recurrent_layers: int,
) -> object:
    nn = torch.nn

    if architecture_type not in {"causal_mdtc", "bidirectional_gru"}:
        raise ValueError("mdtc_distillation_v2_architecture_invalid")

    class DistilledPhonemeStudentV2(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.normalization = nn.LayerNorm(80)
            if architecture_type == "causal_mdtc":
                if mdtc_type is None:
                    raise ValueError("mdtc_distillation_v2_mdtc_type_missing")
                self.projection = nn.Linear(80, hidden_dimension)
                self.backbone = mdtc_type(
                    stack_num=stack_count,
                    stack_size=stack_size,
                    in_channels=hidden_dimension,
                    res_channels=hidden_dimension,
                    kernel_size=kernel_size,
                    causal=True,
                )
                self.output = nn.Linear(hidden_dimension, len(CATEGORY_NAMES))
                self.causal = True
                self.receptive_field_frames = int(self.backbone.padding)
            else:
                if recurrent_layers <= 0:
                    raise ValueError("mdtc_distillation_v2_recurrent_layers_invalid")
                self.backbone = nn.GRU(
                    input_size=80,
                    hidden_size=hidden_dimension,
                    num_layers=recurrent_layers,
                    batch_first=True,
                    bidirectional=True,
                    dropout=0.1 if recurrent_layers > 1 else 0.0,
                )
                self.output = nn.Linear(
                    hidden_dimension * 2, len(CATEGORY_NAMES)
                )
                self.causal = False
                self.receptive_field_frames = 99

        def forward(self, features: object) -> object:
            downsampled = features[:, 1::2]
            normalized = self.normalization(downsampled)
            if architecture_type == "causal_mdtc":
                normalized = torch.nn.functional.gelu(self.projection(normalized))
            encoded, _ = self.backbone(normalized)
            return self.output(encoded)

    return DistilledPhonemeStudentV2()


def category_weights(hard_counts: list[object]) -> np.ndarray:
    counts = np.asarray(hard_counts, dtype=np.float64)
    if counts.shape != (len(CATEGORY_NAMES),) or np.any(counts < 0):
        raise ValueError("mdtc_distillation_v2_category_counts_invalid")
    speech = counts[1:-1]
    observed = speech[speech > 0]
    if len(observed) == 0:
        raise ValueError("mdtc_distillation_v2_speech_counts_empty")
    reference = float(np.median(observed))
    weights = np.ones(len(CATEGORY_NAMES), dtype=np.float32)
    for index in range(1, len(CATEGORY_NAMES) - 1):
        if counts[index] > 0:
            weights[index] = np.clip(math.sqrt(reference / counts[index]), 0.5, 8.0)
    weights[-1] = 0.5
    return weights


def aligned_logits_and_teacher(
    logits: object, teacher: object, *, delay_frames: int
) -> tuple[object, object]:
    if delay_frames < 0 or delay_frames >= logits.shape[1]:
        raise ValueError("mdtc_distillation_v2_delay_invalid")
    if logits.shape != teacher.shape:
        raise ValueError("mdtc_distillation_v2_probability_shape_mismatch")
    if delay_frames == 0:
        return logits, teacher
    return logits[:, delay_frames:], teacher[:, :-delay_frames]


def distillation_losses(
    torch: object,
    logits: object,
    teacher: object,
    *,
    delay_frames: int,
    speech_frame_weight: float,
    hard_loss_weight: float,
    class_weights: object,
) -> object:
    if speech_frame_weight < 1.0 or hard_loss_weight < 0.0:
        raise ValueError("mdtc_distillation_v2_loss_weight_invalid")
    aligned_logits, aligned_teacher = aligned_logits_and_teacher(
        logits, teacher, delay_frames=delay_frames
    )
    log_probabilities = torch.nn.functional.log_softmax(
        aligned_logits.float(), dim=-1
    )
    target = aligned_teacher.float()
    soft_cross_entropy = -(target * log_probabilities).sum(dim=-1)
    speech_weights = 1.0 + (speech_frame_weight - 1.0) * (
        1.0 - target[:, :, BLANK_ID]
    )
    hard_labels = target.argmax(dim=-1)
    hard_cross_entropy = torch.nn.functional.nll_loss(
        log_probabilities.transpose(1, 2), hard_labels, reduction="none"
    )
    hard_weights = class_weights[hard_labels]
    combined = soft_cross_entropy * speech_weights
    if hard_loss_weight:
        combined = combined + hard_loss_weight * hard_cross_entropy * hard_weights
    normalization = speech_weights.sum(dim=1) + hard_loss_weight * hard_weights.sum(
        dim=1
    )
    return combined.sum(dim=1) / normalization.clamp_min(1e-6)


def ctc_target_arrays(probabilities: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(probabilities)
    if values.ndim != 3 or values.shape[-1] != len(CATEGORY_NAMES):
        raise ValueError("mdtc_distillation_v2_ctc_teacher_shape_invalid")
    hard = values.argmax(axis=-1)
    targets = np.zeros(hard.shape, dtype=np.int64)
    lengths = np.zeros(len(hard), dtype=np.int64)
    for row, path in enumerate(hard):
        previous = None
        sequence = []
        for raw_value in path:
            value = int(raw_value)
            if value != previous and value != BLANK_ID:
                sequence.append(value)
            previous = value
        targets[row, : len(sequence)] = sequence
        lengths[row] = len(sequence)
    return targets, lengths


DEFAULT_TARGET = TARGET_IDS[0]
WORD_CONFUSABLES = {
    "vaxi": next(value for value in CONFUSABLE_IDS if value[0] == CATEGORY_NAMES.index("V")),
    "viplav_vaxi": next(value for value in CONFUSABLE_IDS if value[0] == CATEGORY_NAMES.index("V")),
    "faxi": next(value for value in CONFUSABLE_IDS if value[0] == CATEGORY_NAMES.index("F")),
    "mahesh_faxi": next(value for value in CONFUSABLE_IDS if value[0] == CATEGORY_NAMES.index("F")),
    "paxi": next(value for value in CONFUSABLE_IDS if value[0] == CATEGORY_NAMES.index("P")),
    "bakshi": next(value for value in CONFUSABLE_IDS if value[3] == CATEGORY_NAMES.index("SH")),
    "tarang_bakshi": next(value for value in CONFUSABLE_IDS if value[3] == CATEGORY_NAMES.index("SH")),
    "upendra_bakshi": next(value for value in CONFUSABLE_IDS if value[3] == CATEGORY_NAMES.index("SH")),
}
WORD_CLASS_SEQUENCES = {
    "baxy": DEFAULT_TARGET,
    "vaxi": WORD_CONFUSABLES["vaxi"],
    "faxi": WORD_CONFUSABLES["faxi"],
    "paxi": WORD_CONFUSABLES["paxi"],
    "bakshi": WORD_CONFUSABLES["bakshi"],
}
WORD_CLASS_BY_SEQUENCE = {
    tuple(sequence): index
    for index, sequence in enumerate(WORD_CLASS_SEQUENCES.values(), start=1)
}


def _word_target_sequence(
    record: dict[str, object], label: object
) -> tuple[int, ...] | None:
    if int(label) == 1:
        return DEFAULT_TARGET
    phrase = record.get("phrase_id")
    speaker_group = record.get("speaker_group")
    sequence = WORD_CONFUSABLES.get(phrase) if isinstance(phrase, str) else None
    if sequence is None and isinstance(speaker_group, str):
        sequence = WORD_CONFUSABLES.get(speaker_group)
    return sequence


def word_target_arrays(
    records: list[dict[str, object]],
    labels: np.ndarray,
    *,
    confusable_weight: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    label_values = np.asarray(labels).reshape(-1)
    if len(records) != len(label_values) or confusable_weight < 1.0:
        raise ValueError("mdtc_distillation_v2_word_target_contract_invalid")
    maximum_length = max(len(value) for value in (*TARGET_IDS, *CONFUSABLE_IDS))
    targets = np.zeros((len(records), maximum_length), dtype=np.int64)
    lengths = np.zeros(len(records), dtype=np.int64)
    weights = np.zeros(len(records), dtype=np.float32)
    for index, (record, label) in enumerate(
        zip(records, label_values, strict=True)
    ):
        sequence = _word_target_sequence(record, label)
        if sequence is None:
            continue
        targets[index, : len(sequence)] = sequence
        lengths[index] = len(sequence)
        weights[index] = 1.0 if int(label) == 1 else confusable_weight
    return targets, lengths, weights


def word_class_ids(
    records: list[dict[str, object]], labels: np.ndarray
) -> np.ndarray:
    label_values = np.asarray(labels).reshape(-1)
    if len(records) != len(label_values):
        raise ValueError("mdtc_distillation_v2_word_class_contract_invalid")
    classes = np.zeros(len(records), dtype=np.int64)
    for index, (record, label) in enumerate(
        zip(records, label_values, strict=True)
    ):
        sequence = _word_target_sequence(record, label)
        if sequence is not None:
            classes[index] = WORD_CLASS_BY_SEQUENCE[tuple(sequence)]
    return classes


def balanced_word_class_weights(
    class_ids: np.ndarray,
) -> tuple[np.ndarray, dict[str, object]]:
    values = np.asarray(class_ids).reshape(-1)
    active = sorted(int(value) for value in np.unique(values) if int(value) > 0)
    if not active:
        raise ValueError("mdtc_distillation_v2_word_classes_missing")
    weights = np.zeros(len(values), dtype=np.float32)
    counts: dict[str, int] = {}
    class_weights: dict[str, float] = {}
    names = tuple(WORD_CLASS_SEQUENCES)
    for class_id in active:
        if class_id > len(names):
            raise ValueError("mdtc_distillation_v2_word_class_unknown")
        mask = values == class_id
        count = int(mask.sum())
        weight = len(values) / (len(active) * count)
        weights[mask] = weight
        name = names[class_id - 1]
        counts[name] = count
        class_weights[name] = weight
    return weights, {
        "strategy": "equal_corpus_mean_per_explicit_word_class",
        "active_classes": len(active),
        "counts": counts,
        "weights": class_weights,
    }


def _word_class_candidate_sequences(class_id: int) -> tuple[tuple[int, ...], ...]:
    names = tuple(WORD_CLASS_SEQUENCES)
    if not 1 <= class_id <= len(names):
        raise ValueError("mdtc_distillation_v2_word_class_unknown")
    name = names[class_id - 1]
    if name == "baxy":
        return TARGET_IDS
    expected = WORD_CLASS_SEQUENCES[name]
    if name == "bakshi":
        values = tuple(
            sequence
            for sequence in CONFUSABLE_IDS
            if sequence[-2] == CATEGORY_NAMES.index("SH")
        )
    else:
        values = tuple(
            sequence for sequence in CONFUSABLE_IDS if sequence[0] == expected[0]
        )
    if not values:
        raise ValueError("mdtc_distillation_v2_word_class_candidates_missing")
    return values


def _word_class_id_for_sequence(sequence: tuple[int, ...]) -> int | None:
    if sequence in TARGET_IDS:
        return 1
    if sequence not in CONFUSABLE_IDS:
        return None
    if sequence[-2] == CATEGORY_NAMES.index("SH"):
        return tuple(WORD_CLASS_SEQUENCES).index("bakshi") + 1
    initial_names = {"V": "vaxi", "F": "faxi", "P": "paxi"}
    for initial_name, class_name in initial_names.items():
        if sequence[0] == CATEGORY_NAMES.index(initial_name):
            return tuple(WORD_CLASS_SEQUENCES).index(class_name) + 1
    return None


def local_ctc_viterbi_alignment(
    log_probabilities: np.ndarray,
    sequences: tuple[tuple[int, ...], ...],
    *,
    blank_id: int,
) -> tuple[float, tuple[int, ...], int, int]:
    values = np.asarray(log_probabilities, dtype=np.float64)
    if values.ndim != 2 or len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("mdtc_distillation_v2_alignment_values_invalid")
    best_result: tuple[float, tuple[int, ...], int, int] | None = None
    for raw_sequence in sequences:
        sequence = tuple(int(value) for value in raw_sequence)
        if not sequence or any(
            value == blank_id or not 0 <= value < values.shape[1]
            for value in sequence
        ):
            raise ValueError("mdtc_distillation_v2_alignment_sequence_invalid")
        states = [blank_id]
        for value in sequence:
            states.extend((value, blank_id))
        state_values = np.asarray(states, dtype=np.int64)
        skip_allowed = np.zeros(len(states), dtype=bool)
        skip_allowed[2:] = (
            (state_values[2:] != blank_id)
            & (state_values[2:] != state_values[:-2])
        )
        previous = np.full(len(states), -math.inf, dtype=np.float64)
        previous_starts = np.full(len(states), -1, dtype=np.int64)
        sequence_best: tuple[float, int, int] | None = None
        for frame, frame_values in enumerate(values):
            start_scores = np.full(len(states), -math.inf, dtype=np.float64)
            start_scores[:2] = 0.0
            start_starts = np.full(len(states), -1, dtype=np.int64)
            start_starts[:2] = frame
            advance_scores = np.concatenate(([-math.inf], previous[:-1]))
            advance_starts = np.concatenate(([-1], previous_starts[:-1]))
            skip_scores = np.concatenate(([-math.inf, -math.inf], previous[:-2]))
            skip_scores[~skip_allowed] = -math.inf
            skip_starts = np.concatenate(([-1, -1], previous_starts[:-2]))
            candidate_scores = np.stack(
                (start_scores, previous, advance_scores, skip_scores)
            )
            candidate_starts = np.stack(
                (start_starts, previous_starts, advance_starts, skip_starts)
            )
            selected = candidate_scores.argmax(axis=0)
            columns = np.arange(len(states))
            current = (
                candidate_scores[selected, columns] + frame_values[state_values]
            )
            current_starts = candidate_starts[selected, columns]
            for final_state in (len(states) - 2, len(states) - 1):
                score = float(current[final_state])
                start = int(current_starts[final_state])
                if start >= 0 and (
                    sequence_best is None or score > sequence_best[0]
                ):
                    sequence_best = (score, start, frame + 1)
            previous = current
            previous_starts = current_starts
        if sequence_best is None:
            raise ValueError("mdtc_distillation_v2_alignment_not_found")
        score, start, end = sequence_best
        result = (score, sequence, start, end)
        if best_result is None or result[0] > best_result[0]:
            best_result = result
    if best_result is None:
        raise ValueError("mdtc_distillation_v2_alignment_candidates_empty")
    return best_result


def teacher_aligned_word_targets(
    teacher_probabilities: np.ndarray,
    records: list[dict[str, object]],
    labels: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    probabilities = np.asarray(teacher_probabilities, dtype=np.float32)
    classes = word_class_ids(records, labels)
    if probabilities.ndim != 3 or len(probabilities) != len(classes):
        raise ValueError("mdtc_distillation_v2_alignment_contract_invalid")
    maximum_length = max(len(value) for value in (*TARGET_IDS, *CONFUSABLE_IDS))
    targets = np.zeros((len(classes), maximum_length), dtype=np.int64)
    lengths = np.zeros(len(classes), dtype=np.int64)
    starts = np.zeros(len(classes), dtype=np.int64)
    ends = np.ones(len(classes), dtype=np.int64)
    sequence_counts: dict[str, int] = {}
    active_spans = []
    for index, class_id in enumerate(classes):
        if not class_id:
            continue
        values = np.asarray(probabilities[index], dtype=np.float64)
        score, sequence, start, end = local_ctc_viterbi_alignment(
            np.log(np.maximum(values, 1e-12)),
            _word_class_candidate_sequences(int(class_id)),
            blank_id=BLANK_ID,
        )
        del score
        if end - start < len(sequence):
            raise ValueError("mdtc_distillation_v2_alignment_span_too_short")
        targets[index, : len(sequence)] = sequence
        lengths[index] = len(sequence)
        starts[index] = start
        ends[index] = end
        key = "-".join(CATEGORY_NAMES[value] for value in sequence)
        sequence_counts[key] = sequence_counts.get(key, 0) + 1
        active_spans.append(end - start)
    if not active_spans:
        raise ValueError("mdtc_distillation_v2_alignment_spans_missing")
    return targets, lengths, starts, ends, {
        "strategy": "teacher_local_ctc_viterbi_best_pronunciation_span",
        "aligned_records": len(active_spans),
        "minimum_span_frames": min(active_spans),
        "maximum_span_frames": max(active_spans),
        "mean_span_frames": sum(active_spans) / len(active_spans),
        "sequence_counts": sequence_counts,
    }


def write_word_alignment_cache(
    path: Path,
    *,
    feature_manifest_sha256: str,
    teacher_manifest_sha256: str,
    train_values: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    development_values: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    report: dict[str, object],
) -> None:
    path = path.resolve()
    if path.exists():
        raise FileExistsError(f"mdtc_distillation_v2_alignment_cache_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema": "baxy.teacher-local-ctc-word-alignment.v1",
        "feature_manifest_sha256": feature_manifest_sha256,
        "teacher_manifest_sha256": teacher_manifest_sha256,
        "report": report,
    }
    with path.open("xb") as handle:
        np.savez_compressed(
            handle,
            metadata=np.asarray(json.dumps(metadata, sort_keys=True)),
            train_targets=train_values[0],
            train_lengths=train_values[1],
            train_starts=train_values[2],
            train_ends=train_values[3],
            development_targets=development_values[0],
            development_lengths=development_values[1],
            development_starts=development_values[2],
            development_ends=development_values[3],
        )


def load_word_alignment_cache(
    path: Path,
    *,
    feature_manifest_sha256: str,
    teacher_manifest_sha256: str,
    train_count: int,
    development_count: int,
) -> tuple[
    tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    dict[str, object],
]:
    path = path.resolve(strict=True)
    with np.load(path, allow_pickle=False) as values:
        metadata = json.loads(str(values["metadata"]))
        if (
            metadata.get("schema") != "baxy.teacher-local-ctc-word-alignment.v1"
            or metadata.get("feature_manifest_sha256") != feature_manifest_sha256
            or metadata.get("teacher_manifest_sha256") != teacher_manifest_sha256
        ):
            raise ValueError("mdtc_distillation_v2_alignment_cache_source_mismatch")
        train = tuple(
            np.asarray(values[f"train_{name}"])
            for name in ("targets", "lengths", "starts", "ends")
        )
        development = tuple(
            np.asarray(values[f"development_{name}"])
            for name in ("targets", "lengths", "starts", "ends")
        )
    if any(len(value) != train_count for value in train) or any(
        len(value) != development_count for value in development
    ):
        raise ValueError("mdtc_distillation_v2_alignment_cache_shape_mismatch")
    report = metadata.get("report")
    if not isinstance(report, dict):
        raise ValueError("mdtc_distillation_v2_alignment_cache_report_invalid")
    return train, development, report


def hybrid_losses(
    torch: object,
    logits: object,
    teacher: object,
    ctc_targets: object,
    ctc_target_lengths: object,
    word_targets: object,
    word_target_lengths: object,
    word_weights: object,
    word_span_starts: object,
    word_span_ends: object,
    *,
    delay_frames: int,
    speech_frame_weight: float,
    hard_loss_weight: float,
    ctc_loss_weight: float,
    word_ctc_loss_weight: float,
    class_weights: object,
) -> object:
    if ctc_loss_weight < 0.0 or word_ctc_loss_weight < 0.0:
        raise ValueError("mdtc_distillation_v2_ctc_weight_invalid")
    losses = distillation_losses(
        torch,
        logits,
        teacher,
        delay_frames=delay_frames,
        speech_frame_weight=speech_frame_weight,
        hard_loss_weight=hard_loss_weight,
        class_weights=class_weights,
    )
    if not ctc_loss_weight and not word_ctc_loss_weight:
        return losses
    if (
        ctc_targets.ndim != 2
        or ctc_target_lengths.ndim != 1
        or word_targets.ndim != 2
        or word_target_lengths.ndim != 1
        or word_weights.ndim != 1
        or word_span_starts.ndim != 1
        or word_span_ends.ndim != 1
    ):
        raise ValueError("mdtc_distillation_v2_ctc_target_shape_invalid")
    input_lengths = torch.full(
        (logits.shape[0],), logits.shape[1], dtype=torch.long, device=logits.device
    )
    ctc = torch.nn.CTCLoss(blank=BLANK_ID, reduction="none", zero_infinity=True)
    log_probabilities = torch.nn.functional.log_softmax(
        logits.float(), dim=-1
    ).transpose(0, 1)
    if ctc_loss_weight:
        ctc_values = ctc(
            log_probabilities,
            ctc_targets,
            input_lengths,
            ctc_target_lengths,
        )
        losses = losses + ctc_loss_weight * (
            ctc_values / ctc_target_lengths.clamp_min(1)
        )
    if word_ctc_loss_weight:
        span_lengths = (word_span_ends - word_span_starts).clamp_min(1)
        if bool(
            (word_span_starts < 0).any()
            or (word_span_ends > logits.shape[1]).any()
            or (span_lengths < word_target_lengths).any()
        ):
            raise ValueError("mdtc_distillation_v2_word_span_invalid")
        maximum_span = int(span_lengths.max().item())
        offsets = torch.arange(maximum_span, device=logits.device).unsqueeze(0)
        indexes = (word_span_starts.unsqueeze(1) + offsets).clamp_max(
            logits.shape[1] - 1
        )
        span_logits = logits.gather(
            1,
            indexes.unsqueeze(-1).expand(-1, -1, logits.shape[-1]),
        )
        span_log_probabilities = torch.nn.functional.log_softmax(
            span_logits.float(), dim=-1
        ).transpose(0, 1)
        word_values = ctc(
            span_log_probabilities,
            word_targets,
            span_lengths,
            word_target_lengths,
        )
        normalized_words = word_values / word_target_lengths.clamp_min(1)
        losses = losses + word_ctc_loss_weight * normalized_words * word_weights
    return losses


def predict_probabilities(
    torch: object,
    model: object,
    features: np.ndarray,
    *,
    device: str,
    batch_size: int,
) -> np.ndarray:
    chunks = []
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(features), batch_size):
            batch = torch.from_numpy(features[start : start + batch_size]).to(device)
            chunks.append(torch.softmax(model(batch).float(), dim=-1).cpu().numpy())
    return np.concatenate(chunks).astype(np.float32)


def frame_metrics(
    probabilities: np.ndarray,
    teacher: np.ndarray,
    *,
    delay_frames: int,
) -> dict[str, object]:
    student = np.asarray(probabilities)
    target = np.asarray(teacher)
    if delay_frames:
        student = student[:, delay_frames:]
        target = target[:, :-delay_frames]
    predicted = student.argmax(axis=-1)
    labels = target.argmax(axis=-1)
    rows = []
    recalls = []
    for category, name in enumerate(CATEGORY_NAMES):
        mask = labels == category
        count = int(mask.sum())
        correct = int(np.count_nonzero(predicted[mask] == category)) if count else 0
        recall = correct / count if count else None
        if 0 < category < len(CATEGORY_NAMES) - 1 and count >= 10:
            recalls.append(float(recall))
        rows.append(
            {
                "category": name,
                "teacher_frames": count,
                "correct_frames": correct,
                "recall": recall,
            }
        )
    nonblank = labels != BLANK_ID
    return {
        "all_frame_accuracy": float(np.mean(predicted == labels)),
        "nonblank_frame_accuracy": float(np.mean(predicted[nonblank] == labels[nonblank])),
        "macro_observed_speech_recall": float(np.mean(recalls)),
        "categories": rows,
    }


def _edit_distance(left: list[int], right: list[int]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + int(left_value != right_value),
                )
            )
        previous = current
    return previous[-1]


def ctc_sequence_metrics(
    probabilities: np.ndarray,
    target_values: np.ndarray,
    target_lengths: np.ndarray,
) -> dict[str, object]:
    student_targets, student_lengths = ctc_target_arrays(probabilities)
    targets = np.asarray(target_values)
    lengths = np.asarray(target_lengths).reshape(-1)
    if targets.shape != student_targets.shape or len(lengths) != len(targets):
        raise ValueError("mdtc_distillation_v2_ctc_metric_shape_invalid")
    edits = 0
    target_tokens = 0
    exact = 0
    for student, student_length, target, target_length in zip(
        student_targets, student_lengths, targets, lengths, strict=True
    ):
        left = student[: int(student_length)].tolist()
        right = target[: int(target_length)].tolist()
        distance = _edit_distance(left, right)
        edits += distance
        target_tokens += len(right)
        exact += int(distance == 0)
    return {
        "token_error_rate": edits / max(target_tokens, 1),
        "edit_distance": edits,
        "teacher_tokens": target_tokens,
        "exact_sequence_rate": exact / len(targets),
        "exact_sequences": exact,
        "sequences": len(targets),
    }


def word_sequence_metrics(
    probabilities: np.ndarray,
    word_targets: np.ndarray,
    word_target_lengths: np.ndarray,
    labels: np.ndarray,
) -> dict[str, object]:
    student_targets, student_lengths = ctc_target_arrays(probabilities)
    targets = np.asarray(word_targets)
    lengths = np.asarray(word_target_lengths).reshape(-1)
    label_values = np.asarray(labels).reshape(-1)
    if not (
        len(student_targets) == len(targets) == len(lengths) == len(label_values)
    ):
        raise ValueError("mdtc_distillation_v2_word_metric_shape_invalid")
    positive_total = positive_found = confusable_total = confusable_found = 0
    names = tuple(WORD_CLASS_SEQUENCES)
    by_class = {
        name: {"found": 0, "total": 0}
        for name in names
    }
    for student, student_length, target, target_length, label in zip(
        student_targets,
        student_lengths,
        targets,
        lengths,
        label_values,
        strict=True,
    ):
        length = int(target_length)
        if not length:
            continue
        sequence = tuple(int(value) for value in target[:length])
        path = tuple(int(value) for value in student[: int(student_length)])
        found = any(
            path[start : start + length] == sequence
            for start in range(len(path) - length + 1)
        )
        class_id = _word_class_id_for_sequence(sequence)
        if class_id is None:
            raise ValueError("mdtc_distillation_v2_word_metric_class_unknown")
        class_metrics = by_class[names[class_id - 1]]
        class_metrics["total"] += 1
        class_metrics["found"] += int(found)
        if int(label) == 1:
            positive_total += 1
            positive_found += int(found)
        else:
            confusable_total += 1
            confusable_found += int(found)
    positive_recall = positive_found / max(positive_total, 1)
    confusable_recall = confusable_found / max(confusable_total, 1)
    recall_by_class = {
        name: values["found"] / max(values["total"], 1)
        for name, values in by_class.items()
        if values["total"]
    }
    return {
        "positive_sequence_recall": positive_recall,
        "positive_sequences_found": positive_found,
        "positive_sequences_total": positive_total,
        "confusable_sequence_recall": confusable_recall,
        "confusable_sequences_found": confusable_found,
        "confusable_sequences_total": confusable_total,
        "macro_word_sequence_recall": (positive_recall + confusable_recall) / 2.0,
        "minimum_word_sequence_recall": min(positive_recall, confusable_recall),
        "recall_by_word_class": recall_by_class,
        "counts_by_word_class": by_class,
        "macro_word_class_recall": sum(recall_by_class.values()) / len(recall_by_class),
        "minimum_word_class_recall": min(recall_by_class.values()),
    }


def transformed_external_spans(
    teacher_record: dict[str, object],
    *,
    window_end_seconds: float,
) -> tuple[tuple[tuple[int, int, str], ...], tuple[tuple[int, int], ...]]:
    values = teacher_record.get("verifier_locators")
    if not isinstance(values, list):
        return (), ()
    window_start = float(window_end_seconds) - WINDOW_SECONDS
    lexical = []
    veto = []
    for locator in values:
        if not isinstance(locator, dict):
            continue
        absolute_start = float(locator["locator_start_seconds"])
        absolute_end = float(locator["locator_end_seconds"])
        if absolute_start < window_start or absolute_end > window_end_seconds:
            continue
        start = max(0, math.floor((absolute_start - window_start) / FRAME_SECONDS))
        end = min(99, math.ceil((absolute_end - window_start) / FRAME_SECONDS))
        if start >= end:
            continue
        if bool(locator.get("multiword_non_target_veto")):
            veto.append((start, end))
        if locator.get("source") == "parakeet_lexical_proposal":
            lexical.append((start, end, "parakeet_lexical_proposal"))
    return tuple(lexical), tuple(veto)


def score_student_cascade(
    *,
    development_probabilities: np.ndarray,
    development_labels: np.ndarray,
    development_records: list[dict[str, object]],
    human_probabilities: np.ndarray,
    human_records: list[dict[str, object]],
    synthetic_negative_report: dict[str, object],
    human_teacher_report: dict[str, object],
) -> dict[str, object]:
    negative_values = synthetic_negative_report.get("records")
    human_values = human_teacher_report.get("records")
    if not isinstance(negative_values, list) or not isinstance(human_values, list):
        raise ValueError("mdtc_distillation_v2_cascade_records_missing")
    synthetic_by_file = {
        str(record.get("file")): record
        for record in negative_values
        if isinstance(record, dict)
    }
    human_by_path = {
        str(record.get("output_relative_path")): record
        for record in human_values
        if isinstance(record, dict)
    }
    negative_scores = []
    scored_negative_records = []
    for probability, label, record in zip(
        development_probabilities,
        development_labels,
        development_records,
        strict=True,
    ):
        relative_path = str(record.get("relative_path"))
        if int(label) != 0:
            continue
        lexical: tuple[tuple[int, int, str], ...] = ()
        veto: tuple[tuple[int, int], ...] = ()
        eligible = True
        source = synthetic_by_file.get(Path(relative_path).name)
        if int(label) == 0 and relative_path.startswith("negative_test/"):
            eligible = isinstance(source, dict) and bool(source.get("stage1_proposed"))
            stage2 = source.get("stage2") if isinstance(source, dict) else None
            locators = stage2.get("locators") if isinstance(stage2, dict) else None
            if isinstance(locators, list):
                veto = tuple(
                    (int(value["locator_start_frame"]), int(value["locator_end_frame"]))
                    for value in locators
                    if isinstance(value, dict)
                    and bool(value.get("multiword_non_target_veto"))
                )
        if not eligible:
            continue
        scored = score_category_probabilities(
            probability, lexical_locators=lexical, veto_spans=veto
        )
        best = scored.get("best_verifier")
        margin = float(best["margin"]) if isinstance(best, dict) else None
        if int(label) == 0:
            if margin is not None:
                negative_scores.append(margin)
                scored_negative_records.append(
                    {"relative_path": relative_path, "margin": margin}
                )
    maximum_negative = max(negative_scores, default=-math.inf)
    threshold = (
        float(np.nextafter(maximum_negative, math.inf))
        if negative_scores
        else 0.5
    )
    clip_windows: dict[tuple[str, str], list[float]] = {}
    for probability, record in zip(human_probabilities, human_records, strict=True):
        relative_path = str(record.get("relative_path"))
        teacher_record = human_by_path.get(relative_path)
        if not isinstance(teacher_record, dict):
            raise ValueError(f"mdtc_distillation_v2_human_teacher_missing:{relative_path}")
        key = (relative_path, str(record.get("clip_label")))
        clip_windows.setdefault(key, [])
        if not bool(teacher_record.get("stage1_proposed")):
            continue
        lexical, veto = transformed_external_spans(
            teacher_record,
            window_end_seconds=float(record["window_end_seconds"]),
        )
        scored = score_category_probabilities(
            probability, lexical_locators=lexical, veto_spans=veto
        )
        best = scored.get("best_verifier")
        if isinstance(best, dict):
            clip_windows[key].append(float(best["margin"]))
    clips = []
    for (relative_path, label), scores in clip_windows.items():
        score = max(scores) if scores else None
        clips.append(
            {
                "relative_path": relative_path,
                "label": label,
                "score": score,
                "detected": bool(score is not None and score >= threshold),
            }
        )
    positive = [clip for clip in clips if clip["label"] == "positive"]
    hard_negative = [clip for clip in clips if clip["label"] == "hard_negative"]
    positive_values = np.asarray(
        [float(clip["score"]) if clip["score"] is not None else threshold - 100.0 for clip in positive]
    )
    negative_values_array = np.asarray(
        [float(clip["score"]) if clip["score"] is not None else threshold - 100.0 for clip in hard_negative]
    )
    return {
        "operating_point": {
            "selection": "nextafter_maximum_scored_stage1_development_negative_margin",
            "threshold": threshold,
            "maximum_negative_margin": maximum_negative if negative_scores else None,
            "development_negative_locators_scored": len(negative_scores),
            "development_negative_false_accepts": 0,
        },
        "synthetic_positive": {
            "evaluated": False,
            "reason": "not_part_of_stage2_negative_calibration_or_human_validation",
        },
        "human_development_unseen": {
            "positive_accepted": sum(bool(clip["detected"]) for clip in positive),
            "positive_total": len(positive),
            "hard_negative_false_accepts": sum(bool(clip["detected"]) for clip in hard_negative),
            "hard_negative_total": len(hard_negative),
            "margin_auc": roc_auc(positive_values, negative_values_array),
            "clips": clips,
        },
        "top_development_negative_locators": sorted(
            scored_negative_records, key=lambda item: float(item["margin"]), reverse=True
        )[:20],
    }


def run(
    *,
    feature_manifest_path: Path,
    teacher_manifest_path: Path,
    synthetic_negative_report_path: Path,
    human_teacher_report_path: Path,
    wekws_directory: Path,
    output_directory: Path,
    architecture_type: str,
    hidden_dimension: int,
    stack_count: int,
    stack_size: int,
    kernel_size: int,
    recurrent_layers: int,
    delay_frames: int,
    epochs: int,
    patience: int,
    minimum_epochs: int,
    batch_size: int,
    learning_rate: float,
    speech_frame_weight: float,
    hard_loss_weight: float,
    ctc_loss_weight: float,
    word_ctc_loss_weight: float,
    confusable_word_weight: float,
    balance_word_classes: bool,
    teacher_align_word_spans: bool,
    word_alignment_cache_path: Path | None,
    seed: int,
    device: str,
) -> dict[str, object]:
    if min(hidden_dimension, stack_count, stack_size, kernel_size, recurrent_layers, epochs, patience, minimum_epochs, batch_size) <= 0:
        raise ValueError("mdtc_distillation_v2_schedule_invalid")
    if minimum_epochs > epochs:
        raise ValueError("mdtc_distillation_v2_minimum_epochs_invalid")
    if (
        learning_rate <= 0
        or speech_frame_weight < 1
        or hard_loss_weight < 0
        or ctc_loss_weight < 0
        or word_ctc_loss_weight < 0
        or confusable_word_weight < 1
    ):
        raise ValueError("mdtc_distillation_v2_optimization_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    teacher_manifest_path = teacher_manifest_path.resolve(strict=True)
    synthetic_negative_report_path = synthetic_negative_report_path.resolve(strict=True)
    human_teacher_report_path = human_teacher_report_path.resolve(strict=True)
    wekws_directory = wekws_directory.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"mdtc_distillation_v2_output_exists:{output_directory}")
    feature_manifest = read_json(feature_manifest_path)
    teacher_manifest = read_json(teacher_manifest_path)
    negative_report = read_json(synthetic_negative_report_path)
    human_teacher_report = read_json(human_teacher_report_path)
    if feature_manifest.get("schema") != "baxy.mdtc-phonetic-ctc-fbank-features.v1":
        raise ValueError("unsupported_mdtc_distillation_v2_feature_schema")
    if teacher_manifest.get("schema") != "baxy.phoneme-teacher-maxout-posteriors.v2":
        raise ValueError("unsupported_mdtc_distillation_v2_teacher_schema")
    if negative_report.get("schema") != "baxy.livekit-negative-ctc-cascade-development.v1":
        raise ValueError("unsupported_mdtc_distillation_v2_negative_schema")
    if human_teacher_report.get("schema") != "baxy.ccby-wake-ctc-cascade-development.v1":
        raise ValueError("unsupported_mdtc_distillation_v2_human_schema")
    teacher_sources = teacher_manifest.get("sources")
    if not isinstance(teacher_sources, dict) or teacher_sources.get(
        "feature_manifest_sha256"
    ) != sha256(feature_manifest_path):
        raise ValueError("mdtc_distillation_v2_teacher_feature_mismatch")
    if any(
        value.get("blind_human_partition_accessed") is not False
        for value in (feature_manifest, teacher_manifest, negative_report, human_teacher_report)
    ):
        raise ValueError("mdtc_distillation_v2_blind_boundary_invalid")
    train_features, train_labels, train_records = load_partition(
        feature_manifest, "base_train"
    )
    development_features, development_labels, development_records = load_partition(
        feature_manifest, "base_development"
    )
    human_features, _, human_records = load_partition(
        feature_manifest, "human_development"
    )
    train_teacher = load_teacher_partition(
        teacher_manifest, "base_train", len(train_features)
    )
    development_teacher = load_teacher_partition(
        teacher_manifest, "base_development", len(development_features)
    )
    train_ctc_targets, train_ctc_lengths = ctc_target_arrays(train_teacher)
    development_ctc_targets, development_ctc_lengths = ctc_target_arrays(
        development_teacher
    )
    train_word_targets, train_word_lengths, train_word_weights = word_target_arrays(
        train_records,
        train_labels,
        confusable_weight=confusable_word_weight,
    )
    development_word_targets, development_word_lengths, development_word_weights = word_target_arrays(
        development_records,
        development_labels,
        confusable_weight=confusable_word_weight,
    )
    train_word_span_starts = np.zeros(len(train_features), dtype=np.int64)
    train_word_span_ends = np.full(len(train_features), train_teacher.shape[1], dtype=np.int64)
    development_word_span_starts = np.zeros(len(development_features), dtype=np.int64)
    development_word_span_ends = np.full(
        len(development_features), development_teacher.shape[1], dtype=np.int64
    )
    word_span_alignment = None
    if teacher_align_word_spans:
        feature_hash = sha256(feature_manifest_path)
        teacher_hash = sha256(teacher_manifest_path)
        cache_path = (
            word_alignment_cache_path.resolve()
            if word_alignment_cache_path is not None
            else None
        )
        if cache_path is not None and cache_path.exists():
            train_alignment, development_alignment, word_span_alignment = (
                load_word_alignment_cache(
                    cache_path,
                    feature_manifest_sha256=feature_hash,
                    teacher_manifest_sha256=teacher_hash,
                    train_count=len(train_features),
                    development_count=len(development_features),
                )
            )
            (
                train_word_targets,
                train_word_lengths,
                train_word_span_starts,
                train_word_span_ends,
            ) = train_alignment
            (
                development_word_targets,
                development_word_lengths,
                development_word_span_starts,
                development_word_span_ends,
            ) = development_alignment
        else:
            (
                train_word_targets,
                train_word_lengths,
                train_word_span_starts,
                train_word_span_ends,
                train_report,
            ) = teacher_aligned_word_targets(train_teacher, train_records, train_labels)
            (
                development_word_targets,
                development_word_lengths,
                development_word_span_starts,
                development_word_span_ends,
                development_report,
            ) = teacher_aligned_word_targets(
                development_teacher, development_records, development_labels
            )
            word_span_alignment = {
                **train_report,
                "development": development_report,
            }
            if cache_path is not None:
                write_word_alignment_cache(
                    cache_path,
                    feature_manifest_sha256=feature_hash,
                    teacher_manifest_sha256=teacher_hash,
                    train_values=(
                        train_word_targets,
                        train_word_lengths,
                        train_word_span_starts,
                        train_word_span_ends,
                    ),
                    development_values=(
                        development_word_targets,
                        development_word_lengths,
                        development_word_span_starts,
                        development_word_span_ends,
                    ),
                    report=word_span_alignment,
                )
        if cache_path is not None:
            word_span_alignment["cache"] = {
                "path": cache_path.as_posix(),
                "sha256": sha256(cache_path),
            }
    word_class_balance = None
    if balance_word_classes:
        train_word_weights, word_class_balance = balanced_word_class_weights(
            word_class_ids(train_records, train_labels)
        )
        development_word_weights, development_word_class_balance = balanced_word_class_weights(
            word_class_ids(development_records, development_labels)
        )
        word_class_balance["development"] = development_word_class_balance
    train_output = teacher_manifest.get("outputs", {}).get("base_train", {})
    if not isinstance(train_output, dict) or not isinstance(
        train_output.get("hard_category_counts"), list
    ):
        raise ValueError("mdtc_distillation_v2_teacher_counts_missing")
    weight_values = category_weights(train_output["hard_category_counts"])

    sys.path.insert(0, str(wekws_directory))
    import torch
    from wekws.model.mdtc import MDTC

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda_requested_but_unavailable")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    model = build_model(
        torch,
        MDTC,
        architecture_type=architecture_type,
        hidden_dimension=hidden_dimension,
        stack_count=stack_count,
        stack_size=stack_size,
        kernel_size=kernel_size,
        recurrent_layers=recurrent_layers,
    ).to(device)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=5e-5)
    class_weights_tensor = torch.from_numpy(weight_values).to(device)
    generator = torch.Generator().manual_seed(seed)
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.from_numpy(train_features),
            torch.from_numpy(train_teacher),
            torch.from_numpy(train_ctc_targets),
            torch.from_numpy(train_ctc_lengths),
            torch.from_numpy(train_word_targets),
            torch.from_numpy(train_word_lengths),
            torch.from_numpy(train_word_weights),
            torch.from_numpy(train_word_span_starts),
            torch.from_numpy(train_word_span_ends),
        ),
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        generator=generator,
    )
    best_key = None
    best_state = None
    best_epoch = None
    history = []
    stale = 0
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss_sum = 0.0
        train_count = 0
        for (
            features,
            teacher,
            targets,
            target_lengths,
            word_targets,
            word_lengths,
            word_weights,
            word_span_starts,
            word_span_ends,
        ) in loader:
            features = features.to(device)
            teacher = teacher.to(device)
            targets = targets.to(device)
            target_lengths = target_lengths.to(device)
            word_targets = word_targets.to(device)
            word_lengths = word_lengths.to(device)
            word_weights = word_weights.to(device)
            word_span_starts = word_span_starts.to(device)
            word_span_ends = word_span_ends.to(device)
            optimizer.zero_grad(set_to_none=True)
            losses = hybrid_losses(
                torch,
                model(features),
                teacher,
                targets,
                target_lengths,
                word_targets,
                word_lengths,
                word_weights,
                word_span_starts,
                word_span_ends,
                delay_frames=delay_frames,
                speech_frame_weight=speech_frame_weight,
                hard_loss_weight=hard_loss_weight,
                ctc_loss_weight=ctc_loss_weight,
                word_ctc_loss_weight=word_ctc_loss_weight,
                class_weights=class_weights_tensor,
            )
            loss = losses.mean()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            train_loss_sum += float(loss.detach().cpu()) * len(features)
            train_count += len(features)
        development_probabilities = predict_probabilities(
            torch,
            model,
            development_features,
            device=device,
            batch_size=batch_size,
        )
        metrics = frame_metrics(
            development_probabilities,
            development_teacher,
            delay_frames=delay_frames,
        )
        sequence_metrics = ctc_sequence_metrics(
            development_probabilities,
            development_ctc_targets,
            development_ctc_lengths,
        )
        word_metrics = word_sequence_metrics(
            development_probabilities,
            development_word_targets,
            development_word_lengths,
            development_labels,
        )
        model.eval()
        development_loss_sum = 0.0
        with torch.inference_mode():
            for start in range(0, len(development_features), batch_size):
                features = torch.from_numpy(
                    development_features[start : start + batch_size]
                ).to(device)
                teacher = torch.from_numpy(
                    development_teacher[start : start + batch_size]
                ).to(device)
                targets = torch.from_numpy(
                    development_ctc_targets[start : start + batch_size]
                ).to(device)
                target_lengths = torch.from_numpy(
                    development_ctc_lengths[start : start + batch_size]
                ).to(device)
                word_targets = torch.from_numpy(
                    development_word_targets[start : start + batch_size]
                ).to(device)
                word_lengths = torch.from_numpy(
                    development_word_lengths[start : start + batch_size]
                ).to(device)
                word_weights = torch.from_numpy(
                    development_word_weights[start : start + batch_size]
                ).to(device)
                word_span_starts = torch.from_numpy(
                    development_word_span_starts[start : start + batch_size]
                ).to(device)
                word_span_ends = torch.from_numpy(
                    development_word_span_ends[start : start + batch_size]
                ).to(device)
                development_loss_sum += float(
                    hybrid_losses(
                        torch,
                        model(features),
                        teacher,
                        targets,
                        target_lengths,
                        word_targets,
                        word_lengths,
                        word_weights,
                        word_span_starts,
                        word_span_ends,
                        delay_frames=delay_frames,
                        speech_frame_weight=speech_frame_weight,
                        hard_loss_weight=hard_loss_weight,
                        ctc_loss_weight=ctc_loss_weight,
                        word_ctc_loss_weight=word_ctc_loss_weight,
                        class_weights=class_weights_tensor,
                    ).sum().cpu()
                )
        epoch_record = {
            "epoch": epoch,
            "train_loss": train_loss_sum / train_count,
            "development_loss": development_loss_sum / len(development_features),
            "development_frame_metrics": metrics,
            "development_ctc_sequence_metrics": sequence_metrics,
            "development_word_sequence_metrics": word_metrics,
        }
        history.append(epoch_record)
        key = (
            float(
                word_metrics[
                    "minimum_word_class_recall"
                    if balance_word_classes
                    else "minimum_word_sequence_recall"
                ]
            ),
            float(word_metrics["macro_word_class_recall"]),
            float(word_metrics["macro_word_sequence_recall"]),
            float(word_metrics["confusable_sequence_recall"]),
            float(word_metrics["positive_sequence_recall"]),
            -float(sequence_metrics["token_error_rate"]),
            -float(epoch_record["development_loss"]),
        ) if word_ctc_loss_weight else (
            -float(sequence_metrics["token_error_rate"]),
            float(sequence_metrics["exact_sequence_rate"]),
            float(metrics["macro_observed_speech_recall"]),
            -float(epoch_record["development_loss"]),
        ) if ctc_loss_weight else (
            float(metrics["macro_observed_speech_recall"]),
            float(metrics["nonblank_frame_accuracy"]),
            -float(epoch_record["development_loss"]),
        )
        if best_key is None or key > best_key:
            best_key = key
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
            best_epoch = epoch_record
            stale = 0
        else:
            stale += 1
        print(
            f"EPOCH|{epoch}/{epochs}|word={word_metrics['macro_word_sequence_recall']:.6f}|target={word_metrics['positive_sequence_recall']:.6f}|rival={word_metrics['confusable_sequence_recall']:.6f}|ter={sequence_metrics['token_error_rate']:.6f}|exact={sequence_metrics['exact_sequence_rate']:.6f}|macro={metrics['macro_observed_speech_recall']:.6f}|nonblank={metrics['nonblank_frame_accuracy']:.6f}|loss={epoch_record['development_loss']:.6f}",
            flush=True,
        )
        if epoch >= minimum_epochs and stale >= patience:
            break
    if best_state is None or best_epoch is None:
        raise RuntimeError("mdtc_distillation_v2_no_best_state")
    model.load_state_dict(best_state)
    model.eval()
    output_directory.mkdir(parents=True)
    checkpoint_path = output_directory / "mdtc_phoneme_distilled_student_v2.pt"
    torch.save(best_state, checkpoint_path)
    development_probabilities = predict_probabilities(
        torch, model, development_features, device=device, batch_size=batch_size
    )
    human_probabilities = predict_probabilities(
        torch, model, human_features, device=device, batch_size=batch_size
    )
    cascade = score_student_cascade(
        development_probabilities=development_probabilities,
        development_labels=development_labels,
        development_records=development_records,
        human_probabilities=human_probabilities,
        human_records=human_records,
        synthetic_negative_report=negative_report,
        human_teacher_report=human_teacher_report,
    )
    commit = subprocess.run(
        ["git", "-C", str(wekws_directory), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    human_metrics = cascade["human_development_unseen"]
    report: dict[str, object] = {
        "schema": "baxy.mdtc-phoneme-distillation-development.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_lossless_teacher_distillation_without_human_training",
        "architecture": {
            "frontend": "80_bin_kaldi_fbank_downsampled_20ms",
            "classifier": f"{architecture_type}_18_category_maxout_teacher_student",
            "architecture_type": architecture_type,
            "causal": bool(model.causal),
            "hidden_dimension": hidden_dimension,
            "stack_count": stack_count,
            "stack_size": stack_size,
            "kernel_size": kernel_size,
            "recurrent_layers": recurrent_layers,
            "parameters": parameter_count,
            "receptive_field_frames": int(model.receptive_field_frames),
            "teacher_delay_frames": delay_frames,
            "teacher_delay_milliseconds": delay_frames * 20,
        },
        "sources": {
            "feature_manifest": feature_manifest_path.as_posix(),
            "feature_manifest_sha256": sha256(feature_manifest_path),
            "teacher_manifest": teacher_manifest_path.as_posix(),
            "teacher_manifest_sha256": sha256(teacher_manifest_path),
            "synthetic_negative_report": synthetic_negative_report_path.as_posix(),
            "synthetic_negative_report_sha256": sha256(synthetic_negative_report_path),
            "human_teacher_report": human_teacher_report_path.as_posix(),
            "human_teacher_report_sha256": sha256(human_teacher_report_path),
            "wekws_directory": wekws_directory.as_posix(),
            "wekws_commit": commit,
            "wekws_license_sha256": sha256(wekws_directory / "LICENSE"),
            "wekws_mdtc_source_sha256": sha256(wekws_directory / "wekws" / "model" / "mdtc.py"),
            "trainer_source_sha256": sha256(Path(__file__).resolve()),
        },
        "training": {
            "epochs_requested": epochs,
            "epochs_completed": len(history),
            "patience": patience,
            "minimum_epochs": minimum_epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "speech_frame_weight": speech_frame_weight,
            "hard_loss_weight": hard_loss_weight,
            "ctc_loss_weight": ctc_loss_weight,
            "word_ctc_loss_weight": word_ctc_loss_weight,
            "confusable_word_weight": confusable_word_weight,
            "balance_word_classes": balance_word_classes,
            "word_class_balance": word_class_balance,
            "teacher_align_word_spans": teacher_align_word_spans,
            "word_alignment_cache": (
                word_alignment_cache_path.resolve().as_posix()
                if word_alignment_cache_path is not None
                else None
            ),
            "word_span_alignment": word_span_alignment,
            "category_weights": weight_values.tolist(),
            "seed": seed,
            "device": device,
            "seconds": time.perf_counter() - started,
            "best_epoch": best_epoch,
            "history": history,
        },
        "artifacts": {
            "checkpoint": checkpoint_path.as_posix(),
            "checkpoint_sha256": sha256(checkpoint_path),
            "checkpoint_bytes": checkpoint_path.stat().st_size,
        },
        "cascade_development": cascade,
        "development_gate_passed": (
            human_metrics["positive_accepted"] == human_metrics["positive_total"]
            and human_metrics["hard_negative_false_accepts"] == 0
            and cascade["operating_point"]["development_negative_false_accepts"] == 0
        ),
        "human_development_used_for_training": False,
        "candidate_development_use": True,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    report_path = output_directory / "development_report.v1.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--teacher-manifest", type=Path, required=True)
    parser.add_argument("--synthetic-negative-report", type=Path, required=True)
    parser.add_argument("--human-teacher-report", type=Path, required=True)
    parser.add_argument("--wekws-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--architecture",
        choices=("causal_mdtc", "bidirectional_gru"),
        default="causal_mdtc",
    )
    parser.add_argument("--hidden-dimension", type=int, default=64)
    parser.add_argument("--stack-count", type=int, default=3)
    parser.add_argument("--stack-size", type=int, default=4)
    parser.add_argument("--kernel-size", type=int, default=5)
    parser.add_argument("--recurrent-layers", type=int, default=2)
    parser.add_argument("--delay-frames", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--minimum-epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--speech-frame-weight", type=float, default=16.0)
    parser.add_argument("--hard-loss-weight", type=float, default=1.0)
    parser.add_argument("--ctc-loss-weight", type=float, default=0.0)
    parser.add_argument("--word-ctc-loss-weight", type=float, default=0.0)
    parser.add_argument("--confusable-word-weight", type=float, default=16.0)
    parser.add_argument("--balance-word-classes", action="store_true")
    parser.add_argument("--teacher-align-word-spans", action="store_true")
    parser.add_argument("--word-alignment-cache", type=Path)
    parser.add_argument("--seed", type=int, default=20260804)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(
        feature_manifest_path=args.feature_manifest,
        teacher_manifest_path=args.teacher_manifest,
        synthetic_negative_report_path=args.synthetic_negative_report,
        human_teacher_report_path=args.human_teacher_report,
        wekws_directory=args.wekws_dir,
        output_directory=args.output_dir,
        architecture_type=args.architecture,
        hidden_dimension=args.hidden_dimension,
        stack_count=args.stack_count,
        stack_size=args.stack_size,
        kernel_size=args.kernel_size,
        recurrent_layers=args.recurrent_layers,
        delay_frames=args.delay_frames,
        epochs=args.epochs,
        patience=args.patience,
        minimum_epochs=args.minimum_epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        speech_frame_weight=args.speech_frame_weight,
        hard_loss_weight=args.hard_loss_weight,
        ctc_loss_weight=args.ctc_loss_weight,
        word_ctc_loss_weight=args.word_ctc_loss_weight,
        confusable_word_weight=args.confusable_word_weight,
        balance_word_classes=args.balance_word_classes,
        teacher_align_word_spans=args.teacher_align_word_spans,
        word_alignment_cache_path=args.word_alignment_cache,
        seed=args.seed,
        device=args.device,
    )
    print(
        json.dumps(
            {
                "gate": report["development_gate_passed"],
                "cascade": report["cascade_development"],
                "checkpoint": report["artifacts"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
