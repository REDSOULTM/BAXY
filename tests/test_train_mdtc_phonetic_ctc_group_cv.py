from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import torch


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_mdtc_phonetic_ctc_group_cv.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_mdtc_phonetic_ctc_group_cv", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_ctc_training_loss_is_finite_for_positive_and_empty_negative() -> None:
    logits = torch.zeros(2, 20, len(MODULE.VOCABULARY))
    labels = torch.tensor([1, 0])

    losses = MODULE.ctc_training_losses(torch, logits, labels)

    assert losses.shape == (2,)
    assert torch.isfinite(losses).all()


def test_ctc_target_margin_prefers_exact_path_over_blank() -> None:
    logits = torch.full((2, 20, len(MODULE.VOCABULARY)), -8.0)
    logits[:, :, MODULE.BLANK_ID] = 4.0
    for frame, token in zip((2, 5, 8, 11, 14), MODULE.TARGET_IDS, strict=True):
        logits[0, frame, token] = 12.0

    margins = MODULE.ctc_target_margins(torch, logits)

    assert margins[0] > margins[1]
    assert np.isfinite(margins.numpy()).all()
