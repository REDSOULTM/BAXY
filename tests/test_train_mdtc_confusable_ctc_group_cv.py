from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import torch


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_mdtc_confusable_ctc_group_cv.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_mdtc_confusable_ctc_group_cv", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_target_arrays_encode_target_confusable_and_filler() -> None:
    records = [
        {"phrase_id": "target"},
        {"phrase_id": "vaxi"},
        {"phrase_id": "unrelated"},
        {"speaker_group": "tarang_bakshi"},
    ]
    targets, lengths = MODULE.target_arrays(records, np.array([1, 0, 0, 0]))

    assert tuple(targets[0]) == MODULE.TARGET_IDS
    assert tuple(targets[1]) == MODULE.CONFUSABLE_IDS[0]
    assert lengths[2] == 0
    assert tuple(targets[3]) == MODULE.CONFUSABLE_IDS[3]


def test_margin_prefers_target_path_over_vaxi_path() -> None:
    logits = torch.full((2, 30, len(MODULE.VOCABULARY)), -8.0)
    logits[:, :, MODULE.BLANK_ID] = 4.0
    frames = (2, 7, 12, 17, 22)
    for frame, token in zip(frames, MODULE.TARGET_IDS, strict=True):
        logits[0, frame, token] = 12.0
    for frame, token in zip(frames, MODULE.CONFUSABLE_IDS[0], strict=True):
        logits[1, frame, token] = 12.0

    margins = MODULE.confusable_margins(torch, logits)

    assert margins[0] > 0
    assert margins[1] < 0


def test_explicit_confusable_mask_excludes_target_and_filler() -> None:
    targets = np.array(
        [MODULE.TARGET_IDS, MODULE.CONFUSABLE_IDS[0], (0, 0, 0, 0, 0)]
    )
    lengths = np.array([5, 5, 0])

    assert MODULE.explicit_confusable_mask(targets, lengths).tolist() == [
        False,
        True,
        False,
    ]
