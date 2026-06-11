"""Deterministic gesture-to-window control state machines."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from enum import Enum

def play_sound(filename: str):
    try:
        import winsound
        import os
        sound_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'sounds', filename)
        if os.path.exists(sound_path):
            winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass

from .monitors import MonitorRect
from .window_target import WindowRect, WindowTarget


class CameraControlState(str, Enum):
    IDLE = "IDLE"
    ARMED = "ARMED"
    DRAGGING = "DRAGGING"
    SCROLLING = "SCROLLING"
    RESIZING = "RESIZING"
    COOLDOWN = "COOLDOWN"


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
    pinch_distance: float | None = None


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
    camera_width: int = 1280
    camera_height: int = 720
    drag_gain_x_px: float = 2600.0
    drag_gain_y_px: float = 1500.0
    drag_min_px: int = 8
    drag_smoothing_alpha: float = 0.45
    drag_max_step_px: int = 180
    swipe_threshold_norm: float = 0.035
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
    point_tap_threshold_norm: float = 0.075
    point_tap_release_norm: float = 0.045
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

    def move_to_next_monitor(self, target: WindowTarget, direction: str) -> bool:
        if not self.execute or target is None:
            return False
        try:
            import win32gui
            import win32con

            # Make sure we're moving the top-level application window, not a child UI element
            root_hwnd = win32gui.GetAncestor(target.hwnd, win32con.GA_ROOT)
            is_zoomed = win32gui.GetWindowPlacement(root_hwnd)[1] == win32con.SW_SHOWMAXIMIZED
            
            if is_zoomed:
                win32gui.ShowWindow(root_hwnd, win32con.SW_RESTORE)
                
            # Get dimensions AFTER restoring so we don't incorrectly apply maximized bounds
            # to a restored window (which breaks Windows' maximization tracking)
            l, t, r, b = win32gui.GetWindowRect(root_hwnd)
            w = r - l
            h = b - t
            
            current_monitor = _monitor_for_window_center(l, t, w, h, self.monitors)
            cx = current_monitor.left + (current_monitor.right - current_monitor.left) / 2
            cy = current_monitor.top + (current_monitor.bottom - current_monitor.top) / 2
            
            candidates = []
            for m in self.monitors:
                if m == current_monitor:
                    continue
                mcx = m.left + (m.right - m.left) / 2
                mcy = m.top + (m.bottom - m.top) / 2
                
                if direction == "left" and mcx < cx:
                    candidates.append(m)
                elif direction == "right" and mcx > cx:
                    candidates.append(m)
                elif direction == "up" and mcy < cy:
                    candidates.append(m)
                elif direction == "down" and mcy > cy:
                    candidates.append(m)
            
            if not candidates:
                if len(self.monitors) <= 1:
                    if is_zoomed:
                        win32gui.ShowWindow(root_hwnd, win32con.SW_SHOWMAXIMIZED)
                    return False
                # Wrap-around logic
                def monitor_cx(m): return m.left + (m.right - m.left) / 2
                def monitor_cy(m): return m.top + (m.bottom - m.top) / 2
                
                if direction == "left":
                    next_monitor = max(self.monitors, key=monitor_cx)
                elif direction == "right":
                    next_monitor = min(self.monitors, key=monitor_cx)
                elif direction == "up":
                    next_monitor = max(self.monitors, key=monitor_cy)
                elif direction == "down":
                    next_monitor = min(self.monitors, key=monitor_cy)
                else:
                    if is_zoomed:
                        win32gui.ShowWindow(root_hwnd, win32con.SW_SHOWMAXIMIZED)
                    return False
                
                if next_monitor == current_monitor:
                    if is_zoomed:
                        win32gui.ShowWindow(root_hwnd, win32con.SW_SHOWMAXIMIZED)
                    return False
            else:
                # Pick the best candidate using directional weighting
                def dist(m):
                    mcx = m.left + (m.right - m.left) / 2
                    mcy = m.top + (m.bottom - m.top) / 2
                    dx = abs(mcx - cx)
                    dy = abs(mcy - cy)
                    if direction in ("left", "right"):
                        return dx + dy * 10
                    else:
                        return dy + dx * 10
                    
                next_monitor = min(candidates, key=dist)
            
            rel_x = l - current_monitor.left
            rel_y = t - current_monitor.top
            
            # If the window was maximized, we want to center its restored size on the new monitor
            # instead of applying the relative position (since restored pos might be off-screen)
            if is_zoomed:
                new_left = next_monitor.left + int((next_monitor.right - next_monitor.left - w) / 2)
                new_top = next_monitor.top + int((next_monitor.bottom - next_monitor.top - h) / 2)
            else:
                new_left = next_monitor.left + rel_x
                new_top = next_monitor.top + rel_y
            
            flags = win32con.SWP_SHOWWINDOW
            win32gui.SetWindowPos(root_hwnd, win32con.HWND_TOP, new_left, new_top, w, h, flags)
            
            if is_zoomed:
                win32gui.ShowWindow(root_hwnd, win32con.SW_SHOWMAXIMIZED)
            
            # Force window to foreground reliably using AttachThreadInput
            try:
                import win32process
                foreground_hwnd = win32gui.GetForegroundWindow()
                if foreground_hwnd and foreground_hwnd != root_hwnd:
                    foreground_thread, _ = win32process.GetWindowThreadProcessId(foreground_hwnd)
                    target_thread, _ = win32process.GetWindowThreadProcessId(root_hwnd)
                    if foreground_thread != target_thread:
                        win32process.AttachThreadInput(foreground_thread, target_thread, True)
                        win32gui.SetForegroundWindow(root_hwnd)
                        win32gui.BringWindowToTop(root_hwnd)
                        win32process.AttachThreadInput(foreground_thread, target_thread, False)
                    else:
                        win32gui.SetForegroundWindow(root_hwnd)
                        win32gui.BringWindowToTop(root_hwnd)
                else:
                    win32gui.SetForegroundWindow(root_hwnd)
                    win32gui.BringWindowToTop(root_hwnd)
            except Exception as fe:
                print(f"[ACTUATOR] foreground exception: {fe}")
                
            return True
        except Exception as e:
            print(f"[ACTUATOR] move_to_next_monitor exception: {e}")
            return False

    def move_resize(self, target: WindowTarget, left: int, top: int, width: int, height: int) -> bool:
        left, top, width, height = self._bounded_geometry(left, top, width, height)
        if not self.execute:
            return False
        try:
            import win32con
            import win32gui

            win32gui.ShowWindow(target.hwnd, win32con.SW_RESTORE)
            flags = win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
            win32gui.SetWindowPos(target.hwnd, 0, left, top, width, height, flags)
            return True
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


class BaseGestureHandler:
    """Interface for modular gestures."""
    def __init__(self, config: WindowControlConfig, actuator: WindowActuator) -> None:
        self.config = config
        self.actuator = actuator

    def check_activation(self, target: WindowTarget | None, hands: tuple[HandControlPose, ...], timestamp_s: float) -> bool:
        """Returns True if the gesture condition is met and it should take over."""
        return False

    def process(self, target: WindowTarget | None, hands: tuple[HandControlPose, ...], timestamp_s: float) -> tuple[CameraControlState, float, list[ActionEvent]]:
        """Returns (new_state, cooldown_end_s, events).
        Return CameraControlState.ARMED or IDLE to relinquish control.
        cooldown_end_s specifies if the system should enter COOLDOWN after this gesture.
        """
        return CameraControlState.IDLE, 0.0, []

    def on_deactivate(self, target: WindowTarget | None) -> list[ActionEvent]:
        """Cleanup logic when gesture is interrupted or finished."""
        return []

    def _event(self, name: str, target: WindowTarget | None, detail: str, executed: bool) -> ActionEvent:
        return ActionEvent(name, target.title if target else "", target.hwnd if target else 0, detail, executed)


class HybridSwipeGesture(BaseGestureHandler):
    """Fist 2.0: Swipe-to-Monitor Launcher with Dynamic Anchor and short-window velocity."""
    
    def __init__(self, config: WindowControlConfig, actuator: WindowActuator) -> None:
        super().__init__(config, actuator)
        self._drag_target: WindowTarget | None = None
        self._anchor_hand_x: float | None = None
        self._anchor_hand_y: float | None = None
        self._drag_start_time: float | None = None
        self._hand_history: deque[tuple[float, float, float]] = deque(maxlen=3)
        self._fist_start_time: float | None = None
        self._fist_lost_time: float | None = None

    def check_activation(self, target: WindowTarget | None, hands: tuple[HandControlPose, ...], timestamp_s: float) -> bool:
        primary = hands[0]
        if primary.label == "fist":
            if self._fist_start_time is None:
                self._fist_start_time = timestamp_s
            
            if timestamp_s - self._fist_start_time >= 0.15:
                if target is not None:
                    print(f"[CONTROLLER] ARMED -> DRAGGING (fist detected on target: {target.title[:20]})")
                    self._start_swipe(target, primary, timestamp_s)
                    return True
                else:
                    print("[CONTROLLER] ARMED -> ignoring fist (NO TARGET SELECTED)")
        else:
            self._fist_start_time = None
        return False

    def process(self, target: WindowTarget | None, hands: tuple[HandControlPose, ...], timestamp_s: float) -> tuple[CameraControlState, float, list[ActionEvent]]:
        primary = hands[0]
        events = []
        self._hand_history.append((timestamp_s, primary.x, primary.y))
        
        if primary.label == "fist":
            self._fist_lost_time = None
            state, cooldown, evts = self._update_swipe(primary, timestamp_s)
            events.extend(evts)
            return state, cooldown, events
        else:
            if self._fist_lost_time is None:
                self._fist_lost_time = timestamp_s
            
            if timestamp_s - self._fist_lost_time < 0.25:
                # Grace period for label drop (motion blur)
                state, cooldown, evts = self._update_swipe(primary, timestamp_s)
                events.extend(evts)
                return state, cooldown, events
                
            print(f"[CONTROLLER] DRAGGING -> ARMED (fist released, label is {primary.label})", flush=True)
            events.append(self._event("drop_window", self._drag_target, "fist released", False))
            return CameraControlState.ARMED, 0.0, events

    def on_deactivate(self, target: WindowTarget | None) -> list[ActionEvent]:
        self._fist_start_time = None
        self._fist_lost_time = None
        self._hand_history.clear()
        events = []
        if self._drag_target is not None:
            events.append(self._event("drop_window", self._drag_target, "gesture interrupted", False))
            self._drag_target = None
        return events

    def _start_swipe(self, target: WindowTarget, hand: HandControlPose, timestamp_s: float) -> None:
        self._drag_target = target
        self._anchor_hand_x = hand.x
        self._anchor_hand_y = hand.y
        self._drag_start_time = timestamp_s
        self._fist_lost_time = None
        self._hand_history.clear()
        self._hand_history.append((timestamp_s, hand.x, hand.y))
        print(f"[CONTROLLER] swipe start anchor X: {self._anchor_hand_x:.3f}, Y: {self._anchor_hand_y:.3f}", flush=True)
        
        try:
            import winsound
            import os
            sound_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'sounds', '47_Toque_en_madera.wav')
            if os.path.exists(sound_path):
                winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as exc:
            # feedback de audio es best-effort, pero el fallo se LOGUEA
            # (techo de silent-except: no tragar sin rastro).
            print(f"[CONTROLLER] swipe sound failed: {type(exc).__name__}", flush=True)

    def _update_swipe(self, hand: HandControlPose, timestamp_s: float) -> tuple[CameraControlState, float, list[ActionEvent]]:
        if self._anchor_hand_x is None or self._anchor_hand_y is None or self._drag_start_time is None:
            return CameraControlState.DRAGGING, 0.0, []
            
        if len(self._hand_history) < 2:
            return CameraControlState.DRAGGING, 0.0, []
            
        oldest_t, oldest_x, oldest_y = self._hand_history[0]
        dt_history = timestamp_s - oldest_t
        if dt_history <= 0:
            return CameraControlState.DRAGGING, 0.0, []
            
        aspect_ratio = float(self.config.camera_width) / float(max(1, self.config.camera_height))
        dx_total_phys = (hand.x - self._anchor_hand_x) * aspect_ratio
        dy_total_phys = hand.y - self._anchor_hand_y

        dx_hist_phys = (hand.x - oldest_x) * aspect_ratio
        dy_hist_phys = hand.y - oldest_y
        
        vx_current = dx_hist_phys / dt_history
        vy_current = dy_hist_phys / dt_history
        
        velocity_threshold = 0.45
        min_distance = 0.05

        if abs(dx_total_phys) > min_distance or abs(dy_total_phys) > min_distance:
            print(f"[CONTROLLER] flicking... dx_tot: {dx_total_phys:.3f}, vx_cur: {vx_current:.3f}, vy_cur: {vy_current:.3f}", flush=True)

            def play_feedback_local(success: bool):
                if success:
                    play_sound('3_success_arpeggio.wav')
                else:
                    play_sound('45_Thump_rapido.wav')

            if abs(vx_current) > abs(vy_current):
                if vx_current > velocity_threshold:
                    print(f"[CONTROLLER] SWIPE RIGHT TRIGGERED! vx={vx_current:.3f}", flush=True)
                    executed = self.actuator.move_to_next_monitor(self._drag_target, "right")
                    play_feedback_local(executed)
                    return CameraControlState.COOLDOWN, timestamp_s + 1.5, [self._event("swipe_window", self._drag_target, "swiped right", executed)]
                elif vx_current < -velocity_threshold:
                    print(f"[CONTROLLER] SWIPE LEFT TRIGGERED! vx={vx_current:.3f}")
                    executed = self.actuator.move_to_next_monitor(self._drag_target, "left")
                    play_feedback_local(executed)
                    return CameraControlState.COOLDOWN, timestamp_s + 1.5, [self._event("swipe_window", self._drag_target, "swiped left", executed)]
            else:
                if vy_current > velocity_threshold:
                    print(f"[CONTROLLER] SWIPE DOWN TRIGGERED! vy={vy_current:.3f}")
                    executed = self.actuator.move_to_next_monitor(self._drag_target, "down")
                    play_feedback_local(executed)
                    return CameraControlState.COOLDOWN, timestamp_s + 1.5, [self._event("swipe_window", self._drag_target, "swiped down", executed)]
                elif vy_current < -velocity_threshold:
                    print(f"[CONTROLLER] SWIPE UP TRIGGERED! vy={vy_current:.3f}")
                    executed = self.actuator.move_to_next_monitor(self._drag_target, "up")
                    play_feedback_local(executed)
                    return CameraControlState.COOLDOWN, timestamp_s + 1.5, [self._event("swipe_window", self._drag_target, "swiped up", executed)]

        return CameraControlState.DRAGGING, 0.0, []


class PinchScrollGesture(BaseGestureHandler):
    """Pinch and drag up/down to scroll."""
    def __init__(self, config: WindowControlConfig, actuator: WindowActuator) -> None:
        super().__init__(config, actuator)
        self._scroll_target: WindowTarget | None = None
        self._scroll_anchor_y: float | None = None
        self._scroll_last_y: float | None = None
        self._pinch_lost_time: float | None = None

    def check_activation(self, target: WindowTarget | None, hands: tuple[HandControlPose, ...], timestamp_s: float) -> bool:
        primary = hands[0]
        if primary.label == "pinch":
            # ONLY activate scroll if fingers are actually touching (distance < 20% of palm size)
            if primary.pinch_distance is not None and primary.pinch_distance > 0.20:
                return False
                
            self._scroll_target = target
            self._scroll_anchor_y = primary.y
            self._scroll_last_y = primary.y
            self._pinch_lost_time = None
            print(f"[CONTROLLER] Pinch detected, starting scroll on {target.title[:20] if target else 'None'}", flush=True)
            play_sound('8_scifi_chirp.wav')
            return True
        return False

    def process(self, target: WindowTarget | None, hands: tuple[HandControlPose, ...], timestamp_s: float) -> tuple[CameraControlState, float, list[ActionEvent]]:
        primary = hands[0]
        
        # Determine if the pinch is still held tightly enough to scroll
        is_holding_pinch = False
        if primary.label == "pinch":
            if primary.pinch_distance is not None:
                is_holding_pinch = primary.pinch_distance <= 0.35  # Allows some looseness while dragging
            else:
                is_holding_pinch = True
                
        if is_holding_pinch:
            self._pinch_lost_time = None
        else:
            if self._pinch_lost_time is None:
                self._pinch_lost_time = timestamp_s
            
            if timestamp_s - self._pinch_lost_time < 0.3:
                # Grace period for motion blur
                pass
            else:
                return CameraControlState.ARMED, 0.0, []

        if self._scroll_anchor_y is None or self._scroll_last_y is None:
            return CameraControlState.ARMED, 0.0, []

        dy = primary.y - self._scroll_last_y
        events = []
        if abs(dy) > self.config.scroll_threshold_norm:
            wheel_delta = int(round(dy * self.config.scroll_gain))
            min_delta = max(1, int(self.config.scroll_min_wheel_delta))
            max_delta = max(min_delta, int(self.config.scroll_max_wheel_delta))
            
            if abs(wheel_delta) < min_delta:
                wheel_delta = min_delta if wheel_delta > 0 else -min_delta
            wheel_delta = max(-max_delta, min(max_delta, wheel_delta))
            
            x, y = target.rect.center if target else (0, 0)
            executed = self.actuator.scroll(self._scroll_target, x, y, wheel_delta)
            self._scroll_last_y = primary.y
            events.append(self._event("scroll_window", self._scroll_target, f"wheel {wheel_delta}", executed))

        return CameraControlState.DRAGGING, 0.0, events

    def on_deactivate(self, target: WindowTarget | None) -> list[ActionEvent]:
        self._scroll_target = None
        self._scroll_anchor_y = None
        self._scroll_last_y = None
        self._pinch_lost_time = None
        return []


class PointClickGesture(BaseGestureHandler):
    """Point and air-tap to click."""
    def __init__(self, config: WindowControlConfig, actuator: WindowActuator) -> None:
        super().__init__(config, actuator)
        self._point_anchor: tuple[float, float, float] | None = None
        self._point_wait_release: bool = False
        self._last_point_click_s: float = 0.0
        self._point_lost_time: float | None = None

    def check_activation(self, target: WindowTarget | None, hands: tuple[HandControlPose, ...], timestamp_s: float) -> bool:
        if hands[0].label == "point":
            self._point_lost_time = None
            return True
        return False

    def process(self, target: WindowTarget | None, hands: tuple[HandControlPose, ...], timestamp_s: float) -> tuple[CameraControlState, float, list[ActionEvent]]:
        primary = hands[0]
        if primary.label == "point":
            self._point_lost_time = None
        else:
            if self._point_lost_time is None:
                self._point_lost_time = timestamp_s
            
            if timestamp_s - self._point_lost_time < 0.3:
                pass
            else:
                return CameraControlState.ARMED, 0.0, []
            
        tip = (primary.index_tip_x, primary.index_tip_y, primary.index_tip_z) if primary.index_tip_x is not None else None
        if tip is None:
            return CameraControlState.DRAGGING, 0.0, []

        if self._point_anchor is None:
            self._point_anchor = tip
            return CameraControlState.DRAGGING, 0.0, [self._event("point_armed", target, "air tap ready", False)]

        motion_y = tip[1] - self._point_anchor[1]
        motion_z = tip[2] - self._point_anchor[2]
        tap_motion = max(motion_y, abs(motion_z) * 1.8)

        if self._point_wait_release:
            if tap_motion <= self.config.point_tap_release_norm:
                self._point_anchor = tip
                self._point_wait_release = False
            return CameraControlState.DRAGGING, 0.0, []

        # Lower tap threshold to 0.08 for better sensitivity
        if tap_motion < 0.08:
            return CameraControlState.DRAGGING, 0.0, []

        if timestamp_s - self._last_point_click_s < max(0.0, self.config.point_click_cooldown_s):
            return CameraControlState.DRAGGING, 0.0, []

        x, y = target.rect.center if target else (0, 0)
        executed, detail = False, "No target"
        if target:
            executed, detail = self.actuator.click_near(target, x, y, self.config.point_snap_radius_px)
            
        self._point_wait_release = True
        self._last_point_click_s = timestamp_s
        print(f"[CONTROLLER] CLICK TRIGGERED! tap_motion={tap_motion:.2f}", flush=True)
        if executed:
            play_sound('1_pop.wav')
        else:
            play_sound('9_Tap_seco.wav')
        # Add a 1.5s cooldown so the user has time to lower their hand or move without triggering another click
        return CameraControlState.DRAGGING, timestamp_s + 1.5, [self._event("point_click", target, f"air_tap {tap_motion:.2f} {detail}", executed)]

    def on_deactivate(self, target: WindowTarget | None) -> list[ActionEvent]:
        self._point_anchor = None
        self._point_wait_release = False
        self._point_lost_time = None
        return []


class PalmMediaGesture(BaseGestureHandler):
    """Open palm to Pause/Play media."""
    def __init__(self, config: WindowControlConfig, actuator: WindowActuator) -> None:
        super().__init__(config, actuator)
        self._palm_start_time: float | None = None
        self._palm_wait_release = False

    def check_activation(self, target: WindowTarget | None, hands: tuple[HandControlPose, ...], timestamp_s: float) -> bool:
        if len(hands) > 1:
            self._palm_start_time = None
            self._palm_wait_release = False
            return False

        if getattr(self, "_palm_last_checked_time", 0.0) and timestamp_s - self._palm_last_checked_time > 0.2:
            self._palm_start_time = None
            self._palm_wait_release = False

        self._palm_last_checked_time = timestamp_s

        primary = hands[0]
        if primary.label == "palm":
            if self._palm_start_time is None:
                self._palm_start_time = timestamp_s
            
            if not self._palm_wait_release and timestamp_s - self._palm_start_time > 0.55:
                return True
            if self._palm_wait_release:
                return True
        else:
            self._palm_start_time = None
            self._palm_wait_release = False
        return False

    def process(self, target: WindowTarget | None, hands: tuple[HandControlPose, ...], timestamp_s: float) -> tuple[CameraControlState, float, list[ActionEvent]]:
        if self._palm_wait_release:
            # Already triggered, just wait for the user to close their hand
            return CameraControlState.DRAGGING, 0.0, []

        self._palm_wait_release = True
        print("[CONTROLLER] PALM detected -> Toggling Media Play/Pause", flush=True)
        play_sound('2_double_blip.wav')
        # honestidad del evento: si el keypress falla, executed=False (antes el
        # except silencioso dejaba el evento mintiendo "toggled media" True).
        _toggled = False
        try:
            import win32api
            import win32con
            if self.actuator.execute:
                win32api.keybd_event(0xB3, 0, win32con.KEYEVENTF_EXTENDEDKEY, 0)
                win32api.keybd_event(0xB3, 0, win32con.KEYEVENTF_EXTENDEDKEY | win32con.KEYEVENTF_KEYUP, 0)
                _toggled = True
        except Exception as exc:
            print(f"[CONTROLLER] media toggle FAILED: {type(exc).__name__}: {exc}",
                  flush=True)
        return CameraControlState.DRAGGING, timestamp_s + 1.0, [
            self._event("media_toggle", None,
                        "toggled media" if _toggled else "media toggle failed",
                        _toggled)]

    def on_deactivate(self, target: WindowTarget | None) -> list[ActionEvent]:
        self._palm_start_time = None
        self._palm_wait_release = False
        return []


class TwoHandResizeGesture(BaseGestureHandler):
    """Pinch with two hands to zoom/resize."""
    def __init__(self, config: WindowControlConfig, actuator: WindowActuator) -> None:
        super().__init__(config, actuator)
        self._resize_target: WindowTarget | None = None
        self._resize_start_distance: float | None = None
        self._resize_filtered_ratio: float | None = None
        self._last_zoom_step: int = 0
        self._last_zoom_s: float = 0.0
        self._twohand_lost_time: float | None = None

    def check_activation(self, target: WindowTarget | None, hands: tuple[HandControlPose, ...], timestamp_s: float) -> bool:
        if len(hands) >= 2 and hands[0].label == "pinch" and hands[1].label == "pinch":
            self._resize_target = target
            self._resize_start_distance = _hand_distance(hands[0], hands[1])
            self._resize_filtered_ratio = 1.0
            self._last_zoom_step = 0
            self._last_zoom_s = timestamp_s
            self._twohand_lost_time = None
            print(f"[CONTROLLER] TwoHand Pinch detected -> Zooming {target.title[:20] if target else 'None'}", flush=True)
            play_sound('5_soft_bell.wav')
            return True
        return False

    def process(self, target: WindowTarget | None, hands: tuple[HandControlPose, ...], timestamp_s: float) -> tuple[CameraControlState, float, list[ActionEvent]]:
        if len(hands) >= 2 and hands[0].label == "pinch" and hands[1].label == "pinch":
            self._twohand_lost_time = None
        else:
            if self._twohand_lost_time is None:
                self._twohand_lost_time = timestamp_s
            if timestamp_s - self._twohand_lost_time < 0.4:
                pass # Grace period for losing one hand
            else:
                return CameraControlState.ARMED, 0.0, []
            
        if self._resize_target is None or self._resize_start_distance is None or len(hands) < 2:
            return CameraControlState.ARMED, 0.0, []

        distance = _hand_distance(hands[0], hands[1])
        raw_ratio = distance / max(1e-6, self._resize_start_distance)
        
        if self._resize_filtered_ratio is None:
            self._resize_filtered_ratio = raw_ratio
        else:
            alpha = _clamp_float(self.config.resize_ratio_smoothing_alpha, 0.05, 1.0)
            self._resize_filtered_ratio += (raw_ratio - self._resize_filtered_ratio) * alpha
            
        ratio = self._resize_filtered_ratio
        
        step_size = max(0.03, float(self.config.two_hand_zoom_step_ratio))
        step = int(math.trunc((ratio - 1.0) / step_size))
        
        events = []
        if step != self._last_zoom_step and timestamp_s - self._last_zoom_s >= max(0.0, self.config.two_hand_zoom_cooldown_s):
            direction = 1 if step > self._last_zoom_step else -1
            self._last_zoom_step += direction
            self._last_zoom_s = timestamp_s
            x, y = self._resize_target.rect.center if self._resize_target else (0,0)
            executed = self.actuator.zoom(self._resize_target, x, y, direction)
            name = "zoom_in" if direction > 0 else "zoom_out"
            events.append(self._event(name, self._resize_target, f"ratio {ratio:.2f}", executed))

        return CameraControlState.DRAGGING, 0.0, events

    def on_deactivate(self, target: WindowTarget | None) -> list[ActionEvent]:
        self._resize_target = None
        self._resize_start_distance = None
        self._resize_filtered_ratio = None
        self._twohand_lost_time = None
        return []


class FixedGestureWindowController:
    """Gesture Router that delegates to active strategies."""

    def __init__(self, config: WindowControlConfig, actuator: WindowActuator) -> None:
        self.config = config
        self.actuator = actuator
        self.state = CameraControlState.IDLE
        self._cooldown_end_s: float = 0.0
        self._hand_lost_time: float | None = None
        
        # Register available gestures here (Priority Order)
        self._handlers: list[BaseGestureHandler] = [
            PalmMediaGesture(config, actuator),
            TwoHandResizeGesture(config, actuator),
            HybridSwipeGesture(config, actuator),
            PinchScrollGesture(config, actuator),
            PointClickGesture(config, actuator),
        ]
        self._active_handler: BaseGestureHandler | None = None

    def update(
        self,
        timestamp_s: float,
        target: WindowTarget | None,
        hands: tuple[HandControlPose, ...],
        pointer_xy: tuple[float, float],
        face: Any | None = None,
    ) -> WindowControlOutput:
        events: list[ActionEvent] = []

        if timestamp_s < self._cooldown_end_s:
            if not hands:
                self.state = CameraControlState.IDLE
            else:
                self.state = CameraControlState.COOLDOWN
            return WindowControlOutput(self.state, tuple(events), target)

        if not hands:
            if self.state != CameraControlState.IDLE:
                if self._hand_lost_time is None:
                    self._hand_lost_time = timestamp_s
                
                # Allow 0.2s of tracking loss before aborting
                if timestamp_s - self._hand_lost_time > 0.2:
                    if self._active_handler:
                        events.extend(self._active_handler.on_deactivate(target))
                        self._active_handler = None
                    self.state = CameraControlState.IDLE
                    print("[CONTROLLER] state -> IDLE (hand lost)", flush=True)
            return WindowControlOutput(self.state, tuple(events), target)

        self._hand_lost_time = None
        primary = hands[0]

        if self.state == CameraControlState.IDLE:
            print(f"[CONTROLLER] IDLE -> ARMED (hand detected: {primary.label})")
            self.state = CameraControlState.ARMED

        if self.state == CameraControlState.COOLDOWN:
            if primary.label != "fist" and timestamp_s >= self._cooldown_end_s:
                print(f"[CONTROLLER] COOLDOWN -> ARMED (hand opened, label is {primary.label})")
                self.state = CameraControlState.ARMED
            return WindowControlOutput(self.state, tuple(events), target)

        # Let the active handler process the frame
        if self._active_handler is not None:
            new_state, cooldown, handler_events = self._active_handler.process(target, hands, timestamp_s)
            events.extend(handler_events)
            self.state = new_state
            if cooldown > 0:
                self._cooldown_end_s = cooldown
            
            if self.state in (CameraControlState.IDLE, CameraControlState.ARMED, CameraControlState.COOLDOWN):
                self._active_handler.on_deactivate(target)
                self._active_handler = None
                
            return WindowControlOutput(self.state, tuple(events), target)

        # If no active handler, see if any gesture wants to start (in priority order)
        if self.state == CameraControlState.ARMED:
            for handler in self._handlers:
                if handler.check_activation(target, hands, timestamp_s):
                    self._active_handler = handler
                    self.state = CameraControlState.DRAGGING # Base state when a gesture is active
                    break

        return WindowControlOutput(self.state, tuple(events), target)



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

