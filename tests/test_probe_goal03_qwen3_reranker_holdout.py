from __future__ import annotations

from experiments.mind_router_spike import probe_goal03_qwen3_reranker_holdout as probe


def test_synthetic_population_is_hash_bound_and_complete() -> None:
    rows, output, counts = probe.population("synthetic")

    assert len(rows) == 784
    assert counts == {"positive": 477, "no_action": 307}
    assert output == probe.SYNTHETIC_OUTPUT
    assert probe.sha256(probe.VALIDATION) == probe.EXPECTED_SHA256[probe.VALIDATION]


def test_threshold_and_instruction_are_preregistered() -> None:
    assert probe.THRESHOLD == 0.5
    assert probe.MINIMUM_SYNTHETIC_EXACT == 431
    assert probe.MAXIMUM_SYNTHETIC_OOS_ACTIONS == 42
    assert "sibling operations are not relevant" in probe.INSTRUCTION


def test_decide_abstains_below_half_and_picks_top_above() -> None:
    selected, no_match, detail = probe.decide(
        ["app.open", "system.time"],
        [0.82, 0.11],
    )
    assert selected == ("app.open",)
    assert no_match is False
    assert detail["top_name"] == "app.open"

    selected, no_match, detail = probe.decide(
        ["app.open", "system.time"],
        [0.41, 0.40],
    )
    assert selected == ()
    assert no_match is True
    assert detail["top_name"] == "app.open"


def test_candidate_contracts_preserve_catalog_identity() -> None:
    contracts = probe.candidate_contracts()

    # 169 -> 190: the 21 public operations sealed in C03 (2026-09-12 … 2026-09-20; plan post-goal
    # 2026-09-20, Fase 1). The catalogue is still the authenticated one, only larger.
    # 190 -> 191: weather.current (auditoría semántica REOPEN1993, grupo W).
    assert len(contracts) == 191
    assert "app.open" in contracts
