"""Physically verify one exact installed Steam launch, then close only its new process."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from run_external_adapter_gate import CORE, call, receive

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/planner_recovery/steam_launch_gate.json"
PREFERRED_APP_ID = "4747510"  # Small installed demo observed by the read-only catalog gate.


def main() -> None:
    environment = os.environ.copy()
    data_root = Path(environment["LOCALAPPDATA"]) / "BAXY" / ("steam-launch-gate-" + uuid.uuid4().hex)
    environment["BAXY_DATA_DIR"] = str(data_root)
    process = subprocess.Popen(
        [str(CORE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=environment,
    )
    receive(process)
    launched_pid: int | None = None
    cleanup_verified = False

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

    try:
        catalog = invoke("game.catalog.list", {"query": PREFERRED_APP_ID, "limit": 5})
        games = (catalog.get("result") or {}).get("games") or []
        target = next((game for game in games if game.get("appId") == PREFERRED_APP_ID
                       and game.get("state") == "installed"), None)
        if target is None:
            launch = {"status": "skipped", "verified": False, "reason": "exact_installed_target_not_available"}
        else:
            launch = invoke("game.launch", {"appId": PREFERRED_APP_ID})
            launched_pid = (launch.get("result") or {}).get("processId")
    finally:
        if isinstance(launched_pid, int) and launched_pid > 0:
            subprocess.run(
                ["taskkill.exe", "/PID", str(launched_pid), "/T", "/F"],
                capture_output=True, timeout=20, check=False,
            )
            cleanup_verified = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 f"if(Get-Process -Id {launched_pid} -ErrorAction SilentlyContinue){{exit 2}}else{{exit 0}}"],
                capture_output=True, timeout=15, check=False,
            ).returncode == 0
        process.stdin.close()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)

    report = {
        "schema_version": 1,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "authorized_exact_installed_steam_launch",
        "catalog_target_present": bool(games),
        "launch": {
            "status": launch.get("status"), "verified": launch.get("verified"),
            "error": launch.get("errorCode"),
            "effect_may_have_occurred": launch.get("effectMayHaveOccurred", False),
            "authority": (launch.get("result") or {}).get("authority"),
            "process_observed": isinstance(launched_pid, int) and launched_pid > 0,
            "cleanup_requested": isinstance(launched_pid, int) and launched_pid > 0,
            "cleanup_verified": cleanup_verified,
            "reason": launch.get("reason"),
        },
        "stderr": process.stderr.read(),
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(data_root, ignore_errors=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
