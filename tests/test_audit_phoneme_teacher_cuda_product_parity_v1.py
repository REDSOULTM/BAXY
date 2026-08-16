from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_phoneme_teacher_cuda_product_parity_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_phoneme_teacher_cuda_product_parity_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_batch_category_compression_matches_softmax_contract() -> None:
    logits = np.asarray(
        [
            [
                [4.0, 1.0, 2.0, 0.0],
                [0.0, 2.0, 1.0, 4.0],
            ]
        ],
        dtype=np.float32,
    )
    result = MODULE.compress_category_logits_batch(
        logits,
        {"blank": (0,), "target": (1, 2), "other": (3,)},
        ("blank", "target", "other"),
    )
    assert result.shape == (1, 2, 3)
    assert np.allclose(result.sum(axis=2), 1.0)
    assert np.argmax(result[0, 0]) == 0
    assert np.argmax(result[0, 1]) == 2


def test_full_clip_margins_vectorize_over_batch() -> None:
    class Wake:
        CATEGORY_NAMES = ("blank", "a", "b")
        BLANK_ID = 0
        TARGET_IDS = ((1,),)
        CONFUSABLE_IDS = ((2,),)

    probabilities = np.asarray(
        [
            [[0.2, 0.7, 0.1], [0.2, 0.7, 0.1]],
            [[0.2, 0.1, 0.7], [0.2, 0.1, 0.7]],
        ],
        dtype=np.float64,
    )
    margins = MODULE.full_clip_ctc_margins(probabilities, Wake)
    assert margins.shape == (2,)
    assert margins[0] > 0.0
    assert margins[1] < 0.0
