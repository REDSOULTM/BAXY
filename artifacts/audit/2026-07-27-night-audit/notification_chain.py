"""Schedule and immediately cancel one exact future BAXY audit reminder."""

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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def read_line(pipe: Any, timeout: float = 45.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("notification response timed out") from exception
    if not line:
        raise RuntimeError("core closed before notification response")
    return line


def scheduled_task_exists(task_name: str) -> bool:
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "$null -ne (Get-ScheduledTask -TaskName '"
                + task_name
                + "' -ErrorAction SilentlyContinue)"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    return completed.stdout.strip().casefold() == "true"


def remove_exact_audit_task(task_name: str) -> bool:
    if not task_name.startswith("BAXY-Reminder-") or len(task_name) != 46:
        raise RuntimeError("refusing to clean an unexpected scheduled-task identity")
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "Unregister-ScheduledTask -TaskName '"
                + task_name
                + "' -Confirm:$false -ErrorAction Stop"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    return completed.returncode == 0 and not scheduled_task_exists(task_name)


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
        / ("audit-notification-" + uuid.uuid4().hex)
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
    cases: list[dict[str, Any]] = []
    task_name: str | None = None
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
        due = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        scheduled = invoke(
            "notification.schedule",
            {
                "kind": "reminder",
                "title": "BAXY synthetic overnight audit",
                "dueUtc": due,
            },
        )
        task_name = scheduled["taskName"]
        if not scheduled_task_exists(task_name):
            raise RuntimeError("scheduled task was not present after verified schedule")
        canceled = invoke("notification.cancel.latest", {"kind": "reminder"})
        if canceled.get("taskName") != task_name or canceled.get("canceled") is not True:
            raise RuntimeError("cancel.latest did not cancel the exact audit task")
        if scheduled_task_exists(task_name):
            raise RuntimeError("audit task remained after verified cancellation")
    except Exception as exception:
        error = f"{type(exception).__name__}: {exception}"
    finally:
        if task_name is not None and scheduled_task_exists(task_name):
            cleanup["exactTaskRemoved"] = remove_exact_audit_task(task_name)
        else:
            cleanup["exactTaskRemoved"] = False
        cleanup["exactTaskRemaining"] = (
            scheduled_task_exists(task_name) if task_name is not None else False
        )
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        stderr = process.stderr.read()

    report = {
        "schema": "baxy.audit.notification-chain.v1",
        "coreVersion": hello.get("coreVersion"),
        "catalogCount": len(hello.get("capabilities") or []),
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
    return 0 if error is None and not cleanup["exactTaskRemaining"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
