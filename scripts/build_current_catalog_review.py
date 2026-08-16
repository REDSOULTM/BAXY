"""Build the reviewed current-catalogue development oracle.

This repairs the historical 147-case family-prefix corpus without changing or
pretending it is a blind holdout.  Every source row is reviewed against the
compiled authenticated catalogue as an exact action, clarification,
conversation, or unsupported request.  Compatible terminal operation sets are
alternatives, never authority; the generated rows cannot dispatch effects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    current_core_capabilities,
    discover_core,
    write_json_atomic,
)


SOURCE = REPO / "artifacts/fixes/native_predicted_family_qwen3_20260801.json"
SOURCE_SAMPLE_SHA256 = "c8db6a7b32f2ec607edfefd731a59ffb38dc918be3705f2e2fcaeaca0bce3feb"
OUTPUT = REPO / "artifacts/development/current_catalog_review_development.v1.jsonl"
MANIFEST = REPO / "artifacts/development/current_catalog_review_development.v1.manifest.json"


@dataclass(frozen=True)
class Review:
    language: str
    outcome: str
    compatible: tuple[tuple[str, ...], ...]
    basis: str


def action(language: str, *plans: tuple[str, ...], basis: str = "exact_current_catalog_match") -> Review:
    return Review(language, "action", tuple(plans), basis)


def clarify(language: str, *plans: tuple[str, ...], basis: str) -> Review:
    return Review(language, "clarify", tuple(plans), basis)


def conversation(language: str, basis: str) -> Review:
    return Review(language, "conversation", (), basis)


def unsupported(language: str, basis: str) -> Review:
    return Review(language, "unsupported", (), basis)


# Manual semantic review against the compiled catalogue, independent of every
# model prediction recorded in SOURCE.  Keep every case explicit: grouped
# defaults would recreate the family-prefix defect this file removes.
REVIEWS: dict[str, Review] = {
    "app-00": action("es", ("app.open",)),
    "app-01": action("es", ("app.open", "app.close"), basis="explicit_two_step_compound"),
    "app-02": action("es", ("app.open",)),
    "app-03": action("es", ("app.open",)),
    "app-04": action("es", ("app.open",)),
    "app-05": action("es", ("app.open",)),
    "audio-00": unsupported("pt", "outside_es_en_spanglish_language_scope"),
    "audio-01": unsupported("fr", "outside_es_en_spanglish_language_scope"),
    "audio-02": action("es", ("audio.volume.adjust",)),
    "audio-03": action("es", ("audio.volume.adjust",)),
    "audio-04": unsupported("pt", "outside_es_en_spanglish_language_scope"),
    "audio-05": action("es", ("audio.volume",), basis="absolute_level_not_relative_adjustment"),
    "backup-00": clarify("es", ("backup.create", "filesystem.write.text"), basis="missing_file_and_edit_content"),
    "backup-01": clarify("es", ("backup.create", "filesystem.write.text"), basis="ambiguous_env_file_and_setting"),
    "backup-02": unsupported("pt", "outside_es_en_spanglish_language_scope"),
    "backup-03": unsupported("es", "catalogue_cannot_export_backup_to_removable_drive"),
    "backup-04": unsupported("en", "catalogue_has_backup_inventory_but_no_backup_job_log"),
    "bluetooth-00": unsupported("es", "catalogue_controls_radio_and_devices_but_not_settings_ui_navigation"),
    "bluetooth-01": action("es", ("bluetooth.radio.set",)),
    "bluetooth-02": action("es", ("bluetooth.radio.set",)),
    "bluetooth-03": clarify("es", ("bluetooth.device.pair",), basis="missing_device_identity"),
    "bluetooth-04": action("es", ("bluetooth.radio.set",)),
    "bluetooth-05": action("es", ("bluetooth.radio.set",)),
    "browser-00": clarify("es", ("app.open",), basis="default_browser_has_no_authenticated_app_identity"),
    "browser-01": action("es", ("browser.navigate",)),
    "browser-02": action("es", ("web.search", "browser.navigate"), basis="dependent_search_then_navigation"),
    "browser-03": action("es", ("web.search", "browser.navigate"), basis="dependent_search_then_navigation"),
    "browser-04": action("es", ("web.search", "browser.navigate"), basis="dependent_search_then_navigation"),
    "browser-05": unsupported("pt", "outside_es_en_spanglish_language_scope"),
    "calendar-00": conversation("en", "draft_requested_without_send_or_document_effect"),
    "calendar-01": action("es", ("app.open", "input.text.type"), basis="notepad_open_then_literal_typing"),
    "calendar-02": clarify("es", ("calendar.event.create",), basis="event_end_time_missing"),
    "calendar-03": clarify("es", ("calendar.event.create",), basis="event_end_time_missing"),
    "calendar-04": clarify("es", ("calendar.event.create",), basis="event_end_time_missing"),
    "calendar-05": unsupported("es", "catalogue_cannot_compose_new_email"),
    "capture-00": action("es", ("capture.screenshot", "vision.describe"), basis="capture_then_visual_description"),
    "capture-01": conversation("en", "how_to_question_without_action_request"),
    "capture-02": unsupported("pt", "outside_es_en_spanglish_language_scope"),
    "capture-03": action("es", ("capture.screenshot",)),
    "capture-04": unsupported("es", "catalogue_keeps_private_capture_and_cannot_export_to_desktop"),
    "capture-05": unsupported("es", "catalogue_cannot_export_capture_to_desktop"),
    "clipboard-00": action("es", ("clipboard.paste",)),
    "clipboard-01": action("es", ("clipboard.copy",), basis="terminal_copy_with_focus_prerequisites_planned_separately"),
    "clipboard-02": clarify("es", ("clipboard.write.text",), basis="deictic_text_payload_missing"),
    "clipboard-03": clarify("en", ("memory.recall", "clipboard.write.text"), basis="private_email_value_not_grounded"),
    "clipboard-04": action("es", ("app.open", "clipboard.paste"), basis="notepad_open_then_paste"),
    "clipboard-05": action("es", ("clipboard.read.text",)),
    "filesystem-00": unsupported("es", "catalogue_can_read_resolved_text_but_cannot_open_named_known_file"),
    "filesystem-01": action("es", ("filesystem.file.open.latest",)),
    "filesystem-02": action("es", ("filesystem.file.open.latest",)),
    "filesystem-03": unsupported("es", "known_trash_contract_accepts_files_not_named_folders"),
    "filesystem-04": unsupported("es", "write_contract_is_sandbox_confined_not_desktop"),
    "filesystem-05": unsupported("es", "directory_contract_is_sandbox_confined_not_desktop"),
    "game-00": unsupported("es", "catalogue_has_no_steam_big_picture_operation"),
    "game-01": action("es", ("game.launch",)),
    "game-02": action("es", ("game.launch",)),
    "game-03": unsupported("pt", "outside_es_en_spanglish_language_scope"),
    "game-04": unsupported("es", "catalogue_has_no_steam_screenshot_ui_navigation"),
    "game-05": action("es", ("game.catalog.list",)),
    "media-00": unsupported("fr", "outside_es_en_spanglish_language_scope"),
    "media-01": unsupported("fr", "outside_es_en_spanglish_language_scope"),
    "media-02": conversation("es", "question_without_requested_media_effect"),
    "media-03": unsupported("it", "outside_es_en_spanglish_language_scope"),
    "media-04": clarify("es", ("media.play.query",), basis="music_query_missing"),
    "media-05": unsupported("en", "gameplay_outside_authenticated_catalogue"),
    "message-00": action("es", ("message.send",)),
    "message-01": action("es", ("message.send",)),
    "message-02": action("es", ("message.send",)),
    "message-03": action("es", ("message.send",)),
    "message-04": action("es", ("message.send",)),
    "message-05": action("es", ("message.send",)),
    "note-00": action("es", ("note.create",)),
    "note-01": action("es", ("note.create",)),
    "note-02": unsupported("it", "outside_es_en_spanglish_language_scope"),
    "note-03": unsupported("it", "outside_es_en_spanglish_language_scope"),
    "note-04": unsupported("it", "outside_es_en_spanglish_language_scope"),
    "note-05": clarify("es", ("filesystem.known.search", "filesystem.read.text", "filesystem.write.text"), basis="source_file_location_missing"),
    "notification-00": action("es", ("notification.schedule",)),
    "notification-01": action("es", ("notification.schedule",)),
    "notification-02": action("es", ("notification.schedule",)),
    "notification-03": clarify(
        "es",
        ("notification.cancel.at",),
        basis="alarm_identity_or_clock_missing",
    ),
    "notification-04": action("es", ("notification.schedule",)),
    "notification-05": action("es", ("notification.schedule",)),
    "ocr-00": conversation("es", "capability_comment_without_action_request"),
    "office-00": clarify("en", ("office.document.create",), basis="document_topic_and_title_missing"),
    "office-01": conversation("es", "work_loss_observation_without_action_request"),
    "office-02": conversation("es", "complaint_and_location_question_without_document_identity"),
    "office-03": unsupported("pt", "outside_es_en_spanglish_language_scope"),
    "office-04": unsupported("es", "document_contract_cannot_author_six_slide_presentation_content"),
    "office-05": unsupported("es", "document_contract_cannot_author_seven_slide_presentation_content"),
    "peripheral-00": action("es", ("note.create",), basis="note_request_not_peripheral_management"),
    "peripheral-01": unsupported("es", "catalogue_cannot_change_default_microphone"),
    "peripheral-02": unsupported("es", "catalogue_can_mute_default_endpoint_not_discord_scoped_microphone"),
    "peripheral-03": unsupported("en", "catalogue_cannot_set_default_printer"),
    "peripheral-04": action("es", ("audio.microphone.mute",), basis="default_microphone_mute"),
    "reminder-00": action("es", ("reminder.create",), ("notification.schedule",), basis="durable_or_audible_reminder_both_semantically_compatible"),
    "reminder-01": action("es", ("reminder.create",), ("notification.schedule",), basis="durable_or_audible_reminder_both_semantically_compatible"),
    "reminder-02": action("es", ("reminder.create",), ("notification.schedule",), basis="explicit_reminder_can_be_durable_or_audible"),
    "reminder-03": clarify(
        "es",
        ("reminder.create",),
        ("notification.schedule",),
        basis="reminder_content_missing",
    ),
    "reminder-04": clarify("es", ("reminder.create",), basis="reminder_due_time_missing"),
    "reminder-05": action("es", ("reminder.create",), ("notification.schedule",), basis="explicit_reminder_can_be_durable_or_audible"),
    "routine-00": unsupported("es", "habit_tracking_outside_bounded_routine_contract"),
    "routine-01": unsupported("es", "scheduled_time_routine_outside_phrase_trigger_contract"),
    "routine-02": unsupported("es", "habit_tracking_outside_bounded_routine_contract"),
    "routine-03": unsupported("pt", "outside_es_en_spanglish_language_scope"),
    "streaming-00": action("es", ("browser.navigate",), basis="youtube_url_navigation_not_streaming_resource_contract"),
    "streaming-01": clarify("es", ("browser.navigate.named",), basis="requested_browser_known_but_current_video_url_missing"),
    "streaming-02": unsupported("es", "missing_title_and_disney_service_not_in_authenticated_streaming_contract"),
    "streaming-03": action("es", ("web.search",), basis="availability_information_request"),
    "streaming-04": unsupported("es", "catalogue_cannot_select_ordinal_youtube_result"),
    "streaming-05": action("es", ("web.search",), basis="current_movie_information_and_reviews"),
    "system-00": conversation("es", "engineering_context_fragment_not_machine_action"),
    "system-01": conversation("es", "engineering_followup_not_machine_action"),
    "system-02": conversation("es", "technology_comparison_not_current_machine_status"),
    "system-03": conversation("es", "knowledge_explanation_not_machine_status"),
    "system-04": unsupported("es", "catalogue_cannot_attribute_gpu_usage_to_processes"),
    "system-05": conversation("es", "state_observation_without_request"),
    "task-00": conversation("es", "latency_constraint_not_local_task_record"),
    "task-01": conversation("en", "preference_followup_not_local_task_record"),
    "task-02": conversation("es", "engineering_session_audit_not_local_task_record"),
    "task-03": conversation("es", "progress_question_not_local_task_record"),
    "task-04": unsupported("es", "unbounded_ambiguous_enable_everything_request"),
    "task-05": conversation("es", "engineering_instruction_not_local_task_record"),
    "vision-00": unsupported("es", "catalogue_cannot_open_display_settings_ui"),
    "vision-01": unsupported("es", "catalogue_has_no_camera_capture_operation"),
    "vision-02": action("es", ("input.text.type",), basis="literal_typing_into_visible_search_control"),
    "vision-03": unsupported("es", "catalogue_has_no_screen_recording_operation"),
    "vision-04": action("es", ("capture.screenshot", "ocr.read"), basis="capture_then_local_ocr"),
    "vision-05": action("es", ("capture.screenshot", "ocr.read"), basis="capture_then_local_ocr"),
    "web-00": action("es", ("web.search", "browser.navigate.named"), basis="search_then_named_browser_navigation"),
    "web-01": action("es", ("web.search", "browser.navigate"), basis="search_then_navigation"),
    "web-02": action("es", ("web.search", "browser.navigate.named"), basis="search_then_named_browser_navigation"),
    "web-03": action("es", ("filesystem.known.search",), basis="local_file_search_not_web_search"),
    "web-04": action("es", ("web.search",)),
    "web-05": action("es", ("input.visible.click",), basis="visible_button_click_not_web_search"),
    "wifi-00": unsupported("pt", "outside_es_en_spanglish_language_scope"),
    "wifi-01": action("es", ("wifi.status",)),
    "wifi-02": action("es", ("wifi.disconnect",)),
    "wifi-03": action("es", ("wifi.connect.named",)),
    "wifi-04": action("es", ("wifi.ensure.connected", "email.latest.read"), basis="dependent_connectivity_check_then_email_read"),
    "wifi-05": action("es", ("wifi.connect.named",)),
    "window-00": unsupported("es", "catalogue_has_no_incognito_window_operation"),
    "window-01": action("es", ("app.close",), basis="active_window_resolution_is_planner_prerequisite"),
    "window-02": unsupported("pt", "outside_es_en_spanglish_language_scope"),
    "window-03": clarify("es", ("app.open",), basis="application_identity_missing"),
    "window-04": unsupported("es", "catalogue_has_no_drag_and_drop_operation"),
    "window-05": clarify("es", ("window.move",), basis="target_window_and_exact_coordinates_missing"),
}


# Operations added after the historical family-prefix sample receive explicit
# development rows here.  They are not inserted into or presented as part of
# the frozen historical source, and they remain non-authoritative/non-blind.
CURRENT_CATALOG_EXTENSIONS: tuple[tuple[str, str, Review], ...] = (
    (
        "notification-clock-00",
        "Get rid of the five p.m. alarm",
        action("en", ("notification.cancel.at",), basis="exact_clock_alarm_identity"),
    ),
    (
        "notification-clock-01",
        "Quita la alarma de las cinco de la tarde",
        action("es", ("notification.cancel.at",), basis="exact_clock_alarm_identity"),
    ),
    (
        "notification-clock-02",
        "Quita my five p.m. alarm",
        action(
            "spanglish",
            ("notification.cancel.at",),
            basis="exact_clock_alarm_identity",
        ),
    ),
    (
        "notification-clock-03",
        "Remove the 17:30 alarm",
        action("en", ("notification.cancel.at",), basis="exact_clock_alarm_identity"),
    ),
    (
        "notification-clock-04",
        "Cancel the latest alarm",
        action("en", ("notification.cancel.latest",), basis="latest_alarm_identity"),
    ),
)


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def load_source() -> list[dict[str, Any]]:
    report = json.loads(SOURCE.read_text(encoding="utf-8"))
    sample = report.get("frozen_sample")
    if not isinstance(sample, list) or _canonical_hash(sample) != SOURCE_SAMPLE_SHA256:
        raise RuntimeError("historical frozen sample identity changed")
    return [dict(row) for row in sample]


def build_rows(
    sample: Iterable[dict[str, Any]],
    capabilities: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    source_rows = list(sample)
    source_ids = {str(row["case_id"]) for row in source_rows}
    if source_ids != set(REVIEWS) or len(source_ids) != len(source_rows):
        missing = sorted(source_ids - set(REVIEWS))
        stale = sorted(set(REVIEWS) - source_ids)
        raise RuntimeError(f"review coverage mismatch; missing={missing}, stale={stale}")
    capability_rows = sorted(
        (
            {
                "name": str(item["name"]),
                "description": str(item["description"]),
                "argumentsSchema": item["argumentsSchema"],
                "risk": str(item["risk"]),
            }
            for item in capabilities
        ),
        key=lambda item: item["name"],
    )
    catalog_names = {item["name"] for item in capability_rows}
    catalog_sha256 = _canonical_hash(capability_rows)
    output: list[dict[str, Any]] = []
    allowed_languages = {"es", "en", "spanglish", "pt", "fr", "it"}
    allowed_outcomes = {"action", "clarify", "conversation", "unsupported"}
    for source in source_rows:
        case_id = str(source["case_id"])
        review = REVIEWS[case_id]
        if review.language not in allowed_languages or review.outcome not in allowed_outcomes:
            raise RuntimeError(f"invalid review enum for {case_id}")
        flat_operations = {
            operation for plan in review.compatible for operation in plan
        }
        missing_operations = sorted(flat_operations - catalog_names)
        if missing_operations:
            raise RuntimeError(
                f"review {case_id} names unauthenticated operations: {missing_operations}"
            )
        if review.outcome in {"action", "clarify"} and not review.compatible:
            raise RuntimeError(f"review {case_id} needs compatible operations")
        if review.outcome in {"conversation", "unsupported"} and review.compatible:
            raise RuntimeError(f"review {case_id} must not carry operations")
        effect_sets = review.compatible if review.outcome == "action" else ()
        output.append(
            {
                "schema": "baxy.current-catalog-development-review.v1",
                "case_id": case_id,
                "text": str(source["text"]),
                "language": review.language,
                "source_declared_language": str(source["language"]),
                "source_historical_family": str(source["family"]),
                "source_historical_label": str(source["label"]),
                "outcome": review.outcome,
                "compatible_terminal_operation_sets": [
                    list(plan) for plan in review.compatible
                ],
                "compatible_effect_operation_sets": [
                    list(plan) for plan in effect_sets
                ],
                "basis": review.basis,
                "execution_authority": False,
                "blind_holdout": False,
                "source_case_sha256": _canonical_hash(source),
                "catalog_sha256": catalog_sha256,
            }
        )
    for case_id, text, review in CURRENT_CATALOG_EXTENSIONS:
        flat_operations = {
            operation for plan in review.compatible for operation in plan
        }
        missing_operations = sorted(flat_operations - catalog_names)
        if missing_operations:
            raise RuntimeError(
                f"extension {case_id} names unauthenticated operations: {missing_operations}"
            )
        source = {
            "case_id": case_id,
            "text": text,
            "language": review.language,
            "family": "current_catalog_extension",
            "label": "current_catalog_extension",
        }
        output.append(
            {
                "schema": "baxy.current-catalog-development-review.v1",
                "case_id": case_id,
                "text": text,
                "language": review.language,
                "source_declared_language": review.language,
                "source_historical_family": "current_catalog_extension",
                "source_historical_label": "current_catalog_extension",
                "outcome": review.outcome,
                "compatible_terminal_operation_sets": [
                    list(plan) for plan in review.compatible
                ],
                "compatible_effect_operation_sets": [
                    list(plan) for plan in review.compatible
                ],
                "basis": review.basis,
                "execution_authority": False,
                "blind_holdout": False,
                "source_case_sha256": _canonical_hash(source),
                "catalog_sha256": catalog_sha256,
            }
        )
    return output, catalog_sha256


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )
    path.write_text(payload, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    source = load_source()
    rows, catalog_sha256 = build_rows(source, capabilities)
    write_jsonl(args.output, rows)
    output_sha256 = hashlib.sha256(args.output.read_bytes()).hexdigest()
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["outcome"])] = counts.get(str(row["outcome"]), 0) + 1
    language_corrections = sum(
        row["language"] != row["source_declared_language"] for row in rows
    )
    manifest = {
        "schema": "baxy.current-catalog-development-review-manifest.v1",
        "authority": "development_oracle_only_no_execution_authority",
        "blind_holdout": False,
        "source": {
            "path": str(SOURCE.relative_to(REPO)),
            "sample_rows": len(source),
            "sample_sha256": SOURCE_SAMPLE_SHA256,
            "current_catalog_extension_rows": len(CURRENT_CATALOG_EXTENSIONS),
        },
        "catalog": {
            "operations": len(capabilities),
            "sha256": catalog_sha256,
        },
        "review": {
            "rows": len(rows),
            "outcome_counts": dict(sorted(counts.items())),
            "language_metadata_corrections": language_corrections,
            "all_rows_explicitly_reviewed": (
                len(rows) == len(REVIEWS) + len(CURRENT_CATALOG_EXTENSIONS)
                and len(REVIEWS) == 147
            ),
        },
        "output": {
            "path": str(args.output.resolve()),
            "bytes": args.output.stat().st_size,
            "sha256": output_sha256,
        },
    }
    write_json_atomic(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
