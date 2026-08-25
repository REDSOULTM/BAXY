from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_observed_user_corpora import (
    LEVEL_1_NAME,
    LEVEL_2_NAME,
    MANIFEST,
    PRODUCT_SOURCE_PREFIXES,
    SOURCE_MAPPING,
    SOURCE_MESSAGES,
    build,
    read_source_rows,
)


EXPECTED_LEVEL_1_ROWS = 1947
EXPECTED_LEVEL_1_UNIQUE_TEXTS = 626
EXPECTED_LEVEL_2_ROWS = 808
EXPECTED_LEVEL_2_UNIQUE_TEXTS = 281


def test_observed_user_corpora_rebuild_exactly(tmp_path: Path) -> None:
    rebuilt_manifest = tmp_path / MANIFEST.name
    manifest = build(output_dir=tmp_path, manifest_path=rebuilt_manifest)
    published = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert manifest == published
    assert rebuilt_manifest.read_bytes() == MANIFEST.read_bytes()

    level_1 = manifest["levels"]["level_1_all_observed_product_turns"]
    level_2 = manifest["levels"]["level_2_actionable_user_missions"]
    assert level_1["row_count"] == EXPECTED_LEVEL_1_ROWS
    assert level_1["unique_text_sha256"] == EXPECTED_LEVEL_1_UNIQUE_TEXTS
    assert level_2["row_count"] == EXPECTED_LEVEL_2_ROWS
    assert level_2["unique_text_sha256"] == EXPECTED_LEVEL_2_UNIQUE_TEXTS
    assert len(level_2["operation_counts"]) == 32
    assert level_2["possible_chain_rows"] == 74


def test_two_levels_are_exact_private_runtime_projections(tmp_path: Path) -> None:
    build(output_dir=tmp_path, manifest_path=tmp_path / MANIFEST.name)
    level_1 = [row for row, _ in read_source_rows(tmp_path / LEVEL_1_NAME)]
    level_2 = [row for row, _ in read_source_rows(tmp_path / LEVEL_2_NAME)]

    assert len(level_1) == EXPECTED_LEVEL_1_ROWS
    assert all(row["origin"] == "observed_user" for row in level_1)
    assert all(str(row["source"]).startswith(PRODUCT_SOURCE_PREFIXES) for row in level_1)
    assert all(not str(row["source"]).startswith("codex/") for row in level_1)
    assert all(row["class"] == "user_mission" for row in level_2)
    assert {row["message_id"] for row in level_2} < {
        row["message_id"] for row in level_1
    }


def test_every_observed_message_has_one_consistent_acceptance_contract() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source_ids = {
        row["message_id"]
        for row, _ in read_source_rows(SOURCE_MESSAGES)
        if row.get("origin") == "observed_user"
        and str(row.get("source") or "").startswith(PRODUCT_SOURCE_PREFIXES)
    }
    mapping_ids = [
        row["message_id"]
        for row, _ in read_source_rows(SOURCE_MAPPING)
        if row.get("message_id") in source_ids
    ]

    assert len(source_ids) == EXPECTED_LEVEL_1_ROWS
    assert len(mapping_ids) == EXPECTED_LEVEL_1_ROWS
    assert len(mapping_ids) == len(set(mapping_ids))
    assert manifest["contract_consistency"]["conflicting_unique_literals"] == 0


def test_private_generated_jsonl_is_not_versioned() -> None:
    root = Path(__file__).resolve().parents[1]
    ignored = (root / ".gitignore").read_text(encoding="utf-8")
    notice = (root / "tests" / "data" / "TURN_EVIDENCE_DATA_NOTICE.md").read_text(
        encoding="utf-8"
    )

    assert f"/tests/data/{LEVEL_1_NAME}" in ignored
    assert f"/tests/data/{LEVEL_2_NAME}" in ignored
    assert LEVEL_1_NAME in notice
    assert LEVEL_2_NAME in notice


def test_corpus_is_owned_by_the_single_integral_validation_goal() -> None:
    root = Path(__file__).resolve().parents[1]
    sprint_dir = root / "documentacion" / "sprints"
    index = (sprint_dir / "00_INDICE.md").read_text(encoding="utf-8")
    goal_10 = (sprint_dir / "10_VALIDACION_INTEGRAL.md").read_text(encoding="utf-8")
    goal_11 = (sprint_dir / "11_CIERRE.md").read_text(encoding="utf-8")

    assert not (sprint_dir / "11_HISTORICO_REAL.md").exists()
    assert not (sprint_dir / "12_VALIDACION.md").exists()
    assert goal_10.startswith("# Goal 10 — La validación integral del producto")
    assert "1.947/1.947 veredictos individuales" in goal_10
    assert "no permiten ejecutar una vez" in goal_10
    assert goal_11.startswith("# Goal 11 — El cierre")
    assert "no lanza una segunda validación" in index
    assert "# BAXY en once goals" in index
