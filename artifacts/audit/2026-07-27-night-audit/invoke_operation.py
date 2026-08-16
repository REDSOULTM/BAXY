"""Invoke one BAXY operation through the real JSONL boundary.

Audit harness only. It uses an isolated data root and can follow the core's
normal confirmation handshake. It never retries a timed-out effect.
"""

from __future__ import annotations

import argparse
import base64
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


def readline_with_timeout(pipe: Any, timeout: float) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    thread = threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True)
    thread.start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("operation response timed out") from exception
    if not line:
        raise RuntimeError("core closed before operation response")
    return line


def request(
    operation: str,
    arguments: dict[str, Any],
    *,
    mission_id: str,
    invocation_id: str,
    token: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "type": "operation.request",
        "requestId": str(uuid.uuid4()),
        "missionId": mission_id,
        "invocationId": invocation_id,
        "operation": operation,
        "arguments": arguments,
    }
    if token is not None:
        value["confirmationToken"] = token
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--operation", required=True)
    arguments_group = parser.add_mutually_exclusive_group(required=True)
    arguments_group.add_argument("--arguments")
    arguments_group.add_argument("--arguments-base64")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--timeout", type=float, default=40.0)
    args = parser.parse_args()

    raw_arguments = (
        base64.b64decode(args.arguments_base64).decode("utf-8")
        if args.arguments_base64 is not None
        else args.arguments
    )
    arguments = json.loads(raw_arguments)
    if not isinstance(arguments, dict):
        raise SystemExit("--arguments must be a JSON object")
    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-operation-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
    environment = {**os.environ, "BAXY_DATA_DIR": str(data_root)}
    process = subprocess.Popen(
        [str(core)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    started = time.perf_counter()
    responses: list[dict[str, Any]] = []
    timed_out = False
    try:
        hello_line = process.stdout.readline()
        hello = json.loads(hello_line)
        mission_id = str(uuid.uuid4())
        invocation_id = str(uuid.uuid4())
        first = request(
            args.operation,
            arguments,
            mission_id=mission_id,
            invocation_id=invocation_id,
        )
        process.stdin.write(json.dumps(first, separators=(",", ":")) + "\n")
        process.stdin.flush()
        # communicate() is not used because a confirmation requires a second
        # request on the same process and invocation identity.
        line = readline_with_timeout(process.stdout, args.timeout)
        responses.append(json.loads(line))
        if (
            args.confirm
            and responses[-1].get("errorCode") == "confirmation_required"
        ):
            token = responses[-1]["result"]["token"]
            second = request(
                args.operation,
                arguments,
                mission_id=mission_id,
                invocation_id=invocation_id,
                token=token,
            )
            process.stdin.write(json.dumps(second, separators=(",", ":")) + "\n")
            process.stdin.flush()
            line = readline_with_timeout(process.stdout, args.timeout)
            responses.append(json.loads(line))
    except TimeoutError:
        timed_out = True
        process.terminate()
    finally:
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        stderr = process.stderr.read() if process.stderr is not None else ""

    report = {
        "schema": "baxy.audit.single-operation.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "catalog_utf8_bytes": len(hello_line.encode("utf-8")),
        "operation": args.operation,
        "arguments": arguments,
        "confirmation_followed": args.confirm,
        "responses": responses,
        "elapsed_seconds": time.perf_counter() - started,
        "timed_out": timed_out,
        "process_exit_code": process.returncode,
        "stderr": stderr[-2048:],
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(data_root, ignore_errors=True)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
