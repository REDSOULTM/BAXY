from __future__ import annotations

from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "voice_latency"))

from evaluate_phoneme_teacher_category_oracle_v2 import (  # noqa: E402
    compress_category_logits,
)
from phoneme_student_vocabulary_v2 import CATEGORY_NAMES  # noqa: E402


def test_maxout_compression_preserves_a_retained_teacher_argmax() -> None:
    # B is the largest individual teacher token.  Many moderately likely
    # unrelated tokens must not sum into an artificial OTHER winner.
    teacher = torch.tensor([[[0.0, 5.0, 4.0, 4.0, 4.0]]])
    category_ids = {
        name: ((0,) if name == "blank" else (1,) if name == "B" else (2, 3, 4))
        for name in CATEGORY_NAMES
    }
    # Give every other retained singleton the harmless blank logit.  This is
    # only a projection-unit test; resolve_category_ids tests disjointness.
    for name in CATEGORY_NAMES:
        if name not in {"blank", "B", "other"}:
            category_ids[name] = (0,)

    compressed = compress_category_logits(torch, teacher, category_ids)

    assert int(compressed.argmax(dim=-1).item()) == CATEGORY_NAMES.index("B")
    assert torch.allclose(compressed.sum(dim=-1), torch.ones((1, 1)))
