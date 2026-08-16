"""Evaluate local Faster-Whisper large-v3 on MSWC Spanish tuning words."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_faster_whisper_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PARAKEET = load_component(
    "evaluate_mswc_spanish_parakeet_tuning_v6.py",
    "_baxy_mswc_faster_whisper_base_v8",
)
_WHISPER_AUDIT = load_component(
    "audit_ccby_wake_development_faster_whisper_v1.py",
    "_baxy_mswc_faster_whisper_hash_v8",
)


def join_segment_texts(segments: object) -> str:
    return " ".join(
        str(getattr(segment, "text", "")).strip() for segment in segments
    ).strip()


def slot_transcripts(
    *, segments: object, slots: int, slot_seconds: float
) -> list[str]:
    if slots < 1 or slot_seconds <= 0.0:
        raise ValueError("mswc_faster_whisper_slot_schedule_invalid")
    words_by_slot: list[list[str]] = [[] for _ in range(slots)]
    for segment in segments:
        for word in getattr(segment, "words", None) or []:
            start = float(getattr(word, "start", 0.0))
            end = float(getattr(word, "end", start))
            slot = int(max(0.0, (start + end) / 2.0) // slot_seconds)
            text = str(getattr(word, "word", "")).strip()
            if 0 <= slot < slots and text:
                words_by_slot[slot].append(text)
    return [" ".join(words).strip() for words in words_by_slot]


def write_score_cache(
    *,
    path: Path,
    whole_scores: np.ndarray,
    token_scores: np.ndarray,
    transcripts: list[str],
    candidate_words: list[list[str]],
    query_audio_sha256: list[str],
    query_words: list[str],
) -> None:
    candidate_array = np.asarray(candidate_words)
    if (
        path.exists()
        or path.suffix.lower() != ".npz"
        or whole_scores.shape != token_scores.shape
        or whole_scores.shape != candidate_array.shape
        or whole_scores.shape[0] != len(transcripts)
        or whole_scores.shape[0] != len(query_audio_sha256)
        or whole_scores.shape[0] != len(query_words)
    ):
        raise ValueError("mswc_faster_whisper_score_cache_invalid")
    normalized_transcripts = [
        _PARAKEET.normalize_text(transcript) for transcript in transcripts
    ]
    exact_candidate_match = np.asarray(
        [
            [
                transcript == _PARAKEET.normalize_text(candidate)
                for candidate in candidates
            ]
            for transcript, candidates in zip(
                normalized_transcripts, candidate_words, strict=True
            )
        ],
        dtype=np.uint8,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        schema=np.asarray(["baxy.mswc-faster-whisper-score-cache.v1"]),
        whole_transcript_edit=np.asarray(whole_scores, dtype=np.float32),
        whole_or_token_edit=np.asarray(token_scores, dtype=np.float32),
        exact_candidate_match=exact_candidate_match,
        query_audio_sha256=np.asarray(query_audio_sha256),
        query_words=np.asarray(query_words),
        candidate_words=candidate_array,
    )


def evaluate(
    *,
    corpus_manifest_path: Path,
    corpus_root: Path,
    model_directory: Path,
    runtime_dll_directory: Path,
    av_site_packages: Path,
    output_path: Path,
    split_seed: int,
    tuning_classes: int,
    hard_negative_candidates: int,
    cpu_threads: int,
    device: str,
    compute_type: str,
    language: str,
    inference_layout: str,
    inference_batch_size: int,
    slot_seconds: float,
    score_cache_output_path: Path | None = None,
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
        or inference_layout not in {"sequential", "fixed_slot_batched"}
        or inference_batch_size < 1
        or not 1.0 <= slot_seconds <= 5.0
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
        raise ValueError("mswc_faster_whisper_schedule_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    corpus_root = corpus_root.resolve(strict=True)
    model_directory = model_directory.resolve(strict=True)
    runtime_dll_directory = runtime_dll_directory.resolve(strict=True)
    av_site_packages = av_site_packages.resolve(strict=True)
    output_path = output_path.resolve()
    if score_cache_output_path is not None:
        score_cache_output_path = score_cache_output_path.resolve()
    for name in ("config.json", "model.bin", "tokenizer.json"):
        if not (model_directory / name).is_file():
            raise ValueError(f"mswc_faster_whisper_model_file_missing:{name}")
    corpus = _PARAKEET._SEQUENCE.read_object(corpus_manifest_path)
    records_raw = corpus.get("records")
    if (
        corpus.get("schema")
        != "baxy.mswc-spanish-qbye-sequence-research-corpus.v3"
        or corpus.get("official_test_audio_accessed") is not False
        or corpus.get("blind_human_audio_accessed") is not False
        or corpus.get("speaker_reidentification_attempted") is not False
        or not isinstance(records_raw, list)
    ):
        raise ValueError("mswc_faster_whisper_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_faster_whisper_record_invalid")
        records.append(record)
    words = {str(record["class_name"]) for record in records}
    tuning_words, reserved_words = _PARAKEET._SEQUENCE.split_research_words(
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
        raise ValueError("mswc_faster_whisper_partition_invalid")
    hard_negatives = _PARAKEET._PAIR.hard_negative_map(
        selected_words, neighbors=hard_negative_candidates
    )
    candidate_words = [
        [word, *hard_negatives[word][:hard_negative_candidates]]
        for word in query_words
    ]
    paths = []
    for record in query_records:
        relative = Path(str(record["relative_path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("mswc_faster_whisper_relative_path_invalid")
        path = (corpus_root / relative).resolve(strict=True)
        path.relative_to(corpus_root)
        if (
            path.stat().st_size != int(record["audio_bytes"])
            or _PARAKEET._AUDIO.sha256(path) != record["audio_sha256"]
        ):
            raise ValueError("mswc_faster_whisper_audio_hash_invalid")
        paths.append(path)

    dll_handle = os.add_dll_directory(str(runtime_dll_directory))
    os.environ["PATH"] = (
        str(runtime_dll_directory) + os.pathsep + os.environ.get("PATH", "")
    )
    os.environ["OMP_NUM_THREADS"] = str(cpu_threads)
    sys.path.insert(0, str(av_site_packages))
    try:
        import av
        from faster_whisper import BatchedInferencePipeline, WhisperModel
        import ctranslate2
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
    load_seconds = time.perf_counter() - load_started
    transcripts = []
    decode_started = time.perf_counter()
    if inference_layout == "sequential":
        for index, path in enumerate(paths, 1):
            audio = _PARAKEET._AUDIO.decode_opus(path, av)
            segments, _ = model.transcribe(
                audio,
                language=None if language == "auto" else language,
                beam_size=1,
                best_of=1,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=False,
                without_timestamps=True,
                word_timestamps=False,
                initial_prompt=None,
                hotwords=None,
            )
            transcripts.append(join_segment_texts(segments))
            if index % 100 == 0 or index == len(paths):
                print(f"FASTER_WHISPER_TUNING|{index}/{len(paths)}", flush=True)
    else:
        slot_samples = int(round(slot_seconds * _PARAKEET._AUDIO.SAMPLE_RATE))
        combined = np.zeros(len(paths) * slot_samples, dtype=np.float32)
        for index, path in enumerate(paths):
            audio = _PARAKEET._AUDIO.decode_opus(path, av)
            if len(audio) > slot_samples:
                raise ValueError("mswc_faster_whisper_audio_exceeds_slot")
            start = index * slot_samples
            combined[start : start + len(audio)] = audio
        batched_model = BatchedInferencePipeline(model=model)
        clip_timestamps = [
            {"start": index * slot_seconds, "end": (index + 1) * slot_seconds}
            for index in range(len(paths))
        ]
        segments, _ = batched_model.transcribe(
            combined,
            language=None if language == "auto" else language,
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=False,
            without_timestamps=False,
            word_timestamps=True,
            initial_prompt=None,
            hotwords=None,
            batch_size=inference_batch_size,
            clip_timestamps=clip_timestamps,
        )
        transcripts = slot_transcripts(
            segments=segments, slots=len(paths), slot_seconds=slot_seconds
        )
        print(f"FASTER_WHISPER_TUNING|{len(paths)}/{len(paths)}", flush=True)
    decode_seconds = time.perf_counter() - decode_started
    runs = []
    score_matrices: dict[str, np.ndarray] = {}
    for method in ("whole_transcript_edit", "whole_or_token_edit"):
        scores = _PARAKEET.transcript_candidate_scores(
            transcripts=transcripts,
            candidate_words=candidate_words,
            method=method,
        )
        score_matrices[method] = scores
        metrics = _PARAKEET._METRICS.hard_pair_metrics(
            scores=scores, query_words=query_words
        )
        zero_false_recall = (
            float(metrics["true_pairs_accepted_at_zero_false_pairs"])
            / float(metrics["true_pairs"])
        )
        runs.append(
            {
                "method": method,
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
    exact_transcripts = sum(
        _PARAKEET.normalize_text(transcript) == _PARAKEET.normalize_text(word)
        for transcript, word in zip(transcripts, query_words, strict=True)
    )
    nonempty_transcripts = sum(
        bool(_PARAKEET.normalize_text(value)) for value in transcripts
    )
    if score_cache_output_path is not None:
        write_score_cache(
            path=score_cache_output_path,
            whole_scores=score_matrices["whole_transcript_edit"],
            token_scores=score_matrices["whole_or_token_edit"],
            transcripts=transcripts,
            candidate_words=candidate_words,
            query_audio_sha256=[str(record["audio_sha256"]) for record in query_records],
            query_words=query_words,
        )
    if cache_only:
        report = {
            "schema": "baxy.mswc-faster-whisper-score-cache-build.v9",
            "measured_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": f"{word_set}_transcript_score_cache_without_label_metrics",
            "sources": {
                "corpus_manifest_sha256": _PARAKEET._AUDIO.sha256(
                    corpus_manifest_path
                ),
                "model_tree_sha256": _WHISPER_AUDIT.sha256_tree(model_directory),
                "model_bin_sha256": _PARAKEET._AUDIO.sha256(
                    model_directory / "model.bin"
                ),
                "score_cache_sha256": _PARAKEET._AUDIO.sha256(
                    score_cache_output_path
                ),
            },
            "contract": {
                "split_seed": split_seed,
                "word_set": word_set,
                "word_classes": len(selected_words),
                "query_examples_per_word": 6,
                "hard_negative_candidates_per_query": hard_negative_candidates,
                "language": language,
                "compute_type": compute_type,
                "inference_layout": inference_layout,
                "label_metrics_computed": False,
            },
            "queries_cached": len(query_words),
            "accepted": False,
            "runtime": {
                "load_seconds": load_seconds,
                "decode_seconds": decode_seconds,
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
        "schema": "baxy.mswc-spanish-faster-whisper-tuning.v8",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "train_split_only_faster_whisper_large_v3_spanish_transcript_ranking",
        "sources": {
            "corpus_manifest_sha256": _PARAKEET._AUDIO.sha256(
                corpus_manifest_path
            ),
            "model_tree_sha256": _WHISPER_AUDIT.sha256_tree(model_directory),
            "model_bin_sha256": _PARAKEET._AUDIO.sha256(
                model_directory / "model.bin"
            ),
            "runtime_dll_sha256": {
                path.name: _PARAKEET._AUDIO.sha256(path)
                for pattern in ("cublas*.dll", "cudnn*.dll", "cudart*.dll")
                for path in sorted(runtime_dll_directory.glob(pattern))
            },
            "score_cache_sha256": (
                _PARAKEET._AUDIO.sha256(score_cache_output_path)
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
            "language": language,
            "beam_size": 1,
            "best_of": 1,
            "temperature": 0.0,
            "condition_on_previous_text": False,
            "vad_filter": False,
            "without_timestamps": inference_layout == "sequential",
            "word_timestamps": inference_layout == "fixed_slot_batched",
            "initial_prompt": None,
            "hotwords": None,
            "inference_layout": inference_layout,
            "inference_batch_size": inference_batch_size,
            "slot_seconds": slot_seconds if inference_layout == "fixed_slot_batched" else None,
            "quality_floor": quality_floor,
        },
        "transcription_aggregates": {
            "nonempty": nonempty_transcripts,
            "total": len(transcripts),
            "exact_reference_word": exact_transcripts,
            "exact_reference_word_rate": exact_transcripts / len(transcripts),
        },
        "runs": runs,
        "selected": selected,
        "accepted": accepted,
        "runtime": {
            "load_seconds": load_seconds,
            "decode_seconds": decode_seconds,
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
    parser.add_argument("--split-seed", type=int, default=6501)
    parser.add_argument("--tuning-classes", type=int, default=400)
    parser.add_argument("--hard-negative-candidates", type=int, default=40)
    parser.add_argument("--cpu-threads", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument("--language", choices=("es", "auto"), default="es")
    parser.add_argument(
        "--inference-layout",
        choices=("sequential", "fixed_slot_batched"),
        default="sequential",
    )
    parser.add_argument("--inference-batch-size", type=int, default=16)
    parser.add_argument("--slot-seconds", type=float, default=2.0)
    parser.add_argument("--score-cache-output", type=Path)
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
        split_seed=args.split_seed,
        tuning_classes=args.tuning_classes,
        hard_negative_candidates=args.hard_negative_candidates,
        cpu_threads=args.cpu_threads,
        device=args.device,
        compute_type=args.compute_type,
        language=args.language,
        inference_layout=args.inference_layout,
        inference_batch_size=args.inference_batch_size,
        slot_seconds=args.slot_seconds,
        score_cache_output_path=args.score_cache_output,
        word_set=args.word_set,
        cache_only=args.cache_only,
    )
    print(
        json.dumps(
            {
                "accepted": report["accepted"],
                "selected": report.get("selected"),
                "transcription_aggregates": report.get("transcription_aggregates"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
