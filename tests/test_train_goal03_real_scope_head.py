from __future__ import annotations

import numpy as np
import pytest

from experiments.mind_router_spike import train_goal03_real_scope_head as subject


def test_threshold_keeps_at_least_preregistered_fraction() -> None:
    scores = np.arange(477, dtype=np.float64)
    threshold = subject.threshold_for_keep(scores, 0.99)
    assert int((scores >= threshold).sum()) == 473


def test_deduplicate_rejects_conflicting_labels() -> None:
    with pytest.raises(ValueError, match="conflicting labels"):
        subject.deduplicate(
            [
                {"text": "Abre Spotify", "label": 1, "source": "one"},
                {"text": "ábre spotify", "label": 0, "source": "two"},
            ]
        )


def test_summarize_counts_action_and_oos_decisions() -> None:
    summary = subject.summarize(
        np.asarray([2.0, -1.0, 0.5, -0.5]),
        np.asarray([1, 0, 1, 0]),
        0.0,
    )
    assert summary["actions_kept"] == 2
    assert summary["oos_refused"] == 2
