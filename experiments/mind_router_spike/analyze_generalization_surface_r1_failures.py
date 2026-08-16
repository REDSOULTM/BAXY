"""Promote sealed R1 misses to development with stage-aware attribution.

This analysis never starts the mind sidecar and never rewrites blind evidence.
It joins the frozen corpus, recovered score and raw audit, then records the
first policy stage that loses an otherwise-correct operation set.  Once opened,
the failed texts are development data rather than a reusable blind holdout.
"""

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

from experiments.mind_router_spike.recover_generalization_surface_holdout_r1 import (  # noqa: E402
    EXPECTED_AUDIT_SHA256,
    terminal_audits,
)
from experiments.mind_router_spike.probe_current_catalog_review import (  # noqa: E402
    _matches,
    _operation_sets,
    _raw_operations,
    _terminal_operations,
)
from scripts.build_generalization_surface_holdout import OUTPUT as CORPUS  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


AUDIT = REPO / "artifacts/holdout/generalization_surface_holdout_r1.raw.jsonl"
BLIND_RESULT = REPO / "artifacts/holdout/generalization_surface_holdout_r1.json"
DEVELOPMENT = (
    REPO / "artifacts/development/generalization_surface_r1_failures.v1.jsonl"
)
ANALYSIS = (
    REPO
    / "artifacts/holdout/generalization_surface_holdout_r1_failure_analysis.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stage_operations(stage: dict[str, Any]) -> tuple[str, ...]:
    operations = _terminal_operations(stage.get("effect_operations") or [])
    if operations:
        return operations
    operation = stage.get("operation")
    return (str(operation),) if isinstance(operation, str) and operation else ()


def _first_loss_stage(
    audit: dict[str, Any],
    accepted_effects: tuple[tuple[str, ...], ...],
) -> str | None:
    previous_matches = _matches(
        _raw_operations(audit.get("raw_decision")),
        accepted_effects,
    )
    for stage in audit.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        current_matches = _matches(_stage_operations(stage), accepted_effects)
        if previous_matches and not current_matches:
            return str(stage.get("name") or "unnamed")
        previous_matches = current_matches
    return None


def _group_counts(
    rows: Iterable[dict[str, Any]], field: str
) -> dict[str, int]:
    return dict(
        sorted(collections.Counter(str(row[field]) for row in rows).items())
    )


def analyze() -> dict[str, Any]:
    for output in (DEVELOPMENT, ANALYSIS):
        if output.exists():
            raise RuntimeError(f"refusing to overwrite R1 analysis evidence: {output}")
    if sha256(AUDIT) != EXPECTED_AUDIT_SHA256:
        raise RuntimeError("R1 raw audit identity changed")

    cases = [
        json.loads(line)
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    blind_result = json.loads(BLIND_RESULT.read_text(encoding="utf-8"))
    result_rows = {
        str(row["case_id"]): row for row in blind_result.get("rows") or []
    }
    request_ids = {f"blind-generalization-{case['case_id']}" for case in cases}
    audits = terminal_audits(AUDIT, request_ids)
    if len(cases) != 310 or len(result_rows) != len(cases):
        raise RuntimeError("R1 source population is incomplete")

    promoted: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["case_id"])
        scored = result_rows[case_id]
        if bool(scored["exact_turn_correct"]):
            continue
        audit = audits[f"blind-generalization-{case_id}"]
        accepted_intents = _operation_sets(
            case, "compatible_terminal_operation_sets"
        )
        accepted_effects = _operation_sets(
            case, "compatible_effect_operation_sets"
        )
        stages = tuple(str(value) for value in audit.get("stage_names") or ())
        raw_correct = _matches(
            _raw_operations(audit.get("raw_decision")), accepted_intents
        )
        first_loss = _first_loss_stage(audit, accepted_effects) if raw_correct else None
        if stages == ("total_recovery",):
            cause = "recovery"
        elif not bool(scored["retrieval_correct"]):
            cause = "retrieval"
        elif not raw_correct:
            cause = "decision"
        elif first_loss:
            cause = f"veto:{first_loss}"
        elif not bool(scored["kind_correct"]):
            cause = "presentation"
        else:
            cause = "terminal_projection"
        promoted.append(
            {
                "schema": "baxy.generalization-surface-development-case.v1",
                "source_cut": "blind_generalization_surface_cut_b_r1_opened",
                "development_only": True,
                "case_id": case_id,
                "family": case["family"],
                "language": case["language"],
                "surface": case["surface"],
                "text": case["text"],
                "compatible_terminal_operation_sets": [
                    list(value) for value in accepted_intents
                ],
                "compatible_effect_operation_sets": [
                    list(value) for value in accepted_effects
                ],
                "candidate_operations": scored["candidate_operations"],
                "raw_operations": scored["raw_operations"],
                "final_kind": scored["final_kind"],
                "final_intent_operations": scored["final_intent_operations"],
                "final_effect_operations": scored["final_effect_operations"],
                "unsafe_effect": bool(scored["unsafe_effect"]),
                "first_loss_stage": first_loss,
                "failure_cause": cause,
            }
        )

    expected_failures = int(blind_result["metrics"]["failed"])
    expected_unsafe = int(blind_result["metrics"]["unsafe_effects"])
    if len(promoted) != expected_failures:
        raise RuntimeError("promoted failure count differs from sealed result")
    if sum(bool(row["unsafe_effect"]) for row in promoted) != expected_unsafe:
        raise RuntimeError("promoted unsafe count differs from sealed result")

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
        "schema": "baxy.generalization-surface-failure-analysis.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": "offline_analysis_only_no_sidecar_no_plan_no_core_no_provider",
        "effects_executed": 0,
        "holdout_reuse_policy": (
            "failed texts are now development data and R1 is never blind again"
        ),
        "source": {
            "corpus": str(CORPUS.relative_to(REPO)),
            "corpus_sha256": sha256(CORPUS),
            "blind_result": str(BLIND_RESULT.relative_to(REPO)),
            "blind_result_sha256": sha256(BLIND_RESULT),
            "raw_audit": str(AUDIT.relative_to(REPO)),
            "raw_audit_sha256": sha256(AUDIT),
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
            "by_cause": _group_counts(promoted, "failure_cause"),
            "by_first_loss_stage": _group_counts(
                (row for row in promoted if row["first_loss_stage"]),
                "first_loss_stage",
            ),
            "by_family": _group_counts(promoted, "family"),
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
