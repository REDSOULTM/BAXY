"""MediaPipe CPU throttle — import this BEFORE mediapipe or vision tasks.

P7 improvement: limits MediaPipe's CPU usage to avoid starving Whisper
or the LLM during live camera input.
"""
from __future__ import annotations

import os

_APPLIED = False


def apply(n_threads: int = 2) -> None:
    global _APPLIED
    if _APPLIED:
        return

    # Set env vars for XNNPACK and OpenMP
    os.environ.setdefault("OMP_NUM_THREADS", str(n_threads))
    os.environ.setdefault("MKL_NUM_THREADS", str(n_threads))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(n_threads))
    os.environ.setdefault("TFLITE_NUM_THREADS", str(n_threads))

    try:
        import psutil
        p = psutil.Process()
        n_logical = psutil.cpu_count(logical=True) or 4
        # Use first (n_threads + 1) logical cores
        cores = list(range(min(n_threads + 1, n_logical)))
        p.cpu_affinity(cores)
        try:
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        except Exception:
            pass
    except Exception as exc:
        print(f"[_mp_throttle] affinity warning: {exc}")

    _APPLIED = True
