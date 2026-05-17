"""Concrete per-tool verifiers for the 10 hottest tools.

Cada verifier es una funcion pura que recibe (args, result) y lee el estado
real del SO para confirmar el efecto. Filosofia: no usar LLM para verificar;
solo medicion estructural (psutil, win32gui, pathlib, pycaw).

Cobertura inicial (top 10 por uso):
  1. app           open / close / search
  2. steam         open / launch_game / library / store
  3. window        focus / close / minimize / maximize / restore / list / active
  4. filesystem    write / delete / read / list
  5. audio         set_volume / mute / get_volume
  6. terminal      run
  7. gui           screenshot / click / keypress / type
  8. clipboard     read / write
  9. web           open_url
 10. system        time / processes / cpu_ram_gpu / disk / battery

Para tools sin verifier registrado, verify_core.verify() devuelve
confirmed=None con reason="no_verifier_registered" — el caller lo trata
como honest "no medido".

Cada outcome confirmed=True deberia exportar evidence_keys (e.g.
"app:Steam") para que el LoopState (TIER 1 #1) resetee su warning_count
en progreso real.

Trade-off importante: varios de estos tools YA hacen su propia
verificacion internamente (ej. `app_open` con auto-verify, `audio_set_volume`
con re-read post-set). Los verifiers de aqui leen el result.verified flag
cuando esta presente para no duplicar el trabajo. Donde la tool NO mide,
el verifier hace su propio check.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .verify_core import VerifierOutcome, register_verifier


# ============================================================================
# Helpers locales
# ============================================================================

def _ok_evidence(tool: str, reason: str, keys: list[str] | None = None,
                 detail: dict | None = None) -> VerifierOutcome:
    return VerifierOutcome(
        tool_name=tool, confirmed=True, reason=reason,
        evidence_keys=keys or [], detail=detail,
    )


def _unverifiable(tool: str, reason: str, detail: dict | None = None) -> VerifierOutcome:
    return VerifierOutcome(tool_name=tool, confirmed=None, reason=reason, detail=detail)


def _failed(tool: str, reason: str, detail: dict | None = None) -> VerifierOutcome:
    return VerifierOutcome(tool_name=tool, confirmed=False, reason=reason, detail=detail)


def _result_says_unverified(result: dict) -> bool:
    """True si la tool ya reporto unverified/failed/needs_x."""
    if not result.get("ok"):
        return True
    status = str(result.get("status") or "").casefold()
    completion = str(result.get("completion_status") or "").casefold()
    return (
        status in {"failed", "unverified", "needs_verification"}
        or completion.startswith("needs_")
        or completion in {"unverified", "failed"}
    )


def _fold_name(s: str) -> str:
    """Lower + strip + remove .exe suffix para matchear procs."""
    s = s.strip().lower()
    if s.endswith(".exe"):
        s = s[:-4]
    return s


def _proc_matches(query: str, proc_names: set[str]) -> bool:
    """True si algun nombre de proceso (lowercase, con o sin .exe) matchea
    la query (exact stem o substring si query >=4 chars). Reutilizable
    para verify_app_open / verify_steam.
    """
    q = _fold_name(query)
    if not q:
        return False
    for p in proc_names:
        pn = _fold_name(p)
        if pn == q:
            return True
        if len(q) >= 4 and q in pn:
            return True
    return False


# ============================================================================
# 1. app
# ============================================================================

@register_verifier("app")
def verify_app(args: dict, result: dict) -> VerifierOutcome:
    action = str(args.get("action") or "open").lower()
    name = str(args.get("name") or args.get("query") or "").strip()

    if action == "search":
        # search es read-only: el unico efecto es devolver matches.
        if _result_says_unverified(result):
            return _unverifiable("app", "search failed or returned unverified")
        matches = result.get("matches") or []
        return _ok_evidence(
            "app", f"search returned {len(matches)} matches",
            detail={"count": len(matches)},
        )

    if action == "open":
        if not name:
            return _unverifiable("app", "no name to verify")
        if _result_says_unverified(result):
            return _failed("app", f"tool reported failure: {result.get('error', '?')}")

        # Si la tool ya hizo auto-verify y dice True, trust eso.
        if result.get("verified") is True:
            return _ok_evidence(
                "app", f"tool reported verified=True for '{name}'",
                keys=[f"app:{name}"],
                detail={"via": "tool_self_verify"},
            )

        # Best-effort: leer procesos vivos con un short retry para apps
        # que tardan en aparecer (Steam, Epic, Office cold-start).
        from .tools import _running_process_names
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            procs = _running_process_names()
            if _proc_matches(name, procs):
                return _ok_evidence(
                    "app", f"proceso matching '{name}' encontrado en tasklist",
                    keys=[f"app:{name}"],
                    detail={"via": "psutil"},
                )
            time.sleep(0.3)
        return _unverifiable(
            "app",
            f"proceso matching '{name}' no aparecio en 2s (puede estar cargando)",
        )

    if action == "close":
        if not name:
            return _unverifiable("app", "no name to verify")
        # not_running fast-path: la tool ya reporto que no estaba corriendo.
        if result.get("not_running") is True:
            return _ok_evidence(
                "app", f"'{name}' no estaba corriendo (nothing to close)",
                keys=[f"app:{name}:closed"],
                detail={"via": "fast_path"},
            )
        if not result.get("closed"):
            return _failed("app", f"close reported closed=False for '{name}'")
        # Verificacion estructural: el proceso ya no debe aparecer en tasklist.
        time.sleep(0.5)  # window para que el proceso termine de morir
        from .tools import _running_process_names
        procs = _running_process_names()
        if _proc_matches(name, procs):
            return _failed(
                "app", f"proceso matching '{name}' sigue corriendo tras close",
                detail={"via": "psutil"},
            )
        return _ok_evidence(
            "app", f"proceso '{name}' ausente post-close",
            keys=[f"app:{name}:closed"],
            detail={"via": "psutil"},
        )

    if action == "uninstall":
        # Uninstall es lento y async (winget). Marcar inconclusive.
        return _unverifiable("app", "uninstall es async (winget); efecto se mide tras varios minutos")

    return _unverifiable("app", f"unknown app action: {action}")


# ============================================================================
# 2. steam
# ============================================================================

@register_verifier("steam")
def verify_steam(args: dict, result: dict) -> VerifierOutcome:
    action = str(args.get("action") or "open").lower()

    # Acciones que solo abren URLs / deeplinks: dispatch async, no verificable.
    if action in {"open", "library", "store", "store_page", "search_store", "search_library"}:
        if _result_says_unverified(result):
            return _failed("steam", f"steam reported failure: {result.get('error', '?')}")
        # Verificamos al menos que Steam (proceso) este corriendo.
        from .tools import _running_process_names
        time.sleep(0.5)
        procs = _running_process_names()
        if _proc_matches("steam", procs):
            return _ok_evidence(
                "steam", f"Steam client running; {action} dispatched",
                keys=[f"app:Steam"],
                detail={"action": action, "via": "deeplink"},
            )
        return _unverifiable(
            "steam",
            "Steam client no aparece en procesos; deeplink puede estar cargando",
        )

    if action == "launch_game":
        if _result_says_unverified(result):
            return _failed("steam", f"launch_game failed: {result.get('error', '?')}")
        # No medimos el proceso del juego (varia segun titulo); marcamos inconclusive.
        # El usuario puede pedir verify(action="app_opened", name="<game>") explicito.
        matched = result.get("matched_game") or {}
        return _unverifiable(
            "steam",
            f"launch dispatched; verificar proceso del juego no automatizado",
            detail={"matched_game": matched.get("name") if isinstance(matched, dict) else None},
        )

    if action == "list_games":
        if _result_says_unverified(result):
            return _unverifiable("steam", "list_games failed")
        count = result.get("count")
        return _ok_evidence(
            "steam", f"library list returned {count} games",
            detail={"count": count},
        )

    return _unverifiable("steam", f"unknown steam action: {action}")


# ============================================================================
# 3. window
# ============================================================================

@register_verifier("window")
def verify_window(args: dict, result: dict) -> VerifierOutcome:
    action = str(args.get("action") or "list").lower()

    if action == "list":
        if _result_says_unverified(result):
            return _unverifiable("window", "list failed")
        count = len(result.get("windows") or [])
        return _ok_evidence(
            "window", f"listed {count} windows",
            detail={"count": count},
        )

    if action == "active":
        if _result_says_unverified(result):
            return _unverifiable("window", "active failed")
        active = result.get("active") or {}
        if active.get("title"):
            return _ok_evidence(
                "window", f"foreground window: {active.get('title', '')[:60]}",
                detail={"pid": active.get("pid"), "process": active.get("process")},
            )
        return _unverifiable("window", "no foreground window detected")

    if action in {"focus", "close", "minimize", "maximize", "restore"}:
        if _result_says_unverified(result):
            return _failed("window", f"{action} reported failure")
        inner = result.get("result") or {}
        if not inner.get("ok"):
            return _failed(
                "window", f"{action}: {inner.get('error', 'window not found')}",
                detail={"error": inner.get("error")},
            )
        title = str(inner.get("title") or "")
        # Para focus, verificamos via GetForegroundWindow que la ventana del proceso
        # esta realmente activa. Para los otros (close/min/max/restore) confiamos
        # en que el API call no fallo (es dificil distinguir minimized vs hidden).
        if action == "focus":
            try:
                import win32gui  # type: ignore
                hwnd = win32gui.GetForegroundWindow()
                cur_title = win32gui.GetWindowText(hwnd) if hwnd else ""
                if title and title.lower() in cur_title.lower():
                    return _ok_evidence(
                        "window", f"focus verified: '{cur_title[:60]}'",
                        keys=[f"window:{title}:focus"],
                        detail={"via": "GetForegroundWindow"},
                    )
                return _unverifiable(
                    "window",
                    f"focus dispatched pero foreground es '{cur_title[:60]}'",
                )
            except Exception:
                return _unverifiable("window", "win32gui no disponible para verify focus")
        # close/min/max/restore: confiamos en el reporte de la tool.
        return _ok_evidence(
            "window", f"{action} dispatched on '{title[:60]}'",
            keys=[f"window:{title}:{action}"],
        )

    return _unverifiable("window", f"unknown window action: {action}")


# ============================================================================
# 4. filesystem
# ============================================================================

@register_verifier("filesystem")
def verify_filesystem(args: dict, result: dict) -> VerifierOutcome:
    action = str(args.get("action") or "list").lower()
    path = str(args.get("path") or result.get("path") or "")

    # Read-only actions
    if action in {"list", "read", "search", "diff"}:
        if _result_says_unverified(result):
            return _unverifiable("filesystem", f"{action} failed")
        return _ok_evidence("filesystem", f"{action} returned data")

    if action == "write":
        if not path:
            return _unverifiable("filesystem", "path vacio")
        if _result_says_unverified(result):
            return _failed("filesystem", f"write failed: {result.get('error', '?')}")
        # write tool ya hace verify post-write con stat. Trust eso si esta.
        if result.get("verified") is True:
            return _ok_evidence(
                "filesystem", f"write verified ({result.get('bytes', '?')} bytes)",
                keys=[f"file:{path}"],
                detail={"via": "tool_self_verify"},
            )
        # Fallback: stat manual.
        try:
            p = Path(path).expanduser()
            if not p.is_file():
                return _failed("filesystem", f"archivo no existe post-write: {path}")
            size = p.stat().st_size
            if size == 0 and args.get("content"):
                return _failed("filesystem", "archivo vacio post-write con contenido pedido")
            return _ok_evidence(
                "filesystem", f"write verified ({size} bytes)",
                keys=[f"file:{path}"],
                detail={"size": size, "via": "stat"},
            )
        except OSError as exc:
            return _unverifiable("filesystem", f"stat failed: {exc}")

    if action == "delete":
        if not path:
            return _unverifiable("filesystem", "path vacio")
        if _result_says_unverified(result):
            return _failed("filesystem", f"delete failed: {result.get('error', '?')}")
        try:
            p = Path(path).expanduser()
            if p.exists():
                return _failed("filesystem", f"path sigue existiendo: {path}")
            return _ok_evidence(
                "filesystem", f"path '{path}' eliminado",
                keys=[f"file:{path}:deleted"],
                detail={"via": "absent_after_delete"},
            )
        except OSError as exc:
            return _unverifiable("filesystem", f"stat failed: {exc}")

    if action in {"copy", "move", "rename"}:
        dst = str(args.get("dst") or args.get("dest") or args.get("destination") or result.get("dst") or "")
        if not dst:
            return _unverifiable("filesystem", f"{action}: dst vacio")
        if _result_says_unverified(result):
            return _failed("filesystem", f"{action} failed: {result.get('error', '?')}")
        try:
            d = Path(dst).expanduser()
            if not d.exists():
                return _failed("filesystem", f"{action}: dst '{dst}' no existe")
            return _ok_evidence(
                "filesystem", f"{action} verified: '{dst}' presente",
                keys=[f"file:{dst}"],
                detail={"via": "exists_after_op"},
            )
        except OSError as exc:
            return _unverifiable("filesystem", f"stat failed: {exc}")

    if action == "mkdir":
        if not path:
            return _unverifiable("filesystem", "path vacio")
        if _result_says_unverified(result):
            return _failed("filesystem", f"mkdir failed: {result.get('error', '?')}")
        try:
            p = Path(path).expanduser()
            if not p.is_dir():
                return _failed("filesystem", f"directorio no existe post-mkdir: {path}")
            return _ok_evidence(
                "filesystem", f"mkdir verified: {path}",
                keys=[f"file:{path}"],
            )
        except OSError as exc:
            return _unverifiable("filesystem", f"stat failed: {exc}")

    return _unverifiable("filesystem", f"unknown filesystem action: {action}")


# ============================================================================
# 5. audio
# ============================================================================

@register_verifier("audio")
def verify_audio(args: dict, result: dict) -> VerifierOutcome:
    action = str(args.get("action") or "get_volume").lower()

    if action == "get_volume":
        if _result_says_unverified(result):
            return _unverifiable("audio", "get_volume failed")
        level = result.get("level")
        return _ok_evidence(
            "audio", f"volume is {level}",
            detail={"level": level, "muted": result.get("muted")},
        )

    if action == "set_volume":
        # La tool ya hace verify=True post-set comparando expected vs actual.
        if result.get("verified") is True:
            actual = result.get("level")
            return _ok_evidence(
                "audio", f"volume set to {actual} (verified by tool)",
                keys=[f"volume:{actual}"],
                detail={"via": "tool_self_verify"},
            )
        if _result_says_unverified(result):
            return _failed("audio", f"set_volume failed: {result.get('error', '?')}")
        # Fallback: re-leer con pycaw si esta disponible.
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            actual = int(round(volume.GetMasterVolumeLevelScalar() * 100))
            expected = int(args.get("level", -1))
            if expected < 0:
                return _unverifiable("audio", "expected level no esperado")
            if abs(actual - expected) <= 2:
                return _ok_evidence(
                    "audio", f"volume {actual} matches {expected}",
                    keys=[f"volume:{actual}"], detail={"via": "pycaw"},
                )
            return _failed("audio", f"volume actual={actual} != expected={expected}",
                           detail={"actual": actual, "expected": expected})
        except Exception:
            return _unverifiable("audio", "pycaw no disponible para verify")

    if action == "mute":
        if result.get("verified") is True:
            actual = result.get("muted")
            return _ok_evidence(
                "audio", f"mute={actual} (verified by tool)",
                keys=[f"mute:{actual}"],
            )
        if _result_says_unverified(result):
            return _failed("audio", f"mute failed: {result.get('error', '?')}")
        return _unverifiable("audio", "mute dispatched sin verify flag")

    return _unverifiable("audio", f"verifier no implementado para audio.{action}")


# ============================================================================
# 6. terminal
# ============================================================================

@register_verifier("terminal")
def verify_terminal(args: dict, result: dict) -> VerifierOutcome:
    action = str(args.get("action") or "run").lower()
    if action != "run":
        return _unverifiable("terminal", f"unknown terminal action: {action}")
    if _result_says_unverified(result):
        # status=timeout o failed
        status = str(result.get("status") or "")
        if status == "timeout":
            return _failed(
                "terminal", f"command timed out after {result.get('timeout_sec')}s",
                detail={"command": result.get("command")},
            )
        return _failed(
            "terminal", f"terminal failed: {result.get('error', '?')}",
            detail={"command": result.get("command")},
        )
    exit_code = result.get("exit_code")
    if exit_code == 0:
        return _ok_evidence(
            "terminal", "exit_code=0",
            keys=[f"terminal:exit0"],
            detail={"command": result.get("command")},
        )
    return _failed(
        "terminal", f"exit_code={exit_code}",
        detail={"exit_code": exit_code, "stderr": (result.get("stderr") or "")[:200]},
    )


# ============================================================================
# 7. gui
# ============================================================================

@register_verifier("gui")
def verify_gui(args: dict, result: dict) -> VerifierOutcome:
    action = str(args.get("action") or "screenshot").lower()

    if action == "screenshot":
        path = result.get("image_path") or args.get("path")
        if _result_says_unverified(result):
            return _failed("gui", f"screenshot failed: {result.get('error', '?')}")
        if not path:
            return _unverifiable("gui", "screenshot result sin image_path")
        try:
            p = Path(path)
            if not p.is_file():
                return _failed("gui", f"screenshot file ausente: {path}")
            size = p.stat().st_size
            if size < 1000:
                return _failed("gui", f"screenshot sospechosamente chico: {size} bytes")
            return _ok_evidence(
                "gui", f"screenshot saved ({size} bytes)",
                keys=[f"screenshot:{path}"],
                detail={"path": str(p), "size": size},
            )
        except OSError as exc:
            return _unverifiable("gui", f"stat failed: {exc}")

    if action in {"click", "double_click", "right_click", "scroll", "drag", "keypress", "type"}:
        # gui inputs son fire-and-forget; no podemos medir el efecto sin
        # screenshot adicional. Inconclusive es honest.
        if _result_says_unverified(result):
            return _failed("gui", f"{action} failed: {result.get('error', '?')}")
        return _unverifiable(
            "gui",
            f"{action} dispatched; efecto requiere screenshot/vision para confirmar",
        )

    return _unverifiable("gui", f"unknown gui action: {action}")


# ============================================================================
# 8. clipboard
# ============================================================================

@register_verifier("clipboard")
def verify_clipboard(args: dict, result: dict) -> VerifierOutcome:
    action = str(args.get("action") or "read").lower()
    if _result_says_unverified(result):
        return _failed("clipboard", f"clipboard {action} failed: {result.get('error', '?')}")
    if action == "read":
        content = result.get("content")
        if content is None:
            return _unverifiable("clipboard", "clipboard read sin content")
        return _ok_evidence(
            "clipboard", f"clipboard read ({len(content)} chars)",
            detail={"chars": len(content)},
        )
    if action == "write":
        # No podemos verificar sin re-leer (lo cual contamina clipboard del user).
        wrote = result.get("wrote_chars")
        return _unverifiable(
            "clipboard",
            f"write dispatched ({wrote} chars); re-read no se realiza por privacidad",
        )
    return _unverifiable("clipboard", f"unknown clipboard action: {action}")


# ============================================================================
# 9. web
# ============================================================================

@register_verifier("web")
def verify_web(args: dict, result: dict) -> VerifierOutcome:
    action = str(args.get("action") or "search").lower()
    if _result_says_unverified(result):
        return _failed("web", f"web {action} failed: {result.get('error', '?')}")
    if action in {"search", "search_web"}:
        count = result.get("count")
        return _ok_evidence(
            "web", f"search returned {count} results",
            detail={"count": count, "engine": result.get("engine")},
        )
    if action == "open":
        # web_open_url usa webbrowser.open: dispatched, no medible directamente.
        return _unverifiable("web", "open dispatched to default browser (async)")
    if action == "read":
        chars = result.get("chars")
        return _ok_evidence(
            "web", f"page read ({chars} chars)",
            detail={"chars": chars, "title": (result.get("title") or "")[:60]},
        )
    if action == "research":
        sources = result.get("source_count") or 0
        if sources == 0:
            return _unverifiable("web", "research returned 0 sources")
        return _ok_evidence(
            "web", f"research returned {sources} sources",
            detail={"sources": sources},
        )
    return _unverifiable("web", f"unknown web action: {action}")


# ============================================================================
# 10. system (read-only, casi siempre verifiable)
# ============================================================================

@register_verifier("system")
def verify_system(args: dict, result: dict) -> VerifierOutcome:
    action = str(args.get("action") or "time").lower()
    if _result_says_unverified(result):
        return _unverifiable("system", f"{action} failed or partial")
    if action == "time":
        if result.get("iso"):
            return _ok_evidence("system", f"time read: {result.get('human')}")
        return _unverifiable("system", "no iso/human in result")
    if action in {"processes", "windows"}:
        count = len(result.get(action) or [])
        return _ok_evidence(
            "system", f"{action} listed ({count})",
            detail={"count": count},
        )
    if action in {"cpu_ram_gpu", "disk", "battery", "brightness_get"}:
        # Lectura del SO: si la tool no fallo, asumimos confirmed.
        return _ok_evidence("system", f"{action} read OK")
    if action in {"brightness_set", "shutdown", "restart", "sleep"}:
        return _unverifiable(
            "system",
            f"{action} dispatched; efecto async o irreversible — no verificable inline",
        )
    return _unverifiable("system", f"unknown system action: {action}")


# ============================================================================
# Verifiers para tools de soporte / always-confirmed-None
# ============================================================================

@register_verifier("verify")
def verify_meta(args: dict, result: dict) -> VerifierOutcome:
    """Meta: verificar la tool 'verify' produciria recursion. Siempre None."""
    return _unverifiable("verify", "meta-verifier (self-skip to avoid recursion)")


@register_verifier("memory")
def verify_memory(args: dict, result: dict) -> VerifierOutcome:
    """memory.save/recall/list/delete: la tool ya retorna 'ok' del MemoryStore."""
    if _result_says_unverified(result):
        return _failed("memory", f"memory op failed: {result.get('error', '?')}")
    action = str(args.get("action") or "recall").lower()
    if action == "save":
        return _ok_evidence(
            "memory", f"memory saved: {result.get('key')}",
            keys=[f"memory:{result.get('key')}"],
        )
    if action in {"recall", "list"}:
        items = result.get("items") or {}
        n = len(items) if isinstance(items, (dict, list)) else 0
        return _ok_evidence("memory", f"memory {action} returned {n} items")
    if action == "delete":
        return _ok_evidence("memory", f"memory deleted: {result.get('key', '*')}")
    return _unverifiable("memory", f"unknown memory action: {action}")


@register_verifier("whatsapp")
def verify_whatsapp(args: dict, result: dict) -> VerifierOutcome:
    """whatsapp.send_message/open_chat: dispatch async al SO via deeplink.

    El efecto real (chat abierto + texto pre-filled) NO es medible sin GUI
    inspection. Si el dispatch retorno opened=True, marcamos confirmed=None
    con evidence del provider (desktop vs web) y el recipient. El verifier
    NUNCA marca True automaticamente porque WhatsApp no auto-envia — el user
    debe presionar Enter para confirmar.
    """
    if _result_says_unverified(result):
        return _failed("whatsapp", f"whatsapp dispatch failed: {result.get('error', '?')}")
    action = str(args.get("action") or "send_message").lower()
    if action == "status":
        return _ok_evidence("whatsapp", "status query (read-only)")
    if action in {"send_message", "send", "open_chat"}:
        provider = result.get("provider", "?")
        normalized = result.get("recipient_normalized", "?")
        return _unverifiable(
            "whatsapp",
            f"whatsapp {action} dispatched to {provider} for +{normalized} "
            "(message pre-filled, NOT sent — user must press Enter)",
            detail={
                "provider": provider,
                "recipient": result.get("recipient_phone"),
                "has_text": bool(result.get("text")),
            },
        )
    return _unverifiable("whatsapp", f"unknown whatsapp action: {action}")


# ============================================================================
# 14. media (hotfix F 2026-05-17)
# ============================================================================

@register_verifier("media")
def verify_media(args: dict, result: dict) -> VerifierOutcome:
    """Verify media playback / open actions.

    Structural-evidence only: auto_play_info.played + query_match
    for streaming plays, and trust media keys for pause/next/etc.
    We do NOT inspect natural-language text in result or reply.
    """
    if _result_says_unverified(result):
        return _failed("media", "tool reported failure",
                       {"error": result.get("error")})
    action = str(args.get("action") or "").lower()
    if action in {"pause", "resume", "play_pause", "stop", "next", "previous"}:
        return _ok_evidence("media", "media key dispatched", ["action"])
    if action == "play":
        api = result.get("auto_play_info") or {}
        played = api.get("played")
        verified = api.get("verified")
        query_match = api.get("query_match")
        if played and (verified or query_match):
            return _ok_evidence(
                "media", "auto-play verified",
                ["auto_play_info.played", "auto_play_info.query_match"],
            )
        if result.get("url") or result.get("deeplink"):
            return _unverifiable(
                "media",
                "URL/deeplink dispatched, no playback signal",
                {"url": result.get("url"), "deeplink": result.get("deeplink")},
            )
    return _unverifiable("media", "no playback evidence in tool result")


# ============================================================================
# 15. office (hotfix F 2026-05-17)
# ============================================================================

@register_verifier("office")
def verify_office(args: dict, result: dict) -> VerifierOutcome:
    """Verify office document creation / convert actions.

    Structural-evidence: the returned path must exist on the
    filesystem with non-zero size.
    """
    if _result_says_unverified(result):
        return _failed("office", "tool reported failure",
                       {"error": result.get("error")})
    action = str(args.get("action") or "").lower()
    path = result.get("path")
    if action.startswith("create") or action.startswith("convert"):
        if path:
            import os
            if os.path.exists(path):
                size = os.path.getsize(path)
                if size > 0:
                    return _ok_evidence(
                        "office", "file created on disk",
                        ["path", "size"], {"size": size},
                    )
                return _failed("office", "file exists but empty",
                               {"path": path})
            return _failed("office", "claimed path does not exist",
                           {"path": path})
        return _unverifiable("office", "no path in result")
    return _ok_evidence("office", "non-create action", [])


# ============================================================================
# 16. email (hotfix F 2026-05-17)
# ============================================================================

@register_verifier("email")
def verify_email(args: dict, result: dict) -> VerifierOutcome:
    """Verify email send actions.

    Structural-evidence: message_id or sent=True. Both are
    backend-generated, never inferred from text.
    """
    if _result_says_unverified(result):
        return _failed("email", "tool reported failure",
                       {"error": result.get("error")})
    action = str(args.get("action") or "").lower()
    if action in {"send", "send_message"}:
        if result.get("message_id") or result.get("sent") is True:
            return _ok_evidence(
                "email", "send confirmed",
                ["message_id", "sent"],
            )
        return _unverifiable("email", "no send confirmation")
    return _ok_evidence("email", "non-send action", [])


# ============================================================================
# 17. notification (hotfix F 2026-05-17)
# ============================================================================

@register_verifier("notification")
def verify_notification(args: dict, result: dict) -> VerifierOutcome:
    """Verify notification creation actions.

    Structural-evidence: id / resource_id / task_name returned by
    the OS scheduler.
    """
    if _result_says_unverified(result):
        return _failed("notification", "tool reported failure",
                       {"error": result.get("error")})
    action = str(args.get("action") or "").lower()
    if action in {"toast_now", "toast_schedule", "timer_start",
                  "alarm_create", "reminder_create"}:
        rid = (
            result.get("id")
            or result.get("resource_id")
            or result.get("task_name")
        )
        if rid:
            return _ok_evidence(
                "notification", "resource registered",
                ["id", "resource_id", "task_name"],
            )
        return _unverifiable("notification", "no id in result")
    return _ok_evidence("notification", "non-creation action", [])


# ============================================================================
# 18. routine (hotfix F 2026-05-17)
# ============================================================================

@register_verifier("routine")
def verify_routine(args: dict, result: dict) -> VerifierOutcome:
    """Verify routine creation actions.

    Structural-evidence: id / resource_id assigned by the routine
    store.
    """
    if _result_says_unverified(result):
        return _failed("routine", "tool reported failure",
                       {"error": result.get("error")})
    action = str(args.get("action") or "").lower()
    if action == "create":
        rid = result.get("id") or result.get("resource_id")
        if rid:
            return _ok_evidence(
                "routine", "routine registered",
                ["id", "resource_id"],
            )
        return _unverifiable("routine", "create returned no id")
    return _ok_evidence("routine", "non-create action", [])
