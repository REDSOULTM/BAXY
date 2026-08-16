"""Measure literal Parakeet wake-prefix matching through the physical room.

This development gate exercises the existing lexical fallback architecture:
VAD supplies a bounded utterance, offline Parakeet decodes it locally, and a
closed prefix matcher grants wake authority only when the first lexical token
is the configured name.  Captured audio, filenames, and transcript text are
not retained.  The gate compares exact ``Baxy`` with the current Baxy/Baxi
protocol alias policy; neither arm is promoted from this opened smoke.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import wave
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind.voice import (  # noqa: E402
    WakePhraseMatcher,
    _compile_contextual_hotwords,
)


REPORT_SCHEMA = "baxy.lexical-wake-physical-room-development.v1"
SAMPLE_RATE = 16_000


def match_policies(transcript: str) -> dict[str, bool]:
    exact, _ = WakePhraseMatcher({"baxy"}).strip(transcript)
    protocol, _ = WakePhraseMatcher({"baxy", "baxi"}).strip(transcript)
    return {"exactBaxy": exact, "baxyBaxiProtocol": protocol}


def _recognizer(stt_directory: Path, hotwords_score: float) -> tuple[Any, str]:
    import sherpa_onnx

    required = {
        "encoder": stt_directory / "encoder.int8.onnx",
        "decoder": stt_directory / "decoder.int8.onnx",
        "joiner": stt_directory / "joiner.int8.onnx",
        "tokens": stt_directory / "tokens.txt",
    }
    if any(not path.is_file() for path in required.values()):
        raise ValueError("lexical_wake_stt_bundle_incomplete")
    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(required["encoder"]),
        decoder=str(required["decoder"]),
        joiner=str(required["joiner"]),
        tokens=str(required["tokens"]),
        num_threads=4,
        model_type="nemo_transducer",
        decoding_method="modified_beam_search",
        max_active_paths=8,
        hotwords_score=hotwords_score,
    )
    hotwords = _compile_contextual_hotwords(
        stt_directory / "tokens.txt",
        ("baxy", "baxi"),
    )
    if not hotwords:
        raise ValueError("lexical_wake_hotword_encoding_failed")
    return recognizer, hotwords


def _decode(
    recognizer: Any,
    audio: np.ndarray,
    *,
    hotwords: str | None = None,
) -> tuple[str, float]:
    stream = (
        recognizer.create_stream(hotwords=hotwords)
        if hotwords
        else recognizer.create_stream()
    )
    stream.accept_waveform(SAMPLE_RATE, np.asarray(audio, dtype=np.float32))
    started = time.perf_counter()
    recognizer.decode_stream(stream)
    return (stream.result.text or "").strip(), time.perf_counter() - started


def _measure_group(
    *,
    paths: list[Path],
    recognizer: Any,
    contextual_hotwords: str,
    sounddevice: Any,
    input_device: int | str,
    output_device: int | str,
    hardware_rate: int,
    gain: float,
    pre_roll_seconds: float,
    post_roll_seconds: float,
    minimum_correlation: float,
    minimum_snr_db: float,
) -> dict[str, Any]:
    pre_samples = round(pre_roll_seconds * hardware_rate)
    post_samples = round(post_roll_seconds * hardware_rate)
    invalid = 0
    invalid_reasons: Counter[str] = Counter()
    correlations: list[float] = []
    snrs: list[float] = []
    latencies: list[float] = []
    policy_hits: Counter[str] = Counter()
    transcript_hashes: list[str] = []
    source_seconds = 0.0
    for path in paths:
        try:
            source, source_rate = room._read_pcm16(path)
            source_seconds += source.size / source_rate
            played = room._resample(source, source_rate, hardware_rate)
            peak = float(np.max(np.abs(played))) if played.size else 0.0
            if peak <= 1e-7:
                raise ValueError("source_silent")
            played = np.clip(played * (gain / peak), -0.98, 0.98)
            playback = np.pad(played, (pre_samples, post_samples)).astype(
                np.float32
            )
            captured = sounddevice.playrec(
                playback.reshape(-1, 1),
                samplerate=hardware_rate,
                channels=1,
                dtype="float32",
                device=(input_device, output_device),
                blocking=True,
            )
            captured = np.asarray(captured, dtype=np.float32).reshape(-1)
            noise = captured[:pre_samples]
            noise_rms = float(
                np.sqrt(np.mean(np.square(noise), dtype=np.float64))
            )
            captured_rms = float(
                np.sqrt(np.mean(np.square(captured), dtype=np.float64))
            )
            snr_db = 20.0 * math.log10(
                max(captured_rms, 1e-9) / max(noise_rms, 1e-9)
            )
            correlation = room.normalized_delay_correlation(captured, played)
            correlations.append(correlation)
            snrs.append(snr_db)
            if correlation < minimum_correlation or snr_db < minimum_snr_db:
                invalid += 1
                if correlation < minimum_correlation:
                    invalid_reasons["path_correlation_below_floor"] += 1
                if snr_db < minimum_snr_db:
                    invalid_reasons["captured_snr_below_floor"] += 1
            captured_16k = room._resample(captured, hardware_rate, SAMPLE_RATE)
            for arm, hotwords in (
                ("baseline", None),
                ("contextual", contextual_hotwords),
            ):
                transcript, latency = _decode(
                    recognizer,
                    captured_16k,
                    hotwords=hotwords,
                )
                latencies.append(latency)
                transcript_hashes.append(
                    hashlib.sha256(
                        f"{arm}:{transcript}".encode("utf-8")
                    ).hexdigest()
                )
                for policy, matched in match_policies(transcript).items():
                    if matched:
                        policy_hits[f"{arm}:{policy}"] += 1
        except (OSError, RuntimeError, ValueError, wave.Error) as error:
            invalid += 1
            invalid_reasons[type(error).__name__] += 1
    return {
        "files": len(paths),
        "audioSeconds": source_seconds,
        "invalidAcousticPaths": invalid,
        "invalidReasonCounts": dict(sorted(invalid_reasons.items())),
        "pathCorrelationP05": room._percentile(correlations, 0.05),
        "pathCorrelationP50": room._percentile(correlations, 0.50),
        "capturedSnrDbP05": room._percentile(snrs, 0.05),
        "capturedSnrDbP50": room._percentile(snrs, 0.50),
        "decodeSecondsP50": room._percentile(latencies, 0.50),
        "decodeSecondsP95": room._percentile(latencies, 0.95),
        "policyMatches": dict(policy_hits),
        "transcriptSha256": transcript_hashes,
        "transcriptTextRetained": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-output", action="store_true")
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--negative", type=Path, required=True)
    parser.add_argument("--positive-limit", type=room._positive_int)
    parser.add_argument("--negative-limit", type=room._positive_int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input-device", type=room._device, required=True)
    parser.add_argument("--output-device", type=room._device, required=True)
    parser.add_argument("--gain", type=room._finite_float, default=0.25)
    parser.add_argument("--hotwords-score", type=room._finite_float, default=5.0)
    parser.add_argument("--pre-roll-seconds", type=room._finite_float, default=0.5)
    parser.add_argument("--post-roll-seconds", type=room._finite_float, default=0.75)
    parser.add_argument(
        "--minimum-path-correlation", type=room._finite_float, default=0.02
    )
    parser.add_argument(
        "--minimum-captured-snr-db", type=room._finite_float, default=3.0
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.physical_output:
        raise SystemExit("Refusing acoustic playback without --physical-output.")
    if not 0.01 <= args.gain <= 0.95:
        raise SystemExit("--gain must be between 0.01 and 0.95.")
    output_path = args.output.resolve()
    if output_path.exists():
        raise SystemExit("Output already exists.")
    stt_directory = args.stt_directory.resolve(strict=True)
    positive_root = args.positive.resolve(strict=True)
    negative_root = args.negative.resolve(strict=True)
    positives = room._wav_paths(positive_root, args.positive_limit)
    negatives = room._wav_paths(negative_root, args.negative_limit)
    if not positives or not negatives:
        raise SystemExit("Both physical corpus groups require WAV files.")
    if not 0.1 <= args.hotwords_score <= 20.0:
        raise SystemExit("--hotwords-score must be between 0.1 and 20.0.")
    recognizer, contextual_hotwords = _recognizer(
        stt_directory,
        args.hotwords_score,
    )
    import sounddevice as sd

    hardware_rate = room._resolve_hardware_rate(
        sd,
        args.input_device,
        args.output_device,
    )
    input_info = sd.query_devices(args.input_device, "input")
    output_info = sd.query_devices(args.output_device, "output")
    started = time.perf_counter()
    positive = _measure_group(
        paths=positives,
        recognizer=recognizer,
        contextual_hotwords=contextual_hotwords,
        sounddevice=sd,
        input_device=args.input_device,
        output_device=args.output_device,
        hardware_rate=hardware_rate,
        gain=args.gain,
        pre_roll_seconds=args.pre_roll_seconds,
        post_roll_seconds=args.post_roll_seconds,
        minimum_correlation=args.minimum_path_correlation,
        minimum_snr_db=args.minimum_captured_snr_db,
    )
    negative = _measure_group(
        paths=negatives,
        recognizer=recognizer,
        contextual_hotwords=contextual_hotwords,
        sounddevice=sd,
        input_device=args.input_device,
        output_device=args.output_device,
        hardware_rate=hardware_rate,
        gain=args.gain,
        pre_roll_seconds=args.pre_roll_seconds,
        post_roll_seconds=args.post_roll_seconds,
        minimum_correlation=args.minimum_path_correlation,
        minimum_snr_db=args.minimum_captured_snr_db,
    )
    policies: dict[str, dict[str, float | int | bool]] = {}
    for policy in (
        "baseline:exactBaxy",
        "baseline:baxyBaxiProtocol",
        "contextual:exactBaxy",
        "contextual:baxyBaxiProtocol",
    ):
        positive_hits = int(positive["policyMatches"].get(policy, 0))
        negative_hits = int(negative["policyMatches"].get(policy, 0))
        policies[policy] = {
            "positiveHits": positive_hits,
            "positiveTotal": len(positives),
            "recall": positive_hits / len(positives),
            "negativeFalseActivations": negative_hits,
            "negativeTotal": len(negatives),
            "smokePassed": positive_hits == len(positives)
            and negative_hits == 0
            and positive["invalidAcousticPaths"] == 0
            and negative["invalidAcousticPaths"] == 0,
        }
    report = {
        "schema": REPORT_SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_human_literal_parakeet_physical_room_development",
        "stt": {
            "backend": "sherpa-onnx-parakeet-tdt-offline-int8",
            "bundleSha256": {
                name: room._sha256(stt_directory / name)
                for name in (
                    "encoder.int8.onnx",
                    "decoder.int8.onnx",
                    "joiner.int8.onnx",
                    "tokens.txt",
                )
            },
            "contextualHotwordsSha256": hashlib.sha256(
                contextual_hotwords.encode("utf-8")
            ).hexdigest(),
            "contextualHotwordsScore": args.hotwords_score,
        },
        "physicalPath": {
            "topology": "explicit speaker -> room -> explicit microphone",
            "inputDevice": str(input_info["name"]),
            "outputDevice": str(output_info["name"]),
            "hardwareSampleRate": hardware_rate,
            "playbackGain": args.gain,
            "capturedAudioRetained": False,
        },
        "corpus": {
            "positiveSha256": room._corpus_sha256(positives, positive_root),
            "negativeSha256": room._corpus_sha256(negatives, negative_root),
            "filenamesOrTranscriptsRetained": False,
        },
        "positive": positive,
        "negative": negative,
        "policies": policies,
        "elapsedWallSeconds": time.perf_counter() - started,
        "developmentOnly": True,
        "promotable": False,
        "promotionBlockedBy": [
            "opened_development_corpus",
            "insufficient_positive_population",
            "insufficient_negative_exposure",
            "blind_multispeaker_physical_holdout_not_run",
        ],
        "effectsExecuted": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(policies, sort_keys=True))
    return 0 if any(policy["smokePassed"] for policy in policies.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
