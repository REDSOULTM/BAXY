"""Exercise Spotify playback, SMTC seek, pause, and status through BAXY."""

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


def read_line(pipe: Any, timeout: float = 70.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("media operation timed out") from exception
    if not line:
        raise RuntimeError("core closed before media response")
    return line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exact", action="store_true")
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-media-control-" + uuid.uuid4().hex)
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
    errors: list[str] = []
    playback_started = False
    paused = False

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
        responses = [send()]
        if responses[-1].get("errorCode") == "confirmation_required":
            responses.append(send(responses[-1]["result"]["token"]))
        terminal = responses[-1]
        cases.append(
            {
                "operation": operation,
                "arguments": arguments,
                "responses": responses,
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
        return terminal

    started = time.perf_counter()
    try:
        played = invoke(
            "media.play.exact" if args.exact else "media.play.query",
            (
                {"provider": "spotify", "title": "Beat It"}
                if args.exact
                else {"provider": "spotify", "query": "Beat It"}
            ),
        )
        playback_started = (
            played.get("status") == "completed" and played.get("verified") is True
        )
        if not playback_started:
            errors.append(
                ("media.play.exact: " if args.exact else "media.play.query: ")
                + str(played.get("errorCode") or played.get("status"))
            )
        else:
            for operation, arguments in [
                ("media.status", {}),
                ("media.seek.relative", {"seconds": 10}),
                ("media.control", {"action": "pause", "sourceApp": "spotify"}),
                ("media.status", {}),
            ]:
                terminal = invoke(operation, arguments)
                ok = (
                    terminal.get("status") == "completed"
                    and terminal.get("verified") is True
                )
                if operation == "media.control" and ok:
                    paused = True
                if not ok:
                    errors.append(
                        f"{operation}: "
                        f"{terminal.get('errorCode') or terminal.get('status')}"
                    )
    except Exception as exception:
        errors.append(f"{type(exception).__name__}: {exception}")
    finally:
        if playback_started and not paused:
            try:
                terminal = invoke(
                    "media.control",
                    {"action": "pause", "sourceApp": "spotify"},
                )
                paused = (
                    terminal.get("status") == "completed"
                    and terminal.get("verified") is True
                )
                if not paused:
                    errors.append(
                        "cleanup pause: "
                        + str(terminal.get("errorCode") or terminal.get("status"))
                    )
            except Exception as exception:
                errors.append(f"cleanup pause {type(exception).__name__}: {exception}")
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        stderr = process.stderr.read()

    report = {
        "schema": "baxy.audit.media-control-chain.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "catalog_utf8_bytes": len(hello_line.encode("utf-8")),
        "elapsed_seconds": time.perf_counter() - started,
        "total": len(cases),
        "verified": sum(
            case["responses"][-1].get("verified") is True for case in cases
        ),
        "playback_started": playback_started,
        "paused_before_cleanup": paused,
        "cases": cases,
        "errors": errors,
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
                "playback_started": playback_started,
                "paused": paused,
                "errors": errors,
            },
            ensure_ascii=False,
        )
    )
    return 0 if not errors and paused else 1


if __name__ == "__main__":
    raise SystemExit(main())
