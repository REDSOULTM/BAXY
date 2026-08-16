"""Seal a fresh execution-inert catalogue surface against the current tree."""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import build_catalog_surface_holdout_r22 as builder  # noqa: E402
from scripts import build_catalog_surface_holdout_r26 as r26  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/catalog_surface_current_tree_r1.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/catalog_surface_current_tree_r1.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/catalog_surface_current_tree_r1_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/catalog_surface_current_tree_r1_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/catalog_surface_current_tree_r1_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/catalog_surface_current_tree_r1_product.json"
PRIOR_CORPORA = (*r26.PRIOR_CORPORA, r26.OUTPUT)
POLICY_SOURCES = r26.POLICY_SOURCES
BUILDER_DEPENDENCIES = (*r26.BUILDER_DEPENDENCIES, Path(r26.__file__).resolve())
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_catalog_surface_current_tree_r1.py",
    REPO / "experiments/mind_router_spike/analyze_catalog_surface_current_tree_r1.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)


def _fresh_surface(language: str, text: str) -> str:
    body = text.strip().rstrip(".!?").strip()
    suffix = {
        "es": "; con eso termina mi solicitud por ahora.",
        "en": "; that completes my request for now.",
        "spanglish": "; con eso, my request is complete for now.",
    }[language]
    return body + suffix


def configure() -> None:
    builder.OUTPUT = OUTPUT
    builder.PREREGISTRATION = PREREGISTRATION
    builder.MIND_OUTPUT = MIND_OUTPUT
    builder.MIND_AUDIT = MIND_AUDIT
    builder.MEMORY_TRX = MEMORY_TRX
    builder.PRODUCT_OUTPUT = PRODUCT_OUTPUT
    builder.CAMPAIGN = "current-tree-r1"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.catalog-surface-current-tree.r1"
    builder.PREREGISTRATION_SCHEMA = (
        "baxy.catalog-surface-current-tree-preregistration.r1"
    )
    builder.SURFACE_NAME = "cross_language_request_completion"
    builder.METHOD_MATRIX = (
        "post_compound_repair_fresh_request_completion_tail_for_every_operation"
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
