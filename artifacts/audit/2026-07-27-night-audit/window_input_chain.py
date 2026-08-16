"""Exercise a real audit-owned Notepad through BAXY window/input operations."""

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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-window-input-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
    before_notepad = process_ids("Notepad.exe")
    before_osk = process_ids("osk.exe") | process_ids("TabTip.exe")
    pointer_before = cursor_position()
    created_notepad_pid: int | None = None
    cases: list[dict[str, Any]] = []
    error: str | None = None
    cleanup: dict[str, Any] = {}
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

    def resolve_window(pid: int) -> dict[str, Any]:
        resolved = invoke("window.resolve", {"process": "notepad", "limit": 20})
        matches = [
            window for window in resolved["windows"] if window["processId"] == pid
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"expected one audit Notepad window for PID {pid}, got {len(matches)}"
            )
        return matches[0]

    started = time.perf_counter()
    try:
        opened = invoke("app.open", {"appId": "windows.notepad"})
        created_notepad_pid = int(opened["processId"])
        if created_notepad_pid in before_notepad:
            raise RuntimeError("app.open reused a preexisting Notepad process")
        window = resolve_window(created_notepad_pid)
        window = invoke("window.focus", {"windowId": window["windowId"]})["window"]
        active = invoke("window.active", {})["windows"]
        if not any(
            item["processId"] == created_notepad_pid and item["foreground"]
            for item in active
        ):
            raise RuntimeError("window.active did not observe the focused audit window")

        invoke("input.keyboard.status", {})
        invoke("input.keyboard.layout", {"language": "spanish"})
        invoke("input.keyboard.open", {})
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
        invoke("input.select.all", {})
        invoke("input.key.press", {"key": "backspace"})
        invoke("input.text.type", {"text": "BAXY synthetic input audit"})

        window = resolve_window(created_notepad_pid)
        window = invoke("window.maximize", {"windowId": window["windowId"]})["window"]
        window = invoke("window.restore", {"windowId": window["windowId"]})["window"]
        window = invoke(
            "window.move",
            {"windowId": window["windowId"], "x": 120, "y": 120},
        )["window"]
        window = invoke(
            "window.resize",
            {"windowId": window["windowId"], "width": 800, "height": 600},
        )["window"]
        window = invoke("window.minimize", {"windowId": window["windowId"]})["window"]
        window = invoke("window.restore", {"windowId": window["windowId"]})["window"]
        window = invoke("window.focus", {"windowId": window["windowId"]})["window"]

        invoke("input.pointer.control", {"action": "move_center"})
        invoke("input.pointer.control", {"action": "click"})
        invoke("input.pointer.control", {"action": "scroll_down"})
        restore_cursor(pointer_before)

        # The buffer is deliberately dirty. This checks whether app.close
        # reports an unsaved-data prompt honestly. Cleanup below is exact-PID.
        window = resolve_window(created_notepad_pid)
        invoke("app.close", {"windowId": window["windowId"]})
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

        remaining_notepad = process_ids("Notepad.exe") - before_notepad
        cleanup["audit_notepad_before_cleanup"] = sorted(remaining_notepad)
        if created_notepad_pid in remaining_notepad:
            completed = subprocess.run(
                ["taskkill", "/PID", str(created_notepad_pid), "/T", "/F"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False,
            )
            cleanup["notepad_taskkill_exit"] = completed.returncode
        audit_osk = (
            process_ids("osk.exe") | process_ids("TabTip.exe")
        ) - before_osk
        cleanup["audit_osk_before_cleanup"] = sorted(audit_osk)
        for pid in sorted(audit_osk):
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=15,
                check=False,
            )
        time.sleep(1)
        cleanup["remaining_audit_notepad"] = sorted(
            process_ids("Notepad.exe") - before_notepad
        )
        cleanup["remaining_audit_osk"] = sorted(
            (process_ids("osk.exe") | process_ids("TabTip.exe")) - before_osk
        )
        cleanup["cursor_restored"] = cursor_position() == pointer_before

    report = {
        "schema": "baxy.audit.window-input-chain.v1",
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
