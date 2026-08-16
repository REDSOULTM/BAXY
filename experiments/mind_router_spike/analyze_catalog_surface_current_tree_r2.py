"""Aggregate current-tree R2 Mind and App-memory catalogue evidence."""

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
    build_catalog_surface_current_tree_r2 as campaign,
)


def configure() -> None:
    campaign.configure()
    analyzer.MEASUREMENT_SOURCES = campaign.MEASUREMENT_SOURCES
    analyzer.MEMORY_TRX = campaign.MEMORY_TRX
    analyzer.MIND_OUTPUT = campaign.MIND_OUTPUT
    analyzer.CORPUS = campaign.OUTPUT
    analyzer.OUTPUT = campaign.PRODUCT_OUTPUT
    analyzer.POLICY_SOURCES = campaign.POLICY_SOURCES
    analyzer.PREREGISTRATION = campaign.PREREGISTRATION
    analyzer.CAMPAIGN = "current-tree-r2-catalog-surface"
    analyzer.RESULT_SCHEMA = "baxy.catalog-surface-current-tree-r2-result.v1"
    analyzer.RESULT_SCOPE = "sealed_blind_current_tree_r2_all_catalogue_surface"
    analyzer.MEMORY_TEST_PREFIX = "RoutesBlindCurrentTreeR2MemoryRequests("
    analyzer.TOTAL_CASES = 169
    analyzer.MIND_CASES = 158
    analyzer.MEMORY_CASES = 11


def main() -> int:
    configure()
    return analyzer.main()


if __name__ == "__main__":
    raise SystemExit(main())
