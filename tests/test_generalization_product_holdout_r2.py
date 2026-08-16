from __future__ import annotations

import hashlib
import json
from collections import Counter

import pytest

from experiments.mind_router_spike.probe_generalization_product_holdout_r2 import (
    load_inputs,
)
from scripts.build_generalization_product_holdout_r2 import (
    BUILDER_DEPENDENCIES,
    COMPOSITIONS,
    MEASUREMENT_SOURCES,
    OUTPUT,
    POLICY_SOURCES,
    PREREGISTRATION,
    SCENARIOS,
    build_rows,
    development_texts,
    normalize_text,
)


def _capabilities() -> list[dict[str, str]]:
    names = {
        operation
        for scenario in SCENARIOS.values()
        for operation in scenario.operations
    }
    names.update(
        operation
        for composition in COMPOSITIONS
        for operation in composition.operations
    )
    return [{"name": name} for name in sorted(names)]


def test_r2_population_is_large_unique_ownership_aware_and_compositional() -> None:
    rows = build_rows(_capabilities())

    assert len(rows) == 340
    assert len({row["case_id"] for row in rows}) == 340
    assert len({normalize_text(str(row["text"])) for row in rows}) == 340
    assert Counter(row["owner"] for row in rows) == {
        "mind_sidecar": 330,
        "app_private_memory_parser": 10,
    }
    assert Counter(row["case_type"] for row in rows) == {
        "single_action": 310,
        "clarification": 10,
        "composition": 20,
    }
    assert Counter(row["surface"] for row in rows) == {
        "plain": 170,
        "addressed": 170,
    }
    assert Counter(row["language"] for row in rows) == {
        "es": 136,
        "en": 136,
        "spanglish": 68,
    }
    assert all(row["blind_holdout"] is True for row in rows)
    assert all(row["execution_authority"] is False for row in rows)


def test_r2_clarifications_are_effect_free_and_compositions_keep_both_actions() -> None:
    rows = build_rows(_capabilities())
    clarifications = [row for row in rows if row["case_type"] == "clarification"]
    compositions = [row for row in rows if row["case_type"] == "composition"]

    assert all(row["outcome"] == "clarify" for row in clarifications)
    assert all(
        row["compatible_terminal_operation_sets"] == [["message.send"]]
        for row in clarifications
    )
    assert all(
        row["compatible_effect_operation_sets"] == [[]]
        for row in clarifications
    )
    assert all(row["outcome"] == "action" for row in compositions)
    assert all(
        len(row["compatible_terminal_operation_sets"][0]) == 2
        for row in compositions
    )


def test_r2_has_no_exact_normalized_overlap_with_prior_cuts() -> None:
    rows = build_rows(_capabilities())
    normalized = {normalize_text(str(row["text"])) for row in rows}

    assert normalized.isdisjoint(development_texts())


def test_r2_preregistration_freezes_every_policy_and_measurement_source() -> None:
    manifest = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    assert manifest["blind_holdout"] is True
    assert manifest["preregistered_before_measurement"] is True
    assert manifest["measurement_status"] == "unopened"
    assert manifest["method"]["minimum_exact_turn_accuracy"] == 0.99
    assert manifest["method"]["maximum_unsafe_effects"] == 0
    assert manifest["output"]["rows"] == 340
    assert manifest["output"]["sha256"] == hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    assert set(manifest["sources"]["policy_sha256"]) == {
        str(path.relative_to(OUTPUT.parents[2])) for path in POLICY_SOURCES
    }
    assert all(
        len(value) == 64
        for value in manifest["sources"]["policy_sha256"].values()
    )
    # R2 is historical evidence after it has been opened. Its sealed hashes
    # must remain immutable even though the maintained measurement harness and
    # parser tests legitimately evolve for later campaigns.
    assert set(manifest["sources"]["measurement_sha256"]) == {
        str(path.relative_to(OUTPUT.parents[2])) for path in MEASUREMENT_SOURCES
    }
    assert all(
        len(value) == 64
        for value in manifest["sources"]["measurement_sha256"].values()
    )
    assert set(manifest["sources"]["builder_dependencies_sha256"]) == {
        str(path.relative_to(OUTPUT.parents[2])) for path in BUILDER_DEPENDENCIES
    }
    assert all(
        len(value) == 64
        for value in manifest["sources"]["builder_dependencies_sha256"].values()
    )


def test_r2_opened_cut_cannot_be_reopened_after_policy_remediation() -> None:
    rows = [
        json.loads(line)
        for line in OUTPUT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert sum(row["owner"] == "mind_sidecar" for row in rows) == 330
    assert sum(row["owner"] == "app_private_memory_parser" for row in rows) == 10
    with pytest.raises(RuntimeError, match="policy changed after preregistration"):
        load_inputs()
    manifest = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    assert manifest["population"]["owners"] == {
        "mind_sidecar": 330,
        "app_private_memory_parser": 10,
    }
