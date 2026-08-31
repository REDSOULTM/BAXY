"""Goal 09.5.12 — load the shipped lineage close-out, not a fixture copy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.goal095_09512_integrate import (
    BARS_LITERAL,
    EXECUTABLE_PROMPTS,
    FOUR_CLASSES,
    GOAL01_CLOSED,
    HANDOFF_REL,
    LEDGER_REL,
    MAPA_REL,
    MARKDOWN_REL,
    NEXT_PROMPT,
    ORDEN_REL,
    OWNER_PROMPT,
    SCHEMA,
    SYNTHESIS_REL,
    VERSION,
    coverage_snapshot,
    generate_lineage_appendix,
    load_report,
    parse_orden_executable,
    remaining_prompt_files,
    report_path,
    reproduce_manifest_hashes,
    validate_report,
)

REPO = Path(__file__).resolve().parents[1]


def test_shipped_09512_report_is_the_repo_artifact() -> None:
    path = report_path(REPO)
    assert path == REPO / SYNTHESIS_REL
    assert path.is_file()
    assert path.read_text(encoding="utf-8").startswith("{")
    report = load_report(REPO)
    assert report["schema"] == SCHEMA
    assert report["version"] == VERSION
    assert report["next_human_prompt"] == NEXT_PROMPT
    assert report["owner_prompt"] == OWNER_PROMPT
    assert OWNER_PROMPT not in report["next_human_prompt"]
    assert "09.5.12" not in report["next_human_prompt"]
    ledger = json.loads((REPO / LEDGER_REL).read_text(encoding="utf-8"))
    assert ledger["next_human_prompt"] == NEXT_PROMPT
    assert str((ledger.get("full_gate") or {}).get("result") or "").strip()
    assert (REPO / MARKDOWN_REL).is_file()
    assert (REPO / HANDOFF_REL).is_file()
    markdown = (REPO / MARKDOWN_REL).read_text(encoding="utf-8")
    assert "10.0_BASE_VERDE.md" in markdown.split("Siguiente prompt humano", 1)[1]
    assert "09.5.12_INTEGRAR_Y_REPLANIFICAR.md" not in markdown.split(
        "Siguiente prompt humano", 1
    )[1]


def test_coverage_queues_terminals_and_reproducible_hashes() -> None:
    snapshot = coverage_snapshot(REPO)
    assert snapshot["missing"] == 0
    assert snapshot["overlaps"] == 0
    assert snapshot["covered"] == snapshot["manifest_files"]
    assert snapshot["coverage_pct"] == 100.0
    for name, counts in snapshot["campaigns"].items():
        assert counts["pending"] == 0, name
        assert counts["claimed"] == 0, name
    assert snapshot["campaigns"]["transplant"]["total"] == 0
    assert str(snapshot["transplant_empty_reason"]).strip()
    assert snapshot["ledger_files"] > 0
    assert snapshot["ledger_invalid_terminals"] == []
    assert snapshot["ledger_empty_terminals"] == 0
    first = reproduce_manifest_hashes(REPO)
    second = reproduce_manifest_hashes(REPO)
    assert first == second
    for source_id, rec in first.items():
        assert rec["match"] is True, source_id
        assert rec["actual"] == rec["expected"]
    report = load_report(REPO)
    errors = validate_report(report, repo=REPO)
    assert errors == []
    assert report["coverage"]["percent"] == 100.0
    assert report["slices_added"] == 0


def test_map_names_four_classes_and_keeps_goal01() -> None:
    mapa = (REPO / MAPA_REL).read_text(encoding="utf-8")
    indice = (REPO / "biblioteca" / "00_INDICE.md").read_text(encoding="utf-8")
    inventario = (REPO / "biblioteca" / "01_INVENTARIO.md").read_text(encoding="utf-8")
    assert GOAL01_CLOSED in mapa
    assert "1.350" in indice or "1350" in indice
    for label in FOUR_CLASSES:
        assert label in mapa.casefold(), label
        assert label in indice.casefold() or label in inventario.casefold(), label
    assert "cero lote" in mapa.casefold() or "cero trasplante" in mapa.casefold()
    first = generate_lineage_appendix(REPO)
    second = generate_lineage_appendix(REPO)
    assert hashlib.sha256(first.encode("utf-8")).digest() == hashlib.sha256(
        second.encode("utf-8")
    ).digest()
    for label in FOUR_CLASSES:
        assert label in first.casefold(), label
    assert "functiongemma-270m-ft" in first
    report = load_report(REPO)
    assert report["four_classes"] == list(FOUR_CLASSES)


def test_prompts_10_11_inherit_keep_bars_and_have_no_extra_slices() -> None:
    report = load_report(REPO)
    errors = validate_report(report, repo=REPO)
    assert errors == []
    sprints = REPO / "documentacion" / "sprints"
    for name in EXECUTABLE_PROMPTS:
        text = (sprints / name).read_text(encoding="utf-8")
        assert "## Herencia 09.5" in text
        assert "## Objetivo único" in text
        assert "## Criterios de cierre" in text
        assert "## Contrato de sesión" in text
        for bar in BARS_LITERAL:
            assert bar in text, f"{name} missing {bar}"
        assert "Hueco probado:" in text
        assert "500k" in text
    numbered = [
        path.name
        for path in sprints.glob("*.md")
        if path.name[0:2] in {"10", "11"}
        and path.name[2:3] == "."
        and path.name[3].isdigit()
    ]
    assert sorted(numbered) == sorted(EXECUTABLE_PROMPTS)


def test_orden_matches_remaining_executable_and_names_10_0() -> None:
    files = parse_orden_executable(REPO)
    assert files == list(remaining_prompt_files())
    assert files == list(EXECUTABLE_PROMPTS)
    assert files[0] == "10.0_BASE_VERDE.md"
    assert files[-1] == "11.16_FULL_Y_CIERRE.md"
    assert len(files) == len(set(files))
    assert "09.5.12_INTEGRAR_Y_REPLANIFICAR.md" not in files
    text = (REPO / ORDEN_REL).read_text(encoding="utf-8")
    assert "10.0_BASE_VERDE.md" in text
    assert "09.5.12" in text
    siguiente = (REPO / HANDOFF_REL).read_text(encoding="utf-8").split(
        "## Siguiente accion recomendada", 1
    )[1]
    assert "10.0_BASE_VERDE.md" in siguiente
    assert "09.5.12_INTEGRAR_Y_REPLANIFICAR.md" not in siguiente
    report = load_report(REPO)
    assert report["orden"] == files
    assert report["enabled_next"] == NEXT_PROMPT
