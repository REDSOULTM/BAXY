from __future__ import annotations

from collections import Counter
from pathlib import Path

from experiments.mind_router_spike import (
    build_generalization_product_current_tree_r22 as campaign,
)


def _capabilities() -> list[dict[str, str]]:
    names = {
        operation
        for value in campaign.SCENARIOS.values()
        for operation in value.operations
    }
    names.update(
        operation for value in campaign.COMPOSITIONS for operation in value.operations
    )
    return [{"name": name} for name in sorted(names)]


def _rows() -> list[dict[str, object]]:
    campaign.configure()
    return campaign.builder.build_rows(_capabilities())


def test_current_tree_r22_is_large_unique_balanced_and_execution_inert() -> None:
    rows = _rows()

    assert len(rows) == 700
    assert len({str(row["case_id"]) for row in rows}) == 700
    assert (
        len({campaign.builder.normalize_text(str(row["text"])) for row in rows}) == 700
    )
    assert Counter(row["owner"] for row in rows) == {
        "mind_sidecar": 688,
        "app_private_memory_parser": 12,
    }
    assert Counter(row["case_type"] for row in rows) == {
        "single_action": 372,
        "clarification": 20,
        "composition": 200,
        "conversation": 108,
    }
    assert Counter(row["surface"] for row in rows) == {
        "plain": 350,
        "addressed": 350,
    }
    assert all(row["blind_holdout"] is True for row in rows)
    assert all(row["execution_authority"] is False for row in rows)


def test_current_tree_r22_has_no_prior_text_or_composition_overlap() -> None:
    rows = _rows()
    normalized = {campaign.builder.normalize_text(str(row["text"])) for row in rows}
    generated_sequences = {
        tuple(str(value) for value in row["compatible_terminal_operation_sets"][0])
        for row in rows
        if row["case_type"] == "composition"
    }

    assert normalized.isdisjoint(campaign.builder.prior_texts())
    assert generated_sequences.isdisjoint(campaign._prior_composition_sequences())


def test_current_tree_r22_was_opened_once_and_stays_tree_bound() -> None:
    """R22 has been measured; guard the seal instead of its absence.

    The previous guard asserted the campaign was still unopened. It was opened
    on 2026-08-12 and closed at 149 of 688 exact against a 95% bar, so that
    assertion is simply false now. What still has to hold is that the corpus
    and its preregistration exist together and stay bound to the prior
    population they were declared disjoint from.
    """

    assert campaign.OUTPUT.exists()
    assert campaign.PREREGISTRATION.exists()
    assert campaign.MIND_OUTPUT.exists()
    assert campaign.PRIOR_CORPORA[-1] == campaign.r21.OUTPUT
    assert campaign.BUILDER_DEPENDENCIES[-1] == (
        campaign.REPO / "scripts/build_generalization_product_holdout_r21.py"
    )
    assert Path(campaign.__file__).resolve().is_file()
    assert all(path.is_file() for path in campaign.POLICY_SOURCES)
    assert all(path.is_file() for path in campaign.MEASUREMENT_SOURCES)
