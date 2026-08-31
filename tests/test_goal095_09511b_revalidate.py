"""Goal 09.5.11B — load the shipped revalidation matrix, not a fixture copy."""

from __future__ import annotations

from pathlib import Path

from experiments.mind_router_spike.score_goal04_honesty import score_telemetry
from scripts.censo_voz_visible import censar
from scripts.goal095_09511b_revalidate import (
    CORPUS_SHA256,
    GOAL05_HISTORICAL_MATRIX_REL,
    GOAL05_HISTORICAL_MEASURED_PREFIX,
    GOAL05_MATRIX_REL,
    HANDOFF_REL,
    HONESTY_RUNNER_SHA256,
    HONESTY_SCORER_SHA256,
    LEDGER_REL,
    MARKDOWN_REL,
    NEXT_PROMPT,
    OWNER_PROMPT,
    SCHEMA,
    SYNTHESIS_REL,
    VIEWMODEL_REL,
    aplazados_defers_11b_to_goal10,
    corpus_profile,
    goal05_contracts,
    load_json,
    load_jsonl,
    load_report,
    provenance_snapshot,
    report_path,
    required_criterion_ids,
    sha256_file,
    validate_report,
)

REPO = Path(__file__).resolve().parents[1]


def test_shipped_09511b_report_is_the_repo_artifact() -> None:
    path = report_path(REPO)
    assert path == REPO / SYNTHESIS_REL
    assert path.is_file()
    assert path.read_text(encoding="utf-8").startswith("{")
    report = load_report(REPO)
    assert report["schema"] == SCHEMA
    assert (REPO / LEDGER_REL).is_file()
    assert (REPO / MARKDOWN_REL).is_file()
    assert (REPO / HANDOFF_REL).is_file()
    assert (REPO / GOAL05_MATRIX_REL).is_file()


def test_shipped_09511b_matrix_has_every_04_06_row_and_names_11c() -> None:
    report = load_report(REPO)
    errors = validate_report(report, repo=REPO)
    assert errors == []
    present = [row["id"] for row in report["criteria"]]
    assert present == list(required_criterion_ids())
    goals = {row["goal"] for row in report["criteria"]}
    assert {"04", "05", "06", "09.5"} <= goals
    assert report["next_human_prompt"] == NEXT_PROMPT
    assert report["owner_prompt"] == OWNER_PROMPT
    assert OWNER_PROMPT not in report["next_human_prompt"]
    assert "09.5.11B" not in report["next_human_prompt"]
    assert "09.5.11A" not in report["next_human_prompt"]
    assert "09.5.10" not in report["next_human_prompt"]
    assert "10.0" not in report["next_human_prompt"]
    assert report["deferred_to_goal10"] == []
    handoff = (REPO / HANDOFF_REL).read_text(encoding="utf-8")
    siguiente = handoff.split("## Siguiente accion recomendada", 1)[1]
    assert "09.5.11C_REVALIDAR_07_09.md" in siguiente
    assert "09.5.11B_REVALIDAR_04_06.md" not in siguiente
    assert "09.5.11A_REVALIDAR_01_03C.md" not in siguiente
    assert "10.0_BASE_VERDE.md" not in siguiente


def test_shipped_corpus_is_the_frozen_es_en_spanglish_bytes() -> None:
    profile = corpus_profile(REPO)
    assert profile["sha256"] == CORPUS_SHA256
    report = load_report(REPO)
    assert report["corpus"]["sha256"] == CORPUS_SHA256
    assert profile["in_catalog"] == 124
    assert profile["out_of_catalog"] == 36


def test_published_honesty_holdouts_rescore_with_shipped_score_telemetry() -> None:
    report = load_report(REPO)
    honesty = report["holdouts"]["honesty"]
    assert honesty["scorer_sha256"] == HONESTY_SCORER_SHA256
    assert honesty["runner_sha256"] == HONESTY_RUNNER_SHA256
    assert honesty["zeros"] == {
        "unsolicited_effects": 0,
        "unverified_successes": 0,
        "fixed_visible_replies": 0,
    }
    assert honesty["zeros_hold"] is True
    for run in honesty["runs"]:
        telemetry = load_jsonl(REPO / run["telemetry"])
        scored = score_telemetry(telemetry)
        published = load_json(REPO / run["published"])
        assert scored["unsolicited_effects"] == 0 == run["zeros"]["unsolicited_effects"]
        assert scored["unverified_successes"] == 0 == run["zeros"]["unverified_successes"]
        assert scored["fixed_visible_replies"] == 0 == run["zeros"]["fixed_visible_replies"]
        assert scored["unusable_empty_visible"] == 0
        assert scored["zeros_hold"] is True
        assert scored["conversation_replies"] > 0
        assert run["empty_clarify_or_conversation"] == []
        assert published["unsolicited_effects"] == scored["unsolicited_effects"]
        assert len(telemetry) == 160
        for row in telemetry:
            assert row.get("provider_dispatch_enabled") in (False, None)
            assert row.get("external_effect_executed") in (False, None)


def test_visible_prose_census_on_current_src_is_zero() -> None:
    hits = censar(str(REPO / "src"))
    assert hits == []
    report = load_report(REPO)
    assert report["holdouts"]["census"]["literals"] == 0
    assert report["holdouts"]["census"]["files"] == 0
    viewmodel = (REPO / VIEWMODEL_REL).read_text(encoding="utf-8")
    assert "VoiceListenVisibleFacts" in viewmodel
    assert "Listo, te escucho" not in viewmodel


def test_voice_sample_rescored_with_shipped_guards_is_clean() -> None:
    report = load_report(REPO)
    voice = report["holdouts"]["voice"]
    assert voice["rows"] == 100
    assert voice["bad_count"] == 0
    assert voice["narrate_is_compose"] is True
    assert voice["narrator_prompt_is_user_prompt"] is True
    assert voice["personality_in_prompt"] is True


def test_goal05_matrix_and_shipped_contracts_hold() -> None:
    report = load_report(REPO)
    goal05 = report["holdouts"]["goal05"]
    matrix = load_json(REPO / GOAL05_MATRIX_REL)
    historical = load_json(REPO / GOAL05_HISTORICAL_MATRIX_REL)
    assert matrix["schema"] == "baxy.goal05-execution-matrix.v1"
    assert matrix["catalogOperations"] == 170 == goal05["catalog_operations"]
    assert matrix["observed"] + matrix["unverifiable"] == 170
    assert goal05["unverifiable_without_reason"] == []
    assert goal05["live_runs"] > 4
    assert goal05["live_failed_starting_listo"] == []
    assert str(historical.get("measuredAtUtc") or "").startswith(
        GOAL05_HISTORICAL_MEASURED_PREFIX
    )
    assert sha256_file(REPO / GOAL05_HISTORICAL_MATRIX_REL) != sha256_file(
        REPO / GOAL05_MATRIX_REL
    )
    assert goal05["historical_measured_at"] == historical["measuredAtUtc"]
    contracts = goal05_contracts(REPO)
    assert contracts["missing"] == []
    assert contracts["holds"] is True
    assert goal05["contracts"]["holds"] is True


def test_provenance_campaigns_closed_and_no_goal10_deferral() -> None:
    snapshot = provenance_snapshot(REPO)
    assert snapshot["transplant"]["pending"] == 0
    assert snapshot["transplant"]["claimed"] == 0
    assert aplazados_defers_11b_to_goal10(REPO) == []
    report = load_report(REPO)
    assert report["deferred_to_goal10"] == []


def test_validator_rejects_missing_row_bad_next_and_goal10_deferral() -> None:
    report = load_report(REPO)
    missing = dict(report)
    missing["criteria"] = list(report["criteria"])[1:]
    errors = validate_report(missing, repo=REPO)
    assert any("missing criteria" in item for item in errors)

    remitting = dict(report)
    remitting["next_human_prompt"] = OWNER_PROMPT
    errors = validate_report(remitting, repo=REPO)
    assert any("09.5.11B" in item or "next_human_prompt" in item for item in errors)

    to_ten = dict(report)
    to_ten["next_human_prompt"] = "documentacion/sprints/10.0_BASE_VERDE.md"
    to_ten["deferred_to_goal10"] = ["census"]
    errors = validate_report(to_ten, repo=REPO)
    assert any("Goal 10" in item or "10.0" in item or "deferred" in item for item in errors)

    poisoned = dict(report)
    poisoned["corpus"] = dict(report["corpus"], sha256="0" * 64)
    errors = validate_report(poisoned, repo=REPO)
    assert any("corpus sha" in item for item in errors)
