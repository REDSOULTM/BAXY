from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np


def _candidate_module():
    return importlib.import_module(
        "experiments.mind_router_spike.measure_mtop_dual_oos_recovery"
    )


def test_mtop_loader_keeps_train_validation_and_contract_dispositions(
    tmp_path: Path,
) -> None:
    candidate = _candidate_module()
    source = tmp_path / "mtop.jsonl"
    rows = [
        {
            "source_id": "candidate",
            "split": "train",
            "text": "read my notes",
            "projection": {
                "disposition": "candidate",
                "families": ["note"],
            },
        },
        {
            "source_id": "missing",
            "split": "validation",
            "text": "remind me",
            "projection": {
                "disposition": "candidate_missing_information",
                "families": ["reminder"],
            },
        },
        {
            "source_id": "outside",
            "split": "validation",
            "text": "book a restaurant",
            "projection": {
                "disposition": "ood_no_effect",
                "families": [],
            },
        },
        {
            "source_id": "conversation",
            "split": "train",
            "text": "how do reminders work",
            "projection": {
                "disposition": "conversation_no_effect",
                "families": [],
            },
        },
    ]
    source.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    loaded = candidate.load_mtop_development_rows(source)

    assert [(row.source_id, row.split, row.inside_catalogue) for row in loaded] == [
        ("candidate", "train", True),
        ("missing", "validation", True),
        ("outside", "validation", False),
        ("conversation", "train", False),
    ]


def test_hard_negative_mask_keeps_only_routed_outside_rows() -> None:
    candidate = _candidate_module()

    mask = candidate.routed_hard_negative_mask(
        inside_mask=np.asarray([True, False, False, False]),
        lexical_margins=np.asarray([0.9, 0.049, 0.05, 0.8]),
        minimum_margin=0.05,
    )

    np.testing.assert_array_equal(mask, [False, False, True, True])
