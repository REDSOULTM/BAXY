"""MediaPipe CPU throttle — import this BEFORE mediapipe or vision tasks.

P7 improvement: limits MediaPipe's CPU usage to avoid starving Whisper
or the LLM during live camera input. Same policy as scripts/_ort_throttle
for the STT, with one key difference: the STT process pins to the FIRST
logical cores, so the camera process pins to the LAST ones — both throttled
without fighting over the same cores.

Escape hatches: GEMMA4_MP_THROTTLE=0 disables it; GEMMA4_MP_THREADS=N sets
the thread budget (default 2).
"""
from __future__ import annotations

import os

_APPLIED = False


def _pick_cores(n_logical: int, n_threads: int) -> list[int]:
    """Last (n_threads + 1) logical cores — disjoint from the STT's first cores."""
    count = min(max(1, n_threads + 1), max(1, n_logical))
    return list(range(n_logical))[-count:]


def apply(n_threads: int | None = None) -> None:
    global _APPLIED
    if _APPLIED:
        return
    if (os.environ.get("GEMMA4_MP_THROTTLE", "1") or "1").strip().lower() in {"0", "false", "no", "off"}:
        _APPLIED = True
        return
    if n_threads is None:
        try:
            n_threads = max(1, int(os.environ.get("GEMMA4_MP_THREADS", "2")))
        except ValueError:
            n_threads = 2

    # Set env vars for XNNPACK and OpenMP (read at mediapipe/TFLite import time).
    os.environ.setdefault("OMP_NUM_THREADS", str(n_threads))
    os.environ.setdefault("MKL_NUM_THREADS", str(n_threads))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(n_threads))
    os.environ.setdefault("TFLITE_NUM_THREADS", str(n_threads))

    try:
        import psutil

        p = psutil.Process()
        n_logical = psutil.cpu_count(logical=True) or 4
        p.cpu_affinity(_pick_cores(n_logical, n_threads))
        try:
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        except Exception as exc:
            print(f"[_mp_throttle] priority warning: {exc}")
    except Exception as exc:
        print(f"[_mp_throttle] affinity warning: {exc}")

    _APPLIED = True
