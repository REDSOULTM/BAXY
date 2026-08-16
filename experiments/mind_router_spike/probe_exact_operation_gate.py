"""Measure exact product operation selection without executing any effect.

The historical BAXY ledgers contain useful language, but many of their labels
only identify a broad family or describe more than one action.  This probe does
not reinterpret those labels.  It consumes an explicit JSONL oracle whose rows
name the complete ordered operation sequence and the acceptable visible turn
kind.

Only ``catalog.configure`` and ``turn.decide`` are sent to the mind sidecar.
No operation request is ever sent to Core, so this gate is side-effect free.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)

DEFAULT_CASES = (
    REPO
    / "experiments"
    / "mind_router_spike"
    / "data"
    / "exact_operation_development.v1.jsonl"
)
DEFAULT_OUTPUT = (
    REPO / "artifacts" / "fixes" / "exact_operation_development_gate.json"
)
VALID_KINDS = frozenset({"action", "clarify", "conversation", "plan"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percentile(values: Iterable[float], probability: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    index = round((len(ordered) - 1) * probability)
    return round(ordered[index], 6)


def load_cases(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    case_ids: set[str] = set()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        case_id = row.get("case_id")
        text = row.get("text")
        operations = row.get("expected_operations")
        effect_operations = row.get("expected_effect_operations", operations)
        kinds = row.get("expected_kinds")
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            raise ValueError(f"invalid or duplicate case_id at line {line_number}")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"invalid text for {case_id}")
        if not isinstance(operations, list) or any(
            not isinstance(item, str) or not item for item in operations
        ):
            raise ValueError(f"invalid expected_operations for {case_id}")
        if not isinstance(effect_operations, list) or any(
            not isinstance(item, str) or not item for item in effect_operations
        ):
            raise ValueError(f"invalid expected_effect_operations for {case_id}")
        if (
            not isinstance(kinds, list)
            or not kinds
            or any(kind not in VALID_KINDS for kind in kinds)
        ):
            raise ValueError(f"invalid expected_kinds for {case_id}")
        case_ids.add(case_id)
        rows.append(
            {
                **row,
                "text": text.strip(),
                "expected_operations": list(operations),
                "expected_effect_operations": list(effect_operations),
                "expected_kinds": list(kinds),
            }
        )
    if not rows:
        raise ValueError("the exact-operation oracle is empty")
    return rows


def assess_reply(case: dict[str, Any], reply: dict[str, Any]) -> dict[str, Any]:
    observed_intent = list(reply.get("intentOperations") or [])
    observed_effect = list(reply.get("effectOperations") or [])
    expected_intent = list(case["expected_operations"])
    expected_effect = list(case["expected_effect_operations"])
    kind = reply.get("kind")
    reply_contract_ok = reply.get("type") == "turn.result" and kind in VALID_KINDS
    intent_exact = observed_intent == expected_intent
    effect_exact = observed_effect == expected_effect
    kind_ok = kind in case["expected_kinds"]
    exact = reply_contract_ok and intent_exact and effect_exact and kind_ok
    return {
        "exact": exact,
        "reply_contract_ok": reply_contract_ok,
        "intent_exact": intent_exact,
        "effect_exact": effect_exact,
        "kind_ok": kind_ok,
        "observed_kind": kind,
        "observed_intent_operations": observed_intent,
        "observed_effect_operations": observed_effect,
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    exact = sum(bool(row["assessment"]["exact"]) for row in rows)
    intent = sum(bool(row["assessment"]["intent_exact"]) for row in rows)
    effect = sum(bool(row["assessment"]["effect_exact"]) for row in rows)
    kind = sum(bool(row["assessment"]["kind_ok"]) for row in rows)
    latencies = [float(row["seconds"]) for row in rows]
    return {
        "cases": total,
        "exact": exact,
        "exact_accuracy": round(exact / total, 6) if total else None,
        "intent_exact": intent,
        "intent_exact_accuracy": round(intent / total, 6) if total else None,
        "effect_exact": effect,
        "effect_exact_accuracy": round(effect / total, 6) if total else None,
        "kind_ok": kind,
        "kind_accuracy": round(kind / total, 6) if total else None,
        "latency_seconds": {
            "mean": round(statistics.fmean(latencies), 6) if latencies else None,
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "maximum": round(max(latencies), 6) if latencies else None,
        },
    }


def run(
    *,
    cases_path: Path,
    output_path: Path,
    repeats: int,
    limit: int | None,
) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("repeats must be at least one")
    cases = load_cases(cases_path.resolve(strict=True))
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be positive")
        cases = cases[:limit]

    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    catalog_names = {str(capability.get("name") or "") for capability in capabilities}
    referenced = {
        operation
        for case in cases
        for field in ("expected_operations", "expected_effect_operations")
        for operation in case[field]
    }
    missing = sorted(referenced - catalog_names)
    if missing:
        raise ValueError(f"oracle references absent catalog operations: {missing}")

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
    measured: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("mind sidecar did not publish hello")
        configured = client.request(
            {
                "type": "catalog.configure",
                "id": "exact-operation-catalog",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if configured.get("type") != "catalog.ready" or configured.get(
            "count"
        ) != len(capabilities):
            raise RuntimeError("mind sidecar rejected the authenticated catalog")
        client.request(
            {
                "type": "turn.decide",
                "id": "exact-operation-warmup",
                "text": "hola, responde brevemente",
                "history": [],
            },
            limits["turn.decide"],
        )

        for repeat in range(repeats):
            for case in cases:
                started = time.perf_counter()
                reply = client.request(
                    {
                        "type": "turn.decide",
                        "id": f"exact-{repeat}-{case['case_id']}",
                        "text": case["text"],
                        "history": [],
                    },
                    limits["turn.decide"],
                )
                elapsed = time.perf_counter() - started
                measured.append(
                    {
                        "case_id": case["case_id"],
                        "language": case.get("language", "unknown"),
                        "category": case.get("category", "uncategorized"),
                        "repeat": repeat,
                        "seconds": round(elapsed, 6),
                        "expected_operations": case["expected_operations"],
                        "expected_effect_operations": case[
                            "expected_effect_operations"
                        ],
                        "expected_kinds": case["expected_kinds"],
                        "assessment": assess_reply(case, reply),
                    }
                )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "exact-operation-shutdown"},
            timeout=limits["shutdown"],
        )

    by_language: dict[str, Any] = {}
    for language in sorted({row["language"] for row in measured}):
        by_language[language] = _summarize(
            [row for row in measured if row["language"] == language]
        )
    by_category: dict[str, Any] = {}
    for category in sorted({row["category"] for row in measured}):
        by_category[category] = _summarize(
            [row for row in measured if row["category"] == category]
        )

    summary = _summarize(measured)
    report = {
        "schema": "baxy.exact-operation-development-gate.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_not_final_certification",
        "side_effect_free": True,
        "source": {
            "path": str(cases_path.resolve()),
            "sha256": _sha256(cases_path.resolve()),
            "population_cases": len(load_cases(cases_path.resolve())),
            "measured_cases": len(cases),
            "repeats": repeats,
        },
        "runtime": public_runtime_identity(runtime),
        "catalog": {
            "count": len(capabilities),
            "names_sha256": hashlib.sha256(
                "\n".join(sorted(catalog_names)).encode("utf-8")
            ).hexdigest(),
        },
        "summary": summary,
        "by_language": by_language,
        "by_category": by_category,
        "failures": [row for row in measured if not row["assessment"]["exact"]],
        "samples": measured,
        "status": "passed" if summary["exact_accuracy"] == 1.0 else "failed",
    }
    write_json_atomic(output_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    report = run(
        cases_path=args.cases,
        output_path=args.output,
        repeats=args.repeats,
        limit=args.limit,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                **report["summary"],
                "failures": len(report["failures"]),
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
