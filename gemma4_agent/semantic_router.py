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

_BASE_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# Step 6 (2026-05-21): a router-domain fine-tune of the base MiniLM, trained on
# our synthetic multilingual tool queries + the dev split (holdout excluded).
# On the held-out corpus it lifts recall 0.835->0.878 and NO-TOOL keep
# 0.512->0.628, and IMPROVES multilingual probes (0.79->0.90) — the fine-tune is
# the encoder lever the research identified (the base model's short-query
# topical geometry was the ceiling). Same 384-dim MiniLM size => same CPU
# latency. If the artifact is absent (fresh checkout before training), we fall
# back to the base model automatically. Regenerate via
# scripts/train_router_encoder.py + scripts/router_ft_pipeline.py.
_FT_MODEL_DIR = os.path.join(os.path.dirname(__file__), "data", "router_encoder_ft")
_MODEL_NAME_DEFAULT = (
    _FT_MODEL_DIR if os.path.isdir(_FT_MODEL_DIR) else _BASE_MODEL_NAME
)

# Short, intent-style description for each tool. These are what the embedding
# model sees, NOT the full JSON schema description. Keep them concrete and
# free of brand keywords so semantic search works across languages.
TOOL_DESCRIPTIONS: dict[str, str] = {
    "system": (
        "system info, processes and power: current time and date, qué hora "
        "es, qué fecha es hoy; list running processes, kill or force-close a "
        "process, taskkill, mata procesos colgados, lista procesos, cierra "
        "un proceso; CPU RAM GPU disk battery brightness, shutdown restart "
        "sleep"
    ),
    "audio": "audio volume, mute and unmute the sound (silenciar, desmutear, stummschalten, ton an, couper/rétablir le son, silenciar/reativar o som), system sound, media keys, audio devices listing",
    "audio_device": "change default audio output/input device, per-app audio routing",
    "app": "open or close a desktop application by name",
    "steam": "Steam game library, Steam store, launch installed Steam games",
    "window": "list windows, focus, close, minimize, maximize, move, resize",
    "gui": "screenshot, click, type text, hotkeys, scroll, drag with mouse",
    "vision": "describe what is on screen, OCR a region, find UI element",
    "browser": (
        "open a website, URL or web address in a browser; abrir una pagina "
        "web, abrir github o un sitio, abrir una direccion como python.org "
        "o localhost, navegar a un enlace, open a link in the browser"
    ),
    "web": (
        "search the internet and answer questions about the world: latest "
        "news, current prices, who is a person, what is something, what a "
        "movie or game is about, how someone died, when something happened; "
        "buscar en internet, ultimas noticias, precios actuales, quien es "
        "alguien, que es algo, de que trata una pelicula o juego, de que "
        "murio alguien, informacion externa, busca en la web"
    ),
    "uia": (
        "operar dentro de una app ya abierta: clickear o entrar a un boton, canal, "
        "servidor, pestania, seccion, contacto o elemento por su nombre. Windows UI "
        "Automation: find and click named controls inside an open app."
    ),
    "filesystem": (
        "work with local files and folders: read a file, see what is in a "
        "folder, list a directory, write or append to a file, search, "
        "delete, copy, move, rename, zip; que hay en una carpeta, lee un "
        "archivo, abre el archivo de log, lista los archivos, agrega una "
        "linea a un archivo, contenido de Descargas"
    ),
    "package": "install, uninstall, search packages via winget",
    "clipboard": "read or write the clipboard text",
    "terminal": "execute a shell command",
    "memory": (
        "remember facts about the user and their preferences: my name is X, "
        "call me X from now on, remember that I prefer Y, what is my name, "
        "what project am I working on, what preference do I have, change or "
        "forget my setting; recordar datos del usuario, me llamo X, "
        "llamame X, recuerda que prefiero, que preferencia tengo, que "
        "proyecto estoy trabajando, de que proyecto, olvida mi configuracion"
    ),
    "verify": "verify app opened, file exists, window exists, clipboard contains",
    "state": "list open resources, cleanup, checkpoint, rollback",
    "input": (
        "press keys and type on the keyboard: press Escape, press Win, "
        "press arrow down 3 times, type text without pressing enter, send "
        "keystrokes and hotkeys; presiona una tecla, apreta Escape o Win, "
        "escribe sin enter, manda teclas; also keyboard layouts and language"
    ),
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
    "whatsapp": "WhatsApp messaging: send a message, open a chat, mandar mensaje por WhatsApp, escribir a una persona en wsp, decirle algo a alguien en whatsapp, mensaje de texto",
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
    tool_embeddings: Any | None = None  # np.ndarray (DESCRIPTION embeddings)
    # Tool2Vec (Step 4, 2026-05-21): per-tool centroid of synthetic example
    # QUERIES, aligned to tool_names. The runtime tool vector is a blend of the
    # description embedding and this query-centroid — example queries land far
    # closer to real short voice phrasings than a terse English description
    # does (Tool2Vec arXiv:2409.02141 / Re-Invoke arXiv:2408.01875).
    tool2vec: Any | None = None  # np.ndarray [N,384] aligned to tool_names, or None
    permanently_disabled: bool = False  # set only when the lib is missing
    last_attempt_ts: float = 0.0
    last_error: str = ""
    attempt_count: int = 0


# Blend weight: final tool vector = normalize(alpha*tool2vec + (1-alpha)*desc).
# alpha=0 -> pure description (old behaviour), alpha=1 -> pure query-centroid.
# Tuned on the dev split via router_eval; default set after the sweep.
import os as _os2
_TOOL2VEC_ALPHA = float(_os2.environ.get("GEMMA4_TOOL2VEC_ALPHA", "0.6"))
_TOOL2VEC_PATH = os.path.join(
    os.path.dirname(__file__), "data", "tool2vec_centroids.npz")


_STATE = _State()
# Serializes _ensure_loaded across threads. The warmup daemon thread and the
# first user turn both call _ensure_loaded; without this lock they race —
# double-loading the SentenceTransformer (2x memory + load time) and, worse,
# mis-counting concurrent attempts toward _RETRY_MAX_ATTEMPTS so two racing
# loads could falsely trip permanently_disabled. Double-checked locking: the
# fast path (already loaded) never takes the lock.
import threading as _threading
_LOAD_LOCK = _threading.Lock()

# Retry policy for transient failures (e.g. disk full, network blip on first
# model download): wait at least RETRY_COOLDOWN_S before trying again, up to
# RETRY_MAX_ATTEMPTS. After that we give up for the process lifetime.
_RETRY_COOLDOWN_S = 120
_RETRY_MAX_ATTEMPTS = 3


def is_enabled() -> bool:
    """The fallback is on by default. Set GEMMA4_SEMANTIC_FALLBACK=false to disable."""
    raw = (os.environ.get("GEMMA4_SEMANTIC_FALLBACK") or "").strip().casefold()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def _ensure_loaded(known_tool_names: list[str] | None = None) -> bool:
    """Lazy-load the model and pre-compute tool description embeddings.

    Returns False if loading failed (model missing, network blocked, etc). On
    transient failures we record the error and allow a retry after a cooldown.
    On a permanent failure (sentence-transformers not installed) we mark the
    state permanently disabled.
    """
    # Fast path (no lock): already loaded / already permanently disabled.
    if _STATE.permanently_disabled:
        return False
    if _STATE.model is not None and _STATE.tool_embeddings is not None:
        return True
    # Slow path: take the lock so concurrent callers (warmup thread + first
    # turn) don't double-load or mis-count attempts. Re-check inside the lock —
    # another thread may have finished loading while we waited.
    with _LOAD_LOCK:
        if _STATE.permanently_disabled:
            return False
        if _STATE.model is not None and _STATE.tool_embeddings is not None:
            return True
        return _ensure_loaded_locked(known_tool_names)


def _ensure_loaded_locked(known_tool_names: list[str] | None) -> bool:
    """Body of _ensure_loaded; MUST be called holding _LOAD_LOCK."""
    # Cooldown gate: do not retry too often.
    import time as _time
    now = _time.time()
    if _STATE.attempt_count > 0 and (now - _STATE.last_attempt_ts) < _RETRY_COOLDOWN_S:
        return False
    if _STATE.attempt_count >= _RETRY_MAX_ATTEMPTS:
        # Give up after a few transient failures. Will reset only if the
        # process is restarted.
        _STATE.permanently_disabled = True
        return False
    _STATE.attempt_count += 1
    _STATE.last_attempt_ts = now
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
    except ImportError as exc:
        # Library is missing -> permanent (a restart won't fix it without
        # the user installing the package).
        _STATE.permanently_disabled = True
        _STATE.last_error = f"ImportError: {exc}"
        return False
    model_name = os.environ.get("GEMMA4_SEMANTIC_MODEL") or _MODEL_NAME_DEFAULT
    try:
        model = SentenceTransformer(model_name)
    except Exception as exc:
        # ROBUSTNESS (2026-05-21): if the fine-tuned encoder fails to load (a
        # corrupt artifact, a transformers-version tokenizer mismatch, etc.),
        # DON'T leave the router disabled (which looks like "stuck forever" in
        # the UI). Fall back to the base multilingual model so routing keeps
        # working at base quality. Only if THAT also fails do we report.
        _STATE.last_error = f"FT encoder load failed, falling back to base: {exc}"
        if model_name != _BASE_MODEL_NAME:
            try:
                model = SentenceTransformer(_BASE_MODEL_NAME)
                model_name = _BASE_MODEL_NAME
            except Exception as exc2:
                _STATE.last_error = f"SentenceTransformer init failed: {exc2}"
                return False
        else:
            return False
    names = known_tool_names or list(TOOL_DESCRIPTIONS.keys())
    descriptions = [TOOL_DESCRIPTIONS.get(name, name) for name in names]
    try:
        embeddings = model.encode(descriptions, normalize_embeddings=True, show_progress_bar=False)
    except Exception as exc:
        _STATE.last_error = f"encode failed: {exc}"
        return False
    _STATE.model = model
    _STATE.tool_names = names
    _STATE.tool_embeddings = embeddings
    # Blend in Tool2Vec query-centroids if the artifact exists. Missing artifact
    # => pure-description behaviour (graceful, identical to pre-Step-4).
    _STATE.tool2vec = _load_tool2vec(names)
    if _STATE.tool2vec is not None and _TOOL2VEC_ALPHA > 0.0:
        _STATE.tool_embeddings = _blend_embeddings(
            embeddings, _STATE.tool2vec, _TOOL2VEC_ALPHA)
    _STATE.last_error = ""
    return True


def _load_tool2vec(names: list[str]) -> Any | None:
    """Load tool2vec_centroids.npz and align to `names`. Returns an [N,384]
    array (zeros row for tools without a centroid) or None if absent."""
    if not os.path.exists(_TOOL2VEC_PATH):
        return None
    try:
        import numpy as np
        data = np.load(_TOOL2VEC_PATH, allow_pickle=True)
        c_names = list(data["names"])
        c_vecs = np.asarray(data["centroids"], dtype=np.float32)
        idx = {n: i for i, n in enumerate(c_names)}
        dim = c_vecs.shape[1]
        out = np.zeros((len(names), dim), dtype=np.float32)
        for i, n in enumerate(names):
            if n in idx:
                out[i] = c_vecs[idx[n]]
        return out
    except Exception:
        return None


def _blend_embeddings(desc: Any, t2v: Any, alpha: float) -> Any:
    """final = normalize(alpha*t2v + (1-alpha)*desc), per tool. Tools whose
    t2v row is all-zeros (no centroid) keep their pure description vector."""
    import numpy as np
    desc = np.asarray(desc, dtype=np.float32)
    t2v = np.asarray(t2v, dtype=np.float32)
    blended = alpha * t2v + (1.0 - alpha) * desc
    # rows where t2v is empty -> fall back to description
    empty = (np.linalg.norm(t2v, axis=1) == 0.0)
    blended[empty] = desc[empty]
    norms = np.linalg.norm(blended, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return blended / norms


def suggest_tools_semantic(query: str, *, k: int = 12, min_score: float = 0.25) -> list[str]:
    """Return top-k tool names by cosine similarity to the query.

    Cosine similarity over L2-normalized vectors == dot product. We keep
    matches with score >= min_score; below that we treat as 'no idea' and
    return empty so the caller can fall back to whatever default it wants.
    """
    return [name for name, _ in suggest_tools_scored(query, k=k, min_score=min_score)]


def suggest_tools_scored(
    query: str, *, k: int = 12, min_score: float = 0.25,
) -> list[tuple[str, float]]:
    """Like suggest_tools_semantic but returns (tool, cosine) pairs.

    The score is the second signal the planner uses to decide how much to
    trust a match: a high top-1 cosine (≈0.4+) means the wording lands
    squarely on one tool's intent (a confident command like "mutea" →
    audio 0.51), whereas chitchat/self-reference spread thin and low
    (≈0.27–0.3, on generic catch-all tools). Returns at most k pairs above
    min_score, highest first.
    """
    if not query.strip():
        return []
    if not is_enabled():
        return []
    if not _ensure_loaded():
        return []
    import numpy as np
    q_emb = _STATE.model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]  # type: ignore[union-attr]
    tool_emb = np.asarray(_STATE.tool_embeddings, dtype=np.float32)
    q_emb_arr = np.asarray(q_emb, dtype=np.float32)
    scores = tool_emb @ q_emb_arr
    ranked = np.argsort(-scores)
    names = _STATE.tool_names or []
    out: list[tuple[str, float]] = []
    for idx in ranked[: max(1, k)]:
        score = float(scores[idx])
        if score < min_score:
            break
        out.append((names[idx], score))
    return out


def warm_up() -> None:
    """Eager-load the model (useful for tests/benchmarks)."""
    _ensure_loaded()


def reset_cache() -> None:
    """Force the model to re-embed TOOL_DESCRIPTIONS on next use.

    Necesario cuando TOOL_DESCRIPTIONS cambia mid-process (rare, pero pasa
    cuando se agrega una tool nueva como `whatsapp` despues de bootstrap).
    NO descarga el modelo — solo descarta los embeds cacheados para que
    _ensure_loaded los recalcule con la lista actual.
    """
    _STATE.tool_names = None
    _STATE.tool_embeddings = None
    _STATE.attempt_count = 0
    _STATE.last_attempt_ts = 0.0
    _EMBED_CACHE.clear()
    _EMBED_CACHE_ORDER.clear()


# PERF: LRU cache para embeds del input del usuario. El embed de un texto
# corto cuesta 50-150ms en CPU; con cache, queries repetidas ("abre Steam"
# dos veces) son 0ms. Tamaño 256 cubre conversaciones largas sin crecer
# memoria sin limite. Clave: el texto normalizado (lower+strip) para que
# "abre Steam" == "ABRE Steam" == " abre steam ".
_EMBED_CACHE: "dict[str, Any]" = {}
_EMBED_CACHE_ORDER: list[str] = []
_EMBED_CACHE_MAX = 256


def _cache_key(text: str) -> str:
    return " ".join(text.lower().split())


def embed(text: str) -> Any | None:
    """Return a normalized embedding for `text` using the cached model.

    Returns None if the model isn't available (no sentence-transformers, or
    network blocked on first download). The embedding is L2-normalized so
    cosine distance == 2 - 2*dot. Dimension is the model's native output
    (384 for paraphrase-multilingual-MiniLM-L12-v2).
    """
    if not text.strip():
        return None
    key = _cache_key(text)
    cached = _EMBED_CACHE.get(key)
    if cached is not None:
        # LRU touch: mover al final del order para reflejar uso reciente.
        try:
            _EMBED_CACHE_ORDER.remove(key)
        except ValueError:
            pass
        _EMBED_CACHE_ORDER.append(key)
        return cached
    if not _ensure_loaded():
        return None
    vec = _STATE.model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]  # type: ignore[union-attr]
    # Evict LRU si supera el cap.
    if len(_EMBED_CACHE_ORDER) >= _EMBED_CACHE_MAX:
        oldest = _EMBED_CACHE_ORDER.pop(0)
        _EMBED_CACHE.pop(oldest, None)
    _EMBED_CACHE[key] = vec
    _EMBED_CACHE_ORDER.append(key)
    return vec


def status() -> dict[str, Any]:
    return {
        "enabled": is_enabled(),
        "disabled": _STATE.permanently_disabled,
        "attempts": _STATE.attempt_count,
        "last_error": _STATE.last_error,
        "model_loaded": _STATE.model is not None,
        "model_name": os.environ.get("GEMMA4_SEMANTIC_MODEL") or _MODEL_NAME_DEFAULT,
        "tool_count": len(_STATE.tool_names) if _STATE.tool_names else len(TOOL_DESCRIPTIONS),
    }
