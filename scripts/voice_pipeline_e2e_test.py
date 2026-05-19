"""End-to-end test of the new voice pipeline against Grabación (2).wav.

Feeds the test audio chunk-by-chunk through the pipeline (mocking the
mic) and reports:

  - Wake detections (timestamps + scores) vs expected wakes (105).
  - Match rate (recall) within ±1.0s tolerance.
  - Mean time-to-fire (latency proxy).
  - For each matched wake: the transcript of the following command,
    after STT + RapidFuzz post-correction.

This is the empirical proof that the v2 pipeline works on the same
audio that humiliated v1. Run with:

    .venv/Scripts/python scripts/voice_pipeline_e2e_test.py

No external infra needed: pure Python + the audio + the JSON anchors
that the operator already curated.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.voice.audio_io import CHUNK_SAMPLES, SAMPLE_RATE
from gemma4_agent.voice.corrector import FuzzyCorrector
from gemma4_agent.voice.inventory import build_initial_prompt, get_inventory
from gemma4_agent.voice.stt import STT
from gemma4_agent.voice.vad import SileroVAD
from gemma4_agent.voice.wake import WakeDetector

AUDIO_PATH = ROOT / "gemma4_agent" / "voice" / "tests" / "Grabación (2).wav"
EXPECTED_JSON = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_v2_expected.json"


def _load_audio(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        assert wf.getframerate() == SAMPLE_RATE, (
            f"Audio is {wf.getframerate()} Hz, expected {SAMPLE_RATE}"
        )
        assert wf.getnchannels() == 1, "Audio must be mono"
        n = wf.getnframes()
        raw = wf.readframes(n)
    return np.frombuffer(raw, dtype=np.int16)


def _load_expected_wakes(path: Path) -> list[float]:
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return sorted(float(w["timestamp_s"]) for w in d.get("wakes", []))


def _match_wakes(
    detected: list[float],
    expected: list[float],
    tolerance_s: float = 1.0,
) -> tuple[int, int, int, list[tuple[float, float]]]:
    """Bipartite-greedy matching. Returns (tp, fp, fn, pairs)."""
    used = [False] * len(expected)
    tp = 0
    fp = 0
    pairs: list[tuple[float, float]] = []  # (expected_ts, detected_ts)
    for d in detected:
        best_i = -1
        best_gap = tolerance_s + 1
        for i, e in enumerate(expected):
            if used[i]:
                continue
            gap = abs(d - e)
            if gap <= tolerance_s and gap < best_gap:
                best_i = i
                best_gap = gap
        if best_i >= 0:
            used[best_i] = True
            tp += 1
            pairs.append((expected[best_i], d))
        else:
            fp += 1
    fn = sum(1 for u in used if not u)
    return tp, fp, fn, pairs


def run_e2e_test(
    transcribe: bool = True,
    max_commands_to_transcribe: int = 10,
) -> dict:
    """Run the full pipeline on the test audio. Returns a metrics dict."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("e2e")

    if not AUDIO_PATH.exists():
        log.error("Audio not found: %s", AUDIO_PATH)
        return {"error": "audio_missing"}
    if not EXPECTED_JSON.exists():
        log.error("Expected JSON not found: %s", EXPECTED_JSON)
        return {"error": "expected_missing"}

    log.info("Loading audio %s", AUDIO_PATH.name)
    audio = _load_audio(AUDIO_PATH)
    duration_s = len(audio) / SAMPLE_RATE
    log.info("Audio duration: %.2fs (%d samples)", duration_s, len(audio))

    expected = _load_expected_wakes(EXPECTED_JSON)
    log.info("Expected wakes: %d", len(expected))

    # ---- Load pipeline components -----------------------------------
    log.info("Loading VAD...")
    vad = SileroVAD()
    vad.load()

    log.info("Loading wake detector...")
    detected_wakes: list[tuple[float, float]] = []  # (audio_ts, score)
    audio_cursor = [0.0]  # mutable, updated each chunk

    def on_wake(phrase: str, score: float) -> None:
        detected_wakes.append((audio_cursor[0], score))

    wake = WakeDetector(on_wake=on_wake)
    if not wake.load():
        log.error("Wake load failed: %s", wake.last_error)
        return {"error": "wake_load_failed"}

    if transcribe:
        log.info("Loading STT (faster-whisper small, int8 CPU)...")
        stt = STT()
        if not stt.load():
            log.warning(
                "STT load failed: %s — continuing without transcription",
                stt.last_error,
            )
            transcribe = False
    else:
        stt = None  # type: ignore

    inv = get_inventory(include_discovery=False)
    corrector = FuzzyCorrector(inv)
    initial_prompt = build_initial_prompt(inv)

    # ---- Feed chunks ------------------------------------------------
    log.info("Feeding %d chunks of %d samples each (%dms)...",
              len(audio) // CHUNK_SAMPLES, CHUNK_SAMPLES,
              (CHUNK_SAMPLES * 1000) // SAMPLE_RATE)
    t_start = time.time()
    n_speech = 0
    n_silence = 0
    for i in range(0, len(audio) - CHUNK_SAMPLES, CHUNK_SAMPLES):
        chunk = audio[i:i + CHUNK_SAMPLES]
        audio_cursor[0] = (i + CHUNK_SAMPLES) / SAMPLE_RATE
        # Mirror pipeline.py _handle_idle: feed wake EVERY chunk. The
        # wake detector accumulates 80 ms windows internally; gating
        # via VAD upstream destroys that continuity. VAD stats kept
        # for observability only.
        if vad.is_speech(chunk, threshold=0.3):
            n_speech += 1
        else:
            n_silence += 1
        wake.feed(chunk)
    t_elapsed = time.time() - t_start
    log.info(
        "Stream processed in %.2fs (%.2fx realtime). "
        "VAD: speech=%d (%.0f%%) silence=%d",
        t_elapsed, duration_s / max(0.001, t_elapsed),
        n_speech, 100 * n_speech / max(1, n_speech + n_silence), n_silence,
    )

    # ---- Match wakes ------------------------------------------------
    detected_ts = [t for t, _s in detected_wakes]
    tp, fp, fn, pairs = _match_wakes(detected_ts, expected)
    recall = tp / max(1, len(expected))
    precision = tp / max(1, tp + fp)
    f1 = 2 * recall * precision / max(1e-9, recall + precision)
    log.info("WAKE: tp=%d fp=%d fn=%d recall=%.3f precision=%.3f F1=%.3f",
              tp, fp, fn, recall, precision, f1)

    # ---- Transcribe a sample of matched wakes -----------------------
    transcripts: list[dict] = []
    if transcribe and stt is not None:
        # Take up to N matched wakes, transcribe ~3s of audio after each.
        sample = pairs[:max_commands_to_transcribe]
        log.info("Transcribing %d matched commands...", len(sample))
        for expected_ts, detected_ts in sample:
            start_s = max(0, expected_ts - 0.5)
            end_s = min(duration_s, start_s + 4.0)
            start_idx = int(start_s * SAMPLE_RATE)
            end_idx = int(end_s * SAMPLE_RATE)
            clip = audio[start_idx:end_idx]
            t0 = time.time()
            raw = stt.transcribe(clip, initial_prompt=initial_prompt)
            elapsed = time.time() - t0
            stripped = corrector.strip_wake_phrase(raw)
            corrected = corrector.correct(stripped)
            transcripts.append({
                "expected_ts": round(expected_ts, 2),
                "detected_ts": round(detected_ts, 2),
                "audio_dur_s": round(end_s - start_s, 2),
                "stt_latency_s": round(elapsed, 3),
                "raw": raw,
                "after_strip": stripped,
                "after_correct": corrected,
            })
            log.info(
                "  @ %.2fs (lat=%.2fs): %r -> %r",
                expected_ts, elapsed, raw[:60], corrected[:60],
            )

    return {
        "audio_duration_s": round(duration_s, 2),
        "processing_time_s": round(t_elapsed, 2),
        "rt_factor": round(duration_s / max(0.001, t_elapsed), 2),
        "expected_wakes": len(expected),
        "detected_wakes": len(detected_wakes),
        "tp": tp, "fp": fp, "fn": fn,
        "wake_recall": round(recall, 3),
        "wake_precision": round(precision, 3),
        "wake_f1": round(f1, 3),
        "wake_model": "custom_hey_gemma" if wake.using_custom_model else "stock_hey_jarvis",
        "vad_stats": {
            "speech_chunks": n_speech,
            "silence_chunks": n_silence,
            "speech_pct": round(100 * n_speech / max(1, n_speech + n_silence), 1),
        },
        "transcripts": transcripts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-stt", action="store_true",
        help="Skip transcription (wake-detection-only benchmark)",
    )
    parser.add_argument(
        "--max-transcripts", type=int, default=10,
        help="Max number of matched wakes to transcribe",
    )
    parser.add_argument(
        "--json", type=Path, default=None,
        help="Write the result as JSON to this path",
    )
    args = parser.parse_args()

    result = run_e2e_test(
        transcribe=not args.no_stt,
        max_commands_to_transcribe=args.max_transcripts,
    )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Wrote {args.json}")

    print()
    print("=" * 60)
    print("E2E pipeline result")
    print("=" * 60)
    for k in ("wake_model", "wake_recall", "wake_precision", "wake_f1",
              "tp", "fp", "fn", "audio_duration_s", "processing_time_s",
              "rt_factor"):
        print(f"  {k:24s} {result.get(k)}")
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())
