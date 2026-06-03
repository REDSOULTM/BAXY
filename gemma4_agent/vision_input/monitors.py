"""Monitor layout helpers for mapping camera input to the virtual desktop."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MonitorRect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center(self) -> tuple[float, float]:
        return ((self.left + self.right) / 2.0, (self.top + self.bottom) / 2.0)


@dataclass(frozen=True)
class MonitorInfo:
    index: int
    rect: MonitorRect
    device: str = ""
    primary: bool = False


@dataclass(frozen=True)
class VirtualCanvas:
    monitors: tuple[MonitorInfo, ...]
    rect: MonitorRect
    layout_hash: str

    @property
    def width(self) -> int:
        return self.rect.width

    @property
    def height(self) -> int:
        return self.rect.height

    def monitor_for_yaw(self, yaw: float) -> MonitorInfo:
        """Choose a monitor from coarse head yaw.

        The POC deliberately maps only to regions. Calibration replaces this in
        later phases.
        """
        return self.monitor_for_pose(yaw, 0.0)

    def monitor_for_pose(self, yaw: float, pitch: float) -> MonitorInfo:
        """Choose a monitor from coarse head yaw/pitch.

        This handles non-horizontal layouts, such as two top monitors plus one
        lower monitor. The coarse pose is projected into the virtual desktop and
        the containing monitor is selected. If the projected point lands in a
        gap, choose the nearest monitor center.
        """
        if not self.monitors:
            raise RuntimeError("virtual canvas has no monitors")
        ordered = tuple(sorted(self.monitors, key=lambda m: m.rect.center[0]))
        count = len(ordered)
        if count == 1:
            return ordered[0]

        # Project the coarse pose across the full pose range into the virtual
        # desktop. The limits match pointer._POSE_*_LIMIT so a downward look
        # reaches a monitor placed BELOW the others (vertical layouts) instead of
        # saturating against a tight clamp. Pitch gets the wider span.
        yaw_limit, pitch_limit = 0.75, 0.95
        clamped = max(-yaw_limit, min(yaw_limit, yaw))
        clamped_pitch = max(-pitch_limit, min(pitch_limit, pitch))
        x = self.rect.left + ((clamped + yaw_limit) / (2.0 * yaw_limit)) * max(1, self.rect.width)
        y = self.rect.top + ((clamped_pitch + pitch_limit) / (2.0 * pitch_limit)) * max(1, self.rect.height)
        monitor = self.monitor_at(x, y)
        if monitor is not None:
            return monitor
        return self.nearest_monitor(x, y)

    def monitor_at(self, x: float, y: float) -> MonitorInfo | None:
        """Return the monitor containing a virtual-desktop point, if any."""
        for monitor in self.monitors:
            rect = monitor.rect
            if rect.left <= x < rect.right and rect.top <= y < rect.bottom:
                return monitor
        return None

    def nearest_monitor(self, x: float, y: float) -> MonitorInfo:
        """Return the monitor whose center is nearest to a virtual point."""
        if not self.monitors:
            raise RuntimeError("virtual canvas has no monitors")
        return min(
            self.monitors,
            key=lambda monitor: (
                (monitor.rect.center[0] - x) * (monitor.rect.center[0] - x)
                + (monitor.rect.center[1] - y) * (monitor.rect.center[1] - y)
            ),
        )


def enum_monitors() -> tuple[MonitorInfo, ...]:
    """Return Windows monitor rects, falling back to a single virtual screen."""
    try:
        import win32api
        import win32con

        monitors: list[MonitorInfo] = []
        for idx, item in enumerate(win32api.EnumDisplayMonitors()):
            handle = item[0]
            info = win32api.GetMonitorInfo(handle)
            left, top, right, bottom = info["Monitor"]
            flags = int(info.get("Flags", 0))
            monitors.append(
                MonitorInfo(
                    index=idx,
                    rect=MonitorRect(int(left), int(top), int(right), int(bottom)),
                    device=str(info.get("Device", "")),
                    primary=bool(flags & win32con.MONITORINFOF_PRIMARY),
                )
            )
        if monitors:
            return tuple(monitors)
    except Exception:
        pass
    return (_fallback_monitor(),)


def virtual_canvas(monitors: tuple[MonitorInfo, ...] | None = None) -> VirtualCanvas:
    mons = monitors or enum_monitors()
    left = min(m.rect.left for m in mons)
    top = min(m.rect.top for m in mons)
    right = max(m.rect.right for m in mons)
    bottom = max(m.rect.bottom for m in mons)
    payload = [
        {
            "left": m.rect.left,
            "top": m.rect.top,
            "right": m.rect.right,
            "bottom": m.rect.bottom,
            "primary": m.primary,
            "device": m.device,
        }
        for m in sorted(mons, key=lambda m: (m.rect.left, m.rect.top, m.device))
    ]
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return VirtualCanvas(monitors=mons, rect=MonitorRect(left, top, right, bottom), layout_hash=digest)


def canvas_to_dict(canvas: VirtualCanvas) -> dict[str, object]:
    return {
        "rect": asdict(canvas.rect),
        "layout_hash": canvas.layout_hash,
        "monitor_count": len(canvas.monitors),
        "monitors": [asdict(m) for m in canvas.monitors],
    }


def _fallback_monitor() -> MonitorInfo:
    try:
        import ctypes

        user32 = ctypes.windll.user32
        left = int(user32.GetSystemMetrics(76))
        top = int(user32.GetSystemMetrics(77))
        width = int(user32.GetSystemMetrics(78))
        height = int(user32.GetSystemMetrics(79))
        if width > 0 and height > 0:
            return MonitorInfo(0, MonitorRect(left, top, left + width, top + height), "virtual", True)
    except Exception:
        pass
    return MonitorInfo(0, MonitorRect(0, 0, 1920, 1080), "fallback", True)
