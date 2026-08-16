"""Evalúa el KWS acústico de BAXY sin guardar audio, nombres ni texto.

El modo predeterminado mide la arquitectura de producto:

    WAV 16 kHz -> LiveKit WakeWord ONNX -> score/umbral -> activación

El modo --mode lexical existe solo para comparar la ruta de transición antigua
(VAD/STT/prefijo); no aprueba ni sustituye un modelo wake-word acústico.

El corpus debe separarse antes de ejecutar el script:

* --positive: frases que contienen la activación objetivo.
* --negative: habla, TV, música, TTS de BAXY y ruido que no deben activar
  BAXY.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from baxy_mind.voice import SAMPLE_RATE, VoiceEngine, WakePhraseMatcher  # noqa: E402
from baxy_mind.wakeword import (  # noqa: E402
    CALIBRATION_REPORT_SCHEMA,
    WINDOW_SAMPLES,
    AcousticWakeDetector,
    WakeWordRuntimeError,
    load_wakeword_config,
)


_MINIMUM_FAR_CONFIDENCE = 0.95


def _wav_paths(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*.wav") if path.is_file())


def _read_wave(path: Path) -> tuple[np.ndarray, float]:
    with wave.open(str(path), "rb") as source:
        if source.getsampwidth() != 2:
            raise ValueError("wav_not_pcm16")
        sample_rate = source.getframerate()
        channels = source.getnchannels()
        audio = np.frombuffer(source.readframes(source.getnframes()), dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1).astype(np.int16)
    normalized = audio.astype(np.float32) / 32768.0
    if sample_rate != SAMPLE_RATE:
        from scipy.signal import resample_poly

        normalized = resample_poly(normalized, SAMPLE_RATE, sample_rate).astype(np.float32)
    return normalized, len(normalized) / SAMPLE_RATE


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
    return round(ordered[index], 3)


def _regularized_gamma_q(shape: float, value: float) -> float:
    """Regularized upper incomplete gamma, implemented without SciPy.

    For an integer shape ``k + 1`` this is exactly ``P(Poisson(value) <= k)``.
    The evaluator needs that CDF to calculate a one-sided exact Poisson upper
    confidence bound without treating sparse false activations as zero risk.
    """

    if shape <= 0.0 or value < 0.0 or not math.isfinite(shape) or not math.isfinite(value):
        raise ValueError("invalid_gamma_arguments")
    if value == 0.0:
        return 1.0
    epsilon = 3.0e-14
    tiny = 1.0e-300
    maximum_iterations = 10_000
    log_factor = -value + shape * math.log(value) - math.lgamma(shape)
    if value < shape + 1.0:
        # Series for P(a, x); Q = 1 - P in this numerically favorable region.
        term = total = 1.0 / shape
        denominator = shape
        for _ in range(maximum_iterations):
            denominator += 1.0
            term *= value / denominator
            total += term
            if abs(term) <= abs(total) * epsilon:
                return max(0.0, min(1.0, 1.0 - total * math.exp(log_factor)))
        raise RuntimeError("gamma_series_nonconvergent")
    # Continued fraction for Q(a, x), stable in the upper tail.
    b = value + 1.0 - shape
    c = 1.0 / tiny
    d = 1.0 / max(abs(b), tiny) * (1.0 if b >= 0.0 else -1.0)
    fraction = d
    for index in range(1, maximum_iterations + 1):
        numerator = -index * (index - shape)
        b += 2.0
        d = numerator * d + b
        if abs(d) < tiny:
            d = tiny if d >= 0.0 else -tiny
        c = b + numerator / c
        if abs(c) < tiny:
            c = tiny if c >= 0.0 else -tiny
        d = 1.0 / d
        delta = d * c
        fraction *= delta
        if abs(delta - 1.0) <= epsilon:
            return max(0.0, min(1.0, math.exp(log_factor) * fraction))
    raise RuntimeError("gamma_fraction_nonconvergent")


def one_sided_poisson_upper_rate_per_hour(
    activations: int,
    exposure_seconds: float,
    confidence: float,
) -> float | None:
    """Exact one-sided Poisson upper rate, not a point-estimate FAR.

    It solves ``P(X <= observed | lambda_upper * exposure) = 1-confidence``.
    With no false hits at 95% confidence this remains ``-ln(.05)/hours``;
    consequently five quiet hours cannot substantiate a 0.1 FPPH claim.
    """

    if (
        isinstance(activations, bool)
        or not isinstance(activations, int)
        or activations < 0
        or not math.isfinite(exposure_seconds)
        or exposure_seconds <= 0.0
    ):
        return None
    if not math.isfinite(confidence) or not 0.0 < confidence < 1.0:
        return None
    tail_probability = 1.0 - confidence
    if activations == 0:
        upper_mean = -math.log(tail_probability)
    else:
        # The CDF monotonically decreases with the Poisson mean.  Doubling
        # gives a reliable bracket even for a noisy corpus; bisection avoids a
        # dependency on a stats package that may differ from the voice runtime.
        lower = 0.0
        upper = max(1.0, float(activations) + 8.0 * math.sqrt(float(activations) + 1.0))
        while _regularized_gamma_q(float(activations + 1), upper) > tail_probability:
            upper *= 2.0
            if upper > 1.0e12:
                raise RuntimeError("poisson_upper_bound_unbracketed")
        for _ in range(100):
            midpoint = (lower + upper) / 2.0
            if _regularized_gamma_q(float(activations + 1), midpoint) > tail_probability:
                lower = midpoint
            else:
                upper = midpoint
        upper_mean = upper
    return upper_mean * 3600.0 / exposure_seconds


def minimum_zero_event_hours_for_far(target_per_hour: float, confidence: float) -> float:
    """Minimum duration needed for a zero-hit one-sided FAR assertion."""

    if (
        not math.isfinite(target_per_hour)
        or not math.isfinite(confidence)
        or target_per_hour <= 0.0
        or not 0.0 < confidence < 1.0
    ):
        raise ValueError("invalid_far_target")
    return -math.log(1.0 - confidence) / target_per_hour


def _evaluate_acoustic_group(
    detector: AcousticWakeDetector,
    paths: list[Path],
    timeline: float,
) -> tuple[dict[str, float | int | None], float]:
    """Replay clips frame-wise, preserving KWS debounce as in live capture."""

    matched_files = 0
    activations = 0
    invalid = 0
    seconds = 0.0
    wall_latencies: list[float] = []
    prediction_latencies: list[float] = []
    activation_latencies: list[float] = []
    for path in paths:
        try:
            audio, duration = _read_wave(path)
            detector.reset()
            file_start = timeline
            # A short positive clip still needs the frontend's 2 s context.
            replay = audio
            if replay.size < WINDOW_SAMPLES:
                replay = np.pad(replay, (0, WINDOW_SAMPLES - replay.size))
            first_hit: float | None = None
            started = time.perf_counter()
            for offset in range(0, replay.size, 512):
                frame = replay[offset : offset + 512]
                frame_end = min(duration, (offset + frame.size) / SAMPLE_RATE)
                hit = detector.accept(frame, now=file_start + frame_end)
                if detector.scored_last_frame and detector.last_prediction_seconds is not None:
                    prediction_latencies.append(detector.last_prediction_seconds)
                if hit is not None:
                    activations += 1
                    if first_hit is None:
                        first_hit = max(0.0, hit.timestamp - file_start)
            wall_latencies.append(time.perf_counter() - started)
            if first_hit is not None:
                matched_files += 1
                activation_latencies.append(first_hit)
            seconds += duration
            # Separate source clips are independent examples. Preserve a
            # realistic gap so debounce from one file does not suppress its
            # neighbor while the denominator stays the actual negative audio.
            timeline = file_start + duration + detector.config.debounce_seconds
        except (OSError, ValueError, wave.Error, WakeWordRuntimeError):
            invalid += 1
    return {
        "files": len(paths),
        "invalid": invalid,
        "matched_files": matched_files,
        "activations": activations,
        "audio_seconds": round(seconds, 3),
        "activation_p50_seconds": _percentile(activation_latencies, 0.50),
        "activation_p95_seconds": _percentile(activation_latencies, 0.95),
        "inference_wall_p50_seconds": _percentile(wall_latencies, 0.50),
        "inference_wall_p95_seconds": _percentile(wall_latencies, 0.95),
        "prediction_p50_seconds": _percentile(prediction_latencies, 0.50),
        "prediction_p95_seconds": _percentile(prediction_latencies, 0.95),
    }, timeline


def _evaluate_lexical_group(
    recognizer,
    matcher: WakePhraseMatcher,
    paths: list[Path],
) -> dict[str, float | int | None]:
    """Retained only for a measured migration comparison, never KWS approval."""

    matched = 0
    invalid = 0
    seconds = 0.0
    latencies: list[float] = []
    for path in paths:
        try:
            audio, duration = _read_wave(path)
            started = time.perf_counter()
            stream = recognizer.create_stream()
            stream.accept_waveform(SAMPLE_RATE, audio)
            recognizer.decode_stream(stream)
            transcript = str(stream.result.text or "")
            is_wake, _ = matcher.strip(transcript)
            matched += int(is_wake)
            seconds += duration
            latencies.append(time.perf_counter() - started)
        except (OSError, ValueError, wave.Error):
            invalid += 1
    return {
        "files": len(paths),
        "invalid": invalid,
        "matched_files": matched,
        "activations": matched,
        "audio_seconds": round(seconds, 3),
        "activation_p50_seconds": None,
        "activation_p95_seconds": None,
        "inference_wall_p50_seconds": _percentile(latencies, 0.50),
        "inference_wall_p95_seconds": _percentile(latencies, 0.95),
        "prediction_p50_seconds": None,
        "prediction_p95_seconds": None,
    }


def _evaluate_lexical(
    positive: list[Path],
    negative: list[Path],
    stt_dir: Path | None,
) -> tuple[dict[str, float | int | None], dict[str, float | int | None], dict[str, object]]:
    if stt_dir is not None:
        os.environ["BAXY_MIND_STT_DIR"] = str(stt_dir.resolve())
    os.environ["BAXY_VOICE_STREAMING_STT"] = "off"
    engine = VoiceEngine(lambda _text: None)
    try:
        engine.load()
        if engine._recognizer is None:  # noqa: SLF001 - explicit migration gate
            raise RuntimeError("final_stt_unavailable")
        matcher = WakePhraseMatcher()
        positives = _evaluate_lexical_group(engine._recognizer, matcher, positive)  # noqa: SLF001
        negatives = _evaluate_lexical_group(engine._recognizer, matcher, negative)  # noqa: SLF001
    finally:
        engine.shutdown()
    return positives, negatives, {
        "backend": "lexical_fallback",
        "architecture": "Parakeet transcript prefix verifier; not an acoustic KWS",
    }


def _evaluate_acoustic(
    positive: list[Path],
    negative: list[Path],
    manifest: Path | None,
) -> tuple[dict[str, float | int | None], dict[str, float | int | None], dict[str, object]]:
    config = load_wakeword_config(manifest)
    detector = AcousticWakeDetector(config)
    positives, timeline = _evaluate_acoustic_group(detector, positive, timeline=0.0)
    negatives, _ = _evaluate_acoustic_group(detector, negative, timeline=timeline)
    return positives, negatives, {
        "backend": detector.backend,
        "architecture": "Dedicated acoustic KWS; ASR is not loaded",
        "model": config.model_name,
        "phrase": config.phrase,
        "sample_rate": SAMPLE_RATE,
        "window_samples": WINDOW_SAMPLES,
        "threshold": config.threshold,
        "hop_samples": config.hop_samples,
        "debounce_seconds": config.debounce_seconds,
        "model_sha256": config.model_sha256,
        "manifest_schema": "baxy-wakeword-v1",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--negative", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("acoustic", "lexical"), default="acoustic")
    parser.add_argument("--wake-manifest", type=Path)
    parser.add_argument("--stt-dir", type=Path)
    parser.add_argument("--minimum-positive", type=int, default=200)
    parser.add_argument(
        "--minimum-negative-hours",
        type=float,
        default=30.0,
        help="Horas negativas mÃ­nimas; 30 h sin hits sustentan 0.1 FPPH al 95%%.",
    )
    parser.add_argument("--maximum-false-reject-rate", type=float, default=0.05)
    parser.add_argument("--maximum-false-activations-per-hour", type=float, default=0.1)
    parser.add_argument(
        "--far-confidence",
        type=float,
        default=0.95,
        help="Confianza unilateral para el lÃ­mite superior Poisson de FAR (mÃ­nimo 0.95).",
    )
    args = parser.parse_args()
    if args.minimum_positive < 1:
        parser.error("--minimum-positive debe ser al menos 1.")
    if not math.isfinite(args.minimum_negative_hours) or args.minimum_negative_hours <= 0.0:
        parser.error("--minimum-negative-hours debe ser positivo y finito.")
    if (
        not math.isfinite(args.maximum_false_reject_rate)
        or not 0.0 <= args.maximum_false_reject_rate <= 1.0
    ):
        parser.error("--maximum-false-reject-rate debe estar entre 0 y 1.")
    if (
        not math.isfinite(args.maximum_false_activations_per_hour)
        or args.maximum_false_activations_per_hour <= 0.0
    ):
        parser.error("--maximum-false-activations-per-hour debe ser positivo y finito.")
    if (
        not math.isfinite(args.far_confidence)
        or not _MINIMUM_FAR_CONFIDENCE <= args.far_confidence < 1.0
    ):
        parser.error("--far-confidence debe estar entre 0.95 (inclusive) y 1.")

    positive = _wav_paths(args.positive)
    negative = _wav_paths(args.negative)
    if not positive or not negative:
        raise SystemExit("El corpus requiere al menos un WAV positivo y uno negativo.")
    if args.mode == "acoustic":
        positives, negatives, model = _evaluate_acoustic(
            positive,
            negative,
            args.wake_manifest,
        )
    else:
        positives, negatives, model = _evaluate_lexical(positive, negative, args.stt_dir)

    positive_files = int(positives["files"])
    negative_seconds = float(negatives["audio_seconds"])
    recall = float(positives["matched_files"]) / positive_files if positive_files else 0.0
    frr = 1.0 - recall
    negative_hours = negative_seconds / 3600.0
    far_per_hour = (
        float(negatives["activations"]) * 3600.0 / negative_seconds
        if negative_seconds > 0
        else None
    )
    far_upper_per_hour = one_sided_poisson_upper_rate_per_hour(
        int(negatives["activations"]),
        negative_seconds,
        args.far_confidence,
    )
    zero_event_hours_required = minimum_zero_event_hours_for_far(
        args.maximum_false_activations_per_hour,
        args.far_confidence,
    )
    effective_minimum_negative_hours = max(
        args.minimum_negative_hours,
        zero_event_hours_required,
    )
    corpus_sufficient = (
        positive_files >= args.minimum_positive
        and negative_hours >= effective_minimum_negative_hours
        and int(positives["invalid"]) == 0
        and int(negatives["invalid"]) == 0
    )
    promotable = (
        args.mode == "acoustic"
        and corpus_sufficient
        and frr <= args.maximum_false_reject_rate
        and far_upper_per_hour is not None
        and far_upper_per_hour <= args.maximum_false_activations_per_hour
    )
    report = {
        "schema": CALIBRATION_REPORT_SCHEMA,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "model": model,
        "positive": positives,
        "negative": negatives,
        "recall": recall,
        "false_reject_rate": frr,
        "false_activations_per_hour": far_per_hour,
        "far": {
            "method": "poisson_one_sided_upper_exact",
            "confidence": args.far_confidence,
            "observed_activations": int(negatives["activations"]),
            "exposure_hours": negative_hours,
            "observed_per_hour": far_per_hour,
            "upper_confidence_per_hour": far_upper_per_hour,
        },
        "minimum_positive": args.minimum_positive,
        "minimum_negative_hours": args.minimum_negative_hours,
        "minimum_zero_event_hours_for_far": zero_event_hours_required,
        "effective_minimum_negative_hours": effective_minimum_negative_hours,
        "corpus_sufficient": corpus_sufficient,
        "promotion_criteria": {
            "mode": "acoustic",
            "false_reject_rate_lte": args.maximum_false_reject_rate,
            "false_activations_per_hour_lte": args.maximum_false_activations_per_hour,
            "far_confidence_gte": args.far_confidence,
        },
        "promotable": promotable,
        "privacy": "no audio, filename, or transcript is written to this report",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as destination:
        destination.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if promotable else 2


if __name__ == "__main__":
    raise SystemExit(main())
