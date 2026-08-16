from __future__ import annotations

import hashlib
import json
from collections import Counter

from scripts.build_generalization_surface_holdout import (
    CURRENT_REVIEW,
    OUTPUT,
    PREREGISTRATION,
    SCENARIOS,
    development_texts,
    normalize_text,
)


def _sealed_rows_and_manifest() -> tuple[list[dict[str, object]], dict[str, object]]:
    rows = [
        json.loads(line)
        for line in OUTPUT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifest = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    assert manifest["output"]["sha256"] == hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    return rows, manifest


def test_blind_population_is_preregistered_large_and_stratified() -> None:
    rows, manifest = _sealed_rows_and_manifest()

    assert len(rows) == 310
    assert len(SCENARIOS) == 31
    assert Counter(str(row["family"]) for row in rows) == {
        family: 10 for family in SCENARIOS
    }
    assert Counter(str(row["language"]) for row in rows) == {
        "es": 124,
        "en": 124,
        "spanglish": 62,
    }
    assert Counter(str(row["surface"]) for row in rows) == {
        "plain": 155,
        "addressed_polite": 155,
    }
    assert manifest["blind_holdout"] is True
    assert manifest["preregistered_before_measurement"] is True
    assert manifest["measurement_status"] == "unopened"
    assert manifest["method"]["minimum_cases"] == 300
    assert manifest["method"]["minimum_exact_turn_accuracy"] == 0.95
    assert manifest["method"]["trajectory_target"] == 0.99
    assert (
        manifest["method"]["one_sided_95_binomial_lower_if_zero_failures"]
        > 0.99
    )


def test_holdout_has_no_normalized_development_overlap_or_runtime_authority() -> None:
    rows, _ = _sealed_rows_and_manifest()
    normalized = [normalize_text(str(row["text"])) for row in rows]

    assert len(set(normalized)) == len(rows)
    assert set(normalized).isdisjoint(development_texts())
    assert all(row["blind_holdout"] is True for row in rows)
    assert all(row["execution_authority"] is False for row in rows)
    assert all(row["outcome"] == "action" for row in rows)
    assert all(row["compatible_terminal_operation_sets"] for row in rows)
    assert all(
        row["compatible_effect_operation_sets"]
        == row["compatible_terminal_operation_sets"]
        for row in rows
    )


def test_preregistration_binds_corpus_builder_policy_and_measurement_code() -> None:
    manifest = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    assert manifest["output"]["sha256"] == hashlib.sha256(
        OUTPUT.read_bytes()
    ).hexdigest()
    assert manifest["sources"]["current_development_corpus_sha256"] == (
        hashlib.sha256(CURRENT_REVIEW.read_bytes()).hexdigest()
    )
    assert len(manifest["sources"]["policy_sha256"]) == 5
    assert len(manifest["sources"]["measurement_sha256"]) == 4
    assert manifest["planned_measurement"]["effects_executed"] == 0
