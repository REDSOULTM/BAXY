"""Goal 09.5.8 — load the shipped synthesis, not a fixture copy."""

from __future__ import annotations

from pathlib import Path

from scripts.goal095_0958_synthesis import (
    DECISIONS,
    DECIDE_PROMPT,
    INVARIANT_FLAGS,
    LEDGER_REL,
    REQUIRED_AREAS,
    RESOURCE_AREAS,
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


def test_shipped_0958_synthesis_is_the_repo_artifact() -> None:
    path = synthesis_path(REPO)
    assert path == REPO / SYNTHESIS_REL
    assert path.is_file()
    data = load_synthesis(REPO)
    assert data["schema"] == SCHEMA
    assert path.read_text(encoding="utf-8").startswith("{")


def test_shipped_0958_synthesis_satisfies_goal() -> None:
    data = load_synthesis(REPO)
    card_ids = index_ledger_card_ids(REPO)
    errors = validate_synthesis(data, card_ids, repo=REPO)
    assert errors == []
    present = {row["id"] for row in data["areas"]}
    assert set(REQUIRED_AREAS) <= present
    assert data["next_human_prompt"] == DECIDE_PROMPT
    assert RUNTIME_PROMPT not in data["next_human_prompt"]
    assert TOOLS_PROMPT not in data["next_human_prompt"]
    assert VOICE_PROMPT not in data["next_human_prompt"]
    assert data["live_runtime_changed"] is False
    assert data["live_fieldui_dist_changed"] is False
    assert data["live_setup_changed"] is False
    assert data["goal09_reopened"] is False
    assert data["soak_24h_requirement"] is False
    assert data["transplants"] == []
    assert str(data["transplants_empty_reason"]).strip()
    assert data["qwen_vl"]["silenced"] is False
    for name in INVARIANT_FLAGS:
        assert data["invariants"][name] is True
    for row in data["areas"]:
        assert row["decision"] in DECISIONS
        assert str(row["historical"]).strip()
        assert str(row["live_owner"]).strip()
        assert str(row["goal10_consumer"]).strip()
        assert str(row["source"]).strip()
        assert str(row["owner"]).strip()
        assert str(row["owning_test"]).strip()
        assert str(row["mecanismo_reemplazado"]).strip()
        assert row["second_live_path"] is not True
        assert row["citations"]
        for flag in INVARIANT_FLAGS:
            assert row["invariants"][flag] is True
        for cite in row["citations"]:
            assert cite["card_id"] in card_ids
            assert "biblioteca/" not in str(cite.get("path") or "")
        measurement = row["measurement"]
        if row["id"] in RESOURCE_AREAS or measurement.get("comparable") is True:
            for field in ("hardware", "version", "escenario", "denominador"):
                assert str(measurement[field]).strip()
            assert str(measurement["own_overhead"]).strip()
            assert str(measurement["inference"]).strip()
        if measurement.get("comparable") is False:
            assert str(measurement.get("incomparable_reason") or "").strip()
            assert row["decision"] != "reusar"


def test_shipped_0958_ledger_points_at_synthesis_and_09_5_9() -> None:
    path = synthesis_ledger_path(REPO)
    assert path == REPO / LEDGER_REL
    assert path.is_file()
    ledger = load_json(path)
    assert ledger["status"] == "complete"
    assert ledger["synthesis_ref"] == SYNTHESIS_REL.replace("\\", "/")
    assert ledger["next_prompt"] == DECIDE_PROMPT
    assert RUNTIME_PROMPT not in str(ledger["next_prompt"])
    raw = path.read_text(encoding="utf-8").casefold()
    assert "c:\\users\\" not in raw
    assert "d:\\perfil\\" not in raw


def test_0954_campaigns_stay_closed_and_evidence_next_is_09_5_9() -> None:
    queue = load_json_docs(REPO / "artifacts" / "goal095" / "queue" / "ledger.json")
    evidence = counts_for(queue)
    assert evidence["pending"] == 0
    assert evidence["claimed"] == 0
    assert evidence["complete"] == 132
    campaign = load_json_docs(evidence_campaign_path(REPO))
    assert campaign["counts"]["pending"] == 0
    assert campaign["counts"]["claimed"] == 0
    assert campaign["counts"]["complete"] == 132
    assert campaign["next_human_prompt"] == DECIDE_PROMPT
    last = load_json_docs(
        REPO / "artifacts" / "goal095" / "ledger" / "evidence_assets-132-baxy_schema_agent.json"
    )
    assert last["next_prompt"] == DECIDE_PROMPT
    assert "09.5.8_RUNTIME_UI_RECURSOS.md" not in last["next_prompt"]
    assert "09.5.7_TOOLS_SKILLS_MISIONES.md" not in last["next_prompt"]
    assert "09.5.6_VOZ_AUDIO_PRESENCIA.md" not in last["next_prompt"]
    assert "09.5.5_MODELOS_ROUTER_IDIOMAS.md" not in last["next_prompt"]
    assert "09.5.4_AUDITAR_EVIDENCIA_LOTE.md" not in last["next_prompt"]
    docs = load_json_docs(REPO / "artifacts" / "goal095" / "campaigns" / "docs.json")
    code = load_json_docs(REPO / "artifacts" / "goal095" / "campaigns" / "code_tests.json")
    assert docs["counts"]["pending"] == 0 and docs["counts"]["complete"] == 25
    assert code["counts"]["pending"] == 0 and code["counts"]["complete"] == 477
