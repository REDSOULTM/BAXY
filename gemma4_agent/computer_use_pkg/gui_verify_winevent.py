"""3ª señal de verify GUI vía SetWinEventHook.

gui_verify usa 2 señales (frame-diff ROI + foreground). El research (11_plan P2)
recomienda una 3ª: observar EVENTOS de UI Automation (EVENT_OBJECT_INVOKED /
VALUECHANGE / STATECHANGE) con SetWinEventHook para fusión 2-de-3, atacando el
~14.3% de false-PASS ("click ciego": el frame no cambió pero la acción SÍ tuvo
efecto, p.ej. un toggle que no repinta el ROI).

SEGURIDAD: SetWinEventHook es OBSERVACIÓN PURA (un listener async out-of-context,
WINEVENT_OUTOFCONTEXT). NO emite SendInput. Por eso es seguro correr en el
la ventana/app en foco (a diferencia de gui.{type,click,keypress} físicos, que la
matarían — ver feedback_never_run_synthetic_input). Este módulo solo LEE eventos.

DISEÑO: un thread dedicado con CoInitialize + message-pump (GetMessage/Dispatch),
SetWinEventHook al rango INVOKED..STATECHANGE, y un buffer de eventos con
timestamp + el thread-id del evento. La correlación con el hwnd objetivo se hace
por GetWindowThreadProcessId(hwnd) == event_thread_id (filtra ruido de Teams/
Outlook/notificaciones del SO en otros procesos).

GATING: GEMMA4_GUI_VERIFY_WINEVENT (default OFF). Sin pywin32/ctypes -> no-op
total (devuelve None = no medible, no rompe la fusión de 2 señales existente).
"""
from __future__ import annotations

import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any


def winevent_enabled() -> bool:
    return (os.environ.get("GEMMA4_GUI_VERIFY_WINEVENT", "0") or "0").strip().lower() not in {
        "0", "false", "no", "off"}


# Constantes Win32 (de winuser.h). Las definimos para no depender de win32con.
_EVENT_OBJECT_INVOKED = 0x8013
_EVENT_OBJECT_VALUECHANGE = 0x800E
_EVENT_OBJECT_STATECHANGE = 0x800A
_WINEVENT_OUTOFCONTEXT = 0x0000
_WINEVENT_SKIPOWNPROCESS = 0x0002


@dataclass
class _Recorder:
    """Buffer de eventos UI capturados mientras está activo. Vive en su thread."""
    events: "queue.Queue[dict[str, Any]]" = field(default_factory=queue.Queue)
    _thread: threading.Thread | None = None
    _stop: threading.Event = field(default_factory=threading.Event)
    _hook_installed: threading.Event = field(default_factory=threading.Event)
    _tid: int | None = None  # thread id del pump (para PostThreadMessage)


def start_recording() -> Any:
    """Arranca un recorder de eventos UI. Devuelve un handle opaco (o None si no
    disponible / gated off). No lanza nunca."""
    if not winevent_enabled():
        return None
    try:
        import ctypes  # noqa: F401  (probe de disponibilidad)
    except Exception:
        return None
    rec = _Recorder()

    def _pump() -> None:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        ole32 = ctypes.windll.ole32
        try:
            ole32.CoInitialize(None)
        except Exception:
            pass
        WinEventProcType = ctypes.WINFUNCTYPE(
            None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
            wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)

        def _callback(hHook, event, hwnd, idObject, idChild, dwThread, dwms):
            try:
                rec.events.put_nowait({
                    "event": int(event), "hwnd": int(hwnd) if hwnd else 0,
                    "event_thread_id": int(dwThread), "t_ms": int(dwms)})
            except Exception:
                pass

        cb = WinEventProcType(_callback)
        hook = user32.SetWinEventHook(
            _EVENT_OBJECT_STATECHANGE, _EVENT_OBJECT_INVOKED,  # rango STATECHANGE..INVOKED
            0, cb, 0, 0, _WINEVENT_OUTOFCONTEXT | _WINEVENT_SKIPOWNPROCESS)
        rec._tid = int(ctypes.windll.kernel32.GetCurrentThreadId())
        rec._hook_installed.set()
        if not hook:
            return
        # Message pump hasta que nos pidan parar.
        msg = wintypes.MSG()
        while not rec._stop.is_set():
            # PeekMessage no-bloqueante + sleep corto: permite chequear _stop.
            if user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):  # PM_REMOVE
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.01)
        try:
            user32.UnhookWinEvent(hook)
        except Exception:
            pass
        try:
            ole32.CoUninitialize()
        except Exception:
            pass

    t = threading.Thread(target=_pump, name="gui_winevent_pump", daemon=True)
    rec._thread = t
    t.start()
    # Esperar a que el hook se instale (breve), para no perder eventos tempranos.
    rec._hook_installed.wait(timeout=0.5)
    return rec


def stop_and_check(handle: Any, target_hwnd: int | None) -> bool | None:
    """Para el recorder y devuelve si HUBO un evento UI relevante.

    True  = se observó un evento INVOKED/VALUECHANGE/STATECHANGE correlacionado
            con la ventana objetivo (o cualquier evento si no hay target).
    False = el recorder corrió pero NO se observó ningún evento relevante.
    None  = no disponible / gated off / error (no medible -> no afecta la fusión).
    """
    if handle is None:
        return None
    rec: _Recorder = handle
    try:
        # Dar un instante para que lleguen eventos en vuelo, luego parar.
        time.sleep(0.05)
        rec._stop.set()
        if rec._thread is not None:
            rec._thread.join(timeout=0.5)
        # Drenar el buffer.
        seen: list[dict[str, Any]] = []
        while True:
            try:
                seen.append(rec.events.get_nowait())
            except queue.Empty:
                break
        if not seen:
            return False
        if not target_hwnd:
            return True  # hubo actividad UI y no tenemos con qué correlacionar
        # Correlación: el thread del evento == el thread de la ventana objetivo.
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            pid = wintypes.DWORD()
            target_tid = user32.GetWindowThreadProcessId(
                wintypes.HWND(target_hwnd), ctypes.byref(pid))
        except Exception:
            return True  # no pudimos correlacionar -> aceptamos la actividad
        for ev in seen:
            if ev.get("event_thread_id") == int(target_tid):
                return True
        # Hubo eventos pero ninguno del thread de la ventana objetivo (ruido de
        # otro proceso). Conservador: no afirmamos cambio por ruido ajeno.
        return False
    except Exception:
        return None
