"""Goal 09.5.11A — load the shipped revalidation matrix, not a fixture copy."""

from __future__ import annotations

from pathlib import Path

from experiments.mind_router_spike.measure_goal03_catalog_coverage import (
    coverage_ledger_sha256,
)
from experiments.mind_router_spike.run_goal03_comprehension import score as score_comprehension
from scripts.goal095_09511a_revalidate import (
    ACTED_MAX,
    CATALOG_FAMILIES,
    CATALOG_OPERATIONS,
    CATALOG_REACHABLE,
    CORPUS_REL,
    CORPUS_SHA256,
    COVERAGE_03C_REL,
    COVERAGE_11A_REL,
    HANDOFF_REL,
    LANGUAGES,
    LEDGER_REL,
    MARKDOWN_REL,
    NEXT_PROMPT,
    OWNER_PROMPT,
    SCHEMA,
    SEAL_03C,
    SERVED_MIN,
    STABLE_OOC_ACTED_03B,
    SYNTHESIS_REL,
    catalog_delta,
    corpus_profile,
    coverage_identity,
    load_json,
    load_jsonl,
    load_report,
    provenance_snapshot,
    report_path,
    required_criterion_ids,
    rescore_telemetry,
    sha256_file,
    validate_report,
)

REPO = Path(__file__).resolve().parents[1]


def test_shipped_09511a_report_is_the_repo_artifact() -> None:
    path = report_path(REPO)
    assert path == REPO / SYNTHESIS_REL
    assert path.is_file()
    assert path.read_text(encoding="utf-8").startswith("{")
    report = load_report(REPO)
    assert report["schema"] == SCHEMA
    assert (REPO / LEDGER_REL).is_file()
    assert (REPO / MARKDOWN_REL).is_file()
    assert (REPO / HANDOFF_REL).is_file()
    assert (REPO / COVERAGE_11A_REL).is_file()


def test_shipped_09511a_matrix_has_every_01_03c_row_and_names_11b() -> None:
    report = load_report(REPO)
    errors = validate_report(report, repo=REPO)
    assert errors == []
    present = [row["id"] for row in report["criteria"]]
    assert present == list(required_criterion_ids())
    goals = {row["goal"] for row in report["criteria"]}
    assert {"01", "02", "03", "03B", "03C", "09.5"} <= goals
    assert report["next_human_prompt"] == NEXT_PROMPT
    assert report["owner_prompt"] == OWNER_PROMPT
    assert OWNER_PROMPT not in report["next_human_prompt"]
    assert "09.5.11C" not in report["next_human_prompt"]
    assert "10.0" not in report["next_human_prompt"]
    assert report["deferred_to_goal10"] == []
    handoff = (REPO / HANDOFF_REL).read_text(encoding="utf-8")
    siguiente = handoff.split("## Siguiente accion recomendada", 1)[1]
    assert "09.5.11B_REVALIDAR_04_06.md" in siguiente
    assert "09.5.11A_REVALIDAR_01_03C.md" not in siguiente
    assert "10.0_BASE_VERDE.md" not in siguiente


def test_shipped_corpus_is_the_frozen_es_en_spanglish_bytes() -> None:
    profile = corpus_profile(REPO)
    assert profile["sha256"] == CORPUS_SHA256
    assert sha256_file(REPO / CORPUS_REL) == CORPUS_SHA256
    assert profile["in_catalog"] == 124
    assert profile["out_of_catalog"] == 36
    for language in LANGUAGES:
        assert language in profile["languages"]
    report = load_report(REPO)
    assert report["corpus"]["sha256"] == CORPUS_SHA256


def test_published_comprehension_holdouts_rescore_with_shipped_score() -> None:
    report = load_report(REPO)
    comprehension = report["holdouts"]["comprehension"]
    assert comprehension["median_served"] >= SERVED_MIN
    assert comprehension["max_acted"] <= ACTED_MAX
    assert set(LANGUAGES) <= set(comprehension["languages"])
    served = []
    for run in comprehension["runs"]:
        telemetry = load_jsonl(REPO / run["telemetry"])
        scored = score_comprehension(telemetry)
        published = load_json(REPO / run["published"])
        acted = scored["out_of_catalog"]["rows"] - scored["out_of_catalog"]["honest_abstentions"]
        assert scored["in_catalog"]["served"] == run["served"] == published["in_catalog"]["served"]
        assert acted == run["acted"]
        assert set(LANGUAGES) <= set(scored["in_catalog"]["by_language"])
        assert scored["latency_seconds"]["all"]["p50"] == run["p50"]
        assert isinstance(run["p50"], (int, float))
        assert scored["latency_seconds"]["deterministic_path"]["p50"] < 1.0
        assert run["stable_ooc_acted"] == []
        for case_id in STABLE_OOC_ACTED_03B:
            row = next(
                item
                for item in scored["out_of_catalog_rows"]
                if item["case_id"] == case_id
            )
            assert row["acted"] is False
        assert scored["three_zeros"]["effects_executed"] == 0
        served.append(scored["in_catalog"]["served"])
        assert rescore_telemetry(REPO / run["telemetry"])["in_catalog"]["served"] == run["served"]
    assert sorted(served)[1] >= SERVED_MIN


def test_published_catalog_coverage_rescores_and_does_not_drop_03c() -> None:
    current = load_json(REPO / COVERAGE_11A_REL)
    baseline = load_json(REPO / COVERAGE_03C_REL)
    identity = coverage_identity(current)
    assert identity["operations"] == CATALOG_OPERATIONS == current["count"]["operations"]
    assert identity["planner_reachable"] == CATALOG_REACHABLE
    assert identity["families"] == CATALOG_FAMILIES
    assert identity["coverage_ledger_sha256"] == current["coverage_ledger_sha256"]
    assert coverage_ledger_sha256(current["entries"]) == current["coverage_ledger_sha256"]
    assert baseline["coverage_ledger_sha256"] == SEAL_03C
    delta = catalog_delta(baseline, current)
    assert delta["missing_operations"] == []
    assert delta["lost_reachability"] == []
    assert delta["baseline_count"]["operations"] == CATALOG_OPERATIONS
    report = load_report(REPO)
    assert report["holdouts"]["catalog"]["delta"]["missing_operations"] == []
    assert report["catalog_contract_delta"]["missing_operations"] == []


def test_provenance_campaigns_closed_and_sparse_hashes_not_invented() -> None:
    snapshot = provenance_snapshot(REPO)
    assert snapshot["docs"]["pending"] == 0 and snapshot["docs"]["complete"] == 25
    assert snapshot["code_tests"]["pending"] == 0 and snapshot["code_tests"]["complete"] == 477
    assert snapshot["evidence_assets"]["pending"] == 0
    assert snapshot["evidence_assets"]["complete"] == 132
    assert snapshot["transplant"]["pending"] == 0
    assert snapshot["transplant"]["claimed"] == 0
    assert snapshot["sparse_not_invented"] is True
    assert snapshot["protected_rejects_in_lots"] == []
    aplazados = (REPO / "documentacion" / "APLAZADOS.md").read_text(encoding="utf-8")
    assert "09.5.11A" not in aplazados or "Goal 10" not in aplazados


def test_goal01_fieldui_update_keeps_the_previous_finding() -> None:
    mapa = (REPO / "documentacion" / "herencia" / "00_MAPA.md").read_text(encoding="utf-8")
    assert "35 ficheros y `12929F7A" in mapa
    assert "No se corrige subiendo la constante" in mapa
    assert "Actualización 09.5.11A — sello FieldUi" in mapa
    assert "0F6C38D1E3C377012BD7231372363334DB7ADD51845578074E59EFB1195E8122" in mapa
    report = load_report(REPO)
    updates = report["goal01_map_updates"]
    assert updates
    assert updates[0]["previous_finding_retained"] is True


def test_validator_rejects_missing_row_bad_next_and_goal10_deferral() -> None:
    report = load_report(REPO)
    missing = dict(report)
    missing["criteria"] = list(report["criteria"])[1:]
    errors = validate_report(missing, repo=REPO)
    assert any("missing criteria" in item for item in errors)

    remitting = dict(report)
    remitting["next_human_prompt"] = OWNER_PROMPT
    errors = validate_report(remitting, repo=REPO)
    assert any("09.5.11A" in item or "next_human_prompt" in item for item in errors)

    to_ten = dict(report)
    to_ten["next_human_prompt"] = "documentacion/sprints/10.0_BASE_VERDE.md"
    to_ten["deferred_to_goal10"] = ["acted"]
    errors = validate_report(to_ten, repo=REPO)
    assert any("Goal 10" in item or "10.0" in item or "deferred" in item for item in errors)

    poisoned = dict(report)
    poisoned["corpus"] = dict(report["corpus"], sha256="0" * 64)
    errors = validate_report(poisoned, repo=REPO)
    assert any("corpus sha" in item for item in errors)
