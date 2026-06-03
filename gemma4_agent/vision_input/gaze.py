"""Deterministic iris-based gaze refinement.

This is not a semantic model and does not call the LLM. It only uses MediaPipe
face landmarks: iris center relative to each eye box. Calibration can later map
these features to exact screen coordinates; this module provides the stable
geometry primitive.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .landmarks import NormalizedPoint


LEFT_EYE_CORNERS = (33, 133)
LEFT_EYE_VERTICAL = (159, 145)
RIGHT_EYE_CORNERS = (362, 263)
RIGHT_EYE_VERTICAL = (386, 374)
LEFT_IRIS = (468, 469, 470, 471, 472)
RIGHT_IRIS = (473, 474, 475, 476, 477)

# Eye-aspect-ratio (height/width) below which the eye is treated as closed and
# its gaze sample is invalidated. A fully open eye is ~0.25-0.35; a blink drops
# toward ~0.1. Chosen conservatively so a half-closed eye still counts.
# Source: Soukupova & Cech 2016 (EAR for blink detection) adapted to the
# Face Mesh corner/lid landmark spacing — hypothesis, refine against a fixture.
_EYE_CLOSED_EAR = 0.12
# Maximum left/right disagreement (in eye-box units) before we stop trusting a
# binocular estimate. Beyond this the two eyes contradict each other.
_MAX_BINOCULAR_SPREAD = 0.45


@dataclass(frozen=True)
class IrisGazeEstimate:
    x: float
    y: float
    confidence: float
    left_x: float | None = None
    left_y: float | None = None
    right_x: float | None = None
    right_y: float | None = None


@dataclass(frozen=True)
class GazeRefinementConfig:
    enabled: bool = True
    gain_x: float = 0.62
    gain_y: float = 0.42
    deadzone: float = 0.025
    max_offset: float = 0.32
    min_confidence: float = 0.35


def estimate_iris_gaze(landmarks: tuple[NormalizedPoint, ...]) -> IrisGazeEstimate | None:
    """Return normalized gaze offset from iris landmarks.

    x/y are centered around 0.0. Positive x means iris center is toward image
    right; positive y means iris center is lower in the eye box.
    """
    if len(landmarks) < 478:
        return None
    left = _eye_offset(landmarks, LEFT_EYE_CORNERS, LEFT_EYE_VERTICAL, LEFT_IRIS)
    right = _eye_offset(landmarks, RIGHT_EYE_CORNERS, RIGHT_EYE_VERTICAL, RIGHT_IRIS)
    usable = [item for item in (left, right) if item is not None]
    if not usable:
        return None
    x = sum(item[0] for item in usable) / len(usable)
    y = sum(item[1] for item in usable) / len(usable)
    confidence = _gaze_confidence(left, right)
    return IrisGazeEstimate(
        x=_clamp(x, -0.55, 0.55),
        y=_clamp(y, -0.55, 0.55),
        confidence=confidence,
        left_x=left[0] if left is not None else None,
        left_y=left[1] if left is not None else None,
        right_x=right[0] if right is not None else None,
        right_y=right[1] if right is not None else None,
    )


def _gaze_confidence(
    left: tuple[float, float] | None,
    right: tuple[float, float] | None,
) -> float:
    """Confidence in [0, 1] derived from real signals, so min_confidence bites.

    The previous model returned a fixed 0.92 for a single eye (rewarding the
    worst case) and never dropped below 0.47 with two eyes, making any
    min_confidence <= 0.47 a dead gate. Here:
      - Two eyes that AGREE earn high confidence; disagreement (spread) lowers it.
      - A single usable eye is penalized hard (monocular gaze is ambiguous).
      - No usable eye -> caller already returned None upstream.
    """
    have_left = left is not None
    have_right = right is not None
    if have_left and have_right:
        spread = min(_MAX_BINOCULAR_SPREAD, math.hypot(left[0] - right[0], left[1] - right[1]))
        # 0.95 when the eyes coincide, decaying to ~0.40 at max disagreement.
        return _clamp(0.95 - (spread / _MAX_BINOCULAR_SPREAD) * 0.55, 0.0, 1.0)
    if have_left or have_right:
        # Monocular: usable but ambiguous -> below typical min_confidence so the
        # refinement is skipped unless the caller explicitly lowers the bar.
        return 0.30
    return 0.0


def refine_local_point(
    local_x: float,
    local_y: float,
    gaze: IrisGazeEstimate | None,
    config: GazeRefinementConfig | None = None,
) -> tuple[float, float, str]:
    cfg = config or GazeRefinementConfig()
    if not cfg.enabled or gaze is None or gaze.confidence < cfg.min_confidence:
        return (_clamp(local_x, 0.0, 1.0), _clamp(local_y, 0.0, 1.0), "head")
    gx = _deadzone(gaze.x, cfg.deadzone)
    gy = _deadzone(gaze.y, cfg.deadzone)
    offset_x = _clamp(gx * cfg.gain_x, -cfg.max_offset, cfg.max_offset)
    offset_y = _clamp(gy * cfg.gain_y, -cfg.max_offset, cfg.max_offset)
    return (
        _clamp(local_x + offset_x, 0.0, 1.0),
        _clamp(local_y + offset_y, 0.0, 1.0),
        "head+iris",
    )


def _eye_offset(
    landmarks: tuple[NormalizedPoint, ...],
    corner_indexes: tuple[int, int],
    vertical_indexes: tuple[int, int],
    iris_indexes: tuple[int, ...],
) -> tuple[float, float] | None:
    try:
        corners = [landmarks[idx] for idx in corner_indexes]
        vertical = [landmarks[idx] for idx in vertical_indexes]
        iris = [landmarks[idx] for idx in iris_indexes]
    except IndexError:
        return None
    x_min = min(p.x for p in corners)
    x_max = max(p.x for p in corners)
    y_min = min(p.y for p in vertical + corners)
    y_max = max(p.y for p in vertical + corners)
    width = x_max - x_min
    height = y_max - y_min
    if width <= 1e-6 or height <= 1e-6:
        return None
    # Eye-aspect-ratio gate: a closed/blinking eye has a tiny vertical extent,
    # so the iris-vs-eye-box offset on the Y axis is meaningless. Invalidate it
    # rather than feeding a garbage vertical reading into the average.
    lid_gap = max(p.y for p in vertical) - min(p.y for p in vertical)
    if (lid_gap / width) < _EYE_CLOSED_EAR:
        return None
    center = _mean(iris)
    x = (center.x - x_min) / width - 0.5
    y = (center.y - y_min) / height - 0.5
    if abs(x) > 1.1 or abs(y) > 1.1:
        return None
    return (x, y)


def _mean(points: list[NormalizedPoint]) -> NormalizedPoint:
    n = float(len(points))
    return NormalizedPoint(
        sum(p.x for p in points) / n,
        sum(p.y for p in points) / n,
        sum(p.z for p in points) / n,
    )


def _deadzone(value: float, zone: float) -> float:
    zone = max(0.0, zone)
    if abs(value) <= zone:
        return 0.0
    return value - math.copysign(zone, value)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
