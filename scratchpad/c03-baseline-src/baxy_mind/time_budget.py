"""Exact monotonic-budget arithmetic shared by local runtime owners."""

from __future__ import annotations

import math
import time


def remaining_seconds(
    deadline: float,
    maximum: float,
    *,
    now: float | None = None,
) -> float:
    """Return a finite remainder in ``[0, maximum]``.

    Adding a small duration to a large monotonic timestamp can round upward.
    Capping the subtraction by the original duration keeps every downstream
    wait inside the budget the caller actually granted.
    """

    try:
        finite_deadline = float(deadline)
        finite_maximum = float(maximum)
        current = time.monotonic() if now is None else float(now)
    except (TypeError, ValueError):
        return 0.0
    if (
        not math.isfinite(finite_deadline)
        or not math.isfinite(finite_maximum)
        or not math.isfinite(current)
        or finite_maximum <= 0.0
    ):
        return 0.0
    return min(
        finite_maximum,
        max(0.0, finite_deadline - current),
    )


__all__ = ["remaining_seconds"]
