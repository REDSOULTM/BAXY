"""Foco + maximize FIABLE de ventanas en Windows, antes de teclear/clickear.

Problema (sesión #847): al interactuar con apps por GUI (WhatsApp, Spotify), la
ventana a veces queda minimizada/sin foco -> la acción falla o va a la ventana
equivocada. El `window(action=focus)` viejo hacía `SetForegroundWindow` directo,
que FALLA bajo el foreground-lock de Windows (el SO restringe quién puede traer
una ventana al frente).

Solución (informe de investigación C, basada en Microsoft Learn): secuencia
canónica con el truco ALT que la propia doc de Windows describe —
`LockSetForegroundWindow`: *"The system automatically enables calls to
SetForegroundWindow if the user presses the ALT key"*. Simular ALT desbloquea
el lock. Capas, en orden:
  1. truco ALT (keybd_event VK_MENU) -> habilita SetForegroundWindow.
  2. AttachThreadInput + ShowWindow(RESTORE/MAXIMIZE) + SetForegroundWindow.
  3. Verificación con GetForegroundWindow + título (no teclear en la ventana mala).
  4. Capa UIA (uiautomation.SetFocus) para apps UWP (WhatsApp es UWP).
  5. Retry con backoff (3 intentos, 80/160/320 ms).

Todo en CÓDIGO (no depende del LLM). Degrada con gracia si faltan libs.
Fuentes: learn.microsoft.com SetForegroundWindow/LockSetForegroundWindow.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

VK_MENU = 0x12          # ALT
KEYEVENTF_KEYUP = 0x0002
SW_RESTORE = 9
SW_MAXIMIZE = 3


def _press_alt(win32api) -> None:
    """Simula ALT down/up. La doc de LockSetForegroundWindow dice que un input
    de ALT habilita SetForegroundWindow para el proceso llamante."""
    try:
        win32api.keybd_event(VK_MENU, 0, 0, 0)
        win32api.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        try:
            from . import gui_safety
            gui_safety.note_agent_input()
        except Exception:
            pass
    except Exception:
        pass


def _attach_and_set(hwnd: int, win32gui, win32api, win32process, win32con) -> bool:
    """AttachThreadInput + restore/maximize + SetForegroundWindow. Limpia el
    attach en finally para nunca dejar threads enganchados (evita el error 87
    intermitente reportado en pywinauto)."""
    try:
        if win32gui.GetForegroundWindow() == hwnd:
            return True
    except Exception:
        pass
    this_tid = win32api.GetCurrentThreadId()
    attached = False
    fg_tid = 0
    try:
        cur_fg = win32gui.GetForegroundWindow()
        if cur_fg:
            fg_tid, _ = win32process.GetWindowThreadProcessId(cur_fg)
        if fg_tid and fg_tid != this_tid:
            try:
                attached = bool(win32process.AttachThreadInput(this_tid, fg_tid, True))
            except Exception:
                attached = False
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, SW_RESTORE)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
        try:
            win32gui.BringWindowToTop(hwnd)
        except Exception:
            pass
        ok = bool(win32gui.SetForegroundWindow(hwnd))
        for fn in ("SetActiveWindow", "SetFocus"):
            try:
                getattr(win32gui, fn)(hwnd)
            except Exception:
                pass
        return ok
    except Exception as exc:
        logger.debug("attach_and_set falló: %s", exc)
        return False
    finally:
        if attached and fg_tid:
            try:
                win32process.AttachThreadInput(this_tid, fg_tid, False)
            except Exception:
                pass


def _verify_focus(hwnd: int, expected_title_substr: str | None, win32gui) -> bool:
    try:
        fg = win32gui.GetForegroundWindow()
    except Exception:
        return False
    if fg != hwnd:
        return False
    if expected_title_substr:
        try:
            title = (win32gui.GetWindowText(fg) or "").lower()
        except Exception:
            title = ""
        if expected_title_substr.lower() not in title:
            return False
    return True


def _uia_focus(hwnd: int) -> None:
    """Capa UIA para apps UWP (WhatsApp). uiautomation es opcional."""
    try:
        import uiautomation as auto
        ctrl = auto.ControlFromHandle(hwnd)
        if ctrl:
            try:
                ctrl.SetActive()
            except Exception:
                pass
            try:
                ctrl.SetFocus()
            except Exception:
                pass
    except Exception:
        pass


def focus_and_maximize(
    hwnd: int,
    expected_title_substr: str | None = None,
    retries: int = 3,
    initial_sleep: float = 0.08,
) -> bool:
    """Trae `hwnd` a foreground + maximizado + verificado. True si lo logra.

    Combina truco ALT + AttachThreadInput + ShowWindow + verificación + capa
    UIA (UWP) + retry con backoff. Devuelve False si tras los reintentos la
    ventana no quedó en foreground (el caller debe NO teclear en ese caso)."""
    try:
        import win32gui
        import win32api
        import win32process
        import win32con
    except Exception as exc:
        logger.warning("pywin32 no disponible; focus_and_maximize no-op: %s", exc)
        return False

    if not hwnd or not win32gui.IsWindow(hwnd):
        logger.error("focus_and_maximize: hwnd %s inválido", hwnd)
        return False

    backoff = initial_sleep
    for attempt in range(max(1, retries)):
        _press_alt(win32api)
        _attach_and_set(hwnd, win32gui, win32api, win32process, win32con)
        time.sleep(backoff)
        if _verify_focus(hwnd, expected_title_substr, win32gui):
            logger.info("focus OK (intento %d) hwnd=%s", attempt + 1, hwnd)
            return True
        # capa UIA (UWP) y reintento
        _uia_focus(hwnd)
        time.sleep(backoff)
        if _verify_focus(hwnd, expected_title_substr, win32gui):
            logger.info("focus OK vía UIA (intento %d) hwnd=%s", attempt + 1, hwnd)
            return True
        backoff *= 2  # 80 -> 160 -> 320 ms

    logger.warning("focus_and_maximize: agotados %d intentos hwnd=%s", retries, hwnd)
    return False
