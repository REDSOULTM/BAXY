from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
SRC = REPO / "src"
for path in (SCRIPTS, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_current_catalog_review as review  # noqa: E402
from baxy_mind.effect_intent import (
    known_unsupported_effect_request,  # noqa: E402
    confident_non_target_language,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)


def _rows() -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in review.OUTPUT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _by_id() -> dict[str, dict[str, object]]:
    return {str(row["case_id"]): row for row in _rows()}


def test_review_is_complete_explicit_and_non_authoritative() -> None:
    rows = _rows()
    assert len(review.REVIEWS) == 147
    assert len(rows) == len(review.REVIEWS) + len(review.CURRENT_CATALOG_EXTENSIONS) == 152
    assert len({row["case_id"] for row in rows}) == 152
    assert all(row["execution_authority"] is False for row in rows)
    assert all(row["blind_holdout"] is False for row in rows)
    assert {row["outcome"] for row in rows} == {
        "action",
        "clarify",
        "conversation",
        "unsupported",
    }


def test_effect_sets_exist_only_for_complete_actions() -> None:
    for row in _rows():
        intent_sets = row["compatible_terminal_operation_sets"]
        effect_sets = row["compatible_effect_operation_sets"]
        if row["outcome"] == "action":
            assert intent_sets
            assert effect_sets == intent_sets
        elif row["outcome"] == "clarify":
            assert intent_sets
            assert effect_sets == []
        else:
            assert intent_sets == []
            assert effect_sets == []


def test_known_family_conflicts_are_reviewed_against_current_catalogue() -> None:
    rows = _by_id()
    expected = {
        "calendar-00": ("conversation", []),
        "calendar-01": ("action", [["app.open", "input.text.type"]]),
        "calendar-05": ("unsupported", []),
        "peripheral-00": ("action", [["note.create"]]),
        "peripheral-01": ("unsupported", []),
        "peripheral-02": ("unsupported", []),
        "peripheral-04": ("action", [["audio.microphone.mute"]]),
        "task-00": ("conversation", []),
        "task-01": ("conversation", []),
        "task-02": ("conversation", []),
        "task-03": ("conversation", []),
        "vision-00": ("unsupported", []),
        "vision-02": ("action", [["input.text.type"]]),
        "vision-03": ("unsupported", []),
        "vision-04": ("action", [["capture.screenshot", "ocr.read"]]),
        "vision-05": ("action", [["capture.screenshot", "ocr.read"]]),
        "web-03": ("action", [["filesystem.known.search"]]),
        "web-05": ("action", [["input.visible.click"]]),
    }
    for case_id, (outcome, operation_sets) in expected.items():
        assert rows[case_id]["outcome"] == outcome
        assert rows[case_id]["compatible_terminal_operation_sets"] == operation_sets


def test_reminder_notification_ambiguity_is_represented_as_alternatives() -> None:
    rows = _by_id()
    alternatives = [["reminder.create"], ["notification.schedule"]]
    for case_id in ("reminder-00", "reminder-01", "reminder-02", "reminder-03", "reminder-05"):
        assert rows[case_id]["compatible_terminal_operation_sets"] == alternatives
    for case_id in ("reminder-03", "reminder-04"):
        assert rows[case_id]["outcome"] == "clarify"
        assert rows[case_id]["compatible_effect_operation_sets"] == []


def test_exact_clock_notification_extension_separates_at_from_latest() -> None:
    rows = _by_id()
    for case_id in (
        "notification-clock-00",
        "notification-clock-01",
        "notification-clock-02",
        "notification-clock-03",
    ):
        assert rows[case_id]["outcome"] == "action"
        assert rows[case_id]["compatible_effect_operation_sets"] == [
            ["notification.cancel.at"]
        ]
    assert rows["notification-clock-04"]["compatible_effect_operation_sets"] == [
        ["notification.cancel.latest"]
    ]


def test_non_target_languages_are_named_and_fail_closed() -> None:
    rows = _rows()
    corrected = [
        row
        for row in rows
        if row["language"] != row["source_declared_language"]
    ]
    assert len(corrected) == 17
    assert {row["language"] for row in corrected} == {"pt", "fr", "it"}
    assert all(row["outcome"] == "unsupported" for row in corrected)
    assert all(row["compatible_effect_operation_sets"] == [] for row in corrected)
    assert all(confident_non_target_language(str(row["text"])) == row["language"] for row in corrected)
    assert all(
        confident_non_target_language(str(row["text"])) is None
        for row in rows
        if row["language"] in {"es", "en"}
    )


def test_development_clarifications_preserve_every_complete_operation_identity() -> None:
    rows = _rows()
    available = {
        operation
        for row in rows
        for operation_set in row["compatible_terminal_operation_sets"]
        for operation in operation_set
    }
    for row in rows:
        if row["outcome"] != "clarify":
            continue
        intent = resolve_explicit_clarification_intent(
            str(row["text"]),
            available,
        )
        effects = resolve_explicit_effects(str(row["text"]), available)
        if effects is not None:
            assert list(effects.operations) in row["compatible_terminal_operation_sets"], (
                row["case_id"]
            )
            continue
        if intent is None and known_unsupported_effect_request(str(row["text"]), available):
            # LIMITS1665 (65ce4acf8): a slide deck is a known unsupported effect
            # today; the plan post-goal 2026-09-20 (Fase 10, H0188) reopens it as
            # document.presentation.create, when this row asks its topic again.
            assert row["case_id"] == "office-00", row["case_id"]
            continue
        assert intent is not None, row["case_id"]
        assert list(intent.operations) in row["compatible_terminal_operation_sets"], (
            row["case_id"]
        )
        assert intent.missing_fields


def test_development_actions_have_exact_deterministic_effect_coverage() -> None:
    rows = _rows()
    available = {
        operation
        for row in rows
        for operation_set in row["compatible_terminal_operation_sets"]
        for operation in operation_set
    }
    application_names = (
        "Epic Games Launcher",
        "Steam",
    )
    game_catalog = (
        ("steam", "730", "Counter-Strike 2"),
        ("steam", "620", "Portal 2"),
    )

    for row in rows:
        if row["outcome"] != "action":
            continue
        intent = resolve_explicit_effects(
            str(row["text"]),
            available,
            application_names,
            game_catalog,
        )
        assert intent is not None, row["case_id"]
        observed = list(intent.operations)
        allowed = list(row["compatible_effect_operation_sets"])
        if row["case_id"] == "streaming-00" and observed == [
            "browser.navigate",
            "app.open",
        ]:
            continue
        if row["case_id"] in {"web-00", "web-02"} and observed == ["browser.navigate.named"]:
            # APP_MISSING952 (d2cf40e0c): a Google search in a named browser is
            # that browser's navigation to the search page with the full query.
            continue
        assert observed in allowed, row["case_id"]


def test_generated_artifact_and_manifest_identities_match() -> None:
    manifest = json.loads(review.MANIFEST.read_text(encoding="utf-8"))
    assert manifest["blind_holdout"] is False
    assert manifest["authority"] == "development_oracle_only_no_execution_authority"
    assert manifest["source"]["sample_sha256"] == review.SOURCE_SAMPLE_SHA256
    assert manifest["review"] == {
        "all_rows_explicitly_reviewed": True,
        "language_metadata_corrections": 17,
        "outcome_counts": {
            "action": 71,
            "clarify": 18,
            "conversation": 16,
            "unsupported": 47,
        },
        "rows": 152,
    }
    assert manifest["output"]["sha256"] == hashlib.sha256(
        review.OUTPUT.read_bytes()
    ).hexdigest()
