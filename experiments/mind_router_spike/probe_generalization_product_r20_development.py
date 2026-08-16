"""Replay every opened R20 Mind row as post-fix development evidence."""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    probe_generalization_product_r2_development as runner,
)
from scripts import build_generalization_product_holdout_r20 as campaign  # noqa: E402


def configure() -> None:
    runner.CORPUS = campaign.OUTPUT
    runner.OUTPUT = (
        REPO / "artifacts/development/"
        "generalization_product_r20_replay_after_compound_fix.v2.json"
    )
    runner.AUDIT = (
        REPO / "artifacts/development/"
        "generalization_product_r20_replay_after_compound_fix.v2.raw.jsonl"
    )
    runner.CAMPAIGN = "r20"
    runner.RESULT_SCHEMA = "baxy.generalization-product-r20-development-replay.v2"
    runner.RESULT_SCOPE = "opened_r20_population_post_fix_development_only"
    runner.LABEL_CORRECTION_PREFIXES = ()
    runner.PROBE = Path(__file__).resolve()
    runner.TOTAL_CASES = 700
    runner.MIND_CASES = 688


def main() -> int:
    configure()
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
