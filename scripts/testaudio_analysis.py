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

from gemma4_agent.voice.audio_io import SAMPLE_RATE, CHUNK_SAMPLES
from gemma4_agent.voice.stt import StreamingSTT, VAD_SILENCE_MS
from gemma4_agent.voice.wake import WakeDetector

ROOT = Path(__file__).resolve().parent.parent
WAV = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_full.wav"
OUT = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_analysis.json"

# Sprint P.1 2026-05-18: WINDOW_S is now the hard CAP, not the
# segment length. _live_endpoint() closes at silence the same way
# the live transcribe_stream pipeline does (VAD_SILENCE_MS).
WINDOW_S = 15.0           # MAX seconds (hard cap, matches ABSOLUTE_TIMEOUT_S)
WAKE_TAIL_S = 0.5         # pre-wake margin (Sprint L PRE_WAKE_TAIL_S)
CHUNK = 512               # 32ms at 16kHz — same as the live pipeline

# stt.py:transcribe_stream uses these as function-locals; we mirror
# them here so the offline analysis mimics the live endpoint logic.
SPEECH_RMS_THRESHOLD = 200   # matches stt.py line 867
SPEECH_MIN_CHUNKS = 2        # matches stt.py line 868


def _live_endpoint(audio: np.ndarray, start_idx: int,
                   max_s: float = 15.0) -> tuple[int, str]:
    """Simulate the live pipeline's endpoint logic on a pre-recorded
    audio array. Returns (end_idx, reason).

    Mirrors stt.py:transcribe_stream RMS-based endpoint:
    - Wait for SPEECH_MIN_CHUNKS consecutive chunks with
      rms > SPEECH_RMS_THRESHOLD (first_speech_t).
    - Close when silence_ms >= VAD_SILENCE_MS since the last
      speech chunk (endpoint_silence).
    - Hard cap at max_s seconds (max_window).
    - If no speech ever detected, return start_idx (no_speech_detected).

    This is what Whisper actually receives in the live pipeline —
    NOT the fixed 15s window the pre-Sprint-P analysis used.
    """
    n = len(audio)
    max_samples = int(max_s * SAMPLE_RATE)
    end_cap = min(n, start_idx + max_samples)
    speech_streak = 0
    first_speech_idx: int | None = None
    last_speech_idx: int | None = None
    silence_samples = 0
    silence_samples_threshold = int((VAD_SILENCE_MS / 1000.0) * SAMPLE_RATE)
    for i in range(start_idx, end_cap, CHUNK_SAMPLES):
        chunk = audio[i:i + CHUNK_SAMPLES]
        if len(chunk) < CHUNK_SAMPLES:
            break
        chunk_rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
        if chunk_rms > SPEECH_RMS_THRESHOLD:
            speech_streak += 1
            if speech_streak >= SPEECH_MIN_CHUNKS:
                if first_speech_idx is None:
                    first_speech_idx = i
                last_speech_idx = i + CHUNK_SAMPLES
                silence_samples = 0
        else:
            speech_streak = 0
            if first_speech_idx is not None:
                silence_samples += CHUNK_SAMPLES
                if silence_samples >= silence_samples_threshold:
                    assert last_speech_idx is not None
                    return last_speech_idx, "endpoint_silence"
    if first_speech_idx is None:
        return start_idx, "no_speech_detected"
    return end_cap, "max_window"

# Sprint P.1 2026-05-18: wrapped the body in main() so tests can
# import the module to access _live_endpoint without triggering
# Vosk + Whisper load at module import time.
def main() -> None:
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
        # Sprint P.1 2026-05-18: simulate the live pipeline endpoint
        # logic instead of using a fixed WINDOW_S=15s slice. Whisper
        # now sees what transcribe_stream would send it — up to the
        # first VAD_SILENCE_MS gap after speech starts.
        end_idx, endpoint_reason = _live_endpoint(
            audio, start_idx=start_idx, max_s=WINDOW_S,
        )
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
            "endpoint_reason": endpoint_reason,
            "text": text,
            "reject_reason": reason,
            "whisper_raw_text": raw,
            "transcribe_elapsed_s": round(elapsed, 2),
        })
        text_repr = (text[:80] + "...") if len(text) > 80 else text
        raw_repr = (raw[:80] + "...") if len(raw) > 80 else raw
        print(f"  [{k}] t={wake_ts_s:>6.2f}s conf={conf:.3f} "
              f"seg={seg_duration:>5.2f}s endpoint={endpoint_reason:<18s} "
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


if __name__ == "__main__":
    main()
