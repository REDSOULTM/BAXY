"""Phase 1 window-control POC.

This runner turns the Phase 0 detections into a fixed deterministic grammar:
look at a window, then use hand gestures to move it, scroll, zoom, or click. It is
safe by default; real Win32 actions require --execute-actions.
"""
from __future__ import annotations

import argparse
import getpass
import io
import json
import math
import os
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .camera import CameraConfig, OpenCVCamera
from .calibration import (
    CalibrationProfile,
    CalibrationSample,
    CalibrationStore,
    LinearGazeModel,
    default_calibration_targets,
    evaluate_calibration_model,
    fit_linear_model,
    fit_monitor_corrections,
    fit_screen_warp,
    with_monitor_corrections,
    make_feature_dict,
    profile_model,
    with_screen_warp,
)
from .controller import (
    FixedGestureWindowController,
    HandControlPose,
    WindowActuator,
    WindowControlConfig,
)
from .gaze import GazeRefinementConfig
from .gestures import recognize_hand_gesture
from .hand_quality import (
    GestureStateFilter,
    HandIdentityTracker,
    HandQualityConfig,
    HandQualityGate,
)
from .landmarks import CAMERA_DATA_DIR, HandSample, LandmarkFrame, MediaPipeLandmarkDetector
from .monitors import VirtualCanvas, canvas_to_dict, virtual_canvas
from .poc import (
    DEFAULT_CAMERA_BACKEND,
    DEFAULT_CAMERA_HEIGHT,
    DEFAULT_CAMERA_INDEX,
    DEFAULT_CAMERA_WIDTH,
    _camera_backend_value,
    _camera_label,
    _draw_face,
    _draw_hands,
    list_cameras,
)
from .pointer import HeadPointerEstimate, HeadPointerMapper, OneEuroFilter
from .window_target import WindowTarget, WindowTargetStabilizer, WindowTargeter, short_title

try:
    import win32api
except Exception:  # pragma: no cover - optional on non-Windows test envs.
    win32api = None

try:
    import tkinter as tk
except Exception:  # pragma: no cover - optional at runtime.
    tk = None


KEY_QUIT = {ord("q"), ord("Q"), 27}
# Support both ASCII and Win32 virtual-key OEM codes.
KEY_TOGGLE_EXECUTE = {ord("."), 0xBE, 0x6E}
KEY_TOGGLE_CALIBRATION = {ord(","), 0xBC, ord("k"), ord("K")}
KEY_RESTART_CALIBRATION = {ord("p"), ord("P")}
KEY_CALIBRATION_CAPTURE = {32, ord("s"), ord("S")}
KEY_CALIBRATION_SAVE = {10, 13}
KEY_CALIBRATION_NEXT = {ord("n"), ord("N")}
KEY_CALIBRATION_CLEAR = {ord("c"), ord("C")}
SUPPRESSED_RUNTIME_LOG_SNIPPETS = (
    "Created TensorFlow Lite XNNPACK delegate for CPU.",
    "WARNING: All log messages before absl::InitializeLog() is called",
    "inference_feedback_manager.cc:",
    "face_landmarker_graph.cc:",
    "landmark_projection_calculator.cc:",
    "portable_clearcut_uploader.cc:",
    "=== Source Location Trace:",
    "wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180",
)
ONLINE_FEATURE_KEYS = ("yaw", "pitch", "gaze_x", "gaze_y")


@dataclass(frozen=True)
class ValidationSample:
    target_x: float
    target_y: float
    predicted_x: float
    predicted_y: float
    error_px: float
    target_monitor: int
    predicted_monitor: int

    @property
    def monitor_hit(self) -> bool:
        return self.target_monitor == self.predicted_monitor


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


class _GlobalKeyEdgePoller:
    """Edge-triggered global key polling for reliable hotkeys."""

    def __init__(self, watch_keys: tuple[int, ...]) -> None:
        if win32api is not None:
            self._get_async_key_state = win32api.GetAsyncKeyState
        else:
            self._get_async_key_state = None
        self._watch = tuple(int(key) for key in watch_keys)
        self._down: dict[int, bool] = {key: False for key in self._watch}

    def pressed_keys(self) -> list[int]:
        if self._get_async_key_state is None:
            return []
        pressed: list[int] = []
        for key in self._watch:
            is_down = bool(self._get_async_key_state(key) & 0x8000)
            if is_down and not self._down.get(key, False):
                pressed.append(key)
            self._down[key] = is_down
        return pressed


class _GlobalMouseClickPoller:
    """Edge-triggered left-click polling with cursor position."""

    def __init__(self) -> None:
        if win32api is not None:
            self._get_async_key_state = win32api.GetAsyncKeyState
            self._get_cursor_pos = win32api.GetCursorPos
        else:
            self._get_async_key_state = None
            self._get_cursor_pos = None
        self._down = False

    def consume_left_click(self) -> tuple[int, int] | None:
        if self._get_async_key_state is None or self._get_cursor_pos is None:
            return None
        is_down = bool(self._get_async_key_state(0x01) & 0x8000)  # VK_LBUTTON
        fired = is_down and not self._down
        self._down = is_down
        if not fired:
            return None
        try:
            x, y = self._get_cursor_pos()
            return (int(x), int(y))
        except Exception:
            return None


class _StderrNoiseFilter(io.TextIOBase):
    def __init__(self, wrapped: io.TextIOBase, snippets: tuple[str, ...]) -> None:
        self._wrapped = wrapped
        self._snippets = snippets
        self._buffer = ""

    def write(self, s: str) -> int:
        self._buffer += s
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if not _is_suppressed_runtime_log_line(line):
                self._wrapped.write(line + "\n")
        return len(s)

    def flush(self) -> None:
        if self._buffer and not _is_suppressed_runtime_log_line(self._buffer):
            self._wrapped.write(self._buffer)
        self._buffer = ""
        self._wrapped.flush()


def _is_suppressed_runtime_log_line(line: str) -> bool:
    return any(snippet in line for snippet in SUPPRESSED_RUNTIME_LOG_SNIPPETS)


def _set_runtime_log_env_defaults() -> None:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    os.environ.setdefault("GLOG_minloglevel", "3")
    os.environ.setdefault("ABSL_MIN_LOG_LEVEL", "3")


def _install_runtime_log_filter(*, enabled: bool) -> None:
    if not enabled:
        return
    if isinstance(sys.stderr, _StderrNoiseFilter):
        pass
    else:
        sys.stderr = _StderrNoiseFilter(sys.stderr, SUPPRESSED_RUNTIME_LOG_SNIPPETS)
    if not isinstance(sys.stdout, _StderrNoiseFilter):
        sys.stdout = _StderrNoiseFilter(sys.stdout, SUPPRESSED_RUNTIME_LOG_SNIPPETS)


def main(argv: list[str] | None = None) -> int:
    _set_runtime_log_env_defaults()
    # Declare DPI awareness BEFORE any window/monitor work so calibration dots and
    # win32 monitor rects use the same physical pixels on mixed-scaling multi-monitor
    # setups (otherwise dots on a differently-scaled monitor land shifted / miss the corners).
    from .dpi import ensure_dpi_awareness

    ensure_dpi_awareness()
    args = _parse_args(argv)
    if args.list_cameras:
        print(json.dumps(list_cameras(args), indent=2, sort_keys=True))
        return 0
    _install_runtime_log_filter(enabled=args.quiet_runtime_logs)
    report = run_window_control(args)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def run_window_control(args: argparse.Namespace) -> dict[str, Any]:
    import cv2

    calibration_mode = bool(args.run_calibration)
    validation_mode = False
    execute_actions_live = bool(args.execute_actions)
    # User-requested: keep online auto-learning disabled for now.
    auto_online_learn_enabled = False
    canvas = virtual_canvas()
    store = CalibrationStore()
    if args.reset_calibration_history:
        try:
            store.path_for(canvas.layout_hash, args.calibration_user).unlink(missing_ok=True)
        except Exception:
            pass
    loaded_profile = store.load(canvas.layout_hash, args.calibration_user) if args.use_calibration else None
    loaded_model = profile_model(loaded_profile)
    # Warn (don't block) if running at a different resolution than the calibration
    # was captured at: landmark detail differs, so the mapping is degraded. Better
    # to surface it than to silently lose accuracy (recalibrate at this resolution).
    if loaded_profile is not None and loaded_profile.camera_resolution is not None:
        run_res = (int(args.width), int(args.height))
        if tuple(loaded_profile.camera_resolution) != run_res:
            print(
                f"[warn] calibration was captured at {loaded_profile.camera_resolution[0]}x"
                f"{loaded_profile.camera_resolution[1]} but running at {run_res[0]}x{run_res[1]} — "
                "accuracy is degraded; recalibrate at this resolution for best results.",
                flush=True,
            )
    calibration_rejected_reason = None
    if loaded_model is not None and loaded_model.rms_error_px > args.calibration_max_rms_px:
        calibration_rejected_reason = (
            f"loaded calibration RMS {loaded_model.rms_error_px:.1f}px exceeds max {args.calibration_max_rms_px:.1f}px"
        )
        loaded_model = None
    validation_summary = evaluate_calibration_model(loaded_model, loaded_profile.samples, canvas) if loaded_profile else None
    calibration_validated = (
        not args.require_validation_for_actions
        or _validation_summary_passes(validation_summary, args)
    )
    # Calibration and calibrated inference should use stable raw head/iris features.
    auto_center_effective = (not args.no_auto_center) and (not calibration_mode) and (loaded_model is None)
    mapper = HeadPointerMapper(
        canvas,
        GazeRefinementConfig(
            enabled=args.iris_refine,
            gain_x=args.gaze_gain_x,
            gain_y=args.gaze_gain_y,
            deadzone=args.gaze_deadzone,
        ),
        auto_center=auto_center_effective,
        center_alpha=args.auto_center_alpha,
    )
    active_model = None if calibration_mode else loaded_model
    # Cursor-tuned one-euro: a higher min_cutoff than the default 1.0 trims the
    # baseline lag (the filter still raises its cutoff further on fast head moves
    # via beta), so the cursor feels responsive without jittering when still.
    cal_x_filter = OneEuroFilter(min_cutoff=1.7, beta=0.05)
    cal_y_filter = OneEuroFilter(min_cutoff=1.7, beta=0.05)
    calibration_samples: list[CalibrationSample] = []
    calibration_feature_buffer: deque[dict[str, float]] = deque(maxlen=max(1, args.calibration_avg_frames))
    calibration_targets = default_calibration_targets(canvas)
    calibration_target_idx = 0
    calibration_saved_path = None
    calibration_notice = ""
    validation_samples: list[ValidationSample] = []
    validation_point_buffer: deque[tuple[float, float]] = deque(maxlen=max(1, args.validation_avg_frames))
    validation_targets = _default_validation_targets(canvas, args.validation_points_per_monitor)
    validation_target_idx = 0
    validation_fail_count = 0
    debug_capture_count = 0
    stabilized_point: tuple[float, float] | None = None
    targeter = WindowTargeter()
    target_stabilizer = WindowTargetStabilizer(stable_ms=args.target_stable_ms)
    actuator = WindowActuator(
        execute=execute_actions_live,
        desktop_rect=canvas.rect,
        monitors=tuple(monitor.rect for monitor in canvas.monitors),
    )
    controller = FixedGestureWindowController(
        WindowControlConfig(
            execute_actions=execute_actions_live,
            drag_gain_x_px=args.drag_gain_x_px,
            drag_gain_y_px=args.drag_gain_y_px,
            drag_smoothing_alpha=args.drag_smoothing_alpha,
            drag_max_step_px=args.drag_max_step_px,
            scroll_threshold_norm=args.scroll_threshold_norm,
            scroll_gain=args.scroll_gain,
            scroll_rearm_threshold_norm=args.scroll_rearm_threshold_norm,
            scroll_min_wheel_delta=args.scroll_min_wheel_delta,
            scroll_max_wheel_delta=args.scroll_max_wheel_delta,
            resize_ratio_smoothing_alpha=args.resize_ratio_smoothing_alpha,
            resize_step_px=args.resize_step_px,
            maximize_ratio=args.maximize_ratio,
            restore_ratio=args.restore_ratio,
            two_hand_zoom_step_ratio=args.two_hand_zoom_step_ratio,
            two_hand_zoom_cooldown_s=args.two_hand_zoom_cooldown_s,
            point_click_cooldown_s=args.point_click_cooldown_s,
            point_snap_radius_px=args.point_snap_radius_px,
            point_tap_threshold_norm=args.point_tap_threshold_norm,
            point_tap_release_norm=args.point_tap_release_norm,
            window_snap_enabled=args.window_snap,
            window_snap_edge_px=args.window_snap_edge_px,
        ),
        actuator,
    )
    hand_tracker = HandIdentityTracker(max_jump_norm=args.hand_max_jump_norm)
    hand_quality_gate = HandQualityGate(
        HandQualityConfig(
            min_score=args.hand_min_score,
            edge_margin=args.hand_edge_margin,
            max_jump_norm=args.hand_max_jump_norm,
            min_palm_size=args.hand_min_palm_size,
            max_palm_size=args.hand_max_palm_size,
            min_two_hand_distance=args.hand_min_two_hand_distance,
        )
    )
    gesture_filter = GestureStateFilter(
        enter_frames=args.gesture_enter_frames,
        exit_frames=args.gesture_exit_frames,
        min_confidence=args.gesture_min_confidence,
    )
    events: deque[dict[str, object]] = deque(maxlen=args.event_log_size)
    last_face = None
    frames = 0
    started = time.perf_counter()
    window = "Gemma 4 Window Control"
    watch_keys = tuple(
        sorted(
            set(KEY_TOGGLE_EXECUTE)
            | set(KEY_TOGGLE_CALIBRATION)
            | set(KEY_RESTART_CALIBRATION)
            | set(KEY_CALIBRATION_CAPTURE)
            | set(KEY_CALIBRATION_SAVE)
            | set(KEY_CALIBRATION_NEXT)
            | set(KEY_CALIBRATION_CLEAR)
            | set(KEY_QUIT)
        )
    )
    global_keys = _GlobalKeyEdgePoller(watch_keys)
    click_poller = _GlobalMouseClickPoller()
    online_samples: deque[CalibrationSample] = deque(maxlen=max(1, args.online_learn_max_new_samples))
    online_feature_history: deque[tuple[float, dict[str, float], tuple[float, float]]] = deque(
        maxlen=max(8, int(args.online_learn_history_max_frames))
    )
    pending_online_since_train = 0
    camera_info: dict[str, Any] = {}
    desktop_dot = None
    if args.show_desktop_gaze_dot:
        try:
            desktop_dot = DesktopGazeDot(size=args.desktop_gaze_dot_size)
        except Exception:
            desktop_dot = None

    camera_config = CameraConfig(
        args.camera_index,
        args.width,
        args.height,
        args.camera_fps,
        backend=_camera_backend_value(args.camera_backend),
    )
    with OpenCVCamera(camera_config) as camera, MediaPipeLandmarkDetector(
        model_dir=args.model_dir,
        download_models=args.download_models,
        num_hands=args.num_hands,
        min_confidence=args.min_confidence,
    ) as detector:
        camera_info = camera.info()
        camera_label = _camera_label(camera_info, args.camera_backend)
        window = f"Gemma 4 Window Control - {camera_label}"
        if not args.no_window:
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        while True:
            now = time.perf_counter()
            if args.duration > 0 and now - started >= args.duration:
                break
            frame = camera.read()
            bgr = cv2.flip(frame.bgr, 1) if args.mirror else frame.bgr
            timestamp_ms = int(frame.timestamp_s * 1000)
            landmarks = detector.detect(
                bgr,
                timestamp_ms,
                run_face=frames % max(1, args.face_every_n) == 0,
            )
            frames += 1
            if landmarks.primary_face is not None:
                last_face = landmarks.primary_face
            head = mapper.update(last_face, frame.timestamp_s)
            if calibration_mode and head is not None:
                calibration_feature_buffer.append(_head_features(head))
            desktop_point_raw = _desktop_point(head, active_model, canvas, frame.timestamp_s, cal_x_filter, cal_y_filter)
            stabilized_point = _smooth_point(stabilized_point, desktop_point_raw, args.gaze_smooth_alpha, args.gaze_max_step_px)
            desktop_point = stabilized_point
            if validation_mode and desktop_point_raw is not None:
                validation_point_buffer.append(desktop_point_raw)
            click_xy = click_poller.consume_left_click()
            if auto_online_learn_enabled and not calibration_mode:
                _append_online_feature_snapshot(
                    online_feature_history,
                    head=head,
                    desktop_point=desktop_point,
                    timestamp_s=frame.timestamp_s,
                    min_gaze_confidence=args.online_learn_min_gaze_confidence,
                )
                if click_xy is not None:
                    click_sample = _sample_from_click_history(
                        history=online_feature_history,
                        click_xy=click_xy,
                        click_timestamp_s=frame.timestamp_s,
                        lag_ms=args.online_learn_click_lag_ms,
                        window_ms=args.online_learn_window_ms,
                        max_jitter=args.online_learn_max_feature_jitter,
                        max_click_distance_px=args.online_learn_max_click_distance_px,
                    )
                    if click_sample is not None:
                        online_samples.append(click_sample)
                        pending_online_since_train += 1
                if (
                    pending_online_since_train >= max(1, int(args.online_learn_retrain_every))
                    and len(online_samples) >= max(6, int(args.online_learn_min_samples))
                ):
                    active_model, loaded_model, updated = _online_retrain_from_clicks(
                        store=store,
                        layout_hash=canvas.layout_hash,
                        user=args.calibration_user,
                        loaded_model=loaded_model,
                        active_model=active_model,
                        recent_samples=tuple(online_samples),
                        max_total_samples=args.calibration_history_max_samples,
                        max_rms_px=args.calibration_max_rms_px,
                    )
                    pending_online_since_train = 0
                    if updated:
                        calibration_notice = f"auto-learn updated | samples {len(online_samples)}"
            if desktop_dot is not None:
                if calibration_mode and calibration_targets:
                    target_xy = calibration_targets[calibration_target_idx]
                    desktop_dot.move_to(target_xy[0], target_xy[1])
                elif validation_mode and validation_targets:
                    target_xy = validation_targets[validation_target_idx]
                    desktop_dot.move_to(target_xy[0], target_xy[1])
                elif desktop_point is not None:
                    desktop_dot.move_to(desktop_point[0], desktop_point[1])
            if args.show_system_gaze_pointer and not calibration_mode and not validation_mode and desktop_point is not None:
                _set_cursor_pos((int(round(desktop_point[0])), int(round(desktop_point[1]))))
            candidate = _candidate_window(
                targeter,
                desktop_point,
                near_radius_px=args.target_search_radius_px,
                fallback_foreground=args.target_foreground_fallback,
            )
            target = target_stabilizer.update(candidate, frame.timestamp_s)
            hands = _control_hands(landmarks, hand_tracker, hand_quality_gate, gesture_filter, max_hands=args.num_hands)
            output_state = "calibrating" if calibration_mode else "validating" if validation_mode else "idle"
            action_block_reason = _action_block_reason(
                args=args,
                active_model=active_model,
                calibration_mode=calibration_mode,
                validation_mode=validation_mode,
                calibration_validated=calibration_validated,
            )
            effective_execute = execute_actions_live and action_block_reason is None
            actuator.execute = effective_execute
            controller.config = WindowControlConfig(
                execute_actions=effective_execute,
                drag_gain_x_px=args.drag_gain_x_px,
                drag_gain_y_px=args.drag_gain_y_px,
                drag_smoothing_alpha=args.drag_smoothing_alpha,
                drag_max_step_px=args.drag_max_step_px,
                scroll_threshold_norm=args.scroll_threshold_norm,
                scroll_gain=args.scroll_gain,
                scroll_rearm_threshold_norm=args.scroll_rearm_threshold_norm,
                scroll_min_wheel_delta=args.scroll_min_wheel_delta,
                scroll_max_wheel_delta=args.scroll_max_wheel_delta,
                resize_ratio_smoothing_alpha=args.resize_ratio_smoothing_alpha,
                resize_step_px=args.resize_step_px,
                maximize_ratio=args.maximize_ratio,
                restore_ratio=args.restore_ratio,
                two_hand_zoom_step_ratio=args.two_hand_zoom_step_ratio,
                two_hand_zoom_cooldown_s=args.two_hand_zoom_cooldown_s,
                point_click_cooldown_s=args.point_click_cooldown_s,
                point_snap_radius_px=args.point_snap_radius_px,
                point_tap_threshold_norm=args.point_tap_threshold_norm,
                point_tap_release_norm=args.point_tap_release_norm,
                window_snap_enabled=args.window_snap,
                window_snap_edge_px=args.window_snap_edge_px,
            )
            if calibration_mode or validation_mode:
                output_events: tuple[dict[str, object], ...] = ()
            else:
                pointer_xy = _pointer_xy(desktop_point)
                output = controller.update(
                    timestamp_s=frame.timestamp_s,
                    target=target,
                    hands=hands,
                    pointer_xy=pointer_xy,
                )
                output_state = output.state.value
                for event in output.events:
                    events.append(
                        {
                            "time_s": round(time.perf_counter() - started, 3),
                            "name": event.name,
                            "target_title": event.target_title,
                            "target_hwnd": event.target_hwnd,
                            "detail": event.detail,
                            "executed": event.executed,
                        }
                    )
                output_events = tuple(events)

            if not args.no_window:
                annotated = _draw_overlay(
                    bgr.copy(),
                    landmarks,
                    head,
                    hands,
                    candidate,
                    target,
                    output_state,
                    output_events,
                    camera_label,
                    effective_execute,
                    execute_actions_live,
                    _action_status_text(
                        actions_requested=execute_actions_live,
                        actions_effective=effective_execute,
                        block_reason=action_block_reason,
                        candidate=candidate,
                        target=target,
                        hands=hands,
                    ),
                    canvas,
                    args.show_gaze_pointer,
                    args.show_desktop_map,
                    desktop_point,
                    _calibration_status_text(
                        calibration_mode,
                        active_model,
                        calibration_samples,
                        calibration_target_idx,
                        len(calibration_targets),
                        calibration_notice,
                        validation_mode=validation_mode,
                        validation_samples=validation_samples,
                        validation_target_idx=validation_target_idx,
                        validation_target_total=len(validation_targets),
                        validation_summary=validation_summary,
                        actions_requested=execute_actions_live,
                        actions_allowed=effective_execute,
                        auto_learn_samples=len(online_samples),
                    ),
                )
                cv2.imshow(window, annotated)
                key = cv2.waitKey(1) & 0xFF
            else:
                annotated = bgr.copy()
                key = -1
            hotkeys = global_keys.pressed_keys()
            # Quit (q/Esc) must come ONLY from the focused camera window, never
            # from the system-wide poller: otherwise pressing q/Esc in the
            # terminal or in an app you are controlling closes the tool ("window
            # closes itself"). Global hotkeys still drive in-app actions; only the
            # close keys are gated to window focus.
            hotkeys = [k for k in hotkeys if k not in KEY_QUIT]
            all_keys = _merge_keys(key, hotkeys)
            if any(k in KEY_RESTART_CALIBRATION for k in all_keys if k >= 0 and k != 255):
                calibration_mode = True
                validation_mode = False
                calibration_samples.clear()
                calibration_feature_buffer.clear()
                calibration_target_idx = 0
                validation_samples.clear()
                validation_point_buffer.clear()
                validation_target_idx = 0
                validation_fail_count = 0
                calibration_validated = False
                active_model = None
                calibration_notice = "calibration restarted"
                controller = FixedGestureWindowController(
                    WindowControlConfig(
                        execute_actions=execute_actions_live,
                        drag_gain_x_px=args.drag_gain_x_px,
                        drag_gain_y_px=args.drag_gain_y_px,
                        drag_smoothing_alpha=args.drag_smoothing_alpha,
                        drag_max_step_px=args.drag_max_step_px,
                        scroll_threshold_norm=args.scroll_threshold_norm,
                        scroll_gain=args.scroll_gain,
                        scroll_rearm_threshold_norm=args.scroll_rearm_threshold_norm,
                        scroll_min_wheel_delta=args.scroll_min_wheel_delta,
                        scroll_max_wheel_delta=args.scroll_max_wheel_delta,
                        resize_ratio_smoothing_alpha=args.resize_ratio_smoothing_alpha,
                        resize_step_px=args.resize_step_px,
                        maximize_ratio=args.maximize_ratio,
                        restore_ratio=args.restore_ratio,
                        two_hand_zoom_step_ratio=args.two_hand_zoom_step_ratio,
                        two_hand_zoom_cooldown_s=args.two_hand_zoom_cooldown_s,
                        point_click_cooldown_s=args.point_click_cooldown_s,
                        point_snap_radius_px=args.point_snap_radius_px,
                        point_tap_threshold_norm=args.point_tap_threshold_norm,
                        point_tap_release_norm=args.point_tap_release_norm,
                        window_snap_enabled=args.window_snap,
                        window_snap_edge_px=args.window_snap_edge_px,
                    ),
                    actuator,
                )
                continue
            if any(k in KEY_TOGGLE_EXECUTE for k in all_keys if k >= 0 and k != 255):
                execute_actions_live = not execute_actions_live
                actuator.execute = execute_actions_live
            if any(k in KEY_TOGGLE_CALIBRATION for k in all_keys if k >= 0 and k != 255):
                calibration_mode = not calibration_mode
                validation_mode = False
                if calibration_mode:
                    calibration_samples.clear()
                    calibration_feature_buffer.clear()
                    calibration_target_idx = 0
                    validation_samples.clear()
                    validation_point_buffer.clear()
                    validation_target_idx = 0
                    validation_fail_count = 0
                    calibration_validated = False
                    active_model = None
                    calibration_notice = "calibration mode enabled"
                else:
                    if args.use_calibration:
                        active_model = loaded_model
                    calibration_notice = ""
                controller = FixedGestureWindowController(
                    WindowControlConfig(
                        execute_actions=execute_actions_live,
                        drag_gain_x_px=args.drag_gain_x_px,
                        drag_gain_y_px=args.drag_gain_y_px,
                        drag_smoothing_alpha=args.drag_smoothing_alpha,
                        drag_max_step_px=args.drag_max_step_px,
                        scroll_threshold_norm=args.scroll_threshold_norm,
                        scroll_gain=args.scroll_gain,
                        scroll_rearm_threshold_norm=args.scroll_rearm_threshold_norm,
                        scroll_min_wheel_delta=args.scroll_min_wheel_delta,
                        scroll_max_wheel_delta=args.scroll_max_wheel_delta,
                        resize_ratio_smoothing_alpha=args.resize_ratio_smoothing_alpha,
                        resize_step_px=args.resize_step_px,
                        maximize_ratio=args.maximize_ratio,
                        restore_ratio=args.restore_ratio,
                        two_hand_zoom_step_ratio=args.two_hand_zoom_step_ratio,
                        two_hand_zoom_cooldown_s=args.two_hand_zoom_cooldown_s,
                        point_click_cooldown_s=args.point_click_cooldown_s,
                        point_snap_radius_px=args.point_snap_radius_px,
                        point_tap_threshold_norm=args.point_tap_threshold_norm,
                        point_tap_release_norm=args.point_tap_release_norm,
                        window_snap_enabled=args.window_snap,
                        window_snap_edge_px=args.window_snap_edge_px,
                    ),
                    actuator,
                )
            if calibration_mode:
                should_debug_capture = args.save_calibration_debug_captures and _has_capture_key(all_keys)
                debug_target_point = calibration_targets[calibration_target_idx] if calibration_targets else None
                debug_sample_count_before = len(calibration_samples)
                keep_running, calibration_target_idx, active_model, calibration_saved_path, calibration_notice = _handle_calibration_keys(
                    key=key,
                    hotkeys=all_keys,
                    head=head,
                    target_point=debug_target_point,
                    samples=calibration_samples,
                    feature_buffer=calibration_feature_buffer,
                    targets=calibration_targets,
                    target_idx=calibration_target_idx,
                    min_samples=args.calibration_min_samples,
                    layout_hash=canvas.layout_hash,
                    canvas=canvas,
                    camera_resolution=(int(args.width), int(args.height)),
                    store=store,
                    user=args.calibration_user,
                    merge_with_existing=args.merge_calibration_history,
                    max_history_samples=args.calibration_history_max_samples,
                    max_merge_rms_px=args.calibration_max_rms_px,
                    min_capture_frames=args.calibration_min_capture_frames,
                    max_capture_feature_jitter=args.calibration_max_feature_jitter,
                    min_capture_gaze_confidence=args.calibration_min_gaze_confidence,
                )
                if should_debug_capture:
                    debug_capture_count += 1
                    _save_calibration_debug_capture(
                        frame=annotated,
                        output_dir=args.debug_capture_dir,
                        index=debug_capture_count,
                        mode="calibration",
                        notice=calibration_notice,
                        target_point=debug_target_point,
                        desktop_point=desktop_point,
                        head=head,
                        canvas=canvas,
                        sample_count_before=debug_sample_count_before,
                        sample_count_after=len(calibration_samples),
                        validation_sample=None,
                    )
                if not keep_running:
                    if calibration_saved_path is not None and args.validate_after_calibration and active_model is not None:
                        calibration_mode = False
                        validation_mode = True
                        validation_samples.clear()
                        validation_point_buffer.clear()
                        stabilized_point = None
                        cal_x_filter = OneEuroFilter()
                        cal_y_filter = OneEuroFilter()
                        validation_targets = _default_validation_targets(canvas, args.validation_points_per_monitor)
                        validation_target_idx = 0
                        validation_summary = None
                        calibration_validated = False
                        calibration_notice = "validation started: mira el DOT y usa espacio"
                        continue
                    if calibration_saved_path is not None and args.control_after_calibration:
                        calibration_mode = False
                        calibration_feature_buffer.clear()
                        if args.use_calibration:
                            loaded_model = active_model
                        validation_summary = evaluate_calibration_model(active_model, calibration_samples, canvas)
                        calibration_validated = _validation_summary_passes(validation_summary, args)
                        continue
                    break
            elif validation_mode:
                should_debug_capture = args.save_calibration_debug_captures and _has_capture_key(all_keys)
                debug_target_point = validation_targets[validation_target_idx] if validation_targets else None
                debug_desktop_point = desktop_point_raw if desktop_point_raw is not None else desktop_point
                debug_sample_count_before = len(validation_samples)
                keep_running, validation_target_idx, validation_finished, validation_summary, calibration_notice = _handle_validation_keys(
                    key=key,
                    hotkeys=all_keys,
                    desktop_point_buffer=validation_point_buffer,
                    target_point=debug_target_point,
                    samples=validation_samples,
                    targets=validation_targets,
                    target_idx=validation_target_idx,
                    canvas=canvas,
                    min_capture_frames=args.validation_min_capture_frames,
                    args=args,
                )
                if should_debug_capture:
                    debug_capture_count += 1
                    new_validation_sample = (
                        validation_samples[-1]
                        if len(validation_samples) > debug_sample_count_before
                        else None
                    )
                    _save_calibration_debug_capture(
                        frame=annotated,
                        output_dir=args.debug_capture_dir,
                        index=debug_capture_count,
                        mode="validation",
                        notice=calibration_notice,
                        target_point=debug_target_point,
                        desktop_point=debug_desktop_point,
                        head=head,
                        canvas=canvas,
                        sample_count_before=debug_sample_count_before,
                        sample_count_after=len(validation_samples),
                        validation_sample=new_validation_sample,
                    )
                if not keep_running:
                    break
                if validation_finished:
                    if (
                        args.fine_screen_warp
                        and active_model is not None
                        and active_model.screen_warp is None
                        and validation_summary is not None
                    ):
                        warped_model, warped_summary = _fit_validation_screen_warp(
                            active_model,
                            validation_samples,
                            canvas,
                            max_rms_px=args.fine_screen_warp_max_rms_px,
                        )
                        if warped_model is not None and warped_summary is not None:
                            active_model = warped_model
                            validation_summary = warped_summary
                            if args.use_calibration:
                                loaded_model = warped_model
                            calibration_saved_path = _save_calibration_profile(
                                store=store,
                                layout_hash=canvas.layout_hash,
                                user=args.calibration_user,
                                samples=tuple(calibration_samples),
                                model=warped_model,
                            )
                    if _validation_summary_passes(validation_summary, args):
                        validation_mode = False
                        calibration_validated = True
                        validation_fail_count = 0
                        calibration_notice = _validation_notice(validation_summary, passed=True)
                        if active_model is not None and active_model.screen_warp is not None:
                            calibration_notice = f"{calibration_notice} | fine warp active"
                        if args.use_calibration:
                            loaded_model = active_model
                        continue
                    calibration_validated = False
                    validation_fail_count += 1
                    max_retries = max(0, int(args.validation_max_retries))
                    if validation_fail_count > max_retries:
                        validation_mode = False
                        calibration_mode = False
                        validation_point_buffer.clear()
                        calibration_feature_buffer.clear()
                        calibration_notice = (
                            f"{_validation_notice(validation_summary, passed=False)} | "
                            f"retry limit {max_retries} reached; control SAFE, p=recalibrar"
                        )
                        continue
                    bad_targets = _bad_validation_targets(
                        validation_samples,
                        args.validation_max_point_error_px,
                        args.validation_repeat_worst,
                    )
                    calibration_targets = bad_targets or _default_validation_targets(canvas, args.validation_points_per_monitor)
                    calibration_target_idx = 0
                    calibration_feature_buffer.clear()
                    validation_point_buffer.clear()
                    validation_mode = False
                    calibration_mode = True
                    calibration_notice = (
                        f"{_validation_notice(validation_summary, passed=False)} | "
                        f"retry {validation_fail_count}/{max_retries}"
                    )
                    continue
            elif _should_quit(all_keys):
                break

    if not args.no_window:
        cv2.destroyWindow(window)
    if desktop_dot is not None:
        desktop_dot.close()

    diagnostic_samples = list(calibration_samples)
    if not diagnostic_samples and loaded_profile is not None:
        diagnostic_samples = list(loaded_profile.samples)
    calibration_diagnostics = evaluate_calibration_model(active_model, diagnostic_samples, canvas)

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "phase": "1-window-control-poc",
        "execute_actions": bool(execute_actions_live),
        "execute_actions_effective": bool(
            execute_actions_live
            and _actions_allowed(
                args=args,
                active_model=active_model,
                calibration_mode=calibration_mode,
                validation_mode=validation_mode,
                calibration_validated=calibration_validated,
            )
        ),
        "privacy": "No video frames are saved; only aggregate action events are reported.",
        "camera": {
            "index": args.camera_index,
            "backend": args.camera_backend,
            "width": args.width,
            "height": args.height,
            "requested_fps": args.camera_fps,
            "face_every_n": args.face_every_n,
            "mirror": args.mirror,
            "active": camera_info,
        },
        "monitors": canvas_to_dict(canvas),
        "metrics": {
            "elapsed_s": time.perf_counter() - started,
            "frames_total": frames,
            "fps_approx": frames / max(1e-6, time.perf_counter() - started),
        },
        "actions": list(events),
        "calibration": {
            "loaded": loaded_model is not None,
            "active": active_model is not None,
            "run_mode": calibration_mode,
            "samples_collected": len(calibration_samples),
            "saved_path": str(calibration_saved_path) if calibration_saved_path is not None else None,
            "rms_error_px": active_model.rms_error_px if active_model is not None else None,
            "diagnostics": calibration_diagnostics,
            "rejected_reason": calibration_rejected_reason,
            "auto_center_effective": auto_center_effective,
            "validated": calibration_validated,
            "validation": validation_summary,
            "validation_fail_count": validation_fail_count,
            "debug_captures": {
                "enabled": bool(args.save_calibration_debug_captures),
                "count": debug_capture_count,
                "dir": str(args.debug_capture_dir),
            },
            "fine_screen_warp": (
                active_model.screen_warp.to_dict()
                if active_model is not None and active_model.screen_warp is not None
                else None
            ),
        },
    }
    _write_report(report, args.report_path)
    return report


def _candidate_window(
    targeter: WindowTargeter,
    desktop_point: tuple[float, float] | None,
    *,
    near_radius_px: int = 0,
    fallback_foreground: bool = False,
) -> WindowTarget | None:
    target = None
    if desktop_point is None:
        target = None
    elif near_radius_px > 0:
        target = targeter.from_point_near(desktop_point[0], desktop_point[1], radius_px=near_radius_px)
    else:
        target = targeter.from_point(desktop_point[0], desktop_point[1])
    if target is None and fallback_foreground:
        target = targeter.foreground()
    return target


def _pointer_xy(desktop_point: tuple[float, float] | None) -> tuple[int, int] | None:
    if desktop_point is None:
        return None
    return (int(round(desktop_point[0])), int(round(desktop_point[1])))


def _control_hands(
    landmarks: LandmarkFrame,
    tracker: HandIdentityTracker,
    quality_gate: HandQualityGate,
    gesture_filter: GestureStateFilter,
    *,
    max_hands: int,
) -> tuple[HandControlPose, ...]:
    assigned = tracker.assign(landmarks.hands)
    if not assigned:
        gesture_filter.reset_missing(set())
        return ()
    centers = {track_id: _hand_center(hand) for track_id, hand in assigned}
    active_ids: set[str] = set()
    out: list[HandControlPose] = []
    for track_id, hand in assigned[: max(1, int(max_hands))]:
        index_tip = _hand_landmark_xyz(hand, 8)
        palm = _hand_palm_xyz(hand)
        other_centers = tuple(center for other_id, center in centers.items() if other_id != track_id)
        quality = quality_gate.evaluate(track_id, hand, other_centers=other_centers)
        raw = recognize_hand_gesture(hand)
        label = gesture_filter.update(track_id, raw, quality)
        active_ids.add(track_id)
        out.append(
            HandControlPose(
                quality.center_x,
                quality.center_y,
                label,
                hand.handedness,
                hand.score,
                raw.label,
                raw.confidence,
                track_id,
                quality.ok,
                quality.reason,
                quality.palm_size,
                index_tip[0],
                index_tip[1],
                index_tip[2],
                palm[0],
                palm[1],
                palm[2],
            )
        )
    gesture_filter.reset_missing(active_ids)
    return tuple(sorted(out, key=lambda hand: hand.x))


def _hand_center(hand: HandSample) -> tuple[float, float]:
    palm = _hand_palm_xyz(hand)
    return (palm[0] if palm[0] is not None else 0.5, palm[1] if palm[1] is not None else 0.5)


def _hand_palm_xyz(hand: HandSample) -> tuple[float | None, float | None, float | None]:
    points = hand.landmarks
    indexes = (0, 5, 9, 13, 17)
    usable = [points[idx] for idx in indexes if idx < len(points)]
    if not usable:
        return (None, None, None)
    return (
        sum(p.x for p in usable) / len(usable),
        sum(p.y for p in usable) / len(usable),
        sum(p.z for p in usable) / len(usable),
    )


def _hand_landmark_xyz(hand: HandSample, index: int) -> tuple[float | None, float | None, float | None]:
    if index < 0 or index >= len(hand.landmarks):
        return (None, None, None)
    point = hand.landmarks[index]
    return (point.x, point.y, point.z)


def _draw_overlay(
    frame: Any,
    landmarks: LandmarkFrame,
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
    import cv2

    h, w = frame.shape[:2]
    _draw_hands(frame, landmarks)
    _draw_face(frame, landmarks)
    _draw_hand_control_points(frame, hands)
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
    hand_text = " | ".join(_hand_debug_text(idx, hand) for idx, hand in enumerate(hands)) or "no hand"
    cv2.putText(frame, f"state {state} | {hand_text}", (16, 156), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (230, 230, 230), 1)
    cv2.putText(
        frame,
        "fist=mover/snap ventana | palm+stroke=scroll | 2 manos=zoom | point+tap=click snap",
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
        _draw_gaze_pointer(frame, head)
    if show_desktop_map:
        _draw_desktop_map(frame, canvas, head, desktop_point, candidate, target)
    if calibration_text:
        cv2.putText(frame, calibration_text, (16, min(h - 16, 254)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (120, 240, 255), 1)
    return frame


def _draw_hand_control_points(frame: Any, hands: tuple[HandControlPose, ...]) -> None:
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
    if len(pts) >= 2:
        cv2.line(frame, pts[0], pts[1], (60, 255, 60), 2)


def _hand_debug_text(idx: int, hand: HandControlPose) -> str:
    raw = hand.raw_label or hand.label
    conf = "" if hand.gesture_confidence is None else f"{hand.gesture_confidence:.2f}"
    track = f"{hand.track_id}:" if hand.track_id else ""
    quality = "" if hand.quality_ok else f"!{hand.quality_reason}"
    if raw == hand.label:
        return f"h{idx}:{track}{hand.label}{conf}{quality}@{hand.x:.2f},{hand.y:.2f}"
    return f"h{idx}:{track}{raw}->{hand.label}{conf}{quality}@{hand.x:.2f},{hand.y:.2f}"


def _draw_gaze_pointer(frame: Any, head: HeadPointerEstimate | None) -> None:
    import cv2

    pt = _frame_point_from_head(frame, head)
    if pt is None:
        return
    color = (80, 235, 255) if head is not None and head.source.endswith("head+iris") else (120, 200, 255)
    x, y = pt
    cv2.circle(frame, (x, y), 12, color, 2)
    cv2.circle(frame, (x, y), 3, color, -1)
    cv2.line(frame, (x - 18, y), (x + 18, y), color, 1)
    cv2.line(frame, (x, y - 18), (x, y + 18), color, 1)
    cv2.putText(frame, "gaze", (x + 14, max(24, y - 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)


def _draw_desktop_map(
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


def _frame_point_from_head(frame: Any, head: HeadPointerEstimate | None) -> tuple[int, int] | None:
    if head is None:
        return None
    h, w = frame.shape[:2]
    x = int(round(max(0.0, min(1.0, head.local_x)) * (w - 1)))
    y = int(round(max(0.0, min(1.0, head.local_y)) * (h - 1)))
    return (x, y)


def _desktop_point(
    head: HeadPointerEstimate | None,
    model: LinearGazeModel | None,
    canvas: VirtualCanvas,
    timestamp_s: float,
    x_filter: OneEuroFilter,
    y_filter: OneEuroFilter,
) -> tuple[float, float] | None:
    if head is None:
        return None
    if model is None:
        return (head.filtered_x, head.filtered_y)
    features = _head_features(head)
    pred_x, pred_y = model.predict(features)
    if not math.isfinite(pred_x) or not math.isfinite(pred_y):
        return (head.filtered_x, head.filtered_y)
    pred_x = _clamp(pred_x, float(canvas.rect.left), float(canvas.rect.right - 1))
    pred_y = _clamp(pred_y, float(canvas.rect.top), float(canvas.rect.bottom - 1))
    return (
        x_filter.filter(pred_x, timestamp_s),
        y_filter.filter(pred_y, timestamp_s),
    )


def _smooth_point(
    previous: tuple[float, float] | None,
    current: tuple[float, float] | None,
    alpha: float,
    max_step_px: float,
) -> tuple[float, float] | None:
    if current is None:
        return previous
    if previous is None:
        return current
    a = _clamp(alpha, 0.01, 1.0)
    dx = current[0] - previous[0]
    dy = current[1] - previous[1]
    dist = math.hypot(dx, dy)
    limit = max(1.0, float(max_step_px))
    if dist > limit:
        scale = limit / max(1e-6, dist)
        current = (previous[0] + dx * scale, previous[1] + dy * scale)
    return (
        previous[0] + (current[0] - previous[0]) * a,
        previous[1] + (current[1] - previous[1]) * a,
    )


def _head_features(head: HeadPointerEstimate) -> dict[str, float]:
    gaze_x = 0.0
    gaze_y = 0.0
    if head.gaze is not None:
        gaze_x = head.gaze.x
        gaze_y = head.gaze.y
    return make_feature_dict(head.yaw, head.pitch, gaze_x, gaze_y)


def _average_features(buffer: deque[dict[str, float]]) -> dict[str, float]:
    if not buffer:
        return make_feature_dict(0.0, 0.0, 0.0, 0.0)
    keys = ("yaw", "pitch", "gaze_x", "gaze_y")
    return {
        key: sum(float(item.get(key, 0.0)) for item in buffer) / len(buffer)
        for key in keys
    }


def _feature_jitter(samples: tuple[dict[str, float], ...]) -> float:
    if len(samples) < 2:
        return 0.0
    keys = ONLINE_FEATURE_KEYS
    variances: list[float] = []
    for key in keys:
        values = [float(item.get(key, 0.0)) for item in samples]
        mean = sum(values) / len(values)
        variances.append(sum((value - mean) ** 2 for value in values) / len(values))
    return math.sqrt(sum(variances))


def _append_online_feature_snapshot(
    history: deque[tuple[float, dict[str, float], tuple[float, float]]],
    *,
    head: HeadPointerEstimate | None,
    desktop_point: tuple[float, float] | None,
    timestamp_s: float,
    min_gaze_confidence: float,
) -> None:
    if head is None or desktop_point is None:
        return
    if not _head_confident_for_online_learn(head, min_gaze_confidence):
        return
    history.append((timestamp_s, _head_features(head), desktop_point))


def _sample_from_click_history(
    *,
    history: deque[tuple[float, dict[str, float], tuple[float, float]]],
    click_xy: tuple[int, int],
    click_timestamp_s: float,
    lag_ms: float,
    window_ms: float,
    max_jitter: float,
    max_click_distance_px: float,
) -> CalibrationSample | None:
    if not history:
        return None
    lag_s = max(0.0, float(lag_ms) / 1000.0)
    win_s = max(0.04, float(window_ms) / 1000.0)
    end_t = click_timestamp_s - lag_s
    start_t = end_t - win_s
    selected = [item for item in history if start_t <= item[0] <= end_t]
    if len(selected) < 3:
        return None
    feature_rows = tuple(item[1] for item in selected)
    jitter = _feature_jitter(feature_rows)
    if jitter > float(max_jitter):
        return None
    features = _average_features(deque(feature_rows))
    avg_x = sum(item[2][0] for item in selected) / len(selected)
    avg_y = sum(item[2][1] for item in selected) / len(selected)
    click_dist = math.hypot(float(click_xy[0]) - avg_x, float(click_xy[1]) - avg_y)
    if click_dist > float(max_click_distance_px):
        return None
    return CalibrationSample(features=features, target_x=float(click_xy[0]), target_y=float(click_xy[1]))


def _calibration_status_text(
    run_mode: bool,
    model: LinearGazeModel | None,
    samples: list[CalibrationSample],
    target_idx: int,
    target_total: int,
    notice: str,
    *,
    validation_mode: bool = False,
    validation_samples: list[ValidationSample] | None = None,
    validation_target_idx: int = 0,
    validation_target_total: int = 0,
    validation_summary: dict[str, Any] | None = None,
    actions_requested: bool = False,
    actions_allowed: bool = False,
    auto_learn_samples: int = 0,
) -> str:
    action_text = ""
    if actions_requested and not actions_allowed:
        action_text = " | ACTIONS BLOCKED: valida calibracion"
    if validation_mode:
        count = len(validation_samples or [])
        base = (
            f"VALIDANDO {count} muestras | objetivo {validation_target_idx + 1}/{max(1, validation_target_total)} | "
            "sigue el DOT | espacio/s=medir enter=finalizar c=limpiar p=recalibrar"
        )
        return f"{base}{action_text} | {notice}" if notice else f"{base}{action_text}"
    if run_mode:
        base = (
            f"CALIBRANDO {len(samples)} muestras | objetivo {target_idx + 1}/{max(1, target_total)} | "
            "sigue el DOT flotante | espacio/s=capturar n=siguiente enter=guardar y continuar c=limpiar q=salir"
        )
        if auto_learn_samples > 0:
            base = f"{base} | auto-learn samples: {auto_learn_samples}"
        return f"{base} | {notice}" if notice else base
    if model is None:
        base = "calibration: none (usa --run-calibration para entrenar)"
        if auto_learn_samples > 0:
            base = f"{base} | auto-learn samples: {auto_learn_samples}"
        return f"{base}{action_text}"
    base = f"calibration: active rms={model.rms_error_px:.1f}px"
    if validation_summary is not None:
        global_summary = validation_summary.get("global") or {}
        rms = global_summary.get("rms_px")
        p95 = global_summary.get("p95_px")
        accuracy = validation_summary.get("monitor_accuracy")
        if rms is not None and p95 is not None and accuracy is not None:
            base = f"{base} | val rms={float(rms):.0f}px p95={float(p95):.0f}px mon={float(accuracy) * 100:.0f}%"
    if auto_learn_samples > 0:
        base = f"{base} | auto-learn samples: {auto_learn_samples}"
    return f"{base}{action_text} | {notice}" if notice else f"{base}{action_text}"


def _default_validation_targets(canvas: VirtualCanvas, points_per_monitor: int) -> tuple[tuple[int, int], ...]:
    if points_per_monitor >= 9:
        return default_calibration_targets(canvas, margin=0.18)
    margin = 0.18
    pts: list[tuple[int, int]] = []
    for monitor in sorted(canvas.monitors, key=lambda item: (item.rect.left, item.rect.top, item.index)):
        left = monitor.rect.left
        top = monitor.rect.top
        width = max(1, monitor.rect.width)
        height = max(1, monitor.rect.height)
        for nx, ny in ((0.5, 0.5), (margin, margin), (1.0 - margin, margin), (margin, 1.0 - margin), (1.0 - margin, 1.0 - margin)):
            pts.append((int(round(left + nx * width)), int(round(top + ny * height))))
    return tuple(pts)


def _handle_validation_keys(
    *,
    key: int,
    hotkeys: list[int],
    desktop_point_buffer: deque[tuple[float, float]],
    target_point: tuple[int, int] | None,
    samples: list[ValidationSample],
    targets: tuple[tuple[int, int], ...],
    target_idx: int,
    canvas: VirtualCanvas,
    min_capture_frames: int,
    args: argparse.Namespace,
) -> tuple[bool, int, bool, dict[str, Any] | None, str]:
    all_keys = _merge_keys(key, hotkeys)
    if any(item in KEY_QUIT for item in all_keys if item >= 0 and item != 255):
        return (False, target_idx, False, None, "")
    effective_key = key
    if effective_key < 0 or effective_key == 255:
        for candidate in all_keys:
            if candidate in KEY_CALIBRATION_CLEAR | KEY_CALIBRATION_NEXT | KEY_CALIBRATION_CAPTURE | KEY_CALIBRATION_SAVE:
                effective_key = candidate
                break
    notice = ""
    if effective_key in KEY_CALIBRATION_CLEAR:
        samples.clear()
        desktop_point_buffer.clear()
        return (True, 0, False, None, "validation samples cleared")
    if effective_key in KEY_CALIBRATION_NEXT and targets:
        desktop_point_buffer.clear()
        return (True, (target_idx + 1) % len(targets), False, None, "next validation target")
    if effective_key in KEY_CALIBRATION_CAPTURE:
        if target_point is None:
            return (True, target_idx, False, None, "validation ignored: no target")
        if len(desktop_point_buffer) < max(1, int(min_capture_frames)):
            return (
                True,
                target_idx,
                False,
                None,
                f"validation waiting: need {max(1, int(min_capture_frames))} gaze frames",
            )
        predicted = _average_points(tuple(desktop_point_buffer))
        sample = _make_validation_sample(canvas, target_point, predicted)
        samples.append(sample)
        desktop_point_buffer.clear()
        next_idx = target_idx + 1
        if next_idx >= len(targets):
            summary = _validation_summary(samples, canvas)
            return (True, max(0, len(targets) - 1), True, summary, "validation complete")
        return (True, next_idx, False, None, f"validated {len(samples)} err={sample.error_px:.0f}px")
    if effective_key in KEY_CALIBRATION_SAVE or key in (10, 13):
        if samples:
            summary = _validation_summary(samples, canvas)
            return (True, target_idx, True, summary, "validation finalized")
        return (True, target_idx, False, None, "need validation samples")
    return (True, target_idx, False, None, notice)


def _average_points(points: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def _make_validation_sample(
    canvas: VirtualCanvas,
    target_point: tuple[int, int],
    predicted_point: tuple[float, float],
) -> ValidationSample:
    target_x, target_y = float(target_point[0]), float(target_point[1])
    pred_x, pred_y = float(predicted_point[0]), float(predicted_point[1])
    return ValidationSample(
        target_x=target_x,
        target_y=target_y,
        predicted_x=pred_x,
        predicted_y=pred_y,
        error_px=math.hypot(pred_x - target_x, pred_y - target_y),
        target_monitor=_monitor_index_for_point(canvas, target_x, target_y),
        predicted_monitor=_monitor_index_for_point(canvas, pred_x, pred_y),
    )


def _validation_summary(samples: list[ValidationSample], canvas: VirtualCanvas) -> dict[str, Any] | None:
    if not samples:
        return None
    errors = [sample.error_px for sample in samples]
    hits = [sample.monitor_hit for sample in samples]
    by_monitor: dict[str, dict[str, Any]] = {}
    for monitor in canvas.monitors:
        mon_samples = [sample for sample in samples if sample.target_monitor == monitor.index]
        if not mon_samples:
            continue
        mon_errors = [sample.error_px for sample in mon_samples]
        mon_hits = [sample.monitor_hit for sample in mon_samples]
        by_monitor[str(monitor.index)] = {
            **_error_summary(mon_errors),
            "monitor_accuracy": sum(1 for hit in mon_hits if hit) / len(mon_hits),
        }
    return {
        "sample_count": len(samples),
        "global": _error_summary(errors),
        "monitor_accuracy": sum(1 for hit in hits if hit) / len(hits),
        "by_monitor": by_monitor,
        "samples": [asdict(sample) for sample in samples],
    }


def _validation_summary_passes(summary: dict[str, Any] | None, args: argparse.Namespace) -> bool:
    if summary is None:
        return False
    global_summary = summary.get("global") or {}
    try:
        rms = float(global_summary.get("rms_px"))
        p95 = float(global_summary.get("p95_px"))
        monitor_accuracy = float(summary.get("monitor_accuracy"))
    except (TypeError, ValueError):
        return False
    if rms > float(args.validation_max_rms_px):
        return False
    if p95 > float(args.validation_max_p95_px):
        return False
    if monitor_accuracy < float(args.validation_min_monitor_accuracy):
        return False
    for item in (summary.get("by_monitor") or {}).values():
        try:
            if float(item.get("rms_px")) > float(args.validation_max_rms_px):
                return False
            if float(item.get("p95_px")) > float(args.validation_max_p95_px):
                return False
            if float(item.get("monitor_accuracy")) < float(args.validation_min_monitor_accuracy):
                return False
        except (TypeError, ValueError):
            return False
    return True


def _validation_notice(summary: dict[str, Any] | None, *, passed: bool) -> str:
    if summary is None:
        return "validation failed: no summary"
    global_summary = summary.get("global") or {}
    rms = float(global_summary.get("rms_px") or 0.0)
    p95 = float(global_summary.get("p95_px") or 0.0)
    monitor_accuracy = float(summary.get("monitor_accuracy") or 0.0) * 100.0
    status = "validation PASS" if passed else "validation FAIL: repite puntos malos"
    return f"{status} rms={rms:.0f}px p95={p95:.0f}px monitor={monitor_accuracy:.0f}%"


def _fit_validation_screen_warp(
    model: LinearGazeModel,
    samples: list[ValidationSample],
    canvas: VirtualCanvas,
    *,
    max_rms_px: float,
) -> tuple[LinearGazeModel | None, dict[str, Any] | None]:
    if len(samples) < 6:
        return (None, None)
    warp = fit_screen_warp(
        tuple((sample.predicted_x, sample.predicted_y, sample.target_x, sample.target_y) for sample in samples),
        degree=2,
    )
    if warp is None or warp.rms_error_px > float(max_rms_px):
        return (None, None)
    warped_model = with_screen_warp(model, warp)
    corrected_samples = [
        _make_validation_sample(
            canvas,
            (int(round(sample.target_x)), int(round(sample.target_y))),
            warp.apply(sample.predicted_x, sample.predicted_y),
        )
        for sample in samples
    ]
    return (warped_model, _validation_summary(corrected_samples, canvas))


def _bad_validation_targets(
    samples: list[ValidationSample],
    max_point_error_px: float,
    repeat_worst: int,
) -> tuple[tuple[int, int], ...]:
    if not samples:
        return tuple()
    bad = [
        sample
        for sample in samples
        if sample.error_px >= float(max_point_error_px) or not sample.monitor_hit
    ]
    if not bad:
        bad = sorted(samples, key=lambda sample: sample.error_px, reverse=True)[: max(1, int(repeat_worst))]
    else:
        bad = sorted(bad, key=lambda sample: (not sample.monitor_hit, sample.error_px), reverse=True)
    out: list[tuple[int, int]] = []
    for sample in bad[: max(1, int(repeat_worst))]:
        target = (int(round(sample.target_x)), int(round(sample.target_y)))
        if target not in out:
            out.append(target)
    return tuple(out)


def _actions_allowed(
    *,
    args: argparse.Namespace,
    active_model: LinearGazeModel | None,
    calibration_mode: bool,
    validation_mode: bool,
    calibration_validated: bool,
) -> bool:
    if calibration_mode or validation_mode:
        return False
    if not args.require_validation_for_actions:
        return True
    return active_model is not None and calibration_validated


def _action_block_reason(
    *,
    args: argparse.Namespace,
    active_model: LinearGazeModel | None,
    calibration_mode: bool,
    validation_mode: bool,
    calibration_validated: bool,
) -> str | None:
    if calibration_mode:
        return "calibrando"
    if validation_mode:
        return "validando"
    if not args.require_validation_for_actions:
        return None
    if active_model is None:
        return "sin perfil calibrado"
    if not calibration_validated:
        return "validacion no aprobada; usa --no-require-validation-for-actions para probar"
    return None


def _action_status_text(
    *,
    actions_requested: bool,
    actions_effective: bool,
    block_reason: str | None,
    candidate: WindowTarget | None,
    target: WindowTarget | None,
    hands: tuple[HandControlPose, ...],
) -> str:
    if not actions_requested:
        return "ACTIONS OFF: presiona . o relanza con --execute-actions"
    if not actions_effective:
        return f"ACTIONS BLOCKED: {block_reason or 'modo seguro'}"
    if target is None:
        if candidate is None:
            return "ACTIONS READY: mira una ventana hasta que aparezca armed target"
        return "ACTIONS READY: manten mirada estable 350ms para armar ventana"
    if not hands:
        return "ACTIONS READY: ventana armada; muestra mano para gesto"
    labels = ",".join(hand.label for hand in hands)
    return f"ACTIONS READY: target armado; gesto={labels}"


def _monitor_index_for_point(canvas: VirtualCanvas, x: float, y: float) -> int:
    containing = [
        monitor
        for monitor in canvas.monitors
        if monitor.rect.left <= x < monitor.rect.right and monitor.rect.top <= y < monitor.rect.bottom
    ]
    if containing:
        return containing[0].index
    nearest = min(
        canvas.monitors,
        key=lambda monitor: (monitor.rect.center[0] - x) ** 2 + (monitor.rect.center[1] - y) ** 2,
    )
    return nearest.index


def _error_summary(errors: list[float]) -> dict[str, Any]:
    if not errors:
        return {"count": 0, "rms_px": None, "mean_px": None, "p95_px": None, "max_px": None}
    arr = np.asarray(errors, dtype=float)
    return {
        "count": int(arr.size),
        "rms_px": float(np.sqrt(np.mean(arr * arr))),
        "mean_px": float(np.mean(arr)),
        "p95_px": float(np.percentile(arr, 95)),
        "max_px": float(np.max(arr)),
    }


def _handle_calibration_keys(
    *,
    key: int,
    hotkeys: list[int],
    head: HeadPointerEstimate | None,
    target_point: tuple[int, int] | None,
    samples: list[CalibrationSample],
    feature_buffer: deque[dict[str, float]],
    targets: tuple[tuple[int, int], ...],
    target_idx: int,
    min_samples: int,
    layout_hash: str,
    canvas: VirtualCanvas,
    camera_resolution: tuple[int, int] | None,
    store: CalibrationStore,
    user: str | None,
    merge_with_existing: bool,
    max_history_samples: int,
    max_merge_rms_px: float,
    min_capture_frames: int,
    max_capture_feature_jitter: float,
    min_capture_gaze_confidence: float,
) -> tuple[bool, int, LinearGazeModel | None, Path | None, str]:
    all_keys = _merge_keys(key, hotkeys)
    if any(item in KEY_QUIT for item in all_keys if item >= 0 and item != 255):
        return (False, target_idx, None, None, "")
    effective_key = key
    if effective_key < 0 or effective_key == 255:
        for candidate in all_keys:
            if candidate in KEY_CALIBRATION_CLEAR | KEY_CALIBRATION_NEXT | KEY_CALIBRATION_CAPTURE | KEY_CALIBRATION_SAVE:
                effective_key = candidate
                break
    saved_path = None
    model = None
    notice = ""
    if effective_key in KEY_CALIBRATION_CLEAR:
        samples.clear()
        feature_buffer.clear()
        notice = "samples cleared"
    elif effective_key in KEY_CALIBRATION_NEXT and targets:
        target_idx = (target_idx + 1) % len(targets)
        notice = "next target"
    elif effective_key in KEY_CALIBRATION_CAPTURE:
        if target_point is None:
            notice = "capture ignored: no target"
            return (True, target_idx, model, saved_path, notice)
        if head is None:
            notice = "capture rejected: no face/head detected"
            return (True, target_idx, model, saved_path, notice)
        if len(feature_buffer) < max(1, int(min_capture_frames)):
            notice = f"hold still: need {max(1, int(min_capture_frames))} stable frames"
            return (True, target_idx, model, saved_path, notice)
        if not _head_confident_for_online_learn(head, min_capture_gaze_confidence):
            notice = "capture rejected: low gaze confidence"
            return (True, target_idx, model, saved_path, notice)
        jitter = _feature_jitter(tuple(feature_buffer))
        if jitter > float(max_capture_feature_jitter):
            notice = f"capture rejected: unstable ({jitter:.3f})"
            return (True, target_idx, model, saved_path, notice)
        features = _average_features(feature_buffer) if feature_buffer else _head_features(head)
        samples.append(CalibrationSample(features=features, target_x=float(target_point[0]), target_y=float(target_point[1])))
        feature_buffer.clear()
        if targets:
            target_idx = (target_idx + 1) % len(targets)
        notice = f"captured {len(samples)}"
    elif effective_key in KEY_CALIBRATION_SAVE or key in (10, 13):
        if len(samples) >= max(6, int(min_samples)):
            current_samples = tuple(samples)
            current_model = fit_linear_model(current_samples)
            training_samples = current_samples
            model = current_model
            previous_count = 0
            merge_attempted = False
            if merge_with_existing:
                previous = store.load(layout_hash, user)
                if previous is not None and previous.samples:
                    previous_count = len(previous.samples)
                    merge_attempted = True
                    merged_samples = _merge_calibration_samples(
                        previous.samples,
                        current_samples,
                        max_samples=max_history_samples,
                    )
                    merged_model = fit_linear_model(merged_samples)
                    if (
                        merged_model is not None
                        and (model is None or merged_model.rms_error_px <= model.rms_error_px)
                    ):
                        model = merged_model
                        training_samples = merged_samples
            if model is not None:
                if model.rms_error_px > float(max_merge_rms_px):
                    return (
                        True,
                        target_idx,
                        None,
                        None,
                        f"save rejected: rms {model.rms_error_px:.1f}px > {max_merge_rms_px:.1f}px",
                    )
                # Per-monitor local correction: each monitor gets its own
                # predicted->target warp from its own samples, so a weak-signal
                # monitor (e.g. one placed below) stops smearing the others. Only
                # corrections that improve their monitor's RMS are kept.
                corrections = fit_monitor_corrections(model, training_samples, canvas)
                if corrections:
                    model = with_monitor_corrections(model, corrections)
                profile = CalibrationProfile(
                    user=user or getpass.getuser() or "default",
                    layout_hash=layout_hash,
                    samples=training_samples,
                    rms_error_px=model.rms_error_px,
                    model=model.to_dict(),
                    camera_resolution=camera_resolution,
                )
                saved_path = store.save(profile)
                if merge_attempted and len(training_samples) > len(current_samples):
                    merge_text = f"merged {previous_count}+{len(current_samples)} -> {len(training_samples)}"
                elif merge_attempted:
                    merge_text = f"merge skipped (current better) {len(current_samples)}"
                else:
                    merge_text = f"saved current {len(current_samples)}"
                return (False, target_idx, model, saved_path, f"{merge_text} | rms {model.rms_error_px:.1f}px")
            notice = "save failed: model fit returned none"
        else:
            notice = f"need >= {max(6, int(min_samples))} samples"
    return (True, target_idx, model, saved_path, notice)


def _set_cursor_pos(point: tuple[int, int]) -> None:
    if win32api is None:
        return
    try:
        win32api.SetCursorPos((int(point[0]), int(point[1])))
    except Exception:
        pass


def _has_capture_key(keys: list[int]) -> bool:
    return any(key in KEY_CALIBRATION_CAPTURE for key in keys if key >= 0 and key != 255)


def _merge_keys(primary_key: int, hotkeys: list[int]) -> list[int]:
    merged: list[int] = []
    if primary_key >= 0 and primary_key != 255:
        merged.append(primary_key)
    for key in hotkeys:
        if key >= 0 and key != 255 and key not in merged:
            merged.append(key)
    return merged


def _merge_calibration_samples(
    previous: tuple[CalibrationSample, ...],
    current: tuple[CalibrationSample, ...],
    *,
    max_samples: int,
) -> tuple[CalibrationSample, ...]:
    limit = max(1, int(max_samples))
    merged = tuple(previous) + tuple(current)
    if len(merged) <= limit:
        return merged
    return merged[-limit:]


def _head_confident_for_online_learn(head: HeadPointerEstimate, min_confidence: float) -> bool:
    if head.gaze is None:
        return False
    confidence = float(getattr(head.gaze, "confidence", 0.0))
    return math.isfinite(confidence) and confidence >= float(min_confidence)


def _save_calibration_profile(
    *,
    store: CalibrationStore,
    layout_hash: str,
    user: str | None,
    samples: tuple[CalibrationSample, ...],
    model: LinearGazeModel,
) -> Path:
    profile = CalibrationProfile(
        user=user or getpass.getuser() or "default",
        layout_hash=layout_hash,
        samples=samples,
        rms_error_px=model.rms_error_px,
        model=model.to_dict(),
    )
    return store.save(profile)


def _save_calibration_debug_capture(
    *,
    frame: Any,
    output_dir: Path,
    index: int,
    mode: str,
    notice: str,
    target_point: tuple[int, int] | None,
    desktop_point: tuple[float, float] | None,
    head: HeadPointerEstimate | None,
    canvas: VirtualCanvas,
    sample_count_before: int,
    sample_count_after: int,
    validation_sample: ValidationSample | None,
) -> tuple[Path, Path] | None:
    import cv2

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stem = f"{index:04d}_{stamp}_{mode}"
    png_path = output_dir / f"{stem}.png"
    json_path = output_dir / f"{stem}.json"
    try:
        cv2.imwrite(str(png_path), frame)
    except Exception:
        return None
    target_monitor = None
    if target_point is not None:
        target_monitor = _monitor_index_for_point(canvas, float(target_point[0]), float(target_point[1]))
    predicted_monitor = None
    if desktop_point is not None:
        predicted_monitor = _monitor_index_for_point(canvas, float(desktop_point[0]), float(desktop_point[1]))
    payload = {
        "created_at": datetime.now().isoformat(timespec="milliseconds"),
        "mode": mode,
        "notice": notice,
        "image_path": str(png_path),
        "target_point": list(target_point) if target_point is not None else None,
        "target_monitor": target_monitor,
        "predicted_point": list(desktop_point) if desktop_point is not None else None,
        "predicted_monitor": predicted_monitor,
        "sample_count_before": sample_count_before,
        "sample_count_after": sample_count_after,
        "sample_saved": sample_count_after > sample_count_before,
        "head": _head_debug_payload(head),
        "validation_sample": asdict(validation_sample) if validation_sample is not None else None,
        "canvas": canvas_to_dict(canvas),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return (png_path, json_path)


def _head_debug_payload(head: HeadPointerEstimate | None) -> dict[str, Any] | None:
    if head is None:
        return None
    gaze = None
    if head.gaze is not None:
        gaze = {
            "x": head.gaze.x,
            "y": head.gaze.y,
            "confidence": head.gaze.confidence,
            "left_x": head.gaze.left_x,
            "left_y": head.gaze.left_y,
            "right_x": head.gaze.right_x,
            "right_y": head.gaze.right_y,
        }
    return {
        "yaw": head.yaw,
        "pitch": head.pitch,
        "raw_x": head.raw_x,
        "raw_y": head.raw_y,
        "filtered_x": head.filtered_x,
        "filtered_y": head.filtered_y,
        "monitor_index": head.monitor.index,
        "monitor_device": head.monitor.device,
        "region": head.region,
        "source": head.source,
        "local_x": head.local_x,
        "local_y": head.local_y,
        "features": _head_features(head),
        "gaze": gaze,
    }


def _online_retrain_from_clicks(
    *,
    store: CalibrationStore,
    layout_hash: str,
    user: str | None,
    loaded_model: LinearGazeModel | None,
    active_model: LinearGazeModel | None,
    recent_samples: tuple[CalibrationSample, ...],
    max_total_samples: int,
    max_rms_px: float,
) -> tuple[LinearGazeModel | None, LinearGazeModel | None, bool]:
    if len(recent_samples) < 6:
        return active_model, loaded_model, False
    previous = store.load(layout_hash, user)
    previous_samples = previous.samples if previous is not None else ()
    merged_samples = _merge_calibration_samples(previous_samples, recent_samples, max_samples=max_total_samples)
    model = fit_linear_model(merged_samples, feature_keys=ONLINE_FEATURE_KEYS, robust_trim_quantile=0.78, robust_passes=3)
    if model is None:
        return active_model, loaded_model, False
    if model.rms_error_px > float(max_rms_px):
        return active_model, loaded_model, False
    baseline_rms = loaded_model.rms_error_px if loaded_model is not None else float("inf")
    if active_model is not None:
        baseline_rms = min(baseline_rms, active_model.rms_error_px)
    if math.isfinite(baseline_rms) and model.rms_error_px > baseline_rms * 1.05:
        return active_model, loaded_model, False
    profile = CalibrationProfile(
        user=user or getpass.getuser() or "default",
        layout_hash=layout_hash,
        samples=merged_samples,
        rms_error_px=model.rms_error_px,
        model=model.to_dict(),
    )
    store.save(profile)
    return model, model, True


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _should_quit(keys: list[int]) -> bool:
    return any(key in KEY_QUIT for key in keys if key >= 0 and key != 255)


def _write_report(report: dict[str, Any], report_path: Path | None) -> None:
    base = report_path
    if base is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = CAMERA_DATA_DIR / "reports" / f"phase1_window_control_{stamp}.json"
    base.parent.mkdir(parents=True, exist_ok=True)
    json_path = base if base.suffix.lower() == ".json" else base.with_suffix(".json")
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemma 4 camera window-control Phase 1 POC")
    parser.add_argument("--camera-index", type=int, default=DEFAULT_CAMERA_INDEX)
    parser.add_argument("--camera-backend", choices=("any", "dshow", "msmf"), default=DEFAULT_CAMERA_BACKEND)
    parser.add_argument("--quiet-runtime-logs", dest="quiet_runtime_logs", action="store_true", default=True)
    parser.add_argument("--verbose-runtime-logs", dest="quiet_runtime_logs", action="store_false")
    parser.add_argument("--list-cameras", action="store_true")
    parser.add_argument("--camera-scan-limit", type=int, default=8)
    parser.add_argument("--width", type=int, default=DEFAULT_CAMERA_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_CAMERA_HEIGHT)
    parser.add_argument("--camera-fps", type=int, default=30)
    # The cursor follows the HEAD, so the face model must run every frame here —
    # face_every_n>1 only updated the cursor every Nth frame (the dominant cause
    # of "laggy/steppy" tracking: at ~15 FPS, n=4 refreshed the cursor ~4x/sec).
    # The POC (measurement-only) can still skip frames; window control should not.
    parser.add_argument("--face-every-n", type=int, default=1)
    parser.add_argument("--iris-refine", dest="iris_refine", action="store_true", default=True)
    parser.add_argument("--no-iris-refine", dest="iris_refine", action="store_false")
    parser.add_argument("--gaze-gain-x", type=float, default=0.62)
    parser.add_argument("--gaze-gain-y", type=float, default=0.42)
    parser.add_argument("--gaze-deadzone", type=float, default=0.025)
    parser.add_argument("--no-auto-center", action="store_true", help="Disable adaptive center for camera placement.")
    parser.add_argument("--auto-center-alpha", type=float, default=0.03)
    # Responsiveness of the cursor. alpha is the EMA catch-up fraction per frame
    # (higher = snappier, lower = smoother but laggier); max-step caps per-frame
    # travel before the EMA. The old 0.16 / 180px felt sluggish: at ~15 FPS the
    # cursor needed many frames to reach a new target and was speed-capped across
    # the desktop. 0.45 / 600px tracks the head with little perceptible lag while
    # the one-euro filter upstream still absorbs jitter.
    parser.add_argument("--gaze-smooth-alpha", type=float, default=0.45)
    parser.add_argument("--gaze-max-step-px", type=float, default=600.0)
    parser.add_argument("--use-calibration", dest="use_calibration", action="store_true", default=True)
    parser.add_argument("--no-use-calibration", dest="use_calibration", action="store_false")
    parser.add_argument("--reset-calibration-history", action="store_true")
    parser.add_argument("--run-calibration", action="store_true", help="Collect gaze samples and save a calibrated model.")
    parser.add_argument("--control-after-calibration", dest="control_after_calibration", action="store_true", default=True)
    parser.add_argument("--no-control-after-calibration", dest="control_after_calibration", action="store_false")
    parser.add_argument("--merge-calibration-history", dest="merge_calibration_history", action="store_true", default=True)
    parser.add_argument("--no-merge-calibration-history", dest="merge_calibration_history", action="store_false")
    parser.add_argument("--calibration-history-max-samples", type=int, default=1200)
    parser.add_argument("--calibration-min-samples", type=int, default=18)
    parser.add_argument("--calibration-avg-frames", type=int, default=8)
    parser.add_argument("--calibration-min-capture-frames", type=int, default=4)
    parser.add_argument("--calibration-max-feature-jitter", type=float, default=0.040)
    parser.add_argument("--calibration-min-gaze-confidence", type=float, default=0.60)
    parser.add_argument("--calibration-max-rms-px", type=float, default=350.0)
    parser.add_argument("--calibration-user", type=str, default=None)
    parser.add_argument("--validate-after-calibration", dest="validate_after_calibration", action="store_true", default=True)
    parser.add_argument("--no-validate-after-calibration", dest="validate_after_calibration", action="store_false")
    parser.add_argument("--require-validation-for-actions", dest="require_validation_for_actions", action="store_true", default=True)
    parser.add_argument("--no-require-validation-for-actions", dest="require_validation_for_actions", action="store_false")
    parser.add_argument("--validation-points-per-monitor", type=int, choices=(5, 9), default=5)
    parser.add_argument("--validation-avg-frames", type=int, default=8)
    parser.add_argument("--validation-min-capture-frames", type=int, default=4)
    parser.add_argument("--validation-max-rms-px", type=float, default=220.0)
    parser.add_argument("--validation-max-p95-px", type=float, default=380.0)
    parser.add_argument("--validation-min-monitor-accuracy", type=float, default=0.95)
    parser.add_argument("--validation-max-point-error-px", type=float, default=520.0)
    parser.add_argument("--validation-repeat-worst", type=int, default=8)
    parser.add_argument(
        "--validation-max-retries",
        type=int,
        default=1,
        help="How many failed validation rounds can send you back to repeat bad points before falling back to SAFE mode.",
    )
    parser.add_argument("--fine-screen-warp", dest="fine_screen_warp", action="store_true", default=True)
    parser.add_argument("--no-fine-screen-warp", dest="fine_screen_warp", action="store_false")
    parser.add_argument("--fine-screen-warp-max-rms-px", type=float, default=180.0)
    parser.add_argument(
        "--save-calibration-debug-captures",
        action="store_true",
        help="Opt-in privacy debug: save one camera PNG + JSON metadata for each Space/s calibration or validation capture.",
    )
    parser.add_argument("--debug-capture-dir", type=Path, default=Path("test") / "eye_tracking_captures")
    parser.add_argument("--auto-online-learn", action="store_true", help="Disabled/no-op for now; kept only for CLI compatibility.")
    parser.add_argument("--online-learn-min-gaze-confidence", type=float, default=0.62)
    parser.add_argument("--online-learn-min-samples", type=int, default=18)
    parser.add_argument("--online-learn-retrain-every", type=int, default=8)
    parser.add_argument("--online-learn-max-new-samples", type=int, default=240)
    parser.add_argument("--online-learn-click-lag-ms", type=float, default=130.0)
    parser.add_argument("--online-learn-window-ms", type=float, default=180.0)
    parser.add_argument("--online-learn-max-feature-jitter", type=float, default=0.050)
    parser.add_argument("--online-learn-max-click-distance-px", type=float, default=340.0)
    parser.add_argument("--online-learn-history-max-frames", type=int, default=120)
    parser.add_argument("--duration", type=float, default=0.0, help="Seconds to run; 0 means until q/esc.")
    parser.add_argument("--no-window", action="store_true")
    parser.add_argument("--mirror", dest="mirror", action="store_true", default=True)
    parser.add_argument("--no-mirror", dest="mirror", action="store_false")
    parser.add_argument("--download-models", action="store_true")
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument("--num-hands", type=int, default=2)
    parser.add_argument("--min-confidence", type=float, default=0.5)
    parser.add_argument("--stabilizer-window", type=int, default=3, help=argparse.SUPPRESS)
    parser.add_argument("--gesture-enter-frames", type=int, default=2)
    parser.add_argument("--gesture-exit-frames", type=int, default=2)
    parser.add_argument("--gesture-min-confidence", type=float, default=0.50)
    parser.add_argument("--hand-min-score", type=float, default=0.45)
    parser.add_argument("--hand-edge-margin", type=float, default=0.035)
    parser.add_argument("--hand-max-jump-norm", type=float, default=0.28)
    parser.add_argument("--hand-min-palm-size", type=float, default=0.035)
    parser.add_argument("--hand-max-palm-size", type=float, default=0.55)
    parser.add_argument("--hand-min-two-hand-distance", type=float, default=0.085)
    parser.add_argument("--target-stable-ms", type=int, default=350)
    parser.add_argument("--target-search-radius-px", type=int, default=220)
    parser.add_argument("--target-foreground-fallback", dest="target_foreground_fallback", action="store_true", default=True)
    parser.add_argument("--no-target-foreground-fallback", dest="target_foreground_fallback", action="store_false")
    parser.add_argument("--execute-actions", action="store_true")
    parser.add_argument("--drag-gain-x-px", type=float, default=2600.0)
    parser.add_argument("--drag-gain-y-px", type=float, default=1500.0)
    parser.add_argument("--drag-smoothing-alpha", type=float, default=0.45)
    parser.add_argument("--drag-max-step-px", type=int, default=180)
    parser.add_argument("--scroll-threshold-norm", type=float, default=0.035)
    parser.add_argument("--scroll-gain", type=float, default=3600.0)
    parser.add_argument("--scroll-rearm-threshold-norm", type=float, default=0.012)
    parser.add_argument("--scroll-min-wheel-delta", type=int, default=120)
    parser.add_argument("--scroll-max-wheel-delta", type=int, default=360)
    parser.add_argument("--resize-ratio-smoothing-alpha", type=float, default=0.30)
    parser.add_argument("--resize-step-px", type=int, default=24)
    parser.add_argument("--maximize-ratio", type=float, default=1.55)
    parser.add_argument("--restore-ratio", type=float, default=0.65)
    parser.add_argument("--two-hand-zoom-step-ratio", type=float, default=0.12)
    parser.add_argument("--two-hand-zoom-cooldown-s", type=float, default=0.22)
    parser.add_argument("--point-click-cooldown-s", type=float, default=0.70)
    parser.add_argument("--point-snap-radius-px", type=int, default=320)
    parser.add_argument("--point-tap-threshold-norm", type=float, default=0.14)
    parser.add_argument("--point-tap-release-norm", type=float, default=0.055)
    parser.add_argument("--window-snap", dest="window_snap", action="store_true", default=True)
    parser.add_argument("--no-window-snap", dest="window_snap", action="store_false")
    parser.add_argument("--window-snap-edge-px", type=int, default=72)
    parser.add_argument("--event-log-size", type=int, default=80)
    parser.add_argument("--show-gaze-pointer", dest="show_gaze_pointer", action="store_true", default=True)
    parser.add_argument("--no-gaze-pointer", dest="show_gaze_pointer", action="store_false")
    parser.add_argument("--show-desktop-map", dest="show_desktop_map", action="store_true", default=True)
    parser.add_argument("--no-desktop-map", dest="show_desktop_map", action="store_false")
    parser.add_argument("--show-desktop-gaze-dot", dest="show_desktop_gaze_dot", action="store_true", default=True)
    parser.add_argument("--no-desktop-gaze-dot", dest="show_desktop_gaze_dot", action="store_false")
    parser.add_argument("--desktop-gaze-dot-size", type=int, default=44)
    parser.add_argument("--show-system-gaze-pointer", dest="show_system_gaze_pointer", action="store_true", default=False)
    parser.add_argument("--no-system-gaze-pointer", dest="show_system_gaze_pointer", action="store_false")
    parser.add_argument(
        "--global-hotkeys",
        action="store_true",
        help="Listen for q/Esc globally even if OpenCV window is unfocused.",
    )
    parser.add_argument("--report-path", type=Path, default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
