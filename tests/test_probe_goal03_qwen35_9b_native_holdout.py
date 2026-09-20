from __future__ import annotations

from experiments.mind_router_spike import probe_goal03_qwen35_9b_native_holdout as probe


def test_candidate_contracts_preserve_catalog_identity() -> None:
    contracts = probe.candidate_contracts()

    # 169 -> 190: the 21 public operations sealed in C03 (2026-09-12 … 2026-09-20; plan post-goal
    # 2026-09-20, Fase 1). The catalogue is still the authenticated one, only larger.
    # 190 -> 192: weather.current y web.news.headlines (auditoría semántica REOPEN1993, grupos W y N).
    assert len(contracts) == 192
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


def test_malformed_native_response_fails_closed(monkeypatch) -> None:
    def malformed(*args, **kwargs):
        raise ValueError("selector response emitted arguments")

    monkeypatch.setattr(probe, "_select", malformed)

    selected, no_match, error = probe.safe_native_select(
        object(),
        "open calculator",
        [{"name": "app.open"}],
    )

    assert selected == ()
    assert no_match is True
    assert error == {
        "type": "ValueError",
        "message": "selector response emitted arguments",
    }


def test_transport_failures_are_not_hidden(monkeypatch) -> None:
    def unavailable(*args, **kwargs):
        raise ConnectionError("server unavailable")

    monkeypatch.setattr(probe, "_select", unavailable)

    try:
        probe.safe_native_select(object(), "open calculator", [{"name": "app.open"}])
    except ConnectionError as error:
        assert str(error) == "server unavailable"
    else:
        raise AssertionError("transport failure was hidden")
