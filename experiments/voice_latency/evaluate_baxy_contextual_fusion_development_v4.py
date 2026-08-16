"""Evaluate the bounded contextual fallback selected on opened development data.

This is deliberately a development experiment, not a product or holdout claim.
The expanded human partition has already informed the fixed policy:

* a permissive LiveKit sentinel at 0.01 only opens local analysis;
* the established attested CTC verifier keeps its existing authority;
* otherwise, both fixed 2.5 s/4.0 s fusion views and a second, wake-only
  contextual Parakeet decode must corroborate the proposal.

No filename or transcript is retained in the output report.
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


SENTINEL_STAGE1_THRESHOLD = 0.01
FUSION_VIEW_START_SAMPLES = (40_000, 64_000)
CONTEXTUAL_WAKE_TERMS = ("baxy", "baxi", "basi", "bakse")
CONTEXTUAL_HOTWORD_SCORE = 5.0
_CONTEXTUAL_PREFIX_TARGETS = ("baxy", "baxi")
_CONTEXTUAL_SPLIT_PHRASES = (("paz", "y"),)


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_contextual_fusion_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V3 = load_component(
    "evaluate_baxy_fusion_lexical_guard_development_v3.py",
    "_baxy_contextual_fusion_v3",
)
_PRODUCT = _V3._PRODUCT
_HOLDOUT = _V3._HOLDOUT
_SCAN = _V3._SCAN


def has_contextual_wake_evidence(transcript: str, wake: object) -> bool:
    """Recognize only measured renderings from a wake-biased ASR pass.

    ``basi`` and other complete aliases are handled by the existing exact
    matcher.  A bounded ``baxi*`` prefix covers Parakeet's measured
    ``Baximan`` rendering without admitting the ordinary English ``basin``.
    The two-token form covers the measured Spanish homophonic split.
    Acoustic fusion remains mandatory; this function cannot open a turn.
    """

    if wake.has_exact_lexical_target(transcript):
        return True
    words = wake.lexical_words(transcript)
    if any(
        word.startswith(prefix) and len(word) <= len(prefix) + 3
        for word in words
        for prefix in _CONTEXTUAL_PREFIX_TARGETS
    ):
        return True
    return any(
        words[index : index + len(phrase)] == phrase
        for phrase in _CONTEXTUAL_SPLIT_PHRASES
        for index in range(len(words) - len(phrase) + 1)
    )


def guarded_acceptance(
    *,
    established_ctc_accepted: bool,
    fixed_fusion_accepted: bool,
    contextual_lexical_evidence: bool,
) -> tuple[bool, str]:
    if established_ctc_accepted:
        return True, "established_ctc"
    if fixed_fusion_accepted and contextual_lexical_evidence:
        return True, "contextually_guarded_fixed_fusion"
    return False, "rejected"


def fixed_fusion_decision(
    *,
    capture: np.ndarray,
    config: object,
    verifier: object,
    hyper_session: object,
    candidate: dict[str, object],
    wake: object,
) -> tuple[bool, float | None]:
    policy = candidate["policy"]
    maximum_margin = None
    for start in FUSION_VIEW_START_SAMPLES:
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


def _decode_batch(
    recognizer: object,
    proposals: list[dict[str, object]],
    *,
    batch_size: int,
    hotwords: str | None = None,
) -> dict[int, str]:
    transcripts: dict[int, str] = {}
    for start in range(0, len(proposals), batch_size):
        batch = proposals[start : start + batch_size]
        streams = []
        for proposal in batch:
            stream = (
                recognizer.create_stream(hotwords=hotwords)
                if hotwords
                else recognizer.create_stream()
            )
            stream.accept_waveform(16_000, proposal["capture"])
            streams.append(stream)
        for stream in streams:
            recognizer.decode_stream(stream)
        for proposal, stream in zip(batch, streams, strict=True):
            transcripts[id(proposal)] = str(stream.result.text or "").strip()
    return transcripts


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
        raise ValueError("baxy_contextual_fusion_schedule_invalid")
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
        or not isinstance(legacy_metrics, dict)
        or legacy_metrics.get("positive_accepted") != 14
        or legacy_metrics.get("hard_negative_false_accepts") != 0
        or negative.get("schema") != "baxy.wake-verifier-negative-holdout-gate.v1"
        or not isinstance(negative_metrics, dict)
        or negative_metrics.get("stage1_eligible") != 5854
        or negative_metrics.get("negative_false_activations") != 0
        or linear.get("schema")
        != "baxy.hyperspotter-fusion-negative-regression.v1"
        or not isinstance(linear_metrics, dict)
        or int(linear_metrics.get("negativeFalseActivations", 0)) < 1
        or raw_fusion.get("schema")
        != "baxy.hyperspotter-fusion-product-runtime-audit.v1"
        or not isinstance(raw_metrics, dict)
        or raw_metrics.get("positiveHits") != 18
        or raw_metrics.get("falseHits") != 0
    ):
        raise ValueError("baxy_contextual_fusion_selection_evidence_invalid")

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root / "src") not in sys.path:
        sys.path.insert(0, str(repo_root / "src"))
    from baxy_mind import wake_verifier as wake
    from baxy_mind.voice import SileroVad, _compile_contextual_hotwords
    import onnxruntime as ort
    import sherpa_onnx

    eligible_negative_records = [
        record
        for record in negative.get("records", [])
        if isinstance(record, dict) and record.get("stage1_eligible") is True
    ]
    negative_contextual_boundaries = sum(
        has_contextual_wake_evidence(str(record.get("transcript") or ""), wake)
        for record in eligible_negative_records
    )
    if len(eligible_negative_records) != 5854 or negative_contextual_boundaries != 0:
        raise ValueError("baxy_contextual_fusion_negative_boundary_invalid")

    source_records = [
        record
        for record in expanded.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    labels = [record.get("label") for record in source_records]
    if (
        len(source_records) != 12
        or labels.count("positive") != 4
        or labels.count("matched_negative") != 8
    ):
        raise ValueError("baxy_contextual_fusion_expanded_records_invalid")

    config = wake.load_wake_verifier_candidate_config(ctc_manifest_path)
    if _PRODUCT.sha256(stage1_model_path) != config.stage1_model_sha256:
        raise ValueError("baxy_contextual_fusion_stage1_mismatch")
    for name in _HOLDOUT.STT_FILES:
        (stt_directory / name).resolve(strict=True)
    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(stt_directory / "encoder.int8.onnx"),
        decoder=str(stt_directory / "decoder.int8.onnx"),
        joiner=str(stt_directory / "joiner.int8.onnx"),
        tokens=str(stt_directory / "tokens.txt"),
        num_threads=6,
        model_type="nemo_transducer",
        decoding_method="modified_beam_search",
        max_active_paths=8,
        hotwords_score=CONTEXTUAL_HOTWORD_SCORE,
    )
    hotwords = _compile_contextual_hotwords(
        stt_directory / "tokens.txt", CONTEXTUAL_WAKE_TERMS
    )
    if not hotwords:
        raise ValueError("baxy_contextual_fusion_hotwords_invalid")
    warmup = recognizer.create_stream()
    warmup.accept_waveform(16_000, np.zeros(8_000, np.float32))
    recognizer.decode_stream(warmup)
    stage1 = _SCAN.BatchedLiveKitPredictor(stage1_model_path)
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
    proposals: list[dict[str, object]] = []
    started = time.perf_counter()
    for source in source_records:
        path = (corpus_root / str(source["output_relative_path"])).resolve(strict=True)
        wav = source.get("wav")
        if not isinstance(wav, dict) or _PRODUCT.sha256(path) != wav.get("sha256"):
            raise ValueError("baxy_contextual_fusion_audio_hash_mismatch")
        audio = _HOLDOUT.decode_flac(ffmpeg_path, path)
        scan = _SCAN.streaming_scores(
            stage1,
            audio,
            retention_threshold=SENTINEL_STAGE1_THRESHOLD,
            hop_samples=config.stage1_hop_samples,
            frame_samples=512,
        )
        retained = scan["retained_windows"]
        if retained:
            hit = retained[0]
            capture, _ = _HOLDOUT.capture_audio(
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
    primary_transcripts = _decode_batch(
        recognizer, selected, batch_size=stt_batch_size
    )
    intermediate: list[dict[str, object]] = []
    contextual_targets: list[dict[str, object]] = []
    for proposal in proposals:
        hit = proposal["hit"]
        if hit is None:
            established = False
            fixed = False
            margin = None
            transcript = ""
        else:
            transcript = primary_transcripts[id(proposal)]
            established = verifier.verify(
                proposal["capture"],
                transcript,
                float(hit["score"]),
                verification_start_sample=int(proposal["verification_start"]),
            ).accepted
            fixed, margin = fixed_fusion_decision(
                capture=proposal["capture"],
                config=config,
                verifier=verifier,
                hyper_session=hyper_session,
                candidate=candidate,
                wake=wake,
            )
        item = {
            "proposal": proposal,
            "established": established,
            "fixed": fixed,
            "margin": margin,
            "primaryTranscript": transcript,
        }
        intermediate.append(item)
        if fixed and not established:
            contextual_targets.append(proposal)

    contextual_transcripts = _decode_batch(
        recognizer,
        contextual_targets,
        batch_size=stt_batch_size,
        hotwords=hotwords,
    )
    results: list[dict[str, object]] = []
    for index, item in enumerate(intermediate):
        proposal = item["proposal"]
        contextual = contextual_transcripts.get(id(proposal), "")
        lexical = bool(contextual) and has_contextual_wake_evidence(contextual, wake)
        accepted, method = guarded_acceptance(
            established_ctc_accepted=bool(item["established"]),
            fixed_fusion_accepted=bool(item["fixed"]),
            contextual_lexical_evidence=lexical,
        )
        results.append(
            {
                "label": proposal["source"]["label"],
                "sentinelProposed": proposal["hit"] is not None,
                "establishedCtcAccepted": item["established"],
                "fixedFusionAccepted": item["fixed"],
                "fixedFusionDecisionMargin": item["margin"],
                "contextualDecodeExecuted": id(proposal) in contextual_transcripts,
                "contextualLexicalEvidence": lexical,
                "guardedAccepted": accepted,
                "guardMethod": method,
            }
        )
        print(f"BAXY_CONTEXTUAL_FUSION|{index + 1}/{len(intermediate)}", flush=True)

    report: dict[str, object] = {
        "schema": "baxy.contextual-hyperspotter-fusion-development.v4",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_expanded_human_development_policy_selection",
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
            "formula": "established_ctc OR (fixed_fusion_40000_64000 AND wake_only_contextual_lexical_evidence)",
            "sentinelStage1Threshold": SENTINEL_STAGE1_THRESHOLD,
            "fusionViewStartSamples": list(FUSION_VIEW_START_SAMPLES),
            "contextualWakeTerms": list(CONTEXTUAL_WAKE_TERMS),
            "contextualHotwordScore": CONTEXTUAL_HOTWORD_SCORE,
            "expandedPartitionUsedForSelection": True,
            "eligiblePriorNegativeTranscripts": len(eligible_negative_records),
            "priorNegativeContextualBoundariesWithoutHotwords": negative_contextual_boundaries,
            "linearFusionPriorFalseActivations": linear_metrics["negativeFalseActivations"],
        },
        "expandedSentinel": _V3.summarize(results, "sentinelProposed"),
        "expandedEstablishedCtc": _V3.summarize(results, "establishedCtcAccepted"),
        "expandedFixedFusion": _V3.summarize(results, "fixedFusionAccepted"),
        "expandedContextualLexical": _V3.summarize(results, "contextualLexicalEvidence"),
        "expandedGuardedPolicy": _V3.summarize(results, "guardedAccepted"),
        "contextualDecodeCount": len(contextual_transcripts),
        "positiveMinimumFixedFusionMargin": min(
            float(record["fixedFusionDecisionMargin"])
            for record in results
            if record["label"] == "positive"
            and record["fixedFusionDecisionMargin"] is not None
        ),
        "negativeMaximumFixedFusionMargin": max(
            float(record["fixedFusionDecisionMargin"])
            for record in results
            if record["label"] == "matched_negative"
            and record["fixedFusionDecisionMargin"] is not None
        ),
        "runtimeSeconds": time.perf_counter() - started,
        "expandedHumanDevelopmentAudioAccessed": True,
        "blindHumanAudioAccessed": False,
        "audioTranscriptsOrFilenamesRetained": False,
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
    print(json.dumps(report["expandedGuardedPolicy"], sort_keys=True))
    return 0 if report["expandedGuardedPolicy"]["gatePassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
