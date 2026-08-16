"""Seal a post-fix R23 surface holdout for every authenticated operation."""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import build_catalog_surface_holdout_r22 as builder  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/catalog_surface_holdout_r23.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/catalog_surface_holdout_r23.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/catalog_surface_holdout_r23_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/catalog_surface_holdout_r23_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/catalog_surface_holdout_r23_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/catalog_surface_holdout_r23_product.json"
BUILDER_DEPENDENCIES = (
    REPO / "scripts/build_catalog_surface_holdout_r22.py",
    *builder.BUILDER_DEPENDENCIES,
)
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_catalog_surface_holdout_r23.py",
    REPO / "experiments/mind_router_spike/analyze_catalog_surface_holdout_r23.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
PRIOR_CORPORA = (*builder.PRIOR_CORPORA, builder.OUTPUT)


def _fresh_surface(language: str, text: str) -> str:
    body = text.strip().rstrip(".!?").strip()
    suffix = {
        "es": "; porfa, nada mas.",
        "en": "; that's all.",
        "spanglish": "; please, nothing else.",
    }[language]
    return body + suffix


def configure() -> None:
    builder.OUTPUT = OUTPUT
    builder.PREREGISTRATION = PREREGISTRATION
    builder.MIND_OUTPUT = MIND_OUTPUT
    builder.MIND_AUDIT = MIND_AUDIT
    builder.MEMORY_TRX = MEMORY_TRX
    builder.PRODUCT_OUTPUT = PRODUCT_OUTPUT
    builder.CAMPAIGN = "r23"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.catalog-surface-holdout.r23"
    builder.PREREGISTRATION_SCHEMA = "baxy.catalog-surface-preregistration.r23"
    builder.SURFACE_NAME = "alternate_social_closure"
    builder.METHOD_MATRIX = (
        "post_r22_systemic_social_closure_fix_fresh_tail_for_every_operation"
    )
    builder.BUILDER_DEPENDENCIES = BUILDER_DEPENDENCIES
    builder.MEASUREMENT_SOURCES = MEASUREMENT_SOURCES
    builder.PRIOR_CORPORA = PRIOR_CORPORA
    builder._fresh_surface = _fresh_surface


def main() -> int:
    configure()
    return builder.main()


if __name__ == "__main__":
    raise SystemExit(main())
