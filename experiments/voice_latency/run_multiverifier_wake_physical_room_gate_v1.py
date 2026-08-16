"""Evaluate the frozen temporal/phonetic wake cascade through the room.

The candidate accepts strong HyperSpotter+CTC evidence directly. Weaker
evidence requires agreement from LiveKit and Wav2Vec2 QByT in one of the first
two product windows, enforcing the product contract that the wake name is an
utterance prefix. Captured audio and transcript text are never retained.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time
import wave

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (ROOT / "src", ROOT / "scripts", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import capture_controlled_physical_wake_corpus_v1 as capture  # noqa: E402
import run_hyperspotter_fusion_physical_room_gate_v1 as hyper  # noqa: E402
import run_qbyt_physical_room_gate_v1 as qbyt  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind.wakeword import AcousticWakeDetector, WakeWordModelConfig  # noqa: E402


SCHEMA = "baxy.multiverifier-wake-physical-room-development.v1"
SAMPLE_RATE = 16_000
STRONG_FUSION_MARGIN = -3.0
LIVEKIT_SCORE = 0.05
QBYT_MARGIN = -0.02
EARLY_PEAK_MAXIMUM_INDEX = 1


def multiverifier_decision(
    *,
    fusion_margin: float,
    livekit_score: float,
    qbyt_margin: float,
    livekit_peak_index: int,
) -> tuple[bool, str]:
    values = (fusion_margin, livekit_score, qbyt_margin)
    if not all(math.isfinite(value) for value in values) or livekit_peak_index < 0:
        raise ValueError("multiverifier_wake_evidence_invalid")
    if fusion_margin >= STRONG_FUSION_MARGIN:
        return True, "strong_phonetic_fusion"
    if (
        livekit_score >= LIVEKIT_SCORE
        and qbyt_margin >= QBYT_MARGIN
        and livekit_peak_index <= EARLY_PEAK_MAXIMUM_INDEX
    ):
        return True, "early_acoustic_phonetic_consensus"
    return False, "insufficient_consensus"


def fixed_three_second_audio(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    required = 3 * SAMPLE_RATE
    if values.size < required:
        values = np.pad(values, (0, required - values.size))
    return values[:required].astype(np.float32)


def _measure_group(
    *,
    paths: list[Path],
    livekit: AcousticWakeDetector,
    fusion: hyper.HyperspotterFusionDetector,
    query: qbyt.QbyTPhysicalDetector,
    sounddevice: object,
    input_device: int | str,
    output_device: int | str,
    hardware_rate: int,
    gain: float,
    pre_roll_seconds: float,
    post_roll_seconds: float,
    minimum_correlation: float,
    minimum_snr_db: float,
) -> dict[str, object]:
    pre_samples = round(pre_roll_seconds * hardware_rate)
    post_samples = round(post_roll_seconds * hardware_rate)
    invalid = 0
    invalid_reasons: Counter[str] = Counter()
    decisions = 0
    reasons: Counter[str] = Counter()
    correlations: list[float] = []
    snrs: list[float] = []
    latencies: list[float] = []
    livekit_scores: list[float] = []
    fusion_margins: list[float] = []
    qbyt_margins: list[float] = []
    peak_indices: list[int] = []
    source_seconds = 0.0
    for path in paths:
        try:
            source, source_rate = room._read_pcm16(path)
            source_seconds += source.size / source_rate
            played = room._resample(source, source_rate, hardware_rate)
            peak = float(np.max(np.abs(played))) if played.size else 0.0
            if peak <= 1e-7:
                raise ValueError("multiverifier_source_silent")
            played = np.clip(played * (gain / peak), -0.98, 0.98)
            playback = np.pad(played, (pre_samples, post_samples)).astype(np.float32)
            captured = capture.play_and_record(
                sounddevice,
                playback,
                sample_rate=hardware_rate,
                input_device=input_device,
                output_device=output_device,
            )
            captured = np.asarray(captured, dtype=np.float32).reshape(-1)
            noise_rms = float(
                np.sqrt(np.mean(np.square(captured[:pre_samples]), dtype=np.float64))
            )
            capture_rms = float(
                np.sqrt(np.mean(np.square(captured), dtype=np.float64))
            )
            snr_db = 20.0 * math.log10(
                max(capture_rms, 1e-9) / max(noise_rms, 1e-9)
            )
            aligned, correlation, _ = capture.align_known_playback(captured, played)
            correlations.append(correlation)
            snrs.append(snr_db)
            if correlation < minimum_correlation or snr_db < minimum_snr_db:
                invalid += 1
                if correlation < minimum_correlation:
                    invalid_reasons["path_correlation_below_floor"] += 1
                if snr_db < minimum_snr_db:
                    invalid_reasons["captured_snr_below_floor"] += 1
            aligned_16k = room._resample(aligned, hardware_rate, SAMPLE_RATE)
            conditioned, _ = capture.normalize_training_capture(aligned_16k)
            started = time.perf_counter()
            _, _, _, raw_livekit_scores = room._score_recording(
                livekit, conditioned, 0.0
            )
            if not raw_livekit_scores:
                raise ValueError("multiverifier_livekit_scores_empty")
            score_array = np.asarray(raw_livekit_scores, dtype=np.float64)
            livekit_score = float(np.max(score_array))
            peak_index = int(np.argmax(score_array))
            fixed = fixed_three_second_audio(conditioned)
            fusion_margin = float(fusion._score(fixed))
            query_margin = float(query._score(fixed))
            accepted, reason = multiverifier_decision(
                fusion_margin=fusion_margin,
                livekit_score=livekit_score,
                qbyt_margin=query_margin,
                livekit_peak_index=peak_index,
            )
            latencies.append(time.perf_counter() - started)
            livekit_scores.append(livekit_score)
            fusion_margins.append(fusion_margin)
            qbyt_margins.append(query_margin)
            peak_indices.append(peak_index)
            reasons[reason] += 1
            decisions += int(accepted)
        except (OSError, RuntimeError, ValueError, wave.Error) as error:
            invalid += 1
            invalid_reasons[type(error).__name__] += 1
    return {
        "files": len(paths),
        "audioSeconds": source_seconds,
        "acceptedFiles": decisions,
        "rejectedFiles": len(paths) - decisions,
        "decisionReasons": dict(sorted(reasons.items())),
        "invalidAcousticPaths": invalid,
        "invalidReasonCounts": dict(sorted(invalid_reasons.items())),
        "pathCorrelationP05": room._percentile(correlations, 0.05),
        "pathCorrelationP50": room._percentile(correlations, 0.50),
        "capturedSnrDbP05": room._percentile(snrs, 0.05),
        "capturedSnrDbP50": room._percentile(snrs, 0.50),
        "decisionSecondsP50": room._percentile(latencies, 0.50),
        "decisionSecondsP95": room._percentile(latencies, 0.95),
        "livekitScoreP50": room._percentile(livekit_scores, 0.50),
        "livekitScoreMaximum": max(livekit_scores) if livekit_scores else None,
        "fusionMarginP50": room._percentile(fusion_margins, 0.50),
        "fusionMarginMaximum": max(fusion_margins) if fusion_margins else None,
        "qbytMarginP50": room._percentile(qbyt_margins, 0.50),
        "qbytMarginMaximum": max(qbyt_margins) if qbyt_margins else None,
        "livekitPeakIndexMaximum": max(peak_indices) if peak_indices else None,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-output", action="store_true")
    parser.add_argument("--livekit-model", type=Path, required=True)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--qbyt-candidate", type=Path, required=True)
    parser.add_argument("--wav2vec2-model-directory", type=Path, required=True)
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--negative", type=Path, required=True)
    parser.add_argument("--positive-limit", type=room._positive_int)
    parser.add_argument("--negative-limit", type=room._positive_int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input-device", type=room._device, required=True)
    parser.add_argument("--output-device", type=room._device, required=True)
    parser.add_argument("--gain", type=room._finite_float, default=0.25)
    parser.add_argument("--pre-roll-seconds", type=room._finite_float, default=0.25)
    parser.add_argument("--post-roll-seconds", type=room._finite_float, default=0.5)
    parser.add_argument("--minimum-path-correlation", type=room._finite_float, default=0.02)
    parser.add_argument("--minimum-captured-snr-db", type=room._finite_float, default=3.0)
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
    livekit_path = args.livekit_model.resolve(strict=True)
    livekit = AcousticWakeDetector(
        WakeWordModelConfig(
            manifest_path=livekit_path.parent / "multiverifier-candidate.json",
            model_path=livekit_path,
            model_name="baxy-physicalmultialigned-v10",
            phrase="Baxy",
            threshold=LIVEKIT_SCORE,
            hop_samples=4_000,
            debounce_seconds=2.0,
            model_sha256=room._sha256(livekit_path),
            calibration={},
        )
    )
    fusion = hyper.HyperspotterFusionDetector(
        fusion_manifest_path=args.fusion_manifest,
        ctc_manifest_path=args.ctc_verifier_manifest,
        model_name="baxy-hyperspotter-ctc-v2",
        phrase="Baxy",
        hop_samples=8_000,
        debounce_seconds=2.0,
        threads=4,
    )
    query = qbyt.QbyTPhysicalDetector(
        candidate_path=args.qbyt_candidate,
        model_directory=args.wav2vec2_model_directory,
        model_name="baxy-qbyt-rir-v3",
        phrase="Baxy",
        hop_samples=8_000,
        debounce_seconds=2.0,
        device="cuda",
    )
    positive_root = args.positive.resolve(strict=True)
    negative_root = args.negative.resolve(strict=True)
    positive_paths = room._wav_paths(positive_root, args.positive_limit)
    negative_paths = room._wav_paths(negative_root, args.negative_limit)
    import sounddevice as sd

    hardware_rate = room._resolve_hardware_rate(sd, args.input_device, args.output_device)
    common = {
        "livekit": livekit,
        "fusion": fusion,
        "query": query,
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
    started = time.perf_counter()
    positives = _measure_group(paths=positive_paths, **common)
    negatives = _measure_group(paths=negative_paths, **common)
    passed = (
        positives["acceptedFiles"] == positives["files"]
        and negatives["acceptedFiles"] == 0
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_development_temporal_phonetic_cascade_physical_room",
        "policy": {
            "strongFusionMarginGte": STRONG_FUSION_MARGIN,
            "livekitScoreGte": LIVEKIT_SCORE,
            "qbytMarginGte": QBYT_MARGIN,
            "earlyPeakMaximumIndex": EARLY_PEAK_MAXIMUM_INDEX,
            "weakBranch": "livekit_and_qbyt_and_utterance_prefix",
        },
        "models": {
            "livekitSha256": room._sha256(livekit_path),
            "fusion": fusion.source_identities,
            "qbyt": query.source_identities,
        },
        "physicalPath": {
            "inputDevice": str(sd.query_devices(args.input_device, "input")["name"]),
            "outputDevice": str(sd.query_devices(args.output_device, "output")["name"]),
            "hardwareSampleRate": hardware_rate,
            "playbackGain": args.gain,
            "capturedAudioRetained": False,
        },
        "corpus": {
            "positiveSha256": room._corpus_sha256(positive_paths, positive_root),
            "negativeSha256": room._corpus_sha256(negative_paths, negative_root),
            "filenamesOrTranscriptsRetained": False,
        },
        "positive": positives,
        "negative": negatives,
        "elapsedWallSeconds": time.perf_counter() - started,
        "openedDevelopmentPassed": passed,
        "candidateFrozen": passed,
        "blindHumanPartitionAccessed": False,
        "promotable": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"passed": passed, "positive": positives["acceptedFiles"], "negative": negatives["acceptedFiles"]}))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
