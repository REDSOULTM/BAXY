"""Captura de pantalla RÁPIDA con mss (in-process). Extraído de tools.py
(2026-06-09, ratchet archivo-dios). La ruta PowerShell compilaba C# (Add-Type DPI
+ GDI) en cada llamada (~1.1s); mss captura en ~30-200ms sin subprocess.

PRESERVA el contrato: devuelve dict con image_path/width/height/left/top/monitor
(el left/top traduce coords OCR→pantalla para el click) o None si no se puede
(sin mss / error / modo index) → el caller cae a la ruta PowerShell. DPI-aware
para capturar píxeles FÍSICOS (misma escala que el click en pantallas escaladas).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


def _active_rect() -> Optional[tuple]:
    """Rect (left,top,w,h) del monitor que contiene la ventana en foco
    (GetForegroundWindow → MonitorFromWindow → GetMonitorInfo)."""
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return None
        hmon = u.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        if not hmon:
            return None

        class _RECT(ctypes.Structure):
            _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                        ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

        class _MONINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", _RECT),
                        ("rcWork", _RECT), ("dwFlags", wintypes.DWORD)]
        mi = _MONINFO()
        mi.cbSize = ctypes.sizeof(_MONINFO)
        if not u.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            return None
        r = mi.rcMonitor
        return (int(r.left), int(r.top), int(r.right - r.left), int(r.bottom - r.top))
    except Exception:
        return None


def capture(mode: str, path: Path) -> Optional[dict[str, Any]]:
    """Captura `mode` (primary|all|active) a `path`. Devuelve dict con metadata o
    None (→ caller usa PowerShell). El modo `index:` devuelve None a propósito
    (su semántica debe coincidir con Screen.AllScreens del PS)."""
    try:
        import mss as _mss
        import mss.tools as _mss_tools
        _MSS = getattr(_mss, "MSS", None) or _mss.mss  # 10.x renombró a MSS
    except Exception:
        return None
    # DPI-awareness per-monitor v2 (idempotente, best-effort).
    try:
        import ctypes
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    region = None
    shot = None
    try:
        with _MSS() as sct:
            mons = sct.monitors  # [0]=virtual(all), [1..]=cada monitor

            def _primary_mon():
                # El primario de Windows SIEMPRE tiene su esquina en (0,0). mss NO
                # garantiza que mons[1] sea el primario → elegir por origen (0,0),
                # si no el screenshot+click caen en la pantalla equivocada.
                for _m in mons[1:]:
                    if int(_m.get("left", 9) or 0) == 0 and int(_m.get("top", 9) or 0) == 0:
                        return _m
                return mons[1] if len(mons) > 1 else mons[0]

            if mode == "all":
                region = mons[0]
            elif mode == "primary":
                region = _primary_mon()
            elif mode == "active":
                _ar = _active_rect()
                if _ar is not None:
                    region = {"left": _ar[0], "top": _ar[1], "width": _ar[2], "height": _ar[3]}
                else:
                    region = mons[1] if len(mons) > 1 else mons[0]
            elif mode.startswith("index:"):
                return None   # semántica del index → ruta PowerShell
            else:
                region = mons[0]
            shot = sct.grab(region)
            _mss_tools.to_png(shot.rgb, shot.size, output=str(path))
    except Exception:
        return None
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        _left = int(region.get("left", 0)); _top = int(region.get("top", 0))
        _w = int(region.get("width", 0)); _h = int(region.get("height", 0))
    except Exception:
        _left = _top = 0
        _w = getattr(shot, "width", 0); _h = getattr(shot, "height", 0)
    return {
        "image_path": str(path.resolve()),
        "width": _w, "height": _h, "left": _left, "top": _top, "monitor": mode,
        "file_size": path.stat().st_size, "verified": True, "source": "mss",
    }


__all__ = ["capture"]
