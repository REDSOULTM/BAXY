from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src", ROOT / "scripts", ROOT / "experiments/mind_router_spike"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike.train_mtop_operation_classifier import (  # noqa: E402
    LABEL_SEPARATOR,
    NO_ACTION,
    _conditioned_operation,
    _wrong_operation_pairs,
    disposition_from_training_label,
    operation_from_training_label,
    training_label,
)


def _row(disposition: str) -> dict[str, object]:
    return {
        "projection": {"disposition": disposition},
        "semantic": {"intent": "IN:FIXTURE"},
    }


def test_joint_label_preserves_operation_and_turn_disposition() -> None:
    labels = {
        disposition: training_label(
            _row(disposition),  # type: ignore[arg-type]
            "message.send" if disposition != "ood_no_effect" else "__none__",
            "operation-disposition",
        )
        for disposition in (
            "candidate",
            "candidate_missing_information",
            "ood_no_effect",
        )
    }

    assert labels == {
        "candidate": f"message.send{LABEL_SEPARATOR}action",
        "candidate_missing_information": (
            f"message.send{LABEL_SEPARATOR}clarify"
        ),
        "ood_no_effect": f"__none__{LABEL_SEPARATOR}conversation",
    }
    assert operation_from_training_label(
        labels["candidate_missing_information"],
        "operation-disposition",
    ) == "message.send"
    assert disposition_from_training_label(
        labels["candidate_missing_information"],
        "operation-disposition",
    ) == "clarify"


def test_disposition_only_labels_do_not_compete_with_operation_identity() -> None:
    assert training_label(
        _row("candidate_missing_information"),  # type: ignore[arg-type]
        "message.send",
        "disposition",
    ) == "clarify"
    assert disposition_from_training_label("clarify", "disposition") == "clarify"


def test_wrong_operation_pairs_choose_supported_siblings_and_reject_them() -> None:
    row = {
        "text": "skip this song",
        "source_id": "stable-row",
        "projection": {
            "reason": "contract_covered_structure",
            "disposition": "candidate",
            "candidate_operations": ["media.control"],
        },
    }

    pairs = _wrong_operation_pairs(
        [(row, "action")],  # type: ignore[list-item]
        ["media.control", "media.status", "web.search", NO_ACTION],
        count=1,
    )

    assert len(pairs) == 1
    negative, label = pairs[0]
    assert negative is not row
    assert negative["_condition_operation"] == "media.status"
    assert _conditioned_operation(negative) == "media.status"
    assert label == "conversation"


def test_compatibility_head_separates_pair_validity_from_disposition() -> None:
    assert training_label(
        _row("candidate"),  # type: ignore[arg-type]
        "message.send",
        "compatibility",
    ) == "compatible"
    assert training_label(
        _row("ood_no_effect"),  # type: ignore[arg-type]
        NO_ACTION,
        "compatibility",
    ) == "incompatible"
    assert disposition_from_training_label(
        "incompatible",
        "compatibility",
    ) == "conversation"
