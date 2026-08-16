"""Exercise BAXY's local note/task/reminder/routine lifecycles.

Audit harness only. The real core runs against a fresh isolated data root,
confirmation handshakes are followed normally, and the whole root is removed
after the evidence report has been written.
"""

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
        raise TimeoutError("local-data operation timed out") from exception
    if not line:
        raise RuntimeError("core closed before local-data response")
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
        / ("audit-local-data-" + uuid.uuid4().hex)
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
            "elapsed_seconds": time.perf_counter() - started,
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
        # Notes: create, identity read, CAS update, search, trash, restore.
        note = invoke(
            "note.create",
            {"title": "BAXY audit note", "content": "synthetic content one"},
        )
        note_id = note["noteId"]
        note_revision = note["revision"]
        invoke("note.read", {"noteId": note_id})
        note = invoke(
            "note.update",
            {
                "noteId": note_id,
                "expectedRevision": note_revision,
                "expectedTitle": "BAXY audit note",
                "title": "BAXY audit note updated",
                "content": "synthetic content two",
            },
        )
        note_revision = note["revision"]
        invoke("note.search", {"query": "content two", "limit": 10})
        note = invoke(
            "note.trash",
            {
                "noteId": note_id,
                "expectedRevision": note_revision,
                "expectedTitle": "BAXY audit note updated",
                "expectedIsTrashed": False,
            },
        )
        note_revision = note["revision"]
        invoke("note.list", {"scope": "trashed", "limit": 10, "offset": 0})
        invoke(
            "note.restore",
            {
                "noteId": note_id,
                "expectedRevision": note_revision,
                "expectedTitle": "BAXY audit note updated",
                "expectedIsTrashed": True,
            },
        )
        invoke("note.list", {"scope": "active", "limit": 10, "offset": 0})

        # Tasks: create, resolve, update, complete, search, reopen, delete, restore.
        task = invoke(
            "task.create",
            {
                "title": "BAXY audit task",
                "details": "synthetic task details one",
                "due": None,
            },
        )
        task_id = task["taskId"]
        task_version = task["version"]
        selection = invoke(
            "task.resolve.exact",
            {"title": "BAXY audit task", "includeDeleted": False},
        )
        if selection["taskId"] != task_id:
            raise RuntimeError("task.resolve.exact returned the wrong identity")
        task = invoke(
            "task.update",
            {
                "taskId": task_id,
                "expectedVersion": task_version,
                "title": "BAXY audit task updated",
                "details": "synthetic task details two",
                "due": None,
            },
        )
        task = invoke(
            "task.complete",
            {"taskId": task_id, "expectedVersion": task["version"]},
        )
        invoke(
            "task.search",
            {"query": "details two", "status": "completed", "limit": 10},
        )
        task = invoke(
            "task.reopen",
            {"taskId": task_id, "expectedVersion": task["version"]},
        )
        task = invoke(
            "task.delete",
            {
                "taskId": task_id,
                "expectedVersion": task["version"],
                "reviewLabel": "BAXY audit task updated",
            },
        )
        invoke("task.list", {"status": "all", "includeDeleted": True, "limit": 10})
        invoke(
            "task.restore",
            {"taskId": task_id, "expectedVersion": task["version"]},
        )

        # Reminders: future create, list, exact resolve, delete, restore.
        due = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        reminder = invoke(
            "reminder.create",
            {
                "title": "BAXY audit reminder",
                "details": "synthetic reminder details",
                "dueUtc": due,
            },
        )
        reminder_id = reminder["reminderId"]
        invoke("reminder.list", {"limit": 10})
        selection = invoke(
            "reminder.resolve.exact",
            {"title": "BAXY audit reminder", "includeDeleted": False},
        )
        if selection["reminderId"] != reminder_id:
            raise RuntimeError("reminder.resolve.exact returned the wrong identity")
        reminder = invoke(
            "reminder.delete",
            {
                "reminderId": reminder_id,
                "expectedVersion": selection["expectedVersion"],
                "reviewLabel": selection["reviewLabel"],
            },
        )
        invoke(
            "reminder.restore",
            {
                "reminderId": reminder_id,
                "expectedVersion": reminder["version"],
            },
        )

        # Routines: create metadata, resolve/read, toggle, delete, restore.
        routine = invoke(
            "routine.phrase.create",
            {
                "name": "BAXY audit routine",
                "phrase": "run synthetic BAXY audit",
                "action": "capture.screenshot",
            },
        )["routine"]
        routine_id = routine["routineId"]
        invoke("routine.list", {"includeDeleted": False, "limit": 10})
        selection = invoke(
            "routine.resolve.exact",
            {"name": "BAXY audit routine", "includeDeleted": False},
        )
        if selection["routineId"] != routine_id:
            raise RuntimeError("routine.resolve.exact returned the wrong identity")
        invoke("routine.read", {"routineId": routine_id, "includeDeleted": False})
        routine = invoke(
            "routine.set.enabled",
            {
                "routineId": routine_id,
                "expectedRevision": selection["expectedRevision"],
                "enabled": True,
            },
        )
        routine = invoke(
            "routine.set.enabled",
            {
                "routineId": routine_id,
                "expectedRevision": routine["revision"],
                "enabled": False,
            },
        )
        routine = invoke(
            "routine.delete",
            {
                "routineId": routine_id,
                "expectedRevision": routine["revision"],
                "reviewLabel": "BAXY audit routine",
            },
        )
        invoke(
            "routine.restore",
            {
                "routineId": routine_id,
                "expectedRevision": routine["revision"],
            },
        )
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
        "schema": "baxy.audit.local-data-chain.v1",
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
