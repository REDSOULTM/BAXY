"""Development sidecar that adds five frozen operation-ranker candidates.

This entrypoint is restricted to side-effect-free ``turn.decide`` probes.  It
does not bypass the product LLM, policy, grounding, confirmation, authenticated
catalogue, Kernel, or provider boundaries.
"""

from __future__ import annotations

from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.sparse import hstack

import baxy_mind.__main__ as mind
import baxy_mind.family_classifier as family_classifier_module
from baxy_mind.family_classifier import FamilyClassifier as ProductFamilyClassifier
from baxy_mind.planner import MAX_SHORTLIST_OPERATIONS, PlannerCatalog, PlannerTool
from experiments.mind_router_spike.probe_operation_shortlist_current_review import (
    NO_ACTION,
    _resources,
)


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "artifacts" / "research" / "operation_shortlist_v1"
_WORDS, _CHARACTERS, _CLASSES, _COEFFICIENTS, _INTERCEPT = _resources(ASSETS)
_LAST_RANKING: ContextVar[tuple[str, ...]] = ContextVar(
    "baxy_experiment_operation_ranking",
    default=(),
)
_PRODUCT_PRIORITIZED_FAMILY_TOOLS = mind._prioritized_family_tools
_PRODUCT_SHORTLIST = PlannerCatalog.shortlist


@lru_cache(maxsize=512)
def _rank(text: str) -> tuple[str, ...]:
    features = hstack(
        (_WORDS.transform([text]), _CHARACTERS.transform([text])),
        format="csr",
    )
    scores = np.asarray(features @ _COEFFICIENTS.T + _INTERCEPT).reshape(-1)
    order = np.argsort(-scores)
    return tuple(
        _CLASSES[int(index)]
        for index in order
        if _CLASSES[int(index)] != NO_ACTION
    )[:5]


def _merge_ranked(
    tools: tuple[PlannerTool, ...],
    base: tuple[PlannerTool, ...],
    ranking: tuple[str, ...],
) -> tuple[PlannerTool, ...]:
    by_name = {tool.name: tool for tool in tools}
    return tuple(
        {
            tool.name: tool
            for tool in (
                *(by_name[name] for name in ranking if name in by_name),
                *base,
            )
        }.values()
    )[:MAX_SHORTLIST_OPERATIONS]


class TrackingFamilyClassifier(ProductFamilyClassifier):
    def predict(self, text, available_families):
        _LAST_RANKING.set(_rank(text))
        return super().predict(text, available_families)


def _ranked_prioritized_family_tools(tools, *family_groups):
    base = _PRODUCT_PRIORITIZED_FAMILY_TOOLS(tools, *family_groups)
    return _merge_ranked(tools, base, _LAST_RANKING.get())


def _ranked_shortlist(self, objective, **kwargs):
    base = _PRODUCT_SHORTLIST(self, objective, **kwargs)
    return _merge_ranked(self.tools, base, _rank(objective))


family_classifier_module.FamilyClassifier = TrackingFamilyClassifier
mind._prioritized_family_tools = _ranked_prioritized_family_tools
PlannerCatalog.shortlist = _ranked_shortlist


if __name__ == "__main__":
    raise SystemExit(mind.main())
