from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind.effect_intent import (
    message_request_any_channel,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
    unresolved_compound_contract,
)
from baxy_mind.planner import required_predecessors


REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "artifacts/holdout/generalization_product_holdout_v4.jsonl"


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
APPLICATIONS = ("Audacity", "Paint", "Calculadora", "Steam")


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
def test_every_opened_r4_mind_action_has_a_deterministic_contract_oracle(
    row: dict[str, object],
) -> None:
    result = resolve_explicit_effects(
        str(row["text"]),
        AVAILABLE,
        APPLICATIONS,
    )
    clarification = resolve_explicit_clarification_intent(
        str(row["text"]),
        AVAILABLE,
    )
    accepted = {
        _terminal_operations(tuple(group))
        for group in row["compatible_terminal_operation_sets"]
    }

    assert result is not None
    assert clarification is None
    assert unresolved_compound_contract(
        str(row["text"]),
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
def test_every_opened_r4_clarification_preserves_zero_effects(
    row: dict[str, object],
) -> None:
    effect = resolve_explicit_effects(str(row["text"]), AVAILABLE, APPLICATIONS)
    clarification = resolve_explicit_clarification_intent(str(row["text"]), AVAILABLE)
    if message_request_any_channel(str(row["text"])) is not None:
        # REOPEN1993 grupo E (D24, 3bba9bdc3): a message naming a recipient and no
        # client is looked up in the clients (WhatsApp, Discord) and sent when the
        # hit is unique; the client is asked only when the person is in none or both.
        assert effect is not None
        assert effect.operations == ("message.recipient.resolve", "message.send")
        assert clarification is None
    else:
        assert effect is None
        assert clarification is not None
        assert clarification.operations == ("message.send",)
        assert "channel" in clarification.missing_fields


@pytest.mark.parametrize(
    "row",
    MIND_CONVERSATION_ROWS,
    ids=lambda row: str(row["case_id"]),
)
def test_every_opened_r4_conversation_remains_effect_free(
    row: dict[str, object],
) -> None:
    assert resolve_explicit_effects(
        str(row["text"]),
        AVAILABLE,
        APPLICATIONS,
    ) is None
    assert resolve_explicit_clarification_intent(
        str(row["text"]),
        AVAILABLE,
    ) is None
