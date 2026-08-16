"""Open the preregistered R4 Mind-owned population exactly once."""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    probe_generalization_product_holdout_r2 as runner,
)
from scripts import build_generalization_product_holdout_r4 as campaign  # noqa: E402


def configure() -> None:
    runner.BUILDER_DEPENDENCIES = campaign.BUILDER_DEPENDENCIES
    runner.MEASUREMENT_SOURCES = campaign.MEASUREMENT_SOURCES
    runner.AUDIT = campaign.MIND_AUDIT
    runner.OUTPUT = campaign.MIND_OUTPUT
    runner.CORPUS = campaign.OUTPUT
    runner.POLICY_SOURCES = campaign.POLICY_SOURCES
    runner.PREREGISTRATION = campaign.PREREGISTRATION
    runner.BUILDER = REPO / "scripts/build_generalization_product_holdout_r4.py"
    runner.CAMPAIGN = "r4"
    runner.RESULT_SCHEMA = "baxy.generalization-product-holdout-r4-mind-result.v1"
    runner.RESULT_SCOPE = "blind_generalization_product_r4_mind_owned_rows"
    runner.TOTAL_CASES = 400
    runner.MIND_CASES = 390
    runner.MEMORY_CASES = 10


def main() -> int:
    configure()
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
