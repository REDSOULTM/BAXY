from __future__ import annotations

import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.goal095_docs_ledger import TOKEN_LIMIT, load_json
from scripts.goal095_evidence_ledger import (
    SCHEMA,
    claim,
    expire_stale_claims,
    next_pending_evidence,
    validate_ledger,
)
from scripts.goal095_evidence_parse import inventory_binary, parse_jsonl, process_file

REPO = Path(__file__).resolve().parents[1]
QUEUE = REPO / "artifacts" / "goal095" / "queue"
OWNER = "documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md"


def _batch_stub(paths: list[str]) -> dict:
    return {
        "batch_id": "evidence_assets-001-carter",
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
        "card_kind": "run",
        "corpus": "fixture",
        "denominator": "n=1 file",
        "version": "test",
        "hardware": "pytest",
        "limitations": "fixture",
        "identity": "fixture:run",
        "consumers": "tests",
        "associated_benchmark": "none recovered in this campaign",
        "source_files": [path],
        "provisional": True,
        "ranking_claim": False,
        "equivalent_comparison": "",
        "measurement": "rows=3 bytes=120",
        "outcome": "contexto",
        "works": False,
        "current_owner": "tests/",
        "provenance": {
            "path": path,
            "ranges": ["jsonl:schema+counts+samples"],
            "date": "2026-08-31",
            "hardware": "pytest",
            "model": "n/a",
            "commit": "test",
        },
    }


def _file_row(path: str, index: int, *, terminal: str = "parseado_completo") -> dict:
    row = {
        "path": path,
        "sha256": f"h{index}",
        "source_id": "carter",
        "terminal": terminal,
        "ranges": ["jsonl:schema+counts+samples"],
        "extract_ref": f"artifacts/goal095/extract/fake.parse.json#{path}",
    }
    if terminal == "binario_inventariado":
        row["binary_format"] = "wav"
        row["ranges"] = ["blob-meta"]
    if terminal == "duplicado_por_hash":
        row["duplicate_of"] = "other:file"
        row.pop("extract_ref", None)
    if terminal == "excluido_razonado":
        row["exclusion_rule"] = "rust_build_artifact"
        row.pop("extract_ref", None)
    return row


def _ledger(paths: list[str], *, extra: dict | None = None) -> dict:
    path = paths[0]
    body = {
        "schema": SCHEMA,
        "batch_id": "evidence_assets-001-carter",
        "kind": "evidence_assets",
        "status": "complete",
        "claimed_utc": "2026-08-31T12:00:00Z",
        "closed_utc": "2026-08-31T12:30:00Z",
        "estimated_tokens": 100,
        "token_limit": TOKEN_LIMIT,
        "token_target": 300000,
        "source_id": "carter",
        "source_head": "9cf62d236cdef08012897d3c8c680b8afef0d62e",
        "source_root": "Programacion/Carter OS AI",
        "files": [_file_row(item, index) for index, item in enumerate(paths)],
        "cards": [_card(path)],
        "missing": 0,
        "overlaps": 0,
        "next_evidence_assets_batch_id": "evidence_assets-002-carter",
        "next_prompt": "campaign:evidence_assets",
    }
    if extra:
        body.update(extra)
    return body


def _write_mini_queue(
    tmp_path: Path,
    *,
    status: str = "pending",
    claimed_utc: str | None = None,
    lease_expires_utc: str | None = None,
) -> None:
    queue = tmp_path / "artifacts" / "goal095" / "queue"
    queue.mkdir(parents=True)
    (queue / "batches.json").write_text(
        json.dumps(
            [
                {
                    "batch_id": "evidence_assets-001-carter",
                    "estimated_tokens": 10,
                    "file_count": 0,
                    "files": [],
                    "kind": "evidence_assets",
                    "output": "x",
                    "source_id": "carter",
                    "token_limit": TOKEN_LIMIT,
                    "token_target": 300000,
                }
            ]
        ),
        encoding="utf-8",
    )
    item = {
        "batch_id": "evidence_assets-001-carter",
        "kind": "evidence_assets",
        "status": status,
    }
    if claimed_utc:
        item["claimed_utc"] = claimed_utc
        item["lease_expires_utc"] = lease_expires_utc or claimed_utc
    (queue / "ledger.json").write_text(
        json.dumps(
            {
                "batches": [
                    item,
                    {
                        "batch_id": "evidence_assets-002-carter",
                        "kind": "evidence_assets",
                        "status": "pending",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (queue / "summary.json").write_text("{}", encoding="utf-8")


def test_claim_first_pending_evidence_unit(tmp_path: Path) -> None:
    _write_mini_queue(tmp_path)
    record = claim(tmp_path, batch_id="evidence_assets-001-carter")
    assert record["batch_id"] == "evidence_assets-001-carter"
    assert record["kind"] == "evidence_assets"
    assert record["status"] == "claimed"
    assert record["claimed_utc"]
    queue = load_json(tmp_path / "artifacts" / "goal095" / "queue" / "ledger.json")
    row = queue["batches"][0]
    assert row["status"] == "claimed"
    campaign = load_json(
        tmp_path / "artifacts" / "goal095" / "campaigns" / "evidence_assets.json"
    )
    assert campaign["required_human_launches"] == 1
    assert campaign["counts"]["claimed"] == 1


def test_claim_resumes_live_claimed_batch_without_resetting_utc(tmp_path: Path) -> None:
    _write_mini_queue(
        tmp_path,
        status="claimed",
        claimed_utc="2026-08-31T01:50:11Z",
        lease_expires_utc="2026-08-31T07:50:11Z",
    )
    claims = tmp_path / "artifacts" / "goal095" / "claims"
    claims.mkdir(parents=True)
    existing = {
        "schema": SCHEMA,
        "batch_id": "evidence_assets-001-carter",
        "kind": "evidence_assets",
        "status": "claimed",
        "claimed_utc": "2026-08-31T01:50:11Z",
        "lease_expires_utc": "2026-08-31T07:50:11Z",
    }
    (claims / "evidence_assets-001-carter.json").write_text(
        json.dumps(existing), encoding="utf-8"
    )
    record = claim(
        tmp_path,
        now=datetime(2026, 8, 31, 3, 0, tzinfo=timezone.utc),
    )
    assert record["batch_id"] == "evidence_assets-001-carter"
    assert record["claimed_utc"] == "2026-08-31T01:50:11Z"
    queue = load_json(tmp_path / "artifacts" / "goal095" / "queue" / "ledger.json")
    assert queue["batches"][1]["status"] == "pending"


def test_expired_lease_returns_unit_to_pending(tmp_path: Path) -> None:
    _write_mini_queue(
        tmp_path, status="claimed", claimed_utc="2026-08-30T00:00:00Z"
    )
    claims = tmp_path / "artifacts" / "goal095" / "claims"
    claims.mkdir(parents=True)
    (claims / "evidence_assets-001-carter.json").write_text(
        json.dumps(
            {
                "schema": SCHEMA,
                "batch_id": "evidence_assets-001-carter",
                "kind": "evidence_assets",
                "status": "claimed",
                "claimed_utc": "2026-08-30T00:00:00Z",
                "lease_expires_utc": "2026-08-30T06:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    expired = expire_stale_claims(
        tmp_path, now=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    )
    assert expired == ["evidence_assets-001-carter"]
    queue = load_json(tmp_path / "artifacts" / "goal095" / "queue" / "ledger.json")
    assert queue["batches"][0]["status"] == "pending"
    claim_rec = load_json(claims / "evidence_assets-001-carter.json")
    assert claim_rec["status"] == "expired"


def test_parse_jsonl_whole_file_hash_rows_tail(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    lines = [
        json.dumps({"n": 1, "status": "fail", "score": 0.1}),
        json.dumps({"n": 2, "status": "pass", "score": 0.9}),
        json.dumps({"n": 3, "status": "fail", "score": 0.2}),
        json.dumps({"n": 4, "status": "pass", "score": 1.0}),
        json.dumps({"n": 5, "status": "pass", "score": 0.8}),
    ]
    body = ("\n".join(lines) + "\n").encode("utf-8")
    path.write_bytes(body)
    extract = parse_jsonl(path)
    assert extract["sha256"] == hashlib.sha256(body).hexdigest()
    assert extract["bytes"] == len(body)
    assert extract["rows"] == 5
    assert "status" in extract["schema"]["keys"]
    assert extract["extremes"]["numeric"]["score"]["min"] == 0.1
    assert extract["extremes"]["numeric"]["score"]["max"] == 1.0
    assert extract["errors"] == []
    tail = extract["samples"]["tail"]
    assert tail
    last = tail[-1]
    assert last["offset"] > 0
    assert last["offset"] >= extract["bytes"] - len(lines[-1]) - 2
    assert "n\": 5" in last["text"] or "n': 5" in last["text"] or '"n": 5' in last["text"]
    result = process_file(path, source_id="carter", rel="run.jsonl")
    assert result["terminal"] == "parseado_completo"
    assert result["extract"]["sha256"] == extract["sha256"]


def test_inventory_binary_does_not_equate_exists_with_works(tmp_path: Path) -> None:
    path = tmp_path / "clip.wav"
    data_size = 16
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE"
    fmt = b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16)
    data = b"data" + struct.pack("<I", data_size) + b"\x00" * data_size
    raw = header + fmt + data
    path.write_bytes(raw)
    rec = inventory_binary(path, source_id="probando_gemma4", rel="data/clip.wav")
    assert rec["sha256"] == hashlib.sha256(raw).hexdigest()
    assert rec["bytes"] == len(raw)
    assert rec["format"] == "wav"
    assert rec["exists"] is True
    assert rec["works"] is False
    assert rec["existence_means_works"] is False
    assert rec["provenance"]["source_id"] == "probando_gemma4"
    assert rec["recipe"]
    assert rec["consumers"]
    assert "associated_benchmark" in rec
    result = process_file(path, source_id="probando_gemma4", rel="data/clip.wav")
    assert result["terminal"] == "binario_inventariado"
    assert result["extract"]["works"] is False


def test_validate_rejects_leido_and_owner_relaunch() -> None:
    batch = _batch_stub(["a.jsonl"])
    ledger = _ledger(["a.jsonl"])
    ledger["files"][0]["terminal"] = "leido"
    errors = validate_ledger(ledger, batch)
    assert any("leido" in item for item in errors)
    ledger = _ledger(["a.jsonl"])
    ledger["next_prompt"] = OWNER
    errors = validate_ledger(ledger, batch)
    assert any("09.5.4" in item or "relaunch" in item for item in errors)


def test_validate_accepts_four_terminals() -> None:
    paths = ["a.jsonl", "b.wav", "c.jsonl", "d.rlib"]
    batch = _batch_stub(paths)
    ledger = _ledger(paths)
    ledger["files"] = [
        _file_row("a.jsonl", 0, terminal="parseado_completo"),
        _file_row("b.wav", 1, terminal="binario_inventariado"),
        _file_row("c.jsonl", 2, terminal="duplicado_por_hash"),
        _file_row("d.rlib", 3, terminal="excluido_razonado"),
    ]
    ledger["cards"] = [_card("a.jsonl"), _card("b.wav")]
    ledger["cards"][1]["card_id"] = "c2"
    ledger["cards"][1]["card_kind"] = "asset"
    ledger["cards"][1]["source_files"] = ["b.wav"]
    errors = validate_ledger(ledger, batch)
    assert errors == []


def test_validate_rejects_ranking_without_comparison() -> None:
    batch = _batch_stub(["a.jsonl"])
    ledger = _ledger(["a.jsonl"])
    ledger["cards"][0]["ranking_claim"] = True
    ledger["cards"][0]["equivalent_comparison"] = ""
    ledger["cards"][0]["measurement"] = "this is the best model on the set"
    errors = validate_ledger(ledger, batch)
    assert any("ranking" in item for item in errors)


def test_next_pending_skips_current() -> None:
    queue_ledger = {
        "batches": [
            {
                "batch_id": "evidence_assets-001-carter",
                "kind": "evidence_assets",
                "status": "complete",
            },
            {
                "batch_id": "docs-001-carter",
                "kind": "docs",
                "status": "pending",
            },
            {
                "batch_id": "evidence_assets-002-carter",
                "kind": "evidence_assets",
                "status": "pending",
            },
        ]
    }
    nxt = next_pending_evidence(queue_ledger, "evidence_assets-001-carter")
    assert nxt is not None
    assert nxt["batch_id"] == "evidence_assets-002-carter"


def test_claim_refuses_non_first_pending(tmp_path: Path) -> None:
    _write_mini_queue(tmp_path)
    with pytest.raises(RuntimeError, match="first pending evidence_assets"):
        claim(tmp_path, batch_id="evidence_assets-002-carter")


@pytest.mark.skipif(
    not (QUEUE / "batches.json").is_file(), reason="queue v1 not published"
)
def test_queue_still_has_132_evidence_lots() -> None:
    batches = load_json(QUEUE / "batches.json")
    ea = [item for item in batches if item.get("kind") == "evidence_assets"]
    assert len(ea) == 132
    assert ea[0]["batch_id"] == "evidence_assets-001-carter"


CAMPAIGN = REPO / "artifacts" / "goal095" / "campaigns" / "evidence_assets.json"
BATCH_LEDGER_001 = REPO / "artifacts" / "goal095" / "ledger" / "evidence_assets-001-carter.json"
BATCH_LEDGER_132 = (
    REPO / "artifacts" / "goal095" / "ledger" / "evidence_assets-132-baxy_schema_agent.json"
)


def test_published_evidence_campaign_is_terminal() -> None:
    assert CAMPAIGN.is_file()
    campaign = load_json(CAMPAIGN)
    assert campaign["campaign_id"] == "evidence_assets"
    assert campaign["required_human_launches"] == 1
    assert campaign["counts"]["pending"] == 0
    assert campaign["counts"]["claimed"] == 0
    assert campaign["counts"]["complete"] == 132
    assert campaign["next_human_prompt"] == (
        "documentacion/sprints/09.5.8_RUNTIME_UI_RECURSOS.md"
    )
    assert OWNER not in str(campaign["next_human_prompt"])
    queue_ledger = load_json(QUEUE / "ledger.json")
    claimed = [
        item["batch_id"]
        for item in queue_ledger["batches"]
        if item.get("kind") == "evidence_assets" and item.get("status") == "claimed"
    ]
    assert claimed == []
    claims_dir = REPO / "artifacts" / "goal095" / "claims"
    orphan = [
        path.name
        for path in claims_dir.glob("evidence_assets-*.json")
        if load_json(path).get("status") == "claimed"
    ]
    assert orphan == []
    first = load_json(BATCH_LEDGER_001)
    last = load_json(BATCH_LEDGER_132)
    batches = load_json(QUEUE / "batches.json")
    batch_001 = next(
        item for item in batches if item["batch_id"] == "evidence_assets-001-carter"
    )
    batch_132 = next(
        item
        for item in batches
        if item["batch_id"] == "evidence_assets-132-baxy_schema_agent"
    )
    assert validate_ledger(first, batch_001) == []
    assert validate_ledger(last, batch_132) == []
    assert first["claimed_utc"]
    assert last["next_prompt"] == (
        "documentacion/sprints/09.5.8_RUNTIME_UI_RECURSOS.md"
    )
    assert "09.5.4_AUDITAR_EVIDENCIA_LOTE.md" not in last["next_prompt"]
    raw = BATCH_LEDGER_001.read_text(encoding="utf-8").casefold()
    assert "c:\\users\\" not in raw
    assert "d:\\perfil\\" not in raw
    assert all(card["provisional"] is True for card in first["cards"])
    assert all(card.get("works") is not True for card in first["cards"])
