"""Benchmark the proven phoneme teacher as a warm stage-two verifier."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import json
from pathlib import Path
import statistics
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evaluate_phoneme_teacher_category_oracle_v2 import (  # noqa: E402
    compress_category_logits,
    score_category_probabilities,
)
from extract_mdtc_ctc_fbank_features import read_wav  # noqa: E402
from phoneme_student_vocabulary_v2 import (  # noqa: E402
    CATEGORY_NAMES,
    resolve_category_ids,
)
from train_mdtc_livekit_verifier_student import read_json, sha256  # noqa: E402


SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 32_000


def _pad_or_trim(audio: np.ndarray, samples: int) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if len(values) >= samples:
        return values[:samples]
    return np.pad(values, (0, samples - len(values)))


def _latency_summary(milliseconds: list[float]) -> dict[str, float]:
    values = np.asarray(milliseconds, dtype=np.float64)
    if len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("teacher_precision_latency_values_invalid")
    return {
        "iterations": len(values),
        "median_milliseconds": float(np.median(values)),
        "p95_milliseconds": float(np.percentile(values, 95)),
        "p99_milliseconds": float(np.percentile(values, 99)),
        "maximum_milliseconds": float(values.max()),
        "mean_milliseconds": statistics.fmean(milliseconds),
    }


def _external_spans(record: dict[str, object]) -> tuple[
    tuple[tuple[int, int, str], ...], tuple[tuple[int, int], ...]
]:
    locators = record.get("verifier_locators")
    if not isinstance(locators, list):
        return (), ()
    lexical = []
    veto = []
    for locator in locators:
        if not isinstance(locator, dict):
            continue
        start = int(locator["locator_start_frame"])
        end = int(locator["locator_end_frame"])
        if locator.get("source") == "parakeet_lexical_proposal":
            lexical.append((start, end, "parakeet_lexical_proposal"))
        if bool(locator.get("multiword_non_target_veto")):
            veto.append((start, end))
    return tuple(lexical), tuple(veto)


def compare_precision_outputs(
    reference_outputs: dict[str, np.ndarray],
    candidate_outputs: dict[str, np.ndarray],
    reference_metrics: dict[str, object],
    candidate_metrics: dict[str, object],
) -> dict[str, object]:
    differences = []
    greedy_disagreements = 0
    frames = 0
    for relative_path, reference in reference_outputs.items():
        candidate = candidate_outputs[relative_path]
        differences.append(float(np.max(np.abs(reference - candidate))))
        greedy_disagreements += int(
            (reference.argmax(-1) != candidate.argmax(-1)).sum()
        )
        frames += len(reference)
    reference_clips = reference_metrics["clips"]
    candidate_clips = candidate_metrics["clips"]
    if not isinstance(reference_clips, list) or not isinstance(candidate_clips, list):
        raise ValueError("teacher_precision_clips_invalid")
    decisions = [
        bool(left["detected"]) == bool(right["detected"])
        for left, right in zip(reference_clips, candidate_clips, strict=True)
    ]
    return {
        "maximum_category_probability_absolute_difference": max(differences),
        "greedy_frame_disagreements": greedy_disagreements,
        "frames": frames,
        "greedy_frame_disagreement_rate": greedy_disagreements / frames,
        "decisions_identical": decisions,
        "all_decisions_identical": all(decisions),
    }


def evaluate_precision(
    *,
    torch: object,
    model: object,
    processor: object,
    category_ids: dict[str, tuple[int, ...]],
    corpus_directory: Path,
    corpus_records: list[dict[str, object]],
    teacher_records: dict[str, dict[str, object]],
    dtype: object,
    device: str,
) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    clips = []
    category_outputs = {}
    for record in corpus_records:
        relative_path = str(record["output_relative_path"])
        teacher_record = teacher_records.get(relative_path)
        if not isinstance(teacher_record, dict):
            raise ValueError(f"teacher_precision_record_missing:{relative_path}")
        audio = read_wav(corpus_directory / relative_path)
        prepared = processor(
            audio,
            sampling_rate=SAMPLE_RATE,
            return_tensors="pt",
            padding=False,
        )
        with torch.inference_mode():
            logits = model(
                input_values=prepared.input_values.to(device=device, dtype=dtype)
            ).logits
            categories = compress_category_logits(
                torch, logits, category_ids
            )[0].cpu().numpy()
        lexical, veto = _external_spans(teacher_record)
        scored = score_category_probabilities(
            categories,
            lexical_locators=lexical,
            veto_spans=veto,
        )
        best = scored.get("best_verifier")
        margin = float(best["margin"]) if isinstance(best, dict) else None
        detected = bool(
            teacher_record.get("stage1_proposed")
            and margin is not None
            and margin >= 0.5
        )
        clips.append(
            {
                "relative_path": relative_path,
                "label": record["label"],
                "margin": margin,
                "detected": detected,
            }
        )
        category_outputs[relative_path] = categories
    positive = [clip for clip in clips if clip["label"] == "positive"]
    negative = [clip for clip in clips if clip["label"] == "hard_negative"]
    return {
        "positive_accepted": sum(bool(clip["detected"]) for clip in positive),
        "positive_total": len(positive),
        "hard_negative_false_accepts": sum(
            bool(clip["detected"]) for clip in negative
        ),
        "hard_negative_total": len(negative),
        "gate_passed": (
            all(bool(clip["detected"]) for clip in positive)
            and not any(bool(clip["detected"]) for clip in negative)
        ),
        "clips": clips,
    }, category_outputs


def benchmark_latency(
    *,
    torch: object,
    model: object,
    processor: object,
    audio: np.ndarray,
    dtype: object,
    device: str,
    warmup: int,
    iterations: int,
) -> dict[str, object]:
    prepared = processor(
        _pad_or_trim(audio, WINDOW_SAMPLES),
        sampling_rate=SAMPLE_RATE,
        return_tensors="pt",
        padding=False,
    )
    input_values = prepared.input_values.to(device=device, dtype=dtype)
    synchronize = torch.cuda.synchronize if device == "cuda" else lambda: None
    with torch.inference_mode():
        for _ in range(warmup):
            model(input_values=input_values).logits
        synchronize()
        values = []
        for _ in range(iterations):
            started = time.perf_counter()
            model(input_values=input_values).logits
            synchronize()
            values.append((time.perf_counter() - started) * 1000.0)
    report = {
        "audio_seconds": len(input_values[0]) / SAMPLE_RATE,
        **_latency_summary(values),
    }
    if device == "cuda":
        report.update(
            {
                "cuda_memory_allocated_bytes": int(torch.cuda.memory_allocated()),
                "cuda_memory_reserved_bytes": int(torch.cuda.memory_reserved()),
            }
        )
    return report


def run(
    *,
    teacher_directory: Path,
    corpus_manifest_path: Path,
    teacher_report_path: Path,
    output_path: Path,
    warmup: int,
    iterations: int,
    device: str,
    cpu_int8: bool = False,
) -> dict[str, object]:
    teacher_directory = teacher_directory.resolve(strict=True)
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    teacher_report_path = teacher_report_path.resolve(strict=True)
    output_path = output_path.resolve()
    if output_path.exists() or min(warmup, iterations) <= 0:
        raise ValueError("teacher_precision_output_or_schedule_invalid")
    corpus_manifest = read_json(corpus_manifest_path)
    teacher_report = read_json(teacher_report_path)
    if (
        corpus_manifest.get("blind_partition_was_not_scored") is not True
        or teacher_report.get("blind_human_partition_accessed") is not False
    ):
        raise ValueError("teacher_precision_blind_boundary_invalid")
    corpus_records = [
        record
        for record in corpus_manifest.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    if len(corpus_records) != 18:
        raise ValueError("teacher_precision_development_partition_invalid")
    teacher_records = {
        str(record.get("output_relative_path")): record
        for record in teacher_report.get("records", [])
        if isinstance(record, dict)
    }

    import torch
    import transformers
    from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForCTC

    if device not in {"cpu", "cuda"}:
        raise ValueError("teacher_precision_device_invalid")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("teacher_precision_cuda_required")
    load_started = time.perf_counter()
    processor = Wav2Vec2FeatureExtractor.from_pretrained(
        teacher_directory, local_files_only=True
    )
    model = Wav2Vec2ForCTC.from_pretrained(
        teacher_directory, local_files_only=True
    ).eval().to(device)
    load_seconds = time.perf_counter() - load_started
    vocabulary = read_json(teacher_directory / "vocab.json")
    model_config = read_json(teacher_directory / "config.json")
    category_ids = resolve_category_ids(vocabulary, int(model_config["pad_token_id"]))
    corpus_directory = corpus_manifest_path.parent
    sample_audio = read_wav(
        corpus_directory / str(corpus_records[0]["output_relative_path"])
    )
    fp32_metrics, fp32_outputs = evaluate_precision(
        torch=torch,
        model=model,
        processor=processor,
        category_ids=category_ids,
        corpus_directory=corpus_directory,
        corpus_records=corpus_records,
        teacher_records=teacher_records,
        dtype=torch.float32,
        device=device,
    )
    fp32_latency = benchmark_latency(
        torch=torch,
        model=model,
        processor=processor,
        audio=sample_audio,
        dtype=torch.float32,
        device=device,
        warmup=warmup,
        iterations=iterations,
    )

    fp16_report = None
    precision_comparison = None
    if device == "cuda":
        model.half()
        torch.cuda.empty_cache()
        fp16_metrics, fp16_outputs = evaluate_precision(
            torch=torch,
            model=model,
            processor=processor,
            category_ids=category_ids,
            corpus_directory=corpus_directory,
            corpus_records=corpus_records,
            teacher_records=teacher_records,
            dtype=torch.float16,
            device=device,
        )
        fp16_latency = benchmark_latency(
            torch=torch,
            model=model,
            processor=processor,
            audio=sample_audio,
            dtype=torch.float16,
            device=device,
            warmup=warmup,
            iterations=iterations,
        )
        fp16_report = {"development": fp16_metrics, "latency": fp16_latency}
        precision_comparison = compare_precision_outputs(
            fp32_outputs, fp16_outputs, fp32_metrics, fp16_metrics
        )

    int8_report = None
    int8_comparison = None
    int8_quantization_seconds = None
    if device == "cpu" and cpu_int8:
        quantization_started = time.perf_counter()
        int8_model = torch.ao.quantization.quantize_dynamic(
            model, {torch.nn.Linear}, dtype=torch.qint8
        ).eval()
        int8_quantization_seconds = time.perf_counter() - quantization_started
        del model
        gc.collect()
        int8_metrics, int8_outputs = evaluate_precision(
            torch=torch,
            model=int8_model,
            processor=processor,
            category_ids=category_ids,
            corpus_directory=corpus_directory,
            corpus_records=corpus_records,
            teacher_records=teacher_records,
            dtype=torch.float32,
            device=device,
        )
        int8_latency = benchmark_latency(
            torch=torch,
            model=int8_model,
            processor=processor,
            audio=sample_audio,
            dtype=torch.float32,
            device=device,
            warmup=warmup,
            iterations=iterations,
        )
        int8_report = {"development": int8_metrics, "latency": int8_latency}
        int8_comparison = compare_precision_outputs(
            fp32_outputs, int8_outputs, fp32_metrics, int8_metrics
        )
    report = {
        "schema": "baxy.phoneme-teacher-precision-benchmark.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "teacher_directory": teacher_directory.as_posix(),
            "teacher_model_sha256": sha256(teacher_directory / "pytorch_model.bin"),
            "corpus_manifest": corpus_manifest_path.as_posix(),
            "corpus_manifest_sha256": sha256(corpus_manifest_path),
            "teacher_report": teacher_report_path.as_posix(),
            "teacher_report_sha256": sha256(teacher_report_path),
        },
        "runtime": {
            "device": device,
            "model_load_seconds": load_seconds,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "text_phonemizer_required": False,
            "int8_dynamic_quantization_seconds": int8_quantization_seconds,
        },
        "fp32": {"development": fp32_metrics, "latency": fp32_latency},
        "fp16": fp16_report,
        "precision_comparison": precision_comparison,
        "int8_dynamic": int8_report,
        "int8_comparison": int8_comparison,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_partition_accessed": False,
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
    parser.add_argument("--teacher-dir", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--teacher-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--cpu-int8", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = run(
        teacher_directory=arguments.teacher_dir,
        corpus_manifest_path=arguments.corpus_manifest,
        teacher_report_path=arguments.teacher_report,
        output_path=arguments.output,
        warmup=arguments.warmup,
        iterations=arguments.iterations,
        device=arguments.device,
        cpu_int8=arguments.cpu_int8,
    )
    print(
        json.dumps(
            {
                "fp32_gate": report["fp32"]["development"]["gate_passed"],
                "fp16_gate": (
                    report["fp16"]["development"]["gate_passed"]
                    if isinstance(report["fp16"], dict)
                    else None
                ),
                "fp32_latency": report["fp32"]["latency"],
                "fp16_latency": (
                    report["fp16"]["latency"]
                    if isinstance(report["fp16"], dict)
                    else None
                ),
                "int8_gate": (
                    report["int8_dynamic"]["development"]["gate_passed"]
                    if isinstance(report["int8_dynamic"], dict)
                    else None
                ),
                "int8_latency": (
                    report["int8_dynamic"]["latency"]
                    if isinstance(report["int8_dynamic"], dict)
                    else None
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
