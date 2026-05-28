"""Bluetooth domain tool — extracted from domain_tools.py (R2 sprint 2026-05-27).

Por ahora una sola función pero la pongo en su propio módulo para mantener el
patrón 1-área-1-archivo (cuando montemos sub-paquete domain_tools/ proper, todo
ya está separado). Si después aparecen más operaciones de bluetooth (pair,
disconnect, audio-routing), van acá.

Usa PowerShell (Get-PnpDevice + Get-Service bthserv) en vez de netsh porque
Bluetooth no tiene CLI tan limpia como wifi."""
from __future__ import annotations

import json
import subprocess
from typing import Any

from ._shared import _err, _ok


__all__ = ["_device_bluetooth_status"]


def _device_bluetooth_status() -> dict[str, Any]:
    script = (
        "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | "
        "Select-Object FriendlyName,Status,Class,InstanceId | ConvertTo-Json -Depth 3"
    )
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("bluetooth status query failed", stderr=proc.stderr)
    raw = proc.stdout.strip()
    if not raw:
        return _ok(devices=[], count=0, note="No Bluetooth class devices found.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err("bluetooth status returned invalid JSON", raw=raw[:500])
    if isinstance(data, dict):
        data = [data]
    # Also check the Bluetooth Support Service for radio state.
    svc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Service bthserv -ErrorAction SilentlyContinue | Select-Object Status,Name,StartType | ConvertTo-Json"],
        capture_output=True, text=True, timeout=10,
    )
    service_info = None
    if svc.returncode == 0 and svc.stdout.strip():
        try:
            service_info = json.loads(svc.stdout)
        except json.JSONDecodeError:
            pass
    return _ok(devices=data, count=len(data), bthserv=service_info)
