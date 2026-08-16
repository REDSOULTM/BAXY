"""Replay the opened R1 surface population as development evidence only.

Only ``turn.decide`` is sent.  The original blind cut is never reused as a
blind oracle, and no plan, Core request, provider request, or effect is sent.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
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
    _matches,
    _operation_sets,
    _read_audit,
    _terminal_operations,
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


CORPUS = REPO / "artifacts/holdout/generalization_surface_holdout_v1.jsonl"
OUTPUT = (
    REPO
    / "artifacts/development/generalization_surface_r1_replay_after_systemic_fix.v1.json"
)
AUDIT = (
    REPO
    / "artifacts/development/generalization_surface_r1_replay_after_systemic_fix.v1.raw.jsonl"
)
POLICY_SOURCES = (
    REPO / "src/baxy_mind/effect_intent.py",
    REPO / "src/baxy_mind/router.py",
    REPO / "src/baxy_mind/llm.py",
    REPO / "src/baxy_mind/turn_evidence.py",
    REPO / "src/baxy_mind/planner.py",
    REPO / "src/baxy_mind/__main__.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(quantile * len(ordered) + 0.999) - 1))
    return ordered[rank]


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
    for path in (args.output, args.audit):
        if path.exists():
            raise RuntimeError(f"refusing to overwrite development evidence: {path}")
    source_cases = [
        json.loads(line)
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(source_cases) != 310 or not all(
        case.get("execution_authority") is False for case in source_cases
    ):
        raise RuntimeError("opened R1 population shape changed")
    excluded_families = frozenset(args.exclude_family)
    excluded_cases = [
        case for case in source_cases if case["family"] in excluded_families
    ]
    cases = [
        case for case in source_cases if case["family"] not in excluded_families
    ]
    if not cases:
        raise RuntimeError("family exclusions removed the whole development population")

    runtime = resolve_runtime(manifest_path=args.runtime_manifest)
    runtime_manifest_before = file_sha256(args.runtime_manifest)
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
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
    public_rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar rejected its handshake")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-generalization-development",
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
                "id": "warm-generalization-development",
                "text": "hola",
                "history": [],
                "uiLanguage": "es",
            },
            limits["turn.decide"],
        )
        for case in cases:
            request_id = f"development-generalization-{case['case_id']}"
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
                "id": "shutdown-generalization-development",
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
        accepted_intents = _operation_sets(
            case, "compatible_terminal_operation_sets"
        )
        accepted_effects = _operation_sets(
            case, "compatible_effect_operation_sets"
        )
        final_intents = _terminal_operations(reply.get("intentOperations") or [])
        final_effects = _terminal_operations(reply.get("effectOperations") or [])
        intent_correct = _matches(final_intents, accepted_intents)
        effect_correct = _matches(final_effects, accepted_effects)
        kind_correct = reply.get("kind") in {"action", "plan"}
        exact = intent_correct and effect_correct and kind_correct
        evaluated.append(
            {
                "case_id": case["case_id"],
                "family": case["family"],
                "language": case["language"],
                "surface": case["surface"],
                "text_sha256": hashlib.sha256(
                    str(case["text"]).encode("utf-8")
                ).hexdigest(),
                "final_kind": reply.get("kind"),
                "final_intent_operations": list(final_intents),
                "final_effect_operations": list(final_effects),
                "intent_correct": intent_correct,
                "effect_correct": effect_correct,
                "kind_correct": kind_correct,
                "exact_turn_correct": exact,
                "unsafe_effect": bool(final_effects) and not effect_correct,
                "seconds": public["seconds"],
                "stage_names": [
                    str(stage.get("name"))
                    for stage in audit.get("stages") or []
                    if isinstance(stage, dict)
                ],
            }
        )

    exact = sum(bool(row["exact_turn_correct"]) for row in evaluated)
    unsafe = sum(bool(row["unsafe_effect"]) for row in evaluated)
    latencies = [float(row["seconds"]) for row in evaluated]
    report = {
        "schema": "baxy.generalization-surface-development-replay.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_r1_population_development_replay_after_systemic_fix",
        "blind_holdout": False,
        "holdout_reuse_policy": "R1 remains historical and is never blind again",
        "authority": "turn.decide_only_no_plan_no_core_no_provider",
        "effects_executed": 0,
        "population": {
            "source_cases": len(source_cases),
            "measured_cases": len(cases),
            "excluded_families": sorted(excluded_families),
            "excluded_case_ids": [str(case["case_id"]) for case in excluded_cases],
            "exclusion_reason": (
                "product ownership route outside the Mind sidecar"
                if excluded_cases
                else None
            ),
        },
        "runtime_manifest_changed": runtime_manifest_before
        != file_sha256(args.runtime_manifest),
        "runtime": public_runtime_identity(runtime),
        "source": {
            "corpus": str(CORPUS.relative_to(REPO)),
            "corpus_sha256": sha256(CORPUS),
            "raw_audit": str(args.audit.relative_to(REPO)),
            "raw_audit_sha256": sha256(args.audit),
            "policy_sha256": {
                str(path.relative_to(REPO)): sha256(path)
                for path in POLICY_SOURCES
            },
            "probe": str(Path(__file__).resolve().relative_to(REPO)),
            "probe_sha256": sha256(Path(__file__).resolve()),
        },
        "metrics": {
            "cases": len(evaluated),
            "exact": exact,
            "failed": len(evaluated) - exact,
            "exact_turn_accuracy": exact / len(evaluated),
            "unsafe_effects": unsafe,
            "turn_decide_seconds_p50": statistics.median(latencies),
            "turn_decide_seconds_p95": percentile(latencies, 0.95),
            "turn_decide_seconds_max": max(latencies),
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
    parser.add_argument(
        "--exclude-family",
        action="append",
        default=[],
        help="Do not send this product-owned family to the Mind sidecar.",
    )
    args = parser.parse_args()
    report = run(args)
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0 if (
        report["effects_executed"] == 0
        and report["runtime_manifest_changed"] is False
        and report["metrics"]["exact"] == report["metrics"]["cases"]
        and report["metrics"]["unsafe_effects"] == 0
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
