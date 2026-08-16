"""Open the preregistered current-tree Cut-B Mind rows exactly once."""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    build_generalization_product_current_tree_r27 as campaign,
)
from experiments.mind_router_spike import (  # noqa: E402
    probe_generalization_product_holdout_r2 as runner,
)


def configure() -> None:
    runner.BUILDER_DEPENDENCIES = campaign.BUILDER_DEPENDENCIES
    runner.MEASUREMENT_SOURCES = campaign.MEASUREMENT_SOURCES
    runner.AUDIT = campaign.MIND_AUDIT
    runner.OUTPUT = campaign.MIND_OUTPUT
    runner.CORPUS = campaign.OUTPUT
    runner.POLICY_SOURCES = campaign.POLICY_SOURCES
    runner.PREREGISTRATION = campaign.PREREGISTRATION
    runner.BUILDER = Path(campaign.__file__).resolve()
    runner.CAMPAIGN = "current-tree-r27"
    runner.RESULT_SCHEMA = "baxy.generalization-product-current-tree-r27-mind-result.v1"
    runner.RESULT_SCOPE = "blind_current_tree_cut_b_mind_owned_rows"
    runner.TOTAL_CASES = 700
    runner.MIND_CASES = 688
    runner.MEMORY_CASES = 12


def main() -> int:
    configure()
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
