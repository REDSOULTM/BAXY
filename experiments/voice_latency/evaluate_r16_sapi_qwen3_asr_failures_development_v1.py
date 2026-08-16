"""Rescore opened R16 dual-ASR route failures with Qwen3-ASR 0.6B."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
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


EXPECTED_FAILURES = 60


def read_jsonl(path: Path) -> list[dict[str, object]]:
    values = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if any(not isinstance(value, dict) for value in values):
        raise ValueError("baxy_qwen3_asr_jsonl_invalid")
    return values


def select_failures(
    *,
    source_rows: list[dict[str, object]],
    transcript_rows: list[dict[str, object]],
    route_report: dict[str, object],
) -> list[tuple[int, dict[str, object], dict[str, object]]]:
    source_by_id = {str(row.get("case_id")): row for row in source_rows}
    route_rows = route_report.get("rows") if isinstance(route_report, dict) else None
    metrics = route_report.get("metrics", {}) if isinstance(route_report, dict) else {}
    if (
        len(source_by_id) != 700
        or len(transcript_rows) != 337
        or not isinstance(route_rows, list)
        or len(route_rows) != 337
        or route_report.get("schema")
        != "baxy.r16-sapi-dual-asr-product-route-development.v6"
        or metrics.get("contract_correct") != 277
        or metrics.get("unsafe_effects") != 5
        or route_report.get("effects_executed") != 0
    ):
        raise ValueError("baxy_qwen3_asr_population_invalid")
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
        raise ValueError("baxy_qwen3_asr_failure_count_invalid")
    return selected


def evaluate(
    *,
    source_corpus_path: Path,
    transcript_corpus_path: Path,
    route_report_path: Path,
    model_path: Path,
    output_path: Path,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("baxy_qwen3_asr_output_exists")
    source_corpus_path = source_corpus_path.resolve(strict=True)
    transcript_corpus_path = transcript_corpus_path.resolve(strict=True)
    route_report_path = route_report_path.resolve(strict=True)
    model_path = model_path.resolve(strict=True)
    output_path = output_path.resolve()
    source_rows = read_jsonl(source_corpus_path)
    transcript_rows = read_jsonl(transcript_corpus_path)
    route_report = json.loads(route_report_path.read_text(encoding="utf-8-sig"))
    selected = select_failures(
        source_rows=source_rows,
        transcript_rows=transcript_rows,
        route_report=route_report,
    )

    import torch
    from qwen_asr import Qwen3ASRModel
    from baxy_mind.effect_intent import resolve_explicit_effects
    from baxy_mind.voice import SileroVad

    available_operations = frozenset(
        operation
        for _, _, row in selected
        for accepted in base.accepted_effect_sets(row)
        for operation in accepted
    )
    started = time.perf_counter()
    torch.cuda.reset_peak_memory_stats()
    load_started = time.perf_counter()
    model = Qwen3ASRModel.from_pretrained(
        str(model_path),
        dtype=torch.bfloat16,
        device_map="cuda:0",
        max_inference_batch_size=1,
        max_new_tokens=256,
    )
    model_load_seconds = time.perf_counter() - load_started
    vad = SileroVad()
    synthesizer = base.SapiSynthesizer()
    records: list[dict[str, object]] = []
    synthesis_seconds = 0.0
    decode_seconds = 0.0
    audio_seconds = 0.0
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
            transcript = ""
            detected_language = None
            if segmented is not None:
                result = model.transcribe(
                    audio=(segmented, base.SAMPLE_RATE),
                    language=None,
                )[0]
                transcript = str(result.text).strip()
                detected_language = str(result.language)
            decode_seconds += time.perf_counter() - began
            audio_seconds += len(audio) / base.SAMPLE_RATE
            intent = (
                resolve_explicit_effects(transcript, available_operations)
                if transcript
                else None
            )
            actual = tuple(intent.operations) if intent is not None else ()
            reference_words = base.normalized_words(str(source["text"]))
            previous_words = base.normalized_words(str(transcript_row["text"]))
            candidate_words = base.normalized_words(transcript)
            records.append(
                {
                    "caseId": source["case_id"],
                    "language": language,
                    "rate": (-1, 0, 1)[original_index % 3],
                    "vadSegmented": segmented is not None,
                    "previousTranscript": transcript_row["text"],
                    "qwen3AsrTranscript": transcript,
                    "detectedLanguage": detected_language,
                    "referenceWordCount": len(reference_words),
                    "previousWordEdits": base.edit_distance(
                        reference_words, previous_words
                    ),
                    "qwen3AsrWordEdits": base.edit_distance(
                        reference_words, candidate_words
                    ),
                    "actualOperations": list(actual),
                    "deterministicSemanticCorrect": actual
                    in base.accepted_effect_sets(source),
                }
            )
            print(f"BAXY_R16_QWEN3_ASR|{position + 1}/{len(selected)}", flush=True)
    finally:
        synthesizer.close()

    total_words = sum(int(row["referenceWordCount"]) for row in records)
    metrics = {
        "cases": len(records),
        "deterministicSemanticCorrect": sum(
            bool(row["deterministicSemanticCorrect"]) for row in records
        ),
        "previousWordErrorRate": sum(
            int(row["previousWordEdits"]) for row in records
        )
        / total_words,
        "qwen3AsrWordErrorRate": sum(
            int(row["qwen3AsrWordEdits"]) for row in records
        )
        / total_words,
        "allVadSegmented": all(bool(row["vadSegmented"]) for row in records),
        "audioSeconds": audio_seconds,
        "synthesisSeconds": synthesis_seconds,
        "decodeSeconds": decode_seconds,
        "audioRealtimeFactor": decode_seconds / audio_seconds,
        "modelLoadSeconds": model_load_seconds,
        "cudaPeakAllocatedMiB": torch.cuda.max_memory_allocated() / (1024**2),
        "cudaPeakReservedMiB": torch.cuda.max_memory_reserved() / (1024**2),
    }
    report: dict[str, object] = {
        "schema": "baxy.r16-sapi-qwen3-asr-failures-development.v1",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_dual_asr_route_failures_qwen3_asr_0_6b_rescore",
        "sources": {
            "sourceCorpusSha256": base.sha256(source_corpus_path),
            "transcriptCorpusSha256": base.sha256(transcript_corpus_path),
            "routeReportSha256": base.sha256(route_report_path),
            "modelTreeSha256": sha256_tree(model_path),
        },
        "inference": {
            "model": "Qwen3-ASR-0.6B",
            "device": "cuda:0",
            "dtype": "bfloat16",
            "language": "auto",
            "maxInferenceBatchSize": 1,
            "maxNewTokens": 256,
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
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        source_corpus_path=arguments.source_corpus,
        transcript_corpus_path=arguments.transcript_corpus,
        route_report_path=arguments.route_report,
        model_path=arguments.model,
        output_path=arguments.output,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
