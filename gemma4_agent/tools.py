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


_SENSITIVE_KEY_RX = re.compile(r"(password|token|key|secret|api[_-]?key|auth)", re.IGNORECASE)


def _redact_sensitive(value: Any, depth: int = 0) -> Any:
    """CC-105: redacta cualquier key que matchee passwords/tokens/secrets.

    Recursivo (capado en 6 niveles) para dicts anidados (p.ej. args.payload).
    Listas también se inspeccionan. Las strings sensibles se reemplazan por
    '***REDACTED***'.
    """
    if depth > 6:
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and _SENSITIVE_KEY_RX.search(k):
                # Mantenemos info de presencia pero ocultamos el contenido.
                out[k] = "***REDACTED***" if v not in (None, "") else v
            else:
                out[k] = _redact_sensitive(v, depth + 1)
        return out
    if isinstance(value, list):
        return [_redact_sensitive(v, depth + 1) for v in value]
    return value


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
    unverified = _has_unverified_signal(result)

    if not ok:
        result.setdefault("status", "failed")
        result.setdefault("verified", False)
        result.setdefault("completion_status", "failed")
    elif result.get("attempted"):
        result.setdefault("status", "attempted")
        result.setdefault("verified", False)
    elif unverified:
        result.setdefault("status", "needs_verification")
        result.setdefault("verified", False)
    else:
        result.setdefault("status", "done")
        result.setdefault("verified", True)

    result.setdefault("evidence", _result_evidence(result))
    return result


def _has_unverified_signal(result: dict[str, Any]) -> bool:
    for key, value in result.items():
        if key.endswith("_verified") and value is False:
            return True
    if result.get("verified") is False:
        return True
    if result.get("attempted") is True:
        return True
    completion = str(result.get("completion_status") or "").casefold()
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
    "gui": ["screenshot", "click", "double_click", "right_click", "type", "keypress", "hotkey", "scroll", "drag", "wait_for", "locate_text", "click_text", "locate_image"],
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


def _action(args: dict[str, Any], default: str = "") -> str:
    return str(args.get("action") or default).strip().casefold()


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


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
    overlap = len(q_words & c_words)
    if overlap:
        return 40 + int(30 * overlap / len(q_words))
    # Fuzzy fallback: el usuario puede haber dictado mal por voz
    # ("Saint Rose" en vez de "Saints Row") o con typos. Usamos difflib
    # SequenceMatcher.ratio() sobre la frase completa Y sobre cada par
    # de words. Si alguna coincidencia parcial supera el umbral, devolvemos
    # un score bajo pero positivo para que el candidato no se descarte.
    import difflib
    full_ratio = difflib.SequenceMatcher(None, q, c).ratio()
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
            if difflib.SequenceMatcher(None, qw, cw).ratio() >= 0.75:
                matched_words += 1
                break
    if matched_words:
        return 20 + int(20 * matched_words / max(1, len(q_words)))
    return 0


@dataclass(frozen=True)
class AppCandidate:
    name: str
    source: str
    launch: str
    launch_type: str
    process_name: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "launch": self.launch,
            "launch_type": self.launch_type,
            "process_name": self.process_name,
        }


class AppResolver:
    """Discovers apps/games from Windows instead of relying on manual aliases."""

    def __init__(self) -> None:
        self._cache: list[AppCandidate] = []
        self._loaded_sources: set[str] = set()

    def find(self, query: str, limit: int = 8, refresh: bool = False, deep_fallback: bool = True) -> list[AppCandidate]:
        if refresh:
            self._cache = []
            self._loaded_sources = set()

        for source_name, loader in (
            ("path", self._from_path),
            ("shortcuts", self._from_shortcuts),
            ("start_apps", self._from_start_apps),
            ("registry", self._from_uninstall_registry),
            ("steam", self._from_steam),
            ("epic", self._from_epic),
        ):
            self._load_source(source_name, loader)
            matches = self._rank(query, self._cache, limit)
            if matches and max(_score(query, matches[0].name), _score(query, Path(matches[0].launch).stem)) >= 90:
                return matches

        matches = self._rank(query, self._cache, limit)
        if matches or not deep_fallback:
            return matches

        deep_matches = self._from_common_exe_roots(query=query, max_matches=max(limit * 3, 24))
        self._cache.extend(deep_matches)
        return self._rank(query, self._cache, limit)

    def find_steam_library(self, query: str, limit: int = 8) -> list[AppCandidate]:
        candidates = [*self._from_steam(), *self._from_steam_appinfo_cache(query, max(limit * 3, 12))]
        return self._rank(query, candidates, limit)

    def _load_source(self, source_name: str, loader: Callable[[], list[AppCandidate]]) -> None:
        if source_name in self._loaded_sources:
            return
        self._cache.extend(loader())
        self._loaded_sources.add(source_name)

    def _rank(self, query: str, candidates: list[AppCandidate], limit: int) -> list[AppCandidate]:
        ranked: list[tuple[int, AppCandidate]] = []
        seen: set[tuple[str, str]] = set()
        for app in candidates:
            score = max(_score(query, app.name), _score(query, Path(app.launch).stem))
            if score <= 0:
                continue
            key = (_fold(app.name), app.launch.casefold())
            if key in seen:
                continue
            seen.add(key)
            ranked.append((score, app))
        ranked.sort(key=lambda item: (-item[0], item[1].source, item[1].name.casefold()))
        return [app for _score_value, app in ranked[:limit]]

    def _from_path(self) -> list[AppCandidate]:
        out = []
        pathext = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";")
        for folder in os.environ.get("PATH", "").split(os.pathsep):
            root = Path(folder.strip('"'))
            if not root.is_dir():
                continue
            try:
                for child in root.iterdir():
                    if child.is_file() and child.suffix.upper() in pathext:
                        out.append(AppCandidate(child.stem, "PATH", str(child), "file", child.name))
            except OSError:
                continue
        return out

    def _from_shortcuts(self) -> list[AppCandidate]:
        recursive_roots = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        ]
        flat_roots = [
            Path.home() / "Desktop",
            Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "Desktop",
        ]
        out = []
        for root in recursive_roots:
            if not root.is_dir():
                continue
            try:
                for shortcut in root.rglob("*.lnk"):
                    out.append(AppCandidate(shortcut.stem, "shortcut", str(shortcut), "file"))
            except OSError:
                continue
        for root in flat_roots:
            if not root.is_dir():
                continue
            try:
                for shortcut in root.glob("*.lnk"):
                    out.append(AppCandidate(shortcut.stem, "shortcut", str(shortcut), "file"))
            except OSError:
                continue
        return out

    def _from_start_apps(self) -> list[AppCandidate]:
        script = "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Depth 2"
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
        except Exception:
            return []
        raw = proc.stdout.strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = [data]
        out = []
        for item in data:
            name = item.get("Name")
            appid = item.get("AppID")
            if name and appid:
                out.append(AppCandidate(name, "start_app", f"shell:appsFolder\\{appid}", "shell"))
        return out

    def _from_uninstall_registry(self) -> list[AppCandidate]:
        script = r"""
$paths = @(
  'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
$items = foreach ($p in $paths) {
  Get-ItemProperty $p -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName } |
    Select-Object DisplayName,DisplayIcon,InstallLocation
}
$items | ConvertTo-Json -Depth 3
"""
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=25)
        except Exception:
            return []
        raw = proc.stdout.strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = [data]
        out = []
        for item in data:
            name = item.get("DisplayName")
            launch = self._launch_from_registry_item(item)
            if name and launch:
                process = Path(launch).name if Path(launch).suffix.lower() == ".exe" else None
                out.append(AppCandidate(name, "registry", launch, "file", process))
        return out

    def _launch_from_registry_item(self, item: dict[str, Any]) -> str | None:
        icon = str(item.get("DisplayIcon") or "").strip().strip('"')
        icon = re.sub(r",\s*-?\d+$", "", icon).strip('"')
        if (
            icon
            and Path(icon).is_file()
            and Path(icon).suffix.lower() == ".exe"
            and not _looks_like_uninstaller(Path(icon))
        ):
            return icon
        install = str(item.get("InstallLocation") or "").strip().strip('"')
        root = Path(install)
        if root.is_dir():
            exes = sorted(
                (p for p in root.glob("*.exe") if p.is_file() and not _looks_like_uninstaller(p)),
                key=lambda p: len(p.name),
            )
            if exes:
                return str(exes[0])
        return None

    def _from_common_exe_roots(self, query: str, max_matches: int = 80) -> list[AppCandidate]:
        words = _fold(query).split()
        if not words:
            return []
        pattern = "*" + "*".join(words) + "*.exe"
        roots = [
            Path(os.environ.get("ProgramFiles", "C:/Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
            Path(os.environ.get("APPDATA", "")),
            Path("C:/Games"),
            Path("D:/Games"),
            Path("D:/SteamLibrary"),
            Path("E:/Games"),
            Path("E:/SteamLibrary"),
        ]
        out = []
        seen: set[Path] = set()
        for root in roots:
            if not root.is_dir() or root in seen:
                continue
            seen.add(root)
            try:
                proc = subprocess.run(
                    ["where.exe", "/R", str(root), pattern],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in proc.stdout.splitlines():
                    exe = Path(line.strip())
                    if not exe.is_file() or _looks_like_uninstaller(exe):
                        continue
                    pretty = _pretty_exe_name(exe)
                    score = max(_score(query, pretty), _score(query, exe.stem), _score(query, str(exe.parent)))
                    if score <= 0:
                        continue
                    out.append(AppCandidate(pretty, "exe_scan", str(exe), "file", exe.name))
                    if len(out) >= max_matches:
                        return out
            except (OSError, subprocess.TimeoutExpired):
                continue
        return out

    def _from_steam(self) -> list[AppCandidate]:
        steam_roots = self._steam_library_roots()
        out = []
        for root in steam_roots:
            apps = root / "steamapps"
            if not apps.is_dir():
                continue
            for manifest in apps.glob("appmanifest_*.acf"):
                text = manifest.read_text(encoding="utf-8", errors="ignore")
                appid = _acf_value(text, "appid")
                name = _acf_value(text, "name")
                if appid and name:
                    out.append(AppCandidate(name, "steam", f"steam://rungameid/{appid}", "uri"))
        return out

    def _from_steam_appinfo_cache(self, query: str, max_matches: int = 20) -> list[AppCandidate]:
        needle = query.strip().encode("utf-8", errors="ignore").lower()
        if len(needle) < 2:
            return []
        out: list[AppCandidate] = []
        seen: set[str] = set()
        for root in self._steam_library_roots():
            appinfo = root / "appcache" / "appinfo.vdf"
            cache = root / "appcache" / "librarycache"
            if not appinfo.is_file() or not cache.is_dir():
                continue
            try:
                data = appinfo.read_bytes()
                lower = data.lower()
                appid_markers = [
                    (int(child.name), int(child.name).to_bytes(4, "little"))
                    for child in cache.iterdir()
                    if child.is_dir() and child.name.isdigit()
                ]
            except OSError:
                continue

            start = 0
            while len(out) < max_matches:
                pos = lower.find(needle, start)
                if pos < 0:
                    break
                start = pos + 1
                end = data.find(b"\x00", pos)
                if end < 0 or end - pos > 180:
                    continue
                name = data[pos:end].decode("utf-8", errors="replace").strip()
                if not name or _score(query, name) <= 0:
                    continue
                appid = _nearest_steam_appid(data, appid_markers, pos)
                if not appid:
                    continue
                key = _fold(name)
                if key in seen:
                    continue
                seen.add(key)
                out.append(AppCandidate(name, "steam_appinfo", f"steam://nav/games/details/{appid}", "uri"))
        return out

    def _steam_library_roots(self) -> list[Path]:
        roots: list[Path] = []
        for base in [Path("C:/Program Files (x86)/Steam"), Path("C:/Program Files/Steam")]:
            if base.is_dir():
                roots.append(base)
        vdf = next((root / "steamapps" / "libraryfolders.vdf" for root in roots if (root / "steamapps" / "libraryfolders.vdf").is_file()), None)
        if vdf:
            text = vdf.read_text(encoding="utf-8", errors="ignore")
            for path in re.findall(r'"path"\s+"([^"]+)"', text):
                p = Path(path.replace("\\\\", "\\"))
                if p.is_dir() and p not in roots:
                    roots.append(p)
        return roots

    def _from_epic(self) -> list[AppCandidate]:
        manifest_root = Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests")
        if not manifest_root.is_dir():
            return []
        out = []
        for manifest in manifest_root.glob("*.item"):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception:
                continue
            name = data.get("DisplayName") or data.get("AppName")
            install = Path(str(data.get("InstallLocation") or ""))
            exe = None
            if install.is_dir():
                exes = sorted(install.rglob("*.exe"), key=lambda p: len(str(p)))
                exe = str(exes[0]) if exes else None
            if name and exe:
                out.append(AppCandidate(name, "epic", exe, "file", Path(exe).name))
        return out

    def open(self, candidate: AppCandidate) -> dict[str, Any]:
        # T2-app-startfile-no-error-042: capturamos OSError y devolvemos
        # un dict estructurado con detalle del candidate.
        try:
            os.startfile(candidate.launch)  # type: ignore[attr-defined]
        except OSError as exc:
            return {
                "ok": False,
                "error": f"os.startfile failed: {exc}",
                "candidate": {"name": candidate.name, "launch": str(candidate.launch), "launch_type": candidate.launch_type},
            }
        return {"ok": True, "candidate": {"name": candidate.name, "launch": str(candidate.launch), "launch_type": candidate.launch_type}}


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


def _is_private_host(host: str) -> bool:
    """T2-web-no-redirect-cap-014: rechaza loopback/RFC1918/link-local."""
    import ipaddress
    import socket
    if not host:
        return False
    host_norm = host.split(":", 1)[0].strip("[]")
    if host_norm.lower() in {"localhost", "ip6-localhost", "ip6-loopback"}:
        return True
    # Si es IP literal, comprobamos directamente.
    try:
        ip = ipaddress.ip_address(host_norm)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    except ValueError:
        pass
    # Si es hostname, resolvemos y comprobamos cada IP.
    try:
        infos = socket.getaddrinfo(host_norm, None)
    except socket.gaierror:
        return False
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except (ValueError, IndexError):
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


class _SSRFGuardRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Cap redirect count and re-validate each redirect target host."""

    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlparse
        host = urlparse(newurl).hostname or ""
        if _is_private_host(host):
            raise urllib.error.HTTPError(newurl, 451, f"refused redirect to private host: {host}", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


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
            "system_time": self.system_time,
            "list_processes": self.list_processes,
            "list_windows": self.list_windows,
            "app_search": self.app_search,
            "app_open": self.app_open,
            "app_close": self.app_close,
            "filesystem_list": self.filesystem_list,
            "filesystem_read": self.filesystem_read,
            "filesystem_write": self.filesystem_write,
            "filesystem_search": self.filesystem_search,
            "filesystem_delete": self.filesystem_delete,
            "web_open_url": self.web_open_url,
            "terminal_run": self.terminal_run,
            "clipboard_read": self.clipboard_read,
            "clipboard_write": self.clipboard_write,
            "gui_screenshot": self.gui_screenshot,
            "gui_click": self.gui_click,
            "gui_type": self.gui_type,
            "gui_keypress": self.gui_keypress,
            "memory_save": self.memory_save,
            "memory_recall": self.memory_recall,
            "memory_list": self.memory_list,
            "memory_delete": self.memory_delete,
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

    def t_gui(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="screenshot")
        if action == "screenshot":
            return self.gui_screenshot(args)
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
            result = self.web_open_url({"url": args.get("url") or query})
            result.update(content_verified=False, completion_status="opened_url")
            return result
        if action in {"youtube_play", "play_youtube", "play_media"}:
            return self.browser_youtube_play(args)
        if action in {"media_pause", "pause_video"}:
            return self.audio_media_control({"action": "media_play_pause"})
        if action in {"media_stop", "stop_video"}:
            return self.audio_media_control({"action": "media_stop"})
        if action == "search":
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
        return _err("unknown browser action", action=action)

    def t_web(self, args: dict[str, Any]) -> dict[str, Any]:
        action = _action(args, default="search")
        if action in {"search", "search_web"}:
            return self.web_search(args)
        if action == "open":
            return self.web_open_url(args)
        if action == "read":
            return self.web_read(args)
        if action == "research":
            return self.web_research(args)
        return _err("unknown web action", action=action)

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
        return _err("unknown uia action", action=action)

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
            if path:
                return self.knowledge.ingest_file(Path(path).expanduser(), title=str(args.get("title") or "") or None)
            return self.knowledge.ingest_text(str(args.get("text") or ""), source=str(args.get("source") or "user_text"), title=str(args.get("title") or "") or None)
        if action == "search":
            rerank_arg = args.get("rerank")
            return self.knowledge.search(
                str(args.get("query") or ""),
                limit=int(args.get("limit", 5)),
                rerank=None if rerank_arg is None else bool(rerank_arg),
            )
        if action == "list":
            return self.knowledge.list_documents(limit=int(args.get("limit", 100)))
        if action == "delete":
            return self.knowledge.delete(str(args.get("doc_id") or ""))
        return _err("unknown knowledge action", action=action)

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
            return _ok(enabled=self.safety_enabled)
        if action == "pending":
            return self.state.list_confirmations(include_resolved=bool(args.get("include_resolved", False)))
        confirmation_id = str(args.get("confirmation_id") or args.get("id") or "").strip()
        if action == "cancel":
            if not confirmation_id:
                return _err("missing confirmation_id")
            return self.state.resolve_confirmation(confirmation_id, "cancelled")
        if action == "confirm":
            if not confirmation_id:
                pending = self.state.list_confirmations().get("confirmations", [])
                if len(pending) == 1:
                    confirmation_id = str(pending[0]["id"])
            if not confirmation_id:
                return _err("missing confirmation_id")
            item_result = self.state.get_confirmation(confirmation_id)
            if not item_result.get("ok"):
                return item_result
            item = item_result["confirmation"]
            if item.get("status") != "pending":
                return _err("confirmation is not pending", confirmation=item)
            result = self.execute(str(item["tool"]), {**dict(item.get("args") or {}), "confirmed": True})
            self.state.resolve_confirmation(confirmation_id, "confirmed", result)
            return _ok(confirmation_id=confirmation_id, executed_tool=item["tool"], executed_args=item.get("args"), result=result)
        return _err("unknown safety action", action=action)

    def system_time(self, args: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now()
        return _ok(iso=now.isoformat(), human=now.strftime("%H:%M:%S %d/%m/%Y"))

    def list_processes(self, args: dict[str, Any]) -> dict[str, Any]:
        limit = int(args.get("limit", 40))
        proc = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=15)
        rows = csv.reader(proc.stdout.splitlines())
        items = []
        for row in rows:
            if len(row) >= 2:
                items.append({"name": row[0], "pid": row[1]})
            if len(items) >= limit:
                break
        return _ok(processes=items, exit_code=proc.returncode)

    def list_windows(self, args: dict[str, Any]) -> dict[str, Any]:
        limit = int(args.get("limit", 30))
        script = (
            "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
            f"Select-Object -First {limit} ProcessName,MainWindowTitle,Id | ConvertTo-Json -Depth 3"
        )
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=15)
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
        return _ok(windows=windows)

    def system_cpu_ram_gpu(self, args: dict[str, Any]) -> dict[str, Any]:
        script = r"""
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name,LoadPercentage
$os = Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory
$gpu = Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion
[PSCustomObject]@{ cpu=$cpu; os=$os; gpu=$gpu } | ConvertTo-Json -Depth 4
"""
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
        # CC-103: parse defensivo.
        ok, info = parse_ps_json(proc.stdout)
        if not ok:
            return _err("system_cpu_ram_gpu invalid JSON", stdout=info, stderr=_truncate(proc.stderr, 1000), exit_code=proc.returncode)
        return _ok(info=info, exit_code=proc.returncode)

    def system_disk(self, args: dict[str, Any]) -> dict[str, Any]:
        script = "Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID,DriveType,Size,FreeSpace,VolumeName | ConvertTo-Json -Depth 3"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
        ok, data = parse_ps_json(proc.stdout)
        if not ok:
            return _err("system_disk invalid JSON", stdout=data, stderr=_truncate(proc.stderr, 1000), exit_code=proc.returncode)
        if data is None:
            data = []
        if isinstance(data, dict):
            data = [data]
        return _ok(disks=data, exit_code=proc.returncode)

    def system_battery(self, args: dict[str, Any]) -> dict[str, Any]:
        script = "Get-CimInstance Win32_Battery | Select-Object Name,EstimatedChargeRemaining,BatteryStatus | ConvertTo-Json -Depth 3"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
        ok, data = parse_ps_json(proc.stdout)
        if not ok:
            return _err("system_battery invalid JSON", stdout=data, stderr=_truncate(proc.stderr, 1000), exit_code=proc.returncode)
        return _ok(battery=data, exit_code=proc.returncode)

    def system_brightness_get(self, args: dict[str, Any]) -> dict[str, Any]:
        script = "Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness | Select-Object CurrentBrightness | ConvertTo-Json"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
        ok, data = parse_ps_json(proc.stdout)
        if not ok:
            return _err("system_brightness_get invalid JSON", stdout=data, stderr=_truncate(proc.stderr, 1000), exit_code=proc.returncode)
        return _ok(brightness=data, exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 1000))

    def system_brightness_set(self, args: dict[str, Any]) -> dict[str, Any]:
        level = max(0, min(100, int(args.get("level", 50))))
        script = f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
        return _ok(level=level, exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 1000))

    def audio_get_volume(self, args: dict[str, Any]) -> dict[str, Any]:
        try:
            volume = self._audio_endpoint_volume()
            return _ok(level=int(volume.GetMasterVolumeLevelScalar() * 100), muted=bool(volume.GetMute()))
        except ImportError:
            return _err("pycaw/comtypes not installed. Run: pip install pycaw comtypes")

    def audio_set_volume(self, args: dict[str, Any]) -> dict[str, Any]:
        level = max(0, min(100, int(args.get("level", 50))))
        try:
            volume = self._audio_endpoint_volume()
            volume.SetMasterVolumeLevelScalar(level / 100, None)
            return _ok(level=int(volume.GetMasterVolumeLevelScalar() * 100))
        except ImportError:
            return _err("pycaw/comtypes not installed. Run: pip install pycaw comtypes")

    def audio_mute(self, args: dict[str, Any]) -> dict[str, Any]:
        state = bool(args.get("state", True))
        try:
            volume = self._audio_endpoint_volume()
            volume.SetMute(int(state), None)
            return _ok(muted=bool(volume.GetMute()))
        except ImportError:
            return _err("pycaw/comtypes not installed. Run: pip install pycaw comtypes")

    def _audio_endpoint_volume(self) -> Any:
        # Returns an IAudioEndpointVolume COM pointer. Typed as Any because
        # pycaw/comtypes methods (GetMasterVolumeLevelScalar, GetMute, SetMute,
        # SetMasterVolumeLevelScalar) are dispatched dynamically through COM
        # and have no stubs that pyright can introspect.
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL  # type: ignore[import-not-found]
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore[import-not-found]

        device: Any = AudioUtilities.GetSpeakers()
        if device is None:
            raise RuntimeError("no audio endpoint device available")
        if hasattr(device, "EndpointVolume"):
            return device.EndpointVolume
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    def audio_devices(self, args: dict[str, Any]) -> dict[str, Any]:
        script = "Get-PnpDevice -Class AudioEndpoint | Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Depth 3"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=15)
        raw = proc.stdout.strip()
        data = json.loads(raw) if raw else []
        if isinstance(data, dict):
            data = [data]
        return _ok(devices=data, exit_code=proc.returncode)

    def audio_set_default(self, args: dict[str, Any]) -> dict[str, Any]:
        return _err("setting default audio device needs an external helper such as SoundVolumeView or custom WASAPI policy config", requested=args.get("name"))

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
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
        ok, data = parse_ps_json(proc.stdout)
        if not ok:
            return _err("window_active invalid JSON", stdout=data, stderr=_truncate(proc.stderr, 1000), exit_code=proc.returncode)
        return _ok(active=data, exit_code=proc.returncode)

    def window_control(self, action: str, title_query: str) -> dict[str, Any]:
        if not title_query:
            return _err("missing window title/query")
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
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=10)
        ok, data = parse_ps_json(proc.stdout)
        if not ok:
            data = {"ok": False, "error": _truncate(proc.stderr, 1000)}
        elif data is None:
            data = {"ok": False, "error": proc.stderr}
        return _ok(result=data, exit_code=proc.returncode)

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
        # Auto-verify: wait briefly and re-check if a process/window with the
        # target name is now present. Steam-launched games can take longer to
        # show a window, so we also accept the resolved exe name. If
        # auto-verify succeeds, surface status=done so the LLM does not say
        # "could not verify" when the app actually opened. The user can
        # disable this with GEMMA4_APP_OPEN_AUTOVERIFY=false (e.g. for slow
        # Steam launches where the verification window would always be too
        # short).
        import os as _os
        autoverify = (_os.environ.get("GEMMA4_APP_OPEN_AUTOVERIFY") or "").strip().casefold()
        verified = False
        verify_evidence: dict[str, Any] = {}
        if autoverify not in {"false", "0", "no", "off"}:
            try:
                wait_s = float(_os.environ.get("GEMMA4_APP_OPEN_AUTOVERIFY_WAIT_S") or "2.5")
            except ValueError:
                wait_s = 2.5
            time.sleep(max(0.0, min(wait_s, 10.0)))
            post = self.verify_app_opened({"name": name})
            if post.get("found"):
                verified = True
                verify_evidence = {"verify_app_opened_after_wait_s": wait_s, "match": post.get("match")}
            else:
                # Also try matching by the resolved exe/process name when the
                # friendly name differs from the actual window (e.g. "Marvel
                # Rivals" -> "MarvelRivals.exe").
                process_hint = best.process_name or ""
                if process_hint and process_hint.casefold() != name.casefold():
                    post2 = self.verify_app_opened({"name": process_hint})
                    if post2.get("found"):
                        verified = True
                        verify_evidence = {"verify_app_opened_via_process": process_hint, "match": post2.get("match")}
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
        window_close = _close_windows_by_query(name)
        taskkill_results = []
        closed = int(window_close.get("count") or 0) > 0

        for exe in candidates:
            proc = subprocess.run(["taskkill", "/IM", exe, "/F"], capture_output=True, text=True, timeout=20)
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
        items = []
        for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))[:limit]:
            stat = child.stat()
            items.append({
                "name": child.name,
                "path": str(child.resolve()),
                "type": "dir" if child.is_dir() else "file",
                "size": stat.st_size if child.is_file() else None,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            })
        return _ok(path=str(path.resolve()), items=items)

    def filesystem_read(self, args: dict[str, Any]) -> dict[str, Any]:
        path = Path(str(args.get("path", "")).strip()).expanduser()
        limit = int(args.get("max_chars", 12000))
        if not path.is_file():
            return _err("file does not exist", path=str(path))
        content = path.read_text(encoding="utf-8", errors="replace")
        return _ok(path=str(path.resolve()), content=_truncate(content, limit), size_bytes=path.stat().st_size)

    def filesystem_write(self, args: dict[str, Any]) -> dict[str, Any]:
        raw_path = str(args.get("path", "")).strip()
        if not raw_path:
            return _err("empty path")
        path = Path(raw_path).expanduser()
        content = str(args.get("content", ""))
        checkpoint = self._checkpoint_existing_path(f"filesystem write {path}", path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return _ok(path=str(path.resolve()), bytes=len(content.encode("utf-8")), checkpoint=checkpoint.get("checkpoint"))

    def filesystem_search(self, args: dict[str, Any]) -> dict[str, Any]:
        root = Path(str(args.get("root", ".")).strip() or ".").expanduser()
        pattern = str(args.get("pattern", "*")).strip() or "*"
        limit = int(args.get("limit", 50))
        if not root.exists():
            return _err("root does not exist", root=str(root))
        matches = []
        for path in root.rglob(pattern):
            matches.append({"path": str(path.resolve()), "type": "dir" if path.is_dir() else "file"})
            if len(matches) >= limit:
                break
        return _ok(root=str(root.resolve()), pattern=pattern, matches=matches)

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
            return _err("empty url")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        opened = webbrowser.open(url)
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
            return _err("missing url")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        limit = max(1000, min(40000, int(args.get("max_chars", 12000))))
        fetched = _http_get_text(url, timeout=int(args.get("timeout_sec", 12)))
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
        """CC-101: gate de confirmación independiente de `safety_enabled`.

        Pattern alineado con `form_filler._form_submit`. Devuelve `None` si
        la llamada está autorizada para proseguir; devuelve un dict
        `needs_confirmation` en caso contrario.

        `routine_context` y `confirmed_at_create` son inyectados por el
        dispatcher cuando la step proviene de una routine/watcher: NUNCA
        aparecen en `COMPOUND_TOOL_SCHEMAS` (filtrados en `execute`).
        """
        if bool(args.get("confirmed")):
            return None
        if routine_context:
            if confirmed_at_create:
                return None
            return _err(
                f"{tool_name}.{action} blocked: routine step missing confirmed_at_create",
                status="blocked_needs_confirmation",
                tool=tool_name,
                action=action,
            )
        pending = self.state.create_confirmation(
            tool_name,
            _redact_sensitive(
                {**{k: v for k, v in args.items() if k not in {"routine_context", "confirmed_at_create"}}, "confirmed": True}
            ),
            reason=reason,
            risk=risk,
        )
        return _err(
            f"{tool_name}.{action} requires confirmation; call safety(confirm, id=...) or re-call with confirmed=true",
            status="needs_confirmation",
            verified=False,
            completion_status="needs_user_confirmation",
            confirmation=pending.get("confirmation"),
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
        started = time.monotonic()
        proc = subprocess.run(run_arg, cwd=cwd, shell=shell, capture_output=True, text=True, timeout=timeout)
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
        )

    def clipboard_read(self, args: dict[str, Any]) -> dict[str, Any]:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"], capture_output=True, text=True, timeout=10)
        return _ok(content=_truncate(proc.stdout, int(args.get("max_chars", 4000))), exit_code=proc.returncode)

    def clipboard_write(self, args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("content", ""))
        script = "$txt = [Console]::In.ReadToEnd(); Set-Clipboard -Value $txt"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], input=text, capture_output=True, text=True, timeout=10)
        return _ok(wrote_chars=len(text), exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 1000))

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
  $hay = @(
    $e.Current.Name,
    $e.Current.AutomationId,
    $e.Current.ClassName,
    $e.Current.ControlType.ProgrammaticName
  ) -join " "
  return $hay.ToLowerInvariant().Contains($needle)
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
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            return _err("screenshot failed", stderr=_truncate(proc.stderr.strip(), 2000))
        # CC-103: parse defensivo.
        ok, data = parse_ps_json(proc.stdout)
        if not ok or not isinstance(data, dict):
            return _err("screenshot invalid JSON", stdout=data if isinstance(data, str) else None, stderr=_truncate(proc.stderr, 1000))
        if data.get("ok") is False:
            return _err(str(data.get("error") or "screenshot failed"), status="needs_user")
        return _ok(image_path=str(Path(data["path"]).resolve()), width=data["width"], height=data["height"], left=data["left"], top=data["top"], monitor=mode)

    def gui_click(self, args: dict[str, Any]) -> dict[str, Any]:
        x = int(args.get("x") or 0)
        y = int(args.get("y") or 0)
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
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
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

    def gui_type(self, args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("text", ""))
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
        script = "Add-Type -AssemblyName System.Windows.Forms; $t=[Console]::In.ReadToEnd(); [System.Windows.Forms.SendKeys]::SendWait($t)"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], input=text_to_send, capture_output=True, text=True, timeout=20)
        return _ok(chars=len(text), exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 1000))

    def gui_keypress(self, args: dict[str, Any]) -> dict[str, Any]:
        # CC-100 / T3-gui-keypress-sendkeys-injection-009: env-var indirection
        # para nunca f-stringear `keys` en el script PS.
        keys = str(args.get("keys", "")).strip()
        if not keys:
            return _err("empty keys")
        sendkeys = {
            "ENTER": "{ENTER}",
            "ESC": "{ESC}",
            "ESCAPE": "{ESC}",
            "TAB": "{TAB}",
            "CTRL+L": "^l",
            "CTRL+A": "^a",
            "CTRL+C": "^c",
            "CTRL+V": "^v",
            "ALT+F4": "%{F4}",
        }.get(keys.upper(), keys)
        env = {**os.environ, "GEMMA4_KEYS": sendkeys}
        script = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait($env:GEMMA4_KEYS)"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=10)
        return _ok(keys=keys, sendkeys=sendkeys, exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 1000))

    def verify_app_opened(self, args: dict[str, Any]) -> dict[str, Any]:
        name = str(args.get("name") or args.get("query") or "").strip()
        if not name:
            return _err("missing name")
        processes = self.list_processes({"limit": 300}).get("processes", [])
        windows = self.list_windows({"limit": 120}).get("windows", [])
        q = _fold(name)
        proc_matches = [p for p in processes if q in _fold(str(p.get("name", "")))]
        win_matches = [w for w in windows if q in _fold(str(w.get("title", ""))) or q in _fold(str(w.get("process", "")))]
        return _ok(found=bool(proc_matches or win_matches), process_matches=proc_matches[:10], window_matches=win_matches[:10])

    def verify_file_exists(self, args: dict[str, Any]) -> dict[str, Any]:
        path = Path(str(args.get("path", "")).strip()).expanduser()
        return _ok(path=str(path), exists=path.exists(), is_file=path.is_file(), is_dir=path.is_dir(), size=path.stat().st_size if path.exists() and path.is_file() else None)

    def verify_window_exists(self, args: dict[str, Any]) -> dict[str, Any]:
        title = str(args.get("title") or args.get("query") or "").strip()
        if not title:
            return _err("missing title/query")
        windows = self.list_windows({"limit": 120}).get("windows", [])
        q = _fold(title)
        matches = [w for w in windows if q in _fold(str(w.get("title", ""))) or q in _fold(str(w.get("process", "")))]
        return _ok(found=bool(matches), matches=matches[:10])

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

COMPOUND_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"type": "function", "function": {"name": "system", "description": "Compound Windows system tool. Actions: time, processes, cpu_ram_gpu, disk, battery, brightness_get, brightness_set, shutdown, restart, sleep.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "level": {"type": "integer"}, "limit": {"type": "integer"}, "delay_sec": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "audio", "description": "Compound audio/media tool. Actions: get_volume, set_volume, mute, devices, set_default, media_play_pause, media_stop, next, previous. set_volume uses level 0-100; mute uses state boolean. Use media_play_pause for 'para/pausa el video' or stopping current music/video playback.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "level": {"type": "integer"}, "state": {"type": "boolean"}, "name": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "app", "description": "Compound installed app/game tool with dynamic discovery. Actions: search, open, close, uninstall. Use user-facing name, not hardcoded exe names.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer"}, "refresh": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "steam", "description": "Compound Steam tool. Actions: open, library, store, list_games, launch_game, search_library, search_store, store_page, install. Use library for 've a mi biblioteca'. Use store_page/search_store for 'pagina de la tienda de X'; it resolves an AppID and opens steam://store/<appid> inside the Steam client, not a normal browser. search_library first matches local Steam metadata and opens the matching library detail by AppID; otherwise it attempts GUI search and returns unverified with screenshot. Use query/name for game title or appid for direct install.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "query": {"type": "string"}, "name": {"type": "string"}, "appid": {"type": "string"}, "delay_sec": {"type": "number"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "window", "description": "Compound window management tool. Actions: list, active, focus, close, minimize, maximize, restore, move_resize. Use title/query to target a window.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "title": {"type": "string"}, "query": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}, "width": {"type": "integer"}, "height": {"type": "integer"}, "limit": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "gui", "description": "Compound GUI/mouse/keyboard tool. Actions: screenshot, click, double_click, right_click, type, keypress, hotkey, scroll, drag, wait_for, locate_text, click_text, locate_image. locate_text/click_text use local OCR when available and return screen_x/screen_y (screen-space coordinates, pre-translated); raw center_x/center_y are image-local. screenshot accepts monitor='primary'|'all'|'<index>' (default 'all'=VirtualScreen). type escapes SendKeys metacharacters (+^%~(){}[]) by default; pass raw_sendkeys=true to send control sequences literally.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}, "x1": {"type": "integer"}, "y1": {"type": "integer"}, "x2": {"type": "integer"}, "y2": {"type": "integer"}, "text": {"type": "string"}, "keys": {"type": "string"}, "hotkey": {"type": "string"}, "amount": {"type": "integer"}, "target": {"type": "string"}, "image": {"type": "string"}, "lang": {"type": "string"}, "min_conf": {"type": "integer"}, "timeout_sec": {"type": "integer"}, "monitor": {"type": "string"}, "raw_sendkeys": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "vision", "description": "Compound Gemma-4-vision/OCR bridge. Actions: describe_screen, find_element, ocr, compare_before_after. OCR uses local Tesseract if available; screenshots are also re-injected for native Gemma 4 visual reasoning.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "target": {"type": "string"}, "text": {"type": "string"}, "image_path": {"type": "string"}, "lang": {"type": "string"}, "min_conf": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "browser", "description": "Compound browser control tool. Actions: open, search, youtube_play, media_pause, media_stop, active_tab_title, click, find, research. open/search mainly navigate the browser and are not proof of reading content. Use web(action='research') for real investigation. youtube_play opens a direct YouTube video when possible and should be used for 'pon/reproduce una cancion'. media_pause/media_stop pause current playback; use them for 'para el video'. If browser is provided, opens that browser app first and navigates there via GUI; do not use browser='YouTube' because YouTube is a site, not a browser.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "url": {"type": "string"}, "query": {"type": "string"}, "song": {"type": "string"}, "title": {"type": "string"}, "engine": {"type": "string"}, "browser": {"type": "string"}, "target": {"type": "string"}, "delay_sec": {"type": "number"}, "post_open_delay_sec": {"type": "number"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "web", "description": "Compound web research tool. Actions: search, read, research, open. search returns search results with snippets; read fetches and extracts a page; research searches and reads several sources. Use this for 'investiga', current facts, sources, or when the user expects an answer from the internet. Use browser only when the goal is to open/navigate a visible browser.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "query": {"type": "string"}, "url": {"type": "string"}, "limit": {"type": "integer"}, "search_limit": {"type": "integer"}, "read_limit": {"type": "integer"}, "per_page_chars": {"type": "integer"}, "max_chars": {"type": "integer"}, "timeout_sec": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "uia", "description": "Compound Windows UI Automation tool. Actions: tree, find, click, focus, set_value. Prefer this before raw GUI clicks when interacting with standard Windows app controls because it returns names, control types, automation ids, bounds and clickable points. Use window/title to scope to an app window and query/text/target to find controls.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "query": {"type": "string"}, "text": {"type": "string"}, "target": {"type": "string"}, "window": {"type": "string"}, "title": {"type": "string"}, "value": {"type": "string"}, "text_value": {"type": "string"}, "limit": {"type": "integer"}, "timeout_sec": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "filesystem", "description": "Compound filesystem tool. Actions: list, read, write, search, delete, copy, move, rename, mkdir, diff, archive, unarchive, open. Mutating actions create local checkpoints with rollback plans when possible. delete requires confirmed=true (hard gate). copy honors overwrite=false (returns needs_user if dst exists). diff has a max_bytes cap (default 50MB combined); archive has max_files (50000) and max_bytes (5GB) caps to avoid runaway operations.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "path": {"type": "string"}, "src": {"type": "string"}, "dst": {"type": "string"}, "source": {"type": "string"}, "destination": {"type": "string"}, "content": {"type": "string"}, "root": {"type": "string"}, "pattern": {"type": "string"}, "recursive": {"type": "boolean"}, "overwrite": {"type": "boolean"}, "new_name": {"type": "string"}, "left": {"type": "string"}, "right": {"type": "string"}, "archive": {"type": "string"}, "limit": {"type": "integer"}, "max_chars": {"type": "integer"}, "max_bytes": {"type": "integer"}, "max_files": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "state", "description": "Compound operational state tool. Actions: resources, cleanup_plan, cleanup, checkpoint, checkpoints, rollback_plan, rollback, note. Tracks resources opened by the agent and reversible checkpoints; cleanup executes registered cleanup tools. WARNING: state(action='rollback') executes every stored rollback step verbatim via this tool's registry, including destructive ones (e.g. filesystem.delete to undo a copy). Prefer state(action='rollback_plan') first to review the steps, then explicit rollback.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "resource_id": {"type": "string"}, "checkpoint_id": {"type": "string"}, "label": {"type": "string"}, "text": {"type": "string"}, "include_closed": {"type": "boolean"}, "rollback": {"type": "array", "items": {"type": "object"}}, "metadata": {"type": "object"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "input", "description": "Compound keyboard/language tool. Actions: language_list, keyboard_layouts, current_keyboard, set_language_list, switch_keyboard. Uses Windows language APIs; changes are checkpointed so they can be rolled back.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "language_tag": {"type": "string"}, "language_tags": {"type": "array", "items": {"type": "string"}}, "force": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "env", "description": "Compound environment variable tool. Actions: get, set, delete, list. scope is process, user, or machine. process affects only this agent session; user/machine are persistent Windows environment scopes and changes create rollback checkpoints.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "scope": {"type": "string"}, "name": {"type": "string"}, "value": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "registry", "description": "Compound safe registry tool. Actions: query, export, import, add, delete, backup. add/delete export a .reg backup first and create rollback checkpoints.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "key": {"type": "string"}, "path": {"type": "string"}, "name": {"type": "string"}, "value_name": {"type": "string"}, "type": {"type": "string"}, "data": {"type": "string"}, "value": {"type": "string"}, "file": {"type": "string"}, "dst": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "download", "description": "Compound download/integrity tool. Actions: fetch, hash, signature. fetch uses Invoke-WebRequest, then SHA256 and Authenticode for executables; without expected hash or valid signature it returns needs_verification.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "url": {"type": "string"}, "path": {"type": "string"}, "dst": {"type": "string"}, "sha256": {"type": "string"}, "expected_sha256": {"type": "string"}, "algorithm": {"type": "string"}, "overwrite": {"type": "boolean"}, "timeout_sec": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "email", "description": "Compound email tool. Actions: status, draft, send. Real sending uses Microsoft Graph sendMail only when GEMMA4_GRAPH_TOKEN or MS_GRAPH_TOKEN is configured; otherwise returns needs_user instead of pretending.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}, "save_to_sent": {"type": "boolean"}, "timeout_sec": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "reminder", "description": "Compound reminder tool. Actions: status, create, list, delete. Default backend stores local reminders in agent state; graph backend requires Microsoft Graph auth and returns needs_user if missing.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "backend": {"type": "string"}, "title": {"type": "string"}, "text": {"type": "string"}, "due": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "browser_real", "description": "Compound real browser automation tool using Playwright. Actions: status, open, goto, tabs, click, fill, press, text, screenshot, evaluate, connect_cdp, close, attach_visible, active_tab, tab_open, tab_close, tab_focus, click_text, extract, wait_for_download, set_download_path. attach_visible connects to the user's Chrome/Edge/Opera/Brave only if it's already running with --remote-debugging-port=9222; otherwise returns needs_user with the launch command. extract supports mode=main_text|tables|links|html. wait_for_download requires the click that triggers the download to happen inside the same call chain; ALSO not supported for CDP-attached visible sessions (Browser.downloadProgress raw event listening is not wired) — use the user's browser download manager directly in that case.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "session_id": {"type": "string"}, "page_id": {"type": "integer"}, "url": {"type": "string"}, "query": {"type": "string"}, "endpoint": {"type": "string"}, "browser": {"type": "string"}, "port": {"type": "integer"}, "selector": {"type": "string"}, "text": {"type": "string"}, "value": {"type": "string"}, "key": {"type": "string"}, "script": {"type": "string"}, "headless": {"type": "boolean"}, "new_tab": {"type": "boolean"}, "screenshot": {"type": "boolean"}, "full_page": {"type": "boolean"}, "wait_until": {"type": "string"}, "timeout_sec": {"type": "integer"}, "max_chars": {"type": "integer"}, "mode": {"type": "string"}, "exact": {"type": "boolean"}, "target": {"type": "string"}, "save_dir": {"type": "string"}, "path": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "knowledge", "description": "Compound local RAG/knowledge-base tool. Actions: status, ingest, search, list, delete. Uses local SQLite FTS5 + optional cross-encoder rerank (ms-marco-MiniLM-L-6-v2, ~80MB, lazy-loaded). Pass rerank=true/false to override the env default GEMMA4_KNOWLEDGE_RERANK. With rerank, we over-fetch 4x BM25 candidates and re-rank with the cross-encoder for higher precision on >50 docs.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "path": {"type": "string"}, "text": {"type": "string"}, "source": {"type": "string"}, "title": {"type": "string"}, "query": {"type": "string"}, "doc_id": {"type": "string"}, "limit": {"type": "integer"}, "rerank": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "office", "description": "Compound local Office document tool. Actions: status, create_presentation, edit_presentation, create_document, edit_document, create_spreadsheet, edit_spreadsheet, export_pdf, inspect, open. Use create_presentation for PowerPoint requests; returns needs_dependency if python-pptx/python-docx/openpyxl/LibreOffice are missing.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "path": {"type": "string"}, "title": {"type": "string"}, "topic": {"type": "string"}, "content": {"type": "string"}, "body": {"type": "string"}, "slides": {"type": "array", "items": {"type": "object"}}, "rows": {"type": "array", "items": {"type": "array", "items": {}}}, "template": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "audio_device", "description": "Compound Windows audio device/routing tool. Actions: status, list, set_default, set_default_communications, set_app_route, get_app_routes, snapshot, restore. set_default uses SoundVolumeView roles 0+1 (Console+Multimedia); set_default_communications uses role 2. set_app_route uses /SetAppDefault and accepts app=<process.exe or PID>, device=<friendly name|DefaultRenderDevice|DefaultCaptureDevice>, role=0|1|2|all, direction=render|capture. get_app_routes lists per-app overrides via /sjson. snapshot/restore save and replay per-role defaults.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "device": {"type": "string"}, "app": {"type": "string"}, "process": {"type": "string"}, "role": {"type": "string"}, "direction": {"type": "string"}, "checkpoint_id": {"type": "string"}, "snapshot": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "notification", "description": "Compound local notification/timer/alarm/reminder tool. Actions: status, toast_now, toast_schedule, timer_start, timer_cancel, timer_update, timer_list, alarm_create, alarm_cancel, alarm_update, alarm_list, reminder_create, reminder_update, reminder_delete, reminder_list, notification_update, notify_sound, delete, list, history. Uses Windows Scheduled Tasks under \\Gemma4Agent\\ for persistent local notifications; history merges agent state with Get-ScheduledTaskInfo LastRun/NextRun/LastTaskResult.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "title": {"type": "string"}, "text": {"type": "string"}, "message": {"type": "string"}, "due": {"type": "string"}, "time": {"type": "string"}, "seconds": {"type": "integer"}, "minutes": {"type": "integer"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "task_name": {"type": "string"}, "kind": {"type": "string"}, "limit": {"type": "integer"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "routine", "description": "Compound local routine/automation tool. Actions: status, create, list, enable, disable, delete, run_now, simulate, history, import. A routine stores a trigger and ordered steps like [{tool:'audio', args:{action:'set_volume', level:20}}]. Triggers: manual, once (trigger={type:'once', at:'2026-05-15 09:00'}), cron (trigger={type:'cron', cadence:'daily|weekly|hourly|minutes', at:'09:00', days_of_week:['Monday']}), on_app_open / on_app_close (trigger={type:'on_app_open', process:'steam.exe', interval_minutes:2}) which install a process watcher fired on the rising/falling edge. Scheduled triggers fire python -m gemma4_agent.routine_runner. action='import' bulk-imports phrase routines from a TriggerCMD commands.json (source='triggercmd', entries=[...] inline or json_path='<file>'); allowParams=true entries are skipped with a reason for manual setup.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "label": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "trigger": {}, "enabled": {"type": "boolean"}, "steps": {"type": "array", "items": {"type": "object"}}, "limit": {"type": "integer"}, "include_closed": {"type": "boolean"}, "source": {"type": "string"}, "entries": {}, "json_path": {"type": "string"}, "path": {"type": "string"}, "overwrite_same_phrase": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "media", "description": "Compound media playback tool. Actions: status, play, pause, resume, play_pause, stop, next, previous, queue_add, queue_clear, queue_list, now_playing, volume_for_app, open_local, search_local_library, cast_lan. play accepts provider=youtube|vlc|local_file (auto from path). now_playing reads the Windows.Media.Control GlobalSystemMediaTransportControlsSessionManager via PowerShell+WinRT and reports title, artist, album, playback_status and timeline. queue is a local in-state queue for offline planning.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "query": {"type": "string"}, "song": {"type": "string"}, "title": {"type": "string"}, "provider": {"type": "string"}, "path": {"type": "string"}, "url": {"type": "string"}, "app": {"type": "string"}, "level": {"type": "integer"}, "backend": {"type": "string"}, "root": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "source_manager", "description": "Compound local source/citation manager. Actions: status, save, add, list, sources, search, read, get, delete, snapshot_file. Stores source titles, URLs, snippets and file snapshots in local state for later citation/research.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "title": {"type": "string"}, "url": {"type": "string"}, "source": {"type": "string"}, "text": {"type": "string"}, "content": {"type": "string"}, "path": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer"}, "max_chars": {"type": "integer"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "dependency", "description": "Compound local dependency diagnostics. Actions: status, list, verify, explain_missing, install, repair. Reports Python modules/binaries needed by tools and gives install hints; install is advisory unless explicitly handled elsewhere.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "dependency": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "contacts", "description": "Compound local contacts tool. Actions: status, create, add, list, search, delete, update, import_vcard, export_vcard, resolve_recipient. Stores contacts locally in agent state. import_vcard/export_vcard parse and emit RFC 6350-style vCards (FN, N, EMAIL, TEL, NOTE). resolve_recipient scores contacts against a query so the agent can pick the right person before email/messaging actions.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "name": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}, "notes": {"type": "string"}, "query": {"type": "string"}, "recipient": {"type": "string"}, "limit": {"type": "integer"}, "include_closed": {"type": "boolean"}, "path": {"type": "string"}, "content": {"type": "string"}, "vcard": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "notes_tasks", "description": "Compound local notes/tasks tool. Actions include note_create/list/search/update/delete and task_create/list/search/complete/update/delete. Stores notes and tasks in local state.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "title": {"type": "string"}, "text": {"type": "string"}, "content": {"type": "string"}, "query": {"type": "string"}, "due": {"type": "string"}, "tags": {"type": "string"}, "limit": {"type": "integer"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "local_calendar", "description": "Compound local calendar/ICS tool. Actions: status, event_create, event_list, event_update, event_delete, ics_export, ics_import, list, delete. Stores offline calendar events in local state. ics_import parses RFC 5545 VEVENT blocks (with line folding) and normalizes DTSTART/DTEND from compact ICS form (20251231T230000Z) to ISO-8601.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "title": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}, "due": {"type": "string"}, "location": {"type": "string"}, "notes": {"type": "string"}, "path": {"type": "string"}, "content": {"type": "string"}, "ics": {"type": "string"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "habit_tracker", "description": "Compound local habit tracker. Actions: status, create, list, log, stats, delete. Stores habits and logs locally.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "name": {"type": "string"}, "title": {"type": "string"}, "frequency": {"type": "string"}, "at": {"type": "string"}, "value": {}, "note": {"type": "string"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "local_search", "description": "Compound local search tool. Actions: status, search, recent. Searches file names and optionally small text file contents under a local root without cloud.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "root": {"type": "string"}, "query": {"type": "string"}, "pattern": {"type": "string"}, "limit": {"type": "integer"}, "recursive": {"type": "boolean"}, "include_content": {"type": "boolean"}, "max_bytes": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "printer_scanner", "description": "Compound local printer/scanner tool. Actions: status, printers_list, printer_default_get, printer_default_set, print_queue, print_file, cancel_job, scanners_list, scan_document, list. print_file uses Start-Process -Verb Print with temporary default-printer swap to target a specific printer; cancel_job uses Remove-PrintJob. Scanner actions use the WIA COM API and return needs_dependency if no WIA scanner is connected.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "printer": {"type": "string"}, "path": {"type": "string"}, "file": {"type": "string"}, "job_id": {"type": "integer"}, "id": {"type": "integer"}, "device_id": {"type": "string"}, "output": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "desktop_layout", "description": "Compound desktop layout tool. Actions: status, windows, list_windows, displays, snapshot, restore. Snapshots top-level windows with rect/pid/process via Win32 EnumWindows+GetWindowRect; restore replays positions via MoveWindow. Pass snapshot_id or explicit windows list to restore.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "limit": {"type": "integer"}, "snapshot_id": {"type": "string"}, "checkpoint_id": {"type": "string"}, "windows": {"type": "array"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "backup_sync", "description": "Compound local backup tool. Actions: status, backup_create, list, restore, dedupe, verify. Creates ZIP backups, restores them with overwrite|skip|rename policy, finds duplicate files by SHA256, and verifies ZIP integrity.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "src": {"type": "string"}, "path": {"type": "string"}, "dst": {"type": "string"}, "id": {"type": "string"}, "backup_id": {"type": "string"}, "to": {"type": "string"}, "conflict": {"type": "string", "enum": ["overwrite", "skip", "rename"]}, "preview": {"type": "boolean"}, "min_size_bytes": {"type": "integer"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "document", "description": "Compound document ingestion tool for PDF/DOCX/XLSX/PPTX/HTML and plain text. Actions: status, extract_text, extract_tables, extract_images, ocr_pdf, summarize, ingest_to_knowledge, compare_documents. Each backend reports needs_dependency separately (pypdf for PDF text, pdfplumber for PDF tables, python-docx for DOCX, openpyxl for XLSX, python-pptx for PPTX, beautifulsoup4 for HTML, Tesseract+PyMuPDF or pdf2image for ocr_pdf). summarize does NOT call an LLM; it returns text_preview so the agent itself summarizes.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "path": {"type": "string"}, "a": {"type": "string"}, "b": {"type": "string"}, "left": {"type": "string"}, "right": {"type": "string"}, "out_dir": {"type": "string"}, "title": {"type": "string"}, "max_chars": {"type": "integer"}, "preview_chars": {"type": "integer"}, "lang": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "developer", "description": "Compound developer workflow tool. Actions: status, project_detect, run_tests, run_lint, run_format, git_status, git_diff, git_log, start_dev_server, stop_dev_server, list_dev_servers. project_detect inspects path for package.json, pyproject.toml, Cargo.toml, go.mod, etc. and reports stack + package manager. run_tests/lint/format dispatch by stack (pytest/ruff for python, npm/yarn/pnpm for node, cargo for rust, go for go). git_commit and git_push are intentionally NOT exposed; use terminal(...) explicitly so the user sees the command. start_dev_server spawns a detached subprocess and registers it in state for stop_dev_server to kill via taskkill /T.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "path": {"type": "string"}, "root": {"type": "string"}, "args": {"type": "array"}, "limit": {"type": "integer"}, "staged": {"type": "boolean"}, "command": {}, "server_id": {"type": "string"}, "pid": {"type": "integer"}, "timeout_sec": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "device_settings", "description": "Compound tool for WiFi, Bluetooth, displays and power plans. Actions: status, wifi_status, wifi_list, wifi_scan, wifi_connect (auto-creates WPA2-Personal profile when password= is passed), wifi_disconnect, wifi_add_profile (WPA2-Personal XML), wifi_delete_profile, bluetooth_status, display_list, power_plan_list, power_plan_get, power_plan_set. bluetooth_toggle, night_light, display_set_resolution are deferred (elevated/fragile). power_plan_set snapshots the previous plan for rollback.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "ssid": {"type": "string"}, "profile": {"type": "string"}, "adapter": {"type": "string"}, "guid": {"type": "string"}, "plan": {"type": "string"}, "password": {"type": "string"}, "key": {"type": "string"}, "auto_connect": {"type": "boolean"}, "all_users": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "game_launcher", "description": "Compound tool for non-Steam game launchers. Actions: status, discover, launch, open_library_page. discover scans Epic .item manifests, GOG registry, Xbox UWP packages, and Riot install DB. launch uses launcher-specific URIs (com.epicgames.launcher://, shell:AppsFolder, GOG exe, Riot client). Steam is handled by the separate `steam` tool.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "launcher": {"type": "string", "enum": ["epic", "gog", "xbox", "riot"]}, "game": {"type": "string"}, "query": {"type": "string"}, "name": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "media_edit", "description": "Compound ffmpeg-based audio/video editing tool. Actions: status, probe, trim, concat, extract_audio, subtitles_extract, normalize, thumbnail, transcode. Returns needs_dependency if ffmpeg is missing. normalize uses EBU R128 loudnorm (I=-23 LUFS, TP=-2 dB, LRA=7). transcode supports mp4/mkv/webm with libx264/libvpx-vp9. extract_audio supports mp3/aac/wav/flac/ogg/m4a.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "path": {"type": "string"}, "input": {"type": "string"}, "src": {"type": "string"}, "output": {"type": "string"}, "out": {"type": "string"}, "dst": {"type": "string"}, "inputs": {"type": "array"}, "start": {"type": "string"}, "duration": {"type": "string"}, "end": {"type": "string"}, "at": {"type": "string"}, "time": {"type": "string"}, "format": {"type": "string"}, "track": {"type": "integer"}, "crf": {"type": "integer"}, "preset": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "maintenance", "description": "Compound Windows maintenance/security tool. Actions: status, windows_update_status, defender_status, defender_quick_scan, firewall_status, event_logs_query, services_list, service_status, service_start, service_stop, disk_cleanup_describe, restore_point_create. defender_quick_scan blocks until done (up to 15min). disk_cleanup_describe returns the cleanmgr command but does NOT execute it. restore_point_create requires System Protection enabled and is rate-limited to 1/24h on consumer Windows. service_start/stop creates a rollback checkpoint with the reverse action.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "log": {"type": "string"}, "level": {"type": "integer"}, "hours": {"type": "integer"}, "limit": {"type": "integer"}, "name": {"type": "string"}, "query": {"type": "string"}, "description": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "watcher", "description": "Compound file/url watcher tool. Actions: status, list, watch_file, watch_url, check, delete. watch_file/url store a snapshot (mtime+size for files, sha256 of body for urls) and schedule a Scheduled Task that runs gemma4_agent.watcher_runner on the given interval. When the snapshot changes, the optional on_change={tool, args} is dispatched. check evaluates a watcher immediately without waiting for the schedule.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "path": {"type": "string"}, "url": {"type": "string"}, "on_change": {"type": "object"}, "interval_seconds": {"type": "integer"}, "name": {"type": "string"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "job_manager", "description": "Compound generic job tracker. Actions: status, start, list, log, status_of, cancel. start spawns a detached subprocess, redirects stdout/stderr to a log file, registers in state with PID. cancel uses taskkill /T to terminate the process tree. log returns tailed lines. Useful for any long-running command not tied to a specific tool.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "command": {}, "cwd": {"type": "string"}, "label": {"type": "string"}, "job_id": {"type": "string"}, "id": {"type": "string"}, "tail": {"type": "integer"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "network", "description": "Compound network diagnostics tool. Actions: status, ping, traceroute, dns_get, dns_set, dns_resolve, port_check, connections, public_ip. dns_set snapshots the previous DNS list per adapter for rollback (pass addresses=['AUTO'] to restore automatic DNS). firewall_allow/block/remove are intentionally NOT exposed; use terminal(netsh advfirewall) explicitly.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "host": {"type": "string"}, "target": {"type": "string"}, "name": {"type": "string"}, "port": {"type": "integer"}, "count": {"type": "integer"}, "max_hops": {"type": "integer"}, "adapter": {"type": "string"}, "addresses": {"type": "array"}, "state": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "data_analysis", "description": "Compound local data analysis tool using pandas + matplotlib. Actions: status, csv_profile, csv_describe, csv_query, csv_head, csv_to_xlsx, plot_histogram, plot_scatter, plot_line. csv_query uses pandas .query() expressions. Plots write PNG to data_analysis/ under state dir; matplotlib uses the Agg headless backend. Returns needs_dependency if pandas/matplotlib are missing.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "path": {"type": "string"}, "sep": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer"}, "n": {"type": "integer"}, "dst": {"type": "string"}, "column": {"type": "string"}, "x": {"type": "string"}, "y": {"type": "string"}, "x_col": {"type": "string"}, "y_col": {"type": "string"}, "bins": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "fact_check", "description": "Compound lexical fact-check tool. Actions: status, check, compare. TF-IDF + cosine similarity per chunk against the claim plus a negation-cue heuristic (EN+ES). Returns a verdict (supports / weakly_supports / contradicts / no_evidence) and ranked snippets. NO LLM call inside the tool: the agent writes the final answer with citations from the ranked matches. check accepts sources=[paths|ids|inline_texts] and reads from local knowledge by default.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "claim": {"type": "string"}, "text": {"type": "string"}, "sources": {"type": "array"}, "use_knowledge": {"type": "boolean"}, "limit": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "photo_library", "description": "Compound tool for local photo libraries. Actions: status, scan, exif, group_by_date, thumbnails, find_by_date. Requires Pillow for EXIF and thumbnails; scan works without it. group_by_date copies/moves/symlinks photos into YYYY-MM (or year|day) subfolders under output, using EXIF DateTimeOriginal with mtime fallback. Face-recognition and embeddings are intentionally deferred.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "path": {"type": "string"}, "root": {"type": "string"}, "output": {"type": "string"}, "dst": {"type": "string"}, "limit": {"type": "integer"}, "mode": {"type": "string", "enum": ["copy", "move", "symlink", "dry_run"]}, "granularity": {"type": "string", "enum": ["year", "month", "day"]}, "size": {}, "year": {"type": "integer"}, "month": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "container", "description": "Compound Docker / docker-compose wrapper. Actions: status, ps, ps_all, images, inspect, logs, start, stop, restart, exec, compose_up, compose_down, compose_ps. Returns needs_dependency if docker is not on PATH. start/stop/restart create a rollback checkpoint with the reverse action. exec runs an explicit command list inside the container (no shell wrapping).", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "id": {"type": "string"}, "container": {"type": "string"}, "command": {}, "tail": {"type": "integer"}, "cwd": {"type": "string"}, "path": {"type": "string"}, "args": {"type": "array"}, "timeout_sec": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "database", "description": "Compound database tool. Actions: status, list_tables, schema, query (SELECT-only), execute (mutating), export_csv. driver=sqlite|postgres|mysql. SQLite uses stdlib; Postgres needs psycopg or psycopg2; MySQL needs mysql-connector-python or pymysql. query is restricted to read-only statements; execute is for INSERT/UPDATE/DELETE/DDL.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "driver": {"type": "string", "enum": ["sqlite", "postgres", "mysql"]}, "path": {"type": "string"}, "database": {"type": "string"}, "db": {"type": "string"}, "host": {"type": "string"}, "port": {"type": "integer"}, "user": {"type": "string"}, "password": {"type": "string"}, "table": {"type": "string"}, "sql": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer"}, "dst": {"type": "string"}, "output": {"type": "string"}, "create": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "creative_local", "description": "Compound bridge to a local ComfyUI server (default http://127.0.0.1:8188). Actions: status, submit (POST /prompt with API-format workflow), result (GET /history/<id>), wait (poll until done), queue (GET /queue), interrupt (POST /interrupt), models (GET /object_info). Returns needs_user with launch instructions if the server is not reachable. Set GEMMA4_COMFYUI_HOST to override the host.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "host": {"type": "string"}, "workflow": {"type": "object"}, "workflow_path": {"type": "string"}, "path": {"type": "string"}, "client_id": {"type": "string"}, "prompt_id": {"type": "string"}, "id": {"type": "string"}, "timeout_sec": {"type": "number"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "form_filler", "description": "Compound HTML form orchestrator on top of browser_real. Actions: status, discover, plan, apply, submit. discover scans the current page for input/select/textarea + their labels/placeholders. plan matches values={label_or_name: value} against the discovered fields without writing. apply executes fill/click via browser_real. submit clicks a submit button only when confirmed=true; otherwise it returns needs_confirmation with a screenshot so the user can verify before sending the form.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "session_id": {"type": "string"}, "values": {"type": "object"}, "plan": {"type": "array"}, "selector": {"type": "string"}, "confirmed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "peripheral", "description": "Compound USB/HID tool via Get-PnpDevice. Actions: status, usb_list, hid_list, controller_status (matches Xbox/PlayStation/Joy-Con/etc keywords), device_manager_problems (Status != OK), device_disable, device_enable. Vendor RGB SDKs (Logitech/Razer/Corsair) are deferred. device_disable/enable creates a rollback checkpoint and usually requires admin elevation.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "instance_id": {"type": "string"}, "id": {"type": "string"}, "only_present": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "accessibility", "description": "Compound Windows accessibility tool. Actions: status, magnifier_start/stop, narrator_start/stop, dictation_status, settings_panel (opens ms-settings:easeofaccess). High Contrast toggle is deferred because programmatic toggling requires registry write + WM_SETTINGCHANGE broadcast; the safe path is the keyboard shortcut Left Alt + Left Shift + Print Screen.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "study", "description": "Compound flashcards + SM-2 spaced repetition tool. Actions: status, deck_create, deck_list, deck_delete, card_add, card_list, card_delete, due, review (grade q in 0..5), stats. SM-2 algorithm per Wozniak 1990: EF' = EF + (0.1 - (5-q)*(0.08 + (5-q)*0.02)) with EF floor 1.3; intervals 1, 6, then I_n = round(I_{n-1} * EF). When q<3, restart repetitions but keep EF. Storage: SQLite at <state_dir>/study.sqlite.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "deck_id": {"type": "string"}, "card_id": {"type": "string"}, "id": {"type": "string"}, "front": {"type": "string"}, "back": {"type": "string"}, "question": {"type": "string"}, "answer": {"type": "string"}, "q": {"type": "integer"}, "grade": {"type": "integer"}, "limit": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "smart_home", "description": "Compound local smart-home control via Home Assistant REST + optional MQTT publish. Actions: status, discover (or states), get_state(entity_id), set_state, call_service(domain, service, data, target), scene_run(scene), area_list, area_control(area, service), mqtt_publish(topic, payload). All endpoints are LOCAL to your Home Assistant. Auth via env GEMMA4_HASS_TOKEN (long-lived access token from your HA profile). Set GEMMA4_HASS_HOST to override the URL. mqtt_publish needs paho-mqtt; broker via GEMMA4_MQTT_BROKER/PORT/USER/PASSWORD. set_state and call_service snapshot the previous state for rollback when possible.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "host": {"type": "string"}, "token": {"type": "string"}, "entity_id": {"type": "string"}, "state": {}, "attributes": {"type": "object"}, "domain": {"type": "string"}, "service": {"type": "string"}, "data": {"type": "object"}, "target": {"type": "object"}, "scene": {"type": "string"}, "area": {"type": "string"}, "area_id": {"type": "string"}, "limit": {"type": "integer"}, "topic": {"type": "string"}, "payload": {}, "broker": {"type": "string"}, "port": {"type": "integer"}, "qos": {"type": "integer"}, "retain": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "subagent", "description": "Delegate a focused task to a fresh child Gemma4 agent. Actions: status, run(task, tools?, max_turns?). The child starts with empty history and runs at most max_turns (default 4, max 10). tools=[...] restricts which tool schemas the child sees. Use this for bounded sub-tasks the parent wants to keep out of its own context (e.g. 'find which Steam games are tagged metroidvania'). Do NOT chain subagents recursively unless the user asks.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "task": {"type": "string"}, "instruction": {"type": "string"}, "tools": {"type": "array", "items": {"type": "string"}}, "max_turns": {"type": "integer"}, "enable_thinking": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "safety", "description": "Compound safety confirmation tool. Actions: status, pending, confirm, cancel. If another tool returns needs_confirmation, ask the user and then call safety(action='confirm', confirmation_id='...') only after explicit approval.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "confirmation_id": {"type": "string"}, "id": {"type": "string"}, "include_resolved": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "package", "description": "Compound package manager tool via winget. Actions: list, search, install, uninstall. This prototype executes directly.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "query": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "clipboard", "description": "Compound clipboard tool. Actions: read, write.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "content": {"type": "string"}, "max_chars": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "terminal", "description": "Compound terminal tool. Action: run. Direct command execution with command, args, cwd, timeout_sec, shell. shell defaults to false (safer; pass shell=true only when you need shell expansion). Any terminal.run call requires confirmed=true (hard gate). cwd is validated for existence; max_stdout_chars/max_stderr_chars cap output preview and full output spills to captures_dir log.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "command": {"type": "string"}, "args": {"type": "array", "items": {"type": "string"}}, "cwd": {"type": "string"}, "timeout_sec": {"type": "integer"}, "shell": {"type": "boolean"}, "max_stdout_chars": {"type": "integer"}, "max_stderr_chars": {"type": "integer"}}, "required": ["action", "command"]}}},
    {"type": "function", "function": {"name": "memory", "description": "Compound persistent memory tool. Actions: save, recall, list, delete. Save only when user explicitly asks to remember/store something.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "key": {"type": "string"}, "value": {"type": "string"}, "query": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "verify", "description": "Compound verification tool. Actions: app_opened, file_exists, window_exists, clipboard_contains. Use after actions when user needs confirmation.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "query": {"type": "string"}, "path": {"type": "string"}, "title": {"type": "string"}, "text": {"type": "string"}}, "required": ["action"]}}},
]

_apply_action_enums(COMPOUND_TOOL_SCHEMAS)

