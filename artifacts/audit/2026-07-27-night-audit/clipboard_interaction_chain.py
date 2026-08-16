"""Exercise BAXY clipboard copy/paste against audit-owned WPF controls."""

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


user32 = ctypes.windll.user32
WM_SYSCOMMAND = 0x0112
SC_CLOSE = 0xF060


def read_line(pipe: Any, timeout: float = 30.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("clipboard operation timed out") from exception
    if not line:
        raise RuntimeError("core closed before clipboard response")
    return line


def find_window(process_id: int, timeout: float = 10.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches: list[int] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def callback(hwnd: int, _: int) -> bool:
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == process_id and user32.IsWindowVisible(hwnd):
                matches.append(hwnd)
            return True

        user32.EnumWindows(callback, 0)
        if matches:
            return matches[0]
        time.sleep(0.1)
    raise TimeoutError(f"no visible window for audit PID {process_id}")


def activate(hwnd: int) -> None:
    user32.ShowWindow(hwnd, 9)
    if not user32.SetForegroundWindow(hwnd):
        raise RuntimeError("could not activate audit clipboard target")
    time.sleep(0.5)


def close_target(process: subprocess.Popen[str], hwnd: int) -> None:
    user32.PostMessageW(hwnd, WM_SYSCOMMAND, SC_CLOSE, 0)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)


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
        / ("audit-clipboard-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
    run_id = uuid.uuid4().hex
    copy_marker = f"BAXY_AUDIT_COPY_{run_id}"
    paste_marker = f"BAXY_AUDIT_PASTE_{run_id}"
    copy_output = data_root / "copy-target.txt"
    paste_output = data_root / "paste-target.txt"

    core_process = subprocess.Popen(
        [str(core)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env={**os.environ, "BAXY_DATA_DIR": str(data_root)},
    )
    hello_line = read_line(core_process.stdout, 10)
    hello = json.loads(hello_line)
    cases: list[dict[str, Any]] = []
    targets: list[tuple[subprocess.Popen[str], int]] = []
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
            core_process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            core_process.stdin.flush()
            return json.loads(read_line(core_process.stdout))

        started = time.perf_counter()
        responses = [send()]
        if responses[-1].get("errorCode") == "confirmation_required":
            responses.append(send(responses[-1]["result"]["token"]))
        cases.append(
            {
                "operation": operation,
                "arguments": arguments,
                "responses": responses,
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
        terminal = responses[-1]
        if terminal.get("status") != "completed" or terminal.get("verified") is not True:
            raise RuntimeError(
                f"{operation} failed: "
                f"{terminal.get('errorCode') or terminal.get('status')}"
            )
        return terminal["result"]

    def start_target(
        title: str,
        initial_text: str,
        output_path: Path,
        *,
        select_all: bool,
    ) -> tuple[subprocess.Popen[str], int]:
        command = [
            "powershell.exe",
            "-NoProfile",
            "-STA",
            "-File",
            str(target_script),
            "-Title",
            title,
            "-InitialText",
            initial_text,
            "-OutputPath",
            str(output_path),
        ]
        if select_all:
            command.append("-SelectAll")
        process = subprocess.Popen(command, text=True)
        hwnd = find_window(process.pid)
        targets.append((process, hwnd))
        activate(hwnd)
        return process, hwnd

    started = time.perf_counter()
    try:
        copy_target, copy_hwnd = start_target(
            f"BAXY audit copy {run_id[:8]}",
            copy_marker,
            copy_output,
            select_all=True,
        )
        invoke("clipboard.copy", {})
        copied = invoke("clipboard.read.text", {"maxCharacters": len(copy_marker) + 8})
        if copied.get("text") != copy_marker:
            raise RuntimeError("clipboard.copy did not copy the selected audit marker")
        close_target(copy_target, copy_hwnd)
        targets.remove((copy_target, copy_hwnd))
        if copy_output.read_text(encoding="utf-8-sig") != copy_marker:
            raise RuntimeError("copy target text changed unexpectedly")

        invoke("clipboard.write.text", {"text": paste_marker})
        paste_target, paste_hwnd = start_target(
            f"BAXY audit paste {run_id[:8]}",
            "",
            paste_output,
            select_all=False,
        )
        invoke("clipboard.paste", {})
        time.sleep(0.5)
        close_target(paste_target, paste_hwnd)
        targets.remove((paste_target, paste_hwnd))
        if paste_output.read_text(encoding="utf-8-sig") != paste_marker:
            raise RuntimeError("clipboard.paste was accepted but target text did not change")
    except Exception as exception:
        error = f"{type(exception).__name__}: {exception}"
    finally:
        for target, hwnd in targets:
            try:
                close_target(target, hwnd)
            except Exception:
                target.terminate()
        core_process.stdin.close()
        try:
            core_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            core_process.terminate()
            core_process.wait(timeout=5)
        stderr = core_process.stderr.read()

    report = {
        "schema": "baxy.audit.clipboard-interaction-chain.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "catalog_utf8_bytes": len(hello_line.encode("utf-8")),
        "elapsed_seconds": time.perf_counter() - started,
        "total": len(cases),
        "verified": sum(
            case["responses"][-1].get("verified") is True for case in cases
        ),
        "copy_marker_length": len(copy_marker),
        "paste_marker_length": len(paste_marker),
        "copy_target_verified": copy_output.exists()
        and copy_output.read_text(encoding="utf-8-sig") == copy_marker,
        "paste_target_verified": paste_output.exists()
        and paste_output.read_text(encoding="utf-8-sig") == paste_marker,
        "cases": cases,
        "error": error,
        "process_exit_code": core_process.returncode,
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
                "copy_target_verified": report["copy_target_verified"],
                "paste_target_verified": report["paste_target_verified"],
                "error": error,
            },
            ensure_ascii=False,
        )
    )
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
