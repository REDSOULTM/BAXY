"""Goal 09.5.7 — load the shipped synthesis, not a fixture copy."""

from __future__ import annotations

from pathlib import Path

from scripts.goal095_0957_synthesis import (
    INVARIANT_FLAGS,
    LEDGER_REL,
    REJECTED_PATTERNS,
    REQUIRED_CAPABILITIES,
    RUNTIME_PROMPT,
    SCHEMA,
    SYNTHESIS_REL,
    TOOLS_PROMPT,
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


def test_shipped_0957_synthesis_is_the_repo_artifact() -> None:
    path = synthesis_path(REPO)
    assert path == REPO / SYNTHESIS_REL
    assert path.is_file()
    data = load_synthesis(REPO)
    assert data["schema"] == SCHEMA
    assert path.read_text(encoding="utf-8").startswith("{")


def test_shipped_0957_synthesis_satisfies_goal() -> None:
    data = load_synthesis(REPO)
    card_ids = index_ledger_card_ids(REPO)
    errors = validate_synthesis(data, card_ids, repo=REPO)
    assert errors == []
    present = {row["id"] for row in data["capabilities"]}
    assert set(REQUIRED_CAPABILITIES) <= present
    assert data["next_human_prompt"] == RUNTIME_PROMPT
    assert TOOLS_PROMPT not in data["next_human_prompt"]
    assert VOICE_PROMPT not in data["next_human_prompt"]
    assert data["live_catalog_changed"] is False
    assert data["live_providers_changed"] is False
    assert data["live_mission_engine_changed"] is False
    assert data["transplants"] == []
    assert str(data["transplants_empty_reason"]).strip()
    assert data["qwen_vl"]["silenced"] is False
    for name in INVARIANT_FLAGS:
        assert data["invariants"][name] is True
    patterns = {row["pattern"] for row in data["rejections"]}
    assert set(REJECTED_PATTERNS) <= patterns
    assert all(row.get("proposed") is not True for row in data["rejections"])
    kinds = {row["kind"] for row in data["missions"]}
    assert "simple" in kinds and "chained" in kinds
    assert any(row.get("complete") is True for row in data["missions"])
    for row in data["capabilities"]:
        assert str(row["current_operation"]).strip()
        assert str(row["owning_test"]).strip() or (
            isinstance(row.get("proven_gap"), dict) and row["proven_gap"].get("proven") is True
        )
        piece = row["best_piece"]
        assert str(piece["piece"]).strip()
        assert str(piece["evidence"]).strip()
        assert str(piece["coste"]).strip()
        assert str(piece["mecanismo_de_fracaso"]).strip()
        assert row["citations"]
        for flag in INVARIANT_FLAGS:
            assert row["invariants"][flag] is True
        for cite in row["citations"]:
            assert cite["card_id"] in card_ids
            assert "biblioteca/" not in str(cite.get("path") or "")


def test_shipped_0957_ledger_points_at_synthesis_and_09_5_8() -> None:
    path = synthesis_ledger_path(REPO)
    assert path == REPO / LEDGER_REL
    assert path.is_file()
    ledger = load_json(path)
    assert ledger["status"] == "complete"
    assert ledger["synthesis_ref"] == SYNTHESIS_REL.replace("\\", "/")
    assert ledger["next_prompt"] == RUNTIME_PROMPT
    assert TOOLS_PROMPT not in str(ledger["next_prompt"])
    raw = path.read_text(encoding="utf-8").casefold()
    assert "c:\\users\\" not in raw
    assert "d:\\perfil\\" not in raw


def test_0954_campaigns_stay_closed_and_evidence_next_is_09_5_8() -> None:
    queue = load_json_docs(REPO / "artifacts" / "goal095" / "queue" / "ledger.json")
    evidence = counts_for(queue)
    assert evidence["pending"] == 0
    assert evidence["claimed"] == 0
    assert evidence["complete"] == 132
    campaign = load_json_docs(evidence_campaign_path(REPO))
    assert campaign["counts"]["pending"] == 0
    assert campaign["counts"]["claimed"] == 0
    assert campaign["counts"]["complete"] == 132
    assert campaign["next_human_prompt"] == RUNTIME_PROMPT
    last = load_json_docs(
        REPO / "artifacts" / "goal095" / "ledger" / "evidence_assets-132-baxy_schema_agent.json"
    )
    assert last["next_prompt"] == RUNTIME_PROMPT
    assert "09.5.7_TOOLS_SKILLS_MISIONES.md" not in last["next_prompt"]
    assert "09.5.6_VOZ_AUDIO_PRESENCIA.md" not in last["next_prompt"]
    assert "09.5.5_MODELOS_ROUTER_IDIOMAS.md" not in last["next_prompt"]
    assert "09.5.4_AUDITAR_EVIDENCIA_LOTE.md" not in last["next_prompt"]
    docs = load_json_docs(REPO / "artifacts" / "goal095" / "campaigns" / "docs.json")
    code = load_json_docs(REPO / "artifacts" / "goal095" / "campaigns" / "code_tests.json")
    assert docs["counts"]["pending"] == 0 and docs["counts"]["complete"] == 25
    assert code["counts"]["pending"] == 0 and code["counts"]["complete"] == 477
