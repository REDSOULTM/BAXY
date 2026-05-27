"""Read-only capability detection for computer-use windows.

This module does not move the mouse, type, focus, close, or relaunch anything.
It only observes the current/top-level window and exposes a compact snapshot so
the executor can choose API/UIA/CDP/OCR/vision paths and trace why.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import shutil
import time
from typing import Any


@dataclass(slots=True)
class CapabilitySnapshot:
    ok: bool
    window_title: str = ""
    window_class: str = ""
    hwnd: int = 0
    pid: int = 0
    process_name: str = ""
    app_kind: str = "unknown"
    is_browser: bool = False
    is_chromium: bool = False
    cdp_candidate: bool = False
    uia_checked: bool = False
    uia_available: bool | None = None
    uia_element_count: int | None = None
    uia_degraded: bool | None = None
    ocr_available: bool | None = None
    vision_fallback_available: bool | None = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_BROWSER_PROCESSES = {
    "chrome.exe", "msedge.exe", "opera.exe", "opera_gx.exe",
    "brave.exe", "firefox.exe", "vivaldi.exe",
}
_CHROMIUM_CLASSES = {"Chrome_WidgetWin_1", "Chrome_WidgetWin_0", "Intermediate D3D Window"}
_ELECTRON_PROCESSES = {
    "discord.exe", "slack.exe", "teams.exe", "spotify.exe",
    "whatsapp.exe", "code.exe",
}
_OFFICE_PROCESSES = {
    "winword.exe", "excel.exe", "powerpnt.exe", "onenote.exe", "outlook.exe",
}


def _process_name(pid: int) -> str:
    if not pid:
        return ""
    try:
        import psutil  # type: ignore
        return str(psutil.Process(pid).name() or "").casefold()
    except Exception:
        return ""


def _classify(process_name: str, class_name: str) -> tuple[str, bool, bool, bool]:
    proc = (process_name or "").casefold()
    cls = class_name or ""
    is_browser = proc in _BROWSER_PROCESSES
    is_chromium = cls in _CHROMIUM_CLASSES or proc in (_BROWSER_PROCESSES - {"firefox.exe", "vivaldi.exe"})
    if is_browser:
        return "browser", True, is_chromium, proc not in {"firefox.exe", "vivaldi.exe"}
    if proc in _ELECTRON_PROCESSES or cls in _CHROMIUM_CLASSES:
        return "electron_or_webview", False, True, False
    if proc in _OFFICE_PROCESSES:
        return "office", False, False, False
    if cls.startswith("Windows.UI.") or cls in {"ApplicationFrameWindow", "WinUIDesktopWin32WindowClass"}:
        return "winui_uwp", False, False, False
    if proc in {"explorer.exe"}:
        return "explorer_shell", False, False, False
    if proc:
        return "native_or_unknown", False, False, False
    return "unknown", False, False, False


class CapabilityDetector:
    """Small TTL cache around read-only OS/UIA capability snapshots."""

    def __init__(self, tools: Any, ttl_s: float = 0.75):
        self.tools = tools
        try:
            env_ttl = float(os.environ.get("GEMMA4_CAPABILITY_SNAPSHOT_TTL_S", ""))
        except Exception:
            env_ttl = 0.0
        self.ttl_s = max(0.0, env_ttl if env_ttl > 0 else ttl_s)
        self._cache: dict[tuple[str, bool], tuple[float, CapabilitySnapshot]] = {}

    def snapshot(self, window_hint: str = "", include_uia: bool = False) -> dict[str, Any]:
        key = ((window_hint or "").casefold().strip(), bool(include_uia))
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and now - cached[0] <= self.ttl_s:
            data = cached[1].to_dict()
            data["cached"] = True
            return data
        snap = self._snapshot_uncached(window_hint, include_uia)
        self._cache[key] = (now, snap)
        data = snap.to_dict()
        data["cached"] = False
        return data

    def _snapshot_uncached(self, window_hint: str, include_uia: bool) -> CapabilitySnapshot:
        if os.name != "nt":
            return CapabilitySnapshot(ok=False, error="capability detection is Windows-only")
        try:
            import win32gui
            import win32process
        except Exception as exc:
            return CapabilitySnapshot(ok=False, error=f"win32 unavailable: {type(exc).__name__}")

        hwnd = 0
        hint = (window_hint or "").casefold().strip()
        try:
            if hint:
                matches: list[int] = []

                def _cb(h: int, _: object) -> bool:
                    try:
                        title = win32gui.GetWindowText(h) or ""
                        if win32gui.IsWindowVisible(h) and hint in title.casefold():
                            matches.append(h)
                    except Exception:
                        pass
                    return True

                win32gui.EnumWindows(_cb, None)
                hwnd = matches[0] if matches else 0
            if not hwnd:
                hwnd = int(win32gui.GetForegroundWindow() or 0)
            title = win32gui.GetWindowText(hwnd) if hwnd else ""
            cls = win32gui.GetClassName(hwnd) if hwnd else ""
            pid = 0
            if hwnd:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = _process_name(int(pid))
            app_kind, is_browser, is_chromium, cdp_candidate = _classify(proc, cls)
            snap = CapabilitySnapshot(
                ok=bool(hwnd),
                hwnd=int(hwnd or 0),
                window_title=title or "",
                window_class=cls or "",
                pid=int(pid or 0),
                process_name=proc,
                app_kind=app_kind,
                is_browser=is_browser,
                is_chromium=is_chromium,
                cdp_candidate=cdp_candidate,
            )
        except Exception as exc:
            return CapabilitySnapshot(ok=False, error=f"snapshot failed: {type(exc).__name__}: {exc}")

        snap.ocr_available = bool(shutil.which("tesseract") or shutil.which("tesseract.exe"))
        impls = getattr(self.tools, "_impls", None)
        snap.vision_fallback_available = isinstance(impls, dict) and "vision" in impls
        if include_uia:
            snap.uia_checked = True
            try:
                res = self.tools.execute("uia", {
                    "action": "tree",
                    "window": window_hint or snap.window_title,
                    "limit": 80,
                    "timeout_sec": 6,
                })
                elements = res.get("elements") if isinstance(res, dict) else None
                count = len(elements or []) if isinstance(elements, list) else int(res.get("count") or 0)
                snap.uia_available = bool(res.get("ok")) and count > 0
                snap.uia_element_count = count
                snap.uia_degraded = bool(res.get("ok")) and count <= 2 and snap.is_chromium
            except Exception as exc:
                snap.uia_available = False
                snap.error = f"uia snapshot failed: {type(exc).__name__}: {exc}"
        return snap
