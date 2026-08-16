"""Physically verify Bluetooth radio mutation and restore the exact baseline.

The first verified ``off`` call tells us whether the baseline was on through
the core's durable ``effectMayHaveOccurred`` receipt. The gate then exercises
the opposite state when needed and always restores that observed baseline.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_layout import load_build_layout  # noqa: E402

BUILD_LAYOUT = load_build_layout(ROOT)
CORE = BUILD_LAYOUT.core_executable(ROOT)
OUTPUT = ROOT / "artifacts/planner_recovery/bluetooth_radio_roundtrip_gate.json"


def receive(process: subprocess.Popen[str]) -> dict:
    assert process.stdout is not None
    line = process.stdout.readline()
    if not line:
        error = process.stderr.read() if process.stderr is not None else ""
        raise RuntimeError("BAXY core closed: " + error[-2000:])
    return json.loads(line)


def call(process: subprocess.Popen[str], state: bool) -> dict:
    request = {
        "type": "operation.request",
        "requestId": str(uuid.uuid4()),
        "missionId": str(uuid.uuid4()),
        "invocationId": str(uuid.uuid4()),
        "operation": "bluetooth.radio.set",
        "arguments": {"state": state},
    }
    assert process.stdin is not None
    process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
    process.stdin.flush()
    response = receive(process)
    if response.get("errorCode") == "confirmation_required":
        request["requestId"] = str(uuid.uuid4())
        request["confirmationToken"] = response["result"]["token"]
        process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        process.stdin.flush()
        response = receive(process)
    return response


def verified_state(response: dict, state: bool) -> bool:
    result = response.get("result") or {}
    return (
        response.get("status") == "completed"
        and response.get("verified") is True
        and result.get("state") is state
        and result.get("authority") == "windows_radio_api_postread"
    )


def main() -> int:
    run_id = uuid.uuid4().hex
    environment = os.environ.copy()
    data_root = Path(environment["LOCALAPPDATA"]) / "BAXY" / (
        "bluetooth-roundtrip-" + run_id
    )
    environment["BAXY_DATA_DIR"] = str(data_root)
    process = subprocess.Popen(
        [str(CORE)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    steps: list[dict] = []
    baseline: bool | None = None
    restored = False
    try:
        hello = receive(process)
        if not any(
            item.get("name") == "bluetooth.radio.set"
            for item in hello.get("capabilities") or []
        ):
            raise RuntimeError("compiled core does not expose bluetooth.radio.set")

        off = call(process, False)
        steps.append(off)
        if not verified_state(off, False):
            raise RuntimeError(
                "Bluetooth off postread was not verified: "
                + json.dumps(off, ensure_ascii=False, sort_keys=True)
            )
        baseline = bool((off.get("result") or {}).get("changed"))
        if baseline is False:
            on = call(process, True)
            steps.append(on)
            if not verified_state(on, True):
                raise RuntimeError(
                    "Bluetooth on postread was not verified: "
                    + json.dumps(on, ensure_ascii=False, sort_keys=True)
                )
        restore = call(process, baseline)
        steps.append(restore)
        restored = verified_state(restore, baseline)
        if not restored:
            raise RuntimeError(
                "Bluetooth baseline restoration was not verified: "
                + json.dumps(restore, ensure_ascii=False, sort_keys=True)
            )
    finally:
        if baseline is not None and not restored:
            try:
                emergency = call(process, baseline)
                steps.append(emergency)
                restored = verified_state(emergency, baseline)
            except Exception:
                pass
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        shutil.rmtree(data_root, ignore_errors=True)

    report = {
        "schema_version": 1,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "physical_bluetooth_radio_roundtrip_via_real_baxy_core",
        "baseline_state": baseline,
        "restored": restored,
        "verified_steps": sum(
            response.get("verified") is True for response in steps
        ),
        "total_steps": len(steps),
        "error_codes": [
            response.get("errorCode")
            for response in steps
            if response.get("errorCode")
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if restored and report["verified_steps"] == len(steps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
