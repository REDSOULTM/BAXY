"""Measure Parakeet on 2,400 opened human Spanish MSWC query clips.

This is a lexical STT gate, not a command-sentence or microphone-room claim.
The resumable checkpoint and final report retain aggregate counters only.
They never retain class names, speaker metadata, filenames, or transcripts.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import unicodedata

import numpy as np


SAMPLE_RATE = 16_000
STT_FILES = (
    "encoder.int8.onnx",
    "decoder.int8.onnx",
    "joiner.int8.onnx",
    "tokens.txt",
)
TARGET_ACCURACY = 0.99
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("baxy_parakeet_mswc_json_invalid")
    return value


def normalized_words(value: str) -> tuple[str, ...]:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return tuple(_WORD_RE.findall(plain))


def levenshtein_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1]
                    + (left_character != right_character),
                )
            )
        previous = current
    return previous[-1]


def decode_audio(ffmpeg_path: Path, audio_path: Path) -> np.ndarray:
    completed = subprocess.run(
        [
            str(ffmpeg_path),
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(audio_path),
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "pipe:1",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    audio = np.frombuffer(completed.stdout, dtype="<f4").copy()
    if audio.size == 0 or not np.isfinite(audio).all():
        raise ValueError("baxy_parakeet_mswc_audio_invalid")
    return audio


def validate_corpus(corpus: dict[str, object]) -> tuple[list[dict[str, object]], list[str]]:
    records = corpus.get("records")
    classes = corpus.get("evaluation_words")
    contract = corpus.get("contract")
    if (
        corpus.get("schema")
        != "baxy.mswc-spanish-qbye-fresh-evaluation-corpus.v2"
        or corpus.get("official_test_audio_accessed") is not False
        or corpus.get("blind_human_audio_accessed") is not False
        or corpus.get("speaker_reidentification_attempted") is not False
        or not isinstance(records, list)
        or len(records) != 3_200
        or not isinstance(classes, list)
        or len(classes) != 200
        or len(set(map(str, classes))) != 200
        or not isinstance(contract, dict)
        or contract.get("query_examples_per_class") != 12
        or contract.get("all_examples_use_distinct_speakers_within_each_word")
        is not True
    ):
        raise ValueError("baxy_parakeet_mswc_corpus_invalid")
    queries = [
        record
        for record in records
        if isinstance(record, dict)
        and record.get("partition") == "open_keyword_query"
    ]
    if len(queries) != 2_400:
        raise ValueError("baxy_parakeet_mswc_queries_invalid")
    class_names = sorted(map(str, classes))
    class_set = set(class_names)
    if any(
        str(record.get("class_name")) not in class_set
        or not isinstance(record.get("relative_path"), str)
        or not isinstance(record.get("audio_sha256"), str)
        for record in queries
    ):
        raise ValueError("baxy_parakeet_mswc_query_contract_invalid")
    return queries, class_names


def empty_checkpoint(identities: dict[str, str], class_count: int) -> dict[str, object]:
    return {
        "schema": "baxy.parakeet-mswc-spanish-word-checkpoint.v1",
        "identities": identities,
        "completedRecords": 0,
        "exactCorrect": 0,
        "targetPresentCorrect": 0,
        "emptyTranscripts": 0,
        "editDistanceSum": 0,
        "referenceCharacters": 0,
        "audioSeconds": 0.0,
        "decodeSeconds": 0.0,
        "classTotals": [0] * class_count,
        "classCorrect": [0] * class_count,
    }


def load_checkpoint(
    path: Path, identities: dict[str, str], class_count: int
) -> dict[str, object]:
    if not path.exists():
        return empty_checkpoint(identities, class_count)
    value = read_object(path)
    if (
        value.get("schema")
        != "baxy.parakeet-mswc-spanish-word-checkpoint.v1"
        or value.get("identities") != identities
        or not isinstance(value.get("completedRecords"), int)
        or not 0 <= int(value["completedRecords"]) <= 2_400
        or not isinstance(value.get("classTotals"), list)
        or len(value["classTotals"]) != class_count
        or not isinstance(value.get("classCorrect"), list)
        or len(value["classCorrect"]) != class_count
    ):
        raise ValueError("baxy_parakeet_mswc_checkpoint_invalid")
    return value


def write_checkpoint(path: Path, checkpoint: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(checkpoint, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def summarize(checkpoint: dict[str, object]) -> dict[str, object]:
    count = int(checkpoint["completedRecords"])
    if count <= 0:
        raise ValueError("baxy_parakeet_mswc_summary_empty")
    class_totals = np.asarray(checkpoint["classTotals"], dtype=np.int64)
    class_correct = np.asarray(checkpoint["classCorrect"], dtype=np.int64)
    if np.any(class_totals <= 0) or np.any(class_correct > class_totals):
        raise ValueError("baxy_parakeet_mswc_class_summary_invalid")
    exact = int(checkpoint["exactCorrect"]) / count
    target = int(checkpoint["targetPresentCorrect"]) / count
    macro = float(np.mean(class_correct / class_totals))
    cer = int(checkpoint["editDistanceSum"]) / int(
        checkpoint["referenceCharacters"]
    )
    return {
        "queryClips": count,
        "wordClasses": len(class_totals),
        "exactUtteranceAccuracy": exact,
        "targetTokenRecall": target,
        "macroExactUtteranceAccuracy": macro,
        "characterErrorRate": cer,
        "emptyTranscripts": int(checkpoint["emptyTranscripts"]),
        "audioSeconds": float(checkpoint["audioSeconds"]),
        "decodeSeconds": float(checkpoint["decodeSeconds"]),
        "audioRealtimeFactor": float(checkpoint["decodeSeconds"])
        / float(checkpoint["audioSeconds"]),
    }


def evaluate(
    *,
    corpus_manifest_path: Path,
    stt_directory: Path,
    ffmpeg_path: Path,
    output_path: Path,
    batch_size: int,
    decode_workers: int,
) -> dict[str, object]:
    if output_path.exists() or batch_size < 1 or decode_workers < 1:
        raise ValueError("baxy_parakeet_mswc_schedule_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    stt_directory = stt_directory.resolve(strict=True)
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    corpus = read_object(corpus_manifest_path)
    queries, classes = validate_corpus(corpus)
    class_indexes = {name: index for index, name in enumerate(classes)}
    corpus_root = corpus_manifest_path.parent
    for name in STT_FILES:
        (stt_directory / name).resolve(strict=True)
    identities = {
        "corpusManifestSha256": sha256(corpus_manifest_path),
        "ffmpegSha256": sha256(ffmpeg_path),
        **{f"stt:{name}": sha256(stt_directory / name) for name in STT_FILES},
    }
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial.json")
    checkpoint = load_checkpoint(checkpoint_path, identities, len(classes))

    import sherpa_onnx

    load_started = time.perf_counter()
    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(stt_directory / "encoder.int8.onnx"),
        decoder=str(stt_directory / "decoder.int8.onnx"),
        joiner=str(stt_directory / "joiner.int8.onnx"),
        tokens=str(stt_directory / "tokens.txt"),
        num_threads=6,
        model_type="nemo_transducer",
        decoding_method="modified_beam_search",
        max_active_paths=8,
    )
    warmup = recognizer.create_stream()
    warmup.accept_waveform(SAMPLE_RATE, np.zeros(SAMPLE_RATE // 2, np.float32))
    recognizer.decode_stream(warmup)
    load_seconds = time.perf_counter() - load_started

    with ThreadPoolExecutor(max_workers=decode_workers) as pool:
        for start in range(int(checkpoint["completedRecords"]), len(queries), batch_size):
            batch = queries[start : min(start + batch_size, len(queries))]

            def decode_record(record: dict[str, object]) -> np.ndarray:
                path = (corpus_root / str(record["relative_path"])).resolve(
                    strict=True
                )
                if sha256(path) != record["audio_sha256"]:
                    raise ValueError("baxy_parakeet_mswc_audio_hash_mismatch")
                return decode_audio(ffmpeg_path, path)

            audios = list(pool.map(decode_record, batch))
            streams = []
            for audio in audios:
                stream = recognizer.create_stream()
                stream.accept_waveform(SAMPLE_RATE, audio)
                streams.append(stream)
            decode_started = time.perf_counter()
            recognizer.decode_streams(streams)
            checkpoint["decodeSeconds"] = float(checkpoint["decodeSeconds"]) + (
                time.perf_counter() - decode_started
            )
            class_totals = checkpoint["classTotals"]
            class_correct = checkpoint["classCorrect"]
            for record, audio, stream in zip(batch, audios, streams, strict=True):
                reference_words = normalized_words(str(record["class_name"]))
                if len(reference_words) != 1:
                    raise ValueError("baxy_parakeet_mswc_reference_invalid")
                reference = reference_words[0]
                hypothesis_words = normalized_words(str(stream.result.text or ""))
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
                ) + levenshtein_distance(reference, hypothesis)
                checkpoint["referenceCharacters"] = int(
                    checkpoint["referenceCharacters"]
                ) + len(reference)
                checkpoint["audioSeconds"] = float(checkpoint["audioSeconds"]) + (
                    len(audio) / SAMPLE_RATE
                )
            checkpoint["completedRecords"] = start + len(batch)
            write_checkpoint(checkpoint_path, checkpoint)
            print(
                f"BAXY_PARAKEET_MSWC|{checkpoint['completedRecords']}/{len(queries)}",
                flush=True,
            )

    metrics = summarize(checkpoint)
    gate = {
        "minimumExactUtteranceAccuracy": metrics["exactUtteranceAccuracy"]
        >= TARGET_ACCURACY,
        "minimumTargetTokenRecall": metrics["targetTokenRecall"] >= TARGET_ACCURACY,
        "minimumMacroExactUtteranceAccuracy": metrics[
            "macroExactUtteranceAccuracy"
        ]
        >= TARGET_ACCURACY,
        "zeroEmptyTranscripts": metrics["emptyTranscripts"] == 0,
    }
    report: dict[str, object] = {
        "schema": "baxy.parakeet-mswc-spanish-word-gate.v1",
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
            "aggregateCheckpointOnly": True,
        },
        "metrics": metrics,
        "gate": {"passed": all(gate.values()), "checks": gate},
        "runtime": {
            "loadAndWarmupSeconds": load_seconds,
            "batchSize": batch_size,
            "decodeWorkers": decode_workers,
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
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--decode-workers", type=int, default=8)
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
    )
    print(json.dumps({"passed": report["gate"]["passed"], "metrics": report["metrics"]}, sort_keys=True))
    return 0 if report["gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
