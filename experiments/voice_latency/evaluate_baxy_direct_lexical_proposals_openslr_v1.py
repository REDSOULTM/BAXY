"""Apply BAXY's bounded lexical guard to opened OpenSLR direct proposals."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (ROOT / "src", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_lexical_wake_physical_room_gate_v1 as lexical  # noqa: E402
from baxy_mind.wake_cascade import (  # noqa: E402
    WakeCascadeConfig,
    load_wake_cascade_candidate_config,
    match_bounded_lexical_wake,
    time_scaled_recognition_audio,
)


SCHEMA = "baxy.direct-lexical-openslr-negative-regression.v1"
SCREEN_SCHEMA = "baxy.direct-logmel-openslr-negative-regression.v1"
CORPUS_SCHEMA = "baxy.openslr-librispeech-negative-holdout.v1"
SAMPLE_RATE = 16_000
STT_FILES = ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("direct_lexical_openslr_json_invalid")
    return value


def confirm_audio(
    recognizer: Any,
    audio: np.ndarray,
    *,
    contextual_hotwords: str,
    config: WakeCascadeConfig,
    verifier_score: float | None = None,
) -> dict[str, Any]:
    attempts: list[str] = []
    method = None
    factors = (1.0, *config.direct_lexical_retry_speed_factors)
    for factor in factors:
        view = audio if factor == 1.0 else time_scaled_recognition_audio(audio, factor)
        transcript, _ = lexical._decode(
            recognizer,
            view,
            hotwords=contextual_hotwords,
        )
        attempts.append(hashlib.sha256(transcript.encode("utf-8")).hexdigest())
        match = match_bounded_lexical_wake(
            (transcript,),
            config.lexical_aliases,
            verifier_score=verifier_score,
            phonetic_confusion_score_gte=(
                getattr(
                    config,
                    "direct_lexical_phonetic_confusion_score_gte",
                    None,
                )
            ),
        )
        if match is not None:
            method = match.method
            break
    return {
        "accepted": method is not None,
        "method": method,
        "attemptTranscriptSha256": attempts,
    }


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    import soundfile as sf

    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("direct_lexical_openslr_output_exists")
    screen_path = args.screen_report.resolve(strict=True)
    corpus_path = args.corpus_manifest.resolve(strict=True)
    cascade_path = args.cascade_manifest.resolve(strict=True)
    stt_directory = args.stt_directory.resolve(strict=True)
    screen = read_object(screen_path)
    corpus = read_object(corpus_path)
    config = load_wake_cascade_candidate_config(cascade_path)
    screen_sources = screen.get("sources")
    screen_contract = screen.get("contract")
    exact_records = screen.get("exactRecords")
    corpus_records = corpus.get("records")
    corpus_metrics = corpus.get("metrics")
    direct_index = config.direct_lexical_verifier_index
    direct_threshold = config.direct_lexical_verifier_threshold
    if (
        screen.get("schema") != SCREEN_SCHEMA
        or corpus.get("schema") != CORPUS_SCHEMA
        or not isinstance(screen_sources, dict)
        or not isinstance(screen_contract, dict)
        or not isinstance(exact_records, list)
        or not isinstance(corpus_records, list)
        or not isinstance(corpus_metrics, dict)
        or direct_index is None
        or direct_threshold is None
        or screen_sources.get("corpusManifestSha256") != sha256(corpus_path)
        or screen_sources.get("onnxVerifierSha256")
        != config.verifier_graph_sha256s[direct_index]
        or screen_contract.get("verifierScoreGte") != direct_threshold
    ):
        raise ValueError("direct_lexical_openslr_contract_mismatch")
    root = (corpus_path.parent / str(corpus.get("corpus_root") or "")).resolve(
        strict=True
    )
    by_hash = {
        str(record.get("sha256")): record
        for record in corpus_records
        if isinstance(record, dict)
    }
    proposals = [
        record
        for record in exact_records
        if isinstance(record, dict) and record.get("directProposal") is True
    ]
    recognizer, contextual_hotwords = lexical._recognizer(
        stt_directory, config.direct_lexical_hotwords_score
    )
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    for index, proposal in enumerate(proposals):
        audio_hash = str(proposal.get("audioSha256") or "")
        corpus_record = by_hash.get(audio_hash)
        if corpus_record is None:
            raise ValueError("direct_lexical_openslr_record_missing")
        path = (root / str(corpus_record.get("relative_path") or "")).resolve(
            strict=True
        )
        if sha256(path) != audio_hash:
            raise ValueError("direct_lexical_openslr_audio_hash_mismatch")
        audio, rate = sf.read(str(path), dtype="float32", always_2d=False)
        values = np.asarray(audio, dtype=np.float32).reshape(-1)
        if int(rate) != SAMPLE_RATE or not values.size or not np.isfinite(values).all():
            raise ValueError("direct_lexical_openslr_audio_invalid")
        result = confirm_audio(
            recognizer,
            values,
            contextual_hotwords=contextual_hotwords,
            config=config,
            verifier_score=float(proposal["exactScore"]),
        )
        results.append({"audioSha256": audio_hash, **result})
        if (index + 1) % 25 == 0 or index + 1 == len(proposals):
            elapsed = time.perf_counter() - started
            rate_value = (index + 1) / elapsed if elapsed else 0.0
            remaining = (len(proposals) - index - 1) / rate_value if rate_value else None
            print(
                "BAXY_DIRECT_LEXICAL|"
                f"{index + 1}/{len(proposals)}|rate={rate_value:.2f}/s|"
                f"remaining={remaining:.1f}s"
            )
    false_activations = sum(bool(result["accepted"]) for result in results)
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_openslr_direct_proposals_exact_product_lexical_guard",
        "sources": {
            "screenReportSha256": sha256(screen_path),
            "corpusManifestSha256": sha256(corpus_path),
            "cascadeManifestSha256": sha256(cascade_path),
            "directVerifierSha256": config.verifier_graph_sha256s[direct_index],
            "sttFilesSha256": {
                name: sha256(stt_directory / name) for name in STT_FILES
            },
            "evaluatorSourceSha256": sha256(Path(__file__).resolve()),
        },
        "contract": {
            "directVerifierIndex": direct_index,
            "directVerifierScoreGte": direct_threshold,
            "lexicalAliases": sorted(config.lexical_aliases),
            "retrySpeedFactors": list(config.direct_lexical_retry_speed_factors),
            "hotwordsScore": config.direct_lexical_hotwords_score,
            "minimumConsecutiveHops": (
                config.direct_lexical_minimum_consecutive_hops
            ),
            "phoneticConfusionScoreGte": (
                config.direct_lexical_phonetic_confusion_score_gte
            ),
        },
        "metrics": {
            "descriptiveExposureHours": corpus_metrics.get("audio_hours"),
            "utterances": len(corpus_records),
            "directAcousticProposals": len(proposals),
            "lexicalFalseActivations": false_activations,
        },
        "records": results,
        "elapsedWallSeconds": time.perf_counter() - started,
        "directProposalIsWakeAuthority": False,
        "lexicalGuardMeasured": True,
        "transcriptTextRetained": False,
        "candidateFrozen": False,
        "promotable": False,
        "negativeCorpusPreviouslyAccessed": True,
        "blindHumanAudioAccessed": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen-report", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--cascade-manifest", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    report = evaluate(parser.parse_args())
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0 if report["metrics"]["lexicalFalseActivations"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
