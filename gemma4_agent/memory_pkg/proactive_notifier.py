"""Canal de salida PROACTIVO de Jarvis: avisa al usuario por iniciativa propia
(sin que escriba) cuando el observador detecta una rutina repetida.

Decisión del usuario 2026-06-07: estar usando la PC normal y que Baxy, de repente,
sugiera automatizar un patrón — como el Jarvis de Iron Man. Canal: toast nativo de
Windows (siempre) + voz TTS (opcional). Diseño en
documentacion/DISENO_jarvis_proactivo_2026-06-07.md.

NO INTRUSIVO (prioridad #1, el síntoma original era intrusividad):
  - NO avisa en fullscreen / llamada / juego (anti-molestia).
  - respeta los cooldowns del suggestion_queue (1/h, 3/día, 30d por rechazo).
  - solo patrones MUY sólidos (umbrales del pattern_miner: count>=8, consistency>=0.75).

GATES (todos default OFF para no sorprender):
  GEMMA4_JARVIS_PROACTIVE=1       activa el aviso proactivo (toast).
  GEMMA4_JARVIS_PROACTIVE_TTS=1   además habla por voz.

Best-effort: cualquier fallo -> no avisa (nunca rompe el observador).
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# apps donde NO interrumpir (llamada/reunión/juego). Mide la FORMA (proceso en
# foco + fullscreen), no una lista de productos para decidir QUÉ hacer — es una
# guarda estructural anti-molestia. Igual mantenemos un set chico de procesos de
# videollamada conocidos porque fullscreen no siempre los cubre (ventana flotante).
_DO_NOT_DISTURB_PROCS = frozenset({
    "zoom.exe", "teams.exe", "ms-teams.exe", "discord.exe", "webex.exe",
    "skype.exe", "slack.exe", "meet.exe", "googlemeet.exe",
})


def _proactive_enabled() -> bool:
    # ON por default (decisión del user 2026-06-07): el toast proactivo es no-invasivo
    # (anti-molestia + cooldowns). Se apaga explícito con GEMMA4_JARVIS_PROACTIVE=0.
    return (os.environ.get("GEMMA4_JARVIS_PROACTIVE") or "1").strip().lower() \
        not in {"0", "false", "no", "off"}


def _tts_enabled() -> bool:
    return (os.environ.get("GEMMA4_JARVIS_PROACTIVE_TTS") or "").strip().lower() \
        in {"1", "true", "yes", "on"}


def _is_fullscreen_foreground() -> bool:
    """True si la ventana en foco ocupa toda la pantalla (juego/video/presentación)
    — momento donde NO se debe molestar. Best-effort (False si no se puede medir)."""
    try:
        import win32gui  # type: ignore
        import win32api  # type: ignore
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return False
        # el desktop/shell en foco NO es fullscreen-app
        cls = win32gui.GetClassName(hwnd)
        if cls in ("Progman", "WorkerW", "Shell_TrayWnd"):
            return False
        rect = win32gui.GetWindowRect(hwnd)
        sw = win32api.GetSystemMetrics(0)  # SM_CXSCREEN
        sh = win32api.GetSystemMetrics(1)  # SM_CYSCREEN
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        # cubre (casi) toda la pantalla -> fullscreen
        return w >= sw and h >= sh
    except Exception:
        return False


def _in_do_not_disturb(foreground_proc: Optional[str]) -> bool:
    """No molestar si: foco en una app de llamada/reunión, o algo en fullscreen."""
    if foreground_proc and foreground_proc.strip().lower() in _DO_NOT_DISTURB_PROCS:
        return True
    return _is_fullscreen_foreground()


def _speak_async(text: str) -> None:
    """Habla la frase por TTS en un thread aparte (best-effort, no bloquea)."""
    def _go():
        try:
            from ..voice.tts import StreamingTTS
            tts = StreamingTTS()
            tts.feed_text(text)
            if hasattr(tts, "flush"):
                tts.flush()
        except Exception as exc:
            logger.debug("proactive TTS failed: %s", exc)
    threading.Thread(target=_go, name="jarvis-proactive-tts", daemon=True).start()


def notify_suggestion(
    cand: Any,
    *,
    lang: str = "es",
    foreground_proc: Optional[str] = None,
    on_accept: Optional[Callable[[Any], None]] = None,
    on_reject: Optional[Callable[[Any], None]] = None,
    toaster: Any = None,
) -> bool:
    """Avisa proactivamente al usuario de una sugerencia de rutina (cand).

    Devuelve True si se EMITIÓ el aviso (toast/voz), False si se omitió (gate off,
    do-not-disturb, o fallo). Los callbacks on_accept/on_reject se enganchan a los
    botones del toast (Sí/No). `toaster` se inyecta en tests (mock).

    NO crea la rutina acá — eso lo hace on_accept (reusa la lógica del chat).
    """
    if not _proactive_enabled():
        return False
    # ANTI-MOLESTIA: no interrumpir en llamada/fullscreen/juego.
    if _in_do_not_disturb(foreground_proc):
        logger.debug("proactive: do-not-disturb (foco=%s) -> pospongo", foreground_proc)
        return False
    try:
        from .pattern_miner import jarvis_phrase
        body = jarvis_phrase(lang, "offer").format(desc=cand.describe(lang)).strip()
    except Exception as exc:
        logger.debug("proactive: no pude formar la frase: %s", exc)
        return False

    # VOZ (opcional): hablar la sugerencia.
    if _tts_enabled():
        _speak_async(body)

    # TOAST (siempre, el canal principal). Botones Sí/No -> callbacks.
    try:
        if toaster is None:
            from windows_toasts import WindowsToaster, Toast, ToastButton, ToastActivatedEventArgs  # type: ignore
            toaster = WindowsToaster("Baxy")
            toast = Toast()
            toast.text_fields = ["Baxy", body]
            toast.AddAction(ToastButton("Sí, automatizá", arguments="accept"))
            toast.AddAction(ToastButton("No", arguments="reject"))

            def _on_activated(args: "ToastActivatedEventArgs"):
                arg = getattr(args, "arguments", "") or ""
                try:
                    if arg == "accept" and on_accept:
                        on_accept(cand)
                    elif arg == "reject" and on_reject:
                        on_reject(cand)
                except Exception as exc:
                    logger.debug("proactive toast callback failed: %s", exc)
            toast.on_activated = _on_activated
            toaster.show_toast(toast)
        else:
            # path de test: el toaster mock recibe (body, cand, on_accept, on_reject)
            toaster.show(body, cand, on_accept, on_reject)
        logger.info("jarvis proactivo: sugerencia emitida (%s)", cand.describe(lang)[:60])
        return True
    except Exception as exc:
        logger.debug("proactive toast failed: %s", exc)
        return False
