"""Measure a simple action complete and verified: decide → core → verified.

Safe reads only. Mute/volume are reversible but they fight the owner's
machine, so they stay out of this clock.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.baxy_runtime_config import (  # noqa: E402
    add_runtime_arguments,
    resolve_runtime_from_args,
)
from scripts.measure_mind_budget import (  # noqa: E402
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)

DEFAULT_OUTPUT = REPO / "artifacts/product/simple_complete_latency.json"
SIMPLE_COMPLETE_P50_TARGET = 2.5

REQUESTS: tuple[tuple[str, str, str], ...] = (
    ("read-es-01", "es", "Cuanta bateria le queda al equipo?"),
    ("read-es-02", "es", "Como esta la conexion de red?"),
    ("read-es-03", "es", "Que hora es ahora?"),
    ("read-en-01", "en", "How much free disk space is left?"),
    ("read-en-02", "en", "What is the current CPU load?"),
    ("read-sp-01", "spanglish", "Check el estado del wifi."),
)


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 3)


def _core_call(core: JsonLineProcess, operation: str, timeout: float) -> dict[str, Any]:
    request = {
        "type": "operation.request",
        "requestId": str(uuid.uuid4()),
        "missionId": str(uuid.uuid4()),
        "invocationId": str(uuid.uuid4()),
        "operation": operation,
        "arguments": {},
    }
    core.send(request)
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("core agotó su deadline")
        reply = core.next_message(remaining)
        if reply.get("requestId") == request["requestId"] or reply.get(
            "type"
        ) in {"operation.response", "error"}:
            return reply


def measure(runtime: Any, capabilities: list[dict[str, Any]], core_path: Path) -> dict[str, Any]:
    limits = PROFILE_LIMITS["gpu"]
    mind = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=sidecar_environment(
            runtime,
            gpu_layers=runtime.gpu_layers,
            llm_http_timeout=limits["llm_http"],
        ),
        cwd=REPO,
    )
    core_env = {key: str(value) for key, value in os.environ.items()}
    data_root = Path(core_env.get("LOCALAPPDATA", str(REPO))) / "BAXY" / "simple-complete-measure"
    core_env["BAXY_DATA_DIR"] = str(data_root)
    core = JsonLineProcess(
        [str(core_path)],
        environment=core_env,
        cwd=REPO,
    )
    records: list[dict[str, Any]] = []
    try:
        hello = mind.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar did not greet")
        ready = mind.request(
            {
                "type": "catalog.configure",
                "id": "catalog-simple-complete",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("catalogue rejected")
        core.next_message(limits["handshake"])
        for case_id, language, text in REQUESTS:
            begin = time.perf_counter()
            decision = mind.request(
                {
                    "type": "turn.decide",
                    "id": f"simple-complete-{case_id}",
                    "text": text,
                    "history": [],
                },
                limits["turn.decide"],
            )
            operation = str(decision.get("operation") or "")
            kind = str(decision.get("kind") or "")
            verified = False
            status = ""
            if kind == "action" and operation:
                response = _core_call(core, operation, 8.0)
                verified = bool(response.get("verified"))
                status = str(response.get("status") or "")
            seconds = time.perf_counter() - begin
            records.append(
                {
                    "case_id": case_id,
                    "language": language,
                    "kind": kind,
                    "operation": operation,
                    "verified": verified,
                    "status": status,
                    "complete_seconds": round(seconds, 3),
                }
            )
    finally:
        mind.close(graceful_message=None, timeout=15.0)
        core.close(graceful_message=None, timeout=15.0)

    completed = [
        row["complete_seconds"]
        for row in records
        if row["kind"] == "action" and row["verified"]
    ]
    p50 = _percentile(completed, 0.5)
    return {
        "requests": len(records),
        "verified_actions": len(completed),
        "complete_seconds": {
            "p50": p50,
            "p95": _percentile(completed, 0.95),
            "max": round(max(completed), 3) if completed else 0.0,
            "mean": round(statistics.fmean(completed), 3) if completed else 0.0,
        },
        "target_p50": SIMPLE_COMPLETE_P50_TARGET,
        "meets_p50_target": bool(completed) and p50 <= SIMPLE_COMPLETE_P50_TARGET,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    add_runtime_arguments(parser)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    runtime = resolve_runtime_from_args(args)
    core_path = discover_core(args.core)
    capabilities = current_core_capabilities(core_path)
    result = measure(runtime, capabilities, core_path)
    report = {
        "schema": "baxy.simple-complete-latency.v1",
        "clock": "decide → core execute → verified response",
        "authority": "safe reads only; no mute/volume/destructive ops",
        **result,
    }
    write_json_atomic(args.output, report)
    summary = {k: v for k, v in report.items() if k not in {"records"}}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["meets_p50_target"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
