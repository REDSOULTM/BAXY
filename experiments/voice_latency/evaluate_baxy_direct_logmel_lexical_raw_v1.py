"""Evaluate direct log-Mel and literal-ASR wake policies on opened RAW audio."""

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

import run_lexical_wake_physical_room_gate_v1 as lexical  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind.wake_cascade import (  # noqa: E402
    LOGMEL_BINS,
    SAMPLE_RATE,
    WINDOW_SAMPLES,
    has_strict_leading_alias,
    load_wake_cascade_candidate_config,
    numpy_log_mel_spectrogram,
)


SCHEMA = "baxy.direct-logmel-lexical-raw-development.v1"
CURRENT_ALIASES = frozenset(("baxy", "baxi", "boxy"))
EXPANDED_ALIASES = frozenset(("baxy", "baxi", "basi", "boxy", "backsy"))


def stream_windows(audio: np.ndarray, hop_samples: int) -> list[np.ndarray]:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if values.size < 1 or hop_samples < 1 or hop_samples > WINDOW_SAMPLES:
        raise ValueError("direct_logmel_window_invalid")
    padded = np.pad(values, (SAMPLE_RATE, SAMPLE_RATE))
    if len(padded) < WINDOW_SAMPLES:
        padded = np.pad(padded, (0, WINDOW_SAMPLES - len(padded)))
    starts = list(range(0, len(padded) - WINDOW_SAMPLES + 1, hop_samples))
    final = len(padded) - WINDOW_SAMPLES
    if starts[-1] != final:
        starts.append(final)
    return [
        np.ascontiguousarray(padded[start : start + WINDOW_SAMPLES])
        for start in starts
    ]


def summarize(records: list[dict[str, object]], policy: str) -> dict[str, object]:
    hits = sum(bool(record[policy]) for record in records)
    return {"hits": hits, "files": len(records), "rate": hits / len(records)}


def _session(path: Path) -> Any:
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    return ort.InferenceSession(
        str(path), sess_options=options, providers=["CPUExecutionProvider"]
    )


def _measure_group(
    paths: list[Path],
    *,
    mel_filters: np.ndarray,
    verifier: Any,
    threshold: float,
    recognizer: Any,
    contextual_hotwords: str,
    hop_samples: int,
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    logmel_seconds: list[float] = []
    baseline_seconds: list[float] = []
    contextual_seconds: list[float] = []
    for index, path in enumerate(paths):
        audio, rate = room._read_pcm16(path)
        audio = room._resample(audio, rate, SAMPLE_RATE)
        started = time.perf_counter()
        features = np.stack(
            [
                numpy_log_mel_spectrogram(window, mel_filters)
                for window in stream_windows(audio, hop_samples)
            ]
        ).astype(np.float32)
        scores = np.asarray(
            verifier.run(["wake_logit"], {"logmel": features})[0],
            dtype=np.float32,
        ).reshape(-1)
        logmel_seconds.append(time.perf_counter() - started)
        if scores.size != len(features) or not np.isfinite(scores).all():
            raise ValueError("direct_logmel_score_invalid")
        direct_score = float(np.max(scores))
        direct = direct_score >= threshold

        baseline, baseline_latency = lexical._decode(recognizer, audio)
        contextual, contextual_latency = lexical._decode(
            recognizer, audio, hotwords=contextual_hotwords
        )
        baseline_seconds.append(baseline_latency)
        contextual_seconds.append(contextual_latency)
        lexical_current_baseline = has_strict_leading_alias(
            baseline, CURRENT_ALIASES
        )
        lexical_expanded_baseline = has_strict_leading_alias(
            baseline, EXPANDED_ALIASES
        )
        lexical_current_contextual = has_strict_leading_alias(
            contextual, CURRENT_ALIASES
        )
        lexical_expanded_contextual = has_strict_leading_alias(
            contextual, EXPANDED_ALIASES
        )
        records.append(
            {
                "record": index,
                "audioSha256": room._sha256(path),
                "directScore": direct_score,
                "directLogmel": direct,
                "lexicalCurrentBaseline": lexical_current_baseline,
                "lexicalExpandedBaseline": lexical_expanded_baseline,
                "lexicalCurrentContextual": lexical_current_contextual,
                "lexicalExpandedContextual": lexical_expanded_contextual,
                "directAndLexicalExpandedBaseline": (
                    direct and lexical_expanded_baseline
                ),
                "directOrLexicalExpandedBaseline": (
                    direct or lexical_expanded_baseline
                ),
                "baselineTranscriptSha256": hashlib.sha256(
                    baseline.encode("utf-8")
                ).hexdigest(),
                "contextualTranscriptSha256": hashlib.sha256(
                    contextual.encode("utf-8")
                ).hexdigest(),
            }
        )
    policies = (
        "directLogmel",
        "lexicalCurrentBaseline",
        "lexicalExpandedBaseline",
        "lexicalCurrentContextual",
        "lexicalExpandedContextual",
        "directAndLexicalExpandedBaseline",
        "directOrLexicalExpandedBaseline",
    )
    return {
        "files": len(records),
        "policies": {policy: summarize(records, policy) for policy in policies},
        "directScore": {
            "minimum": float(min(record["directScore"] for record in records)),
            "p50": float(
                np.quantile(
                    [float(record["directScore"]) for record in records], 0.5
                )
            ),
            "maximum": float(max(record["directScore"] for record in records)),
        },
        "runtimeSeconds": {
            "directLogmelP50": room._percentile(logmel_seconds, 0.50),
            "directLogmelP95": room._percentile(logmel_seconds, 0.95),
            "lexicalBaselineP50": room._percentile(baseline_seconds, 0.50),
            "lexicalBaselineP95": room._percentile(baseline_seconds, 0.95),
            "lexicalContextualP50": room._percentile(contextual_seconds, 0.50),
            "lexicalContextualP95": room._percentile(contextual_seconds, 0.95),
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
    return parser


def main() -> int:
    args = _parser().parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists.")
    corpus = args.corpus.resolve(strict=True)
    source_manifest = corpus / "manifest.v1.json"
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    if source.get("physicalPath", {}).get("captureTransport") != "wasapi_raw_iaudioclient2":
        raise SystemExit("Corpus is not an attested RAW physical capture.")
    cascade_manifest = args.cascade_manifest.resolve(strict=True)
    config = load_wake_cascade_candidate_config(cascade_manifest)
    mel_filters = np.asarray(
        np.load(config.mel_filters_path, allow_pickle=False), dtype=np.float32
    )
    if mel_filters.shape != (LOGMEL_BINS, 201):
        raise ValueError("direct_logmel_filter_invalid")
    verifier = _session(config.verifier_graph_path)
    recognizer, contextual_hotwords = lexical._recognizer(
        args.stt_directory.resolve(strict=True), 5.0
    )
    started = time.perf_counter()
    positive = _measure_group(
        room._wav_paths(corpus / "positive", None),
        mel_filters=mel_filters,
        verifier=verifier,
        threshold=config.verifier_threshold,
        recognizer=recognizer,
        contextual_hotwords=contextual_hotwords,
        hop_samples=args.hop_samples,
    )
    negative = _measure_group(
        room._wav_paths(corpus / "negative", None),
        mel_filters=mel_filters,
        verifier=verifier,
        threshold=config.verifier_threshold,
        recognizer=recognizer,
        contextual_hotwords=contextual_hotwords,
        hop_samples=args.hop_samples,
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_wasapi_raw_architecture_diagnosis",
        "assets": {
            "cascadeManifestSha256": room._sha256(cascade_manifest),
            "logmelVerifierSha256": config.verifier_graph_sha256,
            "sttFilesSha256": {
                name: room._sha256(args.stt_directory.resolve() / name)
                for name in (
                    "encoder.int8.onnx",
                    "decoder.int8.onnx",
                    "joiner.int8.onnx",
                    "tokens.txt",
                )
            },
        },
        "contract": {
            "windowSamples": WINDOW_SAMPLES,
            "hopSamples": args.hop_samples,
            "verifierScoreGte": config.verifier_threshold,
            "currentAliases": sorted(CURRENT_ALIASES),
            "expandedAliases": sorted(EXPANDED_ALIASES),
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
                "positive": positive["policies"],
                "negative": negative["policies"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
