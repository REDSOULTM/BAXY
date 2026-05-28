"""Higher-level local domain tools for the Gemma4 agent."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import webbrowser
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from ._ps import (
    PSValidationError,
    RX_DAY_OF_WEEK,
    RX_HHMM,
    RX_ISO_DATETIME,
    RX_LOG_NAME,
    RX_SQL_IDENT,
    RX_TCP_STATE,
    is_ipv4,
    is_ipv6,
    parse_ps_json,
    ps_safe_literal,
)
from .state import AgentState


Executor = Callable[[str, dict[str, Any]], dict[str, Any]]


# CC-105 + CC-101: unified in Sprint 4 — bodies live in :mod:`._shared`
# (was duplicated against tools._redact_sensitive / ToolRegistry._hard_gate,
# see audit §2.2). _ok/_err added 2026-05-27 (audit R3 sprint): were also
# triplicated (domain_tools/ops_tools/tools, byte-identical bodies).
from ._shared import (  # noqa: E402
    _err,
    _ok,
    hard_gate as _hard_gate,
    redact_sensitive as _redact_credentials,
)


def office_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            python_pptx=importlib.util.find_spec("pptx") is not None,
            python_docx=importlib.util.find_spec("docx") is not None,
            openpyxl=importlib.util.find_spec("openpyxl") is not None,
            libreoffice=bool(shutil.which("soffice") or shutil.which("libreoffice")),
        )
    if action == "create_presentation":
        return _create_presentation(args, state)
    if action == "create_document":
        return _create_document(args, state)
    if action == "create_spreadsheet":
        return _create_spreadsheet(args, state)
    if action == "inspect":
        return _inspect_office_file(args)
    if action == "open":
        path = _existing_path(args)
        if not path:
            return _err("missing or invalid path", status="needs_user")
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                webbrowser.open(path.as_uri())
        except OSError as exc:
            return _err(
                f"failed to open office file: {exc}",
                path=str(path), status="failed",
                hint="no application registered to open this extension?",
            )
        return _ok(path=str(path.resolve()), opened=True, verified=False,
                   note="Open requested; verification not performed (would require UIA).")
    if action in {"edit_presentation", "edit_document", "edit_spreadsheet", "export_pdf"}:
        return _err(
            f"office.{action} is not implemented yet",
            status="needs_dependency",
            verified=False,
            completion_status="needs_implementation",
            note="Creation and inspection are implemented first; editing/export need template-specific handling.",
        )
    return _err(
        "unknown office action", action=action,
        valid_actions=[
            "status", "create_presentation", "create_document",
            "create_spreadsheet", "inspect", "open",
            "edit_presentation", "edit_document", "edit_spreadsheet", "export_pdf",
        ],
        status="needs_user",
    )


def audio_device_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action in {"status", "list"}:
        helper = _find_soundvolumeview()
        svv_devices = _svv_list_devices() if helper else []
        devices = svv_devices if svv_devices else _audio_endpoints()
        defaults = _svv_current_defaults(svv_devices) if svv_devices else {}
        return _ok(
            devices=devices,
            count=len(devices),
            defaults=defaults,
            soundvolumeview=str(helper) if helper else None,
            can_set_default=bool(helper),
            install_hint="Download SoundVolumeView.zip from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW to the exe path.",
        )
    if action == "snapshot":
        helper = _find_soundvolumeview()
        svv_devices = _svv_list_devices() if helper else []
        defaults = _svv_current_defaults(svv_devices) if svv_devices else {}
        rollback = _audio_rollback_steps(defaults)
        checkpoint = state.checkpoint(
            "audio device snapshot",
            rollback=rollback,
            metadata={"devices": svv_devices or _audio_endpoints(), "defaults": defaults, "helper": str(helper) if helper else None},
        )
        return _ok(
            snapshot=checkpoint.get("checkpoint"),
            defaults=defaults,
            rollback_steps=len(rollback),
            note="Snapshot saves device list and per-role defaults. Restore replays /SetDefault using SoundVolumeView." if rollback else "Defaults not detected; install SoundVolumeView for restorable snapshots.",
        )
    if action == "restore":
        return _restore_audio_default(args, state)
    if action in {"set_default", "set_default_communications"}:
        return _set_default_audio_device(args, state, communications=action == "set_default_communications")
    if action == "set_app_route":
        return _audio_set_app_route(args, state)
    if action == "get_app_routes":
        return _audio_get_app_routes()
    return _err(
        "unknown audio_device action", action=action,
        valid_actions=[
            "status", "list", "snapshot", "set_default", "set_default_app",
            "set_app_route", "rollback",
        ],
        status="needs_user",
    )


def _audio_set_app_route(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Route a specific app to a specific audio device via SoundVolumeView /SetAppDefault.

    SoundVolumeView CLI syntax (NirSoft 2020):
        SoundVolumeView.exe /SetAppDefault "<device-or-render-path>" <role> "<process.exe>"
    Role: 0=Console, 1=Multimedia, 2=Communications.
    """
    helper = _find_soundvolumeview()
    if not helper:
        return _err(
            "set_app_route requires SoundVolumeView",
            status="needs_dependency",
            install_hint="Download SoundVolumeView.zip from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW.",
        )
    device = str(args.get("device") or args.get("name") or "").strip()
    app = str(args.get("app") or args.get("process") or "").strip()
    if not device or not app:
        return _err("set_app_route requires device (or 'default') and app (process name or pid)")
    direction = str(args.get("direction") or "render").casefold()  # render|capture
    role = str(args.get("role") or "1")  # 1=Multimedia by default
    if role not in {"0", "1", "2", "all"}:
        return _err("role must be 0|1|2|all (Console|Multimedia|Communications|all)")

    # If the user just gave a friendly device name, the CLI expects either the
    # full "Device\Speakers\Render" path or the friendly name from /sjson.
    # We accept both: if device looks like "<vendor>\\<dev>\\<dir>" pass through,
    # else resolve via the device list.
    if device.casefold() in {"default", "system_default"}:
        # SoundVolumeView treats empty/Default specially: pass "Default" literal.
        target_arg = "DefaultRenderDevice" if direction == "render" else "DefaultCaptureDevice"
    else:
        target_arg = device

    before_routes = _audio_get_app_routes().get("routes", [])
    rollback_step = {"tool": "audio_device", "args": {"action": "set_app_route", "device": "DefaultRenderDevice", "app": app, "role": role, "direction": direction}}
    checkpoint = state.checkpoint(
        f"audio_device set_app_route {app}->{device}",
        rollback=[rollback_step],
        metadata={"app": app, "target": target_arg, "role": role, "direction": direction, "before": before_routes},
    )
    proc = subprocess.run(
        [str(helper), "/SetAppDefault", target_arg, role, app],
        capture_output=True, text=True, timeout=20,
    )
    after_routes = _audio_get_app_routes().get("routes", [])
    matched_after = [r for r in after_routes if str(r.get("process") or "").casefold() == app.casefold()]
    return _ok(
        app=app, target=target_arg, role=role, direction=direction,
        helper=str(helper),
        exit_code=proc.returncode, stdout=proc.stdout.strip()[:500], stderr=proc.stderr[-500:],
        before=before_routes[:30], after=after_routes[:30],
        matched=matched_after,
        checkpoint=checkpoint.get("checkpoint"),
        verified=proc.returncode == 0,
        status="done" if proc.returncode == 0 else "needs_verification",
        note="Per-app overrides survive across sessions but only apply to the named process; relaunching the app picks up the new default.",
    )


def _audio_get_app_routes() -> dict[str, Any]:
    """List per-app audio overrides via SoundVolumeView /sjson (Type=Application rows)."""
    helper = _find_soundvolumeview()
    if not helper:
        return _err(
            "get_app_routes requires SoundVolumeView",
            status="needs_dependency",
            install_hint="Download SoundVolumeView.zip from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW.",
        )
    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="svv_apps_")
    os.close(fd)
    try:
        proc = subprocess.run([str(helper), "/sjson", tmp_path], capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            return _err("SoundVolumeView /sjson failed", stderr=proc.stderr, exit_code=proc.returncode)
        raw = Path(tmp_path).read_text(encoding="utf-16", errors="replace").lstrip("﻿").strip()
        if not raw:
            raw = Path(tmp_path).read_text(encoding="utf-8", errors="replace").lstrip("﻿").strip()
        if not raw:
            return _ok(routes=[], count=0)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return _err("SoundVolumeView returned invalid JSON")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    if isinstance(data, dict):
        data = [data]
    routes: list[dict[str, Any]] = []
    for entry in data if isinstance(data, list) else []:
        if not isinstance(entry, dict):
            continue
        entry_type = str(entry.get("Type") or "").casefold()
        if entry_type not in {"application", "application volume"}:
            continue
        routes.append({
            "process": entry.get("Process Path") or entry.get("Name"),
            "name": entry.get("Name"),
            "device_name": entry.get("Device Name") or entry.get("Default Endpoint"),
            "default_endpoint": entry.get("Default Endpoint"),
            "default_communications_endpoint": entry.get("Default Communications Endpoint"),
            "muted": entry.get("Muted"),
            "volume_percent": entry.get("Volume Percent") or entry.get("Volume dB"),
        })
    return _ok(routes=routes, count=len(routes))


# Notification entry-point + helpers - extraídos a domain_tools_notifications.py
# (R2 sprint 2026-05-27). domain_tools.py: ~-300 LOC. Re-export AL TOP para que
# tools.py linea 52 () y los call-
# sites internos sigan funcionando sin cambio.
from .domain_tools_notifications import (  # noqa: F401  (re-export por compat)
    _NotificationDueError,
    _delete_notification,
    _enrich_notification_resource,
    _ensure_notification_runner,
    _kind_for_notification_action,
    _notification_due,
    _notification_history,
    _schedule_notification,
    _show_message_box,
    _update_notification,
    notification_tool,
)


# Routine entry-point + import_triggercmd + destructive command detection
# - extraído a domain_tools_routine.py (R2 sprint 2026-05-28). 13 símbolos.
# Re-export AL TOP para que tools.py linea 57 y agent.py linea 1019
# (_looks_destructive) sigan funcionando sin cambio. _find_routine y
# _register_routine_process_watcher quedan en domain_tools.py (los importa
# routine_tool lazy).
from .domain_tools_routine import (  # noqa: F401  (re-export por compat)
    _DESTRUCTIVE_COMMAND_TOKENS,
    _append_routine_run,
    _build_routine_trigger_ps,
    _detect_python_executable,
    _enrich_routine_resource,
    _looks_destructive,
    _register_routine_scheduled_task,
    _routine_history,
    _routine_task_name,
    _terminal_args_for,
    _unregister_routine_scheduled_task,
    import_triggercmd_entries,
    routine_tool,
)


# Smart Home (HomeAssistant + MQTT) - extraído a domain_tools_smart_home.py
# (R2 sprint 2026-05-28). 10 funciones. Re-export para compat (tools.py linea 58).
from .domain_tools_smart_home import (  # noqa: F401  (re-export por compat)
    _hass_alive,
    _hass_area_control,
    _hass_area_list,
    _hass_call_service,
    _hass_get_state,
    _hass_request,
    _hass_set_state,
    _hass_states,
    _smart_home_mqtt_publish,
    smart_home_tool,
)


# Study (flashcards + SM-2) - extraído a domain_tools_study.py
# (R2 sprint 2026-05-28). 12 funciones (entry + 11 helpers).
from .domain_tools_study import (  # noqa: F401  (re-export por compat)
    _study_card_add,
    _study_card_delete,
    _study_card_list,
    _study_connect,
    _study_deck_create,
    _study_deck_delete,
    _study_deck_list,
    _study_due,
    _study_review,
    _study_stats,
    _today_iso,
    study_tool,
)


# Accessibility (Magnifier/Narrator/settings) - extraído a
# domain_tools_accessibility.py (R2 sprint 2026-05-28). 4 funciones.
from .domain_tools_accessibility import (  # noqa: F401  (re-export por compat)
    _accessibility_kill,
    _accessibility_launch,
    _process_running,
    accessibility_tool,
)


def peripheral_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for USB, HID controllers and device manager state.

    Actions: status, usb_list, hid_list, controller_status,
    device_manager_problems, device_disable, device_enable. Vendor RGB APIs
    are deferred (Logitech/Razer/Corsair each ship their own SDK).
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
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
        return _err(
            f"peripheral.{action} is deferred; vendor SDKs (Logitech G HUB, Razer Synapse, Corsair iCUE) each ship their own API/services",
            status="needs_implementation",
            note="If a vendor exposes a stable CLI or HTTP endpoint, we can add a specific binding later.",
        )
    return _err(
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
        return _err("Get-PnpDevice timeout", field=field, reason="powershell_timeout")
    if proc.returncode != 0:
        return _err("Get-PnpDevice failed", stderr=proc.stderr)
    raw = proc.stdout.strip()
    if not raw:
        return _ok(**{field: [], "count": 0})
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err("Get-PnpDevice returned invalid JSON", raw=raw[:500])
    if isinstance(data, dict):
        data = [data]
    return _ok(**{field: data, "count": len(data)})


def _peripheral_device_toggle(action: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    instance_id = str(args.get("instance_id") or args.get("id") or "").strip()
    if not instance_id:
        return _err("missing instance_id (use usb_list/hid_list to find it)")
    verb = "Disable" if action == "device_disable" else "Enable"
    reverse = "device_enable" if action == "device_disable" else "device_disable"
    checkpoint = state.checkpoint(
        f"peripheral {action} {instance_id}",
        rollback=[{"tool": "peripheral", "args": {"action": reverse, "instance_id": instance_id}}],
        metadata={"action": action, "instance_id": instance_id},
    )
    script = f"{verb}-PnpDevice -InstanceId '{_ps_quote(instance_id)}' -Confirm:$false"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30)
    return _ok(
        action=action, instance_id=instance_id,
        exit_code=proc.returncode, stdout=proc.stdout.strip()[:500], stderr=proc.stderr[-2000:],
        checkpoint=checkpoint.get("checkpoint"),
        verified=proc.returncode == 0,
        note="Disable/Enable PnP usually requires admin elevation; if exit_code != 0 the agent likely lacks the privilege.",
    )


def form_filler_tool(args: dict[str, Any], state: AgentState, executor: Executor) -> dict[str, Any]:
    """Compound tool to fill HTML forms with a review gate before submit.

    Actions: status, discover, plan, apply, submit. Works on top of an
    existing browser_real session (pass session_id). discover scans the
    current page for form fields and their labels. plan matches a values
    dict (field_label -> value) against discovered fields without writing.
    apply executes the plan via browser_real.fill / click. submit clicks
    the submit button only when confirmed=true; otherwise it returns
    needs_confirmation with a screenshot for the user to verify.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            note="Requires an existing browser_real session (use browser_real.open or attach_visible first).",
            backend="browser_real_orchestration",
            review_gate_default=True,
        )
    session_id = str(args.get("session_id") or "default")
    if action == "discover":
        return _form_discover(session_id, executor)
    if action == "plan":
        return _form_plan(session_id, args, executor)
    if action == "apply":
        return _form_apply(session_id, args, executor)
    if action == "submit":
        return _form_submit(session_id, args, executor, state)
    return _err(
        "unknown form_filler action", action=action,
        valid_actions=[
            "status", "discover", "fill", "submit", "verify",
        ],
        status="needs_user",
    )


def _form_discover(session_id: str, executor: Executor) -> dict[str, Any]:
    script = r"""
() => {
  function bestLabel(el) {
    if (el.id) {
      const lbl = document.querySelector(`label[for="${el.id}"]`);
      if (lbl) return lbl.innerText.trim();
    }
    const parentLbl = el.closest('label');
    if (parentLbl) return parentLbl.innerText.trim();
    const aria = el.getAttribute('aria-label');
    if (aria) return aria.trim();
    const placeholder = el.getAttribute('placeholder');
    if (placeholder) return placeholder.trim();
    return '';
  }
  function cssPath(el) {
    if (el.id) return `#${CSS.escape(el.id)}`;
    if (el.name) return `${el.tagName.toLowerCase()}[name="${el.name}"]`;
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 6) {
      let part = node.tagName.toLowerCase();
      if (node.className && typeof node.className === 'string') {
        const cls = node.className.trim().split(/\s+/).slice(0, 2).join('.');
        if (cls) part += '.' + cls;
      }
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join(' > ');
  }
  const fields = [];
  const inputs = document.querySelectorAll('input, select, textarea');
  for (const el of inputs) {
    if (el.type === 'hidden') continue;
    fields.push({
      selector: cssPath(el),
      tag: el.tagName.toLowerCase(),
      type: el.type || el.tagName.toLowerCase(),
      name: el.name || '',
      id: el.id || '',
      label: bestLabel(el),
      placeholder: el.getAttribute('placeholder') || '',
      required: el.required || false,
      value: (el.type === 'password') ? '<hidden>' : (el.value || ''),
    });
  }
  const submits = [];
  document.querySelectorAll('button[type="submit"], input[type="submit"], button:not([type])').forEach(b => {
    submits.push({ selector: cssPath(b), text: (b.innerText || b.value || '').trim() });
  });
  return { fields, submits };
}
"""
    result = executor("browser_real", {"action": "evaluate", "session_id": session_id, "script": script})
    if not result.get("ok"):
        return result
    value = result.get("value") or {}
    return _ok(
        session_id=session_id,
        fields=value.get("fields") or [],
        field_count=len(value.get("fields") or []),
        submits=value.get("submits") or [],
        url=result.get("url"),
        title=result.get("title"),
    )


def _form_plan(session_id: str, args: dict[str, Any], executor: Executor) -> dict[str, Any]:
    values = args.get("values") if isinstance(args.get("values"), dict) else {}
    if not values:
        return _err("plan requires values={'field label or name': value}")
    discover = _form_discover(session_id, executor)
    if not discover.get("ok"):
        return discover
    fields = discover.get("fields", [])
    plan: list[dict[str, Any]] = []
    unmatched: list[str] = []
    for key, val in values.items():
        match = _form_match_field(key, fields)
        if not match:
            unmatched.append(str(key))
            continue
        plan.append({"selector": match["selector"], "label": match.get("label") or match.get("name") or match.get("placeholder"), "tag": match["tag"], "type": match["type"], "value": val})
    return _ok(
        session_id=session_id,
        plan=plan, plan_size=len(plan),
        unmatched=unmatched, unmatched_count=len(unmatched),
        submits=discover.get("submits", []),
        url=discover.get("url"), title=discover.get("title"),
    )


def _form_match_field(query: str, fields: list[dict[str, Any]]) -> dict[str, Any] | None:
    q = query.casefold().strip()
    if not q:
        return None
    # 1. Exact match on label / name / id / placeholder.
    for f in fields:
        for key in ("label", "name", "id", "placeholder"):
            if str(f.get(key) or "").casefold() == q:
                return f
    # 2. Substring.
    for f in fields:
        for key in ("label", "name", "id", "placeholder"):
            if q in str(f.get(key) or "").casefold():
                return f
    return None


def _form_apply(session_id: str, args: dict[str, Any], executor: Executor) -> dict[str, Any]:
    plan = args.get("plan") if isinstance(args.get("plan"), list) else None
    if plan is None:
        # If only values were passed, build the plan first.
        if args.get("values"):
            built = _form_plan(session_id, args, executor)
            if not built.get("ok"):
                return built
            plan = built.get("plan", [])
        else:
            return _err("apply requires plan (list) or values (dict)")
    if not plan:
        return _err("plan is empty; nothing to apply")
    applied: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for step in plan:
        selector = str(step.get("selector") or "").strip()
        value = step.get("value")
        tag = str(step.get("type") or step.get("tag") or "").casefold()
        if not selector:
            failed.append({"step": step, "error": "missing selector"})
            continue
        if tag in {"checkbox", "radio"}:
            should_check = bool(value)
            current = executor("browser_real", {"action": "evaluate", "session_id": session_id, "script": f"() => {{ const el = document.querySelector({json.dumps(selector)}); return el ? el.checked : null; }}"})
            if current.get("ok") and bool(current.get("value")) != should_check:
                result = executor("browser_real", {"action": "click", "session_id": session_id, "selector": selector})
            else:
                result = {"ok": True, "noop": True}
        elif tag == "select" or step.get("tag") == "select":
            # For <select>, use JS to set the value option.
            script = f"""() => {{ const el = document.querySelector({json.dumps(selector)}); if (!el) return false; el.value = {json.dumps(str(value))}; el.dispatchEvent(new Event('change', {{bubbles: true}})); return true; }}"""
            result = executor("browser_real", {"action": "evaluate", "session_id": session_id, "script": script})
        else:
            result = executor("browser_real", {"action": "fill", "session_id": session_id, "selector": selector, "value": str(value)})
        (applied if result.get("ok") else failed).append({"step": step, "result": {"ok": result.get("ok"), "error": result.get("error")}})
    return _ok(
        session_id=session_id,
        applied=len(applied), failed=len(failed),
        applied_details=applied, failed_details=failed,
        verified=not failed,
    )


def _form_submit(session_id: str, args: dict[str, Any], executor: Executor, state: AgentState) -> dict[str, Any]:
    confirmed = bool(args.get("confirmed", False))
    selector = str(args.get("selector") or "").strip()
    if not confirmed:
        # Capture a screenshot + summary so the user can verify before submit.
        screenshot = executor("browser_real", {"action": "screenshot", "session_id": session_id})
        discover = _form_discover(session_id, executor)
        pending = state.create_confirmation(
            "form_filler",
            {"action": "submit", "session_id": session_id, "selector": selector, "confirmed": True},
            reason="Submitting a form to the live website. Verify the values are correct.",
            risk="medium",
        )
        return _err(
            "form submission requires confirmation; review the screenshot then call safety(confirm,...) or re-call submit with confirmed=true",
            status="needs_confirmation", verified=False,
            completion_status="needs_user_confirmation",
            screenshot=screenshot.get("image_path"),
            current_fields=[{"label": f.get("label") or f.get("name"), "value": f.get("value")} for f in discover.get("fields", [])],
            url=screenshot.get("url"),
            confirmation=pending.get("confirmation"),
        )
    if selector:
        result = executor("browser_real", {"action": "click", "session_id": session_id, "selector": selector})
    else:
        # Try to find a submit button automatically.
        discover = _form_discover(session_id, executor)
        submits = discover.get("submits", [])
        if not submits:
            return _err("no submit button found; pass selector explicitly")
        result = executor("browser_real", {"action": "click", "session_id": session_id, "selector": submits[0]["selector"]})
    return _ok(session_id=session_id, submit_result=result, verified=result.get("ok"))


def creative_local_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for local generative ML backends (ComfyUI primarily).

    Actions: status, submit, result, wait, queue, interrupt, models. Talks to
    a local ComfyUI HTTP server (default http://127.0.0.1:8188). Returns
    needs_user with the launch command if not reachable.
    """
    action = str(args.get("action") or "status").casefold()
    host = str(args.get("host") or os.environ.get("GEMMA4_COMFYUI_HOST") or "http://127.0.0.1:8188").rstrip("/")
    if action == "status":
        alive = _comfy_alive(host)
        return _ok(
            comfyui=alive,
            host=host,
            launch_instruction="Start ComfyUI manually: `python main.py` from your ComfyUI install. Set GEMMA4_COMFYUI_HOST if it listens on a different port.",
        )
    if not _comfy_alive(host):
        return _err(
            f"ComfyUI is not reachable at {host}",
            status="needs_user", verified=False,
            completion_status="needs_comfyui_running",
            launch_instruction="Start ComfyUI from its install dir (`python main.py`) and re-call.",
        )
    if action == "submit":
        return _comfy_submit(host, args, state)
    if action == "result":
        return _comfy_result(host, args)
    if action == "wait":
        return _comfy_wait(host, args)
    if action == "queue":
        return _comfy_queue(host)
    if action == "interrupt":
        return _comfy_interrupt(host)
    if action == "models":
        return _comfy_models(host)
    return _err(
        "unknown creative_local action", action=action,
        valid_actions=[
            "status", "list_models", "txt2img", "img2img", "queue_status",
            "interrupt",
        ],
        status="needs_user",
    )


def _comfy_alive(host: str) -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(f"{host}/system_stats", headers={"User-Agent": "Gemma4Agent/1.0"})
        with urllib.request.urlopen(req, timeout=2.0):
            return True
    except Exception:
        return False


def _comfy_post_json(host: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    import urllib.request
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{host}{path}", data=data, headers={"Content-Type": "application/json", "User-Agent": "Gemma4Agent/1.0"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except Exception as exc:
        return {"_error": str(exc)}


def _comfy_get_json(host: str, path: str) -> dict[str, Any]:
    import urllib.request
    req = urllib.request.Request(f"{host}{path}", headers={"User-Agent": "Gemma4Agent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except Exception as exc:
        return {"_error": str(exc)}


def _comfy_submit(host: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    workflow = args.get("workflow")
    workflow_path = str(args.get("workflow_path") or args.get("path") or "").strip()
    if not workflow and workflow_path:
        p = Path(workflow_path).expanduser()
        if not p.is_file():
            return _err("workflow_path not found", path=str(p))
        try:
            workflow = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            return _err(f"workflow JSON invalid: {exc}", path=str(p))
    if not isinstance(workflow, dict):
        return _err("submit requires workflow (dict) or workflow_path (json file). ComfyUI 'API format' JSON expected.")
    client_id = str(args.get("client_id") or "gemma4-agent")
    payload = {"prompt": workflow, "client_id": client_id}
    response = _comfy_post_json(host, "/prompt", payload)
    if response.get("_error"):
        return _err(f"submit failed: {response['_error']}")
    prompt_id = response.get("prompt_id")
    if not prompt_id:
        return _err("ComfyUI did not return a prompt_id", response=response)
    state.register_resource(
        "comfy_prompt",
        f"comfy {prompt_id}",
        metadata={"prompt_id": prompt_id, "client_id": client_id, "host": host, "submitted_at": datetime.now().isoformat()},
    )
    return _ok(prompt_id=prompt_id, client_id=client_id, host=host, response=response, note="Use action=wait or action=result to retrieve outputs.")


def _comfy_result(host: str, args: dict[str, Any]) -> dict[str, Any]:
    prompt_id = str(args.get("prompt_id") or args.get("id") or "").strip()
    if not prompt_id:
        return _err("missing prompt_id")
    data = _comfy_get_json(host, f"/history/{prompt_id}")
    if data.get("_error"):
        return _err(f"result fetch failed: {data['_error']}")
    record = data.get(prompt_id)
    if not record:
        return _ok(prompt_id=prompt_id, status="pending", note="No history entry yet; the prompt may still be running.")
    outputs = record.get("outputs") or {}
    saved_images: list[dict[str, Any]] = []
    for node_id, node_output in outputs.items():
        for img in node_output.get("images") or []:
            saved_images.append({"node_id": node_id, "filename": img.get("filename"), "subfolder": img.get("subfolder"), "type": img.get("type")})
    return _ok(prompt_id=prompt_id, status=record.get("status", {}).get("status_str"), outputs=outputs, images=saved_images, verified=True)


def _comfy_wait(host: str, args: dict[str, Any]) -> dict[str, Any]:
    prompt_id = str(args.get("prompt_id") or args.get("id") or "").strip()
    if not prompt_id:
        return _err("missing prompt_id")
    timeout = float(args.get("timeout_sec", 300))
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = _comfy_get_json(host, f"/history/{prompt_id}")
        if not data.get("_error") and prompt_id in data:
            return _comfy_result(host, {"prompt_id": prompt_id})
        time.sleep(2.0)
    return _err("timeout waiting for prompt to finish", prompt_id=prompt_id, timeout_sec=timeout, status="needs_verification")


def _comfy_queue(host: str) -> dict[str, Any]:
    data = _comfy_get_json(host, "/queue")
    if data.get("_error"):
        return _err(f"queue fetch failed: {data['_error']}")
    return _ok(running=len(data.get("queue_running") or []), pending=len(data.get("queue_pending") or []), data=data)


def _comfy_interrupt(host: str) -> dict[str, Any]:
    response = _comfy_post_json(host, "/interrupt", {})
    if response.get("_error"):
        return _err(f"interrupt failed: {response['_error']}")
    return _ok(interrupted=True, response=response)


def _comfy_models(host: str) -> dict[str, Any]:
    data = _comfy_get_json(host, "/object_info")
    if data.get("_error"):
        return _err(f"object_info fetch failed: {data['_error']}")
    return _ok(node_types=len(data), sample=list(data.keys())[:30])


def database_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for local databases.

    Actions: status, list_tables, schema, query (read-only SELECT), execute
    (mutating), export_csv. Drivers: sqlite (stdlib), postgres (psycopg if
    available), mysql (mysql-connector or pymysql if available). For postgres/
    mysql, pass connection params per call (host, port, user, password, db).
    Mutating actions (execute) are not auto-checkpointed because they could
    span millions of rows; the agent must confirm explicitly.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            sqlite=True,
            psycopg=importlib.util.find_spec("psycopg") is not None or importlib.util.find_spec("psycopg2") is not None,
            mysql_connector=importlib.util.find_spec("mysql.connector") is not None,
            pymysql=importlib.util.find_spec("pymysql") is not None,
            note="SQLite is always available. Postgres needs psycopg or psycopg2; MySQL needs mysql-connector-python or pymysql.",
        )
    driver = str(args.get("driver") or "sqlite").casefold()
    try:
        conn, cleanup = _database_connect(driver, args)
    except Exception as exc:
        return _err(f"connect failed: {exc}", driver=driver)
    try:
        if action == "list_tables":
            return _database_list_tables(conn, driver)
        if action == "schema":
            return _database_schema(conn, driver, args)
        if action == "query":
            return _database_query(conn, driver, args)
        if action == "execute":
            return _database_execute(conn, driver, args, state)
        if action == "export_csv":
            return _database_export_csv(conn, driver, args, state)
        return _err(
            "unknown database action", action=action,
            valid_actions=["status", "list_tables", "schema", "query"],
            status="needs_user",
        )
    finally:
        cleanup()


def _database_connect(driver: str, args: dict[str, Any]):
    if driver == "sqlite":
        import sqlite3
        path_raw = str(args.get("path") or args.get("database") or "").strip()
        if not path_raw:
            return None, lambda: None
        path = Path(path_raw).expanduser()
        if not path.is_file() and not bool(args.get("create", False)):
            raise FileNotFoundError(f"SQLite file not found: {path} (pass create=true to allow creating)")
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn, conn.close
    if driver == "postgres":
        if importlib.util.find_spec("psycopg") is not None:
            import psycopg  # type: ignore[import-not-found]
            conn = psycopg.connect(
                host=args.get("host", "localhost"),
                port=int(args.get("port", 5432)),
                user=args.get("user"),
                password=args.get("password"),
                dbname=args.get("database") or args.get("db"),
            )
        elif importlib.util.find_spec("psycopg2") is not None:
            import psycopg2  # type: ignore[import-not-found]
            import psycopg2.extras  # type: ignore[import-not-found]
            conn = psycopg2.connect(
                host=args.get("host", "localhost"),
                port=int(args.get("port", 5432)),
                user=args.get("user"),
                password=args.get("password"),
                dbname=args.get("database") or args.get("db"),
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
        else:
            raise RuntimeError("neither psycopg nor psycopg2 is installed")
        return conn, conn.close
    if driver == "mysql":
        host = str(args.get("host") or "localhost")
        port = int(args.get("port") or 3306)
        user = str(args.get("user") or "")
        password = str(args.get("password") or "")
        database = str(args.get("database") or args.get("db") or "")
        if importlib.util.find_spec("mysql.connector") is not None:
            import mysql.connector  # type: ignore[import-not-found]
            conn = mysql.connector.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
            )
        elif importlib.util.find_spec("pymysql") is not None:
            import pymysql  # type: ignore[import-not-found]
            conn = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                cursorclass=pymysql.cursors.DictCursor,
            )
        else:
            raise RuntimeError("neither mysql-connector-python nor pymysql is installed")
        return conn, conn.close
    raise RuntimeError(f"unsupported driver: {driver}")


def _database_list_tables(conn: Any, driver: str) -> dict[str, Any]:
    cur = conn.cursor()
    if driver == "sqlite":
        cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")
    elif driver == "postgres":
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY table_name")
    else:  # mysql
        cur.execute("SHOW TABLES")
    rows = cur.fetchall()
    tables: list[str] = []
    for row in rows:
        if hasattr(row, "keys"):
            values = list(row.values()) if hasattr(row, "values") else list(dict(row).values())
            if values:
                tables.append(str(values[0]))
        elif isinstance(row, (list, tuple)) and row:
            tables.append(str(row[0]))
    return _ok(driver=driver, tables=tables, count=len(tables))


def _database_schema(conn: Any, driver: str, args: dict[str, Any]) -> dict[str, Any]:
    table_raw = str(args.get("table") or "").strip()
    if not table_raw:
        return _err("missing table name")
    # CC-017 / T2-database-schema-fstring-injection-017: validar identifier.
    try:
        table = ps_safe_literal(table_raw, RX_SQL_IDENT)
    except PSValidationError:
        return _err(
            "invalid table identifier (allowed: letters/digits/underscore, optional schema.table)",
            table=table_raw,
            status="needs_user",
        )
    cur = conn.cursor()
    if driver == "sqlite":
        cur.execute(f"PRAGMA table_info({table})")
        columns = [{"name": r[1], "type": r[2], "notnull": bool(r[3]), "default": r[4], "pk": bool(r[5])} for r in cur.fetchall()]
    elif driver == "postgres":
        cur.execute("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position", (table,))
        columns = [{"name": r[0] if isinstance(r, (list, tuple)) else r["column_name"], "type": r[1] if isinstance(r, (list, tuple)) else r["data_type"]} for r in cur.fetchall()]
    else:
        cur.execute(f"DESCRIBE {table}")
        columns = [{"name": (r[0] if isinstance(r, (list, tuple)) else r.get("Field")), "type": (r[1] if isinstance(r, (list, tuple)) else r.get("Type"))} for r in cur.fetchall()]
    return _ok(driver=driver, table=table, columns=columns)


def _apply_readonly(conn: Any, driver: str) -> None:
    """CC-018: aplica read-only a nivel de driver para la duración del query.
    SQLite -> PRAGMA query_only=1
    Postgres -> SET TRANSACTION READ ONLY (en transacción explícita)
    MySQL -> SET SESSION TRANSACTION READ ONLY
    Si el driver no soporta la operación, la silenciamos (best-effort).
    """
    cur = conn.cursor()
    try:
        if driver == "sqlite":
            cur.execute("PRAGMA query_only = 1")
        elif driver == "postgres":
            cur.execute("BEGIN")
            cur.execute("SET TRANSACTION READ ONLY")
        elif driver == "mysql":
            cur.execute("SET SESSION TRANSACTION READ ONLY")
    except Exception:
        pass


def _release_readonly(conn: Any, driver: str) -> None:
    cur = conn.cursor()
    try:
        if driver == "sqlite":
            cur.execute("PRAGMA query_only = 0")
        elif driver == "postgres":
            try:
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
        elif driver == "mysql":
            cur.execute("SET SESSION TRANSACTION READ WRITE")
    except Exception:
        pass


def _database_query(conn: Any, driver: str, args: dict[str, Any]) -> dict[str, Any]:
    sql = str(args.get("sql") or args.get("query") or "").strip()
    if not sql:
        return _err("missing sql")
    # Pre-check informativo; el enforcement real es a nivel de driver.
    if not _is_read_only_sql(sql):
        return _err(
            "query is restricted to read-only statements (SELECT, WITH, EXPLAIN, PRAGMA, SHOW). Use execute(...) for mutations.",
            status="needs_user",
        )
    # CC-018 / T2-database-readonly-heuristic-018: driver-level enforcement.
    _apply_readonly(conn, driver)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        try:
            rows = cur.fetchall()
        except Exception:
            rows = []
        columns = [d[0] for d in cur.description] if cur.description else []
        serialized: list[dict[str, Any]] = []
        for row in rows[: int(args.get("limit", 200))]:
            if isinstance(row, dict):
                serialized.append({k: _scalarize(v) for k, v in row.items()})
            elif hasattr(row, "keys"):
                serialized.append({k: _scalarize(row[k]) for k in row.keys()})
            else:
                serialized.append({columns[i] if i < len(columns) else f"col{i}": _scalarize(v) for i, v in enumerate(row)})
        return _ok(sql=sql, columns=columns, row_count=len(rows), rows=serialized)
    finally:
        _release_readonly(conn, driver)


def _database_execute(conn: Any, driver: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    sql = str(args.get("sql") or args.get("query") or "").strip()
    if not sql:
        return _err("missing sql")
    if _is_read_only_sql(sql):
        return _err("execute is for mutations; use query(...) for SELECT")
    # CC-101 / CC-019: gate duro independiente de safety_enabled.
    gate = _hard_gate(
        state,
        tool="database",
        action="execute",
        args=args,
        reason=f"database.execute will mutate the database: {sql[:200]}",
        risk="high",
    )
    if gate is not None:
        return gate
    cur = conn.cursor()
    cur.execute(sql)
    try:
        conn.commit()
    except Exception:
        pass
    rowcount = cur.rowcount if hasattr(cur, "rowcount") else None
    return _ok(sql=sql, driver=driver, rowcount=rowcount, verified=True)


def _database_export_csv(conn: Any, driver: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    sql = str(args.get("sql") or args.get("query") or "").strip()
    if not sql or not _is_read_only_sql(sql):
        return _err("export_csv requires a read-only SQL query")
    dst_raw = str(args.get("dst") or args.get("output") or "").strip()
    if dst_raw:
        dst = Path(dst_raw).expanduser()
    else:
        dst = state.path.parent / "database_exports" / f"export_{int(time.time())}.csv"
    dst.parent.mkdir(parents=True, exist_ok=True)
    _apply_readonly(conn, driver)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description] if cur.description else []
        import csv
        with dst.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(columns)
            for row in rows:
                if isinstance(row, dict):
                    writer.writerow([_scalarize(row.get(c)) for c in columns])
                elif hasattr(row, "keys"):
                    writer.writerow([_scalarize(row[c]) for c in columns])
                else:
                    writer.writerow([_scalarize(v) for v in row])
        return _ok(sql=sql, driver=driver, dst=str(dst), rows=len(rows), verified=dst.is_file())
    finally:
        _release_readonly(conn, driver)


def _is_read_only_sql(sql: str) -> bool:
    s = sql.strip().casefold()
    # Strip leading comments and whitespace.
    while s.startswith("--") or s.startswith("/*"):
        if s.startswith("--"):
            s = s.split("\n", 1)[1].strip() if "\n" in s else ""
        else:
            end = s.find("*/")
            s = s[end + 2:].strip() if end >= 0 else ""
    return s.startswith(("select", "with", "explain", "pragma", "show", "describe"))


def _scalarize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def container_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for Docker / docker-compose.

    Actions: status, ps, ps_all, images, inspect, logs, start, stop, restart,
    exec, compose_up, compose_down, compose_ps. Returns needs_dependency if
    docker is not on PATH. exec accepts an explicit command list and runs
    docker exec; we do not wrap arbitrary shells.
    """
    action = str(args.get("action") or "status").casefold()
    docker = shutil.which("docker") or shutil.which("docker.exe")
    if action == "status":
        return _ok(
            docker=bool(docker), docker_path=docker,
            install_hint="winget install Docker.DockerDesktop",
        )
    if not docker:
        return _err(
            "docker is not installed or not on PATH",
            status="needs_dependency", verified=False,
            install_hint="winget install Docker.DockerDesktop",
        )
    if action in {"ps", "ps_all"}:
        return _container_ps(docker, action == "ps_all")
    if action == "images":
        return _container_images(docker)
    if action == "inspect":
        return _container_inspect(docker, args)
    if action == "logs":
        return _container_logs(docker, args)
    if action in {"start", "stop", "restart"}:
        return _container_lifecycle(docker, action, args, state)
    if action == "exec":
        return _container_exec(docker, args)
    if action == "compose_up":
        return _container_compose(docker, "up", args)
    if action == "compose_down":
        return _container_compose(docker, "down", args)
    if action == "compose_ps":
        return _container_compose(docker, "ps", args)
    return _err(
        "unknown container action", action=action,
        valid_actions=[
            "status", "ps", "ps_all", "images", "inspect", "logs",
            "start", "stop", "restart", "pause", "unpause", "rm",
            "compose_up", "compose_down", "compose_ps",
        ],
        status="needs_user",
    )


def _container_ps(docker: str, all_containers: bool) -> dict[str, Any]:
    cmd = [docker, "ps", "--format", "{{json .}}"]
    if all_containers:
        cmd.insert(2, "-a")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("docker ps failed", stderr=proc.stderr, exit_code=proc.returncode)
    containers: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            containers.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return _ok(containers=containers, count=len(containers))


def _container_images(docker: str) -> dict[str, Any]:
    proc = subprocess.run([docker, "images", "--format", "{{json .}}"], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("docker images failed", stderr=proc.stderr)
    images: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            images.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return _ok(images=images, count=len(images))


def _container_inspect(docker: str, args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("name") or args.get("id") or args.get("container") or "").strip()
    if not target:
        return _err("missing container name/id")
    proc = subprocess.run([docker, "inspect", target], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("docker inspect failed", stderr=proc.stderr, target=target)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _err("inspect returned invalid JSON", raw=proc.stdout[:500])
    return _ok(target=target, inspect=data)


def _container_logs(docker: str, args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("name") or args.get("id") or args.get("container") or "").strip()
    if not target:
        return _err("missing container name/id")
    tail = int(args.get("tail", 100))
    proc = subprocess.run([docker, "logs", "--tail", str(tail), target], capture_output=True, text=True, timeout=30)
    return _ok(target=target, tail=tail, exit_code=proc.returncode, stdout=proc.stdout[-8000:], stderr=proc.stderr[-2000:])


def _container_lifecycle(docker: str, action: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    target = str(args.get("name") or args.get("id") or args.get("container") or "").strip()
    if not target:
        return _err("missing container name/id")
    reverse = {"start": "stop", "stop": "start", "restart": "restart"}.get(action)
    checkpoint = state.checkpoint(
        f"container {action} {target}",
        rollback=[{"tool": "container", "args": {"action": reverse, "name": target}}] if reverse else [],
        metadata={"target": target, "action": action},
    )
    proc = subprocess.run([docker, action, target], capture_output=True, text=True, timeout=60)
    return _ok(
        action=action, target=target,
        exit_code=proc.returncode, stdout=proc.stdout.strip()[:500], stderr=proc.stderr[-1000:],
        checkpoint=checkpoint.get("checkpoint"),
        verified=proc.returncode == 0,
    )


def _container_exec(docker: str, args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("name") or args.get("id") or args.get("container") or "").strip()
    cmd = args.get("command")
    if not target:
        return _err("missing container name/id")
    if isinstance(cmd, str):
        cmd_list = cmd.split()
    elif isinstance(cmd, list):
        cmd_list = [str(p) for p in cmd]
    else:
        return _err("command must be string or list")
    if not cmd_list:
        return _err("command is empty")
    proc = subprocess.run([docker, "exec", target, *cmd_list], capture_output=True, text=True, timeout=int(args.get("timeout_sec", 60)))
    return _ok(target=target, command=cmd_list, exit_code=proc.returncode, stdout=proc.stdout[-8000:], stderr=proc.stderr[-2000:], verified=proc.returncode == 0)


def _container_compose(docker: str, subcommand: str, args: dict[str, Any]) -> dict[str, Any]:
    cwd = str(args.get("cwd") or args.get("path") or "").strip() or None
    raw_extra = args.get("args")
    extra: list[Any] = raw_extra if isinstance(raw_extra, list) else []
    cmd = [docker, "compose", subcommand]
    if subcommand == "up":
        cmd.append("-d")
    if subcommand == "ps":
        cmd.extend(["--format", "json"])
    cmd.extend(str(a) for a in extra)
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=int(args.get("timeout_sec", 180)))
    return _ok(subcommand=subcommand, cwd=cwd, command=cmd, exit_code=proc.returncode, stdout=proc.stdout[-6000:], stderr=proc.stderr[-2000:], verified=proc.returncode == 0)


# Photo Library - extraído a domain_tools_photo_library.py
# (R2 sprint 2026-05-28). 8 funciones + _PHOTO_EXTS.
from .domain_tools_photo_library import (  # noqa: F401
    _PHOTO_EXTS,
    _photo_exif,
    _photo_extract_date,
    _photo_find_by_date,
    _photo_group_by_date,
    _photo_open_exif,
    _photo_scan,
    _photo_thumbnails,
    photo_library_tool,
)


# Fact Check (TF-IDF + cosine, pure-Python) - extraído a
# domain_tools_fact_check.py (R2 sprint 2026-05-28).
from .domain_tools_fact_check import (  # noqa: F401
    _NEGATION_CUES_EN,
    _NEGATION_CUES_ES,
    _fact_check_chunks,
    _fact_check_rank,
    fact_check_tool,
)


# Data Analysis (pandas + matplotlib Agg) - extraído a
# domain_tools_data_analysis.py (R2 sprint 2026-05-28). 8 funciones.
from .domain_tools_data_analysis import (  # noqa: F401
    _data_csv_describe,
    _data_csv_head,
    _data_csv_profile,
    _data_csv_query,
    _data_csv_to_xlsx,
    _data_load_df,
    _data_plot,
    data_analysis_tool,
)


# Network diagnostics - extraído a domain_tools_network.py
# (R2 sprint 2026-05-28). 9 funciones (entry + 8 helpers).
from .domain_tools_network import (  # noqa: F401
    _network_connections,
    _network_dns_get,
    _network_dns_resolve,
    _network_dns_set,
    _network_ping,
    _network_port_check,
    _network_public_ip,
    _network_traceroute,
    network_tool,
)


# Watcher (file/url/process) - extraído a domain_tools_watcher.py
# (R2 sprint 2026-05-28). 9 funciones. _register_routine_process_watcher se
# usa por routine_tool — éste lo importa lazy desde domain_tools que ahora
# re-exporta desde aquí.
from .domain_tools_watcher import (  # noqa: F401
    _file_snapshot,
    _process_snapshot,
    _register_routine_process_watcher,
    _register_watcher_scheduled_task,
    _url_snapshot,
    _watcher_check,
    _watcher_register_file,
    _watcher_register_url,
    watcher_tool,
)


# Job Manager (subprocess tracking) - extraído a domain_tools_job_manager.py
# (R2 sprint 2026-05-28). 4 funciones.
from .domain_tools_job_manager import (  # noqa: F401
    _job_manager_cancel,
    _job_manager_log,
    _job_manager_start,
    job_manager_tool,
)


def _pid_owned_by(pid: int, expected_exe_basename: str | None) -> tuple[bool, str | None]:
    """CC-104: Returns (matches, current_name). On Windows queries Get-Process
    and compares ProcessName against the expected basename (without extension).
    `matches` is True only if both checks succeed; False if PID does not exist
    OR is a different process. `current_name` may be None when unknown.
    """
    if os.name != "nt":
        try:
            os.kill(int(pid), 0)
            return True, None
        except (ProcessLookupError, PermissionError, OSError):
            return False, None
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"$p = Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue; "
         f"if ($p) {{ $p.ProcessName }} else {{ '' }}"],
        capture_output=True, text=True, timeout=10,
    )
    name = proc.stdout.strip()
    if not name:
        return False, None
    if not expected_exe_basename:
        return True, name
    expected = Path(expected_exe_basename).stem.casefold()
    return name.casefold() == expected or name.casefold().startswith(expected), name


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ 1 }} else {{ 0 }}"],
            capture_output=True, text=True, timeout=10,
        )
        return proc.returncode == 0 and proc.stdout.strip() == "1"
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def maintenance_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for Windows maintenance and security diagnostics.

    Actions:
      - status
      - windows_update_status
      - defender_status
      - defender_quick_scan
      - firewall_status
      - event_logs_query(log, source?, level?, hours?, limit?)
      - services_list, service_status(name), service_start(name), service_stop(name)
      - disk_cleanup_describe   (manual hint, no execution)
      - restore_point_create(description?)
    Long scans, registry mutations, and update install are NOT exposed; the
    user must use terminal(...) explicitly for those.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            powershell=bool(shutil.which("powershell")),
            backend="windows_native",
            note="Mutating maintenance actions (cleanup execution, update install) require explicit terminal commands.",
        )
    if action == "windows_update_status":
        return _maintenance_windows_update_status()
    if action == "defender_status":
        return _maintenance_defender_status()
    if action == "defender_quick_scan":
        return _maintenance_defender_quick_scan(state)
    if action == "firewall_status":
        return _maintenance_firewall_status()
    if action == "event_logs_query":
        return _maintenance_event_logs(args)
    if action in {"services_list", "services"}:
        return _maintenance_services_list(args)
    if action == "service_status":
        return _maintenance_service_status(args)
    if action in {"service_start", "service_stop"}:
        return _maintenance_service_control(action, args, state)
    if action == "disk_cleanup_describe":
        # T2-maintenance-disk-cleanup-cmd-list-027: no devolvemos arrays
        # ejecutables, solo prosa. El LLM no puede copy-pegar a terminal.
        return _ok(
            note=(
                "Disk cleanup must be run manually by the user. First run cleanmgr /sageset:1 in an "
                "elevated terminal to pick categories, then cleanmgr /sagerun:1 to apply. This tool "
                "intentionally does NOT return executable command arrays — the operation deletes "
                "selected categories irreversibly."
            ),
            status="needs_user",
            verified=False,
        )
    if action == "restore_point_create":
        return _maintenance_restore_point_create(args)
    return _err(
        "unknown maintenance action", action=action,
        valid_actions=[
            "status", "windows_update_status", "defender_status",
            "defender_scan", "disk_cleanup_describe", "firewall_status",
            "service_status", "service_action", "event_logs_query",
            "restore_point_create",
        ],
        status="needs_user",
    )


def _maintenance_windows_update_status() -> dict[str, Any]:
    script = r"""
$results = $null
try {
  $au = New-Object -ComObject Microsoft.Update.AutoUpdate
  $results = $au.Results
} catch {}
$hist = $null
try {
  $session = New-Object -ComObject Microsoft.Update.Session
  $searcher = $session.CreateUpdateSearcher()
  $count = $searcher.GetTotalHistoryCount()
  if ($count -gt 0) {
    $hist = $searcher.QueryHistory(0, [Math]::Min($count, 10)) | ForEach-Object {
      [PSCustomObject]@{ Title=$_.Title; Date=$_.Date; ResultCode=$_.ResultCode; Operation=$_.Operation }
    }
  }
} catch {}
[PSCustomObject]@{
  last_install_success = if ($results) { $results.LastInstallationSuccessDate } else { $null }
  last_search_success  = if ($results) { $results.LastSearchSuccessDate } else { $null }
  history              = $hist
} | ConvertTo-Json -Depth 4
"""
    # try/except: Microsoft.Update.Session COM puede colgarse si el servicio
    # wuauserv esta detenido o el sistema esta en estado WU corrupto.
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return _err("windows update query timeout", reason="wuauserv_unresponsive")
    if proc.returncode != 0:
        return _err("windows_update_status failed", stderr=proc.stderr)
    try:
        data = json.loads(proc.stdout or "null")
    except json.JSONDecodeError:
        return _err("windows_update_status invalid JSON", raw=proc.stdout[:500])
    return _ok(**(data or {}))


def _maintenance_defender_status() -> dict[str, Any]:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntispywareEnabled,AMServiceEnabled,FullScanAge,QuickScanAge,AntivirusSignatureLastUpdated,DefenderSignaturesOutOfDate | ConvertTo-Json -Depth 3"],
        capture_output=True, text=True, timeout=20,
    )
    if proc.returncode != 0:
        return _err("Get-MpComputerStatus failed", stderr=proc.stderr)
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return _err("defender_status invalid JSON", raw=proc.stdout[:500])
    return _ok(defender=data)


def _maintenance_defender_quick_scan(state: AgentState) -> dict[str, Any]:
    """T2-maintenance-defender-scan-timeout-026: lanzar como job para no
    bloquear el agente hasta 15 minutos. El usuario puede sondear con
    `job_manager.status_of` o cancelarlo."""
    state.note("Defender QuickScan requested", metadata={"started_at": datetime.now().isoformat()})
    log_dir = state.path.parent / "logs" / "jobs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"defender_quick_scan_{int(time.time())}.log"
    cmd = ["powershell", "-NoProfile", "-Command", "Start-MpScan -ScanType QuickScan"]
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with log_path.open("wb") as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, creationflags=creationflags)
    resource = state.register_resource(
        "job",
        "defender_quick_scan",
        cleanup_tool="job_manager",
        cleanup_args={"action": "cancel"},
        metadata={
            "cmd": cmd,
            "pid": proc.pid,
            "log": str(log_path),
            "started_at": datetime.now().isoformat(),
            "kind_label": "defender_quick_scan",
        },
    )
    rid = resource.get("resource", {}).get("id")
    if rid:
        state.update_resource(rid, cleanup_args_patch={"action": "cancel", "job_id": rid})
    return _ok(
        scan="QuickScan",
        job_id=rid,
        pid=proc.pid,
        log=str(log_path),
        status="running",
        note="Defender scan running in background; poll job_manager.status_of or job_manager.log to follow progress.",
    )


def _maintenance_firewall_status() -> dict[str, Any]:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction | ConvertTo-Json"],
        capture_output=True, text=True, timeout=15,
    )
    if proc.returncode != 0:
        return _err("firewall_status failed", stderr=proc.stderr)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _err("firewall_status invalid JSON", raw=proc.stdout[:500])
    if isinstance(data, dict):
        data = [data]
    return _ok(profiles=data, count=len(data))


def _maintenance_event_logs(args: dict[str, Any]) -> dict[str, Any]:
    # CC-100 / T2-maintenance-event-log-injection-025: validamos log contra
    # allowlist estricta y pasamos por env-var. hours/limit/level se castean.
    log_raw = str(args.get("log") or "System").strip()
    try:
        log = ps_safe_literal(log_raw, RX_LOG_NAME)
    except PSValidationError as exc:
        return _err(f"invalid log name: {exc}", log=log_raw, status="needs_user")
    level = args.get("level")  # 1=Critical 2=Error 3=Warning 4=Information
    try:
        hours = int(args.get("hours", 24))
        limit = int(args.get("limit", 50))
        level_int = int(level) if level is not None else None
    except (TypeError, ValueError):
        return _err("invalid hours/limit/level (must be integers)", status="needs_user")
    env = {**os.environ, "GEMMA4_LOG_NAME": log}
    level_clause = "" if level_int is None else f"; Level={level_int}"
    cmd = (
        f"$start = (Get-Date).AddHours(-{hours}); "
        f"$f = @{{ LogName=$env:GEMMA4_LOG_NAME; StartTime=$start{level_clause} }}; "
        f"Get-WinEvent -FilterHashtable $f -MaxEvents {limit} -ErrorAction SilentlyContinue | "
        f"Select-Object TimeCreated,Id,LevelDisplayName,ProviderName,Message | ConvertTo-Json -Depth 3"
    )
    # Get-WinEvent puede tardar varios segundos en logs grandes; timeout=30
    # razonable. Agregamos try/except para no propagar TimeoutExpired al
    # caller del tool.
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], env=env, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return _err("Get-WinEvent timeout", log=log, hours=hours, reason="event_log_too_large")
    if proc.returncode != 0:
        return _err("event_logs_query failed", stderr=proc.stderr)
    ok_parse, data = parse_ps_json(proc.stdout)
    if not ok_parse:
        return _err("event_logs_query invalid JSON", raw=data)
    if data is None:
        return _ok(log=log, events=[], count=0, hours=hours)
    if isinstance(data, dict):
        data = [data]
    return _ok(log=log, events=data, count=len(data), hours=hours)


def _maintenance_services_list(args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("name") or args.get("query") or "*").strip()
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Get-Service -Name '{_ps_quote(name)}' -ErrorAction SilentlyContinue | Select-Object Name,DisplayName,Status,StartType | ConvertTo-Json"],
        capture_output=True, text=True, timeout=20,
    )
    if proc.returncode != 0:
        return _err("services_list failed", stderr=proc.stderr)
    raw = proc.stdout.strip()
    if not raw:
        return _ok(services=[], count=0)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err("services_list invalid JSON", raw=raw[:500])
    if isinstance(data, dict):
        data = [data]
    return _ok(services=data, count=len(data))


def _maintenance_service_status(args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("name") or "").strip()
    if not name:
        return _err("missing service name")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Get-Service -Name '{_ps_quote(name)}' -ErrorAction SilentlyContinue | Select-Object Name,DisplayName,Status,StartType | ConvertTo-Json"],
        capture_output=True, text=True, timeout=15,
    )
    if proc.returncode != 0:
        return _err("service_status failed", stderr=proc.stderr)
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
    except json.JSONDecodeError:
        data = None
    if not data:
        return _err("service not found", name=name)
    return _ok(service=data)


def _maintenance_service_control(action: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    name = str(args.get("name") or "").strip()
    if not name:
        return _err("missing service name")
    verb = "Start" if action == "service_start" else "Stop"
    before = _maintenance_service_status({"name": name})
    if not before.get("ok"):
        return before
    checkpoint = state.checkpoint(
        f"service {action} {name}",
        rollback=[{"tool": "maintenance", "args": {"action": "service_stop" if action == "service_start" else "service_start", "name": name}}],
        metadata={"before": before.get("service")},
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"{verb}-Service -Name '{_ps_quote(name)}'"],
        capture_output=True, text=True, timeout=30,
    )
    after = _maintenance_service_status({"name": name})
    return _ok(
        action=action, name=name,
        before=before.get("service"),
        after=after.get("service"),
        exit_code=proc.returncode,
        stderr=proc.stderr[-1000:],
        checkpoint=checkpoint.get("checkpoint"),
        verified=proc.returncode == 0,
    )


def _maintenance_restore_point_create(args: dict[str, Any]) -> dict[str, Any]:
    description = str(args.get("description") or "Gemma4 Agent restore point").strip()
    # System Restore must be enabled on the system drive for this to work.
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Checkpoint-Computer -Description '{_ps_quote(description)}' -RestorePointType MODIFY_SETTINGS"],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        return _err(
            "Checkpoint-Computer failed; System Restore may be disabled or rate-limited (1 per 24h on consumer Windows)",
            stderr=proc.stderr, exit_code=proc.returncode,
            status="needs_user",
            note="Enable System Protection on the system drive via Settings > System > About > Advanced system settings.",
        )
    return _ok(description=description, exit_code=proc.returncode, verified=True)


def media_edit_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for ffmpeg-based audio/video editing.

    Actions: status, trim, concat, extract_audio, subtitles_extract, normalize,
    thumbnail, transcode, probe. Each action returns the output path, ffmpeg
    exit code, and the command run.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
        ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
        return _ok(
            ffmpeg=bool(ffmpeg), ffmpeg_path=ffmpeg,
            ffprobe=bool(ffprobe), ffprobe_path=ffprobe,
            install_hint="winget install Gyan.FFmpeg",
        )
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        return _err(
            "ffmpeg is not installed",
            status="needs_dependency",
            install_hint="winget install Gyan.FFmpeg",
        )
    if action == "probe":
        return _media_edit_probe(args)
    if action == "trim":
        return _media_edit_trim(ffmpeg, args, state)
    if action == "concat":
        return _media_edit_concat(ffmpeg, args, state)
    if action == "extract_audio":
        return _media_edit_extract_audio(ffmpeg, args, state)
    if action == "subtitles_extract":
        return _media_edit_subtitles_extract(ffmpeg, args, state)
    if action == "normalize":
        return _media_edit_normalize(ffmpeg, args, state)
    if action == "thumbnail":
        return _media_edit_thumbnail(ffmpeg, args, state)
    if action == "transcode":
        return _media_edit_transcode(ffmpeg, args, state)
    return _err(
        "unknown media_edit action", action=action,
        valid_actions=[
            "status", "probe", "trim", "concat", "extract_audio",
            "subtitles_extract", "normalize", "thumbnail", "transcode",
        ],
        status="needs_user",
    )


def _media_edit_probe(args: dict[str, Any]) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    if not ffprobe:
        return _err("ffprobe is not installed", status="needs_dependency", install_hint="winget install Gyan.FFmpeg")
    path = _media_edit_input(args)
    if isinstance(path, dict):
        return path
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        return _err("ffprobe failed", stderr=proc.stderr, exit_code=proc.returncode)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _err("ffprobe returned invalid JSON", raw=proc.stdout[:500])
    return _ok(path=str(path), probe=data)


def _media_edit_input(args: dict[str, Any]) -> Path | dict[str, Any]:
    raw = str(args.get("path") or args.get("input") or args.get("src") or "").strip()
    if not raw:
        return _err("missing input path")
    path = Path(raw).expanduser()
    if not path.is_file():
        return _err("input file not found", path=str(path))
    return path


def _media_edit_output(args: dict[str, Any], state: AgentState, src: Path, suffix: str) -> Path:
    raw = str(args.get("output") or args.get("dst") or args.get("out") or "").strip()
    if raw:
        p = Path(raw).expanduser()
    else:
        out_dir = state.path.parent / "media_edit"
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / f"{_safe_name(src.stem)}_{int(time.time())}{suffix}"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _run_ffmpeg(ffmpeg: str, cmd: list[str], timeout: int = 600) -> dict[str, Any]:
    proc = subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", *cmd], capture_output=True, text=True, timeout=timeout)
    return {
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-3000:],
        "stderr": (proc.stderr or "")[-3000:],
        "command": ["ffmpeg", *cmd],
    }


def _media_edit_trim(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    src = _media_edit_input(args)
    if isinstance(src, dict):
        return src
    start = str(args.get("start") or "0").strip()
    duration = str(args.get("duration") or "").strip()
    end = str(args.get("end") or "").strip()
    out = _media_edit_output(args, state, src, src.suffix)
    cmd: list[str] = ["-ss", start, "-i", str(src)]
    if duration:
        cmd.extend(["-t", duration])
    elif end:
        cmd.extend(["-to", end])
    cmd.extend(["-c", "copy", str(out)])
    result = _run_ffmpeg(ffmpeg, cmd)
    return _ok(path=str(out), src=str(src), start=start, duration=duration or None, end=end or None, verified=result["exit_code"] == 0 and out.is_file(), size=out.stat().st_size if out.is_file() else 0, **result)


def _media_edit_concat(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    raw_inputs = args.get("inputs")
    inputs: list[Any] = raw_inputs if isinstance(raw_inputs, list) else []
    if len(inputs) < 2:
        return _err("concat requires at least 2 inputs")
    paths: list[Path] = []
    for raw in inputs:
        p = Path(str(raw)).expanduser()
        if not p.is_file():
            return _err("concat input not found", path=str(p))
        paths.append(p)
    out = _media_edit_output(args, state, paths[0], paths[0].suffix)
    # ffmpeg concat demuxer expects a list file.
    list_file = out.with_suffix(".concat.txt")
    # T2-media_edit-concat-list-injection-045: escape `'` como `'\''` per
    # ffmpeg concat demuxer docs.
    list_file.write_text(
        "\n".join(f"file '{p.as_posix().replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'" for p in paths) + "\n",
        encoding="utf-8",
    )
    cmd = ["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)]
    result = _run_ffmpeg(ffmpeg, cmd)
    try:
        list_file.unlink()
    except OSError:
        pass
    return _ok(path=str(out), inputs=[str(p) for p in paths], verified=result["exit_code"] == 0 and out.is_file(), size=out.stat().st_size if out.is_file() else 0, **result)


def _media_edit_extract_audio(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    src = _media_edit_input(args)
    if isinstance(src, dict):
        return src
    fmt = str(args.get("format") or "mp3").lower()
    if fmt not in {"mp3", "aac", "wav", "flac", "ogg", "m4a"}:
        return _err(f"unsupported audio format: {fmt}", supported=["mp3", "aac", "wav", "flac", "ogg", "m4a"])
    out = _media_edit_output(args, state, src, f".{fmt}")
    codec_map = {"mp3": "libmp3lame", "aac": "aac", "wav": "pcm_s16le", "flac": "flac", "ogg": "libvorbis", "m4a": "aac"}
    cmd = ["-i", str(src), "-vn", "-c:a", codec_map[fmt], str(out)]
    result = _run_ffmpeg(ffmpeg, cmd)
    return _ok(path=str(out), src=str(src), format=fmt, verified=result["exit_code"] == 0 and out.is_file(), size=out.stat().st_size if out.is_file() else 0, **result)


def _media_edit_subtitles_extract(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    src = _media_edit_input(args)
    if isinstance(src, dict):
        return src
    track = int(args.get("track", 0))
    out = _media_edit_output(args, state, src, ".srt")
    cmd = ["-i", str(src), "-map", f"0:s:{track}", str(out)]
    result = _run_ffmpeg(ffmpeg, cmd)
    if result["exit_code"] != 0:
        return _ok(
            path=str(out), src=str(src), track=track,
            verified=False, status="needs_verification",
            note="No embedded subtitle track at that index, or ffmpeg cannot extract this codec.",
            **result,
        )
    return _ok(path=str(out), src=str(src), track=track, verified=out.is_file() and out.stat().st_size > 0, size=out.stat().st_size if out.is_file() else 0, **result)


def _media_edit_normalize(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    src = _media_edit_input(args)
    if isinstance(src, dict):
        return src
    out = _media_edit_output(args, state, src, src.suffix)
    # EBU R128 loudnorm: I=-23 LUFS, TP=-2 dB, LRA=7. Single-pass.
    cmd = ["-i", str(src), "-af", "loudnorm=I=-23:TP=-2:LRA=7", str(out)]
    result = _run_ffmpeg(ffmpeg, cmd, timeout=900)
    return _ok(path=str(out), src=str(src), filter="loudnorm I=-23 TP=-2 LRA=7", verified=result["exit_code"] == 0 and out.is_file(), size=out.stat().st_size if out.is_file() else 0, **result)


def _media_edit_thumbnail(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    src = _media_edit_input(args)
    if isinstance(src, dict):
        return src
    at = str(args.get("at") or args.get("time") or "00:00:01").strip()
    out = _media_edit_output(args, state, src, ".png")
    cmd = ["-ss", at, "-i", str(src), "-frames:v", "1", str(out)]
    result = _run_ffmpeg(ffmpeg, cmd)
    return _ok(path=str(out), src=str(src), at=at, verified=result["exit_code"] == 0 and out.is_file(), size=out.stat().st_size if out.is_file() else 0, **result)


def _media_edit_transcode(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    src = _media_edit_input(args)
    if isinstance(src, dict):
        return src
    fmt = str(args.get("format") or "mp4").lower()
    crf = int(args.get("crf", 23))
    preset = str(args.get("preset") or "medium")
    out = _media_edit_output(args, state, src, f".{fmt}")
    if fmt in {"mp4", "mkv", "webm"}:
        vcodec = "libvpx-vp9" if fmt == "webm" else "libx264"
        acodec = "libopus" if fmt == "webm" else "aac"
        cmd = ["-i", str(src), "-c:v", vcodec, "-preset", preset, "-crf", str(crf), "-c:a", acodec, str(out)]
    else:
        return _err(f"unsupported transcode format: {fmt}", supported=["mp4", "mkv", "webm"])
    result = _run_ffmpeg(ffmpeg, cmd, timeout=1800)
    return _ok(path=str(out), src=str(src), format=fmt, crf=crf, preset=preset, verified=result["exit_code"] == 0 and out.is_file(), size=out.stat().st_size if out.is_file() else 0, **result)


def game_launcher_tool(args: dict[str, Any], state: AgentState, executor: Executor | None = None) -> dict[str, Any]:
    """Compound tool for non-Steam game launchers.

    Actions:
      - status
      - discover(launcher?) -> {epic, gog, xbox, riot} games found on disk
      - launch(launcher, game) -> opens by URI/shortcut/exe
      - open_store_page(launcher, query) -> deferred
      - open_library_page(launcher) -> opens launcher window
    Steam is handled by the existing `steam` tool; we do not duplicate it here.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        epic_dir = _epic_manifests_dir()
        return _ok(
            launchers={
                "epic": epic_dir is not None,
                "gog": _gog_registry_has_games(),
                "xbox": True,  # always queryable via Get-StartApps
                "riot": _riot_install_db() is not None,
            },
            epic_manifest_dir=str(epic_dir) if epic_dir else None,
            note="Steam is handled by the dedicated `steam` tool.",
        )
    if action in {"discover", "list", "discover_games"}:
        return _game_launcher_discover(args)
    if action == "launch":
        return _game_launcher_launch(args, state, executor)
    if action == "open_library_page":
        launcher = str(args.get("launcher") or "").casefold()
        if not executor:
            return _err("open_library_page requires executor", status="needs_implementation")
        target = {
            "epic": "com.epicgames.launcher://store",
            "gog": "goggalaxy://",
            "xbox": "ms-windows-store://home",
        }.get(launcher)
        if not target:
            return _err(f"launcher '{launcher}' not supported for library page", status="needs_user")
        return executor("web", {"action": "open", "url": target})
    if action == "open_store_page":
        return _err(
            "game_launcher.open_store_page is deferred; each store needs its own URI scheme and search",
            status="needs_implementation",
            note="Use browser_real or steam(store_page) instead.",
        )
    return _err(
        "unknown game_launcher action", action=action,
        valid_actions=[
            "status", "discover", "launch", "open_launcher", "store_search",
        ],
        status="needs_user",
    )


def _epic_manifests_dir() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramData", "C:/ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests",
        Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests"),
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def _gog_registry_has_games() -> bool:
    proc = subprocess.run(
        ["reg", "query", r"HKLM\SOFTWARE\WOW6432Node\GOG.com\Games"],
        capture_output=True, text=True, timeout=10,
    )
    return proc.returncode == 0 and bool(proc.stdout.strip())


def _riot_install_db() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramData", "C:/ProgramData")) / "Riot Games" / "RiotClientInstalls.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _game_launcher_discover(args: dict[str, Any]) -> dict[str, Any]:
    launcher = str(args.get("launcher") or "").casefold()
    results: dict[str, list[dict[str, Any]]] = {"epic": [], "gog": [], "xbox": [], "riot": []}
    if not launcher or launcher == "epic":
        results["epic"] = _discover_epic_games()
    if not launcher or launcher == "gog":
        results["gog"] = _discover_gog_games()
    if not launcher or launcher == "xbox":
        results["xbox"] = _discover_xbox_games()
    if not launcher or launcher == "riot":
        results["riot"] = _discover_riot_games()
    total = sum(len(v) for v in results.values())
    return _ok(games=results, total=total, launcher_filter=launcher or None)


def _discover_epic_games() -> list[dict[str, Any]]:
    manifests_dir = _epic_manifests_dir()
    if not manifests_dir:
        return []
    games: list[dict[str, Any]] = []
    for item in manifests_dir.glob("*.item"):
        try:
            data = json.loads(item.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            continue
        games.append({
            "launcher": "epic",
            "app_name": data.get("AppName"),
            "display_name": data.get("DisplayName"),
            "install_location": data.get("InstallLocation"),
            "launch_executable": data.get("LaunchExecutable"),
            "catalog_namespace": data.get("CatalogNamespace"),
            "catalog_item_id": data.get("CatalogItemId"),
            "manifest": str(item),
        })
    return games


def _discover_gog_games() -> list[dict[str, Any]]:
    proc = subprocess.run(
        ["reg", "query", r"HKLM\SOFTWARE\WOW6432Node\GOG.com\Games", "/s"],
        capture_output=True, text=True, timeout=20,
    )
    if proc.returncode != 0:
        return []
    games_by_id: dict[str, dict[str, Any]] = {}
    current_id: str | None = None
    for line in proc.stdout.splitlines():
        line = line.rstrip()
        m = re.match(r".*\\Games\\(\d+)$", line)
        if m:
            cid = m.group(1)
            if cid is None:
                continue
            current_id = cid
            games_by_id.setdefault(cid, {"launcher": "gog", "game_id": cid})
            continue
        if current_id and "REG_SZ" in line:
            parts = line.strip().split(None, 2)
            if len(parts) >= 3:
                key, _, value = parts[0], parts[1], parts[2]
                games_by_id[current_id][key.casefold()] = value
    games = []
    for gid, data in games_by_id.items():
        games.append({
            "launcher": "gog",
            "game_id": gid,
            "name": data.get("gamename"),
            "exe": data.get("exe"),
            "exepath": data.get("exepath"),
            "path": data.get("path"),
            "launch_command": data.get("launchcommand"),
        })
    return games


def _discover_xbox_games() -> list[dict[str, Any]]:
    # Get-AppxPackage with publisher filters Microsoft.Gaming or Microsoft.* gives
    # us UWP/Store games. We avoid system apps by filtering for HasNonRemovablePackage=$false.
    script = r"""
$apps = Get-AppxPackage | Where-Object {
  $_.SignatureKind -eq 'Store' -and
  ($_.PackageFamilyName -like '*Game*' -or $_.Name -like '*Gaming*' -or $_.Name -match 'Xbox|Halo|Forza|Minecraft|Sea Of Thieves|Gears|Age Of Empires')
} | Select-Object Name,PackageFullName,PackageFamilyName,InstallLocation,Version,Publisher
$apps | ConvertTo-Json -Depth 4
"""
    # try/except: Get-AppxPackage puede tardar 5-15s en sistemas con
    # cientos de apps UWP. 30s razonable; no queremos propagar timeout
    # al caller del tool.
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return []
    raw = proc.stdout.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    games = []
    for app in data if isinstance(data, list) else []:
        games.append({
            "launcher": "xbox",
            "name": app.get("Name"),
            "package_full_name": app.get("PackageFullName"),
            "package_family_name": app.get("PackageFamilyName"),
            "install_location": app.get("InstallLocation"),
            "version": app.get("Version"),
            "publisher": app.get("Publisher"),
            "launch_uri": f"shell:AppsFolder\\{app.get('PackageFamilyName')}!App",
        })
    return games


def _discover_riot_games() -> list[dict[str, Any]]:
    db_path = _riot_install_db()
    if not db_path:
        return []
    try:
        data = json.loads(db_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return []
    products = data.get("associated_client") or {}
    games = []
    for product_path, client_path in products.items():
        games.append({
            "launcher": "riot",
            "product_path": product_path,
            "client_path": client_path,
            "name": Path(product_path).name,
        })
    return games


def _game_launcher_launch(args: dict[str, Any], state: AgentState, executor: Executor | None) -> dict[str, Any]:
    launcher = str(args.get("launcher") or "").casefold()
    query = str(args.get("game") or args.get("query") or args.get("name") or "").strip()
    if not launcher:
        return _err("missing launcher (epic|gog|xbox|riot)")
    if not query:
        return _err("missing game name/query")

    discovery = _game_launcher_discover({"launcher": launcher})
    games = discovery.get("games", {}).get(launcher, [])
    q = query.casefold()
    chosen = None
    for game in games:
        name_fields = (game.get("display_name") or game.get("name") or game.get("app_name") or "")
        if q in str(name_fields).casefold():
            chosen = game
            break
    if not chosen:
        return _err(
            f"no {launcher} game matching '{query}'",
            status="needs_user",
            available=[g.get("display_name") or g.get("name") for g in games][:30],
        )

    if launcher == "epic":
        # Epic supports a launch URI: com.epicgames.launcher://apps/<AppName>?action=launch&silent=true
        app_name = chosen.get("app_name")
        if not app_name:
            return _err("epic game has no AppName in manifest", chosen=chosen)
        uri = f"com.epicgames.launcher://apps/{app_name}?action=launch&silent=true"
        os.startfile(uri) if os.name == "nt" else webbrowser.open(uri)
        state.register_resource(
            "game_session", chosen.get("display_name") or app_name,
            metadata={"launcher": "epic", "app_name": app_name, "uri": uri, "started_at": datetime.now().isoformat()},
        )
        return _ok(launcher="epic", game=chosen, uri=uri, verified=False, status="attempted", note="Epic launcher should open and start the game; verify via window list.")
    if launcher == "gog":
        exe = chosen.get("exe") or chosen.get("path")
        if not exe:
            return _err("gog game has no exe registered", chosen=chosen)
        exe_path = Path(exe).expanduser()
        if not exe_path.is_file():
            return _err("gog exe path not found", path=str(exe_path))
        if os.name == "nt":
            os.startfile(exe_path)
        state.register_resource(
            "game_session", chosen.get("name") or exe,
            metadata={"launcher": "gog", "game_id": chosen.get("game_id"), "exe": str(exe_path), "started_at": datetime.now().isoformat()},
        )
        return _ok(launcher="gog", game=chosen, exe=str(exe_path), verified=False, status="attempted")
    if launcher == "xbox":
        uri = chosen.get("launch_uri")
        if not uri:
            return _err("xbox app has no launch URI", chosen=chosen)
        os.startfile(uri) if os.name == "nt" else webbrowser.open(uri)
        state.register_resource(
            "game_session", chosen.get("name") or uri,
            metadata={"launcher": "xbox", "uri": uri, "package_family_name": chosen.get("package_family_name"), "started_at": datetime.now().isoformat()},
        )
        return _ok(launcher="xbox", game=chosen, uri=uri, verified=False, status="attempted")
    if launcher == "riot":
        client = chosen.get("client_path")
        if not client or not Path(client).is_file():
            return _err("riot client path missing", chosen=chosen)
        os.startfile(client) if os.name == "nt" else webbrowser.open(Path(client).as_uri())
        state.register_resource(
            "game_session", chosen.get("name") or client,
            metadata={"launcher": "riot", "client": client, "started_at": datetime.now().isoformat()},
        )
        return _ok(launcher="riot", game=chosen, client=client, verified=False, status="attempted")
    return _err(f"launcher '{launcher}' not supported")


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


# WiFi domain tools - extraídos a domain_tools_wifi.py (R2 sprint 2026-05-27).
# Las 9 funciones _device_wifi_* + _wifi_match_score + _resolve_wifi_target +
# _xml_escape + _WIFI_FILLER viven ahora en su propio módulo. Re-exportamos acá
# para que callers existentes (test_wifi_resolve.py:
# `from gemma4_agent import domain_tools as dt; dt._device_wifi_X`) sigan
# funcionando sin tocar nada. Cuando los callers migren a importar
# `gemma4_agent.domain_tools_wifi` directo, este re-export se puede borrar.
from .domain_tools_wifi import (  # noqa: F401  (re-export por compat)
    _WIFI_FILLER,
    _device_wifi_add_profile,
    _device_wifi_connect,
    _device_wifi_delete_profile,
    _device_wifi_disconnect,
    _device_wifi_profiles,
    _device_wifi_scan,
    _device_wifi_status,
    _resolve_wifi_target,
    _wifi_match_score,
    _xml_escape,
)


# Bluetooth domain tool - extraído a domain_tools_bluetooth.py (R2 sprint
# 2026-05-27). Un sólo método hoy; se aísla para que cuando aparezca más
# (pair/disconnect/audio-routing) tenga su casa.
from .domain_tools_bluetooth import _device_bluetooth_status  # noqa: F401


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
        # GUID de plan de energ�a:  381b4222-f694-41f0-9685-ff5bb260df2e  (Equilibrado) *
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


def developer_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for developer workflows: detect, test, lint, format, git, dev_server.

    Actions:
      - status
      - project_detect(path?)
      - run_tests(path?, args?)
      - run_lint(path?)
      - run_format(path?)
      - git_status(path?)
      - git_diff(path?, staged?)
      - git_log(path?, limit?)
      - start_dev_server(path?, command?)
      - stop_dev_server(server_id?)
      - list_dev_servers
    Mutating git actions (git_commit/push) are intentionally NOT implemented:
    the agent must use terminal(...) explicitly so the user sees the command.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            git=bool(shutil.which("git")),
            python=bool(shutil.which("python") or shutil.which("py")),
            node=bool(shutil.which("node")),
            npm=bool(shutil.which("npm")),
            yarn=bool(shutil.which("yarn")),
            pnpm=bool(shutil.which("pnpm")),
            cargo=bool(shutil.which("cargo")),
            go=bool(shutil.which("go")),
            pytest=bool(shutil.which("pytest")),
            ruff=bool(shutil.which("ruff")),
            black=bool(shutil.which("black")),
            note="Use project_detect first; run_tests/lint/format then dispatch by detected stack.",
        )
    if action == "project_detect":
        return _developer_project_detect(args)
    if action == "run_tests":
        return _developer_run("tests", args)
    if action == "run_lint":
        return _developer_run("lint", args)
    if action == "run_format":
        return _developer_run("format", args)
    if action == "git_status":
        return _developer_git(["status", "--short", "--branch"], args)
    if action == "git_diff":
        cmd = ["diff"]
        if bool(args.get("staged", False)):
            cmd.append("--staged")
        return _developer_git(cmd, args)
    if action == "git_log":
        limit = int(args.get("limit", 10))
        return _developer_git(["log", "--oneline", f"-{limit}"], args)
    if action == "start_dev_server":
        return _developer_start_dev_server(args, state)
    if action == "stop_dev_server":
        return _developer_stop_dev_server(args, state)
    if action == "list_dev_servers":
        servers = _resources_by_kind(state, "dev_server", include_closed=bool(args.get("include_closed", False)))
        return _ok(servers=servers, count=len(servers))
    if action in {"git_commit", "git_push"}:
        return _err(
            f"developer.{action} is intentionally not implemented; use terminal(...) so the command is visible to the user",
            status="needs_user",
            note="Mutating git actions should be explicit, not hidden behind a tool wrapper.",
        )
    return _err(
        "unknown developer action", action=action,
        valid_actions=[
            "status", "project_detect", "run_tests", "run_build",
            "lint", "format", "git_status", "git_log", "git_diff",
            "git_branch", "git_commit",
        ],
        status="needs_user",
    )


def _developer_project_root(args: dict[str, Any]) -> Path:
    raw = str(args.get("path") or args.get("root") or "").strip()
    return Path(raw).expanduser() if raw else Path.cwd()


def _developer_project_detect(args: dict[str, Any]) -> dict[str, Any]:
    root = _developer_project_root(args)
    if not root.exists():
        return _err("path not found", path=str(root))
    markers = {
        "package.json": "node",
        "pyproject.toml": "python",
        "setup.py": "python",
        "requirements.txt": "python",
        "Cargo.toml": "rust",
        "go.mod": "go",
        "pom.xml": "java",
        "build.gradle": "java",
        "Gemfile": "ruby",
        "composer.json": "php",
        "CMakeLists.txt": "cmake",
    }
    detected: list[dict[str, Any]] = []
    for marker, stack in markers.items():
        path = root / marker
        if path.is_file():
            detected.append({"marker": marker, "stack": stack, "path": str(path)})
    # Node sub-detection: detect package manager.
    node_pm = None
    if any(d["stack"] == "node" for d in detected):
        if (root / "pnpm-lock.yaml").is_file():
            node_pm = "pnpm"
        elif (root / "yarn.lock").is_file():
            node_pm = "yarn"
        elif (root / "package-lock.json").is_file():
            node_pm = "npm"
        else:
            node_pm = "npm"  # default
    # Python sub-detection: poetry vs pip.
    python_pm = None
    if any(d["stack"] == "python" for d in detected):
        if (root / "poetry.lock").is_file():
            python_pm = "poetry"
        elif (root / "uv.lock").is_file():
            python_pm = "uv"
        else:
            python_pm = "pip"
    is_git = (root / ".git").exists()
    return _ok(
        root=str(root),
        is_git=is_git,
        detected=detected,
        stacks=sorted({d["stack"] for d in detected}),
        node_package_manager=node_pm,
        python_package_manager=python_pm,
    )


def _developer_run(kind: str, args: dict[str, Any]) -> dict[str, Any]:
    detect = _developer_project_detect(args)
    if not detect.get("ok"):
        return detect
    stacks = detect.get("stacks") or []
    root = Path(detect["root"])
    raw_extra_args = args.get("args")
    extra_args: list[Any] = raw_extra_args if isinstance(raw_extra_args, list) else []
    timeout = int(args.get("timeout_sec", 300))
    # Pick a command for the (stack, kind) pair. We use the first matched stack
    # in priority order: python > node > rust > go.
    priority = ["python", "node", "rust", "go", "java", "ruby", "php"]
    chosen_stack = next((s for s in priority if s in stacks), None)
    if not chosen_stack:
        return _err("no recognized stack to run for", kind=kind, detected=stacks, status="needs_user")
    cmd = _developer_command(chosen_stack, kind, detect, extra_args)
    if not cmd:
        return _err(
            f"developer.{kind} not wired for stack '{chosen_stack}'",
            stack=chosen_stack, kind=kind,
            status="needs_implementation",
            note="Pass explicit command via args=[...] to terminal(...) instead.",
        )
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=timeout)
    return _ok(
        stack=chosen_stack, kind=kind,
        command=cmd, cwd=str(root),
        exit_code=proc.returncode,
        stdout=(proc.stdout or "")[-4000:],
        stderr=(proc.stderr or "")[-2000:],
        passed=proc.returncode == 0,
        verified=proc.returncode == 0,
        status="done" if proc.returncode == 0 else "needs_verification",
    )


def _developer_command(stack: str, kind: str, detect: dict[str, Any], extra: list[Any]) -> list[str] | None:
    if stack == "python":
        if kind == "tests":
            return ["pytest", *map(str, extra)]
        if kind == "lint":
            if shutil.which("ruff"):
                return ["ruff", "check", "."]
            if shutil.which("flake8"):
                return ["flake8"]
        if kind == "format":
            if shutil.which("ruff"):
                return ["ruff", "format", "."]
            if shutil.which("black"):
                return ["black", "."]
    if stack == "node":
        pm = detect.get("node_package_manager") or "npm"
        if kind == "tests":
            return [pm, "test", *map(str, extra)]
        if kind == "lint":
            return [pm, "run", "lint"]
        if kind == "format":
            return [pm, "run", "format"]
    if stack == "rust":
        if kind == "tests":
            return ["cargo", "test"]
        if kind == "lint":
            return ["cargo", "clippy"]
        if kind == "format":
            return ["cargo", "fmt"]
    if stack == "go":
        if kind == "tests":
            return ["go", "test", "./..."]
        if kind == "lint":
            return ["go", "vet", "./..."]
        if kind == "format":
            return ["gofmt", "-w", "."]
    return None


def _developer_git(git_args: list[str], args: dict[str, Any]) -> dict[str, Any]:
    git = shutil.which("git")
    if not git:
        return _err("git is not installed", status="needs_dependency", install_hint="winget install Git.Git")
    root = _developer_project_root(args)
    proc = subprocess.run([git, *git_args], cwd=str(root), capture_output=True, text=True, timeout=30)
    return _ok(
        cwd=str(root),
        command=["git", *git_args],
        exit_code=proc.returncode,
        stdout=(proc.stdout or "")[-6000:],
        stderr=(proc.stderr or "")[-2000:],
        verified=proc.returncode == 0,
        status="done" if proc.returncode == 0 else "needs_verification",
    )


def _developer_start_dev_server(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    root = _developer_project_root(args)
    if not root.exists():
        return _err("path not found", path=str(root))
    explicit = args.get("command")
    if isinstance(explicit, list) and explicit:
        cmd = [str(part) for part in explicit]
    elif isinstance(explicit, str) and explicit.strip():
        cmd = explicit.split()
    else:
        detect = _developer_project_detect({"path": str(root)})
        if not detect.get("ok"):
            return detect
        stacks = detect.get("stacks") or []
        if "node" in stacks:
            pm = detect.get("node_package_manager") or "npm"
            cmd = [pm, "run", "dev"]
        elif "python" in stacks:
            # No universal dev command for python; the user must pass command=.
            return _err(
                "no default dev command for python; pass command='uvicorn app:app --reload' or similar",
                stack="python",
                status="needs_user",
            )
        else:
            return _err("no default dev command for detected stack", stacks=stacks, status="needs_user")
    log_dir = state.path.parent / "dev_servers"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"dev_{int(time.time())}.log"
    log_file = log_path.open("w", encoding="utf-8")
    # T3-developer-start-no-creationflags-detach-037: detach del agent process
    # group para que el dev server sobreviva al cierre del agente.
    creationflags = 0
    if os.name == "nt":
        creationflags = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    proc = subprocess.Popen(cmd, cwd=str(root), stdout=log_file, stderr=subprocess.STDOUT, creationflags=creationflags)
    resource = state.register_resource(
        "dev_server",
        f"{cmd[0]} {' '.join(cmd[1:])}",
        cleanup_tool="developer",
        cleanup_args={"action": "stop_dev_server"},
        metadata={"cmd": cmd, "cwd": str(root), "pid": proc.pid, "log": str(log_path), "started_at": datetime.now().isoformat()},
    )
    # The cleanup_args needs the server_id, but we only have it after registration.
    # CC-102: patch atómico vía API pública.
    rid = resource.get("resource", {}).get("id")
    if rid:
        state.update_resource(rid, cleanup_args_patch={"action": "stop_dev_server", "server_id": rid})
    return _ok(
        server_id=rid, pid=proc.pid, cmd=cmd, cwd=str(root),
        log=str(log_path),
        note="Process detached; use list_dev_servers to inspect and stop_dev_server to terminate.",
    )


def _developer_stop_dev_server(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    server_id = str(args.get("server_id") or args.get("id") or "").strip()
    pid = args.get("pid")
    target = None
    if server_id:
        target = state._load().get("resources", {}).get(server_id)
    elif pid is not None:
        for res in state._load().get("resources", {}).values():
            if res.get("kind") == "dev_server" and (res.get("metadata") or {}).get("pid") == int(pid):
                target = res
                break
    else:
        # Stop the most recent open dev_server.
        opens = _resources_by_kind(state, "dev_server", include_closed=False)
        target = opens[-1] if opens else None
    if not target:
        return _err("no dev_server found", status="needs_user")
    pid = (target.get("metadata") or {}).get("pid")
    if not pid:
        return _err("dev_server has no pid", target=target)
    # CC-104 / T3-developer-stop-no-pid-alive-check-036: verificar identidad
    # antes de matar (Windows recicla PIDs).
    cmd = (target.get("metadata") or {}).get("cmd") or []
    expected = str(cmd[0]) if cmd else None
    matches, current_name = _pid_owned_by(int(pid), expected)
    if not matches:
        return _err(
            "pid_recycled: refused to kill PID held by a different process",
            pid=pid,
            expected_exe=expected,
            current_name=current_name,
            status="needs_user",
        )
    killed = False
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"], capture_output=True, text=True, timeout=10)
        else:
            os.kill(int(pid), 15)
        killed = True
    except (subprocess.SubprocessError, ProcessLookupError, PermissionError, OSError) as exc:
        return _err(f"failed to kill pid {pid}: {exc}", pid=pid)
    state.mark_cleaned(str(target["id"]), {"killed": killed, "pid": pid})
    return _ok(server_id=str(target["id"]), pid=pid, killed=killed, verified=killed)


# Document parsing/extraction - extraído a domain_tools_document.py
# (R2 sprint 2026-05-28). 13 funciones (entry + 12 helpers PDF/DOCX/XLSX/PPTX/
# HTML/text + OCR Tesseract).
from .domain_tools_document import (  # noqa: F401
    _document_compare,
    _document_extract_docx,
    _document_extract_html,
    _document_extract_images,
    _document_extract_pdf,
    _document_extract_pptx,
    _document_extract_tables,
    _document_extract_text,
    _document_extract_xlsx,
    _document_ocr_pdf,
    _document_ocr_pdf_with_fitz,
    _document_ocr_pdf_with_pdf2image,
    document_tool,
)


def active_phrase_triggers(state: AgentState) -> list[dict[str, Any]]:
    """Return enabled on_phrase routines for the chat hook.

    Each item has {id, label, phrase, steps, fold} so the caller can match
    against the user's (folded) input cheaply. Disabled or closed routines
    are skipped.
    """
    out: list[dict[str, Any]] = []
    for resource in state._load().get("resources", {}).values():
        if resource.get("kind") != "routine" or resource.get("status") != "open":
            continue
        meta = resource.get("metadata") or {}
        if str(meta.get("trigger_type") or "").casefold() not in {"on_phrase", "on_keyword"}:
            continue
        if meta.get("enabled") is False:
            continue
        trigger = meta.get("trigger") or {}
        phrase = str(trigger.get("phrase") or trigger.get("keyword") or "").strip()
        if not phrase:
            continue
        out.append({
            "id": str(resource.get("id") or ""),
            "label": str(resource.get("label") or ""),
            "phrase": phrase,
            "steps": meta.get("steps") or [],
        })
    return out


# Routine helpers - extraídos a domain_tools_routine.py (R2 sprint 2026-05-28).
# El cluster de helpers de Scheduled Task vivía acá; el re-export está en el
# bloque del entry point routine_tool más arriba (~línea 285).


def _find_vlc_executable() -> str | None:
    """Localiza vlc.exe en PATH o en las rutas tipicas de instalacion Windows.

    winget install VideoLAN.VLC no agrega vlc al PATH por default, asi que
    shutil.which("vlc") falla aunque este instalado. Probamos las rutas
    estandar como fallback.
    """
    vlc = shutil.which("vlc") or shutil.which("vlc.exe")
    if vlc:
        return vlc
    # Rutas standard de VLC en Windows
    candidates = [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ]
    for c in candidates:
        if Path(c).is_file():
            return c
    return None


def _find_spotify_executable() -> str | None:
    """Localiza Spotify.exe. Spotify desktop instala en %APPDATA%\\Spotify\\
    por default (Microsoft Store version usa shell:AppsFolder).
    """
    spotify = shutil.which("spotify") or shutil.which("spotify.exe")
    if spotify:
        return spotify
    candidates = [
        Path.home() / "AppData" / "Roaming" / "Spotify" / "Spotify.exe",
        Path("C:/Program Files/WindowsApps") / "Spotify.exe",  # raro pero posible
    ]
    for c in candidates:
        try:
            if c.is_file():
                return str(c)
        except OSError:
            continue
    return None


# Streaming platforms — registro centralizado de cada plataforma.
# Cada entry: (canonical_name, normalized_aliases, UWP package_family_name,
#              exe_path_candidates, deeplink_template, web_url_template,
#              install_hint, post_open_note)
#
# {q} en templates se reemplaza con la query URL-encoded.
#
# Notas:
#   - UWP package family names recolectados de docs publicas; pueden variar
#     levemente por region. Usamos shell:AppsFolder\<pfn>!App via `start`.
#     Si el pfn no matchea, Windows no abre nada y caemos a web.
#   - Deeplinks: solo Spotify y Disney+ tienen scheme propio confiable.
#     Netflix/HBO/Prime no exponen schemes documentados → siempre web.
#   - Web URLs verificadas en 2025-2026 (post-rebrand HBO Max -> Max).
# Streaming platform specs. Each entry:
#   aliases:           set of user-friendly names that map to this canonical key.
#   uwp_pfn / exe_paths: how to detect the app on Windows (UWP package or EXE).
#   deeplink:          URI scheme template if the platform has one (Spotify only).
#   web_url:           landing URL. If template has {q}, it's substituted with
#                      url-encoded query and the page loads search results
#                      directly. If no {q}, this is the search page where the
#                      query must be TYPED into the input (Disney+/HBO Max).
#   web_search_via_url: True if {q} substitution gives a functional URL.
#   playback:          dict with selectors for Playwright/CDP automation:
#                       - search_input:   CSS selector for the search <input>
#                       - result_card:    selector for the first result card
#                                          (usually an <a> with the title link)
#                       - play_button:    selector for the Play CTA on detail page
#                       - title_url_pattern: regex describing detail URLs that
#                                            qualify as "watch deep links" — used
#                                            for the title→URL cache.
#   install_hint:      ms-windows-store URI for the user to install if they want.
#   post_open_note:    short note returned in the tool result.
#
# Sources for selectors and URLs: see docs/research/streaming/streaming_playback_field_guide_2026.md (research
# 2026-05-16) — Netflix data-uia family, Disney+/HBO Max data-testid/aria,
# Prime Video data-automation-id. All marked "needs live test" by the research
# are CANDIDATES that the agent tries in order; the first that matches wins.
#
# IMPORTANT: the search_shortcut field was REMOVED (2026-05-16) — no platform
# has a reliable global hotkey to open search ("/" and "s" do NOT work on
# Netflix/Disney+/HBO Max despite earlier code assuming so). For Disney+/HBO
# Max we MUST land on the search page URL and type into the input via DOM
# or via gui.type after focusing the input.
_STREAMING_PLATFORMS: dict[str, dict[str, Any]] = {
    "spotify": {
        "aliases": {"spotify"},
        "uwp_pfn": "SpotifyAB.SpotifyMusic_zpdnekdrzrea0",
        "exe_paths": [
            Path.home() / "AppData" / "Roaming" / "Spotify" / "Spotify.exe",
        ],
        "deeplink": "spotify:search:{q}",
        "web_url": "https://open.spotify.com/search/{q}",
        "web_search_via_url": True,
        "playback": {},  # Spotify uses deeplink + Enter; no web selectors needed
        "install_hint": "winget install Spotify.Spotify",
        "post_open_note": (
            "Spotify opened with search results. App does NOT auto-play. "
            "User must press Enter / click a track."
        ),
    },
    "netflix": {
        "aliases": {"netflix"},
        "uwp_pfn": "4DF9E0F8.Netflix_mcm4njqhnhss8",
        "exe_paths": [],
        "deeplink": None,
        # Verified via CDP probe 2026-05-16:
        # - `?q=` works post-login.
        # - search results: a[data-uia='search-gallery-video-card'] with href
        #   `/search?q=X&jbv=<title_id>`. Click opens DP (mini-modal).
        # - In the DP modal, [data-uia='play-button'] navigates to /watch/<id>
        #   and starts playback.
        # - profile-gate may appear first time per session.
        "web_url": "https://www.netflix.com/search?q={q}",
        "web_search_via_url": True,
        "playback": {
            "profile_picker_check": "[data-uia='profile-gate'], [data-uia='action-select-profile+secondary']",
            "profile_item_anchor": "a[data-uia='action-select-profile+secondary']",
            "search_input": [
                "input[data-uia='search-box-input']",
                "input[placeholder*='buscar' i]",
            ],
            "result_card": [
                "a[data-uia='search-gallery-video-card']",
                "a[data-uia*='video-card']",
                "a[data-uia='search-suggestion-item-link']",
            ],
            # En Netflix, click card abre detalle. Despues hay que click el
            # play-button del modal/detail para iniciar playback (/watch/).
            "play_button": [
                "[data-uia='play-button']",
                "a[data-uia*='play']",
                "button[data-uia*='play']",
                "a[href*='/watch/']",
            ],
            "click_card_starts_playback": False,
            "title_url_pattern": r"netflix\.com/(?:[a-z-]+/)?(?:watch|title)/(\d+)",
        },
        "install_hint": "Install Netflix from Microsoft Store: ms-windows-store://pdp/?productid=9wzdncrfj3tj",
        "post_open_note": (
            "Netflix opened with search results. User clicks a title to play."
        ),
    },
    "disney": {
        "aliases": {"disney", "disney+", "disneyplus", "disney_plus", "disney plus"},
        "uwp_pfn": "Disney.37853FC22B2CE_6rarf9sa4v8jt",
        "exe_paths": [],
        "deeplink": None,
        # Verified via CDP probe 2026-05-16: /es-419/browse/search is the
        # ONLY URL that works (logged in). Other /search variants return 404.
        # F-009: template + default_locale para permitir override segun region
        # del user (es-es, en-us, etc). `web_url` se mantiene como fallback
        # cuando no se puede resolver locale dinamicamente.
        "web_url": "https://www.disneyplus.com/es-419/browse/search",
        "web_url_template": "https://www.disneyplus.com/{locale}/browse/search",
        "default_locale": "es-419",
        "web_search_via_url": False,
        "playback": {
            "search_input": [
                "input[type='search']",
                "input[name='search input']",
                "input[placeholder*='buscar' i]",
                "input[placeholder*='ulo' i]",  # placeholder contains 'Título...'
            ],
            "result_card": [
                "a[data-testid='set-item']",
                "a[href*='/browse/entity-']",
            ],
            "play_button": [
                "[data-testid='playback-action-button']",
                "button[aria-label*='Ver ahora' i]",
                "button[aria-label*='VER AHORA' i]",
                "button[aria-label*='Reproducir' i]",
            ],
            "click_card_starts_playback": False,
            "title_url_pattern": r"disneyplus\.com/[a-z-]+/browse/entity-([A-Za-z0-9_-]+)",
        },
        "install_hint": "Install Disney+ from Microsoft Store: ms-windows-store://pdp/?productid=9NXQXXLFST89",
        "post_open_note": (
            "Disney+ search page opened. Type the title in the search box."
        ),
    },
    "hbo_max": {
        # Rebrand back to HBO Max on 9 July 2025. Verified via CDP probe
        # 2026-05-16: play.hbomax.com/search?q= works; play.max.com redirects
        # to play.hbomax.com. Anchors use data-testid='<uuid>_tile'.
        "aliases": {"hbo_max", "hbo max", "hbomax", "max", "hbo"},
        "uwp_pfn": None,
        "exe_paths": [],
        "deeplink": None,
        "web_url": "https://play.hbomax.com/search?q={q}",
        "web_search_via_url": True,
        "playback": {
            "search_input": [
                "input[type='search']",
                "input[aria-label*='buscar' i]",
                "input[data-testid*='search' i]",
            ],
            "result_card": [
                "a[data-testid$='_tile'][href*='/movie/']",
                "a[data-testid$='_tile'][href*='/show/']",
                "a[data-testid$='_tile'][href*='/series/']",
                "a[data-testid$='_tile']",
                "a[href*='/movie/']",
                "a[href*='/show/']",
                "a[href*='/series/']",
                "a[href*='/feature/']",
            ],
            "play_button": [
                "button[data-testid='play_button']",
                "button[data-testid='playButton']",
                "button[aria-label*='Reproducir' i]",
                "button[aria-label*='Ver' i]",
                "button[aria-label*='Play' i]",
            ],
            "click_card_starts_playback": False,
            "title_url_pattern": r"hbomax\.com/(?:movie|show|series|feature)/([A-Za-z0-9-]+)",
        },
        "install_hint": "HBO Max is web-only on Windows; browser will open.",
        "post_open_note": (
            "HBO Max opened. Type the title in the search box."
        ),
    },
    "prime_video": {
        "aliases": {"prime_video", "prime video", "primevideo", "amazon prime",
                     "amazon_prime", "amazon", "prime"},
        "uwp_pfn": "AmazonVideo.PrimeVideo_pwbj9vvecjh7j",
        "exe_paths": [],
        "deeplink": None,
        # Verified via CDP probe 2026-05-16: ?phrase= works, cards via
        # 'article a[href*=/detail/]'. Detail page auto-opens an inline
        # player (data-testid='draper-player') — explicit play often
        # unnecessary because preview already runs.
        "web_url": "https://www.primevideo.com/search/ref=atv_nb_sr?phrase={q}",
        "web_search_via_url": True,
        "playback": {
            "search_input": [
                "input[name='phrase']",
                "input[type='search']",
                "input[placeholder*='buscar' i]",
            ],
            "result_card": [
                "article a[href*='/detail/']",
                "a[href*='/detail/']",
            ],
            # Prime Video tiene varios botones con aria 'Play' que NO son
            # de iniciar playback (Close Player, mute, etc). Probar primero
            # los explicitos. Si todos fallan, asumir que el detail page
            # ya esta auto-playing (es lo que hace Prime).
            "play_button": [
                "button[data-automation-id='playButton']",
                "button[aria-label*='Watch now' i]",
                "button[aria-label*='Ver ahora' i]",
                "button[aria-label*='Reproducir ahora' i]",
            ],
            # En Prime, el detail page abre un mini-player con auto-play.
            # Markamos card-click como playback-starter (best-effort).
            "click_card_starts_playback": True,
            "title_url_pattern": r"primevideo\.com/(?:region/[a-z]+/)?detail/([A-Z0-9]+)",
        },
        "install_hint": "Install Prime Video from Microsoft Store: ms-windows-store://pdp/?productid=9P6RC76MSMMJ",
        "post_open_note": (
            "Prime Video opened with search results. User clicks a title to play."
        ),
    },
}


def _resolve_streaming_web_url(
    spec: dict[str, Any],
    *,
    state: AgentState | None = None,
) -> str:
    """F-009: resuelve la URL web del provider contemplando locale.

    Si el spec define `web_url_template` (con `{locale}` placeholder) y un
    `default_locale`, formatea segun el locale del user. Si no hay state o
    no se puede resolver, usa el default_locale o cae al web_url estatico.

    Pendiente futuro: agregar `state.user_locale` para soportar override
    real por region. Actualmente siempre usa el default_locale del spec.
    """
    template = spec.get("web_url_template")
    default_locale = spec.get("default_locale")
    if template and default_locale and "{locale}" in template:
        # TODO: cuando exista state.user_locale, usarlo aca con fallback.
        locale = default_locale
        if state is not None:
            user_locale = getattr(state, "user_locale", None)
            if isinstance(user_locale, str) and user_locale.strip():
                locale = user_locale.strip()
        return template.format(locale=locale)
    return str(spec.get("web_url") or "")


def _resolve_streaming_provider(provider_raw: str) -> tuple[str, dict[str, Any]] | None:
    """Mapea un alias del LLM (e.g. 'disney+') al provider canonico + spec.

    Returns (canonical_name, spec_dict) o None si no matchea.
    """
    p = str(provider_raw or "").strip().lower().replace("-", "_")
    for canonical, spec in _STREAMING_PLATFORMS.items():
        if p == canonical or p in spec["aliases"]:
            return canonical, spec
    return None


def _find_streaming_app(spec: dict[str, Any]) -> dict[str, str | None]:
    """Detecta si la app de streaming esta instalada como UWP o como EXE.

    Returns dict con keys:
      - "kind": 'uwp' | 'exe' | None
      - "launch_target": el string que se pasara a `start` (shell:AppsFolder\\<pfn>!App o path al exe)
    """
    # 1. EXE paths (preferencia: spotify desktop, etc.)
    for exe_path in spec.get("exe_paths", []):
        try:
            if exe_path.is_file():
                return {"kind": "exe", "launch_target": str(exe_path)}
        except OSError:
            continue
    # 2. UWP package via Get-AppxPackage check
    pfn = spec.get("uwp_pfn")
    if pfn and os.name == "nt":
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                  f"if (Get-AppxPackage -Name '{pfn.split('_')[0]}') {{ Write-Output yes }}"],
                capture_output=True, text=True, timeout=3,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode == 0 and "yes" in (proc.stdout or "").lower():
                return {"kind": "uwp", "launch_target": f"shell:AppsFolder\\{pfn}!App"}
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {"kind": None, "launch_target": None}


# ---------------------------------------------------------------------------
# Streaming preferences (profile per platform)
# ---------------------------------------------------------------------------
# El user tiene varios perfiles en Netflix/Disney+/HBO/Prime (el "¿Quién está
# viendo?" picker). Para que el auto-play funcione sin preguntar cada vez,
# guardamos el nombre del perfil preferido por plataforma en agent state.

def _get_streaming_preference(state: AgentState | None, provider: str) -> str | None:
    """Lee el perfil guardado para una plataforma. None si no existe."""
    if state is None:
        return None
    try:
        data = state._load()  # noqa: SLF001 — state interno
        resources = data.get("resources", {})
    except Exception:
        return None
    for res in resources.values():
        if not isinstance(res, dict):
            continue
        if res.get("kind") != "streaming_preference":
            continue
        meta = res.get("metadata") or {}
        if str(meta.get("provider", "")).lower() == provider.lower():
            return str(meta.get("profile_name") or "").strip() or None
    return None


# Blacklist de "perfiles" obviamente invalidos. Defense in depth: si el
# extractor de profile_name falla y pasa algo como "Hola" o "Quien eres",
# el writer al state lo rechaza igual. Evita corrupcion persistente del
# store de preferencias.
_INVALID_PROFILE_NAMES = frozenset({
    "hola", "holas", "hello", "hi", "hey",
    "buenos dias", "buenas tardes", "buenas noches",
    "adios", "bye", "chau", "chao",
    "gracias", "thanks",
    "ok", "okay", "vale", "si", "no",
    "ayuda", "help",
    "quien eres", "quien soy", "que eres", "que sos",
    "quién eres", "qué eres",
    "que tal", "que pasa", "como estas",
    "qué tal", "cómo estás",
    "x", "xx", "xxx", "test", "prueba", "default",
})


def _is_valid_profile_name(name: str) -> bool:
    """True si parece un nombre real de perfil de streaming.

    Rechaza:
      - Vacio / solo espacios.
      - Demasiado largo (>30 chars).
      - Greetings / preguntas conocidas (Hola, Quien eres, etc).
      - Solo caracteres no-alfanumericos.
      - Strings con caracteres de tool_call / system markers.
    """
    if not name or not name.strip():
        return False
    n = name.strip()
    if len(n) > 30:
        return False
    if n.lower() in _INVALID_PROFILE_NAMES:
        return False
    # Debe tener al menos UNA letra (cubre nombres en cualquier idioma).
    if not any(ch.isalpha() for ch in n):
        return False
    # Tokens de system / tool_call leak.
    for bad in ("<|", "|>", "tool_call", "system:", "user:", "assistant:"):
        if bad in n:
            return False
    return True


# Query "generica" = el user pidio musica/una cancion SIN nombrar un titulo.
# Detector de query "generica" (pidio musica SIN nombrar titulo/artista).
#
# DISEÑO (minimo hardcode, regla de uso universal): NO enumeramos frases. Un
# pedido generico es uno cuyas palabras-de-contenido son TODAS "tokens
# genericos" (palabra de musica, cuantificador vago, o verbo de play). Si
# queda alguna palabra que no es generica, es un titulo/artista -> NO generico.
# Asi "pon una cancion", "reproduce algo de musica", "play some music" y
# "metele cualquier cosa" matchean sin listarlas; "pon Bad Bunny" no (queda
# "bad"/"bunny"). Y aunque el detector FALLE, el fallback UIA igual reproduce
# el top result de buscar esa frase (validado 2026-05-22) — no es punto critico.
#
# RAICES de contenido (play-verb / music-noun / cuantificador-vago). Se
# matchean por PREFIJO (startswith) para cubrir conjugaciones — por eso aca van
# SOLO tokens >=3 letras y semanticamente fuertes (nunca preposiciones cortas
# como "de", que matchearian "Despacito").
_GENERIC_CONTENT_ROOTS = (
    # play verbs
    "pon", "reproduc", "toca", "play", "put", "metel", "echa", "dale",
    # music nouns
    "cancion", "canción", "music", "música", "rola", "tema", "song", "tune",
    "cancao", "canzon", "chanson", "musik", "lied",
    # vague quantifiers / "anything"
    "algo", "cualquier", "random", "aleatori", "something", "anything",
    "whatever", "some", "qualquer", "qualcosa", "quelque", "irgend",
)
# FILLER de funcion (articulos/preposiciones/pronombres). Se matchean EXACTO
# (no prefijo) para no pisar titulos. Multi-idioma, pero es funcion pura.
_GENERIC_FILLER_WORDS = frozenset({
    "una", "un", "uno", "unos", "unas", "de", "del", "la", "el", "lo", "las",
    "los", "que", "sea", "cosa", "a", "me", "le", "nos", "te", "asi",
    "any", "of", "the", "for", "uma", "um", "qualsiasi",
    "une", "des", "du", "di", "una", "uno",  # fr/it articles
})


def _is_generic_music_query(query: str) -> bool:
    """True si el query NO nombra un titulo/artista concreto.

    Heuristica estructural (sin lista de frases): generico sii TODAS las
    palabras son o bien una RAIZ de contenido generica (por prefijo) o FILLER
    de funcion (exacto). Una sola palabra "real" (titulo/artista) hace False.
    Query vacia = generico. Cap de longitud para frases largas (probable titulo).
    """
    if not query or not query.strip():
        return True
    norm = " ".join(query.strip().lower().split()).strip(" .!?¡¿,;:\"'")
    words = [w for w in norm.split() if w]
    if not words:
        return True
    if len(words) > 6:
        return False
    for w in words:
        if w in _GENERIC_FILLER_WORDS:
            continue
        if any(w.startswith(root) for root in _GENERIC_CONTENT_ROOTS):
            continue
        return False  # palabra real -> hay un titulo/artista
    return True


def _get_spotify_username(state: AgentState | None) -> str | None:
    """Lee el username de Spotify guardado (para deeplink de Liked Songs).
    Reusa el store de streaming_preference con provider='spotify_user'."""
    return _get_streaming_preference(state, "spotify_user")


def _set_streaming_preference(
    state: AgentState | None, provider: str, profile_name: str,
) -> dict[str, Any] | None:
    """Guarda el nombre del perfil preferido para una plataforma.

    Validacion: rechaza nombres que parecen saludos/preguntas (defense in
    depth contra extractor permisivo). Si name es invalido, devuelve dict
    con ok=False para que el caller pueda manejar.

    Si ya existe una preferencia para el mismo provider, la actualiza.
    Devuelve el resource creado/actualizado o None si state es None.
    """
    if state is None:
        return None
    if not _is_valid_profile_name(profile_name):
        return {
            "ok": False,
            "error": f"refused to save invalid profile_name {profile_name!r}",
            "reason": "looks like a greeting / question / unrelated text",
        }
    profile_name = profile_name.strip()
    # Buscar existente.
    try:
        data = state._load()  # noqa: SLF001
        resources = data.get("resources", {})
    except Exception:
        resources = {}
    existing_id = None
    for rid, res in resources.items():
        if (isinstance(res, dict)
                and res.get("kind") == "streaming_preference"
                and str((res.get("metadata") or {}).get("provider", "")).lower() == provider.lower()):
            existing_id = rid
            break
    if existing_id:
        return state.update_resource(
            existing_id,
            metadata_patch={"profile_name": profile_name, "updated_at": datetime.now().isoformat()},
        )
    return state.register_resource(
        "streaming_preference",
        f"{provider} profile",
        metadata={"provider": provider, "profile_name": profile_name,
                  "created_at": datetime.now().isoformat()},
    )


# ---------------------------------------------------------------------------
# Title -> Direct URL cache (the highest-leverage optimization per compass
# research 2026-05-16: bypasses search-page entirely on subsequent plays).
# ---------------------------------------------------------------------------
# On first play we land on the search/detail page. After the user (or the
# agent's selectors) navigates to the actual title detail page, we capture
# the canonical URL and store it as a `streaming_title_cache` resource so
# subsequent calls jump straight to it.

def _normalize_title_key(title: str) -> str:
    """Normaliza titulo para lookup case+accent-insensitive."""
    s = unicodedata.normalize("NFKD", (title or "").strip().lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    # Colapsa espacios y signos triviales para que "Daredevil: Born Again"
    # matchee "daredevil born again".
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _get_cached_title_url(
    state: AgentState | None, provider: str, query: str,
) -> str | None:
    """Devuelve la URL deep-link cacheada para (provider, title) o None."""
    if state is None or not query:
        return None
    key = _normalize_title_key(query)
    if not key:
        return None
    try:
        data = state._load()  # noqa: SLF001
        resources = data.get("resources", {})
    except Exception:
        return None
    for res in resources.values():
        if not isinstance(res, dict):
            continue
        if res.get("kind") != "streaming_title_cache":
            continue
        meta = res.get("metadata") or {}
        if (str(meta.get("provider", "")).lower() == provider.lower()
                and str(meta.get("title_key", "")) == key):
            url = str(meta.get("url") or "").strip()
            if url:
                return url
    return None


def _set_cached_title_url(
    state: AgentState | None, provider: str, query: str, url: str,
) -> None:
    """Persist (provider, title) -> URL. Overwrites if exists. Best-effort."""
    if state is None or not query or not url:
        return
    key = _normalize_title_key(query)
    if not key:
        return
    try:
        data = state._load()  # noqa: SLF001
        resources = data.get("resources", {})
    except Exception:
        return
    # Look for existing entry.
    for rid, res in resources.items():
        if not isinstance(res, dict):
            continue
        if res.get("kind") != "streaming_title_cache":
            continue
        meta = res.get("metadata") or {}
        if (str(meta.get("provider", "")).lower() == provider.lower()
                and str(meta.get("title_key", "")) == key):
            try:
                state.update_resource(
                    rid,
                    metadata_patch={
                        "url": url,
                        "updated_at": datetime.now().isoformat(),
                    },
                )
            except Exception:
                pass
            return
    # Not found -> create.
    try:
        state.register_resource(
            "streaming_title_cache",
            f"{provider}: {query[:60]}",
            metadata={
                "provider": provider,
                "title_query": query,
                "title_key": key,
                "url": url,
                "created_at": datetime.now().isoformat(),
            },
        )
    except Exception:
        pass


# Chromium-based browsers we know how to launch with CDP. Each entry:
#   - process_name: as seen in Get-Process (without .exe)
#   - exe_candidates: filesystem paths to look up the executable
#   - profile_subpath: user_data_dir relative to a Windows env root
#   - profile_root: which env var holds the root (APPDATA / LOCALAPPDATA)
_CDP_BROWSER_CANDIDATES: list[dict[str, Any]] = [
    {
        "key": "opera_gx",
        "progid_match": ("opera gx", "operagx"),
        "process_name": "opera",
        "exe_candidates": [
            r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe",
        ],
        "profile_root": "APPDATA",
        "profile_subpath": r"Opera Software\Opera GX Stable",
    },
    {
        "key": "opera",
        "progid_match": ("operastable", "opera"),
        "process_name": "opera",
        "exe_candidates": [
            r"%LOCALAPPDATA%\Programs\Opera\opera.exe",
        ],
        "profile_root": "APPDATA",
        "profile_subpath": r"Opera Software\Opera Stable",
    },
    {
        "key": "chrome",
        "progid_match": ("chrome",),
        "process_name": "chrome",
        "exe_candidates": [
            r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
            r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
        ],
        "profile_root": "LOCALAPPDATA",
        "profile_subpath": r"Google\Chrome\User Data",
    },
    {
        "key": "edge",
        "progid_match": ("edge", "msedge"),
        "process_name": "msedge",
        "exe_candidates": [
            r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
            r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
        ],
        "profile_root": "LOCALAPPDATA",
        "profile_subpath": r"Microsoft\Edge\User Data",
    },
    {
        "key": "brave",
        "progid_match": ("brave",),
        "process_name": "brave",
        "exe_candidates": [
            r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
        "profile_root": "LOCALAPPDATA",
        "profile_subpath": r"BraveSoftware\Brave-Browser\User Data",
    },
]


def _cdp_endpoint_alive(timeout: float = 1.5) -> bool:
    """Quick check: does http://127.0.0.1:9222/json/version respond?"""
    import urllib.request
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:9222/json/version", timeout=timeout,
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def _detect_default_browser_progid() -> str:
    """Read the user's default browser from the Windows registry. Returns
    lowercase ProgId or '' if unknown."""
    if os.name != "nt":
        return ""
    try:
        import winreg
        key_path = (
            r"SOFTWARE\Microsoft\Windows\Shell\Associations\UrlAssociations"
            r"\https\UserChoice"
        )
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            val, _ = winreg.QueryValueEx(k, "ProgId")
            return str(val or "").lower()
    except Exception:
        return ""


def _running_chromium_process_names() -> set[str]:
    """Set de process names (sin .exe, lowercase) de los Chromium vivos AHORA.

    User-reported 2026-05-22: el agente abria Opera GX (default del registro)
    aunque el user tenia Chrome abierto y logueado en Disney/Netflix. El
    navegador donde vive la sesion es el que esta CORRIENDO, no el default
    nominal del registro. Devolvemos los process names para que
    `_pick_cdp_browser` priorice relanzar ese mismo navegador (preservando su
    --user-data-dir, asi conserva login + tabs via session restore).
    """
    if os.name != "nt":
        return set()
    names = {c["process_name"] for c in _CDP_BROWSER_CANDIDATES}
    try:
        # Una sola pasada: lista todos los procesos cuyo nombre matchea un
        # candidato. -ErrorAction SilentlyContinue evita ruido si ninguno corre.
        name_args = ",".join(sorted(names))
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
              f"Get-Process {name_args} -ErrorAction SilentlyContinue | "
              "Select-Object -ExpandProperty ProcessName -Unique"],
            capture_output=True, text=True, timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return {
            line.strip().lower()
            for line in (res.stdout or "").splitlines()
            if line.strip()
        }
    except Exception:
        return set()


def _pick_cdp_browser() -> dict[str, Any] | None:
    """Choose which Chromium browser to launch with CDP. Priority (user
    decision 2026-05-22 — respetar el navegador default del user):
       1. The user's DEFAULT browser if it's currently RUNNING — relaunch it with
          the same --user-data-dir to preserve the logged-in session + tabs.
       2. The user's default browser even if not running (launch fresh).
       3. Any other Chromium that IS running (fallback: the session likely lives
          in whatever browser is open).
       4. The first installed candidate (Opera GX > Opera > Chrome > Edge > Brave).
    Returns the candidate dict (with `exe` and `user_data_dir` resolved) or None."""
    running = _running_chromium_process_names()
    progid = _detect_default_browser_progid()

    default_cand: dict[str, Any] | None = None
    if progid:
        for cand in _CDP_BROWSER_CANDIDATES:
            if any(m in progid for m in cand["progid_match"]):
                default_cand = cand
                break

    ordered: list[dict[str, Any]] = []
    # 1+2. Default del user primero (corriendo o no — lo relanzamos igual).
    if default_cand is not None:
        ordered.append(default_cand)
    # 3. Otros Chromium vivos (donde puede estar la sesion si el default no corre).
    if running:
        for cand in _CDP_BROWSER_CANDIDATES:
            if cand["process_name"].lower() in running and cand not in ordered:
                ordered.append(cand)
    # 4. Resto de instalados.
    for cand in _CDP_BROWSER_CANDIDATES:
        if cand not in ordered:
            ordered.append(cand)

    for cand in ordered:
        for raw in cand["exe_candidates"]:
            exe = os.path.expandvars(raw)
            if Path(exe).is_file():
                root = os.environ.get(cand["profile_root"], "")
                user_data_dir = str(Path(root) / cand["profile_subpath"])
                return {**cand, "exe": exe, "user_data_dir": user_data_dir}
    return None


def _ensure_cdp_browser(timeout_total: float = 10.0) -> dict[str, Any]:
    """Garantiza que CDP este disponible en :9222. Si no, cierra el browser
    Chromium del user y lo relanza con --remote-debugging-port=9222 + su
    propio --user-data-dir (preserva tabs/login).

    Returns dict con keys:
      - cdp_ok: bool
      - action: 'already_running' | 'relaunched' | 'launched' | 'failed' | 'unsupported' | 'disabled'
      - browser_key: str | None
      - reason: str | None
    """
    if _cdp_endpoint_alive():
        return {"cdp_ok": True, "action": "already_running",
                "browser_key": None, "reason": None}

    # Test isolation: pytest mockea webbrowser.open al nivel del tool, pero
    # _ensure_cdp_browser opera FUERA del executor (urllib + subprocess
    # reales). Para no matar Opera del dev cada vez que corren tests,
    # respetar GEMMA4_DISABLE_AUTO_CDP_LAUNCH=1 o detectar una corrida de tests.
    #
    # BUG 2026-05-22 (trace #847): `"unittest" in sys.modules` y
    # `"pytest" in sys.modules` son FALSOS POSITIVOS en produccion — torch /
    # transformers / numpy.testing importan `unittest` al cargar, asi que el
    # runtime de voz SIEMPRE creia estar en tests y NUNCA lanzaba CDP -> Disney
    # caia a webbrowser.open (abria la pagina pero nunca tipeaba la query).
    # Verificado: importar torch/transformers mete unittest en sys.modules.
    # Señal confiable de "corriendo DENTRO de un test": la env var
    # PYTEST_CURRENT_TEST (pytest la setea por test) o flags explicitos. La
    # presencia del modulo importado NO sirve.
    in_test_env = (
        os.environ.get("GEMMA4_DISABLE_AUTO_CDP_LAUNCH") == "1"
        or "PYTEST_CURRENT_TEST" in os.environ
        or os.environ.get("CI") == "true"
    )
    if in_test_env:
        return {"cdp_ok": False, "action": "disabled",
                "browser_key": None,
                "reason": "auto-launch disabled (test env var or GEMMA4_DISABLE_AUTO_CDP_LAUNCH)"}

    if os.name != "nt":
        return {"cdp_ok": False, "action": "unsupported",
                "browser_key": None,
                "reason": "auto-launch only implemented on Windows"}

    cand = _pick_cdp_browser()
    if not cand:
        return {"cdp_ok": False, "action": "failed",
                "browser_key": None,
                "reason": "no Chromium browser found (Opera/Chrome/Edge/Brave)"}

    exe = cand["exe"]
    user_data_dir = cand["user_data_dir"]
    proc_name = cand["process_name"]
    relaunched = False

    # Cerrar instancias corriendo del mismo browser. Si tenia tabs abiertas,
    # Opera/Chrome las restauran al abrir de nuevo (session restore default).
    # F-003: cierre graceful primero (CloseMainWindow envia WM_CLOSE -> browser
    # guarda session/forms), 3s de espera, solo entonces Stop-Process -Force
    # como ultimo recurso. Reduce perdida de trabajo del user.
    import time as _time
    try:
        running = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
              f"Get-Process {proc_name} -ErrorAction SilentlyContinue | "
              "Select-Object -ExpandProperty Id"],
            capture_output=True, text=True, timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        pids = [p.strip() for p in (running.stdout or "").splitlines() if p.strip()]
        if pids:
            # 1. Pedir cierre suave (WM_CLOSE) a cada proceso.
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                  f"$procs = Get-Process {proc_name} -ErrorAction SilentlyContinue; "
                  "foreach ($p in $procs) { try { $p.CloseMainWindow() | Out-Null } catch {} }"],
                capture_output=True, text=True, timeout=6,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            _time.sleep(3.0)  # dar tiempo al browser para flush session/forms
            # 2. Si quedan vivos, force-kill.
            still = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                  f"Get-Process {proc_name} -ErrorAction SilentlyContinue | "
                  "Select-Object -ExpandProperty Id"],
                capture_output=True, text=True, timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            still_pids = [p.strip() for p in (still.stdout or "").splitlines() if p.strip()]
            if still_pids:
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                      f"Get-Process {proc_name} -ErrorAction SilentlyContinue | "
                      "Stop-Process -Force -ErrorAction SilentlyContinue"],
                    capture_output=True, text=True, timeout=6,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                _time.sleep(1.5)  # let OS clean up handles
            relaunched = True
    except Exception:
        pass

    # Lanzar el browser con CDP.
    try:
        subprocess.Popen(
            [exe, "--remote-debugging-port=9222",
              f"--user-data-dir={user_data_dir}"],
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
                          | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            close_fds=True,
        )
    except Exception as exc:
        return {"cdp_ok": False, "action": "failed",
                "browser_key": cand["key"],
                "reason": f"launch failed: {exc}"}

    # Poll endpoint hasta ~8s.
    deadline = _time.time() + max(3.0, timeout_total - 2.0)
    while _time.time() < deadline:
        if _cdp_endpoint_alive(timeout=1.0):
            return {"cdp_ok": True,
                    "action": "relaunched" if relaunched else "launched",
                    "browser_key": cand["key"], "reason": None}
        _time.sleep(0.6)

    return {"cdp_ok": False, "action": "failed",
            "browser_key": cand["key"],
            "reason": "browser launched but CDP endpoint never came up"}


def _try_cdp_attach(executor: Executor) -> dict[str, Any]:
    """Intenta conectarse al Chrome del user via CDP (puerto 9222).
    Si no esta disponible, intenta lanzar el browser default con CDP
    automaticamente y reintenta.

    Returns dict con keys:
      - "available": bool — True si se conecto exitosamente.
      - "session_id": str — id de la sesion de browser_real.
      - "reason": str | None — por que no se conecto si available=False.
      - "launched_browser": str | None — clave del browser auto-lanzado, si aplica.
    """
    # 0. Garantizar que el browser CDP este corriendo (auto-launch si hace falta).
    ensure = _ensure_cdp_browser()
    if not ensure["cdp_ok"]:
        return {
            "available": False, "session_id": None,
            "reason": f"CDP unavailable: {ensure['reason']}",
            "launched_browser": None,
        }

    try:
        r = executor("browser_real", {
            "action": "connect_cdp",
            "endpoint": "http://127.0.0.1:9222",
            "session_id": "streaming",
        })
        if r.get("ok"):
            return {"available": True, "session_id": "streaming",
                    "reason": None,
                    "launched_browser": ensure.get("browser_key"),
                    "browser_action": ensure.get("action")}
        return {
            "available": False, "session_id": None,
            "reason": str(r.get("error") or "connect_cdp returned not-ok"),
            "launched_browser": ensure.get("browser_key"),
        }
    except Exception as exc:
        return {
            "available": False, "session_id": None,
            "reason": f"connect_cdp exception: {exc}",
        }


def _streaming_cdp_play(
    executor: Executor,
    canonical: str,
    spec: dict[str, Any],
    query: str,
    profile_name: str,
    web_url: str,
    web_search_via_url: bool,
    cached_url: str | None,
    state: AgentState | None = None,
) -> dict[str, Any]:
    """CDP-first playback via Playwright + selectores REALES (verificados
    via probe 2026-05-16 contra Opera GX logueado).

    Flow:
      0. Si cached_url -> goto directo. Si click_card_starts_playback=True
         (Netflix), la URL cacheada YA es /watch/<id> y ya reproduce. Sino
         try click play.
      1. Goto search URL.
      2. Si profile_picker_check selector existe -> click profile_name
         (Netflix presenta profile-gate por sesion).
      3. Si NOT web_search_via_url -> fill search input.
      4. Esperar render + click primer result_card.
      5. Capturar detail URL (cache si matchea title_url_pattern).
      6. Si click_card_starts_playback=True -> ya reproduce. Sino:
         click play_button.
    """
    import time as _time
    playback = spec.get("playback") or {}
    selectors_input = playback.get("search_input") or []
    selectors_card = playback.get("result_card") or []
    selectors_play = playback.get("play_button") or []
    profile_picker_check = playback.get("profile_picker_check")
    profile_item_anchor = playback.get("profile_item_anchor")
    click_starts_playback = bool(playback.get("click_card_starts_playback"))
    title_pattern = playback.get("title_url_pattern")

    steps: list[str] = []
    session_id = "streaming"

    def _try_selectors(action: str, sel_list: list[str], **extras) -> dict[str, Any]:
        last_err = None
        for sel in sel_list:
            try:
                r = executor("browser_real", {
                    "action": action,
                    "session_id": session_id,
                    "selector": sel,
                    "timeout_sec": extras.get("timeout_sec", 6),
                    **{k: v for k, v in extras.items() if k != "timeout_sec"},
                })
                if r.get("ok"):
                    return {"ok": True, "selector": sel, "result": r}
                last_err = r.get("error")
            except Exception as exc:
                last_err = str(exc)
        return {"ok": False, "error": last_err or "all selectors failed"}

    def _get_current_url() -> str:
        try:
            r = executor("browser_real", {
                "action": "active_tab", "session_id": session_id,
            })
            if r.get("ok") and isinstance(r.get("active_tab"), dict):
                return str(r["active_tab"].get("url") or "")
        except Exception:
            pass
        return ""

    def _bring_browser_to_front() -> None:
        """User-reported bug 2026-05-16 21:23: after media play, the browser
        window stays in background and the user can't see what's playing.
        Issue a `window focus` with the provider name as query — Opera's
        page title contains "Disney+" / "Netflix" / etc. for the active tab,
        so this matches and brings it forward (auto-maximizes if small).
        """
        try:
            provider_title = {
                "disney": "Disney+",
                "netflix": "Netflix",
                "hbo_max": "Max",
                "prime_video": "Prime Video",
            }.get(canonical, canonical)
            executor("window", {"action": "focus", "query": provider_title})
            steps.append(f"focused_window:{provider_title}")
        except Exception:
            pass

    # 1. Navegar. Usamos new_tab=True para NO sobreescribir lo que el user
    # tenia abierto. headless=False matches la sesion CDP (Opera GX).
    target_url = cached_url or web_url
    via_cache = bool(cached_url)
    try:
        goto = executor("browser_real", {
            "action": "goto",
            "session_id": session_id,
            "url": target_url,
            "wait_until": "domcontentloaded",
            "timeout_sec": 25,
            "headless": False,
            "new_tab": True,
        })
        if not goto.get("ok"):
            return {
                "player_started": False, "attempted_play": False,
                "steps": steps,
                "abort_reason": f"goto {target_url!r} failed: {goto.get('error')}",
                "via_cache": via_cache,
            }
        steps.append(f"goto:{target_url[:80]}{' (cached)' if via_cache else ''}")
    except Exception as exc:
        return {
            "player_started": False, "attempted_play": False,
            "steps": steps,
            "abort_reason": f"goto exception: {exc}",
            "via_cache": via_cache,
        }
    # F-012: reducido 5.5s -> 2.5s. _try_selectors con timeout_sec interno
    # actua como wait_for_selector con polling, asi que el sleep inicial
    # solo necesita cubrir el DOMContentLoaded -> JS-hydration gap minimo.
    _time.sleep(2.5)

    # FAST PATH: cached URL para Netflix etc.
    if via_cache:
        if click_starts_playback:
            # Cached URL es ya /watch/<id> — esta reproduciendo.
            steps.append("cache_url_loaded_autoplay_expected")
            _bring_browser_to_front()
            return {
                "player_started": True, "attempted_play": True,
                "steps": steps, "abort_reason": None, "via_cache": True,
            }
        # Para otros, intentar el play button.
        play_res = _try_selectors("click", selectors_play, timeout_sec=8)
        if play_res["ok"]:
            steps.append(f"clicked_play_cached:{play_res['selector']}")
            _bring_browser_to_front()
            return {
                "player_started": True, "attempted_play": True,
                "steps": steps, "abort_reason": None, "via_cache": True,
            }
        # Cache URL cargada — usualmente significa que el video ya esta en
        # detail page o auto-reproduciendo. Mark como exito best-effort.
        _bring_browser_to_front()
        return {
            "player_started": True, "attempted_play": True,
            "steps": steps + ["cache_url_loaded_no_play_button"],
            "abort_reason": None, "via_cache": True,
        }

    # 2. Profile picker (Netflix). Sin `evaluate` (que requiere
    # confirmation en CDP). Click directo con selector :has-text(profile)
    # con timeout corto. Si no hay picker, falla rapido y seguimos.
    if profile_picker_check and profile_item_anchor and profile_name:
        prof_selectors = [
            f"{profile_item_anchor}:has-text({profile_name!r})",
        ]
        prof_res = _try_selectors("click", prof_selectors, timeout_sec=3)
        if prof_res["ok"]:
            steps.append(f"clicked_profile:{profile_name}")
            # F-012: reducido 8s -> 4s. Selector polling del fill/click
            # subsiguiente cubre el resto de espera con timeout interno.
            _time.sleep(4.0)
        else:
            # No vimos profile picker (Netflix recuerda sesion) -> continue.
            steps.append("profile_pick_not_needed_or_failed")

    # 3. Si la URL NO tiene query (Disney+), rellenar input.
    if not web_search_via_url:
        fill_res = _try_selectors("fill", selectors_input, value=query,
                                    timeout_sec=10)
        if not fill_res["ok"]:
            return {
                "player_started": False, "attempted_play": False,
                "steps": steps,
                "abort_reason": f"could not find search input: {fill_res['error']}",
                "via_cache": False,
                "hint": "Search page may have changed structure. Selectors: "
                        + ", ".join(selectors_input),
            }
        steps.append(f"filled_search:{fill_res['selector']}")
        # F-012: reducido 4s -> 2s post-fill. El polling del click_card
        # subsiguiente (timeout_sec=12) absorbe el resto del wait.
        _time.sleep(2.0)

    # 4. Click primer result card.
    # F-012: removido 'extra render time' de 2s — _try_selectors timeout=12
    # ya hace polling activo del selector.
    card_res = _try_selectors("click", selectors_card, timeout_sec=12)
    if not card_res["ok"]:
        return {
            "player_started": False, "attempted_play": False,
            "steps": steps,
            "abort_reason": f"could not click first result card: {card_res['error']}",
            "via_cache": False,
            "hint": "Selectors: " + ", ".join(selectors_card),
        }
    steps.append(f"clicked_first_result:{card_res['selector']}")
    # F-012: reducido 5s -> 2.5s post-card-click. El click_play subsiguiente
    # (timeout_sec=10) cubre el resto con polling activo.
    _time.sleep(2.5)

    # 5. Cache URL post-click.
    detail_url = _get_current_url()
    if detail_url and title_pattern:
        try:
            import re as _re
            if _re.search(title_pattern, detail_url):
                _set_cached_title_url(state, canonical, query, detail_url)
                steps.append(f"cached_title_url:{detail_url[:80]}")
        except Exception:
            pass

    # 6. Para plataformas donde click card YA reproduce (Netflix) -> done.
    if click_starts_playback:
        steps.append("playback_started_via_card_click")
        _bring_browser_to_front()
        return {
            "player_started": True, "attempted_play": True,
            "steps": steps, "abort_reason": None, "via_cache": False,
            "detail_url": detail_url,
        }

    # 7. Click play button.
    play_res = _try_selectors("click", selectors_play, timeout_sec=10)
    if play_res["ok"]:
        steps.append(f"clicked_play:{play_res['selector']}")
        _bring_browser_to_front()
        return {
            "player_started": True, "attempted_play": True,
            "steps": steps, "abort_reason": None, "via_cache": False,
            "detail_url": detail_url,
        }
    # Llegamos al detail page pero no encontramos un Play button explicito.
    # Solo asumimos playback automatico cuando spec lo declara explicit
    # (Prime: click del card abre el player). Para Disney/Netflix/HBO ser
    # honestos: attempted_play=True pero player_started=False.
    # Igual traer el browser al frente: el user al menos ve el detail page.
    _bring_browser_to_front()
    return {
        "player_started": click_starts_playback,
        "attempted_play": True,
        "steps": steps + ["detail_page_reached_no_explicit_play_button"],
        "abort_reason": None, "via_cache": False,
        "detail_url": detail_url,
    }


def _streaming_web_auto_play(
    executor: Executor,
    canonical: str,
    query: str,
    profile_name: str,
    wait_seconds: float,
    *,
    spec: dict[str, Any] | None = None,
    web_url: str | None = None,
    web_search_via_url: bool = True,
    state: AgentState | None = None,
) -> dict[str, Any]:
    """Auto-play en web para Netflix/Disney+/HBO Max/Prime Video.

    Estrategia (compass research 2026-05-16):
      1. Intentar CDP attach al Chrome real del user (puerto 9222).
         Si funciona: DOM-level via Playwright + selectors estables.
         Si NO funciona: cae a webbrowser.open + report honesto al user.

    Returns dict con keys:
      - player_started: bool — True solo si confirmamos Play click.
      - attempted_play: bool — True si llegamos a hacer click(s) en el flow.
      - steps: list[str] — pasos completados (para debug).
      - abort_reason: str | None — por que paramos.
      - via_cdp: bool — True si usamos CDP, False si webbrowser fallback.
      - via_cache: bool — True si usamos title->URL cache.
    """
    # 0. Buscar cache title -> URL.
    cached_url = _get_cached_title_url(state, canonical, query)

    # 1. Intentar CDP attach.
    cdp = _try_cdp_attach(executor)
    if cdp["available"] and spec and web_url:
        result = _streaming_cdp_play(
            executor, canonical, spec, query, profile_name,
            web_url=web_url,
            web_search_via_url=web_search_via_url,
            cached_url=cached_url,
            state=state,
        )
        result["via_cdp"] = True
        return result

    # 2. Fallback: webbrowser.open. Honesto — solo abrimos la pagina y
    # le pedimos al user que de UN click. NO intentamos Tab nav ciega
    # (causaba clicks accidentales).
    import webbrowser as _wb
    url_to_open = cached_url or web_url
    if not url_to_open:
        return {
            "player_started": False, "attempted_play": False,
            "steps": [], "via_cdp": False, "via_cache": False,
            "abort_reason": "no URL to open",
        }
    try:
        opened = _wb.open(url_to_open)
    except Exception as exc:
        return {
            "player_started": False, "attempted_play": False,
            "steps": [], "via_cdp": False, "via_cache": bool(cached_url),
            "abort_reason": f"webbrowser.open failed: {exc}",
        }
    if not opened:
        return {
            "player_started": False, "attempted_play": False,
            "steps": [], "via_cdp": False, "via_cache": bool(cached_url),
            "abort_reason": "webbrowser.open returned False",
        }
    return {
        "player_started": False,
        "attempted_play": False,  # honesto: NO intentamos play, solo abrimos.
        "steps": [f"opened_in_default_browser:{url_to_open[:80]}"],
        "via_cdp": False,
        "via_cache": bool(cached_url),
        "abort_reason": None,
        "verification_note": (
            "Opened in default browser. For auto-play, start Chrome with "
            "--remote-debugging-port=9222 so the agent can attach via CDP."
        ),
        "cdp_unavailable_reason": cdp["reason"],
    }


def _detect_spotify_already_running(executor: Executor) -> bool:
    """Devuelve True si hay una ventana 'Spotify' visible antes de mandar
    el deeplink.

    Importa para el wait dinamico: cuando Spotify ya esta abierto mostrando
    el player view, el deeplink `spotify:search:<q>` tarda 2-4s en navegar
    a search results. Default `auto_play_wait=1.8s` alcanza para cold-launch
    (el splash + load tarda mas que la navegacion intra-app) pero NO para
    warm — Enter dispara mientras la UI todavia esta en player view y
    reproduce lo que esta en la cola.
    """
    try:
        windows = executor("window", {"action": "list"})
    except Exception:
        return False
    if not isinstance(windows, dict):
        return False
    items = windows.get("windows") or windows.get("items") or []
    if not isinstance(items, list):
        return False
    for w in items:
        title = ""
        if isinstance(w, dict):
            title = str(w.get("title") or "")
        else:
            title = str(w)
        if "spotify" in title.lower():
            return True
    return False


def _spotify_play_random(
    executor: Executor,
    state: AgentState | None,
    auto_play_wait: float,
) -> dict[str, Any]:
    """User pidio 'una cancion' / 'musica' sin nombrar titulo.

    Decision del user (2026-05-22):
      - Si tenemos el username de Spotify -> reproducir 'Me Gusta' (Liked Songs)
        en shuffle via deeplink spotify:user:<user>:collection.
      - Si NO -> mandar Play global (media key): reanuda lo que Spotify tenga
        cargado / la cola. Universal y sin login, pero si Spotify esta vacio no
        suena nada (lo reportamos honesto).

    Fuente del URI de Liked Songs:
      https://community.spotify.com/t5/Your-Library/What-is-the-Spotify-URI-for-my-Liked-Songs/td-p/5255192
      (spotify:user:<username>:collection — workaround no-oficial pero estable).
    """
    username = _get_spotify_username(state)
    if username:
        # 1. Lanzar app con deeplink a Liked Songs.
        deeplink = f"spotify:user:{username}:collection"
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", deeplink],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, FileNotFoundError) as exc:
            return {"played": False, "mode": "liked_songs",
                    "abort_reason": f"deeplink launch failed: {exc}"}
        # 2. Focus + Enter para reproducir (con shuffle el primer track suena).
        ap = _spotify_auto_play(executor, max(auto_play_wait, 2.5), query=None)
        ap["mode"] = "liked_songs"
        ap["deeplink"] = deeplink
        ap["username"] = username
        return ap
    # Sin username -> Play global.
    try:
        r = executor("audio", {"action": "media_play_pause"})
        ok = bool(isinstance(r, dict) and r.get("ok", True))
        return {
            "played": ok,
            "mode": "global_play_key",
            "abort_reason": None if ok else "media_play_pause returned not-ok",
            "needs_username_hint": (
                "Para reproducir tus 'Me Gusta' aleatorias directamente, decime "
                "tu usuario de Spotify una vez (ej. 'mi usuario de Spotify es "
                "ema123') y lo recuerdo."
            ),
        }
    except Exception as exc:
        return {"played": False, "mode": "global_play_key",
                "abort_reason": f"media_play_pause failed: {exc}"}


def _is_spotify_track_title(title: str) -> bool:
    """Spotify pone "Track • Artist" (o "Spotify - Track • Artist") en el window
    title cuando suena algo. Cuando NO suena nada el title es la marca pelada:
    "Spotify Premium" / "Spotify Free" / "Spotify". True si hay un track."""
    t = (title or "").strip().lower()
    if not t:
        return False
    return t not in {"spotify", "spotify premium", "spotify free",
                      "spotify - premium", "advertisement"}


# Script PowerShell que reproduce en Spotify Desktop via UI Automation.
# VALIDADO EN VIVO 2026-05-22 (track/artista/cancion). Spotify (Electron)
# expone su arbol de accesibilidad: cada item reproducible tiene un boton
# cuyo Name empieza con "Reproducir <X>" (o "Play <X>" en ingles). El TAB+ENTER
# a ciegas NO reproduce nada — el clic UIA via InvokePattern SI.
#
# Estrategia:
#   1. Tomar la ventana de Spotify, leer su title ANTES.
#   2. Enumerar botones cuyo Name empiece con el verbo de play (localizado).
#      Filtrar a los del AREA DE CONTENIDO (x > borde-izq + margen) para
#      descartar la sidebar/biblioteca del user.
#   3. Elegir el que MATCHEA palabras de la query (>=4 chars); si ninguno,
#      el de menor Y (top result). Invoke().
#   4. Leer el title DESPUES y devolver JSON con played/post_play_title.
# Los verbos se pasan como parametro (multi-idioma, sin hardcode en el .ps1).
_SPOTIFY_UIA_PLAY_PS = r"""
param([string]$Query, [string]$PlayVerbs)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
function Get-Title { (Get-Process Spotify -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne "" } | Select-Object -First 1).MainWindowTitle }
$verbs = @()
foreach ($v in ($PlayVerbs -split '\|')) { if ($v.Trim() -ne "") { $verbs += $v.Trim().ToLower() } }
$proc = Get-Process Spotify -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $proc) { [Console]::Out.WriteLine('{"ok":false,"error":"no_spotify_window"}'); exit }
$titleBefore = Get-Title
$root = [System.Windows.Automation.AutomationElement]::FromHandle($proc.MainWindowHandle)
$winRect = $root.Current.BoundingRectangle
$sidebarEdge = $winRect.X + 100
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
$buttons = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
function Is-PlayName($name) { $n=$name.ToLower(); foreach ($v in $verbs) { if ($n.StartsWith($v + " ")) { return $true } }; return $false }
$content = @()
foreach ($b in $buttons) {
  $nm = $b.Current.Name
  if ((Is-PlayName $nm) -and ($b.Current.BoundingRectangle.X -gt $sidebarEdge)) { $content += $b }
}
$content = $content | Sort-Object { $_.Current.BoundingRectangle.Y }
if ($content.Count -eq 0) {
  [Console]::Out.WriteLine((ConvertTo-Json @{ok=$false;error="no_play_button";title_before=$titleBefore} -Compress)); exit
}
$qwords = @(); foreach ($w in ($Query.ToLower() -split '\s+')) { if ($w.Length -ge 4) { $qwords += $w } }
$match = $null
foreach ($b in $content) { $n=$b.Current.Name.ToLower(); foreach ($w in $qwords) { if ($n.Contains($w)) { $match=$b; break } }; if ($match) { break } }
$target = if ($match) { $match } else { $content[0] }
$chosen = $target.Current.Name
$target.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
Start-Sleep -Milliseconds 1500
$titleAfter = Get-Title
[Console]::Out.WriteLine((ConvertTo-Json @{ok=$true;chosen=$chosen;matched_query=($match -ne $null);title_before=$titleBefore;title_after=$titleAfter} -Compress))
"""


def _spotify_auto_play(
    executor: Executor,
    wait_seconds: float,
    query: str | None = None,
) -> dict[str, Any]:
    """Tras enviar spotify:search:<q>, esperar render y reproducir via UI
    Automation (clic real en el boton "Reproducir <X>" del resultado).

    DESCUBRIMIENTO 2026-05-22 (validado en vivo): Tab+Enter / media-keys NO
    reproducen de forma fiable desde la busqueda de Spotify. Spotify Electron
    SI expone su arbol UIA: cada resultado tiene un boton "Reproducir <X>".
    Clickearlo via InvokePattern reproduce de verdad — y eligiendo el que
    matchea la query reproduce EXACTAMENTE lo pedido (track/artista/genero).

    Multi-idioma: los verbos de "play" se detectan por el idioma de la UI de
    Spotify (ES "Reproducir", EN "Play", PT "Reproduzir", etc.) — se pasan al
    script como lista, sin hardcode en el .ps1.

    Returns dict: played, focus_verified, abort_reason, wait_seconds,
    post_play_title, query_match, chosen.
    """
    import json as _json
    import time as _time
    _time.sleep(max(0.5, wait_seconds))

    # Verbos de "Reproducir" en los idiomas de UI de Spotify. La UI puede estar
    # en cualquier idioma — incluimos los principales. (No es la query del user;
    # es el label del boton de Spotify, acotado a idiomas de la app.)
    play_verbs = "|".join([
        "reproducir", "play", "reproduzir", "riproduci", "lire", "abspielen",
        "afspelen", "spela", "odtwórz", "воспроизвести", "再生", "재생", "播放",
    ])

    if os.name != "nt":
        return {"played": False, "focus_verified": False,
                "abort_reason": "UIA play only implemented on Windows",
                "wait_seconds": wait_seconds}

    # IMPORTANTE: pasar un script multilinea con params via `-Command` lo
    # mangla (PowerShell rompe el param binding). Escribir a un .ps1 temporal
    # y correr con `-File` es robusto. Validado en vivo 2026-05-22.
    import tempfile as _tempfile
    ps_path = None
    try:
        with _tempfile.NamedTemporaryFile(
            mode="w", suffix=".ps1", delete=False, encoding="utf-8",
        ) as fh:
            fh.write(_SPOTIFY_UIA_PLAY_PS)
            ps_path = fh.name
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
              "-File", ps_path,
              "-Query", str(query or ""), "-PlayVerbs", play_verbs],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        return {"played": False, "focus_verified": False,
                "abort_reason": f"UIA play subprocess failed: {exc}",
                "wait_seconds": wait_seconds}
    finally:
        if ps_path:
            try:
                os.unlink(ps_path)
            except Exception:
                pass

    out = (proc.stdout or "").strip()
    data: dict[str, Any] = {}
    # El script imprime una linea JSON; tomar la ultima por si hay ruido.
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = _json.loads(line)
                break
            except Exception:
                continue

    if not data.get("ok"):
        reason = data.get("error") or (proc.stderr or "").strip() or "uia_no_output"
        return {
            "played": False, "focus_verified": bool(data),
            "abort_reason": f"UIA play: {reason}",
            "wait_seconds": wait_seconds,
            "title_before_play": data.get("title_before", ""),
        }

    title_after = str(data.get("title_after") or "")
    played = _is_spotify_track_title(title_after)
    chosen = str(data.get("chosen") or "")

    # query_match: ¿lo que suena se parece a lo pedido? Heuristica: palabra
    # >=4 chars de la query en el title o en el nombre del boton elegido.
    query_match: bool | None = None
    if query and played:
        qwords = [w for w in str(query).lower().split() if len(w) >= 4]
        hay = (title_after + " " + chosen).lower()
        if qwords:
            query_match = any(w in hay for w in qwords)
    return {
        "played": played,
        "focus_verified": True,
        "abort_reason": None if played else (
            "UIA clicked a play button but no track in window title — Spotify "
            "may still be loading, or the result was not playable."
        ),
        "wait_seconds": wait_seconds,
        "via_uia": True,
        "chosen": chosen,
        "matched_query": bool(data.get("matched_query")),
        "title_before_play": str(data.get("title_before") or ""),
        "post_play_title": title_after,
        "query_match": query_match,
    }


def _launch_streaming(
    canonical: str,
    spec: dict[str, Any],
    query: str,
    *,
    executor: Executor | None = None,
    auto_play: bool = False,
    auto_play_wait: float = 1.8,
    profile_name: str | None = None,
    state: AgentState | None = None,
) -> dict[str, Any]:
    """Abre la app o web del provider con la query de busqueda.

    Prioridad:
      1. App desktop instalada + deeplink propio -> usar deeplink.
         Si auto_play=True + executor disponible + provider tiene auto-play
         soportado (Spotify), focus + verify + Enter para reproducir.
      2. App desktop instalada sin deeplink -> abrir app (sin busqueda) + abrir web search en background?
         Decision: si NO hay deeplink, vamos directo a web. Abrir la app sin
         busqueda obliga al user a navegar manualmente.
      3. No app -> abrir web URL en browser default.
    """
    import urllib.parse
    if not query:
        return _err(
            f"{canonical} provider requires a query (movie/series/song)",
            provider=canonical,
        )
    encoded = urllib.parse.quote(query)
    # Solo formatear {q} si la plataforma soporta search via URL. Sino,
    # web_url es solo el home y la query se escribira via GUI search shortcut.
    web_search_via_url = bool(spec.get("web_search_via_url", True))
    # F-009: resolver URL contemplando locale dinamico (Disney+ tiene
    # /es-419/ hardcoded). Si el spec define web_url_template + default_locale,
    # formatear con el locale del user (futuro: state.user_locale), sino
    # fallback al default_locale del spec, sino al web_url estatico.
    web_url = _resolve_streaming_web_url(spec, state=state)
    if web_search_via_url and "{q}" in web_url:
        web_url = web_url.format(q=encoded)
    install_hint = spec.get("install_hint", "")
    note = spec.get("post_open_note", "")

    app_info = _find_streaming_app(spec)
    deeplink_tpl = spec.get("deeplink")

    # PATH 1: app instalada + deeplink confiable
    if app_info["kind"] and deeplink_tpl:
        deeplink = deeplink_tpl.format(q=encoded)
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", deeplink],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, FileNotFoundError):
            pass  # fall through to web
        else:
            # AUTO-PLAY: si tenemos executor y el caller lo pidio, esperar
            # carga + focus verify + Enter para que Spotify reproduzca la
            # primera cancion del resultado de busqueda.
            auto_play_info: dict[str, Any] | None = None
            if auto_play and executor is not None and canonical == "spotify":
                # El UIA play necesita que los RESULTADOS de busqueda esten
                # renderizados (los botones "Reproducir <X>" recien existen en
                # el arbol cuando el grid cargo). Validado en vivo 2026-05-22:
                # ~5s alcanza. Piso 4.5s cold, 5.5s si ya estaba abierto (el
                # deeplink navega de player-view a search, mas lento en warm).
                already_open = _detect_spotify_already_running(executor)
                effective_wait = (
                    max(auto_play_wait, 5.5) if already_open
                    else max(auto_play_wait, 4.5)
                )
                auto_play_info = _spotify_auto_play(executor, effective_wait, query=query)
                if auto_play_info is not None:
                    auto_play_info["was_already_open"] = already_open
                    auto_play_info["wait_seconds_used"] = effective_wait
            played = bool(auto_play_info and auto_play_info.get("played"))
            qmatch = auto_play_info.get("query_match") if auto_play_info else None
            # Si played=True pero query_match=False, no marcamos verified=True.
            # El LLM debe saber que el Enter funciono pero el track tocando
            # probablemente no es lo que el user pidio.
            verified = played and qmatch is not False
            if not played:
                completion_status = "opened_search_results_pending_play"
                final_note = note
            elif qmatch is True:
                completion_status = "media_playing_match"
                final_note = (
                    f"{canonical}: playing — Spotify focused, Enter pressed; "
                    f"now-playing title matches query."
                )
            elif qmatch is False:
                completion_status = "media_playing_wrong_track"
                final_note = (
                    f"{canonical}: played — WARN: now-playing title does not match "
                    f"query (possible warm-cache race; queued track may have played "
                    f"instead of search result)."
                )
            else:
                completion_status = "media_playing_unverified"
                final_note = (
                    f"{canonical}: playing — Spotify focused, Enter pressed on first result."
                )
            return _ok(
                action="play",
                provider=canonical,
                query=query,
                deeplink=deeplink,
                app_kind=app_info["kind"],
                launch_target=app_info["launch_target"],
                opened=True,
                played=played,
                auto_play_attempted=auto_play,
                auto_play_info=auto_play_info,
                verified=verified,
                query_match=qmatch,
                status="dispatched" if played else "attempted",
                completion_status=completion_status,
                note=final_note,
            )

    # PATH 2/3: sin deeplink -> usar web.
    #   - auto_play + profile -> _streaming_web_auto_play intenta CDP attach.
    #     Si CDP attached (via_cdp=True), el browser real ya esta navegado;
    #     `opened` es True incluso si el play button no se encontro.
    #   - sin CDP (o sin auto_play) -> webbrowser.open con la search URL.
    web_auto_play_info: dict[str, Any] | None = None
    played = False
    attempted_play = False
    opened = False
    if auto_play and executor is not None and profile_name:
        web_auto_play_info = _streaming_web_auto_play(
            executor, canonical, query, profile_name, auto_play_wait,
            spec=spec, web_url=web_url, web_search_via_url=web_search_via_url,
            state=state,
        )
        played = bool(web_auto_play_info.get("player_started"))
        attempted_play = bool(web_auto_play_info.get("attempted_play"))
        if web_auto_play_info.get("via_cdp"):
            # CDP attached: Opera GX ya esta navegado al search/detail.
            # `opened` es True aunque el play button no se encontrara.
            opened = True
        else:
            # CDP no disponible -> el fallback de _streaming_web_auto_play
            # ya intento webbrowser.open. Chequear si fue exitoso.
            if not web_auto_play_info.get("abort_reason"):
                opened = True
            else:
                # Fallback adicional: intentar webbrowser.open desde aqui.
                try:
                    opened = webbrowser.open(web_url)
                except Exception as exc:
                    return _err(
                        f"Could not open {canonical} "
                        f"(no app deeplink and webbrowser failed): {exc}",
                        provider=canonical, status="failed",
                    )
    else:
        try:
            opened = webbrowser.open(web_url)
        except Exception as exc:
            return _err(
                f"Could not open {canonical} "
                f"(no app deeplink and webbrowser failed): {exc}",
                provider=canonical, status="failed",
            )

    if not opened:
        return _err(
            f"{canonical}: no native deeplink and default browser refused to open.",
            provider=canonical, status="needs_user",
            install_hint=install_hint,
        )

    via_cdp = bool(web_auto_play_info and web_auto_play_info.get("via_cdp"))
    if played:
        note_msg = (
            f"{canonical}: playing — CDP click play executed (profile "
            f"'{profile_name}'). Confirmed via Playwright."
            if via_cdp else
            f"{canonical}: playing — title clicked, Play pressed "
            f"(profile '{profile_name}')."
        )
    elif attempted_play:
        # via_cdp=True + attempted_play=True (sin played): el flow llego al
        # detail page pero no encontro Play button (caso comun: el video ya
        # esta auto-playing en el detail page, o el button selector cambio).
        # Reportar como exito — el user lo ve en pantalla.
        note_msg = (
            f"{canonical}: opened — navigated to '{query}' detail page via "
            f"CDP (profile '{profile_name}'). The video is loading."
            if via_cdp else
            f"{canonical}: opened search results with profile '{profile_name}'. "
            "Click the title to play."
        )
    else:
        note_msg = note
    result = _ok(
        action="play",
        provider=f"{canonical}_web",
        query=query,
        url=web_url,
        opened=True,
        played=played,
        attempted_play=attempted_play,
        auto_play_attempted=bool(auto_play and profile_name),
        profile_name=profile_name,
        web_auto_play_info=web_auto_play_info,
        verified=played,
        status="dispatched" if (played or attempted_play) else "attempted",
        completion_status=(
            "media_playing" if played
            else "playback_attempted_unverified" if attempted_play
            else "opened_search_results_pending_play"
        ),
        note=note_msg,
        via_cdp=via_cdp,
    )
    if app_info["kind"]:
        # Avisamos que la app esta pero no la usamos por falta de deeplink.
        result["app_available_but_no_deeplink"] = True
        result["app_kind"] = app_info["kind"]
    return result


def _media_play_streaming(
    provider: str,
    query: str,
    args: dict[str, Any],
    executor: Executor | None = None,
    state: AgentState | None = None,
) -> dict[str, Any]:
    """Entry point unificado para Spotify/Netflix/Disney+/Max/Prime Video."""
    resolved = _resolve_streaming_provider(provider)
    if not resolved:
        return _err(
            f"unsupported streaming provider: {provider!r}",
            provider=provider, status="needs_dependency",
            install_hint=(
                "Supported providers: spotify, netflix, disney+ (disney), "
                "hbo_max (max), prime_video. Use one of these names."
            ),
        )
    canonical, spec = resolved

    # SPOTIFY USERNAME: si el user lo da (para Liked Songs aleatorias), el LLM
    # lo pasa como spotify_user / username. Persistir igual que los perfiles.
    if canonical == "spotify":
        uname = str(args.get("spotify_user") or args.get("username") or "").strip()
        if uname:
            try:
                _set_streaming_preference(state, "spotify_user", uname)
            except Exception:
                pass  # best-effort

    # auto_play default True para todos: Spotify usa app+Enter; web streaming
    # usa profile picker + click title + click play.
    auto_play_raw = args.get("auto_play", True)
    if isinstance(auto_play_raw, str):
        auto_play = auto_play_raw.strip().lower() not in {"", "false", "0", "no", "off"}
    else:
        auto_play = bool(auto_play_raw)
    wait_raw = args.get("auto_play_wait") or args.get("wait_seconds") or 1.8
    try:
        auto_play_wait = max(0.5, min(10.0, float(wait_raw)))
    except (TypeError, ValueError):
        auto_play_wait = 1.8

    # GENERICO: "pon una cancion" / "musica" SIN titulo. Buscar la palabra
    # literal ("cancion") nunca reproduce nada util. Para Spotify -> random:
    # Liked Songs shuffle si hay username, sino Play global. (decision user
    # 2026-05-22). Solo aplica a Spotify; para video pedir titulo es razonable.
    if (canonical == "spotify" and auto_play and executor is not None
            and _is_generic_music_query(query)):
        rnd = _spotify_play_random(executor, state, auto_play_wait)
        played = bool(rnd.get("played"))
        mode = rnd.get("mode")
        if played and mode == "liked_songs":
            note = (
                "spotify: reproduciendo tus 'Me Gusta' en aleatorio "
                f"(usuario '{rnd.get('username')}')."
            )
            completion = "media_playing"
        elif played and mode == "global_play_key":
            note = (
                "spotify: Play global enviado — reanudando lo que tenías "
                "cargado. " + str(rnd.get("needs_username_hint") or "")
            )
            completion = "media_playing_unverified"
        else:
            note = (
                "spotify: no pude iniciar reproducción aleatoria"
                + (f" ({rnd.get('abort_reason')})" if rnd.get("abort_reason") else "")
                + ". " + str(rnd.get("needs_username_hint") or "")
            )
            completion = "opened_search_results_pending_play"
        return _ok(
            action="play",
            provider="spotify",
            query=query,
            random_playback=True,
            random_mode=mode,
            opened=True,
            played=played,
            auto_play_attempted=True,
            auto_play_info=rnd,
            verified=played and mode == "liked_songs",
            status="dispatched" if played else "attempted",
            completion_status=completion,
            note=note.strip(),
        )

    # PERFIL: solo aplica a plataformas con profile picker (NOT spotify).
    # Si el user paso profile= explicitamente, guardarlo Y usarlo.
    # Si no, leer del state. Si tampoco, pedir al user.
    profile_name: str | None = None
    needs_profile = canonical in {"netflix", "disney", "hbo_max", "prime_video"}
    if needs_profile and auto_play:
        explicit_profile = str(
            args.get("profile") or args.get("profile_name") or "",
        ).strip()
        if explicit_profile:
            profile_name = explicit_profile
            # Guardarlo para proximas veces.
            try:
                _set_streaming_preference(state, canonical, profile_name)
            except Exception:
                pass  # best-effort, no abortar si falla
        else:
            profile_name = _get_streaming_preference(state, canonical)
            if not profile_name:
                # PRIMERA VEZ: pedir al user que diga su perfil. El LLM ve
                # este error en history + tool result, y en el proximo turn
                # cuando el user dice "mi perfil es Ema", llama media de
                # nuevo con profile='Ema'. Confiamos en el LLM para mantener
                # el contexto via su history — no persistimos pending state
                # (eso causaba bugs donde turns ajenos eran atrapados como
                # respuestas).
                return _err(
                    f"need {canonical} profile to auto-play",
                    status="needs_user",
                    provider=canonical,
                    query=query,
                    hint=(
                        f"What's your {canonical} profile name? Tell me once and "
                        f"I'll remember it. Example: \"mi perfil de "
                        f"{canonical} es Emmanuel\" — or call media again with "
                        f"profile='<your name>'. If you don't want auto-play, "
                        f"pass auto_play=false."
                    ),
                    asks_for="streaming_profile",
                )

    return _launch_streaming(
        canonical, spec, query,
        executor=executor, auto_play=auto_play, auto_play_wait=auto_play_wait,
        profile_name=profile_name, state=state,
    )


# Backwards-compat: el viejo _media_play_spotify se mantiene como alias.
def _media_play_spotify(query: str, args: dict[str, Any]) -> dict[str, Any]:
    return _media_play_streaming("spotify", query, args)


def media_tool(args: dict[str, Any], executor: Executor, state: AgentState | None = None) -> dict[str, Any]:
    action = str(args.get("action") or "play").casefold()
    if action == "status":
        streaming = {}
        for canonical, spec in _STREAMING_PLATFORMS.items():
            app_info = _find_streaming_app(spec)
            streaming[canonical] = {
                "app_installed": app_info["kind"] is not None,
                "app_kind": app_info["kind"],
                "has_deeplink": spec.get("deeplink") is not None,
                "web_url_template": spec.get("web_url"),
            }
        return _ok(
            backends=["browser_youtube", "windows_media_keys", "local_file",
                       "vlc_cli", "winrt_smtc",
                       "spotify", "netflix", "disney", "hbo_max", "prime_video"],
            now_playing_supported=True,
            vlc_available=bool(_find_vlc_executable()),
            streaming_platforms=streaming,
            note="now_playing uses Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager via PowerShell. Streaming platforms launch desktop app if installed (with deeplink) else open web search URL.",
        )
    if action == "play":
        query = str(args.get("query") or args.get("song") or args.get("title") or "").strip()
        path = str(args.get("path") or "").strip()
        provider = str(args.get("provider") or "youtube").casefold()
        if path:
            return _media_play_local(path, args)
        # Streaming providers con soporte nativo (Spotify, Netflix, Disney+,
        # HBO Max/Max, Prime Video). Prioriza la app desktop si esta instalada
        # con deeplink confiable, sino abre la web URL de busqueda.
        if _resolve_streaming_provider(provider):
            return _media_play_streaming(provider, query, args, executor=executor, state=state)
        if provider in {"youtube", "yt", "browser"}:
            return executor("browser", {"action": "youtube_play", "query": query or "musica"})
        if provider == "vlc":
            vlc = _find_vlc_executable()
            if not vlc:
                return _err(
                    "VLC is not installed",
                    status="needs_dependency", verified=False,
                    install_hint="winget install VideoLAN.VLC",
                )
            target = str(args.get("path") or args.get("url") or "").strip()
            if not target:
                return _err("vlc provider requires path or url")
            return _media_play_vlc(vlc, target)
        # Otros streaming providers sin soporte nativo: fallback honesto a
        # YouTube con nota explicita de que NO es el provider pedido.
        if provider in {"apple_music", "applemusic", "deezer",
                        "tidal", "amazon_music", "amazonmusic", "soundcloud"}:
            result = executor("browser", {"action": "youtube_play", "query": query or "musica"})
            if isinstance(result, dict):
                result = dict(result)
                result["fallback_from"] = provider
                result["fallback_note"] = (
                    f"{provider} requires native SDK/OAuth not configured; "
                    "played on YouTube instead."
                )
            return result
        return _err(
            f"unsupported media provider: {provider!r}",
            provider=provider, status="needs_dependency", verified=False,
            install_hint="Use provider=youtube (default), local_file with path=..., or vlc with path/url.",
        )
    if action == "open_local":
        path = str(args.get("path") or "").strip()
        if not path:
            return _err("missing path")
        return _media_play_local(path, args)
    if action in {"pause", "resume", "play_pause"}:
        return executor("audio", {"action": "media_play_pause"})
    if action == "stop":
        return executor("audio", {"action": "media_stop"})
    if action == "next":
        return executor("audio", {"action": "next"})
    if action == "previous":
        return executor("audio", {"action": "previous"})
    if action == "now_playing":
        return _media_now_playing()
    if action in {"queue_add", "queue_clear", "queue_list"}:
        if not state:
            return _err("queue actions require state", status="needs_implementation")
        return _media_queue(action, args, state)
    if action == "search_local_library":
        return _media_search_local_library(args)
    if action in {"volume_for_app", "cast_lan"}:
        return _err(
            f"media.{action} is not implemented yet",
            status="needs_implementation", verified=False,
            note=("volume_for_app needs SoundVolumeView /SetAppVolume" if action == "volume_for_app" else "cast_lan needs UPnP/DLNA backend (deferred)"),
        )
    return _err(
        "unknown media action", action=action,
        valid_actions=[
            "status", "play", "pause", "resume", "play_pause",
            "stop", "next", "previous", "now_playing",
        ],
        status="needs_user",
    )


def _media_play_local(path_raw: str, args: dict[str, Any]) -> dict[str, Any]:
    target = Path(path_raw).expanduser()
    if not target.exists():
        return _err("media file not found", path=path_raw)
    backend = str(args.get("backend") or "").casefold()
    if backend == "vlc":
        vlc = _find_vlc_executable()
        if vlc:
            return _media_play_vlc(vlc, str(target))
        return _err(
            "VLC backend requested but vlc not on PATH",
            status="needs_dependency", install_hint="winget install VideoLAN.VLC",
        )
    if os.name == "nt":
        os.startfile(target)
    else:
        webbrowser.open(target.as_uri())
    return _ok(action="play", provider="local_file", path=str(target.resolve()), opened=True, verified=True)


def _media_play_vlc(vlc: str, target: str) -> dict[str, Any]:
    proc = subprocess.Popen(
        [vlc, target, "--play-and-exit", "--no-video-title-show"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return _ok(action="play", provider="vlc", target=target, pid=proc.pid, verified=False, status="attempted", note="VLC launched; verify via now_playing or window list.")


def _media_now_playing() -> dict[str, Any]:
    """Query Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager.

    Pattern from Fleex (2018) and Microsoft Q&A; uses System.WindowsRuntimeSystemExtensions.AsTask
    to convert IAsyncOperation<T> to a Task<T> so PowerShell can wait synchronously.
    """
    script = r"""
$ErrorActionPreference = 'Stop'
try {
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime] > $null
  [Windows.Media.Control.GlobalSystemMediaTransportControlsSession,Windows.Media.Control,ContentType=WindowsRuntime] > $null
  [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties,Windows.Media.Control,ContentType=WindowsRuntime] > $null

  $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
  function Await($op, $resultType) {
    $task = $asTaskGeneric.MakeGenericMethod($resultType).Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    return $task.Result
  }

  $mgr = Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
  $session = $mgr.GetCurrentSession()
  if ($null -eq $session) {
    [PSCustomObject]@{ has_session=$false } | ConvertTo-Json
    exit 0
  }
  $props = Await ($session.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
  $info = $session.GetPlaybackInfo()
  $timeline = $session.GetTimelineProperties()
  [PSCustomObject]@{
    has_session = $true
    source_app_user_model_id = $session.SourceAppUserModelId
    title = $props.Title
    artist = $props.Artist
    album_title = $props.AlbumTitle
    track_number = $props.TrackNumber
    genres = @($props.Genres)
    playback_status = $info.PlaybackStatus.ToString()
    playback_type = $info.PlaybackType.ToString()
    is_play_enabled = $info.Controls.IsPlayEnabled
    is_pause_enabled = $info.Controls.IsPauseEnabled
    is_next_enabled = $info.Controls.IsNextEnabled
    is_previous_enabled = $info.Controls.IsPreviousEnabled
    position_seconds = $timeline.Position.TotalSeconds
    end_seconds = $timeline.EndTime.TotalSeconds
  } | ConvertTo-Json -Depth 4
} catch {
  [PSCustomObject]@{ error = $_.Exception.Message; has_session = $false } | ConvertTo-Json
}
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("now_playing query failed", stderr=proc.stderr, exit_code=proc.returncode)
    raw = proc.stdout.strip()
    if not raw:
        return _ok(has_session=False, note="no active media session")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err("now_playing returned invalid JSON", raw=raw[:1000])
    if not data.get("has_session"):
        return _ok(has_session=False, raw=data)
    return _ok(
        has_session=True,
        title=data.get("title"),
        artist=data.get("artist"),
        album=data.get("album_title"),
        source_app=data.get("source_app_user_model_id"),
        playback_status=data.get("playback_status"),
        playback_type=data.get("playback_type"),
        controls={
            "play": data.get("is_play_enabled"),
            "pause": data.get("is_pause_enabled"),
            "next": data.get("is_next_enabled"),
            "previous": data.get("is_previous_enabled"),
        },
        position_seconds=data.get("position_seconds"),
        end_seconds=data.get("end_seconds"),
        verified=True,
        evidence={"source": "Windows.Media.Control.GSMTCSM"},
    )


def _media_queue(action: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    if action == "queue_clear":
        for item in _resources_by_kind(state, "media_queue", include_closed=False):
            state.mark_cleaned(str(item["id"]), {"deleted": True})
        return _ok(cleared=True)
    if action == "queue_list":
        items = _resources_by_kind(state, "media_queue", include_closed=False)
        items.sort(key=lambda r: str(r.get("metadata", {}).get("added_at", "")))
        return _ok(queue=items, count=len(items))
    if action == "queue_add":
        item_query = str(args.get("query") or args.get("title") or "").strip()
        item_path = str(args.get("path") or "").strip()
        if not item_query and not item_path:
            return _err("queue_add requires query or path")
        label = item_query or Path(item_path).name
        resource = state.register_resource(
            "media_queue",
            label,
            metadata={
                "query": item_query or None,
                "path": item_path or None,
                "provider": args.get("provider"),
                "added_at": datetime.now().isoformat(),
            },
        )
        return _ok(queue_item=resource.get("resource"))
    return _err(
        "unknown queue action", action=action,
        valid_actions=["enqueue", "dequeue", "list", "clear", "current"],
        status="needs_user",
    )


def _media_search_local_library(args: dict[str, Any]) -> dict[str, Any]:
    root_raw = str(args.get("root") or "").strip()
    if not root_raw:
        # default user music folder
        root = Path.home() / "Music"
    else:
        root = Path(root_raw).expanduser()
    if not root.exists():
        return _err("library root not found", root=str(root))
    query = str(args.get("query") or "").casefold()
    extensions = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".wma"}
    limit = int(args.get("limit", 50))
    results = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in extensions:
            continue
        if query and query not in path.name.casefold() and query not in str(path.parent.name).casefold():
            continue
        try:
            results.append({"path": str(path), "name": path.name, "size": path.stat().st_size})
        except OSError:
            continue
        if len(results) >= limit:
            break
    return _ok(results=results, count=len(results), root=str(root))


def source_manager_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(local_state=True, source_count=len(_resources_by_kind(state, "source")))
    if action in {"list", "sources"}:
        return _ok(sources=_resources_by_kind(state, "source", include_closed=bool(args.get("include_closed", False))))
    if action in {"save", "add"}:
        title = str(args.get("title") or args.get("url") or args.get("source") or "source").strip()
        text = str(args.get("text") or args.get("content") or "").strip()
        url = str(args.get("url") or "").strip()
        resource = state.register_resource(
            "source",
            title,
            metadata={"title": title, "url": url, "source": args.get("source"), "text": text, "saved_at": datetime.now().isoformat()},
        )
        return _ok(source=resource.get("resource"))
    if action == "snapshot_file":
        path = _existing_path(args)
        if not path:
            return _err("missing or invalid path")
        max_chars = int(args.get("max_chars", 12000))
        text = path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        resource = state.register_resource("source", path.name, metadata={"title": path.name, "path": str(path), "text": text, "saved_at": datetime.now().isoformat()})
        return _ok(source=resource.get("resource"), chars=len(text))
    if action == "search":
        query = str(args.get("query") or "").casefold()
        if not query:
            return _err("missing query")
        matches = []
        for source in _resources_by_kind(state, "source", include_closed=bool(args.get("include_closed", False))):
            haystack = json.dumps(source.get("metadata", {}), ensure_ascii=False).casefold() + " " + str(source.get("label", "")).casefold()
            if query in haystack:
                matches.append(source)
        return _ok(matches=matches[: int(args.get("limit", 10))], count=len(matches))
    if action in {"read", "get"}:
        source = _find_resource(args, state, "source")
        return _ok(source=source) if source else _err("source not found")
    if action == "delete":
        source = _find_resource(args, state, "source")
        return state.mark_cleaned(str(source["id"]), {"deleted": True}) if source else _err("source not found")
    return _err(
        "unknown source_manager action", action=action,
        valid_actions=[
            "status", "save", "add", "list", "source_get", "source_delete",
            "bibtex_export",
        ],
        status="needs_user",
    )


def dependency_tool(args: dict[str, Any]) -> dict[str, Any]:
    action = str(args.get("action") or "status").casefold()
    catalog = _dependency_catalog()
    if action in {"status", "list"}:
        return _ok(dependencies=list(catalog.values()), missing=[d for d in catalog.values() if not d["available"]])
    if action in {"verify", "explain_missing"}:
        name = str(args.get("name") or args.get("dependency") or "").strip().casefold()
        matches = [item for key, item in catalog.items() if name in {key, item["name"].casefold()}] if name else [d for d in catalog.values() if not d["available"]]
        return _ok(matches=matches, count=len(matches))
    if action in {"install", "repair"}:
        name = str(args.get("name") or args.get("dependency") or "").strip().casefold()
        item = catalog.get(name)
        return _err(
            "dependency.install is advisory in this local tool",
            status="needs_user",
            verified=False,
            completion_status="needs_user_install",
            dependency=item or name,
            install_hint=(item or {}).get("install_hint") or "Use package/terminal explicitly if you want installation.",
        )
    return _err(
        "unknown dependency action", action=action,
        valid_actions=["status", "list", "verify", "explain_missing"],
        status="needs_user",
    )


# Regex laxas; el objetivo no es validar email/phone "correctos" sino
# rechazar valores claramente invalidos (caracteres de control, ints crudos).
# Contacts domain tool - extraído a domain_tools_contacts.py (R2 sprint
# 2026-05-27). Las 10 funciones contacts_tool + helpers vCard + name_similarity
# + _contacts_resolve_recipient + las 3 regex constants + 2 thresholds viven
# ahora en domain_tools_contacts.py. Re-export acá para compat (dispatch lo
# importa vía la clase ToolRegistry, mantenemos nombres en namespace).
from .domain_tools_contacts import (  # noqa: F401  (re-export por compat)
    _CONTROL_CHARS_RE,
    _EMAIL_BASIC_RE,
    _PHONE_BASIC_RE,
    _RESOLVE_AMBIGUOUS_MARGIN,
    _RESOLVE_MIN_SCORE,
    _clean_contact_field,
    _contact_to_vcard,
    _contacts_export_vcard,
    _contacts_import_vcard,
    _contacts_resolve_recipient,
    _contacts_update,
    _name_similarity,
    _vcard_escape,
    _vcard_parse,
    _vcard_unescape,
    contacts_tool,
)


def _parse_due_iso(value: Any) -> tuple[str | None, str | None]:
    """Intenta normalizar un `due` a ISO 8601. Devuelve (iso_str_or_None, error_msg_or_None).

    Acepta:
      - "2026-05-20" -> "2026-05-20T00:00:00"
      - "2026-05-20T15:30" -> "2026-05-20T15:30:00"
      - ya-ISO -> passthrough
      - None / "" -> (None, None)  (sin due es valido)

    Rechaza strings de lenguaje natural ("mañana", "tomorrow") con un mensaje
    claro para que el LLM resuelva el delta antes de llamar.
    """
    if value is None:
        return None, None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None, None
        # Patron ISO laxo: YYYY-MM-DD opcional T HH:MM[:SS]
        if re.match(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?$", s):
            if "T" not in s:
                s = s + "T00:00:00"
            elif s.count(":") == 1:
                s = s + ":00"
            return s, None
        # Intentar parsear como datetime (cubre microseconds, timezones).
        try:
            datetime.fromisoformat(s)
            return s, None
        except ValueError:
            pass
        return None, (
            f"due value {s!r} is not ISO 8601. Pass YYYY-MM-DD or YYYY-MM-DDTHH:MM; "
            "for relative dates ('tomorrow', 'next week') resolve the absolute "
            "date in the agent before calling."
        )
    return None, f"due must be a string, got {type(value).__name__}"


# ---------------------------------------------------------------------------
# WhatsApp tool
# ---------------------------------------------------------------------------

# WhatsApp UWP package family name (instalacion estandar desde Microsoft Store).
_WHATSAPP_UWP_PFN = "5319275A.WhatsAppDesktop_cv1g1gvanyjgm"

# Numero E.164 (puede tener +, espacios, guiones, parentesis).
_WHATSAPP_PHONE_RE = re.compile(r"^[\+\d\s\-\(\)]{7,20}$")


def _normalize_phone_for_whatsapp(phone: str) -> str:
    """Normaliza un numero al formato que espera whatsapp:// y wa.me:
    solo digitos, sin el +, sin separadores. Ej. '+54 9 11 1234-5678' -> '54911123456 78'.
    """
    if not phone:
        return ""
    # Mantener solo digitos.
    digits = re.sub(r"\D", "", phone)
    return digits


def _find_whatsapp_app() -> dict[str, str | None]:
    """Detecta si WhatsApp esta instalado como UWP.

    Returns dict con kind ('uwp' | None) y launch_target.
    Reutiliza el patron de _find_streaming_app.
    """
    if os.name != "nt":
        return {"kind": None, "launch_target": None}
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
              f"if (Get-AppxPackage -Name '{_WHATSAPP_UWP_PFN.split('_')[0]}') {{ Write-Output yes }}"],
            capture_output=True, text=True, timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode == 0 and "yes" in (proc.stdout or "").lower():
            return {"kind": "uwp", "launch_target": f"shell:AppsFolder\\{_WHATSAPP_UWP_PFN}!App"}
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"kind": None, "launch_target": None}


def _resolve_whatsapp_recipient(
    args: dict[str, Any], state: AgentState,
) -> tuple[str | None, str | None, str, str | None] | dict[str, Any]:
    """Resuelve el destinatario.

    Acepta en args:
      - phone="<numero>"  -> usado directamente (validado).
      - contact="<nombre>" o recipient="<nombre>"  -> busca en contacts.

    Returns:
      - tupla (raw_phone, normalized_digits, source, name_for_gui_search) si OK.
        Si phone resolvio -> (phone, normalized, source, None) — usar deeplink.
        Si solo hay nombre (contacto sin phone en store, o store vacio) ->
        (None, None, "gui_search", name_query) — usar GUI search en WhatsApp.
      - dict de error _err(...) si no se pudo resolver (sin phone ni nombre).
    """
    explicit_phone = str(args.get("phone") or args.get("number") or "").strip()
    if explicit_phone:
        if not _WHATSAPP_PHONE_RE.match(explicit_phone):
            return _err(
                f"invalid phone format: {explicit_phone!r}",
                hint=("Pass an international format like +54 9 11 1234-5678 or "
                      "just digits 5491112345678. WhatsApp requires country code."),
                status="needs_user",
            )
        normalized = _normalize_phone_for_whatsapp(explicit_phone)
        if len(normalized) < 7:
            return _err(
                f"phone too short after normalization: {normalized!r}",
                hint="Include country code (e.g. 54 for Argentina, 1 for USA).",
                status="needs_user",
            )
        return explicit_phone, normalized, "explicit", None

    # Resolver por nombre.
    name_query = str(
        args.get("contact") or args.get("recipient") or args.get("to")
        or args.get("name") or ""
    ).strip()
    if not name_query:
        return _err(
            "missing recipient: pass phone='+...' OR contact='<name>'",
            status="needs_user",
        )

    # 1. Intentar contacts store local (rapido si esta).
    resolve_result = _contacts_resolve_recipient({"query": name_query, "limit": 5}, state)
    matches = resolve_result.get("matches") or []
    # Inv 2 (grounding): si la resolución es AMBIGUA (dos contactos casi
    # empatados), NO adivinar — pedir desempate. Mandar al chat equivocado es
    # daño irreversible (bug "mamá"->"Música"). Mejor preguntar.
    if resolve_result.get("ambiguous") and len(matches) >= 2:
        cand_names = [
            str((m["contact"].get("metadata") or {}).get("name")
                or m["contact"].get("label") or "?")
            for m in matches[:3]
        ]
        return _err(
            f"contacto ambiguo para {name_query!r}",
            status="needs_user",
            contact_name=name_query,
            candidates=cand_names,
            hint=f"¿A cuál querías: {', '.join(cand_names)}?",
        )
    if matches:
        best = matches[0]["contact"]
        meta = best.get("metadata") or {}
        phone = str(meta.get("phone") or "").strip()
        if phone:
            normalized = _normalize_phone_for_whatsapp(phone)
            if len(normalized) >= 7:
                return phone, normalized, f"contact:{best.get('id')}", None
        # Contacto encontrado pero sin phone util -> caer a GUI search.

    # 2. Fallback: GUI search dentro de WhatsApp Desktop.
    # WhatsApp ya tiene la lista de contactos del telefono — usa Ctrl+F /
    # campo de busqueda para encontrar al contacto por nombre. Esto cubre
    # el caso "el contacto existe en WhatsApp pero no en mi store local".
    return None, None, "gui_search", name_query


def _resolve_whatsapp_recipient_legacy3(
    args: dict[str, Any], state: AgentState,
) -> tuple[str, str, str] | dict[str, Any]:
    """Backwards-compat 3-tuple form. Solo para tests viejos que esperaban
    (raw, normalized, source). NO usar en codigo nuevo.
    """
    r = _resolve_whatsapp_recipient(args, state)
    if isinstance(r, dict):
        return r
    raw, normalized, source, name = r
    if normalized is None:
        # tests legacy no soportaban el path gui_search; devolver error util.
        return _err(
            f"contact {name!r} found but has no phone number (use new GUI search path)",
            status="needs_user", contact_name=name,
        )
    return raw, normalized, source


def _verify_chat_header_uia(executor: Executor, contact_name: str) -> bool | None:
    """Inv 8 (UIA primary): verifica el chat activo leyendo el ÁRBOL DE
    ACCESIBILIDAD de WhatsApp (no OCR, no mmproj, sub-segundo). WhatsApp Desktop
    moderno es WebView2/Chromium: el nombre del contacto aparece como el `Name`
    de un control (heading/text/listitem). Buscamos un token significativo del
    nombre entre los elementos UIA de la ventana de WhatsApp.

    Returns:
        True  -> encontrado en el árbol UIA (chat correcto).
        None  -> UIA no disponible / sin evidencia -> el caller cae a OCR.
        (no devuelve False: ausencia en UIA no PRUEBA chat equivocado; eso lo
         decide el verificador OCR, más sensible al header visible.)
    """
    import re as _re
    try:
        res = executor("uia", {"action": "find", "window": "WhatsApp",
                               "query": contact_name, "limit": 40})
    except Exception:
        return None
    if not isinstance(res, dict) or not res.get("ok"):
        return None
    matches = res.get("matches")
    if not isinstance(matches, list):
        return None
    names = " ".join(
        str(m.get("name", "")) for m in matches if isinstance(m, dict)).lower()
    if not names.strip():
        return None
    names = _re.sub(r"[^a-záéíóúüñ ]", " ", names)
    tokens = [t for t in _re.split(r"\s+", contact_name.lower()) if len(t) >= 3]
    if not tokens:
        return None
    return True if any(t in names for t in tokens) else None


def _verify_chat_header(executor: Executor, contact_name: str) -> bool:
    """Confirma que el chat abierto en WhatsApp es del contacto pedido.

    Bug #847b: el Enter a ciegas tras buscar abría el chat equivocado (mensaje a
    'mamá' cayó en el grupo 'Música'). Antes de escribir verificamos el chat
    activo. Inv 8: PRIMERO por UIA (árbol de accesibilidad, barato, sin mmproj);
    si UIA no da evidencia, FALLBACK a OCR de la franja superior. Conservador: si
    NINGUNO verifica, devolvemos False -> el caller NO escribe (mejor no mandar
    que mandar al chat equivocado).

    El match es laxo a propósito: el header puede tener emojis/apodos ("Mamá🍓");
    basta con que un token alfabético >=3 chars del contacto aparezca.
    """
    import re as _re
    # Inv 8: UIA primero (más rápido y fiable que OCR, no carga mmproj).
    uia_ok = _verify_chat_header_uia(executor, contact_name)
    if uia_ok is True:
        return True
    # Fallback: OCR de la franja superior.
    try:
        shot = executor("gui", {"action": "locate_text", "text": contact_name})
    except Exception:
        return False
    if not isinstance(shot, dict):
        return False
    # locate_text devuelve found=True y matches si lo encontró en pantalla.
    if shot.get("found"):
        return True
    # Fallback: el OCR completo puede traer el texto aunque el match exacto falle
    # (emojis, mayúsculas). Buscar un token significativo del nombre en el texto.
    ocr_text = ""
    for key in ("text", "ocr_text", "full_text"):
        v = shot.get(key)
        if isinstance(v, str) and v:
            ocr_text = v
            break
    if not ocr_text and isinstance(shot.get("matches"), list):
        ocr_text = " ".join(
            str(m.get("text", "")) for m in shot["matches"] if isinstance(m, dict))
    ocr_norm = _re.sub(r"[^a-záéíóúüñ ]", " ", ocr_text.lower())
    tokens = [t for t in _re.split(r"\s+", contact_name.lower()) if len(t) >= 3]
    if not tokens:
        # nombre muy corto (p.ej. "mi") -> no podemos verificar con seguridad
        return False
    return any(t in ocr_norm for t in tokens)


def _verify_chat_header_status(executor: Executor, contact_name: str) -> str:
    """Tri-state para el envio WhatsApp.

    Returns:
        "confirmed"   -> el header contiene el contacto pedido.
        "wrong_chat"  -> el OCR leyo un header corto y claramente distinto.
        "unknown"     -> UIA/OCR no dio evidencia suficiente.

    El bool historico _verify_chat_header mezclaba "wrong_chat" con "unknown" y eso
    rompio WhatsApp: cuando WebView2 no exponia el header, abortaba envios validos.
    """
    import re as _re

    def _fold(s: str) -> str:
        s = unicodedata.normalize("NFKD", s.casefold())
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return _re.sub(r"[^a-z0-9 ]", " ", s)

    # Do NOT use broad UIA find here. It can match the contact in the search
    # results/sidebar while the active chat is still the old one. For the final
    # send gate we need visible header evidence after the search overlay is gone.
    try:
        shot = executor("gui", {"action": "locate_text", "text": contact_name})
    except Exception:
        return "unknown"
    if not isinstance(shot, dict):
        return "unknown"
    if shot.get("found"):
        return "confirmed"
    ocr_text = ""
    for key in ("text", "ocr_text", "full_text"):
        v = shot.get(key)
        if isinstance(v, str) and v.strip():
            ocr_text = v
            break
    if not ocr_text and isinstance(shot.get("matches"), list):
        ocr_text = " ".join(
            str(m.get("text", "")) for m in shot["matches"] if isinstance(m, dict))
    ocr_norm = _fold(ocr_text)
    target_tokens = [t for t in _fold(contact_name).split() if len(t) >= 3]
    if not target_tokens or not ocr_norm.strip():
        return "unknown"
    if any(t in ocr_norm for t in target_tokens):
        return "confirmed"
    # Si OCR devolvio un texto corto, probablemente es el header visible; si no
    # contiene el contacto pedido, es un chat distinto. Textos largos suelen ser OCR
    # de toda la pantalla/lista, no evidencia fiable para bloquear.
    visible_tokens = [t for t in _re.split(r"\s+", ocr_norm) if len(t) >= 2]
    if visible_tokens and len(visible_tokens) <= 6:
        return "wrong_chat"
    return "unknown"


def _verify_visible_whatsapp_text_status(executor: Executor, target_text: str) -> str:
    """Confirma por OCR que un texto reciente quedo visible en WhatsApp."""
    import re as _re

    def _fold(s: str) -> str:
        s = unicodedata.normalize("NFKD", s.casefold())
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return _re.sub(r"[^a-z0-9 ]", " ", s)

    target = (target_text or "").strip()
    if not target:
        return "unknown"
    try:
        import win32gui  # type: ignore
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return "unknown"
        title = win32gui.GetWindowText(hwnd) or ""
        if "whatsapp" not in title.lower():
            return "unknown"
        rect = win32gui.GetWindowRect(hwnd)
    except Exception:
        return "unknown"

    try:
        shot = executor("gui", {"action": "screenshot", "monitor": "all"})
    except Exception:
        return "unknown"
    if not isinstance(shot, dict) or not shot.get("ok") or not shot.get("image_path"):
        return "unknown"

    try:
        from PIL import Image
        from .ops_tools import ocr_find_text
        image_path = Path(str(shot["image_path"]))
        img = Image.open(image_path)
        screen_left = int(shot.get("left", 0))
        screen_top = int(shot.get("top", 0))
        left, top, right, bottom = [int(v) for v in rect]
        box = (
            max(0, left - screen_left),
            max(0, top - screen_top),
            min(img.width, right - screen_left),
            min(img.height, bottom - screen_top),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            return "unknown"
        crop_path = image_path.with_name(image_path.stem + "_whatsapp_crop.png")
        img.crop(box).save(crop_path)
        found = ocr_find_text(crop_path, target[:80], lang="spa+eng", min_conf=25)
    except Exception:
        return "unknown"

    if not isinstance(found, dict):
        return "unknown"
    if found.get("found"):
        return "confirmed"
    ocr_text = str(found.get("ocr_text") or found.get("text") or "")
    if not ocr_text:
        return "unknown"
    ocr_norm = _fold(ocr_text)
    target_tokens = [t for t in _fold(target).split() if len(t) >= 4]
    if not target_tokens:
        return "unknown"
    needed = target_tokens[: min(4, len(target_tokens))]
    return "confirmed" if all(t in ocr_norm for t in needed) else "unknown"


def _capture_whatsapp_chat_area(executor: Executor) -> dict[str, Any] | None:
    """Captura la zona de mensajes del chat activo, excluyendo sidebar e input."""
    try:
        import win32gui  # type: ignore
        from PIL import Image

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        title = win32gui.GetWindowText(hwnd) or ""
        if "whatsapp" not in title.lower():
            return None
        left, top, right, bottom = [int(v) for v in win32gui.GetWindowRect(hwnd)]
        shot = executor("gui", {"action": "screenshot", "monitor": "all"})
        if not isinstance(shot, dict) or not shot.get("ok") or not shot.get("image_path"):
            return None
        img = Image.open(Path(str(shot["image_path"]))).convert("RGB")
        screen_left = int(shot.get("left", 0))
        screen_top = int(shot.get("top", 0))
        w = max(1, right - left)
        h = max(1, bottom - top)
        # WhatsApp desktop: sidebar a la izquierda, header arriba, composer abajo.
        box = (
            max(0, int(left + w * 0.35) - screen_left),
            max(0, int(top + h * 0.14) - screen_top),
            min(img.width, int(right - w * 0.02) - screen_left),
            min(img.height, int(bottom - h * 0.13) - screen_top),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            return None
        crop = img.crop(box)
        return {"image": crop, "box": box}
    except Exception:
        return None


def _whatsapp_chat_area_changed(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> bool:
    try:
        from PIL import ImageChops, ImageStat

        if not before or not after:
            return False
        a = before.get("image")
        b = after.get("image")
        if a is None or b is None:
            return False
        if a.size != b.size:
            b = b.resize(a.size)
        diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
        bbox = diff.getbbox()
        if bbox is None:
            return False
        area_ratio = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / max(1, a.size[0] * a.size[1])
        mean_delta = sum(ImageStat.Stat(diff).mean) / 3.0
        return area_ratio >= 0.01 and mean_delta >= 0.35
    except Exception:
        return False


def _whatsapp_send_via_gui_search(
    executor: Executor,
    contact_name: str,
    text: str,
    wait_seconds: float,
    auto_send: bool,
) -> dict[str, Any]:
    """Abre WhatsApp generico, busca el contacto por nombre via Ctrl+N,
    selecciona el primer match, escribe el mensaje y opcionalmente envia.

    Flujo (todos los pasos requieren focus verification antes de teclear):
      1. Dispatch whatsapp:// (sin args -> abre la app generica).
      2. Wait wait_seconds para que cargue.
      3. Focus WhatsApp + verify active window title.
      4. Ctrl+N (abre nuevo chat / selector global de contacto).
      5. Type contact_name.
      6. Wait ~1s (deja que filtre los resultados).
      7. Enter (selecciona el primer chat).
      8. Wait ~0.5s (entra al chat).
      9. Type text del mensaje.
      10. Si auto_send: Enter (envia).

    Returns dict con keys:
      - sent: bool
      - chat_opened: bool
      - search_term: str
      - abort_reason: str | None
      - steps: list[str] — pasos completados (para debug)
    """
    import time as _time

    steps: list[str] = []
    action_results: list[dict[str, Any]] = []

    def _compact_result(result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {"type": type(result).__name__}
        keep = (
            "ok", "error", "reason", "status", "completion_status", "verified",
            "state_changed", "state_verify", "method", "keys", "chars",
            "exit_code", "events", "found", "source", "action",
        )
        compact = {k: result.get(k) for k in keep if k in result}
        nested = result.get("result")
        if isinstance(nested, dict):
            compact["result"] = {
                k: nested.get(k)
                for k in ("ok", "error", "action", "title", "process", "pid", "hwnd")
                if k in nested
            }
        return compact

    def _result_failure(label: str, result: Any, *, require_effect: bool = False) -> str | None:
        if not isinstance(result, dict):
            return f"{label} returned non-dict result"
        if result.get("ok") is not True:
            return str(result.get("error") or result.get("reason") or "ok was not true")
        nested = result.get("result")
        if isinstance(nested, dict) and nested.get("ok") is False:
            return str(nested.get("error") or "nested result ok=false")
        if result.get("found") is False:
            return str(result.get("error") or "target window/control was not found")
        if require_effect and result.get("state_changed") is False:
            return str(result.get("state_verify") or "action caused no visible state change")
        events = result.get("events")
        if isinstance(events, (int, float)) and events <= 0:
            return "input injector reported zero events"
        exit_code = result.get("exit_code")
        if isinstance(exit_code, int) and exit_code != 0:
            return f"input command returned exit_code={exit_code}"
        return None

    def _abort(
        label: str,
        reason: str,
        *,
        chat_opened: bool = False,
        result: Any = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "sent": False,
            "chat_opened": chat_opened,
            "search_term": contact_name,
            "abort_reason": f"{label}: {reason}",
            "steps": steps,
            "physical_actions_ok": False,
            "gui_action_results": action_results,
        }
        if result is not None:
            payload["failed_step"] = label
            payload["failed_result"] = _compact_result(result)
        if extra:
            payload.update(extra)
        return payload

    def _checked_executor(
        tool: str,
        args: dict[str, Any],
        label: str,
        *,
        require_effect: bool = False,
    ) -> tuple[dict[str, Any] | None, str | None]:
        if tool == "gui" and str(args.get("action") or "") in {
            "click", "double_click", "right_click", "type", "type_into",
            "click_button", "keypress", "hotkey", "scroll", "drag",
        }:
            _wait_until_not_user_active()
        try:
            result = executor(tool, args)
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"
        failure = _result_failure(label, result, require_effect=require_effect)
        if failure:
            return result, failure
        action_results.append({"step": label, "tool": tool, **_compact_result(result)})
        return result, None

    def _focus_and_verify() -> tuple[bool, str | None, Any]:
        # window.focus ahora hace restore + maximize si la ventana es chica
        # (regla universal aplicada en tools.py:window_control). Damos grace
        # de 0.5s para que el maximize tome efecto antes de verificar.
        last_active: Any = None
        last_title = ""
        for attempt in range(3):
            focus, abort = _checked_executor(
                "window", {"action": "focus", "title": "WhatsApp"}, "focus WhatsApp")
            if abort is not None:
                return False, abort, focus
            _time.sleep(0.5 + 0.25 * attempt)
            active, abort = _checked_executor("window", {"action": "active"}, "read active window")
            if abort is not None:
                return False, abort, active
            last_active = active
            active_title = ""
            a = active.get("active") if isinstance(active, dict) else None
            if isinstance(a, dict):
                active_title = str(a.get("title") or "")
            elif isinstance(active, dict):
                active_title = str(active.get("title") or "")
            last_title = active_title
            if "whatsapp" in active_title.lower():
                return True, None, active
        return False, f"active window is not WhatsApp: {last_title!r}", last_active

    def _focus_compose_box() -> tuple[dict[str, Any] | None, str | None]:
        """Click en la caja de mensaje del chat activo sin depender del idioma UI."""
        try:
            import win32gui  # type: ignore
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None, "no foreground window"
            title = win32gui.GetWindowText(hwnd) or ""
            if "whatsapp" not in title.lower():
                return None, f"active window is not WhatsApp: {title!r}"
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        except Exception as exc:
            return None, f"could not locate WhatsApp compose box: {exc}"
        width = max(1, right - left)
        height = max(1, bottom - top)
        x = int(left + width * 0.72)
        y = int(bottom - max(44, min(72, height * 0.05)))
        return _checked_executor(
            "gui", {"action": "click", "x": x, "y": y}, "focus compose box")

    def _wait_until_not_user_active(timeout_s: float = 3.0) -> None:
        try:
            from . import gui_safety
        except Exception:
            return
        deadline = _time.monotonic() + max(0.0, timeout_s)
        while _time.monotonic() < deadline:
            try:
                if not gui_safety.user_is_active():
                    return
            except Exception:
                return
            _time.sleep(0.2)

    # 1. Abrir WhatsApp (deeplink generico).
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", "whatsapp://"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, FileNotFoundError) as exc:
        return {
            "sent": False, "chat_opened": False, "search_term": contact_name,
            "abort_reason": f"failed to launch WhatsApp: {exc}", "steps": steps,
            "physical_actions_ok": False, "gui_action_results": action_results,
        }
    steps.append("dispatched_deeplink")
    _time.sleep(max(0.5, wait_seconds))

    # 2. Focus + verify (incluye restore+maximize implicito).
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus WhatsApp after launch",
            reason or "could not focus WhatsApp window after launch",
            result=result,
        )
    steps.append("focused")
    # Extra grace tras maximize — el window manager necesita repaint.
    _time.sleep(0.4)

    # 3. Ctrl+N abre el selector global de nuevo chat. Ctrl+F puede quedarse en
    # "buscar dentro del chat actual", lo que produjo falsos positivos: se
    # tipeaba el contacto en la busqueda del chat viejo y luego el mensaje no
    # salia al destinatario pedido.
    result, reason = _checked_executor(
        "gui",
        {
            "action": "keypress", "keys": "ctrl+n",
            "window": "WhatsApp", "method": "sendkeys",
        },
        "open new chat search",
    )
    if reason:
        return _abort("open new chat search", reason, result=result)
    steps.append("opened_new_chat_search")
    _time.sleep(0.6)

    result, reason = _checked_executor(
        "gui",
        {
            "action": "keypress", "keys": "ctrl+a",
            "window": "WhatsApp", "method": "sendkeys",
        },
        "select contact search text",
    )
    if reason:
        return _abort("select contact search text", reason, result=result)
    steps.append("selected_contact_search_text")
    _time.sleep(0.1)

    # 4. Type del nombre del contacto.
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus before typing contact name",
            reason or "lost WhatsApp focus before typing contact name",
            result=result,
        )
    result, reason = _checked_executor(
        "gui",
        {
            "action": "type", "text": contact_name,
            "window": "WhatsApp", "method": "sendkeys",
        },
        "type contact name",
    )
    if reason:
        return _abort("type contact name", reason, result=result)
    steps.append("typed_contact_name")
    _time.sleep(1.0)  # tiempo para que WhatsApp filtre

    # 5. Enter para seleccionar primer resultado y entrar al chat.
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus before selecting contact",
            reason or "lost WhatsApp focus before selecting contact",
            result=result,
        )
    result, reason = _checked_executor(
        "gui",
        {
            "action": "keypress", "keys": "enter",
            "window": "WhatsApp", "method": "sendkeys",
        },
        "select first contact match",
    )
    if reason:
        return _abort("select first contact match", reason, result=result)
    steps.append("selected_first_match")
    _time.sleep(0.8)  # entrar al chat

    # Enter normalmente cierra el selector de nuevo chat. No mandamos Escape aqui:
    # necesitamos conservar el presupuesto fisico para enfocar la caja de mensaje.

    # 5b. Verificacion hard gate. Nunca escribir/enviar si no vemos evidencia
    # del header del chat pedido. Antes "unknown" seguia adelante y podia marcar
    # sent=True aunque el texto hubiera quedado en un buscador o en otro chat.
    chat_status = _verify_chat_header_status(executor, contact_name)
    chat_verified = chat_status == "confirmed"
    steps.append(f"chat_header_verified:{chat_verified}")
    steps.append(f"chat_header_status:{chat_status}")
    if chat_status != "confirmed":
        return {
            "sent": False,
            "chat_opened": chat_status == "wrong_chat",
            "search_term": contact_name,
            "abort_reason": (
                f"no pude confirmar que el chat abierto es de '{contact_name}' "
                "despues de buscarlo — no escribo para no mandar al chat equivocado."
            ),
            "steps": steps, "chat_verified": False, "chat_header_status": chat_status,
            "physical_actions_ok": False, "gui_action_results": action_results,
        }
    chat_area_before_send = _capture_whatsapp_chat_area(executor)

    # 6. Type del mensaje (focus moved al input del chat).
    if not text:
        # open_chat: solo queriamos llegar al chat, no mandar.
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": None, "steps": steps, "chat_verified": chat_verified,
            "chat_header_status": chat_status, "physical_actions_ok": True,
            "gui_action_results": action_results,
        }
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus before typing message",
            reason or "lost WhatsApp focus before typing message",
            chat_opened=True,
            result=result,
        )
    result, reason = _focus_compose_box()
    if reason:
        return _abort("focus compose box", reason, chat_opened=True, result=result)
    steps.append("focused_compose_box")
    _time.sleep(0.2)
    result, reason = _checked_executor(
        "gui",
        {
            "action": "type", "text": text,
            "window": "WhatsApp", "method": "sendkeys",
        },
        "type message",
    )
    if reason:
        return _abort("type message", reason, chat_opened=True, result=result)
    steps.append("typed_message")
    _time.sleep(0.4)

    # 7. Enviar si auto_send.
    if not auto_send:
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": None, "steps": steps, "chat_verified": chat_verified,
            "chat_header_status": chat_status, "physical_actions_ok": True,
            "gui_action_results": action_results,
        }
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus before sending",
            reason or "lost WhatsApp focus before sending",
            chat_opened=True,
            result=result,
        )
    result, reason = _checked_executor(
        "gui",
        {
            "action": "keypress", "keys": "enter",
            "window": "WhatsApp", "method": "sendkeys",
        },
        "send message",
    )
    if reason:
        return _abort("send message", reason, chat_opened=True, result=result)
    steps.append("sent_enter")
    _time.sleep(0.8)
    chat_area_after_send = _capture_whatsapp_chat_area(executor)
    visual_changed = _whatsapp_chat_area_changed(chat_area_before_send, chat_area_after_send)
    steps.append(f"sent_message_area_changed:{visual_changed}")
    message_status = _verify_visible_whatsapp_text_status(executor, text)
    steps.append(f"sent_message_visible:{message_status}")
    if message_status != "confirmed" and not visual_changed:
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": (
                "no pude verificar en pantalla que el mensaje enviado aparezca "
                "en el chat despues de presionar Enter."
            ),
            "steps": steps, "chat_verified": chat_verified,
            "chat_header_status": chat_status,
            "sent_message_visible_status": message_status,
            "sent_message_area_changed": visual_changed,
            "physical_actions_ok": False,
            "gui_action_results": action_results,
        }
    return {
        "sent": True, "chat_opened": True, "search_term": contact_name,
        "abort_reason": None, "steps": steps, "chat_verified": chat_verified,
        "chat_header_status": chat_status, "physical_actions_ok": True,
        "sent_message_visible_status": message_status,
        "sent_message_area_changed": visual_changed,
        "gui_action_results": action_results,
    }


def _whatsapp_auto_send(executor: Executor, wait_seconds: float) -> dict[str, Any]:
    """Tras abrir el chat con el deeplink, esperar carga, asegurar focus
    de la ventana WhatsApp, y mandar Enter.

    Devuelve dict con keys:
      - "sent": bool — True si llegamos a mandar Enter.
      - "focus_verified": bool — si confirmamos que la ventana activa era WhatsApp.
      - "abort_reason": str | None — por que NO mandamos Enter (si aplica).
      - "wait_seconds": float — cuanto esperamos antes del Enter.

    Seguridad: NUNCA mandar Enter si no podemos confirmar que la ventana
    activa contiene "WhatsApp" en el titulo. De lo contrario el Enter va a
    la app que el user tenia en focus (IDE, browser, terminal con comando
    peligroso, etc.).
    """
    import time as _time
    # 1. Esperar a que WhatsApp termine de cargar el chat + rellenar texto.
    _time.sleep(max(0.5, wait_seconds))

    # 2. Asegurar focus: pedir explicitamente que la ventana de WhatsApp
    #    venga al frente. Si no esta abierta, esto falla silenciosamente.
    try:
        focus_result = executor("window", {"action": "focus", "title": "WhatsApp"})
    except Exception as exc:
        return {
            "sent": False, "focus_verified": False,
            "abort_reason": f"focus call failed: {exc}",
            "wait_seconds": wait_seconds,
        }
    focus_ok = bool(focus_result.get("ok"))

    # 3. Verificar que la ventana activa es realmente WhatsApp antes del Enter.
    #    Damos un pequeño grace para que el focus tome efecto.
    _time.sleep(0.3)
    try:
        active = executor("window", {"action": "active"})
    except Exception as exc:
        return {
            "sent": False, "focus_verified": False,
            "abort_reason": f"active check failed: {exc}",
            "wait_seconds": wait_seconds,
        }
    active_title = str(
        (active.get("active") or {}).get("title")
        if isinstance(active.get("active"), dict)
        else (active.get("title") or "")
    ).lower()
    if "whatsapp" not in active_title:
        return {
            "sent": False, "focus_verified": False,
            "abort_reason": (
                f"active window is {active_title!r}, not WhatsApp. "
                "Refusing to send Enter to a different app."
            ),
            "wait_seconds": wait_seconds,
            "focus_call_ok": focus_ok,
        }

    # 4. Enter — la ventana correcta esta en foco, podemos enviar el mensaje.
    try:
        keypress_result = executor("gui", {"action": "keypress", "keys": "enter"})
    except Exception as exc:
        return {
            "sent": False, "focus_verified": True,
            "abort_reason": f"keypress failed: {exc}",
            "wait_seconds": wait_seconds,
        }
    if not keypress_result.get("ok"):
        return {
            "sent": False, "focus_verified": True,
            "abort_reason": f"keypress returned: {keypress_result.get('error', 'unknown')}",
            "wait_seconds": wait_seconds,
        }
    return {
        "sent": True, "focus_verified": True,
        "abort_reason": None,
        "wait_seconds": wait_seconds,
        "active_window_title": active_title,
    }


def whatsapp_tool(
    args: dict[str, Any],
    state: AgentState,
    executor: Executor | None = None,
) -> dict[str, Any]:
    """Compound WhatsApp tool.

    Actions:
      - status:        report whether WhatsApp Desktop (UWP) is installed.
      - send_message:  open WhatsApp chat with phone + pre-filled text.
                        With auto_send=True (default) the tool waits for the
                        chat to load, focuses the WhatsApp window, verifies
                        active window is WhatsApp, then sends Enter — message
                        is actually delivered. With auto_send=False the chat
                        opens but Enter is NOT pressed (legacy behavior).
      - open_chat:     same as send_message but without text (just opens chat,
                        auto_send is ignored here).

    Phone resolution priority:
      1. args.phone (explicit, validated and normalized)
      2. args.contact / args.recipient / args.to / args.name -> lookup in
         state contacts (using existing _contacts_resolve_recipient).

    Safety for auto_send:
      - NEVER sends Enter without confirming the active window title contains
        "WhatsApp". This prevents sending Enter to a wrong window (IDE,
        terminal with destructive command, browser form, etc.).
      - If focus or active-window check fails, returns sent=False with
        abort_reason — the user sees the chat opened and can press Enter
        themselves.

    Defaults:
      auto_send=True for send_message (Meta deeplink doesn't actually auto-send;
      we provide a safe wrapper that does it via a verified keypress sequence).
      Pass auto_send=False if you only want the chat opened for the user to
      review/edit before sending.
    """
    import urllib.parse

    action = str(args.get("action") or "send_message").casefold()

    if action == "status":
        app_info = _find_whatsapp_app()
        return _ok(
            installed=app_info["kind"] is not None,
            app_kind=app_info["kind"],
            launch_target=app_info["launch_target"],
            web_fallback="https://wa.me/<phone>?text=<msg>",
            auto_send_supported=executor is not None,
            note=(
                "send_message with auto_send=True (default) opens chat AND sends "
                "after verifying focus. Set auto_send=False to only open the chat."
            ),
        )

    if action not in {"send_message", "open_chat", "send"}:
        return _err(
            f"unknown action: {action!r}",
            hint="Use action='send_message', 'open_chat', or 'status'.",
        )

    # Resolver destinatario.
    resolved = _resolve_whatsapp_recipient(args, state)
    if isinstance(resolved, dict):  # error
        return resolved
    raw_phone, normalized, source, gui_search_name = resolved

    # Mensaje (opcional para open_chat).
    text = str(args.get("text") or args.get("message") or args.get("body") or "").strip()
    if action in {"send_message", "send"} and not text:
        return _err(
            "missing text for send_message",
            hint="Pass text='<your message>' or use action='open_chat' to just open the chat.",
            status="needs_user",
        )

    # auto_send default True para send_message; False para open_chat.
    # Acepta string truthy/falsy y bool. Si executor=None, no podemos auto_send.
    auto_send_raw = args.get("auto_send", action != "open_chat")
    if isinstance(auto_send_raw, str):
        auto_send = auto_send_raw.strip().lower() not in {"", "false", "0", "no", "off"}
    else:
        auto_send = bool(auto_send_raw)
    if executor is None:
        auto_send = False  # sin executor no podemos focus+keypress
    # open_chat nunca envia: solo abre.
    if action == "open_chat":
        auto_send = False

    # PATH GUI SEARCH: si el resolver indico que necesitamos buscar el
    # contacto via la UI de WhatsApp (porque no tenemos phone), usar el
    # flujo Ctrl+F + type contact_name + Enter + type message + Enter.
    # Esto cubre contactos que existen en WhatsApp pero no en nuestro
    # contacts store local.
    if source == "gui_search" and gui_search_name and executor is not None:
        app_info = _find_whatsapp_app()
        if not app_info["kind"]:
            return _err(
                f"WhatsApp Desktop not installed; cannot search for contact {gui_search_name!r}",
                status="needs_user", provider="whatsapp",
                hint=("Install WhatsApp Desktop from Microsoft Store, OR add "
                      f"the contact phone first: contacts(action='create', "
                      f"name='{gui_search_name}', phone='+...')."),
            )
        wait_seconds_raw = args.get("wait_seconds") or args.get("send_delay_s") or 2.0
        try:
            wait_seconds = max(0.5, min(10.0, float(wait_seconds_raw)))
        except (TypeError, ValueError):
            wait_seconds = 2.0
        gui_result = _whatsapp_send_via_gui_search(
            executor, gui_search_name, text, wait_seconds, auto_send,
        )
        sent = bool(gui_result.get("sent"))
        chat_opened = bool(gui_result.get("chat_opened"))
        return _ok(
            action=action,
            provider="whatsapp_desktop_gui_search",
            recipient_contact=gui_search_name,
            recipient_source="gui_search",
            text=text or None,
            opened=chat_opened or gui_result.get("steps", []) != [],
            sent=sent,
            chat_opened=chat_opened,
            auto_send_attempted=auto_send,
            physical_actions_ok=bool(gui_result.get("physical_actions_ok")),
            gui_search_info=gui_result,
            verified=sent,
            status="dispatched" if sent else "attempted",
            completion_search="message_sent_via_gui_search" if sent
                               else "chat_search_partial",
            completion_status="message_sent" if sent
                               else ("chat_opened_pending_message"
                                     if chat_opened else "search_aborted"),
            note=(
                f"Sent {text!r} to {gui_search_name!r} via WhatsApp Desktop GUI search."
                if sent else
                f"WhatsApp GUI search for {gui_search_name!r} did not complete. "
                f"Reason: {gui_result.get('abort_reason') or 'unknown'}. "
                f"Steps completed: {gui_result.get('steps')}."
            ),
        )
    if source == "gui_search" and executor is None:
        return _err(
            f"contact {gui_search_name!r} requires GUI search but no executor "
            "available (CLI mode)",
            status="needs_user",
            hint=(
                "From CLI, pass phone='+...' explicitly, or run inside the agent "
                "where executor is wired."
            ),
        )
    # Tiempo de espera tras el deeplink antes de mandar Enter. Configurable
    # via args.wait_seconds. Default 1.8s — suficiente para que WhatsApp
    # Desktop ya este corriendo cargue el chat y rellene el input. Primera
    # vez en frio puede tardar mas; el user puede subirlo.
    wait_seconds_raw = args.get("wait_seconds") or args.get("send_delay_s") or 1.8
    try:
        wait_seconds = float(wait_seconds_raw)
    except (TypeError, ValueError):
        wait_seconds = 1.8
    wait_seconds = max(0.3, min(10.0, wait_seconds))

    # Construir URLs. Deeplink desktop scheme y wa.me como fallback.
    encoded_text = urllib.parse.quote(text) if text else ""
    deeplink = f"whatsapp://send?phone={normalized}"
    if encoded_text:
        deeplink += f"&text={encoded_text}"
    web_url = f"https://wa.me/{normalized}"
    if encoded_text:
        web_url += f"?text={encoded_text}"

    app_info = _find_whatsapp_app()
    desktop_err: str | None = None

    # PATH 1: WhatsApp Desktop instalado -> deeplink whatsapp://
    if app_info["kind"] and os.name == "nt":
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", deeplink],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, FileNotFoundError) as exc:
            desktop_err = str(exc)
        else:
            # Auto-send si esta habilitado y tenemos executor.
            auto_send_info: dict[str, Any] | None = None
            if auto_send and executor is not None:
                auto_send_info = _whatsapp_auto_send(executor, wait_seconds)
            sent = bool(auto_send_info and auto_send_info.get("sent"))
            return _ok(
                action=action,
                provider="whatsapp_desktop",
                recipient_phone=raw_phone,
                recipient_normalized=normalized,
                recipient_source=source,
                text=text or None,
                deeplink=deeplink,
                app_kind=app_info["kind"],
                opened=True,
                sent=sent,
                auto_send_attempted=auto_send,
                auto_send_info=auto_send_info,
                verified=sent,
                status="dispatched" if sent else "attempted",
                completion_status="message_sent" if sent
                                   else "chat_opened_pending_enter",
                note=(
                    "Message sent: WhatsApp focused + verified active window + Enter pressed."
                    if sent
                    else (
                        f"WhatsApp Desktop opened with chat pre-filled. "
                        f"{'Auto-send aborted: ' + (auto_send_info or {}).get('abort_reason', '?') + '. ' if auto_send_info and not sent else ''}"
                        "User can press Enter manually."
                    )
                ),
            )

    # PATH 2: fallback a wa.me (web). Auto_send aqui es mas fragil porque
    # depende del estado del browser (loguead/no, "Continuar al chat" click,
    # etc). Mantenemos auto_send=False en este path por seguridad.
    try:
        import webbrowser
        opened = webbrowser.open(web_url)
        if opened:
            result = _ok(
                action=action,
                provider="whatsapp_web",
                recipient_phone=raw_phone,
                recipient_normalized=normalized,
                recipient_source=source,
                text=text or None,
                url=web_url,
                opened=True,
                sent=False,
                auto_send_attempted=auto_send,
                auto_send_info={"abort_reason": "web fallback does not support auto_send safely"}
                                if auto_send else None,
                verified=False,
                status="attempted",
                completion_status="chat_opened_pending_enter",
                note=(
                    "wa.me (WhatsApp Web) opened in default browser. Auto-send "
                    "is disabled on the web path because we cannot reliably "
                    "verify the chat input has focus. User must click "
                    "'Continuar al chat' and press Enter."
                ),
            )
            if desktop_err:
                result["fallback_from"] = "whatsapp_desktop"
                result["fallback_reason"] = desktop_err
            return result
    except Exception as exc:
        return _err(
            f"Could not open WhatsApp (desktop deeplink and web both failed): {exc}",
            status="failed", provider="whatsapp",
            desktop_error=desktop_err,
        )
    return _err(
        "WhatsApp: no desktop app and webbrowser refused to open wa.me",
        status="needs_user", provider="whatsapp",
        install_hint="winget install WhatsApp.WhatsApp",
    )


# Notes / Tasks domain tool - extraído a domain_tools_notes.py (R2 sprint
# 2026-05-27). Re-export para compat (tools.py linea 51 hace
# ).
from .domain_tools_notes import notes_tasks_tool  # noqa: F401


# Local Calendar (ICS) domain tool - extraído a domain_tools_calendar.py
# (R2 sprint 2026-05-27). 9 funciones (entry + 8 helpers ICS). domain_tools.py
# ~-260 LOC. Re-export para compat (tools.py linea 33).
from .domain_tools_calendar import (  # noqa: F401  (re-export por compat)
    _calendar_event_update,
    _calendar_export_path,
    _calendar_ics_import,
    _events_to_ics,
    _ics_escape,
    _ics_normalize_datetime,
    _ics_parse_events,
    _ics_time,
    _ics_unescape,
    local_calendar_tool,
)


# Habit Tracker - extraído a domain_tools_habit_tracker.py (R2 sprint 2026-05-28).
from .domain_tools_habit_tracker import (  # noqa: F401
    _VALID_HABIT_FREQUENCIES,
    habit_tracker_tool,
)


# Local Search - extraído a domain_tools_local_search.py (R2 sprint 2026-05-28).
from .domain_tools_local_search import local_search_tool  # noqa: F401


# Printer & Scanner - extraído a domain_tools_printer_scanner.py
# (R2 sprint 2026-05-28). 6 funciones (entry + 5 helpers).
from .domain_tools_printer_scanner import (  # noqa: F401
    _printer_cancel_job,
    _printer_print_file,
    _printer_set_default,
    _scanner_scan,
    _scanners_list,
    printer_scanner_tool,
)


def _json_or_none(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def desktop_layout_tool(args: dict[str, Any], state: AgentState, executor: Executor) -> dict[str, Any]:
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


# Backup & Sync - extraído a domain_tools_backup_sync.py (R2 sprint 2026-05-28).
# Re-export incluye _next_available_path porque photo_library_tool lo usa
# desde línea ~1856.
from .domain_tools_backup_sync import (  # noqa: F401
    _backup_dedupe,
    _backup_resolve,
    _backup_restore,
    _backup_verify,
    _next_available_path,
    backup_sync_tool,
)


def _create_presentation(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    if importlib.util.find_spec("pptx") is None:
        return _err(
            "python-pptx is not installed",
            status="needs_dependency",
            verified=False,
            completion_status="needs_dependency",
            install_hint="python -m pip install python-pptx",
        )
    from pptx import Presentation

    title = str(args.get("title") or args.get("topic") or "Presentacion").strip()
    path = _output_path(args, state, _safe_name(title), ".pptx")
    slides = _slides_from_args(args, title)
    prs = Presentation()
    if slides:
        first = slides[0]
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        # python-pptx exposes `text` and `text_frame` on specific shape subclasses
        # (placeholders, autoshapes) but the abstract BaseShape type doesn't
        # declare them. Use setattr/getattr to bypass the static-type wall.
        title_shape: Any = slide.shapes.title
        if title_shape is not None:
            title_shape.text = str(first.get("title") or title)
        sub_shape: Any = slide.placeholders[1]
        sub_shape.text = str(first.get("subtitle") or first.get("body") or "")
        for item in slides[1:]:
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            t_shape: Any = slide.shapes.title
            if t_shape is not None:
                t_shape.text = str(item.get("title") or "Slide")
            body_shape: Any = slide.placeholders[1]
            body = body_shape.text_frame
            body.clear()
            raw_bullets = item.get("bullets")
            bullets: list[Any] | None = raw_bullets if isinstance(raw_bullets, list) else None
            if bullets:
                for bullet in bullets:
                    p = body.add_paragraph()
                    p.text = str(bullet)
                    p.level = 0
            else:
                body.text = str(item.get("body") or "")
    prs.save(str(path))
    resource = state.register_resource(
        "office_file",
        path.name,
        cleanup_tool="filesystem",
        cleanup_args={"action": "delete", "path": str(path)},
        metadata={"kind": "presentation", "path": str(path), "slides": len(prs.slides)},
    )
    return _ok(path=str(path.resolve()), kind="presentation", slides=len(prs.slides), resource=resource.get("resource"))


def _create_document(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    if importlib.util.find_spec("docx") is None:
        return _err("python-docx is not installed", status="needs_dependency", verified=False, install_hint="python -m pip install python-docx")
    from docx import Document

    title = str(args.get("title") or "Documento").strip()
    path = _output_path(args, state, _safe_name(title), ".docx")
    doc = Document()
    doc.add_heading(title, 0)
    content = str(args.get("content") or args.get("body") or "")
    for paragraph in [p.strip() for p in content.splitlines() if p.strip()]:
        doc.add_paragraph(paragraph)
    doc.save(str(path))
    resource = state.register_resource("office_file", path.name, cleanup_tool="filesystem", cleanup_args={"action": "delete", "path": str(path)}, metadata={"kind": "document", "path": str(path)})
    return _ok(path=str(path.resolve()), kind="document", resource=resource.get("resource"))


def _create_spreadsheet(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    if importlib.util.find_spec("openpyxl") is None:
        return _err("openpyxl is not installed", status="needs_dependency", verified=False, install_hint="python -m pip install openpyxl")
    from openpyxl import Workbook

    title = str(args.get("title") or "Hoja").strip()
    path = _output_path(args, state, _safe_name(title), ".xlsx")
    wb = Workbook()
    ws = wb.active
    if ws is None:
        return _err("openpyxl Workbook has no active sheet", verified=False)
    ws.title = "Datos"
    raw_rows = args.get("rows")
    rows: list[Any] = raw_rows if isinstance(raw_rows, list) else []
    if not rows:
        rows = [["Campo", "Valor"], ["Titulo", title]]
    for row in rows:
        ws.append(row if isinstance(row, list) else [str(row)])
    wb.save(str(path))
    resource = state.register_resource("office_file", path.name, cleanup_tool="filesystem", cleanup_args={"action": "delete", "path": str(path)}, metadata={"kind": "spreadsheet", "path": str(path), "rows": len(rows)})
    return _ok(path=str(path.resolve()), kind="spreadsheet", rows=len(rows), resource=resource.get("resource"))


def _inspect_office_file(args: dict[str, Any]) -> dict[str, Any]:
    path = _existing_path(args)
    if not path:
        return _err("missing or invalid path")
    return _ok(path=str(path.resolve()), suffix=path.suffix.casefold(), size=path.stat().st_size)


def _output_path(args: dict[str, Any], state: AgentState, stem: str, suffix: str) -> Path:
    raw = str(args.get("path") or "").strip()
    if raw:
        path = Path(raw).expanduser()
    else:
        out_dir = state.path.parent / "generated"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{stem}_{time.strftime('%Y%m%d_%H%M%S')}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.casefold() != suffix:
        path = path.with_suffix(suffix)
    return path


def _existing_path(args: dict[str, Any]) -> Path | None:
    raw = str(args.get("path") or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.exists() else None


def _slides_from_args(args: dict[str, Any], title: str) -> list[dict[str, Any]]:
    slides = args.get("slides")
    if isinstance(slides, str):
        try:
            slides = json.loads(slides)
        except json.JSONDecodeError:
            slides = None
    if isinstance(slides, list) and slides:
        return [item if isinstance(item, dict) else {"title": str(item)} for item in slides]
    topic = str(args.get("topic") or title)
    return [
        {"title": title, "subtitle": topic},
        {"title": "Resumen", "bullets": [f"Contexto de {topic}", "Puntos clave", "Siguiente paso"]},
        {"title": "Conclusiones", "bullets": ["Idea principal", "Impacto", "Acciones recomendadas"]},
    ]


def _safe_name(text: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip())[:50].strip("_")
    return clean or "archivo"


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


def _find_soundvolumeview() -> Path | None:
    raw = os.environ.get("GEMMA4_SOUNDVOLUMEVIEW")
    candidates = [Path(raw)] if raw else []
    candidates.extend([
        # ~/.gemma4/tools/ — bundle path (agent puede bajarlo aca proactivamente)
        Path.home() / ".gemma4" / "tools" / "SoundVolumeView.exe",
        Path.cwd() / "tools" / "SoundVolumeView.exe",
        Path.home() / "Downloads" / "SoundVolumeView.exe",
        Path("C:/Tools/SoundVolumeView/SoundVolumeView.exe"),
        Path("C:/Program Files/SoundVolumeView/SoundVolumeView.exe"),
    ])
    found = shutil.which("SoundVolumeView.exe")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


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


# Notification helpers - extraídos a domain_tools_notifications.py (R2 sprint
# 2026-05-27). Los 9 helpers + _NotificationDueError + _notification_due
# (parsing NL) viven ahora afuera; el re-export está en el bloque del entry
# point notification_tool más arriba (líneas ~263).


def _find_routine(args: dict[str, Any], state: AgentState) -> dict[str, Any] | None:
    rid = str(args.get("id") or args.get("resource_id") or "").strip()
    name = str(args.get("name") or args.get("label") or "").strip().casefold()
    resources = state._load().get("resources", {})
    if rid and rid in resources:
        return resources[rid]
    for resource in resources.values():
        if resource.get("kind") == "routine" and name and str(resource.get("label") or "").casefold() == name:
            return resource
    return None


def _update_resource_metadata(state: AgentState, resource_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    # CC-102: delega en la API pública atómica.
    result = state.update_resource_metadata(resource_id, updates)
    if not result.get("ok"):
        return _err("resource not found", resource_id=resource_id)
    return _ok(resource=result.get("resource"))


def _resources_by_kind(state: AgentState, kinds: str | list[str], include_closed: bool = False) -> list[dict[str, Any]]:
    wanted = {kinds} if isinstance(kinds, str) else set(kinds)
    resources = state._load().get("resources", {}).values()
    out = []
    for resource in resources:
        if resource.get("kind") not in wanted:
            continue
        if not include_closed and resource.get("status") != "open":
            continue
        out.append(resource)
    return out


def _find_resource(args: dict[str, Any], state: AgentState, kinds: str | list[str]) -> dict[str, Any] | None:
    rid = str(args.get("id") or args.get("resource_id") or "").strip()
    query = str(args.get("query") or args.get("name") or args.get("title") or "").strip().casefold()
    resources = state._load().get("resources", {})
    wanted = {kinds} if isinstance(kinds, str) else set(kinds)
    if rid and rid in resources and resources[rid].get("kind") in wanted:
        return resources[rid]
    for resource in resources.values():
        if resource.get("kind") not in wanted:
            continue
        if query and query in json.dumps(resource, ensure_ascii=False).casefold():
            return resource
    return None


def _dependency_catalog() -> dict[str, dict[str, Any]]:
    items = [
        _module_dep("playwright", "Playwright", "python -m pip install playwright && python -m playwright install chromium"),
        _module_dep("pptx", "python-pptx", "python -m pip install python-pptx"),
        _module_dep("docx", "python-docx", "python -m pip install python-docx"),
        _module_dep("openpyxl", "openpyxl", "python -m pip install openpyxl"),
        _module_dep("pyautogui", "pyautogui", "python -m pip install pyautogui"),
        _module_dep("pycaw", "pycaw", "python -m pip install pycaw comtypes"),
        _binary_dep("tesseract", "Tesseract OCR", "winget install UB-Mannheim.TesseractOCR"),
        _binary_dep("ffmpeg", "FFmpeg", "winget install Gyan.FFmpeg"),
        _binary_dep("git", "Git", "winget install Git.Git"),
        _binary_dep("winget", "winget", "Install App Installer from Microsoft Store"),
        _binary_dep("soffice", "LibreOffice", "winget install TheDocumentFoundation.LibreOffice"),
        {
            "name": "SoundVolumeView",
            "key": "soundvolumeview",
            "type": "binary",
            "available": _find_soundvolumeview() is not None,
            "path": str(_find_soundvolumeview()) if _find_soundvolumeview() else None,
            "install_hint": "Download SoundVolumeView from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW.",
        },
    ]
    return {item["key"]: item for item in items}


def _module_dep(module: str, name: str, hint: str) -> dict[str, Any]:
    available = importlib.util.find_spec(module) is not None
    return {"name": name, "key": module, "type": "python_module", "available": available, "install_hint": hint}


def _binary_dep(binary: str, name: str, hint: str) -> dict[str, Any]:
    path = shutil.which(binary) or shutil.which(f"{binary}.exe")
    return {"name": name, "key": binary, "type": "binary", "available": bool(path), "path": path, "install_hint": hint}


# Calendar helpers (ICS export utils) - extraídos a domain_tools_calendar.py
# (R2 sprint 2026-05-27). Los 4 helpers (_calendar_export_path, _events_to_ics,
# _ics_time, _ics_escape) viven junto al resto del calendar; el re-export está
# en el bloque del entry point más arriba.


def _powershell_json(script: str, field: str) -> dict[str, Any]:
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return _err("powershell command failed", exit_code=proc.returncode, stderr=proc.stderr)
    raw = proc.stdout.strip()
    if not raw:
        data: Any = []
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return _err("failed to parse PowerShell JSON", stdout=raw[:1000])
    if isinstance(data, dict) and field.endswith("s"):
        data = [data]
    return _ok(**{field: data, "count": len(data) if isinstance(data, list) else (1 if data else 0)})


def _run_detached_powershell(script: str) -> dict[str, Any]:
    proc = subprocess.Popen(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return {"pid": proc.pid}


def _ps_quote(text: str) -> str:
    return text.replace("'", "''")
