"""Combine opened R9 post-fix evidence across the two product owners."""

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
from scripts import build_generalization_product_holdout_r9 as campaign  # noqa: E402


def configure() -> None:
    analyzer.CORPUS = campaign.OUTPUT
    analyzer.SIDECAR_REPORT = (
        REPO
        / "artifacts/development/"
        "generalization_product_r9_replay_after_systemic_fix.v1.json"
    )
    analyzer.MEMORY_TRX = (
        REPO
        / "artifacts/development/"
        "generalization_product_r9_memory_after_systemic_fix.v1.trx"
    )
    analyzer.OUTPUT = (
        REPO
        / "artifacts/development/"
        "generalization_product_ownership_r9_after_systemic_fix.v1.json"
    )
    analyzer.CAMPAIGN = "r9"
    analyzer.RESULT_SCHEMA = "baxy.generalization-product-ownership-r9-development.v1"
    analyzer.RESULT_SCOPE = "opened_r9_population_post_holdout_development_only"
    analyzer.MEMORY_TEST_PREFIX = "RoutesBlindR9MemoryStatusRequests("
    analyzer.EXPECTED_LABEL_CORRECTIONS = 0
    analyzer.LABEL_CORRECTION_PREFIX = ""
    analyzer.ANALYZER = Path(__file__).resolve()
    analyzer.TOTAL_CASES = 700
    analyzer.MIND_CASES = 688
    analyzer.MEMORY_CASES = 12


def main() -> int:
    configure()
    return analyzer.main()


if __name__ == "__main__":
    raise SystemExit(main())
