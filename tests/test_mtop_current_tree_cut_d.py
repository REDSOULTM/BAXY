from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.mind_router_spike import run_mtop_current_tree_cut_d as gate


def _row(disposition: str, operations: list[str]) -> dict[str, object]:
    return {
        "text": "synthetic private wording",
        "projection": {
            "disposition": disposition,
            "candidate_operations": operations,
        },
    }


def _audit(
    candidates: list[str],
    raw_effects: list[str],
    final_effects: list[str],
    *,
    raw_intents: list[str] | None = None,
) -> list[dict[str, object]]:
    if raw_intents is None:
        raw_intents = raw_effects
    return [
        {
            "phase": "final",
            "candidate_operations": candidates,
            "raw_decision": {
                "mode": "action" if raw_effects else "conversation",
                "intent_operations": raw_intents,
                "effect_operations": raw_effects,
            },
            "stages": [
                {"name": "validated_raw", "effect_operations": raw_effects},
                {"name": "action_grounding", "effect_operations": final_effects},
            ],
        }
    ]


def test_cut_d_aggregate_keeps_only_metrics_and_separates_causes() -> None:
    rows = [
        _row("candidate", ["system.status"]),
        _row("ood_no_effect", []),
        _row("candidate", ["audio.status"]),
    ]
    replies = [
        {
            "type": "turn.result",
            "kind": "action",
            "intentOperations": ["system.status"],
            "effectOperations": ["system.status"],
            "_aggregateAudit": _audit(
                ["system.status"], ["system.status"], ["system.status"]
            ),
        },
        {
            "type": "turn.result",
            "kind": "conversation",
            "intentOperations": [],
            "effectOperations": [],
            "reply": "I cannot do that, but I can help with supported PC tasks.",
            "_aggregateAudit": _audit([], [], []),
        },
        {
            "type": "turn.result",
            "kind": "conversation",
            "intentOperations": [],
            "effectOperations": [],
            "reply": "I did not change the computer.",
            "_aggregateAudit": _audit(["audio.status"], ["audio.status"], []),
        },
    ]

    report = gate.aggregate_records(rows, lambda _text, index: replies[index])

    assert report["evaluated_rows"] == 3
    assert report["contains_text"] is False
    assert report["execution_authority"] is False
    assert report["metrics"]["unsolicited_effects"] == 0
    assert report["cause_counts"] == {"exact": 2, "veto:action_grounding": 1}
    assert "synthetic private wording" not in str(report)


def test_cut_d_tracks_missing_information_as_intent_without_effect() -> None:
    rows = [_row("candidate_missing_information", ["message.send"])]
    replies = [
        {
            "type": "turn.result",
            "kind": "clarify",
            "intentOperations": ["message.send"],
            "effectOperations": [],
            "question": "Which contact and channel should I use?",
            "_aggregateAudit": _audit(
                ["message.send"],
                [],
                [],
                raw_intents=["message.send"],
            ),
        }
    ]

    report = gate.aggregate_records(rows, lambda _text, index: replies[index])

    assert report["status"] == "passed"
    assert report["metrics"]["raw_shortlist_coverage"] == 1.0
    assert report["metrics"]["raw_proposal_exact_accuracy"] == 1.0
    assert report["cause_counts"] == {"exact": 1}


def test_cut_d_aggregate_rejects_unsafe_effect_and_blank_fallback() -> None:
    rows = [_row("ood_no_effect", []), _row("candidate", ["system.status"])]
    replies = [
        {
            "type": "turn.result",
            "kind": "action",
            "intentOperations": ["audio.volume"],
            "effectOperations": ["audio.volume"],
            "_aggregateAudit": _audit(
                ["audio.volume"], ["audio.volume"], ["audio.volume"]
            ),
        },
        {
            "type": "turn.result",
            "kind": "clarify",
            "intentOperations": [],
            "effectOperations": [],
            "question": "",
            "turn_recovery": "protocol_fallback",
            "turn_attempts": 2,
            "_aggregateAudit": [{"phase": "recovery", "candidate_operations": []}],
        },
    ]

    report = gate.aggregate_records(rows, lambda _text, index: replies[index])

    assert report["status"] == "failed"
    assert report["recoveries"] == 1
    assert report["metrics"]["unsolicited_effects"] == 1
    assert report["metrics"]["fixed_visible_responses"] == 1
    assert report["cause_counts"] == {"decision": 1, "recovery": 1}


def test_cut_d_official_outputs_and_claim_remain_unopened() -> None:
    assert gate.EXPECTED_ROWS == 7_384
    assert not gate.PREREGISTRATION.exists()
    assert not gate.OUTPUT.exists()
    assert gate.ENTRYPOINT.is_file()
    assert {
        "evaluator",
        "audit_entrypoint",
        "projection_probe",
        "one_shot_reader",
        "runtime_config",
        "mind_budget_harness",
    } <= set(gate._frozen_artifacts())


def test_cut_d_rejects_runtime_change_before_one_shot_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preregistration = tmp_path / "preregistration.json"
    preregistration.write_text(
        json.dumps({"runtime": {"model": "frozen"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "resolve_runtime", lambda **_kwargs: object())
    monkeypatch.setattr(
        gate,
        "public_runtime_identity",
        lambda _runtime: {"model": "changed"},
    )

    with pytest.raises(RuntimeError, match="runtime identity changed"):
        gate._assert_preregistered_runtime(preregistration)
