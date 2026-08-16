"""Measure multilingual Nemotron lexical wake evidence through the room.

This opened-development gate evaluates a materially different wake-word
architecture: VAD-bounded speech is decoded by the already packaged
cache-aware Nemotron streaming ASR in both automatic-language and English
arms.  The strict arm only accepts a closed first-token wake vocabulary.  A
second, explicitly non-authoritative diagnostic arm searches the whole clip
for common ASR renderings so real clips where the brand occurs mid-sentence
can still reveal whether the acoustic evidence survived speaker -> room ->
microphone playback.

Captured audio, filenames, and transcript text are never retained.  This gate
cannot promote a model: it uses an opened corpus and the broad diagnostic arm
is not an authority policy.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
import wave
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind.voice import WakePhraseMatcher, _fold  # noqa: E402


REPORT_SCHEMA = "baxy.nemotron-lexical-wake-physical-room-development.v1"
SAMPLE_RATE = 16_000
DEFAULT_LANGUAGES = ("auto", "en")
_WORD = re.compile(r"[^\W_]+", flags=re.UNICODE)
_STRICT_ALIASES = frozenset(
    {
        "baxy",
        "baxi",
        "baksi",
        "backsy",
        "backsie",
        "basi",
        "bokse",
        "боксе",
    }
)
_DIAGNOSTIC_EXACT = _STRICT_ALIASES | {"basic", "basir"}


def lexical_policies(transcripts: Iterable[str]) -> dict[str, bool]:
    """Return strict authority and opened-corpus diagnostic evidence."""

    strict_matcher = WakePhraseMatcher(set(_STRICT_ALIASES))
    strict_prefix = False
    diagnostic_anywhere = False
    for transcript in transcripts:
        matched, _ = strict_matcher.strip(transcript)
        strict_prefix = strict_prefix or matched
        words = tuple(_fold(match.group(0)) for match in _WORD.finditer(transcript))
        diagnostic_anywhere = diagnostic_anywhere or any(
            word in _DIAGNOSTIC_EXACT
            or (word.startswith("baxi") and len(word) <= 7)
            for word in words
        )
    return {
        "strictClosedPrefix": strict_prefix,
        "openedDiagnosticAnywhere": diagnostic_anywhere,
    }


def _recognizer(stt_directory: Path, threads: int) -> Any:
    import sherpa_onnx

    required = {
        "encoder": stt_directory / "encoder.int8.onnx",
        "decoder": stt_directory / "decoder.int8.onnx",
        "joiner": stt_directory / "joiner.int8.onnx",
        "tokens": stt_directory / "tokens.txt",
    }
    if any(not path.is_file() for path in required.values()):
        raise ValueError("nemotron_lexical_wake_stt_bundle_incomplete")
    return sherpa_onnx.OnlineRecognizer.from_transducer(
        encoder=str(required["encoder"]),
        decoder=str(required["decoder"]),
        joiner=str(required["joiner"]),
        tokens=str(required["tokens"]),
        num_threads=threads,
        model_type="nemo_transducer",
        decoding_method="greedy_search",
        enable_endpoint_detection=False,
        provider="cpu",
    )


def _decode(recognizer: Any, audio: np.ndarray, language: str) -> tuple[str, float]:
    stream = recognizer.create_stream()
    stream.set_option("language", language)
    stream.accept_waveform(SAMPLE_RATE, np.asarray(audio, dtype=np.float32))
    stream.input_finished()
    started = time.perf_counter()
    while recognizer.is_ready(stream):
        recognizer.decode_stream(stream)
    result = recognizer.get_result_all(stream)
    return str(getattr(result, "text", "") or "").strip(), time.perf_counter() - started


def condition_vad_bounded_audio(
    audio: np.ndarray,
    *,
    noise_samples: int,
    frame_samples: int = 320,
    padding_samples: int = 4_000,
) -> tuple[np.ndarray, dict[str, float]]:
    """Approximate the product VAD boundary and normalize microphone level.

    The physical gate records fixed pre/post-roll to prove the acoustic path,
    while the proposed runtime feeds Nemotron only a VAD-bounded utterance.
    This deterministic energy boundary removes the gate-only padding.  A
    capped peak normalization compensates for Windows microphone gain without
    manufacturing evidence from silence.
    """

    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if values.size < frame_samples or noise_samples < frame_samples:
        raise ValueError("nemotron_physical_audio_too_short")
    values = values - float(np.mean(values[:noise_samples], dtype=np.float64))
    noise = values[:noise_samples]
    noise_rms = float(np.sqrt(np.mean(np.square(noise), dtype=np.float64)))
    frame_count = values.size // frame_samples
    framed = values[: frame_count * frame_samples].reshape(frame_count, frame_samples)
    frame_rms = np.sqrt(np.mean(np.square(framed), axis=1, dtype=np.float64))
    threshold = max(noise_rms * 2.5, 1e-5)
    active = np.flatnonzero(frame_rms >= threshold)
    if active.size:
        start = max(0, int(active[0]) * frame_samples - padding_samples)
        end = min(
            values.size,
            (int(active[-1]) + 1) * frame_samples + padding_samples,
        )
        bounded = values[start:end]
    else:
        start = 0
        end = values.size
        bounded = values
    robust_peak = float(np.percentile(np.abs(bounded), 99.5)) if bounded.size else 0.0
    if robust_peak <= 1e-7:
        raise ValueError("nemotron_physical_audio_silent")
    gain = min(20.0, 0.55 / robust_peak)
    conditioned = np.clip(bounded * gain, -0.98, 0.98).astype(np.float32)
    return conditioned, {
        "conditioningGain": gain,
        "inputRobustPeak": robust_peak,
        "retainedFraction": bounded.size / values.size,
        "energyThreshold": threshold,
        "boundaryStartSeconds": start / SAMPLE_RATE,
        "boundaryEndSeconds": end / SAMPLE_RATE,
    }


def _measure_group(
    *,
    paths: list[Path],
    recognizer: Any,
    languages: tuple[str, ...],
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
    decode_latencies: list[float] = []
    ensemble_latencies: list[float] = []
    policy_hits: Counter[str] = Counter()
    language_policy_hits: Counter[str] = Counter()
    transcript_hashes: list[str] = []
    conditioning_gains: list[float] = []
    retained_fractions: list[float] = []
    input_peaks: list[float] = []
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
            playback = np.pad(played, (pre_samples, post_samples)).astype(np.float32)
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
            noise_rms = float(np.sqrt(np.mean(np.square(noise), dtype=np.float64)))
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
            conditioned, conditioning = condition_vad_bounded_audio(
                captured_16k,
                noise_samples=round(pre_roll_seconds * SAMPLE_RATE),
            )
            conditioning_gains.append(conditioning["conditioningGain"])
            retained_fractions.append(conditioning["retainedFraction"])
            input_peaks.append(conditioning["inputRobustPeak"])
            transcripts: list[str] = []
            ensemble_started = time.perf_counter()
            for language in languages:
                transcript, latency = _decode(recognizer, conditioned, language)
                transcripts.append(transcript)
                decode_latencies.append(latency)
                transcript_hashes.append(
                    hashlib.sha256(
                        f"{language}:{transcript}".encode("utf-8")
                    ).hexdigest()
                )
                for policy, matched in lexical_policies((transcript,)).items():
                    if matched:
                        language_policy_hits[f"{language}:{policy}"] += 1
            ensemble_latencies.append(time.perf_counter() - ensemble_started)
            for policy, matched in lexical_policies(transcripts).items():
                if matched:
                    policy_hits[policy] += 1
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
        "decodeSecondsP50": room._percentile(decode_latencies, 0.50),
        "decodeSecondsP95": room._percentile(decode_latencies, 0.95),
        "ensembleSecondsP50": room._percentile(ensemble_latencies, 0.50),
        "ensembleSecondsP95": room._percentile(ensemble_latencies, 0.95),
        "conditioningGainP50": room._percentile(conditioning_gains, 0.50),
        "retainedAudioFractionP50": room._percentile(retained_fractions, 0.50),
        "inputRobustPeakP50": room._percentile(input_peaks, 0.50),
        "policyMatches": dict(policy_hits),
        "languagePolicyMatches": dict(language_policy_hits),
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
    parser.add_argument("--threads", type=room._positive_int, default=6)
    parser.add_argument(
        "--languages",
        default=",".join(DEFAULT_LANGUAGES),
        help="Comma-separated Nemotron language prompts.",
    )
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
    languages = tuple(
        dict.fromkeys(item.strip() for item in args.languages.split(",") if item.strip())
    )
    if not languages or any(not re.fullmatch(r"[a-z]{2,4}|auto", item) for item in languages):
        raise SystemExit("--languages must contain language IDs or auto.")
    stt_directory = args.stt_directory.resolve(strict=True)
    positive_root = args.positive.resolve(strict=True)
    negative_root = args.negative.resolve(strict=True)
    positives = room._wav_paths(positive_root, args.positive_limit)
    negatives = room._wav_paths(negative_root, args.negative_limit)
    if not positives or not negatives:
        raise SystemExit("Both physical corpus groups require WAV files.")
    recognizer = _recognizer(stt_directory, args.threads)
    import sounddevice as sd

    hardware_rate = room._resolve_hardware_rate(
        sd, args.input_device, args.output_device
    )
    input_info = sd.query_devices(args.input_device, "input")
    output_info = sd.query_devices(args.output_device, "output")
    started = time.perf_counter()
    common = {
        "recognizer": recognizer,
        "languages": languages,
        "sounddevice": sd,
        "input_device": args.input_device,
        "output_device": args.output_device,
        "hardware_rate": hardware_rate,
        "gain": args.gain,
        "pre_roll_seconds": args.pre_roll_seconds,
        "post_roll_seconds": args.post_roll_seconds,
        "minimum_correlation": args.minimum_path_correlation,
        "minimum_snr_db": args.minimum_captured_snr_db,
    }
    positive = _measure_group(paths=positives, **common)
    negative = _measure_group(paths=negatives, **common)
    policies: dict[str, dict[str, float | int | bool]] = {}
    for policy in ("strictClosedPrefix", "openedDiagnosticAnywhere"):
        positive_hits = int(positive["policyMatches"].get(policy, 0))
        negative_hits = int(negative["policyMatches"].get(policy, 0))
        policies[policy] = {
            "positiveHits": positive_hits,
            "positiveTotal": len(positives),
            "recall": positive_hits / len(positives),
            "negativeFalseActivations": negative_hits,
            "negativeTotal": len(negatives),
            "acousticSmokePassed": positive_hits == len(positives)
            and negative_hits == 0
            and positive["invalidAcousticPaths"] == 0
            and negative["invalidAcousticPaths"] == 0,
            "authorityEligible": policy == "strictClosedPrefix",
        }
    report = {
        "schema": REPORT_SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_human_nemotron_multilingual_physical_room_development",
        "architecture": "vad_bounded_nemotron_auto_en_lexical_ensemble",
        "stt": {
            "backend": "sherpa-onnx-nemotron-3.5-streaming-int8",
            "languages": languages,
            "threads": args.threads,
            "bundleSha256": {
                name: room._sha256(stt_directory / name)
                for name in (
                    "encoder.int8.onnx",
                    "decoder.int8.onnx",
                    "joiner.int8.onnx",
                    "tokens.txt",
                )
            },
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
            "diagnostic_anywhere_policy_not_authority",
            "insufficient_positive_population",
            "insufficient_negative_exposure",
            "blind_multispeaker_physical_holdout_not_run",
            "continuous_vad_runtime_not_integrated_or_profiled",
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
    return 0 if any(policy["acousticSmokePassed"] for policy in policies.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
