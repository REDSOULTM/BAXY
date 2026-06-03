"""Coarse head pointer and one-euro smoothing for the POC."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .gaze import GazeRefinementConfig, IrisGazeEstimate, estimate_iris_gaze, refine_local_point
from .landmarks import FaceSample, NormalizedPoint
from .monitors import MonitorInfo, VirtualCanvas


# FaceLandmarker (Tasks API) emits 468 mesh points + 10 refined iris points = 478.
# estimate_yaw_pitch reads index 362 and estimate_iris_gaze requires >=478, so the
# guard must demand the full set. The old guard (<264) let a partial face slip
# through and raise IndexError downstream (verified: gaze.py:51 needs 478).
_MIN_FACE_LANDMARKS = 478


@dataclass(frozen=True)
class HeadPointerEstimate:
    yaw: float
    pitch: float
    raw_x: float
    raw_y: float
    filtered_x: float
    filtered_y: float
    monitor: MonitorInfo
    region: str
    source: str = "head"
    local_x: float = 0.5
    local_y: float = 0.5
    gaze: IrisGazeEstimate | None = None


class HeadPointerMapper:
    """Map face landmarks to a coarse point on the virtual canvas."""

    def __init__(
        self,
        canvas: VirtualCanvas,
        gaze_config: GazeRefinementConfig | None = None,
        *,
        auto_center: bool = True,
        center_alpha: float = 0.03,
        max_center_offset: float = 0.38,
        min_gaze_confidence_for_center: float = 0.55,
        head_yaw_sign: float = 1.0,
        head_pitch_sign: float = 1.0,
    ) -> None:
        self.canvas = canvas
        self.gaze_config = gaze_config or GazeRefinementConfig()
        self.auto_center = auto_center
        # Sign of the matrix-derived yaw/pitch. The MediaPipe matrix uses an
        # OpenGL-style axis convention (#1642); the correct sign depends on
        # whether the frame is mirrored. Flip these if the cursor moves opposite
        # to the head. Defaults assume the mirrored (selfie) frame used by the POC.
        self.head_yaw_sign = float(head_yaw_sign)
        self.head_pitch_sign = float(head_pitch_sign)
        self.center_alpha = _clamp(center_alpha, 0.0, 1.0)
        self.max_center_offset = max(0.0, max_center_offset)
        self.min_gaze_confidence_for_center = _clamp(min_gaze_confidence_for_center, 0.0, 1.0)
        self._x_filter = OneEuroFilter()
        self._y_filter = OneEuroFilter()
        self._yaw_center = 0.0
        self._pitch_center = 0.0
        self._gaze_center_x = 0.0
        self._gaze_center_y = 0.0
        self._center_initialized = False

    def update(self, face: FaceSample | None, timestamp_s: float) -> HeadPointerEstimate | None:
        if face is None or len(face.landmarks) < _MIN_FACE_LANDMARKS:
            return None
        yaw, pitch, _pose_source = estimate_head_pose(
            face, yaw_sign=self.head_yaw_sign, pitch_sign=self.head_pitch_sign
        )
        gaze = estimate_iris_gaze(face.landmarks)
        if self.auto_center:
            self._update_center(yaw, pitch, gaze)
            yaw = _clamp(yaw - self._yaw_center, -_POSE_YAW_LIMIT, _POSE_YAW_LIMIT)
            pitch = _clamp(pitch - self._pitch_center, -_POSE_PITCH_LIMIT, _POSE_PITCH_LIMIT)
            if gaze is not None:
                gaze = IrisGazeEstimate(
                    x=_clamp(gaze.x - self._gaze_center_x, -0.55, 0.55),
                    y=_clamp(gaze.y - self._gaze_center_y, -0.55, 0.55),
                    confidence=gaze.confidence,
                    left_x=gaze.left_x,
                    left_y=gaze.left_y,
                    right_x=gaze.right_x,
                    right_y=gaze.right_y,
                )
        monitor = self.canvas.monitor_for_pose(yaw, pitch)
        head_local_x = _clamp(0.5 + yaw * 1.15, 0.0, 1.0)
        head_local_y = _clamp(0.5 + pitch * 1.05, 0.0, 1.0)
        local_x, local_y, source = refine_local_point(head_local_x, head_local_y, gaze, self.gaze_config)
        raw_x = monitor.rect.left + local_x * monitor.rect.width
        raw_y = monitor.rect.top + local_y * monitor.rect.height
        filtered_x = self._x_filter.filter(raw_x, timestamp_s)
        filtered_y = self._y_filter.filter(raw_y, timestamp_s)
        return HeadPointerEstimate(
            yaw=yaw,
            pitch=pitch,
            raw_x=raw_x,
            raw_y=raw_y,
            filtered_x=filtered_x,
            filtered_y=filtered_y,
            monitor=monitor,
            region=_region_name(local_x, local_y),
            source=f"{_pose_source}+{source}",
            local_x=local_x,
            local_y=local_y,
            gaze=gaze,
        )

    def _update_center(self, yaw: float, pitch: float, gaze: IrisGazeEstimate | None) -> None:
        if not self._center_initialized:
            self._yaw_center = _clamp(yaw, -self.max_center_offset, self.max_center_offset)
            self._pitch_center = _clamp(pitch, -self.max_center_offset, self.max_center_offset)
            if gaze is not None and gaze.confidence >= self.min_gaze_confidence_for_center:
                self._gaze_center_x = _clamp(gaze.x, -0.4, 0.4)
                self._gaze_center_y = _clamp(gaze.y, -0.4, 0.4)
            self._center_initialized = True
            return

        a = self.center_alpha
        self._yaw_center = _clamp(_lerp(self._yaw_center, yaw, a), -self.max_center_offset, self.max_center_offset)
        self._pitch_center = _clamp(
            _lerp(self._pitch_center, pitch, a),
            -self.max_center_offset,
            self.max_center_offset,
        )
        if gaze is not None and gaze.confidence >= self.min_gaze_confidence_for_center:
            self._gaze_center_x = _clamp(_lerp(self._gaze_center_x, gaze.x, a), -0.4, 0.4)
            self._gaze_center_y = _clamp(_lerp(self._gaze_center_y, gaze.y, a), -0.4, 0.4)


class OneEuroFilter:
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.025, d_cutoff: float = 1.0) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x: float | None = None
        self._dx: float = 0.0
        self._last_t: float | None = None

    def filter(self, value: float, timestamp_s: float) -> float:
        if self._last_t is None or self._x is None:
            self._last_t = timestamp_s
            self._x = value
            return value
        # Non-monotonic timestamp guard: a repeated or backward timestamp would
        # collapse dt toward the 1e-3 floor and make raw_dx explode (spurious
        # cursor jump). Mirror MediaPipe one_euro_filter.cc, which returns the
        # last value unchanged when the new timestamp is not strictly later.
        if timestamp_s <= self._last_t:
            return self._x
        dt = max(1e-3, timestamp_s - self._last_t)
        self._last_t = timestamp_s
        raw_dx = (value - self._x) / dt
        a_d = _alpha(self.d_cutoff, dt)
        self._dx = _lerp(self._dx, raw_dx, a_d)
        cutoff = self.min_cutoff + self.beta * abs(self._dx)
        a = _alpha(cutoff, dt)
        self._x = _lerp(self._x, value, a)
        return self._x


def estimate_yaw_pitch(landmarks: tuple[NormalizedPoint, ...]) -> tuple[float, float]:
    """Estimate coarse yaw/pitch from stable face-mesh landmarks (2D fallback).

    The values are normalized, not physical degrees. This 2D heuristic is the
    fallback used only when MediaPipe's facial transformation matrix is missing;
    estimate_head_pose() prefers the 3D matrix, which is far more stable on the
    side monitors (measured: lateral-monitor calibration error dominated by the
    weakness of this heuristic).
    """
    left_eye = _mean(landmarks[33], landmarks[133])
    right_eye = _mean(landmarks[263], landmarks[362])
    eye_mid = _mean(left_eye, right_eye)
    nose = landmarks[1]
    chin = landmarks[152]
    forehead = landmarks[10]
    eye_dist = max(_dist(left_eye, right_eye), 1e-6)
    face_height = max(_dist(forehead, chin), eye_dist)
    yaw = (nose.x - eye_mid.x) / eye_dist
    pitch = ((nose.y - eye_mid.y) / face_height - 0.33) * 2.4
    return (_clamp(yaw, -_POSE_YAW_LIMIT, _POSE_YAW_LIMIT), _clamp(pitch, -_POSE_PITCH_LIMIT, _POSE_PITCH_LIMIT))


# Gain mapping the matrix's radian yaw/pitch into a normalized range.
# ~30 deg (0.52 rad) of head turn maps to ~0.5 here.
_MATRIX_YAW_GAIN = 1.05
_MATRIX_PITCH_GAIN = 1.05

# Clamp range for raw pose. The old ±0.55 ceiling SATURATED the pitch when the
# user looked down at a monitor placed BELOW the others: every point on the
# bottom monitor collapsed to pitch=-0.55, so the calibration regression could
# not resolve vertical position there (measured: bottom-monitor RMS 322px with
# pitch pinned at -0.55, vs ~110px on the coplanar monitors). A wider range
# keeps the downward look resolvable. Vertical layouts need more pitch travel
# than horizontal needs yaw, so pitch gets the wider bound.
_POSE_YAW_LIMIT = 0.75
_POSE_PITCH_LIMIT = 0.95


def yaw_pitch_from_matrix(
    matrix: tuple[tuple[float, ...], ...] | None,
    *,
    yaw_sign: float = 1.0,
    pitch_sign: float = 1.0,
) -> tuple[float, float] | None:
    """Yaw/pitch (normalized) from MediaPipe's 4x4 facial transformation matrix.

    The matrix's upper-left 3x3 is the head rotation R (canonical face -> observed).
    Yaw  = atan2(-R[2][0], R[0][0])  (rotation about the vertical axis)
    Pitch= atan2(-R[2][1], R[2][2])  (rotation about the horizontal axis)
    is the standard extraction; signs depend on MediaPipe's OpenGL-style axis
    convention (google/mediapipe#1642) and must be fixed empirically against the
    real camera, hence the yaw_sign/pitch_sign knobs.
    """
    if not matrix or len(matrix) < 3 or any(len(row) < 3 for row in matrix[:3]):
        return None
    r = matrix
    try:
        yaw = math.atan2(-float(r[2][0]), float(r[0][0]))
        pitch = math.atan2(-float(r[2][1]), float(r[2][2]))
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(yaw) and math.isfinite(pitch)):
        return None
    yaw = _clamp(yaw_sign * yaw * _MATRIX_YAW_GAIN, -_POSE_YAW_LIMIT, _POSE_YAW_LIMIT)
    pitch = _clamp(pitch_sign * pitch * _MATRIX_PITCH_GAIN, -_POSE_PITCH_LIMIT, _POSE_PITCH_LIMIT)
    return (yaw, pitch)


def estimate_head_pose(
    face: FaceSample,
    *,
    yaw_sign: float = 1.0,
    pitch_sign: float = 1.0,
) -> tuple[float, float, str]:
    """Prefer the 3D transformation matrix; fall back to the 2D heuristic.

    Returns (yaw, pitch, source) where source is "matrix" or "heuristic2d".
    """
    from_matrix = yaw_pitch_from_matrix(
        face.transformation_matrix, yaw_sign=yaw_sign, pitch_sign=pitch_sign
    )
    if from_matrix is not None:
        return (from_matrix[0], from_matrix[1], "matrix")
    yaw, pitch = estimate_yaw_pitch(face.landmarks)
    return (yaw, pitch, "heuristic2d")


def jitter_rms_px(samples: list[tuple[float, float]]) -> float | None:
    if len(samples) < 2:
        return None
    cx = sum(x for x, _ in samples) / len(samples)
    cy = sum(y for _, y in samples) / len(samples)
    return math.sqrt(sum((x - cx) ** 2 + (y - cy) ** 2 for x, y in samples) / len(samples))


def frame_delta_rms_px(samples: list[tuple[float, float]]) -> float | None:
    if len(samples) < 2:
        return None
    deltas = [
        (samples[idx][0] - samples[idx - 1][0], samples[idx][1] - samples[idx - 1][1])
        for idx in range(1, len(samples))
    ]
    return math.sqrt(sum(dx * dx + dy * dy for dx, dy in deltas) / len(deltas))


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


def _lerp(old: float, new: float, alpha: float) -> float:
    return alpha * new + (1.0 - alpha) * old


def _dist(a: NormalizedPoint, b: NormalizedPoint) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def _mean(a: NormalizedPoint, b: NormalizedPoint) -> NormalizedPoint:
    return NormalizedPoint((a.x + b.x) / 2.0, (a.y + b.y) / 2.0, (a.z + b.z) / 2.0)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _region_name(local_x: float, local_y: float) -> str:
    col = "left" if local_x < 0.33 else "right" if local_x > 0.66 else "center"
    row = "top" if local_y < 0.33 else "bottom" if local_y > 0.66 else "middle"
    return f"{row}-{col}"
