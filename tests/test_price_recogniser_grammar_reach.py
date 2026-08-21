"""Pin the measurement that explains cut B 700/700 against V8 1 of 21.

The claim these tests protect is structural, not cosmetic: the two sealed
populations exercise different paths through the product, so their numbers were
never comparable.
"""

from __future__ import annotations

import importlib


def _module():
    return importlib.import_module(
        "experiments.mind_router_spike.price_recogniser_grammar_reach"
    )


def test_catalogue_is_the_versioned_alias_source_not_the_corpora() -> None:
    """Neither population may define the operation set it is scored against."""

    candidate = _module()
    operations = candidate.catalogue_operations()
    # 157, not the historical 158: the authenticated catalogue retired
    # notification.cancel.at (recorded in R263 as the only legacy operation
    # absent from the current catalogue) and R267 rebound the recogniser
    # aliases to it. This asserts the current inventory, not a relaxed bar.
    assert len(operations) == 157
    assert "notification.cancel.at" not in operations
    assert operations == tuple(sorted(operations))
    assert "system.time" in operations
    assert "capture.screenshot" in operations


def test_the_two_seals_sit_on_opposite_sides_of_the_recogniser() -> None:
    candidate = _module()
    report = candidate.build()
    cut_b, veto = report["populations"]

    assert cut_b["rows"] == 336
    assert veto["rows"] == 21

    # Cut B resolves deterministically almost everywhere; V8 never does.
    assert cut_b["deterministic_recogniser"]["reach"] >= 0.95
    assert veto["deterministic_recogniser"]["resolved_the_expected_operation"] == 0
    assert veto["deterministic_recogniser"]["did_not_resolve"] == 21


def test_cut_b_cannot_price_the_domain_gate() -> None:
    """Most cut B rows the gate would veto never reach it."""

    candidate = _module()
    cut_b = candidate.build()["populations"][0]
    gate = cut_b["domain_gate"]
    assert gate["would_veto_the_expected_operation"] == 162
    assert gate["rescued_because_the_recogniser_resolved_first"] == 158
    assert gate["veto_actually_reaches_the_turn"] == 4


def test_the_gate_reaches_almost_every_v8_serviceable_row() -> None:
    candidate = _module()
    veto = candidate.build()["populations"][1]
    gate = veto["domain_gate"]
    assert gate["would_veto_the_expected_operation"] == 18
    assert gate["rescued_because_the_recogniser_resolved_first"] == 0
    assert gate["veto_actually_reaches_the_turn"] == 18


def test_neither_population_leaks_its_own_alias_surface() -> None:
    """The gap is grammar reach, not alias vocabulary left in the payload."""

    candidate = _module()
    for population in candidate.build()["populations"]:
        assert (
            population["rows_literally_containing_an_alias_of_their_own_operation"] == 0
        )


def test_the_measurement_starts_nothing_and_executes_nothing() -> None:
    candidate = _module()
    report = candidate.build()
    assert report["product_started"] is False
    assert report["decider_invoked"] is False
    assert report["providers_enabled"] is False
    assert report["effects_executed"] == 0
