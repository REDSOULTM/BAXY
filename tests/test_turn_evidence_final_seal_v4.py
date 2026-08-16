from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))
SCRIPT = SCRIPTS / "blind_reset_turn_evidence_final_seal_v4.py"
SPEC = importlib.util.spec_from_file_location(
    "blind_reset_turn_evidence_final_seal_v4",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
reset = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reset
SPEC.loader.exec_module(reset)


@pytest.fixture(scope="module")
def canonical_v4() -> dict:
    return reset.build_reset_seal(
        reset.DEFAULT_HOLDOUT,
        reset.DEFAULT_V3_SEAL,
    )


def _opaque_report_bytes(*, trailing: bytes = b"") -> bytes:
    cases = [
        (
            b'{"case_id":"holdout:fixture-'
            + f"{index:04d}".encode("ascii")
            + b'","expected_modes":"\xff"}'
        )
        for index in range(848)
    ]
    cases.extend(
        (
            b'{"case_id":"context:fixture-'
            + f"{index:04d}".encode("ascii")
            + b'","expected_families":"\xfe"}'
        )
        for index in range(12)
    )
    return (
        b"{"
        b'"schema":"baxy.turn-policy-ab-gate.v1",'
        b'"fingerprint":"fixture-fingerprint",'
        b'"complete":false,'
        b'"selection":{'
        b'"expected_measured_calls":1720,'
        b'"completed_measured_calls":310,'
        b'"selected_holdout":848,'
        b'"selected_contextual":12'
        b"},"
        b'"cleanliness":{'
        b'"selection_scope":"sealed_final_v3_only",'
        b'"seal_schema":"baxy.turn-evidence-final-seal.v3",'
        b'"seal_sha256":"fixture-seal",'
        b'"sealed_final_source_ids_sha256":"fixture-final",'
        b'"evaluated_holdout_source_ids_sha256":"fixture-final",'
        b'"blind_manifest_rebuilt":true'
        b"},"
        b'"cases":['
        + b",".join(cases)
        + b"]}"
        + trailing
    )


def _journal_line(
    case_id: str,
    *,
    fingerprint: str = "fixture-fingerprint",
    error: str = "",
) -> bytes:
    return (
        b"{"
        b'"schema":"fixture-journal",'
        b'"fingerprint":'
        + json.dumps(fingerprint).encode("ascii")
        + b","
        b'"case_id":'
        + json.dumps(case_id).encode("ascii")
        + b","
        b'"arm":"baseline",'
        b'"result":{"reply":"\xff","error":'
        + json.dumps(error).encode("ascii")
        + b"}}"
    )


def test_v4_rule_is_cryptographically_predeclared() -> None:
    assert (
        reset.canonical_sha256(reset.PRODUCTION_RULE)
        == reset.PRODUCTION_RULE_DECLARATION_SHA256
        == "76f77061330729426e5fd0b063c37991aed4d63c7b83665d4c369cbe4e979807"
    )


def test_v4_derivation_is_reproducible_and_partitions_v3_reserve(
    canonical_v4: dict,
) -> None:
    rebuilt = reset.build_reset_seal(
        reset.DEFAULT_HOLDOUT,
        reset.DEFAULT_V3_SEAL,
    )

    assert rebuilt == canonical_v4
    assert canonical_v4["schema"] == reset.SCHEMA
    assert canonical_v4["eligible_pool"] == {
        "definition": "verified_v3_blind_reserve",
        "rows": 1032,
        "source_ids_sha256": (
            "de36d3762d9dbbcbfdd6fbb06c926178aa6fc84eac5824f26bf05580f22d45d8"
        ),
    }
    assert canonical_v4["final"]["rows"] == 848
    assert (
        canonical_v4["final"]["source_ids_sha256"]
        == "d8463dfcbbeab2be65bc61a0335ac9f896bebae69a60ff2741b4b9b0f1d0507c"
    )
    assert (
        canonical_v4["final"]["ranked_source_ids_sha256"]
        == "ceeedcb650676d2d618faa2e78b56de149770a0a76643bbd967c76065780b437"
    )
    assert (
        canonical_v4["final"]["selection_cutoff_digest_sha256"]
        == "d2f8f603021d62308d188750f5e3a0e1f45674fd09c03e1abe2d1f2c73de82c6"
    )
    assert canonical_v4["blind_reserve"]["rows"] == 184
    assert (
        canonical_v4["blind_reserve"]["source_ids_sha256"]
        == "6516c3a0b9f1a7e0f49ad5b9e30ab934f4be1332763cdb43a44f0759e3f918d9"
    )
    assert (
        canonical_v4["blind_reserve"]["ranked_source_ids_sha256"]
        == "745f163e7841aa83154dfee6d02e8c31be9b01daadd8ab08edb35e1c9ae06d3b"
    )
    assert canonical_v4["audit"] == {
        "predecessor_chain_rebuilt": True,
        "failed_v3_selection_equals_predecessor_final": True,
        "failed_v3_selection_reserve_overlap_rows": 0,
        "final_predecessor_final_overlap_rows": 0,
        "selected_reserve_overlap_rows": 0,
        "eligible_partition_complete": True,
        "only_predecessor_blind_reserve_used": True,
    }
    assert canonical_v4["evaluation"] == {
        "performed_by_generator": False,
        "scores_present": False,
    }
    assert canonical_v4["contains_text_or_labels"] is False


def test_v4_binds_the_preserved_v3_attempt(canonical_v4: dict) -> None:
    attempt = canonical_v4["failed_attempt"]

    assert (
        attempt["report_sha256"]
        == "47e61fea7399be5898ed3a24d10197c986cff93c7c37822c4c2183896636fef1"
    )
    assert (
        attempt["journal_sha256"]
        == "d99534074936aeb99e4b65d70fb1ad4c034e2d46f28263aba18460ece8c5df6f"
    )
    assert (
        attempt["journal_fingerprint"]
        == "00532ca64b048b885157e762f2e0affab958baa8a6bcca4cfbb5ec61cc837c4f"
    )
    assert attempt["report_checkpoint_completed_measured_calls"] == 310
    assert attempt["journal_rows"] == 313
    assert attempt["journal_unique_case_arm_pairs"] == 313
    assert attempt["journal_arms"] == ["baseline"]
    assert attempt["journal_nonempty_error_rows"] == 1
    assert (
        attempt["journal_case_arm_pairs_sha256"]
        == "6c14ddded0918c5fb1fa68faf0bcd0d13ae943417f40499679262480c4b8b934"
    )
    assert attempt["selected_holdout_rows"] == 848
    assert (
        attempt["selected_holdout_source_ids_sha256"]
        == "87c2f9e0bfcadf29d172e0c5a498bba3b517ce10bdcea55c50670f83df2bcc1b"
    )
    assert attempt["selected_contextual_rows"] == 12
    assert (
        attempt["selected_contextual_source_ids_sha256"]
        == "8105d156c7fe454aed7ef4001a93de5c1371d42ad4adaed7c6092c4b20d3235c"
    )


def test_report_parsers_leave_expected_payloads_opaque(
    tmp_path: Path,
) -> None:
    report = tmp_path / "opaque-report.json"
    report.write_bytes(_opaque_report_bytes())

    identity = reset.extract_failed_report_identity(report)
    holdout, contextual = reset.extract_failed_attempt_case_ids(report)

    assert identity["schema"] == "baxy.turn-policy-ab-gate.v1"
    assert identity["complete"] is False
    assert identity["selection"]["completed_measured_calls"] == 310
    assert identity["cleanliness"]["selection_scope"] == (
        "sealed_final_v3_only"
    )
    assert len(holdout) == 848
    assert len(contextual) == 12


def test_report_parser_rejects_trailing_structure(tmp_path: Path) -> None:
    report = tmp_path / "trailing-report.json"
    report.write_bytes(_opaque_report_bytes(trailing=b"\xff"))

    with pytest.raises(ValueError, match="bytes extra"):
        reset.extract_failed_report_identity(report)


def test_journal_validation_skips_opaque_model_reply() -> None:
    rule = dict(
        reset.PRODUCTION_RULE,
        failed_attempt_journal_rows=2,
        failed_attempt_journal_schema="fixture-journal",
        failed_attempt_fingerprint="fixture-fingerprint",
        failed_attempt_journal_arms=["baseline"],
        failed_attempt_nonempty_error_rows=1,
    )
    lines = [
        _journal_line("case-a"),
        _journal_line("case-b", error="technical"),
    ]

    rows = reset.validate_failed_journal(
        lines,
        selected_case_ids={"case-a", "case-b"},
        rule=rule,
    )

    assert [(row["arm"], row["case_id"]) for row in rows] == [
        ("baseline", "case-a"),
        ("baseline", "case-b"),
    ]


def test_journal_validation_rejects_fingerprint_mismatch() -> None:
    rule = dict(
        reset.PRODUCTION_RULE,
        failed_attempt_journal_rows=1,
        failed_attempt_journal_schema="fixture-journal",
        failed_attempt_fingerprint="fixture-fingerprint",
        failed_attempt_journal_arms=["baseline"],
        failed_attempt_nonempty_error_rows=0,
    )

    with pytest.raises(ValueError, match="journal"):
        reset.validate_failed_journal(
            [_journal_line("case-a", fingerprint="other")],
            selected_case_ids={"case-a"},
            rule=rule,
        )


def test_v4_rejects_changed_v3_attempt_bytes(tmp_path: Path) -> None:
    changed = tmp_path / "changed-v3-report.json"
    shutil.copyfile(reset.DEFAULT_FAILED_REPORT, changed)
    with changed.open("ab") as handle:
        handle.write(b" ")

    with pytest.raises(
        ValueError,
        match="cambiaron los bytes del reporte fallido v3",
    ):
        reset.build_reset_seal(
            reset.DEFAULT_HOLDOUT,
            reset.DEFAULT_V3_SEAL,
            failed_report_path=changed,
        )


def test_v4_rejects_mutated_v3_seal(tmp_path: Path) -> None:
    payload = json.loads(
        reset.DEFAULT_V3_SEAL.read_text(encoding="utf-8")
    )
    payload["blind_reserve"]["source_ids_sha256"] = "0" * 64
    changed = tmp_path / "changed-v3-seal.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="bytes del sello v3"):
        reset.build_reset_seal(
            reset.DEFAULT_HOLDOUT,
            changed,
        )


def test_linear_probe_policy_remains_bound_to_v2(
    canonical_v4: dict,
) -> None:
    policy = json.loads(
        (
            REPO
            / "src"
            / "baxy_mind"
            / "data"
            / "turn_evidence_abstention_policy.v1.json"
        ).read_text(encoding="utf-8")
    )

    assert (
        policy["final_seal_source_ids_sha256"]
        == canonical_v4["policy_calibration"][
            "final_source_ids_sha256"
        ]
        == "fa087da33ffde997db39614cd03f98df60223642ce1d78899b49748aef2475a9"
    )
    assert (
        policy["final_seal_source_ids_sha256"]
        != canonical_v4["predecessor"]["final_source_ids_sha256"]
        != canonical_v4["final"]["source_ids_sha256"]
    )


def test_v4_seal_contains_no_case_or_model_payloads(
    canonical_v4: dict,
) -> None:
    encoded = json.dumps(canonical_v4, ensure_ascii=False)

    for forbidden_key in (
        '"cases"',
        '"expected_modes"',
        '"expected_families"',
        '"arms"',
        '"result"',
        '"reply"',
        '"question"',
    ):
        assert forbidden_key not in encoded
