from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import torch


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "train_mswc_spanish_qbye_angular_prototypical_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "train_mswc_spanish_qbye_angular_prototypical_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_angular_prototypical_logits_match_each_query_to_its_class() -> None:
    embeddings = torch.tensor(
        [
            [[1.0, 0.0], [0.9, 0.1], [1.0, 0.0]],
            [[0.0, 1.0], [0.1, 0.9], [0.0, 1.0]],
        ]
    )
    logits = MODULE.angular_prototypical_logits(
        torch, embeddings, torch.tensor(2.0)
    )
    assert torch.argmax(logits, dim=1).tolist() == [0, 1]


def test_attentive_statistics_model_outputs_unit_embeddings() -> None:
    model = MODULE.make_model(torch, hidden_size=8, embedding_size=4).eval()
    values = torch.randn(3, 7, 8)
    mask = torch.tensor(
        [
            [True] * 7,
            [True] * 5 + [False] * 2,
            [True] * 3 + [False] * 4,
        ]
    )
    output = model(values, mask)
    assert output.shape == (3, 4)
    np.testing.assert_allclose(
        torch.linalg.norm(output, dim=1).detach().numpy(), np.ones(3), atol=1e-5
    )


def test_hardest_impostor_loss_rewards_a_wider_margin() -> None:
    narrow = torch.tensor(
        [
            [[1.0, 0.0], [0.8, 0.2]],
            [[0.7, 0.3], [0.6, 0.4]],
        ]
    )
    wide = torch.tensor(
        [
            [[1.0, 0.0], [1.0, 0.0]],
            [[0.0, 1.0], [0.0, 1.0]],
        ]
    )
    narrow_loss = MODULE.hardest_impostor_margin_loss(torch, narrow, margin=0.2)
    wide_loss = MODULE.hardest_impostor_margin_loss(torch, wide, margin=0.2)
    assert wide_loss < narrow_loss


def test_tail_checkpoint_rank_prioritizes_zero_false_recall_after_core_gate() -> None:
    stronger_tail = {
        "top1_accuracy": 0.94,
        "pair_auc": 0.997,
        "equal_error_rate": 0.02,
        "true_pairs_accepted_at_zero_false_pairs": 400,
        "true_pairs": 1000,
    }
    stronger_top1 = {
        **stronger_tail,
        "top1_accuracy": 0.95,
        "true_pairs_accepted_at_zero_false_pairs": 300,
    }
    assert MODULE.checkpoint_rank(
        stronger_tail, "tail_zero_false"
    ) > MODULE.checkpoint_rank(stronger_top1, "tail_zero_false")
