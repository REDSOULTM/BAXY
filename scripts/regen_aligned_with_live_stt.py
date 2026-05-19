"""Regenerate testaudio_groundtruth_aligned.json using the LIVE stt.py
pipeline (which has the MID tier added in R3.1).

This refreshes the small_raw_text field with the new decoding params.
large_text stays as-is (from Sprint N's large-v3 run).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.voice.stt import StreamingSTT, SAMPLE_RATE

ALIGNED_PATH = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_groundtruth_aligned.json"
ANALYSIS_PATH = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_analysis.json"
AUDIO_PATH = ROOT / "gemma4_agent" / "voice" / "tests" / "Grabación (2).wav"


def main():
    import wave
    with wave.open(str(AUDIO_PATH), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
        sr = wf.getframerate()
    audio = np.frombuffer(raw, dtype=np.int16)
    assert sr == SAMPLE_RATE

    with open(ALIGNED_PATH, encoding="utf-8") as fh:
        aligned = json.load(fh)

    print("Loading StreamingSTT...")
    stt = StreamingSTT()
    stt.load()
    print("Ready.")

    import jiwer

    for turn in aligned.get("turns", []):
        k = turn["k"]
        wake_ts = turn["wake_ts_s"]
        dur = turn["segment_duration_s"]
        start_idx = int(max(0, wake_ts - 0.5) * SAMPLE_RATE)
        end_idx = start_idx + int(dur * SAMPLE_RATE)
        segment = audio[start_idx:end_idx]
        t0 = time.time()
        # Use the internal _transcribe_buffer (returns text, reason, raw_text)
        text, reason, raw_text = stt._transcribe_buffer(segment)
        elapsed = time.time() - t0
        print(f"k={k} dur={dur:.2f}s reason={reason} elapsed={elapsed:.2f}s")
        print(f"  old raw: {turn.get('small_raw_text', '')[:80]}")
        print(f"  new raw: {raw_text[:80]}")
        turn["small_raw_text"] = raw_text
        turn["small_text"] = text
        turn["small_reject_reason"] = reason if reason != "ok" else ""
        # Recompute WER vs unchanged large_text
        large = (turn.get("large_text") or "").strip().lower()
        hyp = raw_text.strip().lower()
        if large:
            wer = float(jiwer.wer(large, hyp))
            turn["wer"] = round(wer, 4)
        print(f"  new wer: {turn.get('wer')}")
        print()

    with open(ALIGNED_PATH, "w", encoding="utf-8") as fh:
        json.dump(aligned, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {ALIGNED_PATH}")
    # Print summary
    wers = [t["wer"] for t in aligned["turns"] if t.get("wer") is not None]
    print(f"\nWER summary: mean={np.mean(wers):.4f}  n={len(wers)}")
    for t in aligned["turns"]:
        print(f"  k={t['k']}: {t.get('wer')}")


if __name__ == "__main__":
    main()
