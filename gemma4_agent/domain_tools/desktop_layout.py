"""Desktop Layout domain tool — extracted from domain_tools.py.

Snapshot + restore de layout de ventanas (positions + sizes). Usa Win32
EnumWindows + GetWindowRect para enumerar, MoveWindow para restaurar. Va
contra Win32 directamente (vía Add-Type C# en PowerShell) — no GUI scripting.

Funciones extraídas (4):
  desktop_layout_tool             (entry, 5 acciones)
  _enum_windows_with_rect         (Win32 EnumWindows + GetWindowRect)
  _desktop_layout_restore         (MoveWindow por title match)
  _move_window_by_title           (PS Add-Type + MoveWindow)

Helpers desde domain_tools (lazy): _powershell_json."""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Callable

from .._shared import _err, _ok
from ..memory_pkg.state import AgentState


Executor = Callable[[str, dict[str, Any]], dict[str, Any]]


__all__ = [
    "desktop_layout_tool",
    "_enum_windows_with_rect",
    "_desktop_layout_restore",
    "_move_window_by_title",
]


def desktop_layout_tool(args: dict[str, Any], state: AgentState, executor: Executor) -> dict[str, Any]:
    from .helpers import _powershell_json
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(can_snapshot_windows=True, restore_supported=True, backend="win32_user32_movewindow")
    if action in {"windows", "list_windows"}:
        rich = _enum_windows_with_rect(int(args.get("limit", 120)))
        if rich:
            return _ok(windows=rich, count=len(rich), source="win32_enum")
        return executor("window", {"action": "list", "limit": int(args.get("limit", 80))})
    if action == "displays":
        return _powershell_json("Get-CimInstance -Namespace root\\wmi -ClassName WmiMonitorBasicDisplayParams | Select-Object InstanceName,MaxHorizontalImageSize,MaxVerticalImageSize,Active | ConvertTo-Json -Depth 3", "displays")
    if action == "snapshot":
        windows = _enum_windows_with_rect(int(args.get("limit", 120)))
        rollback = [{"tool": "desktop_layout", "args": {"action": "restore", "windows": windows}}]
        checkpoint = state.checkpoint(
            "desktop layout snapshot",
            rollback=rollback,
            metadata={"windows": windows, "created_by": "desktop_layout"},
        )
        return _ok(snapshot=checkpoint.get("checkpoint"), windows=windows, count=len(windows))
    if action == "restore":
        return _desktop_layout_restore(args, state)
    return _err(
        "unknown desktop_layout action", action=action,
        valid_actions=[
            "status", "windows", "list_windows", "displays",
            "save_snapshot", "restore_snapshot", "list_snapshots",
            "delete_snapshot", "arrange",
        ],
        status="needs_user",
    )


def _enum_windows_with_rect(limit: int) -> list[dict[str, Any]]:
    """Use Win32 EnumWindows + GetWindowRect to list top-level windows with geometry."""
    env = os.environ.copy()
    env["GEMMA4_LIMIT"] = str(max(1, int(limit)))
    script = r"""
Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public class WinEnum {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll", CharSet = CharSet.Auto)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr hWnd, out int pid);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr hWnd);

  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int left; public int top; public int right; public int bottom; }
}
"@
$results = New-Object 'System.Collections.Generic.List[Hashtable]'
$fg = [WinEnum]::GetForegroundWindow()
$cb = [WinEnum+EnumWindowsProc] {
  param($hWnd, $lParam)
  if (-not [WinEnum]::IsWindowVisible($hWnd)) { return $true }
  $len = [WinEnum]::GetWindowTextLength($hWnd)
  if ($len -le 0) { return $true }
  $sb = New-Object System.Text.StringBuilder ($len + 1)
  [WinEnum]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
  $title = $sb.ToString()
  if ([string]::IsNullOrWhiteSpace($title)) { return $true }
  $rect = New-Object WinEnum+RECT
  [WinEnum]::GetWindowRect($hWnd, [ref]$rect) | Out-Null
  $pid_ = 0
  [WinEnum]::GetWindowThreadProcessId($hWnd, [ref]$pid_) | Out-Null
  $proc_name = ""
  try { $proc_name = (Get-Process -Id $pid_ -ErrorAction SilentlyContinue).ProcessName } catch {}
  $results.Add(@{
    hwnd = [int64]$hWnd
    title = $title
    pid = [int]$pid_
    process = $proc_name
    foreground = ($hWnd -eq $fg)
    minimized = [WinEnum]::IsIconic($hWnd)
    maximized = [WinEnum]::IsZoomed($hWnd)
    rect = @{ left=$rect.left; top=$rect.top; right=$rect.right; bottom=$rect.bottom; width=($rect.right - $rect.left); height=($rect.bottom - $rect.top) }
  })
  return $true
}
[WinEnum]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null
$limit = [int]$env:GEMMA4_LIMIT
$results | Select-Object -First $limit | ConvertTo-Json -Depth 5
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    return data if isinstance(data, list) else []


def _desktop_layout_restore(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Restore windows to a snapshot's positions via Win32 MoveWindow."""
    snapshot_id = str(args.get("snapshot_id") or args.get("checkpoint_id") or "").strip()
    explicit_windows = args.get("windows") if isinstance(args.get("windows"), list) else None
    if explicit_windows:
        windows = explicit_windows
    else:
        data = state._load()
        checkpoints = data.get("checkpoints", {})
        checkpoint = None
        if snapshot_id and snapshot_id in checkpoints:
            checkpoint = checkpoints[snapshot_id]
        else:
            for cp in reversed(list(checkpoints.values())):
                if "desktop" in str(cp.get("label", "")).casefold():
                    checkpoint = cp
                    break
        if not checkpoint:
            return _err("no desktop layout snapshot available")
        windows = (checkpoint.get("metadata") or {}).get("windows") or []
    if not windows:
        return _err("snapshot has no windows to restore")

    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for w in windows:
        if not isinstance(w, dict):
            continue
        rect = w.get("rect") or {}
        title = str(w.get("title") or "").strip()
        try:
            x = int(rect.get("left", 0))
            y = int(rect.get("top", 0))
            width = int(rect.get("width") or (rect.get("right", 0) - rect.get("left", 0)))
            height = int(rect.get("height") or (rect.get("bottom", 0) - rect.get("top", 0)))
        except (TypeError, ValueError):
            skipped.append({"title": title, "reason": "invalid rect"})
            continue
        if width <= 0 or height <= 0:
            skipped.append({"title": title, "reason": "non-positive size"})
            continue
        result = _move_window_by_title(title, x, y, width, height)
        if result.get("ok"):
            applied.append({"title": title, "x": x, "y": y, "width": width, "height": height})
        else:
            skipped.append({"title": title, "reason": result.get("error") or "move failed"})
    return _ok(restored=len(applied), skipped=len(skipped), applied=applied, skipped_details=skipped, verified=bool(applied))


def _move_window_by_title(title: str, x: int, y: int, width: int, height: int) -> dict[str, Any]:
    env = os.environ.copy()
    env["GEMMA4_TITLE"] = title
    env["GEMMA4_X"] = str(x)
    env["GEMMA4_Y"] = str(y)
    env["GEMMA4_W"] = str(width)
    env["GEMMA4_H"] = str(height)
    script = r"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32MR {
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool repaint);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@
$q = $env:GEMMA4_TITLE
$p = Get-Process | Where-Object { $_.MainWindowTitle -and $_.MainWindowTitle.Equals($q, [System.StringComparison]::OrdinalIgnoreCase) } | Select-Object -First 1
if (-not $p) {
  $p = Get-Process | Where-Object { $_.MainWindowTitle -and $_.MainWindowTitle.ToLower().Contains($q.ToLower()) } | Select-Object -First 1
}
if (-not $p) { [PSCustomObject]@{ ok=$false; error="window not found"; title=$q } | ConvertTo-Json; exit 0 }
[Win32MR]::ShowWindow($p.MainWindowHandle, 9) | Out-Null  # SW_RESTORE
[Win32MR]::MoveWindow($p.MainWindowHandle,[int]$env:GEMMA4_X,[int]$env:GEMMA4_Y,[int]$env:GEMMA4_W,[int]$env:GEMMA4_H,$true) | Out-Null
[PSCustomObject]@{ ok=$true; title=$p.MainWindowTitle; process=$p.ProcessName } | ConvertTo-Json
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        return _err("MoveWindow failed", stderr=proc.stderr)
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
        return data if isinstance(data, dict) else _err("invalid MoveWindow result")
    except json.JSONDecodeError:
        return _err("invalid MoveWindow JSON", stdout=proc.stdout[:1000])
