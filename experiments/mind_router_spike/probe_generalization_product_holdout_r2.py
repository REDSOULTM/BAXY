"""Open the preregistered R2 Mind-owned blind population exactly once.

Only ``turn.decide`` is sent.  Memory-owned rows are intentionally excluded
and measured by the App-private parser.  No plan, Core request, provider
request, or effect is permitted.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import statistics
import sys
import time
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
    _read_audit,
    _terminal_operations,
)
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    file_sha256,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.build_generalization_product_holdout_r2 import (  # noqa: E402
    BUILDER_DEPENDENCIES,
    MEASUREMENT_SOURCES,
    MIND_AUDIT as AUDIT,
    MIND_OUTPUT as OUTPUT,
    OUTPUT as CORPUS,
    POLICY_SOURCES,
    PREREGISTRATION,
    catalog_identity,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)


BUILDER = REPO / "scripts/build_generalization_product_holdout_r2.py"
CAMPAIGN = "r2"
RESULT_SCHEMA = "baxy.generalization-product-holdout-r2-mind-result.v1"
RESULT_SCOPE = "blind_generalization_product_r2_mind_owned_rows"
TOTAL_CASES = 340
MIND_CASES = 330
MEMORY_CASES = 10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(quantile * len(ordered) + 0.999) - 1))
    return ordered[rank]


def load_inputs() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    if (
        manifest.get("blind_holdout") is not True
        or manifest.get("preregistered_before_measurement") is not True
        or manifest.get("measurement_status") != "unopened"
        or manifest.get("output", {}).get("sha256") != sha256(CORPUS)
        or manifest.get("sources", {}).get("builder_sha256") != sha256(BUILDER)
    ):
        raise RuntimeError(f"{CAMPAIGN.upper()} blind preregistration identity is invalid")
    actual_dependencies = {
        str(path.relative_to(REPO)): sha256(path) for path in BUILDER_DEPENDENCIES
    }
    if manifest["sources"]["builder_dependencies_sha256"] != actual_dependencies:
        raise RuntimeError(
            f"{CAMPAIGN.upper()} builder dependency changed after preregistration"
        )
    actual_policy = {
        str(path.relative_to(REPO)): sha256(path) for path in POLICY_SOURCES
    }
    if manifest["sources"]["policy_sha256"] != actual_policy:
        raise RuntimeError(f"{CAMPAIGN.upper()} policy changed after preregistration")
    actual_measurement = {
        str(path.relative_to(REPO)): sha256(path) for path in MEASUREMENT_SOURCES
    }
    if manifest["sources"]["measurement_sha256"] != actual_measurement:
        raise RuntimeError(
            f"{CAMPAIGN.upper()} measurement code changed after preregistration"
        )

    rows = [
        json.loads(line)
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if (
        len(rows) != TOTAL_CASES
        or len({row["case_id"] for row in rows}) != len(rows)
        or not all(row.get("blind_holdout") is True for row in rows)
        or not all(row.get("execution_authority") is False for row in rows)
    ):
        raise RuntimeError(f"{CAMPAIGN.upper()} blind population shape is invalid")
    mind_rows = [row for row in rows if row["owner"] == "mind_sidecar"]
    memory_rows = [
        row for row in rows if row["owner"] == "app_private_memory_parser"
    ]
    if len(mind_rows) != MIND_CASES or len(memory_rows) != MEMORY_CASES:
        raise RuntimeError(f"{CAMPAIGN.upper()} ownership split is invalid")
    return mind_rows, manifest


def grouped_metrics(
    rows: list[dict[str, Any]], field: str
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row[field])].append(row)
    return {
        key: {
            "cases": len(group),
            "exact": sum(bool(row["exact_turn_correct"]) for row in group),
            "accuracy": sum(bool(row["exact_turn_correct"]) for row in group)
            / len(group),
            "unsafe_effects": sum(bool(row["unsafe_effect"]) for row in group),
        }
        for key, group in sorted(grouped.items())
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    args.output = args.output.resolve()
    args.audit = args.audit.resolve()
    args.runtime_manifest = args.runtime_manifest.resolve()
    if args.output != OUTPUT.resolve() or args.audit != AUDIT.resolve():
        raise RuntimeError(
            f"{CAMPAIGN.upper()} blind evidence paths are preregistered and immutable"
        )
    cases, preregistration = load_inputs()
    for path in (args.output, args.audit):
        if path.exists():
            raise RuntimeError(
                f"refusing to overwrite opened {CAMPAIGN.upper()} evidence: {path}"
            )

    runtime = resolve_runtime(manifest_path=args.runtime_manifest)
    runtime_manifest_before = file_sha256(args.runtime_manifest)
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    catalog_sha256, operation_count = catalog_identity(capabilities)
    if (
        catalog_sha256 != preregistration["catalog"]["sha256"]
        or operation_count != preregistration["catalog"]["operations"]
    ):
        raise RuntimeError(
            f"compiled catalogue changed after {CAMPAIGN.upper()} preregistration"
        )

    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    environment["BAXY_MIND_TURN_AUDIT_PATH"] = str(args.audit)
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    public_rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError(f"sidecar rejected its {CAMPAIGN.upper()} handshake")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": f"catalog-generalization-product-{CAMPAIGN}",
                "capabilities": capabilities,
                "applicationCatalog": application_catalog,
                "gameCatalog": game_catalog,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError(
                f"sidecar rejected the authenticated {CAMPAIGN.upper()} catalogue"
            )
        client.request(
            {
                "type": "turn.decide",
                "id": f"warm-generalization-product-{CAMPAIGN}",
                "text": "hola",
                "history": [],
                "uiLanguage": "es",
            },
            limits["turn.decide"],
        )
        for case in cases:
            request_id = f"blind-product-{CAMPAIGN}-{case['case_id']}"
            before = time.perf_counter()
            reply = client.request(
                {
                    "type": "turn.decide",
                    "id": request_id,
                    "text": case["text"],
                    "history": [],
                    "uiLanguage": "en" if case["language"] == "en" else "es",
                },
                limits["turn.decide"],
            )
            public_rows.append(
                {
                    "request_id": request_id,
                    "reply": reply,
                    "seconds": round(time.perf_counter() - before, 6),
                }
            )
    finally:
        client.close(
            graceful_message={
                "type": "shutdown",
                "id": f"shutdown-generalization-product-{CAMPAIGN}",
            },
            timeout=limits["shutdown"],
        )

    audits = _read_audit(
        args.audit,
        {str(row["request_id"]) for row in public_rows},
    )
    evaluated: list[dict[str, Any]] = []
    for case, public in zip(cases, public_rows, strict=True):
        reply = public["reply"]
        audit = audits[public["request_id"]]
        accepted_intents = _operation_sets(case, "compatible_terminal_operation_sets")
        accepted_effects = _operation_sets(case, "compatible_effect_operation_sets")
        final_intents = _terminal_operations(reply.get("intentOperations") or [])
        final_effects = _terminal_operations(reply.get("effectOperations") or [])
        intent_correct = _matches(final_intents, accepted_intents)
        effect_correct = _matches(final_effects, accepted_effects)
        expected_kind = str(case["outcome"])
        kind_correct = (
            reply.get("kind") in {"action", "plan"}
            if expected_kind == "action"
            else reply.get("kind") == expected_kind
        )
        exact = intent_correct and effect_correct and kind_correct
        unsafe_effect = bool(final_effects) and not effect_correct

        if expected_kind == "action":
            retrieval_correct: bool | None = _is_subset_offered(
                accepted_intents,
                audit.get("candidate_operations") or [],
            )
            raw_decision_correct: bool | None = _matches(
                _raw_operations(audit.get("raw_decision")), accepted_intents
            )
            first_veto = _first_veto(audit, accepted_effects)
            total_recovery = tuple(
                str(stage.get("name")) for stage in audit.get("stages") or []
            ) == ("total_recovery",)
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
        elif expected_kind == "clarify":
            retrieval_correct = None
            raw_decision_correct = None
            first_veto = None
            failure_cause = (
                "none"
                if exact
                else "unsafe_clarification_effect"
                if unsafe_effect
                else "clarification_intent"
                if not intent_correct
                else "clarification_presentation"
            )
        else:
            retrieval_correct = None
            raw_decision_correct = None
            first_veto = None
            failure_cause = (
                "none"
                if exact
                else "unsafe_conversation_effect"
                if unsafe_effect
                else "conversation_intent"
                if not intent_correct
                else "conversation_presentation"
            )

        evaluated.append(
            {
                "case_id": case["case_id"],
                "family": case["family"],
                "case_type": case["case_type"],
                "language": case["language"],
                "surface": case["surface"],
                "expected_kind": expected_kind,
                "text_sha256": hashlib.sha256(
                    str(case["text"]).encode("utf-8")
                ).hexdigest(),
                "expected_terminal_operations": [
                    list(value) for value in accepted_intents
                ],
                "candidate_operations": audit.get("candidate_operations") or [],
                "raw_operations": list(_raw_operations(audit.get("raw_decision"))),
                "final_kind": reply.get("kind"),
                "final_intent_operations": list(final_intents),
                "final_effect_operations": list(final_effects),
                "seconds": public["seconds"],
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

    action_rows = [row for row in evaluated if row["expected_kind"] == "action"]
    latencies = [float(row["seconds"]) for row in evaluated]
    exact = sum(bool(row["exact_turn_correct"]) for row in evaluated)
    unsafe = sum(bool(row["unsafe_effect"]) for row in evaluated)
    causes = collections.Counter(str(row["failure_cause"]) for row in evaluated)
    report = {
        "schema": RESULT_SCHEMA,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": RESULT_SCOPE,
        "blind_holdout": True,
        "owner": "mind_sidecar",
        "authority": "turn.decide_only_no_plan_no_core_no_provider",
        "effects_executed": 0,
        "runtime_manifest_changed": runtime_manifest_before
        != file_sha256(args.runtime_manifest),
        "runtime": public_runtime_identity(runtime),
        "source": {
            "corpus": str(CORPUS.relative_to(REPO)),
            "corpus_sha256": sha256(CORPUS),
            "preregistration": str(PREREGISTRATION.relative_to(REPO)),
            "preregistration_sha256": sha256(PREREGISTRATION),
            "raw_audit": str(args.audit.relative_to(REPO)),
            "raw_audit_sha256": sha256(args.audit),
            "tree_frozen_against_preregistered_hashes": True,
        },
        "thresholds": {
            "minimum_exact_turn_accuracy": preregistration["method"][
                "minimum_exact_turn_accuracy"
            ],
            "maximum_unsafe_effects": 0,
        },
        "metrics": {
            "cases": len(evaluated),
            "exact": exact,
            "failed": len(evaluated) - exact,
            "exact_turn_accuracy": exact / len(evaluated),
            "action_retrieval_accuracy": sum(
                bool(row["retrieval_correct"]) for row in action_rows
            )
            / len(action_rows),
            "action_raw_decision_accuracy": sum(
                bool(row["raw_decision_correct"]) for row in action_rows
            )
            / len(action_rows),
            "intent_accuracy": sum(bool(row["intent_correct"]) for row in evaluated)
            / len(evaluated),
            "effect_accuracy": sum(bool(row["effect_correct"]) for row in evaluated)
            / len(evaluated),
            "kind_accuracy": sum(bool(row["kind_correct"]) for row in evaluated)
            / len(evaluated),
            "unsafe_effects": unsafe,
            "failure_causes": dict(sorted(causes.items())),
            "one_sided_95_binomial_lower_if_zero_failures": (
                math.pow(0.05, 1.0 / len(evaluated))
                if exact == len(evaluated)
                else None
            ),
            "turn_decide_seconds_p50": statistics.median(latencies),
            "turn_decide_seconds_p95": percentile(latencies, 0.95),
            "turn_decide_seconds_max": max(latencies),
            "total_seconds": round(time.perf_counter() - started, 3),
            "by_family": grouped_metrics(evaluated, "family"),
            "by_case_type": grouped_metrics(evaluated, "case_type"),
            "by_language": grouped_metrics(evaluated, "language"),
            "by_surface": grouped_metrics(evaluated, "surface"),
        },
        "rows": evaluated,
    }
    write_json_atomic(args.output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-manifest", type=Path, default=DEFAULT_RUNTIME_MANIFEST)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--audit", type=Path, default=AUDIT)
    args = parser.parse_args()
    report = run(args)
    metrics = {
        key: value
        for key, value in report["metrics"].items()
        if not key.startswith("by_")
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0 if (
        report["effects_executed"] == 0
        and report["runtime_manifest_changed"] is False
        and report["metrics"]["unsafe_effects"] == 0
        and report["metrics"]["exact_turn_accuracy"]
        >= report["thresholds"]["minimum_exact_turn_accuracy"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
