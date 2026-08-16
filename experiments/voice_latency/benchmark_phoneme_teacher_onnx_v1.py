"""Verify fixed-turn ONNX equivalence and latency in BAXY's CPU runtime."""

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
sys.path.insert(0, str(HERE.parents[1] / "src"))
from baxy_mind.wake_verifier import (  # noqa: E402
    OnnxWakeVerifier,
    WakeVerifierConfig,
    compress_category_logits_numpy as product_compress_category_logits_numpy,
    decide_category_probabilities,
    normalize_audio,
    resolve_category_ids as product_resolve_category_ids,
    stage1_eligible,
)
from evaluate_phoneme_teacher_category_oracle_v2 import (  # noqa: E402
    compress_category_logits,
)
from evaluate_phoneme_teacher_stage2_windows_v1 import (  # noqa: E402
    stage1_proposal,
    summarize,
)
from extract_mdtc_ctc_fbank_features import read_wav  # noqa: E402
from train_mdtc_livekit_verifier_student import read_json, sha256  # noqa: E402


SAMPLE_RATE = 16_000


def compress_category_logits_numpy(
    logits: np.ndarray, category_ids: dict[str, tuple[int, ...]]
) -> np.ndarray:
    return product_compress_category_logits_numpy(logits, category_ids)


def latency_summary(milliseconds: list[float]) -> dict[str, float | int]:
    values = np.asarray(milliseconds, dtype=np.float64)
    if len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("phoneme_onnx_latency_invalid")
    return {
        "iterations": len(values),
        "median_milliseconds": float(np.median(values)),
        "p95_milliseconds": float(np.percentile(values, 95)),
        "p99_milliseconds": float(np.percentile(values, 99)),
        "maximum_milliseconds": float(values.max()),
        "mean_milliseconds": statistics.fmean(milliseconds),
    }


def decide(
    categories: dict[str, np.ndarray],
    records: list[dict[str, object]],
    source_records: dict[str, dict[str, object]],
) -> dict[str, object]:
    clips = []
    for record in records:
        relative_path = str(record["output_relative_path"])
        proposal, proposal_source = stage1_proposal(source_records[relative_path])
        confidence = float(proposal["score"]) if proposal is not None else 0.0
        transcript = str(source_records[relative_path].get("parakeet_transcript") or "")
        eligible = stage1_eligible(
            confidence,
            transcript,
            broad_threshold=0.02,
            strong_threshold=0.05,
        )
        decision = decide_category_probabilities(
            categories[relative_path],
            transcript,
            decision_margin=0.5,
            anchor_margin=0.5,
        )
        clips.append(
            {
                "relative_path": relative_path,
                "label": record["label"],
                "stage1_proposed": eligible,
                "proposal_source": proposal_source,
                "margin": decision.margin,
                "method": decision.method,
                "detected": eligible and decision.accepted,
            }
        )
    return summarize(clips)


def run(
    *,
    teacher_directory: Path,
    onnx_path: Path,
    corpus_manifest_path: Path,
    teacher_report_path: Path,
    output_path: Path,
    warmup: int,
    iterations: int,
) -> dict[str, object]:
    teacher_directory = teacher_directory.resolve(strict=True)
    onnx_path = onnx_path.resolve(strict=True)
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    teacher_report_path = teacher_report_path.resolve(strict=True)
    output_path = output_path.resolve()
    if output_path.exists() or min(warmup, iterations) <= 0:
        raise ValueError("phoneme_onnx_benchmark_schedule_invalid")
    corpus_manifest = read_json(corpus_manifest_path)
    teacher_report = read_json(teacher_report_path)
    if (
        corpus_manifest.get("blind_partition_was_not_scored") is not True
        or teacher_report.get("blind_human_partition_accessed") is not False
    ):
        raise ValueError("phoneme_onnx_benchmark_blind_boundary_invalid")
    records = [
        record
        for record in corpus_manifest.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    source_records = {
        str(record.get("output_relative_path")): record
        for record in teacher_report.get("records", [])
        if isinstance(record, dict)
    }
    if len(records) != 18:
        raise ValueError("phoneme_onnx_benchmark_records_invalid")

    import onnxruntime as ort
    import torch
    import transformers
    from transformers import Wav2Vec2ForCTC

    vocabulary = read_json(teacher_directory / "vocab.json")
    model_config = read_json(teacher_directory / "config.json")
    category_ids = product_resolve_category_ids(
        vocabulary, int(model_config["pad_token_id"])
    )
    corpus_directory = corpus_manifest_path.parent
    inputs = {}
    raw_audios = {}
    for record in records:
        relative_path = str(record["output_relative_path"])
        audio = read_wav(corpus_directory / relative_path)
        raw_audios[relative_path] = audio
        values = normalize_audio(audio)
        if values.shape != (1, 48_000):
            raise ValueError(f"phoneme_onnx_input_shape_invalid:{relative_path}:{values.shape}")
        inputs[relative_path] = values
    sample = inputs[str(records[0]["output_relative_path"])]

    torch_load_started = time.perf_counter()
    torch_model = Wav2Vec2ForCTC.from_pretrained(
        teacher_directory, local_files_only=True
    ).eval().cpu()
    torch_load_seconds = time.perf_counter() - torch_load_started
    torch_categories = {}
    with torch.inference_mode():
        for relative_path, values in inputs.items():
            logits = torch_model(input_values=torch.from_numpy(values)).logits
            torch_categories[relative_path] = (
                compress_category_logits(torch, logits, category_ids)[0].cpu().numpy()
            )
        for _ in range(warmup):
            torch_model(input_values=torch.from_numpy(sample)).logits
        torch_latency_values = []
        for _ in range(iterations):
            started = time.perf_counter()
            torch_model(input_values=torch.from_numpy(sample)).logits
            torch_latency_values.append((time.perf_counter() - started) * 1000.0)
    torch_decisions = decide(torch_categories, records, source_records)
    del torch_model
    gc.collect()

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    ort_load_started = time.perf_counter()
    session = ort.InferenceSession(
        str(onnx_path), sess_options=options, providers=["CPUExecutionProvider"]
    )
    ort_load_seconds = time.perf_counter() - ort_load_started
    ort_categories = {}
    for relative_path, values in inputs.items():
        logits = session.run(["logits"], {"input_values": values})[0]
        ort_categories[relative_path] = compress_category_logits_numpy(
            logits, category_ids
        )
    for _ in range(warmup):
        session.run(["logits"], {"input_values": sample})
    ort_latency_values = []
    for _ in range(iterations):
        started = time.perf_counter()
        session.run(["logits"], {"input_values": sample})
        ort_latency_values.append((time.perf_counter() - started) * 1000.0)
    ort_decisions = decide(ort_categories, records, source_records)

    data_path = onnx_path.with_name(onnx_path.name + ".data")
    runtime_verifier = OnnxWakeVerifier(
        WakeVerifierConfig(
            manifest_path=onnx_path.parent / "benchmark-only-manifest.json",
            graph_path=onnx_path,
            graph_data_path=data_path,
            vocabulary_path=teacher_directory / "vocab.json",
            graph_sha256=sha256(onnx_path),
            graph_data_sha256=sha256(data_path),
            vocabulary_sha256=sha256(teacher_directory / "vocab.json"),
            stage1_model_sha256="0" * 64,
            stage1_phrase="Baxy",
            stage1_hop_samples=2_560,
            stage1_debounce_seconds=2.0,
            stage1_pre_roll_seconds=5.0,
            minimum_samples=SAMPLE_RATE,
            maximum_samples=SAMPLE_RATE * 10,
            maximum_turn_samples=SAMPLE_RATE * 30,
            broad_threshold=0.02,
            strong_threshold=0.05,
            decision_margin=0.5,
            anchor_margin=0.5,
            calibration={},
        ),
        session=session,
    )
    runtime_clips = []
    for record in records:
        relative_path = str(record["output_relative_path"])
        proposal, proposal_source = stage1_proposal(source_records[relative_path])
        confidence = float(proposal["score"]) if proposal is not None else 0.0
        transcript = str(source_records[relative_path].get("parakeet_transcript") or "")
        decision = runtime_verifier.verify(
            raw_audios[relative_path], transcript, confidence
        )
        runtime_clips.append(
            {
                "relative_path": relative_path,
                "label": record["label"],
                "stage1_proposed": decision.stage1_eligible,
                "proposal_source": proposal_source,
                "margin": decision.margin,
                "method": decision.method,
                "detected": decision.accepted,
            }
        )
    runtime_decisions = summarize(runtime_clips)

    differences = []
    disagreements = 0
    frames = 0
    for relative_path, reference in torch_categories.items():
        candidate = ort_categories[relative_path]
        differences.append(float(np.max(np.abs(reference - candidate))))
        disagreements += int((reference.argmax(-1) != candidate.argmax(-1)).sum())
        frames += len(reference)
    decision_identity = [
        bool(left["detected"]) == bool(right["detected"])
        for left, right in zip(
            torch_decisions["clips"], ort_decisions["clips"], strict=True
        )
    ]
    report = {
        "schema": "baxy.phoneme-teacher-onnx-benchmark.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "teacher_directory": teacher_directory.as_posix(),
            "teacher_weights_sha256": sha256(teacher_directory / "pytorch_model.bin"),
            "onnx": onnx_path.as_posix(),
            "onnx_sha256": sha256(onnx_path),
            "onnx_data_sha256": sha256(data_path),
            "corpus_manifest": corpus_manifest_path.as_posix(),
            "corpus_manifest_sha256": sha256(corpus_manifest_path),
            "teacher_report": teacher_report_path.as_posix(),
            "teacher_report_sha256": sha256(teacher_report_path),
        },
        "contract": {
            "sample_rate": SAMPLE_RATE,
            "window_samples": 48_000,
            "locator": "product_ctc_exact_with_exact_lexical_anchor_fallback",
            "broad_threshold": 0.02,
            "strong_threshold": 0.05,
            "decision_margin_gte": 0.5,
        },
        "torch_fp32": {
            "model_load_seconds": torch_load_seconds,
            "development": torch_decisions,
            "latency": latency_summary(torch_latency_values),
        },
        "onnx_fp32": {
            "session_load_seconds": ort_load_seconds,
            "providers": session.get_providers(),
            "development": ort_decisions,
            "latency": latency_summary(ort_latency_values),
        },
        "onnx_product_runtime_class": {"development": runtime_decisions},
        "equivalence": {
            "maximum_category_probability_absolute_difference": max(differences),
            "greedy_frame_disagreements": disagreements,
            "frames": frames,
            "greedy_frame_disagreement_rate": disagreements / frames,
            "decisions_identical": decision_identity,
            "all_decisions_identical": all(decision_identity),
        },
        "runtime": {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "onnxruntime": ort.__version__,
            "torch_threads": torch.get_num_threads(),
        },
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
    parser.add_argument("--onnx", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--teacher-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = run(
        teacher_directory=arguments.teacher_dir,
        onnx_path=arguments.onnx,
        corpus_manifest_path=arguments.corpus_manifest,
        teacher_report_path=arguments.teacher_report,
        output_path=arguments.output,
        warmup=arguments.warmup,
        iterations=arguments.iterations,
    )
    print(
        json.dumps(
            {
                "torch_gate": report["torch_fp32"]["development"]["gate_passed"],
                "onnx_gate": report["onnx_fp32"]["development"]["gate_passed"],
                "runtime_class_gate": report["onnx_product_runtime_class"][
                    "development"
                ]["gate_passed"],
                "equivalent": report["equivalence"]["all_decisions_identical"],
                "torch_latency": report["torch_fp32"]["latency"],
                "onnx_latency": report["onnx_fp32"]["latency"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
