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


__all__ = [
    "MAX_CPU_INFERENCE_THREADS",
    "bounded_cpu_threads",
    "cpu_session_options",
]
