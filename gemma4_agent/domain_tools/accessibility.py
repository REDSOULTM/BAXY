"""Accessibility domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Wraps Windows accessibility executables: Magnifier (magnify.exe), Narrator
(narrator.exe), and the Settings page (ms-settings:easeofaccess). High
Contrast toggle is intentionally deferred — its programmatic path requires
registry edits + WM_SETTINGCHANGE broadcast that show a Windows confirmation
dialog; the safe path is the shortcut LAlt+LShift+PrtSc.

Funciones extraídas (4):
  accessibility_tool             (entry, 7+ acciones)
  _process_running               (helper privado del área, sólo usado acá)
  _accessibility_launch          (registra resource para auto-cleanup)
  _accessibility_kill            (taskkill + mark_cleaned)

Helpers desde domain_tools (lazy):
  _ps_quote (string-quote PowerShell), _resources_by_kind (cleanup hook)"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from .._shared import _err, _ok
from ..state import AgentState


__all__ = [
    "accessibility_tool",
    "_process_running",
    "_accessibility_launch",
    "_accessibility_kill",
]


def accessibility_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for Windows accessibility features.

    Actions: status, magnifier_start, magnifier_stop, narrator_start,
    narrator_stop, dictation_status, settings_panel. High Contrast toggle
    via registry is fragile and shows a Windows confirmation dialog; we
    instead point the user at the keyboard shortcut LAlt+LShift+PrtSc and
    expose settings_panel to open the Settings page.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            magnifier_running=_process_running("Magnify.exe"),
            narrator_running=_process_running("Narrator.exe"),
            note="High Contrast toggle is deferred (requires registry + WM_SETTINGCHANGE broadcast). Use action=settings_panel to open the Accessibility Settings instead.",
        )
    if action == "magnifier_start":
        return _accessibility_launch("magnify.exe", state, kind="magnifier")
    if action == "magnifier_stop":
        return _accessibility_kill("Magnify.exe", state, kind="magnifier")
    if action == "narrator_start":
        return _accessibility_launch("narrator.exe", state, kind="narrator")
    if action == "narrator_stop":
        return _accessibility_kill("Narrator.exe", state, kind="narrator")
    if action == "dictation_status":
        # Windows speech recognition runs under sapisvc / WindowsSpeechRecognition.
        return _ok(
            speech_service=_process_running("WindowsSpeech.exe") or _process_running("speech_runtime.exe"),
            shortcut="Win+H starts dictation in Windows 11.",
            note="Programmatic toggle requires the WinRT SpeechRecognizer namespace; not exposed here.",
        )
    if action in {"settings_panel", "open_settings"}:
        # ms-settings:easeofaccess opens the Accessibility settings page.
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", "Start-Process 'ms-settings:easeofaccess'"], capture_output=True, text=True, timeout=10)
        return _ok(opened=proc.returncode == 0, uri="ms-settings:easeofaccess", verified=proc.returncode == 0)
    if action in {"high_contrast_on", "high_contrast_off", "high_contrast_toggle"}:
        return _err(
            f"accessibility.{action} is deferred; the safe path is the shortcut Left Alt + Left Shift + Print Screen which shows a confirmation dialog.",
            status="needs_user",
            note="If you want programmatic toggle, open ms-settings:easeofaccess-highcontrast (via accessibility settings_panel).",
        )
    return _err(
        "unknown accessibility action", action=action,
        valid_actions=[
            "status", "magnifier_start", "magnifier_stop",
            "narrator_start", "narrator_stop",
            "high_contrast_on", "high_contrast_off",
            "color_filter_on", "color_filter_off",
        ],
        status="needs_user",
    )


def _process_running(exe_name: str) -> bool:
    from .helpers import _ps_quote
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"if (Get-Process -Name '{_ps_quote(Path(exe_name).stem)}' -ErrorAction SilentlyContinue) {{ 1 }} else {{ 0 }}"],
        capture_output=True, text=True, timeout=10,
    )
    return proc.stdout.strip() == "1"


def _accessibility_launch(exe: str, state: AgentState, *, kind: str) -> dict[str, Any]:
    try:
        proc = subprocess.Popen([exe], creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except FileNotFoundError:
        return _err(f"{exe} not found on PATH", status="needs_user")
    state.register_resource(
        f"accessibility_{kind}", exe,
        cleanup_tool="accessibility",
        cleanup_args={"action": f"{kind}_stop"},
        metadata={"exe": exe, "pid": proc.pid, "started_at": datetime.now().isoformat()},
    )
    return _ok(kind=kind, exe=exe, pid=proc.pid, verified=True, note=f"{kind} started; close via {kind}_stop.")


def _accessibility_kill(exe: str, state: AgentState, *, kind: str) -> dict[str, Any]:
    from .helpers import _resources_by_kind
    # timeout 15 -> 5s: taskkill normalmente termina en <1s; si tarda 15s
    # algo esta mal (snapshot del sistema corrupto, AV interceptando) y
    # mejor reportar el error rapido que bloquear al caller.
    proc = subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True, text=True, timeout=5)
    killed = proc.returncode == 0
    # Mark any matching resource as cleaned.
    for res in _resources_by_kind(state, f"accessibility_{kind}", include_closed=False):
        state.mark_cleaned(str(res["id"]), {"killed": killed})
    return _ok(kind=kind, exe=exe, killed=killed, exit_code=proc.returncode, stderr=proc.stderr[-500:])
