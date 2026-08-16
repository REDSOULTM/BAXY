"""Seal a current-tree R24 surface holdout for every authenticated operation."""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import build_catalog_surface_holdout_r22 as builder  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/catalog_surface_holdout_r24.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/catalog_surface_holdout_r24.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/catalog_surface_holdout_r24_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/catalog_surface_holdout_r24_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/catalog_surface_holdout_r24_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/catalog_surface_holdout_r24_product.json"
R23_OUTPUT = REPO / "artifacts/holdout/catalog_surface_holdout_r23.jsonl"
POLICY_SOURCES = (
    *builder.POLICY_SOURCES,
    REPO / "src/baxy_mind/catalog_operation_aliases.py",
    REPO / "src/baxy_mind/data/catalog_operation_aliases.v1.json",
)
BUILDER_DEPENDENCIES = (
    REPO / "scripts/build_catalog_surface_holdout_r22.py",
    *builder.BUILDER_DEPENDENCIES,
)
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_catalog_surface_holdout_r24.py",
    REPO / "experiments/mind_router_spike/analyze_catalog_surface_holdout_r24.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
PRIOR_CORPORA = (*builder.PRIOR_CORPORA, builder.OUTPUT, R23_OUTPUT)


def _fresh_surface(language: str, text: str) -> str:
    body = text.strip().rstrip(".!?").strip()
    suffix = {
        "es": "; gracias, eso es todo!",
        "en": "; thank you, nothing else!",
        "spanglish": "; gracias, that's all!",
    }[language]
    return body + suffix


def configure() -> None:
    builder.OUTPUT = OUTPUT
    builder.PREREGISTRATION = PREREGISTRATION
    builder.MIND_OUTPUT = MIND_OUTPUT
    builder.MIND_AUDIT = MIND_AUDIT
    builder.MEMORY_TRX = MEMORY_TRX
    builder.PRODUCT_OUTPUT = PRODUCT_OUTPUT
    builder.CAMPAIGN = "r24"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.catalog-surface-holdout.r24"
    builder.PREREGISTRATION_SCHEMA = "baxy.catalog-surface-preregistration.r24"
    builder.SURFACE_NAME = "gratitude_social_closure"
    builder.METHOD_MATRIX = (
        "current_tree_fresh_gratitude_closure_for_every_operation"
    )
    builder.BUILDER_DEPENDENCIES = BUILDER_DEPENDENCIES
    builder.MEASUREMENT_SOURCES = MEASUREMENT_SOURCES
    builder.POLICY_SOURCES = POLICY_SOURCES
    builder.PRIOR_CORPORA = PRIOR_CORPORA
    builder._fresh_surface = _fresh_surface


def main() -> int:
    configure()
    return builder.main()


if __name__ == "__main__":
    raise SystemExit(main())
