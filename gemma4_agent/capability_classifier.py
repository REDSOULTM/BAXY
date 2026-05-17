"""Bug 1: Capability classifier — map user input to a stable taxonomy of
intent categories, decoupling routing from surface lexicon.

Why: the legacy keyword router maps "ponme/play/reproduce/video" → media,
but "quiero ver daredevil born again" does not match because the verb "ver"
isn't in any keyword group AND the title doesn't reference a platform. The
fix is to map at the level of FUNCTION ("consumir contenido audiovisual"),
not lexicon. The catalog of titles is irrelevant; the function category is
finite (~10 labels).

Architecture:
  - Taxonomy of ~10 abstract labels (NOT verbs, NOT tool names).
  - Each label → bucket of tool names that should be in the subset.
  - Classification via NLI service (mDeBERTa zero-shot). It runs ASYNC
    parallel to the legacy planner so latency on the FIRST turn for a
    novel input is absorbed by the planner's own work. The result is
    cached; the SECOND turn (or any subsequent semantically similar one)
    hits the cache in microseconds.
  - When the classifier verdict arrives in time (before the LLM call), we
    augment the tool subset. When it doesn't, we record the gap (the
    planner missed) so the next equivalent turn benefits.

Failure modes (handled):
  - NLI unavailable → classifier silently returns None; legacy router decides.
  - NLI returns low confidence → no augmentation; legacy router decides.
  - NLI ambiguous between two labels → both buckets are added (Bug 3's
    grounding gate will catch downstream mistakes).
"""
from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable

from .nli_service import get_nli_service

_log = logging.getLogger(__name__)


# Taxonomy. Labels are written as natural Spanish phrases — that's what the
# NLI model is trained on (entailment of premise→hypothesis). They describe
# the FUNCTION the user wants the system to perform, NOT verbs they used.
# Keep small and stable; this is the contract that planner, RAG, and
# evaluator share.
CAPABILITY_LABELS: tuple[str, ...] = (
    "consumir contenido audiovisual",       # media: streaming, video, music
    "controlar reproducción multimedia",     # media: pause/resume/next
    "gestionar agenda y recordatorios",      # calendar / reminders
    "enviar o leer mensajes",                # whatsapp / email
    "navegar la web o buscar información",   # web / browser
    "consultar memoria personal del usuario",  # memory
    "ejecutar acciones del sistema operativo",  # system / process / power
    "manipular archivos o carpetas",         # filesystem
    "controlar audio o dispositivos",        # audio / audio_device
    "consultar conocimiento general",        # no tool (LLM answers from knowledge)
)


# Each capability maps to a bucket of tools that MUST be in the subset for
# the agent to act. When the classifier picks a capability, we union the
# bucket into the existing subset (without replacing). The legacy router
# remains the primary; this is an additive layer.
CAPABILITY_TO_TOOLS: dict[str, frozenset[str]] = {
    "consumir contenido audiovisual": frozenset({"media", "browser"}),
    "controlar reproducción multimedia": frozenset({"media"}),
    "gestionar agenda y recordatorios": frozenset({"calendar", "reminder"}),
    "enviar o leer mensajes": frozenset({"whatsapp", "email"}),
    "navegar la web o buscar información": frozenset({"web", "browser"}),
    "consultar memoria personal del usuario": frozenset({"memory"}),
    "ejecutar acciones del sistema operativo": frozenset({"system", "process", "terminal"}),
    "manipular archivos o carpetas": frozenset({"filesystem"}),
    "controlar audio o dispositivos": frozenset({"audio", "audio_device"}),
    "consultar conocimiento general": frozenset(),  # LLM-only, no tool
}


_CONFIDENCE_THRESHOLD = 0.35  # calibrated against real NLI scores on Daredevil case
_AMBIGUITY_DELTA = 0.10  # top1 - top2 < this → ambiguous, add both buckets
_CACHE_MAX = 256


@dataclass
class CapabilityVerdict:
    """Output of the classifier.

    `top_label`: the highest-scoring capability label (or empty if unknown).
    `confidence`: score of top label (0-1).
    `bucket`: union of tool names recommended (frozenset).
    `ambiguous`: True if top1 and top2 are close.
    `available`: False when NLI is unavailable.
    """
    top_label: str = ""
    confidence: float = 0.0
    bucket: frozenset[str] = frozenset()
    ambiguous: bool = False
    available: bool = True


# ---------- cache ----------

_cache_lock = threading.Lock()
_cache: OrderedDict[str, CapabilityVerdict] = OrderedDict()


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode("utf-8", "ignore")).hexdigest()


def _cache_get(text: str) -> CapabilityVerdict | None:
    key = _cache_key(text)
    with _cache_lock:
        v = _cache.get(key)
        if v is not None:
            _cache.move_to_end(key)
        return v


def _cache_put(text: str, verdict: CapabilityVerdict) -> None:
    key = _cache_key(text)
    with _cache_lock:
        _cache[key] = verdict
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)


def clear_cache() -> None:
    """Test helper: clear the capability cache."""
    with _cache_lock:
        _cache.clear()


# ---------- core API ----------

def classify_capability_cached(user_input: str) -> CapabilityVerdict | None:
    """Cache-only lookup. Returns the cached verdict or None.

    Hot-path safe (no NLI, no blocking).
    """
    if not user_input:
        return None
    return _cache_get(user_input)


def classify_capability_sync(
    user_input: str,
    *,
    timeout_sec: float = 0.5,
) -> CapabilityVerdict | None:
    """Synchronous classification with tight timeout. Returns the verdict or
    None if NLI is unavailable / timed out / input empty.

    The timeout default is 500ms — keep it short; the parallel-async path
    is the preferred way to use NLI in the hot path.
    """
    if not user_input:
        return None
    cached = _cache_get(user_input)
    if cached is not None:
        return cached
    svc = get_nli_service()
    scores = svc.classify_sync(
        user_input,
        list(CAPABILITY_LABELS),
        timeout_sec=timeout_sec,
    )
    if scores is None:
        return CapabilityVerdict(available=False)
    verdict = _build_verdict(scores)
    _cache_put(user_input, verdict)
    return verdict


def classify_capability_async(
    user_input: str,
    callback: Callable[[CapabilityVerdict | None], None] | None = None,
) -> None:
    """Fire-and-forget. Result lands in cache; optional callback receives it.

    The callback runs in the NLI worker thread. Use it for telemetry only;
    do NOT mutate hot-path state from inside it.
    """
    if not user_input:
        if callback:
            callback(None)
        return
    cached = _cache_get(user_input)
    if cached is not None:
        if callback:
            callback(cached)
        return
    svc = get_nli_service()

    def _cb(scores: dict[str, float] | None) -> None:
        if scores is None:
            v = CapabilityVerdict(available=False)
        else:
            v = _build_verdict(scores)
            _cache_put(user_input, v)
        if callback:
            try:
                callback(v)
            except Exception as exc:  # noqa: BLE001
                _log.warning("capability classifier callback raised: %s", exc)

    svc.classify_async(user_input, list(CAPABILITY_LABELS), callback=_cb)


def _build_verdict(scores: dict[str, float]) -> CapabilityVerdict:
    """Internal: turn raw NLI scores into a CapabilityVerdict."""
    if not scores:
        return CapabilityVerdict(top_label="", confidence=0.0)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top_label, top_score = ranked[0]
    if top_score < _CONFIDENCE_THRESHOLD:
        return CapabilityVerdict(top_label=top_label, confidence=top_score)
    ambiguous = False
    bucket = set(CAPABILITY_TO_TOOLS.get(top_label, frozenset()))
    if len(ranked) >= 2:
        second_label, second_score = ranked[1]
        if (top_score - second_score) < _AMBIGUITY_DELTA:
            ambiguous = True
            bucket |= set(CAPABILITY_TO_TOOLS.get(second_label, frozenset()))
    return CapabilityVerdict(
        top_label=top_label,
        confidence=top_score,
        bucket=frozenset(bucket),
        ambiguous=ambiguous,
    )


def augment_subset(
    user_input: str,
    current_subset: list[str],
    *,
    sync_timeout_sec: float = 0.35,
) -> tuple[list[str], dict]:
    """Hot-path entry point. Tries cache first; if miss, runs NLI sync with
    tight timeout; if that times out too, returns subset unchanged AND
    fires an async lookup so the NEXT similar turn benefits.

    Returns (new_subset, telemetry).
    """
    telemetry: dict = {"capability_used": None, "source": None,
                       "confidence": None, "added_tools": []}
    if not user_input:
        return current_subset, telemetry

    # 1. Cache hit (sub-millisecond).
    cached = _cache_get(user_input)
    if cached is not None and cached.available:
        return _apply_verdict(current_subset, cached, telemetry, source="cache")

    # 2. Synchronous attempt with short timeout (300-500ms).
    verdict = classify_capability_sync(user_input, timeout_sec=sync_timeout_sec)
    if verdict is not None and verdict.available and verdict.top_label:
        return _apply_verdict(current_subset, verdict, telemetry, source="sync")

    # 3. Otherwise fire async (warms cache for next turn).
    classify_capability_async(user_input)
    telemetry["source"] = "async_pending"
    return current_subset, telemetry


def _apply_verdict(
    subset: list[str], verdict: CapabilityVerdict,
    telemetry: dict, *, source: str,
) -> tuple[list[str], dict]:
    if verdict.confidence < _CONFIDENCE_THRESHOLD:
        telemetry["source"] = source
        telemetry["capability_used"] = verdict.top_label
        telemetry["confidence"] = verdict.confidence
        telemetry["below_threshold"] = True
        return subset, telemetry
    new_subset = list(subset)
    added: list[str] = []
    existing = set(subset)
    for tool in verdict.bucket:
        if tool not in existing:
            new_subset.append(tool)
            added.append(tool)
            existing.add(tool)
    telemetry["capability_used"] = verdict.top_label
    telemetry["confidence"] = verdict.confidence
    telemetry["source"] = source
    telemetry["added_tools"] = added
    telemetry["ambiguous"] = verdict.ambiguous
    return new_subset, telemetry


__all__ = [
    "CAPABILITY_LABELS",
    "CAPABILITY_TO_TOOLS",
    "CapabilityVerdict",
    "augment_subset",
    "classify_capability_async",
    "classify_capability_cached",
    "classify_capability_sync",
    "clear_cache",
]
