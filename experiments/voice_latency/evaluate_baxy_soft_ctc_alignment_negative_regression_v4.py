"""Focal 100 h regression for the preregistered soft-CTC alignment guard.

The completed full-corpus checkpoint is treated only as an attested locator
set.  Every near-boundary view is reconstructed and rescored with the exact
CPU ONNX graph.  Reports contain aggregate counts only: no record identity,
filename, or transcript is retained.
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

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_soft_ctc_negative_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V2 = load_component(
    "evaluate_baxy_contextual_fusion_negative_regression_v2.py",
    "_baxy_soft_ctc_negative_v2",
)
_V8 = load_component(
    "evaluate_baxy_soft_ctc_alignment_development_v8.py",
    "_baxy_soft_ctc_negative_v8",
)
_PRODUCT = _V2._PRODUCT
_CUDA = _V2._CUDA
_V4 = _V2._V4
_HOLDOUT = _V2._HOLDOUT
_SCAN = _V2._SCAN


def validate_checkpoint_contract(
    checkpoint: object,
    failed_regression: object,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if not isinstance(checkpoint, dict) or not isinstance(failed_regression, dict):
        raise ValueError("baxy_soft_ctc_negative_checkpoint_invalid")
    identities = checkpoint.get("identities")
    near_views = checkpoint.get("nearViews")
    maxima = checkpoint.get("recordMaximumMargins")
    sources = failed_regression.get("sources")
    metrics = failed_regression.get("metrics")
    if (
        checkpoint.get("schema")
        != "baxy.hyperspotter-fusion-negative-regression-checkpoint.v1"
        or checkpoint.get("completedRecords") != 28_139
        or checkpoint.get("viewCount") != 56_278
        or not isinstance(identities, dict)
        or not isinstance(near_views, list)
        or len(near_views) != 36
        or not isinstance(maxima, list)
        or len(maxima) != 28_139
        or failed_regression.get("schema")
        != "baxy.contextual-strength-negative-regression.v3"
        or failed_regression.get("regressionPassed") is not False
        or not isinstance(sources, dict)
        or not isinstance(metrics, dict)
        or metrics.get("sentinelCandidates") != 28_139
        or metrics.get("verificationViews") != 56_278
        or metrics.get("cpuRescoredViews") != 36
        or metrics.get("rawFusionFalseActivations") != 34
        or metrics.get("guardedNegativeFalseActivations") != 1
        or failed_regression.get("blindHumanAudioAccessed") is not False
        or failed_regression.get("recordsTranscriptsOrFilenamesRetained") is not False
    ):
        raise ValueError("baxy_soft_ctc_negative_checkpoint_invalid")
    if any(sources.get(name) != value for name, value in identities.items()):
        raise ValueError("baxy_soft_ctc_negative_checkpoint_identity_invalid")
    for locator in near_views:
        if (
            not isinstance(locator, dict)
            or not isinstance(locator.get("recordIndex"), int)
            or not 0 <= int(locator["recordIndex"]) < 28_139
            or int(locator.get("startSample", -1))
            not in _V4.FUSION_VIEW_START_SAMPLES
            or not math.isfinite(float(locator.get("hyperScore", math.nan)))
        ):
            raise ValueError("baxy_soft_ctc_negative_locator_invalid")
    return near_views, identities


def percentile_summary(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    array = np.asarray(values, dtype=np.float64)
    return {
        "minimum": float(np.min(array)),
        "p50": float(np.percentile(array, 50)),
        "p95": float(np.percentile(array, 95)),
        "maximum": float(np.max(array)),
        "mean": float(np.mean(array)),
    }


def evaluate(
    *,
    completed_checkpoint_path: Path,
    development_report_path: Path,
    failed_strength_regression_path: Path,
    fusion_manifest_path: Path,
    ctc_manifest_path: Path,
    prior_stage1_scan_path: Path,
    corpus_manifest_path: Path,
    stage1_model_path: Path,
    ffmpeg_path: Path,
    stt_directory: Path,
    sherpa_site_packages_path: Path | None,
    output_path: Path,
    stt_batch_size: int,
) -> dict[str, object]:
    if output_path.exists() or stt_batch_size < 1:
        raise ValueError("baxy_soft_ctc_negative_schedule_invalid")
    resolved = [
        completed_checkpoint_path,
        development_report_path,
        failed_strength_regression_path,
        fusion_manifest_path,
        ctc_manifest_path,
        prior_stage1_scan_path,
        corpus_manifest_path,
        stage1_model_path,
        ffmpeg_path,
        stt_directory,
    ]
    (
        completed_checkpoint_path,
        development_report_path,
        failed_strength_regression_path,
        fusion_manifest_path,
        ctc_manifest_path,
        prior_stage1_scan_path,
        corpus_manifest_path,
        stage1_model_path,
        ffmpeg_path,
        stt_directory,
    ) = [path.resolve(strict=True) for path in resolved]
    if sherpa_site_packages_path is not None:
        sherpa_site_packages_path = sherpa_site_packages_path.resolve(strict=True)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    checkpoint = _PRODUCT.read_object(completed_checkpoint_path)
    development = _PRODUCT.read_object(development_report_path)
    failed_regression = _PRODUCT.read_object(failed_strength_regression_path)
    near_views, identities = validate_checkpoint_contract(
        checkpoint, failed_regression
    )
    selected_policy = development.get("selectedSoftCtcPolicy")
    if (
        development.get("schema") != "baxy.soft-ctc-alignment-development.v8"
        or development.get("softCtcDevelopmentGatePassed") is not True
        or development.get("blindHumanAudioAccessed") is not False
        or development.get("audioTranscriptsOrFilenamesRetained") is not False
        or development.get("policy", {}).get("guardRequiresSameFusionPassingView")
        is not True
        or development.get("policy", {}).get("contextualHotwordScore") != 4.0
        or not isinstance(selected_policy, dict)
        or selected_policy.get("threshold") != -0.25
    ):
        raise ValueError("baxy_soft_ctc_negative_development_invalid")
    threshold = float(selected_policy["threshold"])

    candidate = _PRODUCT.load_fusion_candidate(
        fusion_manifest_path, ctc_manifest_path
    )
    if (
        identities.get("fusionManifestSha256")
        != _PRODUCT.sha256(candidate["manifest_path"])
        or identities.get("ctcVerifierManifestSha256")
        != _PRODUCT.sha256(candidate["ctc_manifest_path"])
        or identities.get("stage1ModelSha256") != _PRODUCT.sha256(stage1_model_path)
        or identities.get("corpusManifestSha256")
        != _PRODUCT.sha256(corpus_manifest_path)
        or identities.get("priorStage1ScanSha256")
        != _PRODUCT.sha256(prior_stage1_scan_path)
        or identities.get("actualFfmpegSha256") != _PRODUCT.sha256(ffmpeg_path)
    ):
        raise ValueError("baxy_soft_ctc_negative_source_identity_invalid")

    prior_scan = _PRODUCT.read_object(prior_stage1_scan_path)
    corpus = _PRODUCT.read_object(corpus_manifest_path)
    scan_metrics = prior_scan.get("metrics")
    scan_runtime = prior_scan.get("runtime")
    if (
        prior_scan.get("schema")
        != "baxy.openslr-librispeech-livekit-holdout-scan.v1"
        or prior_scan.get("model_sha256") != _PRODUCT.sha256(stage1_model_path)
        or prior_scan.get("corpus_manifest_sha256")
        != _PRODUCT.sha256(corpus_manifest_path)
        or corpus.get("schema") != "baxy.openslr-librispeech-negative-holdout.v1"
        or not isinstance(scan_metrics, dict)
        or scan_metrics.get("utterances") != 28_539
        or not isinstance(scan_runtime, dict)
        or not isinstance(corpus.get("records"), list)
    ):
        raise ValueError("baxy_soft_ctc_negative_prior_invalid")
    selected = _V2.select_sentinel_records(prior_scan.get("records"))
    if len(selected) != 28_139:
        raise ValueError("baxy_soft_ctc_negative_sentinel_invalid")
    corpus_lookup = {
        str(record["utterance_id"]): record
        for record in corpus["records"]
        if isinstance(record, dict)
    }
    corpus_root = Path(str(corpus["corpus_root"])).resolve(strict=True)

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root / "src") not in sys.path:
        sys.path.insert(0, str(repo_root / "src"))
    from baxy_mind import wake_verifier as wake
    from baxy_mind.voice import _compile_contextual_hotwords
    import onnxruntime as ort

    config = wake.load_wake_verifier_candidate_config(
        candidate["ctc_manifest_path"]
    )
    if _PRODUCT.sha256(stage1_model_path) != config.stage1_model_sha256:
        raise ValueError("baxy_soft_ctc_negative_stage1_identity_invalid")
    overlap_raw = Path(str(scan_runtime["mel_overlap_raw_model"])).resolve(
        strict=True
    )
    overlap_post = Path(str(scan_runtime["mel_overlap_post_model"])).resolve(
        strict=True
    )
    if (
        _PRODUCT.sha256(overlap_raw) != scan_runtime.get("mel_overlap_raw_sha256")
        or _PRODUCT.sha256(overlap_post)
        != scan_runtime.get("mel_overlap_post_sha256")
    ):
        raise ValueError("baxy_soft_ctc_negative_stage1_frontend_invalid")
    stage1 = _SCAN.BatchedLiveKitPredictor(
        stage1_model_path,
        batch_size=32,
        mel_overlap_raw_path=overlap_raw,
        mel_overlap_post_path=overlap_post,
    )
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    cpu_session = ort.InferenceSession(
        str(config.graph_path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    category_ids = wake.resolve_category_ids(
        _PRODUCT.read_object(config.vocabulary_path), wake.BLANK_ID
    )
    policy = candidate["policy"]

    started = time.perf_counter()
    reconstructed: dict[int, np.ndarray] = {}
    raw_false_indexes: set[int] = set()
    soft_passing_indexes: set[int] = set()
    exact_margins: list[float] = []
    soft_margins: list[float] = []
    rescore_ms: list[float] = []
    for position, locator in enumerate(near_views, start=1):
        record_index = int(locator["recordIndex"])
        record = selected[record_index]
        source = corpus_lookup.get(str(record.get("utterance_id")))
        if (
            source is None
            or source.get("relative_path") != record.get("relative_path")
            or source.get("sha256") != record.get("wav_sha256")
        ):
            raise ValueError("baxy_soft_ctc_negative_record_identity_invalid")
        capture = reconstructed.get(record_index)
        if capture is None:
            capture, _, _ = _V2.rescan_capture(
                record=record,
                source=source,
                corpus_root=corpus_root,
                ffmpeg_path=ffmpeg_path,
                stage1=stage1,
                config=config,
            )
            reconstructed[record_index] = capture
        view = dict(_V2.fixed_views(capture, config, wake)).get(
            int(locator["startSample"])
        )
        if view is None:
            raise ValueError("baxy_soft_ctc_negative_view_missing")
        rescore_started = time.perf_counter()
        logits = cpu_session.run(
            ["logits"], {"input_values": wake.normalize_audio(view)}
        )[0]
        probabilities = _CUDA.compress_category_logits_batch(
            logits, category_ids, wake.CATEGORY_NAMES
        )
        ctc_margin = float(_CUDA.full_clip_ctc_margins(probabilities, wake)[0])
        exact_margin = float(locator["hyperScore"]) + float(
            policy["ctc_weight"]
        ) * (
            (ctc_margin - float(policy["ctc_center"]))
            / float(policy["ctc_scale"])
        ) - float(policy["decision_threshold"])
        soft_margin = _V8.soft_local_ctc_margin(probabilities[0], wake)
        rescore_ms.append((time.perf_counter() - rescore_started) * 1000.0)
        exact_margins.append(exact_margin)
        soft_margins.append(soft_margin)
        if exact_margin >= 0.0:
            raw_false_indexes.add(record_index)
            if soft_margin >= threshold:
                soft_passing_indexes.add(record_index)
        print(
            f"BAXY_SOFT_CTC_NEGATIVE|{position}/{len(near_views)}",
            flush=True,
        )

    if len(raw_false_indexes) != 34:
        raise ValueError("baxy_soft_ctc_negative_raw_control_mismatch")

    contextual_indexes: set[int] = set()
    contextual_seconds = 0.0
    if soft_passing_indexes:
        if sherpa_site_packages_path is not None:
            sys.path.append(str(sherpa_site_packages_path))
        import sherpa_onnx

        for name in _HOLDOUT.STT_FILES:
            (stt_directory / name).resolve(strict=True)
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
            hotwords_score=4.0,
        )
        hotwords = _compile_contextual_hotwords(
            stt_directory / "tokens.txt", _V4.CONTEXTUAL_WAKE_TERMS
        )
        if not hotwords:
            raise ValueError("baxy_soft_ctc_negative_hotwords_invalid")
        proposals = [
            {"capture": reconstructed[index], "recordIndex": index}
            for index in sorted(soft_passing_indexes)
        ]
        transcripts = _V4._decode_batch(
            recognizer,
            proposals,
            batch_size=stt_batch_size,
            hotwords=hotwords,
        )
        for proposal in proposals:
            if _V4.has_contextual_wake_evidence(
                transcripts[id(proposal)], wake
            ):
                contextual_indexes.add(int(proposal["recordIndex"]))
        contextual_seconds = time.perf_counter() - contextual_started

    exposure_hours = float(failed_regression["metrics"]["descriptiveExposureHours"])
    guarded_false = len(contextual_indexes)
    report: dict[str, object] = {
        "schema": "baxy.soft-ctc-alignment-negative-regression.v4",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "previously_opened_100h_completed_checkpoint_focal_soft_ctc_regression",
        "sources": {
            **identities,
            "completedCheckpointSha256": _PRODUCT.sha256(
                completed_checkpoint_path
            ),
            "developmentReportSha256": _PRODUCT.sha256(development_report_path),
            "failedStrengthRegressionSha256": _PRODUCT.sha256(
                failed_strength_regression_path
            ),
        },
        "contract": {
            "completedFullCorpusCheckpointUsedForLocatorsOnly": True,
            "everyNearViewReconstructedFromHashedSourceAudio": True,
            "everyNearViewRescoredByExactCpuOnnx": True,
            "rawFusionControlRequired": 34,
            "softCtcThreshold": threshold,
            "softCtcThresholdSelectedBeforeThisRegression": True,
            "softCtcRequiresSameFusionPassingView": True,
            "contextualHotwordScore": 4.0,
            "contextualDecodeRestrictedToSoftCtcPassingRawFusionCandidates": True,
            "priorEstablishedCtcFalseActivations": 0,
            "freshHoldoutClaimSupported": False,
            "farCertificationSupported": False,
        },
        "metrics": {
            "descriptiveExposureHours": exposure_hours,
            "sentinelCandidatesRepresentedByCheckpoint": 28_139,
            "verificationViewsRepresentedByCheckpoint": 56_278,
            "exactCpuRescoredViews": len(near_views),
            "rawFusionFalseActivations": len(raw_false_indexes),
            "softCtcPassingRawFusionFalseActivations": len(soft_passing_indexes),
            "guardedNegativeFalseActivations": guarded_false,
            "guardedDescriptivePointFalseActivationsPerHour": guarded_false
            / exposure_hours,
            "exactFusionMarginSummary": percentile_summary(exact_margins),
            "softCtcMarginSummary": percentile_summary(soft_margins),
        },
        "runtime": {
            "onnxruntime": ort.__version__,
            "runtimeSeconds": time.perf_counter() - started,
            "exactAndSoftRescoreMilliseconds": percentile_summary(rescore_ms),
            "contextualDecodeSeconds": contextual_seconds,
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
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completed-checkpoint", type=Path, required=True)
    parser.add_argument("--development-report", type=Path, required=True)
    parser.add_argument("--failed-strength-regression", type=Path, required=True)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--prior-stage1-scan", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--stage1-model", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--sherpa-site-packages", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stt-batch-size", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        completed_checkpoint_path=arguments.completed_checkpoint,
        development_report_path=arguments.development_report,
        failed_strength_regression_path=arguments.failed_strength_regression,
        fusion_manifest_path=arguments.fusion_manifest,
        ctc_manifest_path=arguments.ctc_verifier_manifest,
        prior_stage1_scan_path=arguments.prior_stage1_scan,
        corpus_manifest_path=arguments.corpus_manifest,
        stage1_model_path=arguments.stage1_model,
        ffmpeg_path=arguments.ffmpeg,
        stt_directory=arguments.stt_directory,
        sherpa_site_packages_path=arguments.sherpa_site_packages,
        output_path=arguments.output,
        stt_batch_size=arguments.stt_batch_size,
    )
    print(
        json.dumps(
            {"passed": report["regressionPassed"], "metrics": report["metrics"]},
            sort_keys=True,
        )
    )
    return 0 if report["regressionPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
