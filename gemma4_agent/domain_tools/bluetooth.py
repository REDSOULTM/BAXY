"""Bluetooth domain tool — extracted from domain_tools.py.

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

from .._shared import _err, _ok


__all__ = ["_device_bluetooth_status"]


# Handler migrado a ToolResult (con  para back-compat). Comportamiento
# idéntico al _ok/_err anterior.
_BT_CACHE: "dict[str, tuple]" = {}


def _device_bluetooth_status(refresh: bool = False) -> dict[str, Any]:
    # LATENCIA (MEDIDO 2026-06-09): hace DOS spawns de PowerShell (Get-PnpDevice +
    # Get-Service) ~2s. El estado BT no cambia seguido -> cache TTL 60s; `refresh`
    # lo revalida. Solo lectura (status), no toca el adaptador.
    import time as _t
    _now = _t.time()
    if not refresh:
        _c = _BT_CACHE.get("status")
        if _c and (_now - _c[0]) < 60.0:
            _r = dict(_c[1]); _r["cached"] = True
            return _r
    res = _device_bluetooth_status_uncached()
    if isinstance(res, dict) and res.get("ok") is not False:
        _BT_CACHE["status"] = (_now, res)
    return res


def _device_bluetooth_status_uncached() -> dict[str, Any]:
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
