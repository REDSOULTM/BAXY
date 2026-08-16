"""Reproduce de forma acotada el bloqueo de bluetooth.device.list."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def one(core: Path, attempt: int, timeout: float) -> dict[str, Any]:
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / f"bluetooth-list-repro-{uuid.uuid4().hex}"
    )
    request = {
        "type": "operation.request",
        "requestId": str(uuid.uuid4()),
        "missionId": str(uuid.uuid4()),
        "invocationId": str(uuid.uuid4()),
        "operation": "bluetooth.device.list",
        "arguments": {},
    }
    process = subprocess.Popen(
        [str(core)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env={**os.environ, "BAXY_DATA_DIR": str(data_root)},
    )
    started = time.perf_counter()
    timed_out = False
    try:
        stdout, stderr = process.communicate(
            input=json.dumps(request, separators=(",", ":")) + "\n",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate(timeout=10)
    elapsed = time.perf_counter() - started
    lines = [line for line in stdout.splitlines() if line.strip()]
    response = json.loads(lines[1]) if len(lines) >= 2 else None
    shutil.rmtree(data_root, ignore_errors=True)
    return {
        "attempt": attempt,
        "timeout_seconds": timeout,
        "elapsed_seconds": round(elapsed, 3),
        "timed_out": timed_out,
        "response": response,
        "exit_code": process.returncode,
        "stderr": stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    rows = [one(core, attempt, args.timeout) for attempt in (1, 2)]
    report = {
        "schema": "baxy-night-audit-bluetooth-list-timeout-repro-v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "core": str(core),
        "reproduced": all(row["timed_out"] for row in rows),
        "runs": rows,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["reproduced"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
