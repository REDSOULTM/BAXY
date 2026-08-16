"""Rank Spanish keyword candidates with forced Whisper token probabilities."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_whisper_alignment_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_WHISPER = load_component(
    "evaluate_mswc_spanish_faster_whisper_tuning_v8.py",
    "_baxy_mswc_whisper_alignment_v9",
)


def candidate_token_sequences(
    *,
    tokenizer: object,
    candidates: list[str],
    token_prefix: str,
    include_eot: bool,
) -> list[list[int]]:
    if token_prefix not in {"leading_space", "none"} or not candidates:
        raise ValueError("mswc_whisper_alignment_tokenization_invalid")
    prefix = " " if token_prefix == "leading_space" else ""
    sequences = []
    for candidate in candidates:
        tokens = [int(value) for value in tokenizer.encode(prefix + candidate)]
        if include_eot:
            tokens.append(int(tokenizer.eot))
        if not tokens:
            raise ValueError("mswc_whisper_alignment_tokens_empty")
        sequences.append(tokens)
    return sequences


def aggregate_token_probabilities(
    probabilities: list[np.ndarray], *, length_power: float
) -> np.ndarray:
    if not 0.0 <= length_power <= 1.0 or not probabilities:
        raise ValueError("mswc_whisper_alignment_aggregation_invalid")
    scores = []
    for values_raw in probabilities:
        values = np.asarray(values_raw, dtype=np.float64)
        if values.ndim != 1 or len(values) == 0 or not np.isfinite(values).all():
            raise ValueError("mswc_whisper_alignment_probabilities_invalid")
        log_sum = float(np.log(np.clip(values, 1e-12, 1.0)).sum())
        scores.append(log_sum / math.pow(len(values), length_power))
    return np.asarray(scores, dtype=np.float64)


def align_candidate_probabilities(
    *,
    model: object,
    encoded_audio: np.ndarray,
    tokenizer: object,
    token_sequences: list[list[int]],
    num_frames: int,
    candidate_batch_size: int,
    ctranslate2: object,
) -> list[np.ndarray]:
    encoded = np.asarray(encoded_audio)
    if (
        encoded.ndim != 3
        or encoded.shape[0] != 1
        or num_frames < 1
        or candidate_batch_size < 1
        or not token_sequences
    ):
        raise ValueError("mswc_whisper_alignment_batch_invalid")
    probabilities = []
    for start in range(0, len(token_sequences), candidate_batch_size):
        block = token_sequences[start : start + candidate_batch_size]
        repeated = np.repeat(encoded, len(block), axis=0)
        storage = ctranslate2.StorageView.from_array(repeated)
        results = model.model.align(
            storage,
            tokenizer.sot_sequence,
            block,
            [num_frames] * len(block),
        )
        if len(results) != len(block):
            raise ValueError("mswc_whisper_alignment_result_shape_invalid")
        for result, tokens in zip(results, block, strict=True):
            values = np.asarray(result.text_token_probs, dtype=np.float64)
            if len(values) != len(tokens):
                raise ValueError("mswc_whisper_alignment_token_probability_invalid")
            probabilities.append(values)
    return probabilities


def write_score_cache(
    *,
    path: Path,
    score_matrices: dict[float, np.ndarray],
    query_audio_sha256: list[str],
    query_words: list[str],
    candidate_words: list[list[str]],
) -> None:
    candidate_array = np.asarray(candidate_words)
    shape = candidate_array.shape
    if (
        path.exists()
        or path.suffix.lower() != ".npz"
        or len(shape) != 2
        or shape[0] != len(query_audio_sha256)
        or shape[0] != len(query_words)
        or any(np.asarray(scores).shape != shape for scores in score_matrices.values())
    ):
        raise ValueError("mswc_whisper_alignment_cache_invalid")
    payload: dict[str, np.ndarray] = {
        "schema": np.asarray(["baxy.mswc-whisper-forced-alignment-score-cache.v1"]),
        "query_audio_sha256": np.asarray(query_audio_sha256),
        "query_words": np.asarray(query_words),
        "candidate_words": candidate_array,
    }
    for length_power, scores in score_matrices.items():
        key = f"scores_length_power_{str(length_power).replace('.', '_')}"
        payload[key] = np.asarray(scores, dtype=np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **payload)


def load_candidate_mask(
    *,
    path: Path,
    query_audio_sha256: list[str],
    query_words: list[str],
    candidate_words: list[list[str]],
) -> tuple[np.ndarray, int]:
    with np.load(path, allow_pickle=False) as cache:
        if cache["schema"].tolist() != [
            "baxy.mswc-forced-alignment-shortlist.v1"
        ]:
            raise ValueError("mswc_whisper_alignment_shortlist_schema_invalid")
        mask = cache["candidate_mask"].astype(bool)
        depth_values = cache["depth"].astype(np.int64)
        if (
            not np.array_equal(cache["query_audio_sha256"], query_audio_sha256)
            or not np.array_equal(cache["query_words"], query_words)
            or not np.array_equal(cache["candidate_words"], candidate_words)
            or mask.shape != np.asarray(candidate_words).shape
            or len(depth_values) != 1
            or int(depth_values[0]) < 1
            or not mask.any(axis=1).all()
        ):
            raise ValueError("mswc_whisper_alignment_shortlist_alignment_invalid")
    return mask, int(depth_values[0])


def promotion_accepted(
    *, selected: dict[str, object], quality_floor: dict[str, float], complete: bool
) -> bool:
    metrics = selected["metrics"]
    if not isinstance(metrics, dict):
        raise ValueError("mswc_whisper_alignment_metrics_invalid")
    return (
        complete
        and float(metrics["hard_candidate_top1_accuracy"])
        >= quality_floor["hard_candidate_top1_accuracy_minimum"]
        and float(metrics["pair_auc"]) >= quality_floor["pair_auc_minimum"]
        and float(metrics["equal_error_rate"])
        <= quality_floor["equal_error_rate_maximum"]
        and float(selected["zero_false_true_pair_recall"])
        >= quality_floor["zero_false_true_pair_recall_minimum"]
    )


def evaluate(
    *,
    corpus_manifest_path: Path,
    corpus_root: Path,
    model_directory: Path,
    runtime_dll_directory: Path,
    av_site_packages: Path,
    output_path: Path,
    score_cache_output_path: Path | None,
    candidate_mask_cache_path: Path | None,
    query_limit: int | None,
    split_seed: int,
    tuning_classes: int,
    hard_negative_candidates: int,
    cpu_threads: int,
    device: str,
    compute_type: str,
    language: str,
    audio_batch_size: int,
    candidate_batch_size: int,
    token_prefix: str,
    include_eot: bool,
    word_set: str = "tuning",
    cache_only: bool = False,
) -> dict[str, object]:
    started = time.perf_counter()
    if (
        output_path.exists()
        or tuning_classes < 2
        or hard_negative_candidates < 1
        or cpu_threads < 1
        or device not in {"cpu", "cuda"}
        or language not in {"es", "auto"}
        or audio_batch_size < 1
        or candidate_batch_size < 1
        or token_prefix not in {"leading_space", "none"}
        or word_set not in {"tuning", "reserved"}
        or (cache_only and score_cache_output_path is None)
        or (query_limit is not None and query_limit < 1)
        or (
            score_cache_output_path is not None
            and (
                score_cache_output_path.exists()
                or score_cache_output_path.suffix.lower() != ".npz"
            )
        )
    ):
        raise ValueError("mswc_whisper_alignment_schedule_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    corpus_root = corpus_root.resolve(strict=True)
    model_directory = model_directory.resolve(strict=True)
    runtime_dll_directory = runtime_dll_directory.resolve(strict=True)
    av_site_packages = av_site_packages.resolve(strict=True)
    output_path = output_path.resolve()
    if score_cache_output_path is not None:
        score_cache_output_path = score_cache_output_path.resolve()
    if candidate_mask_cache_path is not None:
        candidate_mask_cache_path = candidate_mask_cache_path.resolve(strict=True)
    for name in ("config.json", "model.bin", "tokenizer.json"):
        if not (model_directory / name).is_file():
            raise ValueError(f"mswc_whisper_alignment_model_file_missing:{name}")

    corpus = _WHISPER._PARAKEET._SEQUENCE.read_object(corpus_manifest_path)
    records_raw = corpus.get("records")
    if (
        corpus.get("schema")
        != "baxy.mswc-spanish-qbye-sequence-research-corpus.v3"
        or corpus.get("official_test_audio_accessed") is not False
        or corpus.get("blind_human_audio_accessed") is not False
        or corpus.get("speaker_reidentification_attempted") is not False
        or not isinstance(records_raw, list)
    ):
        raise ValueError("mswc_whisper_alignment_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_whisper_alignment_record_invalid")
        records.append(record)
    words = {str(record["class_name"]) for record in records}
    tuning_words, reserved_words = _WHISPER._PARAKEET._SEQUENCE.split_research_words(
        words, seed=split_seed, tuning_classes=tuning_classes
    )
    selected_words = tuning_words if word_set == "tuning" else reserved_words
    query_records = [
        record
        for record in records
        if record.get("partition") == "open_keyword_query"
        and str(record["class_name"]) in selected_words
    ]
    query_words = [str(record["class_name"]) for record in query_records]
    if (
        len(query_records) != len(selected_words) * 6
        or set(query_words) != selected_words
    ):
        raise ValueError("mswc_whisper_alignment_partition_invalid")
    hard_negatives = _WHISPER._PARAKEET._PAIR.hard_negative_map(
        selected_words, neighbors=hard_negative_candidates
    )
    candidate_words = [
        [word, *hard_negatives[word][:hard_negative_candidates]]
        for word in query_words
    ]
    candidate_mask = np.ones(np.asarray(candidate_words).shape, dtype=bool)
    shortlist_depth = None
    if candidate_mask_cache_path is not None:
        candidate_mask, shortlist_depth = load_candidate_mask(
            path=candidate_mask_cache_path,
            query_audio_sha256=[
                str(record["audio_sha256"]) for record in query_records
            ],
            query_words=query_words,
            candidate_words=candidate_words,
        )
    if query_limit is not None:
        query_records = query_records[:query_limit]
        query_words = query_words[:query_limit]
        candidate_words = candidate_words[:query_limit]
        candidate_mask = candidate_mask[:query_limit]
    paths = []
    for record in query_records:
        relative = Path(str(record["relative_path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("mswc_whisper_alignment_relative_path_invalid")
        path = (corpus_root / relative).resolve(strict=True)
        path.relative_to(corpus_root)
        if (
            path.stat().st_size != int(record["audio_bytes"])
            or _WHISPER._PARAKEET._AUDIO.sha256(path) != record["audio_sha256"]
        ):
            raise ValueError("mswc_whisper_alignment_audio_hash_invalid")
        paths.append(path)

    dll_handle = os.add_dll_directory(str(runtime_dll_directory))
    os.environ["PATH"] = (
        str(runtime_dll_directory) + os.pathsep + os.environ.get("PATH", "")
    )
    os.environ["OMP_NUM_THREADS"] = str(cpu_threads)
    sys.path.insert(0, str(av_site_packages))
    try:
        import av
        import ctranslate2
        from faster_whisper import WhisperModel
        from faster_whisper.audio import pad_or_trim
        from faster_whisper.tokenizer import Tokenizer
    finally:
        sys.path.remove(str(av_site_packages))
    load_started = time.perf_counter()
    model = WhisperModel(
        str(model_directory),
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads,
        local_files_only=True,
    )
    tokenizer = Tokenizer(
        model.hf_tokenizer,
        model.model.is_multilingual,
        task="transcribe",
        language=None if language == "auto" else language,
    )
    load_seconds = time.perf_counter() - load_started
    length_powers = (0.0, 0.5, 1.0)
    score_rows: dict[float, list[np.ndarray]] = {
        length_power: [] for length_power in length_powers
    }
    encode_seconds = 0.0
    align_seconds = 0.0
    inference_started = time.perf_counter()
    for batch_start in range(0, len(paths), audio_batch_size):
        batch_records = query_records[batch_start : batch_start + audio_batch_size]
        batch_paths = paths[batch_start : batch_start + audio_batch_size]
        features = []
        frame_counts = []
        for path in batch_paths:
            audio = _WHISPER._PARAKEET._AUDIO.decode_opus(path, av)
            raw_features = model.feature_extractor(audio)
            features.append(pad_or_trim(raw_features))
            frame_counts.append(
                max(
                    1,
                    min(
                        raw_features.shape[-1] - 1,
                        len(audio) // model.feature_extractor.hop_length,
                    ),
                )
            )
        encode_started = time.perf_counter()
        encoded = model.encode(np.stack(features))
        encoded_cpu = np.asarray(encoded.to_device(ctranslate2.Device.cpu))
        encode_seconds += time.perf_counter() - encode_started
        for offset, record in enumerate(batch_records):
            index = batch_start + offset
            selected_indexes = np.flatnonzero(candidate_mask[index])
            tokens = candidate_token_sequences(
                tokenizer=tokenizer,
                candidates=[candidate_words[index][value] for value in selected_indexes],
                token_prefix=token_prefix,
                include_eot=include_eot,
            )
            align_started = time.perf_counter()
            probabilities = align_candidate_probabilities(
                model=model,
                encoded_audio=encoded_cpu[offset : offset + 1],
                tokenizer=tokenizer,
                token_sequences=tokens,
                num_frames=frame_counts[offset],
                candidate_batch_size=candidate_batch_size,
                ctranslate2=ctranslate2,
            )
            align_seconds += time.perf_counter() - align_started
            for length_power in length_powers:
                row = np.full(len(candidate_words[index]), -1e6, dtype=np.float64)
                row[selected_indexes] = aggregate_token_probabilities(
                    probabilities, length_power=length_power
                )
                score_rows[length_power].append(row)
        completed = min(batch_start + len(batch_paths), len(paths))
        if completed % 25 == 0 or completed == len(paths):
            print(
                f"WHISPER_FORCED_ALIGNMENT_TUNING|{completed}/{len(paths)}",
                flush=True,
            )
    inference_seconds = time.perf_counter() - inference_started
    score_matrices = {
        length_power: np.stack(rows)
        for length_power, rows in score_rows.items()
    }
    if cache_only:
        write_score_cache(
            path=score_cache_output_path,
            score_matrices=score_matrices,
            query_audio_sha256=[str(record["audio_sha256"]) for record in query_records],
            query_words=query_words,
            candidate_words=candidate_words,
        )
        report = {
            "schema": "baxy.mswc-whisper-forced-alignment-score-cache-build.v10",
            "measured_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": f"{word_set}_forced_alignment_cache_without_label_metrics",
            "sources": {
                "corpus_manifest_sha256": _WHISPER._PARAKEET._AUDIO.sha256(
                    corpus_manifest_path
                ),
                "model_tree_sha256": _WHISPER._WHISPER_AUDIT.sha256_tree(
                    model_directory
                ),
                "score_cache_sha256": _WHISPER._PARAKEET._AUDIO.sha256(
                    score_cache_output_path
                ),
                "candidate_mask_cache_sha256": (
                    _WHISPER._PARAKEET._AUDIO.sha256(candidate_mask_cache_path)
                    if candidate_mask_cache_path is not None
                    else None
                ),
            },
            "contract": {
                "split_seed": split_seed,
                "word_set": word_set,
                "word_classes": len(selected_words),
                "query_examples_per_word": 6,
                "hard_negative_candidates_per_query": hard_negative_candidates,
                "token_prefix": token_prefix,
                "include_eot": include_eot,
                "length_power_grid": list(length_powers),
                "shortlist_depth_per_signal": shortlist_depth,
                "label_metrics_computed": False,
            },
            "queries_cached": len(query_words),
            "accepted": False,
            "runtime": {
                "load_seconds": load_seconds,
                "inference_seconds": inference_seconds,
                "encode_seconds": encode_seconds,
                "align_seconds": align_seconds,
                "total_seconds": time.perf_counter() - started,
            },
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
        dll_handle.close()
        return report
    runs = []
    for length_power, scores in score_matrices.items():
        metrics = _WHISPER._PARAKEET._METRICS.hard_pair_metrics(
            scores=scores, query_words=query_words
        )
        zero_false_recall = (
            float(metrics["true_pairs_accepted_at_zero_false_pairs"])
            / float(metrics["true_pairs"])
        )
        runs.append(
            {
                "length_power": length_power,
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
    quality_floor_passed = promotion_accepted(
        selected=selected, quality_floor=quality_floor, complete=True
    )
    accepted = promotion_accepted(
        selected=selected,
        quality_floor=quality_floor,
        complete=query_limit is None and word_set == "tuning",
    )
    if score_cache_output_path is not None:
        write_score_cache(
            path=score_cache_output_path,
            score_matrices=score_matrices,
            query_audio_sha256=[str(record["audio_sha256"]) for record in query_records],
            query_words=query_words,
            candidate_words=candidate_words,
        )
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-whisper-forced-alignment-tuning.v9",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "train_split_only_whisper_forced_candidate_token_alignment",
        "sources": {
            "corpus_manifest_sha256": _WHISPER._PARAKEET._AUDIO.sha256(
                corpus_manifest_path
            ),
            "model_tree_sha256": _WHISPER._WHISPER_AUDIT.sha256_tree(
                model_directory
            ),
            "model_bin_sha256": _WHISPER._PARAKEET._AUDIO.sha256(
                model_directory / "model.bin"
            ),
            "score_cache_sha256": (
                _WHISPER._PARAKEET._AUDIO.sha256(score_cache_output_path)
                if score_cache_output_path is not None
                else None
            ),
            "candidate_mask_cache_sha256": (
                _WHISPER._PARAKEET._AUDIO.sha256(candidate_mask_cache_path)
                if candidate_mask_cache_path is not None
                else None
            ),
        },
        "contract": {
            "split_seed": split_seed,
            "word_set": word_set,
            "tuning_word_classes": len(tuning_words),
            "reserved_word_classes": len(reserved_words),
            "query_examples_per_word": 6 if query_limit is None else None,
            "query_limit": query_limit,
            "hard_negative_candidates_per_query": hard_negative_candidates,
            "language": language,
            "token_prefix": token_prefix,
            "include_eot": include_eot,
            "length_power_grid": list(length_powers),
            "audio_batch_size": audio_batch_size,
            "candidate_batch_size": candidate_batch_size,
            "candidate_shortlist_depth_per_signal": shortlist_depth,
            "candidate_shortlist_width_mean": float(candidate_mask.sum(axis=1).mean()),
            "candidate_shortlist_true_recall": float(candidate_mask[:, 0].mean()),
            "quality_floor": quality_floor,
        },
        "runs": runs,
        "selected": selected,
        "quality_floor_passed": quality_floor_passed,
        "accepted": accepted,
        "runtime": {
            "load_seconds": load_seconds,
            "inference_seconds": inference_seconds,
            "encode_seconds": encode_seconds,
            "align_seconds": align_seconds,
            "total_seconds": time.perf_counter() - started,
            "cpu_threads": cpu_threads,
            "device": device,
            "compute_type": compute_type,
            "faster_whisper": __import__("faster_whisper").__version__,
            "ctranslate2": ctranslate2.__version__,
            "av": av.__version__,
        },
        "individual_examples_exported": score_cache_output_path is not None,
        "research_tuning_examples_scored": word_set == "tuning",
        "research_tuning_examples_complete": query_limit is None,
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
    dll_handle.close()
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--runtime-dll-directory", type=Path, required=True)
    parser.add_argument("--av-site-packages", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--score-cache-output", type=Path)
    parser.add_argument("--candidate-mask-cache", type=Path)
    parser.add_argument("--query-limit", type=int)
    parser.add_argument("--split-seed", type=int, default=6501)
    parser.add_argument("--tuning-classes", type=int, default=400)
    parser.add_argument("--hard-negative-candidates", type=int, default=40)
    parser.add_argument("--cpu-threads", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--compute-type", default="int8_float16")
    parser.add_argument("--language", choices=("es", "auto"), default="es")
    parser.add_argument("--audio-batch-size", type=int, default=2)
    parser.add_argument("--candidate-batch-size", type=int, default=41)
    parser.add_argument(
        "--token-prefix", choices=("leading_space", "none"), default="leading_space"
    )
    parser.add_argument("--include-eot", action="store_true")
    parser.add_argument("--word-set", choices=("tuning", "reserved"), default="tuning")
    parser.add_argument("--cache-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        corpus_manifest_path=args.corpus_manifest,
        corpus_root=args.corpus_root,
        model_directory=args.model_directory,
        runtime_dll_directory=args.runtime_dll_directory,
        av_site_packages=args.av_site_packages,
        output_path=args.output,
        score_cache_output_path=args.score_cache_output,
        candidate_mask_cache_path=args.candidate_mask_cache,
        query_limit=args.query_limit,
        split_seed=args.split_seed,
        tuning_classes=args.tuning_classes,
        hard_negative_candidates=args.hard_negative_candidates,
        cpu_threads=args.cpu_threads,
        device=args.device,
        compute_type=args.compute_type,
        language=args.language,
        audio_batch_size=args.audio_batch_size,
        candidate_batch_size=args.candidate_batch_size,
        token_prefix=args.token_prefix,
        include_eot=args.include_eot,
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
