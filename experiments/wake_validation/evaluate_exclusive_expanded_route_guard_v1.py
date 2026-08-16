"""Measure a lexical guard for the exclusive expanded wake route.

This development-only evaluator replays only records that an already-bound
cascade report accepted through the log-Mel route.  It instruments which
upstream models proposed the accepted window and asks whether detections that
depend exclusively on the expanded physical upstream model also have a strict
leading BAXY alias in Parakeet.  It never reads physical v17, retains transcript
text, changes thresholds, or promotes a candidate.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
VOICE = ROOT / "experiments" / "voice_latency"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(VOICE))

import evaluate_baxy_wake_cascade_runtime_raw_v1 as cascade_eval  # noqa: E402
import run_lexical_wake_physical_room_gate_v1 as lexical  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind.wake_cascade import (  # noqa: E402
    HyperspotterCascadeDetector,
    has_strict_leading_alias,
    load_wake_cascade_candidate_config,
    time_scaled_recognition_audio,
)


SCHEMA = "baxy.exclusive-expanded-route-guard-development.v1"
PREREGISTRATION_SCHEMA = (
    "baxy.exclusive-expanded-route-guard-development-preregistration.v1"
)
CASCADE_REPORT_SCHEMA = "baxy.wake-cascade-runtime-raw-development.v1"
TARGET_UPSTREAM_TUPLE = (False, False, True)
SAMPLE_RATE = 16_000
STT_FILES = (
    "encoder.int8.onnx",
    "decoder.int8.onnx",
    "joiner.int8.onnx",
    "tokens.txt",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("exclusive_expanded_json_invalid")
    return value


def _forbid_v17(*paths: Path) -> None:
    if any("v17" in str(path).lower() for path in paths):
        raise ValueError("exclusive_expanded_physical_v17_forbidden")


def _wav_paths(corpus: Path, label: str) -> list[Path]:
    return sorted(path for path in (corpus / label).rglob("*.wav") if path.is_file())


def _accepted_logmel_records(group: dict[str, Any]) -> list[dict[str, Any]]:
    records = group.get("records")
    if not isinstance(records, list):
        raise ValueError("exclusive_expanded_report_records_invalid")
    selected: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("exclusive_expanded_report_record_invalid")
        if record.get("accepted") is True and record.get("reason") == "logmel_verifier":
            selected.append(record)
    declared = group.get("logmelAcceptedFiles")
    if declared != len(selected):
        raise ValueError("exclusive_expanded_report_logmel_count_mismatch")
    return selected


def summarize_guard_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize prospective acceptance after guarding one upstream tuple."""

    values = list(records)
    exclusive = [
        record
        for record in values
        if tuple(record.get("upstreamCandidates", ())) == TARGET_UPSTREAM_TUPLE
    ]
    confirmed = [
        record for record in exclusive if record.get("strictAliasMatched") is True
    ]
    return {
        "currentLogmelAccepted": len(values),
        "exclusiveExpandedAccepted": len(exclusive),
        "exclusiveExpandedStrictAliasAccepted": len(confirmed),
        "guardedLogmelAccepted": len(values) - len(exclusive) + len(confirmed),
        "removedByGuard": len(exclusive) - len(confirmed),
    }


class TracedHyperspotterCascadeDetector(HyperspotterCascadeDetector):
    """Expose only the boolean upstream tuple for a detected window."""

    def reset(self) -> None:
        super().reset()
        self._latest_upstream_candidates: tuple[bool, ...] | None = None
        self.detection_upstream_candidates: tuple[bool, ...] | None = None

    def _upstream_candidates(self, logmel: np.ndarray) -> tuple[bool, ...]:
        values = super()._upstream_candidates(logmel)
        self._latest_upstream_candidates = values
        return values

    def _score_current_window(self, now: float | None):  # type: ignore[no-untyped-def]
        detection = super()._score_current_window(now)
        if detection is not None:
            self.detection_upstream_candidates = self._latest_upstream_candidates
        return detection


def _decode_strict_alias_views(
    recognizer: Any,
    audio: np.ndarray,
    *,
    aliases: frozenset[str],
    speed_factors: tuple[float, ...],
) -> tuple[bool, list[str]]:
    hashes: list[str] = []
    matched = False
    for factor in (1.0, *speed_factors):
        view = audio if factor == 1.0 else time_scaled_recognition_audio(audio, factor)
        transcript, _ = lexical._decode(recognizer, view, hotwords="")
        hashes.append(hashlib.sha256(transcript.encode("utf-8")).hexdigest())
        matched = matched or has_strict_leading_alias(transcript, aliases)
    return matched, hashes


def _replay_logmel_record(
    *,
    path: Path,
    expected: dict[str, Any],
    detector: TracedHyperspotterCascadeDetector,
    recognizer: Any,
    block_samples: int,
) -> dict[str, Any]:
    if _sha256(path) != expected.get("audioSha256"):
        raise ValueError("exclusive_expanded_audio_hash_mismatch")
    audio, sample_rate = room._read_pcm16(path)
    audio = room._resample(audio, sample_rate, SAMPLE_RATE)
    streamed = cascade_eval.stream_audio(audio)
    detector.reset()
    hit = None
    for start in range(0, len(streamed), block_samples):
        hit = detector.accept(streamed[start : start + block_samples], now=10.0)
        if hit is not None:
            break
    if hit is None or hit.method != "logmel_verifier":
        raise ValueError("exclusive_expanded_logmel_replay_mismatch")
    upstream = detector.detection_upstream_candidates
    if upstream is None or len(upstream) != 3:
        raise ValueError("exclusive_expanded_upstream_trace_invalid")
    strict_match = None
    transcript_hashes: list[str] = []
    if upstream == TARGET_UPSTREAM_TUPLE:
        strict_match, transcript_hashes = _decode_strict_alias_views(
            recognizer,
            audio,
            aliases=detector.config.lexical_aliases,
            speed_factors=detector.config.direct_lexical_retry_speed_factors,
        )
    return {
        "record": expected.get("record"),
        "audioSha256": expected.get("audioSha256"),
        "upstreamCandidates": list(upstream),
        "strictAliasMatched": strict_match,
        "attemptTranscriptSha256": transcript_hashes,
    }


def _evaluate_group(
    *,
    label: str,
    group: dict[str, Any],
    corpus: Path,
    detector: TracedHyperspotterCascadeDetector,
    recognizer: Any,
    block_samples: int,
) -> dict[str, Any]:
    paths = _wav_paths(corpus, label)
    if group.get("files") != len(paths):
        raise ValueError("exclusive_expanded_corpus_count_mismatch")
    selected = _accepted_logmel_records(group)
    records: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    for expected in selected:
        index = expected.get("record")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(paths)
        ):
            raise ValueError("exclusive_expanded_record_index_invalid")
        measured = _replay_logmel_record(
            path=paths[index],
            expected=expected,
            detector=detector,
            recognizer=recognizer,
            block_samples=block_samples,
        )
        route_counts[
            "".join("1" if value else "0" for value in measured["upstreamCandidates"])
        ] += 1
        records.append(measured)
    return {
        "files": len(paths),
        "currentAcceptedFiles": group.get("acceptedFiles"),
        "currentLexicalAcceptedFiles": group.get("lexicalAcceptedFiles"),
        "routeTupleCounts": dict(sorted(route_counts.items())),
        **summarize_guard_records(records),
        "prospectiveAcceptedFiles": (
            int(group.get("acceptedFiles", 0))
            - int(group.get("logmelAcceptedFiles", 0))
            + summarize_guard_records(records)["guardedLogmelAccepted"]
        ),
        "records": records,
        "transcriptTextRetained": False,
    }


def _validate_preregistration(
    preregistration: dict[str, Any],
    *,
    candidate_manifest: Path,
    cascade_report: Path,
    corpus_manifest: Path,
    stt_directory: Path,
    output: Path,
    label: str,
    block_samples: int,
) -> None:
    if preregistration.get("schema") != PREREGISTRATION_SCHEMA:
        raise ValueError("exclusive_expanded_preregistration_invalid")
    jobs = preregistration.get("jobs")
    if not isinstance(jobs, dict) or not isinstance(jobs.get(label), dict):
        raise ValueError("exclusive_expanded_preregistration_job_missing")
    job = jobs[label]
    if preregistration.get("programSha256") != _sha256(Path(__file__)):
        raise ValueError("exclusive_expanded_preregistration_program_mismatch")
    expected = {
        "candidateManifestSha256": _sha256(candidate_manifest),
        "cascadeReportSha256": _sha256(cascade_report),
        "corpusManifestSha256": _sha256(corpus_manifest),
    }
    if any(job.get(key) != value for key, value in expected.items()):
        raise ValueError("exclusive_expanded_preregistration_hash_mismatch")
    actual_stt = {name: _sha256(stt_directory / name) for name in STT_FILES}
    if preregistration.get("sttSha256") != actual_stt:
        raise ValueError("exclusive_expanded_preregistration_stt_mismatch")
    contract = preregistration.get("contract")
    if (
        not isinstance(contract, dict)
        or contract.get("blockSamples") != block_samples
        or contract.get("targetUpstreamTuple") != list(TARGET_UPSTREAM_TUPLE)
        or contract.get("physicalV17Read") is not False
        or contract.get("retainTranscriptText") is not False
        or contract.get("promotionEligible") is not False
        or job.get("plannedOutput") != output.relative_to(ROOT).as_posix()
    ):
        raise ValueError("exclusive_expanded_preregistration_contract_mismatch")


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    paths = (
        args.cascade_manifest.resolve(),
        args.cascade_report.resolve(),
        args.corpus.resolve(),
        args.preregistration.resolve(),
        args.output.resolve(),
    )
    _forbid_v17(*paths)
    if args.output.exists():
        raise FileExistsError("exclusive_expanded_output_exists")
    report = _read_object(args.cascade_report)
    if (
        report.get("schema") != CASCADE_REPORT_SCHEMA
        or report.get("blindHumanPartitionAccessed") is not False
        or report.get("developmentOnly") is not True
    ):
        raise ValueError("exclusive_expanded_cascade_report_invalid")
    preregistration = _read_object(args.preregistration)
    corpus_manifest = args.corpus / "manifest.v1.json"
    _validate_preregistration(
        preregistration,
        candidate_manifest=args.cascade_manifest,
        cascade_report=args.cascade_report,
        corpus_manifest=corpus_manifest,
        stt_directory=args.stt_directory,
        output=args.output,
        label=args.label,
        block_samples=args.block_samples,
    )
    config = load_wake_cascade_candidate_config(args.cascade_manifest)
    detector = TracedHyperspotterCascadeDetector(config)
    recognizer, _contextual_hotwords = lexical._recognizer(
        args.stt_directory,
        config.direct_lexical_hotwords_score,
    )
    positive = _evaluate_group(
        label="positive",
        group=report["positive"],
        corpus=args.corpus,
        detector=detector,
        recognizer=recognizer,
        block_samples=args.block_samples,
    )
    negative = _evaluate_group(
        label="negative",
        group=report["negative"],
        corpus=args.corpus,
        detector=detector,
        recognizer=recognizer,
        block_samples=args.block_samples,
    )
    result = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "preregistrationSha256": _sha256(args.preregistration),
        "inputsSha256": {
            "program": _sha256(Path(__file__)),
            "candidateManifest": _sha256(args.cascade_manifest),
            "cascadeReport": _sha256(args.cascade_report),
            "corpusManifest": _sha256(corpus_manifest),
        },
        "contract": {
            "blockSamples": args.block_samples,
            "targetUpstreamTuple": list(TARGET_UPSTREAM_TUPLE),
            "strictAliases": sorted(config.lexical_aliases),
            "retrySpeedFactors": list(config.direct_lexical_retry_speed_factors),
            "hotwords": False,
            "physicalV17Read": False,
            "transcriptTextRetained": False,
        },
        "positive": positive,
        "negative": negative,
        "noPositiveRegression": (
            positive["prospectiveAcceptedFiles"] == positive["currentAcceptedFiles"]
        ),
        "zeroNegativeFalseActivations": negative["prospectiveAcceptedFiles"] == 0,
        "developmentPassed": (
            positive["prospectiveAcceptedFiles"] == positive["currentAcceptedFiles"]
            and negative["prospectiveAcceptedFiles"] == 0
        ),
        "candidateRuntimeModified": False,
        "promotionEligible": False,
        "blindHumanPartitionAccessed": False,
        "effectsExecuted": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cascade-manifest", type=Path, required=True)
    parser.add_argument("--cascade-report", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--block-samples", type=int, default=512)
    args = parser.parse_args()
    result = evaluate(args)
    print(
        json.dumps(
            {
                "label": result["label"],
                "positive": result["positive"]["prospectiveAcceptedFiles"],
                "negative": result["negative"]["prospectiveAcceptedFiles"],
                "passed": result["developmentPassed"],
                "output": str(args.output),
            },
            separators=(",", ":"),
        )
    )
    return 0 if result["developmentPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
