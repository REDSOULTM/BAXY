"""Repeatedly open and gracefully close the installed BAXY desktop UI."""

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

import psutil


user32 = ctypes.windll.user32
WM_CLOSE = 0x0010


def visible_windows_for_pid(pid: int) -> list[int]:
    handles: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
    )

    def callback(hwnd: int, _: int) -> bool:
        owner_pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_pid))
        if owner_pid.value == pid and user32.IsWindowVisible(hwnd):
            handles.append(int(hwnd))
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return handles


def wait_for_window(pid: int, timeout: float) -> list[int]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        handles = visible_windows_for_pid(pid)
        if handles:
            return handles
        if not psutil.pid_exists(pid):
            return []
        time.sleep(0.1)
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cycles", type=int, default=10)
    parser.add_argument("--child-timeout", type=float, default=0.5)
    args = parser.parse_args()
    if args.cycles < 1:
        raise SystemExit("--cycles must be positive")
    if args.child_timeout < 0:
        raise SystemExit("--child-timeout cannot be negative")

    app = args.app.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    cycles: list[dict[str, Any]] = []
    errors: list[str] = []

    for index in range(1, args.cycles + 1):
        data_root = (
            Path(os.environ["LOCALAPPDATA"])
            / "BAXY"
            / ("audit-ui-start-" + uuid.uuid4().hex)
        )
        data_root.mkdir(parents=True, exist_ok=False)
        started = time.perf_counter()
        process = subprocess.Popen(
            [str(app)],
            env={**os.environ, "BAXY_DATA_DIR": str(data_root)},
        )
        cycle_errors: list[str] = []
        handles = wait_for_window(process.pid, 20)
        ready_seconds = time.perf_counter() - started
        if not handles:
            cycle_errors.append("visible_window_timeout")

        descendants: list[psutil.Process] = []
        descendant_names: list[str] = []
        child_deadline = time.monotonic() + args.child_timeout
        while True:
            try:
                parent = psutil.Process(process.pid)
                descendants = parent.children(recursive=True)
            except psutil.Error:
                descendants = []
            descendant_names = sorted(
                {
                    child.name()
                    for child in descendants
                    if child.is_running()
                    and child.name().lower() in {"baxy-core.exe", "python.exe"}
                }
            )
            if (
                "baxy-core.exe"
                in {name.lower() for name in descendant_names}
                or time.monotonic() >= child_deadline
            ):
                break
            time.sleep(0.05)
        child_observed_seconds = time.perf_counter() - started
        if "baxy-core.exe" not in {name.lower() for name in descendant_names}:
            cycle_errors.append("core_child_not_observed")

        for hwnd in handles:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        try:
            exit_code = process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            cycle_errors.append("graceful_close_timeout")
            process.terminate()
            try:
                exit_code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                exit_code = process.wait(timeout=5)

        _, alive = psutil.wait_procs(descendants, timeout=10)
        if alive:
            cycle_errors.append(
                "descendants_after_close:"
                + ",".join(sorted({child.name() for child in alive}))
            )
            for child in alive:
                try:
                    child.terminate()
                except psutil.Error:
                    pass
            psutil.wait_procs(alive, timeout=5)

        try:
            shutil.rmtree(data_root)
            root_removed = True
        except OSError as exception:
            root_removed = False
            cycle_errors.append(f"data_root_cleanup:{type(exception).__name__}")

        cycle = {
            "cycle": index,
            "pid": process.pid,
            "visible_window_count": len(handles),
            "ready_seconds": ready_seconds,
            "child_observed_seconds": child_observed_seconds,
            "observed_product_children": descendant_names,
            "exit_code": exit_code,
            "data_root_removed": root_removed,
            "errors": cycle_errors,
        }
        cycles.append(cycle)
        errors.extend(f"cycle_{index}:{error}" for error in cycle_errors)

    ready = [cycle["ready_seconds"] for cycle in cycles]
    report = {
        "schema": "baxy.audit.ui-startup-stress.v1",
        "app": str(app),
        "cycles": args.cycles,
        "successful_cycles": sum(not cycle["errors"] for cycle in cycles),
        "ready_seconds": {
            "minimum": min(ready),
            "mean": sum(ready) / len(ready),
            "maximum": max(ready),
        },
        "cycle_results": cycles,
        "errors": errors,
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "cycles": report["cycles"],
                "successful_cycles": report["successful_cycles"],
                "ready_seconds": report["ready_seconds"],
                "errors": errors,
            },
            ensure_ascii=False,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
