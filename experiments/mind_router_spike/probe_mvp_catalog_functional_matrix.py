"""Measure every non-memory catalogue operation through the real Mind sidecar.

The reviewed seen corpus has exactly one authenticated scenario per catalogue
operation.  This probe sends the 158 Mind-owned rows through ``turn.decide``
with the compiled Core catalogue and records retrieval, decision and veto
failures.  It never sends a plan to Core or a provider.  The eleven App-owned
private-memory rows remain a separate, explicitly named gate.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
SPIKE = Path(__file__).resolve().parent
for path in (REPO, REPO / "src", REPO / "scripts", SPIKE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from probe_current_catalog_review import (  # noqa: E402
    EXPECTED_STAGE_NAMES,
    _first_veto,
    _is_subset_offered,
    _matches,
    _operation_sets,
    _percentile,
    _raw_operations,
    _read_audit,
    _terminal_operations,
)
from scripts.baxy_runtime_config import (  # noqa: E402
    add_runtime_arguments,
    public_runtime_identity,
    resolve_runtime_from_args,
)
from scripts.measure_mind_budget import (  # noqa: E402
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)


SCENARIOS = (
    REPO
    / "artifacts"
    / "development"
    / "catalog_seen_scenarios_r2_dependency_complete.jsonl"
)
SCENARIOS_SHA256 = "cbe9fc751ccfddf60ba1a66e5ca149ec1c0f29cec02783e2566444294ff51978"
ALIASES = REPO / "src" / "baxy_mind" / "data" / "catalog_operation_aliases.v1.json"
CATALOG_SHA256 = "67c82b61bc661bdf35478a1ae2139e2b609dcbb861e0c59ab5d05dfa0a41fd41"
EXPECTED_OPERATIONS = 169
EXPECTED_MIND_ROWS = 158
EXPECTED_APP_MEMORY_ROWS = 11
DEFAULT_OUTPUT = REPO / "artifacts" / "mvp" / "catalog_functional_matrix_mind_v1.json"
DEFAULT_AUDIT = (
    REPO / "artifacts" / "mvp" / "catalog_functional_matrix_mind_v1.raw.jsonl"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_scenarios() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if file_sha256(SCENARIOS) != SCENARIOS_SHA256:
        raise RuntimeError("the reviewed MVP catalogue scenarios changed")
    rows = [
        json.loads(line)
        for line in SCENARIOS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    targets = {str(row.get("target_operation")) for row in rows}
    if (
        len(rows) != EXPECTED_OPERATIONS
        or len(targets) != EXPECTED_OPERATIONS
        or any(row.get("catalog_sha256") != CATALOG_SHA256 for row in rows)
        or any(row.get("blind_holdout") is not False for row in rows)
        or any(row.get("execution_authority") is not False for row in rows)
        or any(row.get("outcome") != "action" for row in rows)
    ):
        raise RuntimeError("the reviewed MVP catalogue scenario contract is invalid")
    mind = [row for row in rows if row.get("owner") == "mind_sidecar"]
    memory = [row for row in rows if row.get("owner") == "app_memory_parser"]
    if len(mind) != EXPECTED_MIND_ROWS or len(memory) != EXPECTED_APP_MEMORY_ROWS:
        raise RuntimeError("the MVP catalogue ownership split changed")
    return mind, memory


def evaluate_row(
    case: dict[str, Any],
    reply: dict[str, Any],
    audit: dict[str, Any],
    seconds: float,
) -> dict[str, Any]:
    accepted_intents = _operation_sets(case, "compatible_terminal_operation_sets")
    accepted_effects = _operation_sets(case, "compatible_effect_operation_sets")
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
    unsafe_effect = bool(final_effects) and not effect_correct
    first_veto = _first_veto(audit, accepted_effects)
    failure_cause = (
        "none"
        if intent_correct and effect_correct and kind_correct
        else "retrieval"
        if not retrieval_correct
        else "decision"
        if not raw_decision_correct or not intent_correct
        else f"veto:{first_veto or 'unattributed'}"
        if not effect_correct
        else "presentation"
    )
    return {
        "case_id": case["case_id"],
        "family": str(case["target_operation"]).split(".", 1)[0],
        "language": case["language"],
        "target_operation": case["target_operation"],
        "text": case["text"],
        "seconds": round(seconds, 6),
        "candidate_operations": audit.get("candidate_operations") or [],
        "final_kind": reply.get("kind"),
        "final_intent_operations": list(final_intents),
        "final_effect_operations": list(final_effects),
        "retrieval_correct": retrieval_correct,
        "raw_decision_correct": raw_decision_correct,
        "intent_correct": intent_correct,
        "effect_correct": effect_correct,
        "kind_correct": kind_correct,
        "unsafe_effect": unsafe_effect,
        "first_veto": first_veto,
        "failure_cause": failure_cause,
        "exact_turn_correct": intent_correct and effect_correct and kind_correct,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    mind_cases, memory_cases = load_scenarios()
    for path in (args.output, args.audit):
        if path.exists():
            raise RuntimeError(f"refusing to overwrite existing evidence: {path}")
    args.audit.parent.mkdir(parents=True, exist_ok=True)

    runtime = resolve_runtime_from_args(args)
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(
        discover_core(args.core)
    )
    catalog_names = {str(item["name"]) for item in capabilities}
    scenario_names = {
        str(row["target_operation"]) for row in (*mind_cases, *memory_cases)
    }
    if len(capabilities) != EXPECTED_OPERATIONS or catalog_names != scenario_names:
        raise RuntimeError(
            "compiled Core catalogue differs from the 169-row MVP matrix"
        )

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
    observed: list[tuple[dict[str, Any], dict[str, Any], float]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("the Mind sidecar rejected its handshake")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-mvp-functional-matrix",
                "capabilities": capabilities,
                "applicationCatalog": application_catalog,
                "gameCatalog": game_catalog,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("the Mind sidecar rejected the authenticated catalogue")
        client.request(
            {
                "type": "turn.decide",
                "id": "warm-mvp-functional-matrix",
                "text": "hola",
                "history": [],
                "uiLanguage": "es",
            },
            limits["turn.decide"],
        )
        for case in mind_cases:
            request_id = f"mvp-matrix-{case['case_id']}"
            started = time.perf_counter()
            reply = client.request(
                {
                    "type": "turn.decide",
                    "id": request_id,
                    "text": case["text"],
                    "history": [],
                    "uiLanguage": case["language"]
                    if case["language"] in {"es", "en"}
                    else "es",
                },
                limits["turn.decide"],
            )
            observed.append((case, reply, time.perf_counter() - started))
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "shutdown-mvp-matrix"},
            timeout=limits["shutdown"],
        )

    request_ids = {f"mvp-matrix-{case['case_id']}" for case in mind_cases}
    audits = _read_audit(args.audit, request_ids)
    rows = [
        evaluate_row(
            case,
            reply,
            audits[f"mvp-matrix-{case['case_id']}"],
            seconds,
        )
        for case, reply, seconds in observed
    ]
    causes = collections.Counter(str(row["failure_cause"]) for row in rows)
    by_language = {
        language: {
            "cases": len(selected),
            "exact": sum(bool(row["exact_turn_correct"]) for row in selected),
        }
        for language in ("es", "en", "spanglish")
        if (selected := [row for row in rows if row["language"] == language])
    }
    latencies = [float(row["seconds"]) for row in rows]
    exact = sum(bool(row["exact_turn_correct"]) for row in rows)
    unsafe = sum(bool(row["unsafe_effect"]) for row in rows)
    report = {
        "schema": "baxy.mvp-catalog-functional-matrix-mind.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "reviewed_seen_catalog_not_blind",
        "authority": "turn.decide_only_no_plan_sent_to_core_or_provider",
        "audit_stage_names": list(EXPECTED_STAGE_NAMES),
        "program_sha256": file_sha256(Path(__file__)),
        "source": {
            "scenarios": str(SCENARIOS.relative_to(REPO)),
            "scenarios_sha256": SCENARIOS_SHA256,
            "aliases_sha256": file_sha256(ALIASES),
            "catalog_sha256": CATALOG_SHA256,
        },
        "runtime": public_runtime_identity(runtime),
        "catalog": {
            "operations": len(capabilities),
            "mind_owned": len(mind_cases),
            "app_memory_owned": len(memory_cases),
        },
        "metrics": {
            "exact": exact,
            "cases": len(rows),
            "exact_accuracy": exact / len(rows),
            "unsafe_effects": unsafe,
            "failure_causes": dict(sorted(causes.items())),
            "by_language": by_language,
            "latency_seconds": {
                "p50": _percentile(latencies, 0.50),
                "p95": _percentile(latencies, 0.95),
                "maximum": max(latencies),
            },
        },
        "app_memory_gate": {
            "status": "pending_separate_app_gate",
            "cases": len(memory_cases),
            "operations": sorted(str(row["target_operation"]) for row in memory_cases),
        },
        "rows": rows,
        "effects_executed": 0,
        "development_gate_passed": exact == len(rows) and unsafe == 0,
        "promotion_eligible": False,
    }
    write_json_atomic(args.output.resolve(), report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure the 158 Mind-owned operations of the MVP matrix."
    )
    add_runtime_arguments(parser)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    return parser.parse_args()


def main() -> int:
    report = run(parse_args())
    print(
        json.dumps(
            {
                "schema": report["schema"],
                "passed": report["development_gate_passed"],
                "exact": report["metrics"]["exact"],
                "cases": report["metrics"]["cases"],
                "unsafe_effects": report["metrics"]["unsafe_effects"],
                "app_memory_pending": report["app_memory_gate"]["cases"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["development_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
