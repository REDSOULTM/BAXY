"""Combine opened R4 post-fix evidence across the two product owners."""

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
from scripts import build_generalization_product_holdout_r4 as campaign  # noqa: E402


def configure() -> None:
    analyzer.CORPUS = campaign.OUTPUT
    analyzer.SIDECAR_REPORT = (
        REPO
        / "artifacts/development/"
        "generalization_product_r4_replay_after_systemic_fix.v5.json"
    )
    analyzer.MEMORY_TRX = (
        REPO
        / "artifacts/development/"
        "generalization_product_r4_memory_after_systemic_fix.v1.trx"
    )
    analyzer.OUTPUT = (
        REPO
        / "artifacts/development/"
        "generalization_product_ownership_r4_after_systemic_fix.v1.json"
    )
    analyzer.CAMPAIGN = "r4"
    analyzer.RESULT_SCHEMA = "baxy.generalization-product-ownership-r4-development.v1"
    analyzer.RESULT_SCOPE = "opened_r4_population_post_holdout_development_only"
    analyzer.MEMORY_TEST_PREFIX = "RoutesBlindR4MemoryStatusRequests("
    analyzer.EXPECTED_LABEL_CORRECTIONS = 0
    analyzer.LABEL_CORRECTION_PREFIX = ""
    analyzer.ANALYZER = Path(__file__).resolve()
    analyzer.TOTAL_CASES = 400
    analyzer.MIND_CASES = 390
    analyzer.MEMORY_CASES = 10


def main() -> int:
    configure()
    return analyzer.main()


if __name__ == "__main__":
    raise SystemExit(main())
