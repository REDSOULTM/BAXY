"""Fuse HyperSpotter and direct Spanish phoneme-CTC scores on tuning words."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_hyperspotter_ctc_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_HYPER = load_component(
    "evaluate_mswc_hyperspotter_spanish_tuning_v1.py",
    "_baxy_hyperspotter_ctc_hyper_v5",
)
_TEXT_CTC = load_component(
    "evaluate_mswc_spanish_text_ctc_tuning_v4.py",
    "_baxy_hyperspotter_ctc_text_v5",
)


def global_standardize(scores: np.ndarray) -> np.ndarray:
    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 2 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("mswc_hyperspotter_ctc_standardization_invalid")
    deviation = float(np.std(values))
    if deviation <= 0.0:
        raise ValueError("mswc_hyperspotter_ctc_standardization_constant")
    return (values - float(np.mean(values))) / deviation


def row_rank_scores(scores: np.ndarray) -> np.ndarray:
    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] < 2 or not np.isfinite(values).all():
        raise ValueError("mswc_hyperspotter_ctc_ranks_invalid")
    order = np.argsort(values, axis=1)
    ranks = np.empty_like(order)
    rows = np.arange(len(values))[:, None]
    ranks[rows, order] = np.arange(values.shape[1])[None, :]
    return ranks.astype(np.float64) / float(values.shape[1] - 1)


def write_score_cache(
    *,
    path: Path,
    hyper_scores: np.ndarray,
    ctc_scores: np.ndarray,
    candidates: np.ndarray,
    query_audio_sha256: list[str],
    query_words: list[str],
    class_names: list[str],
) -> None:
    if (
        path.exists()
        or path.suffix.lower() != ".npz"
        or hyper_scores.shape != ctc_scores.shape
        or hyper_scores.shape != candidates.shape
        or hyper_scores.shape[0] != len(query_audio_sha256)
        or hyper_scores.shape[0] != len(query_words)
        or not class_names
    ):
        raise ValueError("mswc_hyperspotter_ctc_score_cache_invalid")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        schema=np.asarray(["baxy.mswc-hyperspotter-ctc-score-cache.v1"]),
        hyper_scores=np.asarray(hyper_scores, dtype=np.float32),
        ctc_scores=np.asarray(ctc_scores, dtype=np.float32),
        candidate_indexes=np.asarray(candidates, dtype=np.int32),
        query_audio_sha256=np.asarray(query_audio_sha256),
        query_words=np.asarray(query_words),
        class_names=np.asarray(class_names),
    )


def evaluate(
    *,
    hyperspotter_feature_manifest_path: Path,
    ctc_feature_manifest_path: Path,
    tokenizer_directory: Path,
    phonemizer_site_packages: Path,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    initial_checkpoint_path: Path,
    adapted_checkpoint_path: Path,
    output_path: Path,
    split_seed: int,
    tuning_classes: int,
    hard_negative_candidates: int,
    ctc_length_bonus: float,
    prediction_batch_size: int,
    device: str,
    score_cache_output_path: Path | None = None,
    word_set: str = "tuning",
    cache_only: bool = False,
) -> dict[str, object]:
    started = time.perf_counter()
    if (
        output_path.exists()
        or tuning_classes < 2
        or hard_negative_candidates < 1
        or prediction_batch_size < 1
        or device not in {"cpu", "cuda"}
        or word_set not in {"tuning", "reserved"}
        or (cache_only and score_cache_output_path is None)
        or (
            score_cache_output_path is not None
            and (
                score_cache_output_path.exists()
                or score_cache_output_path.suffix.lower() != ".npz"
            )
        )
    ):
        raise ValueError("mswc_hyperspotter_ctc_schedule_invalid")
    hyperspotter_feature_manifest_path = (
        hyperspotter_feature_manifest_path.resolve(strict=True)
    )
    ctc_feature_manifest_path = ctc_feature_manifest_path.resolve(strict=True)
    tokenizer_directory = tokenizer_directory.resolve(strict=True)
    phonemizer_site_packages = phonemizer_site_packages.resolve(strict=True)
    hyperspotter_root = hyperspotter_root.resolve(strict=True)
    hyperspotter_site_packages = hyperspotter_site_packages.resolve(strict=True)
    initial_checkpoint_path = initial_checkpoint_path.resolve(strict=True)
    adapted_checkpoint_path = adapted_checkpoint_path.resolve(strict=True)
    output_path = output_path.resolve()
    if score_cache_output_path is not None:
        score_cache_output_path = score_cache_output_path.resolve()

    hyper_manifest = _HYPER._LOGMEL.read_object(
        hyperspotter_feature_manifest_path
    )
    hyper_records_raw = hyper_manifest.get("records")
    hyper_files = hyper_manifest.get("files")
    hyper_contract = hyper_manifest.get("contract")
    hyper_sources = hyper_manifest.get("sources")
    if (
        hyper_manifest.get("schema") != "baxy.mswc-hyperspotter-logmel.v1"
        or hyper_manifest.get("official_test_audio_accessed") is not False
        or hyper_manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(hyper_records_raw, list)
        or not isinstance(hyper_files, dict)
        or not isinstance(hyper_contract, dict)
        or not isinstance(hyper_sources, dict)
        or hyper_contract.get("included_partitions")
        != ["open_keyword_enrollment", "open_keyword_query"]
    ):
        raise ValueError("mswc_hyperspotter_ctc_hyper_boundary_invalid")
    hyper_records = []
    for record in hyper_records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_hyperspotter_ctc_hyper_record_invalid")
        hyper_records.append(record)
    words = {str(record["class_name"]) for record in hyper_records}
    tuning_words, reserved_words = _HYPER._SEQUENCE.split_research_words(
        words, seed=split_seed, tuning_classes=tuning_classes
    )
    selected_words = tuning_words if word_set == "tuning" else reserved_words
    hyper_query_indexes = [
        index
        for index, record in enumerate(hyper_records)
        if record.get("partition") == "open_keyword_query"
        and str(record["class_name"]) in selected_words
    ]
    query_words = [
        str(hyper_records[index]["class_name"]) for index in hyper_query_indexes
    ]
    if (
        len(hyper_query_indexes) != len(selected_words) * 6
        or set(query_words) != selected_words
    ):
        raise ValueError("mswc_hyperspotter_ctc_hyper_partition_invalid")
    class_names = sorted(selected_words)
    hard_negatives = _HYPER._PAIR.hard_negative_map(
        selected_words, neighbors=hard_negative_candidates
    )
    candidates = _HYPER.candidate_matrix(
        query_words=query_words,
        class_names=class_names,
        hard_negatives=hard_negatives,
        negative_candidates=hard_negative_candidates,
    )
    hyper_root = hyperspotter_feature_manifest_path.parent
    hyper_feature_path = hyper_root / str(hyper_files["logmel"])
    hyper_offset_path = hyper_root / str(hyper_files["offsets"])
    if (
        _HYPER._LOGMEL.sha256(hyper_feature_path)
        != hyper_files.get("logmel_sha256")
        or _HYPER._LOGMEL.sha256(hyper_offset_path)
        != hyper_files.get("offsets_sha256")
    ):
        raise ValueError("mswc_hyperspotter_ctc_hyper_hash_invalid")
    hyper_features = np.load(hyper_feature_path, mmap_mode="r")
    hyper_offsets = np.load(hyper_offset_path)
    if len(hyper_offsets) != len(hyper_records) + 1 or int(
        hyper_offsets[-1]
    ) != len(hyper_features):
        raise ValueError("mswc_hyperspotter_ctc_hyper_shape_invalid")

    ctc_manifest = _HYPER._SEQUENCE.read_object(ctc_feature_manifest_path)
    ctc_records_raw = ctc_manifest.get("records")
    ctc_files = ctc_manifest.get("files")
    ctc_contract = ctc_manifest.get("contract")
    ctc_sources = ctc_manifest.get("sources")
    if (
        ctc_manifest.get("schema")
        != "baxy.mswc-spanish-qbye-sequence-features.v3"
        or ctc_manifest.get("official_test_audio_accessed") is not False
        or ctc_manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(ctc_records_raw, list)
        or not isinstance(ctc_files, dict)
        or not isinstance(ctc_contract, dict)
        or not isinstance(ctc_sources, dict)
    ):
        raise ValueError("mswc_hyperspotter_ctc_ctc_boundary_invalid")
    ctc_records = []
    ctc_index_by_audio_hash = {}
    for index, record in enumerate(ctc_records_raw):
        if not isinstance(record, dict):
            raise ValueError("mswc_hyperspotter_ctc_ctc_record_invalid")
        ctc_records.append(record)
        key = str(record["audio_sha256"])
        if key in ctc_index_by_audio_hash:
            raise ValueError("mswc_hyperspotter_ctc_audio_duplicate")
        ctc_index_by_audio_hash[key] = index
    ctc_query_indexes = []
    for hyper_index in hyper_query_indexes:
        hyper_record = hyper_records[hyper_index]
        ctc_index = ctc_index_by_audio_hash.get(str(hyper_record["audio_sha256"]))
        if ctc_index is None:
            raise ValueError("mswc_hyperspotter_ctc_audio_alignment_missing")
        ctc_record = ctc_records[ctc_index]
        if (
            ctc_record.get("class_name") != hyper_record.get("class_name")
            or ctc_record.get("partition") != "open_keyword_query"
        ):
            raise ValueError("mswc_hyperspotter_ctc_audio_alignment_invalid")
        ctc_query_indexes.append(ctc_index)
    ctc_root = ctc_feature_manifest_path.parent
    ctc_offset_path = ctc_root / str(ctc_files["offsets"])
    ctc_descriptor = ctc_files.get("ctc_log_probabilities")
    if (
        not isinstance(ctc_descriptor, dict)
        or _HYPER._LOGMEL.sha256(ctc_offset_path)
        != ctc_files.get("offsets_sha256")
    ):
        raise ValueError("mswc_hyperspotter_ctc_ctc_files_invalid")
    ctc_path = ctc_root / str(ctc_descriptor["path"])
    if _HYPER._LOGMEL.sha256(ctc_path) != ctc_descriptor.get("sha256"):
        raise ValueError("mswc_hyperspotter_ctc_ctc_hash_invalid")
    if _HYPER._LOGMEL.sha256(tokenizer_directory / "vocab.json") != ctc_sources.get(
        "model_vocabulary_sha256"
    ):
        raise ValueError("mswc_hyperspotter_ctc_vocab_hash_invalid")
    ctc_offsets = np.load(ctc_offset_path)
    ctc_probabilities = np.load(ctc_path, mmap_mode="r")
    if len(ctc_offsets) != len(ctc_records) + 1 or int(ctc_offsets[-1]) != len(
        ctc_probabilities
    ):
        raise ValueError("mswc_hyperspotter_ctc_ctc_shape_invalid")

    if str(phonemizer_site_packages) not in sys.path:
        sys.path.append(str(phonemizer_site_packages))
    from audit_voxcpm2_gguf_pilot import configure_espeak_backend

    espeak = configure_espeak_backend()
    if espeak is None:
        raise ValueError("mswc_hyperspotter_ctc_espeak_unavailable")
    from transformers import Wav2Vec2PhonemeCTCTokenizer

    ctc_tokenizer = Wav2Vec2PhonemeCTCTokenizer.from_pretrained(
        str(tokenizer_directory),
        local_files_only=True,
        phonemizer_lang="es",
    )
    text_sequences = [
        [int(value) for value in sequence]
        for sequence in ctc_tokenizer(class_names)["input_ids"]
    ]

    model, tokenizer, torch, torch_device = _HYPER.load_hyperspotter_model(
        hyperspotter_root=hyperspotter_root,
        hyperspotter_site_packages=hyperspotter_site_packages,
        initial_checkpoint_path=initial_checkpoint_path,
        adapted_checkpoint_path=adapted_checkpoint_path,
        expected_upstream_commit=str(hyper_sources["hyperspotter_upstream_commit"]),
        device=device,
    )
    hyper_scores = _HYPER.score_hyperspotter_candidates(
        model=model,
        tokenizer=tokenizer,
        torch=torch,
        torch_device=torch_device,
        features=hyper_features,
        offsets=hyper_offsets,
        query_indexes=hyper_query_indexes,
        candidate_indexes=candidates,
        class_names=class_names,
        prediction_batch_size=prediction_batch_size,
        device=device,
        progress_label="HYPERSPOTTER_CTC_FUSION_HYPER",
    )
    del model, tokenizer
    ctc_scores, token_lengths = _TEXT_CTC.score_text_candidates(
        ctc_log_probabilities=ctc_probabilities,
        offsets=ctc_offsets,
        query_indexes=ctc_query_indexes,
        candidate_indexes=candidates,
        text_sequences=text_sequences,
        blank_id=int(ctc_contract["ctc_blank_id"]),
    )
    ctc_scores = ctc_scores + ctc_length_bonus * token_lengths
    if score_cache_output_path is not None:
        write_score_cache(
            path=score_cache_output_path,
            hyper_scores=hyper_scores,
            ctc_scores=ctc_scores,
            candidates=candidates,
            query_audio_sha256=[
                str(ctc_records[index]["audio_sha256"])
                for index in ctc_query_indexes
            ],
            query_words=query_words,
            class_names=class_names,
        )
    if cache_only:
        report = {
            "schema": "baxy.mswc-hyperspotter-ctc-score-cache-build.v6",
            "measured_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": f"{word_set}_aggregate_score_cache_without_label_metrics",
            "sources": {
                "hyperspotter_feature_manifest_sha256": _HYPER._LOGMEL.sha256(
                    hyperspotter_feature_manifest_path
                ),
                "ctc_feature_manifest_sha256": _HYPER._LOGMEL.sha256(
                    ctc_feature_manifest_path
                ),
                "adapted_checkpoint_sha256": _HYPER._LOGMEL.sha256(
                    adapted_checkpoint_path
                ),
                "score_cache_sha256": _HYPER._LOGMEL.sha256(
                    score_cache_output_path
                ),
            },
            "contract": {
                "split_seed": split_seed,
                "word_set": word_set,
                "word_classes": len(selected_words),
                "query_examples_per_word": 6,
                "hard_negative_candidates_per_query": hard_negative_candidates,
                "ctc_length_bonus": ctc_length_bonus,
                "label_metrics_computed": False,
            },
            "queries_cached": len(query_words),
            "accepted": False,
            "runtime_seconds": time.perf_counter() - started,
            "individual_examples_exported": True,
            "research_tuning_examples_scored": word_set == "tuning",
            "research_reserved_examples_scored": word_set == "reserved",
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
    standardized_hyper = global_standardize(hyper_scores)
    standardized_ctc = global_standardize(ctc_scores)
    ranked_hyper = row_rank_scores(hyper_scores)
    ranked_ctc = row_rank_scores(ctc_scores)
    runs = []
    for method, left, right in (
        ("global_zscore_linear", standardized_hyper, standardized_ctc),
        ("per_query_rank_linear", ranked_hyper, ranked_ctc),
    ):
        for hyper_weight in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
            fused = hyper_weight * left + (1.0 - hyper_weight) * right
            metrics = _HYPER.hard_pair_metrics(
                scores=fused, query_words=query_words
            )
            zero_false_recall = (
                float(metrics["true_pairs_accepted_at_zero_false_pairs"])
                / float(metrics["true_pairs"])
            )
            runs.append(
                {
                    "method": method,
                    "hyperspotter_weight": hyper_weight,
                    "ctc_weight": 1.0 - hyper_weight,
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
        "schema": "baxy.mswc-hyperspotter-ctc-fusion-tuning.v5",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "train_split_only_aggregate_fusion_of_text_conditioned_neural_and_ctc_scores",
        "sources": {
            "hyperspotter_feature_manifest_sha256": _HYPER._LOGMEL.sha256(
                hyperspotter_feature_manifest_path
            ),
            "ctc_feature_manifest_sha256": _HYPER._LOGMEL.sha256(
                ctc_feature_manifest_path
            ),
            "adapted_checkpoint_sha256": _HYPER._LOGMEL.sha256(
                adapted_checkpoint_path
            ),
            "tokenizer_vocabulary_sha256": _HYPER._LOGMEL.sha256(
                tokenizer_directory / "vocab.json"
            ),
            "score_cache_sha256": (
                _HYPER._LOGMEL.sha256(score_cache_output_path)
                if score_cache_output_path is not None
                else None
            ),
        },
        "contract": {
            "split_seed": split_seed,
            "word_set": word_set,
            "tuning_word_classes": len(tuning_words),
            "reserved_word_classes": len(reserved_words),
            "query_examples_per_word": 6,
            "hard_negative_candidates_per_query": hard_negative_candidates,
            "ctc_phonemizer_language": "es",
            "ctc_length_bonus": ctc_length_bonus,
            "fusion_weight_grid": [
                0.0,
                0.1,
                0.2,
                0.3,
                0.4,
                0.5,
                0.6,
                0.7,
                0.8,
                0.9,
                1.0,
            ],
            "quality_floor": quality_floor,
        },
        "runs": runs,
        "selected": selected,
        "accepted": accepted,
        "runtime_seconds": time.perf_counter() - started,
        "individual_examples_exported": score_cache_output_path is not None,
        "research_tuning_examples_scored": word_set == "tuning",
        "research_reserved_examples_scored": word_set == "reserved",
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
    parser.add_argument("--hyperspotter-feature-manifest", type=Path, required=True)
    parser.add_argument("--ctc-feature-manifest", type=Path, required=True)
    parser.add_argument("--tokenizer-directory", type=Path, required=True)
    parser.add_argument("--phonemizer-site-packages", type=Path, required=True)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--adapted-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-seed", type=int, default=6501)
    parser.add_argument("--tuning-classes", type=int, default=400)
    parser.add_argument("--hard-negative-candidates", type=int, default=40)
    parser.add_argument("--ctc-length-bonus", type=float, default=0.05)
    parser.add_argument("--prediction-batch-size", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--score-cache-output", type=Path)
    parser.add_argument("--word-set", choices=("tuning", "reserved"), default="tuning")
    parser.add_argument("--cache-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        hyperspotter_feature_manifest_path=args.hyperspotter_feature_manifest,
        ctc_feature_manifest_path=args.ctc_feature_manifest,
        tokenizer_directory=args.tokenizer_directory,
        phonemizer_site_packages=args.phonemizer_site_packages,
        hyperspotter_root=args.hyperspotter_root,
        hyperspotter_site_packages=args.hyperspotter_site_packages,
        initial_checkpoint_path=args.initial_checkpoint,
        adapted_checkpoint_path=args.adapted_checkpoint,
        output_path=args.output,
        split_seed=args.split_seed,
        tuning_classes=args.tuning_classes,
        hard_negative_candidates=args.hard_negative_candidates,
        ctc_length_bonus=args.ctc_length_bonus,
        prediction_batch_size=args.prediction_batch_size,
        device=args.device,
        score_cache_output_path=args.score_cache_output,
        word_set=args.word_set,
        cache_only=args.cache_only,
    )
    print(
        json.dumps(
            {"accepted": report["accepted"], "selected": report.get("selected")},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
