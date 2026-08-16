"""Replay opened R16 dual-ASR transcripts after per-clause retrieval."""

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


def configure() -> None:
    runner.CORPUS = (
        REPO / "artifacts/development/r16_sapi_dual_asr_corpus_v3.v1.jsonl"
    )
    runner.OUTPUT = (
        REPO
        / "artifacts/development/r16_sapi_dual_asr_product_route_development_v7.v1.json"
    )
    runner.AUDIT = (
        REPO
        / "artifacts/development/r16_sapi_dual_asr_product_route_development_v7.v1.raw.jsonl"
    )
    runner.CAMPAIGN = "r16-sapi-dual-asr-v7"
    runner.RESULT_SCHEMA = "baxy.r16-sapi-dual-asr-product-route-development.v7"
    runner.RESULT_SCOPE = (
        "opened_r16_dual_asr_real_mind_route_per_clause_retrieval_"
        "unpolled_audit_no_effects"
    )
    runner.LABEL_CORRECTION_PREFIXES = ()
    runner.PROBE = Path(__file__).resolve()
    runner.TOTAL_CASES = 337
    runner.MIND_CASES = 337


def main() -> int:
    configure()
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
