"""Goal 09.5.5 — load the shipped synthesis, not a fixture copy."""

from __future__ import annotations

from pathlib import Path

from scripts.goal095_0955_synthesis import (
    DECISIONS,
    IN_SCOPE_LANGS,
    LEDGER_REL,
    MODELS_PROMPT,
    REQUIRED_FAMILIES,
    SCHEMA,
    SYNTHESIS_REL,
    VOICE_PROMPT,
    index_ledger_card_ids,
    load_json,
    load_synthesis,
    synthesis_ledger_path,
    synthesis_path,
    validate_synthesis,
)
from scripts.goal095_docs_ledger import load_json as load_json_docs
from scripts.goal095_evidence_campaign import campaign_path as evidence_campaign_path
from scripts.goal095_evidence_campaign import counts_for

REPO = Path(__file__).resolve().parents[1]


def test_shipped_0955_synthesis_is_the_repo_artifact() -> None:
    path = synthesis_path(REPO)
    assert path == REPO / SYNTHESIS_REL
    assert path.is_file()
    data = load_synthesis(REPO)
    assert data["schema"] == SCHEMA
    assert path.read_text(encoding="utf-8").startswith("{")


def test_shipped_0955_synthesis_satisfies_goal() -> None:
    data = load_synthesis(REPO)
    card_ids = index_ledger_card_ids(REPO)
    errors = validate_synthesis(data, card_ids, repo=REPO)
    assert errors == []
    families = {row["family"] for row in data["candidates"]}
    assert set(REQUIRED_FAMILIES) <= families
    claimed = set(data["inventory_claimed_ids"])
    present = {row["id"] for row in data["candidates"]}
    assert claimed <= present
    assert data["languages_in_scope"] == list(IN_SCOPE_LANGS)
    assert data["other_languages_create_work"] is False
    assert data["other_language_work_items"] == []
    assert data["live_weights_changed"] is False
    assert data["next_human_prompt"] == VOICE_PROMPT
    assert MODELS_PROMPT not in data["next_human_prompt"]
    for piece in data["current_stack"]:
        assert piece["decision"] in DECISIONS
        assert piece["umbrales"].strip()
        assert piece["coste"].strip()


def test_shipped_0955_ledger_points_at_synthesis_and_09_5_6() -> None:
    path = synthesis_ledger_path(REPO)
    assert path == REPO / LEDGER_REL
    assert path.is_file()
    ledger = load_json(path)
    assert ledger["status"] == "complete"
    assert ledger["synthesis_ref"] == SYNTHESIS_REL.replace("\\", "/")
    assert ledger["next_prompt"] == VOICE_PROMPT
    assert MODELS_PROMPT not in str(ledger["next_prompt"])
    raw = path.read_text(encoding="utf-8").casefold()
    assert "c:\\users\\" not in raw
    assert "d:\\perfil\\" not in raw


def test_0954_campaigns_stay_closed_and_evidence_next_is_09_5_6() -> None:
    queue = load_json_docs(REPO / "artifacts" / "goal095" / "queue" / "ledger.json")
    evidence = counts_for(queue)
    assert evidence["pending"] == 0
    assert evidence["claimed"] == 0
    assert evidence["complete"] == 132
    campaign = load_json_docs(evidence_campaign_path(REPO))
    assert campaign["counts"]["pending"] == 0
    assert campaign["counts"]["claimed"] == 0
    assert campaign["counts"]["complete"] == 132
    assert campaign["next_human_prompt"] == VOICE_PROMPT
    last = load_json_docs(
        REPO / "artifacts" / "goal095" / "ledger" / "evidence_assets-132-baxy_schema_agent.json"
    )
    assert last["next_prompt"] == VOICE_PROMPT
    assert "09.5.5_MODELOS_ROUTER_IDIOMAS.md" not in last["next_prompt"]
    docs = load_json_docs(REPO / "artifacts" / "goal095" / "campaigns" / "docs.json")
    code = load_json_docs(REPO / "artifacts" / "goal095" / "campaigns" / "code_tests.json")
    assert docs["counts"]["pending"] == 0 and docs["counts"]["complete"] == 25
    assert code["counts"]["pending"] == 0 and code["counts"]["complete"] == 477
