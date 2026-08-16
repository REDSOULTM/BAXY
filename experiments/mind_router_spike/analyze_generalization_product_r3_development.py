"""Combine opened R3 post-fix evidence across the two product owners."""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    analyze_generalization_product_r2_development as analyzer,
)
from scripts import build_generalization_product_holdout_r3 as campaign  # noqa: E402


def configure() -> None:
    analyzer.CORPUS = campaign.OUTPUT
    analyzer.SIDECAR_REPORT = (
        REPO
        / "artifacts/development/"
        "generalization_product_r3_replay_after_systemic_fix.v2.json"
    )
    analyzer.MEMORY_TRX = (
        REPO
        / "artifacts/development/"
        "generalization_product_r3_memory_after_systemic_fix.v1.trx"
    )
    analyzer.OUTPUT = (
        REPO
        / "artifacts/development/"
        "generalization_product_ownership_r3_after_systemic_fix.v1.json"
    )
    analyzer.CAMPAIGN = "r3"
    analyzer.RESULT_SCHEMA = "baxy.generalization-product-ownership-r3-development.v1"
    analyzer.RESULT_SCOPE = "opened_r3_population_post_holdout_development_only"
    analyzer.MEMORY_TEST_PREFIX = "RoutesBlindR3MemoryStatusRequests("
    analyzer.EXPECTED_LABEL_CORRECTIONS = 0
    analyzer.LABEL_CORRECTION_PREFIX = ""
    analyzer.ANALYZER = Path(__file__).resolve()


def main() -> int:
    configure()
    return analyzer.main()


if __name__ == "__main__":
    raise SystemExit(main())
