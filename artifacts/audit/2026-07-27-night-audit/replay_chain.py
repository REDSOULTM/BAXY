"""Verify that duplicate operation identities replay without duplicate effects."""

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


def read_line(pipe: Any, timeout: float = 20.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("replay response timed out") from exception
    if not line:
        raise RuntimeError("core closed before replay response")
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
        / ("audit-replay-" + uuid.uuid4().hex)
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
    responses: list[dict[str, Any]] = []
    error: str | None = None

    def send(request: dict[str, Any]) -> dict[str, Any]:
        process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        process.stdin.flush()
        response = json.loads(read_line(process.stdout))
        responses.append(response)
        return response

    started = time.perf_counter()
    try:
        mission_id = str(uuid.uuid4())
        invocation_id = str(uuid.uuid4())
        base = {
            "type": "operation.request",
            "missionId": mission_id,
            "invocationId": invocation_id,
            "operation": "note.create",
            "arguments": {
                "title": "BAXY replay audit",
                "content": "synthetic idempotency marker",
            },
        }
        first = send({**base, "requestId": str(uuid.uuid4())})
        second = send({**base, "requestId": str(uuid.uuid4())})
        if (
            first.get("status") != "completed"
            or first.get("verified") is not True
            or first.get("replayed") is True
        ):
            raise RuntimeError("initial note.create did not complete normally")
        if (
            second.get("status") != "completed"
            or second.get("verified") is not True
            or second.get("replayed") is not True
        ):
            raise RuntimeError("duplicate note.create was not marked as replay")
        if first.get("result") != second.get("result"):
            raise RuntimeError("replay result changed")

        listed = send(
            {
                "type": "operation.request",
                "requestId": str(uuid.uuid4()),
                "missionId": str(uuid.uuid4()),
                "invocationId": str(uuid.uuid4()),
                "operation": "note.search",
                "arguments": {"query": "idempotency marker", "limit": 10},
            }
        )
        notes = (listed.get("result") or {}).get("notes") or []
        if len(notes) != 1:
            raise RuntimeError(f"duplicate effect observed: expected 1 note, got {len(notes)}")

        # Reusing the same invocation identity with different arguments must
        # conflict rather than replay or execute a second effect.
        conflict = send(
            {
                **base,
                "requestId": str(uuid.uuid4()),
                "arguments": {
                    "title": "BAXY replay audit changed",
                    "content": "different payload",
                },
            }
        )
        if (
            conflict.get("status") != "rejected"
            or conflict.get("verified") is not False
            or conflict.get("errorCode") != "idempotency_conflict"
            or conflict.get("effectMayHaveOccurred", False) is True
        ):
            raise RuntimeError("changed duplicate identity did not fail closed")
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
        "schema": "baxy.audit.replay-chain.v1",
        "coreVersion": hello.get("coreVersion"),
        "catalogCount": len(hello.get("capabilities") or []),
        "elapsedSeconds": time.perf_counter() - started,
        "responses": responses,
        "error": error,
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
                "responses": len(responses),
                "replayed": sum(item.get("replayed") is True for item in responses),
                "error": error,
            },
            ensure_ascii=False,
        )
    )
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
