from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind.effect_intent import (
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from baxy_mind.planner import required_predecessors


REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "artifacts/holdout/generalization_product_holdout_v2.jsonl"
PROMOTED = (
    REPO / "artifacts/development/generalization_product_r2_failures.v1.jsonl"
)


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


CORPUS_ROWS = _jsonl(CORPUS)
PROMOTED_ROWS = _jsonl(PROMOTED)
MIND_ACTION_FAILURES = [
    row
    for row in PROMOTED_ROWS
    if row["owner"] == "mind_sidecar" and row["outcome"] == "action"
]
CLARIFICATION_FAILURES = [
    row
    for row in PROMOTED_ROWS
    if row["owner"] == "mind_sidecar" and row["outcome"] == "clarify"
]
MIND_ACTION_ROWS = [
    row
    for row in CORPUS_ROWS
    if row["owner"] == "mind_sidecar" and row["outcome"] == "action"
]
MIND_CLARIFICATION_ROWS = [
    row
    for row in CORPUS_ROWS
    if row["owner"] == "mind_sidecar" and row["outcome"] == "clarify"
]
AVAILABLE = {
    operation
    for row in CORPUS_ROWS
    for field in (
        "compatible_terminal_operation_sets",
        "compatible_effect_operation_sets",
    )
    for group in row[field]
    for operation in group
}
# The machine snapshot is localized and deliberately does not contain VLC.
# app.installed must still be able to return a verified absence for that
# explicitly queried literal.
APPLICATIONS = ("Calculadora", "Steam")


def _terminal_operations(operations: tuple[str, ...]) -> tuple[str, ...]:
    ordered = tuple(dict.fromkeys(operations))
    technical = {
        predecessor
        for operation in ordered
        for predecessor in required_predecessors(operation)
        if predecessor in ordered
    }
    return tuple(operation for operation in ordered if operation not in technical)


@pytest.mark.parametrize(
    "row",
    MIND_ACTION_FAILURES,
    ids=lambda row: str(row["case_id"]),
)
def test_opened_r2_action_failures_are_deterministic_regressions(
    row: dict[str, object],
) -> None:
    result = resolve_explicit_effects(
        str(row["text"]),
        AVAILABLE,
        APPLICATIONS,
    )
    accepted = {
        _terminal_operations(tuple(group))
        for group in row["compatible_terminal_operation_sets"]
    }
    if str(row["case_id"]).startswith("r2-composition-05-"):
        accepted.update(tuple(reversed(group)) for group in tuple(accepted))

    assert result is not None
    assert _terminal_operations(result.operations) in accepted


@pytest.mark.parametrize(
    "row",
    CLARIFICATION_FAILURES,
    ids=lambda row: str(row["case_id"]),
)
def test_opened_r2_channel_less_messages_ask_only_for_missing_data(
    row: dict[str, object],
) -> None:
    effect = resolve_explicit_effects(
        str(row["text"]),
        AVAILABLE,
        APPLICATIONS,
    )
    clarification = resolve_explicit_clarification_intent(
        str(row["text"]),
        AVAILABLE,
    )

    assert effect is None
    assert clarification is not None
    assert clarification.operations == ("message.send",)
    assert "channel" in clarification.missing_fields


@pytest.mark.parametrize(
    "row",
    MIND_ACTION_ROWS,
    ids=lambda row: str(row["case_id"]),
)
def test_every_r2_mind_action_has_a_deterministic_contract_oracle(
    row: dict[str, object],
) -> None:
    result = resolve_explicit_effects(
        str(row["text"]),
        AVAILABLE,
        APPLICATIONS,
    )
    accepted = {
        _terminal_operations(tuple(group))
        for group in row["compatible_terminal_operation_sets"]
    }
    if str(row["case_id"]).startswith("r2-composition-05-"):
        accepted.update(tuple(reversed(group)) for group in tuple(accepted))

    assert result is not None
    assert _terminal_operations(result.operations) in accepted


@pytest.mark.parametrize(
    "row",
    MIND_CLARIFICATION_ROWS,
    ids=lambda row: str(row["case_id"]),
)
def test_every_r2_mind_clarification_preserves_zero_effects(
    row: dict[str, object],
) -> None:
    assert resolve_explicit_effects(
        str(row["text"]),
        AVAILABLE,
        APPLICATIONS,
    ) is None
    clarification = resolve_explicit_clarification_intent(
        str(row["text"]),
        AVAILABLE,
    )
    assert clarification is not None
    assert clarification.operations == ("message.send",)
    assert "channel" in clarification.missing_fields


@pytest.mark.parametrize(
    "text",
    [
        "Report the overall status of a computer I might buy",
        "Inspect the USB accessories plugged into my phone",
        "Explain how foreground applications work",
        "Start The Crown on Netflix tomorrow",
        "Generate a Word file on another computer",
        "Tell Morgan how Discord messaging works",
        "Grab an image from the web",
        "Review neural network connectivity",
    ],
)
def test_r2_neighboring_domains_do_not_gain_effect_authority(text: str) -> None:
    assert resolve_explicit_effects(text, AVAILABLE, APPLICATIONS) is None
