"""Reproduce app.open against a real core and clean only audit-created Notepad.

Audit harness only. It does not modify BAXY product code or user documents.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
WM_CLOSE = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def window_processes() -> dict[int, list[dict[str, Any]]]:
    found: dict[int, list[dict[str, Any]]] = {}
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @callback_type
    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        found.setdefault(pid.value, []).append(
            {"hwnd": int(hwnd), "title": title.value}
        )
        return True

    user32.EnumWindows(callback, 0)
    return found


def process_image(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def notepad_windows() -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {}
    for pid, windows in window_processes().items():
        image = process_image(pid).casefold()
        if image.endswith("\\notepad.exe"):
            result[pid] = windows
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--app-id", default="windows.notepad")
    args = parser.parse_args()

    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    before = notepad_windows()
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-app-open-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "BAXY_DATA_DIR": str(data_root)}
    request = {
        "type": "operation.request",
        "requestId": str(uuid.uuid4()),
        "missionId": str(uuid.uuid4()),
        "invocationId": str(uuid.uuid4()),
        "operation": "app.open",
        "arguments": {"appId": args.app_id},
    }
    started = time.perf_counter()
    process = subprocess.Popen(
        [str(core)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    stdout, stderr = process.communicate(
        json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n",
        timeout=30,
    )
    elapsed = time.perf_counter() - started
    lines = [line for line in stdout.splitlines() if line.strip()]
    hello = json.loads(lines[0]) if lines else None
    response = json.loads(lines[1]) if len(lines) > 1 else None
    time.sleep(2)
    after = notepad_windows()
    created = {pid: windows for pid, windows in after.items() if pid not in before}

    close_requests: list[dict[str, Any]] = []
    for pid, windows in created.items():
        for window in windows:
            posted = bool(user32.PostMessageW(window["hwnd"], WM_CLOSE, 0, 0))
            close_requests.append(
                {"pid": pid, "hwnd": window["hwnd"], "posted": posted}
            )
    time.sleep(3)
    remaining = {
        pid: windows
        for pid, windows in notepad_windows().items()
        if pid in created
    }
    isolated_json: dict[str, Any] = {}
    for state_file in data_root.rglob("*.json"):
        try:
            isolated_json[str(state_file.relative_to(data_root))] = json.loads(
                state_file.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError):
            isolated_json[str(state_file.relative_to(data_root))] = {
                "unreadable": True
            }
    report = {
        "schema": "baxy.audit.app-open-repro.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion") if isinstance(hello, dict) else None,
        "catalog_utf8_bytes": len(lines[0].encode("utf-8")) + 1 if lines else None,
        "app_id": args.app_id,
        "elapsed_seconds": elapsed,
        "process_exit_code": process.returncode,
        "response": response,
        "preexisting_notepad": before,
        "created_notepad": created,
        "close_requests": close_requests,
        "remaining_created_notepad": remaining,
        "isolated_json": isolated_json,
        "stderr": stderr[-2048:],
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(data_root, ignore_errors=True)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if response is not None and not remaining else 1


if __name__ == "__main__":
    raise SystemExit(main())
