"""Aggregate the sealed R13 Mind and App-memory evidence exactly once."""

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
from scripts import build_generalization_product_holdout_r13 as campaign  # noqa: E402


def configure() -> None:
    analyzer.MEASUREMENT_SOURCES = campaign.MEASUREMENT_SOURCES
    analyzer.MEMORY_TRX = campaign.MEMORY_TRX
    analyzer.MIND_OUTPUT = campaign.MIND_OUTPUT
    analyzer.CORPUS = campaign.OUTPUT
    analyzer.OUTPUT = campaign.PRODUCT_OUTPUT
    analyzer.POLICY_SOURCES = campaign.POLICY_SOURCES
    analyzer.PREREGISTRATION = campaign.PREREGISTRATION
    analyzer.CAMPAIGN = "r13"
    analyzer.RESULT_SCHEMA = "baxy.generalization-product-holdout-r13-result.v1"
    analyzer.RESULT_SCOPE = "sealed_blind_generalization_product_r13_population"
    analyzer.MEMORY_TEST_PREFIX = "RoutesBlindR13MemoryStatusRequests("
    analyzer.TOTAL_CASES = 700
    analyzer.MIND_CASES = 688
    analyzer.MEMORY_CASES = 12


def main() -> int:
    configure()
    return analyzer.main()


if __name__ == "__main__":
    raise SystemExit(main())
