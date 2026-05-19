"""Raw prediction tool: runs the oww model on the test audio without
debounce/threshold filtering and dumps the full score timeline.

Helps diagnose why the audit shows few fires while training shows
high val F1.
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openwakeword
from openwakeword.model import Model

MODEL_PATH = ROOT / "gemma4_agent" / "voice" / "models" / "oww" / "hey_gemma.onnx"
AUDIO_PATH = ROOT / "gemma4_agent" / "voice" / "tests" / "Grabación (2).wav"
EXPECTED_JSON = ROOT / "gemma4_agent" / "voice" / "tests" / "testaudio_v2_expected.json"

SAMPLE_RATE = 16000
CHUNK = 1280  # 80ms


def main():
    with wave.open(str(AUDIO_PATH), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16)
    print(f"Audio: {len(audio)/SAMPLE_RATE:.1f}s")

    with open(EXPECTED_JSON, encoding="utf-8") as fh:
        expected = json.load(fh)
    wake_times = sorted(float(w["timestamp_s"]) for w in expected["wakes"])
    print(f"Expected: {len(wake_times)} wakes")

    model = Model(wakeword_models=[str(MODEL_PATH)], inference_framework="onnx")
    model_name = list(model.models.keys())[0]
    print(f"Model: {model_name}")

    # Run streaming
    scores = []
    times = []
    for i in range(0, len(audio) - CHUNK + 1, CHUNK):
        chunk = audio[i:i + CHUNK]
        prediction = model.predict(chunk)
        score = prediction[model_name]
        scores.append(score)
        times.append(i / SAMPLE_RATE)

    scores = np.array(scores)
    times = np.array(times)
    print(f"\nProcessed {len(scores)} chunks")
    print(f"Score stats: min={scores.min():.3f}  max={scores.max():.3f}  mean={scores.mean():.3f}")
    print(f"Scores > 0.5: {(scores > 0.5).sum()}")
    print(f"Scores > 0.7: {(scores > 0.7).sum()}")
    print(f"Scores > 0.9: {(scores > 0.9).sum()}")

    # For each expected wake time, look at scores in ±1s window
    print("\nScore around each expected wake:")
    print(f"{'wake_t':>8}  {'max_score':>10}  {'time_of_max':>12}  {'gap':>6}")
    matched_count = 0
    for wt in wake_times[:20]:  # first 20
        mask = (times >= wt - 1.0) & (times <= wt + 1.0)
        if not mask.any():
            continue
        local_scores = scores[mask]
        local_times = times[mask]
        max_idx = local_scores.argmax()
        max_score = local_scores[max_idx]
        max_time = local_times[max_idx]
        gap = max_time - wt
        match = "*" if max_score > 0.5 else " "
        if max_score > 0.5:
            matched_count += 1
        print(f"{wt:8.2f}  {max_score:10.3f}  {max_time:12.2f}  {gap:+6.2f}  {match}")

    # Total matched at threshold 0.5 anywhere in ±1s
    total_matched = 0
    for wt in wake_times:
        mask = (times >= wt - 1.0) & (times <= wt + 1.0)
        if mask.any() and scores[mask].max() > 0.5:
            total_matched += 1
    print(f"\nTotal matched (score>0.5 within ±1s of expected): {total_matched}/{len(wake_times)}")

    # Distribution of max scores around expected wakes
    max_scores_at_wakes = []
    for wt in wake_times:
        mask = (times >= wt - 1.0) & (times <= wt + 1.0)
        if mask.any():
            max_scores_at_wakes.append(scores[mask].max())
    arr = np.array(max_scores_at_wakes)
    print(f"\nMax-score-at-expected distribution:")
    print(f"  > 0.9: {(arr > 0.9).sum()}")
    print(f"  > 0.7: {(arr > 0.7).sum()}")
    print(f"  > 0.5: {(arr > 0.5).sum()}")
    print(f"  > 0.3: {(arr > 0.3).sum()}")
    print(f"  > 0.1: {(arr > 0.1).sum()}")
    print(f"  median: {np.median(arr):.3f}")
    print(f"  max: {arr.max():.3f}")


if __name__ == "__main__":
    main()
