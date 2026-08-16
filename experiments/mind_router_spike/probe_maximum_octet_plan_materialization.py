"""Exercise maximum-octet turn-to-plan materialization without effects.

Thirty deterministic permutations cover every operation in every position and
every ordered adjacent pair at least once. Language, connector surface, and
lexical profile are balanced. Each case first uses ``turn.decide`` and then
passes its exact effect contract to the production ``plan`` request, matching
the desktop path. The probe validates all eight operations, dependencies,
argument modes, and literal arguments. It never calls Core or a provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike.probe_catalog_pairwise_composition import (  # noqa: E402
    ACTION_TAILS,
    READ_ONLY_TAILS,
    TAIL_LEXICAL_VARIANTS,
)
from experiments.mind_router_spike.probe_maximum_octet_composition import (  # noqa: E402
    LEXICAL_PROFILES,
    SURFACES,
    _render,
)
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    file_sha256,
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


OUTPUT = REPO / "artifacts/fixes/maximum_octet_plan_materialization_r1.json"
CASE_COUNT = 30
PLAN_TIMEOUT_SECONDS = 60.0


def _balanced_orders() -> list[tuple[str, ...]]:
    tails = (*READ_ONLY_TAILS, *ACTION_TAILS)
    tail_ids = tuple(str(tail["tail_id"]) for tail in tails)
    candidates = list(permutations(tail_ids))
    uncovered_positions = {
        (tail_id, position)
        for tail_id in tail_ids
        for position in range(len(tail_ids))
    }
    uncovered_adjacencies = {
        (left, right)
        for left in tail_ids
        for right in tail_ids
        if left != right
    }
    selected: list[tuple[str, ...]] = []
    selected_set: set[tuple[str, ...]] = set()
    position_counts: Counter[tuple[str, int]] = Counter()
    adjacency_counts: Counter[tuple[str, str]] = Counter()

    while uncovered_positions or uncovered_adjacencies:
        best: tuple[str, ...] | None = None
        best_score = -1
        for order in candidates:
            if order in selected_set:
                continue
            positions = {(tail_id, index) for index, tail_id in enumerate(order)}
            adjacencies = set(zip(order, order[1:]))
            score = (
                100 * len(adjacencies & uncovered_adjacencies)
                + 10 * len(positions & uncovered_positions)
            )
            if score > best_score:
                best = order
                best_score = score
        if best is None or best_score <= 0:
            raise RuntimeError("unable to complete balanced octet coverage")
        selected.append(best)
        selected_set.add(best)
        for position, tail_id in enumerate(best):
            position_counts[(tail_id, position)] += 1
            uncovered_positions.discard((tail_id, position))
        for pair in zip(best, best[1:]):
            adjacency_counts[pair] += 1
            uncovered_adjacencies.discard(pair)

    while len(selected) < CASE_COUNT:
        best = None
        best_score = -1.0
        for order in candidates:
            if order in selected_set:
                continue
            score = sum(
                1.0 / (1 + position_counts[(tail_id, position)])
                for position, tail_id in enumerate(order)
            ) + sum(
                0.25 / (1 + adjacency_counts[pair])
                for pair in zip(order, order[1:])
            )
            if score > best_score:
                best = order
                best_score = score
        if best is None:
            raise RuntimeError("unable to fill balanced octet sample")
        selected.append(best)
        selected_set.add(best)
        for position, tail_id in enumerate(best):
            position_counts[(tail_id, position)] += 1
        for pair in zip(best, best[1:]):
            adjacency_counts[pair] += 1

    return selected


def _expected_arguments(operation: str, language: str) -> dict[str, Any]:
    if operation in {
        "system.time",
        "task.list",
        "note.list",
        "system.process.list",
    }:
        return {}
    if operation == "audio.mute":
        return {"state": True}
    if operation == "audio.volume":
        return {"level": 17}
    if operation == "task.create":
        return {"title": "Matrix Tail" if language == "en" else "Cola Matriz"}
    if operation == "note.create":
        return {
            "title": "Matrix Tail" if language == "en" else "Cola Matriz",
            "content": "verified" if language == "en" else "verificado",
        }
    raise ValueError(f"unexpected octet operation: {operation}")


def build_cases() -> list[dict[str, Any]]:
    tails = (*READ_ONLY_TAILS, *ACTION_TAILS)
    by_id = {str(tail["tail_id"]): tail for tail in tails}
    cases: list[dict[str, Any]] = []
    for index, order in enumerate(_balanced_orders()):
        language = "es" if index % 2 == 0 else "en"
        surface = SURFACES[index % len(SURFACES)]
        lexical_profile = LEXICAL_PROFILES[index % len(LEXICAL_PROFILES)]
        lexical_index = (
            None
            if lexical_profile == "canonical"
            else int(lexical_profile[-1]) - 1
        )
        parts: list[str] = []
        expected_operations: list[str] = []
        expected_arguments: list[dict[str, Any]] = []
        for tail_id in order:
            tail = by_id[tail_id]
            phrase = (
                str(tail[language])
                if lexical_index is None
                else TAIL_LEXICAL_VARIANTS[tail_id][language][lexical_index]
            )
            operation = str(tail["operation"])
            parts.append(phrase.rstrip().rstrip(".?!"))
            expected_operations.append(operation)
            expected_arguments.append(_expected_arguments(operation, language))
        cases.append(
            {
                "case_id": f"octet-plan-{index:02d}",
                "order": order,
                "language": language,
                "surface": surface,
                "lexical_profile": lexical_profile,
                "text": _render(tuple(parts), language, surface),
                "expected_operations": expected_operations,
                "expected_arguments": expected_arguments,
            }
        )
    return cases


def _validate_plan(case: dict[str, Any], reply: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if reply.get("type") != "plan.result" or reply.get("kind") != "plan":
        return ["unexpected_plan_response"]
    steps = reply.get("steps")
    if not isinstance(steps, list) or len(steps) != 8:
        return ["unexpected_step_count"]
    observed_operations = [step.get("operation") for step in steps]
    if observed_operations != case["expected_operations"]:
        errors.append("operation_order_mismatch")
    observed_ids = [step.get("id") for step in steps]
    if observed_ids != [f"step_{index}" for index in range(1, 9)]:
        errors.append("step_identity_mismatch")
    for index, step in enumerate(steps):
        if step.get("dependsOn") != []:
            errors.append(f"unexpected_dependency:{index}")
        if step.get("argumentsMode") != "literal":
            errors.append(f"unexpected_arguments_mode:{index}")
        if step.get("arguments") != case["expected_arguments"][index]:
            errors.append(f"arguments_mismatch:{index}")
    return errors


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(0.95 * len(ordered) + 0.999) - 1))
    return ordered[rank]


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("refusing to overwrite an existing octet-plan artifact")
    output.parent.mkdir(parents=True, exist_ok=True)
    runtime = resolve_runtime(manifest_path=args.runtime_manifest)
    manifest_before = file_sha256(args.runtime_manifest)
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    available = {str(item["name"]) for item in capabilities}
    required = {
        str(tail["operation"])
        for tail in (*READ_ONLY_TAILS, *ACTION_TAILS)
    }
    if not required <= available:
        raise RuntimeError(f"authenticated catalogue lacks {sorted(required - available)}")

    limits = PROFILE_LIMITS["gpu"]
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=sidecar_environment(
            runtime,
            gpu_layers=runtime.gpu_layers,
            llm_http_timeout=limits["llm_http"],
        ),
        cwd=REPO,
    )
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar rejected its handshake")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "octet-plan-catalog",
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
                "id": "octet-plan-warm",
                "text": "hola",
                "history": [],
                "uiLanguage": "es",
            },
            limits["turn.decide"],
        )
        for case in build_cases():
            turn_started = time.perf_counter()
            turn = client.request(
                {
                    "type": "turn.decide",
                    "id": f"turn-{case['case_id']}",
                    "text": case["text"],
                    "history": [],
                    "uiLanguage": case["language"],
                },
                limits["turn.decide"],
            )
            turn_seconds = time.perf_counter() - turn_started
            effect_operations = list(turn.get("effectOperations") or [])
            turn_exact = (
                turn.get("type") == "turn.result"
                and turn.get("kind") == "plan"
                and effect_operations == case["expected_operations"]
            )
            plan_started = time.perf_counter()
            plan = client.request(
                {
                    "type": "plan",
                    "id": f"plan-{case['case_id']}",
                    "text": case["text"],
                    "history": [],
                    "expectedOperations": effect_operations,
                },
                PLAN_TIMEOUT_SECONDS,
            ) if turn_exact else {}
            plan_seconds = time.perf_counter() - plan_started
            plan_errors = _validate_plan(case, plan) if turn_exact else [
                "turn_contract_mismatch"
            ]
            rows.append(
                {
                    **case,
                    "turn_seconds": round(turn_seconds, 6),
                    "plan_seconds": round(plan_seconds, 6),
                    "turn_exact": turn_exact,
                    "plan_exact": not plan_errors,
                    "errors": plan_errors,
                    "observed_effect_operations": effect_operations,
                    "observed_plan": plan,
                }
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "octet-plan-shutdown"},
            timeout=limits["shutdown"],
        )

    cases = build_cases()
    position_counts: Counter[tuple[str, int]] = Counter()
    adjacency_counts: Counter[tuple[str, str]] = Counter()
    for case in cases:
        for position, tail_id in enumerate(case["order"]):
            position_counts[(tail_id, position)] += 1
        adjacency_counts.update(zip(case["order"], case["order"][1:]))
    tail_ids = tuple(str(tail["tail_id"]) for tail in (*READ_ONLY_TAILS, *ACTION_TAILS))
    turn_latencies = [float(row["turn_seconds"]) for row in rows]
    plan_latencies = [float(row["plan_seconds"]) for row in rows]
    report = {
        "schema": "baxy.maximum-octet-plan-materialization.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "balanced_turn_decide_to_plan_exact_arguments",
        "authority": "no_core_request_no_provider_no_effect",
        "runtime": public_runtime_identity(runtime),
        "effects_executed": 0,
        "total_seconds": round(time.perf_counter() - started, 3),
        "metrics": {
            "turn_exact": sum(bool(row["turn_exact"]) for row in rows),
            "plan_exact": sum(bool(row["plan_exact"]) for row in rows),
            "total": len(rows),
            "turn_seconds_p50": statistics.median(turn_latencies),
            "turn_seconds_p95": _p95(turn_latencies),
            "plan_seconds_p50": statistics.median(plan_latencies),
            "plan_seconds_p95": _p95(plan_latencies),
        },
        "coverage": {
            "unique_orders": len({tuple(case["order"]) for case in cases}),
            "language_counts": dict(Counter(case["language"] for case in cases)),
            "surface_counts": dict(Counter(case["surface"] for case in cases)),
            "lexical_counts": dict(Counter(case["lexical_profile"] for case in cases)),
            "every_tail_every_position": all(
                position_counts[(tail_id, position)] > 0
                for tail_id in tail_ids
                for position in range(8)
            ),
            "every_ordered_adjacency": all(
                adjacency_counts[(left, right)] > 0
                for left in tail_ids
                for right in tail_ids
                if left != right
            ),
        },
        "acceptance": {
            "all_turns_exact": all(bool(row["turn_exact"]) for row in rows),
            "all_plans_exact": all(bool(row["plan_exact"]) for row in rows),
            "balanced_coverage_complete": True,
            "runtime_manifest_unchanged": (
                manifest_before == file_sha256(args.runtime_manifest)
            ),
            "zero_effects": True,
        },
        "source": {"probe_sha256": _sha256(Path(__file__).resolve())},
        "failures": [row for row in rows if not row["plan_exact"]],
        "rows": rows,
    }
    report["acceptance"]["balanced_coverage_complete"] = all(
        bool(report["coverage"][key])
        for key in ("every_tail_every_position", "every_ordered_adjacency")
    )
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        default=DEFAULT_RUNTIME_MANIFEST,
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = run(args)
    print(json.dumps({
        "metrics": report["metrics"],
        "coverage": report["coverage"],
        "acceptance": report["acceptance"],
        "failures": [
            {
                "case_id": row["case_id"],
                "errors": row["errors"],
                "observed_effect_operations": row["observed_effect_operations"],
                "observed_plan": row["observed_plan"],
            }
            for row in report["failures"]
        ],
        "effects_executed": report["effects_executed"],
    }, ensure_ascii=False, indent=2))
    return 0 if all(report["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
