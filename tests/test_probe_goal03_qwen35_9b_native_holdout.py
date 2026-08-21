from __future__ import annotations

from experiments.mind_router_spike import probe_goal03_qwen35_9b_native_holdout as probe


def test_candidate_contracts_preserve_catalog_identity() -> None:
    contracts = probe.candidate_contracts()

    assert len(contracts) == 169
    assert contracts["app.open"]["name"] == "app.open"
    assert isinstance(contracts["app.open"]["description"], str)
    assert contracts["app.open"]["arguments_schema"]["type"] == "object"


def test_synthetic_population_is_hash_bound_and_complete() -> None:
    rows, output, counts = probe.population("synthetic")

    assert len(rows) == 784
    assert counts == {"positive": 477, "no_action": 307}
    assert output == probe.SYNTHETIC_OUTPUT
    assert probe.sha256(probe.VALIDATION) == probe.EXPECTED_SHA256[probe.VALIDATION]


def test_native_policy_uses_preregistered_goal_ratio_gates() -> None:
    assert probe.MINIMUM_SYNTHETIC_EXACT == 431
    assert probe.MAXIMUM_SYNTHETIC_OOS_ACTIONS == 42
    assert probe.MINIMUM_REAL_EXACT == 55
    assert probe.MODEL.name == "Qwen3.5-9B-UD-IQ2_XXS.gguf"
