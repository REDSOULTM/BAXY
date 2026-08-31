from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.goal095_code_ledger import (
    SCHEMA,
    TOKEN_LIMIT,
    claim,
    load_json,
    next_pending_code_tests,
    validate_ledger,
)

REPO = Path(__file__).resolve().parents[1]
QUEUE = REPO / "artifacts" / "goal095" / "queue"
BATCH_LEDGER = REPO / "artifacts" / "goal095" / "ledger" / "code_tests-001-carter.json"
BATCH_LEDGER_002 = (
    REPO
    / "artifacts"
    / "goal095"
    / "ledger"
    / "code_tests-002-carter-carter_legacy_Carter_v2.json"
)
CAMPAIGN = REPO / "artifacts" / "goal095" / "campaigns" / "code_tests.json"
BATCH_LEDGER_477 = (
    REPO
    / "artifacts"
    / "goal095"
    / "ledger"
    / "code_tests-477-baxy_schema_agent-baxy_schema_agent.json"
)


def _batch_stub(paths: list[str]) -> dict:
    return {
        "batch_id": "code_tests-001-carter",
        "estimated_tokens": 100,
        "token_limit": TOKEN_LIMIT,
        "files": [
            {
                "path": path,
                "sha256": f"h{index}",
                "source_id": "carter",
            }
            for index, path in enumerate(paths)
        ],
    }


def _card(path: str) -> dict:
    return {
        "card_id": "c1",
        "disposition": "evidence_only",
        "component": "comp",
        "contract": "in -> out",
        "dependencies": "none",
        "historical_test": "n=1",
        "limitations": "l",
        "current_owner": "src/baxy_mind",
        "source_files": [path],
        "failure_mechanism": "m",
        "readme_vs_real": "code exists",
        "invariant_risk": "none if not transplanted",
        "duplicate_layers": "none",
        "provisional": True,
        "provenance": {
            "path": path,
            "ranges": ["1-2"],
            "date": "2026-05-09",
            "hardware": "RTX 4060 Ti 16 GB",
            "model": "gemma-4-E4B",
            "commit": "9cf62d236cdef08012897d3c8c680b8afef0d62e",
        },
    }


def _ledger(paths: list[str], *, extra: dict | None = None) -> dict:
    path = paths[0]
    body = {
        "schema": SCHEMA,
        "batch_id": "code_tests-001-carter",
        "kind": "code_tests",
        "status": "complete",
        "claimed_utc": "2026-08-30T23:00:00Z",
        "closed_utc": "2026-08-30T23:30:00Z",
        "estimated_tokens": 100,
        "token_limit": TOKEN_LIMIT,
        "token_target": 300000,
        "source_id": "carter",
        "source_head": "9cf62d236cdef08012897d3c8c680b8afef0d62e",
        "source_root": "Programacion/Carter OS AI",
        "files": [
            {
                "item": item,
                "path": item,
                "sha256": f"h{index}",
                "source_id": "carter",
                "terminal": "leido",
                "ranges": ["1-10"],
            }
            for index, item in enumerate(paths)
        ],
        "cards": [_card(path)],
        "missing": 0,
        "overlaps": 0,
        "next_code_tests_batch_id": "code_tests-002-carter-carter_legacy_Carter_v2",
        "next_prompt": "campaign:code_tests",
    }
    for row in body["files"]:
        row.pop("item", None)
    if extra:
        body.update(extra)
    return body


def test_validate_rejects_file_outside_batch() -> None:
    batch = _batch_stub(["a.py"])
    ledger = _ledger(["a.py", "b.py"])
    errors = validate_ledger(ledger, batch)
    assert any("outside batch" in item or "extra" in item for item in errors)


def test_validate_rejects_uncovered_file() -> None:
    batch = _batch_stub(["a.py", "b.py"])
    ledger = _ledger(["a.py"])
    errors = validate_ledger(ledger, batch)
    assert any("uncovered" in item for item in errors)


def test_validate_rejects_reuse_without_provisional() -> None:
    batch = _batch_stub(["a.py"])
    ledger = _ledger(["a.py"])
    ledger["cards"][0]["provisional"] = False
    errors = validate_ledger(ledger, batch)
    assert any("provisional" in item for item in errors)


def test_validate_accepts_complete_mini_batch() -> None:
    batch = _batch_stub(["a.py"])
    errors = validate_ledger(_ledger(["a.py"]), batch)
    assert errors == []


def test_claim_refuses_non_first_pending(tmp_path: Path) -> None:
    queue = tmp_path / "artifacts" / "goal095" / "queue"
    queue.mkdir(parents=True)
    (queue / "batches.json").write_text(
        json.dumps(
            [
                {
                    "batch_id": "code_tests-001-carter",
                    "estimated_tokens": 10,
                    "file_count": 0,
                    "files": [],
                    "kind": "code_tests",
                    "output": "x",
                    "source_id": "carter",
                    "token_limit": TOKEN_LIMIT,
                    "token_target": 300000,
                }
            ]
        ),
        encoding="utf-8",
    )
    (queue / "ledger.json").write_text(
        json.dumps(
            {
                "batches": [
                    {
                        "batch_id": "docs-002-carter",
                        "kind": "docs",
                        "status": "pending",
                    },
                    {
                        "batch_id": "code_tests-001-carter",
                        "kind": "code_tests",
                        "status": "pending",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (queue / "summary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="first pending code_tests"):
        claim(tmp_path, batch_id="code_tests-002-carter-carter_legacy_Carter_v2")
    record = claim(tmp_path, batch_id="code_tests-001-carter")
    assert record["batch_id"] == "code_tests-001-carter"
    assert record["kind"] == "code_tests"


def test_next_pending_code_tests_skips_docs_and_current() -> None:
    queue_ledger = {
        "batches": [
            {"batch_id": "docs-002-carter", "kind": "docs", "status": "pending"},
            {
                "batch_id": "code_tests-001-carter",
                "kind": "code_tests",
                "status": "complete",
            },
            {
                "batch_id": "code_tests-002-carter-carter_legacy_Carter_v2",
                "kind": "code_tests",
                "status": "pending",
            },
        ]
    }
    nxt = next_pending_code_tests(queue_ledger, "code_tests-001-carter")
    assert nxt is not None
    assert nxt["batch_id"] == "code_tests-002-carter-carter_legacy_Carter_v2"


@pytest.mark.skipif(not BATCH_LEDGER.is_file(), reason="code_tests-001 ledger not written")
def test_published_code001_ledger_matches_schema() -> None:
    batches = load_json(QUEUE / "batches.json")
    batch = next(
        item for item in batches if item["batch_id"] == "code_tests-001-carter"
    )
    ledger = load_json(BATCH_LEDGER)
    errors = validate_ledger(ledger, batch)
    assert errors == []
    assert ledger["batch_id"] == "code_tests-001-carter"
    assert ledger["estimated_tokens"] <= TOKEN_LIMIT
    assert ledger["kind"] == "code_tests"
    raw = BATCH_LEDGER.read_text(encoding="utf-8").casefold()
    assert "c:\\users\\" not in raw
    assert "d:\\perfil\\" not in raw
    queue_ledger = load_json(QUEUE / "ledger.json")
    row = next(
        item
        for item in queue_ledger["batches"]
        if item["batch_id"] == "code_tests-001-carter"
    )
    assert row["status"] == "complete"
    assert ledger["next_prompt"] != "documentacion/sprints/09.5.3_AUDITAR_CODIGO_LOTE.md"
    claimed_same = [
        item["batch_id"]
        for item in queue_ledger["batches"]
        if item.get("status") == "claimed" and item.get("kind") == "code_tests"
    ]
    assert "code_tests-001-carter" not in claimed_same
    from scripts.build_goal095_queues import load_jsonl, partition_ok

    partition = partition_ok(load_jsonl(QUEUE / "unified_manifest.jsonl"))
    assert partition["missing"] == 0
    assert partition["overlaps"] == 0
    dispositions = {card["disposition"] for card in ledger["cards"]}
    assert dispositions <= {
        "reuse_exact",
        "adapt_candidate",
        "evidence_only",
        "reject_candidate",
    }
    assert all(card["provisional"] is True for card in ledger["cards"])


def test_claim_resumes_live_claimed_batch(tmp_path: Path) -> None:
    queue = tmp_path / "artifacts" / "goal095" / "queue"
    queue.mkdir(parents=True)
    (queue / "batches.json").write_text(
        json.dumps(
            [
                {
                    "batch_id": "code_tests-002-carter-carter_legacy_Carter_v2",
                    "estimated_tokens": 10,
                    "file_count": 0,
                    "files": [],
                    "kind": "code_tests",
                    "output": "x",
                    "source_id": "carter",
                    "token_limit": TOKEN_LIMIT,
                    "token_target": 300000,
                }
            ]
        ),
        encoding="utf-8",
    )
    (queue / "ledger.json").write_text(
        json.dumps(
            {
                "batches": [
                    {
                        "batch_id": "code_tests-002-carter-carter_legacy_Carter_v2",
                        "kind": "code_tests",
                        "status": "claimed",
                        "claimed_utc": "2026-08-31T01:50:11Z",
                    },
                    {
                        "batch_id": "code_tests-003-carter-carter_legacy_Carter_v2",
                        "kind": "code_tests",
                        "status": "pending",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (queue / "summary.json").write_text("{}", encoding="utf-8")
    claims = tmp_path / "artifacts" / "goal095" / "claims"
    claims.mkdir(parents=True)
    existing = {
        "schema": SCHEMA,
        "batch_id": "code_tests-002-carter-carter_legacy_Carter_v2",
        "kind": "code_tests",
        "status": "claimed",
        "claimed_utc": "2026-08-31T01:50:11Z",
    }
    (claims / "code_tests-002-carter-carter_legacy_Carter_v2.json").write_text(
        json.dumps(existing),
        encoding="utf-8",
    )
    record = claim(tmp_path)
    assert record["batch_id"] == "code_tests-002-carter-carter_legacy_Carter_v2"
    assert record["claimed_utc"] == "2026-08-31T01:50:11Z"
    queue_ledger = load_json(queue / "ledger.json")
    assert queue_ledger["batches"][1]["status"] == "pending"


@pytest.mark.skipif(not BATCH_LEDGER_002.is_file(), reason="code_tests-002 ledger not written")
def test_published_code002_ledger_matches_schema() -> None:
    batches = load_json(QUEUE / "batches.json")
    batch = next(
        item
        for item in batches
        if item["batch_id"] == "code_tests-002-carter-carter_legacy_Carter_v2"
    )
    ledger = load_json(BATCH_LEDGER_002)
    errors = validate_ledger(ledger, batch)
    assert errors == []
    assert ledger["next_prompt"] == "campaign:code_tests"
    raw = BATCH_LEDGER_002.read_text(encoding="utf-8").casefold()
    assert "c:\\users\\" not in raw
    assert "d:\\perfil\\" not in raw
    assert "emmanuel" not in raw
    assert all(card["provisional"] is True for card in ledger["cards"])
    campaign = load_json(CAMPAIGN)
    assert campaign["required_human_launches"] == 1
    assert campaign["counts"]["complete"] >= 2
    assert "code_tests-001-carter" in campaign["preserved_complete"]
    assert "code_tests-002-carter-carter_legacy_Carter_v2" in campaign[
        "preserved_complete"
    ]
    if campaign["counts"]["pending"] == 0:
        assert campaign["next_human_prompt"] in {
            "documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md",
            "documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md",
        }
    else:
        assert campaign["next_human_prompt"] is None


@pytest.mark.skipif(not BATCH_LEDGER_477.is_file(), reason="code_tests-477 ledger not written")
def test_published_code477_and_campaign_terminal() -> None:
    batches = load_json(QUEUE / "batches.json")
    batch = next(
        item
        for item in batches
        if item["batch_id"]
        == "code_tests-477-baxy_schema_agent-baxy_schema_agent"
    )
    ledger = load_json(BATCH_LEDGER_477)
    assert validate_ledger(ledger, batch) == []
    assert ledger["next_prompt"] == (
        "documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md"
    )
    assert "09.5.3_AUDITAR_CODIGO_LOTE.md" not in ledger["next_prompt"]
    campaign = load_json(CAMPAIGN)
    assert campaign["counts"]["pending"] == 0
    assert campaign["counts"]["claimed"] == 0
    assert campaign["counts"]["complete"] == 477
    queue_ledger = load_json(QUEUE / "ledger.json")
    claimed = [
        item["batch_id"]
        for item in queue_ledger["batches"]
        if item.get("kind") == "code_tests" and item.get("status") == "claimed"
    ]
    assert claimed == []
    claims_dir = REPO / "artifacts" / "goal095" / "claims"
    orphan_claims = [
        path.name
        for path in claims_dir.glob("code_tests-*.json")
        if load_json(path).get("status") == "claimed"
    ]
    assert orphan_claims == []

