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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .state import AgentState


Executor = Callable[[str, dict[str, Any]], dict[str, Any]]


def _ok(**kwargs: Any) -> dict[str, Any]:
    return {"ok": True, **kwargs}


def _err(message: str, **kwargs: Any) -> dict[str, Any]:
    return {"ok": False, "error": message, **kwargs}


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
            return _err("missing or invalid path")
        os.startfile(path) if os.name == "nt" else webbrowser.open(path.as_uri())
        return _ok(path=str(path.resolve()), opened=True)
    if action in {"edit_presentation", "edit_document", "edit_spreadsheet", "export_pdf"}:
        return _err(
            f"office.{action} is not implemented yet",
            status="needs_dependency",
            verified=False,
            completion_status="needs_implementation",
            note="Creation and inspection are implemented first; editing/export need template-specific handling.",
        )
    return _err("unknown office action", action=action)


def audio_device_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action in {"status", "list"}:
        devices = _audio_endpoints()
        helper = _find_soundvolumeview()
        return _ok(
            devices=devices,
            count=len(devices),
            soundvolumeview=str(helper) if helper else None,
            can_set_default=bool(helper),
            install_hint="Download SoundVolumeView from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW to the exe path.",
        )
    if action == "snapshot":
        checkpoint = state.checkpoint("audio device snapshot", metadata={"devices": _audio_endpoints(), "default": None})
        return _ok(snapshot=checkpoint.get("checkpoint"), note="Windows default device detection is helper-dependent; device list was saved.")
    if action in {"set_default", "set_default_communications"}:
        return _set_default_audio_device(args, state, communications=action == "set_default_communications")
    if action in {"set_app_route", "get_app_routes", "restore"}:
        return _err(
            f"audio_device.{action} needs a dedicated local helper/API",
            status="needs_dependency",
            verified=False,
            completion_status="needs_dependency",
            install_hint="Use SoundVolumeView for default devices; per-app routing needs a Windows audio routing helper.",
        )
    return _err("unknown audio_device action", action=action)


def notification_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(windows=True, scheduled_tasks=shutil.which("powershell") is not None, backend="windows_scheduled_tasks")
    if action in {"list", "timer_list", "alarm_list", "reminder_list"}:
        resources = state.list_resources(include_closed=bool(args.get("include_closed", False))).get("resources", [])
        items = [r for r in resources if r.get("kind") in {"notification", "timer", "alarm", "local_reminder"}]
        return _ok(items=items, count=len(items))
    if action in {"toast_now", "notify_sound"}:
        title = str(args.get("title") or "Gemma4 Agent").strip()
        text = str(args.get("text") or args.get("message") or title).strip()
        result = _show_message_box(title, text)
        return _ok(title=title, text=text, attempted=True, verified=False, result=result, completion_status="notification_requested")
    if action in {"timer_start", "alarm_create", "reminder_create", "toast_schedule"}:
        return _schedule_notification(args, state, kind=_kind_for_notification_action(action))
    if action in {"timer_cancel", "alarm_cancel", "reminder_delete", "delete"}:
        return _delete_notification(args, state)
    if action in {"reminder_update"}:
        return _err("notification.reminder_update is not implemented yet", status="needs_implementation", verified=False)
    return _err("unknown notification action", action=action)


def routine_tool(args: dict[str, Any], state: AgentState, executor: Executor | None = None) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(local_state=True, run_now=bool(executor), triggers=["manual"], persistent_triggers=False)
    if action == "list":
        resources = state.list_resources(include_closed=bool(args.get("include_closed", False))).get("resources", [])
        routines = [r for r in resources if r.get("kind") == "routine"]
        return _ok(routines=routines, count=len(routines))
    if action == "create":
        steps = args.get("steps") or []
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except json.JSONDecodeError:
                return _err("steps must be a JSON array of {tool,args}")
        if not isinstance(steps, list) or not steps:
            return _err("routine.create requires steps array")
        label = str(args.get("name") or args.get("label") or f"Routine {int(time.time())}")
        resource = state.register_resource(
            "routine",
            label,
            cleanup_tool="routine",
            cleanup_args={"action": "delete", "name": label},
            metadata={"enabled": bool(args.get("enabled", True)), "trigger": args.get("trigger") or "manual", "steps": steps},
        )
        return _ok(routine=resource.get("resource"), status="done")
    if action == "run_now":
        routine = _find_routine(args, state)
        if not routine:
            return _err("routine not found")
        if not executor:
            return _err("routine.run_now requires an executor", status="needs_implementation", verified=False)
        if routine.get("metadata", {}).get("enabled") is False:
            return _err("routine is disabled", routine=routine)
        results = []
        for index, step in enumerate(routine.get("metadata", {}).get("steps") or [], start=1):
            if not isinstance(step, dict):
                results.append({"index": index, "ok": False, "error": "invalid step"})
                break
            tool = str(step.get("tool") or "").strip()
            step_args = step.get("args") if isinstance(step.get("args"), dict) else {}
            if not tool or tool == "routine":
                results.append({"index": index, "ok": False, "error": "invalid or recursive tool", "tool": tool})
                break
            result = executor(tool, step_args)
            results.append({"index": index, "tool": tool, "args": step_args, "result": result, "ok": bool(result.get("ok"))})
            if not result.get("ok"):
                break
        return _ok(routine=routine, results=results, completed=all(item.get("ok") for item in results))
    if action in {"delete", "enable", "disable"}:
        routine = _find_routine(args, state)
        if not routine:
            return _err("routine not found")
        if action == "delete":
            return state.mark_cleaned(str(routine["id"]), {"deleted": True})
        enabled = action == "enable"
        return _update_resource_metadata(state, str(routine["id"]), {"enabled": enabled})
    if action in {"simulate", "history"}:
        routine = _find_routine(args, state)
        return _ok(routine=routine, note="history is not persisted yet beyond tool traces") if routine else _err("routine not found")
    return _err("unknown routine action", action=action)


def media_tool(args: dict[str, Any], executor: Executor) -> dict[str, Any]:
    action = str(args.get("action") or "play").casefold()
    if action == "status":
        return _ok(backends=["browser_youtube", "windows_media_keys", "local_file"], now_playing_supported=False)
    if action == "play":
        query = str(args.get("query") or args.get("song") or args.get("title") or "").strip()
        path = str(args.get("path") or "").strip()
        provider = str(args.get("provider") or "youtube").casefold()
        if path:
            target = Path(path).expanduser()
            if not target.exists():
                return _err("media file not found", path=path)
            os.startfile(target) if os.name == "nt" else webbrowser.open(target.as_uri())
            return _ok(action="play", provider="local_file", path=str(target.resolve()), opened=True)
        if provider in {"youtube", "yt", "browser"}:
            return executor("browser", {"action": "youtube_play", "query": query or "musica"})
        return _err("unsupported media provider", provider=provider, status="needs_dependency", verified=False)
    if action in {"pause", "resume", "play_pause"}:
        return executor("audio", {"action": "media_play_pause"})
    if action == "stop":
        return executor("audio", {"action": "media_stop"})
    if action == "next":
        return executor("audio", {"action": "next"})
    if action == "previous":
        return executor("audio", {"action": "previous"})
    if action in {"now_playing", "queue_add", "queue_clear", "queue_list", "volume_for_app", "search_local_library", "cast_lan"}:
        return _err(f"media.{action} is not implemented yet", status="needs_dependency", verified=False)
    return _err("unknown media action", action=action)


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
        slide.shapes.title.text = str(first.get("title") or title)
        slide.placeholders[1].text = str(first.get("subtitle") or first.get("body") or "")
        for item in slides[1:]:
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = str(item.get("title") or "Slide")
            body = slide.placeholders[1].text_frame
            body.clear()
            bullets = item.get("bullets") if isinstance(item.get("bullets"), list) else None
            if bullets:
                for bullet in bullets:
                    p = body.add_paragraph()
                    p.text = str(bullet)
                    p.level = 0
            else:
                body.text = str(item.get("body") or "")
    prs.save(path)
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
    doc.save(path)
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
    ws.title = "Datos"
    rows = args.get("rows") if isinstance(args.get("rows"), list) else []
    if not rows:
        rows = [["Campo", "Valor"], ["Titulo", title]]
    for row in rows:
        ws.append(row if isinstance(row, list) else [str(row)])
    wb.save(path)
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
            install_hint="Download SoundVolumeView and set GEMMA4_SOUNDVOLUMEVIEW to its exe path.",
        )
    roles = ["2"] if communications else ["0", "1"]
    checkpoint = state.checkpoint("audio default device change", metadata={"requested": name, "helper": str(helper), "previous_default": None})
    results = []
    for role in roles:
        proc = subprocess.run([str(helper), "/SetDefault", name, role], capture_output=True, text=True, timeout=20)
        results.append({"role": role, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
    ok = all(item["exit_code"] == 0 for item in results)
    return _ok(requested=name, helper=str(helper), roles=roles, results=results, checkpoint=checkpoint.get("checkpoint"), verified=ok, status="done" if ok else "needs_verification")


def _show_message_box(title: str, text: str) -> dict[str, Any]:
    script = f"Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('{_ps_quote(text)}','{_ps_quote(title)}')"
    return _run_detached_powershell(script)


def _schedule_notification(args: dict[str, Any], state: AgentState, *, kind: str) -> dict[str, Any]:
    title = str(args.get("title") or kind.title()).strip()
    text = str(args.get("text") or args.get("message") or title).strip()
    due = _notification_due(args)
    task_name = f"Gemma4Agent_{kind}_{int(time.time())}"
    display_script = f"Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('{_ps_quote(text)}','{_ps_quote(title)}')"
    ps = f"""
$Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -WindowStyle Hidden -Command "{display_script}"'
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date '{due.strftime('%Y-%m-%d %H:%M:%S')}')
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName '{_ps_quote(task_name)}' -TaskPath '\\Gemma4Agent\\' -Action $Action -Trigger $Trigger -Settings $Settings -Description '{_ps_quote(text)}' -Force | Out-Null
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30)
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


def _kind_for_notification_action(action: str) -> str:
    if action.startswith("timer"):
        return "timer"
    if action.startswith("alarm"):
        return "alarm"
    if action.startswith("reminder"):
        return "local_reminder"
    return "notification"


def _notification_due(args: dict[str, Any]) -> datetime:
    seconds = args.get("seconds")
    minutes = args.get("minutes")
    if seconds is not None:
        return datetime.now() + timedelta(seconds=max(1, int(seconds)))
    if minutes is not None:
        return datetime.now() + timedelta(minutes=max(1, int(minutes)))
    raw = str(args.get("due") or args.get("time") or "").strip()
    if raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
        except ValueError:
            pass
    return datetime.now() + timedelta(minutes=5)


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
    data = state._load()
    resource = data.get("resources", {}).get(resource_id)
    if not resource:
        return _err("resource not found", resource_id=resource_id)
    metadata = resource.setdefault("metadata", {})
    metadata.update(updates)
    state._save(data)
    return _ok(resource=resource)


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
