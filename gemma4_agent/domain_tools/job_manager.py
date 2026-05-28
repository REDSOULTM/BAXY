"""Job Manager domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Tracking de jobs subprocess de larga duración. Distinto de
developer.start_dev_server (especializado): job_manager es genérico. Cada job
tiene PID, log path, label, persistido en state como kind=job. Cancel verifica
identidad del PID (CC-104) antes de taskkill — anti pid-recycle.

Funciones extraídas (4):
  job_manager_tool               (entry, 7 acciones)
  _job_manager_start             (shlex split + Popen + log file)
  _job_manager_log               (tail)
  _job_manager_cancel            (taskkill /F /T con verificación PID)

Helpers desde domain_tools (lazy):
  _resources_by_kind, _find_resource, _safe_name, _pid_alive, _pid_owned_by."""
from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .._shared import _err, _ok
from ..state import AgentState


__all__ = [
    "job_manager_tool",
    "_job_manager_start",
    "_job_manager_log",
    "_job_manager_cancel",
]


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
    from .helpers import _find_resource, _pid_alive, _resources_by_kind
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
    from .helpers import _safe_name
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
    from .helpers import _find_resource
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
    from .helpers import _find_resource, _pid_owned_by
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
