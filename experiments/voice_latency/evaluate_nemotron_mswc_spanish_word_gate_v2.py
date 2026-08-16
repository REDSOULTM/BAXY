"""Measure Nemotron Streaming on 2,400 opened human Spanish MSWC clips.

This is the fixed comparison arm for Parakeet's lexical STT gate.  It uses
the already-selected Spanish language and one-second final padding from the
earlier train-split tuning campaign; no threshold or decode option is tuned
on these opened evaluation clips.  Checkpoints and reports retain aggregate
counters only, never words, speakers, paths, or transcripts.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
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
        raise RuntimeError(f"baxy_nemotron_word_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PARAKEET = load_component(
    "evaluate_parakeet_mswc_spanish_word_gate_v1.py",
    "_baxy_parakeet_word_gate_base_v1",
)

SAMPLE_RATE = _PARAKEET.SAMPLE_RATE
STT_FILES = _PARAKEET.STT_FILES
TARGET_ACCURACY = _PARAKEET.TARGET_ACCURACY
LANGUAGE = "es"
TAIL_PADDING_SECONDS = 1.0


def decode_stream_batch(
    *,
    recognizer: object,
    audio_batch: list[np.ndarray],
    sample_rate: int,
    language: str,
    tail_padding_samples: int,
) -> list[str]:
    streams = []
    for audio in audio_batch:
        stream = recognizer.create_stream()
        stream.set_option("language", language)
        values = np.asarray(audio, dtype=np.float32)
        if tail_padding_samples:
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
    stt_directory: Path,
    ffmpeg_path: Path,
    output_path: Path,
    batch_size: int,
    decode_workers: int,
    num_threads: int,
) -> dict[str, object]:
    if (
        output_path.exists()
        or batch_size < 1
        or decode_workers < 1
        or num_threads < 1
    ):
        raise ValueError("baxy_nemotron_mswc_schedule_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    stt_directory = stt_directory.resolve(strict=True)
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    corpus = _PARAKEET.read_object(corpus_manifest_path)
    queries, classes = _PARAKEET.validate_corpus(corpus)
    class_indexes = {name: index for index, name in enumerate(classes)}
    corpus_root = corpus_manifest_path.parent
    for name in STT_FILES:
        (stt_directory / name).resolve(strict=True)
    identities = {
        "corpusManifestSha256": _PARAKEET.sha256(corpus_manifest_path),
        "ffmpegSha256": _PARAKEET.sha256(ffmpeg_path),
        **{
            f"stt:{name}": _PARAKEET.sha256(stt_directory / name)
            for name in STT_FILES
        },
        "language": LANGUAGE,
        "tailPaddingSeconds": str(TAIL_PADDING_SECONDS),
    }
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial.json")
    checkpoint = _PARAKEET.load_checkpoint(
        checkpoint_path, identities, len(classes)
    )

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
    tail_padding_samples = int(round(TAIL_PADDING_SECONDS * SAMPLE_RATE))
    decode_stream_batch(
        recognizer=recognizer,
        audio_batch=[np.zeros(SAMPLE_RATE // 2, dtype=np.float32)],
        sample_rate=SAMPLE_RATE,
        language=LANGUAGE,
        tail_padding_samples=tail_padding_samples,
    )
    load_seconds = time.perf_counter() - load_started

    with ThreadPoolExecutor(max_workers=decode_workers) as pool:
        for start in range(int(checkpoint["completedRecords"]), len(queries), batch_size):
            batch = queries[start : min(start + batch_size, len(queries))]

            def decode_record(record: dict[str, object]) -> np.ndarray:
                path = (corpus_root / str(record["relative_path"])).resolve(
                    strict=True
                )
                if _PARAKEET.sha256(path) != record["audio_sha256"]:
                    raise ValueError("baxy_nemotron_mswc_audio_hash_mismatch")
                return _PARAKEET.decode_audio(ffmpeg_path, path)

            audios = list(pool.map(decode_record, batch))
            decode_started = time.perf_counter()
            transcripts = decode_stream_batch(
                recognizer=recognizer,
                audio_batch=audios,
                sample_rate=SAMPLE_RATE,
                language=LANGUAGE,
                tail_padding_samples=tail_padding_samples,
            )
            checkpoint["decodeSeconds"] = float(checkpoint["decodeSeconds"]) + (
                time.perf_counter() - decode_started
            )
            class_totals = checkpoint["classTotals"]
            class_correct = checkpoint["classCorrect"]
            for record, audio, transcript in zip(
                batch, audios, transcripts, strict=True
            ):
                reference_words = _PARAKEET.normalized_words(
                    str(record["class_name"])
                )
                if len(reference_words) != 1:
                    raise ValueError("baxy_nemotron_mswc_reference_invalid")
                reference = reference_words[0]
                hypothesis_words = _PARAKEET.normalized_words(transcript)
                exact = hypothesis_words == (reference,)
                target_present = reference in hypothesis_words
                hypothesis = "".join(hypothesis_words)
                class_index = class_indexes[str(record["class_name"])]
                class_totals[class_index] = int(class_totals[class_index]) + 1
                class_correct[class_index] = int(class_correct[class_index]) + int(
                    exact
                )
                checkpoint["exactCorrect"] = int(checkpoint["exactCorrect"]) + int(
                    exact
                )
                checkpoint["targetPresentCorrect"] = int(
                    checkpoint["targetPresentCorrect"]
                ) + int(target_present)
                checkpoint["emptyTranscripts"] = int(
                    checkpoint["emptyTranscripts"]
                ) + int(not hypothesis_words)
                checkpoint["editDistanceSum"] = int(
                    checkpoint["editDistanceSum"]
                ) + _PARAKEET.levenshtein_distance(reference, hypothesis)
                checkpoint["referenceCharacters"] = int(
                    checkpoint["referenceCharacters"]
                ) + len(reference)
                checkpoint["audioSeconds"] = float(checkpoint["audioSeconds"]) + (
                    len(audio) / SAMPLE_RATE
                )
            checkpoint["completedRecords"] = start + len(batch)
            _PARAKEET.write_checkpoint(checkpoint_path, checkpoint)
            print(
                f"BAXY_NEMOTRON_MSWC|{checkpoint['completedRecords']}/{len(queries)}",
                flush=True,
            )

    metrics = _PARAKEET.summarize(checkpoint)
    checks = {
        "minimumExactUtteranceAccuracy": metrics["exactUtteranceAccuracy"]
        >= TARGET_ACCURACY,
        "minimumTargetTokenRecall": metrics["targetTokenRecall"]
        >= TARGET_ACCURACY,
        "minimumMacroExactUtteranceAccuracy": metrics[
            "macroExactUtteranceAccuracy"
        ]
        >= TARGET_ACCURACY,
        "zeroEmptyTranscripts": metrics["emptyTranscripts"] == 0,
    }
    report: dict[str, object] = {
        "schema": "baxy.nemotron-mswc-spanish-word-gate.v2",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_human_spanish_isolated_word_stt_measurement",
        "sources": identities,
        "contract": {
            "queryPartitionOnly": True,
            "queryClipsExpected": 2_400,
            "wordClassesExpected": 200,
            "distinctSpeakersWithinEachWord": True,
            "normalization": "unicode_casefold_strip_diacritics_letter_tokens",
            "targetAccuracy": TARGET_ACCURACY,
            "language": LANGUAGE,
            "tailPaddingSeconds": TAIL_PADDING_SECONDS,
            "decodingMethod": "greedy_search",
            "decodeOptionsFixedBeforeThisMeasurement": True,
            "aggregateCheckpointOnly": True,
        },
        "metrics": metrics,
        "gate": {"passed": all(checks.values()), "checks": checks},
        "runtime": {
            "loadAndWarmupSeconds": load_seconds,
            "batchSize": batch_size,
            "decodeWorkers": decode_workers,
            "numThreads": num_threads,
        },
        "freshHoldoutClaimSupported": False,
        "commandSentenceClaimSupported": False,
        "microphoneRoomClaimSupported": False,
        "officialTestAudioAccessed": False,
        "blindHumanAudioAccessed": False,
        "speakerReidentificationAttempted": False,
        "recordsClassesSpeakersFilenamesOrTranscriptsRetained": False,
        "effectsExecuted": 0,
    }
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    checkpoint_path.unlink(missing_ok=True)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--decode-workers", type=int, default=8)
    parser.add_argument("--num-threads", type=int, default=6)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        corpus_manifest_path=arguments.corpus_manifest,
        stt_directory=arguments.stt_directory,
        ffmpeg_path=arguments.ffmpeg,
        output_path=arguments.output,
        batch_size=arguments.batch_size,
        decode_workers=arguments.decode_workers,
        num_threads=arguments.num_threads,
    )
    print(
        json.dumps(
            {"passed": report["gate"]["passed"], "metrics": report["metrics"]},
            sort_keys=True,
        )
    )
    return 0 if report["gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
