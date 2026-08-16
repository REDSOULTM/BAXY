"""Evaluate a suffix-independent endpoint wake policy on opened RAW audio.

The acoustic cascade keeps running continuously, but an utterance endpoint may
also authorize a turn when local Parakeet decodes a leading BAXY pronunciation.
The command suffix is deliberately not part of an exact canonical-name
decision. Ambiguous pronunciations such as ``Basi``/``basic`` are excluded
from this endpoint route and remain the responsibility of the independent
acoustic cascade. This is a development evaluator only; it never promotes a
candidate.
"""

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
for path in (ROOT / "src", ROOT / "scripts", Path(__file__).resolve().parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import evaluate_baxy_direct_logmel_lexical_raw_v1 as direct  # noqa: E402
import run_lexical_wake_physical_room_gate_v1 as lexical  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind.wake_cascade import (  # noqa: E402
    LOGMEL_BINS,
    SAMPLE_RATE,
    load_wake_cascade_candidate_config,
    match_bounded_lexical_wake,
    match_suffix_independent_endpoint_wake,
    numpy_log_mel_spectrogram,
    time_scaled_recognition_audio,
)


SCHEMA = "baxy.endpoint-lexical-raw-development.v1"


def endpoint_aliases(config: Any) -> frozenset[str]:
    """Return the frozen, pronunciation-oriented leading-token vocabulary."""

    return frozenset((*config.lexical_aliases, "bakse", "backsy"))


def match_endpoint_policy(
    transcript: str,
    aliases: frozenset[str],
    *,
    policy: str,
    verifier_score: float,
    phonetic_confusion_score_gte: float,
    endpoint_direct_score_gte: float,
) -> object | None:
    """Apply one explicit endpoint policy to a decoded transcript."""

    if policy == "strict_score_gated":
        if verifier_score < endpoint_direct_score_gte:
            return None
        return match_suffix_independent_endpoint_wake((transcript,), aliases)
    if policy == "strict_endpoint":
        return match_suffix_independent_endpoint_wake((transcript,), aliases)
    if policy == "bounded_development":
        return match_bounded_lexical_wake(
            (transcript,),
            aliases,
            verifier_score=verifier_score,
            phonetic_confusion_score_gte=phonetic_confusion_score_gte,
        )
    raise ValueError("endpoint_policy_invalid")


def _session(path: Path) -> Any:
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    return ort.InferenceSession(
        str(path), sess_options=options, providers=["CPUExecutionProvider"]
    )


def _direct_score(
    audio: np.ndarray,
    *,
    mel_filters: np.ndarray,
    verifier: Any,
    hop_samples: int,
) -> float:
    features = np.stack(
        [
            numpy_log_mel_spectrogram(window, mel_filters)
            for window in direct.stream_windows(audio, hop_samples)
        ]
    ).astype(np.float32)
    scores = np.asarray(
        verifier.run(["wake_logit"], {"logmel": features})[0],
        dtype=np.float32,
    ).reshape(-1)
    if scores.size != len(features) or not np.isfinite(scores).all():
        raise ValueError("endpoint_direct_score_invalid")
    return float(np.max(scores))


def _decode_endpoint(
    audio: np.ndarray,
    *,
    recognizer: Any,
    hotwords: str,
    aliases: frozenset[str],
    retry_speed_factors: tuple[float, ...],
    policy: str,
    verifier_score: float,
    phonetic_confusion_score_gte: float,
    endpoint_direct_score_gte: float,
) -> tuple[object | None, list[str], float]:
    transcript_hashes: list[str] = []
    started = time.perf_counter()
    match = None
    for factor in (1.0, *retry_speed_factors):
        view = audio if factor == 1.0 else time_scaled_recognition_audio(audio, factor)
        transcript, _ = lexical._decode(
            recognizer,
            view,
            hotwords=hotwords,
        )
        transcript_hashes.append(
            hashlib.sha256(f"{factor:.6f}:{transcript}".encode("utf-8")).hexdigest()
        )
        match = match_endpoint_policy(
            transcript,
            aliases,
            policy=policy,
            verifier_score=verifier_score,
            phonetic_confusion_score_gte=phonetic_confusion_score_gte,
            endpoint_direct_score_gte=endpoint_direct_score_gte,
        )
        if match is not None:
            break
    return match, transcript_hashes, time.perf_counter() - started


def _measure_group(
    paths: list[Path],
    *,
    mel_filters: np.ndarray,
    verifier: Any,
    recognizer: Any,
    hotwords: str,
    aliases: frozenset[str],
    retry_speed_factors: tuple[float, ...],
    hop_samples: int,
    policy: str,
    phonetic_confusion_score_gte: float,
    endpoint_direct_score_gte: float,
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    direct_seconds: list[float] = []
    lexical_seconds: list[float] = []
    total_seconds: list[float] = []
    audio_seconds = 0.0
    for index, path in enumerate(paths):
        audio, rate = room._read_pcm16(path)
        audio = room._resample(audio, rate, SAMPLE_RATE)
        audio_seconds += len(audio) / SAMPLE_RATE

        score_started = time.perf_counter()
        verifier_score = _direct_score(
            audio,
            mel_filters=mel_filters,
            verifier=verifier,
            hop_samples=hop_samples,
        )
        score_seconds = time.perf_counter() - score_started
        match, transcript_hashes, decode_seconds = _decode_endpoint(
            audio,
            recognizer=recognizer,
            hotwords=hotwords,
            aliases=aliases,
            retry_speed_factors=retry_speed_factors,
            policy=policy,
            verifier_score=verifier_score,
            phonetic_confusion_score_gte=phonetic_confusion_score_gte,
            endpoint_direct_score_gte=endpoint_direct_score_gte,
        )
        direct_seconds.append(score_seconds)
        lexical_seconds.append(decode_seconds)
        total_seconds.append(score_seconds + decode_seconds)
        records.append(
            {
                "record": index,
                "audioSha256": room._sha256(path),
                "hit": match is not None,
                "method": getattr(match, "method", None),
                "directScore": verifier_score,
                "asrViews": len(transcript_hashes),
                "transcriptSha256": transcript_hashes,
            }
        )

    hits = sum(bool(record["hit"]) for record in records)
    return {
        "files": len(records),
        "hits": hits,
        "rate": hits / len(records),
        "audioSeconds": audio_seconds,
        "runtimeSeconds": {
            "directP50": room._percentile(direct_seconds, 0.50),
            "directP95": room._percentile(direct_seconds, 0.95),
            "lexicalP50": room._percentile(lexical_seconds, 0.50),
            "lexicalP95": room._percentile(lexical_seconds, 0.95),
            "totalP50": room._percentile(total_seconds, 0.50),
            "totalP95": room._percentile(total_seconds, 0.95),
        },
        "methodCounts": {
            method: sum(record["method"] == method for record in records)
            for method in sorted(
                {
                    str(record["method"])
                    for record in records
                    if record["method"] is not None
                }
            )
        },
        "records": records,
        "transcriptTextRetained": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cascade-manifest", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hop-samples", type=int, default=4_000)
    parser.add_argument(
        "--policy",
        choices=(
            "strict_score_gated",
            "strict_endpoint",
            "bounded_development",
        ),
        default="strict_score_gated",
    )
    parser.add_argument("--endpoint-direct-score-gte", type=float)
    return parser


def main() -> int:
    args = _parser().parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists.")
    corpus = args.corpus.resolve(strict=True)
    source_manifest = corpus / "manifest.v1.json"
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    if source.get("physicalPath", {}).get("captureTransport") != (
        "wasapi_raw_iaudioclient2"
    ):
        raise SystemExit("Corpus is not an attested RAW physical capture.")

    cascade_manifest = args.cascade_manifest.resolve(strict=True)
    config = load_wake_cascade_candidate_config(cascade_manifest)
    endpoint_direct_score_gte = args.endpoint_direct_score_gte
    if endpoint_direct_score_gte is None:
        endpoint_direct_score_gte = config.endpoint_lexical_score_threshold
    if args.policy == "strict_score_gated" and endpoint_direct_score_gte is None:
        raise SystemExit("Cascade has no endpoint lexical score threshold.")
    direct_index = config.direct_lexical_verifier_index
    if direct_index is None:
        raise SystemExit("Cascade has no direct lexical verifier.")
    mel_filters = np.asarray(
        np.load(config.mel_filters_path, allow_pickle=False), dtype=np.float32
    )
    if mel_filters.shape != (LOGMEL_BINS, 201):
        raise ValueError("endpoint_logmel_filter_invalid")
    verifier = _session(config.verifier_graph_paths[direct_index])
    recognizer, hotwords = lexical._recognizer(
        args.stt_directory.resolve(strict=True),
        config.direct_lexical_hotwords_score,
    )
    aliases = endpoint_aliases(config)
    started = time.perf_counter()
    positive = _measure_group(
        room._wav_paths(corpus / "positive", None),
        mel_filters=mel_filters,
        verifier=verifier,
        recognizer=recognizer,
        hotwords=hotwords,
        aliases=aliases,
        retry_speed_factors=config.direct_lexical_retry_speed_factors,
        hop_samples=args.hop_samples,
        policy=args.policy,
        phonetic_confusion_score_gte=(
            config.direct_lexical_phonetic_confusion_score_gte
        ),
        endpoint_direct_score_gte=float(endpoint_direct_score_gte or 0.0),
    )
    negative = _measure_group(
        room._wav_paths(corpus / "negative", None),
        mel_filters=mel_filters,
        verifier=verifier,
        recognizer=recognizer,
        hotwords=hotwords,
        aliases=aliases,
        retry_speed_factors=config.direct_lexical_retry_speed_factors,
        hop_samples=args.hop_samples,
        policy=args.policy,
        phonetic_confusion_score_gte=(
            config.direct_lexical_phonetic_confusion_score_gte
        ),
        endpoint_direct_score_gte=float(endpoint_direct_score_gte or 0.0),
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_wasapi_raw_suffix_independent_endpoint_development",
        "assets": {
            "cascadeManifestSha256": room._sha256(cascade_manifest),
            "directVerifierSha256": config.verifier_graph_sha256s[direct_index],
        },
        "contract": {
            "hopSamples": args.hop_samples,
            "endpointAliases": sorted(aliases),
            "retrySpeedFactors": list(config.direct_lexical_retry_speed_factors),
            "hotwordsScore": config.direct_lexical_hotwords_score,
            "policy": args.policy,
            "endpointDirectScoreGte": endpoint_direct_score_gte,
            "phoneticConfusionScoreGte": (
                config.direct_lexical_phonetic_confusion_score_gte
            ),
            "commandSuffixAffectsDecision": False,
            "ambiguousPronunciationsExcluded": [
                "basi",
                "basic",
                "they see",
                "vas y",
            ],
        },
        "corpusManifestSha256": room._sha256(source_manifest),
        "positive": positive,
        "negative": negative,
        "elapsedWallSeconds": time.perf_counter() - started,
        "candidateFrozen": False,
        "developmentOnly": True,
        "promotable": False,
        "blindHumanPartitionAccessed": False,
        "effectsExecuted": 0,
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
                "positive": f"{positive['hits']}/{positive['files']}",
                "negativeFalseActivations": f"{negative['hits']}/{negative['files']}",
                "totalP95Seconds": positive["runtimeSeconds"]["totalP95"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
