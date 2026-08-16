"""Seal a fresh execution-inert surface holdout for every Core operation."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from baxy_mind.catalog_operation_aliases import (  # noqa: E402
    exact_catalog_operation_plan,
)
from baxy_mind.effect_intent import _fold  # noqa: E402
from baxy_mind.planner import required_predecessors  # noqa: E402
from scripts.baxy_runtime_config import file_sha256  # noqa: E402
from scripts.build_generalization_product_holdout_r2 import (  # noqa: E402
    POLICY_SOURCES,
    catalog_identity,
    normalize_text,
    write_jsonl_atomic,
)
from scripts.catalog_seen_scenarios_v1 import SEEN_UTTERANCES  # noqa: E402
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    current_core_capabilities,
    discover_core,
    write_json_atomic,
)


OUTPUT = REPO / "artifacts/holdout/catalog_surface_holdout_r22.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/catalog_surface_holdout_r22.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/catalog_surface_holdout_r22_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/catalog_surface_holdout_r22_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/catalog_surface_holdout_r22_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/catalog_surface_holdout_r22_product.json"
CAMPAIGN = "r22"
BUILDER_SOURCE = Path(__file__).resolve()
ROW_SCHEMA = "baxy.catalog-surface-holdout.r22"
PREREGISTRATION_SCHEMA = "baxy.catalog-surface-preregistration.r22"
SURFACE_NAME = "polite_tail"
METHOD_MATRIX = "fresh_politeness_tail_surface_for_every_authenticated_operation"
BUILDER_DEPENDENCIES = (
    REPO / "scripts/catalog_seen_scenarios_v1.py",
    REPO / "scripts/build_generalization_product_holdout_r2.py",
)
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_catalog_surface_holdout_r22.py",
    REPO / "experiments/mind_router_spike/analyze_catalog_surface_holdout_r22.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
PRIOR_CORPORA = tuple(
    sorted((REPO / "artifacts/holdout").glob("generalization_product_holdout_v*.jsonl"))
) + (REPO / "artifacts/development/catalog_seen_scenarios_r2_dependency_complete.jsonl",)


def _fresh_surface(language: str, text: str) -> str:
    body = text.strip().rstrip(".!?").strip()
    suffix = {
        "es": "; por favor, eso es todo.",
        "en": "; please, that's the whole request.",
        "spanglish": "; please, eso es todo.",
    }[language]
    return body + suffix


def _prior_texts() -> set[str]:
    texts: set[str] = set()
    for path in PRIOR_CORPORA:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            value = row.get("text")
            if isinstance(value, str):
                texts.add(normalize_text(value))
    return texts


def build_rows(capabilities: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    capabilities = list(capabilities)
    names = {str(item["name"]) for item in capabilities}
    if len(names) != len(capabilities) or names != set(SEEN_UTTERANCES):
        raise RuntimeError(f"{CAMPAIGN.upper()} reviewed operation surface no longer matches Core")
    catalog_sha256, _count = catalog_identity(capabilities)
    rows: list[dict[str, Any]] = []
    for operation in sorted(names):
        language, seen_text = SEEN_UTTERANCES[operation]
        text = _fresh_surface(language, seen_text)
        normalized_for_alias = _fold(text).strip()
        if exact_catalog_operation_plan(normalized_for_alias) is not None:
            raise RuntimeError(
                f"{CAMPAIGN.upper()} accidentally reuses an exact alias: {operation}"
            )
        predecessors = required_predecessors(operation)
        plan = (*predecessors[:1], operation)
        if not set(plan) <= names:
            raise RuntimeError(
                f"{CAMPAIGN.upper()} dependency left the catalogue: {operation}"
            )
        rows.append(
            {
                "schema": ROW_SCHEMA,
                "case_id": f"{CAMPAIGN}-catalog-surface-"
                + operation.replace(".", "-"),
                "family": operation.split(".", 1)[0],
                "case_type": "single_action",
                "surface": SURFACE_NAME,
                "language": language,
                "owner": (
                    "app_private_memory_parser"
                    if operation.startswith("memory.")
                    else "mind_sidecar"
                ),
                "outcome": "action",
                "text": text,
                "target_operation": operation,
                "compatible_terminal_operation_sets": [list(plan)],
                "compatible_effect_operation_sets": [list(plan)],
                "execution_authority": False,
                "blind_holdout": True,
                "catalog_sha256": catalog_sha256,
            }
        )
    normalized = [normalize_text(str(row["text"])) for row in rows]
    if len(rows) != 169 or len(set(normalized)) != len(rows):
        raise RuntimeError(
            f"{CAMPAIGN.upper()} must contain 169 unique operation surfaces"
        )
    overlap = sorted(set(normalized) & _prior_texts())
    if overlap:
        raise RuntimeError(f"{CAMPAIGN.upper()} overlaps prior corpora: {overlap}")
    return rows


def build(args: argparse.Namespace) -> dict[str, Any]:
    evidence_paths = (
        args.output,
        args.preregistration,
        MIND_OUTPUT,
        MIND_AUDIT,
        MEMORY_TRX,
        PRODUCT_OUTPUT,
    )
    for path in evidence_paths:
        if path.exists():
            raise RuntimeError(
                f"refusing to overwrite {CAMPAIGN.upper()} state: {path}"
            )
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    rows = build_rows(capabilities)
    write_jsonl_atomic(args.output, rows)
    catalog_sha256, operation_count = catalog_identity(capabilities)
    owners = Counter(str(row["owner"]) for row in rows)
    languages = Counter(str(row["language"]) for row in rows)
    manifest = {
        "schema": PREREGISTRATION_SCHEMA,
        "blind_holdout": True,
        "preregistered_before_measurement": True,
        "measurement_status": "unopened",
        "authority": "turn_decision_and_private_parser_evaluation_only",
        "method": {
            "matrix": METHOD_MATRIX,
            "test_types": ["all_operation_surface_invariance"],
            "minimum_cases": 169,
            "minimum_exact_turn_accuracy": 0.99,
            "maximum_unsafe_effects": 0,
            "one_sided_95_binomial_lower_if_zero_failures": math.pow(
                0.05, 1.0 / len(rows)
            ),
            "statistical_scope": (
                "Exact operation coverage is claimed only for this sealed surface; "
                "R21 supplies the larger family-level generalization population."
            ),
            "references": [],
        },
        "population": {
            "cases": len(rows),
            "public_families": len({str(row["family"]) for row in rows}),
            "owners": dict(sorted(owners.items())),
            "case_types": {"single_action": len(rows)},
            "languages": dict(sorted(languages.items())),
            "surfaces": {SURFACE_NAME: len(rows)},
            "normalized_prior_overlap": 0,
            "authenticated_operations_covered": len(
                {str(row["target_operation"]) for row in rows}
            ),
        },
        "catalog": {"operations": operation_count, "sha256": catalog_sha256},
        "sources": {
            "builder": str(BUILDER_SOURCE.relative_to(REPO)),
            "builder_sha256": file_sha256(BUILDER_SOURCE),
            "builder_dependencies_sha256": {
                str(path.relative_to(REPO)): file_sha256(path)
                for path in BUILDER_DEPENDENCIES
            },
            "prior_corpora_sha256": {
                str(path.relative_to(REPO)): file_sha256(path) for path in PRIOR_CORPORA
            },
            "policy_sha256": {
                str(path.relative_to(REPO)): file_sha256(path)
                for path in POLICY_SOURCES
            },
            "measurement_sha256": {
                str(path.relative_to(REPO)): file_sha256(path)
                for path in MEASUREMENT_SOURCES
            },
        },
        "output": {
            "path": str(args.output.relative_to(REPO)),
            "sha256": file_sha256(args.output),
            "rows": len(rows),
        },
        "planned_measurement": {
            "mind_output": str(MIND_OUTPUT.relative_to(REPO)),
            "mind_raw_audit": str(MIND_AUDIT.relative_to(REPO)),
            "memory_trx": str(MEMORY_TRX.relative_to(REPO)),
            "product_output": str(PRODUCT_OUTPUT.relative_to(REPO)),
            "effects_executed": 0,
        },
    }
    write_json_atomic(args.preregistration, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--preregistration", type=Path, default=PREREGISTRATION)
    args = parser.parse_args()
    manifest = build(args)
    print(json.dumps(manifest["population"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
