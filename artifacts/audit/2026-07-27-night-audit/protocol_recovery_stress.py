"""Verify that malformed JSONL frames do not poison the next valid request."""

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
from pathlib import Path
from typing import Any


MALFORMED: tuple[tuple[str, str], ...] = (
    ("empty", ""),
    ("whitespace", "   "),
    ("truncated_object", "{"),
    ("json_null", "null"),
    ("json_string", '"hello"'),
    ("json_array", "[]"),
    ("empty_object", "{}"),
    ("unknown_type", '{"type":"audit.unknown"}'),
    ("missing_request_fields", '{"type":"operation.request"}'),
    ("embedded_nul", '{"type":"audit\\u0000unknown"}'),
    ("overlong_frame", "x" * 66_000),
)


def read_line(pipe: Any, timeout: float = 10) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("response timed out") from exception
    if not line:
        raise RuntimeError("core closed before response")
    return line


def valid_request() -> tuple[str, str, str, str]:
    request_id = str(uuid.uuid4())
    mission_id = str(uuid.uuid4())
    invocation_id = str(uuid.uuid4())
    line = json.dumps(
        {
            "type": "operation.request",
            "requestId": request_id,
            "missionId": mission_id,
            "invocationId": invocation_id,
            "operation": "system.time",
            "arguments": {},
        },
        separators=(",", ":"),
    )
    return line, request_id, mission_id, invocation_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-protocol-recovery-" + uuid.uuid4().hex)
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
    hello_line = read_line(process.stdout)
    hello = json.loads(hello_line)
    cases: list[dict[str, Any]] = []
    errors: list[str] = []
    started = time.perf_counter()

    try:
        for label, malformed in MALFORMED:
            process.stdin.write(malformed + "\n")
            process.stdin.flush()
            malformed_response = json.loads(read_line(process.stdout))
            valid, request_id, mission_id, invocation_id = valid_request()
            process.stdin.write(valid + "\n")
            process.stdin.flush()
            recovery = json.loads(read_line(process.stdout))
            malformed_safe = (
                malformed_response.get("type") == "protocol.error"
                and bool(malformed_response.get("errorCode"))
            )
            recovered = (
                recovery.get("type") == "operation.response"
                and recovery.get("requestId") == request_id
                and recovery.get("missionId") == mission_id
                and recovery.get("invocationId") == invocation_id
                and recovery.get("status") == "completed"
                and recovery.get("verified") is True
            )
            if not malformed_safe:
                errors.append(label + ":malformed_frame_not_rejected")
            if not recovered:
                errors.append(label + ":next_request_not_recovered")
            cases.append(
                {
                    "label": label,
                    "input_utf8_bytes": len((malformed + "\n").encode("utf-8")),
                    "protocol_error_code": malformed_response.get("errorCode"),
                    "malformed_safe": malformed_safe,
                    "recovered": recovered,
                    "recovery_error_code": recovery.get("errorCode"),
                }
            )
    except Exception as exception:
        errors.append(f"{type(exception).__name__}:{exception}")
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        stderr = process.stderr.read()
        shutil.rmtree(data_root, ignore_errors=True)

    report = {
        "schema": "baxy.audit.protocol-recovery-stress.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "cases": cases,
        "safe_rejections": sum(case["malformed_safe"] for case in cases),
        "successful_recoveries": sum(case["recovered"] for case in cases),
        "elapsed_seconds": time.perf_counter() - started,
        "errors": errors,
        "process_exit_code": process.returncode,
        "stderr": stderr[-2048:],
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "cases": len(cases),
                "safe_rejections": report["safe_rejections"],
                "successful_recoveries": report["successful_recoveries"],
                "errors": errors,
                "process_exit_code": process.returncode,
            },
            ensure_ascii=False,
        )
    )
    return 0 if len(cases) == len(MALFORMED) and not errors and not stderr else 1


if __name__ == "__main__":
    raise SystemExit(main())
