"""Evaluate sherpa-onnx open-vocabulary KWS on opened RAW room audio."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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

import run_wakeword_physical_room_gate as room  # noqa: E402


SCHEMA = "baxy.sherpa-open-vocab-kws-raw-development.v1"
SAMPLE_RATE = 16_000
TAIL_PADDING_SECONDS = 0.66


def decode_keyword(kws: Any, audio: np.ndarray) -> tuple[bool, float | None]:
    """Decode one independent clip and return the first keyword endpoint."""

    stream = kws.create_stream()
    stream.accept_waveform(SAMPLE_RATE, np.asarray(audio, dtype=np.float32))
    stream.accept_waveform(
        SAMPLE_RATE,
        np.zeros(round(TAIL_PADDING_SECONDS * SAMPLE_RATE), dtype=np.float32),
    )
    stream.input_finished()
    while kws.is_ready(stream):
        kws.decode_stream(stream)
        if kws.get_result(stream):
            timestamps = kws.timestamps(stream)
            return True, float(timestamps[-1]) if timestamps else None
    return False, None


def _measure_group(paths: list[Path], *, kws: Any) -> dict[str, object]:
    records: list[dict[str, object]] = []
    latencies: list[float] = []
    endpoint_seconds: list[float] = []
    audio_seconds = 0.0
    for index, path in enumerate(paths):
        audio, rate = room._read_pcm16(path)
        audio = room._resample(audio, rate, SAMPLE_RATE)
        audio_seconds += len(audio) / SAMPLE_RATE
        started = time.perf_counter()
        hit, endpoint = decode_keyword(kws, audio)
        latencies.append(time.perf_counter() - started)
        if endpoint is not None:
            endpoint_seconds.append(endpoint)
        records.append(
            {
                "record": index,
                "audioSha256": room._sha256(path),
                "hit": hit,
                "keywordEndpointSeconds": endpoint,
            }
        )
    hits = sum(bool(record["hit"]) for record in records)
    return {
        "files": len(records),
        "hits": hits,
        "rate": hits / len(records),
        "audioSeconds": audio_seconds,
        "runtimeSeconds": {
            "p50": room._percentile(latencies, 0.50),
            "p95": room._percentile(latencies, 0.95),
        },
        "keywordEndpointSeconds": {
            "p50": room._percentile(endpoint_seconds, 0.50),
            "p95": room._percentile(endpoint_seconds, 0.95),
        },
        "records": records,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokens", type=Path, required=True)
    parser.add_argument("--encoder", type=Path, required=True)
    parser.add_argument("--decoder", type=Path, required=True)
    parser.add_argument("--joiner", type=Path, required=True)
    parser.add_argument("--keywords-file", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--num-threads", type=int, default=2)
    parser.add_argument("--max-active-paths", type=int, default=4)
    parser.add_argument("--keywords-score", type=float, default=1.0)
    parser.add_argument("--keywords-threshold", type=float, default=0.25)
    parser.add_argument("--num-trailing-blanks", type=int, default=1)
    return parser


def main() -> int:
    args = _parser().parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists.")
    if (
        args.num_threads < 1
        or args.max_active_paths < 1
        or not 0.0 < args.keywords_threshold <= 1.0
        or args.num_trailing_blanks < 1
        or not np.isfinite(args.keywords_score)
    ):
        raise SystemExit("Invalid KWS operating point.")
    assets = {
        name: path.resolve(strict=True)
        for name, path in {
            "tokens": args.tokens,
            "encoder": args.encoder,
            "decoder": args.decoder,
            "joiner": args.joiner,
            "keywords": args.keywords_file,
        }.items()
    }
    corpus = args.corpus.resolve(strict=True)
    source_manifest = corpus / "manifest.v1.json"
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    if source.get("physicalPath", {}).get("captureTransport") != (
        "wasapi_raw_iaudioclient2"
    ):
        raise SystemExit("Corpus is not an attested RAW physical capture.")

    import sherpa_onnx

    kws = sherpa_onnx.KeywordSpotter(
        tokens=str(assets["tokens"]),
        encoder=str(assets["encoder"]),
        decoder=str(assets["decoder"]),
        joiner=str(assets["joiner"]),
        keywords_file=str(assets["keywords"]),
        num_threads=args.num_threads,
        max_active_paths=args.max_active_paths,
        keywords_score=args.keywords_score,
        keywords_threshold=args.keywords_threshold,
        num_trailing_blanks=args.num_trailing_blanks,
        provider="cpu",
    )
    started = time.perf_counter()
    positive = _measure_group(
        room._wav_paths(corpus / "positive", None),
        kws=kws,
    )
    negative = _measure_group(
        room._wav_paths(corpus / "negative", None),
        kws=kws,
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_wasapi_raw_open_vocabulary_kws_development",
        "assets": {
            f"{name}Sha256": room._sha256(path) for name, path in assets.items()
        },
        "contract": {
            "sampleRate": SAMPLE_RATE,
            "tailPaddingSeconds": TAIL_PADDING_SECONDS,
            "numThreads": args.num_threads,
            "maxActivePaths": args.max_active_paths,
            "keywordsScore": args.keywords_score,
            "keywordsThreshold": args.keywords_threshold,
            "numTrailingBlanks": args.num_trailing_blanks,
            "commandSuffixAffectsDecision": False,
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
                "runtimeP95Seconds": positive["runtimeSeconds"]["p95"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
