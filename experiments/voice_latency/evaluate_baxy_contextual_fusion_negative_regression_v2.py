"""Stress the contextual fixed-view fusion on the opened 100-hour corpus.

This is a development regression only.  It re-scans the already-open
LibriSpeech audio at the new 0.01 sentinel threshold, uses CUDA only as a
wide-belt screen backed by exact CPU ONNX rescoring, and runs wake-only
contextual Parakeet solely for exact acoustic false candidates.  The output
retains aggregate metrics, never record identities, filenames, or text.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from typing import Callable

import numpy as np


STAGE1_EXACT_BOUNDARY_GUARD = 0.0001
CONTEXTUAL_VIEW_POLICIES = ("full_capture", "same_exact_fusion_view")


def prior_negative_evidence_authority(prior: dict[str, object]) -> str | None:
    """Return the bounded authority carried by the prior CTC regression."""

    if (
        prior.get("schema") == "baxy.wake-verifier-negative-holdout-gate.v1"
        and prior.get("negative_gate_passed") is True
    ):
        return "product_holdout_gate"
    if (
        prior.get("schema")
        == "baxy.wake-verifier-negative-opened-regression.v1"
        and prior.get("development_gate_passed") is True
        and prior.get("negative_corpus_previously_accessed") is True
        and prior.get("fresh_holdout_claim_supported") is False
        and prior.get("far_certification_supported") is False
        and prior.get("product_operating_point") is False
    ):
        return "opened_development_regression"
    return None


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_contextual_negative_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V1 = load_component(
    "evaluate_baxy_hyperspotter_fusion_negative_regression_v1.py",
    "_baxy_contextual_negative_v1",
)
_V4 = load_component(
    "evaluate_baxy_contextual_fusion_development_v4.py",
    "_baxy_contextual_negative_v4",
)
_PRODUCT = _V1._PRODUCT
_CUDA = _V1._CUDA
_SCAN = _V4._SCAN
_HOLDOUT = _V4._HOLDOUT


def select_sentinel_records(
    scan_records: object, *, threshold: float = _V4.SENTINEL_STAGE1_THRESHOLD
) -> list[dict[str, object]]:
    if not isinstance(scan_records, list):
        raise ValueError("baxy_contextual_negative_scan_records_invalid")
    selected = [
        record
        for record in scan_records
        if isinstance(record, dict) and float(record.get("max_score", -math.inf)) >= threshold
    ]
    if not selected:
        raise ValueError("baxy_contextual_negative_sentinel_empty")
    return selected


def validated_sentinel_records(
    scan_records: object,
    corpus_records: object,
    *,
    expected_utterances: int,
    expected_sentinel_candidates: int | None,
) -> list[dict[str, object]]:
    if (
        not isinstance(scan_records, list)
        or not isinstance(corpus_records, list)
        or expected_utterances < 1
        or len(scan_records) != expected_utterances
        or len(corpus_records) != expected_utterances
    ):
        raise ValueError("baxy_contextual_negative_sentinel_population_invalid")
    selected = select_sentinel_records(scan_records)
    if (
        expected_sentinel_candidates is not None
        and len(selected) != expected_sentinel_candidates
    ):
        raise ValueError("baxy_contextual_negative_sentinel_count_invalid")
    return selected


_SCREENING_IDENTITY_KEYS = (
    "fusionManifestSha256",
    "ctcVerifierManifestSha256",
    "cudaParityReportSha256",
    "teacherWeightsSha256",
    "priorHoldoutReportSha256",
    "priorStage1ScanSha256",
    "corpusManifestSha256",
    "stage1ModelSha256",
    "actualFfmpegSha256",
    "sentinelThreshold",
    "fixedViewStarts",
    "stage1ExactBoundaryGuard",
    "expectedSentinelCandidates",
)


def screening_checkpoint_identities(
    identities: dict[str, str],
) -> dict[str, str]:
    if any(name not in identities for name in _SCREENING_IDENTITY_KEYS):
        raise ValueError("baxy_contextual_negative_screening_identity_invalid")
    return {name: identities[name] for name in _SCREENING_IDENTITY_KEYS}


def fixed_views(
    capture: np.ndarray, config: object, wake: object
) -> list[tuple[int, np.ndarray]]:
    result = []
    for start in _V4.FUSION_VIEW_START_SAMPLES:
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
        raise ValueError("baxy_contextual_negative_views_missing")
    return result


def contextual_decode_proposals(
    record_indexes: set[int],
    captures: dict[int, np.ndarray],
    eligible_view_starts: dict[int, set[int]],
    *,
    policy: str,
    config: object,
    wake: object,
) -> list[dict[str, object]]:
    """Build only the captures authorized by the selected contextual policy."""

    if policy not in CONTEXTUAL_VIEW_POLICIES:
        raise ValueError("baxy_contextual_negative_view_policy_invalid")
    proposals: list[dict[str, object]] = []
    for record_index in sorted(record_indexes):
        capture = captures.get(record_index)
        if capture is None:
            raise ValueError("baxy_contextual_negative_capture_missing")
        if policy == "full_capture":
            proposals.append(
                {
                    "capture": capture,
                    "recordIndex": record_index,
                    "startSample": None,
                }
            )
            continue
        views = dict(fixed_views(capture, config, wake))
        starts = eligible_view_starts.get(record_index, set())
        if not starts:
            raise ValueError("baxy_contextual_negative_eligible_view_missing")
        for start_sample in sorted(starts):
            view = views.get(start_sample)
            if view is None:
                raise ValueError("baxy_contextual_negative_rescore_view_missing")
            proposals.append(
                {
                    "capture": view,
                    "recordIndex": record_index,
                    "startSample": start_sample,
                }
            )
    return proposals


def sentinel_streaming_scores(
    model: object,
    audio: np.ndarray,
    *,
    threshold: float = _V4.SENTINEL_STAGE1_THRESHOLD,
    exact_boundary_guard: float = STAGE1_EXACT_BOUNDARY_GUARD,
    hop_samples: int = 2560,
    frame_samples: int = 512,
) -> dict[str, object]:
    """Screen overlap scores and exactly rescore only the decision boundary."""

    if (
        not 0.0 < exact_boundary_guard < threshold < 1.0
        or hop_samples <= 0
        or frame_samples <= 0
        or not hasattr(model, "predict_overlapping_windows")
        or not hasattr(model, "rescore_windows_exact")
    ):
        raise ValueError("baxy_contextual_negative_stage1_screen_invalid")
    window_samples = round(_SCAN.WINDOW_SECONDS * _SCAN.SAMPLE_RATE)
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    padded = np.concatenate(
        [
            np.zeros(window_samples, np.float32),
            values,
            np.zeros(window_samples, np.float32),
        ]
    )
    padded = np.pad(padded, (0, (-len(padded)) % frame_samples))
    ends = []
    buffered = 0
    since_score = 0
    for end in range(frame_samples, len(padded) + 1, frame_samples):
        buffered = min(window_samples, buffered + frame_samples)
        since_score += frame_samples
        if buffered >= window_samples and since_score >= hop_samples:
            ends.append(end)
            since_score %= hop_samples
    scores = np.asarray(
        model.predict_overlapping_windows(padded, ends, window_samples),
        dtype=np.float64,
    ).reshape(-1)
    if len(scores) != len(ends) or not np.isfinite(scores).all():
        raise ValueError("baxy_contextual_negative_stage1_scores_invalid")
    boundary = np.flatnonzero(np.abs(scores - threshold) <= exact_boundary_guard)
    if len(boundary):
        exact = np.asarray(
            model.rescore_windows_exact(
                padded, ends, boundary.tolist(), window_samples
            ),
            dtype=np.float64,
        ).reshape(-1)
        if len(exact) != len(boundary):
            raise ValueError("baxy_contextual_negative_stage1_rescore_invalid")
        scores[boundary] = exact
    retained = [
        {
            "window_end_seconds": round((end - window_samples) / _SCAN.SAMPLE_RATE, 6),
            "score": float(score),
        }
        for end, score in zip(ends, scores, strict=True)
        if score >= threshold
    ]
    maximum_index = int(np.argmax(scores))
    return {
        "max_score": float(scores[maximum_index]),
        "max_window_end_seconds": (
            ends[maximum_index] - window_samples
        )
        / _SCAN.SAMPLE_RATE,
        "windows_scored": len(scores),
        "boundary_rescored_windows": len(boundary),
        "retained_windows": retained,
    }


def rescan_capture(
    *,
    record: dict[str, object],
    source: dict[str, object],
    corpus_root: Path,
    ffmpeg_path: Path,
    stage1: object,
    config: object,
) -> tuple[np.ndarray, float, float]:
    path = (corpus_root / str(source["relative_path"])).resolve(strict=True)
    if _PRODUCT.sha256(path) != source.get("sha256"):
        raise ValueError("baxy_contextual_negative_audio_hash_mismatch")
    decode_started = time.perf_counter()
    audio = _V1.decode_flac(ffmpeg_path, path)
    decode_ms = (time.perf_counter() - decode_started) * 1000.0
    scan_started = time.perf_counter()
    result = sentinel_streaming_scores(
        stage1,
        audio,
        threshold=_V4.SENTINEL_STAGE1_THRESHOLD,
        hop_samples=config.stage1_hop_samples,
        frame_samples=512,
    )
    scan_ms = (time.perf_counter() - scan_started) * 1000.0
    if not math.isclose(
        float(result["max_score"]),
        float(record["max_score"]),
        rel_tol=0.0,
        abs_tol=STAGE1_EXACT_BOUNDARY_GUARD,
    ):
        raise ValueError("baxy_contextual_negative_stage1_parity_mismatch")
    retained = result["retained_windows"]
    if not retained:
        raise ValueError("baxy_contextual_negative_stage1_hit_missing")
    capture, _ = _HOLDOUT.capture_audio(
        audio,
        hit_end_seconds=float(retained[0]["window_end_seconds"]),
        pre_roll_seconds=config.stage1_pre_roll_seconds,
        maximum_turn_samples=config.maximum_turn_samples,
    )
    return capture, decode_ms, scan_ms


def evaluate(
    *,
    fusion_manifest_path: Path,
    ctc_manifest_path: Path,
    cuda_parity_report_path: Path,
    teacher_directory: Path,
    prior_holdout_report_path: Path,
    prior_stage1_scan_path: Path,
    corpus_manifest_path: Path,
    stage1_model_path: Path,
    ffmpeg_path: Path,
    stt_directory: Path,
    sherpa_site_packages_path: Path | None,
    output_path: Path,
    cuda_batch_size: int,
    record_batch_size: int,
    stt_batch_size: int,
    stage1_workers: int,
    secondary_view_guard: Callable[[np.ndarray, object], bool] | None = None,
    secondary_audio_guard: Callable[
        [np.ndarray, np.ndarray, object, int, int], bool
    ]
    | None = None,
    secondary_guard_contract: dict[str, object] | None = None,
    contextual_result_observer: Callable[[dict[str, object], str, bool], None]
    | None = None,
    contextual_hotword_score: float = _V4.CONTEXTUAL_HOTWORD_SCORE,
    contextual_view_policy: str = "full_capture",
    additional_checkpoint_identities: dict[str, str] | None = None,
    expected_sentinel_candidates: int | None = None,
    screening_cache_path: Path | None = None,
) -> dict[str, object]:
    if (
        output_path.exists()
        or cuda_batch_size < 1
        or record_batch_size < 1
        or stt_batch_size < 1
        or stage1_workers < 1
        or stage1_workers > record_batch_size
        or not math.isfinite(float(contextual_hotword_score))
        or contextual_view_policy not in CONTEXTUAL_VIEW_POLICIES
        or (secondary_view_guard is not None and secondary_audio_guard is not None)
        or (
            (secondary_view_guard is None and secondary_audio_guard is None)
            != (secondary_guard_contract is None)
        )
        or (
            expected_sentinel_candidates is not None
            and expected_sentinel_candidates < 1
        )
    ):
        raise ValueError("baxy_contextual_negative_schedule_invalid")
    parity_path = cuda_parity_report_path.resolve(strict=True)
    teacher_directory = teacher_directory.resolve(strict=True)
    prior_path = prior_holdout_report_path.resolve(strict=True)
    prior_scan_path = prior_stage1_scan_path.resolve(strict=True)
    corpus_path = corpus_manifest_path.resolve(strict=True)
    stage1_model_path = stage1_model_path.resolve(strict=True)
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    stt_directory = stt_directory.resolve(strict=True)
    if sherpa_site_packages_path is not None:
        sherpa_site_packages_path = sherpa_site_packages_path.resolve(strict=True)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if screening_cache_path is None:
        checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial.json")
    else:
        checkpoint_path = screening_cache_path.resolve()
        if checkpoint_path == output_path:
            raise ValueError("baxy_contextual_negative_screening_cache_invalid")
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    print("BAXY_CONTEXTUAL_INIT|paths_resolved", flush=True)

    candidate = _PRODUCT.load_fusion_candidate(
        fusion_manifest_path, ctc_manifest_path
    )
    print("BAXY_CONTEXTUAL_INIT|candidate_verified", flush=True)
    parity = _PRODUCT.read_object(parity_path)
    screening = _V1.screening_contract(parity)
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
        raise ValueError("baxy_contextual_negative_parity_identity_invalid")

    prior = _PRODUCT.read_object(prior_path)
    prior_scan = _PRODUCT.read_object(prior_scan_path)
    corpus = _PRODUCT.read_object(corpus_path)
    print("BAXY_CONTEXTUAL_INIT|evidence_loaded", flush=True)
    prior_metrics = prior.get("metrics")
    scan_metrics = prior_scan.get("metrics")
    scan_runtime = prior_scan.get("runtime")
    prior_authority = prior_negative_evidence_authority(prior)
    prior_is_opened_regression = prior_authority == "opened_development_regression"
    if (
        prior_authority is None
        or not isinstance(prior_metrics, dict)
        or prior_metrics.get("negative_false_activations") != 0
        or prior.get("corpus_manifest_sha256") != _PRODUCT.sha256(corpus_path)
        or prior.get("stage1_scan_sha256") != _PRODUCT.sha256(prior_scan_path)
        or prior_scan.get("schema")
        != "baxy.openslr-librispeech-livekit-holdout-scan.v1"
        or prior_scan.get("corpus_manifest_sha256") != _PRODUCT.sha256(corpus_path)
        or prior_scan.get("model_sha256") != _PRODUCT.sha256(stage1_model_path)
        or not isinstance(scan_metrics, dict)
        or scan_metrics.get("utterances") != 28539
        or not isinstance(scan_runtime, dict)
        or corpus.get("schema") != "baxy.openslr-librispeech-negative-holdout.v1"
    ):
        raise ValueError("baxy_contextual_negative_prior_evidence_invalid")
    scan_records = prior_scan.get("records")
    corpus_records = corpus.get("records")
    selected = validated_sentinel_records(
        scan_records,
        corpus_records,
        expected_utterances=int(scan_metrics["utterances"]),
        expected_sentinel_candidates=expected_sentinel_candidates,
    )
    corpus_lookup = {
        str(record["utterance_id"]): record
        for record in corpus_records
        if isinstance(record, dict)
    }
    corpus_root = Path(str(corpus["corpus_root"])).resolve(strict=True)
    print(f"BAXY_CONTEXTUAL_INIT|sentinel_selected={len(selected)}", flush=True)

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root / "src") not in sys.path:
        sys.path.insert(0, str(repo_root / "src"))
    from baxy_mind import wake_verifier as wake
    import onnxruntime as ort
    import torch
    from transformers import AutoModelForCTC

    if not torch.cuda.is_available():
        raise RuntimeError("baxy_contextual_negative_cuda_unavailable")
    config = wake.load_wake_verifier_candidate_config(
        candidate["ctc_manifest_path"]
    )
    if _PRODUCT.sha256(stage1_model_path) != config.stage1_model_sha256:
        raise ValueError("baxy_contextual_negative_stage1_identity_invalid")
    category_ids = wake.resolve_category_ids(
        _PRODUCT.read_object(config.vocabulary_path), wake.BLANK_ID
    )
    for name in _HOLDOUT.STT_FILES:
        (stt_directory / name).resolve(strict=True)
    print("BAXY_CONTEXTUAL_INIT|runtime_imports_ready", flush=True)

    overlap_raw = Path(str(scan_runtime["mel_overlap_raw_model"])).resolve(strict=True)
    overlap_post = Path(str(scan_runtime["mel_overlap_post_model"])).resolve(strict=True)
    if (
        _PRODUCT.sha256(overlap_raw) != scan_runtime.get("mel_overlap_raw_sha256")
        or _PRODUCT.sha256(overlap_post)
        != scan_runtime.get("mel_overlap_post_sha256")
    ):
        raise ValueError("baxy_contextual_negative_stage1_frontend_invalid")
    stage1 = _SCAN.BatchedLiveKitPredictor(
        stage1_model_path,
        batch_size=32,
        mel_overlap_raw_path=overlap_raw,
        mel_overlap_post_path=overlap_post,
    )
    print("BAXY_CONTEXTUAL_INIT|stage1_ready", flush=True)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    hyper_session = ort.InferenceSession(
        str(candidate["graph_path"]),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    print("BAXY_CONTEXTUAL_INIT|hyper_ready", flush=True)
    teacher = AutoModelForCTC.from_pretrained(
        str(teacher_directory), local_files_only=True
    ).eval().cuda()
    print("BAXY_CONTEXTUAL_INIT|cuda_teacher_ready", flush=True)
    policy = candidate["policy"]
    identities = {
        "fusionManifestSha256": _PRODUCT.sha256(candidate["manifest_path"]),
        "ctcVerifierManifestSha256": _PRODUCT.sha256(candidate["ctc_manifest_path"]),
        "cudaParityReportSha256": _PRODUCT.sha256(parity_path),
        "teacherWeightsSha256": _PRODUCT.sha256(teacher_directory / "pytorch_model.bin"),
        "priorHoldoutReportSha256": _PRODUCT.sha256(prior_path),
        "priorStage1ScanSha256": _PRODUCT.sha256(prior_scan_path),
        "corpusManifestSha256": _PRODUCT.sha256(corpus_path),
        "stage1ModelSha256": _PRODUCT.sha256(stage1_model_path),
        "actualFfmpegSha256": _PRODUCT.sha256(ffmpeg_path),
        "sentinelThreshold": str(_V4.SENTINEL_STAGE1_THRESHOLD),
        "fixedViewStarts": ",".join(map(str, _V4.FUSION_VIEW_START_SAMPLES)),
        "stage1ExactBoundaryGuard": str(STAGE1_EXACT_BOUNDARY_GUARD),
        "contextualViewPolicy": contextual_view_policy,
        "expectedSentinelCandidates": str(
            expected_sentinel_candidates
            if expected_sentinel_candidates is not None
            else len(selected)
        ),
        **{
            f"stt:{name}": _PRODUCT.sha256(stt_directory / name)
            for name in _HOLDOUT.STT_FILES
        },
    }
    if additional_checkpoint_identities is not None:
        if (
            not isinstance(additional_checkpoint_identities, dict)
            or any(
                not isinstance(name, str)
                or not name
                or name in identities
                or not isinstance(value, str)
                or not value
                for name, value in additional_checkpoint_identities.items()
            )
        ):
            raise ValueError("baxy_contextual_negative_checkpoint_extension_invalid")
        identities.update(additional_checkpoint_identities)
    checkpoint_identities = (
        screening_checkpoint_identities(identities)
        if screening_cache_path is not None
        else identities
    )
    print("BAXY_CONTEXTUAL_INIT|identities_hashed", flush=True)
    (
        completed_records,
        record_maximum_margins,
        near_views,
        view_count,
        completed_seconds,
        timings,
    ) = _V1.load_checkpoint(checkpoint_path, checkpoint_identities)
    timings.setdefault("stage1ScanMs", [])

    started_campaign = time.perf_counter()

    def prepare_record(
        pair: tuple[dict[str, object], dict[str, object]]
    ) -> tuple[np.ndarray, float, float]:
        record, source = pair
        return rescan_capture(
            record=record,
            source=source,
            corpus_root=corpus_root,
            ffmpeg_path=ffmpeg_path,
            stage1=stage1,
            config=config,
        )

    def submit_stage1_batch(
        pool: ThreadPoolExecutor, record_start: int
    ) -> tuple[list[dict[str, object]], list[object]]:
        batch = selected[
            record_start : min(record_start + record_batch_size, len(selected))
        ]
        futures = []
        for record in batch:
            source = corpus_lookup.get(str(record.get("utterance_id")))
            if (
                source is None
                or source.get("relative_path") != record.get("relative_path")
                or source.get("sha256") != record.get("wav_sha256")
            ):
                raise ValueError("baxy_contextual_negative_record_identity_invalid")
            futures.append(pool.submit(prepare_record, (record, source)))
        return batch, futures

    batch_starts = list(range(completed_records, len(selected), record_batch_size))
    with ThreadPoolExecutor(max_workers=stage1_workers) as stage1_pool:
        if batch_starts:
            batch_records, stage1_futures = submit_stage1_batch(
                stage1_pool, batch_starts[0]
            )
        for batch_position, record_start in enumerate(batch_starts):
            prepared = [future.result() for future in stage1_futures]
            next_batch = None
            view_audio: list[np.ndarray] = []
            view_locators: list[tuple[int, int]] = []
            decode_ms = []
            scan_ms = []
            for offset, (capture, one_decode_ms, one_scan_ms) in enumerate(prepared):
                index = record_start + offset
                decode_ms.append(one_decode_ms)
                scan_ms.append(one_scan_ms)
                for start_sample, values in fixed_views(capture, config, wake):
                    view_audio.append(values)
                    view_locators.append((index, start_sample))

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
                probabilities = _CUDA.compress_category_logits_batch(
                    cuda_logits, category_ids, wake.CATEGORY_NAMES
                )
                ctc_margins = _CUDA.full_clip_ctc_margins(probabilities, wake)
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
                    margin = combined - float(policy["decision_threshold"])
                    absolute_view_index = view_start + local_index
                    record_index, start_sample = view_locators[absolute_view_index]
                    chunk_index = record_index - record_start
                    chunk_margins[chunk_index] = max(chunk_margins[chunk_index], margin)
                    if margin >= -_V1.CPU_RESCORING_BELT:
                        near_views.append(
                            {
                                "recordIndex": record_index,
                                "startSample": start_sample,
                                "cudaDecisionMargin": margin,
                                "hyperScore": hyper_score,
                            }
                        )
            if not np.isfinite(chunk_margins).all():
                raise ValueError("baxy_contextual_negative_record_score_missing")
            timings["decodeMs"].extend(decode_ms)
            timings["stage1ScanMs"].extend(scan_ms)
            record_maximum_margins.extend(chunk_margins.tolist())
            view_count += len(view_audio)
            completed_records = record_start + len(batch_records)
            elapsed = completed_seconds + time.perf_counter() - started_campaign
            _V1.write_checkpoint(
                checkpoint_path,
                identities=checkpoint_identities,
                completed_records=completed_records,
                record_maximum_margins=record_maximum_margins,
                near_views=near_views,
                view_count=view_count,
                elapsed_seconds=elapsed,
                timings={name: timings[name] for name in ("decodeMs", "hyperMs", "cudaCtcMsPerView")},
            )
            print(
                f"BAXY_CONTEXTUAL_NEGATIVE|{completed_records}/{len(selected)}|views={view_count}|near={len(near_views)}",
                flush=True,
            )
            if batch_position + 1 < len(batch_starts):
                next_batch = submit_stage1_batch(
                    stage1_pool, batch_starts[batch_position + 1]
                )
            if next_batch is not None:
                batch_records, stage1_futures = next_batch

    screening_seconds = completed_seconds + time.perf_counter() - started_campaign
    del teacher
    torch.cuda.empty_cache()
    cpu_session = None
    cpu_rescore_margins = []
    cpu_rescore_ms = []
    raw_false_indexes: set[int] = set()
    secondary_guard_indexes: set[int] = set()
    secondary_guard_view_starts: dict[int, set[int]] = {}
    reconstructed: dict[int, np.ndarray] = {}
    for rescore_index, locator in enumerate(near_views):
        if cpu_session is None:
            cpu_session = ort.InferenceSession(
                str(config.graph_path),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
        record_index = int(locator["recordIndex"])
        record = selected[record_index]
        source = corpus_lookup[str(record["utterance_id"])]
        capture = reconstructed.get(record_index)
        if capture is None:
            capture, _, _ = rescan_capture(
                record=record,
                source=source,
                corpus_root=corpus_root,
                ffmpeg_path=ffmpeg_path,
                stage1=stage1,
                config=config,
            )
            reconstructed[record_index] = capture
        values = dict(fixed_views(capture, config, wake)).get(
            int(locator["startSample"])
        )
        if values is None:
            raise ValueError("baxy_contextual_negative_rescore_view_missing")
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
            raw_false_indexes.add(record_index)
            view_guard_passed = secondary_view_guard is None or secondary_view_guard(
                probabilities[0], wake
            )
            audio_guard_passed = secondary_audio_guard is None or secondary_audio_guard(
                values,
                probabilities[0],
                wake,
                record_index,
                int(locator["startSample"]),
            )
            if view_guard_passed and audio_guard_passed:
                secondary_guard_indexes.add(record_index)
                secondary_guard_view_starts.setdefault(record_index, set()).add(
                    int(locator["startSample"])
                )
        print(
            f"BAXY_CONTEXTUAL_NEGATIVE_CPU|{rescore_index + 1}/{len(near_views)}",
            flush=True,
        )

    contextual_evidence_indexes: set[int] = set()
    contextual_seconds = 0.0
    proposals: list[dict[str, object]] = []
    if secondary_guard_indexes:
        if sherpa_site_packages_path is not None:
            sys.path.append(str(sherpa_site_packages_path))
        import sherpa_onnx
        from baxy_mind.voice import _compile_contextual_hotwords

        contextual_started = time.perf_counter()
        recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(stt_directory / "encoder.int8.onnx"),
            decoder=str(stt_directory / "decoder.int8.onnx"),
            joiner=str(stt_directory / "joiner.int8.onnx"),
            tokens=str(stt_directory / "tokens.txt"),
            num_threads=6,
            model_type="nemo_transducer",
            decoding_method="modified_beam_search",
            max_active_paths=8,
            hotwords_score=float(contextual_hotword_score),
        )
        hotwords = _compile_contextual_hotwords(
            stt_directory / "tokens.txt", _V4.CONTEXTUAL_WAKE_TERMS
        )
        if not hotwords:
            raise ValueError("baxy_contextual_negative_hotwords_invalid")
        for record_index in sorted(secondary_guard_indexes):
            capture = reconstructed.get(record_index)
            if capture is None:
                record = selected[record_index]
                source = corpus_lookup[str(record["utterance_id"])]
                capture, _, _ = rescan_capture(
                    record=record,
                    source=source,
                    corpus_root=corpus_root,
                    ffmpeg_path=ffmpeg_path,
                    stage1=stage1,
                    config=config,
                )
                reconstructed[record_index] = capture
        proposals = contextual_decode_proposals(
            secondary_guard_indexes,
            reconstructed,
            secondary_guard_view_starts,
            policy=contextual_view_policy,
            config=config,
            wake=wake,
        )
        transcripts = _V4._decode_batch(
            recognizer,
            proposals,
            batch_size=stt_batch_size,
            hotwords=hotwords,
        )
        for proposal in proposals:
            transcript = transcripts[id(proposal)]
            evidence = _V4.has_contextual_wake_evidence(transcript, wake)
            if contextual_result_observer is not None:
                contextual_result_observer(proposal, transcript, evidence)
            if evidence:
                contextual_evidence_indexes.add(int(proposal["recordIndex"]))
        contextual_seconds = time.perf_counter() - contextual_started

    exposure_hours = float(scan_metrics["audio_hours"])
    raw_false = len(raw_false_indexes)
    guarded_false = len(contextual_evidence_indexes)
    if screening_cache_path is not None:
        identities["screeningCacheSha256"] = _PRODUCT.sha256(checkpoint_path)
    report: dict[str, object] = {
        "schema": (
            "baxy.same-view-hot-fusion-negative-regression.v3"
            if contextual_view_policy == "same_exact_fusion_view"
            else "baxy.contextual-hyperspotter-fusion-negative-regression.v2"
        ),
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "previously_opened_100h_sentinel_rescan_contextual_guard_regression",
        "sources": identities,
        "contract": {
            **screening,
            "priorStage1MaximaReusedForSafePrefilterOnly": True,
            "sentinelPopulationBoundToCompleteStage1AndCorpusRecords": True,
            "reusableScreeningCacheRetained": screening_cache_path is not None,
            "expectedSentinelCandidates": (
                expected_sentinel_candidates
                if expected_sentinel_candidates is not None
                else len(selected)
            ),
            "everySentinelCandidateRescannedAtRuntimeSchedule": True,
            "firstSentinelCrossingUsedForCapture": True,
            "stage1OverlapScreenExactBoundaryGuard": STAGE1_EXACT_BOUNDARY_GUARD,
            "stage1BoundaryViewsRescoredByOriginalCpuPath": True,
            "fixedFusionViewStarts": list(_V4.FUSION_VIEW_START_SAMPLES),
            "everyFusionViewWithinBeltRescoredByExactCpuOnnx": True,
            "contextualAsrRestrictedToExactAcousticFalseCandidates": True,
            "contextualViewPolicy": contextual_view_policy,
            "contextualEvidenceMustShareExactFusionView": (
                contextual_view_policy == "same_exact_fusion_view"
            ),
            "secondaryViewGuard": secondary_guard_contract,
            "secondaryViewGuardRestrictedToSameExactCpuFusionView": True,
            "contextualHotwordScore": float(contextual_hotword_score),
            "contextualAsrRestrictedToSecondaryGuardPassingCandidates": True,
            "priorEstablishedCtcFalseActivations": 0,
            "priorEvidenceAuthority": (
                prior_authority
            ),
            "freshHoldoutClaimSupported": False,
            "farCertificationSupported": False,
        },
        "metrics": {
            "descriptiveExposureHours": exposure_hours,
            "corpusUtterances": int(scan_metrics["utterances"]),
            "sentinelCandidates": len(selected),
            "verificationViews": view_count,
            "cpuRescoredViews": len(near_views),
            "rawFusionFalseActivations": raw_false,
            "secondaryGuardPassingRawFusionFalseActivations": len(
                secondary_guard_indexes
            ),
            "contextualLexicalEvidenceAmongRawFalse": guarded_false,
            "contextualLexicalEvidenceAmongSecondaryGuard": guarded_false,
            "contextualDecodedCaptures": len(proposals),
            "guardedNegativeFalseActivations": guarded_false,
            "guardedDescriptivePointFalseActivationsPerHour": guarded_false
            / exposure_hours,
            "maximumCudaScreenDecisionMargin": float(np.max(record_maximum_margins)),
            "maximumCpuRescoredDecisionMargin": (
                float(np.max(cpu_rescore_margins)) if cpu_rescore_margins else None
            ),
            "minimumCpuRescoredDecisionMargin": (
                float(np.min(cpu_rescore_margins)) if cpu_rescore_margins else None
            ),
        },
        "runtime": {
            "cudaDevice": torch.cuda.get_device_name(0),
            "torch": torch.__version__,
            "onnxruntime": ort.__version__,
            "cudaBatchSize": cuda_batch_size,
            "recordBatchSize": record_batch_size,
            "stage1Workers": stage1_workers,
            "screeningSeconds": screening_seconds,
            "cpuRescoreSeconds": sum(cpu_rescore_ms) / 1000.0,
            "contextualDecodeSeconds": contextual_seconds,
            "decodeMillisecondsPerCandidate": _V1.percentile_summary(timings["decodeMs"]),
            "hyperMillisecondsPerView": _V1.percentile_summary(timings["hyperMs"]),
            "cudaCtcMillisecondsPerView": _V1.percentile_summary(
                timings["cudaCtcMsPerView"]
            ),
            "cpuCtcMillisecondsPerRescoredView": (
                _V1.percentile_summary(cpu_rescore_ms) if cpu_rescore_ms else None
            ),
        },
        "regressionPassed": guarded_false == 0,
        "candidateDevelopmentUse": True,
        "candidateFrozen": False,
        "productOperatingPoint": False,
        "negativeCorpusPreviouslyAccessed": True,
        "blindHumanAudioAccessed": False,
        "recordsTranscriptsOrFilenamesRetained": False,
        "effectsExecuted": 0,
    }
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if screening_cache_path is None:
        checkpoint_path.unlink(missing_ok=True)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--cuda-parity-report", type=Path, required=True)
    parser.add_argument("--teacher-directory", type=Path, required=True)
    parser.add_argument("--prior-holdout-report", type=Path, required=True)
    parser.add_argument("--prior-stage1-scan", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--stage1-model", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--sherpa-site-packages", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cuda-batch-size", type=int, default=32)
    parser.add_argument("--record-batch-size", type=int, default=64)
    parser.add_argument("--stt-batch-size", type=int, default=8)
    parser.add_argument("--stage1-workers", type=int, default=16)
    parser.add_argument("--expected-sentinel-candidates", type=int, required=True)
    parser.add_argument("--screening-cache", type=Path)
    parser.add_argument(
        "--contextual-view-policy",
        choices=CONTEXTUAL_VIEW_POLICIES,
        default="full_capture",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        fusion_manifest_path=arguments.fusion_manifest,
        ctc_manifest_path=arguments.ctc_verifier_manifest,
        cuda_parity_report_path=arguments.cuda_parity_report,
        teacher_directory=arguments.teacher_directory,
        prior_holdout_report_path=arguments.prior_holdout_report,
        prior_stage1_scan_path=arguments.prior_stage1_scan,
        corpus_manifest_path=arguments.corpus_manifest,
        stage1_model_path=arguments.stage1_model,
        ffmpeg_path=arguments.ffmpeg,
        stt_directory=arguments.stt_directory,
        sherpa_site_packages_path=arguments.sherpa_site_packages,
        output_path=arguments.output,
        cuda_batch_size=arguments.cuda_batch_size,
        record_batch_size=arguments.record_batch_size,
        stt_batch_size=arguments.stt_batch_size,
        stage1_workers=arguments.stage1_workers,
        contextual_view_policy=arguments.contextual_view_policy,
        expected_sentinel_candidates=arguments.expected_sentinel_candidates,
        screening_cache_path=arguments.screening_cache,
    )
    print(json.dumps({"passed": report["regressionPassed"], "metrics": report["metrics"]}, sort_keys=True))
    return 0 if report["regressionPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
