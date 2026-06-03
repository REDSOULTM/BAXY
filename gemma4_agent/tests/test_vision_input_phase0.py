from gemma4_agent.vision_input.gestures import GestureStabilizer, recognize_hand_gesture
from gemma4_agent.vision_input.landmarks import HandSample, NormalizedPoint
from gemma4_agent.vision_input.monitors import MonitorInfo, MonitorRect, VirtualCanvas
from gemma4_agent.vision_input.poc import (
    _collection_samples_complete,
    _empty_confusion,
    _gate_samples_complete,
    _gesture_progress_pct,
    _jitter_state,
    _parse_args,
)
from gemma4_agent.vision_input.pointer import jitter_rms_px


def test_no_hand_recognizes_none() -> None:
    result = recognize_hand_gesture(None)

    assert result.label == "none"
    assert result.confidence == 1.0


def test_gesture_stabilizer_majority_vote() -> None:
    stabilizer = GestureStabilizer(window=3)

    assert stabilizer.update("pinch") == "pinch"
    assert stabilizer.update("fist") in {"fist", "pinch"}
    assert stabilizer.update("fist") == "fist"


def test_virtual_canvas_monitor_for_yaw_three_monitors() -> None:
    monitors = (
        MonitorInfo(0, MonitorRect(-1920, 0, 0, 1080), "left"),
        MonitorInfo(1, MonitorRect(0, 0, 1920, 1080), "center", True),
        MonitorInfo(2, MonitorRect(1920, 0, 3840, 1080), "right"),
    )
    canvas = VirtualCanvas(monitors, MonitorRect(-1920, 0, 3840, 1080), "test")

    assert canvas.monitor_for_yaw(-0.45).device == "left"
    assert canvas.monitor_for_yaw(0.0).device == "center"
    assert canvas.monitor_for_yaw(0.45).device == "right"
    assert canvas.monitor_for_yaw(-0.10).device == "center"
    assert canvas.monitor_for_yaw(0.10).device == "center"


def test_virtual_canvas_monitor_for_pose_user_three_monitor_layout() -> None:
    monitors = (
        MonitorInfo(0, MonitorRect(-1920, 0, 0, 1080), "top-left"),
        MonitorInfo(1, MonitorRect(0, 0, 1920, 1080), "top-right", True),
        MonitorInfo(2, MonitorRect(-968, 1080, 568, 1944), "bottom"),
    )
    canvas = VirtualCanvas(monitors, MonitorRect(-1920, 0, 1920, 1944), "user-layout")

    assert canvas.monitor_for_pose(-0.30, -0.10).device == "top-left"
    assert canvas.monitor_for_pose(0.30, -0.10).device == "top-right"
    assert canvas.monitor_for_pose(0.00, 0.20).device == "bottom"


def test_virtual_canvas_monitor_for_yaw_two_monitors() -> None:
    monitors = (
        MonitorInfo(0, MonitorRect(0, 0, 1920, 1080), "left"),
        MonitorInfo(1, MonitorRect(1920, 0, 3840, 1080), "right"),
    )
    canvas = VirtualCanvas(monitors, MonitorRect(0, 0, 3840, 1080), "test2")

    assert canvas.monitor_for_yaw(-0.40).device == "left"
    assert canvas.monitor_for_yaw(-0.01).device == "left"
    assert canvas.monitor_for_yaw(0.00).device == "right"
    assert canvas.monitor_for_yaw(0.40).device == "right"


def test_virtual_canvas_monitor_for_yaw_one_monitor() -> None:
    monitors = (MonitorInfo(0, MonitorRect(0, 0, 1920, 1080), "solo", True),)
    canvas = VirtualCanvas(monitors, MonitorRect(0, 0, 1920, 1080), "test1")

    assert canvas.monitor_for_yaw(-0.45).device == "solo"
    assert canvas.monitor_for_yaw(0.00).device == "solo"
    assert canvas.monitor_for_yaw(0.45).device == "solo"


def test_jitter_rms_px() -> None:
    assert jitter_rms_px([]) is None
    assert jitter_rms_px([(10.0, 10.0), (10.0, 10.0)]) == 0.0


def test_poc_defaults_to_current_camera() -> None:
    args = _parse_args([])

    assert args.camera_index == 0
    assert args.camera_backend == "msmf"
    assert args.width == 1280
    assert args.height == 720
    assert args.face_every_n == 4
    assert args.iris_refine is True
    assert args.gaze_gain_x == 0.62
    assert args.samples_per_gesture == 10
    assert args.jitter_settle_seconds == 1.0
    assert args.jitter_seconds == 3.0


def test_gesture_progress_pct() -> None:
    confusion = _empty_confusion()
    confusion["fist"]["fist"] = 5

    progress = _gesture_progress_pct(confusion, 10)

    assert progress["fist"] == 50.0
    assert progress["pinch"] == 0.0


def test_gate_samples_do_not_require_point() -> None:
    confusion = _empty_confusion()
    for label in ("fist", "pinch", "palm"):
        confusion[label][label] = 10

    assert _gate_samples_complete(confusion, 10)
    assert not _collection_samples_complete(confusion, 10)
    assert sum(confusion["point"].values()) == 0


def test_jitter_state_has_settle_measure_and_complete_phases() -> None:
    args = _parse_args([])

    assert _jitter_state(None, 10.0, args) == ("waiting", 0.0)
    assert _jitter_state(10.0, 10.5, args) == ("settling", 0.0)

    state, progress = _jitter_state(10.0, 12.5, args)

    assert state == "measuring"
    assert 0.0 < progress < 1.0
    assert _jitter_state(10.0, 14.1, args) == ("complete", 1.0)


def test_point_tolerates_partly_folded_other_fingers() -> None:
    pts = [NormalizedPoint(0.0, 0.0, 0.0) for _ in range(21)]
    pts[0] = NormalizedPoint(0.0, 0.0, 0.0)
    pts[4] = NormalizedPoint(-0.25, 0.2, 0.0)
    pts[5] = NormalizedPoint(0.0, 0.35, 0.0)
    pts[6] = NormalizedPoint(0.0, 0.75, 0.0)
    pts[8] = NormalizedPoint(0.0, 1.25, 0.0)
    pts[9] = NormalizedPoint(0.18, 0.32, 0.0)
    pts[10] = NormalizedPoint(0.18, 0.62, 0.0)
    pts[12] = NormalizedPoint(0.16, 0.52, 0.0)
    pts[13] = NormalizedPoint(0.32, 0.28, 0.0)
    pts[14] = NormalizedPoint(0.32, 0.55, 0.0)
    pts[16] = NormalizedPoint(0.3, 0.46, 0.0)
    pts[17] = NormalizedPoint(0.45, 0.24, 0.0)
    pts[18] = NormalizedPoint(0.45, 0.48, 0.0)
    pts[20] = NormalizedPoint(0.43, 0.39, 0.0)

    result = recognize_hand_gesture(HandSample(tuple(pts)))

    assert result.label == "point"
