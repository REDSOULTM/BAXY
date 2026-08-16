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
SCRIPT = SCRIPTS / "blind_reset_turn_evidence_final_seal_v3.py"
SPEC = importlib.util.spec_from_file_location(
    "blind_reset_turn_evidence_final_seal_v3",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
reset = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reset
SPEC.loader.exec_module(reset)


def test_failed_report_parser_decodes_only_case_ids(tmp_path: Path) -> None:
    report = tmp_path / "opaque-report.json"
    rows = [
        (
            f'{{"case_id":"holdout:fixture-{index}",'
            f'"opaque":{{"case_id":"holdout:false-{index}",'
            '"text":"opaque"}}'
        )
        for index in range(848)
    ]
    rows.extend(
        f'{{"case_id":"context:fixture-{index}","opaque":"\\u00fe"}}'
        for index in range(12)
    )
    raw = ("{\"cases\":[" + ",".join(rows) + "]}").encode("utf-8")
    report.write_bytes(raw.replace(b'"text":"opaque"', b'"text":"\xff"'))

    holdout, contextual = reset.extract_failed_attempt_case_ids(report)

    assert len(holdout) == 848
    assert len(contextual) == 12
    assert holdout[0].startswith("fixture-")
    assert not any("false-" in source_id for source_id in holdout)


def test_failed_report_parser_rejects_trailing_or_invalid_structure(
    tmp_path: Path,
) -> None:
    report = tmp_path / "invalid-report.json"
    report.write_bytes(b'{"cases":[]} trailing')

    with pytest.raises(ValueError, match="bytes extra"):
        reset.extract_failed_attempt_case_ids(report)


def test_v3_rule_is_cryptographically_predeclared() -> None:
    assert (
        reset.canonical_sha256(reset.PRODUCTION_RULE)
        == reset.PRODUCTION_RULE_DECLARATION_SHA256
        == "d3e241eef042b5d34f4879dafc933d0fc95b1fde7d1699cca9e99924728e958c"
    )


def test_versioned_v3_seal_matches_blind_rebuild() -> None:
    output = (
        REPO / "tests" / "data" / "turn_evidence_final_seal.v3.json"
    )
    existing = json.loads(output.read_text(encoding="utf-8"))
    rebuilt = reset.build_reset_seal(
        reset.DEFAULT_HOLDOUT,
        reset.DEFAULT_V2_SEAL,
    )

    assert existing == rebuilt
    assert existing["schema"] == reset.SCHEMA
    assert existing["final"]["rows"] == 848
    assert (
        existing["final"]["source_ids_sha256"]
        == "87c2f9e0bfcadf29d172e0c5a498bba3b517ce10bdcea55c50670f83df2bcc1b"
    )
    assert existing["blind_reserve"]["rows"] == 1032
    assert (
        existing["blind_reserve"]["source_ids_sha256"]
        == "de36d3762d9dbbcbfdd6fbb06c926178aa6fc84eac5824f26bf05580f22d45d8"
    )
    assert (
        existing["audit"]["attempted_v2_selection_overlap_rows"]
        == 0
    )
    assert existing["audit"]["v2_partition_complete"] is True
    assert existing["failed_attempt"]["selected_holdout_rows"] == 848
    assert existing["failed_attempt"]["selected_contextual_rows"] == 12
    assert existing["failed_attempt"]["technical_error_rows"] == 1
    assert existing["failed_attempt"]["journal_unique_case_arm_pairs"] == 55
    assert existing["contains_text_or_labels"] is False


def test_v3_rebuild_rejects_changed_failed_attempt_bytes(
    tmp_path: Path,
) -> None:
    changed = tmp_path / "changed-report.json"
    shutil.copyfile(reset.DEFAULT_FAILED_REPORT, changed)
    with changed.open("ab") as handle:
        handle.write(b" ")

    with pytest.raises(
        ValueError,
        match="cambiaron los bytes del reporte fallido",
    ):
        reset.build_reset_seal(
            reset.DEFAULT_HOLDOUT,
            reset.DEFAULT_V2_SEAL,
            failed_report_path=changed,
        )


def _journal_row(
    *,
    case_id: str,
    fingerprint: str = "fixture-fingerprint",
    error: str = "",
) -> bytes:
    return json.dumps(
        {
            "schema": "fixture-journal",
            "fingerprint": fingerprint,
            "case_id": case_id,
            "arm": "baseline",
            "result": {
                "error": error,
                "reply": {"case_id": "opaque-false-positive"},
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")


def test_journal_validation_rejects_duplicate_or_unselected_pairs() -> None:
    rule = {
        "failed_attempt_journal_rows": 2,
        "failed_attempt_journal_schema": "fixture-journal",
        "failed_attempt_fingerprint": "fixture-fingerprint",
    }
    duplicate = [
        _journal_row(case_id="case-a", error=reset.TECHNICAL_ERROR),
        _journal_row(case_id="case-a"),
    ]
    outside = [
        _journal_row(case_id="case-a", error=reset.TECHNICAL_ERROR),
        _journal_row(case_id="case-outside"),
    ]

    with pytest.raises(ValueError, match="journal no acredita"):
        reset.validate_failed_journal(
            duplicate,
            selected_case_ids={"case-a", "case-b"},
            rule=rule,
        )
    with pytest.raises(ValueError, match="journal no acredita"):
        reset.validate_failed_journal(
            outside,
            selected_case_ids={"case-a", "case-b"},
            rule=rule,
        )


def test_journal_validation_rejects_fingerprint_mismatch() -> None:
    rule = {
        "failed_attempt_journal_rows": 2,
        "failed_attempt_journal_schema": "fixture-journal",
        "failed_attempt_fingerprint": "fixture-fingerprint",
    }
    rows = [
        _journal_row(case_id="case-a", error=reset.TECHNICAL_ERROR),
        _journal_row(
            case_id="case-b",
            fingerprint="different-fingerprint",
        ),
    ]

    with pytest.raises(ValueError, match="journal no acredita"):
        reset.validate_failed_journal(
            rows,
            selected_case_ids={"case-a", "case-b"},
            rule=rule,
        )


def test_v3_rebuild_rejects_changed_v2_predecessor(tmp_path: Path) -> None:
    changed = tmp_path / "changed-v2.json"
    payload = json.loads(reset.DEFAULT_V2_SEAL.read_text(encoding="utf-8"))
    payload["final"]["source_ids_sha256"] = "0" * 64
    changed.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="sello v2 no coincide"):
        reset.build_reset_seal(
            reset.DEFAULT_HOLDOUT,
            changed,
        )


def test_linear_policy_remains_bound_to_v2_not_v3() -> None:
    policy_path = (
        REPO
        / "src"
        / "baxy_mind"
        / "data"
        / "turn_evidence_abstention_policy.v1.json"
    )
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    v2 = json.loads(reset.DEFAULT_V2_SEAL.read_text(encoding="utf-8"))
    v3 = json.loads(reset.DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert (
        policy["final_seal_source_ids_sha256"]
        == v2["final"]["source_ids_sha256"]
    )
    assert (
        policy["final_seal_source_ids_sha256"]
        != v3["final"]["source_ids_sha256"]
    )
