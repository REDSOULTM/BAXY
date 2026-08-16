from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO
    / "experiments"
    / "mind_router_spike"
    / "probe_mtop_product_validation.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_mtop_product_validation",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)


def _row(
    mission: str,
    locale: str,
    disposition: str,
    operations: list[str],
    reason: str = "contract_covered_structure",
) -> dict[str, object]:
    return {
        "split": "validation",
        "mission_id": mission,
        "source_id": f"{mission}:{locale}",
        "locale": locale,
        "projection": {
            "disposition": disposition,
            "reason": reason,
            "candidate_operations": operations,
        },
    }


def test_terminal_user_operations_removes_authenticated_predecessor() -> None:
    assert probe.terminal_user_operations(
        ["message.recipient.resolve", "message.send"]
    ) == ("message.send",)
    assert probe.terminal_user_operations(
        ["reminder.resolve.exact", "reminder.delete"]
    ) == ("reminder.delete",)


def test_expected_turn_separates_identity_from_missing_effect_authority() -> None:
    expected = probe.expected_turn(
        _row(
            "missing",
            "en",
            "candidate_missing_information",
            ["notification.schedule"],
        )
    )

    assert expected == {
        "kinds": ["clarify"],
        "intent_operations": ["notification.schedule"],
        "effect_operations": [],
    }


def test_balanced_selection_keeps_parallel_language_missions_together() -> None:
    rows = [
        _row("one", "en", "candidate", ["web.search"]),
        _row("one", "es", "candidate", ["web.search"]),
        _row("two", "en", "candidate", ["web.search"]),
        _row("two", "es", "candidate", ["web.search"]),
        _row(
            "ood",
            "en",
            "ood_no_effect",
            [],
            "mapped_unsupported_intent",
        ),
    ]

    selected = probe.select_validation_rows(rows, groups_per_stratum=1)
    selected_missions = {row["mission_id"] for row in selected}

    assert "ood" in selected_missions
    supported = selected_missions - {"ood"}
    assert len(supported) == 1
    selected_supported = next(iter(supported))
    assert sum(row["mission_id"] == selected_supported for row in selected) == 2


def test_balanced_selection_quarantines_parallel_projection_conflicts() -> None:
    rows = [
        _row("conflict", "en", "candidate", ["web.search"]),
        _row("conflict", "es", "ood_no_effect", [], "mapped_unsupported_intent"),
        _row("safe", "en", "candidate", ["web.search"]),
    ]

    selected = probe.select_validation_rows(rows, groups_per_stratum=1)

    assert {row["mission_id"] for row in selected} == {"safe"}


def test_assessment_requires_intent_effect_and_kind_exactly() -> None:
    expected = {
        "kinds": ["action", "plan"],
        "intent_operations": ["web.search"],
        "effect_operations": ["web.search"],
    }
    exact = probe.assess(
        expected,
        {
            "type": "turn.result",
            "kind": "action",
            "intentOperations": ["web.search"],
            "effectOperations": ["web.search"],
        },
    )
    wrong = probe.assess(
        expected,
        {
            "type": "turn.result",
            "kind": "clarify",
            "intentOperations": ["web.search"],
            "effectOperations": [],
        },
    )

    assert exact["exact"] is True
    assert wrong["exact"] is False
