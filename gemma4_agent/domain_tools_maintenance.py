"""Maintenance domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Windows maintenance + security diagnostics. Acciones de READ vs WRITE:
  - Read: windows_update_status, defender_status, firewall_status,
    event_logs_query, services_list, service_status, disk_cleanup_describe
  - Write con checkpoint+rollback: service_start, service_stop,
    restore_point_create, defender_quick_scan (lanzado como job background)
  - Disk cleanup execution + Windows Update install: NO expuestos (terminal
    explícito requerido).

Seguridad PS (CC-100): event_logs_query usa allowlist RX_LOG_NAME y env-var
para el log name; service names pasan por _ps_quote; defender scan corre como
job (T2-maintenance-defender-scan-timeout-026).

Funciones extraídas (10):
  maintenance_tool                       (entry, 11 acciones)
  _maintenance_windows_update_status     (Microsoft.Update.Session COM)
  _maintenance_defender_status           (Get-MpComputerStatus)
  _maintenance_defender_quick_scan       (Start-MpScan QuickScan, job)
  _maintenance_firewall_status
  _maintenance_event_logs                (Get-WinEvent, allowlist log name)
  _maintenance_services_list
  _maintenance_service_status
  _maintenance_service_control           (Start/Stop con rollback)
  _maintenance_restore_point_create

Helpers desde domain_tools (lazy): _ps_quote."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from typing import Any

from ._ps import (
    PSValidationError,
    RX_LOG_NAME,
    parse_ps_json,
    ps_safe_literal,
)
from ._shared import _err, _ok
from .tool_result import ToolResult
from .state import AgentState


__all__ = [
    "maintenance_tool",
    "_maintenance_windows_update_status",
    "_maintenance_defender_status",
    "_maintenance_defender_quick_scan",
    "_maintenance_firewall_status",
    "_maintenance_event_logs",
    "_maintenance_services_list",
    "_maintenance_service_status",
    "_maintenance_service_control",
    "_maintenance_restore_point_create",
]


# R4 sprint 2026-05-28: handler migrado a ToolResult con .to_dict().
def _ok_tr(**kw):
    return ToolResult.ok_result(**kw).to_dict()


def _err_tr(msg, **kw):
    return ToolResult.err(msg, **kw).to_dict()


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
        return _ok_tr(
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
        return _ok_tr(
            note=(
                "Disk cleanup must be run manually by the user. First run cleanmgr /sageset:1 in an "
                "elevated terminal to pick categories, then cleanmgr /sagerun:1 to apply. This tool "
                "intentionally does NOT return executable command arrays - the operation deletes "
                "selected categories irreversibly."
            ),
            status="needs_user",
            verified=False,
        )
    if action == "restore_point_create":
        return _maintenance_restore_point_create(args)
    return _err_tr(
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
        return _err_tr("windows update query timeout", reason="wuauserv_unresponsive")
    if proc.returncode != 0:
        return _err_tr("windows_update_status failed", stderr=proc.stderr)
    try:
        data = json.loads(proc.stdout or "null")
    except json.JSONDecodeError:
        return _err_tr("windows_update_status invalid JSON", raw=proc.stdout[:500])
    return _ok_tr(**(data or {}))


def _maintenance_defender_status() -> dict[str, Any]:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntispywareEnabled,AMServiceEnabled,FullScanAge,QuickScanAge,AntivirusSignatureLastUpdated,DefenderSignaturesOutOfDate | ConvertTo-Json -Depth 3"],
        capture_output=True, text=True, timeout=20,
    )
    if proc.returncode != 0:
        return _err_tr("Get-MpComputerStatus failed", stderr=proc.stderr)
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return _err_tr("defender_status invalid JSON", raw=proc.stdout[:500])
    return _ok_tr(defender=data)


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
    return _ok_tr(
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
        return _err_tr("firewall_status failed", stderr=proc.stderr)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _err_tr("firewall_status invalid JSON", raw=proc.stdout[:500])
    if isinstance(data, dict):
        data = [data]
    return _ok_tr(profiles=data, count=len(data))


def _maintenance_event_logs(args: dict[str, Any]) -> dict[str, Any]:
    # CC-100 / T2-maintenance-event-log-injection-025: validamos log contra
    # allowlist estricta y pasamos por env-var. hours/limit/level se castean.
    log_raw = str(args.get("log") or "System").strip()
    try:
        log = ps_safe_literal(log_raw, RX_LOG_NAME)
    except PSValidationError as exc:
        return _err_tr(f"invalid log name: {exc}", log=log_raw, status="needs_user")
    level = args.get("level")  # 1=Critical 2=Error 3=Warning 4=Information
    try:
        hours = int(args.get("hours", 24))
        limit = int(args.get("limit", 50))
        level_int = int(level) if level is not None else None
    except (TypeError, ValueError):
        return _err_tr("invalid hours/limit/level (must be integers)", status="needs_user")
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
        return _err_tr("Get-WinEvent timeout", log=log, hours=hours, reason="event_log_too_large")
    if proc.returncode != 0:
        return _err_tr("event_logs_query failed", stderr=proc.stderr)
    ok_parse, data = parse_ps_json(proc.stdout)
    if not ok_parse:
        return _err_tr("event_logs_query invalid JSON", raw=data)
    if data is None:
        return _ok_tr(log=log, events=[], count=0, hours=hours)
    if isinstance(data, dict):
        data = [data]
    return _ok_tr(log=log, events=data, count=len(data), hours=hours)


def _maintenance_services_list(args: dict[str, Any]) -> dict[str, Any]:
    from .domain_tools_helpers import _ps_quote
    name = str(args.get("name") or args.get("query") or "*").strip()
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Get-Service -Name '{_ps_quote(name)}' -ErrorAction SilentlyContinue | Select-Object Name,DisplayName,Status,StartType | ConvertTo-Json"],
        capture_output=True, text=True, timeout=20,
    )
    if proc.returncode != 0:
        return _err_tr("services_list failed", stderr=proc.stderr)
    raw = proc.stdout.strip()
    if not raw:
        return _ok_tr(services=[], count=0)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err_tr("services_list invalid JSON", raw=raw[:500])
    if isinstance(data, dict):
        data = [data]
    return _ok_tr(services=data, count=len(data))


def _maintenance_service_status(args: dict[str, Any]) -> dict[str, Any]:
    from .domain_tools_helpers import _ps_quote
    name = str(args.get("name") or "").strip()
    if not name:
        return _err_tr("missing service name")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Get-Service -Name '{_ps_quote(name)}' -ErrorAction SilentlyContinue | Select-Object Name,DisplayName,Status,StartType | ConvertTo-Json"],
        capture_output=True, text=True, timeout=15,
    )
    if proc.returncode != 0:
        return _err_tr("service_status failed", stderr=proc.stderr)
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
    except json.JSONDecodeError:
        data = None
    if not data:
        return _err_tr("service not found", name=name)
    return _ok_tr(service=data)


def _maintenance_service_control(action: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .domain_tools_helpers import _ps_quote
    name = str(args.get("name") or "").strip()
    if not name:
        return _err_tr("missing service name")
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
    return _ok_tr(
        action=action, name=name,
        before=before.get("service"),
        after=after.get("service"),
        exit_code=proc.returncode,
        stderr=proc.stderr[-1000:],
        checkpoint=checkpoint.get("checkpoint"),
        verified=proc.returncode == 0,
    )


def _maintenance_restore_point_create(args: dict[str, Any]) -> dict[str, Any]:
    from .domain_tools_helpers import _ps_quote
    description = str(args.get("description") or "Gemma4 Agent restore point").strip()
    # System Restore must be enabled on the system drive for this to work.
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Checkpoint-Computer -Description '{_ps_quote(description)}' -RestorePointType MODIFY_SETTINGS"],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        return _err_tr(
            "Checkpoint-Computer failed; System Restore may be disabled or rate-limited (1 per 24h on consumer Windows)",
            stderr=proc.stderr, exit_code=proc.returncode,
            status="needs_user",
            note="Enable System Protection on the system drive via Settings > System > About > Advanced system settings.",
        )
    return _ok_tr(description=description, exit_code=proc.returncode, verified=True)
