"""Characterize the independent Cut-B development oracle before any sealing."""

from __future__ import annotations

import ast
import importlib
from collections import Counter


def _module():
    return importlib.import_module(
        "experiments.mind_router_spike.build_independent_cut_b_oracle_r146"
    )


def test_oracle_covers_every_public_family_in_every_required_language() -> None:
    candidate = _module()
    rows = candidate.build_rows()

    assert len(candidate.CASES) == 31
    assert len(rows) == 186
    assert Counter(row["language"] for row in rows) == {
        "es": 62,
        "en": 62,
        "spanglish": 62,
    }
    assert all(
        sum(row["family"] == family for row in rows) == 6
        for family in candidate.CASES
    )
    assert all(row["execution_authority"] is False for row in rows)
    assert all(row["blind_holdout"] is False for row in rows)


def test_generator_is_structurally_separate_from_recogniser_measurement() -> None:
    """Generation must not gain language from aliases or recognition code."""

    candidate = _module()
    source = candidate.Path(candidate.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    build_rows = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "build_rows"
    )
    names = {node.id for node in ast.walk(build_rows) if isinstance(node, ast.Name)}

    assert "effect_intent" not in names
    assert "_available_operations" not in names
    assert "_recogniser" not in names
    assert "build_generalization_product_current_tree_r28" not in source
    assert candidate.build_report(candidate.build_rows())["independence"] == {
        "generator_uses_recogniser": False,
        "generator_uses_alias_catalogue": False,
        "generator_uses_prior_cut_b_generator": False,
        "target_operations_are_a_manual_semantic_specification": True,
        "recogniser_is_loaded_only_after_generation_for_measurement": True,
    }


def test_measurement_is_side_effect_free_and_prices_reach_by_cause_boundary() -> None:
    candidate = _module()
    report = candidate.build_report(candidate.build_rows())
    measurement = report["recogniser_measurement"]

    assert report["scope"] == "opened_development_oracle_not_a_blind_cut_b_seal"
    assert report["execution"] == {
        "product_started": False,
        "decider_invoked": False,
        "providers_enabled": False,
        "effects_executed": 0,
        "voice_stt_wake_exercised": False,
    }
    assert measurement["rows"] == 186
    assert measurement["rows"] == (
        measurement["resolved_expected"]
        + measurement["resolved_other"]
        + measurement["unresolved"]
    )
    assert set(measurement["by_family"]) == set(candidate.CASES)
    assert set(measurement["by_language"]) == {"es", "en", "spanglish"}
