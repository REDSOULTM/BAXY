"""Watcher domain tool — extracted from domain_tools.py (R2 sprint 2026-05-28).

File/URL/process watchers persistidos en state.json. Cada watcher tiene un
snapshot (mtime+size para files, sha256 para URLs, running-bool para process)
y se evalúa periódicamente via Scheduled Task que invoca
gemma4_agent.watcher_runner. Cuando hay cambio, se dispara `on_change`
(tool+args).

Funciones extraídas (8):
  watcher_tool                            (entry, 6 acciones)
  _watcher_register_file
  _watcher_register_url
  _file_snapshot
  _url_snapshot
  _process_snapshot
  _register_routine_process_watcher       (lo usa routine_tool para on_app_*)
  _register_watcher_scheduled_task
  _watcher_check

Helpers desde domain_tools (lazy):
  _resources_by_kind, _find_resource, _safe_name, _ps_quote.

Helpers desde domain_tools_routine (lazy):
  _unregister_routine_scheduled_task, _detect_python_executable.

NOTA: routine_tool importa _register_routine_process_watcher lazy desde
domain_tools (que ahora re-exporta desde este módulo). Sin ciclo en runtime."""
from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ._shared import _err, _ok
from .state import AgentState


Executor = Callable[[str, dict[str, Any]], dict[str, Any]]


__all__ = [
    "watcher_tool",
    "_watcher_register_file",
    "_watcher_register_url",
    "_file_snapshot",
    "_url_snapshot",
    "_process_snapshot",
    "_register_routine_process_watcher",
    "_register_watcher_scheduled_task",
    "_watcher_check",
]


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
    from .domain_tools_helpers import _find_resource, _resources_by_kind
    from .domain_tools_routine import _unregister_routine_scheduled_task
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
    from .domain_tools_helpers import _safe_name
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
    from .domain_tools_helpers import _ps_quote
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
    from .domain_tools_helpers import _safe_name
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
    from .domain_tools_helpers import _ps_quote
    from .domain_tools_routine import _detect_python_executable
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
    from .domain_tools_helpers import _find_resource
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
