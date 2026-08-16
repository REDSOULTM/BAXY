"""Aggregate the sealed R6 Mind and App-memory evidence exactly once."""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    analyze_generalization_product_holdout_r2 as analyzer,
)
from scripts import build_generalization_product_holdout_r6 as campaign  # noqa: E402


def configure() -> None:
    analyzer.MEASUREMENT_SOURCES = campaign.MEASUREMENT_SOURCES
    analyzer.MEMORY_TRX = campaign.MEMORY_TRX
    analyzer.MIND_OUTPUT = campaign.MIND_OUTPUT
    analyzer.CORPUS = campaign.OUTPUT
    analyzer.OUTPUT = campaign.PRODUCT_OUTPUT
    analyzer.POLICY_SOURCES = campaign.POLICY_SOURCES
    analyzer.PREREGISTRATION = campaign.PREREGISTRATION
    analyzer.CAMPAIGN = "r6"
    analyzer.RESULT_SCHEMA = "baxy.generalization-product-holdout-r6-result.v1"
    analyzer.RESULT_SCOPE = "sealed_blind_generalization_product_r6_population"
    analyzer.MEMORY_TEST_PREFIX = "RoutesBlindR6MemoryStatusRequests("
    analyzer.TOTAL_CASES = 600
    analyzer.MIND_CASES = 588
    analyzer.MEMORY_CASES = 12


def main() -> int:
    configure()
    return analyzer.main()


if __name__ == "__main__":
    raise SystemExit(main())
