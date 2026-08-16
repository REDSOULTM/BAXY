"""Does the evidence expansion crowd the right operation out of the shortlist?

The policy schema's enum only admits shortlisted operations, so an operation the
shortlist omits is one the model physically cannot name. A measurement of the
policy's tool calling found that on 39.5% of turns whose answer is known, the
expected operation was never offered -- the model was losing before it was
consulted (policy_tool_quality_20260731.json).

This detector isolates the mechanism without the LLM. `PlannerCatalog.shortlist`
ranks families in three tiers: a family named by the turn-evidence expansion
(tier 2), a family that expansion is lexically related to (tier 1) and every
other family, ranked by the catalog's OWN semantic score (tier 0). Only
MAX_SHORTLIST_FAMILIES slots exist. The expansion returns up to
MAX_CANDIDATE_FAMILIES labels and each label pulls in up to three related
families, so tiers 1 and 2 can exceed the slot count on their own and the
catalog's semantic ranking is never consulted.

It compares, over the frozen oracle corpus, the shortlist the product builds
against the shortlist the catalog would build from its own ranking alone. It
invokes no model, dispatches no operation and changes nothing.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
TESTS = REPO / "tests"
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

OUTPUT = REPO / "artifacts" / "fixes" / "shortlist_recall_20260731.json"


def _load_catalog(capabilities: list[dict], encoder: Any) -> Any:
    from baxy_mind.planner import PlannerCatalog

    return PlannerCatalog(capabilities, encoder=encoder)


def run(use_encoder: bool) -> dict[str, Any]:
    import test_effect_intent as frozen
    from scripts.baxy_runtime_config import (
        DEFAULT_RUNTIME_MANIFEST,
        public_runtime_identity,
        resolve_runtime,
    )
    from scripts.measure_mind_budget import (
        DEFAULT_CORE_CANDIDATES,
        PROFILE_LIMITS,
        current_core_capabilities,
        discover_core,
        sidecar_environment,
    )

    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES)))

    # The E5 worker and the evidence corpus are located through the same
    # environment the sidecar receives; without it the router never becomes
    # ready and the measurement would silently fall back to lexical ranking.
    import os

    os.environ.update(sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=PROFILE_LIMITS["gpu"]["llm_http"],
    ))

    encoder = None
    evidence = None
    router = None
    if use_encoder:
        # The same encoder and evidence service the sidecar builds, so the
        # `product` arm below is the real shortlist and not an approximation.
        import time

        from baxy_mind.router import ProcessIntentRouter, RequestBudgetEncoder
        from baxy_mind.turn_evidence import TurnEvidenceService

        router = ProcessIntentRouter()
        if not router.try_ready(180.0):
            raise RuntimeError("el router E5 no quedó listo")
        encoder = RequestBudgetEncoder(router)
        evidence = TurnEvidenceService()
        evidence.start(encoder, lambda: router.try_ready(0.0))
        deadline = time.monotonic() + 185.0
        while evidence.state == "building" and time.monotonic() < deadline:
            time.sleep(0.1)
        # Fail loudly rather than silently comparing two identical arms: an
        # unavailable evidence corpus makes `candidate_families` return () and
        # the expansion arm becomes the catalog-only arm, which would look like
        # `the expansion is innocent` when in fact it was never exercised.
        if evidence.state != "ready":
            raise RuntimeError(
                "la evidencia de turno no quedó lista "
                f"(estado={evidence.state!r}); sin ella la expansión no se "
                "ejercita y la comparación no significa nada")

    # The sidecar never hands raw capabilities to the planner: they cross the
    # same authenticated validation `catalog.configure` performs.
    from baxy_mind.__main__ import configure_tools

    catalog = _load_catalog(configure_tools(capabilities), encoder)

    cases = [
        {"text": text, "expected": list(operations)}
        for text, operations in frozen.CASES
        if operations
    ]

    rows: list[dict[str, Any]] = []
    for case in cases:
        preferred: tuple[str, ...] = ()
        if evidence is not None and encoder is not None:
            preferred = evidence.candidate_families(case["text"], encoder)
        product = [tool.name for tool in catalog.shortlist(
            case["text"], preferred_families=preferred)]
        catalog_only = [tool.name for tool in catalog.shortlist(case["text"])]
        want = case["expected"]
        rows.append({
            "text": case["text"],
            "expected": want,
            "preferred_families": list(preferred),
            "product_offers_all": all(o in product for o in want),
            "catalog_only_offers_all": all(o in catalog_only for o in want),
            "product_shortlist": product,
            "catalog_only_shortlist": catalog_only,
        })

    # Sweep the three cuts that decide what the model may name, in one process:
    # building E5 and the evidence corpus is the expensive part, computing a
    # shortlist is not. Recall alone would be a blind objective, so the mean
    # shortlist length travels with it as the prompt-cost proxy.
    sweep: list[dict[str, Any]] = []
    if use_encoder:
        from baxy_mind import planner as planner_module

        original = (
            planner_module.MAX_CATALOG_GUARANTEED_FAMILIES,
            planner_module.MAX_FAMILY_OPERATIONS,
            planner_module.FAMILY_RELEVANCE_BAND,
            planner_module.LEADING_FAMILIES,
            planner_module.FAMILY_RELEVANCE_BAND_LEADING,
        )
        try:
            for leading in (0, 1, 2, 3, 10):
                for band_lead in (0.08, 0.15, 0.25):
                    for take in (3, 4):
                        planner_module.MAX_CATALOG_GUARANTEED_FAMILIES = 8
                        planner_module.MAX_FAMILY_OPERATIONS = take
                        planner_module.FAMILY_RELEVANCE_BAND = 0.035
                        planner_module.LEADING_FAMILIES = leading
                        planner_module.FAMILY_RELEVANCE_BAND_LEADING = band_lead
                        hit = 0
                        sizes: list[int] = []
                        for row in rows:
                            names = [
                                tool.name for tool in catalog.shortlist(
                                    row["text"],
                                    preferred_families=row["preferred_families"],
                                )
                            ]
                            sizes.append(len(names))
                            if all(o in names for o in row["expected"]):
                                hit += 1
                        sweep.append({
                            "leading_families": leading,
                            "leading_band": band_lead,
                            "family_operations": take,
                            "recall": hit,
                            "recall_share": round(hit / len(rows), 4),
                            "mean_shortlist": round(sum(sizes) / len(sizes), 2),
                            "max_shortlist": max(sizes),
                        })
        finally:
            (
                planner_module.MAX_CATALOG_GUARANTEED_FAMILIES,
                planner_module.MAX_FAMILY_OPERATIONS,
                planner_module.FAMILY_RELEVANCE_BAND,
                planner_module.LEADING_FAMILIES,
                planner_module.FAMILY_RELEVANCE_BAND_LEADING,
            ) = original

    exercised = sum(1 for row in rows if row["preferred_families"])
    if use_encoder and not exercised:
        raise RuntimeError(
            "candidate_families no devolvió ninguna familia en 57 casos: la "
            "expansión no se ejercitó y los dos brazos son el mismo")

    product_recall = sum(1 for row in rows if row["product_offers_all"])
    catalog_recall = sum(1 for row in rows if row["catalog_only_offers_all"])
    lost_to_expansion = [
        row["text"] for row in rows
        if row["catalog_only_offers_all"] and not row["product_offers_all"]
    ]
    gained_by_expansion = [
        row["text"] for row in rows
        if row["product_offers_all"] and not row["catalog_only_offers_all"]
    ]

    report = {
        "schema": "baxy.shortlist-recall.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "model_invocations": 0,
        "encoder_used": bool(use_encoder),
        "runtime": public_runtime_identity(runtime) if use_encoder else None,
        "question": (
            "does the turn-evidence family expansion crowd the expected "
            "operation out of the shortlist the model is allowed to name?"),
        "cases": len(cases),
        "recall": {
            "product": product_recall,
            "catalog_ranking_only": catalog_recall,
            "product_share": round(product_recall / len(cases), 4) if cases else None,
            "catalog_only_share": round(
                catalog_recall / len(cases), 4) if cases else None,
        },
        "sweep": sweep,
        "lost_to_the_expansion": lost_to_expansion,
        "gained_by_the_expansion": gained_by_expansion,
        "reading": (
            "`lost_to_the_expansion` are turns whose expected operation the "
            "catalog's own ranking WOULD have offered and the expansion "
            "displaced. `gained_by_the_expansion` are the turns the expansion "
            "rescues. The expansion is advisory by design, so it should add "
            "recall, never remove it; every entry in the first list is the "
            "advisory path overruling the authenticated catalog."),
        "rows": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-encoder", action="store_true",
        help="rank lexically only; the expansion cannot be measured without E5")
    args, _ = parser.parse_known_args()
    report = run(not args.no_encoder)
    print(json.dumps({
        "cases": report["cases"],
        "recall": report["recall"],
        "lost_to_the_expansion": report["lost_to_the_expansion"],
        "gained_by_the_expansion": report["gained_by_the_expansion"],
        "sweep": report["sweep"],
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
