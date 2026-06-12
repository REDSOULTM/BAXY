"""Eval de CONFUSABLES del wake: % de palabras vecinas que disparan (fake-fires).

Gate G6: fire-rate <= 1% @ threshold de prod (0.25) sobre el held-out de
confusables (25 voces x 22 palabras, ver wake_universal_generate_confusables).
Reporta por palabra para ver qué vecino fonético es el más peligroso.

Uso: python scripts/wake_confusables_eval.py [--models-dir D] [--stem baxy]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import _ort_throttle  # noqa: F401,E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from gemma4_agent.voice.livekit_runtime import LiveKitWakeRuntime  # noqa: E402
from wake_universal_generate_confusables import CONFUSABLES  # noqa: E402

SR = 16000
WINDOW = 2 * SR
HOP = SR // 2
THRESHOLD = 0.25
CONF_DIR = ROOT / "data" / "wake_universal_eval" / "confusables_baxy"
MODELS_DIR = ROOT / "gemma4_agent" / "voice" / "models" / "livekit"


def score_clip(rt: LiveKitWakeRuntime, audio: np.ndarray) -> float:
    x = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    if x.size <= WINDOW:
        pad = np.zeros(WINDOW, dtype=np.int16)
        pad[-x.size:] = x
        return float(rt.predict(pad))
    best = 0.0
    for start in range(0, x.size - WINDOW + 1, HOP):
        best = max(best, float(rt.predict(x[start:start + WINDOW])))
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models-dir", default=str(MODELS_DIR))
    ap.add_argument("--stem", default="baxy")
    args = ap.parse_args()
    rt = LiveKitWakeRuntime(Path(args.models_dir), args.stem)
    assert rt.load(), rt.last_error

    clips = sorted(CONF_DIR.glob("*.wav"))
    assert clips, "faltan confusables (correr wake_universal_generate_confusables)"
    print(f"modelo {args.stem} | {len(clips)} clips confusables")

    fires_by_word: dict[str, list[int]] = {}
    scores = []
    t0 = time.time()
    for c in clips:
        w_idx = int(c.stem.split("__w")[1].split("__")[0])
        word = CONFUSABLES[w_idx]
        audio, sr = sf.read(str(c), dtype="float32")
        if audio.ndim > 1:
            audio = audio[:, 0]
        s = score_clip(rt, audio)
        scores.append(s)
        st = fires_by_word.setdefault(word, [0, 0])
        st[1] += 1
        if s >= THRESHOLD:
            st[0] += 1

    total = len(clips)
    fired = sum(v[0] for v in fires_by_word.values())
    rate = fired / total
    print(f"\nfake-fires: {fired}/{total} = {rate:.3%} @ thr {THRESHOLD} "
          f"-> {'PASS' if rate <= 0.01 else 'FAIL'} (gate <=1%)")
    print(f"scores: p50={np.median(scores):.3f} p90={np.percentile(scores, 90):.3f} "
          f"max={max(scores):.3f}")
    sc = np.asarray(scores)
    print("sweep: " + "  ".join(
        f"thr{t:.2f}={float(np.mean(sc >= t)):.3%}"
        for t in (0.20, 0.25, 0.30, 0.40, 0.50)))
    bad = {w: v for w, v in fires_by_word.items() if v[0]}
    if bad:
        print("por palabra (solo las que dispararon):")
        for w, v in sorted(bad.items(), key=lambda kv: -kv[1][0]):
            print(f"  {w:10} {v[0]}/{v[1]}")
    print(f"total {time.time() - t0:.0f}s")
    return 0 if rate <= 0.01 else 1


if __name__ == "__main__":
    raise SystemExit(main())
