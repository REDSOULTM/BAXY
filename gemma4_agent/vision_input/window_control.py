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
from .config import parse_args
from .calibration_flow import (
    ValidationSample,
    _bad_validation_targets,
    _validation_summary,
    _validation_summary_passes,
    _validation_notice,
    _fit_validation_screen_warp,
    _handle_calibration_keys,
    _handle_validation_keys,
    _save_calibration_profile,
    _save_calibration_debug_capture,
    _online_retrain_from_clicks,
    _make_validation_sample,
    _average_points,
    _head_confident_for_online_learn,
    _merge_calibration_samples,
    _merge_keys,
    _has_capture_key,
    _set_cursor_pos,
    _head_features,
    _error_summary,
    _monitor_index_for_point,
    _head_debug_payload,
    _sample_from_click_history,
    _append_online_feature_snapshot,
)
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


from .config import (
    KEY_QUIT,
    KEY_TOGGLE_EXECUTE,
    KEY_TOGGLE_CALIBRATION,
    KEY_RESTART_CALIBRATION,
    KEY_CALIBRATION_CAPTURE,
    KEY_CALIBRATION_SAVE,
    KEY_CALIBRATION_NEXT,
    KEY_CALIBRATION_CLEAR,
    ONLINE_FEATURE_KEYS,
)
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
from .renderer import DesktopGazeDot, draw_overlay

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
            
        try:
            import win32gui
            fg = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(fg)
            # Only process hotkeys if our OpenCV window is focused
            if title != "Vision Input":
                return []
        except Exception:
            pass
            
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
    args = parse_args(argv)
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
    # Enabled per HCI Best Practices plan
    auto_online_learn_enabled = True
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
        last_face = None
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
                camera_width=camera_config.width,
                camera_height=camera_config.height,
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
                    face=last_face,
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
                annotated = draw_overlay(
                    frame=bgr.copy(),
                    landmarks=landmarks,
                    head=head,
                    hands=hands,
                    candidate=candidate,
                    target=target,
                    state=output_state,
                    events=output_events,
                    camera_label=camera_label,
                    execute_actions=effective_execute,
                    actions_requested=execute_actions_live,
                    action_status=_action_status_text(
                        actions_requested=execute_actions_live,
                        actions_effective=effective_execute,
                        block_reason=action_block_reason,
                        candidate=candidate,
                        target=target,
                        hands=hands,
                    ),
                    canvas=canvas,
                    show_gaze_pointer=args.show_gaze_pointer,
                    show_desktop_map=args.show_desktop_map,
                    desktop_point=desktop_point,
                    calibration_text=_calibration_status_text(
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

    # --- PRE-COMPUTE FACE EXCLUSION ZONE (once, not per hand) ---
    face_box: tuple[float, float, float, float] | None = None
    if landmarks.primary_face is not None:
        face_pts = landmarks.primary_face.landmarks
        if face_pts:
            min_x = min(p.x for p in face_pts)
            max_x = max(p.x for p in face_pts)
            min_y = min(p.y for p in face_pts)
            max_y = max(p.y for p in face_pts)
            pad_x = (max_x - min_x) * 0.3
            pad_y = (max_y - min_y) * 0.3
            face_box = (min_x - pad_x, min_y - pad_y, max_x + pad_x, max_y + pad_y)
    # -----------------------------------------------------------

    for track_id, hand in assigned[: max(1, int(max_hands))]:
        index_tip = _hand_landmark_xyz(hand, 8)
        palm = _hand_palm_xyz(hand)
        other_centers = tuple(center for other_id, center in centers.items() if other_id != track_id)
        quality = quality_gate.evaluate(track_id, hand, other_centers=other_centers)
        prev_label = gesture_filter.get_stable_label(track_id)
        raw = recognize_hand_gesture(hand, previous_label=prev_label)

        # --- FACE EXCLUSION ZONE ---
        face_blocked = False
        if face_box is not None and palm[0] is not None and palm[1] is not None:
            if face_box[0] <= palm[0] <= face_box[2] and face_box[1] <= palm[1] <= face_box[3]:
                raw = type(raw)("none", 1.0, raw.pinch_distance, raw.finger_extended, raw.finger_flexed)
                face_blocked = True
        # ---------------------------

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
                raw.pinch_distance,
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
