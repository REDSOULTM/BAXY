"""Run explicitly authorized physical adapter checks with exact discovered targets.

The gate never guesses a Bluetooth device, Steam ownership, printer, scanner,
Wi-Fi profile, or brightness value. It records a skipped case when the machine
does not expose a target that the corresponding adapter can verify.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from run_external_adapter_gate import CORE, call, receive

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/planner_recovery/hardware_effects_gate.json"


def main() -> None:
    environment = os.environ.copy()
    data_root = Path(environment["LOCALAPPDATA"]) / "BAXY" / ("hardware-gate-" + uuid.uuid4().hex)
    environment["BAXY_DATA_DIR"] = str(data_root)
    process = subprocess.Popen(
        [str(CORE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=environment,
    )
    receive(process)
    cases: list[dict] = []
    reconnect_profile: str | None = None

    def invoke(operation: str, arguments: dict) -> dict:
        request = {
            "type": "operation.request", "requestId": str(uuid.uuid4()),
            "missionId": str(uuid.uuid4()), "invocationId": str(uuid.uuid4()),
            "operation": operation, "arguments": arguments,
        }
        response = call(process, request)
        if response.get("errorCode") == "confirmation_required":
            request["requestId"] = str(uuid.uuid4())
            request["confirmationToken"] = response["result"]["token"]
            response = call(process, request)
        return response

    def record(case: str, operation: str, arguments: dict) -> dict:
        response = invoke(operation, arguments)
        cases.append({
            "case": case, "operation": operation, "status": response.get("status"),
            "verified": response.get("verified"), "error": response.get("errorCode"),
            "effect_may_have_occurred": response.get("effectMayHaveOccurred", False),
            "result": sanitize_result(operation, response.get("result")),
        })
        return response

    def skip(case: str, reason: str) -> None:
        cases.append({"case": case, "status": "skipped", "verified": False, "reason": reason})

    try:
        bluetooth = record("bluetooth_inventory", "bluetooth.device.list", {})
        pairable = next((item for item in (bluetooth.get("result") or {}).get("devices", [])
                         if item.get("canPair") is True and item.get("paired") is not True), None)
        if pairable:
            record("bluetooth_pair", "bluetooth.device.pair", {"deviceId": pairable["deviceId"]})
        else:
            skip("bluetooth_pair", "no_exact_pairable_device")

        peripherals = record("peripheral_inventory", "peripheral.list", {})
        devices = (peripherals.get("result") or {}).get("devices", [])
        printer = next((item for item in devices if item.get("kind") == "printer"
                        and "Brother" in item.get("name", "")), None)
        scanner = next((item for item in devices if item.get("kind") == "scanner"
                        and "Brother" in item.get("name", "")), None)
        document = record(
            "print_document_create", "office.document.create",
            {"format": "docx", "title": "BAXY physical printer verification"},
        )
        document_id = (document.get("result") or {}).get("documentId")
        if printer and document_id:
            record("printer_job", "peripheral.print", {
                "deviceId": printer["deviceId"], "documentId": document_id,
            })
        else:
            skip("printer_job", "no_exact_printer_or_document")
        if scanner:
            record("scanner_capture", "peripheral.scan", {"deviceId": scanner["deviceId"]})
        else:
            skip("scanner_capture", "no_exact_scanner")

        profiles = record("wifi_profiles", "wifi.profile.list", {})
        interface = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"], capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=15, check=False,
        ).stdout
        match = re.search(r"^\s*SSID\s*:\s*(.+?)\s*$", interface, re.MULTILINE)
        current_ssid = match.group(1).strip() if match else None
        current = next((item for item in (profiles.get("result") or {}).get("profiles", [])
                        if current_ssid and item.get("label", "").casefold() == current_ssid.casefold()), None)
        if current:
            reconnect_profile = current["profileId"]
            record("wifi_reconnect_current", "wifi.connect", {"profileId": reconnect_profile})
        else:
            skip("wifi_reconnect_current", "connected_profile_not_resolved")

        brightness = current_brightness()
        if brightness is not None:
            record("brightness_same_value", "system.settings.set", {
                "setting": "brightness", "value": brightness,
            })
        else:
            skip("brightness_same_value", "brightness_wmi_not_available")

        games = (record("steam_catalog", "game.catalog.list", {"limit": 100}).get("result") or {}).get("games", [])
        uninstalled = next((item for item in games if item.get("state") == "owned_not_installed"), None)
        partial = next((item for item in games if item.get("state") in {"downloading", "staging", "partial"}), None)
        if uninstalled:
            skip("steam_install_commit", "exact_target_available_but_install_not_started_without_size_budget")
        else:
            skip("steam_install_commit", "no_owned_uninstalled_target")
        if partial:
            record("steam_cancel_partial", "game.install.cancel", {"appId": partial["appId"]})
        else:
            skip("steam_cancel_partial", "no_partial_download")
    finally:
        if reconnect_profile:
            try:
                invoke("wifi.connect", {"profileId": reconnect_profile})
            except Exception:
                pass
        process.stdin.close()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)

    report = {
        "schema_version": 1,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "authorized_exact_target_hardware_effects",
        "cases": cases,
        "summary": {
            "verified": sum(case.get("verified") is True for case in cases),
            "safe_failures": sum(case.get("status") == "failed" and not case.get("effect_may_have_occurred") for case in cases),
            "ambiguous_effects": sum(case.get("effect_may_have_occurred") is True for case in cases),
            "skipped_no_target": sum(case.get("status") == "skipped" for case in cases),
            "total": len(cases),
        },
        "stderr": process.stderr.read(),
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(data_root, ignore_errors=True)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"-> {OUTPUT}")


def current_brightness() -> int | None:
    command = "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction Stop | Select-Object -First 1).CurrentBrightness"
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=15, check=False,
    )
    try:
        value = int(result.stdout.strip())
    except ValueError:
        return None
    return value if 0 <= value <= 100 else None


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
                "authority": result.get("authority")}
    if operation == "wifi.profile.list":
        return {"version": result.get("version"), "count": len(result.get("profiles") or []),
                "authority": result.get("authority")}
    return result


if __name__ == "__main__":
    main()
