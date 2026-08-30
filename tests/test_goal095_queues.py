from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.build_goal095_queues import (
    ESTIMATOR,
    FROZEN_0950,
    TOKEN_LIMIT,
    assign_records,
    build,
    classify_kind,
    estimate_tokens,
    exclusion_rule,
    load_jsonl,
    make_record,
    pack_batches,
    partition_ok,
    sha256_file,
    sha256_path,
    sparse_exclusions,
)

QUEUE = REPO / "artifacts" / "goal095" / "queue"
COBERTURA = REPO / "documentacion" / "herencia" / "09_5_COBERTURA.md"


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8", newline="\n")


def _specs(tmp: Path) -> dict[str, dict]:
    return {
        "carter": {
            "logical": "Programacion/Carter OS AI",
            "folder": "Carter OS AI",
            "files": None,
        },
        "probando_gemma4": {
            "logical": "Programacion/Probando Gemma 4",
            "folder": "Probando Gemma 4",
            "files": None,
        },
    }


def _mini_programacion(tmp: Path) -> Path:
    root = tmp / "Programacion"
    covered = (REPO / "biblioteca" / "00_INDICE.md").read_bytes()[:200]
    # Same bytes as a biblioteca document listed in 01_INVENTARIO.
    inventory_doc = (
        REPO / "biblioteca" / "carter" / "carter_v5" / "README.md"
    )
    _write(
        root / "Carter OS AI" / "docs" / "ARCHITECTURE.md",
        inventory_doc.read_bytes() if inventory_doc.is_file() else covered,
    )
    _write(
        root / "Carter OS AI" / "docs" / "NEW_NOTE.md",
        "# never inventoried\n",
    )
    _write(
        root / "Carter OS AI" / "carter_v5" / "agent.py",
        "print('agent')\n",
    )
    _write(
        root / "Carter OS AI" / "node_modules" / "pkg" / "index.js",
        "module.exports = 1\n",
    )
    _write(
        root / "Carter OS AI" / "Extras" / "Competidores" / "AutoGPT-master" / "x.md",
        "third party\n",
    )
    _write(
        root / "Probando Gemma 4" / "documentacion" / "03_voz_stt" / "note.md",
        "# voz\n" + ("a" * 100),
    )
    _write(
        root / "Probando Gemma 4" / "gemma4_agent" / "tests" / "test_x.py",
        "def test_ok():\n    assert True\n",
    )
    _write(
        root / "Probando Gemma 4" / "__pycache__" / "x.pyc",
        b"\x00\x01",
    )
    _write(
        root / "Probando Gemma 4" / "data" / "trace.jsonl",
        '{"ok": true}\n',
    )
    return root


def test_exclusion_rules_are_reproducible() -> None:
    assert exclusion_rule(".venv/lib/site.py") == "dot_directory"
    assert exclusion_rule("src/__pycache__/a.pyc") == "python_cache"
    assert exclusion_rule("node_modules/x/index.js") == "node_modules"
    assert exclusion_rule("Extras/Competidores/AutoGPT-master/README.md") == (
        "vendor_snapshot"
    )
    assert exclusion_rule("Referencia OpenClaw/openclaw-main/x.ts") == (
        "vendor_snapshot"
    )
    assert exclusion_rule("docs/ARCHITECTURE.md") is None
    assert exclusion_rule("Extras/Optimizacion Hermes3/guia.md") is None
    assert (
        exclusion_rule("Extras/Optimizacion Hermes3/llama.cpp-master/ggml.c")
        == "vendor_snapshot"
    )


def test_name_match_is_not_prior_coverage(tmp_path: Path) -> None:
    records = [
        make_record(
            "carter",
            {
                "path": "docs/01_INVENTARIO.md",
                "sha256": "ab" * 32,
                "size": 12,
                "mtime_unix": 1,
            },
        )
    ]
    assigned = assign_records(records, biblioteca={}, cards=[])
    assert assigned[0]["assignment"] == "queue"
    assert assigned[0]["cobertura_previa"] is None


def test_hash_identical_to_inventory_is_prior_coverage() -> None:
    inventory_doc = REPO / "biblioteca" / "carter" / "carter_v5" / "README.md"
    digest = sha256_file(inventory_doc)
    records = [
        make_record(
            "carter",
            {
                "path": "carter_v5/README.md",
                "sha256": digest,
                "size": inventory_doc.stat().st_size,
                "mtime_unix": 1,
            },
        )
    ]
    from scripts.build_goal095_queues import biblioteca_index, goal01_cards

    biblio = biblioteca_index(REPO)
    assigned = assign_records(
        records, biblioteca=biblio, cards=goal01_cards(REPO)
    )
    assert assigned[0]["assignment"] == "prior_coverage"
    assert assigned[0]["cobertura_previa"]["kind"] == "hash_identical"
    assert "biblioteca/" in assigned[0]["cobertura_previa"]["biblioteca_path"]


def test_duplicate_hash_is_not_queued_twice() -> None:
    blob = {"path": "a.md", "sha256": "cd" * 32, "size": 4, "mtime_unix": 1}
    records = [
        make_record("carter", dict(blob, path="one.md")),
        make_record("baxy", dict(blob, path="two.md")),
    ]
    assigned = assign_records(records, biblioteca={}, cards=[])
    kinds = {row["path"]: row["assignment"] for row in assigned}
    assert kinds["two.md"] == "queue"
    assert kinds["one.md"] == "duplicate"
    partition = partition_ok(assigned)
    assert partition["missing"] == 0
    assert partition["overlaps"] == 0
    assert partition["queued"] + partition["duplicates"] == 2


def test_batches_stay_under_limit_and_split_by_subsystem() -> None:
    files = []
    for index in range(8):
        files.append(
            make_record(
                "probando_gemma4",
                {
                    "path": f"documentacion/03_voz_stt/n{index}.md",
                    "sha256": f"{index:064x}",
                    "size": 120_000,
                    "mtime_unix": 1,
                },
            )
        )
    assigned = assign_records(files, biblioteca={}, cards=[])
    batches = pack_batches(assigned)
    assert batches
    assert all(item["estimated_tokens"] <= TOKEN_LIMIT for item in batches)
    assert all(item["kind"] == "docs" for item in batches)
    assert all("09.5.2" in item["owner"] for item in batches)
    assert all(item["output"].startswith("artifacts/goal095/ledger/") for item in batches)


def test_binaries_cost_metadata_jsonl_is_parse_complete() -> None:
    assert estimate_tokens(5_000_000, binary=True, parse_complete=False) == 256
    jsonl = estimate_tokens(2_000_000, binary=False, parse_complete=True)
    assert jsonl <= 8192
    assert classify_kind("model.gguf", binary=True, parse_complete=False) == (
        "evidence_assets"
    )
    assert classify_kind("eval.jsonl", binary=False, parse_complete=True) == (
        "evidence_assets"
    )


def test_sparse_exclusions_have_no_invented_hashes() -> None:
    payload = sparse_exclusions()
    assert payload["counted_as_physical_missing"] is False
    assert payload["inspected"] is False
    for entry in payload["entries"]:
        assert entry["individual_hashes"] == "not invented"
        assert entry["individual_paths"] is None


def test_fixture_build_is_deterministic_and_private(tmp_path: Path) -> None:
    programacion = _mini_programacion(tmp_path)
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"
    cobertura_a = tmp_path / "a.md"
    cobertura_b = tmp_path / "b.md"
    kwargs = dict(
        repo=REPO,
        programacion=programacion,
        specs=_specs(tmp_path),
        require_frozen_hash=False,
        include_schema_agent=False,
    )
    first = build(
        **kwargs,
        out_dir=out_a,
        cobertura_path=cobertura_a,
        hash_cache_dir=out_a / "sources",
    )
    second = build(
        **kwargs,
        out_dir=out_b,
        cobertura_path=cobertura_b,
        hash_cache_dir=out_b / "sources",
    )
    assert first["seal"] == second["seal"]
    summary = first["summary"]
    assert summary["missing"] == 0
    assert summary["overlaps"] == 0
    assert summary["queued"] + summary["duplicates"] + summary["prior_coverage"] == (
        summary["manifest_files"]
    )
    manifest = load_jsonl(out_a / "queue" / "unified_manifest.jsonl")
    paths = {row["path"] for row in manifest}
    assert "node_modules/pkg/index.js" not in paths
    assert "Extras/Competidores/AutoGPT-master/x.md" not in paths
    raw = (out_a / "queue" / "unified_manifest.jsonl").read_text(encoding="utf-8")
    assert "d:\\perfil" not in raw.casefold()
    assert "c:\\users\\" not in raw.casefold()
    batches = json.loads((out_a / "queue" / "batches.json").read_text(encoding="utf-8"))
    assert all(item["estimated_tokens"] <= TOKEN_LIMIT for item in batches)
    assert ESTIMATOR == "bytes_div_2"


def test_published_outputs_hold_invariants() -> None:
    if not (QUEUE / "unified_manifest.jsonl").is_file():
        pytest.skip("09.5.1 queue artifacts not published yet")
    manifest = load_jsonl(QUEUE / "unified_manifest.jsonl")
    partition = partition_ok(manifest)
    assert partition["missing"] == 0
    assert partition["overlaps"] == 0
    assert (
        partition["queued"]
        + partition["duplicates"]
        + partition["prior_coverage"]
        == partition["manifest_files"]
    )
    batches = json.loads((QUEUE / "batches.json").read_text(encoding="utf-8"))
    assert batches
    assert all(item["estimated_tokens"] <= TOKEN_LIMIT for item in batches)
    assert all("owner" in item and "output" in item for item in batches)
    assigned = {(item["source_id"], item["path"]) for item in manifest}
    seen_files = set()
    for batch in batches:
        for row in batch["files"]:
            key = (row["source_id"], row["path"])
            assert key in assigned
            seen_files.add(key)
    queued = {
        (item["source_id"], item["path"])
        for item in manifest
        if item["assignment"] == "queue"
    }
    assert seen_files == queued
    for name in (
        "unified_manifest.jsonl",
        "batches.json",
        "sparse_exclusions.json",
        "exclusion_counts.json",
        "ledger.json",
        "summary.json",
    ):
        raw = (QUEUE / name).read_text(encoding="utf-8").casefold()
        assert "c:\\users\\" not in raw
        assert "d:\\perfil\\" not in raw
    cobertura = COBERTURA.read_text(encoding="utf-8")
    assert "c:\\users\\" not in cobertura.casefold()
    assert "d:\\perfil\\" not in cobertura.casefold()
    sparse = json.loads((QUEUE / "sparse_exclusions.json").read_text(encoding="utf-8"))
    assert sparse["counted_as_physical_missing"] is False
    fg = REPO / FROZEN_0950["functiongemma"]["manifest_rel"]
    pg4 = REPO / FROZEN_0950["probando_gemma4"]["manifest_rel"]
    assert sha256_path(fg) == FROZEN_0950["functiongemma"]["manifest_sha256"]
    assert sha256_path(pg4) == FROZEN_0950["probando_gemma4"]["manifest_sha256"]
    recon = json.loads((QUEUE / "reconstruction.json").read_text(encoding="utf-8"))
    assert recon["manifest_sha256"] == sha256_path(QUEUE / "unified_manifest.jsonl")
