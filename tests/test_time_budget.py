from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind.time_budget import remaining_seconds


def test_remaining_seconds_caps_upward_float_rounding() -> None:
    now = 133_604.703
    maximum = 0.04
    deadline = now + maximum

    assert deadline - now > maximum
    assert remaining_seconds(deadline, maximum, now=now) == maximum


@pytest.mark.parametrize(
    ("deadline", "maximum", "now"),
    [
        (1.0, 0.0, 0.0),
        (1.0, -1.0, 0.0),
        (1.0, 1.0, 2.0),
        (math.nan, 1.0, 0.0),
        (1.0, math.nan, 0.0),
        (1.0, 1.0, math.inf),
    ],
)
def test_remaining_seconds_closes_invalid_or_expired_budgets(
    deadline: float,
    maximum: float,
    now: float,
) -> None:
    assert remaining_seconds(deadline, maximum, now=now) == 0.0


def test_remaining_seconds_uses_injected_current_time() -> None:
    assert remaining_seconds(10.0, 4.0, now=7.5) == 2.5


def test_remaining_seconds_uses_the_monotonic_clock_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "baxy_mind.time_budget.time.monotonic",
        lambda: 7.5,
    )

    assert remaining_seconds(10.0, 4.0) == 2.5
