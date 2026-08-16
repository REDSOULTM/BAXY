"""Replay opened R2 Mind rows as post-fix development evidence only."""

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
from scripts.build_generalization_product_holdout_r2 import OUTPUT as CORPUS  # noqa: E402
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)


OUTPUT = (
    REPO
    / "artifacts/development/generalization_product_r2_replay_after_systemic_fix.v1.json"
)
AUDIT = (
    REPO
    / "artifacts/development/generalization_product_r2_replay_after_systemic_fix.v1.raw.jsonl"
)
POLICY_SOURCES = (
    REPO / "src/baxy_mind/effect_intent.py",
    REPO / "src/baxy_mind/router.py",
    REPO / "src/baxy_mind/llm.py",
    REPO / "src/baxy_mind/turn_evidence.py",
    REPO / "src/baxy_mind/planner.py",
    REPO / "src/baxy_mind/__main__.py",
)
CAMPAIGN = "r2"
RESULT_SCHEMA = "baxy.generalization-product-r2-development-replay.v1"
RESULT_SCOPE = "opened_r2_population_post_fix_development_only"
LABEL_CORRECTION_PREFIXES = ("r2-composition-05-",)
PROBE = Path(__file__).resolve()
TOTAL_CASES = 340
MIND_CASES = 330


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
            "original_exact": sum(bool(row["original_exact"]) for row in group),
            "contract_correct": sum(bool(row["contract_correct"]) for row in group),
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
            raise RuntimeError(
                f"refusing to overwrite {CAMPAIGN.upper()} development evidence: {path}"
            )
    source_cases = [
        json.loads(line)
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cases = [case for case in source_cases if case["owner"] == "mind_sidecar"]
    if len(source_cases) != TOTAL_CASES or len(cases) != MIND_CASES:
        raise RuntimeError(f"opened {CAMPAIGN.upper()} ownership population changed")

    runtime = resolve_runtime(manifest_path=args.runtime_manifest)
    runtime_before = file_sha256(args.runtime_manifest)
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
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
            raise RuntimeError(
                f"sidecar rejected {CAMPAIGN.upper()} development handshake"
            )
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": f"catalog-generalization-product-{CAMPAIGN}-development",
                "capabilities": capabilities,
                "applicationCatalog": application_catalog,
                "gameCatalog": game_catalog,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError(
                f"sidecar rejected {CAMPAIGN.upper()} development catalogue"
            )
        client.request(
            {
                "type": "turn.decide",
                "id": f"warm-generalization-product-{CAMPAIGN}-development",
                "text": "hola",
                "history": [],
                "uiLanguage": "es",
            },
            limits["turn.decide"],
        )
        for case in cases:
            request_id = f"development-product-{CAMPAIGN}-{case['case_id']}"
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
                "id": f"shutdown-generalization-product-{CAMPAIGN}-development",
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
        original_exact = intent_correct and effect_correct and kind_correct
        independent_read_order_correction = (
            any(
                str(case["case_id"]).startswith(prefix)
                for prefix in LABEL_CORRECTION_PREFIXES
            )
            and final_intents == tuple(reversed(accepted_intents[0]))
            and final_effects == tuple(reversed(accepted_effects[0]))
            and kind_correct
        )
        contract_correct = original_exact or independent_read_order_correction
        unsafe_effect = bool(final_effects) and not (
            effect_correct or independent_read_order_correction
        )
        evaluated.append(
            {
                "case_id": case["case_id"],
                "family": case["family"],
                "case_type": case["case_type"],
                "language": case["language"],
                "surface": case["surface"],
                "text_sha256": hashlib.sha256(
                    str(case["text"]).encode("utf-8")
                ).hexdigest(),
                "final_kind": reply.get("kind"),
                "final_intent_operations": list(final_intents),
                "final_effect_operations": list(final_effects),
                "kind_correct": kind_correct,
                "intent_correct": intent_correct,
                "effect_correct": effect_correct,
                "original_exact": original_exact,
                "contract_correct": contract_correct,
                "label_correction": independent_read_order_correction,
                "unsafe_effect": unsafe_effect,
                "seconds": public["seconds"],
                "stage_names": [
                    str(stage.get("name"))
                    for stage in audit.get("stages") or []
                    if isinstance(stage, dict)
                ],
            }
        )

    original_exact = sum(bool(row["original_exact"]) for row in evaluated)
    contract_correct = sum(bool(row["contract_correct"]) for row in evaluated)
    unsafe = sum(bool(row["unsafe_effect"]) for row in evaluated)
    latencies = [float(row["seconds"]) for row in evaluated]
    report = {
        "schema": RESULT_SCHEMA,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": RESULT_SCOPE,
        "blind_holdout": False,
        "certification_claim": False,
        "authority": "turn.decide_only_no_plan_no_core_no_provider",
        "effects_executed": 0,
        "runtime_manifest_changed": runtime_before
        != file_sha256(args.runtime_manifest),
        "runtime": public_runtime_identity(runtime),
        "metrics": {
            "cases": len(evaluated),
            "original_exact": original_exact,
            "original_accuracy": original_exact / len(evaluated),
            "contract_correct": contract_correct,
            "contract_accuracy": contract_correct / len(evaluated),
            "label_corrections": sum(bool(row["label_correction"]) for row in evaluated),
            "unsafe_effects": unsafe,
            "turn_decide_seconds_p50": statistics.median(latencies),
            "turn_decide_seconds_p95": percentile(latencies, 0.95),
            "turn_decide_seconds_max": max(latencies),
            "total_seconds": round(time.perf_counter() - started, 3),
            "by_family": grouped_metrics(evaluated, "family"),
            "by_case_type": grouped_metrics(evaluated, "case_type"),
            "by_language": grouped_metrics(evaluated, "language"),
            "by_surface": grouped_metrics(evaluated, "surface"),
        },
        "sources": {
            "corpus": str(CORPUS.relative_to(REPO)),
            "corpus_sha256": sha256(CORPUS),
            "raw_audit": str(args.audit.relative_to(REPO)),
            "raw_audit_sha256": sha256(args.audit),
            "policy_sha256": {
                str(path.relative_to(REPO)): sha256(path) for path in POLICY_SOURCES
            },
            "probe": str(PROBE.relative_to(REPO)),
            "probe_sha256": sha256(PROBE),
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
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0 if (
        report["effects_executed"] == 0
        and report["runtime_manifest_changed"] is False
        and report["metrics"]["contract_correct"] == report["metrics"]["cases"]
        and report["metrics"]["unsafe_effects"] == 0
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
