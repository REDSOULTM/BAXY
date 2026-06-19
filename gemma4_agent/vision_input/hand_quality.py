"""Hand quality, identity tracking, and gesture-state filtering."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .gestures import GestureResult
from .landmarks import HandSample, NormalizedPoint


ACTIVE_GESTURES = {"fist", "palm", "point", "pinch", "two_fingers"}


@dataclass(frozen=True)
class HandQualityConfig:
    min_score: float = 0.45
    edge_margin: float = 0.035
    max_jump_norm: float = 0.28
    min_palm_size: float = 0.035
    max_palm_size: float = 0.55
    min_two_hand_distance: float = 0.085


@dataclass(frozen=True)
class HandQuality:
    ok: bool
    reason: str
    center_x: float
    center_y: float
    palm_size: float
    score: float | None
    jump: float = 0.0


@dataclass(frozen=True)
class TrackedHand:
    track_id: str
    sample: HandSample
    quality: HandQuality
    raw_gesture: GestureResult
    stable_label: str


class HandIdentityTracker:
    """Keep hand identities stable across frames.

    MediaPipe can reorder hands when one hand disappears or crosses another.
    This tracker prefers handedness and nearest previous center, falling back to
    left-to-right order only when no previous track exists.
    """

    def __init__(self, max_jump_norm: float = 0.35) -> None:
        self.max_jump_norm = max(0.05, float(max_jump_norm))
        self._previous: dict[str, tuple[float, float]] = {}

    def assign(self, hands: Iterable[HandSample]) -> tuple[tuple[str, HandSample], ...]:
        items = list(hands)
        if not items:
            self._previous.clear()
            return ()
        labels = self._preferred_ids(items)
        assigned: list[tuple[str, HandSample]] = []
        used_ids: set[str] = set()
        for hand in sorted(items, key=lambda item: _hand_center(item)[0]):
            center = _hand_center(hand)
            candidate_ids = labels.get(id(hand), ())
            best_id = None
            best_dist = float("inf")
            for candidate in candidate_ids:
                if candidate in used_ids:
                    continue
                prev = self._previous.get(candidate)
                dist = 0.0 if prev is None else math.hypot(center[0] - prev[0], center[1] - prev[1])
                if dist < best_dist:
                    best_id = candidate
                    best_dist = dist
            if best_id is None or (best_dist > self.max_jump_norm and len(items) <= len(self._previous)):
                best_id = _first_free(("left", "right", "hand0", "hand1"), used_ids)
            used_ids.add(best_id)
            assigned.append((best_id, hand))
        self._previous = {track_id: _hand_center(hand) for track_id, hand in assigned}
        return tuple(assigned)

    def reset(self) -> None:
        self._previous.clear()

    def _preferred_ids(self, hands: list[HandSample]) -> dict[int, tuple[str, ...]]:
        sorted_hands = sorted(hands, key=lambda item: _hand_center(item)[0])
        out: dict[int, tuple[str, ...]] = {}
        for idx, hand in enumerate(sorted_hands):
            handed = (hand.handedness or "").lower()
            if handed.startswith("left"):
                out[id(hand)] = ("left", "hand0", "right", "hand1")
            elif handed.startswith("right"):
                out[id(hand)] = ("right", "hand1", "left", "hand0")
            else:
                out[id(hand)] = ("left", "hand0", "right", "hand1") if idx == 0 else ("right", "hand1", "left", "hand0")
        return out


class GestureStateFilter:
    """Gesture hysteresis with per-track state and minimum hold frames."""

    def __init__(
        self,
        *,
        enter_frames: int = 2,
        exit_frames: int = 2,
        min_confidence: float = 0.50,
    ) -> None:
        self.enter_frames = max(1, int(enter_frames))
        self.exit_frames = max(1, int(exit_frames))
        self.min_confidence = max(0.0, min(1.0, float(min_confidence)))
        self._state: dict[str, str] = {}
        self._candidate: dict[str, str] = {}
        self._candidate_count: dict[str, int] = {}
        self._missing_count: dict[str, int] = {}


    def update(self, track_id: str, raw: GestureResult, quality: HandQuality) -> str:
        current = self._state.get(track_id, "none")
        if not quality.ok or raw.confidence < self.min_confidence:
            self._missing_count[track_id] = self._missing_count.get(track_id, 0) + 1
            if self._missing_count[track_id] >= self.exit_frames:
                self._state[track_id] = "none"
                self._candidate.pop(track_id, None)
                self._candidate_count.pop(track_id, None)
            return self._state.get(track_id, "none")

        self._missing_count[track_id] = 0
        label = raw.label if raw.label in ACTIVE_GESTURES else "none"
        if label == current:
            self._candidate.pop(track_id, None)
            self._candidate_count.pop(track_id, None)
            return current

        if self._candidate.get(track_id) != label:
            self._candidate[track_id] = label
            self._candidate_count[track_id] = 1
        else:
            self._candidate_count[track_id] = self._candidate_count.get(track_id, 0) + 1

        needed = self.exit_frames if label == "none" else self.enter_frames
        if self._candidate_count[track_id] >= needed:
            self._state[track_id] = label
            self._candidate.pop(track_id, None)
            self._candidate_count.pop(track_id, None)
        return self._state.get(track_id, "none")

    def reset_missing(self, active_ids: set[str]) -> None:
        for track_id in list(self._state):
            if track_id not in active_ids:
                self._missing_count[track_id] = self._missing_count.get(track_id, 0) + 1
                if self._missing_count[track_id] >= self.exit_frames:
                    self._state.pop(track_id, None)
                    self._candidate.pop(track_id, None)
                    self._candidate_count.pop(track_id, None)

    def reset(self) -> None:
        self._state.clear()
        self._candidate.clear()
        self._candidate_count.clear()
        self._missing_count.clear()


class HandQualityGate:
    def __init__(self, config: HandQualityConfig | None = None) -> None:
        self.config = config or HandQualityConfig()
        self._last_center: dict[str, tuple[float, float]] = {}

    def evaluate(
        self,
        track_id: str,
        hand: HandSample,
        *,
        other_centers: tuple[tuple[float, float], ...] = (),
    ) -> HandQuality:
        center = _hand_center(hand)
        palm = _palm_size(hand)
        score = hand.score
        reason = "good"
        ok = True
        if score is not None and score < self.config.min_score:
            ok, reason = False, "low_score"
        elif _near_edge(center, self.config.edge_margin):
            ok, reason = False, "edge"
        elif palm < self.config.min_palm_size:
            ok, reason = False, "too_small"
        elif palm > self.config.max_palm_size:
            ok, reason = False, "too_large"
        elif any(math.hypot(center[0] - ox, center[1] - oy) < self.config.min_two_hand_distance for ox, oy in other_centers):
            ok, reason = False, "occluded"
        previous = self._last_center.get(track_id)
        jump = 0.0 if previous is None else math.hypot(center[0] - previous[0], center[1] - previous[1])
        if ok and jump > self.config.max_jump_norm:
            ok, reason = False, "jump"
        self._last_center[track_id] = center
        return HandQuality(ok, reason, center[0], center[1], palm, score, jump)

    def reset(self) -> None:
        self._last_center.clear()


def _first_free(candidates: tuple[str, ...], used: set[str]) -> str:
    for candidate in candidates:
        if candidate not in used:
            return candidate
    return f"hand{len(used)}"


def _hand_center(hand: HandSample) -> tuple[float, float]:
    points = hand.landmarks
    indexes = (0, 5, 9, 13, 17)
    usable = [points[idx] for idx in indexes if idx < len(points)]
    if not usable:
        return (0.5, 0.5)
    return (
        sum(p.x for p in usable) / len(usable),
        sum(p.y for p in usable) / len(usable),
    )


def _palm_size(hand: HandSample) -> float:
    points = hand.landmarks
    if len(points) < 18:
        return 0.0
    return max(_dist(points[0], points[9]), _dist(points[5], points[17]))


def _near_edge(center: tuple[float, float], margin: float) -> bool:
    m = max(0.0, min(0.25, float(margin)))
    return center[0] < m or center[0] > 1.0 - m or center[1] < m or center[1] > 1.0 - m


def _dist(a: NormalizedPoint, b: NormalizedPoint) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)
