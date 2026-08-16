"""Exercise BAXY external adapters through the real JSONL core boundary.

The default gate uses read-only observations plus reversible browser, Office,
capture/OCR, and Spotify checks. It never pairs hardware, changes Wi-Fi or
settings, prints, scans, installs/cancels Steam content, or creates cloud events.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_layout import load_build_layout  # noqa: E402

BUILD_LAYOUT = load_build_layout(ROOT)
CORE = BUILD_LAYOUT.core_executable(ROOT)
OUTPUT = ROOT / "artifacts/planner_recovery/external_adapters_gate_v2.json"


def main() -> None:
    run_id = uuid.uuid4().hex
    environment = os.environ.copy()
    data_root = Path(environment["LOCALAPPDATA"]) / "BAXY" / ("external-gate-" + run_id)
    environment["BAXY_DATA_DIR"] = str(data_root)
    process = subprocess.Popen(
        [str(CORE)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    hello = receive(process)
    cases: list[dict] = []

    def invoke(name: str, arguments: dict) -> dict:
        mission = str(uuid.uuid4())
        invocation = str(uuid.uuid4())
        request = {
            "type": "operation.request",
            "requestId": str(uuid.uuid4()),
            "missionId": mission,
            "invocationId": invocation,
            "operation": name,
            "arguments": arguments,
        }
        response = call(process, request)
        if response.get("errorCode") == "confirmation_required":
            request["requestId"] = str(uuid.uuid4())
            request["confirmationToken"] = response["result"]["token"]
            response = call(process, request)
        return response

    def record(label: str, operation: str, arguments: dict) -> dict:
        response = invoke(operation, arguments)
        cases.append(
            {
                "case": label,
                "operation": operation,
                "status": response.get("status"),
                "verified": response.get("verified"),
                "error": response.get("errorCode"),
                "effect_may_have_occurred": response.get("effectMayHaveOccurred", False),
                "result": sanitize_result(operation, response.get("result")),
            }
        )
        write_checkpoint(cases, len(hello["capabilities"]), complete=False)
        return response

    try:
        steam = record("steam_catalog", "game.catalog.list", {"limit": 100})
        games = (steam.get("result") or {}).get("games") or []
        if games:
            record("steam_status", "game.install.status", {"appId": games[0]["appId"]})
        record(
            "fall_guys_installation_inventory",
            "game.installed.named",
            {"provider": "any", "title": "Fall Guys"},
        )
        record(
            "fortnite_epic_installation_inventory",
            "game.installed.named",
            {"provider": "epic", "title": "Fortnite"},
        )
        record("bluetooth_inventory", "bluetooth.device.list", {})
        record("peripheral_inventory", "peripheral.list", {})
        record("mouse_inventory", "peripheral.list", {"kind": "mouse"})
        record("scanner_inventory", "peripheral.list", {"kind": "scanner"})
        record("wifi_profiles", "wifi.profile.list", {})
        record("notification_diagnostics", "notification.diagnose", {})
        record("escape_key", "input.key.press", {"key": "escape"})
        record("spanish_keyboard_layout", "input.keyboard.layout", {"language": "spanish"})
        record("keyboard_layout_status", "input.keyboard.status", {})
        microphone = record(
            "microphone_mute_probe", "audio.microphone.mute", {"state": True}
        )
        microphone_baseline = (microphone.get("result") or {}).get("baselineMuted")
        if microphone_baseline is True:
            record("microphone_unmute_probe", "audio.microphone.mute", {"state": False})
            record("microphone_restore_muted", "audio.microphone.mute", {"state": True})
        elif microphone_baseline is False:
            record("microphone_restore_unmuted", "audio.microphone.mute", {"state": False})
        record("web_search", "web.search", {"query": "OpenAI", "limit": 3})
        record("browser_navigation", "browser.navigate", {"url": "https://example.com/"})
        record("browser_reload", "browser.control", {"action": "reload"})
        record(
            "browser_video_navigation",
            "browser.navigate",
            {"url": "https://www.w3schools.com/html/mov_bbb.mp4"},
        )
        record("browser_video_fullscreen", "browser.control", {"action": "fullscreen_video"})
        record("browser_fullscreen_exit", "input.key.press", {"key": "escape"})
        record(
            "streaming_navigation",
            "streaming.navigate",
            {"service": "youtube", "resourceUri": "https://www.youtube.com/results?search_query=BAXY+gate"},
        )
        record("youtube_playback", "media.play.youtube", {"query": "gatos"})

        capture = record("screen_capture", "capture.screenshot", {})
        capture_id = (capture.get("result") or {}).get("captureId")
        if capture_id:
            record("windows_ocr", "ocr.read", {"captureId": capture_id, "language": None})

        now = datetime.now(timezone.utc)
        record(
            "calendar_list",
            "calendar.event.list",
            {
                "startUtc": now.isoformat().replace("+00:00", "Z"),
                "endUtc": (now + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            },
        )
        record("outlook_latest_email_read", "email.latest.read", {})
        document = record(
            "office_create",
            "office.document.create",
            {"format": "docx", "title": "BAXY external adapter gate " + run_id[:8]},
        )
        document_id = (document.get("result") or {}).get("documentId")
        if document_id:
            record("office_read", "office.document.read", {"documentId": document_id})

        record(
            "spotify_query_selection",
            "media.play.query",
            {"provider": "spotify", "query": "jazz"},
        )
        record(
            "spotify_exact_selection",
            "media.play.exact",
            {"provider": "spotify", "title": "Billie Jean"},
        )
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)

    functional_failures = [
        case for case in cases
        if case["verified"] is not True or case["status"] != "completed"
    ]
    report = {
        "schema_version": 2,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "physical_external_adapters_via_real_baxy_core",
        "core_catalog_count": len(hello["capabilities"]),
        "cases": cases,
        "summary": {
            "verified": sum(case["verified"] is True for case in cases),
            "safe_failures": sum(
                case["verified"] is not True and not case["effect_may_have_occurred"]
                for case in cases
            ),
            "ambiguous_effects": sum(case["effect_may_have_occurred"] for case in cases),
            "functional_failures": len(functional_failures),
            "total": len(cases),
        },
        "stderr": process.stderr.read(),
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    shutil.rmtree(data_root, ignore_errors=True)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"-> {OUTPUT}")
    if functional_failures:
        raise SystemExit(1)


def write_checkpoint(cases: list[dict], catalog_count: int, *, complete: bool) -> None:
    report = {
        "schema_version": 2,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "complete": complete,
        "scope": "physical_external_adapters_via_real_baxy_core",
        "core_catalog_count": catalog_count,
        "cases": cases,
    }
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, OUTPUT)


def sanitize_result(operation: str, result: dict | None) -> dict | None:
    if result is None:
        return None
    if operation == "game.catalog.list":
        states: dict[str, int] = {}
        for game in result.get("games") or []:
            state = str(game.get("state", "unknown"))
            states[state] = states.get(state, 0) + 1
        return {"version": result.get("version"), "count": result.get("count"),
                "states": states, "authority": result.get("source")}
    if operation == "bluetooth.device.list":
        devices = result.get("devices") or []
        return {"version": result.get("version"), "count": result.get("count"),
                "paired": sum(item.get("paired") is True for item in devices),
                "pairable": sum(item.get("canPair") is True for item in devices),
                "authority": result.get("authority")}
    if operation == "peripheral.list":
        devices = result.get("devices") or []
        return {"version": result.get("version"), "count": len(devices),
                "printers": sum(item.get("kind") == "printer" for item in devices),
                "scanners": sum(item.get("kind") == "scanner" for item in devices),
                "mice": sum(item.get("kind") == "mouse" for item in devices),
                "mouse_names": [item.get("name") for item in devices
                                if item.get("kind") == "mouse"],
                "requested_kind": result.get("requestedKind"),
                "authority": result.get("authority")}
    if operation == "wifi.profile.list":
        return {"version": result.get("version"), "count": len(result.get("profiles") or []),
                "authority": result.get("authority")}
    if operation == "calendar.event.list":
        return {"version": result.get("version"), "count": len(result.get("events") or []),
                "authority": result.get("authority")}
    if operation == "email.latest.read":
        return {key: value for key, value in result.items()
                if key not in {"body", "sender", "subject"}}
    if operation == "ocr.read":
        return {key: value for key, value in result.items() if key not in {"text"}}
    return result


def call(process: subprocess.Popen[str], request: dict) -> dict:
    process.stdin.write(json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n")
    process.stdin.flush()
    return receive(process)


def receive(process: subprocess.Popen[str]) -> dict:
    line = process.stdout.readline()
    if not line:
        raise RuntimeError("BAXY core closed: " + process.stderr.read())
    return json.loads(line)


if __name__ == "__main__":
    main()
