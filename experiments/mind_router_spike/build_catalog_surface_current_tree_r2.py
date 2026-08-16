"""Prepare the distinct post-repair current-tree catalogue surface R2."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    build_catalog_surface_current_tree_r1 as r1,
)
from scripts import build_catalog_surface_holdout_r22 as builder  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/catalog_surface_current_tree_r2.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/catalog_surface_current_tree_r2.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/catalog_surface_current_tree_r2_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/catalog_surface_current_tree_r2_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/catalog_surface_current_tree_r2_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/catalog_surface_current_tree_r2_product.json"
PRIOR_CORPORA = (*r1.PRIOR_CORPORA, r1.OUTPUT)
POLICY_SOURCES = r1.POLICY_SOURCES
BUILDER_DEPENDENCIES = (*r1.BUILDER_DEPENDENCIES, Path(r1.__file__).resolve())
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_catalog_surface_current_tree_r2.py",
    REPO / "experiments/mind_router_spike/analyze_catalog_surface_current_tree_r2.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
_CLOSURES = {
    "es": (
        "; con esto concluye la tarea.",
        "; mi petición finaliza aquí.",
        "; la solicitud queda completada por ahora.",
    ),
    "en": (
        "; this concludes the task.",
        "; the request has been completed for now.",
        "; that ends my request.",
    ),
    "spanglish": (
        "; con esto, the task is done for now.",
        "; my request is now complete.",
        "; con eso, my task has been finished for now.",
    ),
}


def _fresh_surface(language: str, text: str) -> str:
    body = text.strip().rstrip(".!?").strip()
    closures = _CLOSURES[language]
    digest = hashlib.sha256(f"{language}\0{body}".encode()).digest()
    return body + closures[int.from_bytes(digest[:2], "big") % len(closures)]


def configure() -> None:
    builder.OUTPUT = OUTPUT
    builder.PREREGISTRATION = PREREGISTRATION
    builder.MIND_OUTPUT = MIND_OUTPUT
    builder.MIND_AUDIT = MIND_AUDIT
    builder.MEMORY_TRX = MEMORY_TRX
    builder.PRODUCT_OUTPUT = PRODUCT_OUTPUT
    builder.CAMPAIGN = "current-tree-r2"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.catalog-surface-current-tree.r2"
    builder.PREREGISTRATION_SCHEMA = (
        "baxy.catalog-surface-current-tree-preregistration.r2"
    )
    builder.SURFACE_NAME = "cross_language_request_completion_grammar"
    builder.METHOD_MATRIX = (
        "post_r1_systemic_multilingual_completion_grammar_fresh_variants"
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
