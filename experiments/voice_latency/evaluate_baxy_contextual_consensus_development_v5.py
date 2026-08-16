"""Compare bounded contextual-consensus policies on opened human development data.

This experiment is intentionally restricted to the already-opened development
partition.  It compares independent full-capture and fixed-view ASR evidence
without retaining filenames or transcripts.  It is policy-selection evidence,
not a product operating point or a fresh holdout claim.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Callable

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_contextual_consensus_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V4 = load_component(
    "evaluate_baxy_contextual_fusion_development_v4.py",
    "_baxy_contextual_consensus_v4",
)
_PRODUCT = _V4._PRODUCT
_HOLDOUT = _V4._HOLDOUT
_SCAN = _V4._SCAN
_V3 = _V4._V3


def consensus_policy_signals(
    *,
    full_plain: bool,
    full_hot: bool,
    acoustic_by_view: dict[int, bool],
    plain_by_view: dict[int, bool],
    hot_by_view: dict[int, bool],
) -> dict[str, bool]:
    """Return preregisterable confirmations from independent ASR scopes."""

    starts = tuple(_V4.FUSION_VIEW_START_SAMPLES)
    same_view_hot = any(
        acoustic_by_view.get(start, False) and hot_by_view.get(start, False)
        for start in starts
    )
    same_view_dual = any(
        acoustic_by_view.get(start, False)
        and hot_by_view.get(start, False)
        and plain_by_view.get(start, False)
        for start in starts
    )
    hot_view_count = sum(bool(hot_by_view.get(start, False)) for start in starts)
    return {
        "currentFullHot": full_hot,
        "fullDualDecode": full_hot and full_plain,
        "sameViewHot": same_view_hot,
        "fullAndSameViewHot": full_hot and same_view_hot,
        "sameViewDualDecode": same_view_dual,
        "twoViewHotConsensus": hot_view_count == len(starts),
    }


def _fixed_view_evidence(
    *,
    capture: np.ndarray,
    config: object,
    verifier: object,
    hyper_session: object,
    candidate: dict[str, object],
    wake: object,
) -> tuple[dict[int, np.ndarray], dict[int, float], dict[int, np.ndarray]]:
    views: dict[int, np.ndarray] = {}
    margins: dict[int, float] = {}
    probabilities_by_view: dict[int, np.ndarray] = {}
    policy = candidate["policy"]
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
        combined = float(np.max(hyper_logits)) + float(policy["ctc_weight"]) * (
            (ctc_margin - float(policy["ctc_center"]))
            / float(policy["ctc_scale"])
        )
        views[start] = values
        margins[start] = combined - float(policy["decision_threshold"])
        probabilities_by_view[start] = probabilities
    return views, margins, probabilities_by_view


def _guarded(established: bool, fixed: bool, contextual: bool) -> bool:
    return established or (fixed and contextual)


def evaluate(
    *,
    expanded_corpus_manifest_path: Path,
    stage1_model_path: Path,
    ctc_manifest_path: Path,
    fusion_manifest_path: Path,
    stt_directory: Path,
    ffmpeg_path: Path,
    prior_contextual_development_path: Path,
    failed_negative_regression_path: Path,
    output_path: Path,
    stt_batch_size: int,
    plain_evidence_predicate: Callable[[str, object], bool] | None = None,
    hot_evidence_predicate: Callable[[str, object], bool] | None = None,
    fixed_view_observer: Callable[
        [dict[int, float], dict[int, np.ndarray], object], object
    ]
    | None = None,
    fixed_view_audio_observer: Callable[
        [
            dict[int, np.ndarray],
            dict[int, float],
            dict[int, np.ndarray],
            object,
            dict[str, object],
        ],
        object,
    ]
    | None = None,
    additional_policy_factory: Callable[..., dict[str, bool]] | None = None,
    contextual_hotword_score: float | None = None,
    decode_observer: Callable[[str, list[dict[str, object]], dict[int, str]], None]
    | None = None,
) -> dict[str, object]:
    if (
        output_path.exists()
        or stt_batch_size < 1
        or (fixed_view_observer is not None and fixed_view_audio_observer is not None)
    ):
        raise ValueError("baxy_contextual_consensus_schedule_invalid")
    paths = [
        expanded_corpus_manifest_path,
        stage1_model_path,
        ctc_manifest_path,
        fusion_manifest_path,
        stt_directory,
        ffmpeg_path,
        prior_contextual_development_path,
        failed_negative_regression_path,
    ]
    (
        expanded_corpus_manifest_path,
        stage1_model_path,
        ctc_manifest_path,
        fusion_manifest_path,
        stt_directory,
        ffmpeg_path,
        prior_contextual_development_path,
        failed_negative_regression_path,
    ) = [path.resolve(strict=True) for path in paths]
    output_path = output_path.resolve()

    expanded = _PRODUCT.read_object(expanded_corpus_manifest_path)
    prior_development = _PRODUCT.read_object(prior_contextual_development_path)
    failed_regression = _PRODUCT.read_object(failed_negative_regression_path)
    if (
        expanded.get("schema") != "baxy.ccby-wake-v5-development-corpus.v1"
        or expanded.get("blind_human_audio_accessed") is not False
        or prior_development.get("schema")
        != "baxy.contextual-hyperspotter-fusion-development.v4"
        or prior_development.get("expandedGuardedPolicy", {}).get("gatePassed")
        is not True
        or failed_regression.get("schema")
        != "baxy.contextual-hyperspotter-fusion-negative-regression.v2"
        or failed_regression.get("regressionPassed") is not False
        or failed_regression.get("metrics", {}).get(
            "guardedNegativeFalseActivations"
        )
        != 1
    ):
        raise ValueError("baxy_contextual_consensus_evidence_invalid")

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
        raise ValueError("baxy_contextual_consensus_records_invalid")

    candidate = _PRODUCT.load_fusion_candidate(
        fusion_manifest_path, ctc_manifest_path
    )
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root / "src") not in sys.path:
        sys.path.insert(0, str(repo_root / "src"))
    from baxy_mind import wake_verifier as wake
    from baxy_mind.voice import SileroVad, _compile_contextual_hotwords
    import onnxruntime as ort
    import sherpa_onnx

    plain_evidence_predicate = (
        plain_evidence_predicate or _V4.has_contextual_wake_evidence
    )
    hot_evidence_predicate = (
        hot_evidence_predicate or _V4.has_contextual_wake_evidence
    )
    contextual_hotword_score = (
        _V4.CONTEXTUAL_HOTWORD_SCORE
        if contextual_hotword_score is None
        else float(contextual_hotword_score)
    )
    if not np.isfinite(contextual_hotword_score):
        raise ValueError("baxy_contextual_consensus_hotword_score_invalid")

    config = wake.load_wake_verifier_candidate_config(ctc_manifest_path)
    if _PRODUCT.sha256(stage1_model_path) != config.stage1_model_sha256:
        raise ValueError("baxy_contextual_consensus_stage1_mismatch")
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
        hotwords_score=contextual_hotword_score,
    )
    hotwords = _compile_contextual_hotwords(
        stt_directory / "tokens.txt", _V4.CONTEXTUAL_WAKE_TERMS
    )
    if not hotwords:
        raise ValueError("baxy_contextual_consensus_hotwords_invalid")
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
            raise ValueError("baxy_contextual_consensus_audio_hash_mismatch")
        audio = _HOLDOUT.decode_flac(ffmpeg_path, path)
        scan = _SCAN.streaming_scores(
            stage1,
            audio,
            retention_threshold=_V4.SENTINEL_STAGE1_THRESHOLD,
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
                "label": source["label"],
                "hit": hit,
                "capture": capture,
                "verificationStart": verification_start,
            }
        )

    selected = [proposal for proposal in proposals if proposal["hit"] is not None]
    full_plain = _V4._decode_batch(
        recognizer, selected, batch_size=stt_batch_size
    )
    if decode_observer is not None:
        decode_observer("full_plain", selected, full_plain)
    prepared: list[dict[str, object]] = []
    contextual_targets: list[dict[str, object]] = []
    view_targets: list[dict[str, object]] = []
    for proposal in proposals:
        if proposal["hit"] is None:
            established = False
            views: dict[int, np.ndarray] = {}
            margins: dict[int, float] = {}
            probabilities_by_view: dict[int, np.ndarray] = {}
            plain_evidence = False
        else:
            transcript = full_plain[id(proposal)]
            established = verifier.verify(
                proposal["capture"],
                transcript,
                float(proposal["hit"]["score"]),
                verification_start_sample=int(proposal["verificationStart"]),
            ).accepted
            plain_evidence = plain_evidence_predicate(transcript, wake)
            views, margins, probabilities_by_view = _fixed_view_evidence(
                capture=proposal["capture"],
                config=config,
                verifier=verifier,
                hyper_session=hyper_session,
                candidate=candidate,
                wake=wake,
            )
        fixed = any(margin >= 0.0 for margin in margins.values())
        if fixed_view_audio_observer is not None:
            fixed_view_observation = fixed_view_audio_observer(
                views,
                margins,
                probabilities_by_view,
                wake,
                {
                    "label": proposal["label"],
                    "established": established,
                    "fixed": fixed,
                },
            )
        elif fixed_view_observer is not None:
            fixed_view_observation = fixed_view_observer(
                margins, probabilities_by_view, wake
            )
        else:
            fixed_view_observation = None
        item = {
            "proposal": proposal,
            "established": established,
            "fixed": fixed,
            "margins": margins,
            "fullPlainEvidence": plain_evidence,
            "fixedViewObservation": fixed_view_observation,
            "viewProposals": {},
        }
        prepared.append(item)
        if fixed and not established:
            contextual_targets.append(proposal)
            for start, values in views.items():
                view_proposal = {
                    "capture": values,
                    "label": proposal["label"],
                    "viewStartSample": start,
                }
                item["viewProposals"][start] = view_proposal
                view_targets.append(view_proposal)

    full_hot = _V4._decode_batch(
        recognizer,
        contextual_targets,
        batch_size=stt_batch_size,
        hotwords=hotwords,
    )
    if decode_observer is not None:
        decode_observer("full_hot", contextual_targets, full_hot)
    view_plain = _V4._decode_batch(
        recognizer, view_targets, batch_size=stt_batch_size
    )
    if decode_observer is not None:
        decode_observer("view_plain", view_targets, view_plain)
    view_hot = _V4._decode_batch(
        recognizer,
        view_targets,
        batch_size=stt_batch_size,
        hotwords=hotwords,
    )
    if decode_observer is not None:
        decode_observer("view_hot", view_targets, view_hot)

    policy_names = tuple(
        consensus_policy_signals(
            full_plain=False,
            full_hot=False,
            acoustic_by_view={},
            plain_by_view={},
            hot_by_view={},
        )
    )
    if additional_policy_factory is not None:
        additional_names = tuple(
            additional_policy_factory(
                established=False,
                fixed=False,
                full_hot=False,
                observation=None,
                base_signals={},
            )
        )
        if set(policy_names).intersection(additional_names):
            raise ValueError("baxy_contextual_consensus_policy_name_collision")
        policy_names += additional_names
    results: list[dict[str, object]] = []
    for item in prepared:
        proposal = item["proposal"]
        full_hot_text = full_hot.get(id(proposal), "")
        acoustic_by_view = {
            int(start): float(margin) >= 0.0
            for start, margin in item["margins"].items()
        }
        plain_by_view = {
            int(start): plain_evidence_predicate(
                view_plain.get(id(view_proposal), ""), wake
            )
            for start, view_proposal in item["viewProposals"].items()
        }
        hot_by_view = {
            int(start): hot_evidence_predicate(
                view_hot.get(id(view_proposal), ""), wake
            )
            for start, view_proposal in item["viewProposals"].items()
        }
        signals = consensus_policy_signals(
            full_plain=bool(item["fullPlainEvidence"]),
            full_hot=hot_evidence_predicate(full_hot_text, wake),
            acoustic_by_view=acoustic_by_view,
            plain_by_view=plain_by_view,
            hot_by_view=hot_by_view,
        )
        if additional_policy_factory is not None:
            signals.update(
                additional_policy_factory(
                    established=bool(item["established"]),
                    fixed=bool(item["fixed"]),
                    full_hot=hot_evidence_predicate(full_hot_text, wake),
                    observation=item["fixedViewObservation"],
                    base_signals=signals,
                )
            )
        record: dict[str, object] = {
            "label": proposal["label"],
            "sentinelProposed": proposal["hit"] is not None,
            "establishedCtcAccepted": bool(item["established"]),
            "fixedFusionAccepted": bool(item["fixed"]),
        }
        for name, signal in signals.items():
            record[name] = _guarded(
                bool(item["established"]), bool(item["fixed"]), signal
            )
        results.append(record)

    summaries = {name: _V3.summarize(results, name) for name in policy_names}
    eligible = [
        name
        for name, summary in summaries.items()
        if summary["positiveHits"] == 4 and summary["falseHits"] == 0
    ]
    report: dict[str, object] = {
        "schema": "baxy.contextual-consensus-development.v5",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_human_development_contextual_consensus_selection",
        "sources": {
            "expandedCorpusManifestSha256": _PRODUCT.sha256(
                expanded_corpus_manifest_path
            ),
            "stage1ModelSha256": _PRODUCT.sha256(stage1_model_path),
            "ctcVerifierManifestSha256": _PRODUCT.sha256(ctc_manifest_path),
            "fusionManifestSha256": _PRODUCT.sha256(fusion_manifest_path),
            "priorContextualDevelopmentSha256": _PRODUCT.sha256(
                prior_contextual_development_path
            ),
            "failedNegativeRegressionSha256": _PRODUCT.sha256(
                failed_negative_regression_path
            ),
            "ffmpegSha256": _PRODUCT.sha256(ffmpeg_path),
        },
        "policy": {
            "sentinelStage1Threshold": _V4.SENTINEL_STAGE1_THRESHOLD,
            "fusionViewStartSamples": list(_V4.FUSION_VIEW_START_SAMPLES),
            "contextualWakeTerms": list(_V4.CONTEXTUAL_WAKE_TERMS),
            "contextualHotwordScore": contextual_hotword_score,
            "failedRegressionUsedForAggregateSelection": True,
        },
        "policySummaries": summaries,
        "developmentEligiblePolicies": eligible,
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
    parser.add_argument("--prior-contextual-development", type=Path, required=True)
    parser.add_argument("--failed-negative-regression", type=Path, required=True)
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
        prior_contextual_development_path=arguments.prior_contextual_development,
        failed_negative_regression_path=arguments.failed_negative_regression,
        output_path=arguments.output,
        stt_batch_size=arguments.stt_batch_size,
    )
    print(json.dumps(report["policySummaries"], sort_keys=True))
    return 0 if report["developmentEligiblePolicies"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
