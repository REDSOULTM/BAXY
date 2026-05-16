"""Higher-level local domain tools for the Gemma4 agent."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import time
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


def _ok(**kwargs: Any) -> dict[str, Any]:
    return {"ok": True, **kwargs}


def _err(message: str, **kwargs: Any) -> dict[str, Any]:
    return {"ok": False, "error": message, **kwargs}


_SENSITIVE_KEY_RX = re.compile(r"(password|token|key|secret|api[_-]?key|auth)", re.IGNORECASE)


def _redact_credentials(value: Any, depth: int = 0) -> Any:
    """CC-105: paralelo a tools._redact_sensitive. Redacta keys sensibles
    recursivamente hasta profundidad 6."""
    if depth > 6:
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and _SENSITIVE_KEY_RX.search(k):
                out[k] = "***REDACTED***" if v not in (None, "") else v
            else:
                out[k] = _redact_credentials(v, depth + 1)
        return out
    if isinstance(value, list):
        return [_redact_credentials(v, depth + 1) for v in value]
    return value


def _hard_gate(
    state: AgentState,
    *,
    tool: str,
    action: str,
    args: dict[str, Any],
    reason: str,
    risk: str = "high",
) -> dict[str, Any] | None:
    """CC-101: gate duro replicable desde domain_tools (sin ToolRegistry).

    Devuelve None si la llamada está autorizada; un dict needs_confirmation
    si no. Respeta routine_context + confirmed_at_create como opt-out.
    """
    if bool(args.get("confirmed")):
        return None
    if bool(args.get("routine_context")):
        if bool(args.get("confirmed_at_create")):
            return None
        return _err(
            f"{tool}.{action} blocked: routine step missing confirmed_at_create",
            status="blocked_needs_confirmation",
            tool=tool,
            action=action,
        )
    safe_args = _redact_credentials(
        {**{k: v for k, v in args.items() if k not in {"routine_context", "confirmed_at_create"}}, "confirmed": True}
    )
    pending = state.create_confirmation(tool, safe_args, reason=reason, risk=risk)
    return _err(
        f"{tool}.{action} requires confirmation; call safety(confirm, id=...) or re-call with confirmed=true",
        status="needs_confirmation",
        verified=False,
        completion_status="needs_user_confirmation",
        confirmation=pending.get("confirmation"),
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


def notification_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(windows=True, scheduled_tasks=shutil.which("powershell") is not None, backend="windows_scheduled_tasks")
    if action == "history":
        return _notification_history(args, state)
    if action in {"list", "timer_list", "alarm_list", "reminder_list"}:
        resources = state.list_resources(include_closed=bool(args.get("include_closed", True))).get("resources", [])
        items = [r for r in resources if r.get("kind") in {"notification", "timer", "alarm", "local_reminder"}]
        if action != "list":
            kind = _kind_for_notification_action(action)
            items = [r for r in items if r.get("kind") == kind]
        # Enrich with live ScheduledTask info when available.
        enriched = [_enrich_notification_resource(item) for item in items]
        return _ok(items=enriched, count=len(enriched))
    if action in {"toast_now", "notify_sound"}:
        title = str(args.get("title") or "Gemma4 Agent").strip()
        text = str(args.get("text") or args.get("message") or title).strip()
        result = _show_message_box(title, text)
        return _ok(title=title, text=text, attempted=True, verified=False, result=result, completion_status="notification_requested")
    if action in {"timer_start", "alarm_create", "reminder_create", "toast_schedule"}:
        return _schedule_notification(args, state, kind=_kind_for_notification_action(action))
    if action in {"timer_cancel", "alarm_cancel", "reminder_delete", "delete"}:
        return _delete_notification(args, state)
    if action == "reminder_update":
        return _update_notification(args, state, kind="local_reminder")
    if action in {"timer_update", "alarm_update", "notification_update"}:
        return _update_notification(args, state, kind=_kind_for_notification_action(action.replace("_update", "")))
    return _err(
        "unknown notification action", action=action,
        valid_actions=[
            "status", "history", "list", "timer_list", "alarm_list", "reminder_list",
            "toast_now", "notify_sound", "timer_start", "alarm_create",
            "reminder_create", "toast_schedule", "timer_cancel", "alarm_cancel",
            "reminder_delete", "delete", "reminder_update", "timer_update",
            "alarm_update", "notification_update",
        ],
        status="needs_user",
    )


# Commands that imply destructive or system-altering side effects. If a
# TriggerCMD entry's command matches one of these tokens (case-insensitive,
# word-boundary), the imported routine is created with enabled=false and the
# report flags it. The user must explicitly call routine(action="enable").
# This is conservative on purpose: a few false positives are acceptable when
# the alternative is accidental shutdowns.
_DESTRUCTIVE_COMMAND_TOKENS = (
    "shutdown",      # /s, /r, /h
    "reboot",
    "logoff",
    "format",        # format C:
    "diskpart",
    "rmdir /s",
    "rd /s",
    "del /q",
    "del /f",
    "erase /q",
    "erase /f",
    "cipher /w",
    "powercfg /h off",
    "wmic os reboot",
    "wmic os shutdown",
    "stop-computer",
    "restart-computer",
    "remove-item",   # PowerShell rm -rf
    "uninstall",
)


def _looks_destructive(command: str) -> tuple[bool, list[str]]:
    """Return (is_destructive, matched_tokens) for a command line.

    T3-routine-looks-destructive-broken-cond-030: el primer loop legacy
    simplificaba a `needle in low` y duplicaba el chequeo word-boundary
    de abajo. Removido; sólo queda la versión regex word-boundary.
    """
    matches = [
        t for t in _DESTRUCTIVE_COMMAND_TOKENS
        if re.search(r"\b" + re.escape(t) + r"\b", command, re.IGNORECASE)
    ]
    matches = sorted(set(matches))
    return bool(matches), matches


def import_triggercmd_entries(
    entries: list[dict[str, Any]],
    state: AgentState,
    *,
    overwrite_same_phrase: bool = False,
    auto_disable_destructive: bool = True,
) -> dict[str, Any]:
    """Convert a TriggerCMD commands.json into Gemma4 on_phrase routines.

    Mapping:
      voice    -> trigger.phrase
      command  -> step terminal(command=<command>)
      ground   -> shell=true (foreground/background both run via shell)
      offCommand -> a second on_phrase routine named '<voice> off' that
                    fires when the user says e.g. 'apaga modo cine'.

    Entries with allowParams=true are SKIPPED with reason in the report
    (per user decision: parametrized routines are manual for now).
    Entries with missing/empty voice or command are skipped with reason.

    The function is pure-ish: it only writes to state via routine_tool
    create calls. Returns a structured report so the caller can display
    what worked and what didn't.
    """
    import json as _json
    if not isinstance(entries, list):
        return _err("triggercmd payload must be a list of entries")
    existing_phrases: set[str] = set()
    if not overwrite_same_phrase:
        for r in active_phrase_triggers(state):
            existing_phrases.add(str(r.get("phrase") or "").casefold())

    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            skipped.append({"index": index, "reason": "not_an_object"})
            continue
        trigger_name = str(entry.get("trigger") or "").strip()
        voice = str(entry.get("voice") or "").strip()
        command = str(entry.get("command") or "").strip()
        off_command = str(entry.get("offCommand") or "").strip()
        ground = str(entry.get("ground") or "foreground").strip().casefold()
        # Skip rules.
        if not command:
            skipped.append({"index": index, "trigger": trigger_name, "reason": "empty_command"})
            continue
        if not voice:
            skipped.append({"index": index, "trigger": trigger_name, "reason": "empty_voice"})
            continue
        if len(voice) < 3:
            skipped.append({"index": index, "trigger": trigger_name, "voice": voice, "reason": "voice_too_short"})
            continue
        allow_params = str(entry.get("allowParams") or "").strip().casefold()
        if allow_params in {"true", "1", "yes"}:
            skipped.append({
                "index": index,
                "trigger": trigger_name,
                "voice": voice,
                "reason": "allowParams_true_needs_manual_setup",
                "note": "Parametrized commands (e.g. 'Netflix Stranger Things') must be created by hand for now.",
            })
            continue
        if not overwrite_same_phrase and voice.casefold() in existing_phrases:
            skipped.append({"index": index, "trigger": trigger_name, "voice": voice, "reason": "phrase_already_in_use"})
            continue
        existing_phrases.add(voice.casefold())

        # Safety layer: detect destructive commands and import them disabled
        # by default. User must explicitly call routine(action="enable").
        destructive_on, dangerous_tokens_on = _looks_destructive(command)
        enabled_on = not (auto_disable_destructive and destructive_on)

        # ON routine: voice -> command.
        on_label = trigger_name or f"triggercmd_{index}"
        on_payload = {
            "action": "create",
            "name": on_label,
            "trigger": {"type": "on_phrase", "phrase": voice},
            "steps": [{"tool": "terminal", "args": _terminal_args_for(command, ground)}],
            "enabled": enabled_on,
        }
        on_result = routine_tool(on_payload, state, executor=None)
        if not on_result.get("ok"):
            skipped.append({"index": index, "trigger": trigger_name, "reason": "create_failed", "error": on_result.get("error")})
            continue
        report_item: dict[str, Any] = {
            "trigger": trigger_name,
            "phrase": voice,
            "routine_id": (on_result.get("routine") or {}).get("id"),
            "command": command,
            "ground": ground,
            "enabled": enabled_on,
        }
        if destructive_on:
            report_item["destructive_tokens"] = dangerous_tokens_on
            report_item["note"] = (
                "Imported DISABLED because the command looks destructive "
                f"(matched: {', '.join(dangerous_tokens_on)}). Enable with "
                f"routine(action='enable', id='{report_item['routine_id']}') only when sure."
            )

        # OFF routine: only if offCommand is set. Phrase is "<voice> off" by
        # default; the user can rename later if they want a different keyword.
        if off_command:
            off_voice = f"{voice} off"
            if not overwrite_same_phrase and off_voice.casefold() in existing_phrases:
                report_item["off_skipped"] = "phrase_already_in_use"
            else:
                existing_phrases.add(off_voice.casefold())
                off_label = f"{on_label} (off)"
                destructive_off, dangerous_tokens_off = _looks_destructive(off_command)
                enabled_off = not (auto_disable_destructive and destructive_off)
                off_payload = {
                    "action": "create",
                    "name": off_label,
                    "trigger": {"type": "on_phrase", "phrase": off_voice},
                    "steps": [{"tool": "terminal", "args": _terminal_args_for(off_command, ground)}],
                    "enabled": enabled_off,
                }
                off_result = routine_tool(off_payload, state, executor=None)
                if off_result.get("ok"):
                    report_item["off_routine_id"] = (off_result.get("routine") or {}).get("id")
                    report_item["off_phrase"] = off_voice
                    report_item["off_enabled"] = enabled_off
                    if destructive_off:
                        report_item["off_destructive_tokens"] = dangerous_tokens_off
                else:
                    report_item["off_skipped"] = f"create_failed: {off_result.get('error')}"

        imported.append(report_item)

    return _ok(
        imported=imported,
        imported_count=len(imported),
        skipped=skipped,
        skipped_count=len(skipped),
        total_input=len(entries),
        note="Run routine(action='list') to see all routines. Disable with routine(action='disable', id=...) or delete with routine(action='delete', id=...).",
    )


def _terminal_args_for(command: str, ground: str) -> dict[str, Any]:
    """Build the terminal tool args for a TriggerCMD command line.

    TriggerCMD commands are full Windows command lines with quoted paths
    (e.g. `"C:\\TriggerCMD Comandos\\Volumen.ahk" 50`). We pass them as a
    single shell command with shell=True so cmd.exe handles the quoting.
    background ground means we don't wait for completion; we model that
    with a short timeout (1s) since the terminal tool always runs sync.
    """
    if ground == "background":
        return {"command": command, "shell": True, "timeout_sec": 5}
    return {"command": command, "shell": True, "timeout_sec": 60}


def routine_tool(args: dict[str, Any], state: AgentState, executor: Executor | None = None) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(
            local_state=True,
            run_now=bool(executor),
            triggers=["manual", "cron", "once", "on_app_open", "on_app_close", "on_process_start", "on_process_exit", "on_phrase"],
            persistent_triggers=True,
            backend="windows_scheduled_tasks + watcher poll + chat phrase hook",
            deferred_triggers=["on_file_change", "on_network_event"],
            deferred_reason="File change triggers belong to the watcher tool directly; network events need ETW subscription.",
            on_phrase_note="on_phrase routines fire when the user message contains the configured phrase (case-insensitive, accents folded). The agent confirms the action briefly after firing.",
            import_sources=["triggercmd"],
            import_note="Use routine(action='import', source='triggercmd', json_path='<file>') or entries=[...] to bulk-create on_phrase routines from a TriggerCMD export. allowParams=true entries are skipped for manual setup.",
        )
    if action == "list":
        resources = state.list_resources(include_closed=bool(args.get("include_closed", False))).get("resources", [])
        routines = [_enrich_routine_resource(r) for r in resources if r.get("kind") == "routine"]
        return _ok(routines=routines, count=len(routines))
    if action == "import":
        source = str(args.get("source") or "triggercmd").strip().casefold()
        if source != "triggercmd":
            return _err(f"import source '{source}' not supported; only triggercmd for now")
        # Accept either a path to the JSON file or an inline `entries` array.
        raw_entries = args.get("entries")
        json_path = str(args.get("json_path") or args.get("path") or "").strip()
        if not raw_entries and not json_path:
            return _err("routine.import requires either entries=[...] or json_path='<file>.json'")
        if raw_entries is None and json_path:
            p = Path(json_path).expanduser()
            if not p.is_file():
                return _err(f"json_path does not exist: {p}")
            try:
                raw_entries = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                return _err(f"invalid JSON at {p}: {exc}")
        if isinstance(raw_entries, str):
            try:
                raw_entries = json.loads(raw_entries)
            except json.JSONDecodeError as exc:
                return _err(f"entries string is not valid JSON: {exc}")
        if not isinstance(raw_entries, list):
            return _err("triggercmd entries must be a JSON array")
        return import_triggercmd_entries(
            raw_entries,
            state,
            overwrite_same_phrase=bool(args.get("overwrite_same_phrase", False)),
        )
    if action == "create":
        steps = args.get("steps") or []
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except json.JSONDecodeError:
                return _err("steps must be a JSON array of {tool,args}")
        if not isinstance(steps, list) or not steps:
            return _err("routine.create requires steps array")
        # Validate each step
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                return _err(f"step {index} is not an object", step=step)
            if not str(step.get("tool") or "").strip():
                return _err(f"step {index} has no tool", step=step)
            if str(step.get("tool")).strip() == "routine":
                return _err(f"step {index} cannot call routine recursively")
        label = str(args.get("name") or args.get("label") or f"Routine {int(time.time())}")
        raw_trigger = args.get("trigger")
        trigger: dict[str, Any] = (
            raw_trigger if isinstance(raw_trigger, dict)
            else {"type": str(raw_trigger or "manual")}
        )
        trigger_type = str(trigger.get("type") or "manual").casefold()
        process_triggers = {"on_app_open", "on_app_close", "on_process_start", "on_process_exit"}
        phrase_triggers = {"on_phrase", "on_keyword"}
        if trigger_type not in {"manual", "cron", "once"} | process_triggers | phrase_triggers:
            return _err(
                f"trigger type '{trigger_type}' is not implemented yet; supported: manual, cron, once, on_app_open, on_app_close, on_phrase",
                status="needs_implementation",
                deferred=trigger_type,
            )
        # Validate on_phrase config eagerly so a bad routine doesn't slip into state.
        if trigger_type in phrase_triggers:
            phrase = str(trigger.get("phrase") or trigger.get("keyword") or "").strip()
            if not phrase:
                return _err(f"trigger '{trigger_type}' requires phrase=<text>")
            if len(phrase) < 3:
                return _err("on_phrase requires a phrase of at least 3 chars to avoid spurious matches")
        task_name = None
        watcher_id = None
        if trigger_type in {"cron", "once"}:
            task_name = _routine_task_name(label)
            register = _register_routine_scheduled_task(task_name, label, trigger)
            if not register.get("ok"):
                return register
        elif trigger_type in process_triggers:
            process_name = str(trigger.get("process") or trigger.get("app") or "").strip()
            if not process_name:
                return _err(f"trigger '{trigger_type}' requires process=<exe-name>")
            # We register the routine first (below) then attach a watcher that
            # polls process state and fires routine.run_now on the right edge.
            # The watcher_id is patched into metadata after both exist.
        resource = state.register_resource(
            "routine",
            label,
            cleanup_tool="routine",
            cleanup_args={"action": "delete", "name": label},
            metadata={
                "enabled": bool(args.get("enabled", True)),
                "trigger": trigger,
                "trigger_type": trigger_type,
                "task_name": task_name,
                "watcher_id": None,
                "steps": steps,
            },
        )
        # Attach a process watcher for on_app_open/on_app_close.
        if trigger_type in process_triggers:
            process_name = str(trigger.get("process") or trigger.get("app") or "").strip()
            interval = int(trigger.get("interval_minutes", 2)) * 60
            routine_id = resource.get("resource", {}).get("id")
            edge = "rising" if trigger_type in {"on_app_open", "on_process_start"} else "falling"
            watcher_result = _register_routine_process_watcher(state, label, routine_id, process_name, interval, edge)
            if not watcher_result.get("ok"):
                return watcher_result
            watcher_id = watcher_result.get("watcher_id")
            # CC-102: usa API pública atómica.
            state.update_resource_metadata(routine_id, {"watcher_id": watcher_id})
        return _ok(routine=resource.get("resource"), trigger=trigger, task_name=task_name, watcher_id=watcher_id, status="done")
    if action == "run_now":
        routine = _find_routine(args, state)
        if not routine:
            return _err("routine not found")
        if not executor:
            return _err("routine.run_now requires an executor wired by the registry", status="needs_implementation", verified=False)
        if routine.get("metadata", {}).get("enabled") is False:
            return _err("routine is disabled", routine=routine)
        results = []
        steps = routine.get("metadata", {}).get("steps") or []
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                results.append({"index": index, "ok": False, "error": "invalid step"})
                break
            tool = str(step.get("tool") or "").strip()
            raw_args = step.get("args")
            step_args: dict[str, Any] = raw_args if isinstance(raw_args, dict) else {}
            if not tool or tool == "routine":
                results.append({"index": index, "ok": False, "error": "invalid or recursive tool", "tool": tool})
                break
            result = executor(tool, step_args)
            results.append({"index": index, "tool": tool, "args": step_args, "result": result, "ok": bool(result.get("ok"))})
            if not result.get("ok"):
                break
        completed = bool(results) and all(item.get("ok") for item in results)
        run_record = {
            "ran_at": datetime.now().isoformat(),
            "steps_total": len(steps),
            "steps_executed": len(results),
            "completed": completed,
            "results": results,
        }
        _append_routine_run(state, str(routine["id"]), run_record)
        return _ok(routine=routine, results=results, completed=completed, run=run_record)
    if action in {"delete", "enable", "disable"}:
        routine = _find_routine(args, state)
        if not routine:
            return _err("routine not found")
        if action == "delete":
            metadata_r = routine.get("metadata") or {}
            task_name = str(metadata_r.get("task_name") or "").strip()
            if task_name:
                _unregister_routine_scheduled_task(task_name)
            # Tear down attached watcher too.
            watcher_id = str(metadata_r.get("watcher_id") or "").strip()
            if watcher_id:
                data = state._load()
                w = data.get("resources", {}).get(watcher_id)
                if w:
                    w_task = str((w.get("metadata") or {}).get("task_name") or "").strip()
                    if w_task:
                        _unregister_routine_scheduled_task(w_task)
                    state.mark_cleaned(watcher_id, {"deleted_via": "routine cleanup"})
            return state.mark_cleaned(str(routine["id"]), {"deleted": True})
        enabled = action == "enable"
        return _update_resource_metadata(state, str(routine["id"]), {"enabled": enabled})
    if action == "history":
        routine = _find_routine(args, state) if (args.get("id") or args.get("name")) else None
        return _routine_history(state, routine, limit=int(args.get("limit", 20)))
    if action == "simulate":
        routine = _find_routine(args, state)
        if not routine:
            return _err("routine not found")
        steps = routine.get("metadata", {}).get("steps") or []
        return _ok(routine=routine, would_run=[{"tool": s.get("tool"), "args": s.get("args")} for s in steps if isinstance(s, dict)], step_count=len(steps), note="dry-run; nothing was executed")
    return _err(
        "unknown routine action", action=action,
        valid_actions=[
            "status", "create", "list", "enable", "disable", "run_now",
            "delete", "import_triggercmd", "logs",
        ],
        status="needs_user",
    )


def smart_home_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for local smart home control (Home Assistant + MQTT).

    Actions: status, discover, get_state, set_state, call_service, scene_run,
    area_list, area_control, mqtt_publish. All endpoints are LOCAL HTTP to
    your Home Assistant install; auth is a long-lived access token via
    GEMMA4_HASS_TOKEN env var. mqtt_publish requires paho-mqtt installed.
    """
    action = str(args.get("action") or "status").casefold()
    host = str(args.get("host") or os.environ.get("GEMMA4_HASS_HOST") or "http://homeassistant.local:8123").rstrip("/")
    token = str(args.get("token") or os.environ.get("GEMMA4_HASS_TOKEN") or "").strip()
    alive = _hass_alive(host)
    if action == "status":
        try:
            mqtt_available = importlib.util.find_spec("paho") is not None
        except (ImportError, ValueError, ModuleNotFoundError):
            mqtt_available = False
        return _ok(
            home_assistant=bool(alive),
            host=host,
            has_token=bool(token),
            mqtt_available=mqtt_available,
            note="Set GEMMA4_HASS_HOST and GEMMA4_HASS_TOKEN (long-lived access token from /profile in your HA UI).",
        )
    if not alive:
        return _err(
            f"Home Assistant is not reachable at {host}",
            status="needs_user", verified=False,
            completion_status="needs_home_assistant_running",
            note="Set GEMMA4_HASS_HOST to the URL your HA instance listens on (default http://homeassistant.local:8123).",
        )
    if action == "mqtt_publish":
        return _smart_home_mqtt_publish(args)
    if not token:
        return _err(
            "Home Assistant requires a long-lived access token",
            status="needs_user",
            completion_status="needs_user_auth",
            required_env="GEMMA4_HASS_TOKEN",
            note="Create one in the HA UI > your profile > Long-Lived Access Tokens.",
        )
    if action in {"discover", "states"}:
        return _hass_states(host, token, args)
    if action == "get_state":
        return _hass_get_state(host, token, args)
    if action == "set_state":
        return _hass_set_state(host, token, args, state)
    if action == "call_service":
        return _hass_call_service(host, token, args, state)
    if action == "scene_run":
        scene = str(args.get("scene") or args.get("entity_id") or "").strip()
        if not scene:
            return _err("scene_run requires scene= or entity_id=")
        return _hass_call_service(host, token, {"domain": "scene", "service": "turn_on", "data": {"entity_id": scene}}, state)
    if action in {"area_list", "areas"}:
        return _hass_area_list(host, token)
    if action == "area_control":
        return _hass_area_control(host, token, args, state)
    return _err(
        "unknown smart_home action", action=action,
        valid_actions=[
            "status", "discover", "states", "service_call", "mqtt_publish",
            "automation_trigger",
        ],
        status="needs_user",
    )


def _hass_alive(host: str) -> bool:
    # T3-smart_home-alive-always-true-031: distingue HTTPError (servidor vivo
    # con 401/403) de URLError/timeout (servidor caído).
    import urllib.error
    import urllib.request
    try:
        req = urllib.request.Request(f"{host}/api/", headers={"User-Agent": "Gemma4Agent/1.0"})
        with urllib.request.urlopen(req, timeout=2.0):
            return True
    except urllib.error.HTTPError as exc:
        # Cualquier HTTP code legítimo significa que HA responde.
        return exc.code in (200, 401, 403, 404)
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _hass_request(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    import urllib.request
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "Gemma4Agent/1.0"}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            try:
                return {"_ok": True, "_status": resp.status, "data": json.loads(body) if body else None}
            except json.JSONDecodeError:
                return {"_ok": True, "_status": resp.status, "data": body.decode("utf-8", errors="replace")}
    except Exception as exc:
        return {"_ok": False, "_error": str(exc)}


def _hass_states(host: str, token: str, args: dict[str, Any]) -> dict[str, Any]:
    resp = _hass_request("GET", f"{host}/api/states", token)
    if not resp.get("_ok"):
        return _err(f"GET /api/states failed: {resp.get('_error')}")
    states = resp.get("data") or []
    domain_filter = str(args.get("domain") or "").casefold()
    if domain_filter:
        states = [s for s in states if str(s.get("entity_id", "")).split(".", 1)[0].casefold() == domain_filter]
    limit = int(args.get("limit", 500))
    return _ok(count=len(states), states=states[:limit], domain_filter=domain_filter or None)


def _hass_get_state(host: str, token: str, args: dict[str, Any]) -> dict[str, Any]:
    entity_id = str(args.get("entity_id") or "").strip()
    if not entity_id:
        return _err("missing entity_id")
    resp = _hass_request("GET", f"{host}/api/states/{entity_id}", token)
    if not resp.get("_ok"):
        return _err(f"GET state failed: {resp.get('_error')}", entity_id=entity_id)
    return _ok(entity_id=entity_id, state=resp.get("data"))


def _hass_set_state(host: str, token: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    entity_id = str(args.get("entity_id") or "").strip()
    new_state = args.get("state")
    if not entity_id or new_state is None:
        return _err("set_state requires entity_id and state")
    # Snapshot the previous state for rollback.
    before = _hass_get_state(host, token, {"entity_id": entity_id}).get("state") or {}
    payload = {"state": str(new_state), "attributes": args.get("attributes") if isinstance(args.get("attributes"), dict) else {}}
    checkpoint = state.checkpoint(
        f"smart_home set_state {entity_id}",
        rollback=[{"tool": "smart_home", "args": {"action": "set_state", "entity_id": entity_id, "state": before.get("state"), "attributes": before.get("attributes")}}] if before.get("state") is not None else [],
        metadata={"before": before, "target": payload},
    )
    resp = _hass_request("POST", f"{host}/api/states/{entity_id}", token, payload)
    if not resp.get("_ok"):
        return _err(f"set_state failed: {resp.get('_error')}", entity_id=entity_id, checkpoint=checkpoint.get("checkpoint"))
    return _ok(entity_id=entity_id, before=before, after=resp.get("data"), checkpoint=checkpoint.get("checkpoint"), verified=True)


def _hass_call_service(host: str, token: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    domain = str(args.get("domain") or "").strip()
    service = str(args.get("service") or "").strip()
    if not domain or not service:
        return _err("call_service requires domain and service")
    raw_payload = args.get("data")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    # Merge target into payload (HA accepts entity_id at top-level).
    raw_target = args.get("target")
    target: dict[str, Any] | None = raw_target if isinstance(raw_target, dict) else None
    if target:
        payload = {**payload, **target}
    # For toggle/turn_off/turn_on on a switch/light, snapshot before so rollback exists.
    rollback_step = None
    if service in {"turn_on", "turn_off", "toggle"} and payload.get("entity_id"):
        eid_raw = payload["entity_id"]
        eid = eid_raw if isinstance(eid_raw, str) else (eid_raw[0] if eid_raw else None)
        if eid:
            current = _hass_get_state(host, token, {"entity_id": eid}).get("state") or {}
            if current.get("state") == "on" and service == "turn_off":
                rollback_step = {"tool": "smart_home", "args": {"action": "call_service", "domain": domain, "service": "turn_on", "data": {"entity_id": eid}}}
            elif current.get("state") == "off" and service == "turn_on":
                rollback_step = {"tool": "smart_home", "args": {"action": "call_service", "domain": domain, "service": "turn_off", "data": {"entity_id": eid}}}
    checkpoint = state.checkpoint(
        f"smart_home {domain}.{service}",
        rollback=[rollback_step] if rollback_step else [],
        metadata={"domain": domain, "service": service, "payload": payload},
    )
    resp = _hass_request("POST", f"{host}/api/services/{domain}/{service}", token, payload)
    if not resp.get("_ok"):
        return _err(f"call_service failed: {resp.get('_error')}", domain=domain, service=service)
    return _ok(domain=domain, service=service, payload=payload, response=resp.get("data"), checkpoint=checkpoint.get("checkpoint"), verified=True)


def _hass_area_list(host: str, token: str) -> dict[str, Any]:
    # Areas are exposed via the config endpoint; the WebSocket area_registry/list
    # is more complete, but a REST snapshot via /api/config + /api/states covers
    # the basics for naming.
    resp = _hass_request("GET", f"{host}/api/states", token)
    if not resp.get("_ok"):
        return _err(f"area_list failed: {resp.get('_error')}")
    states = resp.get("data") or []
    areas: dict[str, list[str]] = {}
    for s in states:
        area = (s.get("attributes") or {}).get("area_id") or (s.get("attributes") or {}).get("area") or ""
        if not area:
            continue
        areas.setdefault(str(area), []).append(s.get("entity_id"))
    return _ok(areas=[{"area_id": k, "entities": v, "count": len(v)} for k, v in areas.items()], count=len(areas), note="Areas read from entity attributes; for the full area_registry use the WebSocket API.")


def _hass_area_control(host: str, token: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    area = str(args.get("area") or args.get("area_id") or "").strip()
    service = str(args.get("service") or "turn_off").strip()
    if not area:
        return _err("missing area")
    area_info = _hass_area_list(host, token)
    matching = next((a for a in area_info.get("areas", []) if a.get("area_id") == area or area.casefold() in str(a.get("area_id") or "").casefold()), None)
    if not matching:
        return _err("area not found", area=area, available=[a["area_id"] for a in area_info.get("areas", [])])
    # Group by domain so we call e.g. light.turn_off once per area.
    results: list[dict[str, Any]] = []
    by_domain: dict[str, list[str]] = {}
    for entity in matching.get("entities", []):
        domain = str(entity).split(".", 1)[0]
        by_domain.setdefault(domain, []).append(entity)
    for domain, entities in by_domain.items():
        if domain not in {"light", "switch", "fan", "media_player", "climate", "cover", "vacuum"}:
            continue
        r = _hass_call_service(host, token, {"domain": domain, "service": service, "data": {"entity_id": entities}}, state)
        results.append({"domain": domain, "entities": entities, "result": {"ok": r.get("ok"), "error": r.get("error")}})
    return _ok(area=matching["area_id"], service=service, calls=results, verified=all(r["result"]["ok"] for r in results))


def _smart_home_mqtt_publish(args: dict[str, Any]) -> dict[str, Any]:
    if importlib.util.find_spec("paho.mqtt.client") is None:
        return _err(
            "paho-mqtt is not installed",
            status="needs_dependency",
            install_hint="python -m pip install paho-mqtt",
        )
    topic = str(args.get("topic") or "").strip()
    payload = args.get("payload")
    if not topic:
        return _err("missing topic")
    broker = str(args.get("broker") or os.environ.get("GEMMA4_MQTT_BROKER") or "127.0.0.1").strip()
    port = int(args.get("port", os.environ.get("GEMMA4_MQTT_PORT", 1883) or 1883))
    qos = int(args.get("qos", 0))
    retain = bool(args.get("retain", False))
    import paho.mqtt.client as mqtt  # type: ignore[import-not-found]
    client = mqtt.Client()
    user = os.environ.get("GEMMA4_MQTT_USER")
    pwd = os.environ.get("GEMMA4_MQTT_PASSWORD")
    if user:
        client.username_pw_set(user, pwd)
    try:
        client.connect(broker, port, keepalive=10)
    except Exception as exc:
        return _err(f"MQTT connect failed: {exc}", broker=broker, port=port)
    if isinstance(payload, (dict, list)):
        payload_str = json.dumps(payload)
    else:
        payload_str = str(payload) if payload is not None else ""
    info = client.publish(topic, payload_str, qos=qos, retain=retain)
    client.disconnect()
    return _ok(topic=topic, payload_bytes=len(payload_str), broker=f"{broker}:{port}", qos=qos, retain=retain, rc=info.rc, verified=info.rc == 0)


def study_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for local flashcards + SM-2 spaced repetition.

    Actions: status, deck_create, deck_list, deck_delete, card_add,
    card_list, card_delete, due, review (grade card with q in 0..5), stats.
    Storage: SQLite at <state_dir>/study.sqlite. SM-2 per Wozniak 1990.
    """
    action = str(args.get("action") or "status").casefold()
    db_path = state.path.parent / "study.sqlite"
    conn = _study_connect(db_path)
    try:
        if action == "status":
            cur = conn.cursor()
            decks = cur.execute("SELECT COUNT(*) FROM decks").fetchone()[0]
            cards = cur.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
            due_today = cur.execute("SELECT COUNT(*) FROM cards WHERE due_at <= ?", (_today_iso(),)).fetchone()[0]
            return _ok(db=str(db_path), decks=decks, cards=cards, due_today=due_today, algorithm="SM-2 (Wozniak 1990)")
        if action == "deck_create":
            return _study_deck_create(conn, args)
        if action == "deck_list":
            return _study_deck_list(conn)
        if action == "deck_delete":
            return _study_deck_delete(conn, args)
        if action == "card_add":
            return _study_card_add(conn, args)
        if action == "card_list":
            return _study_card_list(conn, args)
        if action == "card_delete":
            return _study_card_delete(conn, args)
        if action == "due":
            return _study_due(conn, args)
        if action == "review":
            return _study_review(conn, args)
        if action == "stats":
            return _study_stats(conn, args)
        return _err(
            "unknown study action", action=action,
            valid_actions=[
                "status", "deck_create", "deck_list", "deck_delete",
                "card_add", "card_list", "card_review", "card_delete",
                "due_cards", "stats",
            ],
            status="needs_user",
        )
    finally:
        conn.close()


def _study_connect(db_path: Path):
    import sqlite3
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS decks (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS cards (
            id TEXT PRIMARY KEY,
            deck_id TEXT NOT NULL,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            ef REAL NOT NULL DEFAULT 2.5,
            interval_days INTEGER NOT NULL DEFAULT 0,
            repetitions INTEGER NOT NULL DEFAULT 0,
            due_at TEXT NOT NULL,
            last_reviewed_at TEXT,
            last_grade INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(deck_id) REFERENCES decks(id)
        )"""
    )
    conn.commit()
    return conn


def _today_iso() -> str:
    return time.strftime("%Y-%m-%d")


def _study_deck_create(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("name") or "").strip()
    if not name:
        return _err("missing deck name")
    import uuid
    deck_id = f"deck_{uuid.uuid4().hex[:10]}"
    conn.execute("INSERT INTO decks(id, name, created_at) VALUES (?, ?, ?)", (deck_id, name, _today_iso()))
    conn.commit()
    return _ok(deck_id=deck_id, name=name)


def _study_deck_list(conn: Any) -> dict[str, Any]:
    rows = conn.execute("SELECT id, name, created_at FROM decks ORDER BY created_at DESC").fetchall()
    decks = []
    for row in rows:
        card_count = conn.execute("SELECT COUNT(*) FROM cards WHERE deck_id = ?", (row["id"],)).fetchone()[0]
        due_count = conn.execute("SELECT COUNT(*) FROM cards WHERE deck_id = ? AND due_at <= ?", (row["id"], _today_iso())).fetchone()[0]
        decks.append({"deck_id": row["id"], "name": row["name"], "created_at": row["created_at"], "cards": card_count, "due_today": due_count})
    return _ok(decks=decks, count=len(decks))


def _study_deck_delete(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    deck_id = str(args.get("deck_id") or args.get("id") or "").strip()
    if not deck_id:
        return _err("missing deck_id")
    conn.execute("DELETE FROM cards WHERE deck_id = ?", (deck_id,))
    cur = conn.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    conn.commit()
    return _ok(deck_id=deck_id, deleted=cur.rowcount)


def _study_card_add(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    deck_id = str(args.get("deck_id") or "").strip()
    front = str(args.get("front") or args.get("question") or "").strip()
    back = str(args.get("back") or args.get("answer") or "").strip()
    if not deck_id or not front or not back:
        return _err("card_add requires deck_id, front, back")
    if not conn.execute("SELECT id FROM decks WHERE id = ?", (deck_id,)).fetchone():
        return _err("deck not found", deck_id=deck_id)
    import uuid
    card_id = f"card_{uuid.uuid4().hex[:10]}"
    conn.execute(
        "INSERT INTO cards(id, deck_id, front, back, ef, interval_days, repetitions, due_at, created_at) VALUES (?, ?, ?, ?, 2.5, 0, 0, ?, ?)",
        (card_id, deck_id, front, back, _today_iso(), _today_iso()),
    )
    conn.commit()
    return _ok(card_id=card_id, deck_id=deck_id, front=front, back=back, due_at=_today_iso())


def _study_card_list(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    deck_id = str(args.get("deck_id") or "").strip()
    if deck_id:
        rows = conn.execute("SELECT id, deck_id, front, back, ef, interval_days, repetitions, due_at, last_grade FROM cards WHERE deck_id = ? ORDER BY due_at", (deck_id,)).fetchall()
    else:
        rows = conn.execute("SELECT id, deck_id, front, back, ef, interval_days, repetitions, due_at, last_grade FROM cards ORDER BY due_at LIMIT 500").fetchall()
    cards = [dict(row) for row in rows]
    return _ok(cards=cards, count=len(cards))


def _study_card_delete(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    card_id = str(args.get("card_id") or args.get("id") or "").strip()
    if not card_id:
        return _err("missing card_id")
    cur = conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    conn.commit()
    return _ok(card_id=card_id, deleted=cur.rowcount)


def _study_due(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    deck_id = str(args.get("deck_id") or "").strip()
    limit = int(args.get("limit", 20))
    if deck_id:
        rows = conn.execute("SELECT id, deck_id, front, back, ef, interval_days, repetitions, due_at FROM cards WHERE deck_id = ? AND due_at <= ? ORDER BY due_at LIMIT ?", (deck_id, _today_iso(), limit)).fetchall()
    else:
        rows = conn.execute("SELECT id, deck_id, front, back, ef, interval_days, repetitions, due_at FROM cards WHERE due_at <= ? ORDER BY due_at LIMIT ?", (_today_iso(), limit)).fetchall()
    return _ok(due_cards=[dict(row) for row in rows], count=len(rows), today=_today_iso())


def _study_review(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    """Apply SM-2 to a single card's grade q in 0..5."""
    card_id = str(args.get("card_id") or args.get("id") or "").strip()
    q = args.get("q") if args.get("q") is not None else args.get("grade")
    if not card_id or q is None:
        return _err("review requires card_id and q (0..5)")
    try:
        q = int(q)
    except (TypeError, ValueError):
        return _err("q must be an integer 0..5")
    if not (0 <= q <= 5):
        return _err("q out of range; must be 0..5")
    row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    if not row:
        return _err("card not found", card_id=card_id)
    ef = float(row["ef"])
    interval = int(row["interval_days"])
    repetitions = int(row["repetitions"])
    # SM-2 EF update happens regardless of q (per Wozniak 1990).
    ef = max(1.3, ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    if q < 3:
        repetitions = 0
        interval = 1
    else:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = max(1, round(interval * ef))
        repetitions += 1
    from datetime import datetime as _dt, timedelta as _td
    due_at = (_dt.today() + _td(days=interval)).strftime("%Y-%m-%d")
    conn.execute(
        "UPDATE cards SET ef = ?, interval_days = ?, repetitions = ?, due_at = ?, last_reviewed_at = ?, last_grade = ? WHERE id = ?",
        (ef, interval, repetitions, due_at, _today_iso(), q, card_id),
    )
    conn.commit()
    return _ok(card_id=card_id, q=q, ef=round(ef, 4), interval_days=interval, repetitions=repetitions, due_at=due_at)


def _study_stats(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    deck_id = str(args.get("deck_id") or "").strip()
    where_clause = "WHERE deck_id = ?" if deck_id else ""
    params: tuple[Any, ...] = (deck_id,) if deck_id else tuple()
    total = conn.execute(f"SELECT COUNT(*) FROM cards {where_clause}", params).fetchone()[0]
    due_today = conn.execute(f"SELECT COUNT(*) FROM cards {where_clause + (' AND ' if where_clause else 'WHERE ')}due_at <= ?", (*params, _today_iso())).fetchone()[0]
    avg_ef = conn.execute(f"SELECT AVG(ef) FROM cards {where_clause}", params).fetchone()[0] or 2.5
    new_cards = conn.execute(f"SELECT COUNT(*) FROM cards {where_clause + (' AND ' if where_clause else 'WHERE ')}repetitions = 0", params).fetchone()[0]
    return _ok(deck_id=deck_id or None, total=total, due_today=due_today, new=new_cards, avg_ef=round(float(avg_ef), 4))


def accessibility_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for Windows accessibility features.

    Actions: status, magnifier_start, magnifier_stop, narrator_start,
    narrator_stop, dictation_status, settings_panel. High Contrast toggle
    via registry is fragile and shows a Windows confirmation dialog; we
    instead point the user at the keyboard shortcut LAlt+LShift+PrtSc and
    expose settings_panel to open the Settings page.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            magnifier_running=_process_running("Magnify.exe"),
            narrator_running=_process_running("Narrator.exe"),
            note="High Contrast toggle is deferred (requires registry + WM_SETTINGCHANGE broadcast). Use action=settings_panel to open the Accessibility Settings instead.",
        )
    if action == "magnifier_start":
        return _accessibility_launch("magnify.exe", state, kind="magnifier")
    if action == "magnifier_stop":
        return _accessibility_kill("Magnify.exe", state, kind="magnifier")
    if action == "narrator_start":
        return _accessibility_launch("narrator.exe", state, kind="narrator")
    if action == "narrator_stop":
        return _accessibility_kill("Narrator.exe", state, kind="narrator")
    if action == "dictation_status":
        # Windows speech recognition runs under sapisvc / WindowsSpeechRecognition.
        return _ok(
            speech_service=_process_running("WindowsSpeech.exe") or _process_running("speech_runtime.exe"),
            shortcut="Win+H starts dictation in Windows 11.",
            note="Programmatic toggle requires the WinRT SpeechRecognizer namespace; not exposed here.",
        )
    if action in {"settings_panel", "open_settings"}:
        # ms-settings:easeofaccess opens the Accessibility settings page.
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", "Start-Process 'ms-settings:easeofaccess'"], capture_output=True, text=True, timeout=10)
        return _ok(opened=proc.returncode == 0, uri="ms-settings:easeofaccess", verified=proc.returncode == 0)
    if action in {"high_contrast_on", "high_contrast_off", "high_contrast_toggle"}:
        return _err(
            f"accessibility.{action} is deferred; the safe path is the shortcut Left Alt + Left Shift + Print Screen which shows a confirmation dialog.",
            status="needs_user",
            note="If you want programmatic toggle, open ms-settings:easeofaccess-highcontrast (via accessibility settings_panel).",
        )
    return _err(
        "unknown accessibility action", action=action,
        valid_actions=[
            "status", "magnifier_start", "magnifier_stop",
            "narrator_start", "narrator_stop",
            "high_contrast_on", "high_contrast_off",
            "color_filter_on", "color_filter_off",
        ],
        status="needs_user",
    )


def _process_running(exe_name: str) -> bool:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"if (Get-Process -Name '{_ps_quote(Path(exe_name).stem)}' -ErrorAction SilentlyContinue) {{ 1 }} else {{ 0 }}"],
        capture_output=True, text=True, timeout=10,
    )
    return proc.stdout.strip() == "1"


def _accessibility_launch(exe: str, state: AgentState, *, kind: str) -> dict[str, Any]:
    try:
        proc = subprocess.Popen([exe], creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except FileNotFoundError:
        return _err(f"{exe} not found on PATH", status="needs_user")
    state.register_resource(
        f"accessibility_{kind}", exe,
        cleanup_tool="accessibility",
        cleanup_args={"action": f"{kind}_stop"},
        metadata={"exe": exe, "pid": proc.pid, "started_at": datetime.now().isoformat()},
    )
    return _ok(kind=kind, exe=exe, pid=proc.pid, verified=True, note=f"{kind} started; close via {kind}_stop.")


def _accessibility_kill(exe: str, state: AgentState, *, kind: str) -> dict[str, Any]:
    # timeout 15 -> 5s: taskkill normalmente termina en <1s; si tarda 15s
    # algo esta mal (snapshot del sistema corrupto, AV interceptando) y
    # mejor reportar el error rapido que bloquear al caller.
    proc = subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True, text=True, timeout=5)
    killed = proc.returncode == 0
    # Mark any matching resource as cleaned.
    for res in _resources_by_kind(state, f"accessibility_{kind}", include_closed=False):
        state.mark_cleaned(str(res["id"]), {"killed": killed})
    return _ok(kind=kind, exe=exe, killed=killed, exit_code=proc.returncode, stderr=proc.stderr[-500:])


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


def photo_library_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for local photo/video libraries.

    Actions: status, scan, exif, group_by_date, thumbnails, find_by_date.
    Requires Pillow (PIL). Defers any face-recognition/embedding work.
    """
    action = str(args.get("action") or "status").casefold()
    pil_available = importlib.util.find_spec("PIL") is not None
    if action == "status":
        return _ok(
            pillow=pil_available,
            install_hint="python -m pip install Pillow",
            note="EXIF parsing and thumbnails require Pillow; scan/find_by_date work without it for filename listings only.",
        )
    if action == "scan":
        return _photo_scan(args)
    if not pil_available:
        return _err(
            "Pillow is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install Pillow",
        )
    if action == "exif":
        return _photo_exif(args)
    if action == "group_by_date":
        return _photo_group_by_date(args, state)
    if action == "thumbnails":
        return _photo_thumbnails(args, state)
    if action == "find_by_date":
        return _photo_find_by_date(args)
    return _err(
        "unknown photo_library action", action=action,
        valid_actions=[
            "status", "scan", "exif", "group_by_date", "group_by_location",
            "find_duplicates", "thumbnail",
        ],
        status="needs_user",
    )


_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp", ".bmp", ".gif"}


def _photo_scan(args: dict[str, Any]) -> dict[str, Any]:
    root_raw = str(args.get("root") or args.get("path") or "").strip()
    if not root_raw:
        root = Path.home() / "Pictures"
    else:
        root = Path(root_raw).expanduser()
    if not root.exists():
        return _err("root not found", root=str(root))
    limit = int(args.get("limit", 1000))
    photos: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in _PHOTO_EXTS:
            continue
        try:
            stat = path.stat()
            photos.append({"path": str(path), "name": path.name, "size": stat.st_size, "mtime": stat.st_mtime})
        except OSError:
            continue
        if len(photos) >= limit:
            break
    return _ok(root=str(root), count=len(photos), photos=photos[:200], note=f"{len(photos)} photos found (preview limited to 200).")


def _photo_open_exif(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image, ExifTags
    except ImportError:
        return {"error": "PIL not available"}
    try:
        with Image.open(path) as img:
            # _getexif is a private method only on JPEG/TIFF ImageFile subclasses;
            # Pillow doesn't expose it on the base ImageFile type.
            exif_raw = img._getexif() or {}  # type: ignore[attr-defined]
            named: dict[str, Any] = {}
            for tag_id, value in exif_raw.items():
                tag_name = ExifTags.TAGS.get(tag_id, f"Tag{tag_id}")
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8", errors="replace")
                    except Exception:
                        value = repr(value)
                if isinstance(value, dict):
                    # nested (GPS, etc); flatten one level
                    nested = {}
                    for k, v in value.items():
                        name = ExifTags.GPSTAGS.get(k, f"GPS{k}") if tag_name == "GPSInfo" else str(k)
                        nested[name] = str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v
                    value = nested
                if not isinstance(value, (int, float, str, bool, dict, list, type(None))):
                    value = str(value)
                named[tag_name] = value
            return {"size": img.size, "format": img.format, "mode": img.mode, "exif": named}
    except Exception as exc:
        return {"error": f"failed to read: {exc}"}


def _photo_exif(args: dict[str, Any]) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err("file not found", path=str(path))
    info = _photo_open_exif(path)
    if info.get("error"):
        return _err(info["error"], path=str(path))
    return _ok(path=str(path), **info)


def _photo_extract_date(path: Path) -> str | None:
    """Try EXIF DateTimeOriginal/DateTime, fallback to file mtime."""
    info = _photo_open_exif(path)
    exif = info.get("exif") or {}
    for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
        raw = exif.get(key)
        if isinstance(raw, str) and len(raw) >= 10:
            # EXIF format: "YYYY:MM:DD HH:MM:SS"
            return raw[:10].replace(":", "-")
    try:
        return time.strftime("%Y-%m-%d", time.localtime(path.stat().st_mtime))
    except OSError:
        return None


def _photo_group_by_date(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    root_raw = str(args.get("root") or "").strip()
    if not root_raw:
        return _err("missing root")
    root = Path(root_raw).expanduser()
    if not root.is_dir():
        return _err("root not a directory", root=str(root))
    out_raw = str(args.get("output") or args.get("dst") or "").strip()
    if not out_raw:
        out = state.path.parent / "photos_by_date"
    else:
        out = Path(out_raw).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    mode = str(args.get("mode") or "copy").casefold()  # copy|move|symlink|dry_run
    granularity = str(args.get("granularity") or "month").casefold()  # year|month|day
    dry_run = mode == "dry_run"
    moved = 0
    skipped = 0
    plan: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in _PHOTO_EXTS:
            continue
        date = _photo_extract_date(path)
        if not date:
            skipped += 1
            continue
        if granularity == "year":
            subdir_name = date[:4]
        elif granularity == "day":
            subdir_name = date
        else:
            subdir_name = date[:7]  # YYYY-MM
        target_dir = out / subdir_name
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / path.name
        if target.exists():
            target = _next_available_path(target)
        plan.append({"src": str(path), "dst": str(target), "date": date})
        if dry_run:
            moved += 1
            continue
        try:
            if mode == "move":
                shutil.move(str(path), str(target))
            elif mode == "symlink":
                target.symlink_to(path)
            else:
                shutil.copy2(str(path), str(target))
            moved += 1
        except (OSError, shutil.Error):
            skipped += 1
    return _ok(root=str(root), output=str(out), mode=mode, granularity=granularity, processed=moved, skipped=skipped, plan_preview=plan[:30], total_plan=len(plan))


def _photo_thumbnails(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from PIL import Image
    root_raw = str(args.get("root") or "").strip()
    if not root_raw:
        return _err("missing root")
    root = Path(root_raw).expanduser()
    if not root.exists():
        return _err("root not found", root=str(root))
    out_raw = str(args.get("output") or args.get("dst") or "").strip()
    if not out_raw:
        out = state.path.parent / "thumbnails"
    else:
        out = Path(out_raw).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    size_arg: Any = args.get("size", 256)
    if isinstance(size_arg, (list, tuple)) and len(size_arg) == 2:
        size = (int(size_arg[0] or 0), int(size_arg[1] or 0))
    else:
        n: int = int(size_arg) if isinstance(size_arg, (int, float, str)) else 256
        size = (n, n)
    created: list[str] = []
    failed: list[dict[str, str]] = []
    limit = int(args.get("limit", 1000))
    sources = [path for path in root.rglob("*") if path.is_file() and path.suffix.casefold() in _PHOTO_EXTS]
    for path in sources[:limit]:
        target = out / f"{path.stem}_thumb.jpg"
        try:
            with Image.open(path) as img:
                img.thumbnail(size, Image.Resampling.LANCZOS)
                img.convert("RGB").save(target, "JPEG", quality=85)
            created.append(str(target))
        except Exception as exc:
            failed.append({"src": str(path), "error": str(exc)})
    return _ok(root=str(root), output=str(out), size=size, created=len(created), failed=len(failed), failed_details=failed[:10])


def _photo_find_by_date(args: dict[str, Any]) -> dict[str, Any]:
    root_raw = str(args.get("root") or "").strip()
    if not root_raw:
        return _err("missing root")
    year = args.get("year")
    month = args.get("month")
    if year is None:
        return _err("missing year")
    target_prefix = f"{int(year):04d}"
    if month is not None:
        target_prefix += f"-{int(month):02d}"
    root = Path(root_raw).expanduser()
    matches: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in _PHOTO_EXTS:
            continue
        date = _photo_extract_date(path)
        if date and date.startswith(target_prefix):
            matches.append({"path": str(path), "date": date})
        if len(matches) >= int(args.get("limit", 500)):
            break
    return _ok(root=str(root), filter=target_prefix, count=len(matches), photos=matches[:200])


def fact_check_tool(args: dict[str, Any], state: AgentState, knowledge_executor: Executor | None = None) -> dict[str, Any]:
    """Compound tool for lexical claim verification against local sources.

    Actions:
      - status
      - check(claim, sources=[paths|ids|texts]?, use_knowledge=true)
      - compare(claim, text)
    Strategy: TF-IDF + cosine similarity per-chunk against the claim. We do
    NOT call an LLM here; we return ranked snippets so Gemma can write the
    final verdict from real evidence. Stance heuristic (supports/contradicts/
    no_evidence) is rule-based on negation cues, not an ML model.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            backend="tfidf_cosine + bm25_fts5",
            note="Lexical only; no LLM call inside the tool. The agent itself writes the verdict from ranked snippets.",
        )
    if action == "compare":
        claim = str(args.get("claim") or "").strip()
        text = str(args.get("text") or "").strip()
        if not claim or not text:
            return _err("compare requires claim and text")
        chunks = _fact_check_chunks(text)
        ranked = _fact_check_rank(claim, [{"source": "<inline>", "title": "inline", "text": ch} for ch in chunks])
        return _ok(claim=claim, matches=ranked[:10], evaluated=len(chunks))
    if action != "check":
        return _err(
            "unknown fact_check action", action=action,
            valid_actions=["status", "check", "compare"],
            status="needs_user",
        )

    claim = str(args.get("claim") or "").strip()
    if not claim:
        return _err("missing claim")
    raw_sources = args.get("sources")
    sources_arg: list[Any] = raw_sources if isinstance(raw_sources, list) else []
    use_knowledge = bool(args.get("use_knowledge", True))
    limit = int(args.get("limit", 10))

    candidates: list[dict[str, Any]] = []

    # 1. Explicit sources: each entry can be a path, a resource id (res_*), or a text body.
    for entry in sources_arg:
        text = ""
        label = "<inline>"
        path = None
        if isinstance(entry, dict):
            text = str(entry.get("text") or "")
            label = str(entry.get("source") or entry.get("title") or "inline")
            path = entry.get("path")
        elif isinstance(entry, str):
            stripped = entry.strip()
            if stripped.startswith("res_"):
                resource = state._load().get("resources", {}).get(stripped)
                if resource:
                    meta = resource.get("metadata") or {}
                    text = str(meta.get("text") or "")
                    label = str(resource.get("label") or stripped)
                    if not text and meta.get("path") and Path(str(meta["path"])).is_file():
                        text = Path(str(meta["path"])).read_text(encoding="utf-8", errors="replace")[:50000]
            elif Path(stripped).exists() and Path(stripped).is_file():
                text = Path(stripped).read_text(encoding="utf-8", errors="replace")[:50000]
                label = Path(stripped).name
                path = stripped
            else:
                text = stripped
                label = "inline"
        if not text:
            continue
        for ch in _fact_check_chunks(text):
            candidates.append({"source": label, "title": label, "text": ch, "path": path})

    # 2. Local RAG: top-k from knowledge if requested.
    if use_knowledge and knowledge_executor:
        kn = knowledge_executor("knowledge", {"action": "search", "query": claim, "limit": limit})
        for row in kn.get("results", []) if isinstance(kn, dict) else []:
            snip = str(row.get("snippet") or "").replace("[", "").replace("]", "")
            if snip:
                candidates.append({"source": row.get("source") or row.get("title") or "knowledge", "title": row.get("title"), "text": snip})

    if not candidates:
        return _ok(
            claim=claim,
            verdict="no_evidence",
            evaluated=0,
            note="No sources provided and knowledge search returned nothing. Pass sources=[...] or ingest documents first via knowledge(ingest) / document(ingest_to_knowledge).",
            matches=[],
        )

    ranked = _fact_check_rank(claim, candidates)
    top = ranked[:limit]
    # Verdict heuristic:
    # - If best score >= 0.35 and no negation context, lean supports.
    # - If best score >= 0.35 and negation/contradiction cue near match, lean contradicts.
    # - Else no_evidence.
    if not top:
        verdict = "no_evidence"
    else:
        best = top[0]
        if best["score"] >= 0.35:
            verdict = "contradicts" if best.get("negation_signal") else "supports"
        elif best["score"] >= 0.18:
            verdict = "weakly_supports"
        else:
            verdict = "no_evidence"
    return _ok(
        claim=claim,
        verdict=verdict,
        evaluated=len(candidates),
        matches=top,
        note="Verdict is a lexical heuristic; treat as one signal, not ground truth. Inspect matches and write a final answer with citations.",
    )


_NEGATION_CUES_EN = {"not", "no", "never", "false", "untrue", "wrong", "incorrect", "deny", "denies", "denied", "refute", "refuted"}
_NEGATION_CUES_ES = {"no", "nunca", "falso", "falsa", "incorrecto", "incorrecta", "niega", "niegan", "negado", "desmentido", "rechaza", "rechazado"}


def _fact_check_chunks(text: str) -> list[str]:
    """Sentence-level chunks (rough split on . ! ? newlines, then merge short)."""
    raw = re.split(r"(?<=[\.!?])\s+|\n{2,}", text)
    chunks: list[str] = []
    buf = ""
    for sent in raw:
        sent = sent.strip()
        if not sent:
            continue
        if len(buf) + len(sent) < 600:
            buf = f"{buf} {sent}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = sent
    if buf:
        chunks.append(buf)
    return chunks


def _fact_check_rank(claim: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """TF-IDF + cosine similarity. Pure-Python, no sklearn dependency."""
    import math
    from collections import Counter
    def tokenize(text: str) -> list[str]:
        return re.findall(r"[\wÀ-ſ]{2,}", text.casefold())
    claim_tokens = tokenize(claim)
    if not claim_tokens or not candidates:
        return []
    # Build vocabulary and DF over candidates + claim.
    docs = [tokenize(c["text"]) for c in candidates]
    df: Counter[str] = Counter()
    for doc in docs + [claim_tokens]:
        for term in set(doc):
            df[term] += 1
    n_docs = len(docs) + 1

    def tfidf_vector(tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        tf = Counter(tokens)
        total = len(tokens)
        return {t: (count / total) * math.log((n_docs + 1) / (df.get(t, 1) + 1) + 1.0) for t, count in tf.items()}

    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        # Iterate over the smaller dict for the dot product.
        small, large = (a, b) if len(a) <= len(b) else (b, a)
        dot = sum(v * large.get(k, 0.0) for k, v in small.items())
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    claim_vec = tfidf_vector(claim_tokens)
    claim_token_set = set(claim_tokens)
    negation_cues = _NEGATION_CUES_EN | _NEGATION_CUES_ES

    ranked: list[dict[str, Any]] = []
    for cand, tokens in zip(candidates, docs):
        score = cosine(claim_vec, tfidf_vector(tokens))
        # Detect negation cues within a 6-token window of any claim term in the chunk.
        negation_signal = False
        for i, tok in enumerate(tokens):
            if tok not in claim_token_set:
                continue
            window = tokens[max(0, i - 6): i + 7]
            if any(w in negation_cues for w in window):
                negation_signal = True
                break
        ranked.append({
            "source": cand.get("source"),
            "title": cand.get("title"),
            "path": cand.get("path"),
            "score": round(float(score), 4),
            "negation_signal": negation_signal,
            "snippet": cand["text"][:400],
        })
    ranked.sort(key=lambda r: -r["score"])
    return ranked


def data_analysis_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for CSV/Excel local data analysis.

    Actions: status, csv_profile, csv_describe, csv_query, csv_head, csv_to_xlsx,
    plot_histogram, plot_scatter, plot_line. Uses pandas + matplotlib only;
    returns needs_dependency if missing.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            pandas=importlib.util.find_spec("pandas") is not None,
            matplotlib=importlib.util.find_spec("matplotlib") is not None,
            openpyxl=importlib.util.find_spec("openpyxl") is not None,
            install_hint="python -m pip install pandas matplotlib openpyxl",
        )
    if importlib.util.find_spec("pandas") is None:
        return _err(
            "pandas is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install pandas matplotlib openpyxl",
        )
    if action == "csv_profile":
        return _data_csv_profile(args)
    if action == "csv_describe":
        return _data_csv_describe(args)
    if action == "csv_query":
        return _data_csv_query(args)
    if action == "csv_head":
        return _data_csv_head(args)
    if action == "csv_to_xlsx":
        return _data_csv_to_xlsx(args, state)
    if action in {"plot_histogram", "plot_scatter", "plot_line"}:
        return _data_plot(action, args, state)
    return _err(
        "unknown data_analysis action", action=action,
        valid_actions=[
            "status", "csv_describe", "csv_filter", "csv_group_agg",
            "csv_plot", "csv_export", "csv_join", "json_describe",
        ],
        status="needs_user",
    )


def _data_load_df(args: dict[str, Any]):
    import pandas as pd
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return None, _err("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return None, _err("file not found", path=str(path))
    sep = str(args.get("sep") or ",")
    try:
        if path.suffix.casefold() in {".xlsx", ".xls"}:
            df = pd.read_excel(path)
        else:
            df = pd.read_csv(path, sep=sep)
    except Exception as exc:
        return None, _err(f"failed to load: {exc}", path=str(path))
    return df, None


def _data_csv_profile(args: dict[str, Any]) -> dict[str, Any]:
    df, err = _data_load_df(args)
    if err or df is None:
        return err or _err("dataframe missing")
    cols = []
    for col in df.columns:
        s = df[col]
        cols.append({
            "name": str(col),
            "dtype": str(s.dtype),
            "non_null": int(s.notna().sum()),
            "null": int(s.isna().sum()),
            "unique": int(s.nunique(dropna=True)),
        })
    return _ok(
        path=str(args.get("path")),
        rows=int(len(df)),
        columns=int(len(df.columns)),
        column_profile=cols,
        memory_bytes=int(df.memory_usage(index=True, deep=True).sum()),
    )


def _data_csv_describe(args: dict[str, Any]) -> dict[str, Any]:
    df, err = _data_load_df(args)
    if err or df is None:
        return err or _err("dataframe missing")
    desc = df.describe(include="all").fillna("").to_dict()
    return _ok(path=str(args.get("path")), rows=int(len(df)), describe=desc)


def _data_csv_query(args: dict[str, Any]) -> dict[str, Any]:
    df, err = _data_load_df(args)
    if err or df is None:
        return err or _err("dataframe missing")
    query = str(args.get("query") or "").strip()
    if not query:
        return _err("missing query (pandas .query() expression)")
    # T2-data_analysis-pandas-query-eval-035: rechazar `@` (local var access) y
    # backticked column names (parsea con eval). Forzar engine='numexpr' si
    # disponible (más restrictivo); fallback al python engine sólo si numexpr
    # no está y la query no contiene caracteres peligrosos.
    if "@" in query or "`" in query:
        return _err(
            "query contains '@' or backticks; refused for safety. Use plain column names and operators.",
            query=query,
            status="needs_user",
        )
    engine = "numexpr" if importlib.util.find_spec("numexpr") is not None else "python"
    try:
        result = df.query(query, engine=engine)
    except (ValueError, SyntaxError, KeyError, TypeError) as exc:
        return _err(f"query failed: {exc}", query=query, engine=engine)
    limit = int(args.get("limit", 50))
    return _ok(
        path=str(args.get("path")), query=query, engine=engine,
        matched_rows=int(len(result)),
        preview=result.head(limit).to_dict(orient="records"),
    )


def _data_csv_head(args: dict[str, Any]) -> dict[str, Any]:
    df, err = _data_load_df(args)
    if err or df is None:
        return err or _err("dataframe missing")
    n = int(args.get("n", 10))
    return _ok(path=str(args.get("path")), n=n, rows=df.head(n).to_dict(orient="records"))


def _data_csv_to_xlsx(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    df, err = _data_load_df(args)
    if err or df is None:
        return err or _err("dataframe missing")
    if importlib.util.find_spec("openpyxl") is None:
        return _err("openpyxl is required to write .xlsx", status="needs_dependency", install_hint="python -m pip install openpyxl")
    dst_raw = str(args.get("dst") or "").strip()
    if dst_raw:
        dst = Path(dst_raw).expanduser()
    else:
        dst = state.path.parent / "data_analysis" / f"export_{int(time.time())}.xlsx"
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_excel(dst, index=False)
    except Exception as exc:
        return _err(f"to_excel failed: {exc}", dst=str(dst))
    return _ok(path=str(args.get("path")), dst=str(dst), rows=int(len(df)), verified=dst.is_file())


def _data_plot(kind: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    if importlib.util.find_spec("matplotlib") is None:
        return _err("matplotlib is not installed", status="needs_dependency", install_hint="python -m pip install matplotlib")
    df, err = _data_load_df(args)
    if err or df is None:
        return err or _err("dataframe missing")
    import matplotlib
    matplotlib.use("Agg")  # headless backend; safe even when DISPLAY exists
    import matplotlib.pyplot as plt
    dst_raw = str(args.get("dst") or "").strip()
    if dst_raw:
        dst = Path(dst_raw).expanduser()
    else:
        dst = state.path.parent / "data_analysis" / f"{kind}_{int(time.time())}.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    try:
        if kind == "plot_histogram":
            col = str(args.get("column") or "")
            if col not in df.columns:
                return _err("column not found", column=col, available=[str(c) for c in df.columns])
            df[col].dropna().hist(ax=ax, bins=int(args.get("bins", 20)))
            ax.set_title(f"Histogram of {col}")
            ax.set_xlabel(col)
            ax.set_ylabel("count")
        elif kind == "plot_scatter":
            x = str(args.get("x") or args.get("x_col") or "")
            y = str(args.get("y") or args.get("y_col") or "")
            if x not in df.columns or y not in df.columns:
                return _err("x/y column not found", x=x, y=y, available=[str(c) for c in df.columns])
            ax.scatter(df[x], df[y])
            ax.set_xlabel(x); ax.set_ylabel(y); ax.set_title(f"{y} vs {x}")
        elif kind == "plot_line":
            x = str(args.get("x") or args.get("x_col") or "")
            y = str(args.get("y") or args.get("y_col") or "")
            if x not in df.columns or y not in df.columns:
                return _err("x/y column not found", x=x, y=y, available=[str(c) for c in df.columns])
            ax.plot(df[x], df[y])
            ax.set_xlabel(x); ax.set_ylabel(y); ax.set_title(f"{y} over {x}")
        fig.tight_layout()
        fig.savefig(dst, dpi=120)
    except Exception as exc:
        return _err(f"plot failed: {exc}")
    finally:
        plt.close(fig)
    return _ok(path=str(args.get("path")), dst=str(dst), kind=kind, verified=dst.is_file(), size=dst.stat().st_size if dst.is_file() else 0)


def network_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for network diagnostics.

    Actions: status, ping(host), traceroute(host), dns_get, dns_set(adapter,
    addresses, snapshot=True), dns_resolve(name), port_check(host, port),
    connections, public_ip. Writing actions (dns_set) snapshot the previous
    config so they can be rolled back via state.rollback.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            powershell=bool(shutil.which("powershell")),
            ping=bool(shutil.which("ping")),
            tracert=bool(shutil.which("tracert")),
            backend="windows_net",
            note="dns_set requires the adapter name from dns_get and snapshots the previous list.",
        )
    if action == "ping":
        return _network_ping(args)
    if action == "traceroute":
        return _network_traceroute(args)
    if action == "dns_get":
        return _network_dns_get(args)
    if action == "dns_set":
        return _network_dns_set(args, state)
    if action in {"dns_resolve", "resolve"}:
        return _network_dns_resolve(args)
    if action == "port_check":
        return _network_port_check(args)
    if action == "connections":
        return _network_connections(args)
    if action == "public_ip":
        return _network_public_ip()
    if action in {"firewall_allow", "firewall_block", "firewall_remove"}:
        return _err(
            f"network.{action} is intentionally not exposed; modifying firewall rules requires explicit terminal commands",
            status="needs_user",
        )
    return _err(
        "unknown network action", action=action,
        valid_actions=[
            "status", "ping", "traceroute", "dns_get", "dns_set",
            "dns_lookup", "speedtest", "wifi_info", "active_connections",
        ],
        status="needs_user",
    )


def _network_ping(args: dict[str, Any]) -> dict[str, Any]:
    host = str(args.get("host") or args.get("target") or "").strip()
    if not host:
        return _err("missing host")
    count = int(args.get("count", 4))
    proc = subprocess.run(["ping", "-n", str(count), host], capture_output=True, text=True, timeout=30)
    return _ok(host=host, count=count, exit_code=proc.returncode, stdout=proc.stdout[-3000:], reachable=proc.returncode == 0)


def _network_traceroute(args: dict[str, Any]) -> dict[str, Any]:
    host = str(args.get("host") or args.get("target") or "").strip()
    if not host:
        return _err("missing host")
    max_hops = int(args.get("max_hops", 20))
    proc = subprocess.run(["tracert", "-h", str(max_hops), host], capture_output=True, text=True, timeout=120)
    return _ok(host=host, max_hops=max_hops, exit_code=proc.returncode, stdout=proc.stdout[-4000:])


def _network_dns_get(args: dict[str, Any]) -> dict[str, Any]:
    adapter = str(args.get("adapter") or "").strip()
    cmd = "Get-DnsClientServerAddress | Where-Object { $_.ServerAddresses } | Select-Object InterfaceAlias,AddressFamily,ServerAddresses | ConvertTo-Json -Depth 3"
    if adapter:
        cmd = f"Get-DnsClientServerAddress -InterfaceAlias '{_ps_quote(adapter)}' | Select-Object InterfaceAlias,AddressFamily,ServerAddresses | ConvertTo-Json -Depth 3"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=15)
    if proc.returncode != 0:
        return _err("dns_get failed", stderr=proc.stderr)
    raw = proc.stdout.strip()
    if not raw:
        return _ok(adapters=[], count=0)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err("dns_get invalid JSON", raw=raw[:500])
    if isinstance(data, dict):
        data = [data]
    return _ok(adapters=data, count=len(data))


def _network_dns_set(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    adapter = str(args.get("adapter") or "").strip()
    if not adapter:
        return _err("missing adapter (use dns_get first)")
    addresses = args.get("addresses") if isinstance(args.get("addresses"), list) else None
    if not addresses:
        return _err("missing addresses (list of DNS server IPs)")
    addresses = [str(a) for a in addresses if str(a).strip()]
    before = _network_dns_get({"adapter": adapter})
    rollback_addrs: list[str] = []
    for adapter_info in before.get("adapters", []):
        if str(adapter_info.get("InterfaceAlias", "")).casefold() == adapter.casefold() and adapter_info.get("AddressFamily") == 2:
            rollback_addrs = adapter_info.get("ServerAddresses") or []
            break
    rollback_step = {"tool": "network", "args": {"action": "dns_set", "adapter": adapter, "addresses": rollback_addrs or ["AUTO"]}}
    checkpoint = state.checkpoint(
        f"dns_set {adapter}",
        rollback=[rollback_step] if rollback_addrs else [],
        metadata={"before": before, "target_addresses": addresses},
    )
    # CC-100 / T2-network-dns-set-injection-033: validar cada IP antes de
    # interpolar; adapter va por env-var; addresses van también via env-var
    # como string separado por comas.
    if addresses == ["AUTO"] or addresses == ["auto"]:
        env = {**os.environ, "GEMMA4_DNS_ADAPTER": adapter}
        cmd = "Set-DnsClientServerAddress -InterfaceAlias $env:GEMMA4_DNS_ADAPTER -ResetServerAddresses"
    else:
        for addr in addresses:
            if not (is_ipv4(addr) or is_ipv6(addr)):
                return _err(f"invalid DNS address: {addr!r}", status="needs_user")
        env = {
            **os.environ,
            "GEMMA4_DNS_ADAPTER": adapter,
            "GEMMA4_DNS_ADDRS": ",".join(addresses),
        }
        cmd = (
            "$addrs = $env:GEMMA4_DNS_ADDRS -split ','; "
            "Set-DnsClientServerAddress -InterfaceAlias $env:GEMMA4_DNS_ADAPTER -ServerAddresses $addrs"
        )
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], env=env, capture_output=True, text=True, timeout=15)
    after = _network_dns_get({"adapter": adapter})
    return _ok(
        adapter=adapter, target=addresses, before=rollback_addrs, after=after,
        exit_code=proc.returncode, stderr=proc.stderr[-1000:],
        checkpoint=checkpoint.get("checkpoint"),
        verified=proc.returncode == 0,
    )


def _network_dns_resolve(args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("name") or args.get("host") or "").strip()
    if not name:
        return _err("missing name")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Resolve-DnsName '{_ps_quote(name)}' -ErrorAction SilentlyContinue | Select-Object Name,Type,IPAddress,NameHost,TTL | ConvertTo-Json -Depth 3"],
        capture_output=True, text=True, timeout=15,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        return _err("dns_resolve failed", stderr=proc.stderr, name=name)
    raw = proc.stdout.strip()
    if not raw:
        return _ok(name=name, records=[], count=0)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err("dns_resolve invalid JSON", raw=raw[:500])
    if isinstance(data, dict):
        data = [data]
    return _ok(name=name, records=data, count=len(data))


def _network_port_check(args: dict[str, Any]) -> dict[str, Any]:
    host = str(args.get("host") or args.get("target") or "").strip()
    port = args.get("port")
    if not host or port is None:
        return _err("missing host or port")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Test-NetConnection -ComputerName '{_ps_quote(host)}' -Port {int(port)} -InformationLevel Quiet -WarningAction SilentlyContinue"],
        capture_output=True, text=True, timeout=20,
    )
    reachable = (proc.stdout or "").strip().casefold() == "true"
    return _ok(host=host, port=int(port), reachable=reachable, exit_code=proc.returncode)


def _network_connections(args: dict[str, Any]) -> dict[str, Any]:
    # CC-100 / T2-network-connections-state-no-allowlist-034: enum allowlist.
    state_filter_raw = str(args.get("state") or "Established").strip()
    try:
        state_filter = ps_safe_literal(state_filter_raw, RX_TCP_STATE)
    except PSValidationError as exc:
        return _err(f"invalid state filter: {exc}", status="needs_user")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Get-NetTCPConnection -State {state_filter} -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess | ConvertTo-Json -Depth 3"],
        capture_output=True, text=True, timeout=20,
    )
    if proc.returncode != 0:
        return _err("connections query failed", stderr=proc.stderr)
    ok_parse, data = parse_ps_json(proc.stdout)
    if not ok_parse:
        return _err("connections invalid JSON", raw=data)
    if data is None:
        return _ok(connections=[], count=0, state=state_filter)
    if isinstance(data, dict):
        data = [data]
    return _ok(connections=data, count=len(data), state=state_filter)


def _network_public_ip() -> dict[str, Any]:
    import urllib.request
    try:
        req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "Gemma4Agent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return _ok(ip=resp.read().decode("utf-8").strip(), source="api.ipify.org", verified=True)
    except Exception as exc:
        return _err(f"public_ip failed: {exc}")


def watcher_tool(args: dict[str, Any], state: AgentState, executor: Executor | None = None) -> dict[str, Any]:
    """Compound tool for file/url watchers.

    Actions:
      - status
      - watch_file(path, on_change={tool, args})
      - watch_url(url, on_change={tool, args}, interval_seconds?)
      - list
      - check(watcher_id) -> evaluate now without scheduling
      - delete(watcher_id)
    Watchers persist in state as kind=watcher with a snapshot (mtime+size for
    files, content hash for URLs). The schedule is registered as a Scheduled
    Task invoking `python -m gemma4_agent.watcher_runner`.
    """
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(backend="windows_scheduled_tasks", runner_module="gemma4_agent.watcher_runner")
    if action == "list":
        watchers = _resources_by_kind(state, "watcher", include_closed=bool(args.get("include_closed", False)))
        return _ok(watchers=watchers, count=len(watchers))
    if action == "delete":
        target = _find_resource(args, state, "watcher")
        if not target:
            return _err("watcher not found")
        task_name = str((target.get("metadata") or {}).get("task_name") or "").strip()
        if task_name:
            _unregister_routine_scheduled_task(task_name)
        return state.mark_cleaned(str(target["id"]), {"deleted": True})
    if action == "check":
        return _watcher_check(args, state, executor)
    if action == "watch_file":
        return _watcher_register_file(args, state)
    if action == "watch_url":
        return _watcher_register_url(args, state)
    return _err(
        "unknown watcher action", action=action,
        valid_actions=[
            "status", "list", "watch_file", "watch_url", "check",
            "disable", "enable", "delete",
        ],
        status="needs_user",
    )


def _watcher_register_file(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err("missing path")
    target = Path(path_raw).expanduser()
    if not target.exists():
        return _err("watch_file target does not exist (create it first or use watch_url)", path=str(target))
    on_change = args.get("on_change") if isinstance(args.get("on_change"), dict) else None
    interval = int(args.get("interval_seconds", 60))
    snapshot = _file_snapshot(target)
    label = f"watch_file {target.name}"
    task_name = f"Gemma4Watcher_{_safe_name(target.stem)[:30]}_{int(time.time())}"
    resource = state.register_resource(
        "watcher", label,
        cleanup_tool="watcher",
        cleanup_args={"action": "delete", "name": label},
        metadata={
            "kind": "file",
            "path": str(target),
            "snapshot": snapshot,
            "on_change": on_change,
            "interval_seconds": interval,
            "task_name": task_name,
            "created_at": datetime.now().isoformat(),
        },
    )
    rid = resource.get("resource", {}).get("id")
    if rid and interval > 0:
        register = _register_watcher_scheduled_task(task_name, rid, interval, label)
        if not register.get("ok"):
            return register
    return _ok(watcher=resource.get("resource"), task_name=task_name, snapshot=snapshot)


def _watcher_register_url(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    url = str(args.get("url") or "").strip()
    if not url:
        return _err("missing url")
    on_change = args.get("on_change") if isinstance(args.get("on_change"), dict) else None
    interval = int(args.get("interval_seconds", 300))
    snapshot = _url_snapshot(url)
    if not snapshot.get("ok"):
        return snapshot
    label = f"watch_url {url[:50]}"
    task_name = f"Gemma4Watcher_url_{int(time.time())}"
    resource = state.register_resource(
        "watcher", label,
        cleanup_tool="watcher",
        cleanup_args={"action": "delete", "name": label},
        metadata={
            "kind": "url",
            "url": url,
            "snapshot": snapshot,
            "on_change": on_change,
            "interval_seconds": interval,
            "task_name": task_name,
            "created_at": datetime.now().isoformat(),
        },
    )
    rid = resource.get("resource", {}).get("id")
    if rid and interval > 0:
        register = _register_watcher_scheduled_task(task_name, rid, interval, label)
        if not register.get("ok"):
            return register
    return _ok(watcher=resource.get("resource"), task_name=task_name, snapshot=snapshot)


def _file_snapshot(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
        return {"exists": True, "mtime": stat.st_mtime, "size": stat.st_size}
    except OSError:
        return {"exists": False}


def _url_snapshot(url: str) -> dict[str, Any]:
    import urllib.request
    import hashlib as _hashlib
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Gemma4Agent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read(2_000_000)
            digest = _hashlib.sha256(body).hexdigest()
            return {"ok": True, "status_code": resp.status, "sha256": digest, "bytes": len(body), "captured_at": datetime.now().isoformat()}
    except Exception as exc:
        return _err(f"url_snapshot failed: {exc}", url=url)


def _process_snapshot(process_name: str) -> dict[str, Any]:
    """Snapshot whether a given process is running. Matches by exe name (case-insensitive)."""
    if not process_name:
        return {"running": False, "process": process_name}
    base = Path(process_name).stem
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"if (Get-Process -Name '{_ps_quote(base)}' -ErrorAction SilentlyContinue) {{ 1 }} else {{ 0 }}"],
        capture_output=True, text=True, timeout=10,
    )
    return {"running": proc.stdout.strip() == "1", "process": process_name}


def _register_routine_process_watcher(state: AgentState, routine_label: str, routine_id: str, process_name: str, interval_seconds: int, edge: str) -> dict[str, Any]:
    """Create a kind=process watcher that fires routine.run_now on the requested edge."""
    snapshot = _process_snapshot(process_name)
    label = f"process-trigger for {routine_label} ({process_name}, {edge})"
    task_name = f"Gemma4Watcher_proc_{_safe_name(process_name)[:30]}_{int(time.time())}"
    resource = state.register_resource(
        "watcher", label,
        cleanup_tool="watcher",
        cleanup_args={"action": "delete", "name": label},
        metadata={
            "kind": "process",
            "process": process_name,
            "edge": edge,
            "snapshot": snapshot,
            "on_change": {"tool": "routine", "args": {"action": "run_now", "id": routine_id}},
            "interval_seconds": interval_seconds,
            "task_name": task_name,
            "created_at": datetime.now().isoformat(),
            "linked_routine": routine_id,
        },
    )
    watcher_id = resource.get("resource", {}).get("id")
    if watcher_id and interval_seconds > 0:
        scheduled = _register_watcher_scheduled_task(task_name, watcher_id, interval_seconds, label)
        if not scheduled.get("ok"):
            return scheduled
    return _ok(watcher_id=watcher_id, task_name=task_name, snapshot=snapshot, edge=edge)


def _register_watcher_scheduled_task(task_name: str, watcher_id: str, interval_seconds: int, label: str) -> dict[str, Any]:
    python_exe = _detect_python_executable()
    if not python_exe:
        return _err("no python executable found", status="needs_dependency")
    arg_line = f'-m gemma4_agent.watcher_runner --id "{watcher_id}"'
    minutes = max(1, interval_seconds // 60)
    ps = f"""
$Action = New-ScheduledTaskAction -Execute '{_ps_quote(python_exe)}' -Argument '{_ps_quote(arg_line)}'
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes {minutes})
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName '{_ps_quote(task_name)}' -TaskPath '\\Gemma4Agent\\' -Action $Action -Trigger $Trigger -Settings $Settings -Description '{_ps_quote(label)}' -Force | Out-Null
"""
    # timeout 30 -> 15s + try/except. Register-ScheduledTask normalmente
    # <3s; 15s suficiente. Sin try/except, una corrupcion del Task Scheduler
    # mataba el turn entero.
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return _err("schedule task timeout", task_name=task_name, reason="taskscheduler_timeout")
    if proc.returncode != 0:
        return _err("failed to register watcher scheduled task", stderr=proc.stderr, exit_code=proc.returncode)
    return _ok(task_name=task_name, interval_minutes=minutes)


def _watcher_check(args: dict[str, Any], state: AgentState, executor: Executor | None) -> dict[str, Any]:
    target = _find_resource(args, state, "watcher")
    if not target:
        return _err("watcher not found")
    metadata = target.get("metadata") or {}
    kind = metadata.get("kind")
    snapshot_before = metadata.get("snapshot") or {}
    edge = str(metadata.get("edge") or "any").casefold()
    if kind == "file":
        path = Path(str(metadata.get("path") or "")).expanduser()
        snapshot_after = _file_snapshot(path)
    elif kind == "url":
        snapshot_after = _url_snapshot(str(metadata.get("url") or ""))
    elif kind == "process":
        process_name = str(metadata.get("process") or "")
        snapshot_after = _process_snapshot(process_name)
    else:
        return _err("unknown watcher kind", kind=kind)

    changed = snapshot_before != snapshot_after
    # For process watchers, only fire on the requested edge.
    if changed and kind == "process":
        was_running = bool((snapshot_before or {}).get("running"))
        is_running = bool((snapshot_after or {}).get("running"))
        if edge == "rising" and not (is_running and not was_running):
            changed = False
        elif edge == "falling" and not (was_running and not is_running):
            changed = False
    triggered = None
    if changed:
        on_change = metadata.get("on_change") if isinstance(metadata.get("on_change"), dict) else None
        if on_change and executor:
            tool = str(on_change.get("tool") or "").strip()
            tool_args = on_change.get("args") if isinstance(on_change.get("args"), dict) else {}
            if tool and tool != "watcher":
                triggered = {"tool": tool, "args": tool_args, "result": executor(tool, tool_args)}
        # CC-102: actualización atómica del snapshot.
        state.update_resource_metadata(
            str(target["id"]),
            {"snapshot": snapshot_after, "last_change": datetime.now().isoformat()},
        )
    return _ok(
        watcher_id=str(target["id"]),
        kind=kind,
        changed=changed,
        snapshot_before=snapshot_before,
        snapshot_after=snapshot_after,
        triggered=triggered,
    )


def job_manager_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for tracking long-running jobs (subprocess-based).

    Actions:
      - status
      - start(command, cwd?, label?) -> registers a job + Popen
      - list
      - log(job_id, tail?) -> read job log
      - status_of(job_id) -> alive/exited
      - cancel(job_id) -> kill process tree
    Distinct from `developer.start_dev_server` which is specialized for dev
    servers. job_manager is generic.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(backend="subprocess+state", note="Jobs are tracked in state.json with PID, log path, label.")
    if action == "list":
        jobs = _resources_by_kind(state, "job", include_closed=bool(args.get("include_closed", False)))
        for job in jobs:
            pid = (job.get("metadata") or {}).get("pid")
            if pid:
                job["alive"] = _pid_alive(int(pid))
        return _ok(jobs=jobs, count=len(jobs))
    if action == "start":
        return _job_manager_start(args, state)
    if action == "log":
        return _job_manager_log(args, state)
    if action in {"status_of", "info"}:
        job = _find_resource(args, state, "job")
        if not job:
            return _err("job not found")
        pid = (job.get("metadata") or {}).get("pid")
        return _ok(job=job, alive=_pid_alive(int(pid)) if pid else None)
    if action in {"cancel", "stop", "kill"}:
        return _job_manager_cancel(args, state)
    return _err(
        "unknown job_manager action", action=action,
        valid_actions=[
            "status", "start", "list", "log", "status_of", "cancel",
            "wait", "remove",
        ],
        status="needs_user",
    )


def _job_manager_start(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    command = args.get("command")
    if isinstance(command, str):
        # T2-job_manager-start-no-shell-flag-046: respeta quoting con shlex.
        import shlex
        try:
            cmd = shlex.split(command, posix=False)
        except ValueError as exc:
            return _err(f"invalid command quoting: {exc}", command=command, status="needs_user")
    elif isinstance(command, list):
        cmd = [str(part) for part in command]
    else:
        return _err("command must be a string or list")
    if not cmd:
        return _err("command is empty")
    cwd = str(args.get("cwd") or "").strip() or None
    label = str(args.get("label") or " ".join(cmd)[:80]).strip()
    log_dir = state.path.parent / "jobs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"job_{_safe_name(label)[:30]}_{int(time.time())}.log"
    log_file = log_path.open("w", encoding="utf-8")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=log_file, stderr=subprocess.STDOUT, creationflags=creationflags)
    except OSError as exc:
        return _err(f"failed to start job: {exc}", command=cmd, cwd=cwd)
    resource = state.register_resource(
        "job", label,
        cleanup_tool="job_manager",
        cleanup_args={"action": "cancel"},
        metadata={"cmd": cmd, "cwd": cwd, "pid": proc.pid, "log": str(log_path), "started_at": datetime.now().isoformat()},
    )
    rid = resource.get("resource", {}).get("id")
    if rid:
        # CC-102: cleanup_args via API pública.
        state.update_resource(rid, cleanup_args_patch={"action": "cancel", "job_id": rid})
    return _ok(job_id=rid, pid=proc.pid, cmd=cmd, log=str(log_path))


def _job_manager_log(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    job = _find_resource(args, state, "job")
    if not job:
        return _err("job not found")
    log_path = Path((job.get("metadata") or {}).get("log") or "")
    if not log_path.is_file():
        return _err("job log not found", log=str(log_path))
    tail = int(args.get("tail", 100))
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return _err(f"failed to read log: {exc}", log=str(log_path))
    lines = text.splitlines()
    return _ok(job_id=str(job["id"]), log=str(log_path), lines=lines[-tail:], total_lines=len(lines))


def _job_manager_cancel(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    job = _find_resource(args, state, "job")
    if not job:
        return _err("job not found")
    pid = (job.get("metadata") or {}).get("pid")
    if not pid:
        return _err("job has no pid")
    # CC-104: verify PID identity before taskkill.
    cmd = (job.get("metadata") or {}).get("cmd") or []
    expected = str(cmd[0]) if isinstance(cmd, list) and cmd else None
    matches, current_name = _pid_owned_by(int(pid), expected)
    if not matches:
        return _err(
            "pid_recycled: refused to kill PID held by a different process",
            pid=pid,
            expected_exe=expected,
            current_name=current_name,
            status="needs_user",
        )
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"], capture_output=True, text=True, timeout=10)
        else:
            os.kill(int(pid), 15)
    except (subprocess.SubprocessError, ProcessLookupError, PermissionError, OSError) as exc:
        return _err(f"failed to kill pid {pid}: {exc}", pid=pid)
    state.mark_cleaned(str(job["id"]), {"killed": True, "pid": pid})
    return _ok(job_id=str(job["id"]), pid=pid, killed=True)


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


def _device_wifi_add_profile(args: dict[str, Any]) -> dict[str, Any]:
    """Create a WPA2-Personal Wi-Fi profile via netsh wlan add profile.

    Template from Microsoft Win32 Native Wifi docs (WPA2-Personal sample).
    """
    ssid = str(args.get("ssid") or args.get("name") or "").strip()
    password = str(args.get("password") or args.get("key") or "").strip()
    if not ssid or not password:
        return _err("wifi_add_profile requires ssid and password")
    if len(password) < 8 or len(password) > 63:
        return _err("WPA2 passphrase must be 8-63 ASCII characters", length=len(password))
    auto_connect = bool(args.get("auto_connect", True))
    connection_mode = "auto" if auto_connect else "manual"
    profile_xml = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{_xml_escape(ssid)}</name>
  <SSIDConfig>
    <SSID>
      <name>{_xml_escape(ssid)}</name>
    </SSID>
  </SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>{connection_mode}</connectionMode>
  <MSM>
    <security>
      <authEncryption>
        <authentication>WPA2PSK</authentication>
        <encryption>AES</encryption>
        <useOneX>false</useOneX>
      </authEncryption>
      <sharedKey>
        <keyType>passPhrase</keyType>
        <protected>false</protected>
        <keyMaterial>{_xml_escape(password)}</keyMaterial>
      </sharedKey>
    </security>
  </MSM>
</WLANProfile>
"""
    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".xml", prefix="gemma4_wlan_")
    try:
        os.close(fd)
        Path(tmp_path).write_text(profile_xml, encoding="utf-8")
        scope = "all" if bool(args.get("all_users", False)) else "current"
        proc = subprocess.run(
            ["netsh", "wlan", "add", "profile", f"filename={tmp_path}", f"user={scope}"],
            capture_output=True, text=True, timeout=20,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    if proc.returncode != 0:
        return _err("netsh wlan add profile failed", stderr=proc.stderr, exit_code=proc.returncode, stdout=proc.stdout[-500:])
    return _ok(
        ssid=ssid,
        connection_mode=connection_mode,
        scope=scope if 'scope' in locals() else 'current',
        exit_code=proc.returncode,
        stdout=proc.stdout.strip()[:500],
        note="Profile added. Use wifi_connect with the same SSID to actually associate.",
        verified=True,
    )


def _device_wifi_delete_profile(args: dict[str, Any]) -> dict[str, Any]:
    ssid = str(args.get("ssid") or args.get("name") or "").strip()
    if not ssid:
        return _err("missing ssid")
    proc = subprocess.run(["netsh", "wlan", "delete", "profile", f"name={ssid}"], capture_output=True, text=True, timeout=10)
    return _ok(
        ssid=ssid,
        exit_code=proc.returncode,
        stdout=proc.stdout.strip()[:500],
        stderr=proc.stderr[-500:],
        verified=proc.returncode == 0,
    )


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
    )


def _device_wifi_status() -> dict[str, Any]:
    # timeout 15 -> 6s + try/except. netsh wlan show interfaces normalmente
    # tarda <500ms; si Wlansvc esta caido o sin adaptador, mejor abortar
    # rapido que bloquear 15s.
    try:
        proc = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=6)
    except (OSError, subprocess.TimeoutExpired):
        return _err("netsh wlan timeout", reason="wlansvc_unresponsive")
    if proc.returncode != 0:
        return _err("netsh wlan show interfaces failed", stderr=proc.stderr, exit_code=proc.returncode)
    fields: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip().casefold()] = value.strip()
    # netsh localizes keys; map both english and spanish.
    def pick(*keys: str) -> Any:
        for k in keys:
            if fields.get(k.casefold()) is not None:
                return fields.get(k.casefold())
        return None
    return _ok(
        ssid=pick("ssid"),
        state=pick("state", "estado"),
        signal=pick("signal", "se�al"),
        radio_type=pick("radio type", "tipo de radio"),
        bssid=pick("bssid"),
        receive_rate_mbps=pick("receive rate (mbps)", "velocidad de recepci�n (mbps)"),
        transmit_rate_mbps=pick("transmit rate (mbps)", "velocidad de transmisi�n (mbps)"),
        raw=fields,
    )


def _device_wifi_profiles() -> dict[str, Any]:
    try:
        proc = subprocess.run(["netsh", "wlan", "show", "profiles"], capture_output=True, text=True, timeout=6)
    except (OSError, subprocess.TimeoutExpired):
        return _err("netsh wlan timeout", reason="wlansvc_unresponsive")
    if proc.returncode != 0:
        return _err("netsh wlan show profiles failed", stderr=proc.stderr)
    profiles: list[str] = []
    for line in proc.stdout.splitlines():
        if "All User Profile" in line or "Perfil de todos los usuarios" in line:
            _, _, name = line.partition(":")
            name = name.strip()
            if name:
                profiles.append(name)
    return _ok(profiles=profiles, count=len(profiles))


def _device_wifi_scan() -> dict[str, Any]:
    # netsh wlan show networks lists currently visible SSIDs.
    # timeout 20 -> 10s: el scan puede tardar 2-8s segun el adaptador y
    # cuantas redes visibles haya. 10s es suficiente headroom.
    try:
        proc = subprocess.run(["netsh", "wlan", "show", "networks", "mode=bssid"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return _err("netsh wlan scan timeout", reason="wlansvc_unresponsive")
    if proc.returncode != 0:
        return _err("netsh wlan show networks failed", stderr=proc.stderr)
    networks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in proc.stdout.splitlines():
        s = line.strip()
        if s.startswith("SSID ") and ":" in s:
            if current:
                networks.append(current)
            _, _, ssid = s.partition(":")
            current = {"ssid": ssid.strip()}
        elif current is not None and ":" in s:
            key, _, value = s.partition(":")
            current[key.strip().casefold()] = value.strip()
    if current:
        networks.append(current)
    return _ok(networks=networks[:50], count=len(networks))


def _device_wifi_connect(args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("name") or args.get("ssid") or args.get("profile") or "").strip()
    if not name:
        return _err("missing profile name; pass name=<existing profile>")
    password = str(args.get("password") or args.get("key") or "").strip()
    profiles = _device_wifi_profiles().get("profiles", [])
    created = None
    if name not in profiles:
        # If the caller provided a password, auto-create a WPA2-Personal profile.
        if password:
            created = _device_wifi_add_profile({"ssid": name, "password": password, "auto_connect": bool(args.get("auto_connect", True)), "all_users": bool(args.get("all_users", False))})
            if not created.get("ok"):
                return created
        else:
            return _err(
                f"profile '{name}' not found; pass password to auto-create a WPA2-Personal profile, or use wifi_add_profile first",
                status="needs_user",
                available_profiles=profiles[:30],
            )
    proc = subprocess.run(["netsh", "wlan", "connect", f"name={name}"], capture_output=True, text=True, timeout=20)
    return _ok(
        profile=name,
        created_profile=created,
        exit_code=proc.returncode,
        stdout=proc.stdout.strip()[:500],
        stderr=proc.stderr.strip()[:500],
        verified=proc.returncode == 0,
        status="done" if proc.returncode == 0 else "needs_verification",
    )


def _device_wifi_disconnect() -> dict[str, Any]:
    proc = subprocess.run(["netsh", "wlan", "disconnect"], capture_output=True, text=True, timeout=10)
    return _ok(exit_code=proc.returncode, stdout=proc.stdout.strip(), verified=proc.returncode == 0)


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


def document_tool(args: dict[str, Any], state: AgentState, knowledge_executor: Executor | None = None) -> dict[str, Any]:
    """Compound tool for PDF/DOCX/XLSX/PPTX/HTML parsing and ingestion.

    Actions: status, extract_text, extract_tables, extract_images, ocr_pdf,
    summarize, ingest_to_knowledge, compare_documents.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            backends={
                "pdf_text": importlib.util.find_spec("pypdf") is not None,
                "pdf_tables": importlib.util.find_spec("pdfplumber") is not None,
                "docx": importlib.util.find_spec("docx") is not None,
                "xlsx": importlib.util.find_spec("openpyxl") is not None,
                "pptx": importlib.util.find_spec("pptx") is not None,
                "html": importlib.util.find_spec("bs4") is not None,
                "tesseract": bool(shutil.which("tesseract") or shutil.which("tesseract.exe")),
            },
            supported_extensions=[".pdf", ".docx", ".xlsx", ".pptx", ".html", ".htm", ".txt", ".md"],
            note="Each backend reports needs_dependency individually if missing.",
        )
    if action == "extract_text":
        return _document_extract_text(args)
    if action == "extract_tables":
        return _document_extract_tables(args)
    if action == "extract_images":
        return _document_extract_images(args, state)
    if action == "ocr_pdf":
        return _document_ocr_pdf(args, state)
    if action == "summarize":
        # Summarization is delegated to the calling LLM; this tool only extracts
        # enough text and reports basic stats so the agent can summarize.
        text_result = _document_extract_text(args)
        if not text_result.get("ok"):
            return text_result
        text = text_result.get("text") or ""
        return _ok(
            path=text_result.get("path"),
            chars=len(text),
            word_count=len(text.split()),
            text_preview=text[: int(args.get("preview_chars", 4000))],
            note="Use the returned text_preview to write the summary; this tool does not call an LLM.",
        )
    if action == "ingest_to_knowledge":
        if not knowledge_executor:
            return _err("ingest_to_knowledge requires the knowledge executor", status="needs_implementation")
        path_raw = str(args.get("path") or "").strip()
        if not path_raw:
            return _err("missing path")
        # Extract first, then feed to knowledge tool.
        extracted = _document_extract_text({"path": path_raw, "max_chars": int(args.get("max_chars", 200000))})
        if not extracted.get("ok"):
            return extracted
        text = extracted.get("text") or ""
        if not text.strip():
            return _err("no text extracted; cannot ingest", path=path_raw)
        title = str(args.get("title") or Path(path_raw).name)
        return knowledge_executor("knowledge", {"action": "ingest", "title": title, "source": path_raw, "text": text})
    if action == "compare_documents":
        return _document_compare(args)
    return _err(
        "unknown document action", action=action,
        valid_actions=[
            "status", "extract_text", "extract_tables", "extract_images",
            "ocr_pdf", "summarize", "ingest_to_knowledge", "compare_documents",
        ],
        status="needs_user",
    )


def _document_extract_text(args: dict[str, Any]) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err("file not found", path=str(path))
    suffix = path.suffix.casefold()
    max_chars = int(args.get("max_chars", 200000))
    if suffix in {".txt", ".md", ".csv", ".log", ".py", ".ps1", ".yaml", ".yml", ".json"}:
        text = path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        return _ok(path=str(path), suffix=suffix, text=text, chars=len(text), backend="plain")
    if suffix in {".html", ".htm"}:
        return _document_extract_html(path, max_chars)
    if suffix == ".pdf":
        return _document_extract_pdf(path, max_chars)
    if suffix == ".docx":
        return _document_extract_docx(path, max_chars)
    if suffix == ".xlsx":
        return _document_extract_xlsx(path, max_chars)
    if suffix == ".pptx":
        return _document_extract_pptx(path, max_chars)
    return _err(f"unsupported extension: {suffix}", path=str(path))


def _document_extract_pdf(path: Path, max_chars: int) -> dict[str, Any]:
    if importlib.util.find_spec("pypdf") is None:
        return _err(
            "pypdf is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install pypdf",
        )
    from pypdf import PdfReader
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        return _err(f"failed to open PDF: {exc}", path=str(path))
    pages_text: list[str] = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            pages_text.append("")
    text = "\n\n".join(pages_text)
    truncated = len(text) > max_chars
    return _ok(
        path=str(path), suffix=".pdf", backend="pypdf",
        pages=len(reader.pages),
        text=text[:max_chars], chars=len(text), truncated=truncated,
    )


def _document_extract_docx(path: Path, max_chars: int) -> dict[str, Any]:
    if importlib.util.find_spec("docx") is None:
        return _err(
            "python-docx is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install python-docx",
        )
    from docx import Document
    try:
        doc = Document(str(path))
    except Exception as exc:
        return _err(f"failed to open DOCX: {exc}", path=str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text]
    text = "\n".join(paragraphs)
    truncated = len(text) > max_chars
    return _ok(
        path=str(path), suffix=".docx", backend="python-docx",
        paragraphs=len(paragraphs),
        text=text[:max_chars], chars=len(text), truncated=truncated,
    )


def _document_extract_xlsx(path: Path, max_chars: int) -> dict[str, Any]:
    if importlib.util.find_spec("openpyxl") is None:
        return _err(
            "openpyxl is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install openpyxl",
        )
    from openpyxl import load_workbook
    try:
        wb = load_workbook(str(path), read_only=True, data_only=True)
    except Exception as exc:
        return _err(f"failed to open XLSX: {exc}", path=str(path))
    sheets: list[dict[str, Any]] = []
    text_lines: list[str] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = ["" if cell is None else str(cell) for cell in row]
            rows.append(cells)
            text_lines.append(f"[{sheet_name}] " + " | ".join(cells))
            if len("\n".join(text_lines)) > max_chars:
                break
        sheets.append({"name": sheet_name, "rows": len(rows), "preview": rows[:5]})
        if len("\n".join(text_lines)) > max_chars:
            break
    text = "\n".join(text_lines)[:max_chars]
    return _ok(
        path=str(path), suffix=".xlsx", backend="openpyxl",
        sheets=sheets, sheet_count=len(sheets),
        text=text, chars=len(text),
    )


def _document_extract_pptx(path: Path, max_chars: int) -> dict[str, Any]:
    if importlib.util.find_spec("pptx") is None:
        return _err(
            "python-pptx is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install python-pptx",
        )
    from pptx import Presentation
    try:
        prs = Presentation(str(path))
    except Exception as exc:
        return _err(f"failed to open PPTX: {exc}", path=str(path))
    slides_text: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            # BaseShape doesn't declare `text`; only specific subclasses (placeholder,
            # autoshape) expose it. Probe with getattr to dodge the static type wall.
            shape_text = getattr(shape, "text", None)
            if shape_text:
                slides_text.append(str(shape_text))
    text = "\n\n".join(slides_text)
    truncated = len(text) > max_chars
    return _ok(
        path=str(path), suffix=".pptx", backend="python-pptx",
        slides=len(prs.slides),
        text=text[:max_chars], chars=len(text), truncated=truncated,
    )


def _document_extract_html(path: Path, max_chars: int) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if importlib.util.find_spec("bs4") is not None:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        title = soup.title.string if soup.title else None
        return _ok(path=str(path), suffix=".html", backend="beautifulsoup4", title=title, text=text[:max_chars], chars=len(text))
    # Fallback: strip tags with regex.
    text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return _ok(path=str(path), suffix=".html", backend="regex_fallback", text=text[:max_chars], chars=len(text), note="Install beautifulsoup4 for better extraction.")


def _document_extract_tables(args: dict[str, Any]) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err("file not found", path=str(path))
    suffix = path.suffix.casefold()
    if suffix == ".xlsx":
        return _document_extract_xlsx(path, max_chars=200000)
    if suffix == ".pdf":
        if importlib.util.find_spec("pdfplumber") is None:
            return _err(
                "pdfplumber is not installed",
                status="needs_dependency", verified=False,
                install_hint="python -m pip install pdfplumber",
            )
        import pdfplumber  # type: ignore[import-not-found]
        try:
            tables_out: list[dict[str, Any]] = []
            with pdfplumber.open(str(path)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_tables = page.extract_tables() or []
                    for tbl_idx, tbl in enumerate(page_tables):
                        tables_out.append({"page": page_idx + 1, "index": tbl_idx, "rows": len(tbl), "data": tbl[:200]})
            return _ok(path=str(path), suffix=".pdf", backend="pdfplumber", tables=tables_out, table_count=len(tables_out))
        except Exception as exc:
            return _err(f"pdfplumber failed: {exc}", path=str(path))
    return _err(f"extract_tables does not support {suffix}", supported=[".pdf", ".xlsx"])


def _document_extract_images(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err("file not found", path=str(path))
    suffix = path.suffix.casefold()
    out_dir = Path(str(args.get("out_dir") or state.path.parent / "extracted" / f"{_safe_name(path.stem)}_{int(time.time())}")).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []
    if suffix in {".docx", ".pptx", ".xlsx"}:
        # Office Open XML files are zip archives; media lives in word/media/, ppt/media/, xl/media/.
        try:
            with zipfile.ZipFile(path, "r") as archive:
                for entry in archive.infolist():
                    if "/media/" in entry.filename and not entry.is_dir():
                        target = out_dir / Path(entry.filename).name
                        with archive.open(entry) as src, target.open("wb") as dst:
                            shutil.copyfileobj(src, dst)
                        extracted.append(str(target))
        except (zipfile.BadZipFile, OSError) as exc:
            return _err(f"failed to read OOXML media: {exc}", path=str(path))
        return _ok(path=str(path), suffix=suffix, backend="ooxml_zip", out_dir=str(out_dir), images=extracted, count=len(extracted))
    if suffix == ".pdf":
        if importlib.util.find_spec("pypdf") is None:
            return _err("pypdf is not installed", status="needs_dependency", install_hint="python -m pip install pypdf")
        from pypdf import PdfReader
        try:
            reader = PdfReader(str(path))
            for page_idx, page in enumerate(reader.pages):
                for img_idx, img in enumerate(page.images):
                    target = out_dir / f"page{page_idx + 1}_img{img_idx + 1}_{img.name}"
                    target.write_bytes(img.data)
                    extracted.append(str(target))
        except Exception as exc:
            return _err(f"pypdf image extraction failed: {exc}", path=str(path))
        return _ok(path=str(path), suffix=".pdf", backend="pypdf", out_dir=str(out_dir), images=extracted, count=len(extracted))
    return _err(f"extract_images does not support {suffix}", supported=[".pdf", ".docx", ".pptx", ".xlsx"])


def _document_ocr_pdf(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err("PDF not found", path=str(path))
    if path.suffix.casefold() != ".pdf":
        return _err("ocr_pdf only accepts .pdf files", path=str(path))
    tesseract = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if not tesseract:
        return _err(
            "Tesseract OCR is not installed",
            status="needs_dependency", verified=False,
            install_hint="winget install UB-Mannheim.TesseractOCR",
        )
    # We need a backend to render PDF pages to PNG. pypdf does not render; we
    # need pdf2image+poppler OR PyMuPDF (fitz). Try fitz first (no external bin),
    # then pdf2image. If neither is available, return needs_dependency with the
    # full set of options.
    if importlib.util.find_spec("fitz") is not None:
        return _document_ocr_pdf_with_fitz(path, state, tesseract, args)
    if importlib.util.find_spec("pdf2image") is not None:
        return _document_ocr_pdf_with_pdf2image(path, state, tesseract, args)
    return _err(
        "PDF rendering requires PyMuPDF (fitz) or pdf2image+poppler",
        status="needs_dependency", verified=False,
        install_hint="python -m pip install PyMuPDF (preferred, no external binary needed)",
    )


def _document_ocr_pdf_with_fitz(path: Path, state: AgentState, tesseract: str, args: dict[str, Any]) -> dict[str, Any]:
    import fitz  # type: ignore[import-not-found]  # PyMuPDF
    lang = str(args.get("lang") or "spa+eng")
    out_dir = state.path.parent / "extracted" / f"ocr_{_safe_name(path.stem)}_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_text: list[str] = []
    try:
        doc = fitz.open(str(path))
        for idx in range(len(doc)):
            pix = doc[idx].get_pixmap(dpi=200)
            png_path = out_dir / f"page_{idx + 1}.png"
            pix.save(str(png_path))
            proc = subprocess.run([tesseract, str(png_path), "stdout", "-l", lang, "--psm", "6"], capture_output=True, text=True, timeout=60)
            pages_text.append(proc.stdout if proc.returncode == 0 else "")
    except Exception as exc:
        return _err(f"OCR failed: {exc}", path=str(path))
    text = "\n\n".join(pages_text)
    return _ok(
        path=str(path), backend="fitz+tesseract", out_dir=str(out_dir),
        pages=len(pages_text), text=text[: int(args.get("max_chars", 200000))], chars=len(text), lang=lang,
    )


def _document_ocr_pdf_with_pdf2image(path: Path, state: AgentState, tesseract: str, args: dict[str, Any]) -> dict[str, Any]:
    from pdf2image import convert_from_path
    lang = str(args.get("lang") or "spa+eng")
    out_dir = state.path.parent / "extracted" / f"ocr_{_safe_name(path.stem)}_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_text: list[str] = []
    try:
        images = convert_from_path(str(path), dpi=200)
        for idx, img in enumerate(images):
            png_path = out_dir / f"page_{idx + 1}.png"
            img.save(png_path, "PNG")
            proc = subprocess.run([tesseract, str(png_path), "stdout", "-l", lang, "--psm", "6"], capture_output=True, text=True, timeout=60)
            pages_text.append(proc.stdout if proc.returncode == 0 else "")
    except Exception as exc:
        return _err(f"OCR failed: {exc}", path=str(path), install_hint="pdf2image requires poppler; install with: winget install oschwartz10612.Poppler")
    text = "\n\n".join(pages_text)
    return _ok(
        path=str(path), backend="pdf2image+tesseract", out_dir=str(out_dir),
        pages=len(pages_text), text=text[: int(args.get("max_chars", 200000))], chars=len(text), lang=lang,
    )


def _document_compare(args: dict[str, Any]) -> dict[str, Any]:
    a_raw = str(args.get("a") or args.get("left") or "").strip()
    b_raw = str(args.get("b") or args.get("right") or "").strip()
    if not a_raw or not b_raw:
        return _err("compare_documents requires a/left and b/right paths")
    a = Path(a_raw).expanduser()
    b = Path(b_raw).expanduser()
    if not a.is_file() or not b.is_file():
        return _err("one or both documents not found", a=str(a), b=str(b))
    ta = _document_extract_text({"path": str(a), "max_chars": 500000})
    tb = _document_extract_text({"path": str(b), "max_chars": 500000})
    if not ta.get("ok"):
        return ta
    if not tb.get("ok"):
        return tb
    import difflib
    seq_a = (ta.get("text") or "").splitlines()
    seq_b = (tb.get("text") or "").splitlines()
    diff = list(difflib.unified_diff(seq_a, seq_b, fromfile=a.name, tofile=b.name, lineterm=""))
    similarity = difflib.SequenceMatcher(None, ta.get("text") or "", tb.get("text") or "").ratio()
    return _ok(
        a=str(a), b=str(b),
        a_chars=ta.get("chars", 0), b_chars=tb.get("chars", 0),
        similarity=round(similarity, 4),
        diff_lines=len(diff),
        diff_preview="\n".join(diff[:200]),
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


def _routine_task_name(label: str) -> str:
    return f"Gemma4Routine_{_safe_name(label)[:40]}_{int(time.time())}"


def _register_routine_scheduled_task(task_name: str, routine_label: str, trigger: dict[str, Any]) -> dict[str, Any]:
    """Register a Scheduled Task that invokes the routine_runner module.

    CC-100: python_exe / task_name / routine_label / arg_line se pasan por
    env-var; el script PS los referencia con $env:GEMMA4_* y nunca f-stringea
    valores controlados.
    """
    python_exe = _detect_python_executable()
    if not python_exe:
        return _err("no python executable found for scheduled task", status="needs_dependency", verified=False)
    trigger_ps = _build_routine_trigger_ps(trigger)
    if not trigger_ps:
        return _err(f"invalid routine trigger: {trigger}", trigger=trigger)
    # Validamos task_name contra el patrón que produce _routine_task_name.
    try:
        safe_task_name = ps_safe_literal(task_name, re.compile(r"^Gemma4Routine_[A-Za-z0-9_]+$"))
    except PSValidationError as exc:
        return _err(f"invalid task name: {exc}", task_name=task_name)
    env = {
        **os.environ,
        "GEMMA4_ROUTINE_TASK": safe_task_name,
        "GEMMA4_ROUTINE_PY": python_exe,
        "GEMMA4_ROUTINE_LABEL": routine_label,
    }
    ps = (
        "$exe = $env:GEMMA4_ROUTINE_PY\n"
        "$label = $env:GEMMA4_ROUTINE_LABEL\n"
        "$task = $env:GEMMA4_ROUTINE_TASK\n"
        "$labelEsc = $label -replace '\"', '\\\"'\n"
        "$argLine = ('-m gemma4_agent.routine_runner --label \"{0}\"' -f $labelEsc)\n"
        "$Action = New-ScheduledTaskAction -Execute $exe -Argument $argLine\n"
        f"$Trigger = {trigger_ps}\n"
        "$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable\n"
        "Register-ScheduledTask -TaskName $task -TaskPath '\\Gemma4Agent\\' -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null\n"
    )
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return _err("failed to register routine scheduled task", stderr=proc.stderr, exit_code=proc.returncode)
    return _ok(task_name=task_name, trigger=trigger)


def _unregister_routine_scheduled_task(task_name: str) -> dict[str, Any]:
    ps = f"Unregister-ScheduledTask -TaskPath '\\Gemma4Agent\\' -TaskName '{_ps_quote(task_name)}' -Confirm:$false -ErrorAction SilentlyContinue"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=20)
    return {"task_name": task_name, "exit_code": proc.returncode, "stderr": proc.stderr}


def _build_routine_trigger_ps(trigger: dict[str, Any]) -> str | None:
    """Translate a trigger dict into the PowerShell expression for the trigger.

    CC-100 / T3-routine-cron-trigger-ps-injection-028: cualquier valor que se
    interpole en el script PS debe pasar por allowlist regex. Si no encaja,
    devolvemos None (el caller surface como error de validación).
    """
    ttype = str(trigger.get("type") or "manual").casefold()
    if ttype == "manual":
        return None
    if ttype == "once":
        at_raw = str(trigger.get("at") or "").strip()
        if not at_raw:
            return None
        try:
            at = ps_safe_literal(at_raw, RX_ISO_DATETIME)
        except PSValidationError:
            return None
        return f"New-ScheduledTaskTrigger -Once -At (Get-Date '{at}')"
    if ttype == "cron":
        cadence = str(trigger.get("cadence") or trigger.get("every") or "daily").casefold()
        at_raw = str(trigger.get("at") or "09:00").strip()
        try:
            at = ps_safe_literal(at_raw, RX_HHMM)
        except PSValidationError:
            return None
        if cadence == "daily":
            return f"New-ScheduledTaskTrigger -Daily -At '{at}'"
        if cadence == "weekly":
            raw_days = trigger.get("days_of_week")
            days_iter: list[Any] = raw_days if isinstance(raw_days, list) else ["Monday"]
            safe_days: list[str] = []
            for d in days_iter:
                try:
                    safe_days.append(ps_safe_literal(str(d), RX_DAY_OF_WEEK))
                except PSValidationError:
                    return None
            if not safe_days:
                return None
            days_str = ",".join(safe_days)
            return f"New-ScheduledTaskTrigger -Weekly -DaysOfWeek {days_str} -At '{at}'"
        if cadence == "hourly":
            return f"New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)"
        if cadence == "minutes":
            try:
                n = int(trigger.get("interval_minutes", 5))
            except (TypeError, ValueError):
                return None
            if n <= 0:
                return None
            return f"New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes {n})"
    return None


def _detect_python_executable() -> str | None:
    import sys
    candidate = sys.executable
    if candidate and Path(candidate).is_file():
        return candidate
    for name in ("python.exe", "python3.exe", "python", "python3"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _enrich_routine_resource(resource: dict[str, Any]) -> dict[str, Any]:
    """Add live ScheduledTask info if the routine has a task_name."""
    metadata = resource.get("metadata") or {}
    task_name = str(metadata.get("task_name") or "").strip()
    if not task_name:
        return resource
    script = (
        f"$t = Get-ScheduledTask -TaskPath '\\Gemma4Agent\\' -TaskName '{_ps_quote(task_name)}' -ErrorAction SilentlyContinue; "
        f"if ($t) {{ "
        f"  $info = $t | Get-ScheduledTaskInfo; "
        f"  [PSCustomObject]@{{ State=$t.State.ToString(); LastRunTime=$info.LastRunTime; NextRunTime=$info.NextRunTime; LastTaskResult=$info.LastTaskResult }} | ConvertTo-Json -Depth 3 "
        f"}}"
    )
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=15)
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            data = json.loads(proc.stdout)
            if isinstance(data, dict):
                resource = dict(resource)
                resource["scheduled_task_info"] = data
        except json.JSONDecodeError:
            pass
    return resource


def _append_routine_run(state: AgentState, resource_id: str, run_record: dict[str, Any]) -> None:
    # CC-102: atomic append con cap a 50 entries.
    state.update_resource_metadata(
        resource_id,
        {"history": [run_record], "last_run": run_record},
        append_lists=("history",),
        max_append=50,
    )


def _routine_history(state: AgentState, routine: dict[str, Any] | None, *, limit: int = 20) -> dict[str, Any]:
    if routine:
        history = list((routine.get("metadata") or {}).get("history") or [])
        return _ok(routine_id=routine.get("id"), label=routine.get("label"), history=history[-limit:], count=len(history))
    # All routines
    out = []
    for res in state._load().get("resources", {}).values():
        if res.get("kind") != "routine":
            continue
        last = (res.get("metadata") or {}).get("last_run")
        if last:
            out.append({"routine_id": res.get("id"), "label": res.get("label"), "last_run": last})
    return _ok(runs=out, count=len(out))


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
# Cada plataforma tiene:
#   web_url: URL a abrir en el browser.
#     - Si web_search_via_url=True: la URL incluye {q} con la query.
#     - Si web_search_via_url=False: web_url es solo el home; la query se
#       escribe via GUI usando search_shortcut.
#   web_search_via_url: True/False (URL con query funciona o no).
#   search_shortcut: tecla(s) para abrir el campo de busqueda (solo se usa
#     si web_search_via_url=False).
#
# URLs verificadas 2026-05-15 (curl + HTTP HEAD):
#   netflix.com/search?q=X       -> 200 (login redirect, pero acepta query)
#   primevideo.com/search/.../?phrase=X -> 200
#   disneyplus.com/search?q=X    -> 404 (URL no existe)
#   max.com/search?q=X           -> 404 (rebrand HBO Max -> Max, URL movio)
#   open.spotify.com/search/X    -> 200
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
        "search_shortcut": None,  # tiene deeplink, no necesita
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
        "deeplink": None,  # Netflix UWP no expone deeplink de busqueda confiable
        "web_url": "https://www.netflix.com/search?q={q}",
        "web_search_via_url": True,  # URL con ?q= funciona post-login
        "search_shortcut": None,
        "install_hint": "Install Netflix from Microsoft Store: ms-windows-store://pdp/?productid=9wzdncrfj3tj",
        "post_open_note": (
            "Netflix opened with search results. Requires login. "
            "User clicks the title to start playback."
        ),
    },
    "disney": {
        "aliases": {"disney", "disney+", "disneyplus", "disney_plus", "disney plus"},
        "uwp_pfn": "Disney.37853FC22B2CE_6rarf9sa4v8jt",
        "exe_paths": [],
        "deeplink": None,
        # Disney+ NO soporta query via URL — el ?q= devuelve 404. Abrimos
        # home (es-419 locale para que funcione en LATAM) y usamos GUI
        # shortcut "s" para abrir la busqueda + type query.
        "web_url": "https://www.disneyplus.com/es-419/home",
        "web_search_via_url": False,
        "search_shortcut": "s",  # Disney+ usa 's' para abrir search
        "install_hint": "Install Disney+ from Microsoft Store: ms-windows-store://pdp/?productid=9NXQXXLFST89",
        "post_open_note": (
            "Disney+ opened. Use the search bar to find content."
        ),
    },
    "hbo_max": {
        # Rebrand: HBO Max -> Max (2023). Pero el dominio actual es
        # hbomax.com (redirige a play.max.com cuando estas logueado).
        "aliases": {"hbo_max", "hbo max", "hbomax", "max", "hbo"},
        "uwp_pfn": None,  # Max no tiene UWP oficial en Windows
        "exe_paths": [],
        "deeplink": None,
        "web_url": "https://www.hbomax.com/",  # redirige a play.max.com si logueado
        "web_search_via_url": False,
        "search_shortcut": "/",  # Max usa '/' como Netflix
        "install_hint": "Max is web-only on Windows (no native app); browser will open.",
        "post_open_note": (
            "Max (formerly HBO Max) opened. Use search to find content."
        ),
    },
    "prime_video": {
        "aliases": {"prime_video", "prime video", "primevideo", "amazon prime",
                     "amazon_prime", "amazon", "prime"},
        "uwp_pfn": "AmazonVideo.PrimeVideo_pwbj9vvecjh7j",
        "exe_paths": [],
        "deeplink": None,
        "web_url": "https://www.primevideo.com/search/ref=atv_nb_sr?phrase={q}",
        "web_search_via_url": True,
        "search_shortcut": None,
        "install_hint": "Install Prime Video from Microsoft Store: ms-windows-store://pdp/?productid=9P6RC76MSMMJ",
        "post_open_note": (
            "Prime Video opened with search results. Requires login. "
            "User clicks the title to start playback."
        ),
    },
}


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


def _streaming_web_auto_play(
    executor: Executor,
    canonical: str,
    query: str,
    profile_name: str,
    wait_seconds: float,
    *,
    search_shortcut: str | None = None,
    needs_gui_search: bool = False,
) -> dict[str, Any]:
    """Para web streaming: abre la pagina + opcionalmente activa search +
    intenta navigation por teclado para llegar al primer resultado.

    DESIGN PRAGMATICO (2026-05-16): el approach anterior (OCR + click_text
    sobre la grilla de resultados) fallaba el 90% del tiempo porque los
    pósters son IMAGENES sin texto OCR-able. Cambio a estrategia de
    keyboard navigation universal:
      1. Wait carga.
      2. Si needs_gui_search: activate search via shortcut + type + Enter.
      3. Wait resultados.
      4. Press Tab varias veces (3-5) para mover focus a primer titulo.
      5. Press Enter para entrar.
      6. Wait detail.
      7. Press Tab algunas veces para llegar al Play button + Enter.

    Esto NO garantiza play 100%, pero es mas confiable que OCR. El user
    queda en la pagina de resultados/detalle si algun paso falla; un
    click manual completa la accion.

    Returns dict con steps + player_started=bool + abort_reason.
    """
    import time as _time
    steps: list[str] = []
    _time.sleep(max(1.0, wait_seconds))
    steps.append(f"waited_for_page:{wait_seconds}s")

    # 1. Profile picker. Intentar click_text del nombre (esto sigue siendo
    # OCR fragil pero los nombres de perfil suelen ser TEXTO renderizado,
    # no imagen). Si falla, seguir sin error porque puede que ya estemos
    # en el home.
    try:
        click_profile = executor("gui", {
            "action": "click_text", "target": profile_name,
            "timeout_sec": 4,
        })
        if click_profile.get("ok") and click_profile.get("found"):
            steps.append(f"clicked_profile:{profile_name}")
            _time.sleep(3.0)  # carga post-profile (puede ser lenta)
        else:
            steps.append("no_profile_picker_or_not_found")
    except Exception:
        steps.append("profile_click_error")

    # 2. Activar search si needed.
    if needs_gui_search and search_shortcut:
        try:
            executor("gui", {"action": "keypress", "keys": search_shortcut})
            steps.append(f"pressed_search_shortcut:{search_shortcut}")
            _time.sleep(1.2)  # mas tiempo para que aparezca el input
            executor("gui", {"action": "type", "text": query})
            steps.append(f"typed_query:{query}")
            _time.sleep(0.8)
            # NO press Enter en Disney+/Max: el filtro se aplica mientras
            # tipeas. Press Enter va al detail de la primera coincidencia
            # AUTOMATICAMENTE en algunas plataformas, en otras navega a
            # otra cosa. Es safer dejarlo y usar Tab navigation despues.
            _time.sleep(3.0)  # mas tiempo para que renderice resultados
            steps.append("waited_for_search_results")
        except Exception as exc:
            return {
                "player_started": False, "steps": steps,
                "abort_reason": f"gui search via shortcut failed: {exc}",
            }
    else:
        # URL ya tiene search query — esperar mas tiempo a que renderice
        # post-load (Netflix puede tardar 3-5s en pintar la grilla).
        _time.sleep(3.0)
        steps.append("waited_for_url_search_results")

    # 3. Keyboard navigation: Tab al primer titulo + Enter.
    # Cada plataforma tiene un layout distinto. Estos defaults son
    # observados empiricamente; podemos parametrizarlos por plataforma
    # si una falla consistente.
    # Netflix con ?q=:    Tab x 5-7 para llegar al primer poster
    # Disney+ post-search: Tab x 4-6 (search box esta enfocado, salimos)
    # Max/HBO:           similar
    # Prime Video:       Tab x 6-8 (mas chrome arriba)
    tab_count_by_platform = {
        "netflix": 6,
        "disney": 5,
        "hbo_max": 6,
        "prime_video": 7,
    }
    tabs_to_first_result = tab_count_by_platform.get(canonical, 6)

    try:
        for i in range(tabs_to_first_result):
            executor("gui", {"action": "keypress", "keys": "tab"})
            _time.sleep(0.15)
        steps.append(f"tabbed_to_first_result:x{tabs_to_first_result}")
        _time.sleep(0.3)
        executor("gui", {"action": "keypress", "keys": "enter"})
        steps.append("entered_first_result")
        _time.sleep(3.5)  # detail page tarda en cargar
    except Exception as exc:
        return {
            "player_started": False, "steps": steps,
            "abort_reason": f"tab navigation to first result failed: {exc}",
            "note": "Open the page manually and click the title.",
        }

    # 4. En la detail page, intentar Play. Estrategia hybrida:
    #    (a) Tab navigation al Play button (suele ser focusable temprano).
    #    (b) Si OCR encuentra Play text, click directo.
    # Netflix: Play button suele estar en Tab x 1-3.
    # Disney+: similar.
    play_tab_count = 3
    try:
        for i in range(play_tab_count):
            executor("gui", {"action": "keypress", "keys": "tab"})
            _time.sleep(0.15)
        executor("gui", {"action": "keypress", "keys": "enter"})
        steps.append(f"tabbed_to_play_button:x{play_tab_count} + Enter")
        _time.sleep(1.0)
    except Exception as exc:
        steps.append(f"play_tab_nav_error:{exc}")

    # HONESTIDAD: no podemos verificar visualmente sin OCR/vision check
    # (que fue justamente lo que fallaba antes). El return marca
    # `attempted_play=True` para que el reply diga "intenté reproducir"
    # en vez de "no pude reproducir". El user verifica visualmente.
    # player_started=False porque NO tenemos evidencia objetiva de play.
    return {
        "player_started": False,
        "attempted_play": True,  # nuevo: distingue "intente" de "no pude"
        "steps": steps,
        "abort_reason": None,
        "verification_note": (
            "Tab navigation + Enter dispatched. Cannot verify playback "
            "started without OCR/vision check. User confirms visually."
        ),
    }


def _spotify_auto_play(executor: Executor, wait_seconds: float) -> dict[str, Any]:
    """Tras enviar spotify:search:<q>, esperar carga, focus + verify ventana
    Spotify, y mandar Enter para reproducir el primer resultado.

    Spotify Desktop al recibir el deeplink muestra resultados de busqueda
    con la primera fila (track top) seleccionada. Un Enter reproduce
    ese track.

    Returns dict con keys:
      - played: bool
      - focus_verified: bool
      - abort_reason: str | None
      - wait_seconds: float
    """
    import time as _time
    _time.sleep(max(0.5, wait_seconds))
    try:
        executor("window", {"action": "focus", "title": "Spotify"})
    except Exception as exc:
        return {
            "played": False, "focus_verified": False,
            "abort_reason": f"focus call failed: {exc}",
            "wait_seconds": wait_seconds,
        }
    _time.sleep(0.3)
    try:
        active = executor("window", {"action": "active"})
    except Exception as exc:
        return {
            "played": False, "focus_verified": False,
            "abort_reason": f"active check failed: {exc}",
            "wait_seconds": wait_seconds,
        }
    active_title = ""
    a = active.get("active")
    if isinstance(a, dict):
        active_title = str(a.get("title") or "")
    else:
        active_title = str(active.get("title") or "")
    if "spotify" not in active_title.lower():
        return {
            "played": False, "focus_verified": False,
            "abort_reason": (
                f"active window is {active_title!r}, not Spotify. "
                "Refusing to press Enter on a different app."
            ),
            "wait_seconds": wait_seconds,
        }
    try:
        keypress_result = executor("gui", {"action": "keypress", "keys": "enter"})
    except Exception as exc:
        return {
            "played": False, "focus_verified": True,
            "abort_reason": f"keypress failed: {exc}",
            "wait_seconds": wait_seconds,
        }
    if not keypress_result.get("ok"):
        return {
            "played": False, "focus_verified": True,
            "abort_reason": f"keypress returned: {keypress_result.get('error', 'unknown')}",
            "wait_seconds": wait_seconds,
        }
    return {
        "played": True, "focus_verified": True,
        "abort_reason": None,
        "wait_seconds": wait_seconds,
        "active_window_title": active_title,
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
    if web_search_via_url and "{q}" in spec["web_url"]:
        web_url = spec["web_url"].format(q=encoded)
    else:
        web_url = spec["web_url"]
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
                auto_play_info = _spotify_auto_play(executor, auto_play_wait)
            played = bool(auto_play_info and auto_play_info.get("played"))
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
                verified=played,
                status="dispatched" if played else "attempted",
                completion_status="media_playing" if played
                                   else "opened_search_results_pending_play",
                note=(
                    f"{canonical}: playing — Spotify focused, Enter pressed on first result."
                    if played else note
                ),
            )

    # PATH 2/3: no app o no deeplink -> abrir web URL (browser default).
    # Esto siempre funciona si hay browser default. La app instalada-sin-deeplink
    # podemos mencionarla en el note pero abrir web es el camino mas fiable
    # porque lleva al user directamente al resultado de busqueda.
    try:
        import webbrowser
        opened = webbrowser.open(web_url)
        if opened:
            # WEB AUTO-PLAY: si tenemos executor + auto_play + profile_name,
            # intentar el flujo GUI (search + tab navigation + Enter).
            # Best-effort: el flow llega cerca del play pero no garantiza
            # que el video haya empezado (sin OCR/vision check confiable).
            # El reply del LLM debe distinguir attempted_play vs played_verified.
            web_auto_play_info: dict[str, Any] | None = None
            played = False
            attempted_play = False
            if auto_play and executor is not None and profile_name:
                web_auto_play_info = _streaming_web_auto_play(
                    executor, canonical, query, profile_name, auto_play_wait,
                    search_shortcut=spec.get("search_shortcut"),
                    needs_gui_search=not web_search_via_url,
                )
                played = bool(web_auto_play_info.get("player_started"))
                attempted_play = bool(web_auto_play_info.get("attempted_play"))
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
                note=(
                    f"{canonical}: playing — Profile '{profile_name}', "
                    "title clicked, Play pressed."
                    if played else
                    f"{canonical}: search + Tab navigation + Enter dispatched "
                    f"with profile '{profile_name}'. The video MAY be playing "
                    "now — verify visually. If not, click the title manually."
                    if attempted_play else note
                ),
            )
            if app_info["kind"]:
                # Avisamos que la app esta pero no la usamos por falta de deeplink.
                result["app_available_but_no_deeplink"] = True
                result["app_kind"] = app_info["kind"]
            return result
    except Exception as exc:
        return _err(
            f"Could not open {canonical} (no app deeplink and webbrowser failed): {exc}",
            provider=canonical, status="failed",
        )
    return _err(
        f"{canonical}: no native deeplink and default browser refused to open.",
        provider=canonical, status="needs_user",
        install_hint=install_hint,
    )


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
        profile_name=profile_name,
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
_EMAIL_BASIC_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_BASIC_RE = re.compile(r"^[\d\s\-\+\(\)]+$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _clean_contact_field(value: Any) -> str | None:
    """Normaliza un campo de contacto: strip + drop control chars + tipo str.
    Devuelve None si el valor es vacio o no convertible."""
    if value is None:
        return None
    s = _CONTROL_CHARS_RE.sub("", str(value)).strip()
    return s or None


def contacts_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(local_state=True, count=len(_resources_by_kind(state, "contact")))
    if action == "list":
        return _ok(contacts=_resources_by_kind(state, "contact", include_closed=bool(args.get("include_closed", False))))
    if action in {"create", "add"}:
        name = _clean_contact_field(args.get("name"))
        if not name:
            return _err("missing contact name", status="needs_user")
        email = _clean_contact_field(args.get("email"))
        phone = _clean_contact_field(args.get("phone"))
        notes = _clean_contact_field(args.get("notes"))
        # VALIDACION laxa de formato: si el LLM pasa email=123 o phone="abc",
        # devolvemos status=needs_user con el motivo. NO rechazamos formatos
        # no convencionales (internacionales, extensiones) — solo lo
        # claramente roto.
        if email and not _EMAIL_BASIC_RE.match(email):
            return _err(
                f"invalid email format: {email!r}",
                hint="expected user@host.tld; omit field to skip", status="needs_user",
            )
        if phone and not _PHONE_BASIC_RE.match(phone):
            return _err(
                f"invalid phone format: {phone!r}",
                hint="digits + (space/dash/+/parens) only; use _vcard for international formats",
                status="needs_user",
            )
        # CHEQUEO UNICIDAD: contactos con mismo nombre ya existentes generan
        # un warning explicito (no rechazo) para que el LLM decida que hacer.
        existing = [
            c for c in _resources_by_kind(state, "contact", include_closed=False)
            if (c.get("metadata") or {}).get("name", "").strip().casefold() == name.casefold()
        ]
        resource = state.register_resource(
            "contact", name,
            metadata={
                "name": name, "email": email, "phone": phone, "notes": notes,
                "created_at": datetime.now().isoformat(),
            },
        )
        out = _ok(contact=resource.get("resource"))
        if existing:
            out["duplicate_warning"] = {
                "count": len(existing),
                "existing_ids": [c.get("id") for c in existing[:5]],
                "note": (
                    "A contact with the same name already exists. Use action=update "
                    "instead if you want to modify it, or proceed with create for a "
                    "separate entry."
                ),
            }
        return out
    if action == "search":
        query = (_clean_contact_field(args.get("query") or args.get("name")) or "").casefold()
        if not query:
            return _err("missing query/name", status="needs_user")
        try:
            limit = max(1, min(int(args.get("limit", 10)), 100))
        except (TypeError, ValueError):
            limit = 10
        # MATCHING ESTRUCTURADO: en vez de JSON-blob substring (que matchea
        # ids, timestamps, basura), comparar contra los campos del metadata
        # de forma explicita.
        matches: list[dict[str, Any]] = []
        for c in _resources_by_kind(state, "contact", include_closed=True):
            meta = c.get("metadata") or {}
            haystacks = [
                str(meta.get("name") or ""),
                str(meta.get("email") or ""),
                str(meta.get("phone") or ""),
                str(meta.get("notes") or ""),
                str(c.get("label") or ""),
            ]
            if any(query in h.casefold() for h in haystacks):
                matches.append(c)
        return _ok(matches=matches[:limit], count=len(matches), query=query)
    if action == "delete":
        contact = _find_resource(args, state, "contact")
        if not contact:
            return _err("contact not found", status="needs_user")
        return state.mark_cleaned(str(contact["id"]), {"deleted": True})
    if action == "update":
        return _contacts_update(args, state)
    if action == "export_vcard":
        return _contacts_export_vcard(args, state)
    if action == "import_vcard":
        return _contacts_import_vcard(args, state)
    if action == "resolve_recipient":
        return _contacts_resolve_recipient(args, state)
    return _err(
        "unknown contacts action", action=action,
        valid_actions=[
            "status", "list", "create", "add", "search", "delete", "update",
            "export_vcard", "import_vcard", "resolve_recipient",
        ],
        status="needs_user",
    )


def _contacts_update(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    contact = _find_resource(args, state, "contact")
    if not contact:
        return _err("contact not found")
    updates: dict[str, Any] = {}
    for key in ("name", "email", "phone", "notes"):
        if key in args and args[key] is not None:
            updates[key] = args[key]
    if not updates:
        return _err("no updatable fields provided", supported=["name", "email", "phone", "notes"])
    if "name" in updates:
        state.update_resource(str(contact["id"]), label=str(updates["name"]))
    return _update_resource_metadata(state, str(contact["id"]), updates)


def _contacts_export_vcard(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    contacts = _resources_by_kind(state, "contact", include_closed=False)
    if not contacts:
        return _err("no contacts to export", status="needs_user")
    path_raw = str(args.get("path") or "").strip()
    if path_raw:
        path = Path(path_raw).expanduser()
    else:
        path = state.path.parent / "generated" / f"contacts_{time.strftime('%Y%m%d_%H%M%S')}.vcf"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _err("cannot create export directory", path=str(path.parent), reason=str(exc))
    body = "\r\n".join(_contact_to_vcard(c) for c in contacts) + "\r\n"
    try:
        path.write_text(body, encoding="utf-8")
    except (PermissionError, OSError) as exc:
        return _err(
            "vcard write failed", path=str(path), reason=str(exc),
            status="needs_user" if isinstance(exc, PermissionError) else "failed",
        )
    # VERIFICACION post-write.
    try:
        size = path.stat().st_size
    except OSError:
        size = -1
    if size != len(body.encode("utf-8")):
        return _err(
            "vcard write incomplete", path=str(path),
            expected_bytes=len(body.encode("utf-8")), actual_bytes=size,
            status="failed",
        )
    return _ok(path=str(path.resolve()), exported=len(contacts), bytes=size, verified=True)


def _contact_to_vcard(contact: dict[str, Any]) -> str:
    meta = contact.get("metadata") or {}
    name = str(meta.get("name") or contact.get("label") or "")
    email = str(meta.get("email") or "")
    phone = str(meta.get("phone") or "")
    notes = str(meta.get("notes") or "")
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{_vcard_escape(name)}", f"N:{_vcard_escape(name)};;;;"]
    if email:
        lines.append(f"EMAIL:{_vcard_escape(email)}")
    if phone:
        lines.append(f"TEL:{_vcard_escape(phone)}")
    if notes:
        lines.append(f"NOTE:{_vcard_escape(notes)}")
    lines.append("END:VCARD")
    return "\r\n".join(lines)


def _vcard_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _vcard_unescape(text: str) -> str:
    return text.replace("\\,", ",").replace("\\;", ";").replace("\\n", "\n").replace("\\N", "\n").replace("\\\\", "\\")


def _contacts_import_vcard(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    path_raw = str(args.get("path") or args.get("file") or "").strip()
    text = str(args.get("content") or args.get("vcard") or "")
    if path_raw:
        p = Path(path_raw).expanduser()
        if not p.is_file():
            return _err("vCard file not found", path=str(p))
        text = p.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return _err("no vCard content provided")
    cards = _vcard_parse(text)
    if not cards:
        return _err("no VCARD blocks found")
    created = []
    for card in cards:
        name = card.get("fn") or card.get("n") or "Contact"
        resource = state.register_resource(
            "contact",
            name,
            metadata={
                "name": name,
                "email": card.get("email"),
                "phone": card.get("tel"),
                "notes": card.get("note"),
                "imported_from": path_raw or "<inline>",
                "created_at": datetime.now().isoformat(),
            },
        )
        created.append(resource.get("resource"))
    return _ok(imported=len(created), contacts=created[:50], total_parsed=len(cards))


def _vcard_parse(text: str) -> list[dict[str, Any]]:
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in raw_lines:
        if unfolded and (line.startswith(" ") or line.startswith("\t")):
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    cards: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in unfolded:
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if upper == "BEGIN:VCARD":
            current = {}
            continue
        if upper == "END:VCARD":
            if current is not None:
                cards.append(current)
            current = None
            continue
        if current is None:
            continue
        sep = stripped.find(":")
        if sep < 0:
            continue
        head, value = stripped[:sep], stripped[sep + 1:]
        name = head.split(";", 1)[0].upper()
        value = _vcard_unescape(value)
        if name == "FN":
            current["fn"] = value
        elif name == "N":
            # N: Family;Given;Additional;Prefix;Suffix
            parts = value.split(";")
            given = parts[1] if len(parts) > 1 else ""
            family = parts[0] if parts else ""
            current["n"] = (given + " " + family).strip() or value
        elif name == "EMAIL":
            current.setdefault("email", value)
        elif name == "TEL":
            current.setdefault("tel", value)
        elif name == "NOTE":
            current["note"] = value
    return cards


def _contacts_resolve_recipient(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    query = str(args.get("query") or args.get("name") or args.get("recipient") or "").strip()
    if not query:
        return _err("missing query")
    q = query.casefold()
    contacts = _resources_by_kind(state, "contact", include_closed=False)
    scored: list[tuple[int, dict[str, Any]]] = []
    for c in contacts:
        meta = c.get("metadata") or {}
        name = str(meta.get("name") or c.get("label") or "").casefold()
        email = str(meta.get("email") or "").casefold()
        phone = str(meta.get("phone") or "").casefold()
        score = 0
        if q == name:
            score += 100
        elif q in name:
            score += 50
        if q == email:
            score += 90
        elif q in email:
            score += 40
        if q == phone:
            score += 80
        elif q in phone:
            score += 30
        if score:
            scored.append((score, c))
    scored.sort(key=lambda t: -t[0])
    matches = [{"contact": c, "score": s} for s, c in scored[: int(args.get("limit", 5))]]
    return _ok(query=query, matches=matches, count=len(matches), best=matches[0] if matches else None)


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


def _whatsapp_send_via_gui_search(
    executor: Executor,
    contact_name: str,
    text: str,
    wait_seconds: float,
    auto_send: bool,
) -> dict[str, Any]:
    """Abre WhatsApp generico, busca el contacto por nombre via Ctrl+F,
    selecciona el primer match, escribe el mensaje y opcionalmente envia.

    Flujo (todos los pasos requieren focus verification antes de teclear):
      1. Dispatch whatsapp:// (sin args -> abre la app generica).
      2. Wait wait_seconds para que cargue.
      3. Focus WhatsApp + verify active window title.
      4. Ctrl+F (abre el campo de busqueda) o type direct si el campo ya esta.
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

    def _focus_and_verify() -> bool:
        # window.focus ahora hace restore + maximize si la ventana es chica
        # (regla universal aplicada en tools.py:window_control). Damos grace
        # de 0.5s para que el maximize tome efecto antes de verificar.
        try:
            executor("window", {"action": "focus", "title": "WhatsApp"})
        except Exception:
            return False
        _time.sleep(0.5)
        try:
            active = executor("window", {"action": "active"})
        except Exception:
            return False
        active_title = ""
        a = active.get("active")
        if isinstance(a, dict):
            active_title = str(a.get("title") or "")
        else:
            active_title = str(active.get("title") or "")
        return "whatsapp" in active_title.lower()

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
        }
    steps.append("dispatched_deeplink")
    _time.sleep(max(0.5, wait_seconds))

    # 2. Focus + verify (incluye restore+maximize implicito).
    if not _focus_and_verify():
        return {
            "sent": False, "chat_opened": False, "search_term": contact_name,
            "abort_reason": "could not focus WhatsApp window after launch",
            "steps": steps,
        }
    steps.append("focused")
    # Extra grace tras maximize — el window manager necesita repaint.
    _time.sleep(0.4)

    # 3. Ctrl+F para abrir busqueda. WhatsApp Desktop usa Ctrl+F.
    # IMPORTANTE: pasar keys="^f" (SendKeys syntax) o keys="ctrl+f" que el
    # translator convierte. Antes pasabamos hotkey="ctrl+f" pero el handler
    # no traducia "ctrl+f" -> "^f" y SendKeys lo enviaba LITERAL como texto.
    try:
        executor("gui", {"action": "keypress", "keys": "ctrl+f"})
    except Exception as exc:
        return {
            "sent": False, "chat_opened": False, "search_term": contact_name,
            "abort_reason": f"hotkey ctrl+f failed: {exc}", "steps": steps,
        }
    steps.append("opened_search")
    _time.sleep(0.6)

    # 4. Type del nombre del contacto.
    if not _focus_and_verify():
        return {
            "sent": False, "chat_opened": False, "search_term": contact_name,
            "abort_reason": "lost WhatsApp focus before typing contact name",
            "steps": steps,
        }
    try:
        executor("gui", {"action": "type", "text": contact_name})
    except Exception as exc:
        return {
            "sent": False, "chat_opened": False, "search_term": contact_name,
            "abort_reason": f"type contact name failed: {exc}", "steps": steps,
        }
    steps.append("typed_contact_name")
    _time.sleep(1.0)  # tiempo para que WhatsApp filtre

    # 5. Enter para seleccionar primer resultado y entrar al chat.
    if not _focus_and_verify():
        return {
            "sent": False, "chat_opened": False, "search_term": contact_name,
            "abort_reason": "lost WhatsApp focus before selecting contact",
            "steps": steps,
        }
    try:
        executor("gui", {"action": "keypress", "keys": "enter"})
    except Exception as exc:
        return {
            "sent": False, "chat_opened": False, "search_term": contact_name,
            "abort_reason": f"enter to select contact failed: {exc}", "steps": steps,
        }
    steps.append("selected_first_match")
    _time.sleep(0.8)  # entrar al chat

    # 6. Type del mensaje (focus moved al input del chat).
    if not text:
        # open_chat: solo queriamos llegar al chat, no mandar.
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": None, "steps": steps,
        }
    if not _focus_and_verify():
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": "lost WhatsApp focus before typing message",
            "steps": steps,
        }
    try:
        executor("gui", {"action": "type", "text": text})
    except Exception as exc:
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": f"type message failed: {exc}", "steps": steps,
        }
    steps.append("typed_message")
    _time.sleep(0.4)

    # 7. Enviar si auto_send.
    if not auto_send:
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": None, "steps": steps,
        }
    if not _focus_and_verify():
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": "lost WhatsApp focus before sending",
            "steps": steps,
        }
    try:
        executor("gui", {"action": "keypress", "keys": "enter"})
    except Exception as exc:
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": f"enter to send failed: {exc}", "steps": steps,
        }
    steps.append("sent_enter")
    return {
        "sent": True, "chat_opened": True, "search_term": contact_name,
        "abort_reason": None, "steps": steps,
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


def notes_tasks_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(notes=len(_resources_by_kind(state, "note")), tasks=len(_resources_by_kind(state, "task")))
    if action in {"note_create", "create_note"}:
        title = str(args.get("title") or "").strip() or "Nota"
        text = str(args.get("text") or args.get("content") or "").strip()
        # WARNING (no error) si la nota es vacia. La nota se crea igual pero
        # el LLM ve que algo raro pasa y puede corregir en el siguiente turn.
        if not text and title == "Nota":
            return _err(
                "note_create needs at least title or text",
                hint="pass title='...' or text='...'", status="needs_user",
            )
        resource = state.register_resource("note", title, metadata={"title": title, "text": text, "tags": args.get("tags"), "created_at": datetime.now().isoformat()})
        out = _ok(note=resource.get("resource"))
        if not text:
            out["warning"] = "note created with empty text"
        return out
    if action in {"task_create", "create_task"}:
        title = str(args.get("title") or args.get("text") or "").strip()
        if not title:
            return _err(
                "task_create requires title or text", status="needs_user",
            )
        due_raw = args.get("due")
        due_iso, due_err = _parse_due_iso(due_raw)
        if due_err:
            return _err(due_err, value=due_raw, status="needs_user")
        resource = state.register_resource(
            "task", title,
            metadata={
                "title": title, "text": args.get("text"),
                "due": due_iso, "status": "open",
                "created_at": datetime.now().isoformat(),
            },
        )
        return _ok(task=resource.get("resource"))
    if action in {"note_list", "notes", "list"}:
        return _ok(notes=_resources_by_kind(state, "note", include_closed=bool(args.get("include_closed", False))))
    if action in {"task_list", "tasks"}:
        return _ok(tasks=_resources_by_kind(state, "task", include_closed=bool(args.get("include_closed", False))))
    if action in {"note_search", "task_search", "search"}:
        kinds = ["note", "task"] if action == "search" else ["note"] if action.startswith("note") else ["task"]
        query = str(args.get("query") or "").strip().casefold()
        if not query:
            return _err("missing query", status="needs_user")
        try:
            limit = max(1, min(int(args.get("limit", 10)), 100))
        except (TypeError, ValueError):
            limit = 10
        # MATCHING ESTRUCTURADO en campos relevantes (title/text/tags), no
        # sobre el JSON entero (que incluye ids, timestamps).
        matches: list[dict[str, Any]] = []
        for r in _resources_by_kind(state, kinds, include_closed=True):
            meta = r.get("metadata") or {}
            haystacks = [
                str(meta.get("title") or ""),
                str(meta.get("text") or ""),
                str(meta.get("tags") or ""),
                str(r.get("label") or ""),
            ]
            if any(query in h.casefold() for h in haystacks):
                matches.append(r)
        return _ok(matches=matches[:limit], count=len(matches), query=query)
    if action == "task_complete":
        task = _find_resource(args, state, "task")
        if not task:
            return _err("task not found", status="needs_user")
        return _update_resource_metadata(state, str(task["id"]), {"status": "completed", "completed_at": datetime.now().isoformat()})
    if action in {"note_delete", "task_delete", "delete"}:
        resource = _find_resource(args, state, ["note", "task"])
        if not resource:
            return _err("note/task not found", status="needs_user")
        return state.mark_cleaned(str(resource["id"]), {"deleted": True})
    if action in {"note_update", "task_update"}:
        resource = _find_resource(args, state, "note" if action.startswith("note") else "task")
        if not resource:
            return _err("note/task not found", status="needs_user")
        updates = {k: args[k] for k in ("title", "text", "content", "due", "tags") if k in args}
        if "content" in updates and "text" not in updates:
            updates["text"] = updates.pop("content")
        # Validar due si vino en el update.
        if "due" in updates:
            due_iso, due_err = _parse_due_iso(updates["due"])
            if due_err:
                return _err(due_err, value=updates["due"], status="needs_user")
            updates["due"] = due_iso
        if not updates:
            return _err("no updatable fields provided", status="needs_user",
                        supported=["title", "text", "content", "due", "tags"])
        return _update_resource_metadata(state, str(resource["id"]), updates)
    return _err(
        "unknown notes_tasks action", action=action,
        valid_actions=[
            "status", "note_create", "task_create", "note_list", "task_list",
            "note_search", "task_search", "search", "task_complete",
            "note_delete", "task_delete", "note_update", "task_update",
        ],
        status="needs_user",
    )


def local_calendar_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(local_state=True, event_count=len(_resources_by_kind(state, "calendar_event")))
    if action in {"event_list", "list"}:
        return _ok(events=_resources_by_kind(state, "calendar_event", include_closed=bool(args.get("include_closed", False))))
    if action == "event_create":
        title = str(args.get("title") or "").strip()
        if not title:
            return _err("event_create requires title", status="needs_user")
        # VALIDACION start/end como ISO. Antes acepta cualquier string lo que
        # rompe ics_export y comparaciones temporales downstream.
        start_raw = args.get("start") or args.get("due")
        if start_raw is None:
            start_iso = datetime.now().isoformat(timespec="seconds")
        else:
            start_iso, err = _parse_due_iso(start_raw)
            if err:
                return _err(err, field="start", value=start_raw, status="needs_user")
            if start_iso is None:
                start_iso = datetime.now().isoformat(timespec="seconds")
        end_raw = args.get("end")
        end_iso: str | None
        if end_raw:
            end_iso, err = _parse_due_iso(end_raw)
            if err:
                return _err(err, field="end", value=end_raw, status="needs_user")
        else:
            end_iso = None
        # SANITY: end debe ser >= start si ambos estan presentes.
        if end_iso:
            try:
                if datetime.fromisoformat(end_iso) < datetime.fromisoformat(start_iso):
                    return _err(
                        "event end is before start",
                        start=start_iso, end=end_iso, status="needs_user",
                    )
            except ValueError:
                pass
        resource = state.register_resource(
            "calendar_event", title,
            metadata={
                "title": title, "start": start_iso, "end": end_iso,
                "location": args.get("location"), "notes": args.get("notes"),
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        return _ok(event=resource.get("resource"))
    if action in {"event_delete", "delete"}:
        event = _find_resource(args, state, "calendar_event")
        if not event:
            return _err("event not found", status="needs_user")
        return state.mark_cleaned(str(event["id"]), {"deleted": True})
    if action == "ics_export":
        events = _resources_by_kind(state, "calendar_event")
        if not events:
            return _err("no events to export", status="needs_user")
        path = _calendar_export_path(args, state)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return _err("cannot create export directory", path=str(path.parent), reason=str(exc))
        body = _events_to_ics(events)
        try:
            path.write_text(body, encoding="utf-8")
        except (PermissionError, OSError) as exc:
            return _err("ics write failed", path=str(path), reason=str(exc),
                        status="needs_user" if isinstance(exc, PermissionError) else "failed")
        try:
            size = path.stat().st_size
        except OSError:
            size = -1
        return _ok(path=str(path.resolve()), events=len(events), bytes=size, verified=size > 0)
    if action == "event_update":
        return _calendar_event_update(args, state)
    if action == "ics_import":
        return _calendar_ics_import(args, state)
    return _err(
        "unknown local_calendar action", action=action,
        valid_actions=[
            "status", "event_list", "event_create", "event_delete",
            "event_update", "ics_export", "ics_import",
        ],
        status="needs_user",
    )


def _calendar_event_update(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    event = _find_resource(args, state, "calendar_event")
    if not event:
        return _err("event not found")
    updates: dict[str, Any] = {}
    for key in ("title", "start", "end", "location", "notes"):
        if key in args and args[key] is not None:
            updates[key] = args[key]
    if not updates:
        return _err("no updatable fields provided", supported=["title", "start", "end", "location", "notes"])
    if "title" in updates:
        # CC-102: label patch atómico.
        state.update_resource(str(event["id"]), label=str(updates["title"]))
    return _update_resource_metadata(state, str(event["id"]), updates)


def _calendar_ics_import(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    path_raw = str(args.get("path") or args.get("file") or "").strip()
    text = str(args.get("content") or args.get("ics") or "")
    if path_raw:
        p = Path(path_raw).expanduser()
        if not p.is_file():
            return _err("ICS file not found", path=str(p))
        text = p.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return _err("no ICS content provided (pass path or content)")
    events_parsed = _ics_parse_events(text)
    if not events_parsed:
        return _err("no VEVENT blocks found in input")
    created = []
    for evt in events_parsed:
        title = evt.get("summary") or "Evento"
        resource = state.register_resource(
            "calendar_event",
            title,
            metadata={
                "title": title,
                "start": evt.get("dtstart") or "",
                "end": evt.get("dtend") or evt.get("dtstart") or "",
                "location": evt.get("location"),
                "notes": evt.get("description"),
                "uid": evt.get("uid"),
                "imported_from": path_raw or "<inline>",
            },
        )
        created.append(resource.get("resource"))
    return _ok(imported=len(created), events=created[:50], total_parsed=len(events_parsed))


def _ics_parse_events(text: str) -> list[dict[str, Any]]:
    """Parse ICS into a flat list of {uid, summary, dtstart, dtend, location, description}.

    Handles line folding (CRLF + space/tab continues the previous line) and the three
    DATE-TIME forms in RFC 5545: floating, UTC (Z suffix), and TZID-prefixed.
    Property parameters (between ; and :) are dropped except for TZID which is
    preserved as a separate hint.
    """
    # Step 1: unfold continuation lines.
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in raw_lines:
        if unfolded and (line.startswith(" ") or line.startswith("\t")):
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    events: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in unfolded:
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if upper == "BEGIN:VEVENT":
            current = {}
            continue
        if upper == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is None:
            continue
        # Property name is everything before the first ':' or ';' (params).
        # Examples:
        #  DTSTART:20251231T230000Z
        #  DTSTART;TZID=America/New_York:20251231T180000
        #  SUMMARY:Some text with \\n escapes
        sep = stripped.find(":")
        if sep < 0:
            continue
        head, value = stripped[:sep], stripped[sep + 1:]
        name = head.split(";", 1)[0].upper()
        value = _ics_unescape(value)
        if name == "UID":
            current["uid"] = value
        elif name == "SUMMARY":
            current["summary"] = value
        elif name == "DESCRIPTION":
            current["description"] = value
        elif name == "LOCATION":
            current["location"] = value
        elif name == "DTSTART":
            current["dtstart"] = _ics_normalize_datetime(value)
        elif name == "DTEND":
            current["dtend"] = _ics_normalize_datetime(value)
        elif name == "DTSTAMP":
            current["dtstamp"] = _ics_normalize_datetime(value)
    return events


def _ics_unescape(text: str) -> str:
    return text.replace("\\,", ",").replace("\\;", ";").replace("\\n", "\n").replace("\\N", "\n").replace("\\\\", "\\")


def _ics_normalize_datetime(value: str) -> str:
    """Convert an ICS DATE-TIME to an ISO-8601 string when possible.

    - 20251231T230000Z  -> 2025-12-31T23:00:00+00:00
    - 20251231T230000   -> 2025-12-31T23:00:00 (floating)
    - 20251231          -> 2025-12-31
    """
    v = value.strip()
    if not v:
        return ""
    z = v.endswith("Z")
    body = v[:-1] if z else v
    try:
        if "T" in body:
            date_part, time_part = body.split("T", 1)
            iso = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}T{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
            return iso + ("+00:00" if z else "")
        if len(body) == 8:
            return f"{body[:4]}-{body[4:6]}-{body[6:8]}"
    except (IndexError, ValueError):
        pass
    return v


_VALID_HABIT_FREQUENCIES = {"daily", "weekly", "monthly", "weekdays", "custom"}


def habit_tracker_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(habits=len(_resources_by_kind(state, "habit")))
    if action == "list":
        return _ok(habits=_resources_by_kind(state, "habit", include_closed=bool(args.get("include_closed", False))))
    if action == "create":
        name = str(args.get("name") or args.get("title") or "").strip()
        if not name:
            return _err("missing habit name", status="needs_user")
        frequency = str(args.get("frequency") or "daily").lower()
        if frequency not in _VALID_HABIT_FREQUENCIES:
            return _err(
                f"invalid frequency: {frequency!r}",
                valid=sorted(_VALID_HABIT_FREQUENCIES), status="needs_user",
            )
        resource = state.register_resource(
            "habit", name,
            metadata={
                "name": name, "frequency": frequency, "logs": [],
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        return _ok(habit=resource.get("resource"))
    if action == "log":
        habit = _find_resource(args, state, "habit")
        if not habit:
            return _err("habit not found", status="needs_user")
        # VALIDACION del campo `at` como ISO antes de persistir; si el LLM
        # pasa "hoy" como string, _parse_due_iso lo rechaza con un mensaje
        # claro en vez de guardarlo y romper stats downstream.
        at_raw = args.get("at")
        if at_raw is None:
            at_iso = datetime.now().isoformat(timespec="seconds")
        else:
            at_iso, err = _parse_due_iso(at_raw)
            if err:
                return _err(err, field="at", value=at_raw, status="needs_user")
            if at_iso is None:
                at_iso = datetime.now().isoformat(timespec="seconds")
        logs = list(habit.setdefault("metadata", {}).get("logs") or [])
        logs.append({
            "at": at_iso,
            "value": args.get("value", True),
            "note": args.get("note"),
        })
        return _update_resource_metadata(state, str(habit["id"]), {"logs": logs})
    if action == "stats":
        habit = _find_resource(args, state, "habit")
        if not habit:
            return _err("habit not found", status="needs_user")
        meta = habit.get("metadata", {}) or {}
        logs = meta.get("logs") or []
        # Calculo de streak basico para "daily": dias consecutivos contando
        # desde la fecha mas reciente hacia atras. Para otras frecuencias no
        # calculamos streak (semantica ambigua).
        streak = 0
        if logs and meta.get("frequency") == "daily":
            try:
                seen_dates: set[str] = set()
                for entry in logs:
                    at_val = str(entry.get("at") or "")
                    if at_val:
                        seen_dates.add(at_val[:10])  # YYYY-MM-DD
                if seen_dates:
                    sorted_dates = sorted(seen_dates, reverse=True)
                    most_recent = sorted_dates[0]
                    today = datetime.now().date().isoformat()
                    cur = datetime.fromisoformat(most_recent).date()
                    today_d = datetime.fromisoformat(today).date()
                    # streak empieza solo si el log mas reciente es de hoy o ayer
                    if (today_d - cur).days <= 1:
                        streak = 1
                        for i in range(1, len(sorted_dates)):
                            next_d = datetime.fromisoformat(sorted_dates[i]).date()
                            if (cur - next_d).days == 1:
                                streak += 1
                                cur = next_d
                            else:
                                break
            except (ValueError, TypeError):
                streak = 0
        return _ok(
            habit=habit, log_count=len(logs),
            last=logs[-1] if logs else None,
            current_streak=streak, frequency=meta.get("frequency"),
        )
    if action == "delete":
        habit = _find_resource(args, state, "habit")
        if not habit:
            return _err("habit not found", status="needs_user")
        return state.mark_cleaned(str(habit["id"]), {"deleted": True})
    return _err(
        "unknown habit_tracker action", action=action,
        valid_actions=["status", "list", "create", "log", "stats", "delete"],
        status="needs_user",
    )


def local_search_tool(args: dict[str, Any]) -> dict[str, Any]:
    action = str(args.get("action") or "search").casefold()
    if action == "status":
        return _ok(everything_cli=bool(shutil.which("es.exe")), backend="python_rglob")
    if action == "search":
        root = Path(str(args.get("root") or Path.home())).expanduser()
        if not root.exists():
            return _err("root not found", root=str(root), status="needs_user")
        if not root.is_dir():
            return _err("root is not a directory", root=str(root), status="needs_user")
        query = str(args.get("query") or "").casefold()
        pattern = str(args.get("pattern") or "*")
        try:
            limit = max(1, min(int(args.get("limit", 50)), 500))
        except (TypeError, ValueError):
            limit = 50
        include_content = bool(args.get("include_content", False))
        # BUDGET: rglob sin limite sobre Home puede caminar 500K archivos.
        try:
            budget_s = float(args.get("budget_s", 10.0))
        except (TypeError, ValueError):
            budget_s = 10.0
        budget_s = max(1.0, min(budget_s, 60.0))
        deadline = time.time() + budget_s
        max_visited = int(args.get("max_visited", 50000))
        results = []
        visited = 0
        skipped_io = 0
        try:
            iterator = root.rglob(pattern) if bool(args.get("recursive", True)) else root.glob(pattern)
            for path in iterator:
                visited += 1
                if len(results) >= limit or visited > max_visited:
                    break
                if time.time() > deadline:
                    break
                try:
                    name_hit = query in path.name.casefold() if query else True
                    content_hit = False
                    snippet = ""
                    is_file = path.is_file()
                    file_size = path.stat().st_size if is_file else None
                    # BINARY GUARD: si include_content + archivo > max_bytes
                    # ya lo salta. Ademas guard contra binarios reales:
                    # leemos primero los 512 bytes para detectar NUL.
                    if include_content and is_file and file_size is not None and file_size < int(args.get("max_bytes", 2_000_000)):
                        try:
                            with path.open("rb") as fh:
                                head = fh.read(512)
                            if b"\x00" not in head:
                                text = path.read_text(encoding="utf-8", errors="replace")
                                idx = text.casefold().find(query)
                                content_hit = idx >= 0
                                snippet = text[max(0, idx - 80): idx + 180] if content_hit else ""
                        except (PermissionError, OSError):
                            skipped_io += 1
                    if name_hit or content_hit:
                        results.append({
                            "path": str(path), "is_file": is_file,
                            "size": file_size, "snippet": snippet,
                        })
                except (PermissionError, OSError):
                    skipped_io += 1
                    continue
        except OSError as exc:
            return _err(f"search failed: {exc}", root=str(root))
        truncated = (
            len(results) >= limit
            or visited > max_visited
            or time.time() > deadline
        )
        return _ok(
            results=results, count=len(results), root=str(root),
            truncated=truncated, visited=visited, skipped_io=skipped_io,
        )
    if action == "recent":
        root = Path(str(args.get("root") or Path.home())).expanduser()
        if not root.exists() or not root.is_dir():
            return _err("root not found or not a directory", root=str(root), status="needs_user")
        try:
            limit = max(1, min(int(args.get("limit", 20)), 200))
        except (TypeError, ValueError):
            limit = 20
        # BUDGET: rglob igual que en search.
        try:
            budget_s = float(args.get("budget_s", 10.0))
        except (TypeError, ValueError):
            budget_s = 10.0
        deadline = time.time() + max(1.0, min(budget_s, 60.0))
        max_visited = int(args.get("max_visited", 50000))
        files: list[tuple[float, Path]] = []
        visited = 0
        for path in root.rglob(str(args.get("pattern") or "*")):
            visited += 1
            if visited > max_visited or time.time() > deadline:
                break
            if path.is_file():
                try:
                    files.append((path.stat().st_mtime, path))
                except OSError:
                    pass
            if len(files) > 5000:
                break
        files.sort(reverse=True)
        return _ok(
            files=[{"path": str(p), "modified": datetime.fromtimestamp(ts).isoformat()} for ts, p in files[:limit]],
            visited=visited,
            truncated=visited > max_visited or time.time() > deadline,
        )
    return _err(
        "unknown local_search action", action=action,
        valid_actions=["status", "search", "recent"], status="needs_user",
    )


def printer_scanner_tool(args: dict[str, Any]) -> dict[str, Any]:
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


def backup_sync_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(backend="zipfile", restore_supported=True, dedupe_supported=True, verify_supported=True)
    if action == "list":
        resources = _resources_by_kind(state, "backup", include_closed=bool(args.get("include_closed", False)))
        return _ok(backups=resources, count=len(resources))
    if action == "backup_create":
        src = Path(str(args.get("src") or args.get("path") or "")).expanduser()
        if not src.exists():
            return _err("source path not found", src=str(src))
        out_dir = state.path.parent / "backups"
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = Path(str(args.get("dst") or out_dir / f"{_safe_name(src.name)}_{time.strftime('%Y%m%d_%H%M%S')}.zip")).expanduser()
        dst.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as archive:
            if src.is_file():
                archive.write(src, src.name)
            else:
                for child in src.rglob("*"):
                    if child.is_file():
                        archive.write(child, child.relative_to(src.parent))
        resource = state.register_resource("backup", dst.name, metadata={"src": str(src), "dst": str(dst), "created_at": datetime.now().isoformat(), "size": dst.stat().st_size})
        return _ok(backup=resource.get("resource"), path=str(dst.resolve()), size=dst.stat().st_size)
    if action == "restore":
        return _backup_restore(args, state)
    if action == "dedupe":
        return _backup_dedupe(args)
    if action == "verify":
        return _backup_verify(args, state)
    return _err(
        "unknown backup_sync action", action=action,
        valid_actions=[
            "status", "backup_create", "list", "restore",
            "dedup_scan", "sync",
        ],
        status="needs_user",
    )


def _backup_resolve(args: dict[str, Any], state: AgentState) -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve a backup either from resource id or explicit path."""
    rid = str(args.get("id") or args.get("backup_id") or args.get("resource_id") or "").strip()
    if rid:
        resource = state._load().get("resources", {}).get(rid)
        if resource and resource.get("kind") == "backup":
            path_str = str((resource.get("metadata") or {}).get("dst") or "").strip()
            if path_str:
                p = Path(path_str)
                if p.is_file():
                    return p, resource
    explicit = str(args.get("path") or args.get("backup") or "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_file():
            return p, None
    return None, None


def _backup_restore(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    backup_path, resource = _backup_resolve(args, state)
    if not backup_path:
        return _err("backup not found; pass id (res_*) or path to ZIP")
    if backup_path.suffix.casefold() != ".zip":
        return _err("only .zip backups are supported", path=str(backup_path))
    dst_raw = str(args.get("dst") or args.get("to") or "").strip()
    if dst_raw:
        dst = Path(dst_raw).expanduser()
    else:
        original_src = str((resource or {}).get("metadata", {}).get("src") or "").strip()
        dst = Path(original_src).parent if original_src else Path.cwd()
    dst.mkdir(parents=True, exist_ok=True)
    conflict_policy = str(args.get("conflict") or args.get("on_conflict") or "rename").casefold()
    if conflict_policy not in {"overwrite", "skip", "rename"}:
        return _err("conflict policy must be overwrite|skip|rename")
    preview_only = bool(args.get("preview", False))

    # CC-101 / T2-backup_sync-restore-overwrite: gate duro si overwrite y no es preview.
    if conflict_policy == "overwrite" and not preview_only:
        gate = _hard_gate(
            state,
            tool="backup_sync",
            action="restore",
            args=args,
            reason=f"restore with overwrite will replace existing files at {dst}",
            risk="high",
        )
        if gate is not None:
            return gate

    extracted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    renamed: list[dict[str, Any]] = []
    overwritten: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    dst_resolved = dst.resolve()

    try:
        with zipfile.ZipFile(backup_path, "r") as archive:
            entries = archive.infolist()
            if preview_only:
                return _ok(
                    preview=True, backup=str(backup_path), dst=str(dst),
                    entries=[{"name": e.filename, "size": e.file_size} for e in entries[:200]],
                    total_entries=len(entries),
                )
            for entry in entries:
                # CC-021 / T2-backup_sync-zip-slip-021: contención bajo dst.
                candidate = (dst / entry.filename).resolve()
                if candidate != dst_resolved and dst_resolved not in candidate.parents:
                    blocked.append({"name": entry.filename, "reason": "zip-slip outside dst"})
                    continue
                if entry.is_dir():
                    candidate.mkdir(parents=True, exist_ok=True)
                    continue
                final_target = candidate
                final_target.parent.mkdir(parents=True, exist_ok=True)
                if final_target.exists():
                    if conflict_policy == "skip":
                        skipped.append({"name": entry.filename})
                        continue
                    if conflict_policy == "rename":
                        final_target = _next_available_path(final_target)
                        renamed.append({"from": entry.filename, "to": str(final_target.relative_to(dst_resolved))})
                    elif conflict_policy == "overwrite":
                        overwritten.append({"name": entry.filename})
                with archive.open(entry, "r") as src_fh, final_target.open("wb") as dst_fh:
                    shutil.copyfileobj(src_fh, dst_fh)
                extracted.append({"name": entry.filename, "size": entry.file_size, "dst": str(final_target)})
    except (zipfile.BadZipFile, OSError) as exc:
        return _err(f"restore failed: {exc}", backup=str(backup_path), dst=str(dst))
    if blocked:
        # Si bloqueamos al menos uno, devolvemos status=failed para que el agente
        # surface el incidente; el resto extraído se reporta igual.
        return _err(
            f"restore blocked {len(blocked)} entries that would escape dst (zip-slip)",
            backup=str(backup_path), dst=str(dst),
            blocked=blocked[:50], extracted_count=len(extracted),
            extracted=extracted[:50], status="failed",
        )

    return _ok(
        backup=str(backup_path), dst=str(dst), conflict_policy=conflict_policy,
        extracted_count=len(extracted), skipped_count=len(skipped),
        renamed_count=len(renamed), overwritten_count=len(overwritten),
        extracted=extracted[:50], skipped=skipped[:50], renamed=renamed[:50], overwritten=overwritten[:50],
        verified=True, evidence={"dst": str(dst), "entries": len(extracted)},
    )


def _next_available_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for n in range(1, 10000):
        candidate = path.with_name(f"{stem}_{n}{suffix}")
        if not candidate.exists():
            return candidate
    return path.with_name(f"{stem}_{int(time.time())}{suffix}")


def _backup_dedupe(args: dict[str, Any]) -> dict[str, Any]:
    import hashlib
    root_raw = str(args.get("path") or args.get("root") or "").strip()
    if not root_raw:
        return _err("dedupe requires path")
    root = Path(root_raw).expanduser()
    if not root.exists() or not root.is_dir():
        return _err("path is not an existing directory", path=str(root))
    min_size = int(args.get("min_size_bytes", 1))
    by_hash: dict[str, list[str]] = {}
    scanned = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size < min_size:
                continue
            scanned += 1
            digest = hashlib.sha256()
            with path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    digest.update(chunk)
            by_hash.setdefault(digest.hexdigest(), []).append(str(path))
        except OSError:
            continue
    duplicates = {h: paths for h, paths in by_hash.items() if len(paths) > 1}
    duplicate_count = sum(len(paths) - 1 for paths in duplicates.values())
    return _ok(
        root=str(root), scanned=scanned, unique_hashes=len(by_hash),
        duplicate_groups=len(duplicates), duplicate_files=duplicate_count,
        groups=[{"sha256": h, "paths": paths} for h, paths in list(duplicates.items())[:50]],
    )


def _backup_verify(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    backup_path, resource = _backup_resolve(args, state)
    if not backup_path:
        return _err("backup not found")
    try:
        with zipfile.ZipFile(backup_path, "r") as archive:
            bad = archive.testzip()
            return _ok(backup=str(backup_path), size=backup_path.stat().st_size, entries=len(archive.infolist()), corrupted=bool(bad), bad_file=bad, verified=not bad)
    except (zipfile.BadZipFile, OSError) as exc:
        return _err(f"verify failed: {exc}", backup=str(backup_path))


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


def _show_message_box(title: str, text: str) -> dict[str, Any]:
    # CC-100: env-var indirection. _run_detached_powershell no acepta env,
    # así que invocamos Popen directo con env extendido.
    env = {**os.environ, "GEMMA4_MSG_TITLE": title, "GEMMA4_MSG_TEXT": text}
    script = (
        "Add-Type -AssemblyName PresentationFramework; "
        "[System.Windows.MessageBox]::Show($env:GEMMA4_MSG_TEXT, $env:GEMMA4_MSG_TITLE)"
    )
    proc = subprocess.Popen(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return {"pid": proc.pid}


def _ensure_notification_runner(state: AgentState) -> Path:
    """Escribe (si no existe) el runner PS fijo que muestra notificaciones
    leyendo título/texto del JSON persistido por _schedule_notification.

    El runner es estático: nada del LLM se interpola dentro.
    """
    runner_path = state.path.parent / "notifications" / "_runner.ps1"
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    expected = (
        "param([Parameter(Mandatory=$true)][string]$TaskName)\n"
        "$ErrorActionPreference = 'Stop'\n"
        "Add-Type -AssemblyName PresentationFramework\n"
        "$payload = Join-Path $PSScriptRoot ($TaskName + '.json')\n"
        "if (-not (Test-Path $payload)) { exit 1 }\n"
        "$data = Get-Content -Raw -Encoding UTF8 $payload | ConvertFrom-Json\n"
        "$title = [string]$data.title\n"
        "$text = [string]$data.text\n"
        "[System.Windows.MessageBox]::Show($text, $title) | Out-Null\n"
    )
    try:
        if not runner_path.is_file() or runner_path.read_text(encoding="utf-8") != expected:
            runner_path.write_text(expected, encoding="utf-8")
    except OSError:
        pass
    return runner_path


def _schedule_notification(args: dict[str, Any], state: AgentState, *, kind: str) -> dict[str, Any]:
    title = str(args.get("title") or kind.title()).strip()
    text = str(args.get("text") or args.get("message") or title).strip()
    try:
        due = _notification_due(args)
    except _NotificationDueError as exc:
        return _err(str(exc), status="needs_user")
    task_name = f"Gemma4Agent_{kind}_{int(time.time())}"
    # CC-100 / T2-notification-ps-injection-023: el title/text vienen del LLM.
    # Persistimos el mensaje en un JSON dentro del state-dir y registramos la
    # Scheduled Task apuntando a un runner fijo que lo lee por id. Así nada
    # controlado por el LLM se f-stringea dentro del script PS.
    runner = _ensure_notification_runner(state)
    payload_dir = state.path.parent / "notifications"
    payload_dir.mkdir(parents=True, exist_ok=True)
    payload_path = payload_dir / f"{task_name}.json"
    payload_path.write_text(
        json.dumps({"title": title, "text": text, "kind": kind, "task_name": task_name}, ensure_ascii=False),
        encoding="utf-8",
    )
    # Validamos due y task_name antes de embeber (allowlists estrictas).
    try:
        due_literal = ps_safe_literal(due.strftime("%Y-%m-%d %H:%M:%S"), RX_ISO_DATETIME)
        safe_task_name = ps_safe_literal(task_name, re.compile(r"^Gemma4Agent_[A-Za-z0-9_]+$"))
    except PSValidationError as exc:
        return _err(f"invalid schedule parameters: {exc}")
    env = {
        **os.environ,
        "GEMMA4_NOTIF_TASK": safe_task_name,
        "GEMMA4_NOTIF_DUE": due_literal,
        "GEMMA4_NOTIF_RUNNER": str(runner),
    }
    ps = r"""
$task = $env:GEMMA4_NOTIF_TASK
$due  = $env:GEMMA4_NOTIF_DUE
$runner = $env:GEMMA4_NOTIF_RUNNER
$argLine = ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -TaskName "{1}"' -f $runner, $task)
$Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argLine
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date $due)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $task -TaskPath '\Gemma4Agent\' -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return _err("failed to register scheduled notification", stderr=proc.stderr, exit_code=proc.returncode)
    resource = state.register_resource(
        kind,
        title,
        cleanup_tool="notification",
        cleanup_args={"action": "delete", "task_name": task_name},
        metadata={"text": text, "due": due.isoformat(), "task_name": task_name},
    )
    return _ok(kind=kind, title=title, text=text, due=due.isoformat(), task_name=task_name, resource=resource.get("resource"))


def _delete_notification(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    rid = str(args.get("id") or args.get("resource_id") or "").strip()
    task_name = str(args.get("task_name") or "").strip()
    resource = None
    if rid:
        resources = state._load().get("resources", {})
        resource = resources.get(rid)
        task_name = task_name or str((resource or {}).get("metadata", {}).get("task_name") or "")
    if task_name:
        ps = f"Unregister-ScheduledTask -TaskPath '\\Gemma4Agent\\' -TaskName '{_ps_quote(task_name)}' -Confirm:$false"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=20)
        result = {"task_name": task_name, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    else:
        result = {"task_name": None, "note": "no scheduled task name provided"}
    if rid:
        marked = state.mark_cleaned(rid, result)
        return _ok(deleted=True, task=result, resource=marked.get("resource"))
    return _ok(deleted=True, task=result)


def _enrich_notification_resource(resource: dict[str, Any]) -> dict[str, Any]:
    """Augment a notification resource with live Scheduled Task info."""
    metadata = resource.get("metadata") or {}
    task_name = str(metadata.get("task_name") or "").strip()
    if not task_name:
        return resource
    script = (
        f"$t = Get-ScheduledTask -TaskPath '\\Gemma4Agent\\' -TaskName '{_ps_quote(task_name)}' -ErrorAction SilentlyContinue; "
        f"if ($t) {{ "
        f"  $info = $t | Get-ScheduledTaskInfo; "
        f"  [PSCustomObject]@{{ "
        f"    State=$t.State.ToString(); "
        f"    LastRunTime=$info.LastRunTime; "
        f"    NextRunTime=$info.NextRunTime; "
        f"    LastTaskResult=$info.LastTaskResult; "
        f"    NumberOfMissedRuns=$info.NumberOfMissedRuns; "
        f"  }} | ConvertTo-Json -Depth 3 "
        f"}}"
    )
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            data = json.loads(proc.stdout)
            if isinstance(data, dict):
                resource = dict(resource)
                resource["scheduled_task_info"] = data
        except json.JSONDecodeError:
            pass
    return resource


def _notification_history(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Return notifications (open + closed) with scheduled-task last run info."""
    kinds = {"notification", "timer", "alarm", "local_reminder"}
    requested = str(args.get("kind") or "").strip().casefold()
    if requested:
        kinds = {_kind_for_notification_action(requested + "_create" if not requested.endswith("_create") else requested)}
    limit = int(args.get("limit", 50))
    resources = state.list_resources(include_closed=True).get("resources", [])
    items = [r for r in resources if r.get("kind") in kinds]
    items.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    items = items[:limit]
    enriched = [_enrich_notification_resource(item) for item in items]
    return _ok(items=enriched, count=len(enriched), kinds=sorted(kinds))


def _update_notification(args: dict[str, Any], state: AgentState, *, kind: str) -> dict[str, Any]:
    """Cancel and re-register a Scheduled Task with updated trigger/text."""
    rid = str(args.get("id") or args.get("resource_id") or "").strip()
    name_query = str(args.get("name") or args.get("title") or "").strip().casefold()
    resources = state._load().get("resources", {})
    resource = None
    if rid and rid in resources:
        resource = resources[rid]
    elif name_query:
        for res in resources.values():
            if res.get("kind") == kind and name_query in str(res.get("label", "")).casefold():
                resource = res
                break
    if not resource:
        return _err("notification not found", kind=kind, status="needs_user")

    old_task_name = str((resource.get("metadata") or {}).get("task_name") or "").strip()
    # Build merged args from old metadata + updates.
    metadata = dict(resource.get("metadata") or {})
    merged_args = {
        "title": args.get("title") or resource.get("label") or metadata.get("text"),
        "text": args.get("text") or args.get("message") or metadata.get("text"),
        "due": args.get("due"),
        "seconds": args.get("seconds"),
        "minutes": args.get("minutes"),
        "time": args.get("time"),
    }
    # Only override "due" if any of the time keys is provided; else reuse old due.
    if not any(args.get(k) is not None for k in ("due", "seconds", "minutes", "time")):
        merged_args["due"] = metadata.get("due")

    # Unregister the old task (if any).
    cleanup = None
    if old_task_name:
        cleanup = _delete_notification({"id": resource.get("id"), "task_name": old_task_name}, state)
    new = _schedule_notification(merged_args, state, kind=kind)
    if not new.get("ok"):
        return new
    return _ok(updated=True, previous_task=old_task_name, previous_id=resource.get("id"), cleanup=cleanup, new=new)


def _kind_for_notification_action(action: str) -> str:
    if action.startswith("timer"):
        return "timer"
    if action.startswith("alarm"):
        return "alarm"
    if action.startswith("reminder"):
        return "local_reminder"
    return "notification"


class _NotificationDueError(ValueError):
    """T2-notification-no-due-validation-024: parsing inválido sin fallback silencioso."""


def _notification_due(args: dict[str, Any]) -> datetime:
    seconds = args.get("seconds")
    minutes = args.get("minutes")
    if seconds is not None:
        return datetime.now() + timedelta(seconds=max(1, int(seconds)))
    if minutes is not None:
        return datetime.now() + timedelta(minutes=max(1, int(minutes)))
    raw = str(args.get("due") or args.get("time") or "").strip()
    if not raw:
        # Sin due/time/seconds/minutes: mantenemos default explícito.
        return datetime.now() + timedelta(minutes=5)
    # ISO completo.
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except ValueError:
        pass
    # HH:MM como atajo: hoy si futuro, mañana si pasó.
    if re.fullmatch(r"[0-2]\d:[0-5]\d", raw):
        hh, mm = raw.split(":")
        now = datetime.now()
        candidate = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        if candidate <= now:
            candidate = candidate + timedelta(days=1)
        return candidate
    raise _NotificationDueError(f"unrecognized due/time format: {raw!r} (use ISO datetime or HH:MM)")


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


def _calendar_export_path(args: dict[str, Any], state: AgentState) -> Path:
    raw = str(args.get("path") or "").strip()
    if raw:
        path = Path(raw).expanduser()
    else:
        path = state.path.parent / "generated" / f"calendar_{time.strftime('%Y%m%d_%H%M%S')}.ics"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _events_to_ics(events: list[dict[str, Any]]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Gemma4Agent//Local Calendar//ES"]
    for event in events:
        meta = event.get("metadata", {})
        uid = event.get("id", f"evt_{time.time()}")
        title = str(meta.get("title") or event.get("label") or "Evento")
        start = _ics_time(str(meta.get("start") or datetime.now().isoformat()))
        end = _ics_time(str(meta.get("end") or meta.get("start") or datetime.now().isoformat()))
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}@gemma4-agent",
            f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:{_ics_escape(title)}",
        ])
        if meta.get("location"):
            lines.append(f"LOCATION:{_ics_escape(str(meta['location']))}")
        if meta.get("notes"):
            lines.append(f"DESCRIPTION:{_ics_escape(str(meta['notes']))}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _ics_time(raw: str) -> str:
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        value = datetime.now()
    return value.strftime("%Y%m%dT%H%M%S")


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


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
