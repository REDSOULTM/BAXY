from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.adjudicate_observed_product_replay import (
    AdjudicationError,
    adjudicate_rows,
    corrected_contract,
    load_corrections,
    load_reviews,
    mechanical_checks,
    object_sha256,
    text_sha256,
)


MESSAGE_ID = "msg_0123456789abcdef"
MESSAGE = "hola"
RESPONSE = "Hola, ¿cómo estás?"


def final_audit(kind: str, operations: list[str]) -> list[dict]:
    return [
        {
            "phase": "final",
            "final": {"kind": kind, "effect_operations": operations},
        }
    ]


def no_effect_row() -> dict:
    return {
        "schema": "baxy.goal10-observed-product-replay.v2",
        "message_id": MESSAGE_ID,
        "message": MESSAGE,
        "response": RESPONSE,
        "text_sha256": text_sha256(MESSAGE),
        "expected_contract": {
            "acceptance_test_id": "hist_conversation",
            "operations": [],
            "denied_operations": [],
        },
        "turn_audit": final_audit("conversation", []),
        "journal_payloads": [],
    }


def action_row(*, verified: bool = True, include_catalog: bool = True) -> dict:
    operation = "window.application.status"
    response = {
        "status": "completed" if verified else "failed",
        "verified": verified,
        "errorCode": None if verified else "inventory_failed",
    }
    row = {
        "schema": "baxy.goal10-observed-product-replay.v2",
        "message_id": MESSAGE_ID,
        "message": "hay alguna ventana de steam abierta",
        "response": "Hay una ventana de Steam abierta." if verified else "No pude verificarlo.",
        "text_sha256": text_sha256("hay alguna ventana de steam abierta"),
        "expected_contract": {
            "acceptance_test_id": "hist_windows",
            "operations": [operation],
            "denied_operations": ["window.active"],
        },
        "turn_audit": final_audit("action", [operation]),
        "confirmation_mode": "normal",
        "journal_payloads": [
            {"phase": "started", "operation": operation, "invocationId": "inv-1"},
            {
                "phase": "completed",
                "operation": operation,
                "invocationId": "inv-1",
                "response": response,
            },
        ],
    }
    if include_catalog:
        row["catalog_evidence"] = [
            {
                "operation": operation,
                "risk": "read_only",
                "verifier_contract_id": "window.application.status.catalog.visible.snapshot.v1",
            }
        ]
    return row


def semantic_review(row: dict, *, verdict: str = "pass") -> dict:
    return {
        "schema": "baxy.goal10-semantic-review.v1",
        "message_id": row["message_id"],
        "text_sha256": row["text_sha256"],
        "response_sha256": text_sha256(row["response"]),
        "replay_row_sha256": object_sha256(row),
        "checks": {
            dimension: {
                "verdict": verdict,
                "reason": f"{dimension} was checked against the exact turn",
                "evidence": ["exact message and response"],
            }
            for dimension in ("pertinence", "naturalness", "language", "honesty")
        },
        "factual_evidence": [
            {"source": "turn audit", "fact": "This row makes no unsupported dynamic claim."}
        ],
    }


def test_complete_no_effect_row_passes_all_nine_dimensions() -> None:
    row = no_effect_row()
    result = adjudicate_rows([row], {MESSAGE_ID: semantic_review(row)}, {})[0]

    assert result["verdict"] == "pass"
    assert set(result["checks"]) == {
        "pertinence",
        "naturalness",
        "language",
        "honesty",
        "requested_action",
        "risk",
        "confirmation",
        "verification",
        "terminal",
    }
    assert {check["verdict"] for check in result["checks"].values()} == {"pass"}


def test_verified_action_requires_catalog_and_journal_evidence() -> None:
    row = action_row()
    result = adjudicate_rows([row], {MESSAGE_ID: semantic_review(row)}, {})[0]

    assert result["verdict"] == "pass"
    assert result["checks"]["requested_action"]["verdict"] == "pass"
    assert result["checks"]["risk"]["verdict"] == "pass"
    assert result["checks"]["verification"]["verdict"] == "pass"


def test_missing_catalog_and_failed_postcondition_cannot_pass() -> None:
    row = action_row(verified=False, include_catalog=False)
    result = adjudicate_rows([row], {MESSAGE_ID: semantic_review(row)}, {})[0]

    assert result["verdict"] == "fail"
    assert result["checks"]["risk"]["verdict"] == "fail"
    assert result["checks"]["confirmation"]["verdict"] == "fail"
    assert result["checks"]["verification"]["verdict"] == "fail"
    assert result["checks"]["terminal"]["verdict"] == "fail"


def test_stale_or_incomplete_semantic_review_is_rejected() -> None:
    row = no_effect_row()
    review = semantic_review(row)
    review["response_sha256"] = "0" * 64
    with pytest.raises(AdjudicationError, match="stale"):
        adjudicate_rows([row], {MESSAGE_ID: review}, {})

    with pytest.raises(AdjudicationError, match="coverage mismatch"):
        adjudicate_rows([row], {}, {})


def test_semantic_review_is_bound_to_the_complete_physical_row() -> None:
    row = no_effect_row()
    review = semantic_review(row)
    changed = {**row, "shell_status": "different evidence"}

    with pytest.raises(AdjudicationError, match="stale for the captured evidence row"):
        adjudicate_rows([changed], {MESSAGE_ID: review}, {})


def test_legacy_replay_without_catalog_contract_is_rejected() -> None:
    row = no_effect_row()
    review = semantic_review(row)
    row["schema"] = "baxy.goal10-observed-product-replay.v1"

    with pytest.raises(AdjudicationError, match="lacks the v2"):
        adjudicate_rows([row], {MESSAGE_ID: review}, {})


def test_review_loader_rejects_unresolved_and_empty_evidence(tmp_path: Path) -> None:
    row = no_effect_row()
    review = semantic_review(row)
    review["checks"]["honesty"]["verdict"] = "review"
    path = tmp_path / "reviews.jsonl"
    path.write_text(json.dumps(review) + "\n", encoding="utf-8")

    with pytest.raises(AdjudicationError, match="cannot be review/unresolved"):
        load_reviews([path])


def test_correction_is_scoped_by_acceptance_test_and_input_hash(tmp_path: Path) -> None:
    row = no_effect_row()
    ledger = {
        "schema": "baxy.goal10-contract-corrections.v1",
        "corrections": [
            {
                "selector": {
                    "acceptance_test_id": "hist_conversation",
                    "text_sha256": row["text_sha256"],
                },
                "reason": "The frozen prototype contract predates current Identity.",
                "authority_bases": ["documentacion/00_IDENTIDAD.md:161-176"],
                "replacement": {"operations": ["system.time"]},
            }
        ],
    }
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    corrections = load_corrections(path)

    contract, correction = corrected_contract(row, corrections)
    assert contract["operations"] == ["system.time"]
    assert correction is not None

    other = {**row, "text_sha256": "f" * 64}
    unchanged, correction = corrected_contract(other, corrections)
    assert unchanged["operations"] == []
    assert correction is None


def test_bypass_confirmation_scores_when_only_intent_operations_were_selected() -> None:
    row = action_row()
    row["expected_contract"] = {
        "acceptance_test_id": "hist_open",
        "operations": ["app.open"],
        "denied_operations": [],
    }
    row["confirmation_mode"] = "bypass"
    row["turn_audit"] = [
        {
            "phase": "final",
            "final": {
                "kind": "clarify",
                "effect_operations": [],
                "intent_operations": ["app.open"],
            },
        }
    ]
    row["journal_payloads"] = []
    row["catalog_evidence"] = [
        {
            "operation": "app.open",
            "risk": "low_reversible",
            "verifier_contract_id": "app.open.visible.snapshot.v1",
        }
    ]
    checks = mechanical_checks(row, row["expected_contract"])

    assert checks["confirmation"]["verdict"] == "pass"
    assert checks["risk"]["verdict"] == "pass"


def test_normal_sensitive_operation_requires_confirmation_challenge() -> None:
    row = action_row()
    row["catalog_evidence"][0]["risk"] = "privacy_sensitive"
    checks = mechanical_checks(row, row["expected_contract"])

    assert checks["confirmation"]["verdict"] == "fail"
    assert "challenge" in checks["confirmation"]["reason"]


def test_verified_catalog_support_operation_is_not_an_unrequested_effect() -> None:
    effect = "app.close"
    support = "window.resolve"
    row = action_row()
    row["expected_contract"] = {
        "acceptance_test_id": "hist_app_close",
        "operations": [effect],
        "allowed_support_operations": [support, "window.active"],
        "denied_operations": [],
    }
    row["turn_audit"] = final_audit("action", [effect])
    row["catalog_evidence"] = [
        {
            "operation": support,
            "risk": "read_only",
            "verifier_contract_id": "window.resolve.snapshot.v1",
        },
        {
            "operation": effect,
            "risk": "work_loss",
            "verifier_contract_id": "app.close.postread.v1",
        },
    ]
    row["confirmation_mode"] = "bypass"
    row["journal_payloads"] = [
        {"phase": "started", "operation": support, "invocationId": "support"},
        {
            "phase": "completed",
            "operation": support,
            "invocationId": "support",
            "response": {"status": "completed", "verified": True, "errorCode": None},
        },
        {"phase": "started", "operation": effect, "invocationId": "effect"},
        {
            "phase": "completed",
            "operation": effect,
            "invocationId": "effect",
            "response": {"status": "completed", "verified": True, "errorCode": None},
        },
    ]

    checks = mechanical_checks(row, row["expected_contract"])

    assert {dimension: check["verdict"] for dimension, check in checks.items()} == {
        "requested_action": "pass",
        "risk": "pass",
        "confirmation": "pass",
        "verification": "pass",
        "terminal": "pass",
    }
