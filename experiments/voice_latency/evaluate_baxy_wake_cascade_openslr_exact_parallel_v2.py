"""Finish an attested wake-cascade screen with parallel exact CPU rescoring.

This evaluator never repeats or weakens the CUDA screen.  It consumes the
completed, hash-bound v1 screen checkpoint, verifies the unchanged screening
implementation and then distributes independent records across CPU workers.
The production ONNX graphs, route isolation, history windows and thresholds
remain exact.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import sys
import threading
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (ROOT / "src", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from baxy_mind.wake_cascade import (  # noqa: E402
    WINDOW_SAMPLES,
    load_wake_cascade_candidate_config,
    numpy_log_mel_spectrogram,
)


SCHEMA = "baxy.wake-cascade-openslr-negative-regression.v1"
CHECKPOINT_SCHEMA = "baxy.wake-cascade-openslr-exact-parallel-checkpoint.v2"
SCREEN_SCRIPT = HERE / "evaluate_baxy_wake_cascade_openslr_regression_v1.py"


def _load_screen_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "_baxy_wake_openslr_screen_v1_frozen", SCREEN_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("wake_cascade_exact_parallel_screen_component_invalid")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_SCREEN = _load_screen_module()
_THREAD_LOCAL = threading.local()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("wake_cascade_exact_parallel_json_invalid")
    return value


def _write_checkpoint(
    path: Path,
    *,
    identities: dict[str, str],
    completed_records: int,
    exact_proposals: int,
    strong_false: list[str],
    elapsed_seconds: float,
) -> None:
    payload = {
        "schema": CHECKPOINT_SCHEMA,
        "identities": identities,
        "completedRecords": completed_records,
        "exactProposals": exact_proposals,
        "strongFalseAudioSha256": strong_false,
        "elapsedSeconds": elapsed_seconds,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _load_checkpoint(
    path: Path, identities: dict[str, str]
) -> tuple[int, int, list[str], float]:
    if not path.exists():
        return 0, 0, [], 0.0
    payload = _read(path)
    false_hashes = payload.get("strongFalseAudioSha256")
    if (
        payload.get("schema") != CHECKPOINT_SCHEMA
        or payload.get("identities") != identities
        or not isinstance(payload.get("completedRecords"), int)
        or not isinstance(payload.get("exactProposals"), int)
        or not isinstance(false_hashes, list)
        or not all(isinstance(value, str) for value in false_hashes)
        or not isinstance(payload.get("elapsedSeconds"), (int, float))
    ):
        raise ValueError("wake_cascade_exact_parallel_checkpoint_invalid")
    return (
        int(payload["completedRecords"]),
        int(payload["exactProposals"]),
        list(false_hashes),
        float(payload["elapsedSeconds"]),
    )


class _Worker:
    def __init__(self, config: Any) -> None:
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        providers = ["CPUExecutionProvider"]
        self.upstream = tuple(
            ort.InferenceSession(str(path), sess_options=options, providers=providers)
            for path in config.upstream_graph_paths
        )
        self.verifiers = tuple(
            ort.InferenceSession(str(path), sess_options=options, providers=providers)
            for path in config.verifier_graph_paths
        )


def _worker(config: Any) -> _Worker:
    value = getattr(_THREAD_LOCAL, "worker", None)
    if value is None:
        value = _Worker(config)
        _THREAD_LOCAL.worker = value
    return value


def _score_record(
    item: tuple[int, list[int]],
    *,
    records: list[dict[str, Any]],
    corpus_root: Path,
    ffmpeg: Path,
    config: Any,
    mel_filters: np.ndarray,
) -> tuple[bool, bool, str]:
    record_index, indexes = item
    record = records[record_index]
    path = (corpus_root / str(record.get("relative_path") or "")).resolve(
        strict=True
    )
    path.relative_to(corpus_root)
    audio = _SCREEN._AUDIO.decode_flac(ffmpeg, path)
    if len(audio) != int(record.get("frames") or -1):
        raise ValueError("wake_cascade_exact_parallel_audio_length_mismatch")
    streamed = _SCREEN.stream_audio(audio)
    windows = sorted(set(indexes))
    features = [
        numpy_log_mel_spectrogram(
            streamed[
                window_index * config.hop_samples :
                window_index * config.hop_samples + WINDOW_SAMPLES
            ],
            mel_filters,
        )
        for window_index in windows
    ]
    sessions = _worker(config)
    upstream_outputs = [
        np.concatenate(
            [
                session.run(["logits"], {"logmel": feature[None, :, :]})[0]
                for feature in features
            ],
            axis=0,
        )
        for session in sessions.upstream
    ]
    selected = _SCREEN.candidate_routes_by_record(
        upstream_outputs,
        [(0, window_index) for window_index in windows],
        config,
    ).get(0, [])
    audio_hash = str(record.get("sha256") or "")
    if not selected:
        return False, False, audio_hash

    verifier_features: list[np.ndarray] = []
    ranges: list[tuple[int, int, tuple[int, ...]]] = []
    feature_cache = {index: feature for index, feature in zip(windows, features)}
    for window_index, route_indexes in selected:
        start = len(verifier_features)
        history_start = max(0, window_index - config.history_windows + 1)
        for offset in range(history_start, window_index + 1):
            feature = feature_cache.get(offset)
            if feature is None:
                feature = numpy_log_mel_spectrogram(
                    streamed[
                        offset * config.hop_samples :
                        offset * config.hop_samples + WINDOW_SAMPLES
                    ],
                    mel_filters,
                )
                feature_cache[offset] = feature
            verifier_features.append(feature)
        ranges.append((start, len(verifier_features), route_indexes))
    verifier_scores = tuple(
        _SCREEN._batched_session_logits(
            session,
            output_name="wake_logit",
            values=verifier_features,
            batch_size=1,
        )[:, 0]
        for session in sessions.verifiers
    )
    for start, end, route_indexes in ranges:
        for route_index in route_indexes:
            route = config.routes[route_index]
            score = float(np.max(verifier_scores[route.verifier_index][start:end]))
            if score >= route.verifier_threshold:
                return True, True, audio_hash
    return True, False, audio_hash


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    if args.workers < 1 or args.checkpoint_records < 1:
        raise ValueError("wake_cascade_exact_parallel_schedule_invalid")
    output = args.output.resolve()
    if output.exists():
        raise ValueError("wake_cascade_exact_parallel_output_exists")
    candidate = args.cascade_manifest.resolve(strict=True)
    screen_candidate = (
        args.screen_cascade_manifest.resolve(strict=True)
        if args.screen_cascade_manifest is not None
        else candidate
    )
    corpus_manifest = args.corpus_manifest.resolve(strict=True)
    ffmpeg = args.ffmpeg.resolve(strict=True)
    screen_checkpoint = args.screen_checkpoint.resolve(strict=True)
    config = load_wake_cascade_candidate_config(candidate)
    screen_config = load_wake_cascade_candidate_config(screen_candidate)
    if config.lexical_rescue_enabled:
        raise ValueError("wake_cascade_exact_parallel_lexical_rescue_unsupported")
    corpus = _read(corpus_manifest)
    records = corpus.get("records")
    if (
        corpus.get("schema") != "baxy.openslr-librispeech-negative-holdout.v1"
        or corpus.get("blind_human_partition_accessed") is not False
        or not isinstance(records, list)
        or not all(isinstance(record, dict) for record in records)
    ):
        raise ValueError("wake_cascade_exact_parallel_corpus_invalid")
    corpus_root = Path(str(corpus.get("corpus_root") or "")).resolve(strict=True)
    screen = _read(screen_checkpoint)
    identities = screen.get("identities")
    screened = screen.get("screened")
    parity_drifts = screen.get("parityDrifts")
    if (
        screen.get("schema") != _SCREEN.CHECKPOINT_SCHEMA
        or not isinstance(identities, dict)
        or identities.get("cascadeManifestSha256")
        != _SCREEN.sha256(screen_candidate)
        or identities.get("corpusManifestSha256")
        != _SCREEN.sha256(corpus_manifest)
        or identities.get("ffmpegSha256") != _SCREEN.sha256(ffmpeg)
        or identities.get("evaluatorSourceSha256")
        != _SCREEN.sha256(SCREEN_SCRIPT)
        or screen.get("completedRecords") != len(records)
        or not isinstance(screen.get("windows"), int)
        or not isinstance(screened, list)
        or not isinstance(parity_drifts, list)
        or not parity_drifts
        or max(float(value) for value in parity_drifts)
        > _SCREEN.MAXIMUM_PARITY_DRIFT
    ):
        raise ValueError("wake_cascade_exact_parallel_screen_invalid")
    screen_contract = (
        screen_config.upstream_graph_sha256,
        screen_config.mel_filters_sha256,
        screen_config.hop_samples,
        screen_config.primary_threshold,
        screen_config.secondary_threshold,
        screen_config.rescue_alias_index,
        screen_config.rescue_alias_threshold,
    )
    replacement_contract = (
        config.upstream_graph_sha256,
        config.mel_filters_sha256,
        config.hop_samples,
        config.primary_threshold,
        config.secondary_threshold,
        config.rescue_alias_index,
        config.rescue_alias_threshold,
    )
    if screen_contract != replacement_contract:
        raise ValueError("wake_cascade_exact_parallel_screen_contract_mismatch")
    by_record: dict[int, list[int]] = defaultdict(list)
    for locator in screened:
        if not isinstance(locator, dict):
            raise ValueError("wake_cascade_exact_parallel_screen_invalid")
        record_index = locator.get("record")
        window_index = locator.get("window")
        if (
            not isinstance(record_index, int)
            or not isinstance(window_index, int)
            or not 0 <= record_index < len(records)
            or window_index < 0
        ):
            raise ValueError("wake_cascade_exact_parallel_screen_invalid")
        by_record[record_index].append(window_index)
    items = sorted(by_record.items())
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".exact-parallel.partial.json")
    run_identities = {
        "screenCheckpointSha256": _SCREEN.sha256(screen_checkpoint),
        "screenCascadeManifestSha256": _SCREEN.sha256(screen_candidate),
        "cascadeManifestSha256": _SCREEN.sha256(candidate),
        "corpusManifestSha256": _SCREEN.sha256(corpus_manifest),
        "ffmpegSha256": _SCREEN.sha256(ffmpeg),
        "screenEvaluatorSourceSha256": _SCREEN.sha256(SCREEN_SCRIPT),
        "exactEvaluatorSourceSha256": _SCREEN.sha256(Path(__file__).resolve()),
        "workers": str(args.workers),
    }
    completed, exact_proposals, strong_false, prior_seconds = _load_checkpoint(
        partial, run_identities
    )
    if not 0 <= completed <= len(items):
        raise ValueError("wake_cascade_exact_parallel_checkpoint_invalid")
    mel_filters = np.load(config.mel_filters_path, allow_pickle=False).astype(
        np.float32
    )
    started = time.perf_counter()

    def score(item: tuple[int, list[int]]) -> tuple[bool, bool, str]:
        return _score_record(
            item,
            records=records,
            corpus_root=corpus_root,
            ffmpeg=ffmpeg,
            config=config,
            mel_filters=mel_filters,
        )

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for proposal, false_activation, audio_hash in executor.map(
            score, items[completed:]
        ):
            exact_proposals += int(proposal)
            if false_activation:
                strong_false.append(audio_hash)
            completed += 1
            if completed % args.checkpoint_records == 0 or completed == len(items):
                elapsed = prior_seconds + time.perf_counter() - started
                _write_checkpoint(
                    partial,
                    identities=run_identities,
                    completed_records=completed,
                    exact_proposals=exact_proposals,
                    strong_false=strong_false,
                    elapsed_seconds=elapsed,
                )
                print(
                    f"BAXY_WAKE_CASCADE_EXACT_PARALLEL|{completed}/{len(items)}|"
                    f"proposals={exact_proposals}|strong={len(set(strong_false))}",
                    flush=True,
                )
    exact_seconds = prior_seconds + time.perf_counter() - started
    false_hashes = sorted(set(strong_false))
    exposure_hours = float(corpus["metrics"]["audio_hours"])
    far_upper = -math.log(0.05) / exposure_hours if not false_hashes else None
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "previously_opened_100h_negative_development_regression",
        "sources": {
            **identities,
            "cascadeManifestSha256": _SCREEN.sha256(candidate),
            "screenCheckpointSha256": _SCREEN.sha256(screen_checkpoint),
            "screenCascadeManifestSha256": _SCREEN.sha256(screen_candidate),
            "screenEvaluatorSourceSha256": _SCREEN.sha256(SCREEN_SCRIPT),
            "exactEvaluatorSourceSha256": _SCREEN.sha256(Path(__file__).resolve()),
        },
        "contract": {
            "gpuScreenMargin": _SCREEN.SCREEN_MARGIN,
            "maximumObservedGpuToCpuLogitDrift": max(
                float(value) for value in parity_drifts
            ),
            "minimumScreenSafetyMultiplier": _SCREEN.SCREEN_MARGIN
            / max(float(value) for value in parity_drifts),
            "requiredScreenSafetyMultiplier": (
                _SCREEN.MINIMUM_PARITY_SAFETY_MULTIPLIER
            ),
            "gpuMatmulPrecision": "high_tf32_allowed",
            "everyBroadCandidateRescoredByExactCpuOnnx": True,
            "parallelExactWorkers": args.workers,
            "lexicalRescueEnabled": False,
            "lexicalRescueUsesProductParakeet": False,
            "freshHoldoutClaimSupported": False,
            "promotionSupported": False,
        },
        "metrics": {
            "utterances": len(records),
            "descriptiveExposureHours": exposure_hours,
            "windowsScored": int(screen["windows"]),
            "broadScreenWindows": len(screened),
            "broadScreenRecords": len(items),
            "exactUpstreamProposals": exact_proposals,
            "strongFalseActivations": len(false_hashes),
            "lexicalInvocations": 0,
            "lexicalFalseActivations": 0,
            "negativeFalseActivations": len(false_hashes),
            "pointFalseActivationsPerHour": len(false_hashes) / exposure_hours,
            "far95UpperConfidencePerHourIfZero": far_upper,
        },
        "runtime": {
            "screenSeconds": float(screen["elapsedSeconds"]),
            "exactRescoreSeconds": exact_seconds,
            "exactWorkers": args.workers,
        },
        "falseActivationAudioSha256": false_hashes,
        "regressionPassed": not false_hashes,
        "candidateDevelopmentUse": True,
        "candidateFrozen": True,
        "negativeCorpusPreviouslyAccessed": True,
        "blindHumanAudioAccessed": False,
        "transcriptsOrFilenamesRetained": False,
        "effectsExecuted": 0,
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.unlink(missing_ok=True)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen-checkpoint", type=Path, required=True)
    parser.add_argument("--cascade-manifest", type=Path, required=True)
    parser.add_argument("--screen-cascade-manifest", type=Path)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--checkpoint-records", type=int, default=128)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    report = evaluate(parse_args())
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
