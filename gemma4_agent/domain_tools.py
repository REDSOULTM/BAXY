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
    return _err("unknown audio_device action", action=action)


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
    return _err("unknown notification action", action=action)


def routine_tool(args: dict[str, Any], state: AgentState, executor: Executor | None = None) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(
            local_state=True,
            run_now=bool(executor),
            triggers=["manual", "cron", "once", "on_app_open", "on_app_close", "on_process_start", "on_process_exit"],
            persistent_triggers=True,
            backend="windows_scheduled_tasks + watcher poll",
            deferred_triggers=["on_file_change", "on_network_event"],
            deferred_reason="File change triggers belong to the watcher tool directly; network events need ETW subscription.",
        )
    if action == "list":
        resources = state.list_resources(include_closed=bool(args.get("include_closed", False))).get("resources", [])
        routines = [_enrich_routine_resource(r) for r in resources if r.get("kind") == "routine"]
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
        # Validate each step
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                return _err(f"step {index} is not an object", step=step)
            if not str(step.get("tool") or "").strip():
                return _err(f"step {index} has no tool", step=step)
            if str(step.get("tool")).strip() == "routine":
                return _err(f"step {index} cannot call routine recursively")
        label = str(args.get("name") or args.get("label") or f"Routine {int(time.time())}")
        trigger = args.get("trigger") if isinstance(args.get("trigger"), dict) else {"type": str(args.get("trigger") or "manual")}
        trigger_type = str(trigger.get("type") or "manual").casefold()
        process_triggers = {"on_app_open", "on_app_close", "on_process_start", "on_process_exit"}
        if trigger_type not in {"manual", "cron", "once"} | process_triggers:
            return _err(
                f"trigger type '{trigger_type}' is not implemented yet; supported: manual, cron, once, on_app_open, on_app_close",
                status="needs_implementation",
                deferred=trigger_type,
            )
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
            # Patch watcher_id into the routine's metadata so cleanup tears down both.
            data = state._load()
            rec = data.get("resources", {}).get(routine_id)
            if rec:
                rec.setdefault("metadata", {})["watcher_id"] = watcher_id
                state._save(data)
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
            step_args = step.get("args") if isinstance(step.get("args"), dict) else {}
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
    return _err("unknown routine action", action=action)


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
    return _err("unknown smart_home action", action=action)


def _hass_alive(host: str) -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(f"{host}/api/", headers={"User-Agent": "Gemma4Agent/1.0"})
        with urllib.request.urlopen(req, timeout=2.0):
            return True
    except Exception:
        # /api/ may require auth (returns 401). 401 still means HA is alive.
        try:
            import urllib.error  # noqa: F401
            return True
        except Exception:
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
    payload = args.get("data") if isinstance(args.get("data"), dict) else {}
    # Merge target into payload (HA accepts entity_id at top-level).
    target = args.get("target") if isinstance(args.get("target"), dict) else None
    if target:
        payload = {**payload, **target}
    # For toggle/turn_off/turn_on on a switch/light, snapshot before so rollback exists.
    rollback_step = None
    if service in {"turn_on", "turn_off", "toggle"} and payload.get("entity_id"):
        eid = payload["entity_id"] if isinstance(payload["entity_id"], str) else (payload["entity_id"][0] if payload["entity_id"] else None)
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
        return _err("unknown study action", action=action)
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
    return _err("unknown accessibility action", action=action)


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
    proc = subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True, text=True, timeout=15)
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
    return _err("unknown peripheral action", action=action)


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
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
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
    return _err("unknown form_filler action", action=action)


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
    return _err("unknown creative_local action", action=action)


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
            return _database_query(conn, args)
        if action == "execute":
            return _database_execute(conn, args)
        if action == "export_csv":
            return _database_export_csv(conn, args, state)
        return _err("unknown database action", action=action)
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
        if importlib.util.find_spec("mysql.connector") is not None:
            import mysql.connector  # type: ignore[import-not-found]
            conn = mysql.connector.connect(
                host=args.get("host", "localhost"),
                port=int(args.get("port", 3306)),
                user=args.get("user"),
                password=args.get("password"),
                database=args.get("database") or args.get("db"),
            )
        elif importlib.util.find_spec("pymysql") is not None:
            import pymysql  # type: ignore[import-not-found]
            conn = pymysql.connect(
                host=args.get("host", "localhost"),
                port=int(args.get("port", 3306)),
                user=args.get("user"),
                password=args.get("password"),
                database=args.get("database") or args.get("db"),
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
    table = str(args.get("table") or "").strip()
    if not table:
        return _err("missing table name")
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


def _database_query(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    sql = str(args.get("sql") or args.get("query") or "").strip()
    if not sql:
        return _err("missing sql")
    if not _is_read_only_sql(sql):
        return _err(
            "query is restricted to read-only statements (SELECT, WITH, EXPLAIN, PRAGMA, SHOW). Use execute(...) for mutations.",
            status="needs_user",
        )
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


def _database_execute(conn: Any, args: dict[str, Any]) -> dict[str, Any]:
    sql = str(args.get("sql") or args.get("query") or "").strip()
    if not sql:
        return _err("missing sql")
    if _is_read_only_sql(sql):
        return _err("execute is for mutations; use query(...) for SELECT")
    cur = conn.cursor()
    cur.execute(sql)
    try:
        conn.commit()
    except Exception:
        pass
    rowcount = cur.rowcount if hasattr(cur, "rowcount") else None
    return _ok(sql=sql, rowcount=rowcount, verified=True)


def _database_export_csv(conn: Any, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    sql = str(args.get("sql") or args.get("query") or "").strip()
    if not sql or not _is_read_only_sql(sql):
        return _err("export_csv requires a read-only SQL query")
    dst_raw = str(args.get("dst") or args.get("output") or "").strip()
    if dst_raw:
        dst = Path(dst_raw).expanduser()
    else:
        dst = state.path.parent / "database_exports" / f"export_{int(time.time())}.csv"
    dst.parent.mkdir(parents=True, exist_ok=True)
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
    return _ok(sql=sql, dst=str(dst), rows=len(rows), verified=dst.is_file())


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
    return _err("unknown container action", action=action)


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
    extra = args.get("args") if isinstance(args.get("args"), list) else []
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
    return _err("unknown photo_library action", action=action)


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
            exif_raw = img._getexif() or {}
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
    size_arg = args.get("size", 256)
    if isinstance(size_arg, (list, tuple)) and len(size_arg) == 2:
        size = (int(size_arg[0]), int(size_arg[1]))
    else:
        n = int(size_arg)
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
        return _err("unknown fact_check action", action=action)

    claim = str(args.get("claim") or "").strip()
    if not claim:
        return _err("missing claim")
    sources_arg = args.get("sources") if isinstance(args.get("sources"), list) else []
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
    return _err("unknown data_analysis action", action=action)


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
    if err:
        return err
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
    if err:
        return err
    desc = df.describe(include="all").fillna("").to_dict()
    return _ok(path=str(args.get("path")), rows=int(len(df)), describe=desc)


def _data_csv_query(args: dict[str, Any]) -> dict[str, Any]:
    df, err = _data_load_df(args)
    if err:
        return err
    query = str(args.get("query") or "").strip()
    if not query:
        return _err("missing query (pandas .query() expression)")
    try:
        result = df.query(query)
    except Exception as exc:
        return _err(f"query failed: {exc}", query=query)
    limit = int(args.get("limit", 50))
    return _ok(
        path=str(args.get("path")), query=query,
        matched_rows=int(len(result)),
        preview=result.head(limit).to_dict(orient="records"),
    )


def _data_csv_head(args: dict[str, Any]) -> dict[str, Any]:
    df, err = _data_load_df(args)
    if err:
        return err
    n = int(args.get("n", 10))
    return _ok(path=str(args.get("path")), n=n, rows=df.head(n).to_dict(orient="records"))


def _data_csv_to_xlsx(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    df, err = _data_load_df(args)
    if err:
        return err
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
    if err:
        return err
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
    return _err("unknown network action", action=action)


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
    if addresses == ["AUTO"] or addresses == ["auto"]:
        # Restore automatic DNS.
        cmd = f"Set-DnsClientServerAddress -InterfaceAlias '{_ps_quote(adapter)}' -ResetServerAddresses"
    else:
        addr_list = ",".join(f"'{a}'" for a in addresses)
        cmd = f"Set-DnsClientServerAddress -InterfaceAlias '{_ps_quote(adapter)}' -ServerAddresses ({addr_list})"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=15)
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
    state_filter = str(args.get("state") or "Established").strip()
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Get-NetTCPConnection -State {state_filter} -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess | ConvertTo-Json -Depth 3"],
        capture_output=True, text=True, timeout=20,
    )
    if proc.returncode != 0:
        return _err("connections query failed", stderr=proc.stderr)
    raw = proc.stdout.strip()
    if not raw:
        return _ok(connections=[], count=0, state=state_filter)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err("connections invalid JSON", raw=raw[:500])
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
    return _err("unknown watcher action", action=action)


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
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30)
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
        # Update snapshot.
        data = state._load()
        rec = data.get("resources", {}).get(str(target["id"]))
        if rec:
            rec["metadata"]["snapshot"] = snapshot_after
            rec["metadata"]["last_change"] = datetime.now().isoformat()
            state._save(data)
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
    return _err("unknown job_manager action", action=action)


def _job_manager_start(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    command = args.get("command")
    if isinstance(command, str):
        cmd = command.split()
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
        data = state._load()
        rec = data.get("resources", {}).get(rid)
        if rec:
            rec["cleanup_args"] = {"action": "cancel", "job_id": rid}
            state._save(data)
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
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"], capture_output=True, text=True, timeout=10)
        else:
            os.kill(int(pid), 15)
    except Exception as exc:
        return _err(f"failed to kill pid {pid}: {exc}", pid=pid)
    state.mark_cleaned(str(job["id"]), {"killed": True, "pid": pid})
    return _ok(job_id=str(job["id"]), pid=pid, killed=True)


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
        return _ok(
            note="Run `cleanmgr /sageset:1` once to choose categories, then `cleanmgr /sagerun:1` to apply. We do not run this automatically.",
            command_describe=["cleanmgr", "/sageset:1"],
            command_apply=["cleanmgr", "/sagerun:1"],
            status="needs_user",
        )
    if action == "restore_point_create":
        return _maintenance_restore_point_create(args)
    return _err("unknown maintenance action", action=action)


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
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30)
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
    state.note("Defender QuickScan requested", metadata={"started_at": datetime.now().isoformat()})
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Start-MpScan -ScanType QuickScan"],
        capture_output=True, text=True, timeout=900,
    )
    return _ok(
        scan="QuickScan",
        exit_code=proc.returncode,
        stdout=proc.stdout[-2000:],
        stderr=proc.stderr[-2000:],
        verified=proc.returncode == 0,
        status="done" if proc.returncode == 0 else "needs_verification",
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
    log = str(args.get("log") or "System").strip()
    level = args.get("level")  # 1=Critical 2=Error 3=Warning 4=Information
    hours = int(args.get("hours", 24))
    limit = int(args.get("limit", 50))
    filt = {"LogName": log, "StartTime": "{StartTime}"}
    if level is not None:
        filt["Level"] = int(level)
    ht = ";".join(f"{k}='{v}'" if k != "Level" else f"{k}={v}" for k, v in filt.items())
    # Build hashtable inline; using PowerShell since it's safer than building string.
    cmd = (
        f"$start = (Get-Date).AddHours(-{hours}); "
        f"$f = @{{ LogName='{log}'; StartTime=$start"
        f"{'' if level is None else f'; Level={int(level)}'}"
        f" }}; "
        f"Get-WinEvent -FilterHashtable $f -MaxEvents {limit} -ErrorAction SilentlyContinue | "
        f"Select-Object TimeCreated,Id,LevelDisplayName,ProviderName,Message | ConvertTo-Json -Depth 3"
    )
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return _err("event_logs_query failed", stderr=proc.stderr)
    raw = proc.stdout.strip()
    if not raw:
        return _ok(log=log, events=[], count=0, hours=hours)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err("event_logs_query invalid JSON", raw=raw[:500])
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
    return _err("unknown media_edit action", action=action)


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
    inputs = args.get("inputs") if isinstance(args.get("inputs"), list) else []
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
    list_file.write_text("\n".join(f"file '{p.as_posix()}'" for p in paths) + "\n", encoding="utf-8")
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
    return _err("unknown game_launcher action", action=action)


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
            current_id = m.group(1)
            games_by_id.setdefault(current_id, {"launcher": "gog", "game_id": current_id})
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
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30)
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
    return _err("unknown device_settings action", action=action)


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
    proc = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=15)
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
    proc = subprocess.run(["netsh", "wlan", "show", "profiles"], capture_output=True, text=True, timeout=15)
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
    proc = subprocess.run(["netsh", "wlan", "show", "networks", "mode=bssid"], capture_output=True, text=True, timeout=20)
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
    return _err("unknown developer action", action=action)


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
    extra_args = args.get("args") if isinstance(args.get("args"), list) else []
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
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen(cmd, cwd=str(root), stdout=log_file, stderr=subprocess.STDOUT, creationflags=creationflags)
    resource = state.register_resource(
        "dev_server",
        f"{cmd[0]} {' '.join(cmd[1:])}",
        cleanup_tool="developer",
        cleanup_args={"action": "stop_dev_server"},
        metadata={"cmd": cmd, "cwd": str(root), "pid": proc.pid, "log": str(log_path), "started_at": datetime.now().isoformat()},
    )
    # The cleanup_args needs the server_id, but we only have it after registration.
    # Patch it in-place.
    rid = resource.get("resource", {}).get("id")
    if rid:
        data = state._load()
        rec = data.get("resources", {}).get(rid)
        if rec:
            rec["cleanup_args"] = {"action": "stop_dev_server", "server_id": rid}
            state._save(data)
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
    killed = False
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"], capture_output=True, text=True, timeout=10)
        else:
            os.kill(int(pid), 15)
        killed = True
    except Exception as exc:
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
    return _err("unknown document action", action=action)


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
            if hasattr(shape, "text") and shape.text:
                slides_text.append(str(shape.text))
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
        import pdfplumber
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
    import fitz  # PyMuPDF
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


def _routine_task_name(label: str) -> str:
    return f"Gemma4Routine_{_safe_name(label)[:40]}_{int(time.time())}"


def _register_routine_scheduled_task(task_name: str, routine_label: str, trigger: dict[str, Any]) -> dict[str, Any]:
    """Register a Scheduled Task that invokes the routine_runner module."""
    python_exe = _detect_python_executable()
    if not python_exe:
        return _err("no python executable found for scheduled task", status="needs_dependency", verified=False)
    # Use label resolution at fire time; the runner accepts --label or --id.
    arg_line = f'-m gemma4_agent.routine_runner --label "{routine_label}"'
    trigger_ps = _build_routine_trigger_ps(trigger)
    if not trigger_ps:
        return _err(f"invalid routine trigger: {trigger}", trigger=trigger)
    ps = f"""
$Action = New-ScheduledTaskAction -Execute '{_ps_quote(python_exe)}' -Argument '{_ps_quote(arg_line)}'
$Trigger = {trigger_ps}
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName '{_ps_quote(task_name)}' -TaskPath '\\Gemma4Agent\\' -Action $Action -Trigger $Trigger -Settings $Settings -Description 'Gemma4 routine: {_ps_quote(routine_label)}' -Force | Out-Null
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return _err("failed to register routine scheduled task", stderr=proc.stderr, exit_code=proc.returncode)
    return _ok(task_name=task_name, trigger=trigger)


def _unregister_routine_scheduled_task(task_name: str) -> dict[str, Any]:
    ps = f"Unregister-ScheduledTask -TaskPath '\\Gemma4Agent\\' -TaskName '{_ps_quote(task_name)}' -Confirm:$false -ErrorAction SilentlyContinue"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=20)
    return {"task_name": task_name, "exit_code": proc.returncode, "stderr": proc.stderr}


def _build_routine_trigger_ps(trigger: dict[str, Any]) -> str | None:
    """Translate a trigger dict into the PowerShell expression for the trigger."""
    ttype = str(trigger.get("type") or "manual").casefold()
    if ttype == "manual":
        return None
    if ttype == "once":
        at = str(trigger.get("at") or "").strip()
        if not at:
            return None
        return f"New-ScheduledTaskTrigger -Once -At (Get-Date '{at}')"
    if ttype == "cron":
        cadence = str(trigger.get("cadence") or trigger.get("every") or "daily").casefold()
        at = str(trigger.get("at") or "09:00").strip()
        if cadence == "daily":
            return f"New-ScheduledTaskTrigger -Daily -At '{at}'"
        if cadence == "weekly":
            days = trigger.get("days_of_week") if isinstance(trigger.get("days_of_week"), list) else ["Monday"]
            days_str = ",".join(str(d) for d in days)
            return f"New-ScheduledTaskTrigger -Weekly -DaysOfWeek {days_str} -At '{at}'"
        if cadence == "hourly":
            return f"New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)"
        if cadence == "minutes":
            n = int(trigger.get("interval_minutes", 5))
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
    data = state._load()
    resource = data.get("resources", {}).get(resource_id)
    if not resource:
        return
    metadata = resource.setdefault("metadata", {})
    history = list(metadata.get("history") or [])
    history.append(run_record)
    # Keep last 50 runs to avoid unbounded growth.
    metadata["history"] = history[-50:]
    metadata["last_run"] = run_record
    state._save(data)


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


def media_tool(args: dict[str, Any], executor: Executor, state: AgentState | None = None) -> dict[str, Any]:
    action = str(args.get("action") or "play").casefold()
    if action == "status":
        return _ok(
            backends=["browser_youtube", "windows_media_keys", "local_file", "vlc_cli", "winrt_smtc"],
            now_playing_supported=True,
            vlc_available=bool(shutil.which("vlc") or shutil.which("vlc.exe")),
            note="now_playing uses Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager via PowerShell.",
        )
    if action == "play":
        query = str(args.get("query") or args.get("song") or args.get("title") or "").strip()
        path = str(args.get("path") or "").strip()
        provider = str(args.get("provider") or "youtube").casefold()
        if path:
            return _media_play_local(path, args)
        if provider in {"youtube", "yt", "browser"}:
            return executor("browser", {"action": "youtube_play", "query": query or "musica"})
        if provider == "vlc":
            vlc = shutil.which("vlc") or shutil.which("vlc.exe")
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
        return _err("unsupported media provider", provider=provider, status="needs_dependency", verified=False)
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
    return _err("unknown media action", action=action)


def _media_play_local(path_raw: str, args: dict[str, Any]) -> dict[str, Any]:
    target = Path(path_raw).expanduser()
    if not target.exists():
        return _err("media file not found", path=path_raw)
    backend = str(args.get("backend") or "").casefold()
    if backend == "vlc":
        vlc = shutil.which("vlc") or shutil.which("vlc.exe")
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
    return _err("unknown queue action", action=action)


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
    if action == "update":
        return _contacts_update(args, state)
    if action == "export_vcard":
        return _contacts_export_vcard(args, state)
    if action == "import_vcard":
        return _contacts_import_vcard(args, state)
    if action == "resolve_recipient":
        return _contacts_resolve_recipient(args, state)
    return _err("unknown contacts action", action=action)


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
        data = state._load()
        rec = data.get("resources", {}).get(str(contact["id"]))
        if rec:
            rec["label"] = str(updates["name"])
            state._save(data)
    return _update_resource_metadata(state, str(contact["id"]), updates)


def _contacts_export_vcard(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    contacts = _resources_by_kind(state, "contact", include_closed=False)
    if not contacts:
        return _err("no contacts to export")
    path_raw = str(args.get("path") or "").strip()
    if path_raw:
        path = Path(path_raw).expanduser()
    else:
        path = state.path.parent / "generated" / f"contacts_{time.strftime('%Y%m%d_%H%M%S')}.vcf"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\r\n".join(_contact_to_vcard(c) for c in contacts) + "\r\n"
    path.write_text(body, encoding="utf-8")
    return _ok(path=str(path.resolve()), exported=len(contacts))


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
    if action == "event_update":
        return _calendar_event_update(args, state)
    if action == "ics_import":
        return _calendar_ics_import(args, state)
    return _err("unknown local_calendar action", action=action)


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
        # Also update label so listings reflect the new title.
        data = state._load()
        rec = data.get("resources", {}).get(str(event["id"]))
        if rec:
            rec["label"] = str(updates["title"])
            state._save(data)
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
    return _err("unknown printer_scanner action", action=action)


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
    return _err("unknown desktop_layout action", action=action)


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
    return _err("unknown backup_sync action", action=action)


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

    extracted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    renamed: list[dict[str, Any]] = []
    overwritten: list[dict[str, Any]] = []

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
                if entry.is_dir():
                    (dst / entry.filename).mkdir(parents=True, exist_ok=True)
                    continue
                final_target = dst / entry.filename
                final_target.parent.mkdir(parents=True, exist_ok=True)
                if final_target.exists():
                    if conflict_policy == "skip":
                        skipped.append({"name": entry.filename})
                        continue
                    if conflict_policy == "rename":
                        final_target = _next_available_path(final_target)
                        renamed.append({"from": entry.filename, "to": str(final_target.relative_to(dst))})
                    elif conflict_policy == "overwrite":
                        overwritten.append({"name": entry.filename})
                with archive.open(entry, "r") as src_fh, final_target.open("wb") as dst_fh:
                    shutil.copyfileobj(src_fh, dst_fh)
                extracted.append({"name": entry.filename, "size": entry.file_size, "dst": str(final_target)})
    except (zipfile.BadZipFile, OSError) as exc:
        return _err(f"restore failed: {exc}", backup=str(backup_path), dst=str(dst))

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
