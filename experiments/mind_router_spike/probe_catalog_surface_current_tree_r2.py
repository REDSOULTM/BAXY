"""Open the preregistered current-tree catalogue surface R2 exactly once."""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    build_catalog_surface_current_tree_r2 as campaign,
)
from experiments.mind_router_spike import (  # noqa: E402
    probe_generalization_product_holdout_r2 as runner,
)


def configure() -> None:
    campaign.configure()
    runner.BUILDER_DEPENDENCIES = campaign.BUILDER_DEPENDENCIES
    runner.MEASUREMENT_SOURCES = campaign.MEASUREMENT_SOURCES
    runner.AUDIT = campaign.MIND_AUDIT
    runner.OUTPUT = campaign.MIND_OUTPUT
    runner.CORPUS = campaign.OUTPUT
    runner.POLICY_SOURCES = campaign.POLICY_SOURCES
    runner.PREREGISTRATION = campaign.PREREGISTRATION
    runner.BUILDER = Path(campaign.__file__).resolve()
    runner.CAMPAIGN = "current-tree-r2-catalog-surface"
    runner.RESULT_SCHEMA = "baxy.catalog-surface-current-tree-r2-mind-result.v1"
    runner.RESULT_SCOPE = "blind_current_tree_r2_all_catalogue_mind_surface"
    runner.TOTAL_CASES = 169
    runner.MIND_CASES = 158
    runner.MEMORY_CASES = 11


def main() -> int:
    configure()
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
