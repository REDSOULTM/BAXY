from __future__ import annotations

from copy import deepcopy
import json

import pytest

from scripts.adjudicate_observed_product_replay import AdjudicationError, object_sha256, text_sha256
from scripts.build_observed_current_contracts import (
    contract_mapping_rows,
    load_contract_reviews,
    template_rows,
    unique_variants,
)


TEXT = "hay alguna ventana de steam abierta"
TEXT_HASH = text_sha256(TEXT)
HISTORICAL = {
    "outcome_type": "mission_must_implement",
    "operations": ["window.manage"],
    "denied_operations": [],
    "plan": ["Ejecutar y verificar window.manage."],
    "risk": {"class": "low_reversible"},
    "provider_roles": ["window_adapter"],
    "verification": ["HWND observado."],
    "natural_response": "Listo, ajusté la ventana.",
}


def corpus_row(message_id: str) -> dict:
    return {
        "message_id": message_id,
        "text_literal": TEXT,
        "text_sha256": TEXT_HASH,
        "redacted": False,
        "class": "user_mission",
        "language": "es",
    }


def mapping_row(message_id: str) -> dict:
    return {
        "message_id": message_id,
        "acceptance_test_id": "hist_windows",
        **deepcopy(HISTORICAL),
    }


def approved_review(variant: dict) -> dict:
    return {
        "schema": "baxy.goal10-observed-contract-review.v1",
        "text": TEXT,
        "text_sha256": TEXT_HASH,
        "replay_text_sha256": variant["replay_text_sha256"],
        "acceptance_test_id": "hist_windows",
        "historical_contract_sha256": object_sha256(variant["historical_contract"]),
        "verdict": "pass",
        "reason": "The typed catalog owns named application window status.",
        "authority_bases": ["src/Baxy.Kernel/Operations/ProductCatalog.cs:1547-1551"],
        "contract": {
            "kind": "action",
            "operations": ["window.application.status"],
            "allowed_support_operations": [],
            "denied_operations": ["window.active"],
            "success_evidence": ["Verified visible-window snapshot."],
        },
    }


def test_unique_variants_preserve_repetitions_and_one_frozen_contract() -> None:
    rows = [corpus_row("msg_1"), corpus_row("msg_2")]
    mapping = {row["message_id"]: mapping_row(row["message_id"]) for row in rows}

    variants = unique_variants(rows, mapping)

    assert list(variants) == [TEXT_HASH]
    assert variants[TEXT_HASH]["occurrence_count"] == 2
    assert variants[TEXT_HASH]["historical_contract"] == HISTORICAL


def test_conflicting_frozen_contract_for_same_literal_is_rejected() -> None:
    rows = [corpus_row("msg_1"), corpus_row("msg_2")]
    mapping = {row["message_id"]: mapping_row(row["message_id"]) for row in rows}
    mapping["msg_2"]["operations"] = ["window.active"]

    with pytest.raises(AdjudicationError, match="conflicting"):
        unique_variants(rows, mapping)


def test_redacted_literal_binds_source_and_replay_hashes_separately() -> None:
    row = corpus_row("msg_1")
    row["text_literal"] = "%USERPROFILE%\\private.txt"
    row["text_sha256"] = "a" * 64
    row["redacted"] = True
    mapping = {"msg_1": mapping_row("msg_1")}

    variants = unique_variants([row], mapping)

    assert list(variants) == ["a" * 64]
    assert variants["a" * 64]["text_sha256"] == "a" * 64
    assert variants["a" * 64]["replay_text_sha256"] == text_sha256(
        "%USERPROFILE%\\private.txt"
    )
    assert variants["a" * 64]["redacted"] is True


def test_template_is_explicitly_unreviewed_and_keeps_exact_private_text() -> None:
    rows = [corpus_row("msg_1")]
    mapping = {"msg_1": mapping_row("msg_1")}
    variant = unique_variants(rows, mapping)

    template = template_rows(variant)[0]

    assert template["verdict"] == "unreviewed"
    assert template["text"] == TEXT
    assert template["replay_text_sha256"] == TEXT_HASH
    assert template["contract"]["kind"] == ""


def test_approved_review_requires_current_catalog_operations(tmp_path) -> None:
    rows = [corpus_row("msg_1")]
    mapping = {"msg_1": mapping_row("msg_1")}
    variants = unique_variants(rows, mapping)
    review = approved_review(variants[TEXT_HASH])
    path = tmp_path / "reviews.jsonl"
    path.write_text(json.dumps(review) + "\n", encoding="utf-8")

    loaded = load_contract_reviews(
        [path],
        variants,
        {"window.application.status", "window.active"},
    )
    assert loaded[TEXT_HASH]["contract"]["operations"] == ["window.application.status"]

    review["contract"]["operations"] = ["retired.window.manage"]
    path.write_text(json.dumps(review) + "\n", encoding="utf-8")
    with pytest.raises(AdjudicationError, match="outside the current catalog"):
        load_contract_reviews([path], variants, {"window.application.status", "window.active"})


def test_review_coverage_must_equal_all_unique_literals(tmp_path) -> None:
    rows = [corpus_row("msg_1")]
    mapping = {"msg_1": mapping_row("msg_1")}
    variants = unique_variants(rows, mapping)
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")

    with pytest.raises(AdjudicationError, match="missing 1"):
        load_contract_reviews([empty], variants, {"window.application.status"})


def test_mapping_projects_one_review_to_every_real_occurrence(tmp_path) -> None:
    rows = [corpus_row("msg_1"), corpus_row("msg_2")]
    mapping = {row["message_id"]: mapping_row(row["message_id"]) for row in rows}
    variants = unique_variants(rows, mapping)
    review = approved_review(variants[TEXT_HASH])
    path = tmp_path / "reviews.jsonl"
    path.write_text(json.dumps(review) + "\n", encoding="utf-8")
    reviews = load_contract_reviews(
        [path],
        variants,
        {"window.application.status", "window.active"},
    )

    output = contract_mapping_rows(rows, mapping, reviews)

    assert [row["message_id"] for row in output] == ["msg_1", "msg_2"]
    assert all(row["source_text_sha256"] == TEXT_HASH for row in output)
    assert all(row["text_sha256"] == TEXT_HASH for row in output)
    assert all(row["operations"] == ["window.application.status"] for row in output)
    assert all(row["denied_operations"] == ["window.active"] for row in output)
