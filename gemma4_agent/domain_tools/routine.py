"""Routine domain tool — extracted from domain_tools.py.

Sistema de rutinas (macros) persistidas: triggers (manual/cron/once/on_app_*/
on_process_*/on_phrase), steps (lista de tool+args). Persistencia + scheduling
via Windows Scheduled Tasks + watcher poll + chat phrase hook. Importer de
TriggerCMD para bulk-create de on_phrase routines desde commands.json.

Seguridad (CC-100 / T3-routine-cron-trigger-ps-injection-028): TODO valor que
se interpole en script PS pasa por allowlist regex. Comandos que parecen
destructivos (shutdown/format/del-rf/Remove-Item) se importan DISABLED por
default; el usuario los habilita explícitamente con routine(enable).

Funciones extraídas (12) + 1 constante:
  routine_tool                     (entry, 9 acciones)
  import_triggercmd_entries        (140 LOC, bulk create desde TriggerCMD)
  _terminal_args_for               (TriggerCMD command line -> terminal args)
  _looks_destructive               (regex word-boundary contra _DESTRUCTIVE_*)
  _routine_task_name
  _register_routine_scheduled_task (CC-100 env-var indirection)
  _unregister_routine_scheduled_task
  _build_routine_trigger_ps        (cron/once/weekly/hourly/minutes -> PS)
  _detect_python_executable        (para el routine_runner del scheduled task)
  _enrich_routine_resource         (live ScheduledTaskInfo)
  _append_routine_run              (history con cap atómico)
  _routine_history

Constants:
  _DESTRUCTIVE_COMMAND_TOKENS

Helpers desde domain_tools (lazy):
  _safe_name, _ps_quote, _resources_by_kind, _find_resource, _find_routine,
  _update_resource_metadata, _register_routine_process_watcher (queda en
  domain_tools porque consume watcher_tool internals), active_phrase_triggers.

NOTA: _find_routine y _register_routine_process_watcher NO se movieron acá —
viven en domain_tools.py todavía. routine_tool los llama lazy."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .._ps import (
    PSValidationError,
    RX_DAY_OF_WEEK,
    RX_HHMM,
    RX_ISO_DATETIME,
    ps_safe_literal,
)
from .._shared import _err, _ok
from ..memory_pkg.state import AgentState


Executor = Callable[[str, dict[str, Any]], dict[str, Any]]


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


__all__ = [
    "routine_tool",
    "import_triggercmd_entries",
    "_terminal_args_for",
    "_looks_destructive",
    "_routine_task_name",
    "_register_routine_scheduled_task",
    "_unregister_routine_scheduled_task",
    "_build_routine_trigger_ps",
    "_detect_python_executable",
    "_enrich_routine_resource",
    "_append_routine_run",
    "_routine_history",
    "_DESTRUCTIVE_COMMAND_TOKENS",
]


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
    from .helpers import _find_routine, _update_resource_metadata
    from .watcher import _register_routine_process_watcher
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
        # filtro opcional por origen: "qué automatizaste vos" -> created_by=jarvis.
        # Permite al user revisar/apagar SOLO lo que Jarvis creó (reversibilidad).
        _cb = str(args.get("created_by") or "").strip().casefold()
        if _cb:
            routines = [r for r in routines
                        if str((r.get("metadata") or {}).get("created_by") or "user").casefold() == _cb]
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
                # origen de la rutina: "jarvis" = creada proactivamente por la capa
                # Jarvis (vs creación manual del user). Permite list/disable/delete
                # filtrado y que el user apague TODO lo de Jarvis (reversibilidad,
                # pedido 2026-06-07). Default "user".
                "created_by": str(args.get("created_by") or "user"),
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


def _routine_task_name(label: str) -> str:
    from .helpers import _safe_name
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
    from .helpers import _ps_quote
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
    from .helpers import _ps_quote
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
