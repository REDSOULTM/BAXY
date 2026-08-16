from __future__ import annotations

import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PROBE = REPO / "experiments" / "mind_router_spike"
if str(PROBE) not in sys.path:
    sys.path.insert(0, str(PROBE))

import probe_current_catalog_review as probe  # noqa: E402
import probe_current_catalog_ready_pipeline as ready_probe  # noqa: E402
from experiments.mind_router_spike import (  # noqa: E402
    probe_catalog_pairwise_composition as pairwise_probe,
)


def test_compatible_operation_sets_accept_exact_alternatives_only() -> None:
    accepted = (("reminder.create",), ("notification.schedule",))
    assert probe._matches(["reminder.create"], accepted)
    assert probe._matches(["notification.schedule"], accepted)
    assert not probe._matches([], accepted)
    assert not probe._matches(
        ["reminder.create", "notification.schedule"], accepted
    )


def test_retrieval_accepts_any_complete_compatible_set() -> None:
    accepted = (
        ("web.search", "browser.navigate.named"),
        ("browser.navigate",),
    )
    assert probe._is_subset_offered(
        accepted,
        ["web.search", "browser.navigate.named", "app.open"],
    )
    assert probe._is_subset_offered(accepted, ["browser.navigate"])
    assert not probe._is_subset_offered(accepted, ["web.search"])


def test_raw_operation_projection_prefers_intent_identity() -> None:
    assert probe._raw_operations(
        {
            "mode": "conversation",
            "intent_operations": ["message.send"],
            "effect_operations": [],
        }
    ) == ("message.send",)
    assert probe._raw_operations(
        {"mode": "action", "operation": "audio.volume"}
    ) == ("audio.volume",)


def test_first_veto_reports_the_stage_that_removes_a_correct_effect() -> None:
    audit = {
        "raw_decision": {
            "mode": "action",
            "effect_operations": ["clipboard.copy"],
        },
        "stages": [
            {"name": "validated_raw", "effect_operations": ["clipboard.copy"]},
            {"name": "domain_grounding", "effect_operations": []},
            {"name": "compound_conservation", "effect_operations": []},
        ],
    }
    assert probe._first_veto(audit, (("clipboard.copy",),)) == "domain_grounding"


def test_development_input_is_hash_bound_and_explicitly_not_blind() -> None:
    rows, manifest = probe._load_inputs()
    assert len(rows) == 152
    assert manifest["blind_holdout"] is False
    assert all(row["execution_authority"] is False for row in rows)


def test_cross_tail_matrix_covers_four_families_in_both_orders() -> None:
    base_report = (
        REPO
        / "artifacts"
        / "fixes"
        / "current_catalog_review_product_probe_r28_extended_final.json"
    )
    historical = pairwise_probe.build_cases(base_report)
    matrix = pairwise_probe.build_cases(base_report, "cross_tail")

    assert len(historical) == 70
    assert len(matrix) == 560
    assert len({case["case_id"] for case in matrix}) == len(matrix)
    assert {case["tail_id"] for case in matrix} == {
        "time",
        "tasks",
        "notes",
        "processes",
    }
    assert {case["order"] for case in matrix} == {"prefix", "suffix"}
    assert all(
        len(expected) == len(set(expected))
        for case in matrix
        for expected in case["accepted_effect_operations"]
    )


def test_cross_action_tail_matrix_covers_literal_effects_in_both_orders() -> None:
    base_report = (
        REPO
        / "artifacts"
        / "fixes"
        / "current_catalog_review_product_probe_r29_cross_tail_final.json"
    )
    matrix = pairwise_probe.build_cases(base_report, "cross_action_tail")

    assert len(matrix) >= 500
    assert len({case["case_id"] for case in matrix}) == len(matrix)
    assert {case["tail_id"] for case in matrix} == {
        "mute",
        "volume",
        "task-create",
        "note-create",
    }
    assert {case["order"] for case in matrix} == {"prefix", "suffix"}
    assert all(
        len(expected) == len(set(expected))
        for case in matrix
        for expected in case["accepted_effect_operations"]
    )


def test_cross_triad_matrix_places_each_block_in_every_position() -> None:
    base_report = (
        REPO
        / "artifacts"
        / "fixes"
        / "current_catalog_review_product_probe_r30_action_tail_final.json"
    )
    matrix = pairwise_probe.build_cases(base_report, "cross_triad")

    assert len(matrix) >= 1_500
    assert len({case["case_id"] for case in matrix}) == len(matrix)
    assert {case["order"] for case in matrix} == {
        "base-read-action",
        "base-action-read",
        "read-base-action",
        "read-action-base",
        "action-base-read",
        "action-read-base",
    }
    assert all(
        len(expected) == len(set(expected))
        for case in matrix
        for expected in case["accepted_effect_operations"]
    )


def test_cross_triad_surface_matrix_varies_connectors_without_changing_order() -> None:
    base_report = (
        REPO
        / "artifacts"
        / "fixes"
        / "current_catalog_review_product_probe_r30_action_tail_final.json"
    )
    canonical = pairwise_probe.build_cases(base_report, "cross_triad")
    matrix = pairwise_probe.build_cases(base_report, "cross_triad_surface")

    assert len(matrix) == len(canonical) * len(pairwise_probe.TRIAD_SURFACE_PROFILES)
    assert len(matrix) >= 7_500
    assert len({case["case_id"] for case in matrix}) == len(matrix)
    assert {case["surface_profile"] for case in matrix} == set(
        pairwise_probe.TRIAD_SURFACE_PROFILES
    )
    expected_by_semantics = {
        (
            case["source_case_id"],
            case["tail_id"],
            case["order"],
        ): case["accepted_effect_operations"]
        for case in canonical
    }
    assert all(
        case["accepted_effect_operations"]
        == expected_by_semantics[
            (
                case["source_case_id"],
                case["tail_id"],
                case["order"],
            )
        ]
        for case in matrix
    )


def test_cross_triad_lexical_matrix_varies_tails_without_changing_semantics() -> None:
    base_report = (
        REPO
        / "artifacts"
        / "fixes"
        / "current_catalog_review_product_probe_r32_clean_server.json"
    )
    canonical = pairwise_probe.build_cases(base_report, "cross_triad")
    matrix = pairwise_probe.build_cases(base_report, "cross_triad_lexical")

    assert len(matrix) == len(canonical) * 2
    assert len(matrix) >= 3_000
    assert len({case["case_id"] for case in matrix}) == len(matrix)
    assert {case["lexical_profile"] for case in matrix} == {
        "lexical_1",
        "lexical_2",
    }
    expected_by_semantics = {
        (
            case["source_case_id"],
            case["tail_id"],
            case["order"],
        ): case["accepted_effect_operations"]
        for case in canonical
    }
    assert all(
        case["accepted_effect_operations"]
        == expected_by_semantics[
            (
                case["source_case_id"],
                case["tail_id"],
                case["order"],
            )
        ]
        for case in matrix
    )


def test_cross_triad_surface_lexical_matrix_crosses_both_invariances() -> None:
    base_report = (
        REPO
        / "artifacts"
        / "fixes"
        / "current_catalog_review_product_probe_r33_lexical_final.json"
    )
    canonical = pairwise_probe.build_cases(base_report, "cross_triad")
    matrix = pairwise_probe.build_cases(
        base_report,
        "cross_triad_surface_lexical",
    )

    assert len(matrix) == (
        len(canonical) * 2 * len(pairwise_probe.TRIAD_SURFACE_PROFILES)
    )
    assert len(matrix) >= 15_000
    assert len({case["case_id"] for case in matrix}) == len(matrix)
    assert {case["surface_profile"] for case in matrix} == set(
        pairwise_probe.TRIAD_SURFACE_PROFILES
    )
    assert {case["lexical_profile"] for case in matrix} == {
        "lexical_1",
        "lexical_2",
    }


def test_cross_quad_matrix_places_four_blocks_in_every_position() -> None:
    base_report = (
        REPO
        / "artifacts"
        / "fixes"
        / "current_catalog_review_product_probe_r34_surface_lexical_final.json"
    )
    matrix = pairwise_probe.build_cases(base_report, "cross_quad")

    assert len(matrix) >= 5_000
    assert len({case["case_id"] for case in matrix}) == len(matrix)
    assert {case["tail_id"] for case in matrix} == {
        "+".join(group) for group in pairwise_probe.QUAD_TAIL_GROUPS
    }
    assert all(len(case["order"].split(">")) == 4 for case in matrix)
    assert all(
        len({case["order"] for case in matrix if case["tail_id"] == tail_id})
        == 24
        for tail_id in {case["tail_id"] for case in matrix}
    )
    assert all(
        len(expected) == len(set(expected))
        for case in matrix
        for expected in case["accepted_effect_operations"]
    )


def test_raw_attempt_is_joined_to_terminal_recovery(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    records = [
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": "turn-1",
            "phase": "raw_attempt",
            "candidate_operations": ["app.open"],
            "raw_decision": {
                "mode": "action",
                "operation": "app.open",
                "effect_operations": ["app.open"],
            },
            "stages": [],
        },
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": "turn-1",
            "phase": "recovery",
            "candidate_operations": [],
            "raw_decision": None,
            "stages": [{"name": "total_recovery"}],
            "final": {
                "kind": "clarify",
                "intent_operations": [],
                "effect_operations": [],
            },
        },
    ]
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    selected = probe._read_audit(path, {"turn-1"})["turn-1"]

    assert selected["candidate_operations"] == ["app.open"]
    assert selected["raw_decision"]["operation"] == "app.open"
    assert selected["raw_attempts"] == 1
    assert selected["phase"] == "recovery"


def test_ready_probe_rejects_natural_language_due_values_after_schema() -> None:
    assert ready_probe._arguments_are_semantically_ready(
        "notification.schedule",
        {"dueUtc": "2026-08-02T10:00:00Z", "kind": "alarm", "title": "alarm"},
    )
    assert not ready_probe._arguments_are_semantically_ready(
        "notification.schedule",
        {"dueUtc": "in ten minutes", "kind": "alarm", "title": "alarm"},
    )
    assert ready_probe._arguments_are_semantically_ready(
        "app.open",
        {"appId": "Google Chrome"},
    )
