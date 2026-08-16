"""Fuzz the installed JSONL protocol and verify recovery after every input."""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any


def read_line(pipe: Any, timeout: float = 10.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("protocol response timed out") from exception
    if not line:
        raise RuntimeError("core closed before protocol response")
    return line


def invalid_line(index: int) -> tuple[str, str]:
    request_id = str(uuid.UUID(int=index + 1))
    mission_id = str(uuid.UUID(int=index + 100_001))
    invocation_id = str(uuid.UUID(int=index + 200_001))
    variants: tuple[tuple[str, Any], ...] = (
        ("blank", ""),
        ("truncated", '{"type":"operation.request"'),
        ("null", "null"),
        ("array", "[]"),
        ("number", "42"),
        ("string", '"operation.request"'),
        ("empty_object", {}),
        ("unknown_type", {"type": f"audit.unknown.{index}"}),
        ("numeric_type", {"type": index}),
        ("missing_fields", {"type": "operation.request"}),
        (
            "arguments_not_object",
            {
                "type": "operation.request",
                "requestId": request_id,
                "missionId": mission_id,
                "invocationId": invocation_id,
                "operation": "system.time",
                "arguments": ["invalid"],
            },
        ),
        (
            "unknown_operation",
            {
                "type": "operation.request",
                "requestId": request_id,
                "missionId": mission_id,
                "invocationId": invocation_id,
                "operation": f"audit.operation.{index}",
                "arguments": {},
            },
        ),
        (
            "large_unknown_type",
            {"type": "audit.large", "payload": "x" * 60_000},
        ),
        (
            "wrong_identity_types",
            {
                "type": "operation.request",
                "requestId": index,
                "missionId": False,
                "invocationId": [],
                "operation": "system.time",
                "arguments": {},
            },
        ),
    )
    name, value = variants[index % len(variants)]
    if isinstance(value, str):
        return name, value
    return name, json.dumps(value, separators=(",", ":"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=int, default=500)
    args = parser.parse_args()
    if args.cases < 1:
        raise SystemExit("--cases must be positive")

    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-protocol-fuzz-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
    process = subprocess.Popen(
        [str(core)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env={**os.environ, "BAXY_DATA_DIR": str(data_root)},
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    hello = json.loads(read_line(process.stdout))
    problems: list[dict[str, Any]] = []
    invalid_types: Counter[str] = Counter()
    invalid_errors: Counter[str] = Counter()
    started = time.perf_counter()

    for index in range(args.cases):
        variant, line = invalid_line(index)
        try:
            process.stdin.write(line + "\n")
            process.stdin.flush()
            invalid_response = json.loads(read_line(process.stdout))
            response_type = str(invalid_response.get("type"))
            invalid_types[response_type] += 1
            invalid_errors[
                str(
                    invalid_response.get("errorCode")
                    or invalid_response.get("code")
                    or "none"
                )
            ] += 1
            if response_type not in {"protocol.error", "operation.response"}:
                problems.append(
                    {
                        "case": index + 1,
                        "variant": variant,
                        "problem": f"invalid_response_type:{response_type}",
                    }
                )
            if (
                response_type == "operation.response"
                and invalid_response.get("status") == "completed"
            ):
                problems.append(
                    {
                        "case": index + 1,
                        "variant": variant,
                        "problem": "invalid_request_completed",
                    }
                )

            request_id = str(uuid.uuid4())
            mission_id = str(uuid.uuid4())
            invocation_id = str(uuid.uuid4())
            valid = {
                "type": "operation.request",
                "requestId": request_id,
                "missionId": mission_id,
                "invocationId": invocation_id,
                "operation": "system.time",
                "arguments": {},
            }
            process.stdin.write(json.dumps(valid, separators=(",", ":")) + "\n")
            process.stdin.flush()
            recovered = json.loads(read_line(process.stdout))
            expected = {
                "type": "operation.response",
                "requestId": request_id,
                "missionId": mission_id,
                "invocationId": invocation_id,
                "status": "completed",
                "verified": True,
            }
            mismatched = [
                field
                for field, expected_value in expected.items()
                if recovered.get(field) != expected_value
            ]
            if mismatched:
                problems.append(
                    {
                        "case": index + 1,
                        "variant": variant,
                        "problem": "recovery_mismatch",
                        "fields": mismatched,
                    }
                )
        except Exception as exception:
            problems.append(
                {
                    "case": index + 1,
                    "variant": variant,
                    "problem": f"{type(exception).__name__}:{exception}",
                }
            )
            break

    elapsed = time.perf_counter() - started
    process.stdin.close()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)
    stderr = process.stderr.read()
    shutil.rmtree(data_root, ignore_errors=True)
    report = {
        "schema": "baxy.audit.protocol-fuzz-recovery-stress.v1",
        "core": str(core),
        "coreVersion": hello.get("coreVersion"),
        "catalogCount": len(hello.get("capabilities") or []),
        "cases": args.cases,
        "completedCases": (
            args.cases
            if not problems
            else max(int(item["case"]) for item in problems)
        ),
        "elapsedSeconds": elapsed,
        "invalidResponseTypes": dict(invalid_types),
        "invalidErrorCodes": dict(invalid_errors),
        "problems": problems,
        "processExitCode": process.returncode,
        "stderr": stderr[-2048:],
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "cases",
                    "completedCases",
                    "elapsedSeconds",
                    "invalidResponseTypes",
                    "problems",
                    "processExitCode",
                )
            },
            ensure_ascii=False,
        )
    )
    clean = (
        not problems
        and process.returncode == 0
        and not stderr
        and report["catalogCount"] == 168
    )
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
