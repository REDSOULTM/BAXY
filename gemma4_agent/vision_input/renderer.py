"""Renderer for Vision Input System.

Provides the UI rendering and overlay functions for camera control.
"""
from __future__ import annotations

import math
from typing import Any

from .poc import _draw_face, _draw_hands
from .pointer import HeadPointerEstimate
from .window_target import WindowTarget, short_title
from .monitors import VirtualCanvas
from .controller import HandControlPose

try:
    import tkinter as tk
except Exception:  # pragma: no cover
    tk = None


class DesktopGazeDot:
    """Small topmost dot window that follows gaze on desktop."""

    def __init__(self, size: int = 44) -> None:
        if tk is None:
            raise RuntimeError("tkinter unavailable")
        self.size = max(24, int(size))
        self._root = tk.Tk()
        self._color_key = "#00ff00"
        self._root.overrideredirect(True)
        self._root.wm_attributes("-topmost", True)
        self._root.configure(bg=self._color_key)
        try:
            self._root.wm_attributes("-transparentcolor", self._color_key)
        except Exception:
            pass
        self._canvas = tk.Canvas(
            self._root,
            width=self.size,
            height=self.size,
            bg=self._color_key,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack()
        c = self.size // 2
        r = max(8, self.size // 3)
        self._canvas.create_oval(c - r, c - r, c + r, c + r, outline="#ffe252", width=2)
        self._canvas.create_line(c - r - 4, c, c + r + 4, c, fill="#ffe252", width=1)
        self._canvas.create_line(c, c - r - 4, c, c + r + 4, fill="#ffe252", width=1)
        self._root.geometry(f"{self.size}x{self.size}+0+0")
        self._root.update_idletasks()
        self._root.update()

    def move_to(self, x: float, y: float) -> None:
        px = int(round(x)) - self.size // 2
        py = int(round(y)) - self.size // 2
        self._root.geometry(f"{self.size}x{self.size}+{px}+{py}")
        self._root.update_idletasks()
        self._root.update()

    def close(self) -> None:
        try:
            self._root.destroy()
        except Exception:
            pass


def frame_point_from_head(frame: Any, head: HeadPointerEstimate | None) -> tuple[int, int] | None:
    if head is None:
        return None
    h, w = frame.shape[:2]
    x = int(round(max(0.0, min(1.0, head.local_x)) * (w - 1)))
    y = int(round(max(0.0, min(1.0, head.local_y)) * (h - 1)))
    return (x, y)


def hand_debug_text(idx: int, hand: HandControlPose) -> str:
    raw = hand.raw_label or hand.label
    conf = "" if hand.gesture_confidence is None else f"{hand.gesture_confidence:.2f}"
    track = f"{hand.track_id}:" if hand.track_id else ""
    quality = "" if hand.quality_ok else f"!{hand.quality_reason}"
    if raw == hand.label:
        return f"h{idx}:{track}{hand.label}{conf}{quality}@{hand.x:.2f},{hand.y:.2f}"
    return f"h{idx}:{track}{raw}->{hand.label}{conf}{quality}@{hand.x:.2f},{hand.y:.2f}"


def draw_hand_control_points(frame: Any, hands: tuple[HandControlPose, ...]) -> None:
    import cv2

    h, w = frame.shape[:2]
    pts = [(int(hand.x * w), int(hand.y * h)) for hand in hands]
    for idx, (hand, pt) in enumerate(zip(hands, pts)):
        cv2.circle(frame, pt, 8, (60, 255, 60), 2)
        cv2.putText(frame, str(idx), (pt[0] + 8, pt[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 255, 60), 1)
        if hand.label == "point" and hand.index_tip_x is not None and hand.index_tip_y is not None:
            tip = (int(hand.index_tip_x * w), int(hand.index_tip_y * h))
            cv2.circle(frame, tip, 6, (0, 230, 255), 2)
            cv2.line(frame, pt, tip, (0, 230, 255), 1)
        # --- Pinch distance indicator ---
        if hand.pinch_distance is not None and hand.index_tip_x is not None and hand.index_tip_y is not None:
            pd = hand.pinch_distance
            # Green = close enough to scroll (<0.20), Yellow = approaching (<0.35), Dim = too far
            if pd <= 0.20:
                color = (0, 255, 100)
            elif pd <= 0.35:
                color = (0, 220, 255)
            else:
                color = (80, 80, 80)
            tip_pt = (int(hand.index_tip_x * w), int(hand.index_tip_y * h))
            # Draw small distance label near the hand
            dist_text = f"d:{pd:.2f}"
            cv2.putText(frame, dist_text, (pt[0] - 20, pt[1] + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
        # --- Face exclusion feedback ---
        if hand.raw_label != "none" and hand.label == "none" and hand.quality_ok:
            # The raw gesture was overridden to none (likely by face exclusion zone)
            cv2.putText(frame, "FACE ZONE", (pt[0] - 30, pt[1] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
    if len(pts) >= 2:
        cv2.line(frame, pts[0], pts[1], (60, 255, 60), 2)


def draw_gaze_pointer(frame: Any, head: HeadPointerEstimate | None) -> None:
    import cv2

    pt = frame_point_from_head(frame, head)
    if pt is None:
        return
    color = (80, 235, 255) if head is not None and head.source.endswith("head+iris") else (120, 200, 255)
    x, y = pt
    cv2.circle(frame, (x, y), 12, color, 2)
    cv2.circle(frame, (x, y), 3, color, -1)
    cv2.line(frame, (x - 18, y), (x + 18, y), color, 1)
    cv2.line(frame, (x, y - 18), (x, y + 18), color, 1)
    cv2.putText(frame, "gaze", (x + 14, max(24, y - 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)


def draw_desktop_map(
    frame: Any,
    canvas: VirtualCanvas,
    head: HeadPointerEstimate | None,
    desktop_point: tuple[float, float] | None,
    candidate: WindowTarget | None,
    target: WindowTarget | None,
) -> None:
    import cv2

    h, w = frame.shape[:2]
    map_w = min(340, max(220, int(w * 0.32)))
    map_h = 112
    x0 = max(0, w - map_w - 16)
    y0 = 12
    x1 = min(w - 1, x0 + map_w)
    y1 = min(h - 1, y0 + map_h)
    if x1 - x0 < 80 or y1 - y0 < 60:
        return
    cv2.rectangle(frame, (x0, y0), (x1, y1), (15, 15, 15), -1)
    cv2.rectangle(frame, (x0, y0), (x1, y1), (120, 120, 120), 1)
    cv2.putText(frame, "desktop map", (x0 + 8, y0 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (210, 210, 210), 1)
    pad_x = 8
    pad_y = 24
    inner_w = max(1, (x1 - x0) - 2 * pad_x)
    inner_h = max(1, (y1 - y0) - pad_y - 8)
    scale_x = inner_w / max(1, canvas.width)
    scale_y = inner_h / max(1, canvas.height)
    map_left = x0 + pad_x
    map_top = y0 + pad_y

    def map_point(px: float, py: float) -> tuple[int, int]:
        if not math.isfinite(px) or not math.isfinite(py):
            return (map_left, map_top)
        mx = int(round(map_left + (px - canvas.rect.left) * scale_x))
        my = int(round(map_top + (py - canvas.rect.top) * scale_y))
        return (mx, my)

    def map_rect(rect: WindowTarget | None, color: tuple[int, int, int], thickness: int) -> None:
        if rect is None:
            return
        left_top = map_point(rect.rect.left, rect.rect.top)
        right_bottom = map_point(rect.rect.right, rect.rect.bottom)
        cv2.rectangle(frame, left_top, right_bottom, color, thickness)

    for monitor in canvas.monitors:
        left_top = map_point(monitor.rect.left, monitor.rect.top)
        right_bottom = map_point(monitor.rect.right, monitor.rect.bottom)
        fill = (24, 50, 24) if monitor.primary else (34, 34, 34)
        cv2.rectangle(frame, left_top, right_bottom, fill, -1)
        cv2.rectangle(frame, left_top, right_bottom, (100, 100, 100), 1)

    map_rect(candidate, (90, 190, 255), 1)
    map_rect(target, (0, 255, 200), 2)

    if desktop_point is not None:
        pt = map_point(desktop_point[0], desktop_point[1])
        color = (0, 255, 220) if head is not None and head.source.endswith("head+iris") else (100, 220, 255)
        cv2.circle(frame, pt, 4, color, -1)
        cv2.circle(frame, pt, 7, color, 1)


def draw_overlay(
    frame: Any,
    landmarks: Any,
    head: HeadPointerEstimate | None,
    hands: tuple[HandControlPose, ...],
    candidate: WindowTarget | None,
    target: WindowTarget | None,
    state: str,
    events: tuple[dict[str, object], ...],
    camera_label: str,
    execute_actions: bool,
    actions_requested: bool,
    action_status: str,
    canvas: VirtualCanvas,
    show_gaze_pointer: bool,
    show_desktop_map: bool,
    desktop_point: tuple[float, float] | None,
    calibration_text: str,
) -> Any:
    """Render the primary HUD for the vision input system, providing <100ms feedback loop."""
    import cv2

    h, w = frame.shape[:2]
    _draw_hands(frame, landmarks)
    _draw_face(frame, landmarks)
    draw_hand_control_points(frame, hands)
    cv2.rectangle(frame, (0, 0), (w, 238), (0, 0, 0), -1)
    mode = "EXECUTE ACTIONS" if execute_actions else "EXECUTE BLOCKED" if actions_requested else "SAFE PREVIEW"
    mode_color = (0, 80, 255) if execute_actions else (0, 220, 255)
    cv2.putText(frame, f"CAMERA ACTIVE - {camera_label}", (16, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 220, 0), 2)
    cv2.putText(
        frame,
        f"MODE {mode} | .=acciones | ,/k=calibrar | p=recalibrar | q/Esc salir",
        (16, 54),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.50,
        mode_color,
        2,
    )
    head_text = "head none"
    if head is not None:
        gaze_text = ""
        if head.gaze is not None:
            gaze_text = f" gaze {head.gaze.x:+.2f},{head.gaze.y:+.2f}"
        head_text = (
            f"head {head.region} m{head.monitor.index} ({head.filtered_x:.0f},{head.filtered_y:.0f}) "
            f"src {head.source}{gaze_text}"
        )
    cv2.putText(frame, head_text, (16, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (235, 235, 235), 1)
    cv2.putText(
        frame,
        f"looking candidate: {short_title(candidate)}",
        (16, 108),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.47,
        (210, 210, 210),
        1,
    )
    cv2.putText(
        frame,
        f"armed target: {short_title(target)}",
        (16, 132),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.47,
        (210, 240, 255),
        1,
    )
    hand_text = " | ".join(hand_debug_text(idx, hand) for idx, hand in enumerate(hands)) or "no hand"
    cv2.putText(frame, f"state {state} | {hand_text}", (16, 156), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (230, 230, 230), 1)
    cv2.putText(
        frame,
        "fist=mover/snap ventana | pinch=scroll | palm=play/pausa | 2 manos=zoom | point+tap=click",
        (16, 182),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (190, 230, 190),
        1,
    )
    cv2.putText(
        frame,
        action_status,
        (16, 206),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (0, 220, 255) if not execute_actions else (120, 255, 120),
        1,
    )
    latest = events[-1] if events else None
    if latest is not None:
        cv2.putText(
            frame,
            f"last: {latest.get('name')} | {latest.get('detail')} | executed={latest.get('executed')}",
            (16, 230),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (255, 255, 255),
            1,
        )
    if show_gaze_pointer:
        draw_gaze_pointer(frame, head)
    if show_desktop_map:
        draw_desktop_map(frame, canvas, head, desktop_point, candidate, target)
    if calibration_text:
        cv2.putText(frame, calibration_text, (16, min(h - 16, 254)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (120, 240, 255), 1)
    return frame
