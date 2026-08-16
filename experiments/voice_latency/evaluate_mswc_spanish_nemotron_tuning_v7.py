"""Evaluate local Nemotron 3.5 streaming ASR on MSWC Spanish tuning words."""

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
        raise RuntimeError(f"mswc_nemotron_tuning_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PARAKEET = load_component(
    "evaluate_mswc_spanish_parakeet_tuning_v6.py",
    "_baxy_mswc_nemotron_base_v7",
)


def decode_stream_batch(
    *,
    recognizer: object,
    audio_batch: list[np.ndarray],
    sample_rate: int,
    language: str,
    tail_padding_samples: int = 0,
) -> list[str]:
    streams = []
    for audio in audio_batch:
        stream = recognizer.create_stream()
        stream.set_option("language", language)
        values = np.asarray(audio, dtype=np.float32)
        if tail_padding_samples > 0:
            values = np.concatenate(
                (values, np.zeros(tail_padding_samples, dtype=np.float32))
            )
        stream.accept_waveform(sample_rate, values)
        stream.input_finished()
        streams.append(stream)
    while True:
        ready = [stream for stream in streams if recognizer.is_ready(stream)]
        if not ready:
            break
        recognizer.decode_streams(ready)
    transcripts = []
    for stream in streams:
        result = recognizer.get_result_all(stream)
        transcripts.append(
            str(result if isinstance(result, str) else getattr(result, "text", ""))
            .strip()
        )
    return transcripts


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
    language: str,
    tail_padding_seconds: float,
) -> dict[str, object]:
    started = time.perf_counter()
    if (
        output_path.exists()
        or tuning_classes < 2
        or hard_negative_candidates < 1
        or batch_size < 1
        or num_threads < 1
        or language not in {"es", "auto"}
        or not 0.0 <= tail_padding_seconds <= 3.0
    ):
        raise ValueError("mswc_nemotron_tuning_schedule_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    corpus_root = corpus_root.resolve(strict=True)
    stt_directory = stt_directory.resolve(strict=True)
    av_site_packages = av_site_packages.resolve(strict=True)
    output_path = output_path.resolve()
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
        raise ValueError("mswc_nemotron_tuning_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_nemotron_tuning_record_invalid")
        records.append(record)
    words = {str(record["class_name"]) for record in records}
    tuning_words, reserved_words = _PARAKEET._SEQUENCE.split_research_words(
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
        raise ValueError("mswc_nemotron_tuning_partition_invalid")
    hard_negatives = _PARAKEET._PAIR.hard_negative_map(
        tuning_words, neighbors=hard_negative_candidates
    )
    candidate_words = [
        [word, *hard_negatives[word][:hard_negative_candidates]]
        for word in query_words
    ]
    missing = [
        name
        for name in _PARAKEET.STT_FILES
        if not (stt_directory / name).is_file()
    ]
    if missing:
        raise FileNotFoundError(f"mswc_nemotron_tuning_bundle_incomplete:{missing[0]}")
    paths = []
    for record in query_records:
        relative = Path(str(record["relative_path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("mswc_nemotron_tuning_relative_path_invalid")
        path = (corpus_root / relative).resolve(strict=True)
        path.relative_to(corpus_root)
        if (
            path.stat().st_size != int(record["audio_bytes"])
            or _PARAKEET._AUDIO.sha256(path) != record["audio_sha256"]
        ):
            raise ValueError("mswc_nemotron_tuning_audio_hash_invalid")
        paths.append(path)

    sys.path.insert(0, str(av_site_packages))
    try:
        import av
    finally:
        sys.path.remove(str(av_site_packages))
    import sherpa_onnx

    load_started = time.perf_counter()
    recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
        encoder=str(stt_directory / "encoder.int8.onnx"),
        decoder=str(stt_directory / "decoder.int8.onnx"),
        joiner=str(stt_directory / "joiner.int8.onnx"),
        tokens=str(stt_directory / "tokens.txt"),
        num_threads=num_threads,
        model_type="nemo_transducer",
        decoding_method="greedy_search",
        enable_endpoint_detection=False,
        provider="cpu",
    )
    decode_stream_batch(
        recognizer=recognizer,
        audio_batch=[
            np.zeros(
                _PARAKEET._AUDIO.SAMPLE_RATE // 2, dtype=np.float32
            )
        ],
        sample_rate=_PARAKEET._AUDIO.SAMPLE_RATE,
        language=language,
        tail_padding_samples=int(
            round(tail_padding_seconds * _PARAKEET._AUDIO.SAMPLE_RATE)
        ),
    )
    load_seconds = time.perf_counter() - load_started
    transcripts = []
    decode_started = time.perf_counter()
    for start in range(0, len(paths), batch_size):
        audio_batch = [
            _PARAKEET._AUDIO.decode_opus(path, av)
            for path in paths[start : start + batch_size]
        ]
        transcripts.extend(
            decode_stream_batch(
                recognizer=recognizer,
                audio_batch=audio_batch,
                sample_rate=_PARAKEET._AUDIO.SAMPLE_RATE,
                language=language,
                tail_padding_samples=int(
                    round(tail_padding_seconds * _PARAKEET._AUDIO.SAMPLE_RATE)
                ),
            )
        )
        stop = min(start + batch_size, len(paths))
        if stop % 400 == 0 or stop == len(paths):
            print(f"NEMOTRON_TUNING|{stop}/{len(paths)}", flush=True)
    decode_seconds = time.perf_counter() - decode_started
    runs = []
    for method in ("whole_transcript_edit", "whole_or_token_edit"):
        scores = _PARAKEET.transcript_candidate_scores(
            transcripts=transcripts,
            candidate_words=candidate_words,
            method=method,
        )
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
        "schema": "baxy.mswc-spanish-nemotron-tuning.v7",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "train_split_only_nemotron35_spanish_transcript_candidate_ranking",
        "sources": {
            "corpus_manifest_sha256": _PARAKEET._AUDIO.sha256(
                corpus_manifest_path
            ),
            "stt_files_sha256": {
                name: _PARAKEET._AUDIO.sha256(stt_directory / name)
                for name in _PARAKEET.STT_FILES
            },
        },
        "contract": {
            "split_seed": split_seed,
            "tuning_word_classes": len(tuning_words),
            "reserved_word_classes": len(reserved_words),
            "query_examples_per_word": 6,
            "hard_negative_candidates_per_query": hard_negative_candidates,
            "language": language,
            "decoding_method": "greedy_search",
            "stream_input_finished": True,
            "tail_padding_seconds": tail_padding_seconds,
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
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--num-threads", type=int, default=6)
    parser.add_argument("--language", choices=("es", "auto"), default="es")
    parser.add_argument("--tail-padding-seconds", type=float, default=1.0)
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
        language=args.language,
        tail_padding_seconds=args.tail_padding_seconds,
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
