"""Evaluate Spanish text-to-CTC alignment on disjoint MSWC research words."""

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
        raise RuntimeError(f"mswc_text_ctc_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SEQUENCE = load_component(
    "evaluate_mswc_spanish_qbye_sequence_tuning_v3.py",
    "_baxy_text_ctc_sequence_v4",
)
_CTC = load_component(
    "evaluate_mswc_spanish_qbye_ctc_sequence_tuning_v3.py",
    "_baxy_text_ctc_forward_v4",
)
_PAIR = load_component(
    "train_mswc_spanish_qbye_similarity_cnn_v4.py",
    "_baxy_text_ctc_pairs_v4",
)
_METRICS = load_component(
    "evaluate_mswc_hyperspotter_spanish_tuning_v1.py",
    "_baxy_text_ctc_metrics_v4",
)
_HASH = load_component(
    "evaluate_mswc_spanish_qbye_ssl_baseline_v1.py",
    "_baxy_text_ctc_hash_v4",
)


def score_text_candidates(
    *,
    ctc_log_probabilities: np.ndarray,
    offsets: np.ndarray,
    query_indexes: list[int],
    candidate_indexes: np.ndarray,
    text_sequences: list[list[int]],
    blank_id: int,
) -> tuple[np.ndarray, np.ndarray]:
    candidates = np.asarray(candidate_indexes, dtype=np.int64)
    if (
        candidates.ndim != 2
        or len(candidates) != len(query_indexes)
        or candidates.size == 0
    ):
        raise ValueError("mswc_text_ctc_candidate_shape_invalid")
    scores = np.empty(candidates.shape, dtype=np.float64)
    lengths = np.empty(candidates.shape, dtype=np.float64)
    for row, record_index in enumerate(query_indexes):
        start = int(offsets[record_index])
        end = int(offsets[record_index + 1])
        sequences = [text_sequences[index] for index in candidates[row]]
        raw = _CTC.batch_ctc_sequence_log_probabilities(
            np.asarray(ctc_log_probabilities[start:end], dtype=np.float32),
            sequences,
            blank_id,
        )
        scores[row] = raw / max(end - start, 1)
        lengths[row] = [len(sequence) for sequence in sequences]
        if (row + 1) % 400 == 0 or row + 1 == len(query_indexes):
            print(f"TEXT_CTC_TUNING|{row + 1}/{len(query_indexes)}", flush=True)
    return scores, lengths


def evaluate(
    *,
    feature_manifest_path: Path,
    tokenizer_directory: Path,
    output_path: Path,
    split_seed: int,
    tuning_classes: int,
    hard_negative_candidates: int,
    phonemizer_language: str,
) -> dict[str, object]:
    started = time.perf_counter()
    if output_path.exists() or tuning_classes < 2 or hard_negative_candidates < 1:
        raise ValueError("mswc_text_ctc_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    tokenizer_directory = tokenizer_directory.resolve(strict=True)
    output_path = output_path.resolve()
    manifest = _SEQUENCE.read_object(feature_manifest_path)
    records_raw = manifest.get("records")
    files = manifest.get("files")
    contract = manifest.get("contract")
    sources = manifest.get("sources")
    if (
        manifest.get("schema") != "baxy.mswc-spanish-qbye-sequence-features.v3"
        or manifest.get("official_test_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(records_raw, list)
        or not isinstance(files, dict)
        or not isinstance(contract, dict)
        or not isinstance(sources, dict)
    ):
        raise ValueError("mswc_text_ctc_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_text_ctc_record_invalid")
        records.append(record)
    words = {str(record["class_name"]) for record in records}
    tuning_words, reserved_words = _SEQUENCE.split_research_words(
        words, seed=split_seed, tuning_classes=tuning_classes
    )
    query_indexes = [
        index
        for index, record in enumerate(records)
        if record.get("partition") == "open_keyword_query"
        and str(record["class_name"]) in tuning_words
    ]
    query_words = [str(records[index]["class_name"]) for index in query_indexes]
    if len(query_indexes) != tuning_classes * 6 or set(query_words) != tuning_words:
        raise ValueError("mswc_text_ctc_partition_invalid")
    class_names = sorted(tuning_words)
    class_to_index = {name: index for index, name in enumerate(class_names)}
    hard_negatives = _PAIR.hard_negative_map(
        tuning_words, neighbors=hard_negative_candidates
    )
    candidate_indexes = np.asarray(
        [
            [
                class_to_index[query_word],
                *[
                    class_to_index[word]
                    for word in hard_negatives[query_word][:hard_negative_candidates]
                ],
            ]
            for query_word in query_words
        ],
        dtype=np.int64,
    )
    root = feature_manifest_path.parent
    offset_path = root / str(files["offsets"])
    ctc_descriptor = files.get("ctc_log_probabilities")
    if (
        not isinstance(ctc_descriptor, dict)
        or _HASH.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("mswc_text_ctc_files_invalid")
    ctc_path = root / str(ctc_descriptor["path"])
    if _HASH.sha256(ctc_path) != ctc_descriptor.get("sha256"):
        raise ValueError("mswc_text_ctc_logprob_hash_mismatch")
    if _HASH.sha256(tokenizer_directory / "vocab.json") != sources.get(
        "model_vocabulary_sha256"
    ):
        raise ValueError("mswc_text_ctc_vocabulary_hash_mismatch")
    offsets = np.load(offset_path)
    ctc_log_probabilities = np.load(ctc_path, mmap_mode="r")
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(
        ctc_log_probabilities
    ):
        raise ValueError("mswc_text_ctc_feature_shape_invalid")

    from audit_voxcpm2_gguf_pilot import configure_espeak_backend

    espeak = configure_espeak_backend()
    if espeak is None:
        raise ValueError("mswc_text_ctc_espeak_unavailable")
    from transformers import Wav2Vec2PhonemeCTCTokenizer

    tokenizer = Wav2Vec2PhonemeCTCTokenizer.from_pretrained(
        str(tokenizer_directory),
        local_files_only=True,
        phonemizer_lang=phonemizer_language,
    )
    tokenized = tokenizer(class_names)["input_ids"]
    text_sequences = [[int(value) for value in sequence] for sequence in tokenized]
    if any(not sequence for sequence in text_sequences):
        raise ValueError("mswc_text_ctc_tokenization_empty")
    base_scores, token_lengths = score_text_candidates(
        ctc_log_probabilities=ctc_log_probabilities,
        offsets=offsets,
        query_indexes=query_indexes,
        candidate_indexes=candidate_indexes,
        text_sequences=text_sequences,
        blank_id=int(contract["ctc_blank_id"]),
    )
    runs = []
    for length_bonus in (-0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2):
        scores = base_scores + length_bonus * token_lengths
        metrics = _METRICS.hard_pair_metrics(
            scores=scores, query_words=query_words
        )
        zero_false_recall = (
            float(metrics["true_pairs_accepted_at_zero_false_pairs"])
            / float(metrics["true_pairs"])
        )
        runs.append(
            {
                "frame_normalized_token_length_bonus": length_bonus,
                "metrics": metrics,
                "zero_false_true_pair_recall": zero_false_recall,
            }
        )
    selected = max(
        runs,
        key=lambda run: (
            float(run["metrics"]["hard_candidate_top1_accuracy"]),
            float(run["metrics"]["pair_auc"]),
            -float(run["metrics"]["equal_error_rate"]),
            float(run["zero_false_true_pair_recall"]),
        ),
    )
    quality_floor = {
        "hard_candidate_top1_accuracy_minimum": 0.94,
        "pair_auc_minimum": 0.99,
        "equal_error_rate_maximum": 0.05,
        "zero_false_true_pair_recall_minimum": 0.20,
    }
    accepted = (
        float(selected["metrics"]["hard_candidate_top1_accuracy"])
        >= quality_floor["hard_candidate_top1_accuracy_minimum"]
        and float(selected["metrics"]["pair_auc"])
        >= quality_floor["pair_auc_minimum"]
        and float(selected["metrics"]["equal_error_rate"])
        <= quality_floor["equal_error_rate_maximum"]
        and float(selected["zero_false_true_pair_recall"])
        >= quality_floor["zero_false_true_pair_recall_minimum"]
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-text-ctc-tuning.v4",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "train_split_only_spanish_text_to_phoneme_ctc_forward_alignment",
        "sources": {
            "feature_manifest_sha256": _HASH.sha256(feature_manifest_path),
            "tokenizer_vocabulary_sha256": _HASH.sha256(
                tokenizer_directory / "vocab.json"
            ),
        },
        "contract": {
            "split_seed": split_seed,
            "tuning_word_classes": len(tuning_words),
            "reserved_word_classes": len(reserved_words),
            "query_examples_per_word": 6,
            "hard_negative_candidates_per_query": hard_negative_candidates,
            "phonemizer_language": phonemizer_language,
            "ctc_score": "exact_forward_log_probability_divided_by_audio_frames",
            "length_bonus_grid": [-0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2],
            "quality_floor": quality_floor,
        },
        "runs": runs,
        "selected": selected,
        "accepted": accepted,
        "runtime_seconds": time.perf_counter() - started,
        "individual_examples_exported": False,
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
    parser.add_argument("--tokenizer-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-seed", type=int, default=6501)
    parser.add_argument("--tuning-classes", type=int, default=400)
    parser.add_argument("--hard-negative-candidates", type=int, default=40)
    parser.add_argument("--phonemizer-language", default="es")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        feature_manifest_path=args.feature_manifest,
        tokenizer_directory=args.tokenizer_directory,
        output_path=args.output,
        split_seed=args.split_seed,
        tuning_classes=args.tuning_classes,
        hard_negative_candidates=args.hard_negative_candidates,
        phonemizer_language=args.phonemizer_language,
    )
    print(
        json.dumps(
            {"accepted": report["accepted"], "selected": report["selected"]},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
