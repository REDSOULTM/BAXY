"""Real Windows tools for the standalone Gemma 4 agent."""

from __future__ import annotations

import csv
import difflib
import html
import json
import os
import random
import re
import shutil
import subprocess
import time
import unicodedata
import urllib.error
import urllib.request
import webbrowser
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from .domain_tools import (
    audio_device_tool,
    backup_sync_tool,
    contacts_tool,
    dependency_tool,
    desktop_layout_tool,
    habit_tracker_tool,
    local_calendar_tool,
    local_search_tool,
    media_tool,
    accessibility_tool,
    container_tool,
    creative_local_tool,
    data_analysis_tool,
    database_tool,
    developer_tool,
    device_settings_tool,
    document_tool,
    fact_check_tool,
    form_filler_tool,
    game_launcher_tool,
    job_manager_tool,
    maintenance_tool,
    media_edit_tool,
    network_tool,
    notes_tasks_tool,
    notification_tool,
    office_tool,
    peripheral_tool,
    photo_library_tool,
    printer_scanner_tool,
    routine_tool,
    smart_home_tool,
    source_manager_tool,
    study_tool,
    watcher_tool,
    whatsapp_tool,
)
from ._ps import parse_ps_json
from .knowledge import KnowledgeStore
from .memory import MemoryStore
from .ops_tools import browser_real_tool, download_tool, email_tool, env_tool, input_tool, ocr_find_text, ocr_image, registry_tool, reminder_tool, state_tool
from .safety import classify_tool_call
from .state import AgentState


ToolFn = Callable[[dict[str, Any]], dict[str, Any]]


DEFAULT_YOUTUBE_SONGS = [
    {"title": "Rick Astley - Never Gonna Give You Up", "video_id": "dQw4w9WgXcQ"},
    {"title": "Queen - Bohemian Rhapsody", "video_id": "fJ9rUzIMcZQ"},
    {"title": "Mark Ronson - Uptown Funk ft. Bruno Mars", "video_id": "OPf0YbXqDm0"},
    {"title": "Luis Fonsi - Despacito ft. Daddy Yankee", "video_id": "kJQP7kiw5Fk"},
    {"title": "Major Lazer & DJ Snake - Lean On", "video_id": "YqeW9_5kURI"},
]

WEB_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gemma4Agent/1.0"
DEFAULT_WEB_SEARCH_PROVIDER = "duckduckgo_html"


def _ok(**kwargs: Any) -> dict[str, Any]:
    return {"ok": True, **kwargs}


def _err(message: str, **kwargs: Any) -> dict[str, Any]:
    return {"ok": False, "error": message, **kwargs}


# ----------------------------------------------------------------------
# Pre-validators: corren ANTES del safety classifier para que inputs
# obviamente inválidos no exijan confirmación al usuario (UX).
# Cada validator recibe el args dict ya validado contra el schema, y
# devuelve None si está OK, o un dict `_err(...)` si hay que rechazar.
# ----------------------------------------------------------------------

_RX_HHMM_LOCAL = re.compile(r"^[0-2]\d:[0-5]\d$")


def _prevalidate_notification(args: dict[str, Any]) -> dict[str, Any] | None:
    """Rechaza `time`/`due` con formato no reconocible antes de gatear."""
    action = str(args.get("action") or "").casefold()
    if action not in {"alarm_create", "reminder_create", "timer_start", "toast_schedule"}:
        return None
    if args.get("seconds") is not None or args.get("minutes") is not None:
        return None
    raw = str(args.get("due") or args.get("time") or "").strip()
    if not raw:
        return None
    # ISO datetime aceptado, HH:MM aceptado, todo lo demás rechazado.
    if _RX_HHMM_LOCAL.fullmatch(raw):
        return None
    try:
        from datetime import datetime as _dt
        _dt.fromisoformat(raw.replace("Z", "+00:00"))
        return None
    except ValueError:
        return _err(
            f"invalid time/due format: {raw!r} (use ISO datetime or HH:MM)",
            status="needs_user",
            time=raw,
        )


def _prevalidate_backup_sync(args: dict[str, Any]) -> dict[str, Any] | None:
    """Detecta zip-slip antes de pedir confirmación: si el zip tiene entries
    fuera del dst, rechazamos directamente."""
    import zipfile
    from pathlib import Path as _P
    action = str(args.get("action") or "").casefold()
    if action != "restore":
        return None
    src_raw = str(args.get("path") or args.get("backup") or args.get("src") or "").strip()
    if not src_raw:
        return None
    src = _P(src_raw).expanduser()
    if not src.is_file():
        return None  # otro código maneja el "not found"
    dst_raw = str(args.get("dst") or args.get("to") or "").strip()
    if not dst_raw:
        return None
    dst = _P(dst_raw).expanduser().resolve()
    try:
        with zipfile.ZipFile(src, "r") as zf:
            for entry in zf.infolist():
                candidate = (dst / entry.filename).resolve()
                if candidate != dst and dst not in candidate.parents:
                    return _err(
                        f"zip contains entries outside dst (zip-slip); refused before confirmation: {entry.filename!r}",
                        status="failed",
                        verified=False,
                        backup=str(src),
                        dst=str(dst),
                        bad_entry=entry.filename,
                    )
    except (zipfile.BadZipFile, OSError) as exc:
        # No es nuestro trabajo aquí; deja que el flujo principal lo reporte.
        return None
    return None


_PRE_VALIDATORS: dict[str, Any] = {
    "notification": _prevalidate_notification,
    "backup_sync": _prevalidate_backup_sync,
}


# CC-105: unified in Sprint 4 — the body now lives in :mod:`._shared`
# (was duplicated against domain_tools._redact_credentials, see audit §2.2).
from ._shared import redact_sensitive as _redact_sensitive  # noqa: E402


# Completion statuses que representan dispatch async exitoso al SO/browser:
# la operacion llego a destino, el efecto fisico (audio, render, click) no es
# medible desde Python pero NO es un fallo. Estos casos:
#   - NO se etiquetan como "needs_verification" (eso confundia al LLM).
#   - status="dispatched" (nuevo bucket distinto de done/attempted/needs_verif).
#   - verified=None (honest tristate: True medido / False medido y mal / None
#                    no medible).
# Auditoria 2026-05-15 mostro 40+ falsos positivos donde tools dispatch
# (browser.youtube_play, media.play_pause via media key, browser.open url,
# steam.store_page, app.open con launch_requested) reportaban verified=False
# y disparaban el guard "Nota: no dejo evidencia suficiente" aunque la
# accion SI habia ocurrido.
_DISPATCH_OK_COMPLETIONS = frozenset({
    "opened_youtube_video_for_playback",
    "opened_youtube_search_unverified",
    "opened_search_results",
    "opened_url",
    "opened_steam_client_store_page",
    "opened_steam_client_store_search_unverified",
    "opened_matching_steam_library_detail",
    "sent_global_media_key",
    "launch_requested",
    "dispatched",
})


def _normalize_tool_result(name: str, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    result.setdefault("tool", name)
    if args.get("action") and "action" not in result:
        result["action"] = str(args["action"])
    # CC-105 / CC-credential-args-traced-105: redacción de keys sensibles
    # antes de que el resultado llegue a traces/jsonl o se devuelva al LLM.
    # Mutamos el dict result in-place a través de un walk recursivo.
    redacted = _redact_sensitive(result)
    if isinstance(redacted, dict) and redacted is not result:
        result.clear()
        result.update(redacted)

    ok = bool(result.get("ok", False))
    completion = str(result.get("completion_status") or "").casefold()
    is_dispatch_ok = completion in _DISPATCH_OK_COMPLETIONS

    if not ok:
        result.setdefault("status", "failed")
        result.setdefault("verified", False)
        result.setdefault("completion_status", "failed")
    elif is_dispatch_ok:
        # Dispatch async legitimo: URL/deeplink/keypress enviado al SO.
        # status="dispatched" + verified=None (no medible, no fallo).
        result.setdefault("status", "dispatched")
        if "verified" not in result:
            result["verified"] = None
    elif result.get("attempted"):
        result.setdefault("status", "attempted")
        result.setdefault("verified", False)
    elif _has_unverified_signal(result):
        result.setdefault("status", "needs_verification")
        result.setdefault("verified", False)
    else:
        result.setdefault("status", "done")
        result.setdefault("verified", True)

    result.setdefault("evidence", _result_evidence(result))
    return result


def _has_unverified_signal(result: dict[str, Any]) -> bool:
    # FAST EXIT: dispatch async OK no es unverified, sin importar que tenga
    # campos *_verified=False (e.g. playback_verified=False es esperado para
    # un video que se abrio en el browser — no se puede medir desde Python).
    completion = str(result.get("completion_status") or "").casefold()
    if completion in _DISPATCH_OK_COMPLETIONS:
        return False
    for key, value in result.items():
        if key.endswith("_verified") and value is False:
            return True
    if result.get("verified") is False:
        return True
    if result.get("attempted") is True:
        return True
    return any(token in completion for token in ("unverified", "needs_verification", "requested", "attempted"))


def _result_evidence(result: dict[str, Any]) -> dict[str, Any] | str:
    for key in ("evidence", "url", "path", "image_path", "matched_game", "active", "result", "found"):
        if key in result:
            return result[key]
    if result.get("error"):
        return str(result["error"])
    if result.get("stdout"):
        return _truncate(str(result["stdout"]), 500)
    return "tool_result"


ACTION_ENUMS: dict[str, list[str]] = {
    "system": ["time", "processes", "cpu_ram_gpu", "disk", "battery", "brightness_get", "brightness_set", "shutdown", "restart", "sleep"],
    "audio": ["get_volume", "set_volume", "mute", "devices", "set_default", "media_play_pause", "media_stop", "next", "previous"],
    "app": ["search", "open", "close", "uninstall"],
    "steam": ["open", "library", "store", "list_games", "launch_game", "search_library", "search_store", "store_page", "install"],
    "window": ["list", "active", "focus", "close", "minimize", "maximize", "restore", "move_resize"],
    "gui": ["screenshot", "click", "double_click", "right_click", "type", "type_into", "click_button", "keypress", "hotkey", "scroll", "drag", "wait_for", "locate_text", "click_text", "locate_image"],
    "vision": ["describe_screen", "find_element", "ocr", "compare_before_after"],
    "browser": ["open", "search", "youtube_play", "media_pause", "media_stop", "active_tab_title", "click", "find", "research"],
    "web": ["search", "read", "research", "open"],
    "uia": ["tree", "find", "click", "focus", "set_value"],
    "filesystem": ["list", "read", "write", "search", "delete", "copy", "move", "rename", "mkdir", "diff", "archive", "unarchive", "open"],
    "package": ["list", "search", "install", "uninstall"],
    "clipboard": ["read", "write"],
    "terminal": ["run"],
    "memory": ["save", "recall", "list", "delete"],
    "verify": ["app_opened", "file_exists", "window_exists", "clipboard_contains"],
    "state": ["resources", "cleanup_plan", "cleanup", "checkpoint", "checkpoints", "rollback_plan", "rollback", "note"],
    "input": ["language_list", "keyboard_layouts", "current_keyboard", "set_language_list", "switch_keyboard"],
    "env": ["get", "set", "delete", "list"],
    "registry": ["query", "export", "import", "add", "delete", "backup"],
    "download": ["fetch", "hash", "signature"],
    "email": ["status", "draft", "send"],
    "reminder": ["status", "create", "list", "delete"],
    "browser_real": ["status", "open", "goto", "tabs", "click", "fill", "press", "text", "screenshot", "evaluate", "connect_cdp", "close", "attach_visible", "active_tab", "tab_open", "tab_close", "tab_focus", "click_text", "extract", "wait_for_download", "set_download_path"],
    "knowledge": ["status", "ingest", "search", "list", "delete"],
    "office": ["status", "create_presentation", "edit_presentation", "create_document", "edit_document", "create_spreadsheet", "edit_spreadsheet", "export_pdf", "inspect", "open"],
    "audio_device": ["status", "list", "set_default", "set_default_communications", "set_app_route", "get_app_routes", "snapshot", "restore"],
    "notification": ["status", "toast_now", "toast_schedule", "timer_start", "timer_cancel", "timer_update", "timer_list", "alarm_create", "alarm_cancel", "alarm_update", "alarm_list", "reminder_create", "reminder_update", "reminder_delete", "reminder_list", "notification_update", "notify_sound", "delete", "list", "history"],
    "routine": ["status", "create", "list", "enable", "disable", "delete", "run_now", "simulate", "history", "import"],
    "media": ["status", "play", "pause", "resume", "play_pause", "stop", "next", "previous", "queue_add", "queue_clear", "queue_list", "now_playing", "volume_for_app", "open_local", "search_local_library", "cast_lan"],
    "source_manager": ["status", "save", "add", "list", "sources", "search", "read", "get", "delete", "snapshot_file"],
    "dependency": ["status", "list", "verify", "explain_missing", "install", "repair"],
    "contacts": ["status", "create", "add", "list", "search", "delete", "update", "import_vcard", "export_vcard", "resolve_recipient"],
    "notes_tasks": ["status", "note_create", "create_note", "note_list", "notes", "note_search", "note_update", "note_delete", "task_create", "create_task", "task_list", "tasks", "task_search", "task_complete", "task_update", "task_delete", "search", "list", "delete"],
    "local_calendar": ["status", "event_create", "event_list", "event_update", "event_delete", "ics_export", "ics_import", "list", "delete"],
    "habit_tracker": ["status", "create", "list", "log", "stats", "delete"],
    "local_search": ["status", "search", "recent"],
    "printer_scanner": ["status", "printers_list", "printer_default_get", "printer_default_set", "print_queue", "print_file", "cancel_job", "scanners_list", "scan_document", "list"],
    "desktop_layout": ["status", "windows", "list_windows", "displays", "snapshot", "restore"],
    "backup_sync": ["status", "backup_create", "list", "restore", "dedupe", "verify"],
    "document": ["status", "extract_text", "extract_tables", "extract_images", "ocr_pdf", "summarize", "ingest_to_knowledge", "compare_documents"],
    "developer": ["status", "project_detect", "run_tests", "run_lint", "run_format", "git_status", "git_diff", "git_log", "git_commit", "git_push", "start_dev_server", "stop_dev_server", "list_dev_servers"],
    "device_settings": ["status", "wifi_status", "wifi_list", "wifi_profiles", "wifi_scan", "wifi_connect", "wifi_disconnect", "wifi_add_profile", "wifi_delete_profile", "bluetooth_status", "bluetooth_toggle", "bluetooth_pair", "display_list", "display_set_resolution", "display_set_scale", "power_plan_list", "power_plans", "power_plan_get", "power_plan_set", "night_light", "wifi_set_profile"],
    "game_launcher": ["status", "discover", "list", "discover_games", "launch", "open_store_page", "open_library_page"],
    "media_edit": ["status", "probe", "trim", "concat", "extract_audio", "subtitles_extract", "normalize", "thumbnail", "transcode"],
    "maintenance": ["status", "windows_update_status", "defender_status", "defender_quick_scan", "firewall_status", "event_logs_query", "services_list", "services", "service_status", "service_start", "service_stop", "disk_cleanup_describe", "restore_point_create"],
    "watcher": ["status", "list", "watch_file", "watch_url", "check", "delete"],
    "job_manager": ["status", "start", "list", "log", "status_of", "info", "cancel", "stop", "kill"],
    "network": ["status", "ping", "traceroute", "dns_get", "dns_set", "dns_resolve", "resolve", "port_check", "connections", "public_ip", "firewall_allow", "firewall_block", "firewall_remove"],
    "data_analysis": ["status", "csv_profile", "csv_describe", "csv_query", "csv_head", "csv_to_xlsx", "plot_histogram", "plot_scatter", "plot_line"],
    "fact_check": ["status", "check", "compare"],
    "photo_library": ["status", "scan", "exif", "group_by_date", "thumbnails", "find_by_date"],
    "container": ["status", "ps", "ps_all", "images", "inspect", "logs", "start", "stop", "restart", "exec", "compose_up", "compose_down", "compose_ps"],
    "database": ["status", "list_tables", "schema", "query", "execute", "export_csv"],
    "creative_local": ["status", "submit", "result", "wait", "queue", "interrupt", "models"],
    "form_filler": ["status", "discover", "plan", "apply", "submit"],
    "peripheral": ["status", "usb_list", "hid_list", "controller_status", "device_manager_problems", "problems", "device_disable", "device_enable", "rgb_profile_set", "rgb_list", "rgb_set_color"],
    "accessibility": ["status", "magnifier_start", "magnifier_stop", "narrator_start", "narrator_stop", "dictation_status", "settings_panel", "open_settings", "high_contrast_on", "high_contrast_off", "high_contrast_toggle"],
    "study": ["status", "deck_create", "deck_list", "deck_delete", "card_add", "card_list", "card_delete", "due", "review", "stats"],
    "smart_home": ["status", "discover", "states", "get_state", "set_state", "call_service", "scene_run", "area_list", "areas", "area_control", "mqtt_publish"],
    "subagent": ["status", "run"],
    "safety": ["status", "pending", "confirm", "cancel"],
    "session": ["cancel_turn"],
}


def _apply_action_enums(schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for schema in schemas:
        function = schema.get("function") or {}
        name = function.get("name")
        enum = ACTION_ENUMS.get(str(name))
        params = function.get("parameters") or {}
        if isinstance(params, dict):
            params.setdefault("additionalProperties", False)
        if not enum:
            continue
        props = params.get("properties") or {}
        action = props.get("action")
        if isinstance(action, dict):
            action.setdefault("enum", enum)
    return schemas


def _normalize_tool_name(name: str, known: set[str]) -> str | None:
    """Normaliza un tool name mal-formado de Gemma 4 a uno del catálogo, o None.

    Gemma 4 emite a veces el nombre con ruido estructural (no semántico):
      - mayúsculas:        "GUI" / "SYSTEM"
      - espacios/parens:   "gui " / "gui()"
      - segmentado:        "Functions.gui.click" / "tools/gui"
      - prefijo de acción: "gui_click" cuando la tool es "gui"
    Esto NO es ambigüedad de intención (eso lo decide el router/LLM): es un
    nombre que apunta CLARAMENTE a una tool existente pero con forma sucia.
    Normalización 100% ESTRUCTURAL (sin keywords, sin idioma, sin hardcode de
    nombres): solo manipula la string contra el catálogo real `known`.
    Port de carter_v5/adapters/tool_call_repair.py::normalize_tool_name.
    """
    if not name:
        return None
    # 1. exact
    if name in known:
        return name
    # 2. strip whitespace + trailing parens/punct
    stripped = name.strip().rstrip("()[]{} .:")
    if stripped in known:
        return stripped
    # 3. case-insensitive
    low = stripped.casefold()
    by_lower = {k.casefold(): k for k in known}
    if low in by_lower:
        return by_lower[low]
    # 4. segmento: partir en . / \ y probar cada segmento desde la derecha
    #    "Functions.gui.click" -> "click"? no; "gui"? sí. "tools/gui" -> "gui".
    for sep in (".", "/", "\\"):
        if sep in low:
            for seg in reversed([s for s in low.split(sep) if s]):
                if seg in by_lower:
                    return by_lower[seg]
    # 5. prefijo underscore: "gui_click" -> "gui" si "gui" ∈ known.
    #    Probar prefijos progresivos por "_".
    if "_" in low:
        parts = low.split("_")
        for i in range(len(parts) - 1, 0, -1):
            cand = "_".join(parts[:i])
            if cand in by_lower:
                return by_lower[cand]
    return None


def _correct_known_misroute(name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Redirect a tool call whose OWN arguments prove the model picked the
    wrong tool. Validates the LLM's output, not the user's phrasing, so it is
    language-universal. Returns the (possibly corrected) (name, args).

    Rule 1 — volume via the device tool: `audio_device` has no `level`
    parameter; its actions manage the default output/input DEVICE. If the
    model calls it with a numeric `level` (or a set/lower/raise action plus a
    level), it meant to set the VOLUME → route to audio.set_volume. This is
    the exact failure seen on "baja el vol del pc a 10" (audio_device failed).
    """
    if name == "audio_device":
        level = args.get("level")
        action = str(args.get("action") or "").lower()
        wants_volume = level is not None or action in {
            "set_volume", "set", "lower", "raise", "volume", "set_level",
        }
        if wants_volume:
            new_args: dict[str, Any] = {"action": "set_volume"}
            if level is not None:
                new_args["level"] = level
            return "audio", new_args
    return name, args


def _coerce_and_validate_tool_args(name: str, args: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    params = _parameters_for_tool(name)
    if not params:
        return args, []

    props = params.get("properties") or {}
    required = set(params.get("required") or [])
    additional = bool(params.get("additionalProperties", True))
    clean: dict[str, Any] = {}
    errors: list[str] = []

    if not additional:
        for key in sorted(set(args) - set(props)):
            errors.append(f"unexpected argument: {key}")

    for key, spec in props.items():
        if key not in args:
            continue
        value = _coerce_json_value(args[key], spec)
        clean[key] = value
        type_name = spec.get("type")
        if type_name and not _json_type_ok(value, str(type_name)):
            errors.append(f"{key} must be {type_name}, got {type(value).__name__}")
            continue
        enum = spec.get("enum")
        if enum and value not in enum:
            errors.append(f"{key} must be one of {enum}, got {value!r}")
            continue
        if type_name in ("integer", "number") and isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum = spec.get("minimum")
            maximum = spec.get("maximum")
            if minimum is not None and value < minimum:
                errors.append(f"{key} must be >= {minimum}, got {value}")
            if maximum is not None and value > maximum:
                errors.append(f"{key} must be <= {maximum}, got {value}")

    for key in required:
        if key not in clean or clean[key] in {None, ""}:
            errors.append(f"missing required argument: {key}")

    if additional:
        for key, value in args.items():
            clean.setdefault(key, value)
    return clean, errors


def _parameters_for_tool(name: str) -> dict[str, Any] | None:
    for schema in COMPOUND_TOOL_SCHEMAS:
        function = schema.get("function") or {}
        if function.get("name") == name:
            params = function.get("parameters")
            return params if isinstance(params, dict) else None
    return None


def _coerce_json_value(value: Any, spec: dict[str, Any]) -> Any:
    type_name = spec.get("type")
    if value is None:
        return value
    if type_name == "string" and not isinstance(value, str):
        return str(value)
    if type_name == "integer":
        if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
            return int(value)
        if isinstance(value, float) and value.is_integer():
            return int(value)
    if type_name == "number":
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return value
    if type_name == "boolean" and isinstance(value, str):
        low = value.strip().casefold()
        if low in {"1", "true", "yes", "on", "si"}:
            return True
        if low in {"0", "false", "no", "off"}:
            return False
    return value


def _json_type_ok(value: Any, type_name: str) -> bool:
    if value is None:
        return True
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "array":
        return isinstance(value, list)
    if type_name == "object":
        return isinstance(value, dict)
    return True


def _attach_screenshot(result: dict[str, Any], shot: dict[str, Any]) -> dict[str, Any]:
    result["screenshot"] = shot
    if shot.get("ok"):
        for key in ("image_path", "width", "height", "left", "top"):
            if key in shot:
                result[key] = shot[key]
    else:
        result["screenshot_error"] = shot.get("error", "screenshot failed")
    return result


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + f"...<truncated {len(text) - limit} chars>"


# Mapeo de teclas individuales a SendKeys syntax. Source de truth:
# learn.microsoft.com/dotnet/api/system.windows.forms.sendkeys.send
# Las teclas se envuelven entre { } en SendKeys cuando son special.
_SENDKEYS_SPECIAL = {
    "ENTER": "{ENTER}", "RETURN": "{ENTER}",
    "ESC": "{ESC}", "ESCAPE": "{ESC}",
    "TAB": "{TAB}", "BACKSPACE": "{BACKSPACE}", "BS": "{BACKSPACE}",
    "DELETE": "{DELETE}", "DEL": "{DELETE}",
    "SPACE": " ", "SPACEBAR": " ",
    "UP": "{UP}", "DOWN": "{DOWN}", "LEFT": "{LEFT}", "RIGHT": "{RIGHT}",
    "HOME": "{HOME}", "END": "{END}",
    "PGUP": "{PGUP}", "PAGEUP": "{PGUP}",
    "PGDN": "{PGDN}", "PAGEDOWN": "{PGDN}",
    "INS": "{INS}", "INSERT": "{INS}",
    "F1": "{F1}", "F2": "{F2}", "F3": "{F3}", "F4": "{F4}",
    "F5": "{F5}", "F6": "{F6}", "F7": "{F7}", "F8": "{F8}",
    "F9": "{F9}", "F10": "{F10}", "F11": "{F11}", "F12": "{F12}",
    "CAPSLOCK": "{CAPSLOCK}", "NUMLOCK": "{NUMLOCK}",
    "PRINTSCREEN": "{PRTSC}", "PRTSC": "{PRTSC}", "PRINT": "{PRTSC}",
    "PLAYPAUSE": "^v",  # SendKeys no soporta media keys; usar virtual key via gui_keypress_vk
}

# Prefijos modificadores de SendKeys.
_SENDKEYS_MODIFIERS = {
    "CTRL": "^", "CONTROL": "^",
    "ALT": "%",
    "SHIFT": "+",
    "WIN": "^{ESC}",  # Win key no es directamente soportado por SendKeys; workaround limitado
}


def _translate_keys_to_sendkeys(keys: str) -> str:
    """Traduce un especificador de teclas humano-friendly a SendKeys syntax.

    Casos cubiertos:
      - "enter" -> "{ENTER}"
      - "ctrl+f" -> "^f"
      - "Ctrl+Shift+T" -> "^+t"
      - "alt+f4" -> "%{F4}"
      - "ctrl+shift+escape" -> "^+{ESC}"
      - "a" -> "a"  (letra normal)
      - "^f" -> "^f"  (passthrough si ya es SendKeys)
      - "{ENTER}" -> "{ENTER}"  (passthrough)

    Si el formato no es reconocible, devuelve la string tal cual (passthrough)
    para no romper input que ya estaba bien.
    """
    if not keys:
        return ""
    s = keys.strip()
    # Si ya parece SendKeys syntax (empieza con ^+% o tiene {...}), pass.
    if s and (s[0] in "^+%" or s.startswith("{")):
        return s
    # Mapeo exacto para nombres simples (ENTER, F5, etc).
    upper = s.upper()
    if upper in _SENDKEYS_SPECIAL:
        return _SENDKEYS_SPECIAL[upper]
    # Combo con modificadores: split por '+'.
    if "+" in s:
        parts = [p.strip() for p in s.split("+") if p.strip()]
        if not parts:
            return s
        modifier_prefix = ""
        # El ultimo token es la tecla; los anteriores son modificadores.
        for mod in parts[:-1]:
            mu = mod.upper()
            if mu in _SENDKEYS_MODIFIERS:
                # Solo agregamos el simbolo del modificador (^/%/+).
                m = _SENDKEYS_MODIFIERS[mu]
                # Filtramos el workaround inutil de WIN.
                if m in {"^", "%", "+"}:
                    modifier_prefix += m
                # Si el modificador no es estandar, retornamos passthrough.
                else:
                    return s
            else:
                return s
        last = parts[-1].upper()
        if last in _SENDKEYS_SPECIAL:
            return modifier_prefix + _SENDKEYS_SPECIAL[last]
        last_raw = parts[-1]
        if len(last_raw) == 1:
            # Letra/digito normal: lowercase para SendKeys consistency.
            return modifier_prefix + last_raw.lower()
        # Multi-char no especial: envolver en { }.
        return modifier_prefix + "{" + last_raw + "}"
    # No combo, no especial conocido. Para multichar suponemos texto literal.
    if len(s) == 1:
        return s
    # Multichar sin combo (e.g. "abc"): pasar tal cual (SendKeys lo trata como texto).
    return s


def _action(args: dict[str, Any], default: str = "") -> str:
    return str(args.get("action") or default).strip().casefold()


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


# Connective words that must NOT count as a meaningful name overlap (else
# "League of Legends" ~ "Sea of Thieves" via "of"). ES + EN.
_APP_NAME_STOPWORDS = frozenset({
    "of", "the", "a", "an", "and", "in", "on", "for", "to",
    "de", "del", "la", "el", "los", "las", "y", "e", "en", "un", "una",
})


def _score(query: str, candidate: str) -> int:
    q = _fold(query)
    c = _fold(candidate)
    if not q or not c:
        return 0
    if q == c:
        return 100
    if c.startswith(q):
        return 90
    if q in c:
        return 75
    q_words = set(q.split())
    c_words = set(c.split())
    if not q_words:
        return 0
    # 2026-05-20: exclude stopwords from the "meaningful overlap" count.
    # "League of Legends" vs "Sea of Thieves" shared only "of" and scored 50,
    # so "Call of Duty" could resolve to "God of War" when the real game
    # isn't installed. A shared connective word is not a real app match.
    overlap_words = (q_words & c_words) - _APP_NAME_STOPWORDS
    overlap = len(overlap_words)
    if overlap:
        # Normalize against the query's CONTENT words (non-stopwords), so a
        # 1-of-1 content match still scores high.
        q_content = q_words - _APP_NAME_STOPWORDS
        denom = len(q_content) or len(q_words)
        return 40 + int(30 * overlap / denom)
    # Fuzzy fallback: el usuario puede haber dictado mal por voz
    # ("Saint Rose" en vez de "Saints Row") o con typos. Usamos difflib
    # SequenceMatcher.ratio() sobre la frase completa Y sobre cada par
    # de words. Si alguna coincidencia parcial supera el umbral, devolvemos
    # un score bajo pero positivo para que el candidato no se descarte.
    import difflib
    full_ratio = difflib.SequenceMatcher(None, q, c).ratio()
    # 2026-05-20: first-character guard. Short near-anagrams ("teams" vs
    # "steam", ratio ~0.8) were fuzzy-matching and "abre Teams" opened Steam.
    # A real typo almost always keeps the first letter ("spotfy"->"spotify",
    # "calculadra"->"calculadora"); a different first letter on a short query
    # is a different word. Only gate the SHORT single-token case so multi-word
    # / longer queries keep their fuzzy tolerance.
    short_single_token = len(q_words) <= 1 and len(q) <= 7
    if short_single_token and q[:1] != c[:1]:
        full_ratio = 0.0
    if full_ratio >= 0.7:
        # Mapeo lineal: 0.7 -> 35, 1.0 -> 70. Suficiente para entrar al
        # ranking pero no para vencer un startswith/contiene del 75-90.
        return int(35 + (full_ratio - 0.7) * (70 - 35) / 0.3)
    # Word-pair fuzzy: si cualquier word del query tiene una similar
    # (>=0.75) en el candidato, sumamos credito. "saint" vs "saints" = 0.91;
    # "rose" vs "row" = 0.57 (no califica solo). Pero si AL MENOS UN word
    # del query encuentra match difuso, devolvemos un score modesto.
    matched_words = 0
    for qw in q_words:
        if len(qw) < 3:
            continue
        for cw in c_words:
            if len(cw) < 3:
                continue
            # Same first-char guard as above: "teams"~"steam" (ratio ~0.8)
            # is a near-anagram, NOT a typo. A real per-word typo keeps the
            # first letter. This is what made "abre Teams" open Steam.
            if qw[:1] != cw[:1]:
                continue
            if difflib.SequenceMatcher(None, qw, cw).ratio() >= 0.75:
                matched_words += 1
                break
    if matched_words:
        return 20 + int(20 * matched_words / max(1, len(q_words)))
    return 0


# Sprint 5b: AppCandidate + AppResolver moved to :mod:`.app_resolver`.
# Re-export here so existing `from .tools import AppCandidate, AppResolver`
# call sites (and external callers) keep working. The two classes pull the
# small ranking / parsing helpers (_fold, _score, _acf_value,
# _nearest_steam_appid, _pretty_exe_name, _looks_like_uninstaller) lazily
# from this module to avoid a top-level import cycle.
from .app_resolver import AppCandidate, AppResolver  # noqa: E402,F401


def _acf_value(text: str, key: str) -> str | None:
    match = re.search(rf'"{re.escape(key)}"\s+"([^"]+)"', text)
    return match.group(1) if match else None


def _nearest_steam_appid(data: bytes, appid_markers: list[tuple[int, bytes]], pos: int) -> int | None:
    scan_start = max(0, pos - 200_000)
    best_index = -1
    best_appid: int | None = None
    for appid, marker in appid_markers:
        idx = data.rfind(marker, scan_start, pos)
        if idx > best_index:
            best_index = idx
            best_appid = appid
    return best_appid


def _steam_appid_from_launch(launch: str) -> str | None:
    match = re.search(r"/(\d+)$", launch)
    return match.group(1) if match else None


def _steam_store_uri(appid: str) -> str:
    return f"steam://store/{appid}"


def _steam_openurl_uri(url: str) -> str:
    return f"steam://openurl/{url}"


def _steam_store_url(appid: str, name: str | None = None) -> str:
    slug = ""
    if name:
        slug = "/" + re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return f"https://store.steampowered.com/app/{appid}{slug}/"


def _steam_store_first_result(query: str) -> dict[str, str] | None:
    url = f"https://store.steampowered.com/search/?term={quote_plus(query)}"
    try:
        html_text = _http_get_text(url, timeout=12)["text"]
    except Exception:
        return None
    match = re.search(r'href="https://store\.steampowered\.com/app/(\d+)/([^"/?#]+)', html_text)
    if not match:
        match = re.search(r"https://store\.steampowered\.com/app/(\d+)/([^\"'<>?#]+)", html_text)
    if not match:
        return None
    appid = match.group(1)
    raw_slug = unquote(match.group(2)).replace("_", " ").strip()
    title_match = re.search(rf'(?is)data-ds-appid="{re.escape(appid)}".*?<span[^>]+class="title"[^>]*>(.*?)</span>', html_text)
    title = _clean_html_text(title_match.group(1), limit=200) if title_match else raw_slug
    return {"appid": appid, "name": title or raw_slug, "url": _steam_store_url(appid, title or raw_slug)}


def _shortcut_target(shortcut: Path) -> str | None:
    if not shortcut.is_file() or shortcut.suffix.lower() != ".lnk":
        return None
    env = os.environ.copy()
    env["GEMMA4_SHORTCUT"] = str(shortcut)
    script = r"""
$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:GEMMA4_SHORTCUT)
[PSCustomObject]@{ target=$s.TargetPath; arguments=$s.Arguments; working_directory=$s.WorkingDirectory } | ConvertTo-Json -Depth 3
"""
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=8)
    except Exception:
        return None
    raw = proc.stdout.strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    target = str(data.get("target") or "").strip()
    return target or None


def _running_process_names() -> set[str]:
    """Lista (best-effort) de nombres de proceso vivos (lowercase, con .exe).
    Util para el fast-path de app_close: si ningun candidato esta corriendo,
    evitamos el roundtrip de PowerShell + taskkill que tarda 20s.

    Implementacion priorizada por velocidad:
      1) psutil.process_iter() si esta disponible (~80-150ms, no spawn)
      2) Fallback a `tasklist /FO CSV /NH` con timeout corto (puede tardar
         5-10s en algunos entornos; preferimos no usarlo)
      3) Set vacio (caller cae al flujo lento, equivalente al comportamiento
         previo a esta optimizacion — fail open).
    """
    try:
        import psutil
        out: set[str] = set()
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info.get("name") or ""
                if name:
                    out.add(name.lower())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if out:
            return out
    except Exception:
        pass

    # Fallback subprocess. tasklist puede tardar mucho en algunos hosts
    # (10s+) por razones que no controlamos; lo usamos solo si psutil falla.
    try:
        proc = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if proc.returncode != 0 or not proc.stdout:
        return set()
    out = set()
    for row in csv.reader(proc.stdout.splitlines()):
        if row and row[0]:
            out.add(row[0].strip().lower())
    return out


def _candidate_close_exes(name: str, matches: list[AppCandidate]) -> list[str]:
    candidates: list[str] = []
    query_tokens = [token for token in _fold(name).split() if len(token) >= 3]

    def add(exe: str | None) -> None:
        if not exe:
            return
        exe = Path(exe.strip().strip('"')).name
        if not exe.lower().endswith((".exe", ".com", ".bat", ".cmd")):
            return
        if _looks_like_uninstaller(Path(exe)):
            return
        if exe.casefold() not in {item.casefold() for item in candidates}:
            candidates.append(exe)

    for match in matches:
        score = max(_score(name, match.name), _score(name, Path(match.launch).stem))
        if score < 55:
            continue
        tokens = sorted(set(query_tokens + [token for token in _fold(match.name).split() if len(token) >= 3]))
        launch = Path(match.launch.strip().strip('"'))
        if launch.suffix.lower() == ".lnk":
            target = _shortcut_target(launch)
            add(target)
            target_path = Path(target) if target else None
            if target_path and target_path.parent.is_dir():
                try:
                    for exe in target_path.parent.glob("*.exe"):
                        if exe.stem.casefold().startswith(target_path.stem.casefold()[:4]):
                            add(exe.name)
                except OSError:
                    pass
                install_roots = [target_path.parent, target_path.parent.parent]
                for root in install_roots:
                    if not root or not root.is_dir():
                        continue
                    try:
                        for exe in list(root.glob("*.exe"))[:40]:
                            folded = _fold(f"{exe.stem} {exe.parent.name}")
                            if any(token in folded for token in tokens) or _score(root.name, match.name) >= 70:
                                add(exe.name)
                    except OSError:
                        pass
        elif launch.suffix.lower() == ".exe" and (match.source != "PATH" or score >= 75):
            add(launch.name)
        if match.process_name and (match.source != "PATH" or score >= 75):
            add(match.process_name)

    if name.lower().endswith(".exe"):
        add(name)
    return candidates


def _close_windows_by_query(name: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["GEMMA4_CLOSE_QUERY"] = name
    script = r"""
$q=$env:GEMMA4_CLOSE_QUERY.ToLower()
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
}
"@
$targets = Get-Process | Where-Object {
  $_.MainWindowTitle -and (
    $_.MainWindowTitle.ToLower().Contains($q) -or
    $_.ProcessName.ToLower().Contains($q)
  )
}
$closed = @()
foreach ($p in $targets) {
  [Win32]::PostMessage($p.MainWindowHandle,0x0010,[IntPtr]::Zero,[IntPtr]::Zero) | Out-Null
  $closed += [PSCustomObject]@{ title=$p.MainWindowTitle; process=$p.ProcessName; pid=$p.Id }
}
[PSCustomObject]@{ count=$closed.Count; windows=$closed } | ConvertTo-Json -Depth 4
"""
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=12)
    except Exception as exc:
        return {"count": 0, "error": f"{type(exc).__name__}: {exc}"}
    if not proc.stdout.strip():
        return {"count": 0, "stderr": _truncate(proc.stderr.strip(), 1000)}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"count": 0, "stdout": _truncate(proc.stdout.strip(), 1000), "stderr": _truncate(proc.stderr.strip(), 1000)}
    return data if isinstance(data, dict) else {"count": 0, "data": data}


def _looks_like_music_request(query: str) -> bool:
    folded = _fold(query)
    return any(
        token in folded
        for token in (
            "cancion",
            "musica",
            "music",
            "song",
            "tema",
            "track",
            "aleatoria",
            "random",
            "playlist",
        )
    )


def _is_generic_song_query(query: str) -> bool:
    folded = _fold(query)
    if not folded:
        return True
    generic = {
        "cancion",
        "una cancion",
        "cancion aleatoria",
        "musica",
        "musica aleatoria",
        "pon musica",
        "pon una cancion",
        "random song",
        "song",
        "music",
    }
    return folded in generic or ("aleatoria" in folded and any(word in folded for word in ("cancion", "musica", "song", "music")))


def _looks_like_youtube_watch_url(text: str) -> bool:
    return bool(re.search(r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[A-Za-z0-9_-]{11}", text))


def _youtube_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}&autoplay=1"


def _youtube_first_result(query: str) -> dict[str, str] | None:
    if not query:
        return None
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            text = resp.read(2_000_000).decode("utf-8", errors="replace")
    except Exception:
        return None

    seen: set[str] = set()
    for video_id in re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', text):
        if video_id in seen:
            continue
        seen.add(video_id)
        if video_id.startswith(("UC", "PL")):
            continue
        title = _youtube_title_near_video_id(text, video_id)
        return {"video_id": video_id, "title": title or query}
    return None


def _youtube_title_near_video_id(text: str, video_id: str) -> str | None:
    pos = text.find(f'"videoId":"{video_id}"')
    if pos < 0:
        return None
    chunk = text[pos: pos + 5000]
    match = re.search(r'"title":\{"runs":\[\{"text":"([^"]+)"', chunk)
    if not match:
        match = re.search(r'"title":\{"simpleText":"([^"]+)"', chunk)
    if not match:
        return None
    try:
        return json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return match.group(1)


# Sprint 5b: _is_private_host + _SSRFGuardRedirectHandler moved to
# :mod:`.ssrf_guard`. Re-export here so the internal callers
# (_http_get_text below + the audit/smoke harness) keep working.
from .ssrf_guard import _is_private_host, _SSRFGuardRedirectHandler  # noqa: E402,F401


def _http_get_text(url: str, timeout: int = 12, max_bytes: int = 2_000_000, allow_private: bool = False) -> dict[str, Any]:
    # T2-web-no-redirect-cap-014: SSRF guard pre-request y en redirects.
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if not allow_private and _is_private_host(host):
        raise urllib.error.URLError(f"refused: target host is private/loopback ({host}); pass allow_private=True to override")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": WEB_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    )
    opener = urllib.request.build_opener(_SSRFGuardRedirectHandler()) if not allow_private else urllib.request.build_opener()
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read(max_bytes)
        content_type = resp.headers.get("content-type", "")
        charset_match = re.search(r"charset=([^;\s]+)", content_type, re.I)
        charset = charset_match.group(1) if charset_match else "utf-8"
        text = raw.decode(charset, errors="replace")
        return {
            "url": resp.geturl(),
            "status_code": getattr(resp, "status", None),
            "content_type": content_type,
            "text": text,
        }


def _extract_title(markup: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", markup, re.I | re.S)
    if not match:
        return ""
    return _clean_html_text(match.group(1), limit=300)


def _html_to_text(markup: str, limit: int = 12000) -> str:
    markup = re.sub(r"(?is)<(script|style|noscript|svg|canvas).*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>", "\n", markup)
    markup = re.sub(r"(?i)</(p|div|section|article|header|footer|li|h[1-6]|tr)>", "\n", markup)
    return _clean_html_text(markup, limit=limit)


def _clean_html_text(text: str, limit: int = 12000) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return _truncate(text.strip(), limit)


def _decode_duckduckgo_href(href: str) -> str:
    href = html.unescape(href)
    parsed = urlparse(href)
    query = parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return unquote(query["uddg"][0])
    return href


def _duckduckgo_search(query: str, limit: int = 6) -> list[dict[str, str]]:
    page = _http_get_text(f"https://html.duckduckgo.com/html/?q={quote_plus(query)}", timeout=12)["text"]
    results: list[dict[str, str]] = []
    for link in re.finditer(r"(?is)<a[^>]+class=\"result__a\"[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", page):
        chunk = page[link.end(): link.end() + 3000]
        snippet = re.search(r"(?is)<a[^>]+class=\"result__snippet\"[^>]*>(.*?)</a>", chunk)
        url = _decode_duckduckgo_href(link.group(1))
        title = _clean_html_text(link.group(2), limit=300)
        item = {"title": title, "url": url}
        if snippet:
            item["snippet"] = _clean_html_text(snippet.group(1), limit=700)
        results.append(item)
        if len(results) >= limit:
            break
    return results


def _web_search_provider(query: str, limit: int = 6) -> tuple[str, list[dict[str, str]]]:
    provider = os.environ.get("GEMMA4_WEB_SEARCH_PROVIDER", DEFAULT_WEB_SEARCH_PROVIDER).strip().casefold()
    if provider in {"duckduckgo", "duckduckgo_html", "ddg"}:
        return "duckduckgo_html", _duckduckgo_search(query, limit=limit)
    return provider or DEFAULT_WEB_SEARCH_PROVIDER, []


def _pretty_exe_name(path: Path) -> str:
    parts = [p for p in path.parts[-4:-1] if p and p not in {"bin", "x64", "x86", "Win64", "Win32", "Binaries"}]
    stem = re.sub(r"[_-]+", " ", path.stem).strip()
    if parts:
        parent = re.sub(r"[_-]+", " ", parts[-1]).strip()
        if parent and _score(stem, parent) < 80:
            return f"{parent} {stem}"
    return stem


def _looks_like_uninstaller(path: Path) -> bool:
    lower = path.name.casefold()
    return lower.startswith(("unins", "uninstall", "unwise")) or lower in {
        "setup.exe",
        "install.exe",
        "crashreporter.exe",
        "crashreportclient.exe",
        "vc_redist.exe",
        "vc_redist.x64.exe",
        "vc_redist.x86.exe",
    }


class ToolRegistry:
    def __init__(self, memory: MemoryStore, captures_dir: Path, state: AgentState | None = None, safety_enabled: bool = True):
        self.memory = memory
        self.captures_dir = captures_dir
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        self.state = state or AgentState(self.captures_dir.parent / "data" / "state.json")
        self.knowledge = KnowledgeStore(self.state.path.parent / "knowledge.sqlite")
        self.safety_enabled = safety_enabled
        self.apps = AppResolver()
        self._impls: dict[str, ToolFn] = {
            "system": self.t_system,
            "audio": self.t_audio,
            "app": self.t_app,
            "steam": self.t_steam,
            "window": self.t_window,
            "gui": self.t_gui,
            "vision": self.t_vision,
            "browser": self.t_browser,
            "web": self.t_web,
            "uia": self.t_uia,
            "filesystem": self.t_filesystem,
            "package": self.t_package,
            "clipboard": self.t_clipboard,
            "terminal": self.t_terminal,
            "memory": self.t_memory,
            "verify": self.t_verify,
            "skill_load": self.t_skill_load,
            "state": self.t_state,
            "input": self.t_input,
            "env": self.t_env,
            "registry": self.t_registry,
            "download": self.t_download,
            "email": self.t_email,
            "reminder": self.t_reminder,
            "browser_real": self.t_browser_real,
            "knowledge": self.t_knowledge,
            "office": self.t_office,
            "audio_device": self.t_audio_device,
            "notification": self.t_notification,
            "routine": self.t_routine,
            "media": self.t_media,
            "source_manager": self.t_source_manager,
            "dependency": self.t_dependency,
            "contacts": self.t_contacts,
            "whatsapp": self.t_whatsapp,
            "notes_tasks": self.t_notes_tasks,
            "local_calendar": self.t_local_calendar,
            "habit_tracker": self.t_habit_tracker,
            "local_search": self.t_local_search,
            "printer_scanner": self.t_printer_scanner,
            "desktop_layout": self.t_desktop_layout,
            "backup_sync": self.t_backup_sync,
            "document": self.t_document,
            "developer": self.t_developer,
            "device_settings": self.t_device_settings,
            "game_launcher": self.t_game_launcher,
            "media_edit": self.t_media_edit,
            "maintenance": self.t_maintenance,
            "watcher": self.t_watcher,
            "job_manager": self.t_job_manager,
            "network": self.t_network,
            "data_analysis": self.t_data_analysis,
            "fact_check": self.t_fact_check,
            "photo_library": self.t_photo_library,
            "container": self.t_container,
            "database": self.t_database,
            "creative_local": self.t_creative_local,
            "form_filler": self.t_form_filler,
            "peripheral": self.t_peripheral,
            "accessibility": self.t_accessibility,
            "study": self.t_study,
            "smart_home": self.t_smart_home,
            "subagent": self.t_subagent,
            "safety": self.t_safety,
            "session": self.t_session,
        }
        # T3-browser_real-global-session-dict-039: al inicio del proceso, las
        # browser_real resources del run anterior son stale (el dict global
        # _BROWSER_SESSIONS está vacío). Las marcamos como cerradas para
        # evitar cleanup_plan/state.cleanup contra sesiones que no existen.
        self._prune_stale_browser_sessions()

    def _prune_stale_browser_sessions(self) -> None:
        try:
            resources = self.state.list_resources(include_closed=False).get("resources", [])
        except (OSError, ValueError):
            return
        for res in resources:
            if res.get("kind") == "browser_real" and res.get("status") == "open":
                rid = str(res.get("id"))
                self.state.mark_cleaned(rid, {"pruned_on_startup": True, "reason": "no live session"})

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return COMPOUND_TOOL_SCHEMAS

    @property
    def schema_names(self) -> list[str]:
        return [str(schema.get("function", {}).get("name", "")) for schema in COMPOUND_TOOL_SCHEMAS]

    def schemas_for_names(self, names: list[str] | tuple[str, ...] | set[str]) -> list[dict[str, Any]]:
        wanted = {str(name) for name in names}
        return [
            schema
            for schema in COMPOUND_TOOL_SCHEMAS
            if str(schema.get("function", {}).get("name", "")) in wanted
        ]

    def execute(self, name: str, args: dict[str, Any] | None) -> dict[str, Any]:
        clean_args = dict(args or {})
        # CC-101: campos internos NUNCA aceptan inyección desde el LLM —
        # los filtramos antes de cualquier validación. El runner de routines
        # los reintroduce vía `execute_routine_step` (ver más abajo).
        for forbidden in ("_internal_safe", "routine_context", "confirmed_at_create"):
            clean_args.pop(forbidden, None)
        confirmed = bool(clean_args.pop("confirmed", False))
        # Output-coherence guard: catch a known LLM misroute where the call
        # itself proves the wrong tool was chosen, and redirect it. This
        # validates the model's OUTPUT (not the user's words), so it stays
        # universal. Currently: audio_device({...,"level":N}) — the device
        # tool has no `level`; a numeric level means the user wanted VOLUME,
        # so route to audio.set_volume. (Repro: "baja el vol del pc a 10".)
        name, clean_args = _correct_known_misroute(name, clean_args)
        impl = self._impls.get(name)
        if not impl:
            # Gemma 4 a veces ensucia el nombre (mayúsculas, "gui()",
            # "Functions.gui.click", "gui_click"). Normalización estructural
            # contra el catálogo real antes de declarar "unknown". Gate
            # GEMMA4_NORMALIZE_TOOL_NAME=0. (Carter tool_call_repair port.)
            import os as _os_n
            if _os_n.environ.get("GEMMA4_NORMALIZE_TOOL_NAME", "1").strip().lower() \
                    not in {"0", "false", "no", "off"}:
                fixed = _normalize_tool_name(name, set(self._impls.keys()))
                if fixed and fixed != name:
                    impl = self._impls.get(fixed)
                    if impl:
                        name = fixed
            if not impl:
                return _normalize_tool_result(name, clean_args, _err(f"unknown tool: {name}"))
        clean_args, validation_errors = _coerce_and_validate_tool_args(name, clean_args)
        if validation_errors:
            return _normalize_tool_result(
                name,
                clean_args,
                _err(
                    "invalid tool arguments",
                    validation_errors=validation_errors,
                    expected_schema=_parameters_for_tool(name),
                ),
            )
        # Pre-validation hook: corre ANTES del classifier para que inputs
        # claramente inválidos no exijan confirmación al usuario (UX). Los
        # validators son pure-functions que devuelven un dict de error (con
        # `ok=False`) o None. Si devuelve error: short-circuit.
        validator = _PRE_VALIDATORS.get(name)
        if validator is not None:
            err = validator(clean_args)
            if err is not None:
                return _normalize_tool_result(name, clean_args, err)
        if self.safety_enabled and not confirmed and name != "safety":
            decision = classify_tool_call(name, clean_args)
            if decision.requires_confirmation:
                pending = self.state.create_confirmation(name, _redact_sensitive(clean_args), decision.reason, decision.risk)
                return _normalize_tool_result(
                    name,
                    clean_args,
                    _err(
                        "confirmation required",
                        status="needs_confirmation",
                        verified=False,
                        completion_status="needs_confirmation",
                        confirmation=pending.get("confirmation"),
                    ),
                )
        # CC-101: reinyectamos `confirmed` despues de validar para que los
        # gates duros (terminal/system/package/database/backup_sync/filesystem)
        # puedan respetar la confirmacion previa sin chocar con el schema.
        impl_args = dict(clean_args)
        if confirmed:
            impl_args["confirmed"] = True
        try:
            result = impl(impl_args)
        except Exception as exc:
            result = _err(f"{type(exc).__name__}: {exc}")
        return _normalize_tool_result(name, clean_args, result)

    def execute_routine_step(self, name: str, args: dict[str, Any] | None, *, confirmed_at_create: bool) -> dict[str, Any]:
        """Dispatcher para pasos de routines/watchers.

        Inyecta `routine_context=True` y `confirmed_at_create` después de
        pasar por la validación de schema. Estos kwargs son invisibles al LLM
        (no aparecen en COMPOUND_TOOL_SCHEMAS y `execute()` los filtra).
        """
        clean_args = dict(args or {})
        for forbidden in ("_internal_safe", "routine_context", "confirmed_at_create"):
            clean_args.pop(forbidden, None)
        impl = self._impls.get(name)
        if not impl:
            return _normalize_tool_result(name, clean_args, _err(f"unknown tool: {name}"))
        clean_args, validation_errors = _coerce_and_validate_tool_args(name, clean_args)
        if validation_errors:
            return _normalize_tool_result(
                name,
                clean_args,
                _err(
                    "invalid tool arguments",
                    validation_errors=validation_errors,
                    expected_schema=_parameters_for_tool(name),
                ),
            )
        impl_args = dict(clean_args)
        impl_args["routine_context"] = True
        impl_args["confirmed_at_create"] = bool(confirmed_at_create)
        try:
            result = impl(impl_args)
        except Exception as exc:
            result = _err(f"{type(exc).__name__}: {exc}")
        return _normalize_tool_result(name, clean_args, result)

    # ============================================================
    # Compound tools exposed to Gemma 4
    # ============================================================

    def t_system(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args)
        if action == "time":
            return self.system_time(args)
        if action == "processes":
            return self.list_processes(args)
        if action == "cpu_ram_gpu":
            return self.system_cpu_ram_gpu(args)
        if action == "disk":
            return self.system_disk(args)
        if action == "battery":
            return self.system_battery(args)
        if action == "brightness_get":
            return self.system_brightness_get(args)
        if action == "brightness_set":
            return self.system_brightness_set(args)
        if action in ("shutdown", "restart", "sleep"):
            # CC-101 / T1-system-shutdown-no-confirmation-002: gate duro.
            gate = self._hard_gate(
                tool_name="system",
                action=action,
                args=args,
                reason=f"system.{action} will power-off/restart/suspend the machine",
                risk="critical",
                routine_context=bool(args.get("routine_context")),
                confirmed_at_create=bool(args.get("confirmed_at_create")),
            )
            if gate is not None:
                return gate
            if action == "shutdown":
                return self.terminal_run({"command": "shutdown", "args": ["/s", "/t", str(int(args.get("delay_sec", 0)))], "timeout_sec": 10, "_internal_safe": True})
            if action == "restart":
                return self.terminal_run({"command": "shutdown", "args": ["/r", "/t", str(int(args.get("delay_sec", 0)))], "timeout_sec": 10, "_internal_safe": True})
            return self.terminal_run({"command": "rundll32.exe", "args": ["powrprof.dll,SetSuspendState", "0,1,0"], "timeout_sec": 10, "_internal_safe": True})
        return _err("unknown system action", action=action)

    def t_audio(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args)
        if action == "get_volume":
            return self.audio_get_volume(args)
        if action == "set_volume":
            return self.audio_set_volume(args)
        if action == "mute":
            return self.audio_mute(args)
        if action == "devices":
            return self.audio_devices(args)
        if action == "set_default":
            return self.audio_set_default(args)
        if action in {"media_play_pause", "media_pause", "play_pause", "pause", "stop", "media_stop", "next", "previous"}:
            return self.audio_media_control(args)
        return _err("unknown audio action", action=action)

    def t_app(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="open")
        name = args.get("name") or args.get("query")
        if action == "search":
            return self.app_search({"query": name or "", "limit": args.get("limit", 10), "refresh": args.get("refresh", False)})
        if action == "open":
            return self.app_open({"name": name or "", "refresh": args.get("refresh", False)})
        if action == "close":
            return self.app_close({"name": name or ""})
        if action == "uninstall":
            return self.t_package({"action": "uninstall", "name": name or ""})
        return _err("unknown app action", action=action)

    def t_steam(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="open")
        query = str(args.get("query") or args.get("name") or "").strip()
        if action == "open":
            os.startfile("steam://open/main")  # type: ignore[attr-defined]
            resource = self.state.register_resource("steam", "Steam", cleanup_tool="app", cleanup_args={"action": "close", "name": "Steam"})
            return _ok(action=action, uri="steam://open/main", resource=resource.get("resource"))
        if action == "library":
            os.startfile("steam://open/games")  # type: ignore[attr-defined]
            resource = self.state.register_resource("steam", "Steam library", cleanup_tool="app", cleanup_args={"action": "close", "name": "Steam"})
            return _ok(action=action, uri="steam://open/games", resource=resource.get("resource"))
        if action == "store":
            if query:
                return self.t_steam({**args, "action": "store_page", "query": query})
            os.startfile("steam://store")  # type: ignore[attr-defined]
            resource = self.state.register_resource("steam", "Steam store", cleanup_tool="app", cleanup_args={"action": "close", "name": "Steam"})
            return _ok(action=action, uri="steam://store", resource=resource.get("resource"))
        if action == "list_games":
            games = [c.as_dict() for c in self.apps._from_steam()]
            return _ok(games=games, count=len(games))
        if action == "search_library":
            if not query:
                return _err("missing search query")
            matches = self.apps.find_steam_library(query, limit=5)
            if matches:
                best = matches[0]
                appid = _steam_appid_from_launch(best.launch)
                if appid:
                    uri = f"steam://nav/games/details/{appid}"
                    os.startfile(uri)  # type: ignore[attr-defined]
                    resource = self.state.register_resource("steam", f"Steam library: {best.name}", cleanup_tool="app", cleanup_args={"action": "close", "name": "Steam"}, metadata={"uri": uri, "match": best.as_dict()})
                    time.sleep(float(args.get("delay_sec", 2.5)))
                    focus = self.window_control("focus", "Steam")
                    time.sleep(0.5)
                    shot = self.gui_screenshot({})
                    return _attach_screenshot(
                        _ok(
                            action=action,
                            query=query,
                            uri=uri,
                            matched_game=best.as_dict(),
                            alternatives=[m.as_dict() for m in matches[1:5]],
                            resource=resource.get("resource"),
                            local_match_verified=True,
                            visual_verified=False,
                            completion_status="opened_matching_steam_library_detail",
                            focus=focus,
                            note="Matched the query against local Steam metadata and opened the game's library details by AppID. The screenshot is provided for visual verification.",
                        ),
                        shot,
                    )

            os.startfile("steam://open/games")  # type: ignore[attr-defined]
            resource = self.state.register_resource("steam", f"Steam library search: {query}", cleanup_tool="app", cleanup_args={"action": "close", "name": "Steam"}, metadata={"query": query})
            time.sleep(float(args.get("delay_sec", 2.5)))
            focus = self.window_control("focus", "Steam")
            time.sleep(0.5)
            self.gui_keypress({"keys": "CTRL+F"})
            self.gui_type({"text": query})
            shot = self.gui_screenshot({})
            return _attach_screenshot(
                _err(
                    "steam_library_search_unverified",
                    action=action,
                    query=query,
                    uri="steam://open/games",
                    resource=resource.get("resource"),
                    attempted=True,
                    keyboard_attempted=True,
                    visual_verified=False,
                    completion_status="attempted_unverified_gui_search",
                    focus=focus,
                    note="Opened Steam library and sent Ctrl+F plus the query, but no local Steam metadata match was found and the GUI search cannot be trusted until the screenshot is inspected.",
                ),
                shot,
            )
        if action == "launch_game":
            if not query:
                return _err("missing game name")
            matches = [m for m in self.apps.find(query, limit=5) if m.source == "steam"]
            if not matches:
                return _err("steam game not found", query=query)
            os.startfile(matches[0].launch)  # type: ignore[attr-defined]
            resource = self.state.register_resource("steam_game", matches[0].name, cleanup_tool="app", cleanup_args={"action": "close", "name": matches[0].name}, metadata={"launch": matches[0].launch})
            return _ok(query=query, launched=matches[0].as_dict(), alternatives=[m.as_dict() for m in matches[1:]], resource=resource.get("resource"))
        if action in {"search_store", "store_page"}:
            if not query:
                return _err("missing search query")
            return self.steam_store_page(args, query)
        if action == "install":
            appid = str(args.get("appid") or "").strip()
            if appid:
                uri = f"steam://install/{appid}"
                os.startfile(uri)  # type: ignore[attr-defined]
                return _ok(appid=appid, uri=uri)
            return self.t_steam({"action": "search_store", "query": query})
        return _err("unknown steam action", action=action)

    def t_window(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="list")
        if action == "list":
            return self.list_windows(args)
        if action == "active":
            return self.window_active(args)
        if action in {"focus", "close", "minimize", "maximize", "restore"}:
            return self.window_control(action, str(args.get("title") or args.get("query") or ""))
        if action == "move_resize":
            return self.window_move_resize(args)
        return _err("unknown window action", action=action)

    # Acciones GUI que MUTAN la pantalla -> verificamos el efecto post-acción
    # (Fase 1 computer-use: cerrar el "click/type ciego"). Ver gui_verify.py.
    _GUI_MUTATING = {"click", "double_click", "right_click", "type",
                     "keypress", "hotkey", "scroll", "drag"}

    def _gui_dispatch_raw(self, action: str, args: dict[str, Any]) -> dict[str, Any]:
        if action == "click":
            return self.gui_click(args)
        if action == "double_click":
            return self.gui_multi_click(args, button="left", clicks=2)
        if action == "right_click":
            return self.gui_multi_click(args, button="right", clicks=1)
        if action == "type":
            return self.gui_type(args)
        if action in {"keypress", "hotkey"}:
            return self.gui_keypress({"keys": args.get("keys") or args.get("hotkey") or ""})
        if action == "scroll":
            return self.gui_scroll(args)
        if action == "drag":
            return self.gui_drag(args)
        return _err("unknown gui mutating action", action=action)

    def t_gui(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="screenshot")
        if action == "screenshot":
            return self.gui_screenshot(args)
        if action == "type_into":
            return self.gui_type_into(args)
        if action == "click_button":
            return self.gui_click_button(args)
        if action in self._GUI_MUTATING:
            # verify_post_action: capturar ROI antes -> actuar -> verificar que el
            # SO cambió. Anota state_changed en el result (honestidad: el agente
            # deja de creer que hizo algo que no hizo). Best-effort, nunca rompe.
            try:
                from . import gui_verify
                _x = args.get("x"); _y = args.get("y")
                _before = gui_verify.capture_before(
                    int(_x) if _x is not None else None,
                    int(_y) if _y is not None else None)
            except Exception:
                _before = None
            result = self._gui_dispatch_raw(action, args)
            try:
                if _before is not None and isinstance(result, dict) and result.get("ok"):
                    from . import gui_verify
                    _v = gui_verify.verify_after(_before)
                    result["state_changed"] = _v.get("state_changed")
                    result["state_verify"] = _v.get("reason")
                    # Si NO cambió nada medible, marcar para el honesty-guard:
                    # la acción se despachó pero no se observó efecto.
                    if _v.get("state_changed") is False:
                        result["verified"] = False
                        result.setdefault("completion_status", "dispatched_no_effect")
            except Exception:
                pass
            return result
        if action == "wait_for":
            return self.gui_wait_for(args)
        if action in {"locate_text", "click_text"}:
            shot = self.gui_screenshot(args)
            target = str(args.get("text") or args.get("target") or "")
            if not shot.get("ok") or not target:
                shot["target"] = target
                return shot
            found = ocr_find_text(Path(str(shot["image_path"])), target, lang=str(args.get("lang") or "spa+eng"), min_conf=int(args.get("min_conf", 25)))
            # CC-106 / CC-window-virtualscreen-coords-106: añade screen_x/screen_y
            # (pre-traducidos) a cada match para que el LLM pueda clickear sin
            # re-aplicar shot.left/top. center_x/center_y siguen siendo image-local.
            shot_left = int(shot.get("left", 0))
            shot_top = int(shot.get("top", 0))
            enriched_matches = []
            for match in found.get("matches") or []:
                if isinstance(match, dict) and "center_x" in match and "center_y" in match:
                    enriched = dict(match)
                    enriched["screen_x"] = int(match["center_x"]) + shot_left
                    enriched["screen_y"] = int(match["center_y"]) + shot_top
                    enriched["coord_space"] = "image_local"
                    enriched_matches.append(enriched)
                else:
                    enriched_matches.append(match)
            if enriched_matches:
                found["matches"] = enriched_matches
            found = _attach_screenshot(found, shot)
            if action == "click_text" and found.get("found") and found.get("matches"):
                match = found["matches"][0]
                # Usamos screen_x/screen_y si están; caída a la traducción manual si no.
                if isinstance(match, dict) and "screen_x" in match and "screen_y" in match:
                    click = self.gui_click({"x": int(match["screen_x"]), "y": int(match["screen_y"])})
                else:
                    click = self.gui_click({"x": int(match["center_x"]) + shot_left, "y": int(match["center_y"]) + shot_top})
                found["click"] = click
                found["clicked"] = click.get("ok", False)
            return found
        if action == "locate_image":
            shot = self.gui_screenshot(args)
            shot["note"] = "locate_image returns a screenshot for Gemma 4 visual reasoning; template matching is not implemented."
            shot["target"] = args.get("image") or args.get("target")
            return shot
        return _err("unknown gui action", action=action)

    def t_vision(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="describe_screen")
        image_path = Path(str(args.get("image_path") or "")).expanduser() if args.get("image_path") else None
        if action == "ocr":
            shot = {"ok": True, "image_path": str(image_path)} if image_path else self.gui_screenshot(args)
            if not shot.get("ok"):
                return shot
            result = ocr_image(Path(str(shot["image_path"])), lang=str(args.get("lang") or "spa+eng"), min_conf=int(args.get("min_conf", 35)))
            return _attach_screenshot(result, shot)
        if action == "find_element":
            shot = {"ok": True, "image_path": str(image_path)} if image_path else self.gui_screenshot(args)
            if not shot.get("ok"):
                return shot
            target = str(args.get("target") or args.get("text") or "")
            if target:
                result = ocr_find_text(Path(str(shot["image_path"])), target, lang=str(args.get("lang") or "spa+eng"), min_conf=int(args.get("min_conf", 25)))
                return _attach_screenshot(result, shot)
            shot["note"] = "No target text was provided; screenshot captured for Gemma 4 native visual reasoning."
            return shot
        shot = self.gui_screenshot(args)
        shot["vision_action"] = action
        shot["target"] = args.get("target") or args.get("text")
        shot["note"] = "Screenshot captured and re-injected as Gemma 4 image input for native visual reasoning."
        return shot

    def t_browser(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="open")
        query = str(args.get("query") or "").strip()
        browser = str(args.get("browser") or "").strip()
        if action == "open":
            url = str(args.get("url") or "").strip() or query
            if not url:
                # LAUNCH-THE-APP fallback: el modelo chico (E4B-Q4) interpreta
                # "lanzá Chrome" / "abrí Firefox" como browser.open con
                # browser/name="Chrome" y SIN url — porque "Chrome" es un
                # navegador. La intención real es LANZAR el programa, no navegar.
                # En vez de devolver needs_user (que el modelo convierte en "no
                # puedo abrir Chrome sin URL"), delegamos a app.open: hacemos la
                # acción real. No es un hardcode de routing ni una respuesta
                # enlatada — es la tool garantizando su precondición (CLAUDE.md
                # #5) cuando el arg nombra una app y falta el url. La regla en
                # prompts/tool_rules/browser.md enseña la forma correcta
                # (app.open); esto es la red de seguridad determinista.
                app_name = (browser or str(args.get("name") or "")).strip()
                if app_name:
                    res = self.app_open({"name": app_name})
                    if res.get("ok"):
                        res.update(delegated_from="browser.open",
                                   note="No URL given; launched the browser application via app.open.")
                        return res
                    # si app.open tampoco lo encuentra, caemos al error normal
                return _err(
                    "browser.open requires url or query",
                    status="needs_user", action=action,
                )
            result = self.web_open_url({"url": url})
            result.update(content_verified=False, completion_status="opened_url")
            return result
        if action in {"youtube_play", "play_youtube", "play_media"}:
            return self.browser_youtube_play(args)
        if action in {"media_pause", "pause_video"}:
            return self.audio_media_control({"action": "media_play_pause"})
        if action in {"media_stop", "stop_video"}:
            return self.audio_media_control({"action": "media_stop"})
        if action == "search":
            if not query:
                return _err(
                    "browser.search requires non-empty query",
                    status="needs_user", action=action,
                )
            engine = str(args.get("engine") or "google").casefold()
            browser_is_youtube_app = "youtube" in _fold(browser)
            if browser_is_youtube_app and _looks_like_music_request(query):
                play_args = {**args, "browser": "", "query": query}
                return self.browser_youtube_play(play_args)
            if engine == "youtube" or browser_is_youtube_app:
                url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
            else:
                url = f"https://www.google.com/search?q={quote_plus(query)}"
            if browser and not browser_is_youtube_app:
                opened = self.app_open({"name": browser})
                time.sleep(float(args.get("delay_sec", 1.5)))
                self.gui_keypress({"keys": "CTRL+L"})
                self.gui_type({"text": url})
                self.gui_keypress({"keys": "ENTER"})
                return _ok(browser=browser, url=url, opened=opened, method="targeted_browser_gui", content_verified=False, completion_status="opened_search_results")
            result = self.web_open_url({"url": url})
            result.update(content_verified=False, completion_status="opened_search_results")
            return result
        if action in {"research", "read", "search_web"}:
            return self.t_web({**args, "action": action})
        if action == "active_tab_title":
            return self.window_active(args)
        if action in {"click", "find"}:
            shot = self.gui_screenshot(args)
            shot["note"] = f"Use Gemma 4 vision to {action} in browser."
            shot["target"] = args.get("target") or query
            return shot
        return _err(
            "unknown browser action", action=action,
            valid_actions=[
                "open", "search", "youtube_play", "media_pause", "media_stop",
                "research", "read", "active_tab_title", "click", "find",
            ],
            status="needs_user",
        )

    def t_web(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="search")
        if action in {"search", "search_web"}:
            # VALIDACION: web_search sin query es no-op silencioso.
            if not str(args.get("query") or "").strip():
                return _err("web.search requires non-empty query", status="needs_user")
            return self.web_search(args)
        if action == "open":
            if not str(args.get("url") or "").strip():
                return _err("web.open requires url", status="needs_user")
            return self.web_open_url(args)
        if action == "read":
            if not str(args.get("url") or "").strip():
                return _err("web.read requires url", status="needs_user")
            return self.web_read(args)
        if action == "research":
            if not str(args.get("query") or "").strip():
                return _err("web.research requires query", status="needs_user")
            return self.web_research(args)
        return _err(
            "unknown web action", action=action,
            valid_actions=["search", "search_web", "open", "read", "research"],
            status="needs_user",
        )

    def t_uia(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="tree")
        if action == "tree":
            return self.uia_tree(args)
        if action == "find":
            return self.uia_find(args)
        if action == "click":
            return self.uia_click(args)
        if action == "focus":
            return self.uia_focus(args)
        if action in {"set_value", "type"}:
            return self.uia_set_value(args)
        return _err(
            "unknown uia action", action=action,
            valid_actions=["tree", "find", "click", "focus", "set_value", "type"],
            status="needs_user",
        )

    def browser_youtube_play(self, args: dict[str, Any]) -> dict[str, Any]:
        target = self._youtube_play_target(args)
        url = target["url"]
        browser = str(args.get("browser") or "").strip()
        browser_is_site = "youtube" in _fold(browser)

        if browser and not browser_is_site:
            opened = self.app_open({"name": browser})
            time.sleep(float(args.get("delay_sec", 1.5)))
            self.gui_keypress({"keys": "CTRL+L"})
            self.gui_type({"text": url})
            self.gui_keypress({"keys": "ENTER"})
            method = "targeted_browser_gui"
        else:
            opened = self.web_open_url({"url": url})
            method = "default_browser_url"

        time.sleep(float(args.get("post_open_delay_sec", 2.5)))
        shot = self.gui_screenshot({})
        return _attach_screenshot(
            _ok(
                action="youtube_play",
                query=target["query"],
                selected_title=target.get("title"),
                url=url,
                opened=opened,
                method=method,
                direct_video=target["direct_video"],
                visual_verified=False,
                playback_verified=False,
                completion_status="opened_youtube_video_for_playback" if target["direct_video"] else "opened_youtube_search_unverified",
                note="Opened a direct YouTube video URL when possible. Audio playback still depends on the browser/YouTube autoplay state; screenshot is provided for visual verification.",
            ),
            shot,
        )

    def _youtube_play_target(self, args: dict[str, Any]) -> dict[str, Any]:
        raw_query = str(args.get("query") or args.get("song") or args.get("title") or args.get("name") or "").strip()
        if _is_generic_song_query(raw_query):
            choice = random.choice(DEFAULT_YOUTUBE_SONGS)
            return {
                "query": raw_query or "random song",
                "title": choice["title"],
                "url": _youtube_watch_url(choice["video_id"]),
                "direct_video": True,
            }

        if _looks_like_youtube_watch_url(raw_query):
            return {"query": raw_query, "title": None, "url": raw_query, "direct_video": True}

        found = _youtube_first_result(raw_query)
        if found:
            return {
                "query": raw_query,
                "title": found.get("title"),
                "url": _youtube_watch_url(str(found["video_id"])),
                "direct_video": True,
            }

        return {
            "query": raw_query,
            "title": None,
            "url": f"https://www.youtube.com/results?search_query={quote_plus(raw_query)}",
            "direct_video": False,
        }

    def steam_store_page(self, args: dict[str, Any], query: str) -> dict[str, Any]:
        appid = str(args.get("appid") or "").strip()
        matched: dict[str, Any] | None = None
        source = "explicit_appid" if appid else ""

        if not appid:
            local_matches = self.apps.find_steam_library(query, limit=5)
            if local_matches:
                best = local_matches[0]
                local_appid = _steam_appid_from_launch(best.launch)
                if local_appid:
                    appid = local_appid
                    matched = best.as_dict()
                    source = best.source

        if not appid:
            store_match = _steam_store_first_result(query)
            if store_match:
                appid = store_match["appid"]
                matched = store_match
                source = "steam_store_search"

        if appid:
            uri = _steam_store_uri(appid)
            url = _steam_store_url(appid, str((matched or {}).get("name") or query))
            os.startfile(uri)  # type: ignore[attr-defined]
            resource = self.state.register_resource("steam", f"Steam store: {query}", cleanup_tool="app", cleanup_args={"action": "close", "name": "Steam"}, metadata={"appid": appid, "uri": uri, "store_url": url})
            return _ok(
                action=str(args.get("action") or "store_page"),
                query=query,
                appid=appid,
                uri=uri,
                store_url=url,
                opened_in="steam_client",
                matched=matched,
                match_source=source,
                resource=resource.get("resource"),
                content_verified=True,
                visual_verified=False,
                completion_status="opened_steam_client_store_page",
                evidence={"appid": appid, "uri": uri, "store_url": url},
                note="Resolved a Steam AppID and opened the store page through the Steam client URI, not the normal web browser.",
            )

        search_url = f"https://store.steampowered.com/search/?term={quote_plus(query)}"
        uri = _steam_openurl_uri(search_url)
        os.startfile(uri)  # type: ignore[attr-defined]
        resource = self.state.register_resource("steam", f"Steam store search: {query}", cleanup_tool="app", cleanup_args={"action": "close", "name": "Steam"}, metadata={"uri": uri, "store_url": search_url})
        return _ok(
            action=str(args.get("action") or "store_page"),
            query=query,
            uri=uri,
            store_url=search_url,
            opened_in="steam_client",
            resource=resource.get("resource"),
            content_verified=False,
            visual_verified=False,
            completion_status="opened_steam_client_store_search_unverified",
            status="needs_verification",
            verified=False,
            evidence={"query": query, "uri": uri},
            note="No AppID could be resolved, so the Steam client was opened on store search results. This is not proof that the exact app page is selected.",
        )

    def t_filesystem(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="list")
        if action == "list":
            return self.filesystem_list(args)
        if action == "read":
            return self.filesystem_read(args)
        if action == "write":
            return self.filesystem_write(args)
        if action == "search":
            return self.filesystem_search(args)
        if action == "delete":
            return self.filesystem_delete(args)
        if action == "copy":
            return self.filesystem_copy(args)
        if action == "move":
            return self.filesystem_move(args)
        if action == "rename":
            return self.filesystem_rename(args)
        if action == "mkdir":
            return self.filesystem_mkdir(args)
        if action == "diff":
            return self.filesystem_diff(args)
        if action == "archive":
            return self.filesystem_archive(args)
        if action == "unarchive":
            return self.filesystem_unarchive(args)
        if action == "open":
            return self.filesystem_open(args)
        return _err("unknown filesystem action", action=action)

    def t_package(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="search")
        name = str(args.get("name") or args.get("query") or "").strip()
        if action == "list":
            return self.terminal_run({"command": "winget", "args": ["list"], "timeout_sec": 120, "_internal_safe": True})
        if action == "search":
            return self.terminal_run({"command": "winget", "args": ["search", name], "timeout_sec": 120, "_internal_safe": True})
        if action in ("install", "uninstall"):
            # CC-101 / T2-package-install-no-confirm-043: gate duro.
            gate = self._hard_gate(
                tool_name="package",
                action=action,
                args=args,
                reason=f"package.{action} will modify installed software via winget: {name}",
                risk="high",
                routine_context=bool(args.get("routine_context")),
                confirmed_at_create=bool(args.get("confirmed_at_create")),
            )
            if gate is not None:
                return gate
            if action == "install":
                return self.terminal_run({"command": "winget", "args": ["install", "--accept-source-agreements", "--accept-package-agreements", name], "timeout_sec": 1800, "_internal_safe": True})
            return self.terminal_run({"command": "winget", "args": ["uninstall", name], "timeout_sec": 900, "_internal_safe": True})
        return _err("unknown package action", action=action)

    def t_clipboard(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="read")
        if action == "read":
            return self.clipboard_read(args)
        if action == "write":
            return self.clipboard_write(args)
        return _err("unknown clipboard action", action=action)

    def t_terminal(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="run")
        if action == "run":
            return self.terminal_run(args)
        return _err("unknown terminal action", action=action)

    def t_memory(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="recall")
        if action == "save":
            return self.memory_save(args)
        if action == "recall":
            return self.memory_recall(args)
        if action == "list":
            return self.memory_list(args)
        if action == "delete":
            return self.memory_delete(args)
        return _err("unknown memory action", action=action)

    def t_verify(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args)
        if action == "app_opened":
            return self.verify_app_opened(args)
        if action == "file_exists":
            return self.verify_file_exists(args)
        if action == "window_exists":
            return self.verify_window_exists(args)
        if action == "clipboard_contains":
            return self.verify_clipboard_contains(args)
        return _err("unknown verify action", action=action)

    def t_skill_load(self, args: dict[str, Any]) -> dict[str, Any]:
        """TIER 1 #4: el LLM emite skill_load(name="X") para recibir el body
        completo de un SKILL.md como tool_result. El menu de skills aparece
        en el system_prompt al boot; aca solo materializamos el body lazy.

        Cap por turn (cuantas skill_load() puede emitir el LLM en el mismo
        turn) se aplica via self.state, no aca — keep this method simple.
        """
        name = str(args.get("name") or "").strip()
        if not name:
            return _err(
                "skill_load requires name (from the SKILLS AVAILABLE menu)",
                status="needs_user",
            )
        from .skills_registry import load_skill_content, scan_skills
        body = load_skill_content(name)
        if body is None:
            # Si el skill no existe, listar los nombres disponibles como hint.
            available = [s.name for s in scan_skills()]
            return _err(
                f"skill '{name}' not found or not eligible on this system",
                status="needs_user",
                available_skills=available,
                hint="check the SKILLS AVAILABLE menu in the system prompt; skill names are lowercase + hyphens",
            )
        return _ok(
            skill=name,
            recipe=body,
            chars=len(body),
            source="local",
            note="follow this recipe step-by-step using the listed tools",
        )

    def t_state(self, args: dict[str, Any]) -> dict[str, Any]:
        return state_tool(args, self.state, self.execute)

    def t_input(self, args: dict[str, Any]) -> dict[str, Any]:
        return input_tool(args, self.state)

    def t_env(self, args: dict[str, Any]) -> dict[str, Any]:
        return env_tool(args, self.state)

    def t_registry(self, args: dict[str, Any]) -> dict[str, Any]:
        return registry_tool(args, self.state)

    def t_download(self, args: dict[str, Any]) -> dict[str, Any]:
        return download_tool(args, self.state)

    def t_email(self, args: dict[str, Any]) -> dict[str, Any]:
        return email_tool(args, self.state)

    def t_reminder(self, args: dict[str, Any]) -> dict[str, Any]:
        return reminder_tool(args, self.state)

    def t_browser_real(self, args: dict[str, Any]) -> dict[str, Any]:
        return browser_real_tool(args, self.state, self.captures_dir)

    def t_knowledge(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="search")
        if action == "status":
            return self.knowledge.status()
        if action == "ingest":
            path = str(args.get("path") or "").strip()
            title = str(args.get("title") or "").strip() or None
            if path:
                # VALIDACION temprana: si el path no existe, devolver error
                # estructurado en vez de propagar IOError desde knowledge.
                p = Path(path).expanduser()
                if not p.exists():
                    return _err(
                        "knowledge ingest path does not exist", path=str(p),
                        status="needs_user",
                    )
                if not p.is_file():
                    return _err(
                        "knowledge ingest path is not a file", path=str(p),
                        status="needs_user",
                        hint="for directories, ingest each file individually",
                    )
                return self.knowledge.ingest_file(p, title=title)
            # No path: ingest_text. Validar que hay contenido.
            text = str(args.get("text") or "").strip()
            if not text:
                return _err(
                    "knowledge ingest requires either path or non-empty text",
                    status="needs_user",
                )
            return self.knowledge.ingest_text(
                text,
                source=str(args.get("source") or "user_text"),
                title=title,
            )
        if action == "search":
            query = str(args.get("query") or "").strip()
            if not query:
                return _err("knowledge search requires non-empty query", status="needs_user")
            rerank_arg = args.get("rerank")
            try:
                limit = max(1, min(int(args.get("limit", 5)), 50))
            except (TypeError, ValueError):
                limit = 5
            return self.knowledge.search(
                query,
                limit=limit,
                rerank=None if rerank_arg is None else bool(rerank_arg),
            )
        if action == "list":
            try:
                limit = max(1, min(int(args.get("limit", 100)), 1000))
            except (TypeError, ValueError):
                limit = 100
            return self.knowledge.list_documents(limit=limit)
        if action == "delete":
            doc_id = str(args.get("doc_id") or "").strip()
            if not doc_id:
                return _err("knowledge delete requires doc_id", status="needs_user")
            return self.knowledge.delete(doc_id)
        return _err(
            "unknown knowledge action", action=action,
            valid_actions=["status", "ingest", "search", "list", "delete"],
            status="needs_user",
        )

    def t_office(self, args: dict[str, Any]) -> dict[str, Any]:
        return office_tool(args, self.state)

    def t_audio_device(self, args: dict[str, Any]) -> dict[str, Any]:
        return audio_device_tool(args, self.state)

    def t_notification(self, args: dict[str, Any]) -> dict[str, Any]:
        return notification_tool(args, self.state)

    def t_routine(self, args: dict[str, Any]) -> dict[str, Any]:
        return routine_tool(args, self.state, executor=self.execute)

    def t_media(self, args: dict[str, Any]) -> dict[str, Any]:
        # open_local is a documented alias for play(provider=local_file, path=...)
        return media_tool(args, self.execute, self.state)

    def t_source_manager(self, args: dict[str, Any]) -> dict[str, Any]:
        return source_manager_tool(args, self.state)

    def t_dependency(self, args: dict[str, Any]) -> dict[str, Any]:
        return dependency_tool(args)

    def t_contacts(self, args: dict[str, Any]) -> dict[str, Any]:
        return contacts_tool(args, self.state)

    def t_whatsapp(self, args: dict[str, Any]) -> dict[str, Any]:
        return whatsapp_tool(args, self.state, executor=self.execute)

    def t_notes_tasks(self, args: dict[str, Any]) -> dict[str, Any]:
        return notes_tasks_tool(args, self.state)

    def t_local_calendar(self, args: dict[str, Any]) -> dict[str, Any]:
        return local_calendar_tool(args, self.state)

    def t_habit_tracker(self, args: dict[str, Any]) -> dict[str, Any]:
        return habit_tracker_tool(args, self.state)

    def t_local_search(self, args: dict[str, Any]) -> dict[str, Any]:
        return local_search_tool(args)

    def t_printer_scanner(self, args: dict[str, Any]) -> dict[str, Any]:
        return printer_scanner_tool(args)

    def t_desktop_layout(self, args: dict[str, Any]) -> dict[str, Any]:
        return desktop_layout_tool(args, self.state, self.execute)

    def t_document(self, args: dict[str, Any]) -> dict[str, Any]:
        return document_tool(args, self.state, knowledge_executor=self.execute)

    def t_developer(self, args: dict[str, Any]) -> dict[str, Any]:
        return developer_tool(args, self.state)

    def t_device_settings(self, args: dict[str, Any]) -> dict[str, Any]:
        return device_settings_tool(args, self.state)

    def t_game_launcher(self, args: dict[str, Any]) -> dict[str, Any]:
        return game_launcher_tool(args, self.state, executor=self.execute)

    def t_media_edit(self, args: dict[str, Any]) -> dict[str, Any]:
        return media_edit_tool(args, self.state)

    def t_maintenance(self, args: dict[str, Any]) -> dict[str, Any]:
        return maintenance_tool(args, self.state)

    def t_watcher(self, args: dict[str, Any]) -> dict[str, Any]:
        return watcher_tool(args, self.state, executor=self.execute)

    def t_job_manager(self, args: dict[str, Any]) -> dict[str, Any]:
        return job_manager_tool(args, self.state)

    def t_network(self, args: dict[str, Any]) -> dict[str, Any]:
        return network_tool(args, self.state)

    def t_data_analysis(self, args: dict[str, Any]) -> dict[str, Any]:
        return data_analysis_tool(args, self.state)

    def t_fact_check(self, args: dict[str, Any]) -> dict[str, Any]:
        return fact_check_tool(args, self.state, knowledge_executor=self.execute)

    def t_photo_library(self, args: dict[str, Any]) -> dict[str, Any]:
        return photo_library_tool(args, self.state)

    def t_container(self, args: dict[str, Any]) -> dict[str, Any]:
        return container_tool(args, self.state)

    def t_database(self, args: dict[str, Any]) -> dict[str, Any]:
        return database_tool(args, self.state)

    def t_creative_local(self, args: dict[str, Any]) -> dict[str, Any]:
        return creative_local_tool(args, self.state)

    def t_form_filler(self, args: dict[str, Any]) -> dict[str, Any]:
        return form_filler_tool(args, self.state, executor=self.execute)

    def t_peripheral(self, args: dict[str, Any]) -> dict[str, Any]:
        return peripheral_tool(args, self.state)

    def t_accessibility(self, args: dict[str, Any]) -> dict[str, Any]:
        return accessibility_tool(args, self.state)

    def t_study(self, args: dict[str, Any]) -> dict[str, Any]:
        return study_tool(args, self.state)

    def t_smart_home(self, args: dict[str, Any]) -> dict[str, Any]:
        return smart_home_tool(args, self.state)

    def t_subagent(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="run")
        parent = getattr(self, "parent_agent", None)
        if parent is None:
            return _err("subagent requires a running parent agent; cannot delegate from this context",
                        status="needs_implementation", verified=False)
        if action == "status":
            return _ok(
                backend="gemma4_agent.subagent",
                ready=True,
                note="Delegate a focused task to a fresh child agent. Pass max_turns (1..10) and optional tools=[...].",
            )
        if action != "run":
            return _err(f"unknown subagent action: {action}")
        task = str(args.get("task") or args.get("instruction") or "").strip()
        if not task:
            return _err("subagent.run requires task=<instruction>")
        tools_filter = args.get("tools") if isinstance(args.get("tools"), list) else None
        max_turns = int(args.get("max_turns", 4))
        from .subagent import run_subagent
        return run_subagent(parent, task, tools_filter=tools_filter, max_turns=max_turns)

    def t_backup_sync(self, args: dict[str, Any]) -> dict[str, Any]:
        return backup_sync_tool(args, self.state)

    def t_safety(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="status")
        if action == "status":
            pending = self.state.list_confirmations().get("confirmations", [])
            return _ok(
                enabled=self.safety_enabled,
                pending_count=len(pending),
                pending_ids=[str(p.get("id")) for p in pending[:5]],
            )
        if action == "pending":
            return self.state.list_confirmations(include_resolved=bool(args.get("include_resolved", False)))
        confirmation_id = str(args.get("confirmation_id") or args.get("id") or "").strip()
        if action == "cancel":
            if not confirmation_id:
                # Si hay UNA sola pending, auto-elegirla (mismo patron que confirm).
                pending = self.state.list_confirmations().get("confirmations", [])
                if len(pending) == 1:
                    confirmation_id = str(pending[0]["id"])
                else:
                    return _err(
                        "missing confirmation_id (multiple or zero pending)",
                        status="needs_user",
                        pending_count=len(pending),
                        pending_ids=[str(p.get("id")) for p in pending[:5]],
                    )
            return self.state.resolve_confirmation(confirmation_id, "cancelled")
        if action == "confirm":
            if not confirmation_id:
                pending = self.state.list_confirmations().get("confirmations", [])
                if len(pending) == 1:
                    confirmation_id = str(pending[0]["id"])
            if not confirmation_id:
                pending = self.state.list_confirmations().get("confirmations", [])
                return _err(
                    "missing confirmation_id (multiple or zero pending)",
                    status="needs_user",
                    pending_count=len(pending),
                    pending_ids=[str(p.get("id")) for p in pending[:5]],
                    hint="pass id=... or call safety(action=pending) to list ids",
                )
            item_result = self.state.get_confirmation(confirmation_id)
            if not item_result.get("ok"):
                return item_result
            item = item_result["confirmation"]
            if item.get("status") != "pending":
                return _err(
                    "confirmation is not pending",
                    confirmation=item, status="needs_user",
                    hint="confirmation may have been already confirmed/cancelled/expired",
                )
            result = self.execute(str(item["tool"]), {**dict(item.get("args") or {}), "confirmed": True})
            self.state.resolve_confirmation(confirmation_id, "confirmed", result)
            return _ok(
                confirmation_id=confirmation_id,
                executed_tool=item["tool"],
                executed_args=item.get("args"),
                result=result,
                executed_ok=bool(result.get("ok")),
            )
        return _err(
            "unknown safety action", action=action,
            valid_actions=["status", "pending", "confirm", "cancel"],
            status="needs_user",
        )

    def t_session(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args)
        if action == "cancel_turn":
            return _ok(
                action="cancel_turn",
                status="done",
                verified=True,
                completion_status="turn_cancelled",
                note="User asked to interrupt/cancel the current turn. The assistant should acknowledge briefly in the user's language and stop.",
            )
        return _err(
            "unknown session action", action=action,
            valid_actions=["cancel_turn"],
        )

    def system_time(self, args: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now()
        return _ok(iso=now.isoformat(), human=now.strftime("%H:%M:%S %d/%m/%Y"))

    def list_processes(self, args: dict[str, Any]) -> dict[str, Any]:
        limit = int(args.get("limit", 40))
        # Preferir psutil (~30-150ms) sobre tasklist (~1-10s en algunos hosts).
        # En el log de _pre_session se vio que tasklist tardaba 10s+, lo cual
        # se propagaba a verify_app_opened y volvia app_open en una operacion
        # de 15-30s. psutil es in-process, no spawnea procesos.
        try:
            import psutil
            items: list[dict[str, Any]] = []
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    info = p.info
                    name = info.get("name") or ""
                    pid = info.get("pid")
                    if not name or pid is None:
                        continue
                    items.append({"name": name, "pid": str(pid)})
                    if len(items) >= limit:
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if items:
                return _ok(processes=items, source="psutil")
        except Exception:
            pass

        # Fallback subprocess tasklist (timeout reducido de 15 -> 6s; si tarda
        # mas, mejor devolver vacio que bloquear al caller).
        try:
            proc = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=6,
            )
        except (OSError, subprocess.TimeoutExpired):
            return _ok(processes=[], source="tasklist_timeout")
        rows = csv.reader(proc.stdout.splitlines())
        items = []
        for row in rows:
            if len(row) >= 2:
                items.append({"name": row[0], "pid": row[1]})
            if len(items) >= limit:
                break
        return _ok(processes=items, exit_code=proc.returncode, source="tasklist")

    def list_windows(self, args: dict[str, Any]) -> dict[str, Any]:
        limit = int(args.get("limit", 30))
        # Preferir pywin32 EnumWindows (~5-15ms) si esta disponible. Devuelve
        # ventanas REALES con su titulo. Antes este metodo (cuando uso psutil)
        # devolvia *procesos*, lo cual rompia la semantica para callers como
        # gui_focus/verify_window_exists que esperan ventanas top-level.
        try:
            import win32gui  # type: ignore
            import win32process  # type: ignore
            try:
                import psutil
            except Exception:
                psutil = None  # type: ignore[assignment]

            windows: list[dict[str, Any]] = []
            seen_pids: set[int] = set()

            def _enum(hwnd: int, _: Any) -> bool:
                if len(windows) >= limit:
                    return False
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                title = win32gui.GetWindowText(hwnd) or ""
                if not title.strip():
                    return True
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                except Exception:
                    pid = 0
                proc_name = ""
                if pid and pid not in seen_pids and psutil is not None:
                    try:
                        proc_name = psutil.Process(pid).name()
                        seen_pids.add(pid)
                    except Exception:
                        pass
                windows.append({
                    "process": proc_name,
                    "title": title,
                    "pid": pid,
                    "hwnd": hwnd,
                })
                return True

            win32gui.EnumWindows(_enum, None)
            if windows:
                return _ok(windows=windows, source="win32gui")
            # Sin ventanas visibles igual es un resultado valido
            return _ok(windows=[], source="win32gui")
        except Exception:
            pass

        script = (
            "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
            f"Select-Object -First {limit} ProcessName,MainWindowTitle,Id | ConvertTo-Json -Depth 3"
        )
        # timeout 15 -> 8s: si Get-Process tarda mas de 8s, algo grave esta
        # mal y bloquear 15s no ayuda. El caller tiene su propio fallback.
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return _ok(windows=[], source="powershell_timeout")
        ok, data = parse_ps_json(proc.stdout)
        if not ok:
            return _err("list_windows invalid JSON", stdout=data, stderr=_truncate(proc.stderr, 1000), exit_code=proc.returncode)
        if data is None:
            return _ok(windows=[])
        if isinstance(data, dict):
            data = [data]
        windows = [
            {"process": item.get("ProcessName"), "title": item.get("MainWindowTitle"), "pid": item.get("Id")}
            for item in data
        ]
        return _ok(windows=windows, source="powershell")

    def system_cpu_ram_gpu(self, args: dict[str, Any]) -> dict[str, Any]:
        script = r"""
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name,LoadPercentage
$os = Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory
$gpu = Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion
[PSCustomObject]@{ cpu=$cpu; os=$os; gpu=$gpu } | ConvertTo-Json -Depth 4
"""
        # timeout 20 -> 10s. CIM Win32_VideoController es el mas lento (1-3s
        # en sistemas con varios GPUs/displays); 10s da headroom 3x. Si tarda
        # mas hay algo serio mal en WMI.
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return _err("system_cpu_ram_gpu timeout", reason="powershell_cim_timeout")
        # CC-103: parse defensivo.
        ok, info = parse_ps_json(proc.stdout)
        if not ok:
            return _err("system_cpu_ram_gpu invalid JSON", stdout=info, stderr=_truncate(proc.stderr, 1000), exit_code=proc.returncode)
        return _ok(info=info, exit_code=proc.returncode)

    def system_disk(self, args: dict[str, Any]) -> dict[str, Any]:
        # Preferir psutil.disk_partitions + usage (~5ms, in-process). El CIM
        # query normalmente tarda <1s pero spawn de PowerShell paga ~300ms
        # de cold-start. psutil es 60x mas rapido y no spawnea procesos.
        try:
            import psutil
            disks: list[dict[str, Any]] = []
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append({
                        "DeviceID": part.device.rstrip("\\/"),
                        "Mountpoint": part.mountpoint,
                        "Size": usage.total,
                        "FreeSpace": usage.free,
                        "VolumeName": part.fstype,
                    })
                except (PermissionError, OSError):
                    continue
            if disks:
                return _ok(disks=disks, source="psutil")
        except Exception:
            pass

        script = "Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID,DriveType,Size,FreeSpace,VolumeName | ConvertTo-Json -Depth 3"
        # timeout 20s -> 8s (CIM normalmente <1s; si tarda mas, abort).
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return _ok(disks=[], source="powershell_timeout")
        ok, data = parse_ps_json(proc.stdout)
        if not ok:
            return _err("system_disk invalid JSON", stdout=data, stderr=_truncate(proc.stderr, 1000), exit_code=proc.returncode)
        if data is None:
            data = []
        if isinstance(data, dict):
            data = [data]
        return _ok(disks=data, exit_code=proc.returncode, source="powershell")

    def system_battery(self, args: dict[str, Any]) -> dict[str, Any]:
        # psutil.sensors_battery (~0.1ms) > Get-CimInstance (~500ms). Y
        # desktops sin bateria devuelven None limpio en psutil.
        try:
            import psutil
            batt = psutil.sensors_battery()
            if batt is None:
                return _ok(battery=None, has_battery=False, note="No battery (desktop or no driver).")
            return _ok(
                battery={
                    "percent": batt.percent,
                    "plugged": batt.power_plugged,
                    "secsleft": batt.secsleft if batt.secsleft != psutil.POWER_TIME_UNKNOWN else None,
                },
                has_battery=True,
                source="psutil",
            )
        except Exception:
            pass

        script = "Get-CimInstance Win32_Battery | Select-Object Name,EstimatedChargeRemaining,BatteryStatus | ConvertTo-Json -Depth 3"
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return _err("system_battery timeout", reason="powershell_timeout")
        ok, data = parse_ps_json(proc.stdout)
        if not ok:
            return _err("system_battery invalid JSON", stdout=data, stderr=_truncate(proc.stderr, 1000), exit_code=proc.returncode)
        return _ok(battery=data, has_battery=bool(data), exit_code=proc.returncode, source="powershell")

    def system_brightness_get(self, args: dict[str, Any]) -> dict[str, Any]:
        script = "Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness | Select-Object CurrentBrightness | ConvertTo-Json"
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return _err("system_brightness_get timeout", reason="wmi_unresponsive",
                        hint="WMI brightness only works on monitors with DDC/CI support.")
        ok, data = parse_ps_json(proc.stdout)
        if not ok:
            return _err("system_brightness_get invalid JSON",
                        stdout=data, stderr=_truncate(proc.stderr, 1000), exit_code=proc.returncode,
                        hint="Most desktop monitors don't expose WmiMonitorBrightness; this only works on laptops.")
        if data is None:
            return _ok(brightness=None, note="WmiMonitorBrightness returned null (desktop monitor or no DDC/CI).")
        return _ok(brightness=data, exit_code=proc.returncode)

    def system_brightness_set(self, args: dict[str, Any]) -> dict[str, Any]:
        level = max(0, min(100, int(args.get("level", 50))))
        script = f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return _err("system_brightness_set timeout", level=level, reason="wmi_unresponsive")
        if proc.returncode != 0:
            return _err(
                "brightness_set rejected by WMI",
                level=level, exit_code=proc.returncode,
                stderr=_truncate(proc.stderr.strip(), 1000),
                hint="WmiMonitorBrightness only works on laptops; desktop monitors need DDC/CI helper.",
            )
        return _ok(level=level, requested=level, verified=False,
                   note="brightness set request sent; verify by calling brightness_get.")

    def audio_get_volume(self, args: dict[str, Any]) -> dict[str, Any]:
        try:
            volume = self._audio_endpoint_volume()
            return _ok(level=int(volume.GetMasterVolumeLevelScalar() * 100), muted=bool(volume.GetMute()))
        except ImportError:
            return _err("pycaw/comtypes not installed", status="needs_dependency",
                        hint="pip install pycaw comtypes")
        except Exception as exc:
            return _err(f"audio_get_volume failed: {type(exc).__name__}: {exc}", status="failed")

    def audio_set_volume(self, args: dict[str, Any]) -> dict[str, Any]:
        level = max(0, min(100, int(args.get("level", 50))))
        try:
            volume = self._audio_endpoint_volume()
            volume.SetMasterVolumeLevelScalar(level / 100, None)
            # Verificar que SetMasterVolume realmente aplico. En endpoints
            # exclusive-mode el cambio puede ser ignorado silenciosamente.
            actual = int(volume.GetMasterVolumeLevelScalar() * 100)
            if abs(actual - level) > 2:
                return _err(
                    f"volume set to {level} but device reports {actual}",
                    status="failed", requested=level, actual=actual,
                )
            return _ok(level=actual, requested=level, verified=True)
        except ImportError:
            return _err("pycaw/comtypes not installed", status="needs_dependency",
                        hint="pip install pycaw comtypes")
        except Exception as exc:
            return _err(f"audio_set_volume failed: {type(exc).__name__}: {exc}", status="failed")

    def audio_mute(self, args: dict[str, Any]) -> dict[str, Any]:
        state = bool(args.get("state", True))
        try:
            volume = self._audio_endpoint_volume()
            volume.SetMute(int(state), None)
            # Verificar que SetMute aplico comparando con el state pedido.
            actual = bool(volume.GetMute())
            if actual != state:
                return _err(
                    f"mute requested {state} but device reports {actual}",
                    status="failed", requested=state, actual=actual,
                )
            return _ok(muted=actual, requested=state, verified=True)
        except ImportError:
            return _err("pycaw/comtypes not installed", status="needs_dependency",
                        hint="pip install pycaw comtypes")
        except Exception as exc:
            return _err(f"audio_mute failed: {type(exc).__name__}: {exc}", status="failed")

    def _audio_endpoint_volume(self) -> Any:
        # Returns an IAudioEndpointVolume COM pointer. Typed as Any because
        # pycaw/comtypes methods (GetMasterVolumeLevelScalar, GetMute, SetMute,
        # SetMasterVolumeLevelScalar) are dispatched dynamically through COM
        # and have no stubs that pyright can introspect.
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL  # type: ignore[import-not-found]
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore[import-not-found]

        # 2026-05-20: the agent runs tools on worker threads; pycaw's COM
        # objects require COM to be initialized ON THIS THREAD or GetSpeakers()
        # raises "[WinError -2147221008] CoInitialize has not been called".
        # This caused intermittent volume failures ("sube el volumen al 50"
        # FAILED while "baja el vol a 30" happened to work on an already-init
        # thread). CoInitialize is idempotent (returns S_FALSE if already
        # initialized), so calling it here every time is safe.
        try:
            from comtypes import CoInitialize  # type: ignore[import-not-found]
            CoInitialize()
        except Exception:
            pass

        device: Any = AudioUtilities.GetSpeakers()
        if device is None:
            raise RuntimeError("no audio endpoint device available")
        if hasattr(device, "EndpointVolume"):
            return device.EndpointVolume
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    def audio_devices(self, args: dict[str, Any]) -> dict[str, Any]:
        script = "Get-PnpDevice -Class AudioEndpoint | Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Depth 3"
        # timeout 15 -> 8s + try/except (antes una excepcion subia y mataba el turn).
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return _ok(devices=[], note="audio_devices timeout/error", source="powershell_timeout")
        raw = proc.stdout.strip()
        try:
            data = json.loads(raw) if raw else []
        except json.JSONDecodeError:
            return _err("audio_devices invalid JSON", stdout=_truncate(raw, 1000), stderr=_truncate(proc.stderr, 1000))
        if isinstance(data, dict):
            data = [data]
        return _ok(devices=data, exit_code=proc.returncode)

    def audio_set_default(self, args: dict[str, Any]) -> dict[str, Any]:
        # Esta accion no esta implementada nativa: Windows WASAPI policy no
        # expone API publica para cambiar default device sin helper externo
        # (SoundVolumeView, AudioDeviceCmdlets, NirCmd). En vez de devolver
        # _err vacio, marcamos status=needs_user para que el LLM lo dirija
        # a una accion alternativa (audio_device tool con backend distinto).
        return _err(
            "audio_set_default not implemented natively",
            status="needs_user",
            requested=args.get("name"),
            reason="Windows no expone API publica para cambiar default audio device.",
            alternatives=[
                "Use audio_device tool (action=set_default) which wraps an external helper.",
                "Install AudioDeviceCmdlets module and call audio_device.",
            ],
        )

    def audio_media_control(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="media_play_pause")
        vk_by_action = {
            "media_play_pause": 0xB3,
            "media_pause": 0xB3,
            "play_pause": 0xB3,
            "pause": 0xB3,
            "stop": 0xB2,
            "media_stop": 0xB2,
            "next": 0xB0,
            "previous": 0xB1,
        }
        vk = vk_by_action.get(action, 0xB3)
        script = f"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class MediaKey {{
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, int dwFlags, int dwExtraInfo);
}}
"@
[MediaKey]::keybd_event({vk},0,0,0)
Start-Sleep -Milliseconds 80
[MediaKey]::keybd_event({vk},0,2,0)
"""
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
        return _ok(
            action=action,
            virtual_key=vk,
            playback_verified=False,
            completion_status="sent_global_media_key",
            note="Sent a global Windows media key. This should pause/play active media in browsers and media apps, but playback state is not directly verified.",
            exit_code=proc.returncode,
            stderr=_truncate(proc.stderr.strip(), 1000),
        )

    def window_active(self, args: dict[str, Any]) -> dict[str, Any]:
        # Native win32gui (~1ms) en vez de PowerShell + Add-Type (~400ms cold).
        try:
            import win32gui  # type: ignore
            import win32process  # type: ignore
            try:
                import psutil
            except Exception:
                psutil = None  # type: ignore[assignment]

            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return _ok(active=None, note="no foreground window")
            title = win32gui.GetWindowText(hwnd) or ""
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                pid = 0
            proc_name = ""
            if pid and psutil is not None:
                try:
                    proc_name = psutil.Process(pid).name()
                except Exception:
                    pass
            return _ok(active={"hwnd": hwnd, "title": title, "pid": pid, "process": proc_name},
                       source="win32gui")
        except Exception:
            pass

        # Fallback PowerShell con timeout reducido + try/except (antes
        # un timeout subia al caller).
        script = r"""
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@
$h=[Win32]::GetForegroundWindow()
$sb=New-Object System.Text.StringBuilder 1024
[Win32]::GetWindowText($h,$sb,$sb.Capacity) | Out-Null
$pid32=0
[Win32]::GetWindowThreadProcessId($h,[ref]$pid32) | Out-Null
$p=Get-Process -Id $pid32 -ErrorAction SilentlyContinue
[PSCustomObject]@{ hwnd=$h.ToInt64(); title=$sb.ToString(); pid=$pid32; process=$p.ProcessName } | ConvertTo-Json
"""
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=6)
        except (OSError, subprocess.TimeoutExpired):
            return _err("window_active timeout", reason="powershell_timeout")
        ok, data = parse_ps_json(proc.stdout)
        if not ok:
            return _err("window_active invalid JSON", stdout=data, stderr=_truncate(proc.stderr, 1000), exit_code=proc.returncode)
        return _ok(active=data, exit_code=proc.returncode, source="powershell")

    def window_control(self, action: str, title_query: str) -> dict[str, Any]:
        if not title_query:
            return _err("missing window title/query")
        # Native win32gui + EnumWindows: ~10ms vs 400ms PowerShell. Y el
        # match es estricto (usa _match_query) lo que evita falsos positivos.
        try:
            import win32gui  # type: ignore
            import win32con  # type: ignore
            import win32process  # type: ignore
            try:
                import psutil
            except Exception:
                psutil = None  # type: ignore[assignment]

            # SW_* constants
            sw_action = {
                "focus":    None,
                "close":    None,  # usa PostMessage(WM_CLOSE)
                "minimize": win32con.SW_MINIMIZE,
                "maximize": win32con.SW_SHOWMAXIMIZED,
                "restore":  win32con.SW_RESTORE,
            }
            if action not in sw_action:
                return _err("unknown window action", action=action,
                            valid=list(sw_action.keys()))

            candidates: list[tuple[int, str, int, str]] = []  # (hwnd, title, pid, proc_name)

            # El TÍTULO de la ventana suele estar LOCALIZADO por el SO ("Sin
            # título: Bloc de notas" en Windows en español) mientras el usuario
            # pide en SU idioma ("close notepad", "fecha o bloco de notas"). El
            # match por título solo fallaba -> "window not found". Resolvemos el
            # query también a un NOMBRE DE PROCESO vía el AppResolver (que ya
            # traduce builtins localizados, p.ej. "bloco de notas"->notepad.exe)
            # y aceptamos la ventana si su proceso coincide. Así "close notepad"
            # cierra la ventana "Bloc de notas". No es hardcode de routing: es la
            # misma resolución de apps que usa app.open/app.close.
            proc_hints: set[str] = set()
            try:
                for m in self.apps.find(title_query, limit=3):
                    pn = (m.process_name or Path(m.launch).name or "").casefold()
                    if pn:
                        proc_hints.add(pn)
                        proc_hints.add(pn[:-4] if pn.endswith(".exe") else pn)
            except Exception:
                pass

            def _enum(hwnd: int, _: Any) -> bool:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                title = win32gui.GetWindowText(hwnd) or ""
                if not title.strip():
                    return True
                pid = 0
                name = ""
                title_hit = self._match_query(title_query, title)
                if not title_hit and not proc_hints:
                    return True
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if psutil is not None:
                        name = psutil.Process(pid).name()
                except Exception:
                    pass
                proc_hit = bool(name) and name.casefold() in proc_hints
                if title_hit or proc_hit:
                    candidates.append((hwnd, title, pid, name))
                return True

            win32gui.EnumWindows(_enum, None)
            if not candidates:
                return _ok(result={"ok": False, "error": "window not found", "query": title_query},
                           found=False, source="win32gui")

            # Si hay varias coincidencias, preferir la del proceso cuyo nombre
            # tambien matchea el query (mejor signal).
            chosen = next(
                (c for c in candidates if self._match_query(title_query, c[3])),
                candidates[0],
            )
            hwnd, title, pid, proc_name = chosen

            applied = False
            error: str | None = None
            try:
                if action == "focus":
                    # REGLA UNIVERSAL (2026-05-15 user request): si la ventana
                    # esta minimizada, restaurarla. Si tras restore queda muy
                    # chica (probablemente porque el user la habia dejado en
                    # tamaño reducido), maximizarla automaticamente para que
                    # comandos GUI subsecuentes (teclas, clicks) funcionen
                    # consistentemente en la ventana objetivo y no se pierdan
                    # detras de overlap parcial con otras apps.
                    #
                    # Sequence:
                    #   1. IsIconic check -> SW_RESTORE si esta minimizada.
                    #   2. SetForegroundWindow para traerla al frente.
                    #   3. Si el rect resultante es <800x600 (heurustico), tambien
                    #      SW_SHOWMAXIMIZED para garantizar visibilidad.
                    was_minimized = bool(win32gui.IsIconic(hwnd))
                    # Foco ROBUSTO (2026-05-23, informe C): truco ALT +
                    # AttachThreadInput + ShowWindow + verificación + UIA(UWP) +
                    # retry. El SetForegroundWindow directo viejo fallaba bajo el
                    # foreground-lock de Windows (WhatsApp/Spotify no se enfocaban).
                    try:
                        from .win_focus import focus_and_maximize
                        applied = focus_and_maximize(
                            hwnd, expected_title_substr=(title or None))
                    except Exception:
                        # Fallback al camino viejo si win_focus no está disponible.
                        if was_minimized:
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        applied = bool(win32gui.SetForegroundWindow(hwnd))
                        try:
                            l, t, r, b = win32gui.GetWindowRect(hwnd)
                            if (r - l) < 800 or (b - t) < 600:
                                win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
                                win32gui.SetForegroundWindow(hwnd)
                        except Exception:
                            pass
                elif action == "close":
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    # VERIFICAR que la ventana realmente se cerró. WM_CLOSE es un
                    # PEDIDO, no una garantía: si la app muestra un diálogo
                    # "¿guardar cambios?" o ignora el mensaje, la ventana
                    # sobrevive. Antes reportábamos applied=True sin chequear ->
                    # FALSO-PASS (el agente decía "cerré" y el proceso seguía
                    # vivo, el bug clase-Carter). Polleamos hasta ~1.5s a que el
                    # hwnd deje de ser ventana válida/visible. NO forzamos kill
                    # (taskkill sobre trabajo sin guardar sería destructivo,
                    # CLAUDE.md #6); si no cierra, lo reportamos honestamente.
                    applied = False
                    _close_deadline = time.time() + 1.5
                    while time.time() < _close_deadline:
                        time.sleep(0.15)
                        try:
                            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                                applied = True
                                break
                        except Exception:
                            applied = True  # hwnd inválido = cerró
                            break
                    if not applied:
                        error = ("window did not close (app may be showing a "
                                 "save/confirm dialog or ignored WM_CLOSE); not "
                                 "force-killed to avoid data loss")
                else:
                    win32gui.ShowWindow(hwnd, sw_action[action])
                    applied = True
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"

            return _ok(
                result={
                    "ok": applied and error is None, "action": action,
                    "title": title, "process": proc_name, "pid": pid, "hwnd": hwnd,
                    "error": error,
                    "candidates_count": len(candidates),
                },
                found=True, source="win32gui",
            )
        except Exception:
            pass

        # Fallback PowerShell (legacy path).
        env = os.environ.copy()
        env["GEMMA4_WINDOW_QUERY"] = title_query
        env["GEMMA4_WINDOW_ACTION"] = action
        script = r"""
$q=$env:GEMMA4_WINDOW_QUERY.ToLower()
$action=$env:GEMMA4_WINDOW_ACTION
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
}
"@
$p = Get-Process | Where-Object { $_.MainWindowTitle -and $_.MainWindowTitle.ToLower().Contains($q) } | Select-Object -First 1
if (-not $p) { [PSCustomObject]@{ ok=$false; error="window not found"; query=$q } | ConvertTo-Json; exit 0 }
$h=$p.MainWindowHandle
switch ($action) {
  "focus" { [Win32]::SetForegroundWindow($h) | Out-Null }
  "close" { [Win32]::PostMessage($h,0x0010,[IntPtr]::Zero,[IntPtr]::Zero) | Out-Null }
  "minimize" { [Win32]::ShowWindow($h,6) | Out-Null }
  "maximize" { [Win32]::ShowWindow($h,3) | Out-Null }
  "restore" { [Win32]::ShowWindow($h,9) | Out-Null }
}
[PSCustomObject]@{ ok=$true; action=$action; title=$p.MainWindowTitle; process=$p.ProcessName; pid=$p.Id; hwnd=$h.ToInt64() } | ConvertTo-Json
"""
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return _err("window_control timeout", reason="powershell_timeout")
        ok, data = parse_ps_json(proc.stdout)
        if not ok:
            data = {"ok": False, "error": _truncate(proc.stderr, 1000)}
        elif data is None:
            data = {"ok": False, "error": proc.stderr}
        return _ok(result=data, exit_code=proc.returncode, source="powershell")

    def window_move_resize(self, args: dict[str, Any]) -> dict[str, Any]:
        title_query = str(args.get("title") or args.get("query") or "").strip()
        if not title_query:
            return _err("missing window title/query")
        env = os.environ.copy()
        env["GEMMA4_WINDOW_QUERY"] = title_query
        env["GEMMA4_X"] = str(int(args.get("x", 0)))
        env["GEMMA4_Y"] = str(int(args.get("y", 0)))
        env["GEMMA4_W"] = str(int(args.get("width", 1000)))
        env["GEMMA4_H"] = str(int(args.get("height", 700)))
        script = r"""
$q=$env:GEMMA4_WINDOW_QUERY.ToLower()
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool repaint);
}
"@
$p = Get-Process | Where-Object { $_.MainWindowTitle -and $_.MainWindowTitle.ToLower().Contains($q) } | Select-Object -First 1
if (-not $p) { [PSCustomObject]@{ ok=$false; error="window not found"; query=$q } | ConvertTo-Json; exit 0 }
[Win32]::MoveWindow($p.MainWindowHandle,[int]$env:GEMMA4_X,[int]$env:GEMMA4_Y,[int]$env:GEMMA4_W,[int]$env:GEMMA4_H,$true) | Out-Null
[PSCustomObject]@{ ok=$true; title=$p.MainWindowTitle; process=$p.ProcessName; x=$env:GEMMA4_X; y=$env:GEMMA4_Y; width=$env:GEMMA4_W; height=$env:GEMMA4_H } | ConvertTo-Json
"""
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=10)
        ok, data = parse_ps_json(proc.stdout)
        if not ok:
            data = {"ok": False, "error": _truncate(proc.stderr, 1000)}
        elif data is None:
            data = {"ok": False, "error": proc.stderr}
        return _ok(result=data, exit_code=proc.returncode)

    def app_open(self, args: dict[str, Any]) -> dict[str, Any]:
        name = str(args.get("name", "")).strip()
        if not name:
            return _err("empty app name")
        matches = self.apps.find(name, refresh=bool(args.get("refresh", False)))
        if not matches:
            return _err("app not found", query=name, searched_sources=["PATH", "Start Menu", "StartApps", "Registry", "Steam", "Epic"])
        best = matches[0]
        preexisting = self.verify_app_opened({"name": name})
        open_result = self.apps.open(best)
        if not open_result.get("ok"):
            return _err(
                open_result.get("error") or "failed to open app",
                query=name,
                candidate=open_result.get("candidate"),
                status="failed",
            )
        resource = None
        if not preexisting.get("found"):
            resource = self.state.register_resource(
                "app",
                name,
                cleanup_tool="app",
                cleanup_args={"action": "close", "name": name},
                metadata={"resolved": best.as_dict()},
            ).get("resource")
        # Auto-verify con backoff exponencial corto en vez del sleep fijo de
        # 2.5s. La mayoria de las apps "normales" (Steam, Discord, Chrome)
        # muestran su ventana en 200-600ms; el sleep fijo desperdiciaba ~2s
        # cada vez. Hacemos 3 chequeos con timeouts crecientes (0.3, 0.6, 1.2s)
        # que cortan apenas se confirma el proceso/ventana. Total worst case
        # = ~2.1s (igual que antes) pero best case = ~0.3s. Para Steam-games
        # que tardan 10-30s, el caller debe llamar verify(action='app_opened')
        # explicito; no vale la pena bloquear el turn hasta 30s aca.
        import os as _os
        autoverify = (_os.environ.get("GEMMA4_APP_OPEN_AUTOVERIFY") or "").strip().casefold()
        verified = False
        verify_evidence: dict[str, Any] = {}
        if autoverify not in {"false", "0", "no", "off"}:
            # GEMMA4_APP_OPEN_AUTOVERIFY_WAIT_S sigue siendo el cap superior
            # total (suma de los backoffs). Default 2.1s = casi igual al
            # 2.5s anterior pero con corte temprano.
            try:
                cap_s = float(_os.environ.get("GEMMA4_APP_OPEN_AUTOVERIFY_WAIT_S") or "2.1")
            except ValueError:
                cap_s = 2.1
            cap_s = max(0.0, min(cap_s, 10.0))

            process_hint = best.process_name or ""
            elapsed_total = 0.0
            for step_s in (0.3, 0.6, 1.2):
                if elapsed_total >= cap_s:
                    break
                # Recortar el ultimo paso si excederia el cap
                step_s = min(step_s, cap_s - elapsed_total)
                time.sleep(step_s)
                elapsed_total += step_s

                post = self.verify_app_opened({"name": name})
                if post.get("found"):
                    verified = True
                    verify_evidence = {
                        "verify_app_opened_after_s": round(elapsed_total, 2),
                        "match": post.get("match"),
                    }
                    break
                if process_hint and process_hint.casefold() != name.casefold():
                    post2 = self.verify_app_opened({"name": process_hint})
                    if post2.get("found"):
                        verified = True
                        verify_evidence = {
                            "verify_app_opened_via_process": process_hint,
                            "verify_app_opened_after_s": round(elapsed_total, 2),
                            "match": post2.get("match"),
                        }
                        break
        return _ok(
            query=name,
            opened=best.as_dict(),
            alternatives=[m.as_dict() for m in matches[1:5]],
            preexisting=bool(preexisting.get("found")),
            resource=resource,
            status=("done" if verified else "attempted"),
            verified=verified,
            completion_status=("launch_verified" if verified else "launch_requested"),
            evidence={"resolved_target": best.as_dict(), **verify_evidence},
            note=(
                "Auto-verify confirmed a window or process matching the requested app."
                if verified
                else "Launch sent to Windows but no window matched within the auto-verify window. The app may still be loading (Steam/Epic games can take 10-30s); call verify(action='app_opened') again if needed."
            ),
        )

    def app_close(self, args: dict[str, Any]) -> dict[str, Any]:
        name = str(args.get("name", "")).strip()
        if not name:
            return _err("empty app name")
        matches = self.apps.find(name, limit=8)
        candidates = _candidate_close_exes(name, matches)

        # Fast-path: si NI siquiera hay candidatos exe (no encontramos la app
        # en path/registry/start/steam) Y no hay ventana por nombre, devolver
        # "not_running" en <1s. Evita 12s + N*20s de PowerShell+taskkill sobre
        # exes que no existen. Para esto necesitamos chequear procesos vivos
        # con un solo `tasklist` rapido (~200ms).
        running_set = _running_process_names()
        running_candidates = [exe for exe in candidates if exe.lower() in running_set]
        # Antes: substring match `_fold(name) in _fold(p)` producia falsos
        # positivos ("vs" -> matcheaba decenas). Ahora _match_query aplica
        # las mismas reglas que verify_app_opened: exact/substring>=4chars/
        # multi-token.
        name_in_running = any(self._match_query(name, p) for p in running_set)

        if not candidates and not name_in_running:
            return _ok(
                closed=False,
                not_running=True,
                query=name,
                candidate_exes=[],
                running_process_match=False,
                note=(
                    "No matching installed app and no running process named like "
                    f"'{name}' — nothing to close. Fast-path skip of taskkill."
                ),
                resolved_from=[m.as_dict() for m in matches[:5]],
            )

        if candidates and not running_candidates and not name_in_running:
            # Hay candidatos en disco pero ninguno corriendo. taskkill devolveria
            # exit_code=128 instantaneamente, pero por las dudas (puede haber un
            # exe renombrado) saltamos directo al fast-path tambien aca.
            return _ok(
                closed=False,
                not_running=True,
                query=name,
                candidate_exes=candidates,
                running_process_match=False,
                note=(
                    "Installed but no matching process is running. "
                    "Fast-path skip of taskkill."
                ),
                resolved_from=[m.as_dict() for m in matches[:5]],
            )

        # Hay al menos un candidato corriendo (o el query matchea algun proceso).
        # Vale la pena intentar window-close + taskkill.
        window_close = _close_windows_by_query(name)
        taskkill_results = []
        closed = int(window_close.get("count") or 0) > 0

        # Solo intentamos taskkill sobre exes que SABEMOS estan corriendo.
        # taskkill sobre un IM inexistente igual deberia ser rapido pero el
        # binario hace lookup en el snapshot y a veces se cuelga >5s.
        target_exes = running_candidates or candidates
        for exe in target_exes:
            proc = subprocess.run(
                ["taskkill", "/IM", exe, "/F"],
                capture_output=True, text=True,
                timeout=5,  # antes 20s; en practica taskkill termina en <1s
            )
            item = {
                "target": exe,
                "closed": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": _truncate(proc.stdout.strip(), 2000),
                "stderr": _truncate(proc.stderr.strip(), 1000),
            }
            taskkill_results.append(item)
            closed = closed or item["closed"]

        if not closed:
            return _err(
                "app/process not found or could not be closed",
                closed=False,
                query=name,
                candidate_exes=candidates,
                window_close=window_close,
                attempts=taskkill_results,
                resolved_from=[m.as_dict() for m in matches[:5]],
            )

        return _ok(
            closed=True,
            query=name,
            candidate_exes=candidates,
            window_close=window_close,
            attempts=taskkill_results,
            resolved_from=[m.as_dict() for m in matches[:5]],
        )

    def app_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", "")).strip()
        if not query:
            return _err("empty query")
        limit = int(args.get("limit", 10))
        matches = self.apps.find(query, limit=limit, refresh=bool(args.get("refresh", False)))
        return _ok(query=query, matches=[m.as_dict() for m in matches])

    def _backup_path_for(self, path: Path) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(path.resolve()))[-120:]
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.state.path.parent / "file_backups" / f"{stamp}_{safe}"

    def _checkpoint_existing_path(self, label: str, path: Path) -> dict[str, Any]:
        if not path.exists():
            return self.state.checkpoint(label, rollback=[{"tool": "filesystem", "args": {"action": "delete", "path": str(path), "recursive": True}}])
        backup = self._backup_path_for(path)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(path, backup, dirs_exist_ok=True)
        else:
            shutil.copy2(path, backup)
        rollback = [
            {"tool": "filesystem", "args": {"action": "delete", "path": str(path), "recursive": True}},
            {"tool": "filesystem", "args": {"action": "copy", "src": str(backup), "dst": str(path), "overwrite": True}},
        ]
        return self.state.checkpoint(label, rollback=rollback, metadata={"backup": str(backup), "path": str(path.resolve())})

    def filesystem_list(self, args: dict[str, Any]) -> dict[str, Any]:
        path = Path(str(args.get("path", ".")).strip() or ".").expanduser()
        limit = int(args.get("limit", 80))
        if not path.exists():
            return _err("path does not exist", path=str(path))
        if not path.is_dir():
            # Antes: explotaba con NotADirectoryError. Ahora devolvemos err
            # estructurado con hint para que el LLM cambie a filesystem_read.
            return _err(
                "path is not a directory", path=str(path),
                hint="use filesystem.read for files; filesystem.list is for directories",
            )
        items = []
        skipped: list[dict[str, str]] = []
        try:
            children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))
        except PermissionError as exc:
            return _err("permission denied listing directory", path=str(path), reason=str(exc), status="needs_user")
        except OSError as exc:
            return _err("failed to list directory", path=str(path), reason=str(exc))
        for child in children[:limit]:
            try:
                stat = child.stat()
                items.append({
                    "name": child.name,
                    "path": str(child.resolve()),
                    "type": "dir" if child.is_dir() else "file",
                    "size": stat.st_size if child.is_file() else None,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                })
            except (PermissionError, OSError) as exc:
                # Symlinks rotos, locks (Application Data, Recovery), permisos.
                skipped.append({"name": child.name, "reason": f"{type(exc).__name__}: {exc}"})
        truncated = len(children) > limit
        return _ok(
            path=str(path.resolve()), items=items,
            total=len(children), shown=len(items),
            truncated=truncated, skipped=skipped,
        )

    def filesystem_read(self, args: dict[str, Any]) -> dict[str, Any]:
        path = Path(str(args.get("path", "")).strip()).expanduser()
        limit = int(args.get("max_chars", 12000))
        if not path.is_file():
            return _err("file does not exist", path=str(path))
        try:
            size = path.stat().st_size
        except OSError as exc:
            return _err("cannot stat file", path=str(path), reason=str(exc))
        # Si el archivo es enorme NO lo cargues entero solo para truncar despues.
        # Leemos los primeros `limit * 4` bytes (~conservador para UTF-8) y luego
        # truncamos a chars. Para archivos chicos lee normalmente.
        max_bytes_for_read = max(limit * 4, 64 * 1024)
        try:
            with path.open("rb") as fh:
                raw = fh.read(max_bytes_for_read + 1)
        except (PermissionError, OSError) as exc:
            return _err("cannot read file", path=str(path), reason=str(exc), status="needs_user")
        partial = len(raw) > max_bytes_for_read
        if partial:
            raw = raw[:max_bytes_for_read]
        # Heuristica binario: si tiene NUL bytes en los primeros 512, es binario.
        if b"\x00" in raw[:512]:
            return _err(
                "file appears to be binary (NUL byte in head)",
                path=str(path), size_bytes=size,
                hint="for binary files use download.hash or filesystem.head_bytes (if available)",
            )
        try:
            content = raw.decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            return _err("decode failed", path=str(path), reason=str(exc))
        return _ok(
            path=str(path.resolve()),
            content=_truncate(content, limit),
            size_bytes=size,
            partial_read=partial,
            chars_returned=min(len(content), limit),
        )

    def filesystem_write(self, args: dict[str, Any]) -> dict[str, Any]:
        raw_path = str(args.get("path", "")).strip()
        if not raw_path:
            return _err("empty path")
        path = Path(raw_path).expanduser()
        content = str(args.get("content", ""))
        checkpoint = self._checkpoint_existing_path(f"filesystem write {path}", path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as exc:
            return _err("cannot create parent directory", path=str(path), reason=str(exc), status="needs_user")
        try:
            path.write_text(content, encoding="utf-8")
        except (PermissionError, OSError) as exc:
            return _err("write failed", path=str(path), reason=str(exc),
                        status="needs_user" if isinstance(exc, PermissionError) else "failed")
        # Verificar tamaño escrito (en sistemas con full disk write_text puede
        # haberse hecho parcialmente sin levantar IOError).
        try:
            actual_size = path.stat().st_size
        except OSError:
            actual_size = -1
        expected = len(content.encode("utf-8"))
        if actual_size != -1 and actual_size != expected:
            return _err(
                "write incomplete",
                path=str(path), expected_bytes=expected, actual_bytes=actual_size,
                status="failed", checkpoint=checkpoint.get("checkpoint"),
            )
        return _ok(
            path=str(path.resolve()), bytes=expected, verified=actual_size == expected,
            checkpoint=checkpoint.get("checkpoint"),
        )

    # Carpetas de usuario conocidas (es/en) -> ruta real bajo el home. El LLM y
    # el usuario dicen "Descargas"/"Downloads"/"Escritorio" sin ruta absoluta.
    _USER_FOLDER_ALIASES = {
        "downloads": "Downloads", "descargas": "Downloads",
        "desktop": "Desktop", "escritorio": "Desktop",
        "documents": "Documents", "documentos": "Documents",
        "pictures": "Pictures", "imagenes": "Pictures", "imágenes": "Pictures",
        "music": "Music", "musica": "Music", "música": "Music",
        "videos": "Videos", "vídeos": "Videos",
    }

    def _resolve_user_folder(self, raw: str) -> Path:
        """Resuelve una ruta. Si es un nombre de carpeta conocida (Downloads,
        Descargas, ...) la mapea a la carpeta real del home; si no, expanduser."""
        key = raw.strip().strip("/\\").casefold()
        alias = self._USER_FOLDER_ALIASES.get(key)
        if alias:
            return (Path.home() / alias)
        return Path(raw).expanduser()

    def filesystem_search(self, args: dict[str, Any]) -> dict[str, Any]:
        # BUG sesión #847: el LLM pasa `path` (intuitivo, está en el schema) pero
        # esto solo leía `root` -> ignoraba el path y buscaba en "." (el dir del
        # proyecto), por eso "abre el Word de Descargas" no encontraba nada real.
        # Fix: aceptar path/dir como alias de root, y resolver nombres de carpetas
        # conocidas (Downloads/Descargas/Escritorio/Documentos...) al home del user.
        raw_root = str(args.get("root") or args.get("path") or args.get("dir") or ".").strip() or "."
        root = self._resolve_user_folder(raw_root)
        pattern = str(args.get("pattern", "*")).strip() or "*"
        limit = int(args.get("limit", 50))
        if not root.exists():
            return _err("root does not exist", root=str(root))
        if not root.is_dir():
            return _err("root is not a directory", root=str(root))
        # Budget: rglob sobre C:\ puede caminar millones de archivos. Cap a
        # 10s wall-clock o 50K archivos visitados.
        try:
            budget_s = float(args.get("budget_s", 10.0))
        except (TypeError, ValueError):
            budget_s = 10.0
        budget_s = max(1.0, min(budget_s, 60.0))
        deadline = time.monotonic() + budget_s
        max_visited = int(args.get("max_visited", 50000))
        matches = []
        skipped_dirs = 0
        visited = 0
        try:
            it = root.rglob(pattern)
        except OSError as exc:
            return _err("rglob failed", root=str(root), pattern=pattern, reason=str(exc))
        for path in it:
            visited += 1
            if visited > max_visited:
                break
            if time.monotonic() > deadline:
                break
            try:
                is_dir = path.is_dir()
            except (PermissionError, OSError):
                skipped_dirs += 1
                continue
            matches.append({"path": str(path), "type": "dir" if is_dir else "file"})
            if len(matches) >= limit:
                break
        truncated = len(matches) >= limit or visited > max_visited or time.monotonic() > deadline
        return _ok(
            root=str(root.resolve()), pattern=pattern,
            matches=matches, count=len(matches),
            truncated=truncated, visited=visited, skipped_permission=skipped_dirs,
        )

    def filesystem_delete(self, args: dict[str, Any]) -> dict[str, Any]:
        raw_path = str(args.get("path", "")).strip()
        if not raw_path:
            return _err("empty path")
        path = Path(raw_path).expanduser()
        recursive = bool(args.get("recursive", False))
        if not path.exists():
            return _err("path does not exist", path=str(path))
        resolved = path.resolve()
        # CC-101: gate duro para filesystem.delete.
        gate = self._hard_gate(
            tool_name="filesystem",
            action="delete",
            args=args,
            reason=f"Deleting {resolved} (recursive={recursive})",
            risk="high",
            routine_context=bool(args.get("routine_context")),
            confirmed_at_create=bool(args.get("confirmed_at_create")),
        )
        if gate is not None:
            return gate
        checkpoint = self._checkpoint_existing_path(f"filesystem delete {resolved}", path)
        if path.is_dir():
            if not recursive:
                path.rmdir()
            else:
                shutil.rmtree(path)
        else:
            path.unlink()
        return _ok(deleted=str(resolved), recursive=recursive, checkpoint=checkpoint.get("checkpoint"))

    def filesystem_copy(self, args: dict[str, Any]) -> dict[str, Any]:
        src = Path(str(args.get("src") or args.get("source") or "")).expanduser()
        dst = Path(str(args.get("dst") or args.get("dest") or args.get("destination") or "")).expanduser()
        if not str(src) or not str(dst):
            return _err("missing src/dst")
        overwrite = bool(args.get("overwrite", False))
        # T2-filesystem-copy-overwrite-semantics-003: honra overwrite=false en archivos.
        if not src.is_dir() and dst.exists() and not overwrite:
            return _err(
                "destination exists; pass overwrite=true to replace",
                src=str(src), dst=str(dst), status="needs_user",
            )
        checkpoint = self._checkpoint_existing_path(f"filesystem copy to {dst}", dst)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=overwrite)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return _ok(src=str(src.resolve()), dst=str(dst.resolve()), checkpoint=checkpoint.get("checkpoint"))

    def filesystem_move(self, args: dict[str, Any]) -> dict[str, Any]:
        src = Path(str(args.get("src") or args.get("source") or "")).expanduser()
        dst = Path(str(args.get("dst") or args.get("dest") or args.get("destination") or "")).expanduser()
        if not str(src) or not str(dst):
            return _err("missing src/dst")
        dst.parent.mkdir(parents=True, exist_ok=True)
        checkpoint = self.state.checkpoint(
            f"filesystem move {src} to {dst}",
            rollback=[{"tool": "filesystem", "args": {"action": "move", "src": str(dst), "dst": str(src)}}],
        )
        moved = shutil.move(str(src), str(dst))
        return _ok(src=str(src), dst=str(Path(moved).resolve()), checkpoint=checkpoint.get("checkpoint"))

    def filesystem_rename(self, args: dict[str, Any]) -> dict[str, Any]:
        src = Path(str(args.get("src") or args.get("path") or "")).expanduser()
        new_name = str(args.get("new_name") or args.get("name") or "").strip()
        dst_raw = args.get("dst")
        if dst_raw:
            dst = Path(str(dst_raw)).expanduser()
        elif src and new_name:
            dst = src.with_name(new_name)
        else:
            return _err("missing src/new_name")
        checkpoint = self.state.checkpoint(
            f"filesystem rename {src} to {dst}",
            rollback=[{"tool": "filesystem", "args": {"action": "rename", "src": str(dst), "dst": str(src)}}],
        )
        src.rename(dst)
        return _ok(src=str(src.resolve()), dst=str(dst.resolve()), checkpoint=checkpoint.get("checkpoint"))

    def filesystem_mkdir(self, args: dict[str, Any]) -> dict[str, Any]:
        path = Path(str(args.get("path", "")).strip()).expanduser()
        if not str(path):
            return _err("empty path")
        checkpoint = self._checkpoint_existing_path(f"filesystem mkdir {path}", path)
        path.mkdir(parents=True, exist_ok=True)
        return _ok(path=str(path.resolve()), checkpoint=checkpoint.get("checkpoint"))

    def filesystem_diff(self, args: dict[str, Any]) -> dict[str, Any]:
        left = Path(str(args.get("left") or args.get("a") or "")).expanduser()
        right = Path(str(args.get("right") or args.get("b") or "")).expanduser()
        if not left.is_file() or not right.is_file():
            return _err("left/right must be existing files", left=str(left), right=str(right))
        # T2-filesystem-diff-no-size-limit-004: cap a 50 MB combinados.
        max_bytes = int(args.get("max_bytes", 50 * 1024 * 1024))
        total = left.stat().st_size + right.stat().st_size
        if total > max_bytes:
            return _err(
                f"files too large for in-memory diff ({total} bytes > {max_bytes}); use developer.git_diff or terminal(diff)",
                left=str(left), right=str(right), total_bytes=total, max_bytes=max_bytes,
                status="needs_user",
            )
        a = left.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        b = right.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(a, b, fromfile=str(left), tofile=str(right), n=3))
        return _ok(diff=_truncate(diff, int(args.get("max_chars", 12000))))

    def filesystem_archive(self, args: dict[str, Any]) -> dict[str, Any]:
        src = Path(str(args.get("src") or args.get("path") or "")).expanduser()
        dst = Path(str(args.get("dst") or args.get("archive") or "")).expanduser()
        if not src.exists() or not str(dst):
            return _err("missing src/dst", src=str(src), dst=str(dst))
        # T2-filesystem-archive-no-mitigation-005: caps de entries y bytes.
        max_files = int(args.get("max_files", 50_000))
        max_bytes = int(args.get("max_bytes", 5 * 1024 * 1024 * 1024))
        if src.is_dir():
            file_count = 0
            byte_count = 0
            for f in src.rglob("*"):
                if f.is_file():
                    file_count += 1
                    if file_count > max_files:
                        return _err(
                            f"archive exceeds max_files cap ({max_files}); refine src or pass higher max_files",
                            src=str(src), max_files=max_files, status="needs_user",
                        )
                    try:
                        byte_count += f.stat().st_size
                    except OSError:
                        pass
                    if byte_count > max_bytes:
                        return _err(
                            f"archive exceeds max_bytes cap ({max_bytes} bytes)",
                            src=str(src), max_bytes=max_bytes, status="needs_user",
                        )
        checkpoint = self._checkpoint_existing_path(f"filesystem archive {dst}", dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
            if src.is_dir():
                for file in src.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(src.parent))
            else:
                zf.write(src, src.name)
        return _ok(src=str(src.resolve()), archive=str(dst.resolve()), checkpoint=checkpoint.get("checkpoint"))

    def filesystem_unarchive(self, args: dict[str, Any]) -> dict[str, Any]:
        archive = Path(str(args.get("archive") or args.get("src") or "")).expanduser()
        dst = Path(str(args.get("dst") or args.get("destination") or ".")).expanduser()
        if not archive.is_file():
            return _err("archive not found", archive=str(archive))
        checkpoint = self._checkpoint_existing_path(f"filesystem unarchive {dst}", dst)
        dst.mkdir(parents=True, exist_ok=True)
        shutil.unpack_archive(str(archive), str(dst))
        return _ok(archive=str(archive.resolve()), dst=str(dst.resolve()), checkpoint=checkpoint.get("checkpoint"))

    def filesystem_open(self, args: dict[str, Any]) -> dict[str, Any]:
        path = Path(str(args.get("path", "")).strip()).expanduser()
        if not path.exists():
            return _err("path does not exist", path=str(path))
        os.startfile(str(path.resolve()))  # type: ignore[attr-defined]
        return _ok(path=str(path.resolve()))

    def web_open_url(self, args: dict[str, Any]) -> dict[str, Any]:
        url = str(args.get("url", "")).strip()
        if not url:
            return _err("empty url", status="needs_user")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        # VALIDACION: parsear y verificar que tiene host. Sin esto, urls
        # como "https:// " o "https://hola mundo" pasan a webbrowser.open
        # que las ejecuta como query del default browser.
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.hostname:
            return _err(
                "url has no host component",
                url=url, status="needs_user",
                hint="pass a full URL with a hostname, e.g. https://example.com",
            )
        try:
            opened = webbrowser.open(url)
        except Exception as exc:  # noqa: BLE001
            return _err(
                f"webbrowser.open failed: {type(exc).__name__}: {exc}",
                url=url, status="failed",
            )
        resource = self.state.register_resource("browser_url", url, cleanup_tool=None, cleanup_args={}, metadata={"url": url, "opened": opened})
        return _ok(
            url=url,
            opened=opened,
            resource=resource.get("resource"),
            status="attempted",
            verified=False,
            content_verified=False,
            completion_status="open_url_requested",
            evidence={"url": url, "opened": opened},
        )

    def web_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "").strip()
        if not query:
            return _err("missing query")
        limit = max(1, min(10, int(args.get("limit", 6))))
        provider, results = _web_search_provider(query, limit=limit)
        return _ok(
            query=query,
            engine=provider,
            results=results,
            count=len(results),
            status="done" if results else "needs_verification",
            verified=bool(results),
            content_verified=bool(results),
            completion_status="search_results_extracted" if results else "no_search_results_extracted",
            evidence={"query": query, "count": len(results)},
        )

    def web_read(self, args: dict[str, Any]) -> dict[str, Any]:
        url = str(args.get("url") or "").strip()
        if not url:
            return _err("missing url", status="needs_user")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        limit = max(1000, min(40000, int(args.get("max_chars", 12000))))
        timeout = max(1, min(int(args.get("timeout_sec", 12)), 60))
        # try/except: _http_get_text puede tirar URLError (DNS/connection/SSRF
        # block), HTTPError (4xx/5xx), socket.timeout, ssl errors, etc.
        try:
            fetched = _http_get_text(url, timeout=timeout)
        except urllib.error.HTTPError as exc:
            return _err(
                f"HTTP {exc.code}: {exc.reason}",
                url=url, status_code=exc.code,
                status="failed" if exc.code >= 500 else "needs_user",
            )
        except urllib.error.URLError as exc:
            reason = str(exc.reason if hasattr(exc, "reason") else exc)
            return _err(
                f"URL error: {reason}",
                url=url, status="failed",
                hint="check connectivity, DNS, or that the host is publicly reachable",
            )
        except Exception as exc:  # noqa: BLE001
            return _err(
                f"web_read failed: {type(exc).__name__}: {exc}",
                url=url, status="failed",
            )
        text = fetched["text"]
        readable = _html_to_text(text, limit=limit)
        title = _extract_title(text)
        return _ok(
            url=fetched["url"],
            requested_url=url,
            title=title,
            content_type=fetched["content_type"],
            status_code=fetched["status_code"],
            text=readable,
            chars=len(readable),
            status="done",
            verified=True,
            content_verified=True,
            completion_status="page_content_extracted",
            evidence={"url": fetched["url"], "title": title, "chars": len(readable)},
        )

    def web_research(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "").strip()
        if not query:
            return _err("missing query")
        search_limit = max(2, min(10, int(args.get("search_limit", args.get("limit", 6)))))
        read_limit = max(1, min(5, int(args.get("read_limit", 3))))
        per_page_chars = max(1000, min(12000, int(args.get("per_page_chars", 4500))))
        search = self.web_search({"query": query, "limit": search_limit})
        results = search.get("results", [])
        sources = []
        failures = []
        for item in results[:read_limit]:
            url = str(item.get("url") or "")
            try:
                page = self.web_read({"url": url, "max_chars": per_page_chars})
                sources.append({
                    "title": page.get("title") or item.get("title"),
                    "url": page.get("url") or url,
                    "search_snippet": item.get("snippet"),
                    "excerpt": page.get("text"),
                    "content_type": page.get("content_type"),
                    "status_code": page.get("status_code"),
                })
            except Exception as exc:
                failures.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
        return _ok(
            query=query,
            search_results=results,
            sources=sources,
            source_count=len(sources),
            failures=failures,
            status="done" if sources else "needs_verification",
            verified=bool(sources),
            content_verified=bool(sources),
            completion_status="research_sources_read" if sources else "research_search_only",
            evidence={"query": query, "source_count": len(sources)},
            note="Use the returned source excerpts to answer. Mention uncertainty when source_count is low or failures exist.",
        )

    def _hard_gate(
        self,
        *,
        tool_name: str,
        action: str,
        args: dict[str, Any],
        reason: str,
        risk: str = "high",
        routine_context: bool = False,
        confirmed_at_create: bool = False,
    ) -> dict[str, Any] | None:
        """CC-101: confirmation gate independent of ``safety_enabled``.

        Thin wrapper around :func:`gemma4_agent._shared.hard_gate` — the
        body was unified with ``domain_tools._hard_gate`` in Sprint 4
        (audit §2.2). The wrapper still exists so callers can keep
        invoking ``self._hard_gate(...)`` without knowing where state
        comes from.
        """
        from ._shared import hard_gate
        return hard_gate(
            self.state,
            tool=tool_name,
            action=action,
            args=args,
            reason=reason,
            risk=risk,
            routine_context=routine_context,
            confirmed_at_create=confirmed_at_create,
        )

    def terminal_run(self, args: dict[str, Any]) -> dict[str, Any]:
        command = str(args.get("command", "")).strip()
        cmd_args = args.get("args", [])
        cwd = args.get("cwd") or None
        timeout = int(args.get("timeout_sec", 60))
        shell = bool(args.get("shell", False))  # CC-101 / T2-terminal-shell-true-default-006
        if not command:
            return _err("empty command")
        if not isinstance(cmd_args, list):
            cmd_args = [str(cmd_args)]
        # T2-terminal-no-cwd-validation-007: validar cwd si se pasó.
        if cwd:
            cwd_path = Path(str(cwd)).expanduser()
            if not cwd_path.is_dir():
                return _err("cwd does not exist", cwd=str(cwd), status="needs_user")
            cwd = str(cwd_path)
        # CC-101: gate duro para terminal_run cuando lo invoca el LLM.
        # Llamadas internas con propósito conocido pasan `_internal_safe=True`
        # (read-only/listing); ese flag es invisible al schema.
        if not bool(args.get("_internal_safe")):
            gate = self._hard_gate(
                tool_name="terminal",
                action="run",
                args=args,
                reason=f"Run command via terminal: {command} {cmd_args}",
                risk="high",
                routine_context=bool(args.get("routine_context")),
                confirmed_at_create=bool(args.get("confirmed_at_create")),
            )
            if gate is not None:
                return gate
        argv = [command] + [str(x) for x in cmd_args]
        run_arg: str | list[str] = subprocess.list2cmdline(argv) if shell else argv
        # Cap timeout para evitar que el LLM se autobloquee con timeout=3600.
        timeout = max(1, min(timeout, 600))
        started = time.monotonic()
        # try/except: antes TimeoutExpired propagaba y mataba el turn entero.
        # Tambien FileNotFoundError (command no existe) y OSError ahora se
        # convierten en _err estructurado.
        try:
            proc = subprocess.run(
                run_arg, cwd=cwd, shell=shell,
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return _err(
                f"command timed out after {timeout}s",
                command=run_arg, cwd=cwd, timeout_sec=timeout,
                elapsed_ms=elapsed_ms,
                stdout=_truncate((exc.stdout or "").strip() if exc.stdout else "", 1000),
                stderr=_truncate((exc.stderr or "").strip() if exc.stderr else "", 1000),
                status="timeout",
            )
        except FileNotFoundError:
            return _err(
                f"command not found: {command!r}",
                command=command, cwd=cwd,
                status="needs_user",
                hint="check spelling or pass full path; on Windows you may need to include .exe",
            )
        except OSError as exc:
            return _err(
                f"command failed to spawn: {type(exc).__name__}: {exc}",
                command=run_arg, cwd=cwd, status="failed",
            )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        # T2-terminal-stdout-truncate-stderr-008: caps configurables.
        max_stdout = int(args.get("max_stdout_chars", 6000))
        max_stderr = int(args.get("max_stderr_chars", 3000))
        stdout_full = proc.stdout.strip()
        stderr_full = proc.stderr.strip()
        # Si trunca, persistimos a logfile dentro de captures_dir para forensics.
        log_path: str | None = None
        if len(stdout_full) > max_stdout or len(stderr_full) > max_stderr:
            log_file = self.captures_dir / f"terminal_{int(started)}_{proc.returncode}.log"
            try:
                log_file.write_text(
                    f"# command: {run_arg}\n# exit: {proc.returncode}\n# elapsed_ms: {elapsed_ms}\n\n"
                    f"## STDOUT\n{stdout_full}\n\n## STDERR\n{stderr_full}\n",
                    encoding="utf-8",
                )
                log_path = str(log_file)
            except OSError:
                pass
        return _ok(
            command=run_arg,
            cwd=str(Path(cwd).resolve()) if cwd else str(Path.cwd()),
            exit_code=proc.returncode,
            elapsed_ms=elapsed_ms,
            stdout=_truncate(stdout_full, max_stdout),
            stderr=_truncate(stderr_full, max_stderr),
            log_path=log_path,
            success=proc.returncode == 0,
        )

    def clipboard_read(self, args: dict[str, Any]) -> dict[str, Any]:
        max_chars = int(args.get("max_chars", 4000))
        # Tk built-in: ~30ms vs PowerShell Get-Clipboard ~400-800ms.
        try:
            import tkinter
            root = tkinter.Tk()
            root.withdraw()
            try:
                content = root.clipboard_get()
            except tkinter.TclError:
                content = ""
            root.destroy()
            return _ok(content=_truncate(content, max_chars), source="tkinter")
        except Exception:
            pass
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"], capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            return _ok(content="", source="powershell_timeout")
        return _ok(content=_truncate(proc.stdout, max_chars), exit_code=proc.returncode, source="powershell")

    def clipboard_write(self, args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("content", ""))
        # Tk built-in: instant (~10ms). PowerShell paga ~400ms cold-start.
        try:
            import tkinter
            root = tkinter.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()  # asegurar que el sistema vea el contenido
            root.destroy()
            return _ok(wrote_chars=len(text), source="tkinter")
        except Exception:
            pass
        script = "$txt = [Console]::In.ReadToEnd(); Set-Clipboard -Value $txt"
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], input=text, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            return _err("clipboard_write timeout", source="powershell_timeout")
        return _ok(wrote_chars=len(text), exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 1000), source="powershell")

    def _uia_run(self, args: dict[str, Any], action: str) -> dict[str, Any]:
        env = os.environ.copy()
        env["GEMMA4_UIA_ACTION"] = action
        env["GEMMA4_UIA_QUERY"] = str(args.get("query") or args.get("text") or args.get("target") or "")
        env["GEMMA4_UIA_WINDOW"] = str(args.get("window") or args.get("title") or "")
        env["GEMMA4_UIA_VALUE"] = str(args.get("value") or args.get("text_value") or "")
        env["GEMMA4_UIA_LIMIT"] = str(max(1, min(200, int(args.get("limit", 60)))))
        script = r"""
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class GemmaMouse {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(int flags, int dx, int dy, int data, int extra);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
}
"@

function ElemObj($e) {
  if ($null -eq $e) { return $null }
  $r = $e.Current.BoundingRectangle
  $click = $null
  try {
    $p = $e.GetClickablePoint()
    $click = [PSCustomObject]@{ x=[int]$p.X; y=[int]$p.Y }
  } catch {}
  [PSCustomObject]@{
    name=$e.Current.Name
    control_type=($e.Current.ControlType.ProgrammaticName -replace '^ControlType\.','')
    automation_id=$e.Current.AutomationId
    class_name=$e.Current.ClassName
    framework_id=$e.Current.FrameworkId
    enabled=$e.Current.IsEnabled
    offscreen=$e.Current.IsOffscreen
    bounds=[PSCustomObject]@{
      x=[int]$r.X; y=[int]$r.Y; width=[int]$r.Width; height=[int]$r.Height
    }
    clickable_point=$click
  }
}

function Matches($e, $q) {
  if ([string]::IsNullOrWhiteSpace($q)) { return $true }
  $needle = $q.ToLowerInvariant()
  $name = $e.Current.Name; if ($null -eq $name) { $name = "" }
  $nameL = $name.ToLowerInvariant()
  $hay = @(
    $e.Current.Name,
    $e.Current.AutomationId,
    $e.Current.ClassName,
    $e.Current.ControlType.ProgrammaticName
  ) -join " "
  $hayL = $hay.ToLowerInvariant()
  if ($hayL.Contains($needle)) { return $true }
  # Token-aware: el usuario suele decir "botón tres"/"button three" pero el Name
  # del control es solo "Tres". Matchear si un TOKEN significativo del query
  # (>=3 chars, sin palabras genéricas de UI multi-idioma) coincide con el Name,
  # o si el Name está contenido en el query. No es hardcode por-app: son
  # stop-words de UI universales, el matching sigue siendo por el Name real.
  $stop = @("boton","botón","button","bouton","schaltflache","schaltfläche","pulsante","botao","botão","el","la","the","le","les","der","die","das","il","en","in","de","del","of")
  if ($nameL.Length -ge 2 -and $needle.Contains($nameL)) { return $true }
  foreach ($tok in ($needle -split '\s+')) {
    if ($tok.Length -lt 3) { continue }
    if ($stop -contains $tok) { continue }
    if ($nameL -eq $tok -or $nameL.Contains($tok) -or $tok.Contains($nameL)) { return $true }
  }
  return $false
}

function RootElement($windowQuery) {
  if (-not [string]::IsNullOrWhiteSpace($windowQuery)) {
    $q = $windowQuery.ToLowerInvariant()
    $p = Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -and $_.MainWindowTitle.ToLowerInvariant().Contains($q) } | Select-Object -First 1
    if ($p) { return [System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle) }
  }
  $h = [GemmaMouse]::GetForegroundWindow()
  if ($h -ne [IntPtr]::Zero) {
    return [System.Windows.Automation.AutomationElement]::FromHandle($h)
  }
  return [System.Windows.Automation.AutomationElement]::RootElement
}

$action = $env:GEMMA4_UIA_ACTION
$query = $env:GEMMA4_UIA_QUERY
$window = $env:GEMMA4_UIA_WINDOW
$value = $env:GEMMA4_UIA_VALUE
$limit = [int]$env:GEMMA4_UIA_LIMIT
$root = RootElement $window
if ($null -eq $root) {
  [PSCustomObject]@{ ok=$false; error="uia root not found"; window=$window } | ConvertTo-Json -Depth 8
  exit 0
}

$all = @()
try {
  $all = @($root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition))
} catch {
  try {
    $all = @($root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition))
  } catch {
    [PSCustomObject]@{ ok=$false; action=$action; error=("uia traversal failed: " + $_.Exception.Message); window=$window; root=(ElemObj $root) } | ConvertTo-Json -Depth 8
    exit 0
  }
}
$matches = @()
foreach ($e in $all) {
  if (Matches $e $query) {
    $matches += $e
    if ($matches.Count -ge $limit) { break }
  }
}

# FALLBACK ALL-WINDOWS: si el root (foreground o por título) no dio matches y
# NO se pidió una ventana específica, el control puede estar en OTRA ventana que
# no tiene el foco (en el eval, la Calculadora se abre pero el foco queda en
# otra app entre el reset y el click -> "no encontré el botón"). Reescaneamos
# las ventanas top-level visibles y juntamos matches. General: clickear un botón
# de una app que no está al frente. Acotado por $limit.
if ($matches.Count -lt 1 -and [string]::IsNullOrWhiteSpace($window) -and $action -ne "tree") {
  try {
    $desktop = [System.Windows.Automation.AutomationElement]::RootElement
    $tops = @($desktop.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition))
    foreach ($top in $tops) {
      if ($matches.Count -ge $limit) { break }
      try {
        $sub = @($top.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition))
        foreach ($e in $sub) {
          if (Matches $e $query) {
            $matches += $e
            if ($matches.Count -ge $limit) { break }
          }
        }
      } catch {}
    }
    if ($matches.Count -gt 0) { $all = $matches }
  } catch {}
}

if ($action -eq "tree") {
  $items = @()
  foreach ($e in $all) {
    $o = ElemObj $e
    if ($o.name -or $o.automation_id -or $o.control_type -eq "Edit" -or $o.control_type -eq "Button") {
      $items += $o
      if ($items.Count -ge $limit) { break }
    }
  }
  [PSCustomObject]@{ ok=$true; action=$action; window=$window; root=(ElemObj $root); elements=$items; count=$items.Count } | ConvertTo-Json -Depth 8
  exit 0
}

if ($action -eq "find") {
  [PSCustomObject]@{ ok=$true; action=$action; query=$query; window=$window; matches=($matches | ForEach-Object { ElemObj $_ }); count=$matches.Count } | ConvertTo-Json -Depth 8
  exit 0
}

if ($matches.Count -lt 1) {
  [PSCustomObject]@{ ok=$false; action=$action; error="uia element not found"; query=$query; window=$window } | ConvertTo-Json -Depth 8
  exit 0
}

$el = $matches[0]

# Para CLICK: el 1er match laxo puede NO ser el control correcto (query "7"
# matchea cualquier elemento que CONTENGA "7" en Name/AutomationId/ClassName/
# ControlType). Reordenar para clickear el control MÁS clickeable: priorizar
# (1) tipos botón, (2) que soporten InvokePattern, (3) Name que coincide exacto
# o contiene el query, (4) habilitado y en pantalla. Esto arregla el click ciego
# en apps UIA-rico (Calculadora: "7" daba un match equivocado que reportaba ok
# pero no apretaba el dígito). Estable cross-locale (ControlType es inglés).
if ($action -eq "click" -and $matches.Count -gt 1) {
  $btnTypes = @("Button","SplitButton","MenuItem","TabItem","ListItem","Hyperlink","CheckBox","RadioButton")
  $q = $query.ToLowerInvariant()
  $best = $null; $bestScore = [double]::PositiveInfinity
  foreach ($m in $matches) {
    $ct = ($m.Current.ControlType.ProgrammaticName -replace '^ControlType\.','')
    $nm = ($m.Current.Name)
    if ($null -eq $nm) { $nm = "" }
    $nml = $nm.ToLowerInvariant()
    $ctRank = $btnTypes.IndexOf($ct); if ($ctRank -lt 0) { $ctRank = 99 }
    $inv = $null
    $hasInvoke = $m.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$inv)
    $exact = if ($nml -eq $q) { 0 } else { 1 }
    $nameHas = if ($nml.Contains($q)) { 0 } else { 1 }
    $enabled = if ($m.Current.IsEnabled) { 0 } else { 1 }
    $offs = if ($m.Current.IsOffscreen) { 1 } else { 0 }
    # score lexicográfico aplanado a un double (pesos decrecientes)
    $score = $offs*100000 + $enabled*10000 + (&{ if($hasInvoke){0}else{1} })*1000 + $ctRank*10 + $exact*4 + $nameHas*2
    if ($score -lt $bestScore) { $bestScore = $score; $best = $m }
  }
  if ($best -ne $null) { $el = $best }
}

if ($action -eq "focus") {
  $el.SetFocus()
  [PSCustomObject]@{ ok=$true; action=$action; query=$query; element=(ElemObj $el); method="uia_set_focus" } | ConvertTo-Json -Depth 8
  exit 0
}

if ($action -eq "click") {
  $pattern = $null
  if ($el.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
    $pattern.Invoke()
    [PSCustomObject]@{ ok=$true; action=$action; query=$query; element=(ElemObj $el); method="invoke_pattern" } | ConvertTo-Json -Depth 8
    exit 0
  }
  try {
    $p = $el.GetClickablePoint()
    [GemmaMouse]::SetCursorPos([int]$p.X, [int]$p.Y) | Out-Null
    [GemmaMouse]::mouse_event(0x0002,0,0,0,0)
    [GemmaMouse]::mouse_event(0x0004,0,0,0,0)
    [PSCustomObject]@{ ok=$true; action=$action; query=$query; element=(ElemObj $el); method="clickable_point" } | ConvertTo-Json -Depth 8
    exit 0
  } catch {
    [PSCustomObject]@{ ok=$false; action=$action; error=$_.Exception.Message; element=(ElemObj $el) } | ConvertTo-Json -Depth 8
    exit 0
  }
}

if ($action -eq "set_value") {
  $pattern = $null
  if ($el.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
    $pattern.SetValue($value)
    [PSCustomObject]@{ ok=$true; action=$action; query=$query; value=$value; element=(ElemObj $el); method="value_pattern" } | ConvertTo-Json -Depth 8
    exit 0
  }
  $el.SetFocus()
  Add-Type -AssemblyName System.Windows.Forms
  [System.Windows.Forms.SendKeys]::SendWait($value)
  [PSCustomObject]@{ ok=$true; action=$action; query=$query; value=$value; element=(ElemObj $el); method="focus_sendkeys" } | ConvertTo-Json -Depth 8
  exit 0
}

[PSCustomObject]@{ ok=$false; action=$action; error="unknown uia action" } | ConvertTo-Json -Depth 8
"""
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=int(args.get("timeout_sec", 20)))
        raw = proc.stdout.strip()
        if not raw:
            return _err("uia command produced no output", exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 2000))
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return _err("uia returned invalid json", stdout=_truncate(raw, 2000), stderr=_truncate(proc.stderr.strip(), 2000))
        if not isinstance(data, dict):
            data = {"ok": True, "data": data}
        data.setdefault("exit_code", proc.returncode)
        if proc.stderr.strip():
            data.setdefault("stderr", _truncate(proc.stderr.strip(), 1000))
        if data.get("ok"):
            data.setdefault("status", "done")
            data.setdefault("verified", True)
            data.setdefault("completion_status", "uia_action_completed")
        return data

    def uia_tree(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._uia_run(args, "tree")

    def uia_find(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._uia_run(args, "find")

    def uia_click(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._uia_run(args, "click")

    def uia_focus(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._uia_run(args, "focus")

    def uia_set_value(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._uia_run(args, "set_value")

    def gui_screenshot(self, args: dict[str, Any]) -> dict[str, Any]:
        # T3-gui-screenshot-virtual-screen-011: param `monitor=primary|all|<index>`.
        # Default sigue siendo `all` (VirtualScreen) por compatibilidad.
        monitor_raw = str(args.get("monitor") or "all").strip().casefold()
        if monitor_raw == "primary":
            mode = "primary"
        elif monitor_raw == "all":
            mode = "all"
        elif monitor_raw.isdigit():
            mode = f"index:{int(monitor_raw)}"
        else:
            return _err("invalid monitor; use primary|all|<index>", monitor=monitor_raw, status="needs_user")
        name = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = self.captures_dir / name
        env = os.environ.copy()
        env["GEMMA4_SCREENSHOT_PATH"] = str(path)
        env["GEMMA4_SCREENSHOT_MODE"] = mode
        script = r"""
$path = $env:GEMMA4_SCREENSHOT_PATH
$mode = $env:GEMMA4_SCREENSHOT_MODE
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
if ($mode -eq 'primary') {
  $screen = [System.Windows.Forms.Screen]::PrimaryScreen
  $bounds = $screen.Bounds
} elseif ($mode.StartsWith('index:')) {
  $idx = [int]$mode.Substring(6)
  $screens = [System.Windows.Forms.Screen]::AllScreens
  if ($idx -lt 0 -or $idx -ge $screens.Count) {
    [PSCustomObject]@{ ok=$false; error=("monitor index out of range; have {0} screens" -f $screens.Count) } | ConvertTo-Json
    exit 0
  }
  $bounds = $screens[$idx].Bounds
} else {
  $bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
}
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bmp.Size)
$bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
$gfx.Dispose()
$bmp.Dispose()
[PSCustomObject]@{ path=$path; width=$bounds.Width; height=$bounds.Height; left=$bounds.Left; top=$bounds.Top; mode=$mode } | ConvertTo-Json
"""
        # timeout 20 -> 10s + try/except. Screenshot via GDI normalmente <500ms.
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return _err("screenshot timeout", monitor=mode, reason="powershell_timeout")
        if proc.returncode != 0:
            return _err("screenshot failed", stderr=_truncate(proc.stderr.strip(), 2000))
        # CC-103: parse defensivo.
        ok, data = parse_ps_json(proc.stdout)
        if not ok or not isinstance(data, dict):
            return _err("screenshot invalid JSON", stdout=data if isinstance(data, str) else None, stderr=_truncate(proc.stderr, 1000))
        if data.get("ok") is False:
            return _err(str(data.get("error") or "screenshot failed"), status="needs_user")
        # Verificar que el PNG fue escrito (PS puede silenciosamente fallar al
        # guardar si captures_dir no existe o no hay permisos).
        out_path = Path(data["path"])
        if not out_path.is_file():
            return _err("screenshot file missing after capture", expected=str(out_path),
                        hint="check that captures_dir is writable")
        try:
            png_size = out_path.stat().st_size
        except OSError:
            png_size = 0
        if png_size == 0:
            return _err("screenshot file empty (0 bytes)", expected=str(out_path))
        return _ok(
            image_path=str(out_path.resolve()),
            width=data["width"], height=data["height"],
            left=data["left"], top=data["top"], monitor=mode,
            file_size=png_size, verified=True,
        )

    def gui_click(self, args: dict[str, Any]) -> dict[str, Any]:
        x = int(args.get("x") or 0)
        y = int(args.get("y") or 0)
        # Validar que (x, y) esta dentro del VirtualScreen actual. Si el LLM
        # pasa coords negativas o fuera de pantalla, mouse_event silenciosamente
        # no hace nada y devolvemos un _ok falso. Mejor abortar limpio.
        try:
            import win32api  # type: ignore
            virt_x = win32api.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
            virt_y = win32api.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
            virt_w = win32api.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
            virt_h = win32api.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
            if not (virt_x <= x < virt_x + virt_w and virt_y <= y < virt_y + virt_h):
                return _err(
                    "click coordinates outside virtual screen bounds",
                    x=x, y=y,
                    bounds={"left": virt_x, "top": virt_y, "width": virt_w, "height": virt_h},
                    status="needs_user",
                )
        except Exception:
            # Sin win32api seguimos adelante (mejor click impreciso que fallar).
            pass

        script = f"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Mouse {{
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(int flags, int dx, int dy, int data, int extra);
}}
"@
[Mouse]::SetCursorPos({x}, {y}) | Out-Null
[Mouse]::mouse_event(0x0002,0,0,0,0)
[Mouse]::mouse_event(0x0004,0,0,0,0)
"""
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=6)
        except (OSError, subprocess.TimeoutExpired):
            return _err("gui_click timeout", x=x, y=y, reason="powershell_timeout")
        return _ok(x=x, y=y, exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 1000))

    def gui_multi_click(self, args: dict[str, Any], button: str, clicks: int) -> dict[str, Any]:
        x = int(args.get("x") or 0)
        y = int(args.get("y") or 0)
        down, up = ("0x0008", "0x0010") if button == "right" else ("0x0002", "0x0004")
        events = "\n".join([f"[Mouse]::mouse_event({down},0,0,0,0); [Mouse]::mouse_event({up},0,0,0,0); Start-Sleep -Milliseconds 80" for _ in range(clicks)])
        script = f"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Mouse {{
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(int flags, int dx, int dy, int data, int extra);
}}
"@
[Mouse]::SetCursorPos({x}, {y}) | Out-Null
{events}
"""
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
        return _ok(x=x, y=y, button=button, clicks=clicks, exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 1000))

    def gui_scroll(self, args: dict[str, Any]) -> dict[str, Any]:
        amount = int(args.get("amount", args.get("delta", -5)))
        wheel = amount * 120
        script = f"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Mouse {{
  [DllImport("user32.dll")] public static extern void mouse_event(int flags, int dx, int dy, int data, int extra);
}}
"@
[Mouse]::mouse_event(0x0800,0,0,{wheel},0)
"""
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
        return _ok(amount=amount, wheel=wheel, exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 1000))

    def gui_drag(self, args: dict[str, Any]) -> dict[str, Any]:
        x1 = int(args.get("x1") or args.get("from_x") or 0)
        y1 = int(args.get("y1") or args.get("from_y") or 0)
        x2 = int(args.get("x2") or args.get("to_x") or 0)
        y2 = int(args.get("y2") or args.get("to_y") or 0)
        script = f"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Mouse {{
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(int flags, int dx, int dy, int data, int extra);
}}
"@
[Mouse]::SetCursorPos({x1}, {y1}) | Out-Null
[Mouse]::mouse_event(0x0002,0,0,0,0)
Start-Sleep -Milliseconds 120
[Mouse]::SetCursorPos({x2}, {y2}) | Out-Null
Start-Sleep -Milliseconds 120
[Mouse]::mouse_event(0x0004,0,0,0,0)
"""
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
        return _ok(from_xy=[x1, y1], to_xy=[x2, y2], exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 1000))

    def gui_wait_for(self, args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("text") or args.get("target") or "").strip().casefold()
        timeout_s = int(args.get("timeout_sec", 20))
        if not text:
            return _err("missing text/target")
        deadline = time.monotonic() + timeout_s
        last = []
        while time.monotonic() < deadline:
            windows = self.list_windows({"limit": 60}).get("windows", [])
            last = windows
            if any(text in str(w.get("title", "")).casefold() for w in windows):
                return _ok(found=True, target=text, windows=windows)
            time.sleep(0.5)
        return _ok(found=False, target=text, last_windows=last)

    # Títulos/clases de ventanas que NO son apps escribibles (toasts de
    # notificación, shell). Si una de éstas tiene el foco, type_into perdería el
    # texto. Multi-idioma por TÍTULO no es fiable (localizado) -> chequeamos
    # también la CLASE de ventana (estable cross-locale).
    _NON_TYPABLE_TITLES = ("nueva notificación", "new notification", "notification")
    _NON_TYPABLE_CLASSES = ("Windows.UI.Core.CoreWindow", "Shell_TrayWnd",
                            "Progman", "WorkerW", "ForegroundStaging",
                            "MultitaskingViewFrame", "XamlExplorerHostIslandWindow")

    def _is_non_typable_foreground(self, fg_title: str) -> bool:
        try:
            import win32gui
            h = win32gui.GetForegroundWindow()
            if not h:
                return True
            cls = win32gui.GetClassName(h) or ""
            if cls in self._NON_TYPABLE_CLASSES:
                return True
            title = (fg_title or win32gui.GetWindowText(h) or "")
            if not title.strip():
                return True
            if title.strip().casefold() in self._NON_TYPABLE_TITLES:
                return True
        except Exception:
            return False
        return False

    def _focus_typable_window(self, hint: str = "") -> bool:
        """Enfoca una ventana de app escribible. Si `hint` nombra una (o resuelve
        a un proceso vía AppResolver), la prioriza; si no, toma la ventana de app
        normal más arriba en el z-order. Devuelve True si enfocó algo."""
        try:
            import win32gui
            import win32process
        except Exception:
            return False
        # Si hay hint, usar window_control(focus) que ya resuelve título/proceso
        # (incluye la traducción de builtins localizados que agregué a EnumWindows).
        if hint:
            try:
                r = self.window_control("focus", hint)
                inner = r.get("result") if isinstance(r, dict) else None
                if isinstance(inner, dict) and inner.get("ok"):
                    return True
            except Exception:
                pass
        # Fallback: primera ventana visible con título y clase "normal" en z-order.
        target = []
        def _cb(h, _):
            if not win32gui.IsWindowVisible(h):
                return True
            title = win32gui.GetWindowText(h) or ""
            if not title.strip():
                return True
            cls = win32gui.GetClassName(h) or ""
            if cls in self._NON_TYPABLE_CLASSES:
                return True
            if title.strip().casefold() in self._NON_TYPABLE_TITLES:
                return True
            target.append((h, title))
            return False  # primera válida = tope del z-order
        try:
            win32gui.EnumWindows(_cb, None)
        except Exception:
            pass
        if target:
            try:
                from .win_focus import focus_and_maximize
                return bool(focus_and_maximize(target[0][0], expected_title_substr=target[0][1] or None))
            except Exception:
                try:
                    win32gui.SetForegroundWindow(target[0][0])
                    return True
                except Exception:
                    return False
        return False

    def gui_type_into(self, args: dict[str, Any]) -> dict[str, Any]:
        """MACRO determinista (Fase 2 computer-use): teclear `text` en la ventana
        ACTIVA, con verificación. El 4B solo da el OBJETIVO (el texto); el código
        hace el cómo: (1) asegura que hay una ventana de foco real, (2) teclea vía
        gui_type (clipboard-paste para acentos), (3) verify_post_action mide si la
        pantalla cambió. Saca al 4B de formar la llamada GUI (Agent-S2 mixture of
        grounding: el modelo no estima/forma acciones GUI, el código sí).

        Devuelve el result de gui_type anotado con state_changed/typed."""
        text = str(args.get("text") or args.get("value") or "")
        if not text.strip():
            return _err("type_into requiere 'text'", status="needs_user")
        # 1) ¿hay una ventana en foco para recibir el texto? (GetForegroundWindow)
        try:
            import win32gui
            fg = win32gui.GetForegroundWindow()
            fg_title = win32gui.GetWindowText(fg) if fg else ""
        except Exception:
            fg, fg_title = None, ""
        # 1b) GROUNDING: el foreground puede ser un TOAST de notificación
        # ("Nueva notificación" / Windows.UI.Core.CoreWindow) o una ventana sin
        # título — robaría el texto y se perdería. (Bug 2026-05-24: en el macro
        # multi-intent "abrí Notepad y escribí X" el toast tomaba el foco y X se
        # tecleaba en la nada.) Si el foreground NO es una app normal escribible,
        # enfocamos la ÚLTIMA ventana de app real (la más arriba en el z-order
        # con título y clase de ventana normal). 'hint' permite al caller nombrar
        # la ventana objetivo (p.ej. el macro sabe que abrió Notepad).
        hint = str(args.get("window") or args.get("target") or "").strip()
        # Enfocar la ventana objetivo si: (a) el foreground no es escribible
        # (toast/shell) -> buscar cualquier app real, o (b) hay un HINT explícito
        # y el foreground NO es ya esa ventana -> evita escribir en la app
        # equivocada (Word/Edge) que casualmente tenga el foco. Si no hay hint y
        # el foreground ya es escribible, no tocamos nada.
        _need_focus = self._is_non_typable_foreground(fg_title)
        if hint and not _need_focus:
            if not self._match_query(hint, fg_title):
                _need_focus = True
        focus_attempted = False
        if _need_focus:
            focus_attempted = True
            focused = self._focus_typable_window(hint)
            # settle: dar tiempo a que el cambio de foco se asiente antes de
            # teclear (sin esto el primer keystroke puede ir a la ventana vieja).
            time.sleep(0.25)
            try:
                import win32gui as _w
                fg = _w.GetForegroundWindow()
                fg_title = _w.GetWindowText(fg) if fg else fg_title
            except Exception:
                pass
        # 2) capturar estado antes + teclear + verificar (sin VLM)
        try:
            from . import gui_verify
            before = gui_verify.capture_before(None, None)
        except Exception:
            before = None
        typed = self.gui_type({"text": text})
        if not typed.get("ok"):
            return typed
        try:
            if before is not None:
                from . import gui_verify
                v = gui_verify.verify_after(before)
                typed["state_changed"] = v.get("state_changed")
                typed["state_verify"] = v.get("reason")
        except Exception:
            pass
        # VERIFICACIÓN UIA (más fuerte que frame-diff para TEXTO): el dHash sobre
        # la ROI a veces NO trippea con texto chico (anti-aliasing sutil) -> daba
        # state_changed=False aunque el texto SÍ entró (UIA_has_text=True). Bug
        # 2026-05-24: el macro reportaba "no pude confirmar" en un éxito real.
        # Si UIA encuentra el texto tecleado en el árbol de la ventana en foco,
        # eso es prueba directa de que entró y promueve state_changed=True.
        uia_confirmed = None
        try:
            time.sleep(0.2)  # dejar que el texto se asiente en el árbol UIA
            # buscar por una palabra clave corta del título (no el título entero,
            # que incluye "Sin título:" y rompe el match por substring).
            _win_key = (hint or fg_title or "")
            uia_confirmed = self._uia_window_contains_text(_win_key, text)
            if uia_confirmed is not True:
                # reintento sin filtrar por ventana (cualquier ventana en foco):
                uia_confirmed = self._uia_window_contains_text("", text)
        except Exception:
            uia_confirmed = None
        if uia_confirmed is True:
            typed["state_changed"] = True
            typed["state_verify"] = "uia_text_present"
            typed["verified"] = True
        elif typed.get("state_changed") is False:
            typed["verified"] = False
            typed.setdefault("completion_status", "typed_no_effect")
        typed["uia_confirmed"] = uia_confirmed
        typed["typed_into_window"] = fg_title
        typed["action"] = "type_into"
        return typed

    # Clases/procesos cuyo árbol UIA (AX de Chromium/CEF/Electron) es lazy: el
    # 1er walk tras enfocar devuelve vacío. Discord/Spotify/Slack/VSCode/Teams
    # son Electron. Detectamos por CLASE de ventana (estable) y proceso.
    _CHROMIUM_WIN_CLASSES = ("Chrome_WidgetWin_1", "Chrome_WidgetWin_0",
                             "Intermediate D3D Window")

    def _foreground_is_chromium(self, window_hint: str = "") -> bool:
        """¿La ventana objetivo (hint o foreground) es Chromium/CEF/Electron?
        Por clase de ventana (cross-locale). Sirve para decidir el retry lazy."""
        try:
            import win32gui
            h = 0
            if window_hint:
                # buscar una ventana visible cuyo título matchee el hint
                cands = []
                def _cb(hh, _):
                    if win32gui.IsWindowVisible(hh):
                        t = win32gui.GetWindowText(hh) or ""
                        if self._match_query(window_hint, t):
                            cands.append(hh)
                    return True
                win32gui.EnumWindows(_cb, None)
                h = cands[0] if cands else 0
            if not h:
                h = win32gui.GetForegroundWindow()
            if not h:
                return False
            return (win32gui.GetClassName(h) or "") in self._CHROMIUM_WIN_CLASSES
        except Exception:
            return False

    def _click_button_via_ocr(self, label: str, args: dict[str, Any]) -> dict[str, Any] | None:
        """FALLBACK OCR del macro click_button: screenshot -> ocr_find_text(label)
        -> click del centro del match -> verify_post_action. Devuelve el result
        (ok/fail) o None si OCR no encontró nada (para que el caller decida el
        error final). NO depende de UIA — es para apps de render propio (CEF,
        custom-draw) donde el árbol UIA no expone el botón."""
        shot = self.gui_screenshot({})
        if not shot.get("ok"):
            return None
        try:
            found = ocr_find_text(Path(str(shot["image_path"])), label,
                                  lang=str(args.get("lang") or "spa+eng"),
                                  min_conf=int(args.get("min_conf", 25)))
        except Exception:
            return None
        matches = found.get("matches") or []
        if not matches:
            return None
        m = matches[0]
        # traducir coords image-local -> pantalla (igual que el path click_text)
        shot_left, shot_top = int(shot.get("left", 0)), int(shot.get("top", 0))
        if "center_x" in m and "center_y" in m:
            sx, sy = int(m["center_x"]) + shot_left, int(m["center_y"]) + shot_top
        elif "screen_x" in m and "screen_y" in m:
            sx, sy = int(m["screen_x"]), int(m["screen_y"])
        else:
            return None
        try:
            from . import gui_verify
            before = gui_verify.capture_before(sx, sy)
        except Exception:
            before = None
        clicked = self.gui_click({"x": sx, "y": sy})
        if not clicked.get("ok"):
            return _err(clicked.get("error") or "el click OCR falló",
                        label=label, status="failed", grounding="ocr")
        try:
            if before is not None:
                from . import gui_verify
                v = gui_verify.verify_after(before)
                clicked["state_changed"] = v.get("state_changed")
                clicked["state_verify"] = v.get("reason")
                if v.get("state_changed") is False:
                    clicked["verified"] = False
                    clicked.setdefault("completion_status", "clicked_no_effect")
        except Exception:
            pass
        clicked["action"] = "click_button"
        clicked["label"] = label
        clicked["grounding"] = "ocr"
        clicked["ocr_match"] = {k: m.get(k) for k in ("text", "center_x", "center_y", "conf")}
        return clicked

    def gui_click_button(self, args: dict[str, Any]) -> dict[str, Any]:
        """MACRO determinista (computer-use): clickear un control por su LABEL.
        El 4B da el OBJETIVO (el label, p.ej. "Enviar"/"Save"/"Aceptar"); el
        código hace el cómo (Agent-S2 mixture of grounding):
          1) UIA find del control CLICKEABLE cuyo Name mejor matchea el label,
             priorizando tipos botón (Button/MenuItem/ListItem/TabItem/Hyperlink/
             CheckBox/RadioButton) sobre cualquier elemento que solo CONTENGA el
             texto — así "clickeá Enviar" no matchea un label de texto.
          2) capture_before en el punto del control -> Invoke()/click -> verify.
        Devuelve el result UIA anotado con state_changed (verificación SIN VLM).
        No es hardcode: el label viene del usuario en cualquier idioma, el
        matching es por Name del control, no por listas por-app/idioma."""
        label = str(args.get("label") or args.get("target") or args.get("query")
                    or args.get("text") or "").strip()
        if not label:
            return _err("click_button requiere 'label'", status="needs_user")
        window = str(args.get("window") or args.get("title") or "").strip()
        # CASCADA Fase 3: UIA -> (retry lazy-Chromium) -> OCR. El 4B da el label;
        # el código elige el grounding más fiable disponible (Agent-S2 mixture of
        # grounding). UIA primero (estructura, menos spoofeable); si el árbol UIA
        # viene vacío/sin match -y la ventana es Chromium/CEF cuyo AX es lazy- se
        # reintenta el walk tras un delay (gotcha verificado: 1er walk vacío);
        # si aún nada, cae a OCR (PaddleOCR) sobre el screenshot. Visión queda
        # como último recurso (Fase 8, no acá).
        # 1) localizar el botón por UIA (button-prioritized).
        found = self._uia_find_clickable(label, window)
        # 1b) retry lazy-Chromium: el árbol AX de Chromium/CEF (Discord/Spotify/
        # Electron) devuelve VACÍO en el 1er walk tras enfocar; reintentar una vez
        # tras un delay corto antes de caer a OCR.
        if not found.get("ok") and self._foreground_is_chromium(window):
            time.sleep(0.6)
            found = self._uia_find_clickable(label, window)
        # 1c) FALLBACK OCR: si UIA no encontró el control (app sin UIA rico),
        # localizar el label por OCR y clickear su centro, con verificación.
        if not found.get("ok"):
            ocr_res = self._click_button_via_ocr(label, args)
            if ocr_res is not None:
                return ocr_res
            return _err(
                found.get("error") or "no encontré un botón con ese label (UIA ni OCR)",
                label=label, window=window, status="failed",
                candidates=found.get("candidates"), grounding="uia+ocr")
        el = found.get("element") or {}
        pt = found.get("click_point") or {}
        cx, cy = pt.get("x"), pt.get("y")
        # 2) capture_before en el punto -> click -> verify_after.
        try:
            from . import gui_verify
            before = gui_verify.capture_before(cx, cy)
        except Exception:
            before = None
        # Click preferente por UIA InvokePattern (no depende de foreground ni de
        # coordenadas, funciona aunque el control esté parcialmente ocluido). Para
        # apuntar al EXACTO control que rankeamos usamos su AutomationId como query
        # (es único y _uia_run lo matchea); si no hay AutomationId, caemos al
        # punto clickeable por coordenada. _uia_run('click') ya intenta Invoke y
        # si no, clickea el GetClickablePoint del control.
        aid = (el.get("automation_id") or "").strip()
        click_query = aid or el.get("name") or label
        clicked = self._uia_run({"query": click_query, "window": window}, "click")
        if not clicked.get("ok"):
            # fallback: click por coordenada del punto que hallamos
            if cx is not None and cy is not None:
                clicked = self.gui_click({"x": int(cx), "y": int(cy)})
                if clicked.get("ok"):
                    clicked["method"] = "clickable_point_coord"
            if not clicked.get("ok"):
                return _err(clicked.get("error") or "el click falló",
                            label=label, element=el, status="failed")
        try:
            if before is not None:
                from . import gui_verify
                v = gui_verify.verify_after(before)
                clicked["state_changed"] = v.get("state_changed")
                clicked["state_verify"] = v.get("reason")
                if v.get("state_changed") is False:
                    clicked["verified"] = False
                    clicked.setdefault("completion_status", "clicked_no_effect")
        except Exception:
            pass
        clicked["action"] = "click_button"
        clicked["label"] = label
        clicked["clicked_element"] = el
        clicked["grounding"] = "uia"
        return clicked

    # Tipos de control que cuentan como "clickeables tipo botón", en orden de
    # preferencia. Estable cross-locale (son ProgrammaticName de UIA, en inglés).
    _BUTTON_CTYPES = ("Button", "SplitButton", "MenuItem", "TabItem",
                      "ListItem", "Hyperlink", "CheckBox", "RadioButton")

    def _uia_find_clickable(self, label: str, window: str) -> dict[str, Any]:
        """Encuentra el control clickeable cuyo Name mejor matchea `label`,
        priorizando tipos botón. Devuelve {ok, element, click_point} o
        {ok:false, candidates}. Reusa la maquinaria UIA existente (uia find)."""
        res = self._uia_run({"query": label, "window": window, "limit": 120}, "find")
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error") or "uia find falló"}
        matches = res.get("matches") or []
        # PowerShell ConvertTo-Json emite un OBJETO (no lista) cuando hay 1 sola
        # coincidencia -> normalizar. Y descartar cualquier entrada que no sea dict.
        if isinstance(matches, dict):
            matches = [matches]
        matches = [m for m in matches if isinstance(m, dict)]
        if not matches:
            return {"ok": False, "error": "sin coincidencias UIA", "candidates": []}
        from .tools import _score  # type: ignore  # noqa: F401  (módulo propio)
        lab = label.casefold()

        def rank(m: dict) -> tuple:
            name = (m.get("name") or "")
            ctype = (m.get("control_type") or "")
            enabled = bool(m.get("enabled", True))
            offscreen = bool(m.get("offscreen", False))
            has_click = bool(m.get("clickable_point"))
            # ¿es un tipo botón? (índice de preferencia; 99 si no)
            try:
                ctype_rank = self._BUTTON_CTYPES.index(ctype)
            except ValueError:
                ctype_rank = 99
            n = name.casefold()
            exact = 0 if n == lab else 1
            # name contiene el label (mejor señal que el match laxo de _uia_run,
            # que mira también AutomationId/ClassName/ControlType)
            name_has = 0 if lab in n else 1
            # preferir: clickeable, en pantalla, habilitado, tipo botón, nombre exacto/contiene
            return (0 if has_click else 1, 1 if offscreen else 0,
                    0 if enabled else 1, ctype_rank, exact, name_has, len(name))

        ranked = sorted(matches, key=rank)
        # Filtrar lo que NO puede ser un botón clickeable: sin Name Y sin
        # clickable_point no sirve. Aceptamos si tiene punto clickeable.
        best = next((m for m in ranked if m.get("clickable_point")
                     or (m.get("control_type") in self._BUTTON_CTYPES)), None)
        if best is None:
            return {"ok": False, "error": "ninguna coincidencia es clickeable",
                    "candidates": [m.get("name") for m in ranked[:6]]}
        return {"ok": True, "element": best,
                "click_point": best.get("clickable_point")
                or {"x": best.get("bounds", {}).get("x"),
                    "y": best.get("bounds", {}).get("y")}}

    def _uia_window_contains_text(self, window_substr: str, text: str) -> bool | None:
        """¿La ventana en foco (o cuyo título contiene window_substr) tiene un
        control de edición cuyo valor/Name contiene `text`? Lee el árbol UIA.
        None si UIA no está disponible. Es el verificador fuerte de 'el texto
        entró', usado por gui_type_into (más fiable que frame-diff para texto)."""
        try:
            import uiautomation as auto
        except Exception:
            return None
        needle = (text or "").strip().lower()
        if not needle:
            return None
        win_s = (window_substr or "").strip().lower()
        try:
            for w in auto.GetRootControl().GetChildren():
                wname = (w.Name or "").lower()
                if win_s and win_s not in wname and wname not in win_s:
                    continue
                # buscar texto en descendientes acotado (2 niveles)
                stack = list(w.GetChildren())
                depth = 0
                while stack and depth < 400:
                    el = stack.pop()
                    depth += 1
                    val = ""
                    try:
                        vp = el.GetValuePattern()
                        val = (vp.Value or "")
                    except Exception:
                        val = el.Name or ""
                    if needle in (val or "").lower():
                        return True
                    try:
                        stack.extend(el.GetChildren())
                    except Exception:
                        pass
            return False
        except Exception:
            return None

    def gui_type(self, args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("text", ""))
        # BUG tilde (2026-05-23): SendKeys vía stdin pierde acentos. El stdin de
        # PowerShell se decodifica con la code-page de consola (cp1252/OEM en
        # Windows ES), NO UTF-8, así que "mamá" llegaba como "mam?". Mismo gotcha
        # que espeak-ng (CLAUDE.md). Además SendKeys tiene límites con Unicode.
        # FIX: si el texto tiene caracteres NO-ASCII (acentos, ñ, emoji), tipear
        # por CLIPBOARD-PASTE (tkinter es UTF-8-safe), guardando y restaurando el
        # portapapeles del usuario. ASCII puro -> SendKeys (no toca el clipboard).
        non_ascii = any(ord(c) > 127 for c in text)
        if non_ascii and not bool(args.get("raw_sendkeys", False)):
            result = self._gui_type_via_paste(text)
            if result.get("ok"):
                return result
            # si el paste falla, caemos a SendKeys (best-effort, puede perder acentos)

        # T3-gui-type-no-sanitization-010: escapar SendKeys control chars.
        # `+^%~(){}[]` son modificadores/grupos; los envolvemos en `{}` para que
        # SendKeys los tipee literalmente. El orden importa: hay que escapar `{`
        # primero para evitar doble-wrap.
        if not bool(args.get("raw_sendkeys", False)):
            mapping = {"{": "{{}", "}": "{}}", "+": "{+}", "^": "{^}", "%": "{%}",
                       "~": "{~}", "(": "{(}", ")": "{)}", "[": "{[}", "]": "{]}"}
            escaped = []
            for ch in text:
                escaped.append(mapping.get(ch, ch))
            text_to_send = "".join(escaped)
        else:
            text_to_send = text
        # FIX encoding: pasar el texto por env-var (UTF-8 vía PowerShell que lee
        # $env directo) en vez de stdin (que se decodifica con la code-page de
        # consola y corrompe). Igual patrón que gui_keypress.
        env = {**os.environ, "GEMMA4_TYPE_TEXT": text_to_send}
        script = ("Add-Type -AssemblyName System.Windows.Forms; "
                  "[System.Windows.Forms.SendKeys]::SendWait($env:GEMMA4_TYPE_TEXT)")
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return _err("gui_type timeout", chars=len(text), reason="sendkeys_timeout")
        return _ok(chars=len(text), exit_code=proc.returncode, method="sendkeys",
                   stderr=_truncate(proc.stderr.strip(), 1000))

    def _gui_type_via_paste(self, text: str) -> dict[str, Any]:
        """Tipea `text` por clipboard-paste (Ctrl+V). UTF-8-safe para acentos,
        ñ, emoji. Guarda y restaura el portapapeles del usuario para no pisarlo.
        """
        # 1. Guardar clipboard actual (best-effort).
        saved = ""
        try:
            saved = str(self.clipboard_read({"max_chars": 100000}).get("content") or "")
        except Exception:
            saved = ""
        # 2. Poner nuestro texto (tkinter, UTF-8-safe).
        wrote = self.clipboard_write({"content": text})
        if not wrote.get("ok"):
            return _err("paste: clipboard_write failed", method="paste")
        import time as _t
        _t.sleep(0.05)
        # 3. Ctrl+V.
        env = {**os.environ, "GEMMA4_KEYS": "^v"}
        script = ("Add-Type -AssemblyName System.Windows.Forms; "
                  "[System.Windows.Forms.SendKeys]::SendWait($env:GEMMA4_KEYS)")
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           env=env, capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return _err("paste: ctrl+v timeout", method="paste")
        # 4. Restaurar clipboard del usuario (tras dar tiempo al paste).
        _t.sleep(0.1)
        if saved:
            try:
                self.clipboard_write({"content": saved})
            except Exception:
                pass
        return _ok(chars=len(text), method="paste")

    def gui_keypress(self, args: dict[str, Any]) -> dict[str, Any]:
        # CC-100 / T3-gui-keypress-sendkeys-injection-009: env-var indirection
        # para nunca f-stringear `keys` en el script PS.
        keys = str(args.get("keys", "")).strip()
        if not keys:
            return _err("empty keys")
        sendkeys = _translate_keys_to_sendkeys(keys)
        env = {**os.environ, "GEMMA4_KEYS": sendkeys}
        script = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait($env:GEMMA4_KEYS)"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=10)
        return _ok(keys=keys, sendkeys=sendkeys, exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 1000))

    def _match_query(self, query: str, target: str) -> bool:
        """Matching helper compartido entre verify_app_opened / verify_window_exists.

        Reglas (de mas estricto a mas laxo):
          1) exact match (con o sin extension): "chrome" == "chrome.exe" stem.
          2) substring solo si query tiene >=4 chars (evita "vs" -> cualquier exe).
          3) multi-token (>=2 tokens en query): TODOS deben aparecer en target.

        Esto evita los falsos positivos del antiguo `q in target` suelto, que
        confundia al LLM cuando varios procesos del sistema tenian el nombre
        del app buscado como substring (ej. ServiceHub*Chrome*).
        """
        q = _fold(query).strip()
        t = _fold(target).strip()
        if not q or not t:
            return False
        stem = t.rsplit(".", 1)[0] if "." in t else t
        if stem == q or t == q:
            return True
        if len(q) >= 4 and q in t:
            return True
        q_tokens = [tok for tok in q.split() if len(tok) >= 2]
        if len(q_tokens) >= 2:
            return all(tok in t for tok in q_tokens)
        return False

    def verify_app_opened(self, args: dict[str, Any]) -> dict[str, Any]:
        name = str(args.get("name") or args.get("query") or "").strip()
        if not name:
            return _err("missing name")
        # Limit alto para procesos (verify NECESITA exhaustivo, antes 300
        # podia perder matches en sistemas con 500+ procesos). Para ventanas
        # 60 es suficiente — el usuario raramente tiene mas abiertas.
        processes = self.list_processes({"limit": 1000}).get("processes", [])
        windows = self.list_windows({"limit": 60}).get("windows", [])

        proc_matches = [p for p in processes if self._match_query(name, str(p.get("name", "")))]
        win_matches = [
            w for w in windows
            if self._match_query(name, str(w.get("title", "")))
            or self._match_query(name, str(w.get("process", "")))
        ]
        return _ok(
            found=bool(proc_matches or win_matches),
            query=name,
            process_matches=proc_matches[:10],
            window_matches=win_matches[:10],
            match_count_procs=len(proc_matches),
            match_count_windows=len(win_matches),
        )

    def verify_file_exists(self, args: dict[str, Any]) -> dict[str, Any]:
        path = Path(str(args.get("path", "")).strip()).expanduser()
        return _ok(path=str(path), exists=path.exists(), is_file=path.is_file(), is_dir=path.is_dir(), size=path.stat().st_size if path.exists() and path.is_file() else None)

    def verify_window_exists(self, args: dict[str, Any]) -> dict[str, Any]:
        title = str(args.get("title") or args.get("query") or "").strip()
        if not title:
            return _err("missing title/query")
        windows = self.list_windows({"limit": 120}).get("windows", [])
        matches = [
            w for w in windows
            if self._match_query(title, str(w.get("title", "")))
            or self._match_query(title, str(w.get("process", "")))
        ]
        return _ok(found=bool(matches), query=title, matches=matches[:10], match_count=len(matches))

    def verify_clipboard_contains(self, args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("text", ""))
        clip = self.clipboard_read({"max_chars": max(4000, len(text) + 100)})
        content = str(clip.get("content", ""))
        return _ok(found=text in content, expected=text, content=_truncate(content, 1000))

    def memory_save(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.memory.save(str(args.get("key", "")), str(args.get("value", "")))

    def memory_recall(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args.get("query")
        return self.memory.recall(str(query) if query is not None else None)

    def memory_list(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.memory.recall(None)

    def memory_delete(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.memory.delete(str(args.get("key", "")))

from .tool_schemas import COMPOUND_TOOL_SCHEMAS  # Sprint 5b: literal moved to tool_schemas.py

_apply_action_enums(COMPOUND_TOOL_SCHEMAS)


# ---------------------------------------------------------------------------
# 1.8 — Tool schemas "EXACT" en Markdown para inyectar en system prompt.
#
# Item I1 #7 + Bloque C4 del informe de optimizacion externa. Patron del
# gist de Daniel Farina para OpenCode-on-Gemma-4: mostrar al modelo cada
# tool con tipos y REQUIRED/optional explicitos reduce errores de tool
# selection y de nombres de argumentos.
#
# El compilador es puro (solo lee COMPOUND_TOOL_SCHEMAS). Lo expone como
# string Markdown listo para inyectar via cualquier hint del agente
# (persona_hint, plan_hint, o un nuevo schemas_hint que el dev decida
# añadir en agent.py:388). No tocamos agent.py desde aqui (constraint
# del brief).
# ---------------------------------------------------------------------------


def compile_tools_to_markdown_exact(
    schemas: list[dict[str, Any]] | None = None,
    *,
    compact: bool = False,
) -> str:
    """Renderiza COMPOUND_TOOL_SCHEMAS como Markdown estilo "AGENTS.md".

    El formato sigue la convencion de Daniel Farina (OpenCode):
      # Tool Schemas (EXACT parameter names - you MUST use these exactly)

      ## <tool_name>
      <description>

      Parameters:
      - <param> (<type>, REQUIRED|optional): ...
      - ...

    Argumentos:
      schemas: lista opcional; por default usa COMPOUND_TOOL_SCHEMAS.
      compact: si True, omite descripciones largas y limita enums a 5
               valores. Reduce ~60% del tamaño. Usar en perfiles con
               contexto <16K (light, balanced, balanced_8gb).

    Returns:
      String Markdown. Si no hay schemas, devuelve string vacio.
    """
    sch = schemas if schemas is not None else COMPOUND_TOOL_SCHEMAS
    if not sch:
        return ""

    if compact:
        lines: list[str] = [
            "# Tool Schemas (EXACT names - use ONLY these)",
            "",
        ]
    else:
        lines = [
            "# Tool Schemas (EXACT parameter names - you MUST use these exactly)",
            "",
            "Each tool below shows its EXACT parameter names and types. Do NOT invent",
            "parameter names. Use ONLY the action values shown in the enum (when present).",
            "",
        ]

    enum_cap = 5 if compact else 10

    for entry in sch:
        fn = (entry.get("function") or {}) if isinstance(entry, dict) else {}
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        desc = str(fn.get("description") or "").strip()
        params = fn.get("parameters") or {}
        if not isinstance(params, dict):
            params = {}
        props = params.get("properties") or {}
        required = set(params.get("required") or [])

        lines.append(f"## {name}")
        if desc and not compact:
            lines.append(desc)
        elif desc and compact:
            # Solo primera oracion en compact.
            first_sentence = desc.split(".")[0].strip()
            if first_sentence:
                lines.append(first_sentence + ".")
        if props:
            if not compact:
                lines.append("")
                lines.append("Parameters:")
            # Ordena: required primero, despues alfabetico.
            keys_required = [k for k in props.keys() if k in required]
            keys_optional = [k for k in props.keys() if k not in required]
            keys_required.sort()
            keys_optional.sort()
            for key in keys_required + keys_optional:
                spec = props[key] if isinstance(props.get(key), dict) else {}
                tname = str(spec.get("type") or "any")
                tag = "REQUIRED" if key in required else "optional"
                bullet = f"- {key} ({tname}, {tag})"
                enum = spec.get("enum")
                if isinstance(enum, list) and enum:
                    enum_preview = ", ".join(repr(v) for v in enum[:enum_cap])
                    if len(enum) > enum_cap:
                        enum_preview += ", ..."
                    bullet += f": one of [{enum_preview}]"
                items = spec.get("items")
                if isinstance(items, dict) and items.get("type") and not compact:
                    bullet += f" (items: {items.get('type')})"
                lines.append(bullet)
        lines.append("")  # blank line entre tools

    return "\n".join(lines).rstrip() + "\n"

