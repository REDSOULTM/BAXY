"""Device settings compound tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Compound entry dispatch para WiFi/Bluetooth/displays/power plans. Las
sub-áreas viven en sus propios módulos hermanos (wifi, bluetooth); acá
quedan display_list y power_plan_* porque son cortos y no justifican otro
archivo.

Funciones extraídas (5):
  device_settings_tool            (entry compound, despacha por action)
  _device_display_list            (WMI desktop monitors + video controllers)
  _device_power_plan_list         (powercfg /list)
  _device_power_plan_get          (powercfg /getactivescheme)
  _device_power_plan_set          (powercfg /setactive + checkpoint+verify)

Sub-actions delegadas a domain_tools_wifi y domain_tools_bluetooth (lazy)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any

from .._shared import _err, _ok
from ..state import AgentState


__all__ = [
    "device_settings_tool",
    "_device_display_list",
    "_device_power_plan_list",
    "_device_power_plan_get",
    "_device_power_plan_set",
]


def device_settings_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for WiFi, Bluetooth, displays and power plans.

    Actions:
      - status
      - wifi_status, wifi_list, wifi_scan, wifi_connect(name), wifi_disconnect
      - bluetooth_status
      - display_list
      - power_plan_list, power_plan_get, power_plan_set(name|guid)
    Toggles for Bluetooth and night_light are deferred: they require either
    elevated service management or fragile registry hacks. Returning
    needs_implementation is the honest answer.
    """
    from .wifi import (
        _device_wifi_add_profile,
        _device_wifi_connect,
        _device_wifi_delete_profile,
        _device_wifi_disconnect,
        _device_wifi_profiles,
        _device_wifi_scan,
        _device_wifi_status,
    )
    from .bluetooth import _device_bluetooth_status

    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            netsh=bool(shutil.which("netsh")),
            powercfg=bool(shutil.which("powercfg")),
            powershell=bool(shutil.which("powershell")),
            note="WiFi via netsh, displays via WMI, power plans via powercfg. Bluetooth toggle and night_light are deferred (needs elevated/registry hacks).",
        )
    if action == "wifi_status":
        return _device_wifi_status()
    if action in {"wifi_list", "wifi_profiles"}:
        return _device_wifi_profiles()
    if action == "wifi_scan":
        return _device_wifi_scan()
    if action == "wifi_connect":
        return _device_wifi_connect(args)
    if action == "wifi_disconnect":
        return _device_wifi_disconnect()
    if action == "bluetooth_status":
        return _device_bluetooth_status()
    if action == "display_list":
        return _device_display_list()
    if action in {"power_plan_list", "power_plans"}:
        return _device_power_plan_list()
    if action == "power_plan_get":
        return _device_power_plan_get()
    if action == "power_plan_set":
        return _device_power_plan_set(args, state)
    if action == "wifi_add_profile":
        return _device_wifi_add_profile(args)
    if action == "wifi_delete_profile":
        return _device_wifi_delete_profile(args)
    if action in {"bluetooth_toggle", "bluetooth_pair", "night_light", "display_set_resolution", "display_set_scale"}:
        return _err(
            f"device_settings.{action} is deferred",
            status="needs_implementation",
            note=(
                "Bluetooth toggle needs Btagservice control or a UWP runtime;"
                " night_light needs a fragile CloudStore registry write;"
                " display resolution needs IADLXDisplayServices or DISPLAY_DEVICE Win32 calls."
            ),
        )
    return _err(
        "unknown device_settings action", action=action,
        valid_actions=[
            "status", "wifi_status", "wifi_profiles", "wifi_scan",
            "wifi_connect", "wifi_disconnect", "wifi_add_profile",
            "wifi_delete_profile", "bluetooth_status", "bluetooth_devices",
            "displays", "display_set_primary",
            "power_plans", "power_plan_active", "power_plan_set",
        ],
        status="needs_user",
    )


def _device_display_list() -> dict[str, Any]:
    script = r"""
$mons = Get-CimInstance -Namespace root\cimv2 -ClassName Win32_DesktopMonitor | Select-Object Name,ScreenWidth,ScreenHeight,DeviceID,Status
$ctrls = Get-CimInstance -ClassName Win32_VideoController | Select-Object Name,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,DriverVersion,VideoModeDescription
[PSCustomObject]@{ monitors=$mons; controllers=$ctrls } | ConvertTo-Json -Depth 4
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("display_list failed", stderr=proc.stderr)
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return _err("display_list returned invalid JSON", raw=proc.stdout[:500])
    return _ok(data=data)


def _device_power_plan_list() -> dict[str, Any]:
    proc = subprocess.run(["powercfg", "/list"], capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        return _err("powercfg /list failed", stderr=proc.stderr)
    plans: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s*\(([^)]+)\)\s*(\*?)", line, re.IGNORECASE)
        if m:
            plans.append({"guid": m.group(1), "name": m.group(2), "active": m.group(3) == "*"})
    return _ok(plans=plans, count=len(plans))


def _device_power_plan_get() -> dict[str, Any]:
    proc = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        return _err("powercfg /getactivescheme failed", stderr=proc.stderr)
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s*\(([^)]+)\)", proc.stdout, re.IGNORECASE)
    if not m:
        return _ok(raw=proc.stdout.strip())
    return _ok(guid=m.group(1), name=m.group(2), active=True)


def _device_power_plan_set(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    target = str(args.get("guid") or args.get("name") or args.get("plan") or "").strip()
    if not target:
        return _err("missing guid or name")
    plans = _device_power_plan_list().get("plans", [])
    chosen = None
    for plan in plans:
        if plan["guid"].casefold() == target.casefold() or target.casefold() in plan["name"].casefold():
            chosen = plan
            break
    if not chosen:
        return _err("power plan not found", target=target, available=[(p["name"], p["guid"]) for p in plans])
    before = _device_power_plan_get()
    checkpoint = state.checkpoint(
        "power plan change",
        rollback=[{"tool": "device_settings", "args": {"action": "power_plan_set", "guid": before.get("guid")}}] if before.get("guid") else [],
        metadata={"before": before, "target": chosen},
    )
    proc = subprocess.run(["powercfg", "/setactive", chosen["guid"]], capture_output=True, text=True, timeout=10)
    after = _device_power_plan_get()
    return _ok(
        target=chosen,
        before=before,
        after=after,
        exit_code=proc.returncode,
        checkpoint=checkpoint.get("checkpoint"),
        verified=proc.returncode == 0 and (after.get("guid") or "").casefold() == chosen["guid"].casefold(),
    )
