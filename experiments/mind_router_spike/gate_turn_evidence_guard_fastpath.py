"""Physically gate the proposed E5+G conversation fast path.

The candidate would skip the primary policy only when one-sided turn evidence
is valid and the independent semantic guard returns ``no_effect``.  A single
guard false negative on a canonical effect request is sufficient to reject
that rule because the fast path would otherwise convert the request into
conversation before P can preserve or remove authority.

This harness starts only the canonical local model runtime.  It never starts
Core, never dispatches an operation and never changes registered assets.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from baxy_mind.llm import LlmRuntime  # noqa: E402
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    PROFILE_LIMITS,
    sidecar_environment,
    write_json_atomic,
)


DEFAULT_AUDIT = (
    REPO
    / "artifacts"
    / "fixes"
    / "turn_evidence_fastpath_full_audit_20260730.json"
)
DEFAULT_ORACLE = (
    REPO
    / "artifacts"
    / "historical_exhaustive"
    / "runtime_oracle.jsonl"
)
DEFAULT_OUTPUT = (
    REPO
    / "artifacts"
    / "fixes"
    / "turn_evidence_guard_fastpath_gate_20260730.json"
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path} contiene una fila que no es objeto")
            rows.append(value)
    return rows


def _measure_guard(
    runtime: LlmRuntime,
    text: str,
    *,
    timeout: float,
) -> tuple[str, str | None, float]:
    runtime.begin_request(timeout)
    started = time.perf_counter()
    try:
        state, count = runtime._verify_semantic_effect_shape(text)  # noqa: SLF001
    finally:
        runtime.end_request()
    return state, count, time.perf_counter() - started


def run(args: argparse.Namespace) -> dict[str, Any]:
    audit_path = args.audit.resolve(strict=True)
    oracle_path = args.oracle.resolve(strict=True)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if (
        not isinstance(audit, dict)
        or audit.get("schema") != "baxy.turn-evidence-fastpath-audit.v1"
        or audit.get("scope") != "full"
        or audit.get("candidate_gate", {}).get("full_scope") is not True
    ):
        raise ValueError("el audit E5 full no es válido")

    queried = {
        str(case_id)
        for case_id in audit.get("signals", {}).get("queried_case_ids", [])
    }
    oracle = {
        str(row["case_id"]): row
        for row in _read_jsonl(oracle_path)
        if str(row.get("case_id")) in queried
    }
    selected = sorted(
        (
            row
            for row in oracle.values()
            if str(row.get("expected_effect")) in args.expected_effect
        ),
        key=lambda row: str(row["case_id"]),
    )
    if not selected:
        raise ValueError("el filtro no seleccionó señales canónicas")

    resolved = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    limits = PROFILE_LIMITS["gpu"]
    os.environ.update(
        sidecar_environment(
            resolved,
            gpu_layers=resolved.gpu_layers,
            llm_http_timeout=limits["llm_http"],
        )
    )
    model = LlmRuntime()
    observations: list[dict[str, Any]] = []
    false_negative_replays: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        model.start_warmup()
        if not model.wait_warmup(limits["handshake"]):
            raise TimeoutError("el modelo canónico no terminó su warmup")
        for row in selected:
            state, count, elapsed = _measure_guard(
                model,
                str(row["text_literal"]),
                timeout=limits["turn.decide"],
            )
            observation = {
                "case_id": str(row["case_id"]),
                "text_sha256": str(row["text_sha256"]),
                "expected_effect": str(row["expected_effect"]),
                "guard_state": state,
                "guard_effect_count": count,
                "elapsed_seconds": round(elapsed, 4),
            }
            observations.append(observation)
            print(
                f"{observation['case_id']}: {elapsed:.4f}s "
                f"{state}/{count}",
                flush=True,
            )
            if state != "no_effect":
                continue
            for replay in range(args.replay_false_negative):
                replay_state, replay_count, replay_elapsed = _measure_guard(
                    model,
                    str(row["text_literal"]),
                    timeout=limits["turn.decide"],
                )
                false_negative_replays.append(
                    {
                        "case_id": str(row["case_id"]),
                        "replay": replay + 1,
                        "guard_state": replay_state,
                        "guard_effect_count": replay_count,
                        "elapsed_seconds": round(replay_elapsed, 4),
                    }
                )
            if args.stop_on_false_negative:
                break
    finally:
        model.close()

    false_negatives = [
        row for row in observations if row["guard_state"] == "no_effect"
    ]
    latencies = [float(row["elapsed_seconds"]) for row in observations]
    replay_states = [
        str(row["guard_state"]) for row in false_negative_replays
    ]
    reproducible_false_negative = bool(false_negatives) and all(
        state == "no_effect" for state in replay_states
    )
    return {
        "schema": "baxy.turn-evidence-guard-fastpath-gate.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effect_free": True,
        "core_started": False,
        "external_effects_executed": False,
        "runtime": public_runtime_identity(resolved),
        "inputs": {
            "audit": str(audit_path),
            "oracle": str(oracle_path),
            "expected_effect": sorted(args.expected_effect),
            "selected_cases": len(selected),
        },
        "requests_completed": len(observations) + len(false_negative_replays),
        "elapsed_total_seconds": round(time.perf_counter() - started, 4),
        "latency_seconds": {
            "count": len(latencies),
            "p50": round(statistics.median(latencies), 4),
            "max": round(max(latencies), 4),
        },
        "observations": observations,
        "false_negative_replays": false_negative_replays,
        "gate": {
            "false_no_effect_cases": len(false_negatives),
            "reproducible_false_negative": reproducible_false_negative,
            "passed": not false_negatives,
            "candidate_status": (
                "rejected"
                if false_negatives
                else "requires_remaining_signal_gate"
            ),
            "reason": (
                "G returned no_effect for a canonical effect signal"
                if false_negatives
                else "no false negative observed in this selected slice"
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--oracle", type=Path, default=DEFAULT_ORACLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--expected-effect",
        action="append",
        choices=("none", "operation", "review_required", "unsupported"),
        default=None,
    )
    parser.add_argument(
        "--replay-false-negative",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--stop-on-false-negative",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.replay_false_negative <= 5:
        raise SystemExit("--replay-false-negative debe estar entre 1 y 5")
    args.expected_effect = frozenset(
        args.expected_effect or ("operation",)
    )
    report = run(args)
    write_json_atomic(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "requests_completed": report["requests_completed"],
                "gate": report["gate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
