"""Verify durable data and idempotent replay across a real core restart."""

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
        raise TimeoutError("restart/replay response timed out") from exception
    if not line:
        raise RuntimeError("core closed before restart/replay response")
    return line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    core_path = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-restart-replay-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
    environment = {**os.environ, "BAXY_DATA_DIR": str(data_root)}
    mission_id = str(uuid.uuid4())
    invocation_id = str(uuid.uuid4())
    arguments = {
        "title": "BAXY durable replay audit",
        "content": "synthetic durable marker",
    }
    rounds: list[dict[str, Any]] = []
    error: str | None = None
    core_version: str | None = None
    catalog_count: int | None = None

    def run_round(replay_expected: bool) -> dict[str, Any]:
        nonlocal core_version, catalog_count
        process = subprocess.Popen(
            [str(core_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=environment,
        )
        hello_line = read_line(process.stdout, 10)
        hello = json.loads(hello_line)
        core_version = hello.get("coreVersion")
        catalog_count = len(hello.get("capabilities") or [])

        def call(operation: str, payload: dict[str, Any], *, same_id: bool) -> dict[str, Any]:
            request = {
                "type": "operation.request",
                "requestId": str(uuid.uuid4()),
                "missionId": mission_id if same_id else str(uuid.uuid4()),
                "invocationId": invocation_id if same_id else str(uuid.uuid4()),
                "operation": operation,
                "arguments": payload,
            }
            process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            process.stdin.flush()
            return json.loads(read_line(process.stdout))

        created = call("note.create", arguments, same_id=True)
        read = call(
            "note.search",
            {"query": "synthetic durable marker", "limit": 10},
            same_id=False,
        )
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        stderr = process.stderr.read()
        if (
            created.get("status") != "completed"
            or created.get("verified") is not True
            or created.get("replayed") is not replay_expected
        ):
            raise RuntimeError(
                f"note.create replay flag was not {replay_expected} after restart"
            )
        notes = (read.get("result") or {}).get("notes") or []
        if len(notes) != 1:
            raise RuntimeError(f"durable note count was {len(notes)}, expected 1")
        return {
            "helloUtf8Bytes": len(hello_line.encode("utf-8")),
            "create": created,
            "search": read,
            "exitCode": process.returncode,
            "stderr": stderr[-1024:],
        }

    started = time.perf_counter()
    try:
        rounds.append(run_round(replay_expected=False))
        rounds.append(run_round(replay_expected=True))
    except Exception as exception:
        error = f"{type(exception).__name__}: {exception}"

    report = {
        "schema": "baxy.audit.restart-replay-chain.v1",
        "coreVersion": core_version,
        "catalogCount": catalog_count,
        "elapsedSeconds": time.perf_counter() - started,
        "rounds": rounds,
        "error": error,
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(data_root, ignore_errors=True)
    print(
        json.dumps(
            {
                "rounds": len(rounds),
                "replayed": (
                    rounds[-1]["create"].get("replayed") if len(rounds) == 2 else None
                ),
                "error": error,
            },
            ensure_ascii=False,
        )
    )
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
