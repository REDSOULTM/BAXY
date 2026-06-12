"""fp/hr del wake sobre el pool de negativos held-out (~10 h LibriSpeech).

Gate de producto: fp/hr <= 1.0 @ threshold de prod (0.25). Ventana deslizante
2 s / hop 0.5 s con cooldown de 2 s entre fires (un disparo real bloquea la
escucha ese tiempo, así que dos ventanas contiguas sobre el umbral = 1 fire).

Uso: python scripts/wake_fp_hours_eval.py [--models-dir D] [--stem baxy]
                                          [--max-files N]
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

SR = 16000
WINDOW = 2 * SR
HOP = SR // 2
COOLDOWN_S = 2.0
THRESHOLD = 0.25
NEG_DIR = ROOT / "data" / "wake_universal_eval" / "negatives"
MODELS_DIR = ROOT / "gemma4_agent" / "voice" / "models" / "livekit"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models-dir", default=str(MODELS_DIR))
    ap.add_argument("--stem", default="baxy")
    ap.add_argument("--max-files", type=int, default=0)
    args = ap.parse_args()

    rt = LiveKitWakeRuntime(Path(args.models_dir), args.stem)
    assert rt.load(), rt.last_error
    files = sorted(NEG_DIR.glob("**/*.flac"))
    if args.max_files:
        files = files[:args.max_files]
    print(f"modelo {args.stem} | {len(files)} archivos negativos")

    total_s, fires = 0.0, 0
    t0 = time.time()
    for k, f in enumerate(files):
        try:
            audio, sr = sf.read(str(f), dtype="float32")
        except Exception:
            continue
        if audio.ndim > 1:
            audio = audio[:, 0]
        if sr != SR:
            continue
        total_s += audio.size / SR
        x = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
        cooldown_until = -1.0
        for start in range(0, max(1, x.size - WINDOW + 1), HOP):
            t_pos = start / SR
            if t_pos < cooldown_until:
                continue
            w = x[start:start + WINDOW]
            if w.size < WINDOW:
                break
            if float(rt.predict(w)) >= THRESHOLD:
                fires += 1
                cooldown_until = t_pos + COOLDOWN_S
        if (k + 1) % 500 == 0:
            hrs = total_s / 3600
            print(f"  {k + 1}/{len(files)}  {hrs:.2f}h  fires={fires} "
                  f"({time.time() - t0:.0f}s)")

    hrs = total_s / 3600
    fph = fires / max(0.01, hrs)
    print(f"\nfp/hr = {fph:.3f}  ({fires} fires en {hrs:.2f} h) "
          f"@ thr {THRESHOLD}  -> {'PASS' if fph <= 1.0 else 'FAIL'} (gate <=1.0)")
    print(f"total {time.time() - t0:.0f}s")
    return 0 if fph <= 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
