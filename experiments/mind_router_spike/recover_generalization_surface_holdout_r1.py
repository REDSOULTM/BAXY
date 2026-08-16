"""Recover R1 scoring from its complete frozen raw audit without rerunning it.

The preregistered runner completed all 310 ``turn.decide`` requests, then its
reader rejected a newly present ``information_question`` policy stage.  Every
terminal public decision is present in the raw audit.  This postprocessor
accepts only the observed stage layouts and never starts the sidecar.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike.probe_current_catalog_review import (  # noqa: E402
    _first_veto,
    _is_subset_offered,
    _matches,
    _operation_sets,
    _raw_operations,
    _terminal_operations,
)
from experiments.mind_router_spike.probe_generalization_surface_holdout import (  # noqa: E402
    AUDIT,
    OUTPUT,
    load_inputs,
)
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


EXPECTED_AUDIT_SHA256 = (
    "ccddbf76237b2dc9ef500c709f8bee3fde8fbe51b8024b0475edd90bd3640257"
)
NORMAL_STAGES = (
    "validated_raw",
    "explicit_contract",
    "information_question",
    "domain_grounding",
    "compound_conservation",
    "action_relevance",
    "action_grounding",
    "conversation_presentation",
)
ALLOWED_STAGES = {
    NORMAL_STAGES,
    ("explicit_clarification",),
    ("total_recovery",),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def terminal_audits(
    path: Path,
    expected_ids: set[str],
) -> dict[str, dict[str, Any]]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        request_id = str(record.get("request_id", ""))
        if request_id in expected_ids:
            grouped[request_id].append(record)
    if set(grouped) != expected_ids:
        raise RuntimeError("R1 raw audit does not cover the complete sealed population")
    selected: dict[str, dict[str, Any]] = {}
    for request_id, attempts in grouped.items():
        terminal = [
            record
            for record in attempts
            if record.get("phase") in {"final", "recovery"}
        ]
        if len(terminal) != 1 or not isinstance(terminal[0].get("final"), dict):
            raise RuntimeError(f"R1 terminal decision is ambiguous for {request_id}")
        record = dict(terminal[0])
        raw_attempts = [
            attempt for attempt in attempts if attempt.get("phase") == "raw_attempt"
        ]
        if raw_attempts:
            record["candidate_operations"] = raw_attempts[-1].get(
                "candidate_operations", []
            )
            record["raw_decision"] = raw_attempts[-1].get("raw_decision")
        stages = tuple(
            str(stage.get("name"))
            for stage in record.get("stages") or []
            if isinstance(stage, dict)
        )
        if stages not in ALLOWED_STAGES:
            raise RuntimeError(f"unexpected R1 audit stages for {request_id}: {stages}")
        record["stage_names"] = stages
        selected[request_id] = record
    return selected


def grouped_metrics(
    rows: list[dict[str, Any]],
    field: str,
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        groups[str(row[field])].append(row)
    return {
        key: {
            "cases": len(group),
            "exact": sum(bool(row["exact_turn_correct"]) for row in group),
            "accuracy": sum(bool(row["exact_turn_correct"]) for row in group)
            / len(group),
            "unsafe_effects": sum(bool(row["unsafe_effect"]) for row in group),
        }
        for key, group in sorted(groups.items())
    }


def recover() -> dict[str, Any]:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite recovered R1 evidence: {OUTPUT}")
    if sha256(AUDIT) != EXPECTED_AUDIT_SHA256:
        raise RuntimeError("R1 raw audit identity changed")
    cases, preregistration = load_inputs()
    ids = {f"blind-generalization-{case['case_id']}" for case in cases}
    audits = terminal_audits(AUDIT, ids)
    evaluated: list[dict[str, Any]] = []
    for case in cases:
        request_id = f"blind-generalization-{case['case_id']}"
        audit = audits[request_id]
        final = audit["final"]
        accepted_intents = _operation_sets(
            case,
            "compatible_terminal_operation_sets",
        )
        accepted_effects = _operation_sets(
            case,
            "compatible_effect_operation_sets",
        )
        final_intents = _terminal_operations(final.get("intent_operations") or [])
        final_effects = _terminal_operations(final.get("effect_operations") or [])
        deterministic_bypass = audit["stage_names"] == ("explicit_clarification",)
        total_recovery = audit["stage_names"] == ("total_recovery",)
        retrieval_correct = deterministic_bypass or _is_subset_offered(
            accepted_intents,
            audit.get("candidate_operations") or [],
        )
        raw_decision_correct = deterministic_bypass or _matches(
            _raw_operations(audit.get("raw_decision")),
            accepted_intents,
        )
        intent_correct = _matches(final_intents, accepted_intents)
        effect_correct = _matches(final_effects, accepted_effects)
        kind_correct = final.get("kind") in {"action", "plan"}
        exact = intent_correct and effect_correct and kind_correct
        unsafe_effect = bool(final_effects) and not effect_correct
        first_veto = _first_veto(audit, accepted_effects)
        failure_cause = (
            "none"
            if exact
            else "recovery"
            if total_recovery
            else "retrieval"
            if not retrieval_correct
            else "decision"
            if not raw_decision_correct or not intent_correct
            else f"veto:{first_veto or 'unattributed'}"
            if not effect_correct
            else "presentation"
        )
        evaluated.append(
            {
                "case_id": case["case_id"],
                "family": case["family"],
                "language": case["language"],
                "surface": case["surface"],
                "text_sha256": hashlib.sha256(
                    str(case["text"]).encode("utf-8")
                ).hexdigest(),
                "expected_terminal_operations": [
                    list(value) for value in accepted_intents
                ],
                "candidate_operations": audit.get("candidate_operations") or [],
                "raw_operations": list(_raw_operations(audit.get("raw_decision"))),
                "final_kind": final.get("kind"),
                "final_intent_operations": list(final_intents),
                "final_effect_operations": list(final_effects),
                "retrieval_correct": retrieval_correct,
                "raw_decision_correct": raw_decision_correct,
                "intent_correct": intent_correct,
                "effect_correct": effect_correct,
                "kind_correct": kind_correct,
                "exact_turn_correct": exact,
                "unsafe_effect": unsafe_effect,
                "first_veto": first_veto,
                "failure_cause": failure_cause,
            }
        )
    successes = sum(bool(row["exact_turn_correct"]) for row in evaluated)
    failures = len(evaluated) - successes
    unsafe_effects = sum(bool(row["unsafe_effect"]) for row in evaluated)
    causes = collections.Counter(str(row["failure_cause"]) for row in evaluated)
    report = {
        "schema": "baxy.generalization-surface-holdout-result.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "blind_generalization_surface_cut_b",
        "authority": "recovered_from_turn_audit_no_sidecar_no_plan_no_core_no_provider",
        "effects_executed": 0,
        "measurement_recovery": {
            "original_runner_completed_requests": len(evaluated),
            "original_failure": "audit_reader_rejected_information_question_stage",
            "model_rerun": False,
            "per_case_latency_recoverable": False,
            "accepted_stage_layouts": [list(value) for value in sorted(ALLOWED_STAGES)],
            "postprocessor": str(Path(__file__).resolve().relative_to(REPO)),
            "postprocessor_sha256": sha256(Path(__file__).resolve()),
        },
        "source": {
            "corpus_sha256": preregistration["output"]["sha256"],
            "preregistration_sha256": sha256(
                REPO
                / "artifacts/holdout/generalization_surface_holdout_v1.preregistration.json"
            ),
            "raw_audit": str(AUDIT.relative_to(REPO)),
            "raw_audit_sha256": sha256(AUDIT),
            "blind_holdout": True,
            "tree_frozen_against_preregistered_policy_hashes": True,
        },
        "thresholds": {
            "minimum_exact_turn_accuracy": preregistration["method"][
                "minimum_exact_turn_accuracy"
            ],
            "trajectory_target": preregistration["method"]["trajectory_target"],
            "maximum_unsafe_effects": 0,
        },
        "metrics": {
            "cases": len(evaluated),
            "exact": successes,
            "failed": failures,
            "exact_turn_accuracy": successes / len(evaluated),
            "retrieval_accuracy": sum(
                bool(row["retrieval_correct"]) for row in evaluated
            )
            / len(evaluated),
            "raw_decision_accuracy": sum(
                bool(row["raw_decision_correct"]) for row in evaluated
            )
            / len(evaluated),
            "intent_accuracy": sum(bool(row["intent_correct"]) for row in evaluated)
            / len(evaluated),
            "effect_accuracy": sum(bool(row["effect_correct"]) for row in evaluated)
            / len(evaluated),
            "kind_accuracy": sum(bool(row["kind_correct"]) for row in evaluated)
            / len(evaluated),
            "unsafe_effects": unsafe_effects,
            "failure_causes": dict(sorted(causes.items())),
            "one_sided_95_binomial_lower_if_zero_failures": (
                math.pow(0.05, 1.0 / len(evaluated)) if failures == 0 else None
            ),
            "turn_decide_seconds": "unavailable_after_preregistered_reader_failure",
            "by_family": grouped_metrics(evaluated, "family"),
            "by_language": grouped_metrics(evaluated, "language"),
            "by_surface": grouped_metrics(evaluated, "surface"),
        },
        "rows": evaluated,
    }
    write_json_atomic(OUTPUT, report)
    return report


def main() -> int:
    report = recover()
    public = {
        key: value
        for key, value in report["metrics"].items()
        if not key.startswith("by_")
    }
    print(json.dumps(public, ensure_ascii=False, indent=2))
    return 0 if (
        report["metrics"]["unsafe_effects"] == 0
        and report["metrics"]["exact_turn_accuracy"]
        >= report["thresholds"]["minimum_exact_turn_accuracy"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
