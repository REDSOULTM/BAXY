"""Evaluate all opened R16 SAPI commands with Faster-Whisper large-v3."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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


EXPECTED_ROWS = 337
REPORT_SCHEMA = "baxy.r16-sapi-faster-whisper-all-development.v1"
CORPUS_SCHEMA = "baxy.r16-sapi-faster-whisper-transcript-development.v1"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("baxy_faster_whisper_all_jsonl_invalid")
    return rows


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
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
    transcript_output_path: Path,
    model_name: str,
    device: str,
    compute_type: str,
    trailing_silence_seconds: float = base.TRAILING_SILENCE_SECONDS,
    retained_trailing_silence_seconds: float | None = None,
) -> dict[str, object]:
    for candidate in (output_path, transcript_output_path):
        if candidate.exists():
            raise ValueError(f"baxy_faster_whisper_all_output_exists:{candidate}")
    source_corpus_path = source_corpus_path.resolve(strict=True)
    parakeet_corpus_path = parakeet_corpus_path.resolve(strict=True)
    model_path = model_path.resolve(strict=True)
    runtime_dll_directory = runtime_dll_directory.resolve(strict=True)
    output_path = output_path.resolve()
    transcript_output_path = transcript_output_path.resolve()
    source_rows = read_jsonl(source_corpus_path)
    parakeet_rows = read_jsonl(parakeet_corpus_path)
    source_by_id = {str(row.get("case_id")): row for row in source_rows}
    if (
        len(source_rows) != 700
        or len(source_by_id) != 700
        or len(parakeet_rows) != EXPECTED_ROWS
        or len({str(row.get("case_id")) for row in parakeet_rows}) != EXPECTED_ROWS
        or any(row.get("execution_authority") is not False for row in parakeet_rows)
    ):
        raise ValueError("baxy_faster_whisper_all_population_invalid")
    for name in ("config.json", "model.bin", "tokenizer.json"):
        (model_path / name).resolve(strict=True)
    identities = {
        "sourceCorpusSha256": base.sha256(source_corpus_path),
        "parakeetCorpusSha256": base.sha256(parakeet_corpus_path),
        "modelTreeSha256": sha256_tree(model_path),
        "modelName": model_name,
        "device": device,
        "computeType": compute_type,
        "trailingSilenceSeconds": str(trailing_silence_seconds),
        "retainedTrailingSilenceSeconds": str(
            trailing_silence_seconds
            if retained_trailing_silence_seconds is None
            else retained_trailing_silence_seconds
        ),
    }
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial.json")
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if (
            checkpoint.get("identities") != identities
            or checkpoint.get("completed") != len(checkpoint.get("records", []))
        ):
            raise ValueError("baxy_faster_whisper_all_checkpoint_invalid")
    else:
        checkpoint = {
            "identities": identities,
            "completed": 0,
            "records": [],
            "synthesisSeconds": 0.0,
            "decodeSeconds": 0.0,
            "audioSeconds": 0.0,
        }

    dll_handle = os.add_dll_directory(str(runtime_dll_directory))
    os.environ["PATH"] = str(runtime_dll_directory) + os.pathsep + os.environ.get(
        "PATH", ""
    )
    from baxy_mind.effect_intent import resolve_explicit_effects
    from baxy_mind.voice import SileroVad
    from faster_whisper import WhisperModel

    available_operations = frozenset(
        operation
        for row in parakeet_rows
        for accepted in base.accepted_effect_sets(row)
        for operation in accepted
    )
    model = WhisperModel(
        str(model_path),
        device=device,
        compute_type=compute_type,
        cpu_threads=8,
        local_files_only=True,
    )
    vad = SileroVad()
    synthesizer = base.SapiSynthesizer()
    started = time.perf_counter()
    try:
        start_at = int(checkpoint["completed"])
        for index, transcript_row in enumerate(parakeet_rows[start_at:], start=start_at):
            case_id = str(transcript_row.get("case_id"))
            source = source_by_id.get(case_id)
            if (
                source is None
                or transcript_row.get("voice_reference_text_sha256")
                != hashlib.sha256(str(source.get("text", "")).encode("utf-8")).hexdigest()
            ):
                raise ValueError(f"baxy_faster_whisper_all_binding_invalid:{case_id}")
            began = time.perf_counter()
            speech_language = str(source.get("language"))
            audio = synthesizer.synthesize(
                "409" if speech_language == "en" else "80A",
                str(source.get("text")),
                rate=(-1, 0, 1)[index % 3],
            )
            checkpoint["synthesisSeconds"] += time.perf_counter() - began
            segmented = base.segment_with_product_vad(
                vad,
                audio,
                trailing_silence_seconds=trailing_silence_seconds,
                retained_trailing_silence_seconds=retained_trailing_silence_seconds,
            )
            began = time.perf_counter()
            text = ""
            detected_language = None
            language_probability = None
            if segmented is not None:
                segments, info = model.transcribe(
                    segmented,
                    beam_size=5,
                    best_of=5,
                    temperature=0.0,
                    condition_on_previous_text=False,
                    vad_filter=False,
                    without_timestamps=True,
                )
                text = " ".join(segment.text.strip() for segment in segments).strip()
                detected_language = info.language
                language_probability = info.language_probability
            checkpoint["decodeSeconds"] += time.perf_counter() - began
            checkpoint["audioSeconds"] += len(audio) / base.SAMPLE_RATE
            intent = (
                resolve_explicit_effects(text, available_operations) if text else None
            )
            actual = tuple(intent.operations) if intent is not None else ()
            reference_words = base.normalized_words(str(source.get("text")))
            hypothesis_words = base.normalized_words(text)
            checkpoint["records"].append(
                {
                    "caseId": case_id,
                    "language": speech_language,
                    "rate": (-1, 0, 1)[index % 3],
                    "vadSegmented": segmented is not None,
                    "transcript": text,
                    "detectedLanguage": detected_language,
                    "languageProbability": language_probability,
                    "referenceWordCount": len(reference_words),
                    "wordEdits": base.edit_distance(reference_words, hypothesis_words),
                    "actualOperations": list(actual),
                    "deterministicSemanticCorrect": actual
                    in base.accepted_effect_sets(source),
                    "unsafeEffect": source.get("outcome") != "action" and bool(actual),
                }
            )
            checkpoint["completed"] = index + 1
            write_json(checkpoint_path, checkpoint)
            print(f"BAXY_R16_FASTER_WHISPER_ALL|{index + 1}/{EXPECTED_ROWS}", flush=True)
    finally:
        synthesizer.close()
        dll_handle.close()

    records = checkpoint["records"]
    total_words = sum(int(row["referenceWordCount"]) for row in records)
    metrics = {
        "cases": len(records),
        "deterministicSemanticCorrect": sum(
            bool(row["deterministicSemanticCorrect"]) for row in records
        ),
        "semanticAccuracy": sum(
            bool(row["deterministicSemanticCorrect"]) for row in records
        ) / len(records),
        "wordErrorRate": sum(int(row["wordEdits"]) for row in records) / total_words,
        "unsafeEffects": sum(bool(row["unsafeEffect"]) for row in records),
        "allVadSegmented": all(bool(row["vadSegmented"]) for row in records),
        "audioSeconds": checkpoint["audioSeconds"],
        "synthesisSeconds": checkpoint["synthesisSeconds"],
        "decodeSeconds": checkpoint["decodeSeconds"],
        "audioRealtimeFactor": checkpoint["decodeSeconds"] / checkpoint["audioSeconds"],
    }
    report = {
        "schema": REPORT_SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_r16_local_sapi_post_wake_vad_faster_whisper_candidate",
        "sources": identities,
        "inference": {
            "model": model_name,
            "device": device,
            "computeType": compute_type,
            "beamSize": 5,
            "bestOf": 5,
            "language": "auto",
        },
        "vad": {
            "trailingSilenceSeconds": trailing_silence_seconds,
            "retainedTrailingSilenceSeconds": (
                trailing_silence_seconds
                if retained_trailing_silence_seconds is None
                else retained_trailing_silence_seconds
            ),
        },
        "metrics": metrics,
        "runtimeSeconds": time.perf_counter() - started,
        "records": records,
        "developmentOnly": True,
        "humanMicrophoneClaimSupported": False,
        "blindHoldoutClaimSupported": False,
        "candidateFrozen": False,
        "productOperatingPoint": False,
        "effectsExecuted": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_path, report)
    corpus_rows = []
    for source_row, record in zip(parakeet_rows, records, strict=True):
        row = dict(source_row)
        row.update(
            {
                "schema": CORPUS_SCHEMA,
                "text": record["transcript"],
                "transcript_authority": model_name,
            }
        )
        corpus_rows.append(row)
    temporary = transcript_output_path.with_suffix(transcript_output_path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in corpus_rows
        ),
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, transcript_output_path)
    checkpoint_path.unlink(missing_ok=True)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-corpus", type=Path, required=True)
    parser.add_argument("--parakeet-corpus", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--runtime-dll-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--transcript-output", type=Path, required=True)
    parser.add_argument("--model-name", default="faster-whisper-large-v3")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument(
        "--trailing-silence-seconds",
        type=float,
        default=base.TRAILING_SILENCE_SECONDS,
    )
    parser.add_argument("--retained-trailing-silence-seconds", type=float)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        source_corpus_path=arguments.source_corpus,
        parakeet_corpus_path=arguments.parakeet_corpus,
        model_path=arguments.model,
        runtime_dll_directory=arguments.runtime_dll_directory,
        output_path=arguments.output,
        transcript_output_path=arguments.transcript_output,
        model_name=arguments.model_name,
        device=arguments.device,
        compute_type=arguments.compute_type,
        trailing_silence_seconds=arguments.trailing_silence_seconds,
        retained_trailing_silence_seconds=(
            arguments.retained_trailing_silence_seconds
        ),
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
