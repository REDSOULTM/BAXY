"""Peripheral domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

USB / HID / game controllers / device manager state vía Get-PnpDevice. Vendor
RGB APIs deferidas (Logitech G HUB, Razer Synapse, Corsair iCUE) — cada
vendor tiene su SDK propio. Disable/Enable PnP requiere admin elevation;
si exit_code != 0, el agente no tiene la privilegio.

Funciones extraídas (7):
  peripheral_tool                    (entry, 7 acciones)
  _peripheral_usb_list
  _peripheral_hid_list
  _peripheral_controller_status      (palabras clave Xbox/Gamepad/Joy-Con...)
  _peripheral_device_problems        (Status != OK)
  _peripheral_run_json               (helper genérico)
  _peripheral_device_toggle          (Disable/Enable con rollback checkpoint)

Helpers desde domain_tools (lazy): _ps_quote."""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from ._shared import _err, _ok
from .tool_result import ToolResult
from .state import AgentState


__all__ = [
    "peripheral_tool",
    "_peripheral_usb_list",
    "_peripheral_hid_list",
    "_peripheral_controller_status",
    "_peripheral_device_problems",
    "_peripheral_run_json",
    "_peripheral_device_toggle",
]


# R4 sprint 2026-05-28: handler migrado a ToolResult con .to_dict().
def _ok_tr(**kw):
    return ToolResult.ok_result(**kw).to_dict()


def _err_tr(msg, **kw):
    return ToolResult.err(msg, **kw).to_dict()


def peripheral_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for USB, HID controllers and device manager state.

    Actions: status, usb_list, hid_list, controller_status,
    device_manager_problems, device_disable, device_enable. Vendor RGB APIs
    are deferred (Logitech/Razer/Corsair each ship their own SDK).
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok_tr(
            powershell=bool(shutil.which("powershell")),
            backend="windows_pnp",
            note="USB/HID via Get-PnpDevice. Vendor RGB profiles are deferred.",
        )
    if action == "usb_list":
        return _peripheral_usb_list(args)
    if action == "hid_list":
        return _peripheral_hid_list(args)
    if action == "controller_status":
        return _peripheral_controller_status()
    if action in {"device_manager_problems", "problems"}:
        return _peripheral_device_problems()
    if action in {"device_disable", "device_enable"}:
        return _peripheral_device_toggle(action, args, state)
    if action in {"rgb_profile_set", "rgb_list", "rgb_set_color"}:
        return _err_tr(
            f"peripheral.{action} is deferred; vendor SDKs (Logitech G HUB, Razer Synapse, Corsair iCUE) each ship their own API/services",
            status="needs_implementation",
            note="If a vendor exposes a stable CLI or HTTP endpoint, we can add a specific binding later.",
        )
    return _err_tr(
        "unknown peripheral action", action=action,
        valid_actions=[
            "status", "usb_list", "hid_list", "controller_status",
            "device_manager_problems", "device_disable", "device_enable",
        ],
        status="needs_user",
    )


def _peripheral_usb_list(args: dict[str, Any]) -> dict[str, Any]:
    only_present = bool(args.get("only_present", True))
    flag = "-PresentOnly" if only_present else ""
    script = f"Get-PnpDevice {flag} | Where-Object {{ $_.Class -eq 'USB' -or $_.Class -eq 'USBDevice' -or $_.InstanceId -like 'USB*' }} | Select-Object FriendlyName,Class,Status,InstanceId,Manufacturer | ConvertTo-Json -Depth 3"
    return _peripheral_run_json(script, "devices")


def _peripheral_hid_list(args: dict[str, Any]) -> dict[str, Any]:
    only_present = bool(args.get("only_present", True))
    flag = "-PresentOnly" if only_present else ""
    script = f"Get-PnpDevice {flag} -Class HIDClass | Select-Object FriendlyName,Class,Status,InstanceId,Manufacturer | ConvertTo-Json -Depth 3"
    return _peripheral_run_json(script, "devices")


def _peripheral_controller_status() -> dict[str, Any]:
    script = r"""
$kw = @('Xbox','Controller','Gamepad','Wheel','DualShock','DualSense','Joystick','Joy-Con')
$matches = Get-PnpDevice -PresentOnly | Where-Object {
  $name = $_.FriendlyName
  foreach ($k in $kw) { if ($name -and $name -match $k) { return $true } }
  return $false
} | Select-Object FriendlyName,Class,Status,InstanceId,Manufacturer
$matches | ConvertTo-Json -Depth 3
"""
    return _peripheral_run_json(script, "controllers")


def _peripheral_device_problems() -> dict[str, Any]:
    script = "Get-PnpDevice -PresentOnly | Where-Object { $_.Status -ne 'OK' } | Select-Object FriendlyName,Class,Status,Problem,ProblemDescription,InstanceId | ConvertTo-Json -Depth 3"
    return _peripheral_run_json(script, "problems")


def _peripheral_run_json(script: str, field: str) -> dict[str, Any]:
    # timeout 20 -> 10s + try/except. Get-PnpDevice puede tardar 2-6s con
    # muchos devices; 10s da headroom 2x.
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return _err_tr("Get-PnpDevice timeout", field=field, reason="powershell_timeout")
    if proc.returncode != 0:
        return _err_tr("Get-PnpDevice failed", stderr=proc.stderr)
    raw = proc.stdout.strip()
    if not raw:
        return _ok_tr(**{field: [], "count": 0})
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err_tr("Get-PnpDevice returned invalid JSON", raw=raw[:500])
    if isinstance(data, dict):
        data = [data]
    return _ok_tr(**{field: data, "count": len(data)})


def _peripheral_device_toggle(action: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .domain_tools_helpers import _ps_quote
    instance_id = str(args.get("instance_id") or args.get("id") or "").strip()
    if not instance_id:
        return _err_tr("missing instance_id (use usb_list/hid_list to find it)")
    verb = "Disable" if action == "device_disable" else "Enable"
    reverse = "device_enable" if action == "device_disable" else "device_disable"
    checkpoint = state.checkpoint(
        f"peripheral {action} {instance_id}",
        rollback=[{"tool": "peripheral", "args": {"action": reverse, "instance_id": instance_id}}],
        metadata={"action": action, "instance_id": instance_id},
    )
    script = f"{verb}-PnpDevice -InstanceId '{_ps_quote(instance_id)}' -Confirm:$false"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30)
    return _ok_tr(
        action=action, instance_id=instance_id,
        exit_code=proc.returncode, stdout=proc.stdout.strip()[:500], stderr=proc.stderr[-2000:],
        checkpoint=checkpoint.get("checkpoint"),
        verified=proc.returncode == 0,
        note="Disable/Enable PnP usually requires admin elevation; if exit_code != 0 the agent likely lacks the privilege.",
    )
