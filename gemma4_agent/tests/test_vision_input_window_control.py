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
# Refactor 2026-06-11: la lógica de calibración salió de window_control a
# calibration_flow (máquina de estados propia); window_control conserva el
# runner/acciones. _frame_point_from_head fue eliminada (el overlay vive en
# renderer.py) y su test se retiró con ella.
from gemma4_agent.vision_input.calibration_flow import (
    _average_features,
    _bad_validation_targets,
    _feature_jitter,
    _handle_calibration_keys,
    _has_capture_key,
    _make_validation_sample,
    _merge_calibration_samples,
    _save_calibration_debug_capture,
    _sample_from_click_history,
    _validation_summary,
    _validation_summary_passes,
)
# parse_args vive en config (única fuente de verdad de defaults); la copia
# muerta window_control._parse_args —con defaults DIVERGENTES que estos tests
# validaban mientras el runtime usaba otros— se eliminó.
from gemma4_agent.vision_input.config import parse_args
from gemma4_agent.vision_input.window_control import (
    _action_block_reason,
    _action_status_text,
    _candidate_window,
    _control_hands,
    _desktop_point,
    _smooth_point,
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
    config = WindowControlConfig(execute_actions=False)
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


# Rediseño 2026-06-11 (suite de handlers): el arrastre directo con fist fue
# REEMPLAZADO por HybridSwipeGesture (fist sostenido ≥0.15s + target →
# swipe-a-monitor), palm pasó de scroll a MEDIA (dwell 0.55s, anti-falso-
# positivo), el scroll vive en PinchScrollGesture (pinch cerrado <0.20) y la
# activación pasa por el estado ARMED (anti-acción-accidental, HCI doc §2).
# Los tests del contrato viejo (grab/move/snap/palm-scroll) se retiraron con
# la feature; estos cubren los contratos NUEVOS de activación.


def test_first_frame_arms_does_not_act() -> None:
    controller = _controller()
    target = _target()
    first = controller.update(
        timestamp_s=1.0,
        target=target,
        hands=(HandControlPose(0.5, 0.5, "fist"),),
        pointer_xy=(500, 400),
    )
    assert first.state == CameraControlState.ARMED
    assert first.events == ()


def test_sustained_fist_with_target_activates_swipe_handler() -> None:
    controller = _controller()
    target = _target()
    controller.update(
        timestamp_s=1.0, target=target,
        hands=(HandControlPose(0.5, 0.5, "fist"),), pointer_xy=(500, 400),
    )
    # dwell de 0.15s: el segundo frame con el fist sostenido activa el handler
    out = controller.update(
        timestamp_s=1.2, target=target,
        hands=(HandControlPose(0.5, 0.5, "fist"),), pointer_xy=(500, 400),
    )
    assert out.state == CameraControlState.DRAGGING


def test_fist_without_target_stays_armed() -> None:
    controller = _controller()
    controller.update(
        timestamp_s=1.0, target=None,
        hands=(HandControlPose(0.5, 0.5, "fist"),), pointer_xy=(500, 400),
    )
    out = controller.update(
        timestamp_s=1.2, target=None,
        hands=(HandControlPose(0.5, 0.5, "fist"),), pointer_xy=(500, 400),
    )
    assert out.state == CameraControlState.ARMED


def test_loose_pinch_does_not_scroll_tight_pinch_does() -> None:
    target = _target()
    loose = _controller()
    loose.update(
        timestamp_s=1.0, target=target,
        hands=(HandControlPose(0.5, 0.5, "palm"),), pointer_xy=(500, 400),
    )
    out = loose.update(
        timestamp_s=1.1, target=target,
        hands=(HandControlPose(0.5, 0.5, "pinch", pinch_distance=0.5),),
        pointer_xy=(500, 400),
    )
    assert out.state == CameraControlState.ARMED  # pinch flojo: no activa

    tight = _controller()
    tight.update(
        timestamp_s=1.0, target=target,
        hands=(HandControlPose(0.5, 0.5, "palm"),), pointer_xy=(500, 400),
    )
    out = tight.update(
        timestamp_s=1.1, target=target,
        hands=(HandControlPose(0.5, 0.5, "pinch", pinch_distance=0.1),),
        pointer_xy=(500, 400),
    )
    assert out.state == CameraControlState.DRAGGING  # pinch cerrado: scroll activo


def test_palm_requires_dwell_before_media_toggle() -> None:
    # El dwell de 0.55s exige frames CONTINUOS (gap >0.2s resetea el timer —
    # anti-falso-positivo de una palma que pasa frente a la cámara).
    controller = _controller()
    target = _target()
    # frames por índice entero (un while con t+=0.15 acumula drift de float y
    # mete una iteración de más justo sobre el umbral)
    out = None
    for i in range(4):  # t = 1.00, 1.15, 1.30, 1.45 -> 0.45s sostenidos
        out = controller.update(
            timestamp_s=1.0 + 0.15 * i, target=target,
            hands=(HandControlPose(0.5, 0.5, "palm"),), pointer_xy=(500, 400),
        )
    assert out is not None and out.state == CameraControlState.ARMED  # <0.55s
    out = controller.update(  # t = 1.60 -> 0.60s sostenidos: cruza el dwell
        timestamp_s=1.0 + 0.15 * 4, target=target,
        hands=(HandControlPose(0.5, 0.5, "palm"),), pointer_xy=(500, 400),
    )
    assert out.state == CameraControlState.DRAGGING  # dwell cumplido: activa


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


def test_point_activates_click_handler_immediately() -> None:
    # PointClickGesture activa sin dwell (bajo riesgo: el click real exige
    # el air-tap en z después). El contrato viejo de point_armed/point_click
    # por eventos se retiró con el rediseño.
    controller = _controller()
    target = _target()
    controller.update(
        timestamp_s=1.0, target=target,
        hands=(HandControlPose(0.5, 0.5, "palm"),), pointer_xy=(500, 400),
    )
    out = controller.update(
        timestamp_s=1.1, target=target,
        hands=(_point_pose(-0.18),), pointer_xy=(500, 400),
    )
    assert out.state == CameraControlState.DRAGGING


def test_hand_lost_briefly_keeps_state_then_idles() -> None:
    # Tolerancia de 0.2s a pérdida de tracking antes de abortar (anti-flicker).
    controller = _controller()
    target = _target()
    controller.update(
        timestamp_s=1.0, target=target,
        hands=(HandControlPose(0.5, 0.5, "fist"),), pointer_xy=(500, 400),
    )
    controller.update(
        timestamp_s=1.2, target=target,
        hands=(HandControlPose(0.5, 0.5, "fist"),), pointer_xy=(500, 400),
    )
    brief = controller.update(
        timestamp_s=1.3, target=target, hands=(), pointer_xy=(500, 400),
    )
    assert brief.state != CameraControlState.IDLE  # tolerancia
    gone = controller.update(
        timestamp_s=1.6, target=target, hands=(), pointer_xy=(500, 400),
    )
    assert gone.state == CameraControlState.IDLE


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
    args = parse_args([])
    assert args.quiet_runtime_logs is True
    assert args.merge_calibration_history is True
    assert args.reset_calibration_history is False
    assert args.show_system_gaze_pointer is False
    assert args.show_desktop_gaze_dot is True
    assert args.control_after_calibration is True
    assert args.calibration_min_capture_frames == 4
    assert args.calibration_max_feature_jitter == 0.040
    # 350 (no 3000): un RMS de entrenamiento >350px es un perfil basura y el
    # gate debe rechazarlo en guardado/carga/online-learn.
    assert args.calibration_max_rms_px == 350.0
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
    # 0.08 = el umbral que el handler usaba EN VIVO (el flag viejo decía 0.14
    # pero estaba pisado por un hardcode; ahora el config es la única verdad).
    assert args.point_tap_threshold_norm == 0.08
    assert args.point_tap_release_norm == 0.055
    assert args.swipe_velocity_threshold == 0.45
    assert args.swipe_min_distance_norm == 0.05
    assert args.download_models is True
    assert args.online_learn_click_lag_ms == 130.0
    assert args.online_learn_window_ms == 180.0


def test_standalone_marker_flag_parses() -> None:
    # El entrypoint standalone inyecta --standalone; antes el flag no existía y
    # argparse abortaba con SystemExit(2) (entrypoint roto).
    args = parse_args(["--standalone"])
    assert args.standalone is True
    assert parse_args([]).standalone is False


def test_action_block_reason_explains_validation_gate() -> None:
    args = parse_args(["--execute-actions"])
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
    args = parse_args([])

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


# ---------------------------------------------------------------------------
# Regresiones del perfeccionamiento 2026-06-12 (suite de gestos/camara):
# contexto compartido, click en el punto de mirada, throttle, perfil completo.
# ---------------------------------------------------------------------------


class _SpyActuator(WindowActuator):
    """Actuator que registra el punto de click sin tocar win32."""

    def __init__(self) -> None:
        super().__init__(execute=False, desktop_rect=MonitorRect(0, 0, 1920, 1080))
        self.clicks: list[tuple[int, int, int]] = []

    def click_near(self, target, screen_x, screen_y, radius_px):
        self.clicks.append((int(screen_x), int(screen_y), int(radius_px)))
        return (True, "spy")


def test_controller_config_propagates_to_handlers() -> None:
    # El config se reasigna en runtime (toggle de acciones, recalibracion); los
    # handlers deben ver el valor NUEVO via ControlContext, no una copia stale.
    controller = _controller()
    new_config = WindowControlConfig(execute_actions=True, point_snap_radius_px=99)
    controller.config = new_config
    assert controller.config.point_snap_radius_px == 99
    for handler in controller._handlers:
        assert handler.config is new_config


def _drive_point_click(controller, target, pointer):
    # palm arma sin activar handler de click; luego point activa; anchor; tap.
    controller.update(timestamp_s=1.0, target=target,
                      hands=(HandControlPose(0.5, 0.5, "unknown"),), pointer_xy=pointer)
    controller.update(timestamp_s=1.1, target=target,
                      hands=(_point_pose(0.0),), pointer_xy=pointer)   # activa handler
    controller.update(timestamp_s=1.2, target=target,
                      hands=(_point_pose(0.0),), pointer_xy=pointer)   # fija anchor
    return controller.update(timestamp_s=1.3, target=target,
                             hands=(_point_pose(0.10),), pointer_xy=pointer)  # tap 0.10 > 0.08


def test_point_click_lands_at_gaze_pointer_not_window_center() -> None:
    # El gaze pointer ELIGIO la ventana; el click debe caer donde el usuario
    # mira (antes siempre iba al centro de la ventana e ignoraba pointer_xy).
    actuator = _SpyActuator()
    controller = FixedGestureWindowController(WindowControlConfig(), actuator)
    target = _target()  # rect (100,100,900,700) -> centro (500,400)
    out = _drive_point_click(controller, target, pointer=(850, 650))
    assert any(e.name == "point_click" for e in out.events)
    assert actuator.clicks and actuator.clicks[0][:2] == (850, 650)


def test_point_click_clamps_pointer_into_target_and_falls_back_to_center() -> None:
    actuator = _SpyActuator()
    controller = FixedGestureWindowController(WindowControlConfig(), actuator)
    target = _target()
    _drive_point_click(controller, target, pointer=(2000, 50))  # fuera del rect
    assert actuator.clicks and actuator.clicks[0][:2] == (899, 100)  # clamp al borde

    actuator2 = _SpyActuator()
    controller2 = FixedGestureWindowController(WindowControlConfig(), actuator2)
    _drive_point_click(controller2, target, pointer=None)  # sin gaze -> centro
    assert actuator2.clicks and actuator2.clicks[0][:2] == (500, 400)


def test_point_tap_threshold_comes_from_config() -> None:
    # El umbral del air-tap estaba hardcodeado en 0.08 pisando el config.
    actuator = _SpyActuator()
    strict = WindowControlConfig(point_tap_threshold_norm=0.2)
    controller = FixedGestureWindowController(strict, actuator)
    out = _drive_point_click(controller, _target(), pointer=(500, 400))
    assert not any(e.name == "point_click" for e in out.events)  # 0.10 < 0.2
    assert actuator.clicks == []


def test_set_cursor_pos_does_not_raise_without_win32api(monkeypatch) -> None:
    # _set_cursor_pos referenciaba win32api sin importarlo (NameError en vivo
    # con --show-system-gaze-pointer). Ahora el modulo lo importa con guard.
    from gemma4_agent.vision_input import calibration_flow

    assert hasattr(calibration_flow, "win32api")
    monkeypatch.setattr(calibration_flow, "win32api", None)
    calibration_flow._set_cursor_pos((10, 10))  # no-op, no debe lanzar


def test_mp_throttle_picks_last_cores() -> None:
    # El STT (_ort_throttle) se pinea a los PRIMEROS cores; la camara debe ir a
    # los ULTIMOS para no pelear por los mismos.
    from gemma4_agent.vision_input._mp_throttle import _pick_cores

    assert _pick_cores(24, 2) == [21, 22, 23]
    assert _pick_cores(4, 2) == [1, 2, 3]
    assert _pick_cores(1, 2) == [0]


def test_fit_with_loo_ridge_returns_model_on_synthetic_grid() -> None:
    # P13 restaurado: el guardado usa ridge elegido por LOO-CV. Con datos
    # lineales limpios el modelo debe ajustar con error chico.
    from gemma4_agent.vision_input.calibration_flow import _fit_with_loo_ridge

    samples = tuple(
        CalibrationSample(
            features={"yaw": x, "pitch": y, "gaze_x": x * 0.1, "gaze_y": y * 0.1},
            target_x=960.0 + x * 900.0,
            target_y=540.0 + y * 500.0,
        )
        for x in (-0.4, -0.2, 0.0, 0.2, 0.4)
        for y in (-0.4, 0.0, 0.4)
    )
    model = _fit_with_loo_ridge(samples)
    assert model is not None
    assert model.rms_error_px < 30.0


def test_save_calibration_profile_keeps_camera_resolution(tmp_path) -> None:
    # El re-guardado del fine-warp perdia camera_resolution y el warning de
    # "resolucion distinta a la calibrada" quedaba muerto para esos perfiles.
    from gemma4_agent.vision_input.calibration import CalibrationStore, LinearGazeModel
    from gemma4_agent.vision_input.calibration_flow import _save_calibration_profile

    store = CalibrationStore(base_dir=tmp_path)
    model = LinearGazeModel(
        feature_keys=("yaw", "pitch", "gaze_x", "gaze_y"),
        coeffs_x=(0.0, 1.0, 0.0, 0.0, 0.0),
        coeffs_y=(0.0, 0.0, 1.0, 0.0, 0.0),
        rms_error_px=10.0,
    )
    _save_calibration_profile(
        store=store, layout_hash="layout", user="tester",
        samples=(), model=model, camera_resolution=(1280, 720),
    )
    loaded = store.load("layout", "tester")
    assert loaded is not None
    assert loaded.camera_resolution == (1280, 720)


def test_landmark_detector_prefers_tasks_api(monkeypatch) -> None:
    # El orden viejo prefería mp.solutions (deprecada, sin transformation
    # matrix) si existía; ahora Tasks API va primero y solutions es fallback.
    from gemma4_agent.vision_input.landmarks import MediaPipeLandmarkDetector

    detector = MediaPipeLandmarkDetector()
    called = {"tasks": 0, "legacy": 0}
    monkeypatch.setattr(detector, "_start_tasks", lambda mp: called.__setitem__("tasks", called["tasks"] + 1))
    monkeypatch.setattr(detector, "_start_legacy_solutions", lambda mp: called.__setitem__("legacy", called["legacy"] + 1))
    detector.start()
    assert called == {"tasks": 1, "legacy": 0}
