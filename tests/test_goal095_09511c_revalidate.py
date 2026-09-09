"""Goal 09.5.11C — load the shipped revalidation matrix, not a fixture copy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind.first_signal import PATH_MODEL, PATH_RECOGNIZER, should_emit_early
from scripts.goal095_09511c_revalidate import (
    CAMPAIGN_REL,
    HANDOFF_REL,
    LEDGER_REL,
    MARKDOWN_REL,
    NEXT_PROMPT,
    OWNER_PROMPT,
    SCHEMA,
    SYNTHESIS_REL,
    VERSION,
    EnvironmentFailure,
    aplazados_defers_11c_to_goal10,
    in_scope_source_skips,
    live_first_signal,
    live_mission_chains,
    live_r6,
    live_voice_engines,
    load_report,
    provenance_snapshot,
    report_path,
    required_criterion_ids,
    validate_report,
)

REPO = Path(__file__).resolve().parents[1]


def test_shipped_09511c_report_is_the_repo_artifact() -> None:
    path = report_path(REPO)
    assert path == REPO / SYNTHESIS_REL
    assert path.is_file()
    assert path.read_text(encoding="utf-8").startswith("{")
    report = load_report(REPO)
    assert report["schema"] == SCHEMA
    assert report["version"] == VERSION
    assert str(report["reproducibility"]["result"]).strip()
    assert report["next_human_prompt"] == NEXT_PROMPT
    ledger = json.loads((REPO / LEDGER_REL).read_text(encoding="utf-8"))
    assert ledger["next_human_prompt"] == NEXT_PROMPT
    assert str((ledger.get("full_gate") or {}).get("result") or "").strip()
    assert (REPO / LEDGER_REL).is_file()
    assert (REPO / MARKDOWN_REL).is_file()
    assert (REPO / HANDOFF_REL).is_file()
    assert (REPO / CAMPAIGN_REL).is_file()


def test_shipped_09511c_matrix_has_every_07_09_row_and_names_12() -> None:
    report = load_report(REPO)
    errors = validate_report(report, repo=REPO)
    assert errors == []
    present = [row["id"] for row in report["criteria"]]
    assert present == list(required_criterion_ids())
    goals = {row["goal"] for row in report["criteria"]}
    assert {"07", "08", "09", "09.5"} <= goals
    labels = {row["label"] for row in report["criteria"]}
    assert labels <= {"fisica", "fixture"}
    assert "fisica" in labels
    assert "fixture" in labels
    assert report["next_human_prompt"] == NEXT_PROMPT
    assert report["owner_prompt"] == OWNER_PROMPT
    assert OWNER_PROMPT not in report["next_human_prompt"]
    assert "09.5.11C" not in report["next_human_prompt"]
    assert "09.5.11B" not in report["next_human_prompt"]
    assert "10.0" not in report["next_human_prompt"]
    assert report["deferred_to_goal10"] == []
    markdown = (REPO / MARKDOWN_REL).read_text(encoding="utf-8")
    assert "09.5.12_INTEGRAR_Y_REPLANIFICAR.md" in markdown.split(
        "Siguiente prompt humano", 1
    )[1]
    handoff = (REPO / HANDOFF_REL).read_text(encoding="utf-8")
    siguiente = handoff.split("## Siguiente accion recomendada", 1)[1]
    assert (
        "09.5.12_INTEGRAR_Y_REPLANIFICAR.md" in siguiente
        or "10.0_BASE_VERDE.md" in siguiente
    )
    assert "09.5.11C_REVALIDAR_07_09.md" not in siguiente


def test_live_planner_veto_and_r6_postconditions() -> None:
    chains = live_mission_chains()
    assert chains["all_hold"] is True
    assert chains["languages"] == ["es", "en", "es_en"]
    for chain in chains["chains"]:
        assert chain["operations"] == ["app.open", "input.visible.click"]
        assert chain["step_count"] == 2
        assert chain["open_args"]["appId"] == "Steam"
        assert chain["unresolved"] is False
    assert chains["halt"]["holds"] is True
    assert chains["halt"]["veto_mode"] == "recovery"
    assert chains["halt"]["veto_reason"] == "unresolved_compound_effects"
    assert chains["halt"]["veto_effects"] == []
    sealed = live_r6(REPO)
    assert sealed["holds"] is True
    assert sealed["orphan"] == 0
    assert sealed["unverified_successes"] == []
    assert sealed["reuse_forbidden"] is True
    report = load_report(REPO)
    assert report["holdouts"]["missions"]["holds"] is True
    assert report["holdouts"]["missions"]["r6"]["orphan"] == 0


def test_live_first_signal_is_conditional_and_never_asserts() -> None:
    assert should_emit_early(PATH_RECOGNIZER) is False
    assert should_emit_early(PATH_MODEL) is True
    live = live_first_signal()
    assert live["holds"] is True
    assert live["asserted_result"] is False
    assert live["payload_type"] == "turn.signal"
    assert live["languages_differ"] is True
    assert live["listo_in_early"] is False
    report = load_report(REPO)
    assert report["holdouts"]["first_signal"]["live"]["asserted_result"] is False
    assert report["holdouts"]["first_signal"]["holds"] is True


def test_live_wake_stt_tts_resolvers_and_noise_do_not_fire() -> None:
    try:
        engines = live_voice_engines()
    except EnvironmentFailure as error:
        pytest.fail(f"FALLO_DE_AMBIENTE: {error}")
    assert engines["stt_complete"] is True
    assert engines["tts_present"] is True
    assert engines["tts_neural"] is True
    assert engines["wake_onnx_present"] is True
    assert engines["noise_false_activation"] is False
    assert engines["doubtful_question"] is True
    assert engines["doubtful_command"] is False
    assert engines["holds"] is True
    report = load_report(REPO)
    assert report["holdouts"]["voice"]["holds"] is True
    campaigns = report["holdouts"]["campaigns"]
    assert campaigns["holds"] is True
    assert campaigns["in_scope_failures_or_skips"] == []


def test_in_scope_tests_do_not_skip_missing_assets() -> None:
    assert in_scope_source_skips(REPO) == []
    voice = (REPO / "tests" / "test_goal09_voice_engines.py").read_text(encoding="utf-8")
    assert "pytest.skip" not in voice
    assert "resolve_stt_directory" in voice
    assert "FALLO_DE_AMBIENTE" in voice


def test_provenance_campaigns_closed_and_no_goal10_deferral() -> None:
    snapshot = provenance_snapshot(REPO)
    assert snapshot["transplant"]["pending"] == 0
    assert snapshot["transplant"]["claimed"] == 0
    assert aplazados_defers_11c_to_goal10(REPO) == []
    report = load_report(REPO)
    assert report["deferred_to_goal10"] == []
    assert report["holdouts"]["not_rerun"]
    ids = {item["id"] for item in report["holdouts"]["not_rerun"]}
    assert "r6-execution" in ids
    assert "steam-physical" in ids


def test_validator_rejects_missing_row_bad_next_and_goal10_deferral() -> None:
    report = load_report(REPO)
    missing = dict(report)
    missing["criteria"] = list(report["criteria"])[1:]
    errors = validate_report(missing, repo=REPO)
    assert any("missing criteria" in item for item in errors)

    remitting = dict(report)
    remitting["next_human_prompt"] = OWNER_PROMPT
    errors = validate_report(remitting, repo=REPO)
    assert any("09.5.11C" in item or "next_human_prompt" in item for item in errors)

    to_ten = dict(report)
    to_ten["next_human_prompt"] = "documentacion/sprints/10.0_BASE_VERDE.md"
    to_ten["deferred_to_goal10"] = ["steam"]
    errors = validate_report(to_ten, repo=REPO)
    assert any("Goal 10" in item or "10.0" in item or "deferred" in item for item in errors)

    unlabeled = dict(report)
    rows = [dict(report["criteria"][0]), *report["criteria"][1:]]
    rows[0] = dict(rows[0], label="skip")
    unlabeled["criteria"] = rows
    errors = validate_report(unlabeled, repo=REPO)
    assert any("label" in item for item in errors)
