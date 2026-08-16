"""Stress the BAXY fusion on the previously opened 100-hour negative corpus.

This is explicitly a regression, not a fresh holdout or FAR certification.
Prior stage-one eligibility and transcripts are reused without inspecting
their content.  CUDA screens frozen CTC views, while every view within a
fixed 0.25 decision-score belt is rescored by the exact CPU ONNX graph.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from typing import Sequence

import numpy as np


SAMPLE_RATE = 16_000
CPU_RESCORING_BELT = 0.25
MINIMUM_PARITY_SAFETY_MULTIPLIER = 100.0


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_negative_regression_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PRODUCT = load_component(
    "audit_baxy_hyperspotter_fusion_product_candidate_v1.py",
    "_baxy_negative_regression_product_v1",
)
_CUDA = load_component(
    "audit_phoneme_teacher_cuda_product_parity_v1.py",
    "_baxy_negative_regression_cuda_v1",
)


def bytes_sha256(values: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(values, dtype="<f4").tobytes()
    ).hexdigest()


def decode_flac(ffmpeg_path: Path, audio_path: Path) -> np.ndarray:
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
        raise ValueError("baxy_negative_regression_audio_decode_invalid")
    return audio


def reconstruct_capture(
    audio: np.ndarray,
    record: dict[str, object],
    *,
    pre_roll_samples: int,
    trailing_silence_samples: int,
    maximum_turn_samples: int,
) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    hit_end = float(record["hit_window_end_seconds"])
    start = round(hit_end * SAMPLE_RATE) - pre_roll_samples
    leading = max(0, -start)
    source_start = max(0, start)
    capture = np.concatenate(
        (
            np.zeros(leading, np.float32),
            values[source_start:],
            np.zeros(trailing_silence_samples, np.float32),
        )
    )[:maximum_turn_samples]
    capture = np.ascontiguousarray(capture, dtype=np.float32)
    if (
        source_start != record.get("capture_source_start_sample")
        or len(capture) != record.get("capture_samples")
        or bytes_sha256(capture) != record.get("capture_sha256")
    ):
        raise ValueError("baxy_negative_regression_capture_mismatch")
    return capture


def screening_contract(parity_report: dict[str, object]) -> dict[str, float]:
    equivalence = parity_report.get("equivalence")
    contract = parity_report.get("contract")
    if (
        parity_report.get("schema")
        != "baxy.phoneme-teacher-cuda-product-parity.v1"
        or parity_report.get("parityPassed") is not True
        or parity_report.get("blindHumanAudioAccessed") is not False
        or not isinstance(equivalence, dict)
        or not isinstance(contract, dict)
        or contract.get("cudaPermittedForFreshProductGate") is not False
        or contract.get("cudaPermittedForPreviouslyOpenedRegressionScreen")
        is not True
    ):
        raise ValueError("baxy_negative_regression_parity_invalid")
    try:
        observed = float(equivalence["maximumNormalizedFusionScoreDrift"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("baxy_negative_regression_parity_invalid") from error
    multiplier = CPU_RESCORING_BELT / observed if observed > 0.0 else math.inf
    if (
        not math.isfinite(observed)
        or observed < 0.0
        or multiplier < MINIMUM_PARITY_SAFETY_MULTIPLIER
    ):
        raise ValueError("baxy_negative_regression_screening_belt_invalid")
    return {
        "observedMaximumNormalizedScoreDrift": observed,
        "cpuRescoringBelt": CPU_RESCORING_BELT,
        "empiricalSafetyMultiplier": multiplier,
    }


def verification_views(
    capture: np.ndarray, record: dict[str, object], config: object, wake: object
) -> list[tuple[int, np.ndarray]]:
    starts = wake.verification_view_starts(
        primary_start_sample=config.primary_view_start_samples,
        activity_start_sample=int(record["verification_start_sample"]),
        activity_lookback_samples=config.activity_lookback_samples,
    )
    result = []
    for start in starts:
        values = wake.verification_audio(
            capture,
            minimum_samples=config.minimum_samples,
            maximum_samples=config.maximum_samples,
            maximum_turn_samples=config.maximum_turn_samples,
            start_sample=start,
        )
        if values is None:
            continue
        if len(values) < config.maximum_samples:
            values = np.pad(
                values,
                (0, config.maximum_samples - len(values)),
                mode="constant",
            )
        result.append((start, np.ascontiguousarray(values, dtype=np.float32)))
    if not result:
        raise ValueError("baxy_negative_regression_views_missing")
    return result


def percentile_summary(values: Sequence[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or len(array) < 1 or not np.isfinite(array).all():
        raise ValueError("baxy_negative_regression_latency_invalid")
    return {
        "p50": float(np.percentile(array, 50)),
        "p95": float(np.percentile(array, 95)),
        "maximum": float(np.max(array)),
        "mean": float(np.mean(array)),
    }


def write_checkpoint(
    path: Path,
    *,
    identities: dict[str, str],
    completed_records: int,
    record_maximum_margins: list[float],
    near_views: list[dict[str, object]],
    view_count: int,
    elapsed_seconds: float,
    timings: dict[str, list[float]],
) -> None:
    value = {
        "schema": "baxy.hyperspotter-fusion-negative-regression-checkpoint.v1",
        "identities": identities,
        "completedRecords": completed_records,
        "recordMaximumMargins": record_maximum_margins,
        "nearViews": near_views,
        "viewCount": view_count,
        "elapsedSeconds": elapsed_seconds,
        "timings": timings,
    }
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_checkpoint(
    path: Path, identities: dict[str, str]
) -> tuple[int, list[float], list[dict[str, object]], int, float, dict[str, list[float]]]:
    empty_timings = {"decodeMs": [], "hyperMs": [], "cudaCtcMsPerView": []}
    if not path.exists():
        return 0, [], [], 0, 0.0, empty_timings
    value = _PRODUCT.read_object(path)
    timings = value.get("timings")
    if (
        value.get("schema")
        != "baxy.hyperspotter-fusion-negative-regression-checkpoint.v1"
        or value.get("identities") != identities
        or not isinstance(value.get("completedRecords"), int)
        or not isinstance(value.get("recordMaximumMargins"), list)
        or not isinstance(value.get("nearViews"), list)
        or not isinstance(value.get("viewCount"), int)
        or not isinstance(value.get("elapsedSeconds"), (int, float))
        or not isinstance(timings, dict)
        or any(not isinstance(timings.get(name), list) for name in empty_timings)
        or len(value["recordMaximumMargins"]) != value["completedRecords"]
    ):
        raise ValueError("baxy_negative_regression_checkpoint_invalid")
    return (
        int(value["completedRecords"]),
        [float(item) for item in value["recordMaximumMargins"]],
        list(value["nearViews"]),
        int(value["viewCount"]),
        float(value["elapsedSeconds"]),
        {name: [float(item) for item in timings[name]] for name in empty_timings},
    )


def evaluate(
    *,
    fusion_manifest_path: Path,
    ctc_manifest_path: Path,
    cuda_parity_report_path: Path,
    teacher_directory: Path,
    prior_holdout_report_path: Path,
    corpus_manifest_path: Path,
    preregistration_path: Path,
    ffmpeg_path: Path,
    output_path: Path,
    cuda_batch_size: int,
    record_batch_size: int,
) -> dict[str, object]:
    if (
        output_path.exists()
        or cuda_batch_size < 1
        or record_batch_size < 1
    ):
        raise ValueError("baxy_negative_regression_schedule_invalid")
    parity_path = cuda_parity_report_path.resolve(strict=True)
    teacher_directory = teacher_directory.resolve(strict=True)
    prior_path = prior_holdout_report_path.resolve(strict=True)
    corpus_path = corpus_manifest_path.resolve(strict=True)
    prereg_path = preregistration_path.resolve(strict=True)
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial.json")
    candidate = _PRODUCT.load_fusion_candidate(
        fusion_manifest_path, ctc_manifest_path
    )
    parity = _PRODUCT.read_object(parity_path)
    screening = screening_contract(parity)
    parity_sources = parity.get("sources")
    if (
        not isinstance(parity_sources, dict)
        or parity_sources.get("fusionManifestSha256")
        != _PRODUCT.sha256(candidate["manifest_path"])
        or parity_sources.get("ctcVerifierManifestSha256")
        != _PRODUCT.sha256(candidate["ctc_manifest_path"])
        or parity_sources.get("teacherWeightsSha256")
        != _PRODUCT.sha256(teacher_directory / "pytorch_model.bin")
    ):
        raise ValueError("baxy_negative_regression_parity_identity_invalid")
    prior = _PRODUCT.read_object(prior_path)
    corpus = _PRODUCT.read_object(corpus_path)
    preregistration = _PRODUCT.read_object(prereg_path)
    prior_metrics = prior.get("metrics")
    if (
        prior.get("schema") != "baxy.wake-verifier-negative-holdout-gate.v1"
        or prior.get("negative_gate_passed") is not True
        or prior.get("candidate_development_use") is not False
        or prior.get("blind_human_partition_accessed") is not False
        or prior.get("corpus_manifest_sha256") != _PRODUCT.sha256(corpus_path)
        or prior.get("preregistration_sha256") != _PRODUCT.sha256(prereg_path)
        or corpus.get("schema") != "baxy.openslr-librispeech-negative-holdout.v1"
        or corpus.get("blind_human_partition_accessed") is not False
        or preregistration.get("schema")
        != "baxy.wake-verifier-negative-holdout-preregistration.v1"
        or not isinstance(prior_metrics, dict)
        or prior_metrics.get("stage1_eligible") != 5854
        or prior_metrics.get("negative_false_activations") != 0
    ):
        raise ValueError("baxy_negative_regression_prior_evidence_invalid")
    records = prior.get("records")
    corpus_records = corpus.get("records")
    if not isinstance(records, list) or not isinstance(corpus_records, list):
        raise ValueError("baxy_negative_regression_records_invalid")
    eligible = [
        record
        for record in records
        if isinstance(record, dict) and record.get("stage1_eligible") is True
    ]
    if len(eligible) != 5854:
        raise ValueError("baxy_negative_regression_eligible_count_invalid")
    corpus_lookup = {
        str(record["utterance_id"]): record
        for record in corpus_records
        if isinstance(record, dict)
    }
    corpus_root = Path(str(corpus["corpus_root"])).resolve(strict=True)

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root / "src") not in sys.path:
        sys.path.insert(0, str(repo_root / "src"))
    from baxy_mind import wake_verifier as wake
    import onnxruntime as ort
    import torch
    from transformers import AutoModelForCTC

    if not torch.cuda.is_available():
        raise RuntimeError("baxy_negative_regression_cuda_unavailable")
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
    hyper_session = ort.InferenceSession(
        str(candidate["graph_path"]),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    teacher = AutoModelForCTC.from_pretrained(
        str(teacher_directory), local_files_only=True
    ).eval().cuda()
    policy = candidate["policy"]
    identities = {
        "fusionManifestSha256": _PRODUCT.sha256(candidate["manifest_path"]),
        "ctcVerifierManifestSha256": _PRODUCT.sha256(candidate["ctc_manifest_path"]),
        "cudaParityReportSha256": _PRODUCT.sha256(parity_path),
        "teacherWeightsSha256": _PRODUCT.sha256(teacher_directory / "pytorch_model.bin"),
        "priorHoldoutReportSha256": _PRODUCT.sha256(prior_path),
        "corpusManifestSha256": _PRODUCT.sha256(corpus_path),
        "preregistrationSha256": _PRODUCT.sha256(prereg_path),
        "actualFfmpegSha256": _PRODUCT.sha256(ffmpeg_path),
        "preregisteredFfmpegSha256": str(preregistration["ffmpeg_sha256"]),
    }
    (
        completed_records,
        record_maximum_margins,
        near_views,
        view_count,
        completed_seconds,
        timings,
    ) = load_checkpoint(checkpoint_path, identities)

    started_campaign = time.perf_counter()
    for record_start in range(completed_records, len(eligible), record_batch_size):
        batch_records = eligible[
            record_start : min(record_start + record_batch_size, len(eligible))
        ]
        view_audio = []
        view_locators = []
        record_decode_ms = []
        for offset, record in enumerate(batch_records):
            index = record_start + offset
            source = corpus_lookup.get(str(record.get("utterance_id")))
            if (
                source is None
                or source.get("relative_path") != record.get("relative_path")
                or source.get("sha256") != record.get("wav_sha256")
            ):
                raise ValueError("baxy_negative_regression_record_identity_invalid")
            path = (corpus_root / str(source["relative_path"])).resolve(strict=True)
            if _PRODUCT.sha256(path) != source.get("sha256"):
                raise ValueError("baxy_negative_regression_audio_hash_mismatch")
            decode_started = time.perf_counter()
            audio = decode_flac(ffmpeg_path, path)
            record_decode_ms.append((time.perf_counter() - decode_started) * 1000.0)
            capture = reconstruct_capture(
                audio,
                record,
                pre_roll_samples=int(preregistration["stage1_pre_roll_samples"]),
                trailing_silence_samples=int(preregistration["trailing_silence_samples"]),
                maximum_turn_samples=config.maximum_turn_samples,
            )
            for view_start, values in verification_views(capture, record, config, wake):
                view_audio.append(values)
                view_locators.append((index, view_start))
        chunk_margins = np.full(len(batch_records), -np.inf, dtype=np.float64)
        for view_start in range(0, len(view_audio), cuda_batch_size):
            values = view_audio[view_start : view_start + cuda_batch_size]
            normalized = np.concatenate([wake.normalize_audio(item) for item in values])
            tensor = torch.from_numpy(normalized).cuda()
            torch.cuda.synchronize()
            ctc_started = time.perf_counter()
            with torch.inference_mode():
                cuda_logits = teacher(tensor).logits.float().cpu().numpy()
            torch.cuda.synchronize()
            ctc_seconds = time.perf_counter() - ctc_started
            cuda_probabilities = _CUDA.compress_category_logits_batch(
                cuda_logits, category_ids, wake.CATEGORY_NAMES
            )
            ctc_margins = _CUDA.full_clip_ctc_margins(
                cuda_probabilities, wake
            )
            timings["cudaCtcMsPerView"].extend(
                [ctc_seconds * 1000.0 / len(values)] * len(values)
            )
            for local_index, (audio, ctc_margin) in enumerate(
                zip(values, ctc_margins, strict=True)
            ):
                hyper_started = time.perf_counter()
                logmel = _PRODUCT.numpy_log_mel_spectrogram(
                    audio, candidate["mel_filters"]
                )
                hyper_logits = hyper_session.run(
                    ["logits"], {"logmel": logmel[None, :, :]}
                )[0]
                timings["hyperMs"].append(
                    (time.perf_counter() - hyper_started) * 1000.0
                )
                hyper_score = float(np.max(hyper_logits))
                combined = hyper_score + float(policy["ctc_weight"]) * (
                    (float(ctc_margin) - float(policy["ctc_center"]))
                    / float(policy["ctc_scale"])
                )
                decision_margin = combined - float(policy["decision_threshold"])
                absolute_view_index = view_start + local_index
                record_index, start_sample = view_locators[absolute_view_index]
                chunk_index = record_index - record_start
                chunk_margins[chunk_index] = max(
                    chunk_margins[chunk_index], decision_margin
                )
                if decision_margin >= -CPU_RESCORING_BELT:
                    near_views.append(
                        {
                            "recordIndex": record_index,
                            "startSample": start_sample,
                            "cudaDecisionMargin": decision_margin,
                            "hyperScore": hyper_score,
                        }
                    )
        if not np.isfinite(chunk_margins).all():
            raise ValueError("baxy_negative_regression_record_score_missing")
        timings["decodeMs"].extend(record_decode_ms)
        record_maximum_margins.extend(chunk_margins.tolist())
        view_count += len(view_audio)
        completed_records = record_start + len(batch_records)
        elapsed = completed_seconds + time.perf_counter() - started_campaign
        write_checkpoint(
            checkpoint_path,
            identities=identities,
            completed_records=completed_records,
            record_maximum_margins=record_maximum_margins,
            near_views=near_views,
            view_count=view_count,
            elapsed_seconds=elapsed,
            timings=timings,
        )
        print(
            f"BAXY_NEGATIVE_REGRESSION|{completed_records}/{len(eligible)}|views={view_count}|near={len(near_views)}",
            flush=True,
        )

    screening_seconds = completed_seconds + time.perf_counter() - started_campaign
    del teacher
    torch.cuda.empty_cache()
    cpu_session = None
    cpu_rescore_margins = []
    cpu_rescore_ms = []
    false_record_indexes: set[int] = set()
    for rescore_index, locator in enumerate(near_views):
        if cpu_session is None:
            cpu_session = ort.InferenceSession(
                str(config.graph_path),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
        record_index = int(locator["recordIndex"])
        record = eligible[record_index]
        source = corpus_lookup[str(record["utterance_id"])]
        path = (corpus_root / str(source["relative_path"])).resolve(strict=True)
        audio = decode_flac(ffmpeg_path, path)
        capture = reconstruct_capture(
            audio,
            record,
            pre_roll_samples=int(preregistration["stage1_pre_roll_samples"]),
            trailing_silence_samples=int(preregistration["trailing_silence_samples"]),
            maximum_turn_samples=config.maximum_turn_samples,
        )
        values = dict(verification_views(capture, record, config, wake)).get(
            int(locator["startSample"])
        )
        if values is None:
            raise ValueError("baxy_negative_regression_rescore_view_missing")
        cpu_started = time.perf_counter()
        logits = cpu_session.run(
            ["logits"], {"input_values": wake.normalize_audio(values)}
        )[0]
        probabilities = _CUDA.compress_category_logits_batch(
            logits, category_ids, wake.CATEGORY_NAMES
        )
        ctc_margin = float(_CUDA.full_clip_ctc_margins(probabilities, wake)[0])
        cpu_rescore_ms.append((time.perf_counter() - cpu_started) * 1000.0)
        combined = float(locator["hyperScore"]) + float(policy["ctc_weight"]) * (
            (ctc_margin - float(policy["ctc_center"]))
            / float(policy["ctc_scale"])
        )
        margin = combined - float(policy["decision_threshold"])
        cpu_rescore_margins.append(margin)
        if margin >= 0.0:
            false_record_indexes.add(record_index)
        print(
            f"BAXY_NEGATIVE_CPU_RESCORE|{rescore_index + 1}/{len(near_views)}",
            flush=True,
        )

    exposure_hours = float(prior_metrics["exposure_hours"])
    false_activations = len(false_record_indexes)
    report: dict[str, object] = {
        "schema": "baxy.hyperspotter-fusion-negative-regression.v1",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "previously_opened_100h_negative_regression_cuda_screen_cpu_exact_belt",
        "sources": identities,
        "contract": {
            **screening,
            "stage1EligibilityReused": True,
            "priorTranscriptsReusedWithoutContentInspection": True,
            "decoderIdentityMatchesPreregistration": (
                identities["actualFfmpegSha256"]
                == identities["preregisteredFfmpegSha256"]
            ),
            "everyEligibleCaptureHashRevalidated": True,
            "allViewsWithinBeltRescoredByExactCpuOnnx": True,
            "freshHoldoutClaimSupported": False,
            "farCertificationSupported": False,
        },
        "metrics": {
            "descriptiveExposureHours": exposure_hours,
            "priorStage1Retained": len(records),
            "priorStage1Eligible": len(eligible),
            "verificationViews": view_count,
            "cpuRescoredViews": len(near_views),
            "negativeFalseActivations": false_activations,
            "descriptivePointFalseActivationsPerHour": (
                false_activations / exposure_hours
            ),
            "maximumCudaScreenDecisionMargin": float(
                np.max(record_maximum_margins)
            ),
            "maximumCpuRescoredDecisionMargin": (
                float(np.max(cpu_rescore_margins))
                if cpu_rescore_margins
                else None
            ),
            "minimumCpuRescoredDecisionMargin": (
                float(np.min(cpu_rescore_margins))
                if cpu_rescore_margins
                else None
            ),
        },
        "runtime": {
            "cudaDevice": torch.cuda.get_device_name(0),
            "torch": torch.__version__,
            "onnxruntime": ort.__version__,
            "cudaBatchSize": cuda_batch_size,
            "recordBatchSize": record_batch_size,
            "screeningSeconds": screening_seconds,
            "cpuRescoreSeconds": sum(cpu_rescore_ms) / 1000.0,
            "decodeMillisecondsPerEligibleRecord": percentile_summary(
                timings["decodeMs"]
            ),
            "hyperMillisecondsPerView": percentile_summary(timings["hyperMs"]),
            "cudaCtcMillisecondsPerView": percentile_summary(
                timings["cudaCtcMsPerView"]
            ),
            "cpuCtcMillisecondsPerRescoredView": (
                percentile_summary(cpu_rescore_ms) if cpu_rescore_ms else None
            ),
        },
        "regressionPassed": false_activations == 0,
        "candidateDevelopmentUse": True,
        "candidateFrozen": True,
        "productOperatingPoint": False,
        "negativeCorpusPreviouslyAccessed": True,
        "blindHumanAudioAccessed": False,
        "recordsOrFilenamesRetained": False,
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
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--cuda-parity-report", type=Path, required=True)
    parser.add_argument("--teacher-directory", type=Path, required=True)
    parser.add_argument("--prior-holdout-report", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cuda-batch-size", type=int, default=32)
    parser.add_argument("--record-batch-size", type=int, default=32)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        fusion_manifest_path=arguments.fusion_manifest,
        ctc_manifest_path=arguments.ctc_verifier_manifest,
        cuda_parity_report_path=arguments.cuda_parity_report,
        teacher_directory=arguments.teacher_directory,
        prior_holdout_report_path=arguments.prior_holdout_report,
        corpus_manifest_path=arguments.corpus_manifest,
        preregistration_path=arguments.preregistration,
        ffmpeg_path=arguments.ffmpeg,
        output_path=arguments.output,
        cuda_batch_size=arguments.cuda_batch_size,
        record_batch_size=arguments.record_batch_size,
    )
    print(
        json.dumps(
            {
                "passed": report["regressionPassed"],
                "metrics": report["metrics"],
                "runtime": report["runtime"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["regressionPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
