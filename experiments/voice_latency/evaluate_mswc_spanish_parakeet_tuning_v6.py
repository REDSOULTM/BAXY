"""Evaluate local multilingual Parakeet transcripts on MSWC Spanish tuning words."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import time
import unicodedata

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_parakeet_tuning_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SEQUENCE = load_component(
    "evaluate_mswc_spanish_qbye_sequence_tuning_v3.py",
    "_baxy_mswc_parakeet_sequence_v6",
)
_PAIR = load_component(
    "train_mswc_spanish_qbye_similarity_cnn_v4.py",
    "_baxy_mswc_parakeet_pairs_v6",
)
_METRICS = load_component(
    "evaluate_mswc_hyperspotter_spanish_tuning_v1.py",
    "_baxy_mswc_parakeet_metrics_v6",
)
_AUDIO = load_component(
    "extract_mswc_hyperspotter_logmel_v1.py",
    "_baxy_mswc_parakeet_audio_v6",
)


STT_FILES = (
    "encoder.int8.onnx",
    "decoder.int8.onnx",
    "joiner.int8.onnx",
    "tokens.txt",
)


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    unaccented = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", unaccented))


def normalized_edit_similarity(left: str, right: str) -> float:
    return 1.0 - _PAIR.edit_distance(left, right) / max(len(left), len(right), 1)


def transcript_candidate_scores(
    *, transcripts: list[str], candidate_words: list[list[str]], method: str
) -> np.ndarray:
    if method not in {"whole_transcript_edit", "whole_or_token_edit"}:
        raise ValueError("mswc_parakeet_tuning_method_invalid")
    if len(transcripts) != len(candidate_words) or not candidate_words:
        raise ValueError("mswc_parakeet_tuning_transcript_shape_invalid")
    width = len(candidate_words[0])
    if width < 2 or any(len(row) != width for row in candidate_words):
        raise ValueError("mswc_parakeet_tuning_candidate_shape_invalid")
    scores = np.empty((len(transcripts), width), dtype=np.float64)
    for row, (transcript, candidates) in enumerate(
        zip(transcripts, candidate_words, strict=True)
    ):
        normalized = normalize_text(transcript)
        tokens = normalized.split()
        for column, candidate in enumerate(candidates):
            target = normalize_text(candidate)
            values = [normalized_edit_similarity(normalized, target)]
            if method == "whole_or_token_edit":
                values.extend(
                    normalized_edit_similarity(token, target) for token in tokens
                )
            scores[row, column] = max(values)
    return scores


def evaluate(
    *,
    corpus_manifest_path: Path,
    corpus_root: Path,
    stt_directory: Path,
    av_site_packages: Path,
    output_path: Path,
    split_seed: int,
    tuning_classes: int,
    hard_negative_candidates: int,
    batch_size: int,
    num_threads: int,
) -> dict[str, object]:
    started = time.perf_counter()
    if (
        output_path.exists()
        or tuning_classes < 2
        or hard_negative_candidates < 1
        or batch_size < 1
        or num_threads < 1
    ):
        raise ValueError("mswc_parakeet_tuning_schedule_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    corpus_root = corpus_root.resolve(strict=True)
    stt_directory = stt_directory.resolve(strict=True)
    av_site_packages = av_site_packages.resolve(strict=True)
    output_path = output_path.resolve()
    corpus = _SEQUENCE.read_object(corpus_manifest_path)
    records_raw = corpus.get("records")
    if (
        corpus.get("schema")
        != "baxy.mswc-spanish-qbye-sequence-research-corpus.v3"
        or corpus.get("official_test_audio_accessed") is not False
        or corpus.get("blind_human_audio_accessed") is not False
        or corpus.get("speaker_reidentification_attempted") is not False
        or not isinstance(records_raw, list)
    ):
        raise ValueError("mswc_parakeet_tuning_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_parakeet_tuning_record_invalid")
        records.append(record)
    words = {str(record["class_name"]) for record in records}
    tuning_words, reserved_words = _SEQUENCE.split_research_words(
        words, seed=split_seed, tuning_classes=tuning_classes
    )
    query_records = [
        record
        for record in records
        if record.get("partition") == "open_keyword_query"
        and str(record["class_name"]) in tuning_words
    ]
    query_words = [str(record["class_name"]) for record in query_records]
    if len(query_records) != tuning_classes * 6 or set(query_words) != tuning_words:
        raise ValueError("mswc_parakeet_tuning_partition_invalid")
    hard_negatives = _PAIR.hard_negative_map(
        tuning_words, neighbors=hard_negative_candidates
    )
    candidate_words = [
        [word, *hard_negatives[word][:hard_negative_candidates]]
        for word in query_words
    ]
    missing = [name for name in STT_FILES if not (stt_directory / name).is_file()]
    if missing:
        raise FileNotFoundError(f"mswc_parakeet_tuning_bundle_incomplete:{missing[0]}")
    paths = []
    for record in query_records:
        relative = Path(str(record["relative_path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("mswc_parakeet_tuning_relative_path_invalid")
        path = (corpus_root / relative).resolve(strict=True)
        path.relative_to(corpus_root)
        if (
            path.stat().st_size != int(record["audio_bytes"])
            or _AUDIO.sha256(path) != record["audio_sha256"]
        ):
            raise ValueError("mswc_parakeet_tuning_audio_hash_invalid")
        paths.append(path)

    import sys

    sys.path.insert(0, str(av_site_packages))
    try:
        import av
    finally:
        sys.path.remove(str(av_site_packages))
    import sherpa_onnx

    load_started = time.perf_counter()
    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(stt_directory / "encoder.int8.onnx"),
        decoder=str(stt_directory / "decoder.int8.onnx"),
        joiner=str(stt_directory / "joiner.int8.onnx"),
        tokens=str(stt_directory / "tokens.txt"),
        num_threads=num_threads,
        model_type="nemo_transducer",
        decoding_method="modified_beam_search",
        max_active_paths=8,
    )
    warmup = recognizer.create_stream()
    warmup.accept_waveform(
        _AUDIO.SAMPLE_RATE, np.zeros(_AUDIO.SAMPLE_RATE // 2, dtype=np.float32)
    )
    recognizer.decode_stream(warmup)
    load_seconds = time.perf_counter() - load_started
    transcripts = []
    decode_started = time.perf_counter()
    for start in range(0, len(paths), batch_size):
        streams = []
        for path in paths[start : start + batch_size]:
            stream = recognizer.create_stream()
            stream.accept_waveform(_AUDIO.SAMPLE_RATE, _AUDIO.decode_opus(path, av))
            streams.append(stream)
        recognizer.decode_streams(streams)
        transcripts.extend(str(stream.result.text or "").strip() for stream in streams)
        stop = min(start + batch_size, len(paths))
        if stop % 400 == 0 or stop == len(paths):
            print(f"PARAKEET_TUNING|{stop}/{len(paths)}", flush=True)
    decode_seconds = time.perf_counter() - decode_started
    runs = []
    for method in ("whole_transcript_edit", "whole_or_token_edit"):
        scores = transcript_candidate_scores(
            transcripts=transcripts,
            candidate_words=candidate_words,
            method=method,
        )
        metrics = _METRICS.hard_pair_metrics(scores=scores, query_words=query_words)
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
        normalize_text(transcript) == normalize_text(word)
        for transcript, word in zip(transcripts, query_words, strict=True)
    )
    nonempty_transcripts = sum(bool(normalize_text(value)) for value in transcripts)
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
        "schema": "baxy.mswc-spanish-parakeet-tuning.v6",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "train_split_only_multilingual_parakeet_transcript_candidate_ranking",
        "sources": {
            "corpus_manifest_sha256": _AUDIO.sha256(corpus_manifest_path),
            "stt_files_sha256": {
                name: _AUDIO.sha256(stt_directory / name) for name in STT_FILES
            },
        },
        "contract": {
            "split_seed": split_seed,
            "tuning_word_classes": len(tuning_words),
            "reserved_word_classes": len(reserved_words),
            "query_examples_per_word": 6,
            "hard_negative_candidates_per_query": hard_negative_candidates,
            "decoding_method": "modified_beam_search",
            "max_active_paths": 8,
            "normalization": "nfkd_casefold_unaccented_ascii_alphanumeric_words",
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
            "load_and_warmup_seconds": load_seconds,
            "decode_seconds": decode_seconds,
            "total_seconds": time.perf_counter() - started,
            "num_threads": num_threads,
            "batch_size": batch_size,
            "sherpa_onnx": sherpa_onnx.__version__,
            "av": av.__version__,
        },
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
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--av-site-packages", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-seed", type=int, default=6501)
    parser.add_argument("--tuning-classes", type=int, default=400)
    parser.add_argument("--hard-negative-candidates", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-threads", type=int, default=6)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        corpus_manifest_path=args.corpus_manifest,
        corpus_root=args.corpus_root,
        stt_directory=args.stt_directory,
        av_site_packages=args.av_site_packages,
        output_path=args.output,
        split_seed=args.split_seed,
        tuning_classes=args.tuning_classes,
        hard_negative_candidates=args.hard_negative_candidates,
        batch_size=args.batch_size,
        num_threads=args.num_threads,
    )
    print(
        json.dumps(
            {
                "accepted": report["accepted"],
                "selected": report["selected"],
                "transcription_aggregates": report["transcription_aggregates"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
