from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "blind_reset_turn_evidence_final_seal.py"
SPEC = importlib.util.spec_from_file_location(
    "blind_reset_turn_evidence_final_seal",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
reset = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reset
SPEC.loader.exec_module(reset)


def _fixture_ids() -> tuple[list[str], list[str]]:
    selected: list[str] = []
    complement: list[str] = []
    index = 0
    while len(selected) < 12 or len(complement) < 24:
        source_id = f"fixture:{index:04d}"
        if reset.old_source_id_digest(source_id)[0] >= reset.OLD_THRESHOLD:
            selected.append(source_id)
        else:
            complement.append(source_id)
        index += 1
    return selected, complement


def _write_predecessor_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, list[str], list[str]]:
    selected, complement = _fixture_ids()
    source_ids = sorted(selected + complement)
    holdout = tmp_path / "holdout.jsonl"
    holdout.write_text(
        "".join(
            json.dumps(
                {
                    "split": "test",
                    "source_id": source_id,
                    "text": f"opaque private text {source_id}",
                    "mode": "must-never-be-decoded",
                    "families": ["also-opaque"],
                },
                sort_keys=True,
            )
            + "\n"
            for source_id in reversed(source_ids)
        ),
        encoding="utf-8",
    )
    old_selected = [
        source_id
        for source_id in source_ids
        if reset.old_source_id_digest(source_id)[0] >= reset.OLD_THRESHOLD
    ]
    old_complement = [
        source_id
        for source_id in source_ids
        if reset.old_source_id_digest(source_id)[0] < reset.OLD_THRESHOLD
    ]
    old_seal_value = {
        "schema": reset.OLD_SCHEMA,
        "rule": reset.OLD_RULE,
        "holdout": {
            "repo_path": "holdout.jsonl",
            "sha256": reset.file_sha256(holdout),
            "test_rows": len(source_ids),
        },
        "final": {
            "rows": len(old_selected),
            "source_ids_sha256": reset.list_sha256(old_selected),
            "source_ids": old_selected,
        },
        "exploratory_complement": {
            "rows": len(old_complement),
            "source_ids_sha256": reset.list_sha256(old_complement),
        },
        "partition_source_ids_sha256": reset.list_sha256(source_ids),
        "contains_text_or_labels": False,
    }
    old_seal = tmp_path / "old-seal.json"
    old_seal.write_text(
        json.dumps(old_seal_value, sort_keys=True),
        encoding="utf-8",
    )
    return holdout, old_seal, old_selected, old_complement


def test_selective_parser_never_decodes_opaque_test_values(
    tmp_path: Path,
) -> None:
    holdout = tmp_path / "opaque.jsonl"
    holdout.write_bytes(
        b'{"split":"test","source_id":"test-a","text":"\xff",'
        b'"mode":{"nested":["\xfe"]}}\n'
        b'{"split":"validation","source_id":"validation-a",'
        b'"text":"\xfd"}\n'
    )

    assert reset.extract_test_source_ids(holdout) == ["test-a"]


def test_blind_reset_is_reproducible_and_disjoint(
    tmp_path: Path,
) -> None:
    holdout, old_seal, old_final, old_complement = (
        _write_predecessor_fixture(tmp_path)
    )
    contaminated = [
        old_final[0],
        old_final[1],
        old_complement[0],
        old_complement[1],
        old_complement[2],
    ]
    rule = dict(reset.PRODUCTION_RULE, take_rows=10)

    first = reset.build_reset_seal(
        holdout,
        old_seal,
        contaminated_source_ids=contaminated,
        rule=rule,
    )
    second = reset.build_reset_seal(
        holdout,
        old_seal,
        contaminated_source_ids=reversed(contaminated),
        rule=rule,
    )

    assert first == second
    final_ids = set(first["final"]["source_ids"])
    eligible = set(old_complement) - set(contaminated)
    assert final_ids <= eligible
    assert final_ids.isdisjoint(old_final)
    assert final_ids.isdisjoint(contaminated)
    assert first["final"]["rows"] == 10
    assert (
        first["final"]["rows"] + first["blind_reserve"]["rows"]
        == len(eligible)
    )
    assert first["audit"] == {
        "all_declared_contamination_found_in_test": True,
        "old_final_v1_overlap_rows": 0,
        "declared_contamination_overlap_rows": 0,
        "selected_reserve_overlap_rows": 0,
        "eligible_partition_complete": True,
        "only_predecessor_unevaluated_complement_used": True,
    }
    assert first["contamination"]["old_final_overlap_rows"] == 2
    assert first["contamination"]["old_complement_overlap_rows"] == 3
    assert first["evaluation"]["performed_by_generator"] is False
    assert first["evaluation"]["scores_present"] is False
    encoded = json.dumps(first)
    assert "opaque private text" not in encoded
    assert '"mode"' not in encoded
    assert '"families"' not in encoded


def test_reset_rejects_unaccounted_contamination(tmp_path: Path) -> None:
    holdout, old_seal, old_final, old_complement = (
        _write_predecessor_fixture(tmp_path)
    )
    contaminated = [
        old_final[0],
        old_final[1],
        old_complement[0],
        old_complement[1],
        "not-in-test",
    ]

    with pytest.raises(
        ValueError,
        match="contaminación contiene IDs fuera de test",
    ):
        reset.build_reset_seal(
            holdout,
            old_seal,
            contaminated_source_ids=contaminated,
            rule=dict(reset.PRODUCTION_RULE, take_rows=10),
        )


def test_production_rule_is_cryptographically_predeclared() -> None:
    assert (
        reset.canonical_sha256(reset.PRODUCTION_RULE)
        == reset.PRODUCTION_RULE_DECLARATION_SHA256
        == "b06a8ac18cc2bea2b29f628aa5a9a3cf51cede896e50cbf98c8850a0ea27d61d"
    )


def test_versioned_v2_seal_matches_blind_rebuild_and_incident_audit() -> None:
    output = (
        REPO / "tests" / "data" / "turn_evidence_final_seal.v2.json"
    )
    existing = json.loads(output.read_text(encoding="utf-8"))
    rebuilt = reset.build_reset_seal(
        reset.DEFAULT_HOLDOUT,
        reset.DEFAULT_OLD_SEAL,
    )

    assert existing == rebuilt
    assert existing["final"]["rows"] == 2728
    assert (
        existing["final"]["source_ids_sha256"]
        == "fa087da33ffde997db39614cd03f98df60223642ce1d78899b49748aef2475a9"
    )
    assert existing["contamination"]["declared_rows"] == 5
    assert existing["contamination"]["old_final_overlap_rows"] == 2
    assert existing["contamination"]["old_complement_overlap_rows"] == 3
    assert existing["audit"]["old_final_v1_overlap_rows"] == 0
    assert existing["audit"]["declared_contamination_overlap_rows"] == 0
    assert existing["contains_text_or_labels"] is False
