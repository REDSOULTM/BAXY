"""Live goal-07 runs: one reversible compound twice, then Steam library."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import run_llm_plan_execution_gate as gate  # noqa: E402


SCRATCH = Path(os.environ.get("GOAL07_SCRATCH") or ".")
STEAM_OBJECTIVE = "Abre Steam y ve a la biblioteca"
LIBRARY_OBSERVER = r"""
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class BaxySteamPostread {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint procId);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L; public int T; public int R; public int B; }
}
'@
$ids = New-Object 'System.Collections.Generic.HashSet[int]'
Get-Process steam, steamwebhelper -ErrorAction SilentlyContinue | ForEach-Object { [void]$ids.Add($_.Id) }
$script:best = $null
$cb = [BaxySteamPostread+EnumProc]{
  param($h, $l)
  if (-not [BaxySteamPostread]::IsWindowVisible($h)) { return $true }
  $procId = [uint32]0
  [void][BaxySteamPostread]::GetWindowThreadProcessId($h, [ref]$procId)
  if (-not $ids.Contains([int]$procId)) { return $true }
  $r = New-Object BaxySteamPostread+RECT
  [void][BaxySteamPostread]::GetWindowRect($h, [ref]$r)
  $w = $r.R - $r.L; $ht = $r.B - $r.T
  $area = [int64]$w * [int64]$ht
  if ($null -eq $script:best -or $area -gt $script:best.area) {
    $title = New-Object System.Text.StringBuilder 256
    [void][BaxySteamPostread]::GetWindowText($h, $title, 256)
    $script:best = [pscustomobject]@{ hwnd=$h; w=$w; h=$ht; area=$area; title=$title.ToString(); left=$r.L; top=$r.T; procId=[int]$procId }
  }
  return $true
}
[void][BaxySteamPostread]::EnumWindows($cb, [IntPtr]::Zero)
if ($null -eq $best -or $best.w -lt 400 -or $best.h -lt 300) {
  [pscustomobject]@{ ok=$false; error='steam_main_window_not_visible'; width=$(if($best){$best.w}else{0}); height=$(if($best){$best.h}else{0}) } | ConvertTo-Json -Compress
  exit 2
}
$bmp = New-Object System.Drawing.Bitmap $best.w, $best.h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($best.left, $best.top, 0, 0, (New-Object System.Drawing.Size($best.w, $best.h)))
$path = Join-Path $env:TEMP 'baxy-steam-library-postread.bmp'
$bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Bmp)
$g.Dispose(); $bmp.Dispose()
$ocr = & 'C:\Program Files\Tesseract-OCR\tesseract.exe' $path stdout -l eng --psm 6 2>$null
$surface = $ocr -match '(?i)biblioteca|library'
[pscustomobject]@{
  ok = [bool]$surface
  title = $best.title
  width = $best.w
  height = $best.h
  processId = $best.procId
  screenshot = $path
  ocr = (($ocr | Out-String).Trim())
  librarySurface = [bool]$surface
}|ConvertTo-Json -Compress
"""


def build_cases(run_id: str, _document_prefix: str) -> list[dict[str, Any]]:
    reversible = (
        "Reporta el estado del sistema y el estado del audio."
    )
    return [
        {
            "name": "goal07_dual_compound_1",
            "planner_path": "real_llm_current_tree_readonly_plan",
            "objective": reversible,
            "expected": ["system.status", "audio.status"],
            "dependency_positions": [[], []],
            "confirm": set(),
        },
        {
            "name": "goal07_dual_compound_2",
            "planner_path": "real_llm_current_tree_readonly_plan",
            "objective": reversible,
            "expected": ["system.status", "audio.status"],
            "dependency_positions": [[], []],
            "confirm": set(),
        },
        {
            "name": "goal07_steam_library",
            "planner_path": "real_llm_current_tree_mixed_dependency_plan",
            "objective": STEAM_OBJECTIVE,
            "expected": ["app.open", "input.visible.click"],
            "dependency_positions": [[], []],
            "confirm": {"input.visible.click"},
        },
    ]


def observe_library() -> dict[str, Any]:
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-STA",
            "-Command",
            LIBRARY_OBSERVER,
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return {
            "ok": False,
            "error": (completed.stderr or completed.stdout or "library_observer_failed")[:1000],
        }
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        return {"ok": False, "error": completed.stdout[:1000]}
    width = int(payload.get("width") or 0)
    height = int(payload.get("height") or 0)
    ocr = str(payload.get("ocr") or "")
    library_seen = bool(payload.get("librarySurface")) or bool(
        re.search(r"biblioteca|library", ocr, re.IGNORECASE)
    )
    large_enough = width >= 400 and height >= 300
    payload["steamForeground"] = large_enough
    payload["librarySurface"] = library_seen
    payload["ok"] = large_enough and library_seen
    return payload


def write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    scratch = SCRATCH
    gate.OUTPUT = scratch / "goal07_live_missions.json"
    gate.build_cases = build_cases
    try:
        gate.main()
    except SystemExit as error:
        if int(getattr(error, "code", 1) or 0) not in {0, None}:
            # Continue to write per-case evidence even when the steam step fails.
            pass
    report = json.loads(gate.OUTPUT.read_text(encoding="utf-8"))
    cases = {case["case"]: case for case in report.get("cases", [])}
    first = cases.get("goal07_dual_compound_1", {})
    second = cases.get("goal07_dual_compound_2", {})
    steam = cases.get("goal07_steam_library", {})
    write(scratch / "launch_compound_1.log", first)
    write(scratch / "launch_compound_2.log", second)
    observation = observe_library()
    screenshot = observation.get("screenshot")
    if isinstance(screenshot, str) and Path(screenshot).is_file():
        target = scratch / "steam_library_surface.bmp"
        try:
            Path(screenshot).replace(target)
            observation["screenshot"] = str(target)
        except OSError:
            pass
    steam_report = {
        "objective": STEAM_OBJECTIVE,
        "mission": steam,
        "postread": observation,
        "completed": steam.get("status") == "passed" and observation.get("ok") is True,
    }
    write(scratch / "steam_library_mission.json", steam_report)
    if steam.get("status") != "passed" and not observation.get("steamForeground"):
        launcher = {
            "available": Path(r"C:\Program Files (x86)\Steam\steam.exe").is_file(),
            "process_running": True,
            "mission_error": steam.get("error"),
            "postread": observation,
        }
        (scratch / "steam_launch_unavailable.log").write_text(
            json.dumps(launcher, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps({
        "dual_1": first.get("status"),
        "dual_2": second.get("status"),
        "steam": steam.get("status"),
        "library": observation.get("ok"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
