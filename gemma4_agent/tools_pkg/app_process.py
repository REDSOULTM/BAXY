"""Gestión de apps/procesos/ventanas a nivel SO: resolver target de un .lnk,
listar procesos vivos, derivar los .exe a cerrar para una app, y cerrar ventanas
por query (con guarda estructural anti-cierre de editores/IDE/terminales/propio
proceso). Extraído de tools.py (split del archivo-dios, 2026-06-19).

Deps en módulos leaf (sin ciclo con tools.py): text_utils, name_match, app_paths;
AppCandidate solo para type-check. tools.py re-exporta estas funciones.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .app_paths import _looks_like_uninstaller
from .name_match import _fold, _score
from .text_utils import _truncate

if TYPE_CHECKING:
    from .app_resolver import AppCandidate


def _shortcut_target(shortcut: Path) -> str | None:
    if not shortcut.is_file() or shortcut.suffix.lower() != ".lnk":
        return None
    env = os.environ.copy()
    env["GEMMA4_SHORTCUT"] = str(shortcut)
    script = r"""
$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:GEMMA4_SHORTCUT)
[PSCustomObject]@{ target=$s.TargetPath; arguments=$s.Arguments; working_directory=$s.WorkingDirectory } | ConvertTo-Json -Depth 3
"""
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=8)
    except Exception:
        return None
    raw = proc.stdout.strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    target = str(data.get("target") or "").strip()
    return target or None


def _running_process_names() -> set[str]:
    """Lista (best-effort) de nombres de proceso vivos (lowercase, con .exe).
    Util para el fast-path de app_close: si ningun candidato esta corriendo,
    evitamos el roundtrip de PowerShell + taskkill que tarda 20s.

    Implementacion priorizada por velocidad:
      1) psutil.process_iter() si esta disponible (~80-150ms, no spawn)
      2) Fallback a `tasklist /FO CSV /NH` con timeout corto (puede tardar
         5-10s en algunos entornos; preferimos no usarlo)
      3) Set vacio (caller cae al flujo lento, equivalente al comportamiento
         previo a esta optimizacion — fail open).
    """
    try:
        import psutil
        out: set[str] = set()
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info.get("name") or ""
                if name:
                    out.add(name.lower())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if out:
            return out
    except Exception:
        pass

    # Fallback subprocess. tasklist puede tardar mucho en algunos hosts
    # (10s+) por razones que no controlamos; lo usamos solo si psutil falla.
    try:
        proc = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if proc.returncode != 0 or not proc.stdout:
        return set()
    out = set()
    for row in csv.reader(proc.stdout.splitlines()):
        if row and row[0]:
            out.add(row[0].strip().lower())
    return out


def _candidate_close_exes(name: str, matches: list[AppCandidate]) -> list[str]:
    candidates: list[str] = []
    query_tokens = [token for token in _fold(name).split() if len(token) >= 3]

    def add(exe: str | None) -> None:
        if not exe:
            return
        exe = Path(exe.strip().strip('"')).name
        if not exe.lower().endswith((".exe", ".com", ".bat", ".cmd")):
            return
        if _looks_like_uninstaller(Path(exe)):
            return
        if exe.casefold() not in {item.casefold() for item in candidates}:
            candidates.append(exe)

    for match in matches:
        score = max(_score(name, match.name), _score(name, Path(match.launch).stem))
        if score < 55:
            continue
        tokens = sorted(set(query_tokens + [token for token in _fold(match.name).split() if len(token) >= 3]))
        launch = Path(match.launch.strip().strip('"'))
        if launch.suffix.lower() == ".lnk":
            target = _shortcut_target(launch)
            add(target)
            target_path = Path(target) if target else None
            if target_path and target_path.parent.is_dir():
                try:
                    for exe in target_path.parent.glob("*.exe"):
                        if exe.stem.casefold().startswith(target_path.stem.casefold()[:4]):
                            add(exe.name)
                except OSError:
                    pass
                install_roots = [target_path.parent, target_path.parent.parent]
                for root in install_roots:
                    if not root or not root.is_dir():
                        continue
                    try:
                        for exe in list(root.glob("*.exe"))[:40]:
                            folded = _fold(f"{exe.stem} {exe.parent.name}")
                            if any(token in folded for token in tokens) or _score(root.name, match.name) >= 70:
                                add(exe.name)
                    except OSError:
                        pass
        elif launch.suffix.lower() == ".exe" and (match.source != "PATH" or score >= 75):
            add(launch.name)
        if match.process_name and (match.source != "PATH" or score >= 75):
            add(match.process_name)

    if name.lower().endswith(".exe"):
        add(name)
    return candidates


def _close_windows_by_query(name: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["GEMMA4_CLOSE_QUERY"] = name
    # GUARDA ESTRUCTURAL (no por intención): nunca cerramos editores/IDE/terminales
    # ni nuestro propio árbol de procesos, AUNQUE el título matchee el query. El bug
    # que motiva esto: el título de VS Code contiene el path del proyecto ("Probando
    # Gemma 4"), así que "cerrá gemma" -> WM_CLOSE a Code.exe y se pierde trabajo sin
    # guardar. Protege por IDENTIDAD del proceso (ProcessName + PID propio/padre),
    # no por una lista de apps-objetivo hardcodeada. Si el usuario realmente quiere
    # cerrar su editor, el match exacto del ProcessName lo permite igual.
    env["GEMMA4_OWN_PID"] = str(os.getpid())
    try:
        env["GEMMA4_PARENT_PID"] = str(os.getppid())
    except Exception:
        env["GEMMA4_PARENT_PID"] = ""
    script = r"""
$q=$env:GEMMA4_CLOSE_QUERY.ToLower()
$ownPid=[int]$env:GEMMA4_OWN_PID
$parentPid = if ($env:GEMMA4_PARENT_PID) { [int]$env:GEMMA4_PARENT_PID } else { 0 }
# Procesos protegidos: editores/IDE/terminales/shell. Se exime SOLO si el query
# matchea EXACTO el ProcessName (intención inequívoca de cerrar esa app puntual);
# un match por substring/título sobre uno de estos NO cierra.
$protected = @('code','code - insiders','codium','vscodium','devenv','rider64',
  'pycharm64','idea64','webstorm64','clion64','sublime_text','atom','notepad++',
  'windowsterminal','wt','powershell','pwsh','cmd','conhost','explorer',
  'python','pythonw','node','claude','git')
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
}
"@
$targets = Get-Process | Where-Object {
  $_.MainWindowTitle -and (
    $_.MainWindowTitle.ToLower().Contains($q) -or
    $_.ProcessName.ToLower().Contains($q)
  )
}
$closed = @()
$skipped = @()
foreach ($p in $targets) {
  $pn = $p.ProcessName.ToLower()
  $isProtected = $protected -contains $pn
  $exactName = ($pn -eq $q)            # el usuario nombró el proceso exacto
  $isSelf = ($p.Id -eq $ownPid) -or ($p.Id -eq $parentPid)
  if ($isSelf -or ($isProtected -and -not $exactName)) {
    $skipped += [PSCustomObject]@{ title=$p.MainWindowTitle; process=$p.ProcessName; pid=$p.Id; reason=$(if($isSelf){'self'}else{'protected'}) }
    continue
  }
  [Win32]::PostMessage($p.MainWindowHandle,0x0010,[IntPtr]::Zero,[IntPtr]::Zero) | Out-Null
  $closed += [PSCustomObject]@{ title=$p.MainWindowTitle; process=$p.ProcessName; pid=$p.Id }
}
[PSCustomObject]@{ count=$closed.Count; windows=$closed; skipped=$skipped } | ConvertTo-Json -Depth 4
"""
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=12)
    except Exception as exc:
        return {"count": 0, "error": f"{type(exc).__name__}: {exc}"}
    if not proc.stdout.strip():
        return {"count": 0, "stderr": _truncate(proc.stderr.strip(), 1000)}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"count": 0, "stdout": _truncate(proc.stdout.strip(), 1000), "stderr": _truncate(proc.stderr.strip(), 1000)}
    return data if isinstance(data, dict) else {"count": 0, "data": data}
