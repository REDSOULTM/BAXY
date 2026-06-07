"""Observador ambiente — la "capa viva" del Jarvis (R-Jarvis, 2026-05-30).

Observa el comportamiento REAL del usuario (no solo lo que el agente ejecuta) para
que el sistema aprenda QUIÉN es y le dé esa info a Gemma4. Diseño respaldado por
investigación verificada:
  - Generative Agents (Park et al., arXiv:2304.03442): observación → reflexión →
    insight. Este módulo es la capa de OBSERVACIÓN (la reflexión vive en
    taste_reflector.py).
  - On-device personalization (Google): todo local, nada sale de la PC.

Qué observa (METADATA, NO contenido — la línea de privacidad de la investigación):
  - media_play: artista — título de lo que suena (SMTC / Windows.Media.Control,
    cubre Spotify, navegador, cualquier reproductor). Señal de gustos #1.
  - app_focus: qué app tenés en foco y cuánto (proc name, NO el título de ventana
    — los títulos filtran contenido privado: emails, chats, URLs).
  - franja horaria (mañana/tarde/noche/madrugada): ritmo diario.

NO observa: títulos de ventana, teclado, clipboard, pantalla, navegación. Por diseño.

Cómo: muestrea cada `poll_s` segundos en un thread daemon; registra solo CAMBIOS
(transición de app / cambio de canción) con su duración → no infla el log. Escribe
al BehaviorLog con context={"source":"ambient"} para distinguir de lo que abre el
agente. Best-effort: nunca lanza, nunca bloquea el turno de voz.

Gates:
  GEMMA4_AMBIENT_OBSERVER=0   desactiva el observador (default ON si Jarvis ON).
  GEMMA4_JARVIS=0             desactiva todo el loop proactivo (incluye esto).

Privacidad (table-stakes de la industria, todas implementadas vía behavior_log):
  local (~/.gemma4/behavior) · inspectable (profile_inspect) · borrable (prune /
  forget) · pausable (el gate). Ver taste_profile.py para inspect/forget.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    if (os.environ.get("GEMMA4_JARVIS") or "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    # NO grabar en entornos de TEST/DIAGNÓSTICO: pruebas en vivo del agente
    # (scripts/_diag/*, pytest) abren Paint/Calc/Notepad y disparan media de prueba
    # — el observador los grababa en la DB REAL del usuario (usuario.db) como si
    # fueran su uso, contaminando el perfil de gustos y generando correlaciones
    # ESPURIAS ("abrís Spotify -> abrís Disney"). Causa raíz medida 2026-06-07.
    # Señales de entorno no-productivo (cualquiera basta):
    #   - pytest cargado en el proceso;
    #   - GEMMA4_AGENT_SAFETY=0 (lo setean TODOS los harnesses de diag; prod nunca).
    # Override explícito para tests que SÍ quieran ejercitar el observador:
    # GEMMA4_AMBIENT_FORCE=1.
    if (os.environ.get("GEMMA4_AMBIENT_FORCE") or "").strip().lower() not in {"1", "true", "yes", "on"}:
        import sys as _sys
        if "pytest" in _sys.modules:
            return False
        if (os.environ.get("GEMMA4_AGENT_SAFETY") or "").strip().lower() in {"0", "false", "no", "off"}:
            return False
    raw = (os.environ.get("GEMMA4_AMBIENT_OBSERVER") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _slot(ts: float) -> str:
    """Franja horaria humana (para aprender 'usás Spotify de noche')."""
    h = time.localtime(ts).tm_hour
    if 5 <= h < 12:
        return "mañana"
    if 12 <= h < 19:
        return "tarde"
    if 19 <= h < 24:
        return "noche"
    return "madrugada"


def _foreground_proc() -> Optional[str]:
    """Nombre del proceso de la ventana en foco (lowercase). None si no se puede.
    NO devuelve el título (contenido privado) — solo la identidad de la app."""
    try:
        import win32gui
        import win32process
        import psutil
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            return psutil.Process(pid).name().lower()
        except Exception:
            return None
    except Exception:
        return None


def _now_playing() -> Optional[tuple[str, str]]:
    """(clave, app) de lo que suena, o None. clave = 'artista — título'.
    Usa SMTC (Windows.Media.Control) vía winsdk; cubre cualquier reproductor."""
    try:
        import asyncio
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as _Mgr)

        async def _go():
            mgr = await _Mgr.request_async()
            sess = mgr.get_current_session()
            if sess is None:
                return None
            pb = sess.get_playback_info()
            # 4 == Playing en GlobalSystemMediaTransportControlsSessionPlaybackStatus
            try:
                if int(pb.playback_status) != 4:
                    return None
            except Exception:
                pass
            info = await sess.try_get_media_properties_async()
            artist = (info.artist or "").strip()
            title = (info.title or "").strip()
            if not title:
                return None
            key = f"{artist} — {title}" if artist else title
            app = (sess.source_app_user_model_id or "").strip().lower()
            return key, app

        try:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_go())
            finally:
                loop.close()
        except Exception:
            return None
    except Exception:
        return None


class AmbientObserver:
    """Thread daemon que muestrea foco de app + media y registra transiciones."""

    def __init__(self, behavior_log, *, poll_s: float = 5.0, min_dwell_s: float = 8.0):
        self.log = behavior_log
        self.poll_s = max(1.0, float(poll_s))
        self.min_dwell_s = float(min_dwell_s)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._cur_app: Optional[str] = None
        self._app_start = 0.0
        self._last_media: Optional[str] = None

    def start(self) -> bool:
        if not _enabled():
            return False
        if _foreground_proc() is None and _now_playing() is None:
            # ni win32 ni SMTC disponibles (no-Windows / sin deps) → no arranca.
            logger.debug("ambient observer: sin fuentes (win32/SMTC) — no arranca")
            return False
        if self._thread is not None and self._thread.is_alive():
            return True
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="gemma4-ambient-observer", daemon=True)
        self._thread.start()
        logger.info("ambient observer iniciado (poll=%.0fs)", self.poll_s)
        return True

    def stop(self) -> None:
        self._stop.set()
        # flush del app actual
        self._flush_app(time.time())

    def _flush_app(self, now: float) -> None:
        if self._cur_app is None:
            return
        dwell = now - self._app_start
        if dwell >= self.min_dwell_s:
            try:
                self.log.record("app_focus", self._cur_app, context={
                    "source": "ambient", "slot": _slot(self._app_start),
                    "dwell_s": round(dwell, 1)})
            except Exception:
                pass
        self._cur_app = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            now = time.time()
            # --- app en foco (transiciones) ---
            try:
                app = _foreground_proc()
                if app and app != self._cur_app:
                    self._flush_app(now)
                    self._cur_app = app
                    self._app_start = now
            except Exception:
                pass
            # --- media (cambio de canción) ---
            try:
                np = _now_playing()
                if np is not None:
                    key, mapp = np
                    if key != self._last_media:
                        self._last_media = key
                        self.log.record("media_play", key[:120], context={
                            "source": "ambient", "slot": _slot(now), "app": mapp})
            except Exception:
                pass
            self._stop.wait(self.poll_s)
