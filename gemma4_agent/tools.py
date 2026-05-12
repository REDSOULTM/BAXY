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
    notes_tasks_tool,
    notification_tool,
    office_tool,
    printer_scanner_tool,
    routine_tool,
    source_manager_tool,
)
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


def _normalize_tool_result(name: str, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    result.setdefault("tool", name)
    if args.get("action") and "action" not in result:
        result["action"] = str(args["action"])

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
    "browser_real": ["status", "open", "goto", "tabs", "click", "fill", "press", "text", "screenshot", "evaluate", "connect_cdp", "close"],
    "knowledge": ["status", "ingest", "search", "list", "delete"],
    "office": ["status", "create_presentation", "edit_presentation", "create_document", "edit_document", "create_spreadsheet", "edit_spreadsheet", "export_pdf", "inspect", "open"],
    "audio_device": ["status", "list", "set_default", "set_default_communications", "set_app_route", "get_app_routes", "snapshot", "restore"],
    "notification": ["status", "toast_now", "toast_schedule", "timer_start", "timer_cancel", "timer_list", "alarm_create", "alarm_cancel", "alarm_list", "reminder_create", "reminder_update", "reminder_delete", "reminder_list", "notify_sound", "delete"],
    "routine": ["status", "create", "list", "enable", "disable", "delete", "run_now", "simulate", "history"],
    "media": ["status", "play", "pause", "resume", "play_pause", "stop", "next", "previous", "queue_add", "queue_clear", "queue_list", "now_playing", "volume_for_app", "open_local", "search_local_library", "cast_lan"],
    "source_manager": ["status", "save", "add", "list", "sources", "search", "read", "get", "delete", "snapshot_file"],
    "dependency": ["status", "list", "verify", "explain_missing", "install", "repair"],
    "contacts": ["status", "create", "add", "list", "search", "delete", "update", "import_vcard", "export_vcard"],
    "notes_tasks": ["status", "note_create", "create_note", "note_list", "notes", "note_search", "note_update", "note_delete", "task_create", "create_task", "task_list", "tasks", "task_search", "task_complete", "task_update", "task_delete", "search", "list", "delete"],
    "local_calendar": ["status", "event_create", "event_list", "event_update", "event_delete", "ics_export", "ics_import", "list", "delete"],
    "habit_tracker": ["status", "create", "list", "log", "stats", "delete"],
    "local_search": ["status", "search", "recent"],
    "printer_scanner": ["status", "printers_list", "printer_default_get", "printer_default_set", "print_queue", "print_file", "cancel_job", "scanners_list", "scan_document", "list"],
    "desktop_layout": ["status", "windows", "list_windows", "displays", "snapshot", "restore"],
    "backup_sync": ["status", "backup_create", "list", "restore", "dedupe"],
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
        seen: set[tuple[str, str]] = set()
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

    def open(self, candidate: AppCandidate) -> None:
        if candidate.launch_type in {"uri", "shell"}:
            os.startfile(candidate.launch)  # type: ignore[attr-defined]
        else:
            os.startfile(candidate.launch)  # type: ignore[attr-defined]


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


def _http_get_text(url: str, timeout: int = 12, max_bytes: int = 2_000_000) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": WEB_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
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
    def __init__(self, memory: MemoryStore, captures_dir: Path, state: AgentState | None = None, safety_enabled: bool = False):
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

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return COMPOUND_TOOL_SCHEMAS

    def execute(self, name: str, args: dict[str, Any] | None) -> dict[str, Any]:
        clean_args = dict(args or {})
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
        if self.safety_enabled and not confirmed and name != "safety":
            decision = classify_tool_call(name, clean_args)
            if decision.requires_confirmation:
                pending = self.state.create_confirmation(name, clean_args, decision.reason, decision.risk)
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
        try:
            result = impl(clean_args)
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
        if action == "shutdown":
            return self.terminal_run({"command": "shutdown", "args": ["/s", "/t", str(int(args.get("delay_sec", 0)))], "timeout_sec": 10})
        if action == "restart":
            return self.terminal_run({"command": "shutdown", "args": ["/r", "/t", str(int(args.get("delay_sec", 0)))], "timeout_sec": 10})
        if action == "sleep":
            return self.terminal_run({"command": "rundll32.exe", "args": ["powrprof.dll,SetSuspendState", "0,1,0"], "timeout_sec": 10})
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
            found = _attach_screenshot(found, shot)
            if action == "click_text" and found.get("found") and found.get("matches"):
                match = found["matches"][0]
                click = self.gui_click({"x": int(match["center_x"]) + int(shot.get("left", 0)), "y": int(match["center_y"]) + int(shot.get("top", 0))})
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
            return self.terminal_run({"command": "winget", "args": ["list"], "timeout_sec": 120})
        if action == "search":
            return self.terminal_run({"command": "winget", "args": ["search", name], "timeout_sec": 120})
        if action == "install":
            return self.terminal_run({"command": "winget", "args": ["install", "--accept-source-agreements", "--accept-package-agreements", name], "timeout_sec": 1800})
        if action == "uninstall":
            return self.terminal_run({"command": "winget", "args": ["uninstall", name], "timeout_sec": 900})
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
            return self.knowledge.search(str(args.get("query") or ""), limit=int(args.get("limit", 5)))
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
        local_args = dict(args)
        if _action(local_args) == "open_local":
            local_args["action"] = "play"
        return media_tool(local_args, self.execute)

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
        raw = proc.stdout.strip()
        if not raw:
            return _ok(windows=[])
        data = json.loads(raw)
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
        return _ok(info=json.loads(proc.stdout), exit_code=proc.returncode)

    def system_disk(self, args: dict[str, Any]) -> dict[str, Any]:
        script = "Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID,DriveType,Size,FreeSpace,VolumeName | ConvertTo-Json -Depth 3"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
        data = json.loads(proc.stdout) if proc.stdout.strip() else []
        if isinstance(data, dict):
            data = [data]
        return _ok(disks=data, exit_code=proc.returncode)

    def system_battery(self, args: dict[str, Any]) -> dict[str, Any]:
        script = "Get-CimInstance Win32_Battery | Select-Object Name,EstimatedChargeRemaining,BatteryStatus | ConvertTo-Json -Depth 3"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
        raw = proc.stdout.strip()
        return _ok(battery=json.loads(raw) if raw else None, exit_code=proc.returncode)

    def system_brightness_get(self, args: dict[str, Any]) -> dict[str, Any]:
        script = "Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness | Select-Object CurrentBrightness | ConvertTo-Json"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
        raw = proc.stdout.strip()
        return _ok(brightness=json.loads(raw) if raw else None, exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 1000))

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

    def _audio_endpoint_volume(self):
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        device = AudioUtilities.GetSpeakers()
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
        return _ok(active=json.loads(proc.stdout), exit_code=proc.returncode)

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
        data = json.loads(proc.stdout) if proc.stdout.strip() else {"ok": False, "error": proc.stderr}
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
        data = json.loads(proc.stdout) if proc.stdout.strip() else {"ok": False, "error": proc.stderr}
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
        self.apps.open(best)
        resource = None
        if not preexisting.get("found"):
            resource = self.state.register_resource(
                "app",
                name,
                cleanup_tool="app",
                cleanup_args={"action": "close", "name": name},
                metadata={"resolved": best.as_dict()},
            ).get("resource")
        return _ok(
            query=name,
            opened=best.as_dict(),
            alternatives=[m.as_dict() for m in matches[1:5]],
            preexisting=bool(preexisting.get("found")),
            resource=resource,
            status="attempted",
            verified=False,
            completion_status="launch_requested",
            evidence={"resolved_target": best.as_dict()},
            note="Windows was asked to open the resolved app. Use verify(action='app_opened') or window(action='active') if the user needs confirmation.",
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
        checkpoint = self._checkpoint_existing_path(f"filesystem copy to {dst}", dst)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=bool(args.get("overwrite", False)))
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
        a = left.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        b = right.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(a, b, fromfile=str(left), tofile=str(right), n=3))
        return _ok(diff=_truncate(diff, int(args.get("max_chars", 12000))))

    def filesystem_archive(self, args: dict[str, Any]) -> dict[str, Any]:
        src = Path(str(args.get("src") or args.get("path") or "")).expanduser()
        dst = Path(str(args.get("dst") or args.get("archive") or "")).expanduser()
        if not src.exists() or not str(dst):
            return _err("missing src/dst", src=str(src), dst=str(dst))
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

    def terminal_run(self, args: dict[str, Any]) -> dict[str, Any]:
        command = str(args.get("command", "")).strip()
        cmd_args = args.get("args", [])
        cwd = args.get("cwd") or None
        timeout = int(args.get("timeout_sec", 60))
        shell = bool(args.get("shell", True))
        if not command:
            return _err("empty command")
        if not isinstance(cmd_args, list):
            cmd_args = [str(cmd_args)]
        argv = [command] + [str(x) for x in cmd_args]
        run_arg: str | list[str] = subprocess.list2cmdline(argv) if shell else argv
        started = time.monotonic()
        proc = subprocess.run(run_arg, cwd=cwd, shell=shell, capture_output=True, text=True, timeout=timeout)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return _ok(
            command=run_arg,
            cwd=str(Path(cwd).resolve()) if cwd else str(Path.cwd()),
            exit_code=proc.returncode,
            elapsed_ms=elapsed_ms,
            stdout=_truncate(proc.stdout.strip(), 6000),
            stderr=_truncate(proc.stderr.strip(), 3000),
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
        name = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = self.captures_dir / name
        env = os.environ.copy()
        env["GEMMA4_SCREENSHOT_PATH"] = str(path)
        script = r"""
$path = $env:GEMMA4_SCREENSHOT_PATH
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bmp.Size)
$bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
$gfx.Dispose()
$bmp.Dispose()
[PSCustomObject]@{ path=$path; width=$bounds.Width; height=$bounds.Height; left=$bounds.Left; top=$bounds.Top } | ConvertTo-Json
"""
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            return _err("screenshot failed", stderr=_truncate(proc.stderr.strip(), 2000))
        data = json.loads(proc.stdout)
        return _ok(image_path=str(Path(data["path"]).resolve()), width=data["width"], height=data["height"], left=data["left"], top=data["top"])

    def gui_click(self, args: dict[str, Any]) -> dict[str, Any]:
        x = int(args.get("x"))
        y = int(args.get("y"))
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
        x = int(args.get("x"))
        y = int(args.get("y"))
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
        x1 = int(args.get("x1", args.get("from_x")))
        y1 = int(args.get("y1", args.get("from_y")))
        x2 = int(args.get("x2", args.get("to_x")))
        y2 = int(args.get("y2", args.get("to_y")))
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
        script = "Add-Type -AssemblyName System.Windows.Forms; $t=[Console]::In.ReadToEnd(); [System.Windows.Forms.SendKeys]::SendWait($t)"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], input=text, capture_output=True, text=True, timeout=20)
        return _ok(chars=len(text), exit_code=proc.returncode, stderr=_truncate(proc.stderr.strip(), 1000))

    def gui_keypress(self, args: dict[str, Any]) -> dict[str, Any]:
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
        script = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{sendkeys}')"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
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
    {"type": "function", "function": {"name": "gui", "description": "Compound GUI/mouse/keyboard tool. Actions: screenshot, click, double_click, right_click, type, keypress, hotkey, scroll, drag, wait_for, locate_text, click_text, locate_image. locate_text/click_text use local OCR when available and return screen coordinates.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}, "x1": {"type": "integer"}, "y1": {"type": "integer"}, "x2": {"type": "integer"}, "y2": {"type": "integer"}, "text": {"type": "string"}, "keys": {"type": "string"}, "hotkey": {"type": "string"}, "amount": {"type": "integer"}, "target": {"type": "string"}, "image": {"type": "string"}, "lang": {"type": "string"}, "min_conf": {"type": "integer"}, "timeout_sec": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "vision", "description": "Compound Gemma-4-vision/OCR bridge. Actions: describe_screen, find_element, ocr, compare_before_after. OCR uses local Tesseract if available; screenshots are also re-injected for native Gemma 4 visual reasoning.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "target": {"type": "string"}, "text": {"type": "string"}, "image_path": {"type": "string"}, "lang": {"type": "string"}, "min_conf": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "browser", "description": "Compound browser control tool. Actions: open, search, youtube_play, media_pause, media_stop, active_tab_title, click, find, research. open/search mainly navigate the browser and are not proof of reading content. Use web(action='research') for real investigation. youtube_play opens a direct YouTube video when possible and should be used for 'pon/reproduce una cancion'. media_pause/media_stop pause current playback; use them for 'para el video'. If browser is provided, opens that browser app first and navigates there via GUI; do not use browser='YouTube' because YouTube is a site, not a browser.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "url": {"type": "string"}, "query": {"type": "string"}, "song": {"type": "string"}, "title": {"type": "string"}, "engine": {"type": "string"}, "browser": {"type": "string"}, "target": {"type": "string"}, "delay_sec": {"type": "number"}, "post_open_delay_sec": {"type": "number"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "web", "description": "Compound web research tool. Actions: search, read, research, open. search returns search results with snippets; read fetches and extracts a page; research searches and reads several sources. Use this for 'investiga', current facts, sources, or when the user expects an answer from the internet. Use browser only when the goal is to open/navigate a visible browser.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "query": {"type": "string"}, "url": {"type": "string"}, "limit": {"type": "integer"}, "search_limit": {"type": "integer"}, "read_limit": {"type": "integer"}, "per_page_chars": {"type": "integer"}, "max_chars": {"type": "integer"}, "timeout_sec": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "uia", "description": "Compound Windows UI Automation tool. Actions: tree, find, click, focus, set_value. Prefer this before raw GUI clicks when interacting with standard Windows app controls because it returns names, control types, automation ids, bounds and clickable points. Use window/title to scope to an app window and query/text/target to find controls.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "query": {"type": "string"}, "text": {"type": "string"}, "target": {"type": "string"}, "window": {"type": "string"}, "title": {"type": "string"}, "value": {"type": "string"}, "text_value": {"type": "string"}, "limit": {"type": "integer"}, "timeout_sec": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "filesystem", "description": "Compound filesystem tool. Actions: list, read, write, search, delete, copy, move, rename, mkdir, diff, archive, unarchive, open. Mutating actions create local checkpoints with rollback plans when possible.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "path": {"type": "string"}, "src": {"type": "string"}, "dst": {"type": "string"}, "source": {"type": "string"}, "destination": {"type": "string"}, "content": {"type": "string"}, "root": {"type": "string"}, "pattern": {"type": "string"}, "recursive": {"type": "boolean"}, "overwrite": {"type": "boolean"}, "new_name": {"type": "string"}, "left": {"type": "string"}, "right": {"type": "string"}, "archive": {"type": "string"}, "limit": {"type": "integer"}, "max_chars": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "state", "description": "Compound operational state tool. Actions: resources, cleanup_plan, cleanup, checkpoint, checkpoints, rollback_plan, rollback, note. Tracks resources opened by the agent and reversible checkpoints; cleanup executes registered cleanup tools.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "resource_id": {"type": "string"}, "checkpoint_id": {"type": "string"}, "label": {"type": "string"}, "text": {"type": "string"}, "include_closed": {"type": "boolean"}, "rollback": {"type": "array", "items": {"type": "object"}}, "metadata": {"type": "object"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "input", "description": "Compound keyboard/language tool. Actions: language_list, keyboard_layouts, current_keyboard, set_language_list, switch_keyboard. Uses Windows language APIs; changes are checkpointed so they can be rolled back.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "language_tag": {"type": "string"}, "language_tags": {"type": "array", "items": {"type": "string"}}, "force": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "env", "description": "Compound environment variable tool. Actions: get, set, delete, list. scope is process, user, or machine. process affects only this agent session; user/machine are persistent Windows environment scopes and changes create rollback checkpoints.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "scope": {"type": "string"}, "name": {"type": "string"}, "value": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "registry", "description": "Compound safe registry tool. Actions: query, export, import, add, delete, backup. add/delete export a .reg backup first and create rollback checkpoints.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "key": {"type": "string"}, "path": {"type": "string"}, "name": {"type": "string"}, "value_name": {"type": "string"}, "type": {"type": "string"}, "data": {"type": "string"}, "value": {"type": "string"}, "file": {"type": "string"}, "dst": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "download", "description": "Compound download/integrity tool. Actions: fetch, hash, signature. fetch uses Invoke-WebRequest, then SHA256 and Authenticode for executables; without expected hash or valid signature it returns needs_verification.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "url": {"type": "string"}, "path": {"type": "string"}, "dst": {"type": "string"}, "sha256": {"type": "string"}, "expected_sha256": {"type": "string"}, "algorithm": {"type": "string"}, "overwrite": {"type": "boolean"}, "timeout_sec": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "email", "description": "Compound email tool. Actions: status, draft, send. Real sending uses Microsoft Graph sendMail only when GEMMA4_GRAPH_TOKEN or MS_GRAPH_TOKEN is configured; otherwise returns needs_user instead of pretending.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}, "save_to_sent": {"type": "boolean"}, "timeout_sec": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "reminder", "description": "Compound reminder tool. Actions: status, create, list, delete. Default backend stores local reminders in agent state; graph backend requires Microsoft Graph auth and returns needs_user if missing.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "backend": {"type": "string"}, "title": {"type": "string"}, "text": {"type": "string"}, "due": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "browser_real", "description": "Compound real browser automation tool using Playwright. Actions: status, open, goto, tabs, click, fill, press, text, screenshot, evaluate, connect_cdp, close. It keeps persistent sessions by session_id and runs headless by default; connect_cdp can attach to a browser started with remote debugging.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "session_id": {"type": "string"}, "page_id": {"type": "integer"}, "url": {"type": "string"}, "query": {"type": "string"}, "endpoint": {"type": "string"}, "selector": {"type": "string"}, "text": {"type": "string"}, "value": {"type": "string"}, "key": {"type": "string"}, "script": {"type": "string"}, "headless": {"type": "boolean"}, "new_tab": {"type": "boolean"}, "screenshot": {"type": "boolean"}, "full_page": {"type": "boolean"}, "wait_until": {"type": "string"}, "timeout_sec": {"type": "integer"}, "max_chars": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "knowledge", "description": "Compound local RAG/knowledge-base tool. Actions: status, ingest, search, list, delete. Uses local SQLite FTS5 only; ingest supports text files and explicit text, no cloud embeddings.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "path": {"type": "string"}, "text": {"type": "string"}, "source": {"type": "string"}, "title": {"type": "string"}, "query": {"type": "string"}, "doc_id": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "office", "description": "Compound local Office document tool. Actions: status, create_presentation, edit_presentation, create_document, edit_document, create_spreadsheet, edit_spreadsheet, export_pdf, inspect, open. Use create_presentation for PowerPoint requests; returns needs_dependency if python-pptx/python-docx/openpyxl/LibreOffice are missing.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "path": {"type": "string"}, "title": {"type": "string"}, "topic": {"type": "string"}, "content": {"type": "string"}, "body": {"type": "string"}, "slides": {"type": "array", "items": {"type": "object"}}, "rows": {"type": "array", "items": {"type": "array", "items": {}}}, "template": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "audio_device", "description": "Compound Windows audio device/routing tool. Actions: status, list, set_default, set_default_communications, set_app_route, get_app_routes, snapshot, restore. Default device changes need a local helper such as SoundVolumeView and create checkpoints.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "device": {"type": "string"}, "app": {"type": "string"}, "checkpoint_id": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "notification", "description": "Compound local notification/timer/alarm/reminder tool. Actions: status, toast_now, toast_schedule, timer_start, timer_cancel, timer_list, alarm_create, alarm_cancel, alarm_list, reminder_create, reminder_update, reminder_delete, reminder_list, notify_sound, delete. Uses Windows Scheduled Tasks for persistent local notifications.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "title": {"type": "string"}, "text": {"type": "string"}, "message": {"type": "string"}, "due": {"type": "string"}, "time": {"type": "string"}, "seconds": {"type": "integer"}, "minutes": {"type": "integer"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "task_name": {"type": "string"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "routine", "description": "Compound local routine/automation tool. Actions: status, create, list, enable, disable, delete, run_now, simulate, history. A routine stores a trigger and ordered steps like [{tool:'audio', args:{action:'set_volume', level:20}}]. Persistent triggers are planned; run_now executes immediately.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "label": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "trigger": {"type": "string"}, "enabled": {"type": "boolean"}, "steps": {"type": "array", "items": {"type": "object"}}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "media", "description": "Compound media playback tool. Actions: status, play, pause, resume, play_pause, stop, next, previous, queue_add, queue_clear, queue_list, now_playing, volume_for_app, open_local, search_local_library, cast_lan. Use this instead of raw browser/audio for music/video requests.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "query": {"type": "string"}, "song": {"type": "string"}, "title": {"type": "string"}, "provider": {"type": "string"}, "path": {"type": "string"}, "app": {"type": "string"}, "level": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "source_manager", "description": "Compound local source/citation manager. Actions: status, save, add, list, sources, search, read, get, delete, snapshot_file. Stores source titles, URLs, snippets and file snapshots in local state for later citation/research.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "title": {"type": "string"}, "url": {"type": "string"}, "source": {"type": "string"}, "text": {"type": "string"}, "content": {"type": "string"}, "path": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer"}, "max_chars": {"type": "integer"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "dependency", "description": "Compound local dependency diagnostics. Actions: status, list, verify, explain_missing, install, repair. Reports Python modules/binaries needed by tools and gives install hints; install is advisory unless explicitly handled elsewhere.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "dependency": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "contacts", "description": "Compound local contacts tool. Actions: status, create, add, list, search, delete, update, import_vcard, export_vcard. Stores contacts locally in agent state.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "name": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}, "notes": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer"}, "include_closed": {"type": "boolean"}, "path": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "notes_tasks", "description": "Compound local notes/tasks tool. Actions include note_create/list/search/update/delete and task_create/list/search/complete/update/delete. Stores notes and tasks in local state.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "title": {"type": "string"}, "text": {"type": "string"}, "content": {"type": "string"}, "query": {"type": "string"}, "due": {"type": "string"}, "tags": {"type": "string"}, "limit": {"type": "integer"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "local_calendar", "description": "Compound local calendar/ICS tool. Actions: status, event_create, event_list, event_update, event_delete, ics_export, ics_import, list, delete. Stores offline calendar events in local state.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "title": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}, "due": {"type": "string"}, "location": {"type": "string"}, "notes": {"type": "string"}, "path": {"type": "string"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "habit_tracker", "description": "Compound local habit tracker. Actions: status, create, list, log, stats, delete. Stores habits and logs locally.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "id": {"type": "string"}, "resource_id": {"type": "string"}, "name": {"type": "string"}, "title": {"type": "string"}, "frequency": {"type": "string"}, "at": {"type": "string"}, "value": {}, "note": {"type": "string"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "local_search", "description": "Compound local search tool. Actions: status, search, recent. Searches file names and optionally small text file contents under a local root without cloud.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "root": {"type": "string"}, "query": {"type": "string"}, "pattern": {"type": "string"}, "limit": {"type": "integer"}, "recursive": {"type": "boolean"}, "include_content": {"type": "boolean"}, "max_bytes": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "printer_scanner", "description": "Compound local printer/scanner tool. Actions: status, printers_list, printer_default_get, printer_default_set, print_queue, print_file, cancel_job, scanners_list, scan_document, list. Current implementation focuses on printer discovery and queues.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "printer": {"type": "string"}, "path": {"type": "string"}, "job_id": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "desktop_layout", "description": "Compound desktop layout tool. Actions: status, windows, list_windows, displays, snapshot, restore. Snapshots visible windows/monitors into checkpoints; restore is planned.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "limit": {"type": "integer"}, "checkpoint_id": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "backup_sync", "description": "Compound local backup tool. Actions: status, backup_create, list, restore, dedupe. Creates ZIP backups and registers them in state; restore/dedupe are planned.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "src": {"type": "string"}, "path": {"type": "string"}, "dst": {"type": "string"}, "include_closed": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "safety", "description": "Compound safety confirmation tool. Actions: status, pending, confirm, cancel. If another tool returns needs_confirmation, ask the user and then call safety(action='confirm', confirmation_id='...') only after explicit approval.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "confirmation_id": {"type": "string"}, "id": {"type": "string"}, "include_resolved": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "package", "description": "Compound package manager tool via winget. Actions: list, search, install, uninstall. This prototype executes directly.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "query": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "clipboard", "description": "Compound clipboard tool. Actions: read, write.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "content": {"type": "string"}, "max_chars": {"type": "integer"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "terminal", "description": "Compound terminal tool. Action: run. Direct command execution with command, args, cwd, timeout_sec, shell.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "command": {"type": "string"}, "args": {"type": "array", "items": {"type": "string"}}, "cwd": {"type": "string"}, "timeout_sec": {"type": "integer"}, "shell": {"type": "boolean"}}, "required": ["action", "command"]}}},
    {"type": "function", "function": {"name": "memory", "description": "Compound persistent memory tool. Actions: save, recall, list, delete. Save only when user explicitly asks to remember/store something.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "key": {"type": "string"}, "value": {"type": "string"}, "query": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "verify", "description": "Compound verification tool. Actions: app_opened, file_exists, window_exists, clipboard_contains. Use after actions when user needs confirmation.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "name": {"type": "string"}, "query": {"type": "string"}, "path": {"type": "string"}, "title": {"type": "string"}, "text": {"type": "string"}}, "required": ["action"]}}},
]

_apply_action_enums(COMPOUND_TOOL_SCHEMAS)


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"type": "function", "function": {"name": "system_time", "description": "Return current local system time.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "list_processes", "description": "List running Windows processes.", "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "default": 40}}, "required": []}}},
    {"type": "function", "function": {"name": "list_windows", "description": "List visible windows and titles.", "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "default": 30}}, "required": []}}},
    {"type": "function", "function": {"name": "app_search", "description": "Search installed apps/games dynamically across PATH, Start Menu shortcuts, Windows StartApps, uninstall registry, common executable roots, Steam libraries, and Epic manifests. Use when unsure what app name resolves to.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 10}, "refresh": {"type": "boolean", "default": False}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "app_open", "description": "Open an installed app/game by dynamic discovery. The resolver searches PATH, Start Menu, Windows apps, registry, common exe folders, Steam, and Epic; no fixed app alias list is required.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "refresh": {"type": "boolean", "default": False}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "app_close", "description": "Close an app/game by resolving its installed executable or process name, then using taskkill.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "filesystem_list", "description": "List files and folders in a path.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "default": "."}, "limit": {"type": "integer", "default": 80}}, "required": []}}},
    {"type": "function", "function": {"name": "filesystem_read", "description": "Read a UTF-8 text file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "max_chars": {"type": "integer", "default": 12000}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "filesystem_write", "description": "Write a UTF-8 text file, creating parent folders as needed.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "filesystem_search", "description": "Search files recursively by glob pattern under a root.", "parameters": {"type": "object", "properties": {"root": {"type": "string", "default": "."}, "pattern": {"type": "string", "default": "*"}, "limit": {"type": "integer", "default": 50}}, "required": []}}},
    {"type": "function", "function": {"name": "filesystem_delete", "description": "Delete a file or directory. Direct execution prototype: no confirmation layer.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "recursive": {"type": "boolean", "default": False}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "web_open_url", "description": "Open a URL in the default browser.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "terminal_run", "description": "Run a terminal command. Direct execution prototype: no confirmation layer.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "args": {"type": "array", "items": {"type": "string"}, "default": []}, "cwd": {"type": "string"}, "timeout_sec": {"type": "integer", "default": 60}, "shell": {"type": "boolean", "default": True}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "clipboard_read", "description": "Read Windows clipboard text.", "parameters": {"type": "object", "properties": {"max_chars": {"type": "integer", "default": 4000}}, "required": []}}},
    {"type": "function", "function": {"name": "clipboard_write", "description": "Write text to Windows clipboard.", "parameters": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}}},
    {"type": "function", "function": {"name": "gui_screenshot", "description": "Take a screenshot of the current desktop. The agent will send the image back to Gemma 4 for visual reasoning.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "gui_click", "description": "Click a screen coordinate in pixels.", "parameters": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}}},
    {"type": "function", "function": {"name": "gui_type", "description": "Type text into the focused UI element.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "gui_keypress", "description": "Send a key or shortcut. Examples: ENTER, ESC, CTRL+L, CTRL+A, CTRL+C, CTRL+V, ALT+F4.", "parameters": {"type": "object", "properties": {"keys": {"type": "string"}}, "required": ["keys"]}}},
    {"type": "function", "function": {"name": "memory_save", "description": "Save persistent memory ONLY when the user explicitly asks to remember or save a preference/fact.", "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}}},
    {"type": "function", "function": {"name": "memory_recall", "description": "Recall persistent memory by optional query.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "memory_list", "description": "List all persistent memory items.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "memory_delete", "description": "Delete a persistent memory item by key. Use key='*' to clear all memory if user explicitly asks.", "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}}},
]
