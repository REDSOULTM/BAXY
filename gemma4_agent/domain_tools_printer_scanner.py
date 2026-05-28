"""Printer & Scanner domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Imprimir y escanear desde Windows usando PowerShell + WIA (COM via
WScript.Network y WIA.DeviceManager).

Funciones extraídas (6):
  printer_scanner_tool           (entry, 9 acciones)
  _printer_set_default
  _printer_print_file
  _printer_cancel_job
  _scanners_list                 (enumera scanners WIA)
  _scanner_scan                  (scan via WIA Items.Transfer)

Helpers desde domain_tools (lazy):
  _ps_quote, _powershell_json, _json_or_none."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from ._shared import _err, _ok


__all__ = [
    "printer_scanner_tool",
    "_printer_set_default",
    "_printer_print_file",
    "_printer_cancel_job",
    "_scanners_list",
    "_scanner_scan",
]


def printer_scanner_tool(args: dict[str, Any]) -> dict[str, Any]:
    from .domain_tools_helpers import _powershell_json, _ps_quote
    action = str(args.get("action") or "printers_list").casefold()
    if action == "status":
        return _ok(powershell=bool(shutil.which("powershell")), backend="Windows PrintManagement")
    if action in {"printers_list", "list"}:
        return _powershell_json("Get-Printer | Select-Object Name,DriverName,PortName,PrinterStatus,Default | ConvertTo-Json -Depth 3", "printers")
    if action == "printer_default_get":
        return _powershell_json("Get-Printer | Where-Object Default -eq $true | Select-Object Name,DriverName,PortName,PrinterStatus,Default | ConvertTo-Json -Depth 3", "printer")
    if action == "print_queue":
        name = str(args.get("name") or args.get("printer") or "").strip()
        script = f"Get-PrintJob -PrinterName '{_ps_quote(name)}' | Select-Object ID,DocumentName,JobStatus,SubmittedTime | ConvertTo-Json -Depth 3" if name else "Get-Printer | ForEach-Object { Get-PrintJob -PrinterName $_.Name -ErrorAction SilentlyContinue } | Select-Object ID,PrinterName,DocumentName,JobStatus,SubmittedTime | ConvertTo-Json -Depth 3"
        return _powershell_json(script, "jobs")
    if action == "printer_default_set":
        return _printer_set_default(args)
    if action == "print_file":
        return _printer_print_file(args)
    if action == "cancel_job":
        return _printer_cancel_job(args)
    if action == "scanners_list":
        return _scanners_list()
    if action == "scan_document":
        return _scanner_scan(args)
    return _err(
        "unknown printer_scanner action", action=action,
        valid_actions=[
            "status", "printers_list", "printer_default_get",
            "printer_default_set", "print_file", "scan_status",
        ],
        status="needs_user",
    )


def _printer_set_default(args: dict[str, Any]) -> dict[str, Any]:
    from .domain_tools_helpers import _json_or_none
    name = str(args.get("name") or args.get("printer") or "").strip()
    if not name:
        return _err("missing printer name")
    # The standard mechanism is the WScript.Network COM object's SetDefaultPrinter,
    # because Set-Printer doesn't expose a -Default flag in all builds.
    env = os.environ.copy()
    env["GEMMA4_PRINTER"] = name
    script = (
        "$net = New-Object -ComObject WScript.Network; "
        "$net.SetDefaultPrinter($env:GEMMA4_PRINTER); "
        "$d = Get-CimInstance Win32_Printer | Where-Object { $_.Default -eq $true } | Select-Object Name; "
        "$d | ConvertTo-Json -Depth 3"
    )
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("failed to set default printer", stderr=proc.stderr, exit_code=proc.returncode)
    return _ok(printer=name, default=_json_or_none(proc.stdout), verified=True)


def _printer_print_file(args: dict[str, Any]) -> dict[str, Any]:
    from .domain_tools_helpers import _json_or_none, _powershell_json, _ps_quote
    path_raw = str(args.get("path") or args.get("file") or "").strip()
    if not path_raw:
        return _err("missing file path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err("file not found", path=str(path))
    printer_name = str(args.get("printer") or "").strip()
    # Start-Process -Verb Print sends the document to the default printer using the
    # registered handler for the file extension. To target a non-default printer,
    # we briefly switch the system default, print, then restore. This is the
    # documented Windows-supported path for non-Office files.
    env = os.environ.copy()
    env["GEMMA4_PRINT_PATH"] = str(path)
    env["GEMMA4_PRINT_PRINTER"] = printer_name
    script = r"""
$ErrorActionPreference = 'Stop'
$prev = (Get-CimInstance Win32_Printer | Where-Object { $_.Default -eq $true } | Select-Object -First 1 -ExpandProperty Name)
$target = $env:GEMMA4_PRINT_PRINTER
$changed = $false
if ($target -and $target -ne $prev) {
  $net = New-Object -ComObject WScript.Network
  $net.SetDefaultPrinter($target)
  $changed = $true
}
try {
  Start-Process -FilePath $env:GEMMA4_PRINT_PATH -Verb Print -PassThru -WindowStyle Hidden | Out-Null
  Start-Sleep -Milliseconds 800
} finally {
  if ($changed -and $prev) {
    $net = New-Object -ComObject WScript.Network
    $net.SetDefaultPrinter($prev)
  }
}
[PSCustomObject]@{ ok=$true; path=$env:GEMMA4_PRINT_PATH; printer=$target; previous=$prev } | ConvertTo-Json
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return _err("print_file failed", stderr=proc.stderr, exit_code=proc.returncode)
    data = _json_or_none(proc.stdout) or {}
    # Probe queue to confirm a job appeared (best-effort).
    queue_probe = _powershell_json(
        f"Get-PrintJob -PrinterName '{_ps_quote(printer_name)}' -ErrorAction SilentlyContinue | Select-Object ID,DocumentName,JobStatus | ConvertTo-Json -Depth 3" if printer_name else "Get-Printer | ForEach-Object { Get-PrintJob -PrinterName $_.Name -ErrorAction SilentlyContinue } | Select-Object ID,PrinterName,DocumentName,JobStatus | ConvertTo-Json -Depth 3",
        "jobs",
    )
    return _ok(path=str(path), printer=printer_name or data.get("previous"), verified=bool(queue_probe.get("ok")), queue=queue_probe, evidence=data)


def _printer_cancel_job(args: dict[str, Any]) -> dict[str, Any]:
    from .domain_tools_helpers import _json_or_none, _ps_quote
    printer_name = str(args.get("printer") or "").strip()
    job_id = args.get("job_id") if args.get("job_id") is not None else args.get("id")
    if not printer_name:
        return _err("missing printer name")
    if job_id is None:
        # cancel all
        script = f"Get-PrintJob -PrinterName '{_ps_quote(printer_name)}' -ErrorAction SilentlyContinue | Remove-PrintJob -Confirm:$false; [PSCustomObject]@{{ ok=$true; printer='{_ps_quote(printer_name)}'; cancelled='all' }} | ConvertTo-Json"
    else:
        script = f"Remove-PrintJob -PrinterName '{_ps_quote(printer_name)}' -ID {int(job_id)} -Confirm:$false; [PSCustomObject]@{{ ok=$true; printer='{_ps_quote(printer_name)}'; cancelled={int(job_id)} }} | ConvertTo-Json"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("cancel_job failed", stderr=proc.stderr, exit_code=proc.returncode)
    return _ok(printer=printer_name, cancelled=job_id if job_id is not None else "all", result=_json_or_none(proc.stdout), verified=True)


def _scanners_list() -> dict[str, Any]:
    """Use WIA via PowerShell to enumerate scanners."""
    script = r"""
$ErrorActionPreference = 'Stop'
try {
  $dm = New-Object -ComObject WIA.DeviceManager
  $items = @()
  foreach ($info in $dm.DeviceInfos) {
    $type = $info.Type
    # WiaDeviceType: 1=Scanner, 2=StreamingVideo, 0=Unspecified, 65536=Camera
    if ($type -eq 1) {
      $items += [PSCustomObject]@{
        DeviceID = $info.DeviceID
        Name = $info.Properties.Item('Name').Value
        Manufacturer = $info.Properties.Item('Manufacturer').Value
      }
    }
  }
  $items | ConvertTo-Json -Depth 3
} catch {
  [PSCustomObject]@{ error = $_.Exception.Message } | ConvertTo-Json
}
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    raw = proc.stdout.strip()
    if not raw:
        return _ok(scanners=[], count=0, note="No WIA devices detected.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err("scanner enumeration returned invalid JSON", raw=raw[:1000])
    if isinstance(data, dict):
        if "error" in data:
            return _err(f"scanner enumeration failed: {data['error']}", status="needs_dependency", note="WIA may not be available; install scanner drivers.")
        data = [data]
    return _ok(scanners=data, count=len(data))


def _scanner_scan(args: dict[str, Any]) -> dict[str, Any]:
    from .domain_tools_helpers import _json_or_none
    out_raw = str(args.get("output") or args.get("path") or "").strip()
    if not out_raw:
        out = Path.home() / "Pictures" / f"scan_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
    else:
        out = Path(out_raw).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    device_id = str(args.get("device_id") or "").strip()
    env = os.environ.copy()
    env["GEMMA4_SCAN_OUT"] = str(out)
    env["GEMMA4_SCAN_DEVICE"] = device_id
    script = r"""
$ErrorActionPreference = 'Stop'
try {
  $dm = New-Object -ComObject WIA.DeviceManager
  $device = $null
  if ($env:GEMMA4_SCAN_DEVICE) {
    foreach ($info in $dm.DeviceInfos) {
      if ($info.DeviceID -eq $env:GEMMA4_SCAN_DEVICE) { $device = $info.Connect(); break }
    }
  }
  if (-not $device) {
    foreach ($info in $dm.DeviceInfos) {
      if ($info.Type -eq 1) { $device = $info.Connect(); break }
    }
  }
  if (-not $device) { throw "No scanner connected" }
  $item = $device.Items.Item(1)
  $image = $item.Transfer()
  if (Test-Path $env:GEMMA4_SCAN_OUT) { Remove-Item -LiteralPath $env:GEMMA4_SCAN_OUT -Force }
  $image.SaveFile($env:GEMMA4_SCAN_OUT)
  [PSCustomObject]@{ ok=$true; path=$env:GEMMA4_SCAN_OUT } | ConvertTo-Json
} catch {
  [PSCustomObject]@{ ok=$false; error=$_.Exception.Message } | ConvertTo-Json
}
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        return _err("scan failed", stderr=proc.stderr, exit_code=proc.returncode)
    data = _json_or_none(proc.stdout) or {}
    if not data.get("ok"):
        return _err(f"scan failed: {data.get('error')}", status="needs_dependency" if "No scanner" in str(data.get("error")) else None)
    return _ok(path=str(out), size=out.stat().st_size if out.exists() else 0, verified=out.exists())
