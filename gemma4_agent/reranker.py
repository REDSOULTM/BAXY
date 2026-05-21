"""Conditional cross-encoder reranker — the research's Stage-E tiebreaker.

The four reports recommend a cross-encoder reranker fired CONDITIONALLY on the
uncertainty band (compass_bbd4: "bge-reranker-v2-m3 on top-15 IF top-1 fused
score in [0.40,0.65]... fires on ~10-15% of turns"). A cross-encoder reads the
(query, tool-description) pair jointly, so it resolves short/ambiguous queries
the bi-encoder places weakly — exactly the residual failures ("who directed
Oppenheimer" -> empty, "cuántas pestañas" -> empty).

We use a SMALL multilingual cross-encoder (mmarco-mMiniLMv2-L12, ~120MB, ~50ms/
pair on CPU) instead of the 2.3GB bge-reranker, per the report's lighter
alternative ("MS-MARCO-MiniLM ~40ms/batch, accept ~1 nDCG point"). It fires ONLY
when the primary router is UNCERTAIN (empty or single weak candidate) and the
turn is not clearly smalltalk — so the common, confident path pays nothing.

Lazy-loaded, fully optional: if the model is absent or disabled the router
behaves exactly as before. Disable with GEMMA4_RERANKER=0.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

_MODEL_NAME = os.environ.get(
    "GEMMA4_RERANKER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
# Only rerank tools whose cross-encoder score clears this (model-specific; the
# mmarco model outputs logits ~[-11,+11], higher = more relevant). Tuned so a
# genuine match passes and noise doesn't.
_SCORE_FLOOR = float(os.environ.get("GEMMA4_RERANKER_FLOOR", "-3.0"))
_TOP_K = int(os.environ.get("GEMMA4_RERANKER_TOPK", "3"))


@dataclass
class _State:
    model: Any | None = None
    disabled: bool = False
    tried: bool = False


_S = _State()


def is_enabled() -> bool:
    raw = (os.environ.get("GEMMA4_RERANKER") or "").strip().casefold()
    return raw not in {"0", "false", "no", "off"}


def _load() -> Any | None:
    if _S.model is not None:
        return _S.model
    if _S.disabled or _S.tried:
        return _S.model
    _S.tried = True
    try:
        from sentence_transformers import CrossEncoder
        _S.model = CrossEncoder(_MODEL_NAME, max_length=128)
        return _S.model
    except Exception:
        _S.disabled = True
        return None


def warm_up() -> None:
    if is_enabled():
        _load()


def rerank(query: str, candidates: list[tuple[str, str]]) -> list[str]:
    """Score (tool, description) candidates jointly against the query; return
    the tools whose score clears the floor, best first, capped to _TOP_K.
    `candidates` is a list of (tool_name, short_description). Returns [] on any
    failure (caller keeps its existing subset)."""
    if not is_enabled() or not candidates:
        return []
    m = _load()
    if m is None:
        return []
    try:
        pairs = [(query, desc) for _, desc in candidates]
        scores = m.predict(pairs, show_progress_bar=False)
        ranked = sorted(zip(candidates, scores), key=lambda x: -float(x[1]))
        out = [c[0] for (c, s) in ranked if float(s) >= _SCORE_FLOOR]
        return out[:_TOP_K]
    except Exception:
        return []
