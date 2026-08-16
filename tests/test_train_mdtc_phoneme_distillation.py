from __future__ import annotations

import importlib.util
from pathlib import Path

import torch


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_mdtc_phoneme_distillation.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_mdtc_phoneme_distillation", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_distillation_loss_upweights_speech_frames_without_shape_change() -> None:
    logits = torch.zeros(2, 3, MODULE.CATEGORY_COUNT)
    teacher = torch.zeros_like(logits)
    teacher[:, :, MODULE.BLANK_ID] = 1.0
    teacher[0, 1, MODULE.BLANK_ID] = 0.0
    teacher[0, 1, 1] = 1.0

    losses = MODULE.posterior_distillation_losses(
        torch, logits, teacher, speech_frame_weight=16.0
    )

    assert losses.shape == (2,)
    assert torch.isfinite(losses).all()


def test_logits_pairs_prefers_target_over_vaxi_path() -> None:
    logits = torch.full((2, 30, MODULE.CATEGORY_COUNT), -8.0)
    logits[:, :, MODULE.BLANK_ID] = 4.0
    frames = (2, 7, 12, 17, 22)
    for frame, token in zip(frames, MODULE.TARGET_IDS, strict=True):
        logits[0, frame, token] = 12.0
    for frame, token in zip(frames, MODULE.CONFUSABLE_IDS[0], strict=True):
        logits[1, frame, token] = 12.0

    pairs = MODULE.logits_pairs(torch, logits)

    assert pairs[0, 1] > 0
    assert pairs[1, 1] < 0
