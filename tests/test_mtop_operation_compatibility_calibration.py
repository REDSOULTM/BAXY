from __future__ import annotations

import numpy as np

from experiments.mind_router_spike.calibrate_mtop_operation_compatibility import (
    _select_threshold,
)


def test_threshold_selection_maximizes_the_weaker_pair_boundary() -> None:
    selected = _select_threshold(
        np.asarray([0.91, 0.82, 0.72, 0.62]),
        np.asarray([0.58, 0.41, 0.31, 0.12]),
    )

    assert selected is not None
    assert 0.58 < selected["threshold"] <= 0.62
    assert selected["compatible_accuracy"] == 1.0
    assert selected["incompatible_accuracy"] == 1.0
