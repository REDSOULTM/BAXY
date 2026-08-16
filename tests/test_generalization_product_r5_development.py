from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind.__main__ import _explicit_stable_no_effect_turn_decision
from baxy_mind.effect_intent import (
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
    unresolved_compound_contract,
)
from baxy_mind.planner import required_predecessors


REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "artifacts/holdout/generalization_product_holdout_v5.jsonl"


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


CORPUS_ROWS = _jsonl(CORPUS)
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
MIND_CONVERSATION_ROWS = [
    row
    for row in CORPUS_ROWS
    if row["owner"] == "mind_sidecar" and row["outcome"] == "conversation"
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
AVAILABLE.update(
    {
        "app.open",
        "game.install.prepare",
        "game.install.status",
        "game.installed.named",
        "package.install.prepare",
    }
)
# Model the production collision surface: Steam is an installed application,
# while Obsidian and GIMP must still be queryable as truthful absences.
APPLICATIONS = ("Steam", "Calculadora")


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
    MIND_ACTION_ROWS,
    ids=lambda row: str(row["case_id"]),
)
def test_every_opened_r5_mind_action_has_a_deterministic_contract_oracle(
    row: dict[str, object],
) -> None:
    text = str(row["text"])
    result = resolve_explicit_effects(text, AVAILABLE, APPLICATIONS)
    accepted = {
        _terminal_operations(tuple(group))
        for group in row["compatible_terminal_operation_sets"]
    }

    assert result is not None
    assert resolve_explicit_clarification_intent(text, AVAILABLE) is None
    assert unresolved_compound_contract(
        text,
        AVAILABLE,
        APPLICATIONS,
        resolved_intent=result,
    ) is None
    assert _terminal_operations(result.operations) in accepted


@pytest.mark.parametrize(
    "row",
    MIND_CLARIFICATION_ROWS,
    ids=lambda row: str(row["case_id"]),
)
def test_every_opened_r5_clarification_preserves_zero_effects(
    row: dict[str, object],
) -> None:
    text = str(row["text"])
    assert resolve_explicit_effects(text, AVAILABLE, APPLICATIONS) is None
    clarification = resolve_explicit_clarification_intent(text, AVAILABLE)
    assert clarification is not None
    assert clarification.operations == ("message.send",)
    assert "channel" in clarification.missing_fields


@pytest.mark.parametrize(
    "row",
    MIND_CONVERSATION_ROWS,
    ids=lambda row: str(row["case_id"]),
)
def test_every_opened_r5_conversation_remains_effect_free(
    row: dict[str, object],
) -> None:
    text = str(row["text"])
    assert resolve_explicit_effects(text, AVAILABLE, APPLICATIONS) is None
    assert resolve_explicit_clarification_intent(text, AVAILABLE) is None


@pytest.mark.parametrize(
    "row",
    MIND_CONVERSATION_ROWS,
    ids=lambda row: str(row["case_id"]),
)
def test_every_opened_r5_conversation_has_a_stable_zero_effect_turn_contract(
    row: dict[str, object],
) -> None:
    decision = _explicit_stable_no_effect_turn_decision(str(row["text"]))

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["effect_operations"] == []
