"""Reject or retain a Faster-Whisper candidate on one opened R16 SAPI case.

This is a development diagnostic, not a product gate.  The reference labels are
used only after decoding to score the result; they are never passed to the ASR.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

import evaluate_r16_sapi_voice_semantics_development_v1 as base  # noqa: E402
from audit_ccby_wake_development_faster_whisper_v1 import (  # noqa: E402
    sha256_tree,
)


REPORT_SCHEMA = "baxy.r16-sapi-faster-whisper-turbo-pilot-development.v1"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("baxy_faster_whisper_turbo_pilot_jsonl_invalid")
    return rows


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def evaluate(
    *,
    source_corpus_path: Path,
    parakeet_corpus_path: Path,
    model_path: Path,
    runtime_dll_directory: Path,
    output_path: Path,
    case_id: str,
    model_name: str,
    devices: tuple[tuple[str, str], ...],
    trailing_silence_seconds: float,
    retained_trailing_silence_seconds: float,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError(f"baxy_faster_whisper_turbo_pilot_output_exists:{output_path}")
    source_corpus_path = source_corpus_path.resolve(strict=True)
    parakeet_corpus_path = parakeet_corpus_path.resolve(strict=True)
    model_path = model_path.resolve(strict=True)
    runtime_dll_directory = runtime_dll_directory.resolve(strict=True)
    output_path = output_path.resolve()
    for name in ("config.json", "model.bin", "tokenizer.json"):
        (model_path / name).resolve(strict=True)

    source_rows = read_jsonl(source_corpus_path)
    parakeet_rows = read_jsonl(parakeet_corpus_path)
    matching_sources = [row for row in source_rows if row.get("case_id") == case_id]
    matching_transcripts = [
        (index, row)
        for index, row in enumerate(parakeet_rows)
        if row.get("case_id") == case_id
    ]
    if len(matching_sources) != 1 or len(matching_transcripts) != 1:
        raise ValueError(f"baxy_faster_whisper_turbo_pilot_case_invalid:{case_id}")
    source = matching_sources[0]
    transcript_index, parakeet = matching_transcripts[0]
    reference_text = str(source.get("text", ""))
    if parakeet.get("voice_reference_text_sha256") != hashlib.sha256(
        reference_text.encode("utf-8")
    ).hexdigest():
        raise ValueError(f"baxy_faster_whisper_turbo_pilot_binding_invalid:{case_id}")

    from baxy_mind.effect_intent import resolve_explicit_effects
    from baxy_mind.voice import SileroVad
    from faster_whisper import WhisperModel

    available_operations = frozenset(
        operation
        for row in parakeet_rows
        for accepted in base.accepted_effect_sets(row)
        for operation in accepted
    )
    speech_language = str(source.get("language"))
    rate = (-1, 0, 1)[transcript_index % 3]
    synthesizer = base.SapiSynthesizer()
    try:
        synthesis_started = time.perf_counter()
        audio = synthesizer.synthesize(
            "409" if speech_language == "en" else "80A",
            reference_text,
            rate=rate,
        )
        synthesis_seconds = time.perf_counter() - synthesis_started
    finally:
        synthesizer.close()
    segmented = base.segment_with_product_vad(
        SileroVad(),
        audio,
        trailing_silence_seconds=trailing_silence_seconds,
        retained_trailing_silence_seconds=retained_trailing_silence_seconds,
    )
    if segmented is None:
        raise ValueError(f"baxy_faster_whisper_turbo_pilot_vad_failed:{case_id}")

    dll_handle = os.add_dll_directory(str(runtime_dll_directory))
    os.environ["PATH"] = str(runtime_dll_directory) + os.pathsep + os.environ.get(
        "PATH", ""
    )
    results: list[dict[str, object]] = []
    try:
        for device, compute_type in devices:
            load_started = time.perf_counter()
            model = WhisperModel(
                str(model_path),
                device=device,
                compute_type=compute_type,
                cpu_threads=8,
                local_files_only=True,
            )
            load_seconds = time.perf_counter() - load_started
            decode_started = time.perf_counter()
            segments, information = model.transcribe(
                segmented,
                beam_size=5,
                best_of=5,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=False,
                without_timestamps=True,
                word_timestamps=True,
            )
            decoded = list(segments)
            decode_seconds = time.perf_counter() - decode_started
            text = " ".join(segment.text.strip() for segment in decoded).strip()
            intent = (
                resolve_explicit_effects(text, available_operations) if text else None
            )
            actual = tuple(intent.operations) if intent is not None else ()
            accepted = base.accepted_effect_sets(source)
            results.append(
                {
                    "device": device,
                    "computeType": compute_type,
                    "transcript": text,
                    "detectedLanguage": information.language,
                    "languageProbability": information.language_probability,
                    "loadSeconds": load_seconds,
                    "decodeSeconds": decode_seconds,
                    "audioRealtimeFactor": decode_seconds
                    / (len(segmented) / base.SAMPLE_RATE),
                    "actualOperations": list(actual),
                    "deterministicSemanticCorrect": actual in accepted,
                    "averageLogProbabilities": [
                        segment.avg_logprob for segment in decoded
                    ],
                    "words": [
                        {"text": word.word, "probability": word.probability}
                        for segment in decoded
                        for word in (segment.words or [])
                    ],
                }
            )
            del decoded, segments, model
            gc.collect()
    finally:
        dll_handle.close()

    semantic_successes = sum(
        bool(result["deterministicSemanticCorrect"]) for result in results
    )
    report: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_r16_single_sapi_candidate_rejection_pilot",
        "sources": {
            "sourceCorpusSha256": file_sha256(source_corpus_path),
            "parakeetCorpusSha256": file_sha256(parakeet_corpus_path),
            "modelTreeSha256": sha256_tree(model_path),
            "modelName": model_name,
        },
        "case": {
            "caseId": case_id,
            "language": speech_language,
            "rate": rate,
            "referenceTextSha256": hashlib.sha256(
                reference_text.encode("utf-8")
            ).hexdigest(),
        },
        "audio": {
            "seconds": len(audio) / base.SAMPLE_RATE,
            "segmentedSeconds": len(segmented) / base.SAMPLE_RATE,
            "synthesisSeconds": synthesis_seconds,
            "trailingSilenceSeconds": trailing_silence_seconds,
            "retainedTrailingSilenceSeconds": retained_trailing_silence_seconds,
        },
        "decoding": {
            "beamSize": 5,
            "bestOf": 5,
            "temperature": 0.0,
            "language": "auto",
            "initialPrompt": None,
            "hotwords": None,
            "expectedLabelsAvailableToAsr": False,
        },
        "results": results,
        "promotion": {
            "promoted": semantic_successes == len(results),
            "semanticSuccesses": semantic_successes,
            "evaluatedProfiles": len(results),
            "rejectionReasons": (
                []
                if semantic_successes == len(results)
                else ["opened_failure_not_recovered"]
            ),
        },
        "effectsExecuted": 0,
        "developmentOnly": True,
        "humanMicrophoneClaimSupported": False,
        "blindHoldoutClaimSupported": False,
        "candidateFrozen": False,
        "productOperatingPoint": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_path, report)
    return report


def parse_device(value: str) -> tuple[str, str]:
    device, separator, compute_type = value.partition(":")
    if separator != ":" or device not in {"cpu", "cuda"} or not compute_type:
        raise argparse.ArgumentTypeError("expected cpu:TYPE or cuda:TYPE")
    return device, compute_type


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-corpus", type=Path, required=True)
    parser.add_argument("--parakeet-corpus", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--runtime-dll-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument(
        "--device",
        dest="devices",
        action="append",
        type=parse_device,
        required=True,
    )
    parser.add_argument("--trailing-silence-seconds", type=float, default=0.95)
    parser.add_argument(
        "--retained-trailing-silence-seconds", type=float, default=0.70
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        source_corpus_path=arguments.source_corpus,
        parakeet_corpus_path=arguments.parakeet_corpus,
        model_path=arguments.model,
        runtime_dll_directory=arguments.runtime_dll_directory,
        output_path=arguments.output,
        case_id=arguments.case_id,
        model_name=arguments.model_name,
        devices=tuple(arguments.devices),
        trailing_silence_seconds=arguments.trailing_silence_seconds,
        retained_trailing_silence_seconds=arguments.retained_trailing_silence_seconds,
    )
    print(json.dumps(report["promotion"], sort_keys=True))
    return 0 if report["promotion"]["promoted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
