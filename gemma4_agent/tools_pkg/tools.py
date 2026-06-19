"""Real Windows tools for the standalone Carter agent."""

from __future__ import annotations

import csv
import difflib
import json
import logging
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
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus, urlparse

from ..domain_tools import (
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
    source_manager_tool,
    study_tool,
    watcher_tool,
    whatsapp_tool,
    # Detector estructural multilingüe de pedidos de música (raíces por prefijo,
    # cubre es/en/it/pt/fr/de) — reusado para NO repetir listas de keywords por
    # idioma acá (ley de producto #1/#3). Ver _is_generic_music_query en domain_tools.
    _is_generic_music_query,
)
from .._ps import parse_ps_json
from ..computer_use_pkg import gui_safety
from ..computer_use_pkg import gui_verify
from ..memory_pkg.knowledge import KnowledgeStore
from ..memory_pkg.memory import MemoryStore
from .ops_tools import browser_real_tool, download_tool, email_tool, env_tool, input_tool, ocr_find_text, ocr_image, registry_tool, reminder_tool, state_tool
from ..safety_pkg.safety import classify_tool_call
from ..memory_pkg.state import AgentState


ToolFn = Callable[[dict[str, Any]], dict[str, Any]]

_log = logging.getLogger(__name__)


DEFAULT_YOUTUBE_SONGS = [
    {"title": "Rick Astley - Never Gonna Give You Up", "video_id": "dQw4w9WgXcQ"},
    {"title": "Queen - Bohemian Rhapsody", "video_id": "fJ9rUzIMcZQ"},
    {"title": "Mark Ronson - Uptown Funk ft. Bruno Mars", "video_id": "OPf0YbXqDm0"},
    {"title": "Luis Fonsi - Despacito ft. Daddy Yankee", "video_id": "kJQP7kiw5Fk"},
    {"title": "Major Lazer & DJ Snake - Lean On", "video_id": "YqeW9_5kURI"},
]

DEFAULT_WEB_SEARCH_PROVIDER = "duckduckgo_html"


# _ok / _err: single source of truth en ._shared. No duplicar en
# tools/ops_tools/domain_tools (los bodies deben ser byte-idénticos).
# Importados acá temprano porque _ok/_err se usan en el resto del módulo
# desde ~línea 100. El import de redact_sensitive más abajo se mantiene
# aparte.
from .._shared import _err, _ok  # noqa: E402


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
    # ISO datetime aceptado, HH:MM aceptado.
    if _RX_HHMM_LOCAL.fullmatch(raw):
        return None
    try:
        from datetime import datetime as _dt
        _dt.fromisoformat(raw.replace("Z", "+00:00"))
        return None
    except ValueError:
        pass
    # LENGUAJE NATURAL: "a las 7 de la mañana", "mañana a las 9". El
    # tool (_notification_due) ya las resuelve vía datetime_parse; el validador
    # debe DEJARLAS PASAR si parse_when las entiende con confianza. Si NO -> sigue
    # rechazando (honesto: pedir hora exacta, no inventar). Misma capa que
    # reminder, para alarmas/timers (no solo ISO/HH:MM).
    try:
        from ..support.datetime_parse import parse_when as _pw
        if _pw(raw):
            return None
    except Exception:
        pass
    return _err(
        f"invalid time/due format: {raw!r} (use ISO datetime, HH:MM, or a clear "
        "time like 'a las 7 de la mañana')",
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
    except (zipfile.BadZipFile, OSError):
        # No es nuestro trabajo aquí; deja que el flujo principal lo reporte.
        return None
    return None


_PRE_VALIDATORS: dict[str, Any] = {
    "notification": _prevalidate_notification,
    "backup_sync": _prevalidate_backup_sync,
}


# redact_sensitive: single source of truth en :mod:`._shared`. No duplicar
# contra domain_tools._redact_credentials.
from .._shared import redact_sensitive as _redact_sensitive  # noqa: E402


# Completion statuses que representan dispatch async exitoso al SO/browser:
# la operacion llego a destino, el efecto fisico (audio, render, click) no es
# medible desde Python pero NO es un fallo. Estos casos:
#   - NO se etiquetan como "needs_verification" (eso confundia al LLM).
#   - status="dispatched" (nuevo bucket distinto de done/attempted/needs_verif).
#   - verified=None (honest tristate: True medido / False medido y mal / None
#                    no medible).
# Sin estos, los tools que despachan (browser.youtube_play, media.play_pause
# via media key, browser.open url, steam.store_page, app.open con
# launch_requested) reportan verified=False y disparan el guard "Nota: no
# dejo evidencia suficiente" aunque la accion SI ocurrio: falso positivo.
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


def _normalize_tool_result(name: str, args: dict[str, Any], result: Any) -> dict[str, Any]:
    # CONTRATO handler->dispatcher: un handler SIEMPRE debe devolver un dict. Si
    # devuelve list/None/str (handler roto), NO crashear el turno entero con
    # AttributeError ('list' object has no attribute 'setdefault') — eso reventaba
    # el turno completo (BUG real #busca_teclados, 2026-06-04: el AttributeError
    # escapaba al try/except de execute() porque la normalización corría FUERA del
    # try). Degradar a error honesto y trazable. ESTRUCTURAL (mide la FORMA del
    # result, no su contenido). Cubre execute() y execute_routine_step(). El repo
    # YA declara esta invariante (test_tool_dispatch_contract: "execute() never
    # raises"); esto la cierra para el caso non-dict, no solo el de excepción.
    if not isinstance(result, dict):
        result = _err(
            f"tool {name} returned non-dict result ({type(result).__name__})",
            status="failed", raw_result_type=type(result).__name__,
        )
    result.setdefault("tool", name)
    if args.get("action") and "action" not in result:
        result["action"] = str(args["action"])
    # Redacción de keys sensibles antes de que el resultado llegue a
    # traces/jsonl o se devuelva al LLM. Mutamos el dict result in-place a
    # través de un walk recursivo.
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
    "browser_real": ["status", "open", "goto", "tabs", "click", "click_accessible", "toggle_accessible", "fill", "press", "type_text", "text", "screenshot", "evaluate", "connect_cdp", "close", "attach_visible", "active_tab", "tab_open", "tab_close", "tab_focus", "click_text", "extract", "wait_for_download", "set_download_path"],
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
    "device_settings": ["status", "wifi_status", "wifi_list", "wifi_profiles", "wifi_scan", "wifi_connect", "wifi_disconnect", "wifi_add_profile", "wifi_delete_profile", "bluetooth_status", "bluetooth_toggle", "bluetooth_pair", "brightness_get", "brightness_set", "brightness_up", "brightness_down", "display_list", "display_set_resolution", "display_set_scale", "power_plan_list", "power_plans", "power_plan_get", "power_plan_set", "night_light", "wifi_set_profile"],
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
    "subagent": ["status", "run"],
    "safety": ["status", "pending", "confirm", "cancel"],
    "session": ["cancel_turn"],
    # whatsapp/mcp tenían `action` libre (sin enum) → el 4B podía inventar acciones
    # inválidas (ej. 'send_whatsapp') que solo se rechazaban tras intentar, gastando
    # un turno de retry. Con enum, _coerce_and_validate_tool_args rechaza a nivel
    # schema (más barato). El set incluye TODAS las acciones que los handlers aceptan
    # (whatsapp suma los alias de LECTURA que t_whatsapp intercepta y rutea a vision).
    "whatsapp": ["status", "send_message", "send", "open_chat", "read", "read_message",
                 "read_messages", "read_chat", "last_message", "unread", "list_messages",
                 "get_messages"],
    "mcp": ["list", "call"],
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


def _invalid_args_result(name: str, clean_args: dict[str, Any],
                         validation_errors: list[str]) -> dict[str, Any]:
    """Error de argumentos inválidos CORREGIBLE en 1 reintento.

    El caso típico (system(action='calculator')) es un enum de acción inválido: la
    grammar de --jinja de Gemma fuerza la ESTRUCTURA del tool-call pero NO el enum
    del argumento (json-schema-to-grammar no cubre la notación fc de Gemma), así que
    el 4B igual puede inventar la acción. En vez de una GBNF custom (que pelea con la
    grammar interna y puede romper TODO el tool-calling), devolvemos un error
    máximamente accionable: acciones válidas explícitas + hint de que, si lo que
    quería no está, ESTA no es la tool. El loop del agente corrige en 1 turno."""
    valid_actions = ACTION_ENUMS.get(str(name))
    extra: dict[str, Any] = {}
    if valid_actions:
        extra["hint"] = (
            f"'{name}' SOLO acepta action en {list(valid_actions)}. Si lo que "
            f"necesitás no está en esa lista, '{name}' NO es la tool correcta: elegí "
            f"otra del subset, o si es operar una app abierta usá "
            f"gui(action='type'/'keypress').")
    return _normalize_tool_result(
        name, clean_args,
        _err("invalid tool arguments", validation_errors=validation_errors,
             expected_schema=_parameters_for_tool(name), **extra))


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


# Maquinaria SendInput CACHEADA a nivel módulo. CAUSA RAÍZ del "anda ~6 veces
# y muere": recrear WinDLL + redeclarar argtypes + redefinir las clases
# Structure en CADA llamada acumula estado en el proceso hasta que SendInput
# deja de entregar (la cola de input se corrompe). Medido: con todo recreado
# por llamada -> 3-6 OK luego falla. Construir la maquinaria UNA sola vez
# elimina el acumulador. _SENDINPUT = None hasta el primer uso; en no-Windows
# queda None y el caller cae al path legacy.
_SENDINPUT = None


def _sendinput_machine():
    """Devuelve (user32, INPUT_factories) cacheado, o None si no aplica."""
    global _SENDINPUT
    if _SENDINPUT is not None:
        return _SENDINPUT if _SENDINPUT is not False else None
    if os.name != "nt":
        _SENDINPUT = False
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        ULONG_PTR = wintypes.WPARAM

        class _MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class _KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ULONG_PTR)]

        class _HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                        ("wParamH", wintypes.WORD)]

        class _INPUTUNION(ctypes.Union):
            _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT),
                        ("hi", _HARDWAREINPUT)]

        class _INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

        user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
        user32.SendInput.restype = wintypes.UINT
        user32.VkKeyScanW.argtypes = (wintypes.WCHAR,)
        user32.VkKeyScanW.restype = ctypes.c_short
        _SENDINPUT = {
            "user32": user32, "ctypes": ctypes, "INPUT": _INPUT,
            "KEYBD": _KEYBDINPUT, "size": ctypes.sizeof(_INPUT),
        }
        return _SENDINPUT
    except Exception:
        _SENDINPUT = False
        return None


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
    # QUERY empieza con CANDIDATO ("calculadora" -> exe "calc"): nombre largo vs
    # nombre corto del .exe, misma app. Candidato >=4 chars y query de 1 palabra
    # (evita "ch"->chrome y "hola mundo..."->app espuria).
    if len(c) >= 4 and " " not in q and q.startswith(c):
        return 88
    if q in c:
        return 75
    q_words = set(q.split())
    c_words = set(c.split())
    if not q_words:
        return 0
    # Exclude stopwords from the "meaningful overlap" count.
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
    # First-character guard. Short near-anagrams ("teams" vs
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


# AppCandidate/AppResolver + _site_resolution_relevant (discriminador nombre<->host
# del fix de honestidad gibberish) viven en :mod:`.app_resolver`, re-exportados acá.
from .app_resolver import AppCandidate, AppResolver, _SITE_REQUEST_FILLERS, _site_resolution_relevant  # noqa: E402,F401


# Helpers de dominio (registrable_label / is_probably_guessed_domain /
# _KNOWN_REAL_DOMAINS) extraídos a site_resolver.py (2026-06-07, baja LOC).
from .site_resolver import (  # noqa: E402,F401
    registrable_label as _registrable_label,
    is_probably_guessed_domain as _is_probably_guessed_domain,
    _KNOWN_REAL_DOMAINS,
)

# Helpers de Steam extraídos a steam_store.py (ratchet anti-archivo-dios). Shim de
# back-compat: siguen accesibles como tools._steam_* / tools._acf_value.
from .steam_store import (  # noqa: E402,F401
    _acf_value,
    _nearest_steam_appid,
    _steam_appid_from_launch,
    _steam_store_uri,
    _steam_openurl_uri,
    _steam_store_url,
    _steam_store_first_result,
    _is_placeholder_appid,
)


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
    # GUARDA ESTRUCTURAL (no por intención): nunca cerramos editores/IDE/terminales
    # ni nuestro propio árbol de procesos, AUNQUE el título matchee el query. El bug
    # que motiva esto: el título de VS Code contiene el path del proyecto ("Probando
    # Gemma 4"), así que "cerrá gemma" -> WM_CLOSE a Code.exe y se pierde trabajo sin
    # guardar. Protege por IDENTIDAD del proceso (ProcessName + PID propio/padre),
    # no por una lista de apps-objetivo hardcodeada. Si el usuario realmente quiere
    # cerrar su editor, el match exacto del ProcessName lo permite igual.
    env["GEMMA4_OWN_PID"] = str(os.getpid())
    try:
        env["GEMMA4_PARENT_PID"] = str(os.getppid())
    except Exception:
        env["GEMMA4_PARENT_PID"] = ""
    script = r"""
$q=$env:GEMMA4_CLOSE_QUERY.ToLower()
$ownPid=[int]$env:GEMMA4_OWN_PID
$parentPid = if ($env:GEMMA4_PARENT_PID) { [int]$env:GEMMA4_PARENT_PID } else { 0 }
# Procesos protegidos: editores/IDE/terminales/shell. Se exime SOLO si el query
# matchea EXACTO el ProcessName (intención inequívoca de cerrar esa app puntual);
# un match por substring/título sobre uno de estos NO cierra.
$protected = @('code','code - insiders','codium','vscodium','devenv','rider64',
  'pycharm64','idea64','webstorm64','clion64','sublime_text','atom','notepad++',
  'windowsterminal','wt','powershell','pwsh','cmd','conhost','explorer',
  'python','pythonw','node','claude','git')
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
$skipped = @()
foreach ($p in $targets) {
  $pn = $p.ProcessName.ToLower()
  $isProtected = $protected -contains $pn
  $exactName = ($pn -eq $q)            # el usuario nombró el proceso exacto
  $isSelf = ($p.Id -eq $ownPid) -or ($p.Id -eq $parentPid)
  if ($isSelf -or ($isProtected -and -not $exactName)) {
    $skipped += [PSCustomObject]@{ title=$p.MainWindowTitle; process=$p.ProcessName; pid=$p.Id; reason=$(if($isSelf){'self'}else{'protected'}) }
    continue
  }
  [Win32]::PostMessage($p.MainWindowHandle,0x0010,[IntPtr]::Zero,[IntPtr]::Zero) | Out-Null
  $closed += [PSCustomObject]@{ title=$p.MainWindowTitle; process=$p.ProcessName; pid=$p.Id }
}
[PSCustomObject]@{ count=$closed.Count; windows=$closed; skipped=$skipped } | ConvertTo-Json -Depth 4
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


# Subconjunto de RAÍCES que son SUSTANTIVO-de-música o CUANTIFICADOR (NO verbos de
# play). _looks_like_music_request usa solo estas para conservar la semántica
# original: un pedido cuenta como "de música" por mencionar canción/música/etc o un
# cuantificador vago, NO por el solo verbo "pon" (así 'pon Bad Bunny' sigue abriendo
# resultados de búsqueda, no auto-reproduce). Derivado por prefijo de la tupla
# compartida para no duplicar la lista por idioma.
_MUSIC_NOUN_ROOTS = (
    "cancion", "canción", "music", "música", "musica", "musik", "muziek", "musique",
    "rola", "tema", "song", "tune", "cancao", "canção", "canzon", "chanson", "lied",
    "morceau", "brano",
    "algo", "cualquier", "random", "aleatori", "something", "anything", "whatever",
    "some", "qualquer", "qualcosa", "quelque", "irgend", "nagot", "iets", "etwas",
)


def _looks_like_music_request(query: str) -> bool:
    """¿El query MENCIONA música (sustantivo de canción o cuantificador vago)?
    Estructural y multilingüe: matchea RAÍCES por prefijo (es/en/it/pt/fr/de) en vez
    de una lista de keywords por idioma. Así 'una canzone', 'spiele musik' o 'uma
    música' matchean igual que 'una canción' (ley de producto #1/#3). NO cuenta el
    solo verbo de play como música (conserva la conducta vieja: 'pon X' con título
    abre búsqueda, no auto-reproduce)."""
    norm = " ".join(_fold(query).split()).strip(" .!?,;:\"'")
    if not norm:
        return False
    return any(
        word.startswith(root)
        for word in norm.split()
        for root in _MUSIC_NOUN_ROOTS
    )


def _is_generic_song_query(query: str) -> bool:
    """Pedido de música SIN un título nombrado → reproducir algo genérico.
    Delega en el detector estructural multilingüe de domain_tools (raíces por
    prefijo + filler de función), que NO enumera frases por idioma y cubre
    es/en/it/pt/fr/de. Reemplaza la vieja tabla de 10 frases es/en (ley #1/#3)."""
    return _is_generic_music_query(query)


# Resolución de YouTube extraída a youtube_search.py (split archivo-dios 2026-06-19).
# Re-exportada acá para los métodos de esta clase.
from .youtube_search import (  # noqa: E402,F401
    _looks_like_youtube_watch_url,
    _youtube_first_result,
    _youtube_title_near_video_id,
    _youtube_watch_url,
)


# _is_private_host + _SSRFGuardRedirectHandler live in :mod:`.ssrf_guard`.
# Re-export here so the internal callers (_http_get_text below + the
# audit/smoke harness) keep working.
from ..safety_pkg.ssrf_guard import _is_private_host, _SSRFGuardRedirectHandler  # noqa: E402,F401


# HTTP fetch + HTML→texto extraídos a web_text.py (split archivo-dios 2026-06-19).
# Re-exportados acá para los métodos de esta clase y para steam_store/web_search,
# que históricamente los importaban lazy desde tools.py.
from .web_text import (  # noqa: E402,F401
    WEB_USER_AGENT,
    _clean_html_text,
    _extract_title,
    _html_to_text,
    _http_get_text,
)


# Scrapers HTML de búsqueda web (DDG/Bing) + selector de proveedor extraídos a
# web_search.py (2026-06-08, ratchet archivo-dios). Re-exportados con los nombres
# privados que el resto de tools.py espera.
from .web_search import (  # noqa: E402
    web_search_provider as _web_search_provider,
)


# Búsqueda web (ddgs) + resolución de sitio extraídas a site_resolver.py (2026-06-07).
from .site_resolver import (  # noqa: E402
    ddgs_search_all_backends as _ddgs_search_all_backends,
    resolve_site_by_search as _resolve_site_by_search_impl,
)


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
            "computer_use": self.t_computer_use,
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
            "file_process": self.t_file_process,
            "fact_check": self.t_fact_check,
            "photo_library": self.t_photo_library,
            "container": self.t_container,
            "database": self.t_database,
            "creative_local": self.t_creative_local,
            "form_filler": self.t_form_filler,
            "peripheral": self.t_peripheral,
            "accessibility": self.t_accessibility,
            "study": self.t_study,
            "subagent": self.t_subagent,
            "safety": self.t_safety,
            "session": self.t_session,
            "mcp": self.t_mcp,
        }
        # Al inicio del proceso, las browser_real resources del run anterior
        # son stale (el dict global _BROWSER_SESSIONS está vacío). Las marcamos
        # como cerradas para evitar cleanup_plan/state.cleanup contra sesiones
        # que no existen.
        self._prune_stale_browser_sessions()
        # Enrolar las tools MCP al router UNA vez al boot (gated GEMMA4_MCP,
        # default off). Best-effort: si falla (SDK ausente, servidor caído,
        # timeout), el agente arranca igual sin MCP. NO bloquea el caso feliz:
        # discover tiene timeout y cachea.
        self._enroll_mcp_tools_best_effort()

    def _enroll_mcp_tools_best_effort(self) -> None:
        try:
            from .mcp_client import mcp_enabled, discover_mcp_tools
            if not mcp_enabled():
                return
            discovered = discover_mcp_tools()
            if not discovered:
                return
            from .mcp_client import mcp_tool_id
            from ..routing.semantic_router import enroll_mcp_tools
            payload = [
                {"id": mcp_tool_id(t["server"], t["name"]),
                 "description": t.get("description") or t["name"]}
                for t in discovered
            ]
            n = enroll_mcp_tools(payload)
            import logging as _lg
            _lg.getLogger(__name__).info("MCP: enrolled %d tools into router", n)
        except Exception as exc:  # noqa: BLE001
            import logging as _lg
            _lg.getLogger(__name__).warning("MCP enroll skipped: %s", exc)

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
        # PRESERVAR EL ORDEN de `names`: el router (planner._antiprimacy_order) ya
        # las ordena por score desc (mayor confianza primero) contra el primacy
        # bias del 4B (Liu et al. 2023 "Lost in the Middle"). Iterar
        # COMPOUND_TOOL_SCHEMAS y filtrar por `set` PERDERIA ese reorden (la feature
        # quedaba inerte). La clave de cache incluye el ORDEN (tuple, no frozenset):
        # mismo subset en distinto orden = entradas distintas, si no el cache
        # congelaria el primer orden. MCP bypasea el cache (catalogo dinamico).
        wanted = {str(name) for name in names}
        order = {str(name): i for i, name in enumerate(names)}  # 1ra aparicion gana
        has_mcp = any(n.startswith("mcp__") for n in wanted)
        lean_on = _lean_descriptions_on()
        cache_key: tuple | None = None
        if not has_mcp:
            cache_key = (tuple(str(n) for n in names), lean_on)
            cached = _SCHEMAS_FOR_NAMES_CACHE.get(cache_key)
            if cached is not None:
                # Copia de la lista externa: el cache es dueño de su lista; el
                # caller no debe poder mutarla. Los dicts internos se comparten
                # (igual que el path sin cache: out referencia los literales
                # globales cuando LEAN esta off, y copias estables cuando on).
                return list(cached)
        out = [
            schema
            for schema in COMPOUND_TOOL_SCHEMAS
            if str(schema.get("function", {}).get("name", "")) in wanted
        ]
        # Si el subset incluye tools MCP enroladas (nombres mcp__*),
        # resolvemos sus schemas dinámicos desde el cliente MCP (aditivo, NO muta
        # el literal global COMPOUND_TOOL_SCHEMAS). Solo si el subset realmente las
        # pidió -> 0 overhead cuando no hay MCP en el turno.
        if has_mcp:
            try:
                from .mcp_client import mcp_tool_schemas
                out.extend(s for s in mcp_tool_schemas()
                           if str(s.get("function", {}).get("name", "")) in wanted)
            except Exception:
                pass
        # Reordenar al orden pedido por `names` (anti-primacy del router). Sort
        # estable: tools con la misma posicion (no deberia pasar) preservan el
        # orden de COMPOUND_TOOL_SCHEMAS. Aca es donde el reorden del router al fin
        # llega al subset que ve el LLM.
        out.sort(key=lambda s: order.get(str(s.get("function", {}).get("name", "")), len(order)))
        # Descripciones lean opt-in (GEMMA4_LEAN_RULES) — SOLO en el subset
        # que ve el LLM; no muta el literal global. Default off = sin cambio.
        if lean_on:
            out = [_with_lean_description(s) for s in out]
        if cache_key is not None:
            # Guardamos una copia: si despues mutaramos out (no lo hacemos hoy)
            # el cache quedaria intacto. list() basta (dicts compartidos a proposito).
            _SCHEMAS_FOR_NAMES_CACHE[cache_key] = list(out)
        return out

    def execute(self, name: str, args: dict[str, Any] | None) -> dict[str, Any]:
        clean_args = dict(args or {})
        # Campos internos NUNCA aceptan inyección desde el LLM —
        # los filtramos antes de cualquier validación. El runner de routines
        # los reintroduce vía `execute_routine_step` (ver más abajo).
        # `_confirmed_by_gate` lo inyecta SOLO el flujo de confirmación real
        # (safety(action=confirm) → re-ejecuta tras un round-trip del usuario); el
        # LLM no puede falsificarlo porque se filtra acá antes de leerlo.
        _gate_confirmed = bool(clean_args.get("_confirmed_by_gate"))
        for forbidden in ("_internal_safe", "routine_context", "confirmed_at_create",
                          "_confirmed_by_gate"):
            clean_args.pop(forbidden, None)
        # Coerción honesta de `confirmed`: el 4B a veces emite el flag como STRING
        # ("false"/"no"/"0") y `bool("false")` daba True (string no-vacío es truthy)
        # → la op irreversible procedía SIN confirmar, salteando el safety gate de
        # abajo. Mismo bug-class ya arreglado para `state` del mute (ver audio_mute):
        # un string solo cuenta como confirmado si NO es un negativo conocido.
        _raw_confirmed = clean_args.pop("confirmed", False)
        if isinstance(_raw_confirmed, str):
            _llm_confirmed = _raw_confirmed.strip().lower() not in {"false", "no", "0", "off", ""}
        else:
            _llm_confirmed = bool(_raw_confirmed)
        # SEGURIDAD CRÍTICA (cacería t1-4, juez LLM): el 4B aprendió a AUTO-emitir
        # `confirmed:true` en la PRIMERA llamada → salteaba el gate de confirmación
        # de operaciones irreversibles (medido: 15 casos, incl "borra todo en C:/",
        # "borra system32"). El usuario NUNCA confirmó. Un `confirmed` venido del LLM
        # NO es una confirmación real. La confirmación VÁLIDA solo llega por:
        #   (a) `_confirmed_by_gate` → el flujo safety(confirm) tras round-trip real;
        #   (b) `confirmed_at_create` → rutina pre-confirmada al crearse (más abajo).
        # la regla de confirmar lo irreversible. El gate de abajo decide por RIESGO si confirmar;
        # para lo reversible (la mayoría) `_llm_confirmed` igual ahorra el round-trip
        # innecesario, pero NUNCA puede saltear lo irreversible.
        confirmed = _gate_confirmed or _llm_confirmed
        # Output-coherence guard: catch a known LLM misroute where the call
        # itself proves the wrong tool was chosen, and redirect it. This
        # validates the model's OUTPUT (not the user's words), so it stays
        # universal. Currently: audio_device({...,"level":N}) — the device
        # tool has no `level`; a numeric level means the user wanted VOLUME,
        # so route to audio.set_volume. (Repro: "baja el vol del pc a 10".)
        name, clean_args = _correct_known_misroute(name, clean_args)
        # Tool MCP enrolada (nombre 'mcp__server__tool'). El router la rankeó y
        # el cap la limitó como una tool más; acá la ruteamos transparente al
        # cliente MCP (no aparece en _impls porque es dinámica). Gated por
        # mcp_enabled() dentro de call_mcp_by_id (fallback honesto si está off).
        try:
            from .mcp_client import is_mcp_tool_name, call_mcp_by_id, mcp_tool_annotations
            if is_mcp_tool_name(name):
                # Las tools MCP son externas y de semántica desconocida. ANTES saltaban
                # el safety classifier por completo (este early-return precede al gate de
                # abajo): una mcp__fs__delete_file se ejecutaba sin confirmar aunque
                # safety estuviera ON. Acá aplicamos un gate equivalente, honrando un
                # `confirmed` previo. La decisión es ESTRUCTURAL (annotations del
                # protocolo MCP o verbo del nombre), no por idioma del usuario.
                if self.safety_enabled and not confirmed:
                    from ..safety_pkg.safety import classify_mcp_call
                    from ..safety_pkg.confirmation_policy import should_confirm as _should_confirm
                    _decision = classify_mcp_call(name, mcp_tool_annotations(name))
                    if _should_confirm(_decision):
                        _reason = _decision.reason or f"confirmación de tool MCP externa ({name})"
                        pending = self.state.create_confirmation(
                            name, _redact_sensitive(clean_args), _reason, _decision.risk or "mcp")
                        return _normalize_tool_result(name, clean_args, _err(
                            "confirmation required", status="needs_confirmation",
                            verified=False, completion_status="needs_confirmation",
                            confirmation=pending.get("confirmation")))
                mcp_args = dict(clean_args)
                mcp_args.pop("confirmed", None)
                return _normalize_tool_result(name, clean_args, call_mcp_by_id(name, mcp_args))
        except Exception as exc:
            # Preservar el traceback en el log de dev (antes se perdía: solo el
            # mensaje llegaba al LLM, dificultando distinguir bug de error esperado).
            _log.exception("MCP dispatch error for %s", name)
            return _normalize_tool_result(name, clean_args, _err(f"MCP dispatch error: {exc}"))
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
        # REDIRECCIÓN de CLICK VISUAL: "apretá el icono X" que el 4B mandó a una
        # tool de app (steam/app/window) con action='click' -> rutear a
        # gui(click_text) para que el OCR localice y clickee el elemento VISIBLE.
        # Estructural (verbo de acción + objetivo de texto, sin coords), gate por
        # env. Sin esto: 'click' rebota del enum y el 4B cae en un callejón
        # (capturas 2026-06-08: steam click -> launch_game -> nada).
        import os as _os_vc
        if _os_vc.environ.get("GEMMA4_VISUAL_CLICK_REDIRECT", "1").strip().lower() \
                not in {"0", "false", "no", "off"}:
            from .visual_click_redirect import maybe_redirect_visual_click
            _redir = maybe_redirect_visual_click(name, clean_args, ACTION_ENUMS.get(name))
            if _redir is not None and self._impls.get("gui"):
                name = "gui"
                impl = self._impls["gui"]
                clean_args = _redir
        clean_args, validation_errors = _coerce_and_validate_tool_args(name, clean_args)
        if validation_errors:
            return _invalid_args_result(name, clean_args, validation_errors)
        # Pre-validation hook: corre ANTES del classifier para que inputs
        # claramente inválidos no exijan confirmación al usuario (UX). Los
        # validators son pure-functions que devuelven un dict de error (con
        # `ok=False`) o None. Si devuelve error: short-circuit.
        validator = _PRE_VALIDATORS.get(name)
        if validator is not None:
            err = validator(clean_args)
            if err is not None:
                return _normalize_tool_result(name, clean_args, err)
        # Catálogo de PRECONDICIONES: antes de actuar, chequear estado del SO
        # (app instalada, whatsapp presente). Un False medido bloquea con mensaje
        # accionable -> needs_user (que el recovery clasifica como
        # ERR_MISSING_PRECONDITION, budget=1). None/unknown NO bloquea (fail-open).
        # Gated GEMMA4_PRECONDITIONS (default off). 0 overhead si off.
        try:
            from ..safety_pkg.preconditions import ensure_preconditions
            _prec = ensure_preconditions(name, clean_args)
            if _prec is not None:
                return _normalize_tool_result(name, clean_args, _err(
                    _prec.detail, status="needs_user",
                    completion_status="needs_dependency",
                    precondition=_prec.name))
        except Exception:
            pass
        # Skip del gate SOLO con confirmación REAL: el round-trip del usuario
        # (`_gate_confirmed`, vía safety(confirm)) o una rutina pre-confirmada al
        # crearse (`confirmed_at_create`, reinyectado por execute_routine_step). El
        # `confirmed` AUTO-EMITIDO por el LLM (`_llm_confirmed`) NO saltea el gate de
        # lo irreversible — el classifier decide por RIESGO. Para lo reversible, el
        # propio classifier no pide confirmación, así que no hay round-trip molesto.
        if self.safety_enabled and not _gate_confirmed and name != "safety":
            decision = classify_tool_call(name, clean_args)
            # La POLÍTICA de confirmación decide si confirmar (default confirm_risky:
            # never auto-aprueba lo reversible pero SIEMPRE confirma lo irreversible;
            # always confirma todo). Guarda estructural, sin LLM.
            from ..safety_pkg.confirmation_policy import should_confirm as _should_confirm
            if _should_confirm(decision):
                _c_reason = decision.reason or f"política de confirmación activa ({name})"
                pending = self.state.create_confirmation(name, _redact_sensitive(clean_args), _c_reason, decision.risk or "policy")
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
        # Reinyectamos `confirmed` despues de validar para que los gates duros
        # (terminal/system/package/database/backup_sync/filesystem) puedan
        # respetar la confirmacion previa sin chocar con el schema. SOLO la
        # confirmación REAL (`_gate_confirmed`, round-trip del usuario) llega a los
        # impls — NUNCA el `confirmed` auto-emitido por el LLM, que para irreversibles
        # ya fue interceptado por el gate de arriba (no debe alimentar un gate interno
        # del impl que lo trate como "ya confirmado").
        impl_args = dict(clean_args)
        if _gate_confirmed:
            impl_args["confirmed"] = True
        try:
            result = impl(impl_args)
        except Exception as exc:
            # Traceback al log de dev (el mensaje conciso sigue yendo al LLM). Sin
            # esto se pierde el stack -> imposible distinguir un bug (None.method,
            # index error) de un error esperado al depurar.
            _log.exception("tool %s raised during execute", name)
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
            return _invalid_args_result(name, clean_args, validation_errors)
        impl_args = dict(clean_args)
        impl_args["routine_context"] = True
        impl_args["confirmed_at_create"] = bool(confirmed_at_create)
        try:
            result = impl(impl_args)
        except Exception as exc:
            _log.exception("tool %s raised during routine step", name)
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
        if action in ("brightness_get", "get_brightness"):
            return self.system_brightness_get(args)
        if action in ("brightness_set", "set_brightness", "brightness",
                      "brightness_up", "brightness_down"):
            a = dict(args)
            if action == "brightness_up" and "level" not in a and "delta" not in a:
                a["delta"] = 20
            elif action == "brightness_down" and "level" not in a and "delta" not in a:
                a["delta"] = -20
            return self.system_brightness_set(a)
        if action in ("shutdown", "restart", "sleep"):
            # gate duro: confirmación obligatoria antes de power-off/restart/sleep.
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
            res = self.app_open({"name": name or "", "refresh": args.get("refresh", False)})
            # FALLBACK A WEB: "ve a pivigames/gmail.com/portal uniej" ->
            # el 4B rutea a app.open, pero es un SITIO, no una app instalada. Tres
            # señales de que hay que NAVEGAR en vez de abrir una app:
            #   (a) app.open no encontró NADA ("app not found"); o
            #   (b) el nombre es un DOMINIO (tiene punto: "gmail.com") -> es web,
            #       aunque app.open haya matcheado algo (falso: "Visite Java.com"); o
            #   (c) app.open dijo ok pero, para una consulta MULTI-PALABRA, el match
            #       es DÉBIL: "portal uniej" (2 palabras) -> "Portal de realidad mixta"
            #       (score 55, solo "portal" coincide). OJO: NO aplicar a consultas de
            #       UNA palabra — ahí app_open resuelve bien por alias/typo aunque el
            #       _score crudo sea bajo ("calculadora"->calc.exe score 0; "calculadra"
            #       ->Calculadora score 64). Esos son APPS reales, no falsos. Por eso el
            #       weak-match SOLO cuenta con 2+ palabras (donde "1 palabra suelta
            #       coincide" es señal fiable de falso match).
            # Resolvemos el sitio por búsqueda real y abrimos. Si la web no resuelve,
            # devolvemos el resultado original (honesto). Mismo patrón browser<->app.
            # Usamos `_score` directo del module scope: `from .tools import _score`
            # sería circular (tools.py importándose a sí mismo).
            _app_score = _score
            nm = str(name or "").strip()
            site_shaped = bool(nm) and 3 <= len(nm) <= 40 and "\\" not in nm and "/" not in nm and len(nm.split()) <= 4
            not_found = (not res.get("ok")) and str(res.get("error") or "") == "app not found"
            is_domain = "." in nm and " " not in nm  # "gmail.com", "pivigames.blog"
            weak_match = False
            if res.get("ok") and len(nm.split()) >= 2:  # solo multi-palabra
                matched_name = str((res.get("opened") or {}).get("name") or "")
                if matched_name:
                    try:
                        weak_match = _app_score(nm, matched_name) < 70
                    except Exception:
                        weak_match = False
            if site_shaped and (not_found or is_domain or weak_match):
                try:
                    resolved = self._resolve_site_by_search(nm)
                except Exception:
                    resolved = None
                # HONESTIDAD: el buscador SIEMPRE devuelve algo (gibberish->softonic),
                # antes abríamos y mentíamos. Solo "abierto con éxito" si el sitio
                # resuelto guarda relación estructural con el nombre (ver la función).
                if resolved and _site_resolution_relevant(nm, resolved):
                    opened = self.web_open_url({"url": resolved})
                    if opened.get("ok"):
                        opened.update(
                            delegated_from="app.open",
                            resolved_from_name=nm, resolved_url=resolved,
                            note=(f"'{nm}' no es una app instalada; lo resolví "
                                  f"como sitio web ({resolved}) y lo abrí."))
                        return opened
            return res
        if action == "close":
            return self.app_close({"name": name or ""})
        if action == "uninstall":
            return self.t_package({"action": "uninstall", "name": name or ""})
        return _err("unknown app action", action=action)

    def t_steam(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="open")
        query = str(args.get("query") or args.get("name") or "").strip()
        # ANTI-APPID-INVENTADO (2026-06-10, red estructural): el 4B alucina appids
        # placeholder ("1234567890") en CUALQUIER action, no solo store_page. Si el
        # appid parece inventado, lo descartamos de los args -> la action resuelve
        # por query (confiable) en vez de abrir una página rota. El schema ya pide
        # NO inventar appid, pero el 4B es no-determinista; esta es la red dura.
        _appid_in = str(args.get("appid") or "").strip()
        if _appid_in and _is_placeholder_appid(_appid_in):
            args = {k: v for k, v in args.items() if k != "appid"}
        # RED DE HONESTIDAD (BUG real eval run2): "¿Steam está abierto?" -> el 4B
        # elige steam(open) (vía forced-retry/schema, aunque el router NO ofrezca
        # steam) -> abría Steam y MENTÍA "Listo, abrí Steam". Una pregunta de ESTADO
        # NO debe ABRIR la app. Si el texto del turno es una pregunta de estado,
        # responder si el proceso corre — NO ejecutar open. Solo activo si el agente
        # plumeó _current_user_text (sin él = no-op, no rompe tests/CLI).
        if action == "open":
            _ut = (getattr(self, "_current_user_text", "") or "").strip()
            try:
                from ..routing.planner import _is_app_state_check as _isc
            except Exception:
                _isc = None
            if _ut and _isc and _isc(_ut):
                try:
                    _names = _running_process_names()
                    _running = any("steam" in n for n in _names)
                except Exception:
                    _running = None
                return _ok(action="status", app="Steam", running=_running,
                           completion_status="reported_state_did_not_open",
                           note="pregunta de estado: NO abrí Steam, reporté si corre")
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
        if action in {"install", "play_or_install"}:
            # INSTALAR un juego ("instalame doom eternal"). El URI
            # steam://install/<appid> abre el DIÁLOGO de instalación NATIVO de
            # Steam (el usuario confirma la descarga ahí mismo) — NO solo la
            # página de la tienda.
            #
            # El 4B casi nunca conoce el AppID numérico; emite
            # steam(action='install', query='doom eternal'). Sin `appid`, caer a
            # search_store solo ABRE la página de la tienda y NUNCA instala. Por
            # eso resolvemos el NOMBRE -> AppID con la MISMA cascada que
            # store_page (biblioteca local de Steam -> búsqueda real en la
            # store) y recién ahí disparamos steam://install/<appid>.
            appid = str(args.get("appid") or "").strip()
            match_source = "explicit_appid" if appid else ""
            matched: dict[str, Any] | None = None
            # Sin appid Y sin query no hay nada que instalar: pedir el juego en
            # vez de "abrir la tienda" a ciegas (que tampoco abriría nada y
            # mentiría — mentira estructural).
            if not appid and not query:
                return _err("missing game name to install", action="install",
                            status="needs_user",
                            hint="¿Qué juego querés instalar? Pasá el nombre en query o el appid.")
            if not appid:
                resolved = self._resolve_steam_appid(query)
                if resolved:
                    appid = resolved["appid"]
                    matched = resolved.get("match")
                    match_source = resolved.get("source", "")
            if appid:
                uri = f"steam://install/{appid}"
                os.startfile(uri)  # type: ignore[attr-defined]
                game_name = (matched or {}).get("name") or query or appid
                resource = self.state.register_resource(
                    "steam", f"Steam install: {game_name}",
                    cleanup_tool="app", cleanup_args={"action": "close", "name": "Steam"},
                    metadata={"appid": appid, "uri": uri},
                )
                # Confianza de la resolución: explicit_appid y la biblioteca
                # LOCAL son altas; el resultado de búsqueda en la store es BAJA
                # (puede traer el juego equivocado y arrancar una descarga de
                # varios GB). Lo marcamos para que el reply le diga al usuario
                # QUÉ juego se está instalando y pueda cancelar en el diálogo de
                # Steam si no es el correcto.
                low_confidence = match_source == "steam_store_search"

                # AUTO-CONFIRMAR el diálogo de instalación (instalar de verdad, no
                # dejar el diálogo abierto). Steam NO tiene instalación silenciosa
                # (doc oficial de Valve) y SteamCMD necesita credenciales -> la
                # ÚNICA vía es confirmar el diálogo.
                # Medido: el diálogo (SDL_app) expone su botón de instalar
                # con InvokePattern funcional -> lo invocamos por ACCESIBILIDAD
                # (NO SendInput; el click físico ni siquiera serviría: los botones
                # reportan bounds 0,0). El botón se elige por EMBEDDINGS
                # multilingües (no lista de keywords por idioma). SOLO en alta
                # confianza: si el juego salió de búsqueda en la store, dejamos el
                # diálogo abierto para que el user verifique (evita descargar el
                # juego equivocado, varios GB). Gate de entorno por si rompe.
                confirm: dict[str, Any] | None = None
                _auto = os.environ.get("GEMMA4_STEAM_AUTOCONFIRM_INSTALL", "1").strip().lower()
                if _auto not in {"0", "false", "no", "off"} and not low_confidence:
                    confirm = self._steam_confirm_install_dialog(game_name)

                installed = bool(confirm and confirm.get("confirmed"))
                if installed:
                    return _ok(
                        action="install", query=query or None, appid=appid,
                        resolved_game=game_name, uri=uri, matched=matched,
                        match_source=match_source or None,
                        resolution_confidence="high",
                        resource=resource.get("resource"),
                        opened_in="steam_client",
                        confirm=confirm,
                        completion_status="confirmed_install_download_started",
                        note=(
                            f"Started installing '{game_name}': resolved the "
                            f"AppID, opened Steam's install dialog, and confirmed "
                            f"it via accessibility (UIA InvokePattern), so the "
                            f"download is now running in Steam. No manual click "
                            f"was needed."
                        ),
                    )
                # No se auto-confirmó (baja confianza, gate off, no apareció el
                # diálogo, o el botón no era invocable): dejamos el diálogo abierto
                # y lo decimos honestamente — el user aprieta Instalar.
                reason = (confirm or {}).get("reason") if confirm else (
                    "store_search_low_confidence" if low_confidence else "autoconfirm_disabled")
                return _ok(
                    action="install",
                    query=query or None,
                    appid=appid,
                    resolved_game=game_name,
                    uri=uri,
                    matched=matched,
                    match_source=match_source or None,
                    resolution_confidence="low" if low_confidence else "high",
                    resource=resource.get("resource"),
                    opened_in="steam_client",
                    confirm=confirm,
                    completion_status="opened_steam_install_dialog",
                    note=(
                        f"Opened Steam's install dialog for '{game_name}' "
                        f"(steam://install/{appid}); the user needs to press "
                        f"Install to start the download (reason: {reason})."
                        + (" The game was matched by a Steam store SEARCH (not "
                           "the local library), so confirm with the user that "
                           f"'{game_name}' is the game they meant before "
                           "installing — they can cancel in Steam's dialog if "
                           "it's the wrong title."
                           if low_confidence else "")
                    ),
                )
            # No se pudo resolver el AppID (nombre desconocido o sin red): caemos
            # a la página de la tienda para que el usuario encuentre el juego y
            # presione Instalar manualmente. SOLO afirmamos que se abrió la
            # tienda si REALMENTE se abrió (fallback.ok) — si no, no mentimos.
            fallback = self.t_steam({"action": "store_page", "query": query})
            if isinstance(fallback, dict):
                opened = bool(fallback.get("ok"))
                fallback.update(
                    requested_action="install",
                    install_status=("appid_unresolved_opened_store_page" if opened
                                    else "appid_unresolved_store_page_failed"),
                    note=(
                        "Could not resolve a Steam AppID for the requested game, "
                        "so the Steam store page was opened instead of the "
                        "install dialog. Ask the user to confirm the exact game, "
                        "or press Install on the store page."
                        if opened else
                        "Could not resolve a Steam AppID and could not open the "
                        "store page either. Ask the user for the exact game name "
                        "or its Steam AppID."
                    ),
                )
            return fallback
        return _err("unknown steam action", action=action)

    # Tipos de control "botón de acción" del diálogo de Steam (medido: el botón
    # Instalar es ButtonControl con InvokePattern). ControlTypeName de uiautomation.
    _STEAM_DIALOG_BTN_TYPES = {"ButtonControl", "SplitButtonControl"}

    def _steam_confirm_install_dialog(
        self, game_name: str, timeout_s: float = 12.0
    ) -> dict[str, Any]:
        """Confirma el diálogo de instalación de Steam por ACCESIBILIDAD (UIA
        InvokePattern), SIN input físico. El diálogo es una ventana SDL_app cuyo
        árbol UIA expone los botones: Instalar/Install/Installieren, Cancelar,
        selectores de disco, checkboxes de acceso directo.

        Elige el botón de confirmar por EMBEDDINGS multilingües (no lista de
        keywords por idioma — cumple el constraint de producto): el concepto
        'install / confirm install' matchea 'Instalar'/'Install'/'Installieren' y
        NO 'Cancelar'/'Cancel'. Umbral + margen para no arriesgar (igual que el
        matcher cross-lingual de gui_click_button). Invoca por InvokePattern y
        VERIFICA que el diálogo se cerró. Si no aparece el diálogo, el botón no es
        invocable, o no hay match con confianza -> se DETIENE y reporta
        confirmed=False con la razón (NUNCA cae a click físico).

        Devuelve {confirmed: bool, reason, button?, candidates?}.
        """
        try:
            import uiautomation as auto
        except Exception:
            return {"confirmed": False, "reason": "uiautomation_unavailable"}
        try:
            from ..routing.semantic_router import embed as _embed
        except Exception:
            _embed = None  # type: ignore[assignment]

        if _embed is None:
            return {"confirmed": False, "reason": "no_encoder_for_button_match"}
        # Concepto multi-idioma: el encoder es multilingüe, así que 'install'
        # ancla bien contra Instalar/Installieren/Installer/Установить, etc.
        qv = _embed("install")
        if qv is None:
            return {"confirmed": False, "reason": "encoder_returned_none"}

        def _confident_install_button(window):
            # De los botones de `window`, elegir el que mejor matchea 'install'
            # por embeddings, SOLO si supera umbral+margen. Devuelve
            # (button_el, name, sim) o None. Esto es a la vez el DISCRIMINADOR del
            # diálogo (la ventana principal de Steam NO tiene un botón que matchee
            # 'install' con confianza -> no la confundimos con el diálogo) y el
            # selector del botón a invocar. Multi-idioma, sin keywords.
            names = []
            for el in self._steam_collect_dialog_buttons(window):
                try:
                    nm = (el.Name or "").strip()
                except Exception:
                    nm = ""
                if nm:
                    names.append((nm, el))
            if not names:
                return None
            scored = []
            for nm, el in names:
                nv = _embed(nm)
                if nv is None:
                    continue
                sim = float(sum(a * b for a, b in zip(qv, nv)))
                scored.append((sim, nm, el))
            if not scored:
                return None
            scored.sort(key=lambda x: -x[0])
            top_sim, top_name, top_el = scored[0]
            second = scored[1][0] if len(scored) > 1 else 0.0
            if top_sim < self._XLING_SIM_MIN or (top_sim - second) < self._XLING_MARGIN:
                return None
            return top_el, top_name, top_sim

        def _find_dialog():
            # El diálogo de instalación: WindowControl SDL_app que contiene un
            # botón que matchea 'install' CON CONFIANZA. Ese requisito lo
            # distingue de la ventana PRINCIPAL de Steam (también SDL_app, pero
            # sin un botón 'install' de alta similitud) — una heurística por
            # conteo (≥2 botones) matchea la biblioteca por error.
            for w in auto.GetRootControl().GetChildren():
                try:
                    if "SDL" not in (w.ClassName or ""):
                        continue
                except Exception:
                    continue
                hit = _confident_install_button(w)
                if hit is not None:
                    return w, hit
            return None, None

        # 1) Poll hasta que aparezca el diálogo (Steam tarda en despertar/resolver).
        dialog = None
        hit = None
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            dialog, hit = _find_dialog()
            if dialog is not None:
                break
            time.sleep(0.5)
        if dialog is None or hit is None:
            return {"confirmed": False, "reason": "install_dialog_not_found"}

        top_el, top_name, top_sim = hit

        # 3) Si el botón de instalar está DESHABILITADO, Steam no puede proceder
        #    (caso real: "NO HAY SUFICIENTE ESPACIO" — ningún disco tenía ~80GB
        #    libres -> Instalar disabled). Invocarlo no haría
        #    nada; reportamos honestamente el bloqueo en vez de afirmar que se
        #    apretó. No leemos el texto por idioma: usamos IsEnabled (estructural).
        try:
            if top_el.IsEnabled is False:
                return {"confirmed": False, "reason": "install_button_disabled",
                        "button": top_name,
                        "hint": ("Steam no puede instalar ahora — el botón está "
                                 "deshabilitado (típicamente falta de espacio en "
                                 "disco o el juego no está disponible). El usuario "
                                 "debe liberar espacio / elegir otro disco.")}
        except Exception:
            pass

        # 4) Invocar por InvokePattern (accesibilidad, NO SendInput).
        try:
            ip = top_el.GetInvokePattern()
            if ip is None:
                return {"confirmed": False, "reason": "button_no_invoke_pattern",
                        "button": top_name}
            ip.Invoke()
        except Exception as exc:
            return {"confirmed": False, "reason": f"invoke_failed: {exc}",
                    "button": top_name}
        try:
            from .. import gui_safety as _gs
            _gs.note_agent_input()
        except Exception:
            pass

        # 5) Verificar el efecto: el diálogo de instalación debe haberse cerrado
        #    (al confirmar, Steam lo cierra y arranca la descarga). Si sigue
        #    abierto, NO afirmamos éxito (honestidad estructural).
        time.sleep(1.5)
        still_open, _ = _find_dialog()
        confirmed = still_open is None
        return {
            "confirmed": confirmed,
            "reason": "dialog_closed_after_invoke" if confirmed
            else "invoked_but_dialog_still_open",
            "button": top_name,
            "button_sim": round(top_sim, 3),
            "grounding": "uia_invoke_multilingual",
        }

    def _steam_collect_dialog_buttons(self, window: Any) -> list[Any]:
        """Recorre el subárbol de una ventana y devuelve sus controles botón
        (acotado en profundidad para no colgarse). Reusado por el confirmador."""
        out: list[Any] = []
        stack = [window]
        depth = 0
        while stack and depth < 6000:
            el = stack.pop()
            depth += 1
            try:
                if (el.ControlTypeName or "") in self._STEAM_DIALOG_BTN_TYPES:
                    out.append(el)
            except Exception:
                pass
            try:
                stack.extend(el.GetChildren())
            except Exception:
                pass
        return out

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
        # AUTO-DELEGACIÓN (la tool garantiza su precondición). El 4B
        # a veces llama window(action='open', query='<sitio>') para "abrir una
        # página" — pero `window` no abre páginas (no tiene 'open'). En vez de un
        # error duro (que en movilidad/no_vidente deja la tarea trabada), si el
        # arg parece una URL o un sitio/tienda, lo abrimos en el navegador por
        # defecto (web_open_url, que SIEMPRE funciona). Si parece el nombre de una
        # APP, delegamos a app.open. Mismo patrón que browser.open->app.open.
        if action == "open":
            target = str(args.get("url") or args.get("query") or args.get("title")
                         or args.get("name") or "").strip()
            looks_url = bool(target) and (
                target.lower().startswith(("http://", "https://"))
                or bool(re.search(r"[a-z0-9-]+\.[a-z]{2,}(/|$|\?)", target, re.IGNORECASE)))
            if looks_url:
                # Es una URL/dominio explícito -> abrir en el navegador por defecto.
                r = self.web_open_url({"url": target})
                r.update(delegated_from="window.open", completion_status="opened_url")
                return r
            # No es una URL (p.ej. "Instant Gaming", "youtube"): NO adivinamos el
            # dominio (el 4B le erraría el TLD). Devolvemos un error ACCIONABLE que
            # lo reencamina a la herramienta correcta — que para un sitio sin URL
            # exacta es web(search) -> browser.open (ver browser.md). En movilidad/
            # no_vidente, la guarda de continuación re-promptea con esto.
            return _err(
                "window no abre páginas web", action=action, target=target[:60],
                status="needs_verification",
                hint=("Para abrir un SITIO web nombrado (sin URL exacta), primero "
                      "web(action='search', query='<sitio>') para obtener la URL "
                      "real, luego browser(action='open', url=<esa URL>). Para una "
                      "URL exacta, browser(action='open', url=...). window solo "
                      "controla ventanas (focus/close/minimize/...)."),
            )
        return _err("unknown window action", action=action,
                    hint="window solo controla VENTANAS (focus/close/minimize/...). "
                         "Para abrir una PÁGINA web usá browser/open_url; para una "
                         "APP usá app.open.")

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
            key_args = dict(args)
            key_args["keys"] = args.get("keys") or args.get("hotkey") or ""
            return self.gui_keypress(key_args)
        if action == "scroll":
            return self.gui_scroll(args)
        if action == "drag":
            return self.gui_drag(args)
        return _err("unknown gui mutating action", action=action)

    # Acciones GUI que MUEVEN el mouse o TECLEAN (control físico). La guarda de
    # actividad del usuario aplica a todas; la de password solo a las que teclean.
    _GUI_PHYSICAL = {"click", "double_click", "right_click", "type", "type_into",
                     "click_button", "keypress", "hotkey", "scroll", "drag"}
    _GUI_TYPING = {"type", "type_into"}

    def t_gui(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="screenshot")
        if action == "screenshot":
            return self.gui_screenshot(args)
        if action == "open":
            target = str(args.get("target") or args.get("name") or args.get("query")
                         or args.get("app") or "").strip()
            if not target:
                return _err("gui.open requiere target/name; para abrir apps usa app.open",
                            action=action, status="needs_user")
            result = self.t_app({"action": "open", "name": target,
                                 "refresh": args.get("refresh", False)})
            if isinstance(result, dict):
                result.setdefault("routed_from", "gui.open")
                result.setdefault("routed_to", "app.open")
            return result
        # GUARDAS Fase 5 (antes de cualquier control físico):
        #  (a) no pelear el mouse/teclado si el usuario está activo ahora;
        #  (b) no teclear en campos de contraseña (secret handoff).
        if action in self._GUI_PHYSICAL:
            try:
                # (0) cap de acciones físicas por turno (anti pop-up/injection)
                _bud = gui_safety.check_action_budget()
                if _bud is not None:
                    _bud["action"] = action
                    return _bud
                _blk = gui_safety.check_user_activity()
                if _blk is not None:
                    _blk["action"] = action
                    return _blk
                if action in self._GUI_TYPING:
                    _pwd = gui_safety.check_password_field()
                    if _pwd is not None:
                        _pwd["action"] = action
                        return _pwd
                gui_safety.note_action()  # consume 1 del presupuesto del turno
            except Exception:
                pass
        if action == "click" and (args.get("x") is None or args.get("y") is None):
            label = str(args.get("label") or args.get("target") or args.get("text") or "").strip()
            if label:
                click_args = dict(args)
                click_args["label"] = label
                return self.gui_click_button(click_args)
            return _err("gui.click sin coordenadas requiere label/target/text",
                        action=action, status="needs_user")
        if action == "type_into":
            return self.gui_type_into(args)
        if action == "click_button":
            return self.gui_click_button(args)
        if action in self._GUI_MUTATING:
            # verify_post_action: capturar ROI antes -> actuar -> verificar que el
            # SO cambió. Anota state_changed en el result (honestidad: el agente
            # deja de creer que hizo algo que no hizo). Best-effort, nunca rompe.
            try:
                _x = args.get("x"); _y = args.get("y")
                _before = gui_verify.capture_before(
                    int(_x) if _x is not None else None,
                    int(_y) if _y is not None else None)
            except Exception:
                _before = None
            result = self._gui_dispatch_raw(action, args)
            try:
                if _before is not None and isinstance(result, dict) and result.get("ok"):
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
            # Añade screen_x/screen_y (pre-traducidos) a cada match para que el
            # LLM pueda clickear sin re-aplicar shot.left/top. center_x/center_y
            # siguen siendo image-local.
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

    def t_computer_use(self, args: dict[str, Any]) -> dict[str, Any]:
        """Tool UNIVERSAL de operación-en-app (rediseño 2026-05-25): ahora es UNA
        tool más del registry — el router la ofrece y el LLM la llama con `goal`, en
        vez del short-circuit pre-LLM que secuestraba turnos. Internamente: el 4B
        planifica primitivas (plan_for) y el PlanExecutor las ejecuta verificando por
        estado del SO. Devuelve un result normal (ok/steps/...) como cualquier tool.
        El planner del agente vive en computer_use.py; el agente backref da los
        helpers (focus/título/quick-switcher) que el executor reusa."""
        goal = str(args.get("goal") or args.get("text") or args.get("target") or "").strip()
        if not goal:
            return _err("computer_use requiere 'goal' (el objetivo en lenguaje natural)",
                        status="needs_user")
        agent = getattr(self, "parent_agent", None)
        if agent is None:
            return _err("computer_use no disponible (sin agente)", status="failed")
        try:
            from ..computer_use_pkg.computer_use import plan_for, PlanExecutor, summarize_result
            # PLAN DETERMINISTA (accesibilidad): el caller puede pasar un plan ya
            # construido (`steps`) para los casos estructurados claros (p.ej.
            # "escribí X en app Y" -> [focus_app(Y), type(X)]) y NO depender del 4B
            # planner, que MEDIDO devuelve plan vacío o mete toda la frase como texto.
            # Si no hay steps, planifica el 4B (caminos abiertos: nav multi-paso, etc.).
            plan = args.get("steps") or args.get("plan")
            if not (isinstance(plan, list) and plan and all(isinstance(s, dict) for s in plan)):
                plan = plan_for(agent, goal)
            if not plan:
                return _err("no pude planificar la acción", goal=goal[:60], status="failed")
            result = PlanExecutor(agent).execute(plan, "cu_tool")
            reply = summarize_result(goal, plan, result)
            verified = bool(result.get("ok")) and bool(result.get("verified", result.get("ok")))
            return _ok(action="computer_use", goal=goal[:80],
                       ops=[s["op"] for s in plan], steps=result.get("steps"),
                       verified=verified,
                       completion_status="done" if verified else "attempted",
                       reply=reply)
        except Exception as exc:
            return _err(f"computer_use falló: {exc}", goal=goal[:60], status="failed")

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
        # monitor ACTIVO por default (default "all"=panorámica que el 2B aluvina).
        _shot_args = dict(args)
        if not str(args.get("monitor") or "").strip():
            _shot_args["monitor"] = "active"
        shot = self.gui_screenshot(_shot_args)
        shot["vision_action"] = action
        shot["target"] = args.get("target") or args.get("text")
        # describe directo con ancla OCR (vision_describe.py); ocr_fn lee el OCR allí.
        described = self._describe_image_directly(
            shot.get("image_path"),
            str(args.get("target") or args.get("text") or "").strip(),
            ocr_fn=self.t_vision)
        if described:
            shot["description"] = described
            shot["completion_status"] = "screen_described"
            shot["note"] = "Pantalla descrita por visión (texto en `description`)."
        else:
            shot["note"] = "Screenshot captured and re-injected as Gemma 4 image input for native visual reasoning."
        return shot

    def _describe_image_directly(self, image_path: Any, focus: str = "",
                                 ocr_text: str = "", ocr_fn: Any = None) -> str | None:
        from .vision_describe import describe_image  # extraído 2026-06-07
        return describe_image(getattr(self, "parent_agent", None), image_path,
                              focus, ocr_text, ocr_fn=ocr_fn)

    def t_browser(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="open")
        query = str(args.get("query") or "").strip()
        browser = str(args.get("browser") or "").strip()
        # RED DE HONESTIDAD (mismo patrón que t_steam): "¿Chrome está abierto?" -> el
        # 4B elige browser(open) -> abría el navegador y MENTÍA "Listo, abrí Chrome".
        # Una pregunta de ESTADO no debe ABRIR. Si el texto del turno es pregunta de
        # estado Y no trae una URL/query real, reportar si el navegador corre, no abrir.
        if action == "open" and not query and not str(args.get("url") or args.get("target") or "").strip():
            _ut = (getattr(self, "_current_user_text", "") or "").strip()
            try:
                from ..routing.planner import _is_app_state_check as _isc
            except Exception:
                _isc = None
            if _ut and _isc and _isc(_ut):
                try:
                    _names = _running_process_names()
                    # nombre del navegador a buscar: el que nombró el user, o
                    # cualquiera de los conocidos si no nombró ninguno.
                    _br = browser.lower()
                    if _br:
                        _running = any(_br in n for n in _names)
                    else:
                        _running = any(b in n for n in _names
                                       for b in ("chrome", "msedge", "firefox", "brave", "opera"))
                except Exception:
                    _running = None
                return _ok(action="status", app=(browser or "navegador"), running=_running,
                           completion_status="reported_state_did_not_open",
                           note="pregunta de estado: NO abrí el navegador, reporté si corre")
        if action == "open":
            # Aliases para `url` que el 4B usa frecuentemente (caso medido: el
            # modelo pasó `target:"canvas"` y la tool devolvía needs_user porque
            # solo leía url/query). El schema DECLARA `target` como propiedad
            # pero el handler lo ignoraba — inconsistencia schema↔handler que se
            # corrige leyendo el alias acá. También aceptamos
            # `site`/`domain` (formas que el 4B inventa por la descripción del
            # schema). OJO: NO incluimos `name` aquí porque más abajo el
            # bloque LAUNCH-THE-APP usa `name` para "lanzá Chrome" (donde name
            # es la app navegador, no una URL). Orden: url > target > site >
            # domain > query.
            url = (str(args.get("url") or "").strip()
                   or str(args.get("target") or "").strip()
                   or str(args.get("site") or "").strip()
                   or str(args.get("domain") or "").strip()
                   or query)
            # SITE-NAME -> RESOLVER POR BÚSQUEDA (2026-05-27): "ve a la página de
            # pivigames" da un NOMBRE de sitio, no una URL. Si el target es una
            # palabra suelta (sin punto ni esquema), lo resolvemos con una búsqueda
            # REAL — NO adivinamos el TLD (resolver por lookup). Guardamos
            # el nombre original para el reporte; `url` queda con la URL resuelta.
            _resolved_from = None
            # ¿el target es algo que hay que RESOLVER por búsqueda (no abrir a ciegas)?
            # Dos casos (bug medido 2026-06-07 "ve a pivigames" -> abrió pivigames.com
            # INVENTADO; el real es pivigames.blog):
            #   (a) nombre PELADO ("pivigames", sin punto) — el caso original;
            #   (b) DOMINIO ADIVINADO por el 4B ("pivigames.com"): una sola etiqueta
            #       + TLD genérico, SIN path ni subdominio. El modelo le pega ".com"
            #       a cualquier nombre; no es prueba de que el dominio exista. Lo
            #       verificamos por búsqueda igual. NO tocamos: URLs con path, con
            #       www/subdominio, ni dominios obviamente reales (allowlist corta).
            _bare_name = (url and not url.startswith(("http://", "https://"))
                          and "." not in url and "/" not in url
                          and len(url) >= 3 and len(url.split()) <= 4)
            # PROCEDENCIA (fix 2026-06-07, approach B): el 4B emite la URL COMPLETA
            # "https://www.pivigames.com/" adivinando el .com. No se puede distinguir
            # de un dominio real POR LA FORMA (google.com y pivigames.com son iguales).
            # La señal de adivinanza es la PROCEDENCIA: si el comando fue "ve a pivigames"
            # (el NOMBRE) pero NUNCA dijo "pivigames.com" -> el dominio+TLD NO aparece
            # en su texto -> el modelo lo inventó -> resolver por búsqueda. Si el user
            # SÍ tipeó/dictó el dominio ("andá a lanacion.com") -> abrir directo (cero
            # latencia). Mismo patrón que el grounding del teléfono de WhatsApp.
            _guessed_domain = False
            _lookup = url
            if url and not _bare_name:
                _reg = _registrable_label(url)   # (sld, tld) o None si tiene path real
                if _reg:
                    _sld, _tld = _reg
                    _dom = f"{_sld}.{_tld}"
                    _ut_low = (getattr(self, "_current_user_text", "") or "").lower()
                    # ADIVINADO si el dominio completo NO aparece en el texto del user
                    # (el 4B le puso el .com) -> resolver por búsqueda. Si el user SÍ
                    # lo dictó -> directo (cero latencia, intención explícita).
                    if _dom not in _ut_low:
                        _guessed_domain = True
                        _lookup = _sld   # buscar por el nombre, sin el TLD inventado
            if url and (_bare_name or _guessed_domain):
                resolved = self._resolve_site_by_search(_lookup)
                # Guard de honestidad (como app.open): aceptar solo si el sitio
                # resuelto guarda relación estructural con el nombre.
                if resolved and _site_resolution_relevant(_lookup, resolved):
                    _resolved_from, url = url, resolved
                elif _guessed_domain:
                    # dominio ADIVINADO + búsqueda sin resultado -> NO abrir el
                    # inventado (bug 've a portal uniej'->portalunab.mx inexistente).
                    return _err(
                        f"no encontré el sitio de «{_lookup}»; el dominio que se "
                        f"formó ({url}) puede no existir y no quiero abrir una "
                        f"página equivocada",
                        status="needs_user", action="open",
                        attempted_name=_lookup, attempted_url=url,
                        completion_status="site_not_resolved")
                # _bare_name sin resolver (no adivinado) -> url queda como estaba.
            if url.startswith(("http://", "https://")):
                try:
                    from .site_resolver import user_requested_open as _uro
                    _ut = getattr(self, "_current_user_text", "") or ""
                    if not _uro(url, _ut):
                        _rr = self.web_read({"url": url})
                        if isinstance(_rr, dict):
                            _rr.setdefault("redirected_from", "browser.open")
                            _rr["action"] = "read"
                            _rr["opened"] = False
                            _rr["note"] = (
                                "browser.open sin pedido de VER -> no abrí navegador; "
                                "leí el contenido para responder."
                            )
                        return _rr
                except Exception:
                    pass
            # ABRIR EN UN NAVEGADOR ESPECÍFICO (2026-05-27): "pon X en Opera" trae
            # browser="Opera"+url -> lanzar ESE navegador con la URL y verificar su
            # ventana. Si no se resuelve -> default con nota honesta (no fingir).
            if browser and url.startswith(("http://", "https://")):
                _b = self._open_url_in_browser(browser, url)
                if _b is not None:
                    if _resolved_from:
                        _b.update(resolved_from_name=_resolved_from, resolved_url=url)
                    return _b
                # no se pudo abrir en ESE navegador -> default + nota honesta abajo.
            if _resolved_from:
                res = self.web_open_url({"url": url})
                res.update(
                    resolved_from_name=_resolved_from, resolved_url=url,
                    method="search_top_result",
                    note=f"'{_resolved_from}' no es un dominio; resolví por búsqueda a {url} y lo abrí.",
                )
                if browser:
                    res["browser_note"] = (
                        f"No pude abrir en {browser} específicamente; lo abrí en tu navegador por defecto.")
                return res
            if not url:
                # LAUNCH-THE-APP fallback: el modelo chico (E4B-Q4) interpreta
                # "lanzá Chrome" / "abrí Firefox" como browser.open con
                # browser/name="Chrome" y SIN url — porque "Chrome" es un
                # navegador. La intención real es LANZAR el programa, no navegar.
                # En vez de devolver needs_user (que el modelo convierte en "no
                # puedo abrir Chrome sin URL"), delegamos a app.open: hacemos la
                # acción real. No es un hardcode de routing ni una respuesta
                # enlatada — es la tool garantizando su precondición cuando el arg nombra una app y falta el url. La regla en
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
            if browser:
                # se pidió un navegador específico pero llegamos al default
                # (no se pudo abrir en ése): nota honesta, no fingir.
                result["browser_note"] = (
                    f"No pude abrir en {browser} específicamente; lo abrí en tu navegador por defecto.")
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
                extracted = {}
            else:
                url = f"https://www.google.com/search?q={quote_plus(query)}"
                # browser.search antes solo abría Google y dejaba al 4B sin los
                # URLs reales en el historial; en movilidad/no_vidente eso
                # terminaba en "verifica/elegí el resultado". Extraemos resultados
                # estructurados en paralelo a abrir la página para que el siguiente
                # paso pueda hacer browser.open(top_result_url) sin delegar.
                try:
                    extracted = self.web_search({
                        "query": query,
                        "limit": int(args.get("limit", 5) or 5),
                    })
                except Exception as exc:  # noqa: BLE001
                    extracted = {"ok": False, "error": f"web_search failed: {type(exc).__name__}: {exc}"}

            def _with_search_results(res: dict[str, Any]) -> dict[str, Any]:
                if not isinstance(extracted, dict):
                    return res
                results = extracted.get("results") or []
                if results:
                    top = results[0]
                    top_url = str(top.get("url") or "")
                    res.update(
                        action="search",
                        query=query,
                        search_results=results,
                        top_result=top,
                        top_result_url=top_url,
                        search_verified=bool(extracted.get("verified") or extracted.get("content_verified")),
                        content_verified=True,
                        completion_status="opened_search_results_with_extracted_results",
                        next_step_hint=(
                            "If the user asked to open a named site/page, call "
                            "browser(action='open', url=top_result_url). Do not ask "
                            "the user to inspect or choose unless the results are truly ambiguous."
                        ),
                    )
                elif extracted:
                    res["search_results_error"] = extracted.get("error") or extracted.get("message")
                return res
            if browser and not browser_is_youtube_app:
                # ANTES (bug 2026-05-27): abría el navegador y tecleaba la URL con
                # gui_keypress/gui_type (SendInput) — FRÁGIL (race de foco -> "stuck
                # at attempted") y PELIGROSO (el SendInput va a la ventana enfocada;
                # cerraba la app en foco). Ahora lanzamos el navegador CON la URL como
                # argumento (navega ahí, sin SendInput) vía _open_url_in_browser, que
                # además verifica la ventana. Si no se puede, default honesto.
                b = self._open_url_in_browser(browser, url)
                if b is not None:
                    return _with_search_results(b)
                result = self.web_open_url({"url": url})
                result["browser_note"] = (
                    f"No pude abrir en {browser} específicamente; usé tu navegador por defecto.")
                result.update(action="search", query=query, content_verified=False,
                              completion_status="opened_search_results")
                return _with_search_results(result)
            result = self.web_open_url({"url": url})
            result.update(action="search", query=query,
                          content_verified=False, completion_status="opened_search_results")
            return _with_search_results(result)
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
            _open_url = str(args.get("url") or "").strip()
            if not _open_url:
                return _err("web.open requires url", status="needs_user")
            # GUARD conocimiento-vs-abrir (2026-06-08): "háblame de X" -> web.open de un
            # tab fallido en vez de RESPONDER -> si el user no dictó el dominio, leer y responder (PROCEDENCIA, site_resolver.user_requested_open).
            try:
                from .site_resolver import user_requested_open as _uro
                _ut = getattr(self, "_current_user_text", "") or ""
                if not _uro(_open_url, _ut):
                    _rr = self.web_read({"url": _open_url})
                    if isinstance(_rr, dict):
                        _rr.setdefault("redirected_from", "web.open")
                        _rr["action"] = "read"
                        _rr["opened"] = False
                        _rr["note"] = "web.open sin pedido de VER -> no abrí navegador; leí el contenido."
                    return _rr
            except Exception:
                pass
            return self.web_open_url(args)
        if action == "read":
            if not str(args.get("url") or "").strip():
                _read_query = str(args.get("query") or "").strip()
                if _read_query:
                    _rr = self.web_research({
                        "query": _read_query,
                        "search_limit": args.get("search_limit", args.get("limit", 6)),
                        "read_limit": args.get("read_limit", 3),
                        "per_page_chars": args.get("per_page_chars", args.get("max_chars", 4500)),
                    })
                    if isinstance(_rr, dict):
                        _rr.setdefault("redirected_from", "web.read")
                        _rr["note"] = (
                            "web.read requiere url; vino query, así que ejecuté "
                            "web.research para buscar y leer fuentes."
                        )
                    return _rr
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
            # ANCHOR-BINDING: no clickear bait de pop-up no relacionado al
            # objetivo del turno (label frase-larga + cosine bajo). Conservador.
            try:
                _anc = gui_safety.check_anchor(str(args.get("query") or args.get("text")
                                                   or args.get("target") or ""))
                if _anc is not None:
                    _anc["action"] = "uia.click"
                    return _anc
            except Exception:
                pass
            # CASCADA Fase 3 en uia.click (el tool que el agente elige para
            # "clic en X"). En ventanas CHROMIUM/CEF (Edge/Chrome/Electron) el
            # árbol UIA del contenido web es inconsistente y el InvokePattern del
            # proxy NO dispara el onclick del DOM (verificado: matchea un nodo y
            # el click no tiene efecto). La investigación (síntesis §1) dice que
            # OCR/coordenada es más fiable que el AX del CEF -> en Chromium vamos
            # DIRECTO a OCR (no doble-acción: el UIA invoke no haría nada útil).
            # Fuera de Chromium: UIA primero, y si el match fue débil (sin
            # elemento / nameless) caer a OCR.
            label = str(args.get("query") or args.get("text")
                        or args.get("target") or "").strip()
            try:
                if label and self._foreground_is_chromium(str(args.get("window") or "")):
                    ocr_res = self._click_button_via_ocr(label, args)
                    if ocr_res is not None and ocr_res.get("ok"):
                        ocr_res["grounding"] = "ocr"
                        ocr_res["cascade"] = "chromium_direct_ocr"
                        return ocr_res
                    # si OCR no halló el label, seguimos al camino UIA (best-effort)
            except Exception:
                pass
            res = self.uia_click(args)
            try:
                el_name = (res.get("element") or {}).get("name") if isinstance(res, dict) else None
                method = res.get("method") if isinstance(res, dict) else None
                weak = (not res.get("ok")) or (not el_name)
                if label and weak:
                    ocr_res = self._click_button_via_ocr(label, args)
                    if ocr_res is not None and ocr_res.get("ok"):
                        ocr_res["uia_first"] = {"ok": res.get("ok"), "method": method,
                                                "element": el_name}
                        return ocr_res
            except Exception:
                pass
            return res
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

    def _resolve_steam_appid(self, query: str) -> dict[str, Any] | None:
        """Resolve a game NAME to a Steam AppID via the local-then-store cascade.

        Returns {"appid", "match", "source"} or None when nothing resolves.
        Shared by store_page and install so both use the SAME resolution: first
        the local Steam library metadata (instant, offline), then a real Steam
        store search (network). Kept as one method so the two call sites can
        never drift apart. Does NOT take an explicit appid — callers that have
        one should short-circuit before calling this.
        """
        if not query:
            return None
        local_matches = self.apps.find_steam_library(query, limit=5)
        if local_matches:
            best = local_matches[0]
            local_appid = _steam_appid_from_launch(best.launch)
            if local_appid:
                return {"appid": local_appid, "match": best.as_dict(), "source": best.source}
        store_match = _steam_store_first_result(query)
        if store_match:
            return {"appid": store_match["appid"], "match": store_match, "source": "steam_store_search"}
        return None

    def steam_store_page(self, args: dict[str, Any], query: str) -> dict[str, Any]:
        appid = str(args.get("appid") or "").strip()
        matched: dict[str, Any] | None = None
        source = "explicit_appid" if appid else ""

        # ANTI-APPID-INVENTADO (2026-06-10): el 4B a veces alucina un appid
        # placeholder ("1234567890", "123456789") en vez de pasar la query ->
        # store_page abría steam://store/<basura> -> "steam failed". Si HAY query,
        # la resolución por nombre (biblioteca local -> store real) es CONFIABLE;
        # el appid del LLM NO. Regla: con query presente, RESOLVER por query y usar
        # ese appid; el del LLM solo se honra si coincide o si no hay query. Además
        # se descarta un appid que parezca inventado (placeholder evidente).
        if appid and (_is_placeholder_appid(appid) or query):
            resolved = self._resolve_steam_appid(query) if query else None
            if resolved:
                # query resolvió: ese appid manda (el del LLM era inventado o redundante).
                appid = resolved["appid"]
                matched = resolved.get("match")
                source = resolved.get("source", "")
            elif _is_placeholder_appid(appid):
                # sin resolución y el appid es claramente basura -> tratarlo como ausente.
                appid = ""
                source = ""

        if not appid:
            resolved = self._resolve_steam_appid(query)
            if resolved:
                appid = resolved["appid"]
                matched = resolved.get("match")
                source = resolved.get("source", "")

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
        res = email_tool(args, self.state)
        # FALLBACK SIN TOKEN (2026-05-27): email_tool arma la URL de compose de
        # Gmail cuando no hay Graph token; acá (que SÍ tenemos el browser) la
        # abrimos de verdad con la sesión logueada del usuario. NO envía: abre
        # el redactor pre-rellenado para que el usuario confirme y mande. Es la
        # vía universal para alguien sin manos (cero setup, sin token).
        if isinstance(res, dict) and res.get("fallback") == "gmail_web_compose" \
                and res.get("compose_url"):
            opened = self.web_open_url({"url": str(res["compose_url"])})
            res = {**res, **{k: v for k, v in opened.items()
                             if k not in ("ok",)}}
            res["ok"] = bool(opened.get("ok", res.get("ok")))
            res["opened_compose"] = bool(opened.get("ok"))
        return res

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
        enriched = dict(args)
        enriched["_user_text"] = getattr(self, "_current_user_text", "") or ""
        return media_tool(enriched, self.execute, self.state)

    def t_source_manager(self, args: dict[str, Any]) -> dict[str, Any]:
        return source_manager_tool(args, self.state)

    def t_dependency(self, args: dict[str, Any]) -> dict[str, Any]:
        return dependency_tool(args)

    def t_contacts(self, args: dict[str, Any]) -> dict[str, Any]:
        return contacts_tool(args, self.state)

    def t_whatsapp(self, args: dict[str, Any]) -> dict[str, Any]:
        # LEER mensajes (2026-05-27, no-vidente): el tool de WhatsApp solo ENVÍA.
        # Para "leeme el último mensaje / qué me escribió X" el 4B a veces rutea a
        # whatsapp con una acción de lectura (read/read_messages/last/unread...).
        # No existe scraping de WhatsApp; lo UNIVERSAL es LEER LA PANTALLA por
        # visión (sirve para cualquier chat). Delegamos a vision.describe_screen
        # con foco en los mensajes — garantía de outcome, no respuesta enlatada.
        _act = str(args.get("action") or "").casefold()
        if _act in {"read", "read_message", "read_messages", "read_chat",
                    "last_message", "unread", "list_messages", "get_messages"}:
            return self.t_vision({
                "action": "describe_screen",
                "target": "los mensajes de chat visibles; leé en voz el/los "
                          "último(s) mensaje(s): quién lo envió y qué dice",
            })
        # REDIRECCIÓN A EMAIL (2026-05-27, bug medido en vivo): el 4B a veces rutea
        # "mandale un correo a ana@gmail.com" a whatsapp con contact="ana@gmail.com"
        # (o "un correo a ana@gmail.com"). Un destinatario con '@...' (dominio) es un
        # EMAIL, no un chat de WhatsApp. Lo redirigimos a la tool email (abre el
        # redactor de Gmail pre-rellenado) — garantía de outcome a nivel de tool,
        # como network->device_settings. Solo si el destinatario parece email real.
        import re as _re
        _rcpt = " ".join(str(args.get(k) or "") for k in ("contact", "to", "recipient", "name", "phone"))
        _m = _re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", _rcpt)
        _body = str(args.get("text") or args.get("body") or args.get("message") or "").strip()
        if _act in {"send_message", "send", ""} and _m:
            _to = _m.group(0)
            res = self.t_email({"action": "send", "to": _to, "body": _body})
            if isinstance(res, dict):
                res.setdefault("delegated_from", "whatsapp(email-recipient)")
            return res
        # ABRIR LA APP (no un chat): "abre whatsapp" — el 4B a veces elige el tool
        # whatsapp en vez de app.open (MEDIDO en el replay 2026-05-30), pero
        # whatsapp_tool SOLO abre CHATS (necesita contacto/teléfono) y fallaría.
        # Sin destinatario NI mensaje, la intención es abrir la APP → delegamos a
        # app.open (mismo patrón que la redirección a email). `status` sí va al tool.
        if _act not in {"status"} and not _rcpt.strip() and not _body:
            res = self.t_app({"action": "open", "name": "WhatsApp"})
            if isinstance(res, dict):
                res.setdefault("delegated_from", "whatsapp(open-app)")
            return res
        # GROUNDING DE PROCEDENCIA DEL TELÉFONO (C1 "destinatario equivocado =
        # daño irreversible", 2026-05-30). Cuando el user NO da destinatario
        # ("manda un mensaje por wsp") el 4B a veces ALUCINA un número placeholder
        # (caso real: phone='+34 123456' -> WhatsApp abre y muestra "el
        # número +34 123456 no está en WhatsApp"). El 4B NO tiene la base de
        # contactos: un `phone=` que emite es, o bien lo que el user DICTÓ, o bien
        # inventado. Guarda ESTRUCTURAL que mide la FORMA (no keyword-lists ni
        # idioma): el teléfono explícito es de fiar solo si el user dictó esos
        # dígitos en su mensaje (solapamiento bidireccional tolera que el 4B
        # complete el código de país). Si no -> está fabricado -> NO abrir un chat
        # con basura: soltar el número y resolver por nombre si hay, o PREGUNTAR.
        # Solo activo si el agente plumeó el texto del turno (sin él = no-op, igual
        # que antes — no rompe tests/CLI que no lo setean).
        _ut = (getattr(self, "_current_user_text", "") or "").strip()
        _phone_arg = str(args.get("phone") or args.get("number") or "").strip()
        if _ut and _phone_arg and _act in {"send_message", "send", "open_chat", ""}:
            _pd = _re.sub(r"\D", "", _phone_arg)
            _ud = _re.sub(r"\D", "", _ut)
            _grounded = bool(_pd) and len(_ud) >= 6 and (_pd in _ud or _ud in _pd)
            if not _grounded:
                _name_alt = str(args.get("contact") or args.get("recipient")
                                or args.get("to") or args.get("name") or "").strip()
                if _name_alt:
                    # Hay un nombre alternativo: soltar el teléfono fabricado y
                    # dejar que el resolver use el nombre (contacto / GUI search).
                    args = {k: v for k, v in args.items()
                            if k not in ("phone", "number")}
                else:
                    # Sin destinatario real: pedirlo. El LLM formula la pregunta en
                    # el idioma del user; status=needs_user la gatea. NUNCA mandar
                    # a un número inventado.
                    return {
                        "ok": False, "status": "needs_user", "provider": "whatsapp",
                        "error": "no me dijiste a quién mandarle el mensaje",
                        "hint": ("Faltó el destinatario: preguntá al usuario a quién "
                                 "mandar el mensaje (nombre de contacto o número con "
                                 "código de país). NUNCA inventes ni uses un número "
                                 "de ejemplo como +34 123456."),
                        "fabricated_phone": _phone_arg,
                    }
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
        # BRILLO DE PANTALLA (2026-05-27): el brillo vive en `system`
        # (brightness_get/set), pero el modelo chico lo pide de forma natural por
        # `device_settings` (es un ajuste de pantalla). En vez de fallar ("no
        # tengo herramienta para el brillo"), delegamos a la impl real de system
        # — garantía de precondición, mismo patrón que browser.open->app.open.
        # Un usuario con baja visión sube/baja el brillo por voz sin saber en qué
        # tool vive. Acepta variantes que el 4B inventa (brightness_up/down/set).
        _act = str(args.get("action") or "").casefold()
        if _act in {"brightness_get", "get_brightness", "brightness_status"}:
            return self.system_brightness_get(args)
        if _act in {"brightness_set", "set_brightness", "brightness",
                    "brightness_up", "brightness_down", "set_screen_brightness"}:
            a = dict(args)
            # mapear up/down a un delta si no vino un nivel explícito
            if _act == "brightness_up" and "level" not in a and "delta" not in a:
                a["delta"] = 20
            elif _act == "brightness_down" and "level" not in a and "delta" not in a:
                a["delta"] = -20
            res = self.system_brightness_set(a)
            if isinstance(res, dict):
                res.setdefault("delegated_from", "device_settings." + _act)
            return res
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

    def t_file_process(self, args: dict[str, Any]) -> dict[str, Any]:
        """B6: file-processor unificado. Detecta el tipo del archivo (por extensión) y
        DELEGA al procesador correcto (data_analysis/document/vision-OCR) vía execute(),
        sin que el 4B tenga que elegir. Patrón "analizá este archivo" (Mark-XXXIX).
        Gated GEMMA4_FILE_PROCESSOR. Guarda estructural (extensión, sin LLM/keywords)."""
        from ..domain_tools.file_process import (
            detect_file_kind, plan_for_kind, file_processor_enabled,
        )
        if not file_processor_enabled():
            return _err("file_process disabled (set GEMMA4_FILE_PROCESSOR=1)", status="needs_user")
        raw = str(args.get("path") or args.get("file") or "").strip()
        p = Path(raw).expanduser() if raw else None
        if not raw or p is None or not p.is_file():
            return _err(f"file not found: {raw!r}", status="needs_user")
        kind = detect_file_kind(p)
        plan = plan_for_kind(kind)
        if plan is None:
            return _err(
                f"file_process: tipo '{kind}' ({p.suffix}) no auto-procesable todavía",
                status="needs_user", file_kind=kind, path=str(p))
        tool, action, path_arg = plan
        result = self.execute(tool, {"action": action, path_arg: str(p)})
        if isinstance(result, dict):
            result.setdefault("file_process", {"kind": kind, "delegated_to": f"{tool}.{action}"})
        return result

    def t_mcp(self, args: dict[str, Any]) -> dict[str, Any]:
        """B9: tool puente a servidores MCP (Model Context Protocol). Gated
        GEMMA4_MCP. action=list descubre las tools de los servidores declarados;
        action=call ejecuta una tool MCP. UNA tool puente (no N tools en el catálogo)
        para no inflar el subset del 4B (R7)."""
        from .mcp_client import mcp_enabled, discover_mcp_tools, call_mcp_tool
        if not mcp_enabled():
            return _err("MCP disabled (set GEMMA4_MCP=1 and configure ~/.gemma4/mcp_servers.json)",
                        status="needs_user")
        action = str(args.get("action") or "list").casefold()
        if action == "list":
            tools = discover_mcp_tools()
            return _ok(
                tools=[{"server": t["server"], "name": t["name"],
                        "description": t["description"]} for t in tools],
                count=len(tools))
        if action == "call":
            server = str(args.get("server") or "").strip()
            tool = str(args.get("tool") or args.get("name") or "").strip()
            if not server or not tool:
                return _err("mcp call needs 'server' and 'tool'", status="needs_user")
            return call_mcp_tool(server, tool, args.get("arguments") or args.get("args") or {})
        return _err("unknown mcp action", valid_actions=["list", "call"], status="needs_user")

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
            # Confirmación REAL del usuario (round-trip): re-ejecuta con el canal
            # INTERNO `_confirmed_by_gate` (no `confirmed`, que el LLM podría falsificar)
            # → execute() lo reconoce como confirmación válida y saltea el gate.
            result = self.execute(str(item["tool"]),
                                  {**dict(item.get("args") or {}), "_confirmed_by_gate": True})
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
        # psutil+nvidia-smi ~57ms vs ~2.4s WMI -> system_info_fast.py (ratchet dios).
        from .system_info_fast import cpu_ram_gpu as _cpu_ram_gpu
        res = _cpu_ram_gpu()
        if res.get("ok"):
            return _ok(info=res["info"], source=res.get("source"))
        return _err(str(res.get("error") or "system_cpu_ram_gpu failed"),
                    **{k: v for k, v in res.items() if k not in ("ok", "error")})

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

    @staticmethod
    def _extract_brightness_level(raw: Any) -> int | None:
        """Normaliza lo que devuelve WmiMonitorBrightness a un entero 0..100.
        Puede venir como int, {"CurrentBrightness": N}, o lista de esos (varios
        monitores -> tomamos el primero). None si no se puede leer."""
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        if isinstance(raw, dict):
            raw = raw.get("CurrentBrightness")
        if isinstance(raw, bool):
            return None
        if isinstance(raw, (int, float)):
            return int(raw)
        return None

    def system_brightness_set(self, args: dict[str, Any]) -> dict[str, Any]:
        # DELTA relativo (2026-05-27): "subí/bajá el brillo" sin un número -> el 4B
        # manda delta=+/-N. Leemos el nivel actual y aplicamos el delta (clamp
        # 0..100). Sin level ni delta, default 50. Esto hace "sube el brillo" por
        # voz funcione sin que el usuario tenga que decir un porcentaje exacto.
        if "level" not in args and args.get("delta") is not None:
            try:
                delta = int(args.get("delta"))
            except (TypeError, ValueError):
                delta = 0
            cur = self.system_brightness_get({})
            raw = cur.get("brightness")
            # brightness_get devuelve el objeto WMI crudo: puede ser un int, o
            # {"CurrentBrightness": N}, o una lista de esos (multi-monitor), o None.
            base = self._extract_brightness_level(raw)
            if base is None:
                base = 50  # monitor sin DDC/CI: arrancamos de un punto medio
            level = max(0, min(100, base + delta))
        else:
            level = max(0, min(100, int(args.get("level", 50))))
        script = f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return _err("system_brightness_set timeout", level=level, reason="wmi_unresponsive")
        if proc.returncode != 0:
            # (a) FALLO DEL SO honesto: WMI rechazó el set (monitor sin
            # WmiMonitorBrightnessMethods / sin DDC-CI). NO es un bug del agente;
            # es una limitación de hardware. _err con hint -> el reply dice "no se
            # puede en este monitor", no miente con un éxito.
            return _err(
                "brightness_set rejected by WMI",
                level=level, exit_code=proc.returncode,
                reason="wmi_unsupported",
                stderr=_truncate(proc.stderr.strip(), 1000),
                hint="WmiMonitorBrightness only works on laptops; desktop monitors need DDC/CI helper.",
            )
        # El set NO falló, pero WmiSetBrightness es fire-and-hope: en algunos
        # paneles el WMI acepta la llamada (returncode 0) y el brillo NO cambia.
        # Igual que audio_set_volume re-lee el endpoint, RE-LEEMOS el nivel post-set
        # y comparamos con lo pedido. Tri-estado honesto (mismo contrato que
        # keypress/audio/_DISPATCH_OK_COMPLETIONS):
        #   verified=True  -> medido y dentro de tolerancia (±5%): éxito real.
        #   verified=False -> medido y NO cambió: honesto, NO afirmamos éxito.
        #   verified=None  -> no medible (monitor sin DDC reporta null): dispatched,
        #                     "se envió pero no se pudo confirmar" (NO es fallo).
        post = self.system_brightness_get({})
        actual = self._extract_brightness_level(post.get("brightness"))
        if actual is None:
            # No se pudo RE-LEER el nivel (WmiMonitorBrightness null/ausente, aunque
            # el set no diera error). No medible != fallo: honesto verified=None.
            return _ok(
                level=level, requested=level, verified=None,
                status="dispatched",
                note="brightness set request sent but the level could not be re-read to confirm it changed.",
            )
        if abs(actual - level) <= 5:  # tolerancia ~5% (paneles cuantizan a pasos)
            return _ok(level=actual, requested=level, verified=True)
        # (b) Se intentó pero el panel NO aplicó el cambio: honesto, no afirmamos
        # éxito plano. verified=False -> el guard de honestidad no dirá "Listo".
        return _err(
            f"brightness set to {level} but monitor reports {actual}",
            level=actual, requested=level, verified=False,
            status="failed", reason="brightness_unchanged",
            hint="WMI accepted the call but the panel did not apply it; the monitor may not honor software brightness.",
        )

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
        raw = args.get("state")
        try:
            volume = self._audio_endpoint_volume()
            if raw is None:
                # El 4B a veces emite action='mute' SIN state (sobre todo al pedir
                # DESMUTEAR: "quitá el silencio"/"reactivá el sonido" — MEDIDO 2/3
                # fraseos de unmute omiten state). El viejo default True MUTEABA un
                # pedido de DESMUTEAR (lo opuesto). Sin state explícito → TOGGLE:
                # invertir el estado actual, lo intuitivo para un mute/unmute pelado.
                state = not bool(volume.GetMute())
            elif isinstance(raw, str):
                # El parser de leaks puede dar "false"/"true" como STRING, y
                # bool("false") daba True (mutea al pedir desmutear). Coerción real.
                state = raw.strip().lower() not in {"false", "no", "0", "off", ""}
            else:
                state = bool(raw)
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
        # LATENCIA (MEDIDO 2026-06-09): `Get-PnpDevice` PowerShell ~1.5s. Cache TTL
        # 60s (los dispositivos no cambian seguido); `refresh=True` revalida.
        _ttl = 60.0
        _now = time.time()
        if not args.get("refresh"):
            _c = getattr(self, "_audio_devices_cache", None)
            if _c and (_now - _c[0]) < _ttl:
                return _ok(devices=_c[1], source="cache", cached=True)
        script = "Get-PnpDevice -Class AudioEndpoint | Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Depth 3"
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
        self._audio_devices_cache = (_now, data)
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
                        from ..computer_use_pkg.win_focus import focus_and_maximize
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
                    # las reglas del proyecto #6); si no cierra, lo reportamos honestamente.
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
        # PRESET DIRECCIONAL (fix capacidad): el usuario dice "a la izquierda" /
        # "mitad derecha" / "lado a lado"; el LLM pasa `position` y el rect se
        # calcula contra el área de trabajo REAL de la pantalla (en el script PS,
        # que conoce el tamaño). Si no hay position, usa x/y/width/height crudos
        # (comportamiento previo, defaults 0/0/1000/700). Estructural, multi-idioma.
        _pos_raw = str(args.get("position") or args.get("preset") or "").strip().lower()
        _POS_MAP = {
            "izquierda": "left", "left": "left", "izq": "left",
            "derecha": "right", "right": "right", "der": "right",
            "arriba": "top", "top": "top", "abajo": "bottom", "bottom": "bottom",
            "mitad izquierda": "left", "mitad derecha": "right",
            "maximizar": "max", "maximizada": "max", "maximize": "max",
            "centro": "center", "center": "center", "centrar": "center",
        }
        position = ""
        for k, v in _POS_MAP.items():
            if k in _pos_raw:
                position = v
                break
        env["GEMMA4_POSITION"] = position
        env["GEMMA4_X"] = str(int(args.get("x", 0)))
        env["GEMMA4_Y"] = str(int(args.get("y", 0)))
        env["GEMMA4_W"] = str(int(args.get("width", 1000)))
        env["GEMMA4_H"] = str(int(args.get("height", 700)))
        script = r"""
$q=$env:GEMMA4_WINDOW_QUERY.ToLower()
$pos=$env:GEMMA4_POSITION
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool repaint);
}
"@
Add-Type -AssemblyName System.Windows.Forms
$wa = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$p = Get-Process | Where-Object { $_.MainWindowTitle -and $_.MainWindowTitle.ToLower().Contains($q) } | Select-Object -First 1
if (-not $p) { [PSCustomObject]@{ ok=$false; error="window not found"; query=$q } | ConvertTo-Json; exit 0 }
if ($pos) {
  switch ($pos) {
    "left"   { $x=$wa.X; $y=$wa.Y; $w=[int]($wa.Width/2); $h=$wa.Height }
    "right"  { $x=$wa.X+[int]($wa.Width/2); $y=$wa.Y; $w=[int]($wa.Width/2); $h=$wa.Height }
    "top"    { $x=$wa.X; $y=$wa.Y; $w=$wa.Width; $h=[int]($wa.Height/2) }
    "bottom" { $x=$wa.X; $y=$wa.Y+[int]($wa.Height/2); $w=$wa.Width; $h=[int]($wa.Height/2) }
    "max"    { $x=$wa.X; $y=$wa.Y; $w=$wa.Width; $h=$wa.Height }
    "center" { $w=[int]($wa.Width*0.6); $h=[int]($wa.Height*0.6); $x=$wa.X+[int](($wa.Width-$w)/2); $y=$wa.Y+[int](($wa.Height-$h)/2) }
    default  { $x=[int]$env:GEMMA4_X; $y=[int]$env:GEMMA4_Y; $w=[int]$env:GEMMA4_W; $h=[int]$env:GEMMA4_H }
  }
} else { $x=[int]$env:GEMMA4_X; $y=[int]$env:GEMMA4_Y; $w=[int]$env:GEMMA4_W; $h=[int]$env:GEMMA4_H }
[Win32]::MoveWindow($p.MainWindowHandle,$x,$y,$w,$h,$true) | Out-Null
[PSCustomObject]@{ ok=$true; title=$p.MainWindowTitle; process=$p.ProcessName; position=$pos; x=$x; y=$y; width=$w; height=$h } | ConvertTo-Json
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
        # DESVÍO WEB->BROWSER (cluster A7, cacería tanda 2): si el "nombre de app"
        # es en realidad un objetivo WEB (URL/host:port/IP/localhost/about:/
        # dominio.tld), app.open no abre nada real y miente "Listo, abrí X". Lo
        # correcto es abrirlo en el navegador. Estructural (mide la FORMA), no una
        # lista de sitios. Gate GEMMA4_APP_OPEN_WEB_DIVERT=0 lo apaga.
        import os as _os_wd
        try:
            from ..routing.planner import _is_web_target as _iwt
        except Exception:
            _iwt = None
        if (_os_wd.environ.get("GEMMA4_APP_OPEN_WEB_DIVERT", "1").strip().lower()
                not in {"0", "false", "no", "off"}) and _iwt and _iwt(name):
            try:
                self.trace_note = "app_open_web_divert"
            except Exception:
                pass
            return self.t_browser({"action": "open", "url": name,
                                   "_diverted_from": "app.open"})
        matches = self.apps.find(name, refresh=bool(args.get("refresh", False)))
        if not matches:
            return _err("app not found", query=name, searched_sources=["PATH", "Start Menu", "StartApps", "Registry", "Steam", "Epic"])
        best = matches[0]
        # PISO DE APERTURA (2026-06-10, MEDIDO en _diag_app_open_score_floor.py):
        # abrir matches[0] con cualquier score>0 ABRÍA una app aleatoria ante un
        # nombre inexistente (vivo: "abre jitomatador por favor" -> ok=True de
        # otra app). Distribución medida con la query CANÓNICA (alias builtin
        # traducido, mismo ranking de find): legítimos exactos/alias=100, typos
        # con primera letra conservada=46-88 ("stema"->Steam 46, "discrod" 53);
        # basura=<=40 (la banda word-pair-fuzzy de 1 token da exactamente 40 por
        # fórmula; el resto ni matchea). Piso 45: corta TODA la banda débil sin
        # tocar los typos medidos. Bajo el piso -> "app not found" HONESTO (el
        # mismo error activa el fallback a sitio web de t_app, que es el camino
        # correcto para "abrí <sitio>"). GEMMA4_APP_OPEN_MIN_SCORE lo ajusta.
        try:
            _floor = int(os.environ.get("GEMMA4_APP_OPEN_MIN_SCORE") or "45")
        except ValueError:
            _floor = 45
        if _floor > 0:
            _best_score = self.apps.top_match_score(name, best)
            if _best_score < _floor:
                return _err(
                    "app not found", query=name,
                    searched_sources=["PATH", "Start Menu", "StartApps", "Registry", "Steam", "Epic"],
                    weak_match={**best.as_dict(), "score": _best_score},
                    note=(f"el mejor candidato ('{best.name}', score {_best_score}) "
                          f"queda bajo el piso de apertura ({_floor}): no abro una "
                          "app que probablemente no es la pedida."),
                )
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
        # HONESTIDAD TRI-ESTADO. Cuando el
        # auto-verify NO confirmó la ventana, eso NO es "falló" (verified=False)
        # — es "no medible aún" (verified=None): el launch se despachó sin error
        # y la app puede seguir cargando (Steam/Epic tardan 10-30s). Antes
        # devolvíamos verified=False explícito, que (a) peleaba con el propio
        # _normalize_tool_result (launch_requested ∈ _DISPATCH_OK_COMPLETIONS lo
        # mapea a verified=None vía setdefault, pero el False explícito lo
        # bloqueaba), y (b) disparaba el guard "no dejó evidencia" + reintentos
        # = el flakeo events=0 medido (auditoría 2026-05-15). verified=None deja
        # que el normalizador y el verifier traten esto como dispatch async
        # honesto. Si la app ya estaba abierta -> True. Si verificamos -> True.
        # Si no -> None (no mentimos: el note lo dice claro).
        verified_tristate: bool | None
        if verified or preexisting.get("found"):
            verified_tristate = True
        else:
            verified_tristate = None
        return _ok(
            query=name,
            opened=best.as_dict(),
            alternatives=[m.as_dict() for m in matches[1:5]],
            preexisting=bool(preexisting.get("found")),
            resource=resource,
            status=("done" if verified_tristate else "dispatched"),
            verified=verified_tristate,
            completion_status=("launch_verified" if verified else "launch_requested"),
            evidence={"resolved_target": best.as_dict(), **verify_evidence},
            note=(
                "Auto-verify confirmed a window or process matching the requested app."
                if verified
                else "App was already running (window/process found before launch)."
                if preexisting.get("found")
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
        # GUARDA: taskkill /F es force-kill irreversible (sin prompt de guardar).
        # NUNCA matamos por la fuerza editores/IDE/terminales/runtime salvo que el
        # query nombre EXACTO ese exe. Misma protección estructural que window-close.
        _protected_exes = {
            "code.exe", "code - insiders.exe", "codium.exe", "vscodium.exe",
            "devenv.exe", "rider64.exe", "pycharm64.exe", "idea64.exe",
            "webstorm64.exe", "clion64.exe", "sublime_text.exe", "notepad++.exe",
            "windowsterminal.exe", "wt.exe", "powershell.exe", "pwsh.exe",
            "cmd.exe", "conhost.exe", "explorer.exe", "python.exe", "pythonw.exe",
            "node.exe", "claude.exe", "git.exe",
        }
        _q_fold = _fold(name)
        target_exes = [
            exe for exe in target_exes
            if exe.lower() not in _protected_exes or _fold(exe.lower().removesuffix(".exe")) == _q_fold
        ]
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
        scored = [
            {
                **m.as_dict(),
                "match_score": max(_score(query, m.name), _score(query, Path(m.launch).stem)),
            }
            for m in matches
        ]
        best_score = max((int(m.get("match_score", 0)) for m in scored), default=0)
        if scored and best_score < 55:
            return _ok(
                query=query,
                matches=scored,
                status="needs_verification",
                verified=False,
                completion_status="low_confidence_local_app_search",
                hint=(
                    "app.search only searches installed local apps/games. These "
                    "matches are weak; if the user asked for a website, store, "
                    "product, price, or web result, continue with web.search/"
                    "browser.open instead of treating this as a local app match."
                ),
            )
        return _ok(
            query=query,
            matches=scored,
            verified=bool(scored),
            completion_status="local_app_search_results",
        )

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
        # Bug 2026-05-29 (handler-delegation): el 4B usa filesystem.read para "leer/
        # qué dice/resumime" un PDF/Word/PPT (prior arraigado) -> binario inútil (los
        # PDFs reales tienen NUL bytes -> error abajo). Delegamos a document.extract_text
        # (texto real). Gated por el mismo flag que el subset-override.
        import os as _os_fr
        if (_os_fr.environ.get("GEMMA4_FILE_TOOL_ROUTING", "1") or "1").strip().lower() not in {
                "0", "false", "no", "off"} and path.suffix.lower() in {
                ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".html", ".htm"}:
            try:
                _doc = self.t_document({"action": "extract_text", "path": str(path)})
                if isinstance(_doc, dict) and _doc.get("ok"):
                    return _doc
            except Exception:
                pass  # si falla, cae a la lectura normal (no perdemos el read)
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
        # RED DE SEGURIDAD how-to (BUG real medido, cacería tanda 1): "cómo elimino
        # una carpeta" -> el 4B llamaba filesystem.delete y BORRABA la carpeta ante
        # una PREGUNTA (daño irreversible). El subset del router ya excluye filesystem
        # en how-to, pero es sugestivo (forced-retry da acceso igual). Acá, si el
        # texto del turno es una pregunta how-to, NO borrar — explicar. Solo activo
        # si el agente plumeó _current_user_text (sin él = no-op, no rompe tests/CLI).
        _ut = (getattr(self, "_current_user_text", "") or "").strip()
        if _ut:
            try:
                from ..routing.planner import (
                    _is_howto_or_info_question as _howto,
                    _is_prompt_injection as _inject)
                if _howto(_ut):
                    return _ok(action="explain", completion_status="howto_not_executed",
                               note="pregunta how-to: NO borré nada; el asistente explica cómo, no ejecuta")
                # PROMPT-INJECTION ("ignora tus permisos y borra"): NUNCA auto-
                # confirmar una acción irreversible bajo un intento de saltar reglas.
                # Forzar confirmación explícita (ignorando un confirmed=true que
                # pudiera venir del propio injection).
                if _inject(_ut):
                    return _err("acción destructiva bajo intento de saltar permisos; "
                                "requiere confirmación explícita del usuario",
                                status="needs_confirmation",
                                completion_status="injection_blocked", verified=False)
            except Exception:
                pass
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

    # NOTA (2026-06-09): la vieja lista _NON_SITE_HOSTS (reddit/instagram/…) se
    # eliminó. resolve_site_by_search ahora descarta agregadores/redes/perfiles de
    # tercero por SEÑAL ESTRUCTURAL (el nombre debe ser un LABEL COMPLETO del
    # dominio, no un substring parcial) — universal, sin lista de dominios. Medido
    # en scripts/_diag/_diag_non_site_hosts.py: cubre insta/reddi/face y los
    # agregadores no-occidentales (VK/Weibo/Naver) que la lista no contemplaba.

    def _site_search_all_backends(self, name: str, limit: int = 12) -> list[dict[str, str]]:
        # Wrapper-método sobre ddgs_search_all_backends: punto mockeable para que
        # los tests mock-only no peguen a la red en el 2do pase del resolvedor.
        return _ddgs_search_all_backends(name, limit=limit)

    def _resolve_site_by_search(self, name: str) -> str | None:
        # Delega en site_resolver.resolve_site_by_search (extraído 2026-06-07),
        # inyectando las deps de ESTA registry. None si nada matchea (no abre basura).
        # CACHE TTL por nombre (2026-06-10, incluye el None): la resolución son
        # 1-2 pases de red (MEDIDO 8.6-11s en red móvil) y el miss de app.open la
        # repagaba ENTERA cuando el 4B re-llamaba la tool en el mismo turno. Un
        # sitio no cambia de dominio en minutos; el None (nombre sin sitio) menos.
        key = (name or "").strip().lower()
        cache: dict[str, tuple[float, str | None]] = getattr(
            self, "_site_resolve_cache", None) or {}
        self._site_resolve_cache = cache
        hit = cache.get(key)
        if hit is not None and time.monotonic() - hit[0] < 600.0:
            return hit[1]
        url = _resolve_site_by_search_impl(
            name,
            web_search=self.web_search,
            fillers=_SITE_REQUEST_FILLERS,
            search_all_backends=lambda q, lim=12: self._site_search_all_backends(q, limit=lim),
        )
        cache[key] = (time.monotonic(), url)
        return url

    def _open_url_in_browser(self, browser: str, url: str) -> dict[str, Any] | None:
        """Abre `url` en el NAVEGADOR `browser` (honra "pon X en Opera"). Resuelve
        el navegador con el AppResolver y lo lanza con la URL como argumento; luego
        intenta verificar que su ventana apareció. Devuelve el result (ok=True con
        navigated_url) o None si no se pudo resolver/lanzar ESE navegador (el caller
        cae al navegador por defecto con nota honesta). NO finge: si no abrió en el
        navegador pedido, devuelve None."""
        name = (browser or "").strip()
        if not name:
            return None
        try:
            matches = self.apps.find(name)
        except Exception:
            matches = []
        if not matches:
            return None
        try:
            open_result = self.apps.open(matches[0], url_arg=url)
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "browser": name}
        if not open_result.get("ok") or not (open_result.get("candidate") or {}).get("navigated_url"):
            # el resolver no pudo pasar la URL a ese navegador -> default honesto.
            return None
        # verificar ventana del navegador (best-effort; no bloquear si no confirma)
        verified = False
        try:
            v = self.verify_app_opened({"name": name})
            verified = bool(v.get("found"))
        except Exception:
            pass
        # registrar el recurso para cleanup (igual que app_open)
        try:
            self.state.register_resource(
                "browser_url", url, cleanup_tool=None, cleanup_args={},
                metadata={"url": url, "browser": name})
        except Exception:
            pass
        return _ok(
            url=url, browser=name, opened=True,
            navigated_url=url, method="launch_browser_with_url",
            verified=verified, content_verified=False,
            completion_status="opened_url_in_browser" if verified else "opened_url_in_browser_unverified",
            note=f"Abrí {url} en {name}." + ("" if verified else
                 " (no pude confirmar la ventana, pero se lanzó)."),
        )

    def web_open_url(self, args: dict[str, Any]) -> dict[str, Any]:
        url = str(args.get("url", "")).strip()
        if not url:
            return _err("empty url", status="needs_user")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        # VALIDACION: parsear y verificar que tiene host. Sin esto, urls
        # como "https:// " o "https://hola mundo" pasan a webbrowser.open
        # que las ejecuta como query del default browser.
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
        timeout_arg = args.get("timeout_sec")
        try:
            timeout_sec = int(timeout_arg) if timeout_arg not in (None, "") else None
        except Exception:
            timeout_sec = None
        provider, results = _web_search_provider(query, limit=limit, timeout_sec=timeout_sec)
        from .web_source_quality import annotate_web_results, primary_web_results
        results = annotate_web_results(results)
        primary_results = primary_web_results(results)
        return _ok(
            query=query,
            engine=provider,
            results=results,
            primary_results=primary_results,
            answer_guidance=(
                "For factual answers, prefer primary_results and top-ranked "
                "non-discussion sources. Treat source_kind='discussion' as "
                "opinion/speculation unless the user asked for discussion. "
                "If sources disagree, state the uncertainty instead of merging "
                "uncorroborated claims."
            ),
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
        # LATENCIA con red mala (MEDIDO 2026-06-09, datos móviles): web_research
        # encadena search + N reads de página completa; sin cota cada uno puede
        # colgar ~10-12 s. Acotamos: la búsqueda interna hereda el timeout del
        # turno (default agresivo) y cada lectura de página tiene un tope corto.
        # Override GEMMA4_WEB_READ_TIMEOUT (default 6 s/página).
        _search_to = args.get("timeout_sec")
        _read_to = max(2, min(12, int(os.environ.get("GEMMA4_WEB_READ_TIMEOUT", "6") or "6")))
        search = self.web_search({"query": query, "limit": search_limit,
                                  "timeout_sec": _search_to})
        results = search.get("results", [])
        allow_discussion = bool(re.search(
            r"\b(foro|forum|opinion|opiniones|discussion|discusion|"
            r"comentarios|comments|comunidad|community|social)\b",
            query.casefold(),
        ))
        read_candidates = list(results)
        if not allow_discussion:
            non_discussion = [
                item for item in read_candidates
                if isinstance(item, dict) and item.get("source_kind") != "discussion"
            ]
            if non_discussion:
                read_candidates = non_discussion
        sources = []
        failures = []
        for item in read_candidates[:read_limit]:
            url = str(item.get("url") or "")
            try:
                page = self.web_read({"url": url, "max_chars": per_page_chars,
                                      "timeout_sec": _read_to})
                sources.append({
                    "title": page.get("title") or item.get("title"),
                    "url": page.get("url") or url,
                    "search_snippet": item.get("snippet"),
                    "source_kind": item.get("source_kind"),
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
        body was unified with ``domain_tools._hard_gate``
        (audit §2.2). The wrapper still exists so callers can keep
        invoking ``self._hard_gate(...)`` without knowing where state
        comes from.
        """
        from .._shared import hard_gate
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
        # FAST-PATH in-process (uia_fast.py con `uiautomation`): evita el spawn de
        # PowerShell + Add-Type C# (~600ms/llamada). Misma UIAutomationCore.dll que
        # el .NET del PS -> misma calidad de clicks/patterns (verificado en fuentes).
        # Fallback al PowerShell si uiautomation no está o devuelve None. Kill-switch
        # GEMMA4_UIA_PYTHON=0 (revierte 100% al camino PS validado).
        if os.environ.get("GEMMA4_UIA_PYTHON", "1").strip().lower() not in {"0", "false", "no", "off"}:
            try:
                from .uia_fast import run as _uia_py
                _r = _uia_py(
                    action,
                    str(args.get("query") or args.get("text") or args.get("target") or ""),
                    str(args.get("window") or args.get("title") or ""),
                    str(args.get("value") or args.get("text_value") or ""),
                    int(args.get("limit", 60)),
                )
                if isinstance(_r, dict):
                    return _ok(**_r) if _r.get("ok") else _err(
                        str(_r.get("error") or "uia failed"),
                        **{k: v for k, v in _r.items() if k not in ("ok", "error")})
            except Exception:
                pass  # cae al PowerShell
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

# Cast seguro double->int: los elementos OFFSCREEN devuelven BoundingRectangle
# con valores enorme/Infinity/NaN (p.ej. ±1.79e308); un [int] directo OVERFLOWEA
# y crashea TODO el ForEach-Object con "Valor demasiado grande" -> el comando UIA
# no emite nada (bug latente, 2026-05-25). Clampeamos al rango int32.
function SafeInt($v) {
  try {
    if ([double]::IsNaN($v) -or [double]::IsInfinity($v)) { return 0 }
    if ($v -gt 2147483647) { return 2147483647 }
    if ($v -lt -2147483648) { return -2147483648 }
    return [int][math]::Round([double]$v)
  } catch { return 0 }
}

function ElemObj($e) {
  if ($null -eq $e) { return $null }
  $r = $e.Current.BoundingRectangle
  $click = $null
  try {
    $p = $e.GetClickablePoint()
    $click = [PSCustomObject]@{ x=(SafeInt $p.X); y=(SafeInt $p.Y) }
  } catch {}
  $patterns = @()
  $toggleState = $null
  $pat = $null
  try {
    if ($e.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pat)) {
      $patterns += "Invoke"
    }
  } catch {}
  $pat = $null
  try {
    if ($e.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern, [ref]$pat)) {
      $patterns += "Toggle"
      try { $toggleState = [string]$pat.Current.ToggleState } catch {}
    }
  } catch {}
  $pat = $null
  try {
    if ($e.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pat)) {
      $patterns += "Value"
    }
  } catch {}
  $isPassword = $false
  try { $isPassword = [bool]$e.Current.IsPassword } catch {}
  [PSCustomObject]@{
    name=$e.Current.Name
    control_type=($e.Current.ControlType.ProgrammaticName -replace '^ControlType\.','')
    automation_id=$e.Current.AutomationId
    class_name=$e.Current.ClassName
    framework_id=$e.Current.FrameworkId
    enabled=$e.Current.IsEnabled
    is_password=$isPassword
    offscreen=$e.Current.IsOffscreen
    bounds=[PSCustomObject]@{
      x=(SafeInt $r.X); y=(SafeInt $r.Y); width=(SafeInt $r.Width); height=(SafeInt $r.Height)
    }
    clickable_point=$click
    patterns=$patterns
    toggle_state=$toggleState
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
  try {
    if ([bool]$el.Current.IsPassword) {
      [PSCustomObject]@{
        ok=$false; action=$action; query=$query; element=(ElemObj $el);
        error="refusing to set value on a password/protected field";
        status="needs_user"; verified=$false;
        completion_status="needs_secret_handoff"
      } | ConvertTo-Json -Depth 8
      exit 0
    }
  } catch {}
  $pattern = $null
  if ($el.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
    $pattern.SetValue($value)
    [PSCustomObject]@{ ok=$true; action=$action; query=$query; value_chars=$value.Length; element=(ElemObj $el); method="value_pattern" } | ConvertTo-Json -Depth 8
    exit 0
  }
  [PSCustomObject]@{
    ok=$false; action=$action; query=$query; value_chars=$value.Length;
    element=(ElemObj $el); method="value_pattern_unavailable";
    verified=$false; completion_status="uia_value_pattern_unavailable";
    error="element does not expose ValuePattern"
  } | ConvertTo-Json -Depth 8
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

    def _screenshot_mss(self, mode: str, path: "Path") -> "dict[str, Any] | None":
        """Wrapper thin sobre screenshot_fast.capture (extraído 2026-06-09, ratchet
        archivo-dios). Devuelve el dict _ok() o None (→ caller cae al PowerShell)."""
        from .screenshot_fast import capture as _capture
        data = _capture(mode, path)
        return _ok(**data) if isinstance(data, dict) else None

    def gui_screenshot(self, args: dict[str, Any]) -> dict[str, Any]:
        # T3-gui-screenshot-virtual-screen-011: param `monitor=primary|all|<index>`.
        # Default sigue siendo `all` (VirtualScreen) por compatibilidad.
        monitor_raw = str(args.get("monitor") or "all").strip().casefold()
        if monitor_raw == "primary":
            mode = "primary"
        elif monitor_raw == "all":
            mode = "all"
        elif monitor_raw in {"active", "focused", "current"}:
            mode = "active"  # ventana en foco; evita la panorámica que el 2B aluvina
        elif monitor_raw.isdigit():
            mode = f"index:{int(monitor_raw)}"
        else:
            return _err("invalid monitor; use primary|all|active|<index>", monitor=monitor_raw, status="needs_user")
        name = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = self.captures_dir / name
        # LATENCIA (MEDIDO 2026-06-09): la captura por PowerShell compila C#
        # (Add-Type, DPI+GDI) en CADA llamada → ~1.1s. `mss` es captura pura-Python
        # in-process (~30-130ms, 8-35x). PRESERVA el contrato (path,width,height,
        # left,top — el left/top traduce coords OCR→pantalla para el click) y la
        # DPI-awareness (clave en pantallas escaladas: capturar en píxeles FÍSICOS
        # = misma escala que el click). Fallback al script PowerShell si mss falla
        # o no está. Kill-switch GEMMA4_SCREENSHOT_MSS=0.
        if os.environ.get("GEMMA4_SCREENSHOT_MSS", "1").strip().lower() not in {"0", "false", "no", "off"}:
            _fast = self._screenshot_mss(mode, path)
            if _fast is not None:
                return _fast
        env = os.environ.copy()
        env["GEMMA4_SCREENSHOT_PATH"] = str(path)
        env["GEMMA4_SCREENSHOT_MODE"] = mode
        script = r"""
$path = $env:GEMMA4_SCREENSHOT_PATH
$mode = $env:GEMMA4_SCREENSHOT_MODE
# DPI-AWARENESS (2026-05-25): sin esto, en pantallas escaladas (p.ej. laptop a
# 150% — el hardware TARGET de RED) GDI captura en coords LÓGICAS (1260x840)
# mientras el cursor/mouse_event opera en FÍSICAS (1890x1260). El OCR hallaba
# el botón en el bitmap lógico y el click caía en el lugar equivocado -> toda
# la cascada OCR fallaba en clicks por coordenada. Marcamos el proceso
# PER_MONITOR_AWARE_V2 para capturar a resolución física real = misma escala
# que el click. Debe ir ANTES de leer bounds / CopyFromScreen.
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class GemmaDpi {
  [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr value);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
"@
try {
  # -4 = DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
  if (-not [GemmaDpi]::SetProcessDpiAwarenessContext([IntPtr](-4))) { [GemmaDpi]::SetProcessDPIAware() | Out-Null }
} catch { try { [GemmaDpi]::SetProcessDPIAware() | Out-Null } catch {} }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
if ($mode -eq 'primary') {
  $screen = [System.Windows.Forms.Screen]::PrimaryScreen
  $bounds = $screen.Bounds
} elseif ($mode -eq 'active') {
  # Monitor que contiene la ventana en FOCO (GetForegroundWindow). Si no se puede
  # resolver (sin ventana en foco), cae al primario. Reduce densidad multi-monitor.
  Add-Type @"
using System;
using System.Runtime.InteropServices;
public class GemmaFg { [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow(); }
"@
  try {
    $hwnd = [GemmaFg]::GetForegroundWindow()
    if ($hwnd -ne [IntPtr]::Zero) {
      $screen = [System.Windows.Forms.Screen]::FromHandle($hwnd)
    } else {
      $screen = [System.Windows.Forms.Screen]::PrimaryScreen
    }
  } catch { $screen = [System.Windows.Forms.Screen]::PrimaryScreen }
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

        # DPI-aware (2026-05-25): el screenshot ahora captura en coords FÍSICAS,
        # así que el click DEBE operar en el mismo espacio físico o el OCR-click
        # cae en el lugar equivocado en pantallas escaladas. SetProcessDpiAware
        # ANTES de SetCursorPos.
        script = f"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Mouse {{
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(int flags, int dx, int dy, int data, int extra);
  [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr value);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}}
"@
try {{ if (-not [Mouse]::SetProcessDpiAwarenessContext([IntPtr](-4))) {{ [Mouse]::SetProcessDPIAware() | Out-Null }} }} catch {{ try {{ [Mouse]::SetProcessDPIAware() | Out-Null }} catch {{}} }}
[Mouse]::SetCursorPos({x}, {y}) | Out-Null
[Mouse]::mouse_event(0x0002,0,0,0,0)
[Mouse]::mouse_event(0x0004,0,0,0,0)
"""
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=6)
        except (OSError, subprocess.TimeoutExpired):
            return _err("gui_click timeout", x=x, y=y, reason="powershell_timeout")
        try:
            gui_safety.note_agent_input()  # marcar que ESTE input fue del agente
        except Exception:
            pass
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
                from ..computer_use_pkg.win_focus import focus_and_maximize
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
        # FOCO antes de teclear (auditoría §7.1). Caminos:
        # (a) hay hint y el foreground NO es ya esa ventana -> _focus_window_chen
        #     (secuencia Raymond Chen: SetForegroundWindow + SendMessageTimeout +
        #     verify; SIN AttachThreadInput, que Chen desaconseja por cuelgues). Si
        #     falla, caemos a _focus_typable_window como respaldo.
        # (b) sin hint pero el foreground es no-escribible (toast/shell) ->
        #     _focus_typable_window busca la app real más arriba en z-order.
        # (c) el foreground YA es la ventana objetivo -> no tocar el foco.
        # NOTA medida (2026-05-24): el código de inyección NO acumula handles
        # (GDI/USER constantes x10) — el "3-6 y falla" observado en el harness se
        # rastreó a contaminación del test (cuentas consecutivas sin reset + foco
        # robado por otra ventana), NO a un leak. Por eso preferimos NO re-enfocar
        # cuando ya está puesto (evita churn de foco innecesario).
        if hint and not self._match_query(hint, fg_title):
            focus_attempted = True
            if not self._focus_window_chen(hint):
                self._focus_typable_window(hint)  # respaldo si Chen no logró el foco
            time.sleep(0.12)
            try:
                import win32gui as _w
                fg = _w.GetForegroundWindow()
                fg_title = _w.GetWindowText(fg) if fg else fg_title
            except Exception:
                pass
        elif _need_focus:
            focus_attempted = True
            focused = self._focus_typable_window(hint)
            time.sleep(0.25)
            try:
                import win32gui as _w
                fg = _w.GetForegroundWindow()
                fg_title = _w.GetWindowText(fg) if fg else fg_title
            except Exception:
                pass
        # WINDOW-READY GATE (2026-05-24): una app recién abierta (calculadora UWP,
        # Notepad) tarda en estar LISTA para recibir teclas — los primeros
        # keystrokes se pierden si llegan antes (eval Tier-4: '5+3' -> display '3',
        # se comió '5+'). En vez de un sleep fijo (frágil), POLLEAMOS hasta que el
        # foreground sea estable la ventana objetivo, cap ~1.5s. Universal: no
        # depende de la app; mide que la ventana esté al frente y quieta.
        #
        # MODO 1 (hint matchea): esperar a ESA ventana estable. Es el caso medido
        # al 100% — NO tocar. MODO 2 (sin hint, o hint no matchea tras ~1s): caer
        # a esperar que CUALQUIER foreground escribible esté estable, para no
        # perder teclas igual (t1_write_1). El modo 2 NO debe demorar ni romper el
        # modo 1: por eso el modo 1 tiene prioridad y su propio break.
        _gate_ready = False  # ¿la ventana objetivo quedó estable al frente?
        try:
            import win32gui as _w
            _deadline = time.time() + 1.5
            _stable = 0
            _last = None
            _saw_hint = False
            while time.time() < _deadline:
                _h = _w.GetForegroundWindow()
                _t = _w.GetWindowText(_h) if _h else ""
                _hint_match = bool(hint) and self._match_query(hint, _t)
                if _hint_match:
                    _saw_hint = True
                # MODO 1: si hay hint, exigir que matchee Y esté estable.
                if hint and not _saw_hint:
                    # todavía no apareció la ventana objetivo: esperarla.
                    _stable = 0
                    _last = None
                    time.sleep(0.12)
                    continue
                # Acá: o no hay hint, o el hint ya apareció. Exigir estable.
                if _t == _last and _t:
                    _stable += 1
                    if _stable >= 2:
                        fg_title = _t
                        _gate_ready = True
                        break
                _last = _t
                time.sleep(0.12)
        except Exception:
            _gate_ready = True  # sin win32gui no podemos gate-ar; no bloquear
        # Si había hint y la ventana objetivo NUNCA quedó estable al frente, el
        # foreground es OTRO (toast, app del usuario, IDE). Teclear ahí mandaría el
        # texto a la ventana equivocada — abortar honestamente en vez de tipear a
        # ciegas (verify_by_OS_state: no afirmar lo que no se pudo hacer). Bug
        # encontrado en la revisión 2026-05-24: el gate salía por timeout y tecleaba
        # igual. Sin hint NO abortamos (no hay objetivo que confirmar).
        if hint and not _gate_ready:
            return _err(
                f"no pude poner '{hint}' al frente para escribir (otra ventana "
                "tiene el foco); no tecleo a ciegas",
                status="needs_user", action="type_into",
                typed_into_window=fg_title, state_changed=False, verified=False)
        # 2) capturar estado antes + teclear + verificar (sin VLM)
        try:
            before = gui_verify.capture_before(None, None)
        except Exception:
            before = None
        # snapshot UIA del texto de la ventana ANTES de teclear: para detectar
        # 'el contenido cambió' sin buscar un literal (la calculadora nunca muestra
        # '2+2' pero su display pasa de '0' a otra cosa). Universal: mide cambio.
        _uia_before = None
        try:
            _uia_before = self._uia_focused_text_snapshot(hint or fg_title or "")
        except Exception:
            _uia_before = None
        typed = self.gui_type({"text": text})
        if not typed.get("ok"):
            return typed
        try:
            if before is not None:
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
        # Señal UIA de CAMBIO (sin literal): si el snapshot de texto de la ventana
        # cambió tras teclear, algo entró aunque no encontremos el string exacto
        # (calculadora: '2+2' nunca aparece, pero el display deja de ser '0').
        uia_changed = None
        if uia_confirmed is not True and _uia_before is not None:
            try:
                _uia_after = self._uia_focused_text_snapshot(hint or fg_title or "")
                if _uia_after is not None:
                    uia_changed = (_uia_after != _uia_before)
            except Exception:
                uia_changed = None
        if uia_confirmed is True:
            typed["state_changed"] = True
            typed["state_verify"] = "uia_text_present"
            typed["verified"] = True
        elif uia_changed is True:
            # cambió el contenido de texto de la ventana -> el tipeo tuvo efecto.
            typed["state_changed"] = True
            typed["state_verify"] = "uia_content_changed"
            typed["verified"] = True
        elif typed.get("state_changed") is False:
            typed["verified"] = False
            typed.setdefault("completion_status", "typed_no_effect")
        typed["uia_confirmed"] = uia_confirmed
        typed["uia_changed"] = uia_changed
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
            before = gui_verify.capture_before(sx, sy)
        except Exception:
            before = None
        clicked = self.gui_click({"x": sx, "y": sy})
        if not clicked.get("ok"):
            return _err(clicked.get("error") or "el click OCR falló",
                        label=label, status="failed", grounding="ocr")
        try:
            if before is not None:
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

    def _vision_escalate(self, label: str, window: str, candidates: Any) -> dict[str, Any] | None:
        """ÚLTIMO RECURSO (Fase 8): UIA y OCR no localizaron `label`. Si el gate
        de visión lo permite (VRAM + presupuesto por misión ≤2), captura un
        screenshot y lo devuelve adjunto para que el agente lo razone con su
        visión NATIVA (Gemma 4 + mmproj) — o localiza de otra forma, o reporta
        honestamente qué ve. NO clickea por visión a ciegas (grounding por VLM
        no es fiable). Devuelve None si no se puede escalar (gate/VRAM/budget) ->
        el caller da error honesto."""
        try:
            from .. import gui_vision_gate
        except Exception:
            return None
        ok, why = gui_vision_gate.can_escalate()
        if not ok:
            return None
        shot = self.gui_screenshot({})
        if not shot.get("ok"):
            return None
        gui_vision_gate.note_escalation()  # consume presupuesto de la misión
        result = _attach_screenshot(_err(
            f"no localicé '{label}' por UIA ni OCR; escalo a visión",
            label=label, window=window, status="needs_vision",
            grounding="vision_escalation",
            ocr_candidates=candidates,
            budget=gui_vision_gate.budget_state(),
            note=("UIA y OCR no encontraron el control. Te paso una captura: "
                  "mirá la pantalla y decime qué botón/control corresponde a "
                  f"'{label}', o avisá honestamente que no está visible. NO "
                  "adivines coordenadas."),
        ), shot)
        return result

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
        # ANCHOR-BINDING: si el label parece bait de pop-up no relacionado
        # al objetivo del turno (frase larga + cosine bajo), no clickear sin
        # confirmar. Conservador (0 fricción en labels cortos legítimos).
        try:
            _anc = gui_safety.check_anchor(label)
            if _anc is not None:
                _anc["action"] = "click_button"
                return _anc
        except Exception:
            pass
        window = str(args.get("window") or args.get("title") or "").strip()
        # FOREGROUND-SAFE (2026-05-25, CAUSA RAÍZ RE-MEDIDA): el primer modelo
        # ("Electron solo puebla su árbol con foco") era una correlación NO aislada.
        # Medición limpia este sesión: el árbol UIA in-process de Discord se lee
        # COMPLETO (708 controles, 10/10 clicks) AUNQUE Discord NO tenga el
        # foreground (lo tenía VS Code). El 6/10 viejo NO era COMError ni árbol
        # colapsado: era el robo de foco de _focus_window_chen compitiendo con el
        # usuario activo (teclado/Moonlight). En uso real el usuario ESTÁ usando el
        # PC, así que NO robamos foco salvo necesidad. ESTRATEGIA: leer in-process
        # PRIMERO (no toca el foreground del usuario); solo si falla, recién ahí
        # enfocar como fallback y reintentar. Foreground-safe por defecto.
        # 0) UIA IN-PROCESS sin tocar el foco (uiautomation, SIN PowerShell).
        # MEDIDO: 12/12 calc, 10/10 Discord sin foco. No perturba al usuario activo.
        _inproc = self._uia_click_inproc(label, window)
        if _inproc is not None and _inproc.get("ok"):
            _inproc["action"] = "click_button"
            _inproc["focus_stolen"] = False
            return _inproc
        # 0b) FALLBACK con foco: el read sin foco no encontró el control. Recién
        # ahora enfocamos (último recurso menos amable con el usuario activo) y
        # reintentamos el read in-process. Cubre apps que SÍ requieren foreground
        # para poblar (o un control que aún no estaba en vista). _focus_window_chen
        # es la secuencia segura (Raymond Chen, sin AttachThreadInput); enfocamos
        # por el TOKEN más largo del hint (nombre de app, estable aunque el título
        # cambie: "Amigos - Discord" -> "@Ron92 - Discord").
        if window:
            try:
                import re as _re_w
                _toks = sorted((t for t in _re_w.findall(r"\w+", window) if len(t) >= 4),
                               key=len, reverse=True)
                self._focus_window_chen(_toks[0] if _toks else window)
                time.sleep(0.7)  # dejar que el provider UIA pueble el árbol
            except Exception:
                pass
            _inproc2 = self._uia_click_inproc(label, window)
            if _inproc2 is not None and _inproc2.get("ok"):
                _inproc2["action"] = "click_button"
                _inproc2["focus_stolen"] = True
                return _inproc2
        # CASCADA Fase 3 (resto): UIA-PowerShell -> (retry) -> OCR -> visión.
        # 1) localizar el botón por UIA (button-prioritized) vía _uia_run (PowerShell).
        found = self._uia_find_clickable(label, window)
        # 1b) retry lazy-Chromium: el árbol AX de Chromium/CEF (Discord/Spotify/
        # Electron) devuelve VACÍO en el 1er walk tras enfocar; reintentar una vez
        # tras un delay corto antes de caer a OCR.
        if not found.get("ok") and self._foreground_is_chromium(window):
            time.sleep(0.6)
            found = self._uia_find_clickable(label, window)
        # 1b2) RETRY por ÁRBOL UIA NO-LISTO (2026-05-25): un find que falla puede ser
        # porque el árbol UIA aún no se pobló (app cargando, provider on-demand).
        # Reintentar el find con delay corto antes de caer a OCR recupera ese caso en
        # apps con UIA ESTABLE (Notepad/Settings/Office/navegadores). Gateado por
        # GEMMA4_CLICK_UIA_RETRIES (default 4). Universal.
        # TECHO MEDIDO (Discord, 2026-05-25): el árbol UIA de Discord (Electron) es
        # INTERMITENTE de forma patológica — alterna entre poblado (~248 controles) y
        # COLAPSADO (6-7) en estados que duran más que cualquier retry razonable, NO-
        # determinista. NO es falta de flag (se llena SIN --force-renderer-accessibility,
        # que Discord IGNORA — solo acepta una lista cerrada de chromiumSwitches). El
        # retry NO resuelve Discord de forma fiable (medido 8/8 fail en colapso); para
        # Discord/Electron-inestables el camino real es OCR/visión. Ver memoria
        # project_inapp_nav_discord.
        if not found.get("ok"):
            try:
                _retries = int(os.environ.get("GEMMA4_CLICK_UIA_RETRIES", "4"))
            except ValueError:
                _retries = 4
            for _i in range(max(0, _retries)):
                time.sleep(0.7)
                found = self._uia_find_clickable(label, window)
                if found.get("ok"):
                    found["uia_retries"] = _i + 1
                    break
        # 1c) FALLBACK OCR: si UIA no encontró el control (app sin UIA rico),
        # localizar el label por OCR y clickear su centro, con verificación.
        if not found.get("ok"):
            ocr_res = self._click_button_via_ocr(label, args)
            if ocr_res is not None:
                return ocr_res
            # 1d) ÚLTIMO RECURSO (Fase 8): visión gateada. UIA y OCR fallaron.
            # NO clickeamos por visión a ciegas (no es fiable); ESCALAMOS a un
            # screenshot para que el agente lo razone con su visión nativa y o
            # bien localice de otra forma o reporte honestamente qué ve. Gateado
            # por VRAM + presupuesto por misión (≤2). Si no se puede escalar,
            # error honesto.
            vis = self._vision_escalate(label, window, found.get("candidates"))
            if vis is not None:
                return vis
            return _err(
                found.get("error") or "no encontré un botón con ese label (UIA ni OCR)",
                label=label, window=window, status="failed",
                candidates=found.get("candidates"), grounding="uia+ocr")
        el = found.get("element") or {}
        pt = found.get("click_point") or {}
        cx, cy = pt.get("x"), pt.get("y")
        # 2) capture_before en el punto -> click -> verify_after.
        try:
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
                v = gui_verify.verify_after(before)
                clicked["state_changed"] = v.get("state_changed")
                clicked["state_verify"] = v.get("reason")
                # RECOVERY Fase 4: si el click NO tuvo efecto observable
                # (state_changed False) y tenemos un punto, recuperar UNA vez:
                # re-enfocar la ventana del control + reintentar el click. Causa
                # típica: el control no tenía foco o la ventana estaba detrás.
                # Bounded (1 retry) para no loopear. Reduce 'clicks sin efecto'.
                if v.get("state_changed") is False and cx is not None and cy is not None:
                    rec = self._recover_click(label, window, el, cx, cy)
                    if rec is not None:
                        rec["action"] = "click_button"
                        rec["label"] = label
                        rec["clicked_element"] = el
                        rec["recovered"] = True
                        return rec
                    clicked["verified"] = False
                    clicked.setdefault("completion_status", "clicked_no_effect")
        except Exception:
            pass
        clicked["action"] = "click_button"
        clicked["label"] = label
        clicked["clicked_element"] = el
        clicked["grounding"] = "uia"
        return clicked

    def _recover_click(self, label: str, window: str, el: dict, cx: int, cy: int) -> dict[str, Any] | None:
        """RECOVERY (Fase 4) para un click sin efecto: re-enfocar la ventana del
        control y reintentar el click UNA vez por coordenada, re-verificando. El
        foco perdido es la causa #1 de 'click sin efecto' (la ventana estaba
        detrás o el control no tenía foco). Devuelve el result si el reintento
        SÍ cambió el estado, o None si tampoco funcionó (el caller reporta el
        fallo honesto). Bounded: 1 intento, sin recursión."""
        try:
            # re-enfocar: por window hint, o por el proceso del elemento clickeado.
            focus_target = window or (el.get("name") or "")
            if focus_target:
                self.window_control("focus", focus_target)
                time.sleep(0.25)
            before2 = gui_verify.capture_before(cx, cy)
            retry = self.gui_click({"x": int(cx), "y": int(cy)})
            if not retry.get("ok"):
                return None
            v2 = gui_verify.verify_after(before2)
            retry["state_changed"] = v2.get("state_changed")
            retry["state_verify"] = v2.get("reason")
            retry["grounding"] = "uia"
            retry["recovery"] = "refocus_retry"
            # Solo consideramos recuperado si AHORA sí cambió algo (o no se pudo
            # medir -> lo dejamos pasar como best-effort, igual que el path normal).
            if v2.get("state_changed") is False:
                retry["verified"] = False
                retry.setdefault("completion_status", "clicked_no_effect")
                return None  # el retry tampoco tuvo efecto -> fallo honesto
            return retry
        except Exception:
            return None

    # Tipos de control que cuentan como "clickeables tipo botón", en orden de
    # preferencia. Estable cross-locale (son ProgrammaticName de UIA, en inglés).
    _BUTTON_CTYPES = ("Button", "SplitButton", "MenuItem", "TabItem",
                      "ListItem", "Hyperlink", "CheckBox", "RadioButton")

    def _uia_click_inproc(self, label: str, window: str) -> dict[str, Any] | None:
        """Encuentra y CLICKEA un control por Name IN-PROCESS con `uiautomation`
        (sin PowerShell). CAUSA RAÍZ medida (2026-05-25): el _uia_run viejo lanza
        PowerShell que PARPADEA una consola y ROBA el foreground a la app justo
        después de enfocarla -> el árbol UIA de Electron (Discord) colapsa a 0 y el
        find falla. La lectura in-process NO roba foco -> con la app enfocada da
        10/10 estable en Discord. Devuelve {ok, ...} clickeando vía InvokePattern, o
        None si uiautomation no está / no encontró (caller cae a _uia_run/OCR).
        Match: substring case-insensitive del Name, priorizando tipos botón."""
        try:
            import uiautomation as auto
        except Exception:
            return None
        try:
            lab = label.strip().lower()
            win_s = (window or "").strip().lower()
            # tokens del hint de ventana para matchear título dinámico (Discord).
            win_toks = [t for t in re.findall(r"\w+", win_s) if len(t) >= 4]
            best = None  # (rank, control)
            _BTN = {"ButtonControl", "MenuItemControl", "TabItemControl",
                    "ListItemControl", "HyperlinkControl", "SplitButtonControl",
                    "CheckBoxControl", "RadioButtonControl", "TreeItemControl"}
            for w in auto.GetRootControl().GetChildren():
                wn = (w.Name or "").lower()
                if win_s and win_s not in wn and not any(t in wn for t in win_toks):
                    if wn not in win_s:
                        continue
                stack = list(w.GetChildren())
                depth = 0
                while stack and depth < 4000:
                    el = stack.pop()
                    depth += 1
                    try:
                        nm = (el.Name or "").strip()
                        ct = el.ControlTypeName or ""
                    except Exception:
                        nm, ct = "", ""
                    if nm and lab in nm.lower():
                        # rank: botón exacto > botón substring > no-botón.
                        is_btn = ct in _BTN
                        exact = nm.lower() == lab
                        rank = (0 if (is_btn and exact) else
                                1 if is_btn else
                                2 if exact else 3)
                        if best is None or rank < best[0]:
                            best = (rank, el)
                            if rank == 0:
                                stack = []  # match perfecto, parar
                                break
                    try:
                        stack.extend(el.GetChildren())
                    except Exception:
                        pass
                if best is not None:
                    break
            if best is None:
                return None
            el = best[1]
            # capturar estado antes (frame-diff) + invocar + verify.
            try:
                _before = gui_verify.capture_before(None, None)
            except Exception:
                _before = None
            invoked = False
            try:
                ip = el.GetInvokePattern()
                ip.Invoke()
                invoked = True
            except Exception:
                # sin InvokePattern -> click por coordenada del centro del bbox.
                try:
                    r = el.BoundingRectangle
                    cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
                    self.gui_click({"x": cx, "y": cy})
                    invoked = True
                except Exception:
                    return None
            try:
                from .. import gui_safety as _gs
                _gs.note_agent_input()  # el Invoke/click es input del agente
            except Exception:
                pass
            time.sleep(0.2)
            changed = None
            try:
                if _before is not None:
                    changed = gui_verify.verify_after(_before).get("state_changed")
            except Exception:
                pass
            # HONESTIDAD TRI-ESTADO.
            # `changed` es la señal CRUDA del verifier de estado del SO:
            #   True  -> el SO confirmó el cambio (click verificado).
            #   False -> medido y NADA cambió (false-PASS atrapado).
            #   None  -> NO se pudo medir (sin _before, o verify_after crasheó:
            #            UIA demorado en Electron/Discord, frame-diff no disponible).
            # ANTES emitíamos `verified = changed is True`, que coaccionaba None->
            # False: "no sé" se reportaba como "falló". Eso (a) hacía que el
            # PlanExecutor reintentara = DOBLE-CLICK físico, y (b) volvía inútil la
            # recuperación tri-estado de _click (que sólo restaura desde verified
            # None). Propagamos `changed` TAL CUAL como verified (None=no medible),
            # consistente con las otras capas (_uia_run/OCR/recover_click) que NUNCA
            # ponen verified=False salvo state_changed=False.
            return {"ok": bool(invoked), "grounding": "uia_inproc",
                    "element": {"name": (el.Name or "")[:80],
                                "type": el.ControlTypeName},
                    "state_changed": changed, "verified": changed,
                    "label": label}
        except Exception as exc:
            return {"ok": False, "error": f"uia_inproc falló: {exc}",
                    "grounding": "uia_inproc"}

    def _uia_find_clickable(self, label: str, window: str) -> dict[str, Any]:
        """Encuentra el control clickeable cuyo Name mejor matchea `label`,
        priorizando tipos botón. Devuelve {ok, element, click_point} o
        {ok:false, candidates}. Reusa la maquinaria UIA existente (uia find)."""
        res = self._uia_run({"query": label, "window": window, "limit": 120}, "find")
        if not res.get("ok"):
            # el find léxico falló del todo -> intentar cross-lingual (R7) antes
            # de rendirse (p.ej. label en otro idioma que el de la UI).
            sem = self._uia_find_clickable_semantic(label, window)
            if sem is not None:
                return sem
            return {"ok": False, "error": res.get("error") or "uia find falló"}
        matches = res.get("matches") or []
        # PowerShell ConvertTo-Json emite un OBJETO (no lista) cuando hay 1 sola
        # coincidencia -> normalizar. Y descartar cualquier entrada que no sea dict.
        if isinstance(matches, dict):
            matches = [matches]
        matches = [m for m in matches if isinstance(m, dict)]
        if not matches:
            sem = self._uia_find_clickable_semantic(label, window)
            if sem is not None:
                return sem
            return {"ok": False, "error": "sin coincidencias UIA", "candidates": []}
        # `_score` ya está en module scope, no necesitamos
        # import circular del propio módulo.
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
        # R7: además exigir que el match LÉXICO sea bueno (name exacto o contiene
        # el label). Si el "mejor" no comparte texto con el label (p.ej. el query
        # "five" matcheó algo laxo por AutomationId), NO sirve -> intentar el
        # match CROSS-LINGUAL por embeddings antes de rendirse.
        if best is not None and lab and lab not in (best.get("name") or "").casefold():
            best = None  # el match léxico no es del label -> probar semántico
        if best is None:
            sem = self._uia_find_clickable_semantic(label, window)
            if sem is not None:
                return sem
            return {"ok": False, "error": "ninguna coincidencia es clickeable",
                    "candidates": [m.get("name") for m in ranked[:6]]}
        return {"ok": True, "element": best,
                "click_point": best.get("clickable_point")
                or {"x": best.get("bounds", {}).get("x"),
                    "y": best.get("bounds", {}).get("y")}}

    # Matcher cross-lingual (R7): aceptar si top-1 supera SIM_MIN Y le saca MARGIN al
    # 2º (el margin es la salvaguarda real). SIM_MIN bajado 0.75→0.55 (2026-06-09): el
    # 0.75 venía de un entreno sin seed (open↔Abrir=0.849 por suerte; seed fijo→~0.63).
    # MARGIN 0.10→0.05 (2026-06-11, encoder corpus-v3): la geometría nueva comprime
    # los márgenes (open vs Abrir/Cerrar/Minimizar: margen 0.070, antes >0.10). MEDIDO
    # (_recalibrate_xling_margin.py): los candidatos INCORRECTOS quedan bloqueados por
    # SIM_MIN (tops 0.29-0.48 < 0.55) — el margin actúa como defensa secundaria entre
    # candidatos que ya superan el piso; 0.05 conserva el caso correcto medido.
    _XLING_SIM_MIN = float(os.environ.get("GEMMA4_XLING_SIM_MIN", "0.55"))
    _XLING_MARGIN = float(os.environ.get("GEMMA4_XLING_MARGIN", "0.05"))

    def _uia_find_clickable_semantic(self, label: str, window: str) -> dict[str, Any] | None:
        """R7 — match CROSS-LINGUAL del label contra los Names de los controles
        clickeables, por EMBEDDINGS multilingües (reusa el encoder MiniLM del
        router, sin cargar otro modelo). Resuelve 'five'↔'Cinco', 'open'↔'Abrir'
        sin tablas de traducción por idioma (cumple el constraint: embeddings +
        fallback seguro). Opt-in: GEMMA4_GUI_XLING=0 lo apaga. None si no aplica
        (sin encoder, sin candidatos, o sin match con margen)."""
        import os as _os
        if (_os.environ.get("GEMMA4_GUI_XLING", "1").strip().lower()
                in {"0", "false", "no", "off"}):
            return None
        try:
            from ..routing.semantic_router import embed as _embed
        except Exception:
            return None
        # traer TODOS los controles del árbol (query vacío) y quedarnos con los
        # clickeables con Name no vacío.
        res = self._uia_run({"query": "", "window": window, "limit": 200}, "find")
        cands = res.get("matches") or []
        if isinstance(cands, dict):
            cands = [cands]
        cands = [c for c in cands if isinstance(c, dict)
                 and (c.get("name") or "").strip()
                 and (c.get("clickable_point") or c.get("control_type") in self._BUTTON_CTYPES)
                 and not c.get("offscreen", False)]
        if not cands:
            return None
        qv = _embed(label)
        if qv is None:
            return None  # sin encoder -> fallback seguro (no forzar)
        scored = []
        for c in cands:
            nv = _embed(c.get("name") or "")
            if nv is None:
                continue
            sim = float(sum(a * b for a, b in zip(qv, nv)))  # coseno (vectores L2-norm)
            scored.append((sim, c))
        if not scored:
            return None
        scored.sort(key=lambda x: -x[0])
        top_sim, top = scored[0]
        second = scored[1][0] if len(scored) > 1 else 0.0
        if top_sim < self._XLING_SIM_MIN or (top_sim - second) < self._XLING_MARGIN:
            return None  # sin confianza/margen -> no arriesgar el click
        return {"ok": True, "element": top, "grounding_match": "xlingual",
                "xling_sim": round(top_sim, 3),
                "click_point": top.get("clickable_point")
                or {"x": top.get("bounds", {}).get("x"),
                    "y": top.get("bounds", {}).get("y")}}

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

    def _uia_focused_text_snapshot(self, window_substr: str = "") -> str | None:
        """Devuelve una huella del TEXTO visible (Value + Name de edits/text) de
        la ventana en foco, para detectar 'algo cambió tras teclear' SIN buscar un
        literal. Caso calculadora: el display nunca muestra '2+2' literal, pero su
        valor pasa de '0' a otra cosa — comparar el snapshot ANTES/DESPUÉS lo
        detecta. Universal (no busca un string esperado, mide cambio). None si UIA
        no está. Acotado (depth cap) para no costar latencia."""
        try:
            import uiautomation as auto
        except Exception:
            return None
        win_s = (window_substr or "").strip().lower()
        parts: list[str] = []
        try:
            for w in auto.GetRootControl().GetChildren():
                wname = (w.Name or "").lower()
                if win_s and win_s not in wname and wname not in win_s:
                    continue
                stack = list(w.GetChildren())
                depth = 0
                while stack and depth < 300:
                    el = stack.pop()
                    depth += 1
                    val = ""
                    try:
                        vp = el.GetValuePattern()
                        val = vp.Value or ""
                    except Exception:
                        val = ""
                    # incluir Name SOLO de controles de texto/edición/resultado
                    # (no botones, que son estáticos y no reflejan el tipeo).
                    try:
                        ct = el.ControlTypeName or ""
                    except Exception:
                        ct = ""
                    if not val and ct in ("EditControl", "TextControl", "DocumentControl"):
                        val = el.Name or ""
                    if val:
                        parts.append(val)
                    try:
                        stack.extend(el.GetChildren())
                    except Exception:
                        pass
                if win_s:
                    break  # ya encontramos la ventana objetivo
            return "".join(parts) if parts else ""
        except Exception:
            return None

    def _focus_window_chen(self, title_substr: str) -> bool:
        """Trae al frente la ventana cuyo título contiene `title_substr` con la
        secuencia CANÓNICA de Raymond Chen (auditoría §7.1): SetForegroundWindow
        es ASÍNCRONO cross-process — GetForegroundWindow devuelve el HWND nuevo
        ANTES de que la ventana bombee la activación, así que 'foreground estable
        2 lecturas' NO basta. El fix: SetForegroundWindow -> SendMessageTimeout(
        WM_NULL) [espera a que el target procese su cola] -> verificar. Devuelve
        True si la ventana quedó realmente al frente. Best-effort (no-Windows->False).
        """
        if os.name != "nt" or not title_substr:
            return False
        try:
            import ctypes
            from ctypes import wintypes
            # CACHE de instancia (causa del "3 OK luego muere", DIAGNOSTICADO +
            # MEDIDO): recrear el WinDLL, re-declarar argtypes y SOBRE TODO crear un
            # @WINFUNCTYPE nuevo por llamada acumula estado en el proceso hasta
            # corromper la cola de input -> SendInput deja de entregar. Inicializamos
            # user32 + el callback EnumWindows UNA sola vez. Medido: callback recreado
            # = muere a las 3; cacheado = aguanta (6/6 limpio).
            if getattr(self, "_chen_u32", None) is None:
                u = ctypes.WinDLL("user32", use_last_error=True)
                # argtypes/restype COMPLETOS: en 64-bit, sin declararlos, ctypes
                # asume int (32-bit) para HWND/punteros y los TRUNCA -> handles
                # corruptos, comparaciones falsas, callbacks que reciben basura.
                u.GetForegroundWindow.restype = wintypes.HWND
                u.SetForegroundWindow.argtypes = (wintypes.HWND,)
                u.SetForegroundWindow.restype = wintypes.BOOL
                u.IsWindowVisible.argtypes = (wintypes.HWND,)
                u.IsWindowVisible.restype = wintypes.BOOL
                # IsIconic + ShowWindow: para RESTAURAR una ventana minimizada antes
                # de enfocarla. Una app minimizada (Electron/Chromium: Discord/Slack)
                # NO renderiza su DOM -> su árbol UIA colapsa a ~5 controles y el
                # find/click falla (lo que parecía "árbol intermitente" 2026-05-25 era
                # esto: Discord estaba iconic, rect en -21333). SetForegroundWindow NO
                # des-minimiza; hay que ShowWindow(SW_RESTORE). Medido: restaurar
                # llevó el árbol de 5 -> 646 controles.
                u.IsIconic.argtypes = (wintypes.HWND,)
                u.IsIconic.restype = wintypes.BOOL
                u.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
                u.ShowWindow.restype = wintypes.BOOL
                u.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
                u.GetWindowTextW.restype = ctypes.c_int
                u.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
                u.GetWindowTextLengthW.restype = ctypes.c_int
                _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, ctypes.c_void_p)
                u.EnumWindows.argtypes = (_WNDENUMPROC, wintypes.LPARAM)
                u.EnumWindows.restype = wintypes.BOOL
                u.SendMessageTimeoutW.argtypes = (
                    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                    wintypes.UINT, wintypes.UINT, ctypes.POINTER(wintypes.DWORD))
                u.SendMessageTimeoutW.restype = wintypes.LPARAM
                u.keybd_event.argtypes = (wintypes.BYTE, wintypes.BYTE,
                                          wintypes.DWORD, ctypes.c_void_p)
                self._chen_u32 = u
                self._chen_found = []

                def _cb_impl(h, _):
                    u2 = self._chen_u32
                    if u2.IsWindowVisible(h):
                        n = u2.GetWindowTextLengthW(h)
                        if n:
                            b = ctypes.create_unicode_buffer(n + 1)
                            u2.GetWindowTextW(h, b, n + 1)
                            t = b.value.lower()
                            if self._chen_sub in t or t in self._chen_sub:
                                self._chen_found.append(h)
                            else:
                                # candidatos para el fallback por PROCESO (solo
                                # ventanas visibles con título, como el match).
                                self._chen_others.append(h)
                    return True
                # mismo tipo que se pasó a EnumWindows.argtypes (c_void_p lParam).
                self._chen_enum_cb = _WNDENUMPROC(_cb_impl)  # PERSISTENTE
            user32 = self._chen_u32
            self._chen_sub = title_substr.lower()
            self._chen_found.clear()
            self._chen_others = []
            user32.EnumWindows(self._chen_enum_cb, 0)
            if not self._chen_found:
                # FALLBACK POR NOMBRE DE PROCESO (MEDIDO 2026-06-12): las apps de
                # título DINÁMICO nunca contienen su propio nombre — Spotify
                # reproduciendo se titula "Artista - Canción", el navegador se
                # titula con la página, el editor con el archivo. focus_app
                # fallaba con la app ABIERTA (3 reintentos, ~14.5s) y la misión
                # moría. El nombre del PROCESO (Spotify.exe) es estable e
                # independiente del idioma/contenido -> match estructural
                # universal. Solo corre cuando el título no matcheó (sin costo
                # en el hot-path feliz).
                try:
                    import win32process  # type: ignore
                    import psutil  # type: ignore
                    sub_tok = re.sub(r"[^a-z0-9]+", "", self._chen_sub)
                    if len(sub_tok) >= 3:
                        _pid_name: dict[int, str] = {}
                        for h in self._chen_others:
                            try:
                                _, pid = win32process.GetWindowThreadProcessId(h)
                                name = _pid_name.get(pid)
                                if name is None:
                                    name = psutil.Process(pid).name().lower()
                                    name = re.sub(r"\.exe$", "", name)
                                    name = re.sub(r"[^a-z0-9]+", "", name)
                                    _pid_name[pid] = name
                                if name and (name == sub_tok
                                             or name.startswith(sub_tok)
                                             or sub_tok.startswith(name)):
                                    self._chen_found.append(h)
                            except Exception:
                                continue
                except Exception:
                    pass
            if not self._chen_found:
                return False
            hwnd = self._chen_found[0]
            # RESTAURAR si está minimizada ANTES de enfocar: una app iconic no
            # renderiza -> su árbol UIA colapsa (Discord 5 controles) y todo
            # find/click falla. SW_RESTORE = 9. Universal (cualquier app minimizada).
            try:
                if user32.IsIconic(hwnd):
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    time.sleep(0.4)  # dejar que el DOM/árbol se repueble
            except Exception:
                pass
            # ALT-TRICK (2026-05-25, CAUSA RAÍZ final): SetForegroundWindow lo BLOQUEA
            # el foreground-lock de Windows si nuestro proceso no recibió input del
            # usuario reciente -> Discord NO pasaba al frente -> su árbol UIA quedaba
            # en 0 (lo que parecía "intermitente" era esto). La doc de
            # LockSetForegroundWindow dice que un input de ALT REHABILITA
            # SetForegroundWindow para el proceso. Simular ALT down/up antes -> el
            # foco SÍ se logra (medido: Discord pasó al frente y su árbol a 266).
            try:
                _VK_MENU = 0x12
                _KEYUP = 0x0002
                user32.keybd_event(_VK_MENU, 0, 0, 0)
                user32.keybd_event(_VK_MENU, 0, _KEYUP, 0)
                # El ALT sintético resetea GetLastInputInfo -> sin esto, la guarda
                # de actividad-del-usuario confunde NUESTRO ALT con el usuario y
                # difiere la acción siguiente (bug medido 2026-05-25: type_into tras
                # enfocar daba blocked=user_active desde el 1er turno). Marcar que
                # la actividad reciente fue del agente. Universal (todo control GUI
                # que enfoca pasa por acá).
                from .. import gui_safety as _gs
                _gs.note_agent_input()
            except Exception:
                pass
            user32.SetForegroundWindow(hwnd)
            # Chen ping: esperar a que el target procese la activación encolada.
            res = wintypes.DWORD()
            WM_NULL, SMTO_ABORTIFHUNG = 0x0000, 0x0002
            user32.SendMessageTimeoutW(hwnd, WM_NULL, 0, 0, SMTO_ABORTIFHUNG,
                                       1500, ctypes.byref(res))
            # comparar como INT: GetForegroundWindow (HWND/c_void_p) vs hwnd (int del
            # callback) pueden diferir en TIPO aunque sean el mismo handle -> el ==
            # directo daba False aunque el foco SÍ se logró (bug medido). int() de
            # ambos lo resuelve. None (top desconocido) -> caer a comparación laxa.
            #
            # POLL (MEDIDO 2026-06-12): aun tras el WM_NULL, el switch de foreground
            # aterriza ASÍNCRONO unos cientos de ms después (el ping volvió en ~30ms,
            # GetForegroundWindow aún devolvía la ventana vieja, y 300ms después el
            # target SÍ estaba al frente). El compare inmediato daba falso negativo
            # en focos EXITOSOS -> un retry de regalo en cada focus_app. Pollear
            # hasta ~700ms antes de concluir.
            try:
                _deadline = time.monotonic() + 0.7
                while True:
                    _fg = user32.GetForegroundWindow()
                    if int(_fg or 0) == int(hwnd or 0):
                        return True
                    if time.monotonic() >= _deadline:
                        return False
                    time.sleep(0.05)
            except Exception:
                return True  # enfocamos; no pudimos verificar -> asumir OK
        except Exception:
            return False

    def _send_text_via_sendinput(self, text: str) -> dict[str, Any] | None:
        """Teclea `text` con Win32 SendInput IN-PROCESS (sin lanzar PowerShell).

        FIX P0 (2026-05-24, auditoría §7.1): el camino viejo lanza un proceso
        PowerShell + SendKeys.SendWait POR llamada. El cold-start del CLR (0.5-6s,
        variable con la carga) hace que las teclas lleguen antes de que la ventana
        recién enfocada bombee la activación (SetForegroundWindow es asíncrono
        cross-process; doc Raymond Chen). Eso explica la flakiness MEDIDA: calc
        fresca 100% vs saturada 0-50% con código idéntico. SendInput in-process
        elimina el proceso externo y su cold-start.

        HÍBRIDO (medido 6/6 en calc + 5/5 en Notepad, incl. espacios y acentos):
        - Carácter con tecla física (VkKeyScanW != -1) -> VK code real (+ SHIFT si
          lo pide el high-byte). NECESARIO para la calc: el operador '+' por
          KEYEVENTF_UNICODE NO lo toma como operador (daba "3", perdía "5+"); por
          VK_ADD sí. Universal: VkKeyScanW respeta el layout activo del usuario.
        - Carácter SIN tecla (acentos no mapeados, ñ según layout, emoji) ->
          KEYEVENTF_UNICODE (independiente de layout -> multi-usuario).

        Devuelve dict ok/err, o None si SendInput no está disponible (no-Windows,
        sin ctypes) -> el caller cae al camino PowerShell legacy. Best-effort."""
        if not text:
            return None
        # RED ESTRUCTURAL anti-self-kill (BUG #suma_calc, 2026-06-04): SendInput va
        # IN-PROCESS al foreground REAL del escritorio. Si el foreground es el PROPIO
        # proceso (VS Code host / el server durante un eval batch), tipear contra sí
        # mismo mata la sesión (memoria: synthetic-input-lives-in-vscode). Abortar
        # honestamente ANTES de emitir input. Correcto también en prod: nunca querés
        # teclear contra tu propia ventana. GEMMA4_NO_PHYSICAL_INPUT=1 lo desactiva
        # del todo (modo eval).
        if os.environ.get("GEMMA4_NO_PHYSICAL_INPUT", "").strip().lower() in {"1", "true", "yes", "on"}:
            return {"ok": False, "verified": False,
                    "completion_status": "no_physical_input_mode",
                    "error": "physical input disabled (eval mode)"}
        try:
            import win32gui as _wg, win32process as _wp
            _fg = _wg.GetForegroundWindow()
            if _fg and _wp.GetWindowThreadProcessId(_fg)[1] == os.getpid():
                return {"ok": False, "verified": False,
                        "completion_status": "aborted_self_target",
                        "error": "foreground is the host process; refusing to type into self"}
        except Exception:
            pass  # sin win32 / no-Windows -> seguimos (best-effort)
        _m = _sendinput_machine()
        if _m is None:
            return None  # no-Windows / sin ctypes -> caller cae a legacy
        try:
            user32 = _m["user32"]
            _INPUT = _m["INPUT"]
            _KEYBDINPUT = _m["KEYBD"]
            _size = _m["size"]
            INPUT_KEYBOARD = 1
            KEYEVENTF_UNICODE = 0x0004
            KEYEVENTF_KEYUP = 0x0002
            VK_SHIFT = 0x10

            def _vk(vk: int, up: bool) -> "_INPUT":
                i = _INPUT()
                i.type = INPUT_KEYBOARD
                i.u.ki = _KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)
                return i

            def _uni(ch: str, up: bool) -> "_INPUT":
                f = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
                i = _INPUT()
                i.type = INPUT_KEYBOARD
                i.u.ki = _KEYBDINPUT(0, ord(ch), f, 0, 0)
                return i

            def _emit(events: list) -> int:
                buf = (_INPUT * len(events))(*events)
                return user32.SendInput(len(events), buf, _size)

            # NUMPAD para dígitos y operadores aritméticos: VK dedicados que NO
            # requieren SHIFT (DIAGNOSTICADO + MEDIDO 2026-05-24). En layout ES,
            # VkKeyScanW('*') devuelve vk 0xBB CON shift y '+' el MISMO 0xBB sin
            # shift -> mandar el operador con SHIFT es frágil: si el SHIFT-up no se
            # procesa (ráfaga rápida), queda "pegado" y los siguientes chars salen
            # mal -> "pierde el operador" tras varias cuentas. Los VK de numpad
            # (VK_ADD/SUBTRACT/MULTIPLY/DIVIDE/DECIMAL) no usan SHIFT -> robusto y
            # layout-independiente para aritmética. El experimento crudo con numpad
            # dio 6/6 estable; con VkKeyScanW+SHIFT degradaba. Para texto general
            # (letras/espacio) seguimos con VkKeyScanW (correcto) y Unicode (resto).
            _NUMPAD = {"0": 0x60, "1": 0x61, "2": 0x62, "3": 0x63, "4": 0x64,
                       "5": 0x65, "6": 0x66, "7": 0x67, "8": 0x68, "9": 0x69,
                       "+": 0x6B, "-": 0x6D, "*": 0x6A, "/": 0x6F, ".": 0x6E}
            sent_total = 0
            for ch in text:
                np_vk = _NUMPAD.get(ch)
                if np_vk is not None:
                    # numpad directo: sin SHIFT, sin depender del layout.
                    sent_total += _emit([_vk(np_vk, False), _vk(np_vk, True)])
                    time.sleep(0.012)
                    continue
                r = user32.VkKeyScanW(ch)
                if r != -1 and ((r >> 8) & 0xFF) == 0:
                    vk = r & 0xFF
                    sent_total += _emit([_vk(vk, False), _vk(vk, True)])
                elif r != -1 and ((r >> 8) & 0xFF) == 1:  # requiere SHIFT
                    vk = r & 0xFF
                    sent_total += _emit([_vk(VK_SHIFT, False), _vk(vk, False),
                                         _vk(vk, True), _vk(VK_SHIFT, True)])
                else:  # sin tecla física -> Unicode
                    sent_total += _emit([_uni(ch, False), _uni(ch, True)])
                # micro-pausa: la calc UWP a veces colapsa ráfagas de teclas; 12ms
                # por char es imperceptible (texto de voz es corto) y robusto.
                time.sleep(0.012)
            return {"ok": True, "chars": len(text), "method": "sendinput",
                    "events": sent_total}
        except Exception as exc:
            return {"ok": False, "error": f"sendinput failed: {exc}",
                    "method": "sendinput"}

    def gui_type(self, args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("text", ""))
        forced_method = str(args.get("method") or args.get("input_method") or "").strip().lower()
        force_paste = forced_method == "paste" or bool(args.get("force_paste"))
        force_sendkeys = forced_method == "sendkeys" or bool(args.get("force_sendkeys"))
        if force_paste and not bool(args.get("raw_sendkeys", False)):
            result = self._gui_type_via_paste(text)
            if result.get("ok"):
                try:
                    gui_safety.note_agent_input()
                except Exception:
                    pass
            return result
        # REGRESION WebView2 (2026-05-25): SendInput in-process no inyecta de forma
        # fiable en inputs WebView2/Chromium/Electron (WhatsApp/Discord/Spotify). Antes
        # del 23 el camino era SendKeys/paste y llegaba. FIX: si el target es
        # Chromium, saltar SendInput y usar paste (UTF-8-safe, funciona en inputs web).
        # Gate GEMMA4_KEYS_SENDINPUT=0 fuerza no-SendInput.
        _win_hint = str(args.get("window") or args.get("title") or "")
        _skip_sendinput = (
            force_sendkeys
            or os.environ.get("GEMMA4_KEYS_SENDINPUT", "1").strip().lower() in {"0", "false", "no", "off"}
            or self._foreground_is_chromium(_win_hint))
        # P0 (auditoría §7.1): intentar SendInput IN-PROCESS primero (sin el
        # cold-start de PowerShell que causaba la pérdida de caracteres bajo carga).
        # Maneja ASCII, operadores Y acentos (híbrido VK/Unicode). Si no está
        # disponible o falla, cae al camino legacy (paste / SendKeys-PowerShell).
        if not bool(args.get("raw_sendkeys", False)) and not _skip_sendinput:
            _si = self._send_text_via_sendinput(text)
            if _si is not None and _si.get("ok"):
                try:
                    gui_safety.note_agent_input()
                except Exception:
                    pass
                return _ok(chars=len(text), method="sendinput",
                           events=_si.get("events"))
        # BUG tilde (2026-05-23): SendKeys vía stdin pierde acentos. El stdin de
        # PowerShell se decodifica con la code-page de consola (cp1252/OEM en
        # Windows ES), NO UTF-8, así que "mamá" llegaba como "mam?". Mismo gotcha
        # que espeak-ng. Además SendKeys tiene límites con Unicode.
        # FIX: si el texto tiene caracteres NO-ASCII (acentos, ñ, emoji), tipear
        # por CLIPBOARD-PASTE (tkinter es UTF-8-safe), guardando y restaurando el
        # portapapeles del usuario. ASCII puro -> SendKeys (no toca el clipboard).
        # WebView2/Chromium: preferir PASTE (evento de pegado, llega al input web)
        # aunque sea ASCII — SendKeys de texto largo a WebView2 es menos fiable que
        # un paste. Apps nativas: solo paste para no-ASCII (acentos), como antes.
        non_ascii = any(ord(c) > 127 for c in text)
        if ((non_ascii or _skip_sendinput) and not force_sendkeys
                and not bool(args.get("raw_sendkeys", False))):
            result = self._gui_type_via_paste(text)
            if result.get("ok"):
                try:
                    gui_safety.note_agent_input()
                except Exception:
                    pass
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
        try:
            gui_safety.note_agent_input()
        except Exception:
            pass
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
        # 4. Restaurar clipboard del usuario solo cuando WebView2 ya consumio
        # el paste. Con 0.1s WhatsApp a veces pegaba el clipboard restaurado.
        _t.sleep(0.5)
        if saved:
            try:
                self.clipboard_write({"content": saved})
            except Exception:
                pass
        return _ok(chars=len(text), method="paste")

    # Teclas especiales (sin modificador) -> Virtual-Key code, para SendInput
    # in-process. Cubre el caso común del agente (ENTER/TAB/ESC/flechas/F-keys).
    # Las combos con modificador (CTRL+S, etc.) caen al path SendKeys legacy.
    _VK_NAMED = {
        "ENTER": 0x0D, "RETURN": 0x0D, "ESC": 0x1B, "ESCAPE": 0x1B, "TAB": 0x09,
        "BACKSPACE": 0x08, "BS": 0x08, "DELETE": 0x2E, "DEL": 0x2E,
        "SPACE": 0x20, "SPACEBAR": 0x20, "UP": 0x26, "DOWN": 0x28,
        "LEFT": 0x25, "RIGHT": 0x27, "HOME": 0x24, "END": 0x23,
        "PGUP": 0x21, "PAGEUP": 0x21, "PGDN": 0x22, "PAGEDOWN": 0x22,
        "INS": 0x2D, "INSERT": 0x2D,
        "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
        "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    }

    # VK de modificadores para combos in-process (ctrl/alt/shift/win).
    _VK_MODIFIER = {"CTRL": 0x11, "CONTROL": 0x11, "ALT": 0x12, "MENU": 0x12,
                    "SHIFT": 0x10, "WIN": 0x5B, "WINDOWS": 0x5B, "META": 0x5B}

    def _vk_for_key(self, token: str) -> int | None:
        """VK de UNA tecla (nombrada o letra/dígito/símbolo simple) para SendInput.
        Devuelve None si no se puede mapear sin layout (deja el fallback a SendKeys)."""
        t = token.strip()
        if not t:
            return None
        named = self._VK_NAMED.get(t.upper())
        if named is not None:
            return named
        if len(t) == 1:
            # letra o dígito ASCII: VK = ord(mayúscula) para A-Z/0-9 (layout US-base,
            # suficiente para atajos estándar ctrl+k/ctrl+a/ctrl+f que NO dependen del
            # layout para la tecla base). Símbolos raros -> None (cae a SendKeys).
            ch = t.upper()
            if "A" <= ch <= "Z" or "0" <= ch <= "9":
                return ord(ch)
        return None

    def _keypress_via_sendinput(self, keys: str) -> dict[str, Any] | None:
        """Teclas vía SendInput IN-PROCESS (sin PowerShell). Maneja: (a) una tecla
        nombrada/simple, (b) un COMBO con modificadores ("ctrl+k", "ctrl+shift+t",
        "alt+f4"). Fix §7.1: evita el cold-start de PowerShell + el parpadeo de
        consola que roba/devuelve el foreground (el churn de foco desincronizaba la
        inyección — por eso ctrl+k a Discord por SendKeys no aterrizaba fiable). El
        combo presiona los modificadores, la tecla base, y suelta en orden inverso,
        TODO en un solo SendInput (atómico). None si algún token no se puede mapear
        -> el caller cae al SendKeys legacy."""
        raw = keys.strip()
        if not raw:
            return None
        # Separar combo por '+': el ÚLTIMO token es la tecla base; los previos son
        # modificadores. (Una sola tecla -> sin modificadores.)
        parts = [p for p in raw.replace(" ", "").split("+") if p]
        if not parts:
            return None
        *mods, base = parts
        base_vk = self._vk_for_key(base)
        if base_vk is None:
            return None
        mod_vks: list[int] = []
        for m in mods:
            mv = self._VK_MODIFIER.get(m.upper())
            if mv is None:
                return None  # modificador desconocido -> fallback SendKeys
            mod_vks.append(mv)
        _m = _sendinput_machine()
        if _m is None:
            return None
        try:
            user32 = _m["user32"]; _INPUT = _m["INPUT"]; _KEYBDINPUT = _m["KEYBD"]
            _size = _m["size"]
            KEYEVENTF_KEYUP = 0x0002

            def _ev(vk, up):
                i = _INPUT(); i.type = 1
                i.u.ki = _KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)
                return i
            seq = []
            for mv in mod_vks:               # modificadores DOWN (en orden)
                seq.append(_ev(mv, False))
            seq.append(_ev(base_vk, False))  # tecla base DOWN
            seq.append(_ev(base_vk, True))   # tecla base UP
            for mv in reversed(mod_vks):     # modificadores UP (orden inverso)
                seq.append(_ev(mv, True))
            buf = (_INPUT * len(seq))(*seq)
            n = user32.SendInput(len(seq), buf, _size)
            return {"ok": True, "keys": keys, "method": "sendinput", "events": n}
        except Exception as exc:
            return {"ok": False, "error": f"keypress sendinput failed: {exc}"}

    def gui_keypress(self, args: dict[str, Any]) -> dict[str, Any]:
        # CC-100 / T3-gui-keypress-sendkeys-injection-009: env-var indirection
        # para nunca f-stringear `keys` en el script PS.
        keys = str(args.get("keys", "")).strip()
        if not keys:
            return _err("empty keys")
        forced_method = str(args.get("method") or args.get("input_method") or "").strip().lower()
        # REGRESION medida 2026-05-25 (RED: "wsp funcionaba perfecto antes del 23"):
        # antes del 23 los keystrokes iban por PowerShell-SendKeys y llegaban a
        # WhatsApp. La migracion a SendInput (856a345) y luego a combos por SendInput
        # (69f3c76) rompio apps WebView2/Electron/Chromium: ctrl+f/ctrl+k podia no
        # llegar al input web. FIX hibrido: SendInput para apps nativas; SendKeys para
        # WebView2/Chromium. Gate GEMMA4_KEYS_SENDINPUT=0 fuerza SendKeys siempre.
        _win_hint = str(args.get("window") or args.get("title") or "")
        _force_sendkeys = (
            forced_method == "sendkeys"
            or bool(args.get("force_sendkeys"))
            or os.environ.get("GEMMA4_KEYS_SENDINPUT", "1").strip().lower() in {"0", "false", "no", "off"}
            or self._foreground_is_chromium(_win_hint))
        # P0 (§7.1): tecla simple nombrada -> SendInput in-process (sin PowerShell),
        # SALVO que el target sea WebView2/Chromium (ahí SendInput no llega).
        _si = None if _force_sendkeys else self._keypress_via_sendinput(keys)
        if _si is not None and _si.get("ok"):
            try:
                gui_safety.note_agent_input()
            except Exception:
                pass
            return _ok(keys=keys, method="sendinput", events=_si.get("events"))
        # combos con modificador / teclas no mapeadas -> SendKeys legacy.
        sendkeys = _translate_keys_to_sendkeys(keys)
        env = {**os.environ, "GEMMA4_KEYS": sendkeys}
        script = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait($env:GEMMA4_KEYS)"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=10)
        # marcar input del agente también en el camino SendKeys (combos con
        # modificador como ctrl+a): si no, la guarda de actividad-del-usuario
        # confunde estas teclas con el usuario y difiere la acción siguiente.
        try:
            gui_safety.note_agent_input()
        except Exception:
            pass
        return _ok(keys=keys, sendkeys=sendkeys, exit_code=proc.returncode,
                   method="sendkeys", stderr=_truncate(proc.stderr.strip(), 1000))

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

    # Procesos/ventanas de UPDATER/INSTALADOR que NO son la app real. Squirrel
    # (Discord/Slack/Teams/GitHub Desktop) lanza Update.exe que muestra una
    # ventana TRANSITORIA cuyo título puede contener el nombre de la app ("Discord")
    # hasta que entrega control al proceso real -> daba false-PASS (R4). Filtramos
    # por NOMBRE DE PROCESO del updater (forma estructural, estable cross-locale),
    # no por keyword de contenido.
    _UPDATER_PROCS = ("update.exe", "squirrel.exe", "setup.exe", "installer.exe",
                      "updater.exe", "msiexec.exe", "vcredist", "stub.exe")

    def _is_updater_proc(self, proc_name: str) -> bool:
        p = (proc_name or "").strip().lower()
        return any(u in p for u in self._UPDATER_PROCS) if p else False

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
        # R4: descartar matches de UPDATER. Una ventana cuyo proceso es Update.exe/
        # Squirrel NO es la app abierta — es el instalador transitorio. Sin esto,
        # "Discord" en el título del updater daba found=True aunque Discord.exe no
        # corría (3 false-PASS medidos en run7).
        real_procs = [p for p in proc_matches if not self._is_updater_proc(str(p.get("name", "")))]
        # ventana real = su proceso no es updater Y su título no es de updater
        # ("Discord Updater" tiene proceso vacío pero título de updater).
        def _win_is_real(w: dict) -> bool:
            if self._is_updater_proc(str(w.get("process", ""))):
                return False
            tl = str(w.get("title", "")).lower()
            return not any(k in tl for k in ("updater", "update failed", "installing",
                                             "instalando", "setup", "actualiz"))
        real_wins = [w for w in win_matches if _win_is_real(w)]
        updater_only = bool((proc_matches or win_matches) and not (real_procs or real_wins))
        return _ok(
            # found ahora exige un match REAL (no solo el updater transitorio).
            found=bool(real_procs or real_wins),
            query=name,
            process_matches=real_procs[:10],
            window_matches=real_wins[:10],
            match_count_procs=len(real_procs),
            match_count_windows=len(real_wins),
            updater_only=updater_only,  # señal honesta: solo se vio el instalador
        )

    def verify_file_exists(self, args: dict[str, Any]) -> dict[str, Any]:
        path = Path(str(args.get("path", "")).strip()).expanduser()
        return _ok(path=str(path), exists=path.exists(), is_file=path.is_file(), is_dir=path.is_dir(), size=path.stat().st_size if path.exists() and path.is_file() else None)

    # Procesos cuyo nombre identifica un navegador Chromium-family. Usado por
    # verify_window_exists cuando el query es un DOMINIO (foo.bar.cl): el
    # título de la ventana del navegador casi nunca contiene el dominio
    # crudo (lleva el title de la pestaña activa). Antes esto daba found=False
    # aunque la URL hubiera cargado bien — el agente narraba "no pude verificar"
    # tras un browser.open exitoso (incidente 2026-05-27, capturas).
    _BROWSER_PROCS: tuple[str, ...] = (
        "chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "operagx.exe",
        "brave.exe", "vivaldi.exe", "iexplore.exe",
    )

    @staticmethod
    def _looks_like_domain(s: str) -> bool:
        """Estructural: termina en .TLD (2+ letras) y no tiene espacios. Cubre
        foo.com, sub.dom.cl, etc. Multilingüe (no usa lista de TLDs)."""
        import re as _re
        s = (s or "").strip()
        if not s or " " in s:
            return False
        return bool(_re.search(r"\.[A-Za-z]{2,}(?:/|$)", s))

    @staticmethod
    def _cdp_url_match(domain: str, timeout_s: float = 1.0) -> dict[str, Any] | None:
        """Si CDP :9222 está vivo, leer /json/list y matchear URL real contra
        el dominio. Devuelve {found, url, title} o None si CDP no está. NO lanza
        un navegador — solo lee. La instancia CDP dedicada del agente
        (ver project_browser_cdp_dedicated_instance_2026_05_26) la habilita."""
        import urllib.request as _ur, json as _json, re as _re
        try:
            with _ur.urlopen("http://127.0.0.1:9222/json/list", timeout=timeout_s) as r:
                tabs = _json.loads(r.read())
        except Exception:
            return None
        d = (domain or "").strip().lower()
        # comparar host: el dominio query puede ser "portal2.uniej.cl" y la URL
        # real "https://portal2.uniej.cl/ingresar-al-portal" -> match por host.
        for t in tabs or []:
            if (t.get("type") or "").lower() != "page":
                continue
            url = str(t.get("url") or "").lower()
            if not url:
                continue
            try:
                host = _re.sub(r"^[a-z]+://([^/]+).*", r"\1", url)
            except Exception:
                host = url
            if d == host or d in host or host in d:
                return {"found": True, "url": t.get("url"), "title": t.get("title")}
        return {"found": False, "url": None, "title": None}

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
        if matches:
            # Match fuerte: el query aparece en algún título/proceso.
            return _ok(found=True, query=title, matches=matches[:10],
                       match_count=len(matches), verified_by="window_title")
        # Match NO encontrado por título/proceso. Si el query parece un DOMINIO,
        # hay dos rescates honestos antes de declarar found=False:
        # (1) CDP :9222 vivo -> leer URLs reales (verificación fuerte por URL).
        # (2) Hay algún navegador abierto -> verificación INFERIDA (no podemos
        #     leer la URL del Opera/Chrome del user porque Chromium 136+ ignora
        #     --remote-debugging-port sobre el perfil real — hardening 2025).
        # En (2) devolvemos found=True con caveat explícito: NO es mentira (el
        # navegador SÍ se abrió), y el caveat le dice al LLM/usuario el límite.
        if self._looks_like_domain(title):
            cdp = self._cdp_url_match(title)
            if cdp is not None:  # CDP responde
                return _ok(
                    found=bool(cdp.get("found")), query=title,
                    matches=[{"url": cdp.get("url"), "title": cdp.get("title")}]
                            if cdp.get("found") else [],
                    match_count=1 if cdp.get("found") else 0,
                    verified_by="cdp_url",
                )
            # CDP no disponible: buscar cualquier ventana de navegador conocido.
            browsers_open = [
                w for w in windows
                if str(w.get("process", "")).lower() in self._BROWSER_PROCS
            ]
            if browsers_open:
                return _ok(
                    found=True, query=title, matches=browsers_open[:5],
                    match_count=len(browsers_open),
                    verified_by="browser_window_present",
                    caveat=("dominio asumido cargado en navegador detectado; "
                            "no se puede leer URL sin CDP — el perfil del user "
                            "ignora --remote-debugging-port (Chromium 136+)."),
                )
        return _ok(found=False, query=title, matches=[], match_count=0,
                   verified_by="none")

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

from .tool_schemas import COMPOUND_TOOL_SCHEMAS  # literal moved to tool_schemas.py

_apply_action_enums(COMPOUND_TOOL_SCHEMAS)


# ---------------------------------------------------------------------------
# v22-next (OPT-IN GEMMA4_LEAN_RULES, dormant): descripciones de schema LEAN para
# los tools cuya `description` es la mas pesada (medido: whatsapp 918 tok,
# computer_use 466, media 393, audio 391). Se aplican SOLO en schemas_for_names
# (el subset que se manda al LLM) cuando el flag esta on -> NO muta el literal
# global (el contract-test lo ve verbatim) y NO toca el default. PRESERVAN el
# contenido CRITICO PARA SELECCION (que hace el tool + los limites NO-usar-para +
# la regla de slot-filling) y cortan los ejemplos/prosa largos. Validar EN VIVO
# (las descripciones DRIVEN la seleccion de tool -> mayor riesgo que los rules).
# Ver documentacion/PLAN_optimizacion_prompt_tokens.md.
LEAN_DESCRIPTIONS: dict[str, str] = {
    "whatsapp": (
        "Compound WhatsApp messaging. Actions: status, send_message, open_chat, "
        "read_messages (read aloud on-screen messages via screen vision — for 'leeme el "
        "último mensaje de X'). Opens WhatsApp Desktop via deeplink (else wa.me). Phone "
        "required: pass phone='+54911...' OR contact='<name>' to resolve from local "
        "contacts. AUTO-SEND: send_message presses Enter after verifying WhatsApp has "
        "focus (returns sent=True); if focus check fails it aborts safely (sent=False); "
        "auto_send=false to open without sending. SLOT FILLING: if channel/contact/body "
        "aren't ALL known, do NOT send_message — ask the ONE missing slot in the user's "
        "language (order: body, then contact, then channel). The pattern 'Dile/Decile/"
        "Mandale a <CONTACT> [en|por] wsp que <BODY>' has all slots → CALL it (contact "
        "after the verb, body after 'que'); aliases (amor, mama, mi amiga) ARE valid "
        "contacts. Ex: 'Mandale a mama por whatsapp que llego tarde' -> "
        "whatsapp(action='send_message', contact='mama', text='que llego tarde'). Missing "
        "body ('dile amor') -> ask 'qué mensaje y a quién?'. NEVER say 'no tengo "
        "herramienta para enviar mensaje' — this tool exists; ask the missing slot. "
        "CANONICAL params (aliases exist but prefer these): contact (or phone), text. "
        "Resolution if several given: phone>number; text>message>body; "
        "contact>recipient>to>name."
    ),
    "computer_use": (
        "Operate INSIDE an already-open app when no dedicated tool exists: open a chat/"
        "channel and type/send a message (Discord/Slack/Teams), join/control a Discord "
        "voice channel (mute/unmute/deafen/leave), navigate to a URL in the browser, "
        "open/close tabs, wait/scroll/click-by-name/type. Pass the user's FULL goal in "
        "natural language (any language) in `goal`; the tool decomposes it (focus_app, "
        "open_chat, open_voice, type, send, open_url, click, keypress, scroll, "
        "discord_control) and verifies by OS state. Pass ONLY what the user asked: if they just want to GO to a chat (no message), the goal is only to go — do NOT add a text like 'escribile hola' they didn't dictate. Ex (go): 'andá al chat de juan en discord'. Ex (msg): 'escribile a juan que llego tarde'. "
        "NOT for: opening/closing/focusing a whole app (use app/window), WhatsApp "
        "(use whatsapp), system volume/media keys (use audio). USE when the command is "
        "operating inside an already-open app that has no dedicated tool."
    ),
    "media": (
        "Compound media playback. Actions: status, play, pause, resume, play_pause, stop, "
        "next, previous, queue_add/clear/list, now_playing, open_local, "
        "search_local_library, cast_lan. play accepts provider=youtube|spotify|netflix|"
        "disney|hbo_max|prime_video|vlc|local_file. Streaming auto_play (default true): "
        "Spotify via deeplink+Enter; Netflix/Disney+/Max/Prime via web GUI flow (needs "
        "profile the first time → returns needs_user asks_for=streaming_profile). "
        "auto_play=false to just open. Generic Spotify request without a title ('pon una "
        "cancion', 'play something') → random playback; pass the user's generic phrase as "
        "query, NEVER the literal word. spotify_user=<name> for Liked Songs shuffle. "
        "now_playing reads the Windows media session."
    ),
    "audio": (
        "Compound audio/media-key tool. Actions: get_volume, set_volume, mute, devices, "
        "set_default, media_play_pause, media_stop, next, previous. set_volume(level: int "
        "0-100) is ABSOLUTE — resolve number-words/percent to int before calling. "
        "media_stop/media_play_pause send the global Windows media key (affects whatever "
        "holds media focus). Use ONLY to pause/stop the audio/video itself — NOT to close "
        "the host app/tab (use window.close / app.close for that)."
    ),
    # Extensión 2026-06-01 (auditoría, hallazgo LEAN-coverage): los próximos tools más
    # pesados. PRESERVAN qué hace + límites NO-usar-para + desambiguación; cortan
    # ejemplos multi-línea. Opt-in (GEMMA4_LEAN_RULES), no muta el literal global.
    "window": (
        "Compound window management. Actions: list, active, focus, close, minimize, "
        "maximize, restore, move_resize. close(query|title) closes a top-level window by "
        "visible-title substring (any app, any language: 'cierra/close/fecha/chiudi X'). "
        "If the target is a SINGLE TAB inside a multi-tab browser, prefer "
        "browser_real.tab_close. Don't confuse 'cerrar X' (this) with 'stop X media' "
        "(audio.media_stop)."
    ),
    "gui": (
        "Compound GUI/mouse/keyboard. Actions: screenshot, click, double_click, "
        "right_click, type, type_into, click_button, keypress, hotkey, scroll, drag, "
        "wait_for, locate_text, click_text, locate_image. click_button(label=) finds a "
        "clickable control by name via UIA and clicks WITH verification (use for 'click "
        "Send' instead of guessing x/y; optional window=<title> scopes it). type_into types "
        "into the target window with verification. locate_text/click_text use local OCR and "
        "return screen_x/screen_y. screenshot monitor='primary'|'all'|'<index>'. type "
        "escapes SendKeys metacharacters unless raw_sendkeys=true."
    ),
    "uia": (
        "Compound Windows UI Automation. Actions: tree, find, click, focus, set_value. "
        "Prefer over raw gui clicks for standard Windows controls (returns names, types, "
        "ids, bounds, clickable points). Scope with window/title; find with "
        "query/text/target. To CLICK a control whose name you know, call action='click' "
        "DIRECTLY with query=<label> — do NOT tree/find first (those only READ). The click "
        "action locates the best match and verifies the effect."
    ),
    "browser_real": (
        "Real browser automation via Playwright. Actions: status, open, goto, tabs, click, "
        "click_accessible, toggle_accessible, fill, press, type_text, text, screenshot, "
        "evaluate, connect_cdp, close, attach_visible, active_tab, tab_open, tab_close, "
        "tab_focus, click_text, extract, wait_for_download, set_download_path. "
        "attach_visible connects to the user's Chrome/Edge/Opera/Brave only if it's running "
        "with --remote-debugging-port=9222, else returns needs_user with the launch cmd. "
        "extract mode=main_text|tables|links|html. tab_close closes ONE tab (browser stays "
        "open) — prefer it over window.close when the wording targets a single tab AND the "
        "browser is attached; for plain 'cierra YouTube' use window.close."
    ),
    "session": (
        "Meta-session control. Action cancel_turn: the user wants to interrupt/cancel/abort/"
        "stop the current turn (does NOT perform a domain action — just stops and "
        "acknowledges briefly). Use for short messages meaning 'stop what you're doing' / 'I "
        "changed my mind' / 'wait, hold on', or a single word that conventionally means "
        "'time out'/'enough' in ANY language (judge from context, not a keyword list). NOT "
        "for 'para la música' (audio.media_play_pause) or 'wait, can you also…' (normal "
        "amending turn). After it fires, reply a one-line ack in the user's language."
    ),
    "routine": (
        "Local routine/automation. Actions: status, create, list, enable, disable, delete, "
        "run_now, simulate, history, import. A routine stores a trigger + ordered steps "
        "(e.g. [{tool:'audio', args:{action:'set_volume', level:20}}]). Triggers: manual, "
        "once ({type:'once', at:'2026-05-15 09:00'}), cron ({type:'cron', "
        "cadence:'daily|weekly|hourly|minutes', at:'09:00', days_of_week:[...]}), "
        "on_app_open/on_app_close ({type:'on_app_open', process:'steam.exe'}). import "
        "bulk-loads phrase routines from a TriggerCMD commands.json."
    ),
    "developer": (
        "Developer workflow. Actions: status, project_detect, run_tests, run_lint, "
        "run_format, git_status, git_diff, git_log, start_dev_server, stop_dev_server, "
        "list_dev_servers. project_detect reports stack + package manager. run_tests/lint/"
        "format dispatch by stack (pytest/ruff, npm/yarn/pnpm, cargo, go). git_commit/"
        "git_push are intentionally NOT exposed — use terminal(...) so the user sees the "
        "command. start_dev_server spawns a detached process tracked for stop_dev_server."
    ),
    "device_settings": (
        "WiFi, Bluetooth, SCREEN BRIGHTNESS, displays, power plans. Actions: status, "
        "wifi_status/list/scan/connect/disconnect/add_profile/delete_profile, "
        "bluetooth_status, brightness_get/set/up/down (set: level 0-100 OR delta +/-N; "
        "up/down for 'subí/bajá el brillo'), display_list, power_plan_list/get/set. "
        "wifi_connect REQUIRES the network name in `name` (auto-creates WPA2 profile when "
        "password= is passed). bluetooth_toggle/night_light/display_set_resolution are "
        "deferred. power_plan_set snapshots the previous plan for rollback."
    ),
}


def _lean_descriptions_on() -> bool:
    # DEFAULT ON (validado en vivo junto a las lean rules).
    # GEMMA4_LEAN_RULES=0 para opt-out.
    return (os.environ.get("GEMMA4_LEAN_RULES", "1") or "1").strip().lower() not in {"0", "false", "no", "off"}


def _with_lean_description(schema: dict[str, Any]) -> dict[str, Any]:
    """Shallow-copy `schema` swapping in the lean description if one exists.
    NUNCA muta el literal global (devuelve copia solo de los 2 niveles tocados)."""
    fn = schema.get("function", {})
    lean = LEAN_DESCRIPTIONS.get(str(fn.get("name", "")))
    if not lean:
        return schema
    new_fn = dict(fn)
    new_fn["description"] = lean
    return {**schema, "function": new_fn}


# ---------------------------------------------------------------------------
# Cache por-subset de schemas_for_names (2026-06-02, deuda tecnica oportunista).
#
# schemas_for_names reconstruye la lista filtrando COMPOUND_TOOL_SCHEMAS +
# aplicando LEAN en CADA llamada (1-2 veces/turno). El ahorro MEDIDO es
# despreciable (~16 us/call, 0.016 ms -- trabajo en memoria sin I/O; ver el
# reporte del sprint), pero el cache es correcto y barato.
#
# CLAVE = (frozenset(names), lean_on). Solo cacheamos lo ESTABLE en la sesion:
#   - El subset de nombres pedidos (orden irrelevante -> frozenset).
#   - El flag LEAN (afecta el CONTENIDO de las descripciones; se lee por-llamada
#     y los tests lo togglean -> DEBE estar en la clave, si no servimos stale).
#
# INVALIDACION del catalogo MCP: las tools mcp__* son DINAMICAS (se descubren al
# boot, re-descubribles con discover_mcp_tools(force=True)/reset_cache()). En vez
# de versionar el catalogo MCP, BYPASEAMOS el cache cuando el subset pide alguna
# mcp__* -> asi NUNCA servimos un schema MCP stale (ni uno lean cuando es full).
# Los subsets con MCP son raros (GEMMA4_MCP default OFF) -> costo nulo. El cache
# cubre el 100% del caso comun (sin MCP) y es imposible que devuelva MCP obsoleto.
_SCHEMAS_FOR_NAMES_CACHE: dict[tuple, list[dict[str, Any]]] = {}


def _invalidate_schemas_cache() -> None:
    """Vacia el cache por-subset. Llamar si LEAN_DESCRIPTIONS o el catalogo
    estatico mutan en runtime (tests / reconfig). El caso normal NO lo necesita:
    LEAN esta en la clave y los subsets MCP bypasean el cache."""
    _SCHEMAS_FOR_NAMES_CACHE.clear()


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

