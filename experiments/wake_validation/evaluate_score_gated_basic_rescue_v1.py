"""Evaluate a score-gated ``basic`` wake confusion on opened development data.

The program deliberately cannot read the consumed physical v17 corpus.  It
uses the already-opened endpoint-confusable physical corpus and the opened
OpenSLR 100-hour negative screen to decide whether the manifest's existing
phonetic-confusion score gate can safely cover a leading ``basic`` ASR token.
Transcript text and filenames are never written to the report.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
VOICE = ROOT / "experiments" / "voice_latency"
for path in (ROOT / "src", ROOT / "scripts", VOICE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_lexical_wake_physical_room_gate_v1 as lexical  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind.wake_cascade import (  # noqa: E402
    load_wake_cascade_candidate_config,
    normalize_lexical_transcript,
    time_scaled_recognition_audio,
)


SCHEMA = "baxy.score-gated-basic-rescue-development.v1"
PREREGISTRATION_SCHEMA = "baxy.score-gated-basic-rescue-development-preregistration.v1"
ENDPOINT_SCHEMA = "baxy.endpoint-lexical-raw-development.v1"
OPENSLR_SCREEN_SCHEMA = "baxy.direct-logmel-openslr-negative-regression.v1"
OPENSLR_CORPUS_SCHEMA = "baxy.openslr-librispeech-negative-holdout.v1"
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
        raise ValueError("score_gated_basic_json_invalid")
    return value


def score_gated_basic_match(
    transcripts: Iterable[str],
    *,
    verifier_score: float | None,
    score_gte: float | None,
) -> bool:
    """Return true only for a leading ``basic`` above a finite frozen gate."""

    if (
        verifier_score is None
        or score_gte is None
        or not math.isfinite(verifier_score)
        or not math.isfinite(score_gte)
        or verifier_score < score_gte
    ):
        return False
    for transcript in transcripts:
        words = normalize_lexical_transcript(transcript).split()
        if words[:1] == ["basic"]:
            return True
    return False


def _decode_views(
    recognizer: Any,
    audio: np.ndarray,
    *,
    contextual_hotwords: str,
    factors: tuple[float, ...],
    verifier_score: float,
    score_gte: float,
) -> dict[str, Any]:
    hashes: list[str] = []
    basic_views = 0
    for factor in factors:
        view = audio if factor == 1.0 else time_scaled_recognition_audio(audio, factor)
        transcript, _ = lexical._decode(
            recognizer,
            view,
            hotwords=contextual_hotwords,
        )
        hashes.append(hashlib.sha256(transcript.encode("utf-8")).hexdigest())
        if score_gated_basic_match(
            (transcript,),
            verifier_score=verifier_score,
            score_gte=score_gte,
        ):
            basic_views += 1
    return {
        "basicMatched": basic_views > 0,
        "basicViews": basic_views,
        "attemptTranscriptSha256": hashes,
    }


def _decode_flac(ffmpeg: Path, path: Path) -> np.ndarray:
    completed = subprocess.run(
        (
            str(ffmpeg),
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "pipe:1",
        ),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    audio = np.frombuffer(completed.stdout, dtype="<f4").copy()
    if not audio.size or not np.isfinite(audio).all():
        raise ValueError("score_gated_basic_openslr_audio_invalid")
    return audio


def _validate_preregistration(
    preregistration: dict[str, Any],
    *,
    paths: dict[str, Path],
    output: Path,
    score_gte: float,
) -> None:
    if preregistration.get("schema") != PREREGISTRATION_SCHEMA:
        raise ValueError("score_gated_basic_preregistration_invalid")
    expected = preregistration.get("inputsSha256")
    if not isinstance(expected, dict):
        raise ValueError("score_gated_basic_preregistration_invalid")
    for name, path in paths.items():
        if expected.get(name) != _sha256(path):
            raise ValueError(f"score_gated_basic_input_hash_mismatch:{name}")
    contract = preregistration.get("contract")
    planned = preregistration.get("plannedOutput")
    if (
        not isinstance(contract, dict)
        or contract.get("scoreGte") != score_gte
        or contract.get("readPhysicalV17") is not False
        or contract.get("retainTranscriptText") is not False
        or contract.get("promotionEligible") is not False
        or str(planned) != output.relative_to(ROOT).as_posix()
    ):
        raise ValueError("score_gated_basic_preregistration_contract_mismatch")


def _evaluate_confusable(
    *,
    report: dict[str, Any],
    corpus: Path,
    recognizer: Any,
    contextual_hotwords: str,
    factors: tuple[float, ...],
    score_gte: float,
) -> dict[str, Any]:
    if report.get("schema") != ENDPOINT_SCHEMA:
        raise ValueError("score_gated_basic_endpoint_report_invalid")
    result: dict[str, Any] = {}
    for label in ("positive", "negative"):
        group = report.get(label)
        records = group.get("records") if isinstance(group, dict) else None
        paths = room._wav_paths(corpus / label, None)
        if not isinstance(records, list) or len(records) != len(paths):
            raise ValueError("score_gated_basic_confusable_identity_mismatch")
        measured: list[dict[str, Any]] = []
        for index, (record, path) in enumerate(zip(records, paths, strict=True)):
            if not isinstance(record, dict) or record.get("record") != index:
                raise ValueError("score_gated_basic_confusable_record_invalid")
            if record.get("audioSha256") != room._sha256(path):
                raise ValueError("score_gated_basic_confusable_audio_mismatch")
            score = record.get("directScore")
            if not isinstance(score, (int, float)) or float(score) < score_gte:
                continue
            audio, sample_rate = room._read_pcm16(path)
            audio = room._resample(audio, sample_rate, SAMPLE_RATE)
            decoded = _decode_views(
                recognizer,
                audio,
                contextual_hotwords=contextual_hotwords,
                factors=factors,
                verifier_score=float(score),
                score_gte=score_gte,
            )
            measured.append(
                {
                    "audioSha256": record["audioSha256"],
                    "verifierScore": float(score),
                    **decoded,
                }
            )
        result[label] = {
            "files": len(paths),
            "eligibleAboveGate": len(measured),
            "scoreGatedBasicMatches": sum(
                bool(record["basicMatched"]) for record in measured
            ),
            "records": measured,
        }
    return result


def _evaluate_openslr(
    *,
    screen: dict[str, Any],
    corpus: dict[str, Any],
    corpus_manifest: Path,
    ffmpeg: Path,
    recognizer: Any,
    contextual_hotwords: str,
    factors: tuple[float, ...],
    score_gte: float,
) -> dict[str, Any]:
    if (
        screen.get("schema") != OPENSLR_SCREEN_SCHEMA
        or corpus.get("schema") != OPENSLR_CORPUS_SCHEMA
    ):
        raise ValueError("score_gated_basic_openslr_input_invalid")
    exact_records = screen.get("exactRecords")
    corpus_records = corpus.get("records")
    metrics = corpus.get("metrics")
    if (
        not isinstance(exact_records, list)
        or not isinstance(corpus_records, list)
        or not isinstance(metrics, dict)
    ):
        raise ValueError("score_gated_basic_openslr_input_invalid")
    corpus_root = (
        corpus_manifest.parent / str(corpus.get("corpus_root") or "")
    ).resolve(strict=True)
    by_hash = {
        str(record.get("sha256")): record
        for record in corpus_records
        if isinstance(record, dict)
    }
    proposals = [
        record
        for record in exact_records
        if isinstance(record, dict)
        and record.get("directProposal") is True
        and isinstance(record.get("exactScore"), (int, float))
        and float(record["exactScore"]) >= score_gte
    ]
    measured: list[dict[str, Any]] = []
    started = time.perf_counter()
    for index, proposal in enumerate(proposals, 1):
        audio_hash = str(proposal.get("audioSha256") or "")
        source = by_hash.get(audio_hash)
        if not isinstance(source, dict):
            raise ValueError("score_gated_basic_openslr_record_missing")
        path = (corpus_root / str(source.get("relative_path") or "")).resolve(
            strict=True
        )
        if _sha256(path) != audio_hash:
            raise ValueError("score_gated_basic_openslr_audio_mismatch")
        decoded = _decode_views(
            recognizer,
            _decode_flac(ffmpeg, path),
            contextual_hotwords=contextual_hotwords,
            factors=factors,
            verifier_score=float(proposal["exactScore"]),
            score_gte=score_gte,
        )
        measured.append(
            {
                "audioSha256": audio_hash,
                "verifierScore": float(proposal["exactScore"]),
                **decoded,
            }
        )
        if index % 10 == 0 or index == len(proposals):
            elapsed = time.perf_counter() - started
            rate = index / elapsed if elapsed else 0.0
            remaining = (len(proposals) - index) / rate if rate else None
            print(
                "BAXY_BASIC_RESCUE|"
                f"{index}/{len(proposals)}|rate={rate:.2f}/s|"
                f"remaining={remaining:.1f}s",
                flush=True,
            )
    return {
        "utterances": len(corpus_records),
        "descriptiveExposureHours": metrics.get("audio_hours"),
        "directProposalsAboveGate": len(proposals),
        "viewsDecoded": len(proposals) * len(factors),
        "scoreGatedBasicFalseActivations": sum(
            bool(record["basicMatched"]) for record in measured
        ),
        "records": measured,
    }


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("score_gated_basic_output_exists")
    paths = {
        "program": Path(__file__).resolve(),
        "candidateManifest": args.candidate_manifest.resolve(strict=True),
        "confusableReport": args.confusable_report.resolve(strict=True),
        "confusableCorpusManifest": (
            args.confusable_corpus.resolve(strict=True) / "manifest.v1.json"
        ),
        "openslrScreenReport": args.openslr_screen_report.resolve(strict=True),
        "openslrCorpusManifest": args.openslr_corpus_manifest.resolve(strict=True),
        "ffmpeg": args.ffmpeg.resolve(strict=True),
    }
    stt_directory = args.stt_directory.resolve(strict=True)
    for name in STT_FILES:
        paths[f"stt:{name}"] = stt_directory / name
    config = load_wake_cascade_candidate_config(paths["candidateManifest"])
    score_gte = config.direct_lexical_phonetic_confusion_score_gte
    if score_gte is None or not math.isfinite(score_gte):
        raise ValueError("score_gated_basic_manifest_gate_missing")
    preregistration_path = args.preregistration.resolve(strict=True)
    _validate_preregistration(
        _read_object(preregistration_path),
        paths=paths,
        output=output,
        score_gte=score_gte,
    )
    factors = (1.0, *config.direct_lexical_retry_speed_factors)
    recognizer, contextual_hotwords = lexical._recognizer(
        stt_directory, config.direct_lexical_hotwords_score
    )
    confusable = _evaluate_confusable(
        report=_read_object(paths["confusableReport"]),
        corpus=args.confusable_corpus.resolve(strict=True),
        recognizer=recognizer,
        contextual_hotwords=contextual_hotwords,
        factors=factors,
        score_gte=score_gte,
    )
    openslr = _evaluate_openslr(
        screen=_read_object(paths["openslrScreenReport"]),
        corpus=_read_object(paths["openslrCorpusManifest"]),
        corpus_manifest=paths["openslrCorpusManifest"],
        ffmpeg=paths["ffmpeg"],
        recognizer=recognizer,
        contextual_hotwords=contextual_hotwords,
        factors=factors,
        score_gte=score_gte,
    )
    passed = (
        confusable["positive"]["scoreGatedBasicMatches"] >= 1
        and confusable["negative"]["scoreGatedBasicMatches"] == 0
        and openslr["scoreGatedBasicFalseActivations"] == 0
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "preregistrationSha256": _sha256(preregistration_path),
        "inputsSha256": {name: _sha256(path) for name, path in paths.items()},
        "contract": {
            "leadingToken": "basic",
            "scoreGte": score_gte,
            "scoreSource": "existing_manifest_phonetic_confusion_gate",
            "retrySpeedFactors": list(config.direct_lexical_retry_speed_factors),
            "hotwordsScore": config.direct_lexical_hotwords_score,
            "physicalV17Read": False,
            "transcriptTextRetained": False,
            "filenamesRetained": False,
        },
        "confusablePhysicalDevelopment": confusable,
        "openslr100hNegativeDevelopment": openslr,
        "passed": passed,
        "candidateRuntimeModified": False,
        "promotionEligible": False,
        "blindHumanPartitionAccessed": False,
        "effectsExecuted": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--confusable-report", type=Path, required=True)
    parser.add_argument("--confusable-corpus", type=Path, required=True)
    parser.add_argument("--openslr-screen-report", type=Path, required=True)
    parser.add_argument("--openslr-corpus-manifest", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    report = evaluate(_parser().parse_args())
    summary = {
        "confusablePositiveBasic": report["confusablePhysicalDevelopment"]["positive"][
            "scoreGatedBasicMatches"
        ],
        "confusableNegativeBasic": report["confusablePhysicalDevelopment"]["negative"][
            "scoreGatedBasicMatches"
        ],
        "openslrBasicFalseActivations": report["openslr100hNegativeDevelopment"][
            "scoreGatedBasicFalseActivations"
        ],
        "passed": report["passed"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
