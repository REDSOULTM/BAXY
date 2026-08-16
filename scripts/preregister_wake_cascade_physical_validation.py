"""Freeze the exact candidate, corpus selection, and programs for a wake gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
VOICE_EXPERIMENTS = ROOT / "experiments" / "voice_latency"
for path in (ROOT / "src", ROOT / "scripts", VOICE_EXPERIMENTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import capture_controlled_physical_wake_corpus_v1 as capture  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind.wake_cascade import (  # noqa: E402
    load_wake_cascade_candidate_config,
)
from wake_validation_program_tree import fingerprint_program_tree  # noqa: E402


SCHEMA = "baxy.wake-cascade-physical-validation-preregistration.v2"
CAPTURE_SCRIPT = VOICE_EXPERIMENTS / "capture_controlled_physical_wake_corpus_v1.py"
EVALUATOR_SCRIPT = VOICE_EXPERIMENTS / "evaluate_baxy_wake_cascade_runtime_raw_v1.py"
ENDPOINT_EVALUATOR_SCRIPT = (
    VOICE_EXPERIMENTS / "evaluate_baxy_endpoint_voice_runtime_v1.py"
)
FUSION_SCRIPT = VOICE_EXPERIMENTS / "fuse_baxy_cascade_endpoint_reports_v1.py"
STT_FILES = ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt")
PROGRAM_SOURCE_ROOTS = (ROOT / "src" / "baxy_mind", ROOT / "scripts", VOICE_EXPERIMENTS)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--negative", type=Path, required=True)
    parser.add_argument("--positive-limit", type=int, default=48)
    parser.add_argument("--negative-limit", type=int, default=96)
    parser.add_argument("--seed", type=int, default=20260808)
    parser.add_argument("--maximum-source-seconds", type=float, default=20.0)
    parser.add_argument("--gain", type=float, default=0.65)
    parser.add_argument("--pre-roll-seconds", type=float, default=0.25)
    parser.add_argument("--post-roll-seconds", type=float, default=0.5)
    parser.add_argument("--minimum-path-correlation", type=float, default=0.10)
    parser.add_argument("--minimum-captured-snr-db", type=float, default=3.0)
    parser.add_argument("--maximum-capture-attempts", type=int, default=6)
    parser.add_argument("--raw-capture-helper", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _candidate_assets(config: object, manifest_sha256: str) -> dict[str, object]:
    verifier_hashes = tuple(config.verifier_graph_sha256s)
    return {
        "manifestSha256": manifest_sha256,
        "upstreamGraphSha256": list(config.upstream_graph_sha256),
        "melFiltersSha256": config.mel_filters_sha256,
        "logmelVerifierSha256": (
            list(verifier_hashes)
            if len(verifier_hashes) > 1
            else config.verifier_graph_sha256
        ),
    }


def main() -> int:
    args = _parser().parse_args()
    if (
        args.positive_limit < 48
        or args.negative_limit < 96
        or not 0.01 <= args.gain <= 0.95
        or args.maximum_source_seconds <= 0
        or args.maximum_capture_attempts < 1
    ):
        raise SystemExit("Preregistration parameters do not meet the product gate.")
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Preregistration output already exists.")
    candidate = args.candidate_manifest.resolve(strict=True)
    positive_root = args.positive.resolve(strict=True)
    negative_root = args.negative.resolve(strict=True)
    helper = args.raw_capture_helper.resolve(strict=True)
    stt = args.stt_directory.resolve(strict=True)
    config = load_wake_cascade_candidate_config(candidate)
    hybrid_endpoint = bool(
        config.endpoint_lexical_verifier_index is not None
        and config.endpoint_lexical_score_threshold is not None
    )
    positives = capture.select_sources(
        positive_root,
        args.positive_limit,
        args.seed,
        maximum_source_seconds=args.maximum_source_seconds,
    )
    negatives = capture.select_sources(
        negative_root,
        args.negative_limit,
        args.seed + 1,
        maximum_source_seconds=args.maximum_source_seconds,
    )
    stt_hashes = {}
    for name in STT_FILES:
        stt_hashes[name] = _sha((stt / name).resolve(strict=True))
    payload = {
        "schema": SCHEMA,
        "createdAtUtc": datetime.now(timezone.utc).isoformat(),
        "role": "validation",
        "candidateFrozen": True,
        "corpusSelectionFrozen": True,
        "candidate": _candidate_assets(config, _sha(candidate)),
        "sourceSelection": {
            "seed": args.seed,
            "positiveFiles": len(positives),
            "negativeFiles": len(negatives),
            "positiveRootSha256": room._corpus_sha256(positives, positive_root),
            "negativeRootSha256": room._corpus_sha256(negatives, negative_root),
        },
        "captureContract": {
            "captureTransport": "wasapi_raw_iaudioclient2",
            "rawCaptureHelperSha256": _sha(helper),
            "playbackGain": args.gain,
            "preRollSecondsNotRetained": args.pre_roll_seconds,
            "postRollSecondsNotRetained": args.post_roll_seconds,
            "maximumSourceSeconds": args.maximum_source_seconds,
            "maximumCaptureAttempts": args.maximum_capture_attempts,
            "minimumPathCorrelation": args.minimum_path_correlation,
            "minimumCapturedSnrDb": args.minimum_captured_snr_db,
        },
        "evaluationContract": {
            "blockSamples": 512,
            "verificationPolicy": (
                "cascade_or_score_gated_endpoint" if hybrid_endpoint else "cascade"
            ),
            "captureScriptSha256": _sha(CAPTURE_SCRIPT),
            "evaluatorScriptSha256": _sha(EVALUATOR_SCRIPT),
            **(
                {
                    "endpointEvaluatorScriptSha256": _sha(ENDPOINT_EVALUATOR_SCRIPT),
                    "fusionScriptSha256": _sha(FUSION_SCRIPT),
                    "endpointDirectScoreGte": (config.endpoint_lexical_score_threshold),
                    "endpointAliases": sorted(config.endpoint_lexical_aliases),
                }
                if hybrid_endpoint
                else {}
            ),
            "sttFilesSha256": stt_hashes,
            "programTree": fingerprint_program_tree(
                repository_root=ROOT,
                source_roots=PROGRAM_SOURCE_ROOTS,
            ),
        },
        "blindHumanPartitionAccessed": False,
        "effectsExecuted": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as sink:
        json.dump(payload, sink, ensure_ascii=False, indent=2)
        sink.write("\n")
    print(
        json.dumps(
            {
                "preregistered": True,
                "candidateManifestSha256": payload["candidate"]["manifestSha256"],
                "positiveFiles": len(positives),
                "negativeFiles": len(negatives),
                "outputSha256": _sha(output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
