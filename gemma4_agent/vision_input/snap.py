"""Snap-to-element helpers that reuse existing Windows UIA/OCR surfaces."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SnapTarget:
    x: int
    y: int
    name: str = ""
    control_type: str = ""
    rect: tuple[int, int, int, int] | None = None
    source: str = "uia"


CLICKABLE_CONTROL_TYPES = {
    "ButtonControl",
    "CalendarControl",
    "CheckBoxControl",
    "ComboBoxControl",
    "DataItemControl",
    "EditControl",
    "HyperlinkControl",
    "ImageControl",
    "ListItemControl",
    "MenuItemControl",
    "RadioButtonControl",
    "SliderControl",
    "TabItemControl",
    "TextControl",
    "TreeItemControl",
}


def uia_control_from_point(x: int, y: int) -> SnapTarget | None:
    """Return the UIA control at a point without clicking it."""
    try:
        import uiautomation as auto

        ctrl: Any = auto.ControlFromPoint(int(x), int(y))
        if ctrl is None:
            return None
        rect = getattr(ctrl, "BoundingRectangle", None)
        rect_tuple = None
        if rect is not None:
            rect_tuple = (
                int(getattr(rect, "left", 0)),
                int(getattr(rect, "top", 0)),
                int(getattr(rect, "right", 0)),
                int(getattr(rect, "bottom", 0)),
            )
        return SnapTarget(
            x=int(x),
            y=int(y),
            name=str(getattr(ctrl, "Name", "") or ""),
            control_type=str(getattr(ctrl, "ControlTypeName", "") or ""),
            rect=rect_tuple,
            source="uia",
        )
    except Exception:
        return None


def snap_click_target_near(
    x: int,
    y: int,
    *,
    radius_px: int = 180,
    max_control_area_px: int = 900_000,
    bounds: tuple[int, int, int, int] | None = None,
) -> SnapTarget | None:
    """Find a nearby deterministic UIA target suitable for a click.

    Gaze is coarse. Instead of blindly clicking the exact point, scan a small
    grid around it and prefer compact controls exposed by UI Automation.
    """
    radius = max(0, int(radius_px))
    candidates: list[tuple[float, SnapTarget]] = []
    for px, py in _scan_points(int(x), int(y), radius):
        if bounds is not None and not _point_in_rect(px, py, bounds):
            continue
        target = uia_control_from_point(px, py)
        if target is None or target.rect is None:
            continue
        left, top, right, bottom = target.rect
        if bounds is not None and not _rect_intersects((left, top, right, bottom), bounds):
            continue
        width = max(0, right - left)
        height = max(0, bottom - top)
        if width <= 2 or height <= 2:
            continue
        area = width * height
        if area > max_control_area_px and target.control_type not in {"DocumentControl", "PaneControl"}:
            continue
        center_x = left + width // 2
        center_y = top + height // 2
        clickable_bonus = 0.0 if target.control_type in CLICKABLE_CONTROL_TYPES else 120.0
        size_penalty = min(260.0, (area ** 0.5) * 0.08)
        distance = ((center_x - x) ** 2 + (center_y - y) ** 2) ** 0.5
        sample_distance = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
        score = distance + sample_distance * 0.35 + size_penalty + clickable_bonus
        candidates.append((
            score,
            SnapTarget(
                x=int(center_x),
                y=int(center_y),
                name=target.name,
                control_type=target.control_type,
                rect=target.rect,
                source=target.source,
            ),
        ))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _scan_points(x: int, y: int, radius: int) -> tuple[tuple[int, int], ...]:
    if radius <= 0:
        return ((x, y),)
    rings = (0, radius // 4, radius // 2, radius)
    points: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for r in rings:
        offsets = ((0, 0),) if r == 0 else (
            (r, 0),
            (-r, 0),
            (0, r),
            (0, -r),
            (r, r),
            (-r, r),
            (r, -r),
            (-r, -r),
        )
        for dx, dy in offsets:
            point = (int(x + dx), int(y + dy))
            if point in seen:
                continue
            seen.add(point)
            points.append(point)
    return tuple(points)


def _point_in_rect(x: int, y: int, rect: tuple[int, int, int, int]) -> bool:
    left, top, right, bottom = rect
    return left <= x < right and top <= y < bottom


def _rect_intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]
