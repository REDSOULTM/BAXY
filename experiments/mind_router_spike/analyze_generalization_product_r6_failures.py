"""Promote every opened R6 miss to development without rewriting evidence."""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    analyze_generalization_product_r3_failures as analyzer,
)
from scripts import build_generalization_product_holdout_r6 as campaign  # noqa: E402


def configure() -> None:
    analyzer.campaign = campaign
    analyzer.DEVELOPMENT = (
        REPO / "artifacts/development/generalization_product_r6_failures.v1.jsonl"
    )
    analyzer.ANALYSIS = (
        REPO
        / "artifacts/holdout/generalization_product_holdout_r6_failure_analysis.json"
    )
    analyzer.CAMPAIGN = "r6"
    analyzer.TOTAL_CASES = 600
    analyzer.MIND_CASES = 588
    analyzer.MEMORY_CASES = 12
    analyzer.MEMORY_TEST_PREFIX = "RoutesBlindR6MemoryStatusRequests("
    analyzer.SOURCE_CUT = "blind_generalization_product_r6_opened"
    analyzer.ANALYSIS_SCHEMA = "baxy.generalization-product-r6-failure-analysis.v1"


def main() -> int:
    configure()
    return analyzer.main()


if __name__ == "__main__":
    raise SystemExit(main())
