"""Promote every opened R3 miss to development without rewriting blind evidence."""

from __future__ import annotations

import collections
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    analyze_generalization_product_holdout_r2 as holdout_analyzer,
)
from scripts import build_generalization_product_holdout_r3 as campaign  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


DEVELOPMENT = (
    REPO / "artifacts/development/generalization_product_r3_failures.v1.jsonl"
)
ANALYSIS = (
    REPO / "artifacts/holdout/generalization_product_holdout_r3_failure_analysis.json"
)
CAMPAIGN = "r3"
TOTAL_CASES = 340
MIND_CASES = 330
MEMORY_CASES = 10
MEMORY_TEST_PREFIX = "RoutesBlindR3MemoryStatusRequests("
SOURCE_CUT = "blind_generalization_product_r3_opened"
ANALYSIS_SCHEMA = "baxy.generalization-product-r3-failure-analysis.v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _counts(rows: Iterable[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row[field]) for row in rows).items()))


def _memory_results() -> list[dict[str, Any]]:
    holdout_analyzer.CAMPAIGN = CAMPAIGN
    holdout_analyzer.MEMORY_CASES = MEMORY_CASES
    holdout_analyzer.MEMORY_TEST_PREFIX = MEMORY_TEST_PREFIX
    return holdout_analyzer._memory_results(campaign.MEMORY_TRX)


def analyze() -> dict[str, Any]:
    for output in (DEVELOPMENT, ANALYSIS):
        if output.exists():
            raise RuntimeError(
                f"refusing to overwrite {CAMPAIGN.upper()} analysis evidence: {output}"
            )

    corpus = [
        json.loads(line)
        for line in campaign.OUTPUT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    case_by_id = {str(case["case_id"]): case for case in corpus}
    product = json.loads(campaign.PRODUCT_OUTPUT.read_text(encoding="utf-8"))
    mind = json.loads(campaign.MIND_OUTPUT.read_text(encoding="utf-8"))
    mind_rows = {str(row["case_id"]): row for row in mind["rows"]}
    memory_rows = {str(row["case_id"]): row for row in _memory_results()}
    if (
        len(case_by_id) != TOTAL_CASES
        or len(mind_rows) != MIND_CASES
        or len(memory_rows) != MEMORY_CASES
    ):
        raise RuntimeError(f"{CAMPAIGN.upper()} source evidence is incomplete")

    promoted: list[dict[str, Any]] = []
    for case_id, case in case_by_id.items():
        if case["owner"] == "mind_sidecar":
            scored = mind_rows[case_id]
            if scored["exact_turn_correct"]:
                continue
            promoted.append(
                {
                    "schema": "baxy.generalization-product-development-case.v1",
                    "source_cut": SOURCE_CUT,
                    "development_only": True,
                    "case_id": case_id,
                    "family": case["family"],
                    "case_type": case["case_type"],
                    "owner": case["owner"],
                    "language": case["language"],
                    "surface": case["surface"],
                    "text": case["text"],
                    "outcome": case["outcome"],
                    "compatible_terminal_operation_sets": case[
                        "compatible_terminal_operation_sets"
                    ],
                    "compatible_effect_operation_sets": case[
                        "compatible_effect_operation_sets"
                    ],
                    "candidate_operations": scored["candidate_operations"],
                    "raw_operations": scored["raw_operations"],
                    "final_kind": scored["final_kind"],
                    "final_intent_operations": scored[
                        "final_intent_operations"
                    ],
                    "final_effect_operations": scored[
                        "final_effect_operations"
                    ],
                    "unsafe_effect": bool(scored["unsafe_effect"]),
                    "first_loss_stage": scored["first_veto"],
                    "failure_cause": scored["failure_cause"],
                }
            )
        else:
            scored = memory_rows[case_id]
            if scored["passed"]:
                continue
            promoted.append(
                {
                    "schema": "baxy.generalization-product-development-case.v1",
                    "source_cut": SOURCE_CUT,
                    "development_only": True,
                    "case_id": case_id,
                    "family": case["family"],
                    "case_type": case["case_type"],
                    "owner": case["owner"],
                    "language": case["language"],
                    "surface": case["surface"],
                    "text": case["text"],
                    "outcome": case["outcome"],
                    "compatible_terminal_operation_sets": case[
                        "compatible_terminal_operation_sets"
                    ],
                    "compatible_effect_operation_sets": case[
                        "compatible_effect_operation_sets"
                    ],
                    "candidate_operations": [],
                    "raw_operations": [],
                    "final_kind": "no_route",
                    "final_intent_operations": [],
                    "final_effect_operations": [],
                    "unsafe_effect": False,
                    "first_loss_stage": "app_private_memory_parser",
                    "failure_cause": "app_parser",
                }
            )

    expected_failures = int(product["metrics"]["failed"])
    expected_unsafe = int(product["metrics"]["unsafe_effects"])
    if len(promoted) != expected_failures:
        raise RuntimeError(
            f"promoted {CAMPAIGN.upper()} failures differ from the sealed product result"
        )
    if sum(bool(row["unsafe_effect"]) for row in promoted) != expected_unsafe:
        raise RuntimeError(
            f"promoted {CAMPAIGN.upper()} unsafe count differs from the sealed product result"
        )

    DEVELOPMENT.parent.mkdir(parents=True, exist_ok=True)
    DEVELOPMENT.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in promoted
        ),
        encoding="utf-8",
        newline="\n",
    )
    report = {
        "schema": ANALYSIS_SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": "offline_analysis_only_no_sidecar_no_plan_no_core_no_provider",
        "effects_executed": 0,
        "holdout_reuse_policy": (
            f"opened {CAMPAIGN.upper()} failures are development data and "
            f"{CAMPAIGN.upper()} is never blind again"
        ),
        "source": {
            "corpus": str(campaign.OUTPUT.relative_to(REPO)),
            "corpus_sha256": sha256(campaign.OUTPUT),
            "mind_result": str(campaign.MIND_OUTPUT.relative_to(REPO)),
            "mind_result_sha256": sha256(campaign.MIND_OUTPUT),
            "mind_raw_audit": str(campaign.MIND_AUDIT.relative_to(REPO)),
            "mind_raw_audit_sha256": sha256(campaign.MIND_AUDIT),
            "memory_trx": str(campaign.MEMORY_TRX.relative_to(REPO)),
            "memory_trx_sha256": sha256(campaign.MEMORY_TRX),
            "product_result": str(campaign.PRODUCT_OUTPUT.relative_to(REPO)),
            "product_result_sha256": sha256(campaign.PRODUCT_OUTPUT),
            "analyzer": str(Path(__file__).resolve().relative_to(REPO)),
            "analyzer_sha256": sha256(Path(__file__).resolve()),
        },
        "development_output": {
            "path": str(DEVELOPMENT.relative_to(REPO)),
            "sha256": sha256(DEVELOPMENT),
            "rows": len(promoted),
        },
        "metrics": {
            "failures": len(promoted),
            "unsafe_effects": sum(bool(row["unsafe_effect"]) for row in promoted),
            "by_owner": _counts(promoted, "owner"),
            "by_case_type": _counts(promoted, "case_type"),
            "by_cause": _counts(promoted, "failure_cause"),
            "by_family": _counts(promoted, "family"),
        },
    }
    write_json_atomic(ANALYSIS, report)
    return report


def main() -> int:
    report = analyze()
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
