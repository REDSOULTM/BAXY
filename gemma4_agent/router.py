"""The unified tool router — single public entry point.

2026-05-21: after the rebuild that applied the four deep-research reports, the
routing stack is ONE pipeline with ONE decision. This module is its public
face: import `router` and you have the whole thing. The internals stay split
into cohesive single-responsibility modules (the encoder/Tool2Vec retriever,
the intent centroids, the calibrated abstain head, the orchestrator) because
that is what reads well and tests well — but there is exactly one router, one
entry point, and one decision per turn. The dead BM25+RRF `router_v2` was
deleted; `intent_router` / `semantic_router` are now implementation details
reached through here.

Per-turn flow (all CPU, tens of ms warm):
    select_tool_names(text, plan, ...) ->
        keyword layer (precise action verbs, shrinking over time)
        UNION fine-tuned-encoder + Tool2Vec retrieval (suggest_tools_scored)
        gated by ONE calibrated abstain decision (abstain_head) with narrow
        escapes (confident peak, pending-intent, streaming continuation hint)

See docs/architecture/router_rebuild_2026_05_21.md for the measured results
(holdout recall 0.835->0.881, NO-TOOL keep 0.512->0.628, multilingual 0.79->0.90)
and the reproducible training recipe.
"""
from __future__ import annotations

# Orchestrator (the brain: keyword layer + abstain gate + capping).
from .planner import (
    MAX_SELECTED_TOOLS,
    MissionPlan,
    MissionStep,
    plan_mission,
    select_tool_names,
)

# Intent centroids (info / action / chitchat / selfref / meta).
from .intent_router import (
    classify_intent,
    is_conversational,
    wants_knowledge,
)

# Fine-tuned encoder + Tool2Vec retrieval over the tool vocabulary.
from .semantic_router import (
    TOOL_DESCRIPTIONS,
    embed,
    suggest_tools_scored,
    suggest_tools_semantic,
)

# Calibrated NO-TOOL abstention head.
from .abstain_head import (
    build_features as abstain_features,
    is_enabled as abstain_enabled,
    load_model as load_abstain_model,
)

# Per-tool logit head (each tool clears its own calibrated threshold) — the
# anti-bloat subset selector that yields 1-3 tools for a crisp command.
from .tool_head import (
    is_enabled as tool_head_enabled,
    load as load_tool_head,
)

# Conditional cross-encoder reranker — Stage-E tiebreaker that rescues short/
# ambiguous queries the bi-encoder placed too weakly (fires only on the
# empty-but-not-smalltalk band, so the common path pays nothing).
from .reranker import (
    is_enabled as reranker_enabled,
    rerank as rerank_tools,
    warm_up as warm_up_reranker,
)

__all__ = [
    # orchestrator
    "select_tool_names", "plan_mission", "MissionPlan", "MissionStep",
    "MAX_SELECTED_TOOLS",
    # intent
    "classify_intent", "is_conversational", "wants_knowledge",
    # retrieval
    "suggest_tools_scored", "suggest_tools_semantic", "embed",
    "TOOL_DESCRIPTIONS",
    # abstention
    "load_abstain_model", "abstain_features", "abstain_enabled",
    # per-tool subset selector
    "load_tool_head", "tool_head_enabled",
    # conditional cross-encoder rescue
    "rerank_tools", "reranker_enabled", "warm_up_reranker",
]
