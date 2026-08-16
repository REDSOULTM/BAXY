"""Validate exact literal payload fidelity across the reviewed current catalogue.

The backing probe traverses ``turn.decide`` and the product ``arguments`` or
``plan`` request for every reviewed case. This probe adds an independent,
manually curated argument oracle for all seventy presentable action cases. It
checks exact non-temporal arguments, plan modes and dependencies, and bounded
clock semantics. No request is sent to Core or to a provider.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    probe_current_catalog_ready_pipeline as ready,
)
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    file_sha256,
)
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


OUTPUT = REPO / "artifacts/fixes/current_catalog_argument_fidelity_r1.json"
BACKING_OUTPUT = (
    REPO
    / "artifacts/research/current_catalog_ready_pipeline_r15_argument_fidelity.json"
)
BACKING_AUDIT = BACKING_OUTPUT.with_suffix(".raw.jsonl")


EXACT_LITERAL_ARGUMENTS: dict[str, dict[str, dict[str, Any]]] = {
    "app-00": {"app.open": {"appId": "Epic Games Launcher"}},
    "app-01": {
        "app.open": {"appId": "windows.notepad"},
        "window.active": {},
    },
    "app-02": {"app.open": {"appId": "Steam"}},
    "app-03": {"app.open": {"appId": "Steam"}},
    "app-04": {"app.open": {"appId": "Steam"}},
    "app-05": {"app.open": {"appId": "Steam"}},
    "audio-02": {"audio.volume.adjust": {"amount": 1, "direction": "down"}},
    "audio-03": {"audio.volume.adjust": {"amount": 10, "direction": "down"}},
    "audio-05": {"audio.volume": {"level": 10}},
    "bluetooth-01": {"bluetooth.radio.set": {"state": True}},
    "bluetooth-02": {"bluetooth.radio.set": {"state": False}},
    "bluetooth-04": {"bluetooth.radio.set": {"state": False}},
    "bluetooth-05": {"bluetooth.radio.set": {"state": True}},
    "browser-01": {"browser.navigate": {"url": "https://github.com"}},
    "browser-02": {
        "web.search": {"query": "página de Steam de Marvel Rivals"},
    },
    "browser-03": {"web.search": {"query": "página de descargas de Python"}},
    "browser-04": {"web.search": {"query": "página oficial de OpenAI"}},
    "calendar-01": {
        "app.open": {"appId": "windows.notepad"},
        "input.text.type": {"text": "reunion manana"},
    },
    "capture-00": {"capture.screenshot": {}},
    "capture-03": {"capture.screenshot": {}},
    "clipboard-00": {"clipboard.paste": {}},
    "clipboard-01": {"clipboard.copy": {}},
    "clipboard-04": {
        "app.open": {"appId": "windows.notepad"},
        "clipboard.paste": {},
    },
    "clipboard-05": {"clipboard.read.text": {}},
    "filesystem-01": {"filesystem.file.open.latest": {"folder": "downloads"}},
    "filesystem-02": {"filesystem.file.open.latest": {"folder": "downloads"}},
    "game-01": {"game.launch": {"appId": "730"}},
    "game-05": {"game.catalog.list": {}},
    "message-00": {
        "message.recipient.resolve": {"channel": "whatsapp", "recipient": "amor"}
    },
    "message-01": {
        "message.recipient.resolve": {"channel": "whatsapp", "recipient": "amor"}
    },
    "message-02": {
        "message.recipient.resolve": {"channel": "whatsapp", "recipient": "amor"}
    },
    "message-03": {
        "message.recipient.resolve": {"channel": "whatsapp", "recipient": "amor"}
    },
    "message-04": {
        "message.recipient.resolve": {"channel": "whatsapp", "recipient": "amor"}
    },
    "message-05": {
        "message.recipient.resolve": {
            "channel": "whatsapp",
            "recipient": "enmanuel",
        }
    },
    "note-00": {
        "note.create": {"content": "tengo que comprar pan", "title": "comprar pan"}
    },
    "note-01": {
        "note.create": {
            "content": "tengo que llamar al medico manana",
            "title": "llamar al medico manana",
        }
    },
    "peripheral-00": {
        "note.create": {
            "content": "terminé de configurar el micrófono",
            "title": "configurar el micrófono",
        }
    },
    "peripheral-04": {"audio.microphone.mute": {"state": True}},
    "streaming-00": {
        "browser.navigate": {"url": "https://www.youtube.com/"},
    },
    "streaming-03": {
        "web.search": {
            "query": "Donde puedo ver la pelicula de superman que salio el ano pasado??"
        }
    },
    "streaming-05": {
        "web.search": {"query": "Hablame de emilia perez la pelicula es buena?"}
    },
    "vision-02": {"input.text.type": {"text": "Batman"}},
    "vision-04": {"capture.screenshot": {}},
    "vision-05": {"capture.screenshot": {}},
    "web-00": {
        "web.search": {"query": "mejores teclados mecánicos 2026"},
    },
    "web-01": {"web.search": {"query": "Alan Turing"}},
    "web-02": {"web.search": {"query": "flash"}},
    "web-03": {
        "filesystem.known.search": {"folder": "all_known", "query": "Batman"}
    },
    "web-04": {
        "web.search": {
            "query": "el App ID de Doom Eternal en Steam usando la API publica"
        }
    },
    "web-05": {"input.visible.click": {"label": "Guardar"}},
    "wifi-01": {"wifi.status": {}},
    "wifi-02": {"wifi.disconnect": {}},
    "wifi-03": {"wifi.connect.named": {"profileName": "RV 2"}},
    "wifi-04": {"wifi.ensure.connected": {}, "email.latest.read": {}},
    "wifi-05": {"wifi.connect.named": {"profileName": "la familia"}},
    "window-01": {"window.active": {}},
    "notification-clock-00": {
        "notification.cancel.at": {"hour": 5, "kind": "alarm", "period": "pm"}
    },
    "notification-clock-01": {
        "notification.cancel.at": {"hour": 5, "kind": "alarm", "period": "pm"}
    },
    "notification-clock-02": {
        "notification.cancel.at": {"hour": 5, "kind": "alarm", "period": "pm"}
    },
    "notification-clock-03": {
        "notification.cancel.at": {"hour": 17, "kind": "alarm", "minute": 30}
    },
    "notification-clock-04": {"notification.cancel.latest": {"kind": "alarm"}},
}


TEMPORAL_ARGUMENTS: dict[str, dict[str, Any]] = {
    "notification-00": {
        "operation": "notification.schedule",
        "arguments": {"kind": "alarm", "title": "alarma para las 7 de la maniana"},
        "tomorrow_local_hour": 7,
    },
    "notification-01": {
        "operation": "notification.schedule",
        "arguments": {"kind": "alarm", "title": "alarma para mañana 8am"},
        "tomorrow_local_hour": 8,
    },
    "notification-02": {
        "operation": "notification.schedule",
        "arguments": {"kind": "alarm", "title": "temporizador de 10 minutos"},
        "offset_seconds": 600,
    },
    "notification-04": {
        "operation": "notification.schedule",
        "arguments": {"kind": "alarm", "title": "timer de 5 minutos"},
        "offset_seconds": 300,
    },
    "notification-05": {
        "operation": "notification.schedule",
        "arguments": {"kind": "alarm", "title": "temporizador de diez minutos"},
        "offset_seconds": 600,
    },
    "reminder-00": {
        "operation": "reminder.create",
        "arguments": {"title": "saque la comida"},
        "offset_seconds": 1_200,
    },
    "reminder-01": {
        "operation": "reminder.create",
        "arguments": {"title": "salgo"},
        "offset_seconds": 3_600,
    },
    "reminder-02": {
        "operation": "reminder.create",
        "arguments": {"title": "tomar agua"},
        "offset_seconds": 120,
    },
    "reminder-05": {
        "operation": "reminder.create",
        "arguments": {"title": "tomar agua"},
        "offset_seconds": 3_600,
    },
}


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _observed_steps(row: dict[str, Any]) -> list[dict[str, Any]]:
    downstream = row.get("downstream")
    if not isinstance(downstream, dict):
        return []
    if downstream.get("type") == "arguments.result":
        return [
            {
                "id": "step_1",
                "operation": downstream.get("operation"),
                "arguments": downstream.get("arguments"),
                "argumentsMode": "literal",
                "dependsOn": [],
            }
        ]
    steps = downstream.get("steps")
    return [dict(step) for step in steps] if isinstance(steps, list) else []


def _temporal_errors(
    row: dict[str, Any],
    operation: str,
    arguments: object,
) -> list[str]:
    case_id = str(row["case_id"])
    spec = TEMPORAL_ARGUMENTS[case_id]
    if operation != spec["operation"] or not isinstance(arguments, dict):
        return ["temporal_operation_or_arguments"]
    expected_arguments = dict(spec["arguments"])
    observed_without_due = dict(arguments)
    due = _parse_utc(observed_without_due.pop("dueUtc", None))
    if observed_without_due != expected_arguments:
        return ["temporal_literal_mismatch"]
    started = _parse_utc(row.get("started_at_utc"))
    finished = _parse_utc(row.get("finished_at_utc"))
    if due is None or started is None or finished is None:
        return ["temporal_clock_shape"]
    offset_seconds = spec.get("offset_seconds")
    if isinstance(offset_seconds, int):
        tolerance = timedelta(seconds=8)
        if not (
            started + timedelta(seconds=offset_seconds) - tolerance
            <= due
            <= finished + timedelta(seconds=offset_seconds) + tolerance
        ):
            return ["temporal_relative_offset"]
        return []
    tomorrow_hour = spec.get("tomorrow_local_hour")
    local_started = started.astimezone()
    local_due = due.astimezone()
    if (
        not isinstance(tomorrow_hour, int)
        or local_due.date() != local_started.date() + timedelta(days=1)
        or (local_due.hour, local_due.minute, local_due.second)
        != (tomorrow_hour, 0, 0)
    ):
        return ["temporal_local_clock"]
    return []


def evaluate(backing: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = backing.get("rows")
    if not isinstance(rows, list):
        raise ValueError("backing report has no rows")
    expected_case_ids = set(EXACT_LITERAL_ARGUMENTS) | set(TEMPORAL_ARGUMENTS)
    source_action_ids = {
        str(row["case_id"])
        for row in rows
        if isinstance(row, dict)
        and "ready" in row.get("presentable_expected_outcomes", [])
    }
    if source_action_ids != expected_case_ids:
        raise ValueError(
            "argument oracle coverage mismatch: "
            f"missing={sorted(source_action_ids - expected_case_ids)}, "
            f"stale={sorted(expected_case_ids - source_action_ids)}"
        )

    evaluated: list[dict[str, Any]] = []
    for raw_row in rows:
        if not isinstance(raw_row, dict) or str(raw_row.get("case_id")) not in expected_case_ids:
            continue
        row = dict(raw_row)
        case_id = str(row["case_id"])
        errors: list[str] = []
        if row.get("observed_outcome") != "ready":
            errors.append("not_ready")
        steps = _observed_steps(row)
        if not steps:
            errors.append("missing_steps")
        literal_arguments: dict[str, object] = {}
        for index, step in enumerate(steps, 1):
            step_id = f"step_{index}"
            dependencies = step.get("dependsOn")
            mode = step.get("argumentsMode")
            if step.get("id") != step_id:
                errors.append(f"step_id:{index}")
            if not isinstance(dependencies, list) or any(
                dependency not in {f"step_{prior}" for prior in range(1, index)}
                for dependency in dependencies
            ):
                errors.append(f"dependencies:{index}")
            operation = step.get("operation")
            if not isinstance(operation, str):
                errors.append(f"operation:{index}")
                continue
            if mode == "literal":
                if dependencies:
                    errors.append(f"literal_dependency:{index}")
                literal_arguments[operation] = step.get("arguments")
            elif mode == "after_dependencies":
                if not dependencies or step.get("arguments") is not None:
                    errors.append(f"dependent_arguments:{index}")
            else:
                errors.append(f"arguments_mode:{index}")

        if case_id in TEMPORAL_ARGUMENTS:
            spec = TEMPORAL_ARGUMENTS[case_id]
            expected_operations = {str(spec["operation"])}
            if set(literal_arguments) != expected_operations:
                errors.append("literal_operation_set")
            else:
                operation = str(spec["operation"])
                errors.extend(
                    _temporal_errors(row, operation, literal_arguments[operation])
                )
        else:
            expected = EXACT_LITERAL_ARGUMENTS[case_id]
            if literal_arguments != expected:
                errors.append("literal_arguments_mismatch")
        evaluated.append(
            {
                "case_id": case_id,
                "family": row.get("family"),
                "text": row.get("text"),
                "exact": not errors,
                "errors": errors,
                "literal_arguments": literal_arguments,
                "steps": steps,
            }
        )
    failures = [row for row in evaluated if not row["exact"]]
    return evaluated, failures


def run(args: argparse.Namespace) -> dict[str, Any]:
    for path in (args.output, args.backing_output, args.audit):
        if path.exists():
            raise RuntimeError(f"refusing to overwrite existing artifact: {path}")
    manifest_before = file_sha256(args.runtime_manifest)
    backing = ready.run(output=args.backing_output, audit=args.audit)
    evaluated, failures = evaluate(backing)
    report = {
        "schema": "baxy.current-catalog-argument-fidelity.development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "reviewed_development_exact_literal_arguments_no_blind_holdout",
        "authority": "turn_arguments_plan_only_no_core_no_provider_no_effect",
        "effects_executed": 0,
        "core_or_provider_requests_sent": 0,
        "metrics": {
            "exact": sum(bool(row["exact"]) for row in evaluated),
            "total": len(evaluated),
            "temporal_cases": len(TEMPORAL_ARGUMENTS),
            "non_temporal_cases": len(EXACT_LITERAL_ARGUMENTS),
        },
        "acceptance": {
            "all_presentable_actions_ready": all(
                row.get("observed_outcome") == "ready"
                for row in backing["rows"]
                if "ready" in row.get("presentable_expected_outcomes", [])
            ),
            "all_literal_arguments_exact": not failures,
            "backing_presentable_exact": backing["summary"][
                "presentable_exact_accuracy"
            ]
            == 1.0,
            "runtime_manifest_unchanged": manifest_before
            == file_sha256(args.runtime_manifest),
            "zero_effects": True,
        },
        "source": {
            "probe_sha256": file_sha256(Path(__file__).resolve()),
            "backing_probe_sha256": file_sha256(Path(ready.__file__).resolve()),
            "backing_report": str(args.backing_output),
            "backing_report_sha256": file_sha256(args.backing_output),
        },
        "backing_summary": backing["summary"],
        "failures": failures,
        "rows": evaluated,
    }
    write_json_atomic(args.output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--backing-output", type=Path, default=BACKING_OUTPUT)
    parser.add_argument("--audit", type=Path, default=BACKING_AUDIT)
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        default=DEFAULT_RUNTIME_MANIFEST,
    )
    args = parser.parse_args()
    report = run(args)
    print(
        json.dumps(
            {
                "metrics": report["metrics"],
                "acceptance": report["acceptance"],
                "backing_summary": report["backing_summary"],
                "failures": report["failures"],
                "effects_executed": report["effects_executed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(report["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
