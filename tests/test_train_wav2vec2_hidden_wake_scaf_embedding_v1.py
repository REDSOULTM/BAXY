from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import torch


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_wav2vec2_hidden_wake_scaf_embedding_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_wav2vec2_hidden_wake_scaf_embedding_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_fixed_sequence_crops_and_pads_with_mask() -> None:
    short, short_mask = MODULE.fixed_sequence(np.ones((3, 2)), 5)
    assert short.shape == (5, 2)
    assert short_mask.tolist() == [True, True, True, False, False]
    long, long_mask = MODULE.fixed_sequence(np.arange(14).reshape(7, 2), 5)
    assert long.tolist() == np.arange(14).reshape(7, 2)[1:6].tolist()
    assert long_mask.all()


def test_arcface_margin_only_reduces_target_logit() -> None:
    embeddings = torch.nn.functional.normalize(torch.tensor([[1.0, 0.2]]), dim=-1)
    centers = torch.tensor([[[1.0, 0.0]], [[0.0, 1.0]]])
    labels = torch.tensor([0])
    plain = MODULE.class_cosines(torch, embeddings, centers) * 10.0
    margin = MODULE.subcenter_arcface_logits(
        torch, embeddings, centers, labels, margin=0.2, scale=10.0
    )
    assert margin[0, 0] < plain[0, 0]
    assert margin[0, 1] == plain[0, 1]


def test_human_group_margins_are_speaker_held_out() -> None:
    aligned = np.asarray(
        [[1.0, 0.0], [1.0, 0.0], [0.0, 0.0], [0.0, 0.0], [1.0, 0.0], [0.0, 0.0]]
    )
    scans = [
        np.asarray([[1.0, 0.0]]),
        np.asarray([[1.0, 0.0]]),
        np.asarray([[0.0, 1.0]]),
        np.asarray([[0.0, 1.0]]),
        np.asarray([[1.0, 0.0]]),
        np.asarray([[0.0, 1.0]]),
    ]
    labels = np.asarray([1, 1, 0, 0, 1, 0])
    margins, folds = MODULE.human_group_margins(
        aligned_positive_embeddings=aligned,
        scan_embeddings=scans,
        labels=labels,
        groups=["a", "b", "a", "b", "c", "c"],
    )
    assert np.all(margins[labels == 1] > 0.0)
    assert np.all(margins[labels == 0] < 0.0)
    assert {fold["held_group"] for fold in folds} == {"a", "b", "c"}
