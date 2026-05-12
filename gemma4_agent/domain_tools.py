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
    return _err("unknown source_manager action", action=action)


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
    return _err("unknown dependency action", action=action)


def contacts_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(local_state=True, count=len(_resources_by_kind(state, "contact")))
    if action == "list":
        return _ok(contacts=_resources_by_kind(state, "contact", include_closed=bool(args.get("include_closed", False))))
    if action in {"create", "add"}:
        name = str(args.get("name") or "").strip()
        if not name:
            return _err("missing contact name")
        resource = state.register_resource(
            "contact",
            name,
            metadata={"name": name, "email": args.get("email"), "phone": args.get("phone"), "notes": args.get("notes"), "created_at": datetime.now().isoformat()},
        )
        return _ok(contact=resource.get("resource"))
    if action == "search":
        query = str(args.get("query") or args.get("name") or "").casefold()
        matches = [c for c in _resources_by_kind(state, "contact", include_closed=True) if query in json.dumps(c, ensure_ascii=False).casefold()]
        return _ok(matches=matches[: int(args.get("limit", 10))], count=len(matches))
    if action == "delete":
        contact = _find_resource(args, state, "contact")
        return state.mark_cleaned(str(contact["id"]), {"deleted": True}) if contact else _err("contact not found")
    if action in {"update", "export_vcard", "import_vcard"}:
        return _err(f"contacts.{action} is not implemented yet", status="needs_implementation", verified=False)
    return _err("unknown contacts action", action=action)


def notes_tasks_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(notes=len(_resources_by_kind(state, "note")), tasks=len(_resources_by_kind(state, "task")))
    if action in {"note_create", "create_note"}:
        title = str(args.get("title") or "Nota").strip()
        text = str(args.get("text") or args.get("content") or "").strip()
        resource = state.register_resource("note", title, metadata={"title": title, "text": text, "tags": args.get("tags"), "created_at": datetime.now().isoformat()})
        return _ok(note=resource.get("resource"))
    if action in {"task_create", "create_task"}:
        title = str(args.get("title") or args.get("text") or "Tarea").strip()
        resource = state.register_resource("task", title, metadata={"title": title, "text": args.get("text"), "due": args.get("due"), "status": "open", "created_at": datetime.now().isoformat()})
        return _ok(task=resource.get("resource"))
    if action in {"note_list", "notes", "list"}:
        return _ok(notes=_resources_by_kind(state, "note", include_closed=bool(args.get("include_closed", False))))
    if action in {"task_list", "tasks"}:
        return _ok(tasks=_resources_by_kind(state, "task", include_closed=bool(args.get("include_closed", False))))
    if action in {"note_search", "task_search", "search"}:
        kinds = ["note", "task"] if action == "search" else ["note"] if action.startswith("note") else ["task"]
        query = str(args.get("query") or "").casefold()
        matches = [r for r in _resources_by_kind(state, kinds, include_closed=True) if query in json.dumps(r, ensure_ascii=False).casefold()]
        return _ok(matches=matches[: int(args.get("limit", 10))], count=len(matches))
    if action == "task_complete":
        task = _find_resource(args, state, "task")
        return _update_resource_metadata(state, str(task["id"]), {"status": "completed", "completed_at": datetime.now().isoformat()}) if task else _err("task not found")
    if action in {"note_delete", "task_delete", "delete"}:
        resource = _find_resource(args, state, ["note", "task"])
        return state.mark_cleaned(str(resource["id"]), {"deleted": True}) if resource else _err("note/task not found")
    if action in {"note_update", "task_update"}:
        resource = _find_resource(args, state, "note" if action.startswith("note") else "task")
        if not resource:
            return _err("note/task not found")
        updates = {k: args[k] for k in ("title", "text", "content", "due", "tags") if k in args}
        if "content" in updates and "text" not in updates:
            updates["text"] = updates.pop("content")
        return _update_resource_metadata(state, str(resource["id"]), updates)
    return _err("unknown notes_tasks action", action=action)


def local_calendar_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(local_state=True, event_count=len(_resources_by_kind(state, "calendar_event")))
    if action in {"event_list", "list"}:
        return _ok(events=_resources_by_kind(state, "calendar_event", include_closed=bool(args.get("include_closed", False))))
    if action == "event_create":
        title = str(args.get("title") or "Evento").strip()
        start = str(args.get("start") or args.get("due") or datetime.now().isoformat())
        end = str(args.get("end") or "")
        resource = state.register_resource("calendar_event", title, metadata={"title": title, "start": start, "end": end, "location": args.get("location"), "notes": args.get("notes")})
        return _ok(event=resource.get("resource"))
    if action in {"event_delete", "delete"}:
        event = _find_resource(args, state, "calendar_event")
        return state.mark_cleaned(str(event["id"]), {"deleted": True}) if event else _err("event not found")
    if action == "ics_export":
        events = _resources_by_kind(state, "calendar_event")
        path = _calendar_export_path(args, state)
        path.write_text(_events_to_ics(events), encoding="utf-8")
        return _ok(path=str(path.resolve()), events=len(events))
    if action in {"event_update", "ics_import"}:
        return _err(f"local_calendar.{action} is not implemented yet", status="needs_implementation", verified=False)
    return _err("unknown local_calendar action", action=action)


def habit_tracker_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(habits=len(_resources_by_kind(state, "habit")))
    if action == "list":
        return _ok(habits=_resources_by_kind(state, "habit", include_closed=bool(args.get("include_closed", False))))
    if action == "create":
        name = str(args.get("name") or args.get("title") or "").strip()
        if not name:
            return _err("missing habit name")
        resource = state.register_resource("habit", name, metadata={"name": name, "frequency": args.get("frequency") or "daily", "logs": []})
        return _ok(habit=resource.get("resource"))
    if action == "log":
        habit = _find_resource(args, state, "habit")
        if not habit:
            return _err("habit not found")
        logs = list(habit.setdefault("metadata", {}).get("logs") or [])
        logs.append({"at": str(args.get("at") or datetime.now().isoformat()), "value": args.get("value", True), "note": args.get("note")})
        return _update_resource_metadata(state, str(habit["id"]), {"logs": logs})
    if action == "stats":
        habit = _find_resource(args, state, "habit")
        if not habit:
            return _err("habit not found")
        logs = habit.get("metadata", {}).get("logs") or []
        return _ok(habit=habit, log_count=len(logs), last=logs[-1] if logs else None)
    if action == "delete":
        habit = _find_resource(args, state, "habit")
        return state.mark_cleaned(str(habit["id"]), {"deleted": True}) if habit else _err("habit not found")
    return _err("unknown habit_tracker action", action=action)


def local_search_tool(args: dict[str, Any]) -> dict[str, Any]:
    action = str(args.get("action") or "search").casefold()
    if action == "status":
        return _ok(everything_cli=bool(shutil.which("es.exe")), backend="python_rglob")
    if action == "search":
        root = Path(str(args.get("root") or Path.home())).expanduser()
        if not root.exists():
            return _err("root not found", root=str(root))
        query = str(args.get("query") or "").casefold()
        pattern = str(args.get("pattern") or "*")
        limit = int(args.get("limit", 50))
        include_content = bool(args.get("include_content", False))
        results = []
        try:
            iterator = root.rglob(pattern) if bool(args.get("recursive", True)) else root.glob(pattern)
            for path in iterator:
                if len(results) >= limit:
                    break
                name_hit = query in path.name.casefold() if query else True
                content_hit = False
                snippet = ""
                if include_content and path.is_file() and path.stat().st_size < int(args.get("max_bytes", 2_000_000)):
                    try:
                        text = path.read_text(encoding="utf-8", errors="replace")
                        idx = text.casefold().find(query)
                        content_hit = idx >= 0
                        snippet = text[max(0, idx - 80): idx + 180] if content_hit else ""
                    except OSError:
                        pass
                if name_hit or content_hit:
                    results.append({"path": str(path), "is_file": path.is_file(), "size": path.stat().st_size if path.is_file() else None, "snippet": snippet})
        except OSError as exc:
            return _err(f"search failed: {exc}", root=str(root))
        return _ok(results=results, count=len(results), root=str(root))
    if action == "recent":
        root = Path(str(args.get("root") or Path.home())).expanduser()
        files = []
        for path in root.rglob(str(args.get("pattern") or "*")):
            if path.is_file():
                try:
                    files.append((path.stat().st_mtime, path))
                except OSError:
                    pass
            if len(files) > 5000:
                break
        files.sort(reverse=True)
        return _ok(files=[{"path": str(p), "modified": datetime.fromtimestamp(ts).isoformat()} for ts, p in files[: int(args.get("limit", 20))]])
    return _err("unknown local_search action", action=action)


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
    if action in {"printer_default_set", "print_file", "cancel_job", "scanners_list", "scan_document"}:
        return _err(f"printer_scanner.{action} is not implemented yet", status="needs_implementation", verified=False)
    return _err("unknown printer_scanner action", action=action)


def desktop_layout_tool(args: dict[str, Any], state: AgentState, executor: Executor) -> dict[str, Any]:
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(can_snapshot_windows=True, restore_supported=False)
    if action in {"windows", "list_windows"}:
        return executor("window", {"action": "list", "limit": int(args.get("limit", 80))})
    if action == "displays":
        return _powershell_json("Get-CimInstance -Namespace root\\wmi -ClassName WmiMonitorBasicDisplayParams | Select-Object InstanceName,MaxHorizontalImageSize,MaxVerticalImageSize,Active | ConvertTo-Json -Depth 3", "displays")
    if action == "snapshot":
        windows = executor("window", {"action": "list", "limit": int(args.get("limit", 120))})
        checkpoint = state.checkpoint("desktop layout snapshot", metadata={"windows": windows.get("windows", []), "created_by": "desktop_layout"})
        return _ok(snapshot=checkpoint.get("checkpoint"), windows=windows)
    if action == "restore":
        return _err("desktop_layout.restore is not implemented yet", status="needs_implementation", verified=False)
    return _err("unknown desktop_layout action", action=action)


def backup_sync_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(backend="zipfile", restore_supported=False)
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
    if action in {"restore", "dedupe"}:
        return _err(f"backup_sync.{action} is not implemented yet", status="needs_implementation", verified=False)
    return _err("unknown backup_sync action", action=action)


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
            f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
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
