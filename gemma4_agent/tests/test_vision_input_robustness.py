"""Regression tests for the vision_input robustness fixes (plan P1-P6).

Each test pins a gate from the camera-subsystem improvement plan:
- P1: pointer.update guard demands the full 478-landmark face (no IndexError).
- P2: gaze confidence is reachable and penalizes the monocular case.
- P3: OneEuroFilter ignores non-monotonic timestamps (no spurious jump).
- P4: camera read() retries transient glitches; buffer drop is opt-in.
- P5: FacePresenceWatcher tolerates single-frame blips and validates args.
- P6: the gesture recognizer reports unknown (not high-confidence fist) on
      degenerate landmarks.
"""
from __future__ import annotations

import hashlib
import math

from gemma4_agent.vision_input.camera import CameraConfig, OpenCVCamera
from gemma4_agent.vision_input.gaze import estimate_iris_gaze
from gemma4_agent.vision_input.gestures import recognize_hand_gesture
from gemma4_agent.vision_input.landmarks import (
    DEFAULT_MODELS,
    FaceSample,
    HandSample,
    NormalizedPoint,
    _download_atomic,
)
from gemma4_agent.vision_input.monitors import MonitorInfo, MonitorRect, VirtualCanvas
from gemma4_agent.vision_input.pointer import (
    HeadPointerMapper,
    OneEuroFilter,
    estimate_head_pose,
    yaw_pitch_from_matrix,
)
from gemma4_agent.vision_input.watchers import FacePresenceWatcher

import pytest


def _canvas() -> VirtualCanvas:
    return VirtualCanvas(
        (MonitorInfo(0, MonitorRect(0, 0, 1000, 1000), "primary", True),),
        MonitorRect(0, 0, 1000, 1000),
        "test",
    )


def _full_face() -> FaceSample:
    pts = [NormalizedPoint(0.5, 0.5, 0.0) for _ in range(478)]
    pts[1] = NormalizedPoint(0.5, 0.43, 0.0)
    pts[10] = NormalizedPoint(0.5, 0.18, 0.0)
    pts[152] = NormalizedPoint(0.5, 0.82, 0.0)
    pts[33] = NormalizedPoint(0.38, 0.40, 0.0)
    pts[133] = NormalizedPoint(0.47, 0.40, 0.0)
    pts[263] = NormalizedPoint(0.62, 0.40, 0.0)
    pts[362] = NormalizedPoint(0.53, 0.40, 0.0)
    pts[159] = NormalizedPoint(0.425, 0.38, 0.0)
    pts[145] = NormalizedPoint(0.425, 0.42, 0.0)
    pts[386] = NormalizedPoint(0.575, 0.38, 0.0)
    pts[374] = NormalizedPoint(0.575, 0.42, 0.0)
    # Iris centers inside each eye box (centered -> small/zero offset).
    for idx in (468, 469, 470, 471, 472):
        pts[idx] = NormalizedPoint(0.425, 0.40, 0.0)
    for idx in (473, 474, 475, 476, 477):
        pts[idx] = NormalizedPoint(0.575, 0.40, 0.0)
    return FaceSample(tuple(pts))


# ----- P1: pointer guard --------------------------------------------------

def test_pointer_update_rejects_partial_face_without_indexerror() -> None:
    mapper = HeadPointerMapper(_canvas(), auto_center=False)
    # 300 landmarks: enough to pass the old (<264) guard but estimate_yaw_pitch
    # reads index 362 -> would raise IndexError without the 478 guard.
    partial = FaceSample(tuple(NormalizedPoint(0.5, 0.5, 0.0) for _ in range(300)))

    assert mapper.update(partial, 1.0) is None


def test_pointer_update_accepts_full_face() -> None:
    mapper = HeadPointerMapper(_canvas(), auto_center=False)

    assert mapper.update(_full_face(), 1.0) is not None


# ----- P2: gaze confidence model ------------------------------------------

def test_gaze_two_eyes_in_agreement_beats_monocular() -> None:
    binocular = estimate_iris_gaze(_full_face().landmarks)

    pts = list(_full_face().landmarks)
    # Collapse the left eye box so the left eye is invalid -> monocular estimate.
    for idx in (33, 133, 159, 145, 468, 469, 470, 471, 472):
        pts[idx] = NormalizedPoint(0.40, 0.40, 0.0)
    monocular = estimate_iris_gaze(tuple(pts))

    assert binocular is not None
    assert monocular is not None
    assert binocular.confidence > monocular.confidence
    assert monocular.confidence < 0.35  # below default min_confidence -> gate bites


def test_gaze_closed_eye_is_invalidated() -> None:
    pts = list(_full_face().landmarks)
    # Squeeze BOTH eyes' vertical lids shut (EAR -> ~0): no usable gaze.
    for idx in (159, 145):
        pts[idx] = NormalizedPoint(0.425, 0.400, 0.0)
    for idx in (386, 374):
        pts[idx] = NormalizedPoint(0.575, 0.400, 0.0)

    assert estimate_iris_gaze(tuple(pts)) is None


# ----- P3: one-euro non-monotonic timestamp -------------------------------

def test_one_euro_ignores_non_monotonic_timestamp() -> None:
    f = OneEuroFilter()
    f.filter(0.0, 0.0)
    f.filter(10.0, 0.033)
    before = f.filter(10.0, 0.066)
    # Repeated timestamp then a backward one: must not produce a spurious jump.
    repeated = f.filter(500.0, 0.066)
    backward = f.filter(500.0, 0.040)

    assert repeated == before
    assert backward == before


# ----- P4: camera read retry ----------------------------------------------

class _FakeCap:
    def __init__(self, script: list[tuple[bool, object]], opened: bool = True) -> None:
        self._script = script
        self._opened = opened
        self.calls = 0

    def read(self):
        item = self._script[min(self.calls, len(self._script) - 1)]
        self.calls += 1
        return item

    def isOpened(self) -> bool:
        return self._opened


def test_camera_read_retries_transient_glitch() -> None:
    cam = OpenCVCamera(CameraConfig(read_retries=3, read_retry_sleep_s=0.0))
    cam._cap = _FakeCap([(False, None), (True, object())])

    frame = cam.read()

    assert frame.sequence == 1
    assert cam._cap.calls == 2


def test_camera_read_raises_when_disconnected() -> None:
    cam = OpenCVCamera(CameraConfig(read_retries=3, read_retry_sleep_s=0.0))
    cam._cap = _FakeCap([(False, None)], opened=False)

    with pytest.raises(RuntimeError, match="disconnected"):
        cam.read()


def test_camera_config_drop_stale_frames_default_on() -> None:
    assert CameraConfig().drop_stale_frames is True


# ----- P5: watcher debounce -----------------------------------------------

def test_watcher_emits_under_noisy_presence_stream() -> None:
    w = FacePresenceWatcher(debounce_s=0.3, glitch_tolerance_s=0.2)
    # present at t=0 with a single dropped frame at t=0.15; the transition to
    # present must still fire once debounce_s elapses.
    stream = [
        (1, 0.00),
        (1, 0.05),
        (0, 0.15),  # blip
        (1, 0.20),
        (1, 0.35),
    ]
    events = [w.update(c, t) for c, t in stream]
    kinds = [e.kind for e in events if e is not None]

    assert "face_entered" in kinds


def test_watcher_does_not_emit_below_debounce() -> None:
    w = FacePresenceWatcher(debounce_s=1.0)
    assert w.update(1, 0.0) is None
    assert w.update(1, 0.2) is None  # not enough time elapsed


def test_watcher_ignores_backward_timestamp() -> None:
    w = FacePresenceWatcher(debounce_s=0.3)
    w.update(1, 0.0)
    assert w.update(1, -5.0) is None  # backward jump ignored, no crash


def test_watcher_rejects_negative_debounce() -> None:
    with pytest.raises(ValueError):
        FacePresenceWatcher(debounce_s=-1.0)
    with pytest.raises(ValueError):
        FacePresenceWatcher(glitch_tolerance_s=-1.0)


# ----- P6: degenerate gesture guard ---------------------------------------

def test_degenerate_landmarks_report_unknown_not_fist() -> None:
    collapsed = HandSample(tuple(NormalizedPoint(0.5, 0.5, 0.0) for _ in range(21)))

    result = recognize_hand_gesture(collapsed)

    assert result.label == "unknown"
    assert result.confidence == 0.0


# ----- P11: DPI awareness --------------------------------------------------

def test_dpi_awareness_is_idempotent_and_safe() -> None:
    from gemma4_agent.vision_input.dpi import ensure_dpi_awareness

    first = ensure_dpi_awareness()
    second = ensure_dpi_awareness()
    # Never raises; once applied, repeat calls report so.
    assert isinstance(first, str)
    assert second in ("already-applied", first)


# ----- P8: matrix-based head pose -----------------------------------------

def _yaw_matrix(angle_rad: float) -> tuple[tuple[float, ...], ...]:
    """4x4 transform with a pure rotation of `angle_rad` about the vertical axis."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return (
        (c, 0.0, s, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (-s, 0.0, c, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )


def test_yaw_pitch_from_matrix_tracks_rotation_and_sign() -> None:
    left = yaw_pitch_from_matrix(_yaw_matrix(-0.4))
    center = yaw_pitch_from_matrix(_yaw_matrix(0.0))
    right = yaw_pitch_from_matrix(_yaw_matrix(0.4))

    assert center is not None and abs(center[0]) < 1e-6
    assert left is not None and right is not None
    assert left[0] < center[0] < right[0]  # monotonic in head yaw

    flipped = yaw_pitch_from_matrix(_yaw_matrix(0.4), yaw_sign=-1.0)
    assert flipped is not None and flipped[0] < 0  # sign knob flips direction


def test_yaw_pitch_from_matrix_rejects_missing_matrix() -> None:
    assert yaw_pitch_from_matrix(None) is None
    assert yaw_pitch_from_matrix(((1.0, 0.0),)) is None  # too small


def _pitch_down_matrix(angle_rad: float) -> tuple[tuple[float, ...], ...]:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, c, -s, 0.0),
        (0.0, s, c, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )


def test_downward_pitch_does_not_saturate() -> None:
    # A monitor placed BELOW the others needs the downward look to stay resolvable
    # instead of pinning to the clamp ceiling. Distinct downward angles must yield
    # distinct, monotonically increasing pitch magnitudes (regression for the
    # bottom-monitor saturation bug: RMS 322px when pitch was pinned at -0.55).
    pitches = []
    for deg in (20, 30, 40, 50):
        yp = yaw_pitch_from_matrix(_pitch_down_matrix(math.radians(deg)))
        assert yp is not None
        pitches.append(yp[1])
    # strictly more negative as the head tilts further down (no saturation)
    for earlier, later in zip(pitches, pitches[1:]):
        assert later < earlier - 1e-3, f"pitch saturated: {pitches}"


def test_estimate_head_pose_prefers_matrix_then_falls_back() -> None:
    with_matrix = FaceSample(
        tuple(NormalizedPoint(0.5, 0.5, 0.0) for _ in range(478)),
        transformation_matrix=_yaw_matrix(0.3),
    )
    yaw, _pitch, source = estimate_head_pose(with_matrix)
    assert source == "matrix"
    assert yaw > 0.0

    no_matrix = _full_face()  # transformation_matrix is None
    _yaw2, _pitch2, source2 = estimate_head_pose(no_matrix)
    assert source2 == "heuristic2d"


def test_mapper_reports_matrix_pose_source() -> None:
    pts = list(_full_face().landmarks)
    face = FaceSample(tuple(pts), transformation_matrix=_yaw_matrix(0.0))
    mapper = HeadPointerMapper(_canvas(), auto_center=False)
    est = mapper.update(face, 1.0)
    assert est is not None
    assert est.source.startswith("matrix")


# ----- P14: model license traceability ------------------------------------

def test_models_are_apache_and_hash_pinned() -> None:
    for key, spec in DEFAULT_MODELS.items():
        assert spec.license == "Apache-2.0", f"{key} must be commercial-OK"
        assert len(spec.sha256) == 64, f"{key} .task must be sha256-pinned for license traceability"


def test_download_atomic_verifies_hash_and_cleans_tmp(tmp_path, monkeypatch) -> None:
    payload = b"fake-task-bytes"
    expected = hashlib.sha256(payload).hexdigest()

    class _Resp:
        def __init__(self) -> None:
            self._chunks = [payload, b""]
            self._i = 0

        def read(self, _n):
            item = self._chunks[self._i]
            self._i = min(self._i + 1, len(self._chunks) - 1)
            return item

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    dest = tmp_path / "m.task"
    _download_atomic("http://example/m.task", dest, expected_sha256=expected)

    assert dest.read_bytes() == payload
    assert not (tmp_path / "m.task.tmp").exists()  # tmp cleaned up


def test_download_atomic_warns_on_hash_mismatch(tmp_path, monkeypatch) -> None:
    payload = b"unexpected-bytes"

    class _Resp:
        def __init__(self) -> None:
            self._done = False

        def read(self, _n):
            if self._done:
                return b""
            self._done = True
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    dest = tmp_path / "m.task"
    with pytest.warns(UserWarning, match="sha256 mismatch"):
        _download_atomic("http://example/m.task", dest, expected_sha256="0" * 64)
    # Still written (warn, not fail) so a benign upstream update doesn't brick it.
    assert dest.read_bytes() == payload
