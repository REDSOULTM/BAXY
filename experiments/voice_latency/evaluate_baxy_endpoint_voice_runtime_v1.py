"""Exercise BAXY's production endpoint-wake decoder on opened RAW audio.

Unlike the policy evaluator, this probe calls ``VoiceEngine._decode_utterance``
with the real Parakeet recognizer and the real manifest-bound cascade scorer.
Microphone segmentation is covered separately by deterministic runtime tests;
this development probe performs no effects and never promotes a candidate.
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
for path in (ROOT / "src", Path(__file__).resolve().parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_lexical_wake_physical_room_gate_v1 as lexical  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind.voice import VoiceEngine  # noqa: E402
from baxy_mind.wake_cascade import (  # noqa: E402
    SAMPLE_RATE,
    HyperspotterCascadeDetector,
    load_wake_cascade_candidate_config,
)


SCHEMA = "baxy.endpoint-voice-runtime-development.v1"


def _measure_group(
    paths: list[Path],
    *,
    engine: VoiceEngine,
    delivered: list[str],
    events: list[dict[str, Any]],
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    elapsed: list[float] = []
    audio_seconds = 0.0
    for index, path in enumerate(paths):
        audio, rate = room._read_pcm16(path)
        audio = room._resample(audio, rate, SAMPLE_RATE)
        audio_seconds += len(audio) / SAMPLE_RATE
        delivered_before = len(delivered)
        events_before = len(events)
        with engine._lock:  # noqa: SLF001 - isolated development probe
            engine._armed_until = 0.0  # noqa: SLF001
        started = time.perf_counter()
        engine._decode_utterance(  # noqa: SLF001 - production boundary under test
            audio,
            np.empty(0, dtype=np.int16),
            "endpoint_wake_candidate",
        )
        wall_seconds = time.perf_counter() - started
        elapsed.append(wall_seconds)
        new_events = events[events_before:]
        wake_events = [
            event for event in new_events if event.get("event") == "wake_detected"
        ]
        recognized = next(
            (event for event in new_events if event.get("event") == "recognized"),
            None,
        )
        ignored = next(
            (
                event
                for event in reversed(new_events)
                if event.get("event") == "ignored"
            ),
            None,
        )
        new_text = delivered[delivered_before:]
        wake_event = wake_events[-1] if wake_events else {}
        records.append(
            {
                "record": index,
                "audioSha256": room._sha256(path),
                "hit": bool(wake_events),
                "commandDelivered": bool(new_text),
                "commandSha256": (
                    hashlib.sha256(new_text[-1].encode("utf-8")).hexdigest()
                    if new_text
                    else None
                ),
                "method": wake_event.get("method"),
                "verifierScore": wake_event.get("verifierScore"),
                "ignoredReason": ignored.get("reason") if ignored else None,
                "recognizedSeconds": (
                    recognized.get("seconds") if recognized is not None else None
                ),
                "wallSeconds": wall_seconds,
            }
        )
    hits = sum(bool(record["hit"]) for record in records)
    return {
        "files": len(records),
        "hits": hits,
        "rate": hits / len(records),
        "audioSeconds": audio_seconds,
        "runtimeSeconds": {
            "wallP50": room._percentile(elapsed, 0.50),
            "wallP95": room._percentile(elapsed, 0.95),
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
    return parser


def main() -> int:
    args = _parser().parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists.")
    corpus = args.corpus.resolve(strict=True)
    corpus_manifest = corpus / "manifest.v1.json"
    source = json.loads(corpus_manifest.read_text(encoding="utf-8"))
    if source.get("physicalPath", {}).get("captureTransport") != (
        "wasapi_raw_iaudioclient2"
    ):
        raise SystemExit("Corpus is not an attested RAW physical capture.")

    manifest = args.cascade_manifest.resolve(strict=True)
    config = load_wake_cascade_candidate_config(manifest)
    if (
        config.endpoint_lexical_verifier_index is None
        or config.endpoint_lexical_score_threshold is None
    ):
        raise SystemExit("Cascade has no endpoint lexical proposal.")
    recognizer, hotwords = lexical._recognizer(
        args.stt_directory.resolve(strict=True),
        config.direct_lexical_hotwords_score,
    )
    detector = HyperspotterCascadeDetector(config)
    delivered: list[str] = []
    events: list[dict[str, Any]] = []
    engine = VoiceEngine(delivered.append, events.append)
    engine._recognizer = recognizer  # noqa: SLF001 - development runtime binding
    engine._stt_directory = args.stt_directory.resolve()  # noqa: SLF001
    engine._wake_hotwords = hotwords  # noqa: SLF001
    engine._wake_cascade_config = config  # noqa: SLF001
    engine._acoustic_wake_detector = detector  # noqa: SLF001
    engine._wake_backend = "acoustic"  # noqa: SLF001
    engine._wake_model_name = "baxy-hyperspotter-logmel-cascade-v1"  # noqa: SLF001
    engine._mode = "wake"  # noqa: SLF001
    engine.speak = lambda _text: True  # type: ignore[method-assign]

    started = time.perf_counter()
    positive = _measure_group(
        room._wav_paths(corpus / "positive", None),
        engine=engine,
        delivered=delivered,
        events=events,
    )
    negative = _measure_group(
        room._wav_paths(corpus / "negative", None),
        engine=engine,
        delivered=delivered,
        events=events,
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_wasapi_raw_production_voice_endpoint_development",
        "assets": {
            "cascadeManifestSha256": room._sha256(manifest),
            "sttDirectory": args.stt_directory.resolve().name,
        },
        "contract": {
            "origin": "endpoint_wake_candidate",
            "endpointDirectScoreGte": config.endpoint_lexical_score_threshold,
            "endpointAliases": sorted(config.endpoint_lexical_aliases),
            "retrySpeedFactors": list(config.endpoint_lexical_retry_speed_factors),
            "ttsSuppressed": True,
        },
        "corpusManifestSha256": room._sha256(corpus_manifest),
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
                "wallP95Seconds": positive["runtimeSeconds"]["wallP95"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
