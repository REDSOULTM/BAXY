"""Dispositivos de audio: listar endpoints, fijar/restaurar el default, y
helpers de SoundVolumeView (svv). Extraído de domain_tools/__init__.py (ratchet
anti-archivo-dios, patrón sibling+shim). Sin ciclo: importa _ok/_err de _shared,
_find_soundvolumeview/_powershell_json de .helpers, y recibe AgentState por param.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .._shared import _ok, _err
from ..memory_pkg.state import AgentState
from .helpers import _find_soundvolumeview, _powershell_json

def _audio_endpoints() -> list[dict[str, Any]]:
    script = "Get-PnpDevice -Class AudioEndpoint | Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Depth 3"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    return data if isinstance(data, list) else []


# _find_soundvolumeview — extraído a domain_tools_helpers.py.


def _set_default_audio_device(args: dict[str, Any], state: AgentState, *, communications: bool) -> dict[str, Any]:
    name = str(args.get("name") or args.get("device") or "").strip()
    if not name:
        return _err("missing device name")
    helper = _find_soundvolumeview()
    if not helper:
        return _err(
            "setting default audio device needs SoundVolumeView or a custom WASAPI policy helper",
            requested=name,
            status="needs_dependency",
            verified=False,
            completion_status="needs_dependency",
            install_hint="Download SoundVolumeView.zip from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW to its exe path.",
        )

    devices_before = _svv_list_devices()
    target = _svv_find_device(devices_before, name)
    if not target:
        return _err(
            "audio device not found",
            requested=name,
            available=[d.get("Name") or d.get("Device Name") for d in devices_before],
            status="needs_user",
            verified=False,
        )

    defaults_before = _svv_current_defaults(devices_before)
    rollback = _audio_rollback_steps(defaults_before)
    checkpoint = state.checkpoint(
        "audio default device change",
        rollback=rollback,
        metadata={
            "requested": name,
            "helper": str(helper),
            "communications": communications,
            "defaults_before": defaults_before,
            "device_before": target.get("Name") or target.get("Device Name"),
        },
    )

    # Role mapping (SoundVolumeView): 0=Console, 1=Multimedia, 2=Communications.
    roles = ["2"] if communications else ["0", "1"]
    role_names = {"0": "Console", "1": "Multimedia", "2": "Communications"}
    results = []
    for role in roles:
        proc = subprocess.run(
            [str(helper), "/SetDefault", name, role],
            capture_output=True, text=True, timeout=20,
        )
        results.append({
            "role": role,
            "role_name": role_names.get(role, role),
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        })

    devices_after = _svv_list_devices()
    defaults_after = _svv_current_defaults(devices_after)
    expected_roles = ["Communications"] if communications else ["Console", "Multimedia"]
    verified = _audio_verify_default(defaults_after, name, expected_roles)
    return _ok(
        requested=name,
        helper=str(helper),
        roles=roles,
        results=results,
        defaults_before=defaults_before,
        defaults_after=defaults_after,
        checkpoint=checkpoint.get("checkpoint"),
        verified=verified,
        status="done" if verified else "needs_verification",
        evidence={"defaults_before": defaults_before, "defaults_after": defaults_after, "exit_codes": [r["exit_code"] for r in results]},
    )


def _restore_audio_default(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    checkpoint_id = str(args.get("checkpoint_id") or args.get("snapshot") or "").strip()
    data = state._load()
    checkpoints = data.get("checkpoints", {})
    checkpoint = None
    if checkpoint_id and checkpoint_id in checkpoints:
        checkpoint = checkpoints[checkpoint_id]
    else:
        # latest audio snapshot
        for cp in reversed(list(checkpoints.values())):
            if "audio" in str(cp.get("label", "")).casefold():
                checkpoint = cp
                break
    if not checkpoint:
        return _err("no audio checkpoint available; create one with audio_device(action=snapshot) first")

    helper = _find_soundvolumeview()
    if not helper:
        return _err(
            "audio_device.restore requires SoundVolumeView",
            status="needs_dependency",
            verified=False,
            install_hint="Download SoundVolumeView.zip from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW.",
        )
    defaults = checkpoint.get("metadata", {}).get("defaults") or {}
    if not defaults:
        return _err("checkpoint has no defaults to restore", checkpoint_id=checkpoint.get("id"))

    role_to_int = {"Console": "0", "Multimedia": "1", "Communications": "2"}
    results = []
    for role_name, device_name in defaults.items():
        role_int = role_to_int.get(role_name)
        if not role_int or not device_name:
            continue
        proc = subprocess.run(
            [str(helper), "/SetDefault", device_name, role_int],
            capture_output=True, text=True, timeout=20,
        )
        results.append({
            "role": role_name,
            "device": device_name,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        })
    devices_after = _svv_list_devices()
    defaults_after = _svv_current_defaults(devices_after)
    verified = all(defaults_after.get(role) == device for role, device in defaults.items() if device)
    return _ok(
        restored_from=checkpoint.get("id"),
        defaults_requested=defaults,
        defaults_after=defaults_after,
        results=results,
        verified=verified,
        status="done" if verified else "needs_verification",
    )


def _svv_list_devices() -> list[dict[str, Any]]:
    """Use SoundVolumeView /sjson to dump full device table."""
    helper = _find_soundvolumeview()
    if not helper:
        return []
    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="svv_")
    os.close(fd)
    try:
        proc = subprocess.run(
            [str(helper), "/sjson", tmp_path],
            capture_output=True, text=True, timeout=20,
        )
        if proc.returncode != 0:
            return []
        raw = Path(tmp_path).read_text(encoding="utf-16", errors="replace").lstrip("﻿").strip()
        if not raw:
            # SoundVolumeView sometimes writes utf-8; retry.
            raw = Path(tmp_path).read_text(encoding="utf-8", errors="replace").lstrip("﻿").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _svv_current_defaults(devices: list[dict[str, Any]]) -> dict[str, str]:
    """Read per-role default from SoundVolumeView output.

    The /sjson dump has a 'Default' column with values like 'Render', 'Capture'
    or empty, plus a 'Default Multimedia', 'Default Communications' set in some
    versions. We prefer the columns 'Default' and 'Default Multimedia' /
    'Default Communications' when present, otherwise we fall back to the
    composite 'Default' string.
    """
    defaults: dict[str, str] = {}
    for dev in devices:
        if not isinstance(dev, dict):
            continue
        name = str(dev.get("Name") or dev.get("Device Name") or "").strip()
        if not name:
            continue
        direction = str(dev.get("Direction") or "").strip()
        if direction and direction.casefold() != "render":
            # Only render devices count for default playback roles here.
            # Recording defaults are mirrored under same columns; the role
            # name itself disambiguates downstream consumers.
            pass
        for role, column in (("Console", "Default"), ("Multimedia", "Default Multimedia"), ("Communications", "Default Communications")):
            value = str(dev.get(column) or "").strip().casefold()
            if value in {"render", "capture", "yes", "true", "1"}:
                # Only set if not already taken (first device wins for the role).
                defaults.setdefault(role, name)
    # Some SoundVolumeView builds collapse roles into a single "Default" column
    # carrying values like "Render;Multimedia". Handle that fallback.
    if not defaults:
        for dev in devices:
            if not isinstance(dev, dict):
                continue
            name = str(dev.get("Name") or dev.get("Device Name") or "").strip()
            raw = str(dev.get("Default") or "").strip().casefold()
            if not name or not raw:
                continue
            if "render" in raw or "capture" in raw:
                defaults.setdefault("Console", name)
                defaults.setdefault("Multimedia", name)
    return defaults


def _svv_find_device(devices: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    q = query.casefold().strip()
    if not q:
        return None
    # Exact match first
    for dev in devices:
        for key in ("Name", "Device Name", "Item ID"):
            if str(dev.get(key) or "").casefold() == q:
                return dev
    # Substring match second
    for dev in devices:
        for key in ("Name", "Device Name", "Item ID"):
            if q in str(dev.get(key) or "").casefold():
                return dev
    return None


def _audio_rollback_steps(defaults: dict[str, str]) -> list[dict[str, Any]]:
    """Build a list of {tool, args} rollback steps for the checkpoint."""
    steps: list[dict[str, Any]] = []
    if not defaults:
        return steps
    # Group Console+Multimedia under a single set_default (covers roles 0,1).
    normal_device = defaults.get("Multimedia") or defaults.get("Console")
    if normal_device:
        steps.append({"tool": "audio_device", "args": {"action": "set_default", "name": normal_device}})
    comm_device = defaults.get("Communications")
    if comm_device and comm_device != normal_device:
        steps.append({"tool": "audio_device", "args": {"action": "set_default_communications", "name": comm_device}})
    return steps


def _audio_verify_default(defaults_after: dict[str, str], requested_name: str, expected_roles: list[str]) -> bool:
    """Return True if the requested device matches all expected roles."""
    if not defaults_after:
        return False
    q = requested_name.casefold().strip()
    for role in expected_roles:
        current = str(defaults_after.get(role) or "").casefold()
        if not current:
            return False
        if q not in current and current not in q:
            return False
    return True


# Notification helpers - extraídos a domain_tools_notifications.py.
# Los 9 helpers + _NotificationDueError + _notification_due
# (parsing NL) viven ahora afuera; el re-export está en el bloque del entry
# point notification_tool más arriba (líneas ~263).


# Cross-cutting helpers (_find_routine, _update_resource_metadata,
# _resources_by_kind, _find_resource, _powershell_json, _ps_quote) — extraídos
# a domain_tools_helpers.py. El re-export más arriba
# del módulo (debajo del import de _ok/_err) deja `dt._X` accesible para los
# callers que hacen `from gemma4_agent import domain_tools as dt`. Estos
# bloques quedan como ancla histórica.


# Dependency catalog helpers - extraídos a domain_tools_dependency.py.


# Calendar helpers (ICS export utils) - extraídos a domain_tools_calendar.py.
# Los 4 helpers (_calendar_export_path, _events_to_ics,
# _ics_time, _ics_escape) viven junto al resto del calendar; el re-export está
# en el bloque del entry point más arriba.


def _run_detached_powershell(script: str) -> dict[str, Any]:
    proc = subprocess.Popen(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return {"pid": proc.pid}
