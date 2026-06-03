from gemma4_agent.vision_input.gaze import GazeRefinementConfig, estimate_iris_gaze, refine_local_point
from gemma4_agent.vision_input.landmarks import FaceSample, NormalizedPoint
from gemma4_agent.vision_input.monitors import MonitorInfo, MonitorRect, VirtualCanvas
from gemma4_agent.vision_input.pointer import HeadPointerMapper


def _face_with_iris(iris_shift_x: float = 0.0, iris_shift_y: float = 0.0, nose_shift_x: float = 0.0) -> FaceSample:
    pts = [NormalizedPoint(0.5, 0.5, 0.0) for _ in range(478)]

    # Head-pose landmarks.
    pts[1] = NormalizedPoint(0.5 + nose_shift_x, 0.43, 0.0)
    pts[10] = NormalizedPoint(0.5, 0.18, 0.0)
    pts[152] = NormalizedPoint(0.5, 0.82, 0.0)
    pts[33] = NormalizedPoint(0.38, 0.40, 0.0)
    pts[133] = NormalizedPoint(0.47, 0.40, 0.0)
    pts[263] = NormalizedPoint(0.62, 0.40, 0.0)
    pts[362] = NormalizedPoint(0.53, 0.40, 0.0)

    # Eye vertical bounds.
    pts[159] = NormalizedPoint(0.425, 0.38, 0.0)
    pts[145] = NormalizedPoint(0.425, 0.42, 0.0)
    pts[386] = NormalizedPoint(0.575, 0.38, 0.0)
    pts[374] = NormalizedPoint(0.575, 0.42, 0.0)

    left_center = NormalizedPoint(0.425 + iris_shift_x, 0.40 + iris_shift_y, 0.0)
    right_center = NormalizedPoint(0.575 + iris_shift_x, 0.40 + iris_shift_y, 0.0)
    for idx in (468, 469, 470, 471, 472):
        pts[idx] = left_center
    for idx in (473, 474, 475, 476, 477):
        pts[idx] = right_center
    return FaceSample(tuple(pts))


def test_estimate_iris_gaze_uses_iris_landmarks() -> None:
    centered = estimate_iris_gaze(_face_with_iris().landmarks)
    shifted = estimate_iris_gaze(_face_with_iris(iris_shift_x=0.015).landmarks)

    assert centered is not None
    assert shifted is not None
    assert abs(centered.x) < 0.01
    assert shifted.x > centered.x
    assert shifted.confidence > 0.0


def test_refine_local_point_applies_deadzone_and_gain() -> None:
    gaze = estimate_iris_gaze(_face_with_iris(iris_shift_x=0.02).landmarks)

    local_x, local_y, source = refine_local_point(
        0.5,
        0.5,
        gaze,
        GazeRefinementConfig(gain_x=1.0, gain_y=1.0, deadzone=0.0),
    )

    assert source == "head+iris"
    assert local_x > 0.5
    assert abs(local_y - 0.5) < 1e-9


def test_head_pointer_mapper_refines_with_iris() -> None:
    canvas = VirtualCanvas(
        (MonitorInfo(0, MonitorRect(0, 0, 1000, 1000), "primary", True),),
        MonitorRect(0, 0, 1000, 1000),
        "test",
    )
    head_only = HeadPointerMapper(canvas, GazeRefinementConfig(enabled=False), auto_center=False)
    iris = HeadPointerMapper(
        canvas,
        GazeRefinementConfig(enabled=True, gain_x=1.0, deadzone=0.0),
        auto_center=False,
    )

    head_estimate = head_only.update(_face_with_iris(iris_shift_x=0.02), 1.0)
    iris_estimate = iris.update(_face_with_iris(iris_shift_x=0.02), 1.0)

    assert head_estimate is not None
    assert iris_estimate is not None
    # source is "<pose>+<refine>"; these fixtures have no transformation matrix,
    # so the pose source is the 2D heuristic fallback.
    assert head_estimate.source == "heuristic2d+head"
    assert iris_estimate.source == "heuristic2d+head+iris"
    assert iris_estimate.raw_x > head_estimate.raw_x


def test_head_pointer_auto_center_handles_camera_offset() -> None:
    canvas = VirtualCanvas(
        (
            MonitorInfo(0, MonitorRect(-1920, 0, 0, 1080), "left", False),
            MonitorInfo(1, MonitorRect(0, 0, 1920, 1080), "center", True),
            MonitorInfo(2, MonitorRect(1920, 0, 3840, 1080), "right", False),
        ),
        MonitorRect(-1920, 0, 3840, 1080),
        "test",
    )
    raw_mapper = HeadPointerMapper(canvas, GazeRefinementConfig(enabled=False), auto_center=False)
    mapper = HeadPointerMapper(canvas, GazeRefinementConfig(enabled=False), auto_center=True, center_alpha=0.3)
    face = _face_with_iris(nose_shift_x=0.055)
    baseline = raw_mapper.update(face, 1.0)
    current = mapper.update(face, 1.0)
    for idx in range(2, 20):
        current = mapper.update(face, float(idx))
    assert baseline is not None
    assert current is not None
    assert baseline.monitor.index == 2
    assert current.monitor.index == 1
