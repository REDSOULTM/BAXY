"""Goal 09.5.9 — load the shipped decision matrix, not a fixture copy."""

from __future__ import annotations

from pathlib import Path

from scripts.goal095_0959_matrix import (
    ASSIGNMENT_REL,
    BATCH_CAP,
    CAMPAIGN_REL,
    DECIDE_PROMPT,
    FORBIDDEN_TERMINALS,
    LEDGER_REL,
    PROTECTED_REJECTS,
    REUSE_ADAPT,
    SCHEMA,
    SYNTHESIS_REL,
    TERMINALS,
    TRANSPLANT_PROMPT,
    TRANSPLANT_TERMINALS,
    campaign_counts,
    campaign_path,
    index_audit_card_ids,
    index_synthesis_responsibility_ids,
    load_assignment,
    load_campaign,
    load_json,
    load_matrix,
    lots_from_matrix,
    matrix_path,
    synthesis_ledger_path,
    validate_campaign,
    validate_matrix,
)
from scripts.goal095_docs_ledger import load_json as load_json_docs
from scripts.goal095_evidence_campaign import campaign_path as evidence_campaign_path
from scripts.goal095_evidence_campaign import counts_for

REPO = Path(__file__).resolve().parents[1]


def test_shipped_0959_matrix_is_the_repo_artifact() -> None:
    path = matrix_path(REPO)
    assert path == REPO / SYNTHESIS_REL
    assert path.is_file()
    data = load_matrix(REPO)
    assert data["schema"] == SCHEMA
    assert path.read_text(encoding="utf-8").startswith("{")
    assign = REPO / ASSIGNMENT_REL
    assert assign.is_file()
    assert assign.read_text(encoding="utf-8").startswith("{")
    camp = campaign_path(REPO)
    assert camp == REPO / CAMPAIGN_REL
    assert camp.is_file()


def test_shipped_0959_matrix_satisfies_goal() -> None:
    data = load_matrix(REPO)
    assignment = load_assignment(REPO)
    card_ids = index_audit_card_ids(REPO)
    synthesis_ids = index_synthesis_responsibility_ids(REPO)
    errors = validate_matrix(data, card_ids, synthesis_ids, assignment, repo=REPO)
    assert errors == []
    present = {row["id"] for row in data["responsibilities"]}
    assert set(PROTECTED_REJECTS) <= present
    assert data["estado_del_arte_added"] is False
    assert data["live_src_changed"] is False
    assert data["other_languages_create_work"] is False
    assert DECIDE_PROMPT not in str(data["next_human_prompt"])
    json_text = REPO.joinpath(SYNTHESIS_REL).read_text(encoding="utf-8")
    for forbidden in ("review", "pendiente"):
        assert f'"decision": "{forbidden}"' not in json_text
    for old in ("conservar", "medir", "reusar", "reemplazar_candidato"):
        if old in FORBIDDEN_TERMINALS:
            assert f'"decision": "{old}"' not in json_text
    mapping = assignment["card_to_row"]
    assert set(mapping) == card_ids
    assert len(mapping) == len(card_ids)
    row_ids = {row["id"] for row in data["responsibilities"]}
    assert set(mapping.values()) <= row_ids
    assigned_refs: list[str] = []
    for row in data["responsibilities"]:
        assert row["decision"] in TERMINALS
        assert row["decision"] not in FORBIDDEN_TERMINALS
        for field in ("conducta", "pruebas", "recursos", "arquitectura"):
            assert str(row[field]).strip()
        assigned_refs.extend(row["synthesis_refs"])
        if row["id"] in PROTECTED_REJECTS:
            assert row["decision"] == "rechazar"
            assert row["protected"] is True
        if row["decision"] in REUSE_ADAPT:
            tokens = row["transplant_batch"]
            if isinstance(tokens, dict):
                tokens = tokens.get("tokens")
            assert int(tokens) < BATCH_CAP
            assert str(row["pieza_que_se_retira"]).strip()
        if row["decision"] == "medir_antes":
            for field in ("instrument", "corpus", "presupuesto", "stop_rule"):
                assert str(row[field]).strip()
        if row["decision"] == "rechazar":
            for field in ("mecanismo_de_fracaso", "coste", "invariante"):
                assert str(row[field]).strip()
    assert len(assigned_refs) == len(set(assigned_refs))
    assert set(assigned_refs) == synthesis_ids


def test_shipped_0959_campaign_matches_matrix_and_blocks_protected() -> None:
    matrix = load_matrix(REPO)
    campaign = load_campaign(REPO)
    errors = validate_campaign(campaign, matrix)
    assert errors == []
    expected = lots_from_matrix(matrix)
    assert [lot["responsibility_id"] for lot in campaign["lots"]] == [
        lot["responsibility_id"] for lot in expected
    ]
    counts = campaign_counts(campaign)
    assert campaign["counts"]["pending"] == counts["pending"]
    assert campaign["counts"]["claimed"] == counts["claimed"]
    assert campaign["counts"]["complete"] == counts["complete"]
    assert campaign["counts"]["total"] == len(campaign["lots"])
    transplant_rows = [
        row["id"]
        for row in matrix["responsibilities"]
        if row["decision"] in TRANSPLANT_TERMINALS
    ]
    assert set(lot["responsibility_id"] for lot in campaign["lots"]) == set(transplant_rows)
    if not transplant_rows:
        assert str(campaign["empty_reason"]).strip()
        assert str(matrix["transplants_empty_reason"]).strip()
        assert counts["pending"] == 0
        assert counts["claimed"] == 0
        assert counts["total"] == 0
    for lot in campaign["lots"]:
        assert lot["responsibility_id"] not in PROTECTED_REJECTS
        assert lot["status"] in {"pending", "claimed", "complete"}
    assert DECIDE_PROMPT not in str(campaign["next_human_prompt"])
    assert TRANSPLANT_PROMPT in str(campaign["owner_prompt"])


def test_shipped_0959_ledger_points_at_matrix() -> None:
    path = synthesis_ledger_path(REPO)
    assert path == REPO / LEDGER_REL
    assert path.is_file()
    ledger = load_json(path)
    assert ledger["status"] == "complete"
    assert ledger["synthesis_ref"] == SYNTHESIS_REL.replace("\\", "/")
    assert DECIDE_PROMPT not in str(ledger["next_prompt"])
    raw = path.read_text(encoding="utf-8").casefold()
    assert "c:\\users\\" not in raw
    assert "d:\\perfil\\" not in raw


def test_0954_campaigns_stay_closed() -> None:
    queue = load_json_docs(REPO / "artifacts" / "goal095" / "queue" / "ledger.json")
    evidence = counts_for(queue)
    assert evidence["pending"] == 0
    assert evidence["claimed"] == 0
    assert evidence["complete"] == 132
    campaign = load_json_docs(evidence_campaign_path(REPO))
    assert campaign["counts"]["pending"] == 0
    assert campaign["counts"]["claimed"] == 0
    assert campaign["counts"]["complete"] == 132
    docs = load_json_docs(REPO / "artifacts" / "goal095" / "campaigns" / "docs.json")
    code = load_json_docs(REPO / "artifacts" / "goal095" / "campaigns" / "code_tests.json")
    assert docs["counts"]["pending"] == 0 and docs["counts"]["complete"] == 25
    assert code["counts"]["pending"] == 0 and code["counts"]["complete"] == 477


def test_validator_rejects_double_assignment_and_protected_lot() -> None:
    matrix = load_matrix(REPO)
    assignment = load_assignment(REPO)
    card_ids = index_audit_card_ids(REPO)
    synthesis_ids = index_synthesis_responsibility_ids(REPO)
    bad = dict(matrix)
    bad_rows = [dict(row) for row in matrix["responsibilities"]]
    bad_rows[0] = dict(bad_rows[0], decision="review")
    bad["responsibilities"] = bad_rows
    errors = validate_matrix(bad, card_ids, synthesis_ids, assignment, repo=REPO)
    assert any("decision" in item or "review" in item for item in errors)

    campaign = load_campaign(REPO)
    poisoned = dict(campaign)
    poisoned["lots"] = list(campaign["lots"]) + [
        {
            "lot_id": "transplant-functiongemma-270m-ft",
            "responsibility_id": "functiongemma-270m-ft",
            "decision": "adaptar",
            "status": "pending",
            "order": 0,
            "pieza_que_se_retira": "Qwen",
            "transplant_batch": 1000,
        }
    ]
    poisoned["counts"] = {
        "pending": len(poisoned["lots"]),
        "claimed": 0,
        "complete": 0,
        "total": len(poisoned["lots"]),
    }
    camp_errors = validate_campaign(poisoned, matrix)
    assert any("protected" in item or "functiongemma" in item for item in camp_errors)
