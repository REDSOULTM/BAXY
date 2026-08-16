"""Aggregate current-tree Cut-B Mind and private-memory evidence once."""

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
from experiments.mind_router_spike import (  # noqa: E402
    build_generalization_product_current_tree_r26 as campaign,
)


def configure() -> None:
    analyzer.MEASUREMENT_SOURCES = campaign.MEASUREMENT_SOURCES
    analyzer.MEMORY_TRX = campaign.MEMORY_TRX
    analyzer.MIND_OUTPUT = campaign.MIND_OUTPUT
    analyzer.CORPUS = campaign.OUTPUT
    analyzer.OUTPUT = campaign.PRODUCT_OUTPUT
    analyzer.POLICY_SOURCES = campaign.POLICY_SOURCES
    analyzer.PREREGISTRATION = campaign.PREREGISTRATION
    analyzer.CAMPAIGN = "current-tree-r26"
    analyzer.RESULT_SCHEMA = "baxy.generalization-product-current-tree-r26-result.v1"
    analyzer.RESULT_SCOPE = "sealed_blind_current_tree_cut_b_population"
    analyzer.MEMORY_TEST_PREFIX = (
        "RoutesBlindCurrentTreeR26GeneralizationMemoryStatusRequests("
    )
    analyzer.TOTAL_CASES = 700
    analyzer.MIND_CASES = 688
    analyzer.MEMORY_CASES = 12


def main() -> int:
    configure()
    return analyzer.main()


if __name__ == "__main__":
    raise SystemExit(main())
