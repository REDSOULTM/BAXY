"""Notifications domain tool — extracted from domain_tools.py (R2 sprint
2026-05-27).

Una sola entry point pública (notification_tool) que maneja timer/alarm/
reminder/toast/notification vía actions. Persistencia + scheduling via Windows
Scheduled Tasks + un runner PS estático (CC-100: nada del LLM se f-stringea en
el script PS, todo va por env-var + JSON payload). Lenguaje natural en `due`
("a las 7 de la mañana") se delega a datetime_parse.parse_when.

Funciones extraídas (9 + 1 exception):
  notification_tool                  (entry, 14 acciones)
  _show_message_box                  (popup inmediato)
  _ensure_notification_runner        (escribe el runner.ps1 estático)
  _schedule_notification             (registra Scheduled Task)
  _delete_notification               (Unregister-ScheduledTask)
  _enrich_notification_resource      (Get-ScheduledTaskInfo live)
  _notification_history
  _update_notification               (cancel + re-register)
  _kind_for_notification_action
  _notification_due                  (parse: ISO / HH:MM / NL)
  _NotificationDueError

Helpers desde domain_tools (lazy, dentro de funciones):
  _ps_quote (vive en domain_tools.py:10822 — string-quote para PS)

Helpers desde ._ps (top-level, ya disponibles):
  PSValidationError, RX_ISO_DATETIME, ps_safe_literal

Mock-friendly: subprocess.run + state.* son los puntos de patch típicos.
Tests futuros pueden mockear gemma4_agent.domain_tools_notifications.subprocess.run."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .._ps import PSValidationError, RX_ISO_DATETIME, ps_safe_literal
from .._shared import _err, _ok
from ..memory_pkg.state import AgentState


__all__ = [
    "notification_tool",
    "_show_message_box",
    "_ensure_notification_runner",
    "_schedule_notification",
    "_delete_notification",
    "_enrich_notification_resource",
    "_notification_history",
    "_update_notification",
    "_kind_for_notification_action",
    "_notification_due",
    "_NotificationDueError",
]


def notification_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    import shutil
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
    from .helpers import _ps_quote  # vive aún en domain_tools.py
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
    from .helpers import _ps_quote
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
    # LENGUAJE NATURAL (2026-05-27): "a las 7 de la mañana", "mañana a las 9",
    # "las 6 de la tarde". El 4B NO convierte fiable estas frases a HH:MM/ISO
    # (medido), así que las alarmas/timers fallaban con NL aunque los recordatorios
    # ya lo soportan. Misma capa universal y conservadora que reminder_tool
    # (datetime_parse.py): si NO resuelve con confianza -> error honesto (no
    # inventamos un horario; una alarma a la hora equivocada es inútil).
    try:
        from ..support.datetime_parse import parse_when as _parse_when
        _iso = _parse_when(raw)
    except Exception:
        _iso = None
    if _iso:
        try:
            return datetime.fromisoformat(_iso.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
        except ValueError:
            pass
    raise _NotificationDueError(
        f"unrecognized due/time format: {raw!r} (use ISO datetime, HH:MM, "
        "or a clear time like 'a las 7 de la mañana')")
