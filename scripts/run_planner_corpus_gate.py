"""Run every natural historical compound case through the no-effect planner.

The gate sends only ``plan`` requests to the sidecar. It never grounds a later
step, calls the core operation endpoint, or confirms an effect.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.baxy_runtime_config import (  # noqa: E402
    add_runtime_arguments,
    public_runtime_identity,
    resolve_runtime_from_args,
)
from scripts.build_layout import load_build_layout  # noqa: E402

AUDIT = REPO / "artifacts/planner_recovery/historical_compound_audit.json"
OUTPUT = REPO / "artifacts/planner_recovery/historical_planner_gate.json"
BUILD_LAYOUT = load_build_layout(REPO)
CORE = BUILD_LAYOUT.core_executable(REPO)


def core_capabilities(environment: dict[str, str], core_path: Path) -> list[dict]:
    process = subprocess.Popen(
        [str(core_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    try:
        hello = json.loads(process.stdout.readline())
        return [
            {key: item[key] for key in ("name", "description", "argumentsSchema", "risk")}
            for item in hello["capabilities"]
        ]
    finally:
        process.stdin.close()
        process.wait(timeout=20)


def main() -> None:
    global AUDIT, OUTPUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=AUDIT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--core", type=Path, default=CORE)
    add_runtime_arguments(parser)
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Ignore an existing checkpoint and evaluate every case again.",
    )
    parser.add_argument(
        "--retry-rejections",
        action="store_true",
        help="Keep successful cases and reevaluate non-plan.result checkpoints.",
    )
    args = parser.parse_args()
    AUDIT = args.audit.resolve()
    OUTPUT = args.output.resolve()
    runtime = resolve_runtime_from_args(args)
    runtime_identity = public_runtime_identity(runtime)
    core_path = args.core.resolve(strict=True)
    if not core_path.is_file():
        raise FileNotFoundError("baxy-core no es un archivo")
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    cases = [
        item for item in audit["missions"]
        if item["classification"] == "natural_evaluable"
    ]
    if len(cases) != audit["summary"]["classification_counts"]["natural_evaluable"]:
        raise RuntimeError("historical audit count changed")
    results: list[dict] = []
    if OUTPUT.is_file() and not args.restart:
        previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if previous.get("runtime") != runtime_identity:
            raise RuntimeError(
                "el checkpoint no acredita este runtime; usa --restart"
            )
        if previous.get("schema_version") == 1 and (
            not previous.get("complete", False) or args.retry_rejections
        ):
            results = list(previous.get("cases") or [])
            if args.retry_rejections:
                results = [
                    item for item in results
                    if item.get("response_type") == "plan.result"
                ]
    completed_ids = {item.get("mission_id") for item in results}
    remaining = [item for item in cases if item["mission_id"] not in completed_ids]
    if not remaining:
        print(f"planner corpus already has {len(results)}/{len(cases)} checkpoints")
        return

    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONPATH": str(runtime.python_path),
            "HF_HUB_OFFLINE": "1",
            "BAXY_MIND_LLM_GGUF": str(runtime.gguf),
            "BAXY_MIND_LLAMA_SERVER": str(runtime.llama_server),
            "BAXY_MIND_NGL": str(runtime.gpu_layers),
            "BAXY_DATA_DIR": str(
                Path(environment["LOCALAPPDATA"])
                / "BAXY"
                / ("planner-corpus-" + uuid.uuid4().hex)
            ),
        }
    )
    environment.update(runtime.adapter_environment())
    capabilities = core_capabilities(environment, core_path)
    process = subprocess.Popen(
        [str(runtime.python), "-X", "utf8", "-m", "baxy_mind"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
        cwd=REPO,
        env=environment,
    )

    def receive() -> dict:
        line = process.stdout.readline()
        if not line:
            raise RuntimeError("planner sidecar closed: " + process.stderr.read())
        return json.loads(line)

    def call(message: dict) -> dict:
        process.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
        process.stdin.flush()
        return receive()

    started = time.perf_counter()
    hello = receive()
    if hello.get("type") != "hello" or hello.get("protocol") != "baxy.mind.v1":
        raise RuntimeError("el sidecar no emitió un saludo válido")
    ready = call(
        {"type": "catalog.configure", "id": "catalog", "capabilities": capabilities}
    )
    if ready.get("type") != "catalog.ready":
        raise RuntimeError(f"catalog rejected: {ready}")

    try:
        for offset, case in enumerate(remaining, 1):
            objective = case["representative_objective"]
            before = time.perf_counter()
            reply = call(
                {
                    "type": "plan",
                    "id": case["mission_id"],
                    "text": objective,
                    "history": [],
                }
            )
            result = {
                "mission_id": case["mission_id"],
                "objective": objective,
                "historical_operations": case["historical_operations"],
                "seconds": round(time.perf_counter() - before, 3),
                "response_type": reply.get("type"),
            }
            if reply.get("type") == "plan.result":
                result["kind"] = reply.get("kind")
                result["operations"] = [
                    step.get("operation") for step in reply.get("steps", [])
                ]
            else:
                result["error_code"] = reply.get("code")
                result["error"] = reply.get("message") or reply.get("code")
            results.append(result)
            write_report(
                results,
                len(capabilities),
                started,
                runtime.gguf.name,
                runtime_identity,
                complete=False,
                stderr="",
            )
            index = len(results)
            if index % 10 == 0 or offset == len(remaining):
                print(f"planner corpus {index}/{len(cases)}", flush=True)
    finally:
        try:
            call({"type": "shutdown", "id": "shutdown"})
        finally:
            process.stdin.close()
            process.wait(timeout=20)

    report = write_report(
        results,
        len(capabilities),
        started,
        runtime.gguf.name,
        runtime_identity,
        complete=True,
        stderr=process.stderr.read(),
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"-> {OUTPUT}")


def write_report(
    results: list[dict],
    catalog_count: int,
    started: float,
    model_name: str,
    runtime_identity: dict,
    *,
    complete: bool,
    stderr: str,
) -> dict:
    kinds = Counter(item.get("kind", "error") for item in results)
    rejected = [item for item in results if item["response_type"] != "plan.result"]
    safe_rejections = [
        item for item in rejected
        if item.get("error_code") in (None, "request_failed")
    ]
    errors = [item for item in rejected if item not in safe_rejections]
    forbidden = [
        item for item in results
        if any(str(operation).startswith("memory.") for operation in item.get("operations", []))
    ]
    report = {
        "schema_version": 1,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "complete": complete,
        "scope": "all_natural_historical_cases_planner_only_no_tool_execution",
        "source_audit": str(AUDIT.relative_to(REPO)).replace("\\", "/"),
        "model": model_name,
        "runtime": runtime_identity,
        "core_catalog_count": catalog_count,
        "startup_and_total_seconds": round(time.perf_counter() - started, 3),
        "cases": results,
        "summary": {
            "evaluated": len(results),
            "kind_counts": dict(kinds),
            "safe_rejections": len(safe_rejections),
            "request_errors": len(errors),
            "private_operations_accepted": len(forbidden),
            "tools_executed": 0,
            "status": (
                "passed" if complete and not errors and not forbidden
                else "failed" if complete else "in_progress"
            ),
        },
        "stderr": stderr,
    }
    temporary = OUTPUT.with_name(f".{OUTPUT.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        for attempt in range(7):
            try:
                os.replace(temporary, OUTPUT)
                break
            except PermissionError:
                if attempt == 6:
                    raise
                # Indexers and virus scanners can briefly retain the previous
                # checkpoint on Windows. Keep the update atomic and bounded.
                time.sleep(0.05 * (2**attempt))
    finally:
        temporary.unlink(missing_ok=True)
    return report


if __name__ == "__main__":
    main()
