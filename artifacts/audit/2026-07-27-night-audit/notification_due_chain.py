"""Exercise due-reminder listing and dismissal in an isolated BAXY store."""

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


def read_line(pipe: Any, timeout: float = 20.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("notification operation timed out") from exception
    if not line:
        raise RuntimeError("core closed before notification response")
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
        / ("audit-notification-due-" + uuid.uuid4().hex)
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
    error: str | None = None

    def invoke(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        mission_id = str(uuid.uuid4())
        invocation_id = str(uuid.uuid4())
        request = {
            "type": "operation.request",
            "requestId": str(uuid.uuid4()),
            "missionId": mission_id,
            "invocationId": invocation_id,
            "operation": operation,
            "arguments": arguments,
        }
        started = time.perf_counter()
        process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        process.stdin.flush()
        response = json.loads(read_line(process.stdout))
        cases.append(
            {
                "operation": operation,
                "arguments": arguments,
                "responses": [response],
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
        if response.get("status") != "completed" or response.get("verified") is not True:
            raise RuntimeError(
                f"{operation} failed: "
                f"{response.get('errorCode') or response.get('status')}"
            )
        return response["result"]

    started = time.perf_counter()
    try:
        title = "BAXY synthetic due reminder " + uuid.uuid4().hex[:8]
        due = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
        reminder = invoke(
            "reminder.create",
            {"title": title, "details": "night audit", "dueUtc": due},
        )
        time.sleep(3)
        due_list = invoke("notification.list.due", {"limit": 10})
        matches = [
            item
            for item in due_list.get("reminders", [])
            if item.get("reminderId") == reminder.get("reminderId")
        ]
        if len(matches) != 1:
            raise RuntimeError("due listing did not return the exact audit reminder")
        selected = matches[0]
        invoke(
            "notification.dismiss",
            {
                "reminderId": selected["reminderId"],
                "expectedVersion": selected["version"],
            },
        )
        final = invoke("notification.list.due", {"limit": 10})
        if any(
            item.get("reminderId") == reminder.get("reminderId")
            for item in final.get("reminders", [])
        ):
            raise RuntimeError("dismissed reminder remained in due notifications")
    except Exception as exception:
        error = f"{type(exception).__name__}: {exception}"
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        stderr = process.stderr.read()

    report = {
        "schema": "baxy.audit.notification-due-chain.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "catalog_utf8_bytes": len(hello_line.encode("utf-8")),
        "elapsed_seconds": time.perf_counter() - started,
        "total": len(cases),
        "verified": sum(
            case["responses"][-1].get("verified") is True for case in cases
        ),
        "cases": cases,
        "error": error,
        "process_exit_code": process.returncode,
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
                "total": report["total"],
                "verified": report["verified"],
                "error": error,
            },
            ensure_ascii=False,
        )
    )
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
