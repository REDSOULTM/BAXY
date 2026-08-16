"""Guard the V8 veto-damage split against silent drift.

The instrument reads a consumed, failed and unreopenable campaign. These tests
pin the arithmetic that R144 published and the two properties that make the
reading trustworthy: the classifier calls a veto damaging only when the raw
proposal *was* the expected operation, and the priced relaxation is refused by
the same population that motivated it.
"""

from __future__ import annotations

import importlib


def _module():
    return importlib.import_module(
        "experiments.mind_router_spike.price_v8_veto_damage_by_cause"
    )


def test_classifier_only_calls_a_veto_damaging_on_the_expected_operation() -> None:
    candidate = _module()
    classify = candidate._classify

    # An operation was expected and the model proposed exactly it: damage.
    assert classify("served", "system.time", "system.time") == "correct_proposal"
    # An operation was expected and the model proposed another: the veto works.
    assert classify("served", "system.time", "task.search") == "wrong_proposal"
    # No operation is serviceable: any proposal is wrong, abstention is right.
    assert classify("outside_catalogue", None, "window.minimize") == "wrong_proposal"
    assert classify("outside_catalogue", None, None) == "correct_abstention"
    # An expected operation with no proposal at all is not veto damage.
    assert classify("served", "system.status", None) == "no_proposal"


def test_the_two_curated_rules_still_veto_the_six_published_surfaces() -> None:
    """The damage attribution is only valid while these predicates still fire."""

    candidate = _module()
    grounded = candidate.effect_intent.operation_domain_is_grounded
    surfaces = (
        ("Check what hour this device indicates at this instant.", "system.time"),
        ("Consulta qué hora señala este aparato en este instante.", "system.time"),
        ("Consulta what hour señala este aparato right this instant.", "system.time"),
        ("Descubre which part of the day cree estar este equipo.", "system.time"),
        ("Tell me how healthy this device is doing right now.", "system.status"),
        ("Cuéntame how healthy anda este aparato right now.", "system.status"),
    )
    for text, operation in surfaces:
        assert grounded(text, operation, ()) is False, text
        assert (
            candidate.effect_intent._curated_domain_is_grounded(text, operation, ())
            is False
        ), text


def test_restatement_overlap_separates_a_paraphrase_from_a_real_question() -> None:
    candidate = _module()
    overlap = candidate._restatement_overlap
    request = "Enséñame qué trabajos siguen despiertos dentro del equipo."
    paraphrase = "¿Cuáles son los trabajos que actualmente están en ejecución dentro del equipo?"
    absent_datum = "¿Qué nombre tiene la carpeta que quieres respaldar?"
    assert overlap(paraphrase, request) > overlap(absent_datum, request)


def test_published_split_and_ceiling_are_the_numbers_r144_reported() -> None:
    candidate = _module()
    report = candidate.build()

    integrity = report["integrity"]
    assert integrity["v8_artifacts"]["artifacts_match_consumption_receipt"]
    assert integrity["program_identity"]["runtime_files_identical"]

    split = report["question_1_vetos_by_what_they_retired"]
    assert split["veto_count"] == 31
    assert split["retired_a_correct_proposal"] == 6
    assert split["retired_a_wrong_proposal"] == 25
    assert split["damaged_rows"] == [
        "v8-mach-02-en",
        "v8-mach-02-es",
        "v8-mach-02-mix",
        "v8-srv-01-mix",
        "v8-srv-03-en",
        "v8-srv-03-mix",
    ]

    attribution = report["question_2_damage_attribution"]
    assert len(attribution) == 6
    assert all(row["fired"] for row in attribution)
    assert {row["predicate"] for row in attribution} == {
        "effect_intent._curated_domain_is_grounded"
    }

    clarifications = report["question_3_clarifications"]
    assert clarifications["clarification_rows"] == 9
    assert clarifications["useful_clarifications"] == 0
    assert clarifications["after_a_correct_proposal"] == 2

    ceiling = report["question_4_honest_ceiling"]
    assert ceiling["served_today"] == "1/21"
    assert (
        ceiling["served_if_nothing_after_the_decision_discarded_a_correct_proposal"]
        == "7/21"
    )
    assert ceiling["lost_after_the_decision"] == 6

    relaxation = report["priced_relaxation"]
    assert relaxation["verdict"] == "rejected_reopens_a_hard_zero"
    assert relaxation["correct_proposals_recovered"] == 6
    assert relaxation["wrong_proposals_released"] == 6
    assert relaxation["unsolicited_effects_reopened"] == 5


def test_the_measurement_neither_reopens_nor_rescores_v8() -> None:
    candidate = _module()
    report = candidate.build()
    assert report["v8_reopened"] is False
    assert report["v8_rescored"] is False
    assert report["providers_enabled"] is False
    assert report["effects_executed"] == 0
    assert report["reads_only_published_artifacts"] is True
