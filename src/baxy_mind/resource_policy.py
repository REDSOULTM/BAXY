"""Shared resource ceilings for resident local inference runtimes.

ONNX Runtime defaults to one worker per physical core and keeps those workers
spinning between requests.  That is a useful server default and a hostile
desktop-assistant default: on this machine it can occupy all 24 logical CPUs
after the first TTS or wake inference.  Every directly owned CPU session goes
through this module so idle workers sleep and active inference stays bounded.
"""

from __future__ import annotations

import math
import os
from typing import Any


DEFAULT_CPU_INFERENCE_THREADS = 2
MAX_CPU_INFERENCE_THREADS = 4


def bounded_cpu_threads(
    environment_name: str,
    *,
    default: int = DEFAULT_CPU_INFERENCE_THREADS,
) -> int:
    """Return a finite desktop-safe thread count, optionally overridden."""

    try:
        configured = int(os.environ.get(environment_name, str(default)))
    except (TypeError, ValueError):
        configured = default
    if not math.isfinite(float(configured)):
        configured = default
    return max(1, min(MAX_CPU_INFERENCE_THREADS, configured))


def cpu_session_options(
    ort: Any,
    *,
    environment_name: str = "BAXY_MIND_ONNX_THREADS",
    default_threads: int = DEFAULT_CPU_INFERENCE_THREADS,
) -> Any:
    """Create non-spinning, sequential ONNX options for a resident CPU model."""

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = bounded_cpu_threads(
        environment_name,
        default=default_threads,
    )
    options.inter_op_num_threads = 1
    if hasattr(ort, "ExecutionMode"):
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.add_session_config_entry("session.intra_op.allow_spinning", "0")
    options.add_session_config_entry("session.inter_op.allow_spinning", "0")
    return options


def _lowest_available_affinity_mask(available_mask: int, count: int) -> int:
    selected = 0
    remaining = max(1, count)
    bit = 1
    while available_mask and remaining:
        if available_mask & bit:
            selected |= bit
            available_mask &= ~bit
            remaining -= 1
        bit <<= 1
    return selected


def constrain_current_windows_process() -> None:
    """Give the mind a hard CPU boundary before any native runtime loads."""

    if os.name != "nt":
        return

    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel32.SetPriorityClass.restype = ctypes.c_int
    kernel32.GetProcessAffinityMask.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    )
    kernel32.GetProcessAffinityMask.restype = ctypes.c_int
    kernel32.SetProcessAffinityMask.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
    kernel32.SetProcessAffinityMask.restype = ctypes.c_int
    process = kernel32.GetCurrentProcess()
    below_normal_priority_class = 0x00004000
    if not kernel32.SetPriorityClass(process, below_normal_priority_class):
        raise OSError(ctypes.get_last_error(), "SetPriorityClass failed")

    process_mask = ctypes.c_size_t()
    system_mask = ctypes.c_size_t()
    if not kernel32.GetProcessAffinityMask(
        process,
        ctypes.byref(process_mask),
        ctypes.byref(system_mask),
    ):
        raise OSError(ctypes.get_last_error(), "GetProcessAffinityMask failed")
    cpu_count = bounded_cpu_threads("BAXY_MIND_PROCESS_CPUS", default=4)
    selected = _lowest_available_affinity_mask(process_mask.value, cpu_count)
    if not selected or not kernel32.SetProcessAffinityMask(process, selected):
        raise OSError(ctypes.get_last_error(), "SetProcessAffinityMask failed")


__all__ = [
    "MAX_CPU_INFERENCE_THREADS",
    "bounded_cpu_threads",
    "constrain_current_windows_process",
    "cpu_session_options",
]
