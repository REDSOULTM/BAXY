from collections import deque

import numpy as np

from gemma4_agent.vision_input.calibration import CalibrationSample
from gemma4_agent.vision_input.controller import (
    CameraControlState,
    FixedGestureWindowController,
    HandControlPose,
    WindowActuator,
    WindowControlConfig,
)
from gemma4_agent.vision_input.calibration import LinearGazeModel
from gemma4_agent.vision_input.gaze import IrisGazeEstimate
from gemma4_agent.vision_input.monitors import MonitorInfo, MonitorRect, VirtualCanvas
from gemma4_agent.vision_input.pointer import HeadPointerEstimate
from gemma4_agent.vision_input.hand_quality import GestureStateFilter, HandIdentityTracker, HandQualityGate
from gemma4_agent.vision_input.landmarks import HandSample, LandmarkFrame, NormalizedPoint
from gemma4_agent.vision_input.window_control import (
    _average_features,
    _action_block_reason,
    _action_status_text,
    _bad_validation_targets,
    _candidate_window,
    _control_hands,
    _desktop_point,
    _feature_jitter,
    _frame_point_from_head,
    _handle_calibration_keys,
    _has_capture_key,
    _make_validation_sample,
    _merge_calibration_samples,
    _parse_args,
    _save_calibration_debug_capture,
    _sample_from_click_history,
    _smooth_point,
    _validation_summary,
    _validation_summary_passes,
)
from gemma4_agent.vision_input.window_target import WindowRect, WindowTarget, WindowTargetStabilizer


def _target() -> WindowTarget:
    return WindowTarget(
        hwnd=123,
        title="Test Window",
        class_name="TestClass",
        rect=WindowRect(100, 100, 900, 700),
        visible=True,
        iconic=False,
    )


def _controller() -> FixedGestureWindowController:
    config = WindowControlConfig(execute_actions=False, drag_gain_x_px=1000.0, drag_gain_y_px=1000.0)
    actuator = WindowActuator(
        execute=False,
        desktop_rect=MonitorRect(0, 0, 1920, 1080),
        monitors=(MonitorRect(0, 0, 1920, 1080),),
    )
    return FixedGestureWindowController(config, actuator)


def _hand_sample(cx: float, cy: float, *, score: float = 0.9) -> HandSample:
    pts = [NormalizedPoint(cx, cy, 0.0) for _ in range(21)]
    pts[0] = NormalizedPoint(cx, cy + 0.05, 0.0)
    pts[5] = NormalizedPoint(cx - 0.05, cy, 0.0)
    pts[9] = NormalizedPoint(cx, cy - 0.06, 0.0)
    pts[13] = NormalizedPoint(cx + 0.04, cy, 0.0)
    pts[17] = NormalizedPoint(cx + 0.08, cy, 0.0)
    pts[4] = NormalizedPoint(cx - 0.12, cy + 0.05, 0.0)
    pts[6] = NormalizedPoint(cx, cy - 0.12, 0.0)
    pts[8] = NormalizedPoint(cx, cy - 0.25, 0.0)
    pts[10] = NormalizedPoint(cx + 0.04, cy - 0.03, 0.0)
    pts[12] = NormalizedPoint(cx + 0.02, cy + 0.04, 0.0)
    pts[14] = NormalizedPoint(cx + 0.08, cy - 0.02, 0.0)
    pts[16] = NormalizedPoint(cx + 0.06, cy + 0.04, 0.0)
    pts[18] = NormalizedPoint(cx + 0.12, cy - 0.02, 0.0)
    pts[20] = NormalizedPoint(cx + 0.10, cy + 0.04, 0.0)
    return HandSample(tuple(pts), score=score)


def _point_pose(offset_y: float, offset_z: float = 0.0) -> HandControlPose:
    return HandControlPose(
        0.5,
        0.5,
        "point",
        index_tip_x=0.5,
        index_tip_y=0.5 + offset_y,
        index_tip_z=offset_z,
        palm_x=0.5,
        palm_y=0.5,
        palm_z=0.0,
    )


def test_window_target_stabilizer_requires_dwell() -> None:
    target = _target()
    stabilizer = WindowTargetStabilizer(stable_ms=350)

    assert stabilizer.update(target, 10.0) is None
    assert stabilizer.update(target, 10.2) is None
    assert stabilizer.update(target, 10.4) == target


def test_fist_grabs_and_moves_window_in_safe_mode() -> None:
    controller = _controller()
    target = _target()

    first = controller.update(
        timestamp_s=1.0,
        target=target,
        hands=(HandControlPose(0.5, 0.5, "fist"),),
        pointer_xy=(500, 400),
    )
    second = controller.update(
        timestamp_s=1.1,
        target=target,
        hands=(HandControlPose(0.6, 0.55, "fist"),),
        pointer_xy=(500, 400),
    )

    assert first.state == CameraControlState.DRAGGING
    assert first.events[0].name == "grab_window"
    assert second.events[0].name == "move_window"
    assert second.events[0].executed is False


def test_open_palm_ends_drag() -> None:
    controller = _controller()
    target = _target()

    controller.update(
        timestamp_s=1.0,
        target=target,
        hands=(HandControlPose(0.5, 0.5, "fist"),),
        pointer_xy=(500, 400),
    )
    out = controller.update(
        timestamp_s=1.1,
        target=target,
        hands=(HandControlPose(0.5, 0.5, "palm"),),
        pointer_xy=(500, 400),
    )

    assert out.state == CameraControlState.ARMED
    assert out.events[0].name == "drop_window"


def test_two_hands_zoom_content() -> None:
    controller = _controller()
    target = _target()

    start = controller.update(
        timestamp_s=1.0,
        target=target,
        hands=(HandControlPose(0.4, 0.5, "palm"), HandControlPose(0.6, 0.5, "palm")),
        pointer_xy=(500, 400),
    )
    zoomed = controller.update(
        timestamp_s=1.3,
        target=target,
        hands=(HandControlPose(0.3, 0.5, "palm"), HandControlPose(0.7, 0.5, "palm")),
        pointer_xy=(500, 400),
    )

    assert start.state == CameraControlState.RESIZING
    assert start.events[0].name == "two_hand_start"
    assert any(event.name == "zoom_in" for event in zoomed.events)


def test_two_hands_do_not_move_window_with_center_motion() -> None:
    controller = _controller()
    target = _target()

    controller.update(
        timestamp_s=1.0,
        target=target,
        hands=(HandControlPose(0.4, 0.5, "palm"), HandControlPose(0.6, 0.5, "palm")),
        pointer_xy=(500, 400),
    )
    moved = controller.update(
        timestamp_s=1.3,
        target=target,
        hands=(HandControlPose(0.5, 0.5, "palm"), HandControlPose(0.7, 0.5, "palm")),
        pointer_xy=(500, 400),
    )

    assert not any(event.name == "two_hand_move_window" for event in moved.events)
    assert not any(event.name == "move_window" for event in moved.events)


def test_fist_drag_snaps_to_left_monitor_half() -> None:
    controller = _controller()
    target = _target()

    controller.update(
        timestamp_s=1.0,
        target=target,
        hands=(HandControlPose(0.5, 0.5, "fist"),),
        pointer_xy=(500, 400),
    )
    moved = controller.update(
        timestamp_s=1.1,
        target=target,
        hands=(HandControlPose(-0.2, 0.5, "fist"),),
        pointer_xy=(500, 400),
    )

    assert moved.events[0].name == "move_window"
    assert moved.events[0].detail.startswith("snap left move to 0,0 960x1080")


def test_point_gesture_clicks_once_until_released() -> None:
    controller = _controller()
    target = _target()

    armed = controller.update(
        timestamp_s=1.0,
        target=target,
        hands=(_point_pose(-0.18),),
        pointer_xy=(500, 400),
    )
    clicked = controller.update(
        timestamp_s=1.1,
        target=target,
        hands=(_point_pose(0.00),),
        pointer_xy=(500, 400),
    )
    held = controller.update(
        timestamp_s=1.3,
        target=target,
        hands=(_point_pose(0.02),),
        pointer_xy=(500, 400),
    )
    retracted = controller.update(
        timestamp_s=1.4,
        target=target,
        hands=(_point_pose(-0.17),),
        pointer_xy=(500, 400),
    )

    assert armed.events[0].name == "point_armed"
    assert clicked.events[0].name == "point_click"
    assert clicked.events[0].executed is False
    assert held.events == ()
    assert retracted.events == ()


def test_point_gesture_has_priority_over_non_two_hand_combo() -> None:
    controller = _controller()
    target = _target()

    armed = controller.update(
        timestamp_s=1.0,
        target=target,
        hands=(HandControlPose(0.2, 0.5, "palm"), _point_pose(-0.18)),
        pointer_xy=(500, 400),
    )
    clicked = controller.update(
        timestamp_s=1.1,
        target=target,
        hands=(HandControlPose(0.2, 0.5, "palm"), _point_pose(0.00)),
        pointer_xy=(500, 400),
    )

    assert armed.events[0].name == "point_armed"
    assert clicked.events[0].name == "point_click"


def test_two_hand_requires_manipulation_labels() -> None:
    controller = _controller()
    target = _target()

    out = controller.update(
        timestamp_s=1.0,
        target=target,
        hands=(HandControlPose(0.4, 0.5, "unknown"), HandControlPose(0.6, 0.5, "palm")),
        pointer_xy=(500, 400),
    )

    assert out.state == CameraControlState.ARMED
    assert out.events == ()


def test_control_hands_blocks_edge_hand_quality() -> None:
    frame = LandmarkFrame(1, (_hand_sample(0.01, 0.5),), (), "test")

    hands = _control_hands(
        frame,
        HandIdentityTracker(),
        HandQualityGate(),
        GestureStateFilter(enter_frames=1, exit_frames=1),
        max_hands=1,
    )

    assert hands[0].quality_ok is False
    assert hands[0].quality_reason == "edge"
    assert hands[0].label == "none"


def test_control_hands_applies_gesture_enter_hysteresis() -> None:
    frame = LandmarkFrame(1, (_hand_sample(0.5, 0.5),), (), "test")
    tracker = HandIdentityTracker()
    quality = HandQualityGate()
    filt = GestureStateFilter(enter_frames=2, exit_frames=1)

    first = _control_hands(frame, tracker, quality, filt, max_hands=1)
    second = _control_hands(frame, tracker, quality, filt, max_hands=1)

    assert first[0].raw_label == "point"
    assert first[0].label == "none"
    assert second[0].label == "point"


def test_palm_vertical_motion_scrolls_window() -> None:
    controller = _controller()
    target = _target()

    start = controller.update(
        timestamp_s=1.0,
        target=target,
        hands=(HandControlPose(0.5, 0.5, "palm"),),
        pointer_xy=(500, 400),
    )
    scroll = controller.update(
        timestamp_s=1.1,
        target=target,
        hands=(HandControlPose(0.5, 0.44, "palm"),),
        pointer_xy=(500, 400),
    )

    assert start.events[0].name == "scroll_start"
    assert scroll.events[0].name == "scroll_window"
    assert "wheel -" in scroll.events[0].detail


def test_palm_scroll_ignores_clutch_return_motion() -> None:
    controller = _controller()
    target = _target()

    controller.update(
        timestamp_s=1.0,
        target=target,
        hands=(HandControlPose(0.5, 0.5, "palm"),),
        pointer_xy=(500, 400),
    )
    first_stroke = controller.update(
        timestamp_s=1.1,
        target=target,
        hands=(HandControlPose(0.5, 0.56, "palm"),),
        pointer_xy=(500, 400),
    )
    return_motion = controller.update(
        timestamp_s=1.2,
        target=target,
        hands=(HandControlPose(0.5, 0.44, "palm"),),
        pointer_xy=(500, 400),
    )
    second_stroke = controller.update(
        timestamp_s=1.3,
        target=target,
        hands=(HandControlPose(0.5, 0.50, "palm"),),
        pointer_xy=(500, 400),
    )

    assert first_stroke.events[0].name == "scroll_window"
    assert "wheel " in first_stroke.events[0].detail
    assert "-" not in first_stroke.events[0].detail
    assert return_motion.events == ()
    assert second_stroke.events[0].name == "scroll_window"
    assert "-" not in second_stroke.events[0].detail


def test_drag_holds_position_when_fist_tracking_flickers_unknown() -> None:
    controller = _controller()
    target = _target()

    controller.update(
        timestamp_s=1.0,
        target=target,
        hands=(HandControlPose(0.5, 0.5, "fist"),),
        pointer_xy=(500, 400),
    )
    flicker = controller.update(
        timestamp_s=1.1,
        target=target,
        hands=(HandControlPose(0.8, 0.8, "unknown"),),
        pointer_xy=(500, 400),
    )
    moved = controller.update(
        timestamp_s=1.2,
        target=target,
        hands=(HandControlPose(0.65, 0.55, "fist"),),
        pointer_xy=(500, 400),
    )

    assert flicker.state == CameraControlState.DRAGGING
    assert flicker.events == ()
    assert moved.events[0].name == "move_window"


def test_frame_point_from_head_clamps_bounds() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    head = HeadPointerEstimate(
        yaw=0.0,
        pitch=0.0,
        raw_x=10.0,
        raw_y=20.0,
        filtered_x=10.0,
        filtered_y=20.0,
        monitor=MonitorInfo(0, MonitorRect(0, 0, 100, 100)),
        region="middle-center",
        source="head+iris",
        local_x=1.2,
        local_y=-0.2,
        gaze=IrisGazeEstimate(0.0, 0.0, 1.0),
    )
    assert _frame_point_from_head(frame, head) == (639, 0)
    assert _frame_point_from_head(frame, None) is None


def test_desktop_point_falls_back_when_model_returns_nan() -> None:
    model = LinearGazeModel(
        feature_keys=("yaw", "pitch", "gaze_x", "gaze_y"),
        coeffs_x=(float("nan"), 0.0, 0.0, 0.0, 0.0),
        coeffs_y=(0.0, 0.0, 0.0, 0.0, 0.0),
        rms_error_px=0.0,
    )
    head = HeadPointerEstimate(
        yaw=0.0,
        pitch=0.0,
        raw_x=100.0,
        raw_y=120.0,
        filtered_x=101.0,
        filtered_y=121.0,
        monitor=MonitorInfo(0, MonitorRect(0, 0, 1920, 1080)),
        region="middle-center",
        source="head",
        local_x=0.5,
        local_y=0.5,
        gaze=IrisGazeEstimate(0.0, 0.0, 1.0),
    )
    pt = _desktop_point(
        head,
        model,
        type("Canvas", (), {"rect": MonitorRect(0, 0, 1920, 1080)})(),  # Minimal canvas shape for helper.
        1.0,
        type("Filter", (), {"filter": lambda self, value, _: value})(),
        type("Filter", (), {"filter": lambda self, value, _: value})(),
    )
    assert pt == (101.0, 121.0)


def test_average_features_smooths_buffer() -> None:
    buf = deque(
        [
            {"yaw": 0.1, "pitch": -0.1, "gaze_x": 0.02, "gaze_y": -0.02},
            {"yaw": 0.3, "pitch": 0.1, "gaze_x": 0.06, "gaze_y": 0.02},
        ]
    )
    out = _average_features(buf)
    assert out["yaw"] == 0.2
    assert out["pitch"] == 0.0
    assert out["gaze_x"] == 0.04
    assert out["gaze_y"] == 0.0


def test_window_control_args_enable_desktop_pointer_defaults() -> None:
    args = _parse_args([])
    assert args.quiet_runtime_logs is True
    assert args.merge_calibration_history is True
    assert args.reset_calibration_history is False
    assert args.show_system_gaze_pointer is False
    assert args.show_desktop_gaze_dot is True
    assert args.control_after_calibration is True
    assert args.calibration_min_capture_frames == 4
    assert args.calibration_max_feature_jitter == 0.040
    assert args.validate_after_calibration is True
    assert args.require_validation_for_actions is True
    assert args.validation_points_per_monitor == 5
    assert args.validation_max_rms_px == 220.0
    assert args.validation_max_retries == 1
    assert args.fine_screen_warp is True
    assert args.fine_screen_warp_max_rms_px == 180.0
    assert args.save_calibration_debug_captures is False
    assert str(args.debug_capture_dir).endswith("test\\eye_tracking_captures") or str(args.debug_capture_dir).endswith("test/eye_tracking_captures")
    assert args.target_search_radius_px == 220
    assert args.target_foreground_fallback is True
    assert args.gesture_enter_frames == 2
    assert args.gesture_exit_frames == 2
    assert args.gesture_min_confidence == 0.50
    assert args.hand_edge_margin == 0.035
    assert args.hand_max_jump_norm == 0.28
    assert args.two_hand_zoom_step_ratio == 0.12
    assert args.point_snap_radius_px == 320
    assert args.point_tap_threshold_norm == 0.14
    assert args.point_tap_release_norm == 0.055
    assert args.window_snap is True
    assert args.window_snap_edge_px == 72
    assert args.online_learn_click_lag_ms == 130.0
    assert args.online_learn_window_ms == 180.0


def test_action_block_reason_explains_validation_gate() -> None:
    args = _parse_args(["--execute-actions"])
    model = LinearGazeModel(
        feature_keys=("yaw", "pitch", "gaze_x", "gaze_y"),
        coeffs_x=(0.0, 1.0, 1.0, 1.0, 1.0),
        coeffs_y=(0.0, 1.0, 1.0, 1.0, 1.0),
        rms_error_px=250.0,
    )

    reason = _action_block_reason(
        args=args,
        active_model=model,
        calibration_mode=False,
        validation_mode=False,
        calibration_validated=False,
    )

    assert reason is not None
    assert "validacion" in reason
    assert _action_status_text(
        actions_requested=True,
        actions_effective=False,
        block_reason=reason,
        candidate=None,
        target=None,
        hands=(),
    ).startswith("ACTIONS BLOCKED")


def test_candidate_window_uses_near_then_foreground_fallback() -> None:
    target = _target()

    class Targeter:
        def __init__(self) -> None:
            self.near_called = False
            self.foreground_called = False

        def from_point_near(self, x: float, y: float, *, radius_px: int) -> WindowTarget | None:
            self.near_called = True
            assert (x, y, radius_px) == (10.0, 20.0, 220)
            return None

        def from_point(self, x: float, y: float) -> WindowTarget | None:
            raise AssertionError("strict from_point should not be called with near radius")

        def foreground(self) -> WindowTarget | None:
            self.foreground_called = True
            return target

    targeter = Targeter()

    out = _candidate_window(
        targeter,  # type: ignore[arg-type]
        (10.0, 20.0),
        near_radius_px=220,
        fallback_foreground=True,
    )

    assert out == target
    assert targeter.near_called
    assert targeter.foreground_called


def test_smooth_point_caps_large_jump() -> None:
    prev = (100.0, 100.0)
    current = (600.0, 100.0)
    out = _smooth_point(prev, current, 1.0, 120.0)
    assert out is not None
    assert out[0] == 220.0


def test_merge_calibration_samples_keeps_recent_tail() -> None:
    previous = tuple(
        CalibrationSample(features={"yaw": float(i)}, target_x=float(i), target_y=float(i))
        for i in range(5)
    )
    current = tuple(
        CalibrationSample(features={"yaw": float(i + 5)}, target_x=float(i + 5), target_y=float(i + 5))
        for i in range(4)
    )
    merged = _merge_calibration_samples(previous, current, max_samples=6)
    assert len(merged) == 6
    assert merged[0].target_x == 3.0
    assert merged[-1].target_x == 8.0


def test_feature_jitter_detects_unstable_series() -> None:
    stable = (
        {"yaw": 0.10, "pitch": 0.05, "gaze_x": 0.01, "gaze_y": -0.01},
        {"yaw": 0.11, "pitch": 0.06, "gaze_x": 0.00, "gaze_y": -0.02},
        {"yaw": 0.09, "pitch": 0.04, "gaze_x": 0.01, "gaze_y": -0.01},
    )
    noisy = (
        {"yaw": 0.25, "pitch": 0.20, "gaze_x": 0.20, "gaze_y": -0.20},
        {"yaw": -0.20, "pitch": -0.25, "gaze_x": -0.20, "gaze_y": 0.20},
        {"yaw": 0.30, "pitch": 0.15, "gaze_x": 0.25, "gaze_y": -0.18},
    )
    assert _feature_jitter(stable) < _feature_jitter(noisy)


def test_sample_from_click_history_uses_stable_window() -> None:
    history = deque(
        [
            (1.00, {"yaw": 0.10, "pitch": 0.05, "gaze_x": 0.01, "gaze_y": -0.01}, (980.0, 500.0)),
            (1.05, {"yaw": 0.11, "pitch": 0.06, "gaze_x": 0.01, "gaze_y": -0.02}, (1000.0, 520.0)),
            (1.10, {"yaw": 0.09, "pitch": 0.04, "gaze_x": 0.00, "gaze_y": -0.01}, (1012.0, 528.0)),
            (1.15, {"yaw": 0.10, "pitch": 0.05, "gaze_x": 0.01, "gaze_y": -0.01}, (1018.0, 534.0)),
        ]
    )
    sample = _sample_from_click_history(
        history=history,
        click_xy=(1020, 530),
        click_timestamp_s=1.20,
        lag_ms=40.0,
        window_ms=180.0,
        max_jitter=0.050,
        max_click_distance_px=120.0,
    )
    assert sample is not None
    assert sample.target_x == 1020.0
    assert sample.target_y == 530.0


def test_sample_from_click_history_rejects_far_click() -> None:
    history = deque(
        [
            (1.00, {"yaw": 0.10, "pitch": 0.05, "gaze_x": 0.01, "gaze_y": -0.01}, (980.0, 500.0)),
            (1.05, {"yaw": 0.11, "pitch": 0.06, "gaze_x": 0.01, "gaze_y": -0.02}, (1000.0, 520.0)),
            (1.10, {"yaw": 0.09, "pitch": 0.04, "gaze_x": 0.00, "gaze_y": -0.01}, (1012.0, 528.0)),
            (1.15, {"yaw": 0.10, "pitch": 0.05, "gaze_x": 0.01, "gaze_y": -0.01}, (1018.0, 534.0)),
        ]
    )
    sample = _sample_from_click_history(
        history=history,
        click_xy=(300, 200),
        click_timestamp_s=1.20,
        lag_ms=40.0,
        window_ms=180.0,
        max_jitter=0.050,
        max_click_distance_px=120.0,
    )
    assert sample is None


def test_calibration_capture_without_head_returns_visible_notice() -> None:
    keep_running, target_idx, model, saved_path, notice = _handle_calibration_keys(
        key=32,
        hotkeys=[],
        head=None,
        target_point=(100, 100),
        samples=[],
        feature_buffer=deque(),
        targets=((100, 100),),
        target_idx=0,
        min_samples=6,
        layout_hash="layout",
        canvas=VirtualCanvas(
            (MonitorInfo(0, MonitorRect(0, 0, 1920, 1080), "primary", True),),
            MonitorRect(0, 0, 1920, 1080),
            "layout",
        ),
        camera_resolution=None,
        store=type("Store", (), {"load": lambda *_: None, "save": lambda *_: None})(),
        user=None,
        merge_with_existing=False,
        max_history_samples=100,
        max_merge_rms_px=300.0,
        min_capture_frames=4,
        max_capture_feature_jitter=0.04,
        min_capture_gaze_confidence=0.6,
    )

    assert keep_running
    assert target_idx == 0
    assert model is None
    assert saved_path is None
    assert notice == "capture rejected: no face/head detected"


def test_calibration_capture_clears_feature_buffer() -> None:
    monitor = MonitorInfo(0, MonitorRect(0, 0, 1000, 800), "primary", True)
    head = HeadPointerEstimate(
        yaw=0.1,
        pitch=-0.1,
        raw_x=500.0,
        raw_y=300.0,
        filtered_x=500.0,
        filtered_y=300.0,
        monitor=monitor,
        region="middle-center",
        source="head+iris",
        local_x=0.5,
        local_y=0.4,
        gaze=IrisGazeEstimate(0.02, -0.02, 0.9),
    )
    feature_buffer = deque(
        [
            {"yaw": 0.1, "pitch": -0.1, "gaze_x": 0.01, "gaze_y": -0.01},
            {"yaw": 0.11, "pitch": -0.09, "gaze_x": 0.02, "gaze_y": -0.02},
            {"yaw": 0.10, "pitch": -0.10, "gaze_x": 0.02, "gaze_y": -0.01},
            {"yaw": 0.10, "pitch": -0.10, "gaze_x": 0.01, "gaze_y": -0.02},
        ]
    )
    samples: list[CalibrationSample] = []

    keep_running, target_idx, model, saved_path, notice = _handle_calibration_keys(
        key=32,
        hotkeys=[],
        head=head,
        target_point=(100, 100),
        samples=samples,
        feature_buffer=feature_buffer,
        targets=((100, 100), (200, 200)),
        target_idx=0,
        min_samples=6,
        layout_hash="layout",
        canvas=VirtualCanvas(
            (MonitorInfo(0, MonitorRect(0, 0, 1920, 1080), "primary", True),),
            MonitorRect(0, 0, 1920, 1080),
            "layout",
        ),
        camera_resolution=None,
        store=type("Store", (), {"load": lambda *_: None, "save": lambda *_: None})(),
        user=None,
        merge_with_existing=False,
        max_history_samples=100,
        max_merge_rms_px=300.0,
        min_capture_frames=4,
        max_capture_feature_jitter=0.04,
        min_capture_gaze_confidence=0.6,
    )

    assert keep_running
    assert target_idx == 1
    assert model is None
    assert saved_path is None
    assert notice == "captured 1"
    assert len(samples) == 1
    assert len(feature_buffer) == 0


def test_debug_capture_writes_png_and_json(tmp_path) -> None:
    canvas = VirtualCanvas(
        (MonitorInfo(0, MonitorRect(0, 0, 1000, 800), "primary", True),),
        MonitorRect(0, 0, 1000, 800),
        "layout",
    )
    frame = np.zeros((48, 64, 3), dtype=np.uint8)

    result = _save_calibration_debug_capture(
        frame=frame,
        output_dir=tmp_path,
        index=1,
        mode="calibration",
        notice="captured 1",
        target_point=(500, 400),
        desktop_point=(510.0, 395.0),
        head=None,
        canvas=canvas,
        sample_count_before=0,
        sample_count_after=1,
        validation_sample=None,
    )

    assert result is not None
    png_path, json_path = result
    assert png_path.is_file()
    assert json_path.is_file()
    assert '"sample_saved": true' in json_path.read_text(encoding="utf-8")
    assert _has_capture_key([32])


def test_validation_summary_passes_and_fails_by_thresholds() -> None:
    canvas = VirtualCanvas(
        (MonitorInfo(0, MonitorRect(0, 0, 1000, 800), "primary", True),),
        MonitorRect(0, 0, 1000, 800),
        "layout",
    )
    samples = [
        _make_validation_sample(canvas, (200, 200), (210.0, 205.0)),
        _make_validation_sample(canvas, (800, 600), (790.0, 590.0)),
    ]
    summary = _validation_summary(samples, canvas)
    args = _parse_args([])

    assert _validation_summary_passes(summary, args)

    bad = [
        _make_validation_sample(canvas, (200, 200), (900.0, 700.0)),
        _make_validation_sample(canvas, (800, 600), (100.0, 100.0)),
    ]
    bad_summary = _validation_summary(bad, canvas)

    assert not _validation_summary_passes(bad_summary, args)


def test_bad_validation_targets_prefers_large_errors_and_monitor_misses() -> None:
    canvas = VirtualCanvas(
        (
            MonitorInfo(0, MonitorRect(0, 0, 1000, 800), "left", True),
            MonitorInfo(1, MonitorRect(1000, 0, 2000, 800), "right", False),
        ),
        MonitorRect(0, 0, 2000, 800),
        "layout",
    )
    samples = [
        _make_validation_sample(canvas, (200, 200), (205.0, 205.0)),
        _make_validation_sample(canvas, (1200, 200), (300.0, 200.0)),
        _make_validation_sample(canvas, (1800, 600), (1500.0, 400.0)),
    ]

    targets = _bad_validation_targets(samples, max_point_error_px=250.0, repeat_worst=2)

    assert (1200, 200) in targets
    assert len(targets) == 2
