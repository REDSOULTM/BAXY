"""Evaluate the production wake cascade with its exact 512-sample stream API."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (ROOT / "src", ROOT / "scripts", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import evaluate_raw_lexical_fusion_wake_corpus_v1 as summaries  # noqa: E402
import run_lexical_wake_physical_room_gate_v1 as lexical  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind.wake_cascade import (  # noqa: E402
    HyperspotterCascadeDetector,
    has_strict_leading_alias,
    load_wake_cascade_candidate_config,
    match_bounded_lexical_wake,
    time_scaled_recognition_audio,
)
from wake_validation_program_tree import fingerprint_program_tree  # noqa: E402


SCHEMA = "baxy.wake-cascade-runtime-raw-development.v1"
PREREGISTRATION_SCHEMA = (
    "baxy.wake-cascade-physical-validation-preregistration.v2"
)
SAMPLE_RATE = 16_000
MINIMUM_RIGHT_CONTEXT_SECONDS = 1.25
CAPTURE_SCRIPT = HERE / "capture_controlled_physical_wake_corpus_v1.py"
STT_FILES = ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt")
PROGRAM_SOURCE_ROOTS = (ROOT / "src" / "baxy_mind", ROOT / "scripts", HERE)


def _read_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError("baxy_wake_cascade_preregistration_invalid") from error
    if not isinstance(value, dict):
        raise ValueError("baxy_wake_cascade_preregistration_invalid")
    return value


def _validate_preregistration(
    preregistration: Path,
    *,
    cascade_manifest: Path,
    config: object,
    corpus_source: dict[str, object],
    stt_directory: Path,
    block_samples: int,
    verification_policy: str,
) -> str:
    payload = _read_object(preregistration)
    candidate = payload.get("candidate")
    selection = payload.get("sourceSelection")
    capture_contract = payload.get("captureContract")
    evaluation = payload.get("evaluationContract")
    sources = corpus_source.get("sources")
    counts = corpus_source.get("counts")
    physical = corpus_source.get("physicalPath")
    if not all(
        isinstance(value, dict)
        for value in (candidate, selection, capture_contract, evaluation, sources, counts, physical)
    ):
        raise ValueError("baxy_wake_cascade_preregistration_invalid")
    assert isinstance(candidate, dict)
    assert isinstance(selection, dict)
    assert isinstance(capture_contract, dict)
    assert isinstance(evaluation, dict)
    assert isinstance(sources, dict)
    assert isinstance(counts, dict)
    assert isinstance(physical, dict)
    expected_assets = {
        "manifestSha256": room._sha256(cascade_manifest),
        "upstreamGraphSha256": list(config.upstream_graph_sha256),
        "melFiltersSha256": config.mel_filters_sha256,
        "logmelVerifierSha256": (
            list(getattr(config, "verifier_graph_sha256s", ()))
            if len(getattr(config, "verifier_graph_sha256s", ())) > 1
            else config.verifier_graph_sha256
        ),
    }
    stt_hashes = evaluation.get("sttFilesSha256")
    program_tree = evaluation.get("programTree")
    if not isinstance(stt_hashes, dict) or not isinstance(program_tree, dict):
        raise ValueError("baxy_wake_cascade_preregistration_invalid")
    actual_stt = {
        name: room._sha256((stt_directory / name).resolve(strict=True))
        for name in STT_FILES
    }
    if (
        payload.get("schema") != PREREGISTRATION_SCHEMA
        or payload.get("role") != "validation"
        or payload.get("candidateFrozen") is not True
        or payload.get("corpusSelectionFrozen") is not True
        or payload.get("blindHumanPartitionAccessed") is not False
        or payload.get("effectsExecuted") != 0
        or any(candidate.get(name) != value for name, value in expected_assets.items())
        or selection.get("seed") != corpus_source.get("seed")
        or selection.get("positiveFiles") != counts.get("positive")
        or selection.get("negativeFiles") != counts.get("negative")
        or selection.get("positiveRootSha256") != sources.get("positiveRootSha256")
        or selection.get("negativeRootSha256") != sources.get("negativeRootSha256")
        or any(
            capture_contract.get(name) != physical.get(name)
            for name in (
                "captureTransport",
                "rawCaptureHelperSha256",
                "playbackGain",
                "preRollSecondsNotRetained",
                "postRollSecondsNotRetained",
                "maximumSourceSeconds",
                "maximumCaptureAttempts",
                "minimumPathCorrelation",
                "minimumCapturedSnrDb",
            )
        )
        or evaluation.get("blockSamples") != block_samples
        or evaluation.get("verificationPolicy") != verification_policy
        or evaluation.get("captureScriptSha256") != room._sha256(CAPTURE_SCRIPT)
        or evaluation.get("evaluatorScriptSha256") != room._sha256(Path(__file__))
        or stt_hashes != actual_stt
        or program_tree
        != fingerprint_program_tree(
            repository_root=ROOT,
            source_roots=PROGRAM_SOURCE_ROOTS,
        )
    ):
        raise ValueError("baxy_wake_cascade_preregistration_mismatch")
    return room._sha256(preregistration)


def stream_audio(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError("baxy_wake_cascade_runtime_audio_invalid")
    left = SAMPLE_RATE
    minimum_right = round(MINIMUM_RIGHT_CONTEXT_SECONDS * SAMPLE_RATE)
    right = max(minimum_right, 48_000 - left - len(values))
    return np.pad(values, (left, right))


def _evaluate_group(
    paths: list[Path], *, detector: HyperspotterCascadeDetector,
    recognizer: object | None, block_samples: int, verification_policy: str,
    contextual_hotwords: str = "",
) -> dict[str, object]:
    if verification_policy not in {"cascade", "lexical_all"}:
        raise ValueError("baxy_wake_cascade_verification_policy_invalid")
    records: list[dict[str, object]] = []
    latencies: list[float] = []
    for index, path in enumerate(paths):
        audio, sample_rate = room._read_pcm16(path)
        audio = room._resample(audio, sample_rate, SAMPLE_RATE)
        streamed = stream_audio(audio)
        detector.reset()
        hit = None
        consumed = 0
        started = time.perf_counter()
        for start in range(0, len(streamed), block_samples):
            block = streamed[start : start + block_samples]
            consumed += len(block)
            hit = detector.accept(block, now=10.0)
            if hit is not None:
                break
        transcript_hash = None
        transcript_attempt_hashes: list[str] = []
        lexical_accepted = False
        accepted = False
        reason = "no_upstream_candidate"
        lexical_required = hit is not None and (
            verification_policy == "lexical_all" or hit.lexical_rescue_required
        )
        if hit is not None and not lexical_required:
            accepted = True
            reason = "logmel_verifier"
        elif lexical_required:
            if recognizer is None:
                raise ValueError("baxy_wake_cascade_lexical_recognizer_missing")
            if hit is not None and hit.method == "direct_lexical_proposal":
                lexical_match = None
                views = (
                    (1.0, audio),
                    *(
                        (factor, time_scaled_recognition_audio(audio, factor))
                        for factor in (
                            detector.config.direct_lexical_retry_speed_factors
                        )
                    ),
                )
                for _factor, view in views:
                    transcript, _ = lexical._decode(
                        recognizer,
                        view,
                        hotwords=contextual_hotwords,
                    )
                    transcript_attempt_hashes.append(
                        hashlib.sha256(transcript.encode("utf-8")).hexdigest()
                    )
                    lexical_match = match_bounded_lexical_wake(
                        (transcript,),
                        detector.config.lexical_aliases,
                        verifier_score=hit.verifier_score,
                        phonetic_confusion_score_gte=(
                            detector.config.direct_lexical_phonetic_confusion_score_gte
                        ),
                    )
                    if lexical_match is not None:
                        transcript_hash = transcript_attempt_hashes[-1]
                        break
                lexical_accepted = lexical_match is not None
            else:
                transcript, _ = lexical._decode(recognizer, audio)
                transcript_hash = hashlib.sha256(
                    transcript.encode("utf-8")
                ).hexdigest()
                transcript_attempt_hashes.append(transcript_hash)
                lexical_accepted = has_strict_leading_alias(
                    transcript, detector.config.lexical_aliases
                )
            accepted = lexical_accepted
            reason = (
                (
                    "bounded_direct_lexical_verifier"
                    if hit is not None and hit.method == "direct_lexical_proposal"
                    else "strict_leading_lexical_verifier"
                    if verification_policy == "lexical_all"
                    else "strict_leading_lexical_rescue"
                )
                if accepted
                else "candidate_rejected"
            )
        latencies.append(time.perf_counter() - started)
        records.append(
            {
                "record": index,
                "audioSha256": room._sha256(path),
                "upstreamCandidate": hit is not None,
                "candidateAvailableAtStreamSeconds": (
                    consumed / SAMPLE_RATE if hit is not None else None
                ),
                "logmelVerifierScore": (
                    hit.verifier_score if hit is not None else None
                ),
                "lexicalVerifierInvoked": bool(
                    lexical_required
                ),
                "lexicalTranscriptSha256": transcript_hash,
                "lexicalAttemptTranscriptSha256": transcript_attempt_hashes,
                "lexicalAccepted": lexical_accepted,
                "accepted": accepted,
                "reason": reason,
            }
        )
    return {
        "files": len(paths),
        "upstreamCandidateFiles": sum(
            bool(record["upstreamCandidate"]) for record in records
        ),
        "logmelAcceptedFiles": sum(
            record["reason"] == "logmel_verifier" for record in records
        ),
        "lexicalInvocations": sum(
            bool(record["lexicalVerifierInvoked"]) for record in records
        ),
        "lexicalAcceptedFiles": sum(
            bool(record["lexicalAccepted"]) for record in records
        ),
        "acceptedFiles": sum(bool(record["accepted"]) for record in records),
        "runtimeSeconds": summaries._summary(latencies),
        "records": records,
        "transcriptTextRetained": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cascade-manifest", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--block-samples", type=int, default=512)
    parser.add_argument(
        "--verification-policy",
        choices=("cascade", "lexical_all"),
        default="cascade",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--role", choices=("development", "validation"), required=True)
    parser.add_argument("--preregistration", type=Path)
    args = parser.parse_args()
    if not 64 <= args.block_samples <= 4_000:
        raise SystemExit("Block samples must be between 64 and 4000.")
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists.")
    corpus = args.corpus.resolve(strict=True)
    corpus_manifest = (corpus / "manifest.v1.json").resolve(strict=True)
    source = json.loads(corpus_manifest.read_text(encoding="utf-8"))
    if (
        source.get("blindHumanPartitionAccessed") is not False
        or source.get("physicalPath", {}).get("captureTransport")
        != "wasapi_raw_iaudioclient2"
    ):
        raise SystemExit("Corpus is not an opened attested WASAPI RAW capture.")
    cascade_manifest = args.cascade_manifest.resolve(strict=True)
    config = load_wake_cascade_candidate_config(cascade_manifest)
    stt_directory = args.stt_directory.resolve(strict=True)
    preregistration_hash = None
    if args.role == "validation":
        if args.preregistration is None:
            raise SystemExit("Validation requires a frozen preregistration.")
        preregistration_hash = _validate_preregistration(
            args.preregistration.resolve(strict=True),
            cascade_manifest=cascade_manifest,
            config=config,
            corpus_source=source,
            stt_directory=stt_directory,
            block_samples=args.block_samples,
            verification_policy=args.verification_policy,
        )
    detector = HyperspotterCascadeDetector(config)
    recognizer = None
    contextual_hotwords = ""
    if (
        config.lexical_rescue_enabled
        or config.direct_lexical_verifier_index is not None
        or args.verification_policy == "lexical_all"
    ):
        recognizer, contextual_hotwords = lexical._recognizer(
            stt_directory, config.direct_lexical_hotwords_score
        )
    started = time.perf_counter()
    positive = _evaluate_group(
        room._wav_paths(corpus / "positive", None),
        detector=detector,
        recognizer=recognizer,
        block_samples=args.block_samples,
        verification_policy=args.verification_policy,
        contextual_hotwords=contextual_hotwords,
    )
    negative = _evaluate_group(
        room._wav_paths(corpus / "negative", None),
        detector=detector,
        recognizer=recognizer,
        block_samples=args.block_samples,
        verification_policy=args.verification_policy,
        contextual_hotwords=contextual_hotwords,
    )
    passed = (
        positive["acceptedFiles"] == positive["files"]
        and negative["acceptedFiles"] == 0
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "exact_production_stream_api_opened_wasapi_raw",
        "role": args.role,
        "contract": {
            "sampleRate": SAMPLE_RATE,
            "blockSamples": args.block_samples,
            "leftContextSeconds": 1.0,
            "minimumRightContextSeconds": MINIMUM_RIGHT_CONTEXT_SECONDS,
            "lexicalFallback": (
                "bounded_direct_lexical_with_manifest_speed_views"
                if config.direct_lexical_verifier_index is not None
                else "full_utterance_leading_exact_normalized_alias"
                if config.lexical_rescue_enabled
                else "disabled"
            ),
            "verificationPolicy": args.verification_policy,
        },
        "assets": {
            "cascadeManifestSha256": room._sha256(cascade_manifest),
            "upstreamGraphSha256": list(config.upstream_graph_sha256),
            "melFiltersSha256": config.mel_filters_sha256,
            "logmelVerifierSha256": (
                list(getattr(config, "verifier_graph_sha256s", ()))
                if len(getattr(config, "verifier_graph_sha256s", ())) > 1
                else config.verifier_graph_sha256
            ),
        },
        "corpusManifestSha256": room._sha256(corpus_manifest),
        "preregistrationSha256": preregistration_hash,
        "positive": positive,
        "negative": negative,
        "elapsedWallSeconds": time.perf_counter() - started,
        "openedCorpusPassed": passed,
        "candidateFrozen": passed,
        "corpusFrozen": passed and args.role == "validation",
        "blindHumanPartitionAccessed": False,
        "promotable": passed and args.role == "validation",
        "developmentOnly": True,
        "effectsExecuted": 0,
        "filenamesOrTranscriptsRetained": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "passed": passed,
                "positive": positive["acceptedFiles"],
                "negative": negative["acceptedFiles"],
                "proposals": (
                    positive["upstreamCandidateFiles"]
                    + negative["upstreamCandidateFiles"]
                ),
                "runtimeP95": positive["runtimeSeconds"]["p95"],
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
