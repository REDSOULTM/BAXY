from __future__ import annotations

from collections import Counter

from scripts import build_generalization_product_holdout_r4 as campaign


def _capabilities() -> list[dict[str, str]]:
    names = {
        operation
        for value in campaign.SCENARIOS.values()
        for operation in value.operations
    }
    names.update(
        operation
        for value in campaign.COMPOSITIONS
        for operation in value.operations
    )
    return [{"name": name} for name in sorted(names)]


def _rows() -> list[dict[str, object]]:
    campaign.configure()
    return campaign.builder.build_rows(_capabilities())


def test_r4_population_is_large_unique_balanced_and_execution_inert() -> None:
    rows = _rows()

    assert len(rows) == 400
    assert len({row["case_id"] for row in rows}) == 400
    assert len(
        {campaign.builder.normalize_text(str(row["text"])) for row in rows}
    ) == 400
    assert Counter(row["owner"] for row in rows) == {
        "mind_sidecar": 390,
        "app_private_memory_parser": 10,
    }
    assert Counter(row["case_type"] for row in rows) == {
        "single_action": 310,
        "clarification": 10,
        "composition": 40,
        "conversation": 40,
    }
    assert Counter(row["surface"] for row in rows) == {
        "plain": 200,
        "addressed": 200,
    }
    assert all(row["blind_holdout"] is True for row in rows)
    assert all(row["execution_authority"] is False for row in rows)


def test_r4_non_actions_are_effect_free_and_actions_keep_their_contracts() -> None:
    rows = _rows()
    non_actions = [row for row in rows if row["outcome"] != "action"]
    actions = [row for row in rows if row["outcome"] == "action"]

    assert {row["outcome"] for row in non_actions} == {"clarify", "conversation"}
    assert all(row["compatible_effect_operation_sets"] == [[]] for row in non_actions)
    assert all(row["compatible_effect_operation_sets"] != [[]] for row in actions)
    assert all(row["compatible_terminal_operation_sets"] != [[]] for row in actions)


def test_r4_has_no_exact_normalized_overlap_with_prior_cuts() -> None:
    rows = _rows()
    normalized = {
        campaign.builder.normalize_text(str(row["text"])) for row in rows
    }

    assert normalized.isdisjoint(campaign.builder.prior_texts())
