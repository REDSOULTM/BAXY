"""Queue a burst of safe read-only requests through one installed core."""

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


OPERATIONS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("system.time", {}),
    ("system.identity", {}),
    ("system.status", {}),
    ("audio.status", {}),
    ("network.status", {}),
    ("network.dns.status", {}),
    ("network.port.list", {}),
    ("note.list", {}),
    ("task.list", {}),
    ("reminder.list", {}),
    ("routine.list", {}),
    ("backup.list", {}),
)


def read_line(pipe: Any, timeout: float) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("response timed out") from exception
    if not line:
        raise RuntimeError("core closed before all responses")
    return line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requests", type=int, default=240)
    args = parser.parse_args()
    if args.requests < 1:
        raise SystemExit("--requests must be positive")

    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-protocol-burst-" + uuid.uuid4().hex)
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
    hello_line = read_line(process.stdout, 10)
    hello = json.loads(hello_line)

    requests: list[dict[str, Any]] = []
    expected: dict[str, tuple[str, str, str]] = {}
    for index in range(args.requests):
        operation, arguments = OPERATIONS[index % len(OPERATIONS)]
        request_id = str(uuid.uuid4())
        mission_id = str(uuid.uuid4())
        invocation_id = str(uuid.uuid4())
        request = {
            "type": "operation.request",
            "requestId": request_id,
            "missionId": mission_id,
            "invocationId": invocation_id,
            "operation": operation,
            "arguments": arguments,
        }
        requests.append(request)
        expected[request_id] = (mission_id, invocation_id, operation)

    writer_errors: list[str] = []

    def write_requests() -> None:
        try:
            for request in requests:
                process.stdin.write(
                    json.dumps(request, separators=(",", ":")) + "\n"
                )
            process.stdin.flush()
        except Exception as exception:
            writer_errors.append(f"{type(exception).__name__}:{exception}")

    started = time.perf_counter()
    writer = threading.Thread(target=write_requests)
    writer.start()
    responses: list[dict[str, Any]] = []
    reader_error: str | None = None
    try:
        for _ in requests:
            responses.append(json.loads(read_line(process.stdout, 30)))
    except Exception as exception:
        reader_error = f"{type(exception).__name__}:{exception}"
    writer.join(timeout=10)
    if writer.is_alive():
        writer_errors.append("writer_thread_timeout")
    elapsed = time.perf_counter() - started

    seen: set[str] = set()
    mismatches: list[dict[str, Any]] = []
    statuses: dict[str, int] = {}
    for response in responses:
        request_id = str(response.get("requestId"))
        status = str(response.get("status"))
        statuses[status] = statuses.get(status, 0) + 1
        if request_id in seen:
            mismatches.append({"requestId": request_id, "error": "duplicate"})
            continue
        seen.add(request_id)
        expected_identity = expected.get(request_id)
        if expected_identity is None:
            mismatches.append({"requestId": request_id, "error": "unexpected"})
            continue
        mission_id, invocation_id, operation = expected_identity
        problems: list[str] = []
        if response.get("missionId") != mission_id:
            problems.append("missionId")
        if response.get("invocationId") != invocation_id:
            problems.append("invocationId")
        if status != "completed" or response.get("verified") is not True:
            problems.append(
                "terminal:"
                + str(response.get("errorCode") or response.get("status"))
            )
        if problems:
            mismatches.append(
                {
                    "requestId": request_id,
                    "operation": operation,
                    "errors": problems,
                }
            )

    missing = sorted(set(expected) - seen)
    process.stdin.close()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)
    stderr = process.stderr.read()
    shutil.rmtree(data_root, ignore_errors=True)

    report = {
        "schema": "baxy.audit.protocol-burst-stress.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "requests": len(requests),
        "responses": len(responses),
        "elapsed_seconds": elapsed,
        "responses_per_second": len(responses) / elapsed if elapsed else None,
        "statuses": statuses,
        "missing_count": len(missing),
        "missing_request_ids": missing,
        "mismatches": mismatches,
        "writer_errors": writer_errors,
        "reader_error": reader_error,
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
                "requests": report["requests"],
                "responses": report["responses"],
                "elapsed_seconds": report["elapsed_seconds"],
                "responses_per_second": report["responses_per_second"],
                "statuses": statuses,
                "missing_count": report["missing_count"],
                "mismatch_count": len(mismatches),
                "writer_errors": writer_errors,
                "reader_error": reader_error,
                "process_exit_code": process.returncode,
            },
            ensure_ascii=False,
        )
    )
    clean = (
        len(responses) == len(requests)
        and not missing
        and not mismatches
        and not writer_errors
        and reader_error is None
        and process.returncode == 0
        and not stderr
    )
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
