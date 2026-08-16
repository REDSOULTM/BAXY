"""Tune a phoneme-CTC hypothesis cascade on train-only MSWC research words."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_qbye_ctc_tuning_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_TUNING = load_component(
    "evaluate_mswc_spanish_qbye_sequence_tuning_v3.py",
    "_baxy_qbye_ctc_tuning_base_v3",
)
_BASELINE = load_component(
    "evaluate_mswc_spanish_qbye_ssl_baseline_v1.py",
    "_baxy_qbye_ctc_tuning_hash_v3",
)


def batch_ctc_sequence_log_probabilities(
    log_probabilities: np.ndarray,
    sequences: list[list[int]],
    blank_id: int,
) -> np.ndarray:
    values = np.asarray(log_probabilities, dtype=np.float64)
    if (
        values.ndim != 2
        or not len(values)
        or not values.shape[1]
        or not np.isfinite(values).all()
        or not 0 <= blank_id < values.shape[1]
    ):
        raise ValueError("mswc_qbye_ctc_tuning_log_probabilities_invalid")
    results = np.full(len(sequences), -np.inf, dtype=np.float64)
    valid_indexes = [
        index
        for index, sequence in enumerate(sequences)
        if sequence
        and all(0 <= int(token) < values.shape[1] and int(token) != blank_id for token in sequence)
    ]
    if not valid_indexes:
        return results
    active = [[int(token) for token in sequences[index]] for index in valid_indexes]
    state_lengths = np.asarray([2 * len(sequence) + 1 for sequence in active], dtype=np.int64)
    maximum_states = int(state_lengths.max())
    states = np.full((len(active), maximum_states), blank_id, dtype=np.int64)
    valid_states = np.zeros_like(states, dtype=np.bool_)
    for row, sequence in enumerate(active):
        length = state_lengths[row]
        valid_states[row, :length] = True
        for label_index, token in enumerate(sequence):
            states[row, 2 * label_index + 1] = token
    skip_allowed = np.zeros_like(valid_states)
    if maximum_states > 2:
        skip_allowed[:, 2:] = (
            valid_states[:, 2:]
            & (states[:, 2:] != blank_id)
            & (states[:, 2:] != states[:, :-2])
        )
    previous = np.full_like(states, -np.inf, dtype=np.float64)
    previous[:, 0] = values[0, blank_id]
    previous[:, 1] = values[0, states[:, 1]]
    previous[~valid_states] = -np.inf
    for frame in range(1, len(values)):
        total = previous.copy()
        from_previous = np.full_like(previous, -np.inf)
        from_previous[:, 1:] = previous[:, :-1]
        total = np.logaddexp(total, from_previous)
        from_skip = np.full_like(previous, -np.inf)
        from_skip[:, 2:] = previous[:, :-2]
        total = np.logaddexp(total, np.where(skip_allowed, from_skip, -np.inf))
        emissions = values[frame, states]
        previous = np.where(valid_states, total + emissions, -np.inf)
    row_indexes = np.arange(len(active))
    final = previous[row_indexes, state_lengths - 1]
    penultimate = previous[row_indexes, state_lengths - 2]
    results[valid_indexes] = np.logaddexp(final, penultimate)
    return results


def ctc_shortlist_matrix(
    *,
    ctc_log_probabilities: np.ndarray,
    offsets: np.ndarray,
    query_indexes: list[int],
    edit_scores: np.ndarray,
    class_names: list[str],
    enrollment_sequences_by_class: dict[str, list[list[int]]],
    blank_id: int,
    maximum_shortlist: int,
) -> tuple[np.ndarray, np.ndarray]:
    if maximum_shortlist < 1 or maximum_shortlist > len(class_names):
        raise ValueError("mswc_qbye_ctc_tuning_shortlist_invalid")
    ctc_scores = np.full_like(edit_scores, -100.0, dtype=np.float64)
    shortlisted = np.zeros_like(edit_scores, dtype=np.bool_)
    for query_row, record_index in enumerate(query_indexes):
        selected = np.argpartition(
            edit_scores[query_row], -maximum_shortlist
        )[-maximum_shortlist:]
        selected = selected[np.argsort(edit_scores[query_row, selected])[::-1]]
        sequences = []
        owners = []
        for class_index in selected:
            for sequence in enrollment_sequences_by_class[class_names[int(class_index)]]:
                sequences.append(sequence)
                owners.append(int(class_index))
        start = int(offsets[record_index])
        end = int(offsets[record_index + 1])
        raw_scores = batch_ctc_sequence_log_probabilities(
            np.asarray(ctc_log_probabilities[start:end], dtype=np.float32),
            sequences,
            blank_id,
        ) / max(end - start, 1)
        for class_index in selected:
            values = [
                score
                for score, owner in zip(raw_scores, owners, strict=True)
                if owner == int(class_index)
            ]
            finite = [float(value) for value in values if np.isfinite(value)]
            ctc_scores[query_row, int(class_index)] = max(finite) if finite else -100.0
            shortlisted[query_row, int(class_index)] = True
    return ctc_scores, shortlisted


def evaluate(
    *,
    feature_manifest_path: Path,
    output_path: Path,
    split_seed: int,
    tuning_classes: int,
    maximum_shortlist: int,
) -> dict[str, object]:
    started = time.perf_counter()
    if output_path.exists():
        raise ValueError("mswc_qbye_ctc_tuning_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    output_path = output_path.resolve()
    manifest = _TUNING.read_object(feature_manifest_path)
    records_raw = manifest.get("records")
    files = manifest.get("files")
    contract = manifest.get("contract")
    if (
        manifest.get("schema") != "baxy.mswc-spanish-qbye-sequence-features.v3"
        or manifest.get("official_test_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(records_raw, list)
        or not isinstance(files, dict)
        or not isinstance(contract, dict)
    ):
        raise ValueError("mswc_qbye_ctc_tuning_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict) or not isinstance(
            record.get("greedy_ctc_token_ids"), list
        ):
            raise ValueError("mswc_qbye_ctc_tuning_record_invalid")
        records.append(record)
    words = {str(record["class_name"]) for record in records}
    tuning_words, reserved_words = _TUNING.split_research_words(
        words, seed=split_seed, tuning_classes=tuning_classes
    )
    enrollment_indexes = [
        index
        for index, record in enumerate(records)
        if record["partition"] == "open_keyword_enrollment"
        and str(record["class_name"]) in tuning_words
    ]
    query_indexes = [
        index
        for index, record in enumerate(records)
        if record["partition"] == "open_keyword_query"
        and str(record["class_name"]) in tuning_words
    ]
    class_names = sorted(tuning_words)
    enrollment_classes = [str(records[index]["class_name"]) for index in enrollment_indexes]
    query_classes = [str(records[index]["class_name"]) for index in query_indexes]
    if len(enrollment_indexes) != tuning_classes * 2 or len(query_indexes) != tuning_classes * 6:
        raise ValueError("mswc_qbye_ctc_tuning_partition_invalid")
    enrollment_sequences = [
        [int(value) for value in records[index]["greedy_ctc_token_ids"]]
        for index in enrollment_indexes
    ]
    query_sequences = [
        [int(value) for value in records[index]["greedy_ctc_token_ids"]]
        for index in query_indexes
    ]
    edit_scores = _TUNING.edit_score_matrix(
        enrollment_sequences=enrollment_sequences,
        enrollment_classes=enrollment_classes,
        query_sequences=query_sequences,
        class_names=class_names,
        aggregation="maximum",
    )
    enrollment_sequences_by_class = {
        name: [
            sequence
            for sequence, class_name in zip(
                enrollment_sequences, enrollment_classes, strict=True
            )
            if class_name == name
        ]
        for name in class_names
    }
    root = feature_manifest_path.parent
    offset_path = root / str(files["offsets"])
    ctc_descriptor = files.get("ctc_log_probabilities")
    if (
        not isinstance(ctc_descriptor, dict)
        or _BASELINE.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("mswc_qbye_ctc_tuning_files_invalid")
    ctc_path = root / str(ctc_descriptor["path"])
    if _BASELINE.sha256(ctc_path) != ctc_descriptor.get("sha256"):
        raise ValueError("mswc_qbye_ctc_tuning_logprob_hash_mismatch")
    offsets = np.load(offset_path)
    ctc_log_probabilities = np.load(ctc_path, mmap_mode="r")
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(ctc_log_probabilities):
        raise ValueError("mswc_qbye_ctc_tuning_feature_shape_invalid")
    ctc_scores, maximum_mask = ctc_shortlist_matrix(
        ctc_log_probabilities=ctc_log_probabilities,
        offsets=offsets,
        query_indexes=query_indexes,
        edit_scores=edit_scores,
        class_names=class_names,
        enrollment_sequences_by_class=enrollment_sequences_by_class,
        blank_id=int(contract["ctc_blank_id"]),
        maximum_shortlist=maximum_shortlist,
    )
    class_to_index = {name: index for index, name in enumerate(class_names)}
    targets = np.asarray([class_to_index[name] for name in query_classes], dtype=np.int64)
    runs = []
    for shortlist in (5, 10, 20, 40):
        if shortlist > maximum_shortlist:
            continue
        active = np.zeros_like(maximum_mask)
        for row in range(len(edit_scores)):
            chosen = np.argpartition(edit_scores[row], -shortlist)[-shortlist:]
            active[row, chosen] = True
        proposal_recall = float(np.mean(active[np.arange(len(active)), targets]))
        for edit_weight in (0.0, 0.25, 0.5, 1.0, 2.0):
            scores = np.where(active, ctc_scores + edit_weight * edit_scores, -100.0)
            metrics = _TUNING.score_metrics(
                scores=scores,
                class_names=class_names,
                query_classes=query_classes,
            )
            runs.append(
                {
                    "method": "greedy_edit_shortlist_then_ctc_hypothesis_score",
                    "shortlist_classes": shortlist,
                    "edit_weight": edit_weight,
                    "proposal_recall": proposal_recall,
                    "metrics": metrics,
                }
            )
    viable = [
        run
        for run in runs
        if float(run["metrics"]["top1_accuracy"]) >= 0.85
        and float(run["metrics"]["pair_auc"]) >= 0.99
        and float(run["metrics"]["equal_error_rate"]) <= 0.05
    ]
    ranked = viable if viable else runs
    selected = max(
        ranked,
        key=lambda run: (
            int(run["metrics"]["true_pairs_accepted_at_zero_false_pairs"]),
            float(run["metrics"]["top1_accuracy"]),
            float(run["metrics"]["pair_auc"]),
            -float(run["metrics"]["equal_error_rate"]),
        ),
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-qbye-ctc-sequence-tuning.v3",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "train_split_only_tuning_of_greedy_shortlist_and_ctc_hypothesis_scoring",
        "sources": {"feature_manifest_sha256": _BASELINE.sha256(feature_manifest_path)},
        "contract": {
            "split_seed": split_seed,
            "tuning_word_classes": len(tuning_words),
            "reserved_word_classes": len(reserved_words),
            "maximum_shortlist": maximum_shortlist,
            "ctc_score_normalization": "exact_forward_log_probability_divided_by_query_frames",
            "enrollment_aggregation": "maximum_of_two_distinct_speaker_hypotheses",
            "non_proposed_score": -100.0,
            "selection_rank": "zero_false_recall_then_top1_then_auc_then_negative_eer_after_quality_floor",
        },
        "runs": runs,
        "selected": selected,
        "runtime_seconds": time.perf_counter() - started,
        "research_tuning_examples_scored": True,
        "research_reserved_examples_scored": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-seed", type=int, default=6501)
    parser.add_argument("--tuning-classes", type=int, default=400)
    parser.add_argument("--maximum-shortlist", type=int, default=40)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        feature_manifest_path=args.feature_manifest,
        output_path=args.output,
        split_seed=args.split_seed,
        tuning_classes=args.tuning_classes,
        maximum_shortlist=args.maximum_shortlist,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
