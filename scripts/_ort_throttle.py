"""ONNX Runtime CPU throttle — import this BEFORE livekit.wakeword.

Sprint 7.5 (2026-05-19): the universal eval froze the operator's PC
twice by saturating all 24 logical cores. Root causes:
  1. LiveKit's WakeWordModel creates ort.InferenceSession without
     SessionOptions, so ONNX defaults to all-cores intra-op threads.
  2. ONNX Runtime busy-waits ("spinning") between jobs, pinning every
     thread to 100% even when idle.

Three layers of defense, all applied at import time:
  A. Monkeypatch ort.InferenceSession so every session ONLY gets:
       intra_op_num_threads = N   (default 3)
       inter_op_num_threads = 1
       session.intra_op.allow_spinning = 0   (no busy-wait)
       execution_mode = SEQUENTIAL
  B. Pin the whole process to the first N*2 logical cores via psutil
     affinity (OS-level cap — ONNX cannot escape it).
  C. Set OMP/MKL env vars for any openmp-based ops.

Usage:
    import _ort_throttle           # sets env + affinity, patches ORT
    _ort_throttle.apply(n_threads=3)
    # ... now import livekit.wakeword etc.
"""
from __future__ import annotations

import os

_APPLIED = False


def apply(n_threads: int = 3) -> None:
    global _APPLIED
    if _APPLIED:
        return

    # Layer C: env vars (must be set before numpy/onnx import ideally).
    os.environ.setdefault("OMP_NUM_THREADS", str(n_threads))
    os.environ.setdefault("MKL_NUM_THREADS", str(n_threads))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(n_threads))
    os.environ.setdefault("ORT_DISABLE_SPINNING", "1")

    # Layer B: process affinity — hard OS cap.
    try:
        import psutil
        p = psutil.Process()
        n_logical = psutil.cpu_count(logical=True) or 4
        # Use first (n_threads + 1) logical cores, leave the rest free.
        cores = list(range(min(n_threads + 1, n_logical)))
        p.cpu_affinity(cores)
        # Lower priority so foreground apps win the scheduler.
        try:
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        except Exception:
            pass
    except Exception as exc:  # affinity unreliable on some Windows builds
        print(f"[_ort_throttle] affinity warning: {exc}")

    # Layer A: monkeypatch ORT InferenceSession.
    try:
        import onnxruntime as ort

        _orig_init = ort.InferenceSession.__init__

        def _throttled_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if kwargs.get("sess_options") is None and len(args) < 2:
                so = ort.SessionOptions()
                so.intra_op_num_threads = n_threads
                so.inter_op_num_threads = 1
                so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                try:
                    so.add_session_config_entry(
                        "session.intra_op.allow_spinning", "0",
                    )
                except Exception:
                    pass
                kwargs["sess_options"] = so
            return _orig_init(self, *args, **kwargs)

        ort.InferenceSession.__init__ = _throttled_init  # type: ignore[assignment]
        print(f"[_ort_throttle] applied: {n_threads} intra threads, "
              f"no spinning, affinity capped")
    except Exception as exc:
        print(f"[_ort_throttle] ORT patch warning: {exc}")

    _APPLIED = True
