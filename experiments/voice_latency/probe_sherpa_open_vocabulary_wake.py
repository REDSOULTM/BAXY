"""Measure sherpa-onnx open-vocabulary KWS as a BAXY wake-word candidate.

This is a synthetic feasibility probe, never promotion evidence.  It uses the
installed Windows SAPI voices at several rates, deterministic noise and hard
phonetic negatives.  A real held-out microphone corpus is still mandatory.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sherpa_onnx


SAMPLE_RATE = 16_000
TARGET_PHONES = (
    ("B AE1 K S IY0", "BAXY_AE"),
    ("B AA1 K S IY0", "BAXY_AA"),
    ("B AE1 K S IY1", "BAXY_AE_STRESS"),
)
POSITIVE_PHRASES = (
    "Baxy",
    "Hola Baxy",
    "Oye Baxy",
    "Baxy por favor",
    "Hey Baxy",
    "Baxy check the computer",
)
NEGATIVE_PHRASES = (
    "taxi",
    "maxi",
    "Betsy",
    "Baxter",
    "Paxi",
    "back seat",
    "back soon",
    "backs easy",
    "Oye taxi",
    "Hey Betsy",
    "Hola Maxi",
    "abre Spotify",
    "pon el volumen al cincuenta por ciento",
    "how much disk space is left",
    "mute the sound please",
    "the assistant is ready",
)


def _synthesize(language_code: str, text: str, rate: int) -> np.ndarray:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    temporary = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    path = Path(temporary.name)
    temporary.close()
    try:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        token = next(
            candidate
            for candidate in voice.GetVoices()
            if str(candidate.GetAttribute("Language")).upper() == language_code
        )
        voice.Voice = token
        voice.Rate = rate
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(str(path), 3, False)
        voice.AudioOutputStream = stream
        voice.Speak(text)
        stream.Close()
        with wave.open(str(path), "rb") as source:
            source_rate = source.getframerate()
            channels = source.getnchannels()
            if source.getsampwidth() != 2:
                raise RuntimeError("sapi_not_pcm16")
            audio = np.frombuffer(
                source.readframes(source.getnframes()),
                dtype=np.int16,
            )
        if channels > 1:
            audio = audio.reshape(-1, channels).mean(axis=1).astype(np.int16)
        normalized = audio.astype(np.float32) / 32768.0
    finally:
        path.unlink(missing_ok=True)
        pythoncom.CoUninitialize()
    if source_rate != SAMPLE_RATE:
        target = max(1, round(len(normalized) * SAMPLE_RATE / source_rate))
        normalized = np.interp(
            np.linspace(0, len(normalized) - 1, target),
            np.arange(len(normalized)),
            normalized,
        ).astype(np.float32)
    return normalized


def _with_noise(audio: np.ndarray, snr_db: float | None, seed: int) -> np.ndarray:
    if snr_db is None:
        return audio.copy()
    rng = np.random.default_rng(seed)
    signal_rms = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
    if signal_rms <= 0.0:
        return audio.copy()
    noise = rng.normal(0.0, 1.0, audio.size).astype(np.float32)
    noise_rms = float(np.sqrt(np.mean(np.square(noise), dtype=np.float64)))
    scale = signal_rms / (10.0 ** (snr_db / 20.0)) / max(noise_rms, 1e-9)
    return np.clip(audio + noise * scale, -1.0, 1.0).astype(np.float32)


def _corpus() -> tuple[list[np.ndarray], list[np.ndarray], float]:
    positives: list[np.ndarray] = []
    negatives: list[np.ndarray] = []
    seed = 0
    for language in ("80A", "409"):
        for rate in (-2, 0, 2):
            for phrase in POSITIVE_PHRASES:
                clean = _synthesize(language, phrase, rate)
                for snr in (None, 20.0, 10.0):
                    positives.append(_with_noise(clean, snr, seed))
                    seed += 1
            for phrase in NEGATIVE_PHRASES:
                clean = _synthesize(language, phrase, rate)
                for snr in (None, 20.0):
                    negatives.append(_with_noise(clean, snr, seed))
                    seed += 1
    # Include deterministic non-speech exposure.  It is useful for catching
    # catastrophic noise triggers, but is not counted as diverse room audio.
    rng = np.random.default_rng(20260803)
    for _ in range(24):
        negatives.append((rng.normal(0.0, 0.02, SAMPLE_RATE * 5)).astype(np.float32))
    negative_seconds = sum(len(audio) / SAMPLE_RATE for audio in negatives)
    return positives, negatives, negative_seconds


def _spotter(model: Path, keywords: Path) -> sherpa_onnx.KeywordSpotter:
    return sherpa_onnx.KeywordSpotter(
        tokens=str(model / "tokens.txt"),
        encoder=str(model / "encoder-epoch-13-avg-2-chunk-8-left-64.int8.onnx"),
        decoder=str(model / "decoder-epoch-13-avg-2-chunk-8-left-64.onnx"),
        joiner=str(model / "joiner-epoch-13-avg-2-chunk-8-left-64.int8.onnx"),
        keywords_file=str(keywords),
        num_threads=1,
        provider="cpu",
    )


def _detect(spotter: sherpa_onnx.KeywordSpotter, audio: np.ndarray) -> tuple[bool, float]:
    stream = spotter.create_stream()
    started = time.perf_counter()
    chunk = 1_600
    detected = False
    replay = np.concatenate((audio, np.zeros(round(0.8 * SAMPLE_RATE), np.float32)))
    for offset in range(0, replay.size, chunk):
        stream.accept_waveform(SAMPLE_RATE, replay[offset : offset + chunk])
        while spotter.is_ready(stream):
            spotter.decode_stream(stream)
            if spotter.get_result(stream):
                detected = True
                spotter.reset_stream(stream)
    stream.input_finished()
    while spotter.is_ready(stream):
        spotter.decode_stream(stream)
        if spotter.get_result(stream):
            detected = True
            spotter.reset_stream(stream)
    return detected, time.perf_counter() - started


def _percentile(values: list[float], fraction: float) -> float:
    return round(float(np.quantile(np.asarray(values), fraction)), 6)


def _evaluate(
    model: Path,
    positives: list[np.ndarray],
    negatives: list[np.ndarray],
    score: float,
    threshold: float,
) -> dict[str, object]:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as file:
        keywords = Path(file.name)
        for phones, label in TARGET_PHONES:
            file.write(f"{phones} :{score} #{threshold} @{label}\n")
    try:
        spotter = _spotter(model, keywords)
        positive_hits = 0
        negative_hits = 0
        latencies: list[float] = []
        for audio in positives:
            hit, latency = _detect(spotter, audio)
            positive_hits += int(hit)
            latencies.append(latency)
        for audio in negatives:
            hit, latency = _detect(spotter, audio)
            negative_hits += int(hit)
            latencies.append(latency)
    finally:
        keywords.unlink(missing_ok=True)
    recall = positive_hits / len(positives)
    false_positive_rate = negative_hits / len(negatives)
    return {
        "score": score,
        "threshold": threshold,
        "positive_hits": positive_hits,
        "recall": recall,
        "negative_hits": negative_hits,
        "negative_clip_false_positive_rate": false_positive_rate,
        "inference_p50_seconds": _percentile(latencies, 0.50),
        "inference_p95_seconds": _percentile(latencies, 0.95),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    positives, negatives, negative_seconds = _corpus()
    measurements = [
        _evaluate(args.model, positives, negatives, score, threshold)
        for score in (1.0, 1.5, 2.0)
        for threshold in (0.20, 0.25, 0.35, 0.45)
    ]
    ranked = sorted(
        measurements,
        key=lambda item: (
            int(item["negative_hits"]),
            -float(item["recall"]),
            float(item["inference_p95_seconds"]),
        ),
    )
    report = {
        "schema": "baxy.sherpa-open-vocabulary-wake-feasibility.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate": "sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20 chunk8 int8",
        "method": "SAPI es/en, rates -2/0/2, clean/20/10 dB positives, phonetic negatives",
        "positive_clips": len(positives),
        "negative_clips": len(negatives),
        "negative_audio_seconds": round(negative_seconds, 3),
        "measurements": measurements,
        "best_observed": ranked[0],
        "promotable": False,
        "promotion_block": "synthetic_audio_is_not_a_held_out_physical_microphone_corpus",
        "effects_executed": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
