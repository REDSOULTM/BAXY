"""Invoke one audit-only visible WPF button through BAXY and verify cleanup."""

from __future__ import annotations

import argparse
import ctypes
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


def visible_windows_for_pid(pid: int) -> list[int]:
    found: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
    )

    def callback(hwnd: int, _: int) -> bool:
        observed = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(
            hwnd, ctypes.byref(observed)
        )
        if observed.value == pid and ctypes.windll.user32.IsWindowVisible(hwnd):
            found.append(int(hwnd))
        return True

    callback_ref = callback_type(callback)
    ctypes.windll.user32.EnumWindows(callback_ref, 0)
    return found


def read_line(pipe: Any, timeout: float = 30.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("visible click response timed out") from exception
    if not line:
        raise RuntimeError("core closed before visible click response")
    return line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--target-script", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    target_script = args.target_script.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-visible-click-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
    target = subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-STA",
            "-File",
            str(target_script),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if visible_windows_for_pid(target.pid):
            break
        if target.poll() is not None:
            raise RuntimeError("audit button target exited before showing")
        time.sleep(0.1)
    else:
        target.terminate()
        raise RuntimeError("audit button target did not show")

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

        first = send()
        responses = [first]
        if first.get("errorCode") == "confirmation_required":
            responses.append(send(first["result"]["token"]))
        case = {
            "operation": operation,
            "arguments": arguments,
            "responses": responses,
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
        resolved = invoke("window.resolve", {"process": "powershell", "limit": 50})
        matches = [
            item
            for item in resolved["windows"]
            if item["processId"] == target.pid
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one audit button window, got {len(matches)}")
        focused = invoke(
            "window.focus", {"windowId": matches[0]["windowId"]}
        )["window"]
        invoke("input.visible.click", {"label": "BAXY audit button"})
        resolved = invoke("window.resolve", {"process": "powershell", "limit": 50})
        matches = [
            item
            for item in resolved["windows"]
            if item["processId"] == target.pid
        ]
        if len(matches) != 1:
            raise RuntimeError("audit button window disappeared unexpectedly")
        invoke("app.close", {"windowId": matches[0]["windowId"]})
        target.wait(timeout=10)
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
        if target.poll() is None:
            target.terminate()
            target.wait(timeout=5)

    report = {
        "schema": "baxy.audit.visible-click-chain.v1",
        "coreVersion": hello.get("coreVersion"),
        "catalogCount": len(hello.get("capabilities") or []),
        "elapsedSeconds": time.perf_counter() - started,
        "cases": cases,
        "error": error,
        "targetExitCode": target.returncode,
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
                "targetExitCode": target.returncode,
            },
            ensure_ascii=False,
        )
    )
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
