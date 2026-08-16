"""Replay every opened R8 Mind-owned row as development evidence.

The sealed R8 corpus is immutable.  Two email surfaces contain a documented
builder corruption (the person name replacement ``Lee -> Reese`` changed the
Spanish read verb).  This replay therefore preserves the original oracle and
reports those rows as failures instead of relabelling or silently repairing
the blind artifact.
"""

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
from scripts import build_generalization_product_holdout_r8 as campaign  # noqa: E402


def configure() -> None:
    runner.CORPUS = campaign.OUTPUT
    runner.OUTPUT = (
        REPO
        / "artifacts/development/"
        "generalization_product_r8_replay_after_systemic_fix.v1.json"
    )
    runner.AUDIT = (
        REPO
        / "artifacts/development/"
        "generalization_product_r8_replay_after_systemic_fix.v1.raw.jsonl"
    )
    runner.CAMPAIGN = "r8"
    runner.RESULT_SCHEMA = "baxy.generalization-product-r8-development-replay.v1"
    runner.RESULT_SCOPE = "opened_r8_population_post_fix_development_only"
    runner.LABEL_CORRECTION_PREFIXES = ()
    runner.PROBE = Path(__file__).resolve()
    runner.TOTAL_CASES = 700
    runner.MIND_CASES = 688


def main() -> int:
    configure()
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
