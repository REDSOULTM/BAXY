"""Live goal-07 runs: one reversible compound twice, then Steam library."""

from __future__ import annotations

import json
import os
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
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class BaxyFg {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
}
'@
$hwnd=[BaxyFg]::GetForegroundWindow()
$title=New-Object System.Text.StringBuilder 512
[void][BaxyFg]::GetWindowText($hwnd,$title,512)
$procId=0; [void][BaxyFg]::GetWindowThreadProcessId($hwnd,[ref]$procId)
$proc=Get-Process -Id $procId -ErrorAction SilentlyContinue
$names=@()
try {
  $root=[System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
  $all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
  foreach($item in $all){
    try {
      $name=$item.Current.Name
      if($name -and $name -match '(?i)biblioteca|library'){ $names += $name }
    } catch {}
  }
} catch {}
[pscustomobject]@{
  foregroundTitle=$title.ToString()
  processName=$(if($proc){$proc.ProcessName}else{''})
  processPath=$(if($proc){$proc.Path}else{''})
  libraryNames=@($names | Select-Object -Unique -First 12)
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
    names = [str(name) for name in payload.get("libraryNames") or []]
    process = str(payload.get("processName") or "").casefold()
    title = str(payload.get("foregroundTitle") or "")
    steam_foreground = process.startswith("steam")
    library_seen = any(
        "library" in name.casefold() or "biblioteca" in name.casefold()
        for name in names + [title]
    )
    payload["steamForeground"] = steam_foreground
    payload["librarySurface"] = library_seen
    payload["ok"] = steam_foreground and library_seen
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
