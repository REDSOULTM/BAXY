"""Per-Monitor-V2 DPI awareness for the camera-control subsystem (Windows).

Without this, a non-DPI-aware process is fed *virtualized* (scaled) coordinates
by Windows: tkinter's geometry "+x+y" and win32 monitor rects then disagree on
multi-monitor setups with mixed scaling. The visible symptom is that calibration
dots on a monitor at a different scale land shifted and never reach the corners.

Declaring Per-Monitor-Aware-V2 makes win32 rects and window placement use the
same physical pixels across every monitor. Must run BEFORE any window (cv2/tk) or
monitor enumeration. Idempotent and safe to call on non-Windows (no-op).
"""
from __future__ import annotations

_applied = False


def ensure_dpi_awareness() -> str:
    """Make the process Per-Monitor-V2 DPI aware. Returns a short status string.

    Tries the most precise API first and falls back for older Windows:
      1. user32.SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)  [Win10 1703+]
      2. shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE) [Win8.1+]
      3. user32.SetProcessDPIAware()                                  [Vista+]
    Never raises; a process can only set this once, so later calls are no-ops.
    """
    global _applied
    if _applied:
        return "already-applied"
    try:
        import ctypes
    except Exception:
        return "no-ctypes"
    # Only meaningful on Windows.
    if not hasattr(ctypes, "windll"):
        _applied = True
        return "not-windows"

    # 1) Per-Monitor-V2 (best): coordinates are physical on every monitor.
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 == -4
        ctx = ctypes.c_void_p(-4)
        if bool(ctypes.windll.user32.SetProcessDpiAwarenessContext(ctx)):
            _applied = True
            return "per-monitor-v2"
    except Exception:
        pass

    # 2) Per-Monitor (V1).
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE == 2
        hr = ctypes.windll.shcore.SetProcessDpiAwareness(2)
        # S_OK (0) or E_ACCESSDENIED (already set) both mean we are aware enough.
        if hr in (0, -2147024891):
            _applied = True
            return "per-monitor-v1"
    except Exception:
        pass

    # 3) System-DPI aware (last resort: correct on the primary scale only).
    try:
        if bool(ctypes.windll.user32.SetProcessDPIAware()):
            _applied = True
            return "system-aware"
    except Exception:
        pass

    return "failed"
