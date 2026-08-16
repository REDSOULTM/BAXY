"""Terminate one audit-owned ping process through BAXY's work-loss path."""

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

import psutil


def ping_pids() -> set[int]:
    return {
        process.pid
        for process in psutil.process_iter(["name"])
        if (process.info["name"] or "").casefold() == "ping.exe"
    }


def read_line(pipe: Any, timeout: float = 30.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("process termination response timed out") from exception
    if not line:
        raise RuntimeError("core closed before process termination response")
    return line


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
        / ("audit-process-terminate-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
    baseline = ping_pids()
    if baseline:
        raise SystemExit("refusing test because a preexisting ping.exe is running")
    target = subprocess.Popen(
        ["ping.exe", "-t", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    time.sleep(0.5)
    if target.poll() is not None:
        raise RuntimeError("audit ping target exited before the test")

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
    cases: list[dict[str, Any]] = []
    error: str | None = None
    cleanup: dict[str, Any] = {}

    def invoke(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        mission_id = str(uuid.uuid4())
        invocation_id = str(uuid.uuid4())

        def send(token: str | None = None) -> dict[str, Any]:
            request: dict[str, Any] = {
                "type": "operation.request",
                "requestId": str(uuid.uuid4()),
                "missionId": mission_id,
                "invocationId": invocation_id,
                "operation": operation,
                "arguments": arguments,
            }
            if token is not None:
                request["confirmationToken"] = token
            process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            process.stdin.flush()
            return json.loads(read_line(process.stdout))

        started = time.perf_counter()
        first = send()
        responses = [first]
        if first.get("errorCode") == "confirmation_required":
            responses.append(send(first["result"]["token"]))
        case = {
            "operation": operation,
            "arguments": arguments,
            "responses": responses,
            "elapsedSeconds": time.perf_counter() - started,
        }
        cases.append(case)
        terminal = responses[-1]
        if terminal.get("status") != "completed" or terminal.get("verified") is not True:
            raise RuntimeError(
                f"{operation} failed: {terminal.get('errorCode') or terminal.get('status')}"
            )
        return terminal["result"]

    started = time.perf_counter()
    try:
        invoke("system.process.list", {"sort": "name", "limit": 50})
        terminated = invoke(
            "system.process.terminate.named",
            {"name": "ping"},
        )
        target.wait(timeout=10)
        if target.returncode is None or target.pid in ping_pids():
            raise RuntimeError("audit ping process remained after verified termination")
        if (
            int(terminated.get("beforeCount", 0)) != 1
            or int(terminated.get("terminatedCount", 0)) != 1
            or int(terminated.get("afterCount", -1)) != 0
            or terminated.get("originalIdentitiesAbsent") is not True
        ):
            raise RuntimeError("termination receipt did not bind exactly one process")
    except Exception as exception:
        error = f"{type(exception).__name__}: {exception}"
    finally:
        if target.poll() is None:
            target.terminate()
            try:
                target.wait(timeout=5)
            except subprocess.TimeoutExpired:
                target.kill()
                target.wait(timeout=5)
            cleanup["targetTerminatedByHarness"] = True
        else:
            cleanup["targetTerminatedByHarness"] = False
        cleanup["remainingPingPids"] = sorted(ping_pids() - baseline)
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        stderr = process.stderr.read()

    report = {
        "schema": "baxy.audit.process-terminate-chain.v1",
        "coreVersion": hello.get("coreVersion"),
        "catalogCount": len(hello.get("capabilities") or []),
        "targetPid": target.pid,
        "elapsedSeconds": time.perf_counter() - started,
        "cases": cases,
        "error": error,
        "cleanup": cleanup,
        "coreExitCode": process.returncode,
        "stderr": stderr[-2048:],
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(data_root, ignore_errors=True)
    print(
        json.dumps(
            {
                "verified": sum(
                    case["responses"][-1].get("verified") is True for case in cases
                ),
                "total": len(cases),
                "error": error,
                "cleanup": cleanup,
            },
            ensure_ascii=False,
        )
    )
    return 0 if error is None and not cleanup["remainingPingPids"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
