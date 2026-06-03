"""Deterministic gesture-to-window control state machines."""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .monitors import MonitorRect
from .window_target import WindowRect, WindowTarget


class CameraControlState(str, Enum):
    IDLE = "IDLE"
    ARMED = "ARMED"
    DRAGGING = "DRAGGING"
    SCROLLING = "SCROLLING"
    RESIZING = "RESIZING"


TWO_HAND_CONTROL_LABELS = {"palm", "pinch"}


@dataclass(frozen=True)
class ControlTransition:
    state: CameraControlState
    action: str | None = None


class CameraControlStateMachine:
    """State machine only; Phase 0 never executes GUI actions."""

    def __init__(self) -> None:
        self.state = CameraControlState.IDLE

    def update(self, *, hand_present: bool, gesture: str) -> ControlTransition:
        if not hand_present:
            self.state = CameraControlState.IDLE
            return ControlTransition(self.state)
        if self.state == CameraControlState.IDLE:
            self.state = CameraControlState.ARMED
            return ControlTransition(self.state)
        if self.state == CameraControlState.ARMED and gesture == "fist":
            self.state = CameraControlState.DRAGGING
            return ControlTransition(self.state, "grab")
        if self.state == CameraControlState.DRAGGING and gesture == "palm":
            self.state = CameraControlState.ARMED
            return ControlTransition(self.state, "drop")
        return ControlTransition(self.state)


@dataclass(frozen=True)
class HandControlPose:
    """Normalized hand pose in camera-frame coordinates."""

    x: float
    y: float
    label: str
    handedness: str = ""
    score: float | None = None
    raw_label: str = ""
    gesture_confidence: float | None = None
    track_id: str = ""
    quality_ok: bool = True
    quality_reason: str = "good"
    palm_size: float = 0.0
    index_tip_x: float | None = None
    index_tip_y: float | None = None
    index_tip_z: float | None = None
    palm_x: float | None = None
    palm_y: float | None = None
    palm_z: float | None = None


@dataclass(frozen=True)
class ActionEvent:
    name: str
    target_title: str = ""
    target_hwnd: int | None = None
    detail: str = ""
    executed: bool = False


@dataclass(frozen=True)
class WindowControlOutput:
    state: CameraControlState
    events: tuple[ActionEvent, ...]
    target: WindowTarget | None


@dataclass(frozen=True)
class WindowControlConfig:
    execute_actions: bool = False
    drag_gain_x_px: float = 2600.0
    drag_gain_y_px: float = 1500.0
    drag_min_px: int = 8
    drag_smoothing_alpha: float = 0.45
    drag_max_step_px: int = 180
    scroll_threshold_norm: float = 0.035
    scroll_gain: float = 3600.0
    scroll_rearm_threshold_norm: float = 0.012
    scroll_min_wheel_delta: int = 120
    scroll_max_wheel_delta: int = 360
    resize_ratio_threshold: float = 0.045
    resize_ratio_smoothing_alpha: float = 0.30
    resize_step_px: int = 24
    resize_min_width: int = 360
    resize_min_height: int = 240
    maximize_ratio: float = 1.55
    restore_ratio: float = 0.65
    two_hand_min_distance: float = 0.10
    two_hand_zoom_step_ratio: float = 0.12
    two_hand_zoom_cooldown_s: float = 0.22
    point_click_cooldown_s: float = 0.70
    # Snap search radius. Webcam head-pose lands the cursor ~300-400px from intent
    # (measured), so the snap must scan at least that far to find the real button;
    # a radius smaller than the tracking error leaves the target outside the scan.
    point_snap_radius_px: int = 320
    point_tap_threshold_norm: float = 0.14
    point_tap_release_norm: float = 0.055
    window_snap_enabled: bool = True
    window_snap_edge_px: int = 72


class WindowActuator:
    """Small Win32 actuator. In safe mode it only reports intended actions."""

    def __init__(
        self,
        *,
        execute: bool = False,
        desktop_rect: MonitorRect | None = None,
        monitors: tuple[MonitorRect, ...] = (),
    ) -> None:
        self.execute = execute
        self.desktop_rect = desktop_rect
        self.monitors = tuple(monitors)

    def move_resize(self, target: WindowTarget, left: int, top: int, width: int, height: int) -> bool:
        left, top, width, height = self._bounded_geometry(left, top, width, height)
        if not self.execute:
            return False
        try:
            import win32con
            import win32gui

            win32gui.ShowWindow(target.hwnd, win32con.SW_RESTORE)
            flags = win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
            return bool(win32gui.SetWindowPos(target.hwnd, 0, left, top, width, height, flags))
        except Exception:
            return False

    def maximize(self, target: WindowTarget) -> bool:
        if not self.execute:
            return False
        try:
            import win32con
            import win32gui

            win32gui.ShowWindow(target.hwnd, win32con.SW_SHOWMAXIMIZED)
            return True
        except Exception:
            return False

    def restore(self, target: WindowTarget) -> bool:
        if not self.execute:
            return False
        try:
            import win32con
            import win32gui

            win32gui.ShowWindow(target.hwnd, win32con.SW_RESTORE)
            return True
        except Exception:
            return False

    def scroll(self, target: WindowTarget, screen_x: int, screen_y: int, wheel_delta: int) -> bool:
        if not self.execute:
            return False
        try:
            import win32con
            import win32gui

            delta = max(-720, min(720, int(wheel_delta)))
            if abs(delta) < 1:
                return False
            wparam = _make_long(0, delta)
            lparam = _make_long(screen_x, screen_y)
            win32gui.PostMessage(target.hwnd, win32con.WM_MOUSEWHEEL, wparam, lparam)
            return True
        except Exception:
            return False

    def zoom(self, target: WindowTarget, screen_x: int, screen_y: int, direction: int) -> bool:
        if not self.execute:
            return False
        try:
            import win32con
            import win32gui

            delta = 120 if direction > 0 else -120
            wparam = _make_long(win32con.MK_CONTROL, delta)
            lparam = _make_long(screen_x, screen_y)
            win32gui.PostMessage(target.hwnd, win32con.WM_MOUSEWHEEL, wparam, lparam)
            return True
        except Exception:
            return False

    def click_near(self, target: WindowTarget, screen_x: int, screen_y: int, radius_px: int) -> tuple[bool, str]:
        snap_x, snap_y = int(screen_x), int(screen_y)
        snap_detail = "raw"
        try:
            from .snap import snap_click_target_near

            bounds = (target.rect.left, target.rect.top, target.rect.right, target.rect.bottom)
            snap = snap_click_target_near(snap_x, snap_y, radius_px=radius_px, bounds=bounds)
            if snap is not None:
                snap_x, snap_y = snap.x, snap.y
                label = snap.name or snap.control_type or snap.source
                snap_detail = f"{snap.source}:{label[:40]} @{snap_x},{snap_y}"
        except Exception:
            snap_detail = "raw"
        if not self.execute:
            return (False, snap_detail)
        try:
            import win32con
            import win32gui

            child = int(win32gui.WindowFromPoint((snap_x, snap_y)) or target.hwnd)
            client_x, client_y = win32gui.ScreenToClient(child, (snap_x, snap_y))
            lparam = _make_long(client_x, client_y)
            win32gui.PostMessage(child, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            win32gui.PostMessage(child, win32con.WM_LBUTTONUP, 0, lparam)
            return (True, snap_detail)
        except Exception:
            return (False, snap_detail)

    def _bounded_geometry(self, left: int, top: int, width: int, height: int) -> tuple[int, int, int, int]:
        width = max(80, int(width))
        height = max(60, int(height))
        if self.desktop_rect is None:
            return (int(left), int(top), width, height)
        bounds = self.desktop_rect
        width = min(width, bounds.width)
        height = min(height, bounds.height)
        max_left = bounds.right - width
        max_top = bounds.bottom - height
        return (
            int(max(bounds.left, min(max_left, left))),
            int(max(bounds.top, min(max_top, top))),
            width,
            height,
        )


class FixedGestureWindowController:
    """Fixed deterministic grammar for the first window-control phase.

    - Fist grabs the looked-at window and moves it with the hand.
    - Open palm scrolls the looked-at window.
    - Two hands zoom content by changing hand distance.
    - Point clicks the nearest interactable control near gaze within the looked-at window.
    """

    def __init__(self, config: WindowControlConfig, actuator: WindowActuator) -> None:
        self.config = config
        self.actuator = actuator
        self.state = CameraControlState.IDLE
        self._drag_target: WindowTarget | None = None
        self._drag_start_hand: tuple[float, float] | None = None
        self._drag_start_rect: WindowRect | None = None
        self._last_drag_rect: tuple[int, int, int, int] | None = None
        self._drag_filtered_pos: tuple[float, float] | None = None
        self._scroll_target: WindowTarget | None = None
        self._scroll_anchor_y: float | None = None
        self._scroll_last_y: float | None = None
        self._scroll_direction: int | None = None
        self._resize_target: WindowTarget | None = None
        self._resize_start_distance: float | None = None
        self._resize_start_rect: WindowRect | None = None
        self._resize_filtered_ratio: float | None = None
        self._last_resize_rect: tuple[int, int, int, int] | None = None
        self._last_zoom_step = 0
        self._last_zoom_s = 0.0
        self._resize_started_s = 0.0
        self._resize_max_sent = False
        self._resize_restore_sent = False
        self._point_down = False
        self._point_anchor: tuple[float, float, float] | None = None
        self._point_wait_release = False
        self._last_point_click_s = -9999.0

    def update(
        self,
        *,
        timestamp_s: float,
        target: WindowTarget | None,
        hands: tuple[HandControlPose, ...],
        pointer_xy: tuple[int, int] | None,
    ) -> WindowControlOutput:
        events: list[ActionEvent] = []
        if not hands:
            if self.state in {CameraControlState.DRAGGING, CameraControlState.SCROLLING, CameraControlState.RESIZING}:
                events.append(self._event("release", self._active_target(), "hand lost", False))
            self._reset_interaction()
            self.state = CameraControlState.IDLE
            return WindowControlOutput(self.state, tuple(events), target)

        if self.state == CameraControlState.DRAGGING:
            events.extend(self._update_drag(hands[0]))
            return WindowControlOutput(self.state, tuple(events), self._drag_target or target)

        if self.state == CameraControlState.RESIZING:
            events.extend(self._update_resize(timestamp_s, hands))
            return WindowControlOutput(self.state, tuple(events), self._resize_target or target)

        if self.state == CameraControlState.SCROLLING:
            primary = hands[0]
            if primary.label == "palm" and self._scroll_target is not None:
                events.extend(self._update_scroll(self._scroll_target, primary, pointer_xy))
                return WindowControlOutput(self.state, tuple(events), self._scroll_target)
            events.append(self._event("scroll_end", self._scroll_target, "palm released", False))
            self._reset_scroll()
            self.state = CameraControlState.ARMED
            return WindowControlOutput(self.state, tuple(events), target)

        if len(hands) >= 2 and target is not None and _two_hand_control_ready(hands):
            events.extend(self._update_resize(timestamp_s, hands, target=target))
            return WindowControlOutput(self.state, tuple(events), target)

        primary = _primary_action_hand(hands)
        if self.state == CameraControlState.IDLE:
            self.state = CameraControlState.ARMED
        if primary.label != "point":
            self._reset_point()

        if primary.label == "fist" and target is not None:
            events.extend(self._start_drag(target, primary))
        elif primary.label == "palm" and target is not None:
            events.extend(self._update_scroll(target, primary, pointer_xy))
        elif primary.label == "point" and target is not None:
            events.extend(self._update_point_click(timestamp_s, target, primary, pointer_xy))
        else:
            if self.state == CameraControlState.SCROLLING:
                events.append(self._event("scroll_end", self._scroll_target, "palm released", False))
            self._scroll_target = None
            self._scroll_anchor_y = None
            self._reset_point()
            self.state = CameraControlState.ARMED

        return WindowControlOutput(self.state, tuple(events), target)

    def _start_drag(self, target: WindowTarget, hand: HandControlPose) -> list[ActionEvent]:
        if self.state != CameraControlState.DRAGGING:
            self.state = CameraControlState.DRAGGING
            self._drag_target = target
            self._drag_start_hand = (hand.x, hand.y)
            self._drag_start_rect = target.rect
            self._last_drag_rect = None
            self._drag_filtered_pos = None
            return [self._event("grab_window", target, "fist", self.actuator.execute)]
        return []

    def _update_drag(self, hand: HandControlPose) -> list[ActionEvent]:
        if hand.label == "palm":
            target = self._drag_target
            self._reset_interaction()
            self.state = CameraControlState.ARMED
            return [self._event("drop_window", target, "open palm", self.actuator.execute)]
        if hand.label != "fist":
            return []
        if self._drag_target is None or self._drag_start_hand is None or self._drag_start_rect is None:
            self._reset_interaction()
            self.state = CameraControlState.ARMED
            return []
        dx = (hand.x - self._drag_start_hand[0]) * self.config.drag_gain_x_px
        dy = (hand.y - self._drag_start_hand[1]) * self.config.drag_gain_y_px
        desired_left = float(self._drag_start_rect.left + dx)
        desired_top = float(self._drag_start_rect.top + dy)
        if self._drag_filtered_pos is None:
            filtered_left, filtered_top = desired_left, desired_top
        else:
            filtered_left, filtered_top = self._drag_filtered_pos
            alpha = _clamp_float(self.config.drag_smoothing_alpha, 0.05, 1.0)
            step_x = (desired_left - filtered_left) * alpha
            step_y = (desired_top - filtered_top) * alpha
            max_step = max(1.0, float(self.config.drag_max_step_px))
            mag = math.hypot(step_x, step_y)
            if mag > max_step:
                scale = max_step / mag
                step_x *= scale
                step_y *= scale
            filtered_left += step_x
            filtered_top += step_y
        self._drag_filtered_pos = (filtered_left, filtered_top)
        left = int(round(filtered_left))
        top = int(round(filtered_top))
        width = self._drag_start_rect.width
        height = self._drag_start_rect.height
        snap_detail = ""
        if self.config.window_snap_enabled:
            left, top, width, height, snap_detail = _snap_window_rect(
                left,
                top,
                width,
                height,
                self.actuator.monitors,
                edge_px=self.config.window_snap_edge_px,
            )
        rect_key = (left, top, width, height)
        if self._last_drag_rect is not None:
            moved = math.hypot(left - self._last_drag_rect[0], top - self._last_drag_rect[1])
            if moved < self.config.drag_min_px:
                return []
        self._last_drag_rect = rect_key
        executed = self.actuator.move_resize(self._drag_target, left, top, width, height)
        detail = f"{snap_detail}move to {left},{top} {width}x{height}"
        return [self._event("move_window", self._drag_target, detail, executed)]

    def _update_scroll(
        self,
        target: WindowTarget,
        hand: HandControlPose,
        pointer_xy: tuple[int, int] | None,
    ) -> list[ActionEvent]:
        if self.state != CameraControlState.SCROLLING or self._scroll_target is None:
            self.state = CameraControlState.SCROLLING
            self._scroll_target = target
            self._scroll_anchor_y = hand.y
            self._scroll_last_y = hand.y
            self._scroll_direction = None
            return [self._event("scroll_start", target, "open palm", self.actuator.execute)]
        if self._scroll_anchor_y is None or self._scroll_last_y is None:
            self._scroll_anchor_y = hand.y
            self._scroll_last_y = hand.y
            return []
        dy = hand.y - self._scroll_last_y
        if self._scroll_direction is None:
            dy = hand.y - self._scroll_anchor_y
            if abs(dy) < self.config.scroll_threshold_norm:
                return []
            self._scroll_direction = 1 if dy > 0 else -1
        elif abs(dy) < self.config.scroll_rearm_threshold_norm:
            return []
        elif (dy > 0 and self._scroll_direction < 0) or (dy < 0 and self._scroll_direction > 0):
            # Clutch return: keep palm open, move the hand back, but do not send reverse scroll.
            self._scroll_last_y = hand.y
            return []
        wheel_delta = int(round(dy * self.config.scroll_gain))
        min_delta = max(1, int(self.config.scroll_min_wheel_delta))
        max_delta = max(min_delta, int(self.config.scroll_max_wheel_delta))
        if abs(wheel_delta) < min_delta:
            wheel_delta = min_delta if wheel_delta > 0 else -min_delta
        wheel_delta = max(-max_delta, min(max_delta, wheel_delta))
        x, y = pointer_xy or target.rect.center
        executed = self.actuator.scroll(self._scroll_target, x, y, wheel_delta)
        self._scroll_last_y = hand.y
        return [self._event("scroll_window", self._scroll_target, f"wheel {wheel_delta}", executed)]

    def _update_resize(
        self,
        timestamp_s: float,
        hands: tuple[HandControlPose, ...],
        *,
        target: WindowTarget | None = None,
    ) -> list[ActionEvent]:
        if len(hands) < 2 or not _two_hand_control_ready(hands):
            target = self._resize_target
            self._reset_interaction()
            self.state = CameraControlState.ARMED
            return [self._event("resize_end", target, "two hands released", False)]
        left, right = hands[0], hands[1]
        distance = _hand_distance(left, right)
        if distance < self.config.two_hand_min_distance:
            return []
        if self.state != CameraControlState.RESIZING:
            if target is None:
                return []
            self.state = CameraControlState.RESIZING
            self._resize_target = target
            self._resize_start_distance = distance
            self._resize_start_rect = target.rect
            self._resize_filtered_ratio = 1.0
            self._last_resize_rect = None
            self._last_zoom_step = 0
            self._last_zoom_s = timestamp_s
            self._resize_started_s = timestamp_s
            self._resize_max_sent = False
            self._resize_restore_sent = False
            return [self._event("two_hand_start", target, "two hands", self.actuator.execute)]

        if (
            self._resize_target is None
            or self._resize_start_distance is None
            or self._resize_start_rect is None
        ):
            self._reset_interaction()
            self.state = CameraControlState.ARMED
            return []

        events: list[ActionEvent] = []
        raw_ratio = distance / max(1e-6, self._resize_start_distance)
        if self._resize_filtered_ratio is None:
            self._resize_filtered_ratio = raw_ratio
        else:
            alpha = _clamp_float(self.config.resize_ratio_smoothing_alpha, 0.05, 1.0)
            self._resize_filtered_ratio += (raw_ratio - self._resize_filtered_ratio) * alpha
        ratio = self._resize_filtered_ratio
        events.extend(self._update_two_hand_zoom(timestamp_s, ratio))
        return events

    def _update_two_hand_zoom(self, timestamp_s: float, ratio: float) -> list[ActionEvent]:
        if self._resize_target is None:
            return []
        step_size = max(0.03, float(self.config.two_hand_zoom_step_ratio))
        step = int(math.trunc((ratio - 1.0) / step_size))
        if step == self._last_zoom_step:
            return []
        if timestamp_s - self._last_zoom_s < max(0.0, self.config.two_hand_zoom_cooldown_s):
            return []
        direction = 1 if step > self._last_zoom_step else -1
        self._last_zoom_step += direction
        self._last_zoom_s = timestamp_s
        x, y = self._resize_target.rect.center
        executed = self.actuator.zoom(self._resize_target, x, y, direction)
        name = "zoom_in" if direction > 0 else "zoom_out"
        return [self._event(name, self._resize_target, f"ratio {ratio:.2f}", executed)]

    def _update_point_click(
        self,
        timestamp_s: float,
        target: WindowTarget,
        hand: HandControlPose,
        pointer_xy: tuple[int, int] | None,
    ) -> list[ActionEvent]:
        tip = _point_tip_vector(hand)
        if tip is None:
            self._reset_point()
            return []
        if self._point_anchor is None:
            self._point_anchor = tip
            return [self._event("point_armed", target, "air tap ready", False)]
        motion_y = tip[1] - self._point_anchor[1]
        motion_z = tip[2] - self._point_anchor[2]
        tap_motion = max(motion_y, abs(motion_z) * 1.8)
        if self._point_wait_release:
            if tap_motion <= self.config.point_tap_release_norm:
                self._point_anchor = tip
                self._point_wait_release = False
                self._point_down = False
            return []
        if tap_motion < self.config.point_tap_threshold_norm:
            return []
        if timestamp_s - self._last_point_click_s < max(0.0, self.config.point_click_cooldown_s):
            return []
        x, y = pointer_xy or target.rect.center
        executed, detail = self.actuator.click_near(target, x, y, self.config.point_snap_radius_px)
        self._point_down = True
        self._point_wait_release = True
        self._last_point_click_s = timestamp_s
        return [self._event("point_click", target, f"air_tap {tap_motion:.2f} {detail}", executed)]

    def _active_target(self) -> WindowTarget | None:
        return self._drag_target or self._scroll_target or self._resize_target

    def _reset_interaction(self) -> None:
        self._drag_target = None
        self._drag_start_hand = None
        self._drag_start_rect = None
        self._last_drag_rect = None
        self._drag_filtered_pos = None
        self._reset_scroll()
        self._resize_target = None
        self._resize_start_distance = None
        self._resize_start_rect = None
        self._resize_filtered_ratio = None
        self._last_resize_rect = None
        self._last_zoom_step = 0
        self._last_zoom_s = 0.0
        self._resize_max_sent = False
        self._resize_restore_sent = False
        self._reset_point()

    def _reset_scroll(self) -> None:
        self._scroll_target = None
        self._scroll_anchor_y = None
        self._scroll_last_y = None
        self._scroll_direction = None

    def _reset_point(self) -> None:
        self._point_down = False
        self._point_anchor = None
        self._point_wait_release = False

    def _event(self, name: str, target: WindowTarget | None, detail: str, executed: bool) -> ActionEvent:
        return ActionEvent(
            name=name,
            target_title=target.title if target is not None else "",
            target_hwnd=target.hwnd if target is not None else None,
            detail=detail,
            executed=bool(executed),
        )


def _hand_distance(a: HandControlPose, b: HandControlPose) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _two_hand_control_ready(hands: tuple[HandControlPose, ...]) -> bool:
    if len(hands) < 2:
        return False
    return all(hand.label in TWO_HAND_CONTROL_LABELS for hand in hands[:2])


def _primary_action_hand(hands: tuple[HandControlPose, ...]) -> HandControlPose:
    for label in ("point", "fist"):
        for hand in hands:
            if hand.label == label:
                return hand
    return hands[0]


def _point_tip_vector(hand: HandControlPose) -> tuple[float, float, float] | None:
    """Index fingertip position relative to the palm, in normalized camera space."""

    if hand.index_tip_x is None or hand.index_tip_y is None:
        return None
    palm_x = hand.palm_x if hand.palm_x is not None else hand.x
    palm_y = hand.palm_y if hand.palm_y is not None else hand.y
    palm_z = hand.palm_z if hand.palm_z is not None else 0.0
    tip_z = hand.index_tip_z if hand.index_tip_z is not None else 0.0
    return (
        float(hand.index_tip_x) - float(palm_x),
        float(hand.index_tip_y) - float(palm_y),
        float(tip_z) - float(palm_z),
    )


def _snap_window_rect(
    left: int,
    top: int,
    width: int,
    height: int,
    monitors: tuple[MonitorRect, ...],
    *,
    edge_px: int,
) -> tuple[int, int, int, int, str]:
    if not monitors:
        return (left, top, width, height, "")
    monitor = _monitor_for_window_center(left, top, width, height, monitors)
    edge = max(12, int(edge_px))
    right = left + width
    # Top snap has priority only when not also clearly at a side. This avoids
    # accidental maximize while moving across upper-left or upper-right corners.
    near_left = left <= monitor.left + edge
    near_right = right >= monitor.right - edge
    near_top = top <= monitor.top + edge
    if near_top and not (near_left or near_right):
        return (monitor.left, monitor.top, monitor.width, monitor.height, "snap top ")
    if near_left:
        return (monitor.left, monitor.top, max(80, monitor.width // 2), monitor.height, "snap left ")
    if near_right:
        half = max(80, monitor.width // 2)
        return (monitor.right - half, monitor.top, half, monitor.height, "snap right ")
    return (left, top, width, height, "")


def _monitor_for_window_center(
    left: int,
    top: int,
    width: int,
    height: int,
    monitors: tuple[MonitorRect, ...],
) -> MonitorRect:
    cx = left + width / 2.0
    cy = top + height / 2.0
    containing = [
        monitor
        for monitor in monitors
        if monitor.left <= cx < monitor.right and monitor.top <= cy < monitor.bottom
    ]
    if containing:
        return containing[0]
    return min(
        monitors,
        key=lambda monitor: (monitor.center[0] - cx) ** 2 + (monitor.center[1] - cy) ** 2,
    )


def _clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _make_long(low: int, high: int) -> int:
    return (int(low) & 0xFFFF) | ((int(high) & 0xFFFF) << 16)
