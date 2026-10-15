"""The llama-server settings the mind reads from the environment: context and batch sizes, KV cache,
GPU slots, health polling, request timeout, the loopback endpoint and the decider's private state directory.
"""

from __future__ import annotations

import math
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


MAX_CONTEXT_TOKENS = 12288
# M61 (goal v3 step 7, VRAM ≤ 3,8 GB): 3 slots × 12 288 peaked at 3 876 MiB in the app (llama-server alone, measured per
# process). The decider needs ≤ ~8 100 tokens (catalog 6 100 + four-turn history ≤ 1 700 + output 300), so each slot
# gets 10 240 by default (−128 MiB); an explicit BAXY_MIND_CTX may still ask up to MAX_CONTEXT_TOKENS.
DEFAULT_CONTEXT_TOKENS = 10240
DEFAULT_BATCH_TOKENS = 2048
DEFAULT_UBATCH_TOKENS = 256
MAX_UBATCH_TOKENS = 512
# C03 integrated diagnostics: q8 fits the 4 GiB ceiling for the candidate;
# q4 degraded facts and confirmations. Keep the measured profile reproducible.
DEFAULT_KV_CACHE_TYPE = "q8_0"
# M59 (goal v3 step 7): V in q4_0 with K in q8_0 saved 284 MiB but has no fast CUDA flash-attention kernel for mixed
# K/V types in this llama.cpp build: decisions 2.5× slower (reserve p50 0.91 → 2.34 s) and the app timed out (v3e).
# V follows K unless BAXY_MIND_KV_CACHE_TYPE_V is set for a measured run.
DEFAULT_KV_CACHE_TYPE_V = DEFAULT_KV_CACHE_TYPE
MAX_CHAT_HISTORY_MESSAGES = 12
MAX_CHAT_HISTORY_CHARS = 6_000
LLM_HEALTH_POLL_TIMEOUT_SECONDS = 0.25
LLM_HEALTH_POLL_INTERVAL_SECONDS = 0.1


VALIDATED_CLASSIFIER_REUSE_CAPACITY = 32


def _gpu_slots_from_env(value: str | None) -> int:
    return int(value.strip()) if value is not None and value.strip() in {"2", "3"} else 3


# Slots of the owned GPU server (``-np``); the HTTP pool leases exactly these. M57 (goal v3 step 7, VRAM ≤ 3,8 GB):
# BAXY_MIND_GPU_SLOTS=2 lowers them for a measured run (each slot keeps its own KV cache: 3 × 12 288 tokens peaked at
# ≈ 4 040 MiB for all of BAXY in the app); the reserved slot stays the last one.
GPU_SERVER_SLOTS = _gpu_slots_from_env(os.environ.get("BAXY_MIND_GPU_SLOTS"))


def _own_decider_state_dir() -> tuple[Path, Any]:
    """A private directory for the decider's saved slot states, after sweeping those whose mind is gone.

    Estabilización A, revisión H3: a mind killed without ``close`` (the App kills its job 2 s after closing stdin)
    left its 170 MB behind. A mind keeps its directory's ``owner.lock`` open while it lives, so a lock that can be
    deleted has no owner and its directory goes.
    """

    for stale in Path(tempfile.gettempdir()).glob("baxy-decider-slot-*"):
        try:
            (stale / "owner.lock").unlink(missing_ok=True)
        except OSError:
            continue  # its mind still runs
        shutil.rmtree(stale, ignore_errors=True)
    directory = Path(tempfile.mkdtemp(prefix="baxy-decider-slot-"))
    return directory, (directory / "owner.lock").open("w")


def _request_timeout_from_env(value: str | None = None) -> float:
    cpu_fallback = os.environ.get("BAXY_MIND_NGL", "").strip() == "0"
    default_seconds = 120.0 if cpu_fallback else 19.0
    maximum_seconds = 120.0 if cpu_fallback else 55.0
    raw = (
        value
        if value is not None
        else os.environ.get("BAXY_MIND_LLM_REQUEST_TIMEOUT", str(default_seconds))
    )
    try:
        seconds = float(raw)
    except (TypeError, ValueError):
        seconds = default_seconds
    if not math.isfinite(seconds):
        seconds = default_seconds
    return max(1.0, min(maximum_seconds, seconds))


def _context_size_from_env(value: str | None = None) -> int:
    """Return the measured context ceiling, never the model's 128K maximum."""

    raw = value if value is not None else os.environ.get("BAXY_MIND_CTX", str(DEFAULT_CONTEXT_TOKENS))
    try:
        requested = int(str(raw).strip())
    except (TypeError, ValueError):
        requested = DEFAULT_CONTEXT_TOKENS
    return max(1024, min(MAX_CONTEXT_TOKENS, requested))


def _batch_sizes_from_env(
    batch_value: str | None = None,
    ubatch_value: str | None = None,
) -> tuple[int, int]:
    """Return a bounded llama.cpp prefill profile.

    These controls exist so the registered runtime can be measured on a
    constrained GPU without changing model weights, context, slot count or
    decoding semantics.  Invalid inherited environment must never create an
    oversized allocation or prevent the local sidecar from starting.
    """

    raw_batch = (
        batch_value
        if batch_value is not None
        else os.environ.get("BAXY_MIND_BATCH", str(DEFAULT_BATCH_TOKENS))
    )
    raw_ubatch = (
        ubatch_value
        if ubatch_value is not None
        else os.environ.get("BAXY_MIND_UBATCH", str(DEFAULT_UBATCH_TOKENS))
    )
    try:
        batch = int(str(raw_batch).strip())
    except (TypeError, ValueError):
        batch = DEFAULT_BATCH_TOKENS
    try:
        ubatch = int(str(raw_ubatch).strip())
    except (TypeError, ValueError):
        ubatch = DEFAULT_UBATCH_TOKENS
    batch = max(128, min(DEFAULT_BATCH_TOKENS, batch))
    ubatch = max(32, min(MAX_UBATCH_TOKENS, ubatch, batch))
    return batch, ubatch


def _kv_offload_from_env(value: str | None = None) -> bool:
    """Return whether llama.cpp may place the KV cache on the GPU."""

    raw = value if value is not None else os.environ.get("BAXY_MIND_KV_OFFLOAD", "1")
    return str(raw).strip().casefold() not in {"0", "false", "no", "off"}


def _kv_cache_type_from_env(value: str | None = None) -> str:
    """Return the promoted KV quantization with a bounded research override.

    M59 (goal v3 step 7): ``BAXY_MIND_KV_CACHE_TYPE_V`` sets the V cache alone (K keeps its type); V in q4_0 saved as
    much as K+V in q4_0 (server 3 724 → 3 440 MiB with 3 slots of 12 288) while K keeps the attention scores exact.
    """

    raw = (
        value
        if value is not None
        else os.environ.get("BAXY_MIND_KV_CACHE_TYPE", DEFAULT_KV_CACHE_TYPE)
    )
    candidate = str(raw).strip().casefold()
    return candidate if candidate in {"q8_0", "q4_0"} else DEFAULT_KV_CACHE_TYPE


def _loopback_endpoint_from_env(value: str | None = None) -> str | None:
    raw = value if value is not None else os.environ.get("BAXY_MIND_LLM_ENDPOINT")
    if raw is None or not raw.strip():
        return None
    parsed = urlparse(raw.strip())
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "BAXY_MIND_LLM_ENDPOINT debe ser un origen HTTP de loopback con puerto"
        )
    host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
    return f"http://{host}:{parsed.port}"
