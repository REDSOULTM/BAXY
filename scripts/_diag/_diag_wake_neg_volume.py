"""Measure total negative audio duration + window count (headers only).

SAFE: reads only soundfile headers (no decode, no inference). Fast.
"""
import sys, glob, time
from pathlib import Path
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
files = sorted(glob.glob(str(
    ROOT / "data/wake_universal_eval/negatives/LibriSpeech/**/*.flac"
), recursive=True))
print("total flac files:", len(files))

t0 = time.time()
tot_s = 0.0
tot_windows = 0
srset = set()
WIN, HOP = 32000, 8000
for f in files:
    info = sf.info(f)
    n = info.frames
    srset.add(info.samplerate)
    tot_s += n / info.samplerate
    nwin = max(1, (n - WIN) // HOP + 1) if n >= WIN else 0
    tot_windows += nwin
print("header scan time s:", round(time.time() - t0, 2))
print("total audio hours:", round(tot_s / 3600, 2))
print("samplerates present:", sorted(srset))
print("total sliding windows (predicts):", tot_windows)
print("est minutes @27ms/predict (throttled 2thr):",
      round(tot_windows * 0.027 / 60, 1))
