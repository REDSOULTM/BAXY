"""Offline confusion-matrix + invariance gate for the geometric gesture recognizer.

This replaces the need to hand-collect 50 manual gesture samples per run: the
recognizer is validated against a versioned, commercial-OK fixture of real
MediaPipe 21-landmark hands (kinivi keypoint.csv subset, Apache-2.0). See
fixtures/hand_landmarks/NOTICE.md for attribution and the regeneration recipe.

Gate (plan P9): per-class accuracy of palm/fist/point >= 0.95 on the fixture,
and the recognizer is invariant to in-plane rotation and to translation/scale of
the input landmarks (those are not part of any gesture's meaning).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from gemma4_agent.vision_input.gestures import recognize_hand_gesture
from gemma4_agent.vision_input.landmarks import HandSample, NormalizedPoint

FIXTURE = Path(__file__).parent / "fixtures" / "hand_landmarks" / "kinivi_keypoint_subset.csv"

# kinivi label -> our gesture vocabulary. Label 3 (kinivi "OK") is intentionally
# excluded: it is geometrically distinct from our "pinch".
KINIVI_TO_GESTURE = {0: "palm", 1: "fist", 2: "point"}
ACCURACY_GATE = 0.95


def _load_fixture() -> list[tuple[str, HandSample]]:
    samples: list[tuple[str, HandSample]] = []
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        label = int(parts[0])
        if label not in KINIVI_TO_GESTURE:
            continue
        vals = [float(v) for v in parts[1:]]
        pts = tuple(NormalizedPoint(vals[2 * i], vals[2 * i + 1], 0.0) for i in range(21))
        samples.append((KINIVI_TO_GESTURE[label], HandSample(pts)))
    return samples


def _confusion(samples: list[tuple[str, HandSample]]) -> dict[str, Counter]:
    conf: dict[str, Counter] = defaultdict(Counter)
    for truth, hand in samples:
        conf[truth][recognize_hand_gesture(hand).label] += 1
    return conf


def test_fixture_present_and_balanced() -> None:
    samples = _load_fixture()
    counts = Counter(truth for truth, _ in samples)
    assert set(counts) == {"palm", "fist", "point"}
    for gesture in ("palm", "fist", "point"):
        assert counts[gesture] >= 200  # representative sample size per class


@pytest.mark.parametrize("gesture", ["palm", "fist", "point"])
def test_per_class_accuracy_meets_gate(gesture: str) -> None:
    conf = _confusion(_load_fixture())
    total = sum(conf[gesture].values())
    correct = conf[gesture][gesture]
    accuracy = correct / total
    assert accuracy >= ACCURACY_GATE, (
        f"{gesture} accuracy {accuracy:.3f} < {ACCURACY_GATE}; "
        f"distribution={dict(conf[gesture])}"
    )


def test_no_fist_misread_as_pinch() -> None:
    # A false pinch is a false click -> the most damaging confusion. The tightened
    # pinch rule (flex_count <= 1) must keep this at zero on the fixture.
    conf = _confusion(_load_fixture())
    assert conf["fist"]["pinch"] == 0


def _rotate(hand: HandSample, degrees: float, *, scale: float = 1.0, shift: float = 0.0) -> HandSample:
    """Rotate landmarks in-plane about the wrist, optionally scale and translate."""
    theta = math.radians(degrees)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    wrist = hand.landmarks[0]
    out = []
    for p in hand.landmarks:
        dx, dy = p.x - wrist.x, p.y - wrist.y
        rx = (dx * cos_t - dy * sin_t) * scale + wrist.x + shift
        ry = (dx * sin_t + dy * cos_t) * scale + wrist.y + shift
        out.append(NormalizedPoint(rx, ry, 0.0))
    return HandSample(tuple(out))


def test_recognizer_invariant_to_rotation_translation_scale() -> None:
    # The recognizer's features are distances/angles between landmarks, which are
    # inherently invariant to in-plane rotation, translation and uniform scale.
    # This pins that property: a clean gesture keeps its label under those.
    samples = _load_fixture()
    # Use only clean, correctly-classified samples so we test invariance, not
    # the recognizer's borderline cases.
    clean = [(g, h) for g, h in samples if recognize_hand_gesture(h).label == g]
    assert len(clean) >= 100
    checked = 0
    for gesture, hand in clean[:150]:
        for deg in (15.0, -30.0, 45.0):
            for scale, shift in ((1.0, 0.0), (1.7, 0.0), (1.0, 0.3)):
                transformed = _rotate(hand, deg, scale=scale, shift=shift)
                assert recognize_hand_gesture(transformed).label == gesture
                checked += 1
    assert checked > 0
