from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_text_ctc_tuning_v4.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_text_ctc_tuning_v4", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_score_text_candidates_uses_each_query_and_candidate_sequence() -> None:
    probabilities = np.log(
        np.asarray(
            [
                [0.7, 0.2, 0.1],
                [0.1, 0.8, 0.1],
                [0.7, 0.1, 0.2],
                [0.1, 0.1, 0.8],
            ],
            dtype=np.float64,
        )
    )
    scores, lengths = MODULE.score_text_candidates(
        ctc_log_probabilities=probabilities,
        offsets=np.asarray([0, 2, 4]),
        query_indexes=[0, 1],
        candidate_indexes=np.asarray([[0, 1], [1, 0]]),
        text_sequences=[[1], [2]],
        blank_id=0,
    )
    assert scores.shape == lengths.shape == (2, 2)
    assert scores[0, 0] > scores[0, 1]
    assert scores[1, 0] > scores[1, 1]
    assert np.all(lengths == 1)
