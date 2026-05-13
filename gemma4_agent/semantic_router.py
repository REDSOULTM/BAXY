"""Semantic fallback router using local multilingual embeddings.

Activated by `select_tool_names` when keyword matching returns nothing
(usually because the user wrote in a language or wording our regex
keywords don't cover). Inspired by OS-Copilot's similarity_search_with_score
approach (Chroma + top-k), but here we keep everything local and cache the
tool embedding matrix in memory.

Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
(50+ languages, ~120MB on first download). The model is loaded lazily on
first call so importing this module is cheap and doesn't trigger a network
roundtrip.

Override the model via env GEMMA4_SEMANTIC_MODEL. Disable the fallback
entirely with GEMMA4_SEMANTIC_FALLBACK=false.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

_MODEL_NAME_DEFAULT = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Short, intent-style description for each tool. These are what the embedding
# model sees, NOT the full JSON schema description. Keep them concrete and
# free of brand keywords so semantic search works across languages.
TOOL_DESCRIPTIONS: dict[str, str] = {
    "system": "system info: time, processes, CPU, RAM, GPU, disk, battery, brightness",
    "audio": "audio volume, mute, system sound, media keys, audio devices listing",
    "audio_device": "change default audio output/input device, per-app audio routing",
    "app": "open or close a desktop application by name",
    "steam": "Steam game library, Steam store, launch installed Steam games",
    "window": "list windows, focus, close, minimize, maximize, move, resize",
    "gui": "screenshot, click, type text, hotkeys, scroll, drag with mouse",
    "vision": "describe what is on screen, OCR a region, find UI element",
    "browser": "open URL or search query in a web browser",
    "web": "search the web and extract content from sources",
    "uia": "Windows UI Automation tree: find and click named controls",
    "filesystem": "list, read, write, search, delete, copy, move, rename, zip files and folders",
    "package": "install, uninstall, search packages via winget",
    "clipboard": "read or write the clipboard text",
    "terminal": "execute a shell command",
    "memory": "save, recall, list, delete persistent user preferences",
    "verify": "verify app opened, file exists, window exists, clipboard contains",
    "state": "list open resources, cleanup, checkpoint, rollback",
    "input": "list keyboard layouts, set Windows language list",
    "env": "get, set, delete environment variables",
    "registry": "query, export, add, delete Windows registry entries",
    "download": "download a file, hash a file, check signature",
    "email": "send email via Microsoft Graph",
    "reminder": "create a local or cloud reminder",
    "browser_real": "drive a real browser via Playwright: tabs, fill forms, click, extract text",
    "knowledge": "ingest documents and search a local knowledge base",
    "office": "create PowerPoint, Word, Excel documents",
    "notification": "schedule timers, alarms, reminders, toast notifications",
    "routine": "create automation routines with manual, cron, or on-app-open triggers",
    "media": "play music or video, pause, stop, next, previous, now playing",
    "source_manager": "save research sources, snapshots, citations",
    "dependency": "diagnose missing Python modules or binaries",
    "contacts": "manage contacts: create, search, vCard import/export, resolve recipient",
    "notes_tasks": "create and search local notes and tasks",
    "local_calendar": "create local calendar events, import ICS",
    "habit_tracker": "track personal habits and streaks",
    "local_search": "search local files by name or content",
    "printer_scanner": "list printers, print a file, cancel print job, list scanners, scan document",
    "desktop_layout": "snapshot and restore window positions across monitors",
    "backup_sync": "create ZIP backups, restore, deduplicate",
    "safety": "confirm pending risky actions",
    "document": "extract text, tables, images from PDF, DOCX, XLSX, PPTX, HTML",
    "developer": "developer workflows: tests, lint, format, git status/diff, start/stop dev server",
    "device_settings": "WiFi, Bluetooth, display, power plans, system settings",
    "game_launcher": "Epic Games, GOG, Xbox app, Riot Client games",
    "media_edit": "ffmpeg video and audio editing: trim, transcode, normalize, thumbnails",
    "maintenance": "Windows Update, Defender, firewall, event logs, services, restore points",
    "watcher": "watch a file or URL for changes",
    "job_manager": "start and track long-running background subprocess jobs",
    "network": "ping, traceroute, DNS, port check, active connections, public IP",
    "data_analysis": "CSV analysis: profile, describe, query, plot histogram/scatter/line",
    "fact_check": "verify a claim against local sources",
    "photo_library": "organize photos by date, EXIF, thumbnails",
    "container": "Docker containers: ps, logs, start, stop, exec, compose",
    "database": "query and manage SQLite, Postgres, MySQL databases",
    "creative_local": "generate images via local ComfyUI or Stable Diffusion",
    "form_filler": "fill and submit a live web form with review gate",
    "peripheral": "USB devices, controllers, HID listing, device manager problems",
    "accessibility": "Magnifier, Narrator, accessibility settings panel",
    "study": "flashcards with SM-2 spaced repetition",
    "smart_home": "Home Assistant local control and MQTT publish",
}


@dataclass
class _State:
    model: Any | None = None
    tool_names: list[str] | None = None
    tool_embeddings: Any | None = None  # np.ndarray
    disabled: bool = False


_STATE = _State()


def is_enabled() -> bool:
    """The fallback is on by default. Set GEMMA4_SEMANTIC_FALLBACK=false to disable."""
    raw = (os.environ.get("GEMMA4_SEMANTIC_FALLBACK") or "").strip().casefold()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def _ensure_loaded(known_tool_names: list[str] | None = None) -> bool:
    """Lazy-load the model and pre-compute tool description embeddings.

    Returns False if loading failed (model missing, network blocked, etc) so the
    caller can skip the fallback silently. We only print to stderr once per
    process.
    """
    if _STATE.disabled:
        return False
    if _STATE.model is not None and _STATE.tool_embeddings is not None:
        return True
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
    except ImportError:
        _STATE.disabled = True
        return False
    model_name = os.environ.get("GEMMA4_SEMANTIC_MODEL") or _MODEL_NAME_DEFAULT
    try:
        model = SentenceTransformer(model_name)
    except Exception:
        _STATE.disabled = True
        return False
    names = known_tool_names or list(TOOL_DESCRIPTIONS.keys())
    descriptions = [TOOL_DESCRIPTIONS.get(name, name) for name in names]
    try:
        embeddings = model.encode(descriptions, normalize_embeddings=True, show_progress_bar=False)
    except Exception:
        _STATE.disabled = True
        return False
    _STATE.model = model
    _STATE.tool_names = names
    _STATE.tool_embeddings = embeddings
    return True


def suggest_tools_semantic(query: str, *, k: int = 12, min_score: float = 0.25) -> list[str]:
    """Return top-k tool names by cosine similarity to the query.

    Cosine similarity over L2-normalized vectors == dot product. We keep
    matches with score >= min_score; below that we treat as 'no idea' and
    return empty so the caller can fall back to whatever default it wants.
    """
    if not query.strip():
        return []
    if not is_enabled():
        return []
    if not _ensure_loaded():
        return []
    import numpy as np
    q_emb = _STATE.model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]  # type: ignore[union-attr]
    scores = np.asarray(_STATE.tool_embeddings) @ np.asarray(q_emb)
    ranked = np.argsort(-scores)
    names = _STATE.tool_names or []
    out: list[str] = []
    for idx in ranked[: max(1, k)]:
        score = float(scores[idx])
        if score < min_score:
            break
        out.append(names[idx])
    return out


def warm_up() -> None:
    """Eager-load the model (useful for tests/benchmarks)."""
    _ensure_loaded()


def embed(text: str) -> Any | None:
    """Return a normalized embedding for `text` using the cached model.

    Returns None if the model isn't available (no sentence-transformers, or
    network blocked on first download). The embedding is L2-normalized so
    cosine distance == 2 - 2*dot. Dimension is the model's native output
    (384 for paraphrase-multilingual-MiniLM-L12-v2).
    """
    if not text.strip():
        return None
    if not _ensure_loaded():
        return None
    return _STATE.model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]  # type: ignore[union-attr]


def status() -> dict[str, Any]:
    return {
        "enabled": is_enabled(),
        "disabled": _STATE.disabled,
        "model_loaded": _STATE.model is not None,
        "model_name": os.environ.get("GEMMA4_SEMANTIC_MODEL") or _MODEL_NAME_DEFAULT,
        "tool_count": len(_STATE.tool_names) if _STATE.tool_names else len(TOOL_DESCRIPTIONS),
    }
