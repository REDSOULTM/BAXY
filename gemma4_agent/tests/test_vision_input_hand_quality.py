from gemma4_agent.vision_input.gestures import GestureResult
from gemma4_agent.vision_input.hand_quality import (
    GestureStateFilter,
    HandIdentityTracker,
    HandQuality,
    HandQualityGate,
)
from gemma4_agent.vision_input.landmarks import HandSample, NormalizedPoint


def _hand(cx: float, cy: float, *, handedness: str = "", score: float = 0.9) -> HandSample:
    pts = [NormalizedPoint(cx, cy, 0.0) for _ in range(21)]
    pts[0] = NormalizedPoint(cx, cy + 0.06, 0.0)
    pts[5] = NormalizedPoint(cx - 0.06, cy, 0.0)
    pts[9] = NormalizedPoint(cx, cy - 0.07, 0.0)
    pts[13] = NormalizedPoint(cx + 0.035, cy, 0.0)
    pts[17] = NormalizedPoint(cx + 0.07, cy, 0.0)
    return HandSample(tuple(pts), handedness=handedness, score=score)


def _quality(ok: bool = True) -> HandQuality:
    return HandQuality(ok, "good" if ok else "edge", 0.5, 0.5, 0.1, 0.9)


def test_hand_quality_rejects_edge_hands() -> None:
    gate = HandQualityGate()

    result = gate.evaluate("left", _hand(0.01, 0.5))

    assert result.ok is False
    assert result.reason == "edge"


def test_hand_identity_tracker_prefers_handedness() -> None:
    tracker = HandIdentityTracker()

    assigned = tracker.assign((_hand(0.7, 0.5, handedness="Right"), _hand(0.3, 0.5, handedness="Left")))

    assert {track_id for track_id, _ in assigned} == {"left", "right"}


def test_gesture_state_filter_requires_enter_frames() -> None:
    filt = GestureStateFilter(enter_frames=2, exit_frames=2)

    first = filt.update("left", GestureResult("point", 0.9), _quality(True))
    second = filt.update("left", GestureResult("point", 0.9), _quality(True))

    assert first == "none"
    assert second == "point"


def test_gesture_state_filter_exits_after_bad_quality() -> None:
    filt = GestureStateFilter(enter_frames=1, exit_frames=2)
    filt.update("left", GestureResult("palm", 0.9), _quality(True))

    first_bad = filt.update("left", GestureResult("palm", 0.9), _quality(False))
    second_bad = filt.update("left", GestureResult("palm", 0.9), _quality(False))

    assert first_bad == "palm"
    assert second_bad == "none"
