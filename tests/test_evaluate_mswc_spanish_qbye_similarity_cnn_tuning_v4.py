from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_qbye_similarity_cnn_tuning_v4.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_qbye_similarity_cnn_tuning_v4", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_pair_scores_use_maximum_enrollment_template() -> None:
    values = MODULE.maximum_pair_scores(
        pair_scores=np.asarray([0.2, 0.8, -0.1]),
        query_rows=[0, 0, 1],
        class_indexes=[1, 1, 0],
        shape=(2, 2),
        floor=-100.0,
    )
    assert values[0, 1] == 0.8
    assert values[1, 0] == -0.1
    assert values[0, 0] == -100.0
