"""Guard the V8 veto-damage split against silent drift.

The instrument reads a consumed, failed and unreopenable campaign. These tests
pin the arithmetic that R144 published and the two properties that make the
reading trustworthy: the classifier calls a veto damaging only when the raw
proposal *was* the expected operation, and the priced relaxation is refused by
the same population that motivated it.
"""

from __future__ import annotations

import importlib


# The consumed V8 evidence no longer hashes to its consumption receipt, and
# cannot: the six artifacts were committed with their CRLF preserved
# (`.gitattributes -text`, R277/R278) after the receipt was written, and the
# bytes the runner hashed while consuming the campaign survive in no repository
# of this project — `Programacion\BAXY` holds these same bytes. What stays
# auditable is that the evidence has not moved since, so it is sealed here (§7).
V8_EVIDENCE_SHA256 = {
    "corpus_sha256": (
        "afdfd428946972f57b75662f8cffcd9024ebe4d165a3e757f8dece77f2f10a38"
    ),
    "preregistration_sha256": (
        "e53cd8935efb3f8c70baf9b4ff8a1fcecf5dd0aa99e78358bc104246bf3a74ac"
    ),
    "raw_reply_audit_sha256": (
        "1911f07f0f80c3dcaaf5e40781ff0e5d188143cb5fe33df325408dcc33e34010"
    ),
    "result_sha256": (
        "915b74d1fb56f34c18b94f856a0c8d3dd5ed7444b64282bbf626922d6c8201c7"
    ),
    "telemetry_sha256": (
        "28ba0e9fe99cf27dcf94643049f1b6a6dbb3a483b3cf9c8a6bad5c73dd1d07ba"
    ),
    "turn_audit_sha256": (
        "d3b9659350aabe6bf15d191bf14627457ca3ecbf08d9dcbf6ee76fb8446e28c3"
    ),
}

# Runtime data bound by the V8 preregistration that is no longer what it froze.
# Test files are excluded for the same reason the published audit calls the
# runtime identical while recording tests/test_veto_reach_v8.py as changed —
# a test is not what the campaign executed.
V8_DATA_DRIFTED_SINCE_THE_CAMPAIGN = {
    "src/baxy_mind/data/catalog_operation_aliases.v1.json": (
        "e8fc3ca7bb94224b24f653eb267d4426165554e78947e261fddbaf046b17a5a4"
    ),
}

# Programs V8 executed that goal 03 replaced, kept apart from the data drift so
# the two never blur into one another. The consequence has to be said plainly:
# **V8's numbers describe a decision path this tree no longer has.** Retrieval
# ranked families and handed out a window inside the winner; it now ranks the
# authenticated operations directly. The forced tool-choice contract was on for
# a model whose filename contained "qwen3"; it is off. Both changes were priced
# on a fresh paraphrase population (artifacts/development/goal03_*.json) and
# both move these files by construction. Anything drifting that is not listed
# here still turns this red.
V8_PROGRAMS_REPLACED_BY_GOAL_03 = {
    "src/baxy_mind/__main__.py": (
        "dd422531619907e544f52c211d5ae4a921d8d8d8ba54cd977feeb70d33cd2906"
    ),
    "src/baxy_mind/llm.py": (
        "ac73372b1211a8fb0e98e18415be4607cb5aea4d08feb40f76cc9650b4ca959d"
    ),
}


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
    assert integrity["v8_artifacts"]["observed"] == V8_EVIDENCE_SHA256
    # What moved since the campaign, named file by file and split by kind: the
    # catalogue aliases moved with the catalogue (157 -> 158 operations), and
    # goal 03 replaced the two decision-path programs.
    identity = integrity["program_identity"]
    assert {
        row["file"]: row["observed_sha256"]
        for row in identity["files"]
        if not row["identical"] and not row["file"].startswith("tests/")
    } == {
        **V8_DATA_DRIFTED_SINCE_THE_CAMPAIGN,
        **V8_PROGRAMS_REPLACED_BY_GOAL_03,
    }

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
