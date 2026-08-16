"""Evaluate a conservative lexical guard for the BAXY fusion fallback.

The policy is fixed before expanded results are produced:

* preserve every acceptance from the established product CTC verifier;
* otherwise, require both the continuous HyperSpotter/CTC fusion and an exact
  local-ASR lexical rendering of a BAXY alias.

Legacy human development and the already-open 100-hour negative regression
define the rule.  Expanded human development is excluded from selection and
is evaluated only after the rule is fixed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_lexical_guard_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PRODUCT = load_component(
    "audit_baxy_hyperspotter_fusion_product_candidate_v1.py",
    "_baxy_lexical_guard_product_v3",
)
_HOLDOUT = load_component(
    "evaluate_wake_verifier_negative_holdout_v1.py",
    "_baxy_lexical_guard_holdout_v3",
)
_SCAN = load_component(
    "scan_openslr_librispeech_livekit_development.py",
    "_baxy_lexical_guard_scan_v3",
)


def guarded_acceptance(
    *,
    established_ctc_accepted: bool,
    continuous_fusion_accepted: bool,
    exact_lexical_target: bool,
) -> tuple[bool, str]:
    if established_ctc_accepted:
        return True, "established_ctc"
    if continuous_fusion_accepted and exact_lexical_target:
        return True, "lexically_guarded_continuous_fusion"
    return False, "rejected"


def summarize(records: list[dict[str, object]], decision_name: str) -> dict[str, object]:
    positives = [record for record in records if record["label"] == "positive"]
    negatives = [
        record for record in records if record["label"] == "matched_negative"
    ]
    positive_hits = sum(bool(record[decision_name]) for record in positives)
    false_hits = sum(bool(record[decision_name]) for record in negatives)
    return {
        "positiveHits": positive_hits,
        "positiveTotal": len(positives),
        "falseHits": false_hits,
        "negativeTotal": len(negatives),
        "gatePassed": positive_hits == len(positives) and false_hits == 0,
    }


def continuous_fusion_decision(
    *,
    capture: np.ndarray,
    verification_start_sample: int,
    config: object,
    verifier: object,
    hyper_session: object,
    candidate: dict[str, object],
    wake: object,
) -> tuple[bool, float | None]:
    policy = candidate["policy"]
    maximum_margin = None
    for start in wake.verification_view_starts(
        primary_start_sample=config.primary_view_start_samples,
        activity_start_sample=verification_start_sample,
        activity_lookback_samples=config.activity_lookback_samples,
    ):
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
        values = np.ascontiguousarray(values, dtype=np.float32)
        logmel = _PRODUCT.numpy_log_mel_spectrogram(
            values, candidate["mel_filters"]
        )
        hyper_logits = hyper_session.run(
            ["logits"], {"logmel": logmel[None, :, :]}
        )[0]
        ctc_logits = verifier._session.run(
            ["logits"], {"input_values": wake.normalize_audio(values)}
        )[0]
        probabilities = wake.compress_category_logits_numpy(
            ctc_logits, verifier._category_ids
        )
        ctc_margin = _PRODUCT.full_clip_ctc_margin(
            np.log(np.maximum(probabilities, 1e-12)), wake
        )
        score = float(np.max(hyper_logits)) + float(policy["ctc_weight"]) * (
            (ctc_margin - float(policy["ctc_center"]))
            / float(policy["ctc_scale"])
        )
        margin = score - float(policy["decision_threshold"])
        maximum_margin = margin if maximum_margin is None else max(maximum_margin, margin)
    return (
        maximum_margin is not None and maximum_margin >= 0.0,
        maximum_margin,
    )


def evaluate(
    *,
    expanded_corpus_manifest_path: Path,
    stage1_model_path: Path,
    ctc_manifest_path: Path,
    fusion_manifest_path: Path,
    stt_directory: Path,
    ffmpeg_path: Path,
    legacy_product_report_path: Path,
    negative_holdout_report_path: Path,
    linear_negative_regression_path: Path,
    raw_fusion_audit_path: Path,
    output_path: Path,
    stt_batch_size: int,
) -> dict[str, object]:
    if output_path.exists() or stt_batch_size < 1:
        raise ValueError("baxy_lexical_guard_schedule_invalid")
    paths = [
        expanded_corpus_manifest_path,
        stage1_model_path,
        ctc_manifest_path,
        fusion_manifest_path,
        stt_directory,
        ffmpeg_path,
        legacy_product_report_path,
        negative_holdout_report_path,
        linear_negative_regression_path,
        raw_fusion_audit_path,
    ]
    (
        expanded_corpus_manifest_path,
        stage1_model_path,
        ctc_manifest_path,
        fusion_manifest_path,
        stt_directory,
        ffmpeg_path,
        legacy_product_report_path,
        negative_holdout_report_path,
        linear_negative_regression_path,
        raw_fusion_audit_path,
    ) = [path.resolve(strict=True) for path in paths]
    output_path = output_path.resolve()
    candidate = _PRODUCT.load_fusion_candidate(
        fusion_manifest_path, ctc_manifest_path
    )
    expanded = _PRODUCT.read_object(expanded_corpus_manifest_path)
    legacy = _PRODUCT.read_object(legacy_product_report_path)
    negative = _PRODUCT.read_object(negative_holdout_report_path)
    linear = _PRODUCT.read_object(linear_negative_regression_path)
    raw_fusion = _PRODUCT.read_object(raw_fusion_audit_path)
    legacy_metrics = legacy.get("metrics")
    negative_metrics = negative.get("metrics")
    linear_metrics = linear.get("metrics")
    raw_metrics = raw_fusion.get("allHumanDevelopment")
    if (
        expanded.get("schema") != "baxy.ccby-wake-v5-development-corpus.v1"
        or expanded.get("blind_human_audio_accessed") is not False
        or legacy.get("schema")
        != "baxy.wake-verifier-product-capture-development.v1"
        or legacy.get("blind_human_partition_accessed") is not False
        or not isinstance(legacy_metrics, dict)
        or legacy_metrics.get("positive_accepted") != 14
        or legacy_metrics.get("positive_total") != 14
        or legacy_metrics.get("hard_negative_false_accepts") != 0
        or legacy_metrics.get("hard_negative_total") != 4
        or negative.get("schema") != "baxy.wake-verifier-negative-holdout-gate.v1"
        or negative.get("negative_gate_passed") is not True
        or not isinstance(negative_metrics, dict)
        or negative_metrics.get("stage1_eligible") != 5854
        or negative_metrics.get("negative_false_activations") != 0
        or linear.get("schema")
        != "baxy.hyperspotter-fusion-negative-regression.v1"
        or not isinstance(linear_metrics, dict)
        or int(linear_metrics.get("negativeFalseActivations", 0)) < 1
        or raw_fusion.get("schema")
        != "baxy.hyperspotter-fusion-product-runtime-audit.v1"
        or raw_fusion.get("rawProductParityPassed") is not True
        or not isinstance(raw_metrics, dict)
        or raw_metrics.get("positiveHits") != 18
        or raw_metrics.get("falseHits") != 0
    ):
        raise ValueError("baxy_lexical_guard_selection_evidence_invalid")

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root / "src") not in sys.path:
        sys.path.insert(0, str(repo_root / "src"))
    from baxy_mind import wake_verifier as wake
    from baxy_mind.voice import SileroVad
    import onnxruntime as ort
    import sherpa_onnx

    eligible_negative_records = [
        record
        for record in negative.get("records", [])
        if isinstance(record, dict) and record.get("stage1_eligible") is True
    ]
    exact_negative_transcripts = sum(
        wake.has_exact_lexical_target(str(record.get("transcript") or ""))
        for record in eligible_negative_records
    )
    if len(eligible_negative_records) != 5854 or exact_negative_transcripts != 0:
        raise ValueError("baxy_lexical_guard_negative_lexical_boundary_invalid")
    source_records = [
        record
        for record in expanded.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    labels = [record.get("label") for record in source_records]
    if len(source_records) != 12 or labels.count("positive") != 4 or labels.count("matched_negative") != 8:
        raise ValueError("baxy_lexical_guard_expanded_records_invalid")
    config = wake.load_wake_verifier_candidate_config(ctc_manifest_path)
    if _PRODUCT.sha256(stage1_model_path) != config.stage1_model_sha256:
        raise ValueError("baxy_lexical_guard_stage1_mismatch")
    for name in _HOLDOUT.STT_FILES:
        (stt_directory / name).resolve(strict=True)
    stage1 = _SCAN.BatchedLiveKitPredictor(stage1_model_path)
    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(stt_directory / "encoder.int8.onnx"),
        decoder=str(stt_directory / "decoder.int8.onnx"),
        joiner=str(stt_directory / "joiner.int8.onnx"),
        tokens=str(stt_directory / "tokens.txt"),
        num_threads=6,
        model_type="nemo_transducer",
        decoding_method="modified_beam_search",
        max_active_paths=8,
    )
    warmup = recognizer.create_stream()
    warmup.accept_waveform(wake.SAMPLE_RATE, np.zeros(wake.SAMPLE_RATE // 2, np.float32))
    recognizer.decode_stream(warmup)
    verifier = wake.OnnxWakeVerifier(config)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    hyper_session = ort.InferenceSession(
        str(candidate["graph_path"]),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    vad = SileroVad()
    corpus_root = expanded_corpus_manifest_path.parent
    proposals = []
    started = time.perf_counter()
    for source in source_records:
        path = (corpus_root / str(source["output_relative_path"])).resolve(strict=True)
        wav = source.get("wav")
        if not isinstance(wav, dict) or _PRODUCT.sha256(path) != wav.get("sha256"):
            raise ValueError("baxy_lexical_guard_audio_hash_mismatch")
        audio = _HOLDOUT.decode_flac(ffmpeg_path, path)
        scan = _SCAN.streaming_scores(
            stage1,
            audio,
            retention_threshold=config.broad_threshold,
            hop_samples=config.stage1_hop_samples,
            frame_samples=512,
        )
        retained = scan["retained_windows"]
        if retained:
            hit = retained[0]
            capture, _source_start = _HOLDOUT.capture_audio(
                audio,
                hit_end_seconds=float(hit["window_end_seconds"]),
                pre_roll_seconds=config.stage1_pre_roll_seconds,
                maximum_turn_samples=config.maximum_turn_samples,
            )
            verification_start = _HOLDOUT.activity_verification_start(
                capture,
                pre_roll_seconds=config.stage1_pre_roll_seconds,
                threshold=config.activity_vad_threshold,
                alignment_samples=config.activity_alignment_samples,
                default_start_sample=config.primary_view_start_samples,
                vad=vad,
            )
        else:
            hit = None
            capture = None
            verification_start = None
        proposals.append(
            {
                "source": source,
                "hit": hit,
                "capture": capture,
                "verification_start": verification_start,
            }
        )
    selected = [proposal for proposal in proposals if proposal["hit"] is not None]
    transcripts: dict[int, str] = {}
    for start in range(0, len(selected), stt_batch_size):
        batch = selected[start : start + stt_batch_size]
        streams = []
        for proposal in batch:
            stream = recognizer.create_stream()
            stream.accept_waveform(wake.SAMPLE_RATE, proposal["capture"])
            streams.append(stream)
        for stream in streams:
            recognizer.decode_stream(stream)
        for proposal, stream in zip(batch, streams, strict=True):
            transcripts[id(proposal)] = str(stream.result.text or "").strip()

    results = []
    for index, proposal in enumerate(proposals):
        source = proposal["source"]
        hit = proposal["hit"]
        if hit is None:
            transcript = ""
            established = False
            continuous = False
            continuous_margin = None
        else:
            transcript = transcripts[id(proposal)]
            established_decision = verifier.verify(
                proposal["capture"],
                transcript,
                float(hit["score"]),
                verification_start_sample=int(proposal["verification_start"]),
            )
            established = established_decision.accepted
            if established_decision.stage1_eligible:
                continuous, continuous_margin = continuous_fusion_decision(
                    capture=proposal["capture"],
                    verification_start_sample=int(proposal["verification_start"]),
                    config=config,
                    verifier=verifier,
                    hyper_session=hyper_session,
                    candidate=candidate,
                    wake=wake,
                )
            else:
                continuous = False
                continuous_margin = None
        lexical = wake.has_exact_lexical_target(transcript)
        guarded, method = guarded_acceptance(
            established_ctc_accepted=established,
            continuous_fusion_accepted=continuous,
            exact_lexical_target=lexical,
        )
        results.append(
            {
                "label": source["label"],
                "stage1Proposed": hit is not None,
                "exactLexicalTarget": lexical,
                "establishedCtcAccepted": established,
                "continuousFusionAccepted": continuous,
                "continuousFusionDecisionMargin": continuous_margin,
                "guardedAccepted": guarded,
                "guardMethod": method,
            }
        )
        print(f"BAXY_LEXICAL_GUARD|{index + 1}/{len(proposals)}", flush=True)
    report: dict[str, object] = {
        "schema": "baxy.hyperspotter-fusion-lexical-guard-development.v3",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "legacy_and_open_negative_selected_expanded_excluded_product_capture",
        "sources": {
            "expandedCorpusManifestSha256": _PRODUCT.sha256(expanded_corpus_manifest_path),
            "stage1ModelSha256": _PRODUCT.sha256(stage1_model_path),
            "ctcVerifierManifestSha256": _PRODUCT.sha256(ctc_manifest_path),
            "fusionManifestSha256": _PRODUCT.sha256(fusion_manifest_path),
            "legacyProductReportSha256": _PRODUCT.sha256(legacy_product_report_path),
            "negativeHoldoutReportSha256": _PRODUCT.sha256(negative_holdout_report_path),
            "linearNegativeRegressionSha256": _PRODUCT.sha256(linear_negative_regression_path),
            "rawFusionAuditSha256": _PRODUCT.sha256(raw_fusion_audit_path),
            "ffmpegSha256": _PRODUCT.sha256(ffmpeg_path),
        },
        "policy": {
            "formula": "established_ctc OR (continuous_fusion AND exact_lexical_target)",
            "selectionPartition": "human_legacy_plus_previously_opened_negative_regression",
            "expandedPartitionUsedForSelection": False,
            "establishedCtcLegacyPositiveHits": 14,
            "establishedCtcLegacyPositiveTotal": 14,
            "establishedCtcLegacyFalseHits": 0,
            "eligibleNegativeTranscripts": len(eligible_negative_records),
            "eligibleNegativeExactLexicalTargets": exact_negative_transcripts,
            "linearFusionNegativeFalseActivations": linear_metrics["negativeFalseActivations"],
        },
        "expandedStage1": {
            "positiveProposals": sum(
                result["label"] == "positive" and result["stage1Proposed"]
                for result in results
            ),
            "negativeProposals": sum(
                result["label"] == "matched_negative" and result["stage1Proposed"]
                for result in results
            ),
            "positiveExactLexicalTargets": sum(
                result["label"] == "positive" and result["exactLexicalTarget"]
                for result in results
            ),
            "negativeExactLexicalTargets": sum(
                result["label"] == "matched_negative" and result["exactLexicalTarget"]
                for result in results
            ),
        },
        "expandedEstablishedCtc": summarize(results, "establishedCtcAccepted"),
        "expandedContinuousFusion": summarize(results, "continuousFusionAccepted"),
        "expandedGuardedPolicy": summarize(results, "guardedAccepted"),
        "runtimeSeconds": time.perf_counter() - started,
        "expandedHumanDevelopmentAudioAccessed": True,
        "blindHumanAudioAccessed": False,
        "audioTranscriptsOrFilenamesRetained": False,
        "candidateFrozen": True,
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
    parser.add_argument("--expanded-corpus-manifest", type=Path, required=True)
    parser.add_argument("--stage1-model", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--legacy-product-report", type=Path, required=True)
    parser.add_argument("--negative-holdout-report", type=Path, required=True)
    parser.add_argument("--linear-negative-regression", type=Path, required=True)
    parser.add_argument("--raw-fusion-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stt-batch-size", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        expanded_corpus_manifest_path=arguments.expanded_corpus_manifest,
        stage1_model_path=arguments.stage1_model,
        ctc_manifest_path=arguments.ctc_verifier_manifest,
        fusion_manifest_path=arguments.fusion_manifest,
        stt_directory=arguments.stt_directory,
        ffmpeg_path=arguments.ffmpeg,
        legacy_product_report_path=arguments.legacy_product_report,
        negative_holdout_report_path=arguments.negative_holdout_report,
        linear_negative_regression_path=arguments.linear_negative_regression,
        raw_fusion_audit_path=arguments.raw_fusion_audit,
        output_path=arguments.output,
        stt_batch_size=arguments.stt_batch_size,
    )
    print(
        json.dumps(
            {
                "stage1": report["expandedStage1"],
                "ctc": report["expandedEstablishedCtc"],
                "continuous": report["expandedContinuousFusion"],
                "guarded": report["expandedGuardedPolicy"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["expandedGuardedPolicy"]["gatePassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
