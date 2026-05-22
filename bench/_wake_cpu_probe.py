"""One-shot CPU probe for the wake predict-throttle (overnight Phase 3, eje:
LATENCIA). Loads the REAL wake model and feeds N seconds of synthetic 16 kHz
audio in 32 ms chunks, measuring process CPU time. Run twice with
GEMMA4_WAKE_PREDICT_EVERY_N=1 and =4 to confirm the ~75%-less-CPU claim.

Safe: CPU/ONNX only, no GPU, no mic. Uses scripts/_ort_throttle to avoid the
documented PC-freeze (ONNX busy-wait). Prints one CSV line: every_n,cpu_s,chunks.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import _ort_throttle  # noqa: F401  (side-effect: throttle ORT)
except Exception:
    pass

import numpy as np

from gemma4_agent.voice.wake import WakeDetector, LIVEKIT_PREDICT_EVERY_N_CHUNKS

SR = 16000
CHUNK = 512  # 32 ms at 16 kHz
SECONDS = float(os.environ.get("PROBE_SECONDS", "30"))


def main() -> int:
    det = WakeDetector(on_wake=lambda *a, **k: None)
    if not det.load():
        print(f"LOAD_FAILED {det.last_error}", file=sys.stderr)
        return 1
    backend = getattr(det, "_backend", "?")
    if backend != "livekit":
        print(f"SKIP backend={backend} (probe targets livekit)", file=sys.stderr)
        return 2

    rng = np.random.default_rng(0)
    n_chunks = int(SECONDS * SR / CHUNK)
    # Pre-generate quiet, speech-like noise so generation isn't in the timed loop.
    chunks = [(rng.standard_normal(CHUNK) * 300).astype(np.int16) for _ in range(n_chunks)]

    # Warm one predict so model init isn't counted.
    for c in chunks[:70]:
        det.feed(c)

    t0 = time.process_time()
    for c in chunks:
        det.feed(c)
    cpu = time.process_time() - t0
    print(f"{LIVEKIT_PREDICT_EVERY_N_CHUNKS},{cpu:.4f},{n_chunks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
