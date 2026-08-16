"""Open the preregistered generalization holdout exactly once.

Only ``turn.decide`` is sent.  Raw opt-in policy telemetry attributes misses to
retrieval, decision, or the first authority veto.  No plan, Core request,
provider request, or effect is permitted by this probe.
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
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    MEASUREMENT_SOURCES,
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


OUTPUT = REPO / "artifacts/holdout/generalization_surface_holdout_r1.json"
AUDIT = REPO / "artifacts/holdout/generalization_surface_holdout_r1.raw.jsonl"
BUILDER = REPO / "scripts/build_generalization_surface_holdout.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        raise RuntimeError("blind holdout preregistration identity is invalid")
    expected_policy = manifest["sources"]["policy_sha256"]
    actual_policy = {
        str(path.relative_to(REPO)): sha256(path) for path in POLICY_SOURCES
    }
    if expected_policy != actual_policy:
        raise RuntimeError("policy sources changed after holdout preregistration")
    expected_measurement = manifest["sources"]["measurement_sha256"]
    actual_measurement = {
        str(path.relative_to(REPO)): sha256(path) for path in MEASUREMENT_SOURCES
    }
    if expected_measurement != actual_measurement:
        raise RuntimeError("measurement sources changed after holdout preregistration")
    rows = [
        json.loads(line)
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if (
        len(rows) != manifest["output"]["rows"]
        or len({row.get("case_id") for row in rows}) != len(rows)
        or not all(row.get("blind_holdout") is True for row in rows)
        or not all(row.get("execution_authority") is False for row in rows)
    ):
        raise RuntimeError("blind holdout population shape is invalid")
    return rows, manifest


def grouped_metrics(
    rows: list[dict[str, Any]],
    field: str,
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        groups[str(row[field])].append(row)
    return {
        value: {
            "cases": len(group),
            "exact": sum(bool(row["exact_turn_correct"]) for row in group),
            "accuracy": sum(bool(row["exact_turn_correct"]) for row in group)
            / len(group),
            "unsafe_effects": sum(bool(row["unsafe_effect"]) for row in group),
        }
        for value, group in sorted(groups.items())
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    cases, preregistration = load_inputs()
    for path in (args.output, args.audit):
        if path.exists():
            raise RuntimeError(f"refusing to overwrite opened holdout evidence: {path}")
    args.audit.parent.mkdir(parents=True, exist_ok=True)
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
        raise RuntimeError("compiled catalogue changed after holdout preregistration")
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    environment["BAXY_MIND_TURN_AUDIT_PATH"] = str(args.audit.resolve())
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
            raise RuntimeError("sidecar rejected its handshake")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-generalization-holdout",
                "capabilities": capabilities,
                "applicationCatalog": application_catalog,
                "gameCatalog": game_catalog,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("sidecar rejected the authenticated catalogue")
        client.request(
            {
                "type": "turn.decide",
                "id": "warm-generalization-holdout",
                "text": "hola",
                "history": [],
                "uiLanguage": "es",
            },
            limits["turn.decide"],
        )
        for case in cases:
            request_id = f"blind-generalization-{case['case_id']}"
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
            graceful_message={"type": "shutdown", "id": "shutdown-generalization"},
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
        accepted_intents = _operation_sets(
            case,
            "compatible_terminal_operation_sets",
        )
        accepted_effects = _operation_sets(
            case,
            "compatible_effect_operation_sets",
        )
        final_intents = _terminal_operations(reply.get("intentOperations") or [])
        final_effects = _terminal_operations(reply.get("effectOperations") or [])
        retrieval_correct = _is_subset_offered(
            accepted_intents,
            audit.get("candidate_operations") or [],
        )
        raw_decision_correct = _matches(
            _raw_operations(audit.get("raw_decision")),
            accepted_intents,
        )
        intent_correct = _matches(final_intents, accepted_intents)
        effect_correct = _matches(final_effects, accepted_effects)
        kind_correct = reply.get("kind") in {"action", "plan"}
        exact = intent_correct and effect_correct and kind_correct
        unsafe_effect = bool(final_effects) and not effect_correct
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
    latencies = [float(row["seconds"]) for row in evaluated]
    successes = sum(bool(row["exact_turn_correct"]) for row in evaluated)
    failures = len(evaluated) - successes
    unsafe_effects = sum(bool(row["unsafe_effect"]) for row in evaluated)
    causes = collections.Counter(str(row["failure_cause"]) for row in evaluated)
    runtime_manifest_after = file_sha256(args.runtime_manifest)
    report = {
        "schema": "baxy.generalization-surface-holdout-result.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "blind_generalization_surface_cut_b",
        "authority": "turn.decide_only_no_plan_no_core_no_provider",
        "effects_executed": 0,
        "runtime_manifest_changed": runtime_manifest_before
        != runtime_manifest_after,
        "runtime": public_runtime_identity(runtime),
        "source": {
            "corpus": str(CORPUS.relative_to(REPO)),
            "corpus_sha256": sha256(CORPUS),
            "preregistration": str(PREREGISTRATION.relative_to(REPO)),
            "preregistration_sha256": sha256(PREREGISTRATION),
            "raw_audit": str(args.audit.relative_to(REPO)),
            "raw_audit_sha256": sha256(args.audit),
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
            "turn_decide_seconds_p50": statistics.median(latencies),
            "turn_decide_seconds_p95": percentile(latencies, 0.95),
            "total_seconds": round(time.perf_counter() - started, 3),
            "by_family": grouped_metrics(evaluated, "family"),
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
    public_metrics = {
        key: value
        for key, value in report["metrics"].items()
        if not key.startswith("by_")
    }
    print(json.dumps(public_metrics, ensure_ascii=False, indent=2))
    return 0 if (
        report["effects_executed"] == 0
        and report["runtime_manifest_changed"] is False
        and report["metrics"]["unsafe_effects"] == 0
        and report["metrics"]["exact_turn_accuracy"]
        >= report["thresholds"]["minimum_exact_turn_accuracy"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
