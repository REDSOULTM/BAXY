"""Evaluate a candidate BAXY wake model through speaker -> room -> microphone.

The gate plays existing positive and negative WAVs on one explicit output
device, records one explicit input device, and sends only that captured signal
through the product ``AcousticWakeDetector``.  Captured audio, transcripts and
file names are never written.  ``--physical-output`` is required so this
cannot make sound accidentally from CI or an ordinary source gate.

The generated report intentionally uses ``baxy-wake-corpus-gate-v3`` so a
fully sufficient passing physical corpus can be consumed by
``install_baxy_wake_model.ps1``.  Development smokes remain non-promotable
whenever corpus size, acoustic-path evidence, FRR or exact Poisson FAR fails.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from baxy_mind.wakeword import (  # noqa: E402
    CALIBRATION_REPORT_SCHEMA,
    DEFAULT_DEBOUNCE_S,
    DEFAULT_HOP_SAMPLES,
    SAMPLE_RATE,
    WINDOW_SAMPLES,
    AcousticWakeDetector,
    WakeWordModelConfig,
)

from evaluate_wake_corpus import (  # noqa: E402
    minimum_zero_event_hours_for_far,
    one_sided_poisson_upper_rate_per_hour,
)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("value must be finite")
    return parsed


def _device(value: str) -> int | str:
    stripped = value.strip()
    try:
        return int(stripped)
    except ValueError:
        return stripped


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _corpus_sha256(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(_sha256(path)))
    return digest.hexdigest()


def _wav_paths(directory: Path, limit: int | None) -> list[Path]:
    paths = sorted(path for path in directory.rglob("*.wav") if path.is_file())
    return paths[:limit] if limit is not None else paths


def _read_pcm16(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as source:
        if source.getsampwidth() != 2:
            raise ValueError("wav_not_pcm16")
        sample_rate = source.getframerate()
        channels = source.getnchannels()
        audio = np.frombuffer(source.readframes(source.getnframes()), dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return audio.astype(np.float32) / 32768.0, sample_rate


def _resample(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return np.asarray(audio, dtype=np.float32)
    from scipy.signal import resample_poly

    divisor = math.gcd(source_rate, target_rate)
    return resample_poly(
        audio,
        target_rate // divisor,
        source_rate // divisor,
    ).astype(np.float32)


def normalized_delay_correlation(captured: np.ndarray, reference: np.ndarray) -> float:
    """Maximum normalized correlation, allowing arbitrary acoustic delay."""

    from scipy.signal import correlate

    captured64 = np.asarray(captured, dtype=np.float64).reshape(-1)
    reference64 = np.asarray(reference, dtype=np.float64).reshape(-1)
    if reference64.size == 0 or captured64.size < reference64.size:
        return 0.0
    reference64 -= reference64.mean()
    captured64 -= captured64.mean()
    reference_energy = float(np.dot(reference64, reference64))
    if reference_energy <= 1e-12:
        return 0.0
    numerator = correlate(captured64, reference64, mode="valid", method="fft")
    squared = np.square(captured64)
    cumulative = np.concatenate(([0.0], np.cumsum(squared)))
    window_energy = cumulative[reference64.size :] - cumulative[: -reference64.size]
    denominator = np.sqrt(np.maximum(window_energy * reference_energy, 1e-24))
    return float(np.clip(np.max(np.abs(numerator) / denominator), 0.0, 1.0))


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return float(ordered[round((len(ordered) - 1) * fraction)])


def _resolve_hardware_rate(
    sounddevice: Any,
    input_device: int | str,
    output_device: int | str,
) -> int:
    input_info = sounddevice.query_devices(input_device, "input")
    output_info = sounddevice.query_devices(output_device, "output")
    candidates: list[int] = []
    for value in (
        input_info["default_samplerate"],
        output_info["default_samplerate"],
        48_000,
        44_100,
        16_000,
    ):
        rate = int(round(float(value)))
        if rate not in candidates:
            candidates.append(rate)
    for rate in candidates:
        try:
            sounddevice.check_input_settings(
                device=input_device,
                channels=1,
                dtype="float32",
                samplerate=rate,
            )
            sounddevice.check_output_settings(
                device=output_device,
                channels=1,
                dtype="float32",
                samplerate=rate,
            )
        except Exception:  # noqa: BLE001 - PortAudio exposes backend-specific types
            continue
        return rate
    raise RuntimeError("no_common_physical_sample_rate")


def _score_recording(
    detector: AcousticWakeDetector,
    captured: np.ndarray,
    timeline: float,
) -> tuple[int, float | None, list[float], list[float]]:
    detector.reset()
    replay = np.asarray(captured, dtype=np.float32).reshape(-1)
    required_window = int(
        getattr(
            detector,
            "window_samples",
            getattr(getattr(detector, "config", None), "window_samples", WINDOW_SAMPLES),
        )
    )
    if required_window < 1:
        raise ValueError("wake_detector_window_invalid")
    if replay.size < required_window:
        replay = np.pad(replay, (0, required_window - replay.size))
    hits = 0
    first_hit: float | None = None
    prediction_seconds: list[float] = []
    scores: list[float] = []
    for offset in range(0, replay.size, 512):
        frame = replay[offset : offset + 512]
        frame_end = (offset + frame.size) / SAMPLE_RATE
        hit = detector.accept(frame, now=timeline + frame_end)
        if detector.scored_last_frame and detector.last_prediction_seconds is not None:
            prediction_seconds.append(detector.last_prediction_seconds)
            raw_score = getattr(detector, "last_score", None)
            if isinstance(raw_score, (int, float)) and math.isfinite(raw_score):
                scores.append(float(raw_score))
        if hit is not None:
            hits += 1
            if first_hit is None:
                first_hit = max(0.0, hit.timestamp - timeline)
    return hits, first_hit, prediction_seconds, scores


def _measure_group(
    *,
    paths: list[Path],
    detector: AcousticWakeDetector,
    sounddevice: Any,
    input_device: int | str,
    output_device: int | str,
    hardware_rate: int,
    gain: float,
    pre_roll_seconds: float,
    post_roll_seconds: float,
    minimum_correlation: float,
    minimum_snr_db: float,
    timeline: float,
) -> tuple[dict[str, Any], float]:
    matched_files = 0
    activations = 0
    invalid = 0
    source_seconds = 0.0
    correlations: list[float] = []
    snr_values: list[float] = []
    activation_seconds: list[float] = []
    prediction_seconds: list[float] = []
    scores: list[float] = []
    invalid_reasons: Counter[str] = Counter()
    pre_samples = round(pre_roll_seconds * hardware_rate)
    post_samples = round(post_roll_seconds * hardware_rate)

    for path in paths:
        try:
            source, source_rate = _read_pcm16(path)
            source_seconds += source.size / source_rate
            played = _resample(source, source_rate, hardware_rate)
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
            capture_rms = float(np.sqrt(np.mean(np.square(captured), dtype=np.float64)))
            snr_db = 20.0 * math.log10(max(capture_rms, 1e-9) / max(noise_rms, 1e-9))
            correlation = normalized_delay_correlation(captured, played)
            correlations.append(correlation)
            snr_values.append(snr_db)
            if correlation < minimum_correlation or snr_db < minimum_snr_db:
                invalid += 1
                if correlation < minimum_correlation:
                    invalid_reasons["path_correlation_below_floor"] += 1
                if snr_db < minimum_snr_db:
                    invalid_reasons["captured_snr_below_floor"] += 1

            captured_16k = _resample(captured, hardware_rate, SAMPLE_RATE)
            hits, first_hit, latencies, observed_scores = _score_recording(
                detector,
                captured_16k,
                timeline,
            )
            activations += hits
            if first_hit is not None:
                matched_files += 1
                activation_seconds.append(first_hit)
            prediction_seconds.extend(latencies)
            scores.extend(observed_scores)
            timeline += source.size / source_rate + detector.config.debounce_seconds
        except (OSError, RuntimeError, ValueError, wave.Error) as error:
            invalid += 1
            invalid_reasons[type(error).__name__] += 1

    return {
        "files": len(paths),
        "invalid_acoustic_paths": invalid,
        "invalid_reason_counts": dict(sorted(invalid_reasons.items())),
        "matched_files": matched_files,
        "activations": activations,
        "audio_seconds": source_seconds,
        "path_correlation_p05": _percentile(correlations, 0.05),
        "path_correlation_p50": _percentile(correlations, 0.50),
        "captured_snr_db_p05": _percentile(snr_values, 0.05),
        "captured_snr_db_p50": _percentile(snr_values, 0.50),
        "activation_p50_seconds": _percentile(activation_seconds, 0.50),
        "activation_p95_seconds": _percentile(activation_seconds, 0.95),
        "prediction_p50_seconds": _percentile(prediction_seconds, 0.50),
        "prediction_p95_seconds": _percentile(prediction_seconds, 0.95),
        "score_p05": _percentile(scores, 0.05),
        "score_p50": _percentile(scores, 0.50),
        "score_p95": _percentile(scores, 0.95),
        "score_maximum": max(scores) if scores else None,
    }, timeline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-output", action="store_true")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--phrase", default="Baxy")
    parser.add_argument("--threshold", type=_finite_float, required=True)
    parser.add_argument(
        "--hop-samples", type=_positive_int, default=DEFAULT_HOP_SAMPLES
    )
    parser.add_argument(
        "--debounce-seconds",
        type=_finite_float,
        default=DEFAULT_DEBOUNCE_S,
    )
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--negative", type=Path, required=True)
    parser.add_argument("--positive-limit", type=_positive_int)
    parser.add_argument("--negative-limit", type=_positive_int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input-device", type=_device, required=True)
    parser.add_argument("--output-device", type=_device, required=True)
    parser.add_argument("--gain", type=_finite_float, default=0.65)
    parser.add_argument("--pre-roll-seconds", type=_finite_float, default=0.5)
    parser.add_argument("--post-roll-seconds", type=_finite_float, default=0.75)
    parser.add_argument("--minimum-path-correlation", type=_finite_float, default=0.02)
    parser.add_argument("--minimum-captured-snr-db", type=_finite_float, default=3.0)
    parser.add_argument("--minimum-positive", type=_positive_int, default=200)
    parser.add_argument("--minimum-negative-hours", type=_finite_float, default=30.0)
    parser.add_argument("--maximum-false-reject-rate", type=_finite_float, default=0.05)
    parser.add_argument(
        "--maximum-false-activations-per-hour",
        type=_finite_float,
        default=0.1,
    )
    parser.add_argument("--far-confidence", type=_finite_float, default=0.95)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.physical_output:
        raise SystemExit("Refusing acoustic playback without --physical-output.")
    if not 0.001 <= args.threshold <= 0.999:
        raise SystemExit("--threshold must be between 0.001 and 0.999.")
    if not 0.01 <= args.gain <= 0.95:
        raise SystemExit("--gain must be between 0.01 and 0.95.")
    if args.pre_roll_seconds <= 0.0 or args.post_roll_seconds <= 0.0:
        raise SystemExit("pre/post roll must be positive.")
    if not 0.0 <= args.maximum_false_reject_rate <= 0.05:
        raise SystemExit("maximum FRR must be between 0 and 0.05.")
    if not 0.0 < args.maximum_false_activations_per_hour <= 0.1:
        raise SystemExit("maximum FAR must be between 0 and 0.1/h.")
    if not 0.95 <= args.far_confidence < 1.0:
        raise SystemExit("FAR confidence must be in [0.95, 1).")

    model_path = args.model.resolve(strict=True)
    positive_root = args.positive.resolve(strict=True)
    negative_root = args.negative.resolve(strict=True)
    positive_paths = _wav_paths(positive_root, args.positive_limit)
    negative_paths = _wav_paths(negative_root, args.negative_limit)
    if not positive_paths or not negative_paths:
        raise SystemExit("Both physical corpus groups require WAV files.")

    import sounddevice as sd

    model_hash = _sha256(model_path)
    config = WakeWordModelConfig(
        manifest_path=model_path.parent / "candidate-physical-gate.json",
        model_path=model_path,
        model_name=args.model_name,
        phrase=args.phrase,
        threshold=args.threshold,
        hop_samples=args.hop_samples,
        debounce_seconds=args.debounce_seconds,
        model_sha256=model_hash,
        calibration={},
    )
    detector = AcousticWakeDetector(config)
    hardware_rate = _resolve_hardware_rate(
        sd,
        args.input_device,
        args.output_device,
    )
    input_info = sd.query_devices(args.input_device, "input")
    output_info = sd.query_devices(args.output_device, "output")
    started = time.perf_counter()
    positives, timeline = _measure_group(
        paths=positive_paths,
        detector=detector,
        sounddevice=sd,
        input_device=args.input_device,
        output_device=args.output_device,
        hardware_rate=hardware_rate,
        gain=args.gain,
        pre_roll_seconds=args.pre_roll_seconds,
        post_roll_seconds=args.post_roll_seconds,
        minimum_correlation=args.minimum_path_correlation,
        minimum_snr_db=args.minimum_captured_snr_db,
        timeline=0.0,
    )
    negatives, _ = _measure_group(
        paths=negative_paths,
        detector=detector,
        sounddevice=sd,
        input_device=args.input_device,
        output_device=args.output_device,
        hardware_rate=hardware_rate,
        gain=args.gain,
        pre_roll_seconds=args.pre_roll_seconds,
        post_roll_seconds=args.post_roll_seconds,
        minimum_correlation=args.minimum_path_correlation,
        minimum_snr_db=args.minimum_captured_snr_db,
        timeline=timeline,
    )
    positive_files = int(positives["files"])
    negative_seconds = float(negatives["audio_seconds"])
    negative_hours = negative_seconds / 3600.0
    recall = int(positives["matched_files"]) / positive_files
    false_reject_rate = 1.0 - recall
    false_activations = int(negatives["activations"])
    observed_far = false_activations / negative_hours if negative_hours else None
    far_upper = one_sided_poisson_upper_rate_per_hour(
        false_activations,
        negative_seconds,
        args.far_confidence,
    )
    zero_event_hours = minimum_zero_event_hours_for_far(
        args.maximum_false_activations_per_hour,
        args.far_confidence,
    )
    effective_negative_hours = max(args.minimum_negative_hours, zero_event_hours)
    corpus_sufficient = (
        positive_files >= args.minimum_positive
        and negative_hours >= effective_negative_hours
        and int(positives["invalid_acoustic_paths"]) == 0
        and int(negatives["invalid_acoustic_paths"]) == 0
    )
    promotable = (
        corpus_sufficient
        and false_reject_rate <= args.maximum_false_reject_rate
        and far_upper is not None
        and far_upper <= args.maximum_false_activations_per_hour
    )
    report = {
        "schema": CALIBRATION_REPORT_SCHEMA,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "mode": "acoustic",
        "model": {
            "backend": detector.backend,
            "architecture": "Product AcousticWakeDetector over physical microphone capture",
            "model": config.model_name,
            "phrase": config.phrase,
            "sample_rate": SAMPLE_RATE,
            "window_samples": WINDOW_SAMPLES,
            "threshold": config.threshold,
            "hop_samples": config.hop_samples,
            "debounce_seconds": config.debounce_seconds,
            "model_sha256": model_hash,
        },
        "physical_path": {
            "topology": "explicit speaker -> room -> explicit microphone",
            "input_device": str(input_info["name"]),
            "output_device": str(output_info["name"]),
            "hardware_sample_rate": hardware_rate,
            "playback_gain": args.gain,
            "minimum_path_correlation": args.minimum_path_correlation,
            "minimum_captured_snr_db": args.minimum_captured_snr_db,
            "captured_audio_retained": False,
        },
        "corpus": {
            "selection": "sorted unique source WAVs; no repetition",
            "positive_sha256": _corpus_sha256(positive_paths, positive_root),
            "negative_sha256": _corpus_sha256(negative_paths, negative_root),
            "filenames_or_transcripts_retained": False,
        },
        "positive": positives,
        "negative": negatives,
        "recall": recall,
        "false_reject_rate": false_reject_rate,
        "false_activations_per_hour": observed_far,
        "far": {
            "method": "poisson_one_sided_upper_exact",
            "confidence": args.far_confidence,
            "observed_activations": false_activations,
            "exposure_hours": negative_hours,
            "observed_per_hour": observed_far,
            "upper_confidence_per_hour": far_upper,
        },
        "minimum_positive": args.minimum_positive,
        "minimum_negative_hours": args.minimum_negative_hours,
        "minimum_zero_event_hours_for_far": zero_event_hours,
        "effective_minimum_negative_hours": effective_negative_hours,
        "corpus_sufficient": corpus_sufficient,
        "promotion_criteria": {
            "mode": "acoustic",
            "false_reject_rate_lte": args.maximum_false_reject_rate,
            "false_activations_per_hour_lte": args.maximum_false_activations_per_hour,
            "far_confidence_gte": args.far_confidence,
        },
        "elapsed_wall_seconds": time.perf_counter() - started,
        "promotable": promotable,
        "privacy": "no captured audio, filename, or transcript is written to this report",
        "effects_executed": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if promotable else 2


if __name__ == "__main__":
    raise SystemExit(main())
