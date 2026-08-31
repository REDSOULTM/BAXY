"""Goal 09.5.10 — load the shipped transplant campaign, not a fixture copy."""

from __future__ import annotations

from pathlib import Path

from scripts.goal095_0959_matrix import (
    CAMPAIGN_REL,
    DECIDE_PROMPT,
    HANDOFF_REL,
    LEDGER_09510_REL,
    MARKDOWN_09510_REL,
    PROTECTED_REJECTS,
    REVALIDATE_PROMPT,
    TRANSPLANT_PROMPT,
    TRANSPLANT_TERMINALS,
    apply_transplant_closeout,
    campaign_counts,
    campaign_path,
    closeout_next_human_prompt,
    index_audit_card_ids,
    index_orphan_transplant_claims,
    index_synthesis_responsibility_ids,
    load_assignment,
    load_campaign,
    load_json,
    load_matrix,
    load_transplant_ledger,
    lots_from_matrix,
    transplant_ledger_path,
    validate_campaign,
    validate_matrix,
    validate_transplant_closeout,
)
from scripts.goal095_docs_ledger import load_json as load_json_docs
from scripts.goal095_evidence_campaign import campaign_path as evidence_campaign_path
from scripts.goal095_evidence_campaign import counts_for

REPO = Path(__file__).resolve().parents[1]


def test_shipped_09510_campaign_is_the_repo_artifact() -> None:
    path = campaign_path(REPO)
    assert path == REPO / CAMPAIGN_REL
    assert path.is_file()
    assert path.read_text(encoding="utf-8").startswith("{")
    ledger = transplant_ledger_path(REPO)
    assert ledger == REPO / LEDGER_09510_REL
    assert ledger.is_file()
    assert (REPO / MARKDOWN_09510_REL).is_file()
    assert (REPO / HANDOFF_REL).is_file()


def test_shipped_09510_campaign_matches_matrix_and_is_drained() -> None:
    matrix = load_matrix(REPO)
    campaign = load_campaign(REPO)
    assignment = load_assignment(REPO)
    card_ids = index_audit_card_ids(REPO)
    synthesis_ids = index_synthesis_responsibility_ids(REPO)
    assert validate_matrix(matrix, card_ids, synthesis_ids, assignment, repo=REPO) == []
    errors = validate_campaign(campaign, matrix, repo=REPO)
    assert errors == []
    expected = lots_from_matrix(matrix)
    assert [lot["responsibility_id"] for lot in campaign["lots"]] == [
        lot["responsibility_id"] for lot in expected
    ]
    transplant_rows = [
        row["id"]
        for row in matrix["responsibilities"]
        if row["decision"] in TRANSPLANT_TERMINALS
    ]
    assert [lot["responsibility_id"] for lot in campaign["lots"]] == transplant_rows
    counts = campaign_counts(campaign)
    assert campaign["counts"]["pending"] == 0
    assert campaign["counts"]["claimed"] == 0
    assert counts["pending"] == 0
    assert counts["claimed"] == 0
    assert campaign["counts"]["total"] == len(campaign["lots"])
    assert campaign["required_human_launches"] == 1
    assert campaign["owner_prompt"] == TRANSPLANT_PROMPT
    assert campaign["next_human_prompt"] == REVALIDATE_PROMPT
    assert TRANSPLANT_PROMPT not in str(campaign["next_human_prompt"])
    assert DECIDE_PROMPT not in str(campaign["next_human_prompt"])
    for name in PROTECTED_REJECTS:
        assert name not in [lot["responsibility_id"] for lot in campaign["lots"]]
        assert name not in transplant_rows
    if not campaign["lots"]:
        assert str(campaign["empty_reason"]).strip()
        assert str(matrix["transplants_empty_reason"]).strip()
        assert counts["total"] == 0
    for lot in campaign["lots"]:
        assert lot["status"] == "complete"
        assert str(lot.get("terminal") or "").strip()
        assert lot["responsibility_id"] not in PROTECTED_REJECTS
    assert index_orphan_transplant_claims(REPO) == []


def test_shipped_09510_closeout_names_11a_not_10() -> None:
    campaign = load_campaign(REPO)
    matrix = load_matrix(REPO)
    errors = validate_transplant_closeout(campaign, matrix, repo=REPO)
    assert errors == []
    ledger = load_transplant_ledger(REPO)
    assert ledger["status"] == "complete"
    assert ledger["goal"] == "09.5.10"
    assert ledger["required_human_launches"] == 1
    assert ledger["owner_prompt"] == TRANSPLANT_PROMPT
    assert ledger["next_prompt"] == REVALIDATE_PROMPT
    assert TRANSPLANT_PROMPT not in str(ledger["next_prompt"])
    assert matrix["next_human_prompt"] == REVALIDATE_PROMPT
    assert TRANSPLANT_PROMPT not in str(matrix["next_human_prompt"])
    handoff = (REPO / HANDOFF_REL).read_text(encoding="utf-8")
    assert (REPO / HANDOFF_REL).is_file()
    siguiente = handoff.split("## Siguiente accion recomendada", 1)[1]
    assert "09.5.10_TRASPLANTAR_LOTE.md" not in siguiente.replace("\\", "/")
    raw = transplant_ledger_path(REPO).read_text(encoding="utf-8").casefold()
    assert "c:\\users\\" not in raw
    assert "d:\\perfil\\" not in raw


def test_0952_0954_campaigns_stay_closed() -> None:
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
    assert docs["counts"]["pending"] == 0 and docs["counts"]["claimed"] == 0
    assert docs["counts"]["complete"] == 25
    assert code["counts"]["pending"] == 0 and code["counts"]["claimed"] == 0
    assert code["counts"]["complete"] == 477


def test_sparse_hashes_stay_not_invented() -> None:
    req = load_json(REPO / "artifacts" / "goal095" / "extract" / "_09510_requirements.json")
    for item in req.get("requirements") or []:
        hashes = str(item.get("individual_hashes") or "").strip()
        assert hashes in {"not invented", ""}
    matrix = load_matrix(REPO)
    blob = str(matrix.get("sparse_assets") or {}).casefold()
    assert "not invented" in blob
    env = REPO / "artifacts" / "goal095" / "environment" / "09.5.10.md"
    assert not env.is_file()


def test_closeout_pointer_is_shared_by_empty_queue_and_last_lot() -> None:
    empty = {
        "schema": "baxy.goal095.campaign.v1",
        "campaign_id": "transplant",
        "kind": "transplant",
        "required_human_launches": 1,
        "owner_prompt": TRANSPLANT_PROMPT,
        "lots": [],
        "counts": {"pending": 0, "claimed": 0, "complete": 0, "total": 0},
        "empty_reason": "synthetic empty queue",
        "next_human_prompt": TRANSPLANT_PROMPT,
        "cursor_status": "complete",
        "cursor_batch_id": None,
    }
    closed_empty = apply_transplant_closeout(empty, updated_utc="2026-08-31T12:00:00Z")
    assert closed_empty["next_human_prompt"] == REVALIDATE_PROMPT
    assert closeout_next_human_prompt(closed_empty) == REVALIDATE_PROMPT
    assert TRANSPLANT_PROMPT not in closed_empty["next_human_prompt"]
    assert closed_empty["owner_prompt"] == TRANSPLANT_PROMPT
    assert closed_empty["required_human_launches"] == 1

    live = {
        **empty,
        "empty_reason": "",
        "cursor_status": "pending",
        "lots": [
            {
                "lot_id": "transplant-example",
                "responsibility_id": "example",
                "decision": "adaptar",
                "status": "pending",
                "order": 0,
                "pieza_que_se_retira": "old-path",
                "transplant_batch": 1000,
                "terminal": "",
            }
        ],
        "counts": {"pending": 1, "claimed": 0, "complete": 0, "total": 1},
        "next_human_prompt": TRANSPLANT_PROMPT,
    }
    still_open = apply_transplant_closeout(live, updated_utc="2026-08-31T12:00:01Z")
    assert still_open["next_human_prompt"] == TRANSPLANT_PROMPT
    assert still_open["counts"]["pending"] == 1

    last = dict(still_open)
    last["lots"] = [
        dict(still_open["lots"][0], status="complete", terminal="adapted-min-seam")
    ]
    last["counts"] = {"pending": 0, "claimed": 0, "complete": 1, "total": 1}
    closed_last = apply_transplant_closeout(last, updated_utc="2026-08-31T12:00:02Z")
    assert closed_last["next_human_prompt"] == REVALIDATE_PROMPT
    assert closed_last["next_human_prompt"] == closed_empty["next_human_prompt"]
    assert closed_last["cursor_status"] == "complete"


def test_validator_rejects_self_remit_and_protected_lot() -> None:
    matrix = load_matrix(REPO)
    campaign = load_campaign(REPO)
    remitting = dict(campaign)
    remitting["next_human_prompt"] = TRANSPLANT_PROMPT
    errors = validate_campaign(remitting, matrix)
    assert any("09.5.10" in item or "expected" in item for item in errors)

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
            "terminal": "",
        }
    ]
    poisoned["counts"] = {
        "pending": 1,
        "claimed": 0,
        "complete": 0,
        "total": len(poisoned["lots"]),
    }
    poisoned["next_human_prompt"] = TRANSPLANT_PROMPT
    camp_errors = validate_campaign(poisoned, matrix)
    assert any("protected" in item or "functiongemma" in item for item in camp_errors)
