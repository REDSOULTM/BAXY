"""Measure the reviewed catalogue through the final side-effect-free mind stage.

The development review already fixes the requested terminal effects.  This
probe sends ``turn.decide`` and then either ``arguments`` or ``plan`` so a
request counts as ready only after every literal plan step satisfies the
authenticated schema.  It never sends an operation to Core or a provider.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import probe_current_catalog_review as review  # noqa: E402
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
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
from baxy_mind.effect_intent import (  # noqa: E402
    build_game_catalog_index,
    resolve_game_catalog_app_id,
)


DEFAULT_OUTPUT = REPO / "artifacts/research/current_catalog_ready_pipeline_r2.json"
DEFAULT_AUDIT = REPO / "artifacts/research/current_catalog_ready_pipeline_r2.raw.jsonl"

PRESENTABLE_OUTCOME_OVERRIDES = {
    "ocr-00": (
        ("clarify", "conversation"),
        "a non-effect fragment may be acknowledged or clarified without authority",
    ),
    "system-00": (
        ("clarify", "conversation"),
        "a non-effect parenthetical fragment may be acknowledged or clarified",
    ),
}


def _percentile(values: Iterable[float], probability: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    return round(ordered[round((len(ordered) - 1) * probability)], 6)


def _terminal_plan_operations(reply: dict[str, Any]) -> tuple[str, ...]:
    steps = reply.get("steps")
    if not isinstance(steps, list):
        return ()
    operations = tuple(
        str(step.get("operation") or "")
        for step in steps
        if isinstance(step, dict)
    )
    if len(operations) != len(steps) or any(not operation for operation in operations):
        return ()
    return review._terminal_operations(operations)


def _accepted(case: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    return review._operation_sets(case, "compatible_terminal_operation_sets")


def _arguments_are_semantically_ready(
    operation: str,
    arguments: object,
) -> bool:
    """Check product invariants that are narrower than the JSON Schema."""

    if not isinstance(arguments, dict):
        return False
    if operation not in {"notification.schedule", "reminder.create"}:
        return True
    due_utc = arguments.get("dueUtc")
    if not isinstance(due_utc, str):
        return False
    try:
        parsed = datetime.fromisoformat(due_utc.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _plan_arguments_are_semantically_ready(reply: dict[str, Any]) -> bool:
    steps = reply.get("steps")
    if not isinstance(steps, list):
        return False
    return all(
        isinstance(step, dict)
        and isinstance(step.get("operation"), str)
        and (
            step.get("argumentsMode") != "literal"
            or _arguments_are_semantically_ready(
                str(step["operation"]),
                step.get("arguments"),
            )
        )
        for step in steps
    )


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    exact = sum(bool(row["exact"]) for row in rows)
    presentable_exact = sum(bool(row["presentable_exact"]) for row in rows)
    action_rows = [row for row in rows if row["expected_outcome"] == "ready"]
    ready = sum(row["observed_outcome"] == "ready" for row in action_rows)
    presentable_action_rows = [
        row
        for row in rows
        if "ready" in row["presentable_expected_outcomes"]
    ]
    presentable_ready = sum(
        row["observed_outcome"] == "ready"
        for row in presentable_action_rows
    )
    outcomes = Counter(str(row["observed_outcome"]) for row in rows)
    turn_seconds = [float(row["turn_seconds"]) for row in rows]
    total_seconds = [float(row["total_seconds"]) for row in rows]
    return {
        "cases": total,
        "exact": exact,
        "exact_accuracy": round(exact / total, 6),
        "presentable_exact": presentable_exact,
        "presentable_exact_accuracy": round(presentable_exact / total, 6),
        "complete_action_cases": len(action_rows),
        "ready_actions": ready,
        "ready_action_rate": (
            round(ready / len(action_rows), 6) if action_rows else None
        ),
        "presentable_complete_action_cases": len(presentable_action_rows),
        "presentable_ready_actions": presentable_ready,
        "presentable_ready_action_rate": (
            round(presentable_ready / len(presentable_action_rows), 6)
            if presentable_action_rows
            else None
        ),
        "observed_outcomes": dict(sorted(outcomes.items())),
        "turn_latency_seconds": {
            "p50": _percentile(turn_seconds, 0.50),
            "p95": _percentile(turn_seconds, 0.95),
        },
        "ready_pipeline_latency_seconds": {
            "p50": _percentile(total_seconds, 0.50),
            "p95": _percentile(total_seconds, 0.95),
            "maximum": round(max(total_seconds), 6),
        },
    }


def run(*, output: Path, audit: Path) -> dict[str, Any]:
    cases, manifest = review._load_inputs()
    if output.exists() or audit.exists():
        raise RuntimeError("refusing to overwrite an existing ready-pipeline artifact")
    output.parent.mkdir(parents=True, exist_ok=True)
    audit.parent.mkdir(parents=True, exist_ok=True)
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    catalog_names = {str(item["name"]) for item in capabilities}
    game_entries = tuple(
        (
            str(entry.get("provider") or ""),
            str(entry.get("appId") or ""),
            str(entry.get("name") or ""),
        )
        for entry in (game_catalog or {}).get("entries", [])
        if isinstance(entry, dict)
    )
    authenticated_games = build_game_catalog_index(game_entries)
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    environment["BAXY_MIND_TURN_AUDIT_PATH"] = str(audit.resolve())
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    measured: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("mind sidecar did not publish hello")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "current-ready-catalog",
                "capabilities": capabilities,
                "applicationCatalog": application_catalog,
                "gameCatalog": game_catalog,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("mind sidecar rejected the authenticated catalogue")
        client.request(
            {
                "type": "turn.decide",
                "id": "current-ready-warmup",
                "text": "hola, responde brevemente",
                "history": [],
            },
            limits["turn.decide"],
        )
        for index, case in enumerate(cases):
            accepted = _accepted(case)
            if any(operation not in catalog_names for group in accepted for operation in group):
                raise RuntimeError("review references an operation outside the catalogue")
            expected_outcome = {
                "action": "ready",
                "clarify": "clarify",
                "conversation": "conversation",
                "unsupported": "conversation",
            }[str(case["outcome"])]
            presentable_expected_outcomes = (expected_outcome,)
            presentable_adjustment = ""
            override = PRESENTABLE_OUTCOME_OVERRIDES.get(str(case["case_id"]))
            if override is not None:
                presentable_expected_outcomes, presentable_adjustment = override
            elif (
                case["case_id"] == "game-02"
                and resolve_game_catalog_app_id(
                    str(case["text"]),
                    authenticated_games,
                )
                is None
            ):
                presentable_expected_outcomes = ("conversation",)
                presentable_adjustment = (
                    "the requested title is absent from the authenticated installed-game inventory"
                )
            started = time.perf_counter()
            started_at_utc = datetime.now(timezone.utc).isoformat()
            turn_started = time.perf_counter()
            turn = client.request(
                {
                    "type": "turn.decide",
                    "id": f"current-ready-turn-{index}",
                    "text": case["text"],
                    "history": [],
                    "uiLanguage": case["language"],
                },
                limits["turn.decide"],
            )
            turn_seconds = time.perf_counter() - turn_started
            kind = str(turn.get("kind") or "")
            effects = tuple(str(value) for value in turn.get("effectOperations") or [])
            observed_outcome = "invalid_turn"
            terminal_operations: tuple[str, ...] = ()
            downstream: dict[str, Any] | None = None
            if kind == "conversation":
                observed_outcome = "conversation"
            elif kind == "clarify":
                observed_outcome = "clarify"
            elif kind == "action" and isinstance(turn.get("operation"), str):
                operation = str(turn["operation"])
                downstream = client.request(
                    {
                        "type": "arguments",
                        "id": f"current-ready-arguments-{index}",
                        "operation": operation,
                        "text": case["text"],
                    },
                    limits["arguments"],
                )
                if (
                    downstream.get("type") == "arguments.result"
                    and downstream.get("ok") is True
                    and isinstance(downstream.get("arguments"), dict)
                ):
                    if _arguments_are_semantically_ready(
                        operation,
                        downstream["arguments"],
                    ):
                        observed_outcome = "ready"
                        terminal_operations = (operation,)
                    else:
                        observed_outcome = "semantic_arguments_error"
                elif (
                    downstream.get("type") == "arguments.result"
                    and downstream.get("ok") is False
                    and isinstance(downstream.get("question"), str)
                    and str(downstream["question"]).strip()
                ):
                    observed_outcome = "clarify"
                else:
                    observed_outcome = "arguments_error"
            elif kind == "plan" and effects:
                downstream = client.request(
                    {
                        "type": "plan",
                        "id": f"current-ready-plan-{index}",
                        "text": case["text"],
                        "history": [],
                        "expectedOperations": list(effects),
                    },
                    60.0,
                )
                if downstream.get("type") == "plan.result":
                    if downstream.get("kind") == "plan":
                        if _plan_arguments_are_semantically_ready(downstream):
                            terminal_operations = _terminal_plan_operations(downstream)
                            observed_outcome = "ready"
                        else:
                            observed_outcome = "semantic_arguments_error"
                    elif (
                        downstream.get("kind") == "clarify"
                        and isinstance(downstream.get("question"), str)
                        and str(downstream["question"]).strip()
                    ):
                        observed_outcome = "clarify"
                    else:
                        observed_outcome = "invalid_plan_result"
                else:
                    observed_outcome = "plan_error"
            operation_correct = (
                not terminal_operations
                if expected_outcome != "ready"
                else terminal_operations in accepted
            )
            exact = observed_outcome == expected_outcome and operation_correct
            presentable_operation_correct = (
                operation_correct
                if "ready" in presentable_expected_outcomes
                else not terminal_operations
            )
            presentable_exact = (
                observed_outcome in presentable_expected_outcomes
                and presentable_operation_correct
            )
            measured.append(
                {
                    "case_id": case["case_id"],
                    "family": case["source_historical_family"],
                    "text": case["text"],
                    "accepted_terminal_operations": [list(group) for group in accepted],
                    "expected_outcome": expected_outcome,
                    "presentable_expected_outcomes": list(
                        presentable_expected_outcomes
                    ),
                    "presentable_adjustment": presentable_adjustment,
                    "observed_outcome": observed_outcome,
                    "terminal_operations": list(terminal_operations),
                    "operation_correct": operation_correct,
                    "exact": exact,
                    "presentable_operation_correct": presentable_operation_correct,
                    "presentable_exact": presentable_exact,
                    "turn": {
                        "kind": kind,
                        "intent_operations": list(turn.get("intentOperations") or []),
                        "effect_operations": list(effects),
                    },
                    "downstream": downstream,
                    "turn_seconds": round(turn_seconds, 6),
                    "total_seconds": round(time.perf_counter() - started, 6),
                    "started_at_utc": started_at_utc,
                    "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "current-ready-shutdown"},
            timeout=limits["shutdown"],
        )

    by_family: dict[str, dict[str, Any]] = {}
    for family, family_rows in sorted(
        defaultdict(list, {
            family: [row for row in measured if row["family"] == family]
            for family in {str(row["family"]) for row in measured}
        }).items()
    ):
        by_family[family] = _summarize(family_rows)
    failures = [row for row in measured if not row["exact"]]
    presentable_failures = [
        row for row in measured if not row["presentable_exact"]
    ]
    report = {
        "schema": "baxy.current-catalog-ready-pipeline.development.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "reviewed_development_only_blind_holdout_remains_sealed",
        "side_effect_free": True,
        "core_or_provider_requests_sent": 0,
        "source": {
            "corpus": str(review.CORPUS),
            "corpus_sha256": review._sha256(review.CORPUS),
            "rows": len(cases),
            "all_rows_explicitly_reviewed": manifest["review"][
                "all_rows_explicitly_reviewed"
            ],
        },
        "runtime": public_runtime_identity(runtime),
        "summary": _summarize(measured),
        "by_family": by_family,
        "failure_groups": dict(
            Counter(
                f"{row['family']}:{row['observed_outcome']}"
                for row in failures
            ).most_common()
        ),
        "failures": failures,
        "presentable_failure_groups": dict(
            Counter(
                f"{row['family']}:{row['observed_outcome']}"
                for row in presentable_failures
            ).most_common()
        ),
        "presentable_failures": presentable_failures,
        "rows": measured,
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()
    report = run(output=args.output, audit=args.audit)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(json.dumps(report["failure_groups"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
