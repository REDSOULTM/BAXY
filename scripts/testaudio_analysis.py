"""Offline analysis of operator-provided testaudio (Sprint M.1).

Loads gemma4_agent/voice/tests/testaudio_full.wav (regenerated
from the .m4a via ffmpeg), runs the Vosk wake detector over it,
and transcribes each detected segment via the real Whisper
pipeline. Emits a structured JSON summary at
gemma4_agent/voice/tests/testaudio_analysis.json.

Run from project root:
    python scripts/testaudio_analysis.py
"""
from __future__ import annotations

import json
import sys
import time
import wave
from pathlib import Path

import numpy as np

# Make the project root importable so we can `from gemma4_agent...`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gemma4_agent.voice.audio_io import SAMPLE_RATE
from gemma4_agent.voice.stt import StreamingSTT
from gemma4_agent.voice.wake import WakeDetector

ROOT = Path(__file__).resolve().parent.parent
WAV = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_full.wav"
OUT = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_analysis.json"

WINDOW_S = 15.0           # how much audio to send to Whisper per wake
WAKE_TAIL_S = 0.5         # pre-wake margin (Sprint L PRE_WAKE_TAIL_S)
CHUNK = 512               # 32ms at 16kHz — same as the live pipeline

print(f"Loading audio from {WAV}...")
assert WAV.exists(), f"audio not found at {WAV}"
with wave.open(str(WAV), "rb") as wf:
    sr = wf.getframerate()
    assert sr == SAMPLE_RATE, f"expected {SAMPLE_RATE} Hz, got {sr}"
    raw = wf.readframes(wf.getnframes())
audio = np.frombuffer(raw, dtype=np.int16)
total_s = len(audio) / SAMPLE_RATE
print(f"Audio: {total_s:.1f}s ({total_s/60:.2f} min), {len(audio)} samples")

# --- Step 1: Wake detection ---
print("Loading Vosk wake detector...")
detections: list[tuple[float, str, float]] = []


def _on_wake(phrase: str, ts: float, tail_s: float = 0.0,
             confidence: float = 0.0) -> None:
    detections.append((ts, phrase, confidence))


detector = WakeDetector(on_wake=_on_wake)
if not detector.load():
    raise RuntimeError(f"Vosk load failed: {detector.last_error}")

print(f"Running wake detector over {len(audio)} samples (chunk={CHUNK})...")
t0 = time.time()
fake_ts = 0.0
for i in range(0, len(audio) - CHUNK, CHUNK):
    chunk = audio[i:i + CHUNK]
    detector.feed(chunk)
    fake_ts = (i + CHUNK) / SAMPLE_RATE
print(f"Wake detection done in {time.time() - t0:.1f}s — {len(detections)} fires")
for k, (ts, phrase, conf) in enumerate(detections):
    print(f"  [{k}] ts={ts:.2f}s phrase={phrase!r} conf={conf:.3f}")

# --- Step 2: Map detector ts back to sample index ---
# WakeDetector's `ts` is time.monotonic() — not useful for indexing
# the offline WAV. Instead, we walk the audio in the same chunking
# and record sample index when a wake fires. Re-run with index
# capture.
print("\nRe-running with sample-index capture...")
detector.reset()  # clear internal Vosk state
detector._samples_since_last_result = 0
index_detections: list[tuple[int, str, float]] = []
fired_count_at_start = 0


def _on_wake_indexed(phrase: str, ts: float, tail_s: float = 0.0,
                     confidence: float = 0.0) -> None:
    # Append; we'll associate with current i below.
    index_detections.append((-1, phrase, confidence))


detector._on_wake = _on_wake_indexed
for i in range(0, len(audio) - CHUNK, CHUNK):
    before = len(index_detections)
    detector.feed(audio[i:i + CHUNK])
    if len(index_detections) > before:
        # Update the latest entry with the sample index.
        idx, phr, cf = index_detections[-1]
        index_detections[-1] = (i + CHUNK, phr, cf)

# --- Step 3: Transcribe each segment ---
print(f"\nLoading Whisper STT for {len(index_detections)} segments...")
stt = StreamingSTT()
if not stt.load():
    raise RuntimeError(f"Whisper load failed: {stt.last_error}")

results = []
for k, (sample_idx, phrase, conf) in enumerate(index_detections):
    start_idx = max(0, sample_idx - int(WAKE_TAIL_S * SAMPLE_RATE))
    end_idx = min(len(audio), sample_idx + int(WINDOW_S * SAMPLE_RATE))
    segment = audio[start_idx:end_idx]
    seg_duration = (end_idx - start_idx) / SAMPLE_RATE
    wake_ts_s = sample_idx / SAMPLE_RATE
    t0 = time.time()
    # Hotfix M.2.3 2026-05-18: 3-tuple includes raw_text — what
    # Whisper produced before the quality_check killed it.
    text, reason, raw = stt._transcribe_buffer(segment)
    elapsed = time.time() - t0
    results.append({
        "k": k,
        "wake_sample_idx": int(sample_idx),
        "wake_ts_s": round(wake_ts_s, 2),
        "wake_phrase": phrase,
        "wake_conf": round(conf, 3),
        "segment_duration_s": round(seg_duration, 2),
        "text": text,
        "reject_reason": reason,
        "whisper_raw_text": raw,
        "transcribe_elapsed_s": round(elapsed, 2),
    })
    text_repr = (text[:80] + "...") if len(text) > 80 else text
    raw_repr = (raw[:80] + "...") if len(raw) > 80 else raw
    print(f"  [{k}] t={wake_ts_s:>6.2f}s conf={conf:.3f} "
          f"reason={reason:<20s} text={text_repr!r} raw={raw_repr!r}")

# --- Step 4: Categorize ---
buckets: dict[str, list] = {
    "legitimate_passed": [],
    "legitimate_rejected": [],
    "expected_rejected": [],
    "wake_false_positive": [],
}
for r in results:
    if r["text"]:
        buckets["legitimate_passed"].append({
            "k": r["k"], "wake_ts_s": r["wake_ts_s"], "text": r["text"],
        })
    elif r["reject_reason"] in {"no_speech", "too_short"}:
        # No speech detected at all — likely either wake was false
        # or the operator paused. Mark as expected_rejected; wake
        # false-positive analysis happens manually since we don't
        # have ground truth.
        buckets["expected_rejected"].append({
            "k": r["k"], "wake_ts_s": r["wake_ts_s"],
            "reason": r["reject_reason"],
        })
    else:
        # Whisper produced output but the quality filter killed it.
        # In offline analysis we can't distinguish legitimate-rejected
        # from wake-false-positive without the operator labelling.
        # Default to legitimate_rejected — these are the cases worth
        # investigating.
        buckets["legitimate_rejected"].append({
            "k": r["k"], "wake_ts_s": r["wake_ts_s"],
            "reason": r["reject_reason"],
        })

summary = {
    "source_file": "Grabación (2).m4a",
    "total_duration_s": round(total_s, 2),
    "wake_detections": len(results),
    "buckets": {
        "legitimate_passed": buckets["legitimate_passed"],
        "legitimate_rejected": buckets["legitimate_rejected"],
        "expected_rejected": buckets["expected_rejected"],
    },
    "bucket_counts": {k: len(v) for k, v in buckets.items()},
    "reject_reason_distribution": {},
    "all_results": results,
}

# Reject reason distribution
from collections import Counter
counts = Counter(r["reject_reason"] for r in results)
summary["reject_reason_distribution"] = dict(counts)

OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                encoding="utf-8")
print(f"\nWrote {OUT}")
print(f"\nBucket counts: {summary['bucket_counts']}")
print(f"Reject reason distribution: {summary['reject_reason_distribution']}")
