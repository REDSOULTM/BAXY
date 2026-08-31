from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.goal095_docs_ledger import (
    SCHEMA,
    TOKEN_LIMIT,
    claim,
    load_json,
    next_pending_docs,
    validate_ledger,
)

REPO = Path(__file__).resolve().parents[1]
QUEUE = REPO / "artifacts" / "goal095" / "queue"
BATCH_LEDGER = REPO / "artifacts" / "goal095" / "ledger" / "docs-001-carter.json"


def _batch_stub(paths: list[str]) -> dict:
    return {
        "batch_id": "docs-001-carter",
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
        "claim_kind": "documental",
        "problem": "p",
        "outcome": "fracaso",
        "solution_or_failure": "s",
        "causal_mechanism": "m",
        "measurement": "n=1",
        "provenance": {
            "path": path,
            "ranges": ["1-2"],
            "date": "2026-05-02",
            "hardware": "RTX 4060 Ti 16 GB",
            "model": "qwen3:8b",
            "commit": "9cf62d236cdef08012897d3c8c680b8afef0d62e",
        },
        "limitations": "l",
        "validity": "historica",
        "current_piece": "src/baxy_mind",
        "source_files": [path],
        "repeats": [],
    }


def _ledger(paths: list[str], *, extra: dict | None = None) -> dict:
    path = paths[0]
    body = {
        "schema": SCHEMA,
        "batch_id": "docs-001-carter",
        "kind": "docs",
        "status": "complete",
        "claimed_utc": "2026-08-30T20:05:00Z",
        "closed_utc": "2026-08-30T21:00:00Z",
        "estimated_tokens": 100,
        "token_limit": TOKEN_LIMIT,
        "token_target": 300000,
        "source_id": "carter",
        "source_head": "9cf62d236cdef08012897d3c8c680b8afef0d62e",
        "source_root": "Programacion/Carter OS AI",
        "files": [
            {
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
        "next_docs_batch_id": "docs-002-carter",
        "next_prompt": "campaign:docs",
    }
    if extra:
        body.update(extra)
    return body


def test_validate_rejects_file_outside_batch() -> None:
    batch = _batch_stub(["a.md"])
    ledger = _ledger(["a.md", "b.md"])
    errors = validate_ledger(ledger, batch)
    assert any("outside batch" in item or "extra" in item for item in errors)


def test_validate_rejects_uncovered_file() -> None:
    batch = _batch_stub(["a.md", "b.md"])
    ledger = _ledger(["a.md"])
    errors = validate_ledger(ledger, batch)
    assert any("uncovered" in item for item in errors)


def test_validate_accepts_complete_mini_batch() -> None:
    batch = _batch_stub(["a.md"])
    errors = validate_ledger(_ledger(["a.md"]), batch)
    assert errors == []


def test_claim_refuses_non_first_pending(tmp_path: Path) -> None:
    queue = tmp_path / "artifacts" / "goal095" / "queue"
    queue.mkdir(parents=True)
    (queue / "batches.json").write_text(
        json.dumps(
            [
                {
                    "batch_id": "docs-001-carter",
                    "estimated_tokens": 10,
                    "file_count": 0,
                    "files": [],
                    "kind": "docs",
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
                        "batch_id": "docs-001-carter",
                        "kind": "docs",
                        "status": "pending",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (queue / "summary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError):
        claim(tmp_path, batch_id="docs-002-carter")


def test_next_pending_docs_skips_current() -> None:
    queue_ledger = {
        "batches": [
            {"batch_id": "docs-001-carter", "kind": "docs", "status": "complete"},
            {"batch_id": "docs-002-carter", "kind": "docs", "status": "pending"},
        ]
    }
    nxt = next_pending_docs(queue_ledger, "docs-001-carter")
    assert nxt is not None
    assert nxt["batch_id"] == "docs-002-carter"


@pytest.mark.skipif(not BATCH_LEDGER.is_file(), reason="docs-001 ledger not written")
def test_published_docs001_ledger_matches_schema() -> None:
    batches = load_json(QUEUE / "batches.json")
    batch = next(item for item in batches if item["batch_id"] == "docs-001-carter")
    ledger = load_json(BATCH_LEDGER)
    errors = validate_ledger(ledger, batch)
    assert errors == []
    assert ledger["batch_id"] == "docs-001-carter"
    assert ledger["estimated_tokens"] <= TOKEN_LIMIT
    assert ledger["next_prompt"] == "campaign:docs"
    assert "09.5.2_LEER_DOCUMENTACION_LOTE.md" not in str(ledger["next_prompt"])
    raw = BATCH_LEDGER.read_text(encoding="utf-8").casefold()
    assert "c:\\users\\" not in raw
    assert "d:\\perfil\\" not in raw
    queue_ledger = load_json(QUEUE / "ledger.json")
    row = next(
        item
        for item in queue_ledger["batches"]
        if item["batch_id"] == "docs-001-carter"
    )
    assert row["status"] == "complete"
    claimed = [
        item["batch_id"]
        for item in queue_ledger["batches"]
        if item.get("kind") == "docs" and item.get("status") == "claimed"
    ]
    assert claimed == []
    summary = load_json(QUEUE / "summary.json")
    assert summary["missing"] == 0
    assert summary["overlaps"] == 0
    from scripts.build_goal095_queues import load_jsonl, partition_ok

    partition = partition_ok(load_jsonl(QUEUE / "unified_manifest.jsonl"))
    assert partition["missing"] == 0
    assert partition["overlaps"] == 0
    campaign_path = REPO / "artifacts" / "goal095" / "campaigns" / "docs.json"
    assert campaign_path.is_file()
    campaign = load_json(campaign_path)
    assert campaign["campaign_id"] == "docs"
    assert campaign["required_human_launches"] == 1
    assert "docs-001-carter" in campaign["preserved_complete"]
    if campaign["counts"]["pending"] == 0:
        assert campaign["counts"]["complete"] == 25
        assert campaign["counts"]["claimed"] == 0
        assert campaign["next_human_prompt"] == (
            "documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md"
        )
        last = load_json(REPO / "artifacts" / "goal095" / "ledger" / "docs-025-baxy.json")
        assert last["next_prompt"] == (
            "documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md"
        )
        assert "09.5.2_LEER_DOCUMENTACION_LOTE.md" not in last["next_prompt"]
    else:
        assert campaign["next_human_prompt"] is None
