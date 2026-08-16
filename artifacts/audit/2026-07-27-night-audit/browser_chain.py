"""Exercise the verified Opera CDP chain in one real core process."""

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


def read_line(pipe: Any, timeout: float = 45.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("browser operation timed out") from exception
    if not line:
        raise RuntimeError("core closed before browser response")
    return line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generic", action="store_true")
    parser.add_argument("--streaming", action="store_true")
    parser.add_argument("--step-delay", type=float, default=0.0)
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-browser-chain-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True)
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

        first = send()
        responses = [first]
        if first.get("errorCode") == "confirmation_required":
            responses.append(send(first["result"]["token"]))
        return {"operation": operation, "arguments": arguments, "responses": responses}

    if args.streaming:
        steps = [
            (
                "streaming.navigate",
                {
                    "service": "youtube",
                    "resourceUri": "https://www.youtube.com/",
                },
            ),
            ("browser.page.read", {"maximumCharacters": 2000}),
            ("browser.tabs.list", {"limit": 5}),
            ("browser.control", {"action": "reload"}),
        ]
    else:
        first_step = (
            ("browser.navigate", {"url": "https://example.com/"})
            if args.generic
            else (
                "browser.navigate.named",
                {"browser": "opera", "url": "https://example.com/"},
            )
        )
        steps = [
            first_step,
            ("browser.page.read", {"maximumCharacters": 2000}),
            ("browser.tabs.list", {"limit": 5}),
            ("browser.control", {"action": "scroll_down"}),
            ("browser.control", {"action": "reload"}),
            ("browser.navigate", {"url": "https://example.com/?baxy-audit=1"}),
            ("browser.control", {"action": "back"}),
            ("browser.control", {"action": "close"}),
        ]
    started = time.perf_counter()
    error = None
    try:
        for operation, arguments in steps:
            case_started = time.perf_counter()
            case = invoke(operation, arguments)
            case["elapsed_seconds"] = time.perf_counter() - case_started
            cases.append(case)
            terminal = case["responses"][-1]
            if terminal.get("status") != "completed" or terminal.get("verified") is not True:
                break
            if args.step_delay > 0:
                time.sleep(args.step_delay)
    except Exception as exception:  # evidence captures the exact boundary failure
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
        "schema": "baxy.audit.browser-chain.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "catalog_utf8_bytes": len(hello_line.encode("utf-8")),
        "elapsed_seconds": time.perf_counter() - started,
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
                "total": len(cases),
                "verified": sum(
                    case["responses"][-1].get("verified") is True for case in cases
                ),
                "error": error,
            },
            ensure_ascii=False,
        )
    )
    return 0 if len(cases) == len(steps) and error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
