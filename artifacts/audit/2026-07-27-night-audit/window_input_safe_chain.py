"""Exercise BAXY window/input operations on an audit-only text surface."""

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


class Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def cursor_position() -> tuple[int, int]:
    point = Point()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        raise OSError("GetCursorPos failed")
    return int(point.x), int(point.y)


def restore_cursor(position: tuple[int, int]) -> None:
    ctypes.windll.user32.SetCursorPos(position[0], position[1])


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


def close_osk_pid(pid: int) -> bool:
    for hwnd in visible_windows_for_pid(pid):
        ctypes.windll.user32.PostMessageW(hwnd, 0x0112, 0xF060, 0)
    for _ in range(20):
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(0.1)
    return False


def process_ids(image_name: str) -> set[int]:
    completed = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
    )
    found: set[int] = set()
    for line in completed.stdout.splitlines():
        if not line.startswith('"'):
            continue
        fields = [field.strip('"') for field in line.split('","')]
        if len(fields) >= 2 and fields[1].isdigit():
            found.add(int(fields[1]))
    return found


def read_line(pipe: Any, timeout: float = 30.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("window/input operation timed out") from exception
    if not line:
        raise RuntimeError("core closed before window/input response")
    return line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--target-script", type=Path, required=True)
    parser.add_argument("--diagnostic-script", type=Path)
    parser.add_argument("--skip-known-broken-select-all", action="store_true")
    parser.add_argument("--continue-after-window-failure", action="store_true")
    parser.add_argument("--close-osk-through-baxy", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    target_script = args.target_script.resolve(strict=True)
    diagnostic_script = (
        args.diagnostic_script.resolve(strict=True)
        if args.diagnostic_script is not None
        else None
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-window-safe-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
    before_osk = process_ids("osk.exe")
    pointer_before = cursor_position()
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
            raise RuntimeError("audit text target exited before showing a window")
        time.sleep(0.1)
    else:
        target.terminate()
        raise RuntimeError("audit text target did not show a window")

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
    cleanup: dict[str, Any] = {}
    select_diagnostic: dict[str, Any] | None = None
    window_recoveries: list[dict[str, Any]] = []

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

    def resolve_target() -> dict[str, Any]:
        resolved = invoke("window.resolve", {"process": "powershell", "limit": 50})
        matches = [
            window
            for window in resolved["windows"]
            if window["processId"] == target.pid
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"expected one audit text window for PID {target.pid}, got {len(matches)}"
            )
        return matches[0]

    def window_action(
        operation: str,
        window: dict[str, Any],
        extra_arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        arguments = {"windowId": window["windowId"], **(extra_arguments or {})}
        try:
            return invoke(operation, arguments)["window"]
        except RuntimeError as exception:
            if not args.continue_after_window_failure:
                raise
            time.sleep(0.5)
            observed = resolve_target()
            window_recoveries.append(
                {
                    "operation": operation,
                    "failure": str(exception),
                    "observedAfter500ms": observed,
                }
            )
            return observed

    started = time.perf_counter()
    try:
        window = resolve_target()
        window = invoke("window.focus", {"windowId": window["windowId"]})["window"]
        active = invoke("window.active", {})["windows"]
        if not any(
            item["processId"] == target.pid and item["foreground"] for item in active
        ):
            raise RuntimeError("window.active did not observe the audit text target")

        invoke("input.keyboard.status", {})
        invoke("input.keyboard.layout", {"language": "spanish"})
        keyboard = invoke("input.keyboard.open", {})
        keyboard_pid = keyboard.get("openedProcessId")
        invoke(
            "input.text.type",
            {
                "text": (
                    "BAXY synthetic input audit line 1\r\n"
                    "BAXY synthetic input audit line 2\r\n"
                    "BAXY synthetic input audit line 3"
                )
            },
        )
        if not args.skip_known_broken_select_all:
            try:
                invoke("input.select.all", {})
            except RuntimeError:
                if diagnostic_script is not None:
                    diagnostic = subprocess.run(
                        [
                            "powershell.exe",
                            "-NoProfile",
                            "-NonInteractive",
                            "-STA",
                            "-File",
                            str(diagnostic_script),
                        ],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=20,
                        check=False,
                    )
                    try:
                        select_diagnostic = json.loads(
                            diagnostic.stdout.splitlines()[-1]
                        )
                    except (IndexError, json.JSONDecodeError):
                        select_diagnostic = {
                            "diagnosticExitCode": diagnostic.returncode,
                            "parseFailed": True,
                        }
                raise
        invoke("input.key.press", {"key": "backspace"})
        invoke("input.text.type", {"text": "BAXY synthetic input audit"})

        window = resolve_target()
        window = window_action("window.maximize", window)
        window = window_action("window.restore", window)
        window = window_action(
            "window.move",
            window,
            {"x": 160, "y": 140},
        )
        window = window_action(
            "window.resize",
            window,
            {"width": 760, "height": 520},
        )
        window = window_action("window.minimize", window)
        window = window_action("window.restore", window)
        window = window_action("window.focus", window)

        invoke("input.pointer.control", {"action": "move_center"})
        invoke("input.pointer.control", {"action": "click"})
        invoke("input.pointer.control", {"action": "scroll_down"})
        restore_cursor(pointer_before)

        if args.close_osk_through_baxy and keyboard_pid is not None:
            resolved_osk = invoke("window.resolve", {"process": "osk", "limit": 20})
            osk_matches = [
                item
                for item in resolved_osk["windows"]
                if item["processId"] == int(keyboard_pid)
            ]
            if len(osk_matches) != 1:
                raise RuntimeError(
                    f"expected one audit OSK window, got {len(osk_matches)}"
                )
            invoke("app.close", {"windowId": osk_matches[0]["windowId"]})

        window = resolve_target()
        invoke("app.close", {"windowId": window["windowId"]})
        target.wait(timeout=10)
        if keyboard_pid is not None and int(keyboard_pid) not in before_osk:
            cleanup["osk_closed_by_system_message"] = close_osk_pid(int(keyboard_pid))
    except Exception as exception:
        error = f"{type(exception).__name__}: {exception}"
    finally:
        restore_cursor(pointer_before)
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        stderr = process.stderr.read()
        if target.poll() is None:
            target.terminate()
            try:
                target.wait(timeout=5)
            except subprocess.TimeoutExpired:
                target.kill()
                target.wait(timeout=5)
        for osk_pid in process_ids("osk.exe") - before_osk:
            cleanup[f"osk_{osk_pid}_closed"] = close_osk_pid(osk_pid)
        cleanup["target_exit_code"] = target.returncode
        cleanup["remaining_audit_osk"] = sorted(
            process_ids("osk.exe") - before_osk
        )
        cleanup["cursor_restored"] = cursor_position() == pointer_before

    report = {
        "schema": "baxy.audit.window-input-safe-chain.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "catalog_utf8_bytes": len(hello_line.encode("utf-8")),
        "elapsed_seconds": time.perf_counter() - started,
        "target_pid": target.pid,
        "total": len(cases),
        "verified": sum(
            case["responses"][-1].get("verified") is True for case in cases
        ),
        "cases": cases,
        "error": error,
        "select_diagnostic": select_diagnostic,
        "window_recoveries": window_recoveries,
        "cleanup": cleanup,
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
                "cleanup": cleanup,
            },
            ensure_ascii=False,
        )
    )
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
