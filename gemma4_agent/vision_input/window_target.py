"""Window targeting helpers for deterministic camera control.

The camera subsystem only decides which existing desktop window is under the
coarse head pointer. It does not inspect pixels semantically and does not call
the LLM.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


IGNORED_CLASS_NAMES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow",
}

IGNORED_TITLE_PREFIXES = (
    "Gemma 4 Camera Control",
    "Gemma 4 Window Control",
)


@dataclass(frozen=True)
class WindowRect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)

    @property
    def center(self) -> tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)


@dataclass(frozen=True)
class WindowTarget:
    hwnd: int
    title: str
    class_name: str
    rect: WindowRect
    visible: bool
    iconic: bool

    def to_dict(self) -> dict[str, object]:
        out = asdict(self)
        out["rect"] = asdict(self.rect)
        return out


class WindowTargeter:
    """Resolve the top-level window under a screen point."""

    def __init__(
        self,
        *,
        ignored_class_names: set[str] | None = None,
        ignored_title_prefixes: tuple[str, ...] = IGNORED_TITLE_PREFIXES,
    ) -> None:
        self.ignored_class_names = set(IGNORED_CLASS_NAMES)
        if ignored_class_names:
            self.ignored_class_names.update(ignored_class_names)
        self.ignored_title_prefixes = ignored_title_prefixes

    def from_point(self, x: float, y: float) -> WindowTarget | None:
        try:
            import win32con
            import win32gui

            child = int(win32gui.WindowFromPoint((int(round(x)), int(round(y)))) or 0)
            if not child:
                return None
            hwnd = int(win32gui.GetAncestor(child, win32con.GA_ROOT) or child)
            return self._target_from_hwnd(hwnd, win32gui)
        except Exception:
            return None

    def from_point_near(self, x: float, y: float, *, radius_px: int = 160) -> WindowTarget | None:
        """Resolve a window at or near a point.

        Gaze is intentionally coarse. If it lands on a border, taskbar edge, or
        one-pixel virtual-desktop boundary, strict WindowFromPoint can return no
        usable top-level window. Search a small deterministic grid around the
        point before falling back to foreground targeting.
        """
        direct = self.from_point(x, y)
        if direct is not None:
            return direct
        radius = max(0, int(radius_px))
        if radius <= 0:
            return None
        offsets = (
            (radius // 4, 0),
            (-radius // 4, 0),
            (0, radius // 4),
            (0, -radius // 4),
            (radius // 2, 0),
            (-radius // 2, 0),
            (0, radius // 2),
            (0, -radius // 2),
            (radius, 0),
            (-radius, 0),
            (0, radius),
            (0, -radius),
            (radius // 2, radius // 2),
            (-radius // 2, radius // 2),
            (radius // 2, -radius // 2),
            (-radius // 2, -radius // 2),
        )
        seen: set[tuple[int, int]] = set()
        for dx, dy in offsets:
            key = (int(dx), int(dy))
            if key in seen:
                continue
            seen.add(key)
            target = self.from_point(x + dx, y + dy)
            if target is not None:
                return target
        return None

    def foreground(self) -> WindowTarget | None:
        try:
            import win32gui

            hwnd = int(win32gui.GetForegroundWindow() or 0)
            return self._target_from_hwnd(hwnd, win32gui)
        except Exception:
            return None

    def _target_from_hwnd(self, hwnd: int, win32gui: object) -> WindowTarget | None:
        try:
            if not hwnd or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return None
            title = str(win32gui.GetWindowText(hwnd) or "")
            class_name = str(win32gui.GetClassName(hwnd) or "")
            if class_name in self.ignored_class_names:
                return None
            if any(title.startswith(prefix) for prefix in self.ignored_title_prefixes):
                return None
            left, top, right, bottom = [int(v) for v in win32gui.GetWindowRect(hwnd)]
            rect = WindowRect(left, top, right, bottom)
            if rect.width < 80 or rect.height < 60:
                return None
            return WindowTarget(
                hwnd=int(hwnd),
                title=title or class_name or f"hwnd:{hwnd}",
                class_name=class_name,
                rect=rect,
                visible=True,
                iconic=bool(win32gui.IsIconic(hwnd)),
            )
        except Exception:
            return None


class WindowTargetStabilizer:
    """Require the same looked-at window for a short dwell before arming it."""

    def __init__(self, stable_ms: int = 350, lost_grace_ms: int = 500) -> None:
        self.stable_s = max(0.0, stable_ms / 1000.0)
        self.lost_grace_s = max(0.0, lost_grace_ms / 1000.0)
        self._candidate_hwnd: int | None = None
        self._candidate: WindowTarget | None = None
        self._candidate_since_s = 0.0
        self._stable: WindowTarget | None = None
        self._last_seen_s = 0.0

    def update(self, candidate: WindowTarget | None, timestamp_s: float) -> WindowTarget | None:
        hwnd = candidate.hwnd if candidate is not None else None
        if hwnd != self._candidate_hwnd:
            self._candidate_hwnd = hwnd
            self._candidate = candidate
            self._candidate_since_s = timestamp_s
        elif candidate is not None:
            self._candidate = candidate

        if candidate is not None:
            self._last_seen_s = timestamp_s
            if timestamp_s - self._candidate_since_s >= self.stable_s:
                self._stable = candidate
        elif self._stable is not None and timestamp_s - self._last_seen_s > self.lost_grace_s:
            self._stable = None
        return self._stable

    @property
    def candidate(self) -> WindowTarget | None:
        return self._candidate


def short_title(target: WindowTarget | None, max_len: int = 68) -> str:
    if target is None:
        return "none"
    title = target.title.replace("\r", " ").replace("\n", " ").strip()
    if len(title) <= max_len:
        return title
    return title[: max(0, max_len - 3)] + "..."
