"""Replay every opened R18 Mind row as post-fix development evidence."""

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
from scripts import build_generalization_product_holdout_r18 as campaign  # noqa: E402


def configure() -> None:
    runner.CORPUS = campaign.OUTPUT
    runner.OUTPUT = (
        REPO / "artifacts/development/"
        "generalization_product_r18_replay_after_systemic_fix.v1.json"
    )
    runner.AUDIT = (
        REPO / "artifacts/development/"
        "generalization_product_r18_replay_after_systemic_fix.v1.raw.jsonl"
    )
    runner.CAMPAIGN = "r18"
    runner.RESULT_SCHEMA = "baxy.generalization-product-r18-development-replay.v1"
    runner.RESULT_SCOPE = "opened_r18_population_post_fix_development_only"
    runner.LABEL_CORRECTION_PREFIXES = ()
    runner.PROBE = Path(__file__).resolve()
    runner.TOTAL_CASES = 700
    runner.MIND_CASES = 688


def main() -> int:
    configure()
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
