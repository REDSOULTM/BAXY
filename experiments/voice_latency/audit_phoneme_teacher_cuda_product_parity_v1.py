"""Bound CUDA teacher drift against the exact CPU ONNX product graph.

The resulting bound is used only to accelerate an already-open negative
regression corpus.  It cannot promote a candidate or replace the CPU product
runtime.  Human development is reported in aggregate and the blind human
partition is never accessed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from typing import Mapping

import numpy as np


MAXIMUM_NORMALIZED_SCORE_DRIFT = 0.02


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_cuda_parity_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PRODUCT = load_component(
    "audit_baxy_hyperspotter_fusion_product_candidate_v1.py",
    "_baxy_cuda_parity_product_v1",
)


def compress_category_logits_batch(
    logits: np.ndarray,
    category_ids: Mapping[str, tuple[int, ...]],
    category_names: tuple[str, ...],
) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float32)
    if values.ndim != 3 or values.shape[0] < 1:
        raise ValueError("baxy_cuda_parity_logits_invalid")
    reduced = np.stack(
        [
            values[:, :, list(category_ids[name])].max(axis=-1)
            for name in category_names
        ],
        axis=-1,
    )
    reduced -= reduced.max(axis=-1, keepdims=True)
    probabilities = np.exp(reduced)
    probabilities /= probabilities.sum(axis=-1, keepdims=True)
    if not np.isfinite(probabilities).all():
        raise ValueError("baxy_cuda_parity_probabilities_invalid")
    return probabilities


def full_clip_ctc_margins(
    probabilities: np.ndarray, wake: object
) -> np.ndarray:
    values = np.asarray(probabilities, dtype=np.float64)
    if values.ndim != 3 or values.shape[2] != len(wake.CATEGORY_NAMES):
        raise ValueError("baxy_cuda_parity_probabilities_invalid")
    log_probabilities = np.log(np.maximum(values, 1e-12))
    target = np.max(
        np.stack(
            [
                _PRODUCT.ctc_log_probability_batch(
                    log_probabilities, sequence, blank_id=wake.BLANK_ID
                )
                for sequence in wake.TARGET_IDS
            ]
        ),
        axis=0,
    )
    confusable = np.max(
        np.stack(
            [
                _PRODUCT.ctc_log_probability_batch(
                    log_probabilities, sequence, blank_id=wake.BLANK_ID
                )
                for sequence in wake.CONFUSABLE_IDS
            ]
        ),
        axis=0,
    )
    result = target - confusable
    if not np.isfinite(result).all():
        raise ValueError("baxy_cuda_parity_margin_invalid")
    return result


def audit(
    *,
    teacher_directory: Path,
    onnx_benchmark_report_path: Path,
    fusion_manifest_path: Path,
    ctc_manifest_path: Path,
    human_source_manifest_path: Path,
    legacy_root: Path,
    expanded_root: Path,
    output_path: Path,
    batch_size: int,
) -> dict[str, object]:
    if output_path.exists() or batch_size < 1:
        raise ValueError("baxy_cuda_parity_schedule_invalid")
    teacher_directory = teacher_directory.resolve(strict=True)
    benchmark_path = onnx_benchmark_report_path.resolve(strict=True)
    source_path = human_source_manifest_path.resolve(strict=True)
    benchmark = _PRODUCT.read_object(benchmark_path)
    benchmark_sources = benchmark.get("sources")
    if (
        benchmark.get("schema") != "baxy.phoneme-teacher-onnx-benchmark.v1"
        or benchmark.get("blind_human_partition_accessed") is not False
        or not isinstance(benchmark_sources, dict)
        or _PRODUCT.sha256(teacher_directory / "pytorch_model.bin")
        != benchmark_sources.get("teacher_weights_sha256")
    ):
        raise ValueError("baxy_cuda_parity_teacher_evidence_invalid")
    candidate = _PRODUCT.load_fusion_candidate(
        fusion_manifest_path, ctc_manifest_path
    )
    ctc_manifest = _PRODUCT.read_object(candidate["ctc_manifest_path"])
    if (
        ctc_manifest.get("graphDataSha256")
        != benchmark_sources.get("onnx_data_sha256")
    ):
        raise ValueError("baxy_cuda_parity_onnx_identity_invalid")
    source = _PRODUCT.read_object(source_path)
    records = _PRODUCT.human_records(source)
    roots = {
        "human_legacy": legacy_root.resolve(strict=True),
        "human_expanded": expanded_root.resolve(strict=True),
    }

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root / "src") not in sys.path:
        sys.path.insert(0, str(repo_root / "src"))
    from baxy_mind import wake_verifier as wake
    import onnxruntime as ort
    import soundfile as sf
    import torch
    from transformers import AutoModelForCTC

    if not torch.cuda.is_available():
        raise RuntimeError("baxy_cuda_parity_cuda_unavailable")
    config = wake.load_wake_verifier_candidate_config(
        candidate["ctc_manifest_path"]
    )
    category_ids = wake.resolve_category_ids(
        _PRODUCT.read_object(config.vocabulary_path), wake.BLANK_ID
    )
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    onnx_started = time.perf_counter()
    session = ort.InferenceSession(
        str(config.graph_path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    onnx_load_seconds = time.perf_counter() - onnx_started
    cuda_started = time.perf_counter()
    model = AutoModelForCTC.from_pretrained(
        str(teacher_directory), local_files_only=True
    ).eval().cuda()
    cuda_load_seconds = time.perf_counter() - cuda_started

    normalized_audio = []
    corpora = []
    for record in records:
        path = (
            roots[str(record["corpus"])] / str(record["relative_path"])
        ).resolve(strict=True)
        if _PRODUCT.sha256(path) != str(record["audio_sha256"]).lower():
            raise ValueError("baxy_cuda_parity_audio_hash_mismatch")
        waveform, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
        audio = waveform.mean(axis=1, dtype=np.float32)
        if sample_rate != _PRODUCT.SAMPLE_RATE or audio.shape != (_PRODUCT.AUDIO_SAMPLES,):
            raise ValueError("baxy_cuda_parity_audio_contract_invalid")
        normalized_audio.append(wake.normalize_audio(audio)[0])
        corpora.append(str(record["corpus"]))

    maximum_logit_difference = 0.0
    maximum_probability_difference = 0.0
    frame_disagreements = 0
    frames = 0
    onnx_margins = []
    cuda_margins = []
    onnx_seconds = 0.0
    cuda_seconds = 0.0
    for start in range(0, len(normalized_audio), batch_size):
        values = np.stack(normalized_audio[start : start + batch_size]).astype(
            np.float32
        )
        started = time.perf_counter()
        onnx_logits = session.run(["logits"], {"input_values": values})[0]
        onnx_seconds += time.perf_counter() - started
        tensor = torch.from_numpy(values).cuda()
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            cuda_logits = model(tensor).logits.float().cpu().numpy()
        torch.cuda.synchronize()
        cuda_seconds += time.perf_counter() - started
        if onnx_logits.shape != cuda_logits.shape:
            raise ValueError("baxy_cuda_parity_output_shape_invalid")
        maximum_logit_difference = max(
            maximum_logit_difference,
            float(np.max(np.abs(onnx_logits - cuda_logits))),
        )
        onnx_probabilities = compress_category_logits_batch(
            onnx_logits, category_ids, wake.CATEGORY_NAMES
        )
        cuda_probabilities = compress_category_logits_batch(
            cuda_logits, category_ids, wake.CATEGORY_NAMES
        )
        maximum_probability_difference = max(
            maximum_probability_difference,
            float(np.max(np.abs(onnx_probabilities - cuda_probabilities))),
        )
        onnx_paths = np.argmax(onnx_probabilities, axis=2)
        cuda_paths = np.argmax(cuda_probabilities, axis=2)
        frame_disagreements += int(np.count_nonzero(onnx_paths != cuda_paths))
        frames += int(onnx_paths.size)
        onnx_margins.extend(full_clip_ctc_margins(onnx_probabilities, wake).tolist())
        cuda_margins.extend(full_clip_ctc_margins(cuda_probabilities, wake).tolist())
        print(
            f"BAXY_CUDA_PARITY|{min(start + batch_size, len(records))}/{len(records)}",
            flush=True,
        )
    margin_differences = np.abs(
        np.asarray(onnx_margins) - np.asarray(cuda_margins)
    )
    score_scale = float(candidate["policy"]["ctc_scale"])
    maximum_normalized_drift = float(np.max(margin_differences) / score_scale)
    passed = (
        maximum_normalized_drift <= MAXIMUM_NORMALIZED_SCORE_DRIFT
        and frame_disagreements == 0
    )
    corpus_array = np.asarray(corpora)

    def partition(mask: np.ndarray) -> dict[str, object]:
        differences = margin_differences[mask]
        return {
            "clips": int(np.count_nonzero(mask)),
            "maximumCtcMarginAbsoluteDifference": float(np.max(differences)),
            "meanCtcMarginAbsoluteDifference": float(np.mean(differences)),
            "maximumNormalizedFusionScoreDrift": float(
                np.max(differences) / score_scale
            ),
        }

    report: dict[str, object] = {
        "schema": "baxy.phoneme-teacher-cuda-product-parity.v1",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "human_development_cuda_acceleration_bound_against_cpu_product_onnx",
        "sources": {
            "teacherWeightsSha256": _PRODUCT.sha256(
                teacher_directory / "pytorch_model.bin"
            ),
            "onnxBenchmarkReportSha256": _PRODUCT.sha256(benchmark_path),
            "fusionManifestSha256": _PRODUCT.sha256(candidate["manifest_path"]),
            "ctcVerifierManifestSha256": _PRODUCT.sha256(
                candidate["ctc_manifest_path"]
            ),
            "humanSourceManifestSha256": _PRODUCT.sha256(source_path),
        },
        "contract": {
            "maximumNormalizedFusionScoreDriftLte": MAXIMUM_NORMALIZED_SCORE_DRIFT,
            "categoryGreedyFrameDisagreementsEq": 0,
            "cudaPermittedForFreshProductGate": False,
            "cudaPermittedForPreviouslyOpenedRegressionScreen": True,
        },
        "equivalence": {
            "maximumRawLogitAbsoluteDifference": maximum_logit_difference,
            "maximumCategoryProbabilityAbsoluteDifference": maximum_probability_difference,
            "categoryGreedyFrameDisagreements": frame_disagreements,
            "categoryFrames": frames,
            "maximumCtcMarginAbsoluteDifference": float(np.max(margin_differences)),
            "maximumNormalizedFusionScoreDrift": maximum_normalized_drift,
        },
        "legacyDevelopment": partition(corpus_array == "human_legacy"),
        "expandedIndependentDevelopment": partition(
            corpus_array == "human_expanded"
        ),
        "runtime": {
            "cudaDevice": torch.cuda.get_device_name(0),
            "torch": torch.__version__,
            "onnxruntime": ort.__version__,
            "batchSize": batch_size,
            "onnxSessionLoadSeconds": onnx_load_seconds,
            "cudaModelLoadSeconds": cuda_load_seconds,
            "onnxInferenceSeconds": onnx_seconds,
            "cudaInferenceSeconds": cuda_seconds,
            "cudaPeakAllocatedBytes": int(torch.cuda.max_memory_allocated()),
        },
        "parityPassed": passed,
        "candidateDevelopmentUse": True,
        "candidateFrozen": True,
        "productOperatingPoint": False,
        "humanDevelopmentAudioAccessed": True,
        "blindHumanAudioAccessed": False,
        "audioOrFilenamesRetained": False,
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
    parser.add_argument("--teacher-directory", type=Path, required=True)
    parser.add_argument("--onnx-benchmark-report", type=Path, required=True)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--human-source-manifest", type=Path, required=True)
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--expanded-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = audit(
        teacher_directory=arguments.teacher_directory,
        onnx_benchmark_report_path=arguments.onnx_benchmark_report,
        fusion_manifest_path=arguments.fusion_manifest,
        ctc_manifest_path=arguments.ctc_verifier_manifest,
        human_source_manifest_path=arguments.human_source_manifest,
        legacy_root=arguments.legacy_root,
        expanded_root=arguments.expanded_root,
        output_path=arguments.output,
        batch_size=arguments.batch_size,
    )
    print(
        json.dumps(
            {
                "passed": report["parityPassed"],
                "equivalence": report["equivalence"],
                "runtime": report["runtime"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["parityPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
