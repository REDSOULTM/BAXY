from __future__ import annotations

from experiments.mind_router_spike import probe_goal03_xlam2_3b_native_holdout as probe


def test_candidate_contracts_preserve_catalog_identity() -> None:
    contracts = probe.candidate_contracts()

    # 169 -> 190: the 21 public operations sealed in C03 (2026-09-12 … 2026-09-20; plan post-goal
    # 2026-09-20, Fase 1). The catalogue is still the authenticated one, only larger.
    # 190 -> 193: weather.current, web.news.headlines y package.uninstall (auditoría semántica REOPEN1993, grupos W, N y G).
    assert len(contracts) == 193
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
    assert probe.MODEL.name == "xLAM-2-3B-fc-r-Q4_K_M.gguf"
    assert probe.EXPECTED_SHA256[probe.MODEL] == (
        "bd1a0480eadf5eddced7159e4b7aa68cc3cb47715d7410c99d3b4c485e47ae43"
    )


def test_malformed_native_response_fails_closed(monkeypatch) -> None:
    def malformed(*args, **kwargs):
        raise ValueError("selector response has no unique choice")

    monkeypatch.setattr(probe, "select_xlam", malformed)

    selected, no_match, error = probe.safe_native_select(
        object(),
        "open calculator",
        [{"name": "app.open"}],
    )

    assert selected == ()
    assert no_match is True
    assert error == {
        "type": "ValueError",
        "message": "selector response has no unique choice",
    }


def test_transport_failures_are_not_hidden(monkeypatch) -> None:
    def unavailable(*args, **kwargs):
        raise ConnectionError("server unavailable")

    monkeypatch.setattr(probe, "select_xlam", unavailable)

    try:
        probe.safe_native_select(object(), "open calculator", [{"name": "app.open"}])
    except ConnectionError as error:
        assert str(error) == "server unavailable"
    else:
        raise AssertionError("transport failure was hidden")


def test_smoke_does_not_open_the_exam() -> None:
    rows, output, counts = probe.population("smoke")

    assert len(rows) == 2
    assert counts == {"positive": 1, "no_action": 1}
    assert output == probe.SMOKE_OUTPUT
    assert rows[0]["expected_operation"] == "app.open"
    assert rows[1]["expected_operation"] == "__no_action__"


def test_xlam_parser_reads_json_array_and_prose() -> None:
    mapping = {"baxy_app__open": "app.open"}

    selected, no_match, error = probe.parse_xlam_content(
        '[{"name": "baxy_app__open", "arguments": {}}]',
        mapping,
    )
    assert selected == ("app.open",)
    assert no_match is False
    assert error is None

    selected, no_match, error = probe.parse_xlam_content(
        "The capital of France is Paris.",
        mapping,
    )
    assert selected == ()
    assert no_match is True
    assert error is None


def test_xlam_parser_recovers_name_from_malformed_array() -> None:
    mapping = {"baxy_app__open": "app.open"}

    selected, no_match, error = probe.parse_xlam_content(
        '[{"name": "baxy_app__open", "arguments": {"app_name"::"calculator"}}]',
        mapping,
    )
    assert selected == ("app.open",)
    assert no_match is False
    assert error is not None
    assert error["type"] == "JSONDecodeError"


def test_xlam_parser_rejects_escaped_tool_names() -> None:
    selected, no_match, error = probe.parse_xlam_content(
        '[{"name": "not_a_candidate", "arguments": {}}]',
        {"baxy_app__open": "app.open"},
    )
    assert selected == ()
    assert no_match is True
    assert error == {
        "type": "ValueError",
        "message": "selector response escaped the declared tools",
    }
