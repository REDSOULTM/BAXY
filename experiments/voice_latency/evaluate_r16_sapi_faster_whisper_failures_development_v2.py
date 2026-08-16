"""Rescore opened R16 Parakeet route failures with Faster-Whisper large-v3."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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


EXPECTED_FAILURES = 88
DOMAIN_HOTWORDS = (
    "BAXY Windows assistant comandos commands aplicación application audio archivos files "
    "portapapeles clipboard captura screenshot OCR readable text correo email calendario "
    "calendar recordatorio reminder tareas tasks Wi-Fi Bluetooth ventanas windows multimedia "
    "media playback state playing paquetes packages instalar install impresora printer cámara "
    "camera micrófono microphone volumen volume red network navegador browser pestañas tabs "
    "documento document notas notes notificaciones notifications copia backup streaming"
)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    values = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if any(not isinstance(value, dict) for value in values):
        raise ValueError("baxy_faster_whisper_jsonl_invalid")
    return values


def select_failures(
    *,
    source_rows: list[dict[str, object]],
    transcript_rows: list[dict[str, object]],
    route_report: dict[str, object],
) -> list[tuple[int, dict[str, object], dict[str, object]]]:
    source_by_id = {str(row.get("case_id")): row for row in source_rows}
    route_rows = route_report.get("rows") if isinstance(route_report, dict) else None
    if (
        len(source_by_id) != 700
        or len(transcript_rows) != 337
        or not isinstance(route_rows, list)
        or len(route_rows) != 337
    ):
        raise ValueError("baxy_faster_whisper_population_invalid")
    failed = {
        str(row.get("case_id"))
        for row in route_rows
        if row.get("contract_correct") is False
    }
    selected: list[tuple[int, dict[str, object], dict[str, object]]] = []
    for index, transcript in enumerate(transcript_rows):
        case_id = str(transcript.get("case_id"))
        source = source_by_id.get(case_id)
        if (
            case_id not in failed
            or source is None
            or transcript.get("voice_reference_text_sha256")
            != base.hashlib.sha256(str(source.get("text", "")).encode("utf-8")).hexdigest()
        ):
            continue
        selected.append((index, source, transcript))
    if len(selected) != EXPECTED_FAILURES:
        raise ValueError("baxy_faster_whisper_failure_count_invalid")
    return selected


def evaluate(
    *,
    source_corpus_path: Path,
    transcript_corpus_path: Path,
    route_report_path: Path,
    model_path: Path,
    runtime_dll_directory: Path,
    output_path: Path,
    hotwords: str | None,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("baxy_faster_whisper_output_exists")
    source_corpus_path = source_corpus_path.resolve(strict=True)
    transcript_corpus_path = transcript_corpus_path.resolve(strict=True)
    route_report_path = route_report_path.resolve(strict=True)
    model_path = model_path.resolve(strict=True)
    runtime_dll_directory = runtime_dll_directory.resolve(strict=True)
    output_path = output_path.resolve()
    source_rows = read_jsonl(source_corpus_path)
    transcript_rows = read_jsonl(transcript_corpus_path)
    route_report = json.loads(route_report_path.read_text(encoding="utf-8-sig"))
    if (
        route_report.get("schema")
        != "baxy.r16-sapi-voice-product-route-development.v5"
        or route_report.get("metrics", {}).get("contract_correct") != 249
        or route_report.get("metrics", {}).get("unsafe_effects") != 7
        or route_report.get("effects_executed") != 0
    ):
        raise ValueError("baxy_faster_whisper_route_evidence_invalid")
    selected = select_failures(
        source_rows=source_rows,
        transcript_rows=transcript_rows,
        route_report=route_report,
    )
    for name in ("config.json", "model.bin", "tokenizer.json"):
        (model_path / name).resolve(strict=True)
    dll_handle = os.add_dll_directory(str(runtime_dll_directory))
    os.environ["PATH"] = str(runtime_dll_directory) + os.pathsep + os.environ.get(
        "PATH", ""
    )

    from baxy_mind.effect_intent import resolve_explicit_effects
    from baxy_mind.voice import SileroVad
    from faster_whisper import WhisperModel

    available_operations = frozenset(
        operation
        for _, _, row in selected
        for accepted in base.accepted_effect_sets(row)
        for operation in accepted
    )
    model = WhisperModel(
        str(model_path),
        device="cuda",
        compute_type="float16",
        cpu_threads=8,
        local_files_only=True,
    )
    vad = SileroVad()
    synthesizer = base.SapiSynthesizer()
    records: list[dict[str, object]] = []
    synthesis_seconds = 0.0
    decode_seconds = 0.0
    audio_seconds = 0.0
    started = time.perf_counter()
    try:
        for position, (original_index, source, transcript_row) in enumerate(selected):
            began = time.perf_counter()
            language = str(source["language"])
            audio = synthesizer.synthesize(
                "409" if language == "en" else "80A",
                str(source["text"]),
                rate=(-1, 0, 1)[original_index % 3],
            )
            synthesis_seconds += time.perf_counter() - began
            segmented = base.segment_with_product_vad(vad, audio)
            began = time.perf_counter()
            faster_transcript = ""
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
                    hotwords=hotwords,
                )
                faster_transcript = " ".join(
                    segment.text.strip() for segment in segments
                ).strip()
                detected_language = info.language
                language_probability = info.language_probability
            decode_seconds += time.perf_counter() - began
            audio_seconds += len(audio) / base.SAMPLE_RATE
            intent = (
                resolve_explicit_effects(faster_transcript, available_operations)
                if faster_transcript
                else None
            )
            actual = tuple(intent.operations) if intent is not None else ()
            reference_words = base.normalized_words(str(source["text"]))
            parakeet_words = base.normalized_words(str(transcript_row["text"]))
            faster_words = base.normalized_words(faster_transcript)
            records.append(
                {
                    "caseId": source["case_id"],
                    "language": language,
                    "rate": (-1, 0, 1)[original_index % 3],
                    "vadSegmented": segmented is not None,
                    "parakeetTranscript": transcript_row["text"],
                    "fasterWhisperTranscript": faster_transcript,
                    "detectedLanguage": detected_language,
                    "languageProbability": language_probability,
                    "referenceWordCount": len(reference_words),
                    "parakeetWordEdits": base.edit_distance(
                        reference_words, parakeet_words
                    ),
                    "fasterWhisperWordEdits": base.edit_distance(
                        reference_words, faster_words
                    ),
                    "actualOperations": list(actual),
                    "deterministicSemanticCorrect": actual
                    in base.accepted_effect_sets(source),
                }
            )
            print(
                f"BAXY_R16_FASTER_WHISPER|{position + 1}/{len(selected)}",
                flush=True,
            )
    finally:
        synthesizer.close()
        dll_handle.close()

    total_words = sum(int(row["referenceWordCount"]) for row in records)
    metrics = {
        "cases": len(records),
        "deterministicSemanticCorrect": sum(
            bool(row["deterministicSemanticCorrect"]) for row in records
        ),
        "parakeetWordErrorRate": sum(
            int(row["parakeetWordEdits"]) for row in records
        )
        / total_words,
        "fasterWhisperWordErrorRate": sum(
            int(row["fasterWhisperWordEdits"]) for row in records
        )
        / total_words,
        "allVadSegmented": all(bool(row["vadSegmented"]) for row in records),
        "audioSeconds": audio_seconds,
        "synthesisSeconds": synthesis_seconds,
        "decodeSeconds": decode_seconds,
        "audioRealtimeFactor": decode_seconds / audio_seconds,
    }
    report: dict[str, object] = {
        "schema": "baxy.r16-sapi-faster-whisper-failures-development.v2",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_parakeet_route_failures_faster_whisper_large_v3_rescore",
        "sources": {
            "sourceCorpusSha256": base.sha256(source_corpus_path),
            "transcriptCorpusSha256": base.sha256(transcript_corpus_path),
            "routeReportSha256": base.sha256(route_report_path),
            "modelTreeSha256": sha256_tree(model_path),
        },
        "inference": {
            "model": "faster-whisper-large-v3",
            "device": "cuda",
            "computeType": "float16",
            "beamSize": 5,
            "bestOf": 5,
            "language": "auto",
            "hotwords": hotwords,
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
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-corpus", type=Path, required=True)
    parser.add_argument("--transcript-corpus", type=Path, required=True)
    parser.add_argument("--route-report", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--runtime-dll-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--domain-hotwords", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        source_corpus_path=arguments.source_corpus,
        transcript_corpus_path=arguments.transcript_corpus,
        route_report_path=arguments.route_report,
        model_path=arguments.model,
        runtime_dll_directory=arguments.runtime_dll_directory,
        output_path=arguments.output,
        hotwords=DOMAIN_HOTWORDS if arguments.domain_hotwords else None,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
