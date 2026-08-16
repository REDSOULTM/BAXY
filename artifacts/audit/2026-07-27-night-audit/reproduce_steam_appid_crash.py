"""Reproduce sin efectos el cierre del core ante un Steam AppID schema-válido."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def one(core: Path, operation: str, attempt: int) -> dict[str, Any]:
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / f"steam-appid-repro-{operation.replace('.', '-')}-{uuid.uuid4().hex}"
    )
    environment = {**os.environ, "BAXY_DATA_DIR": str(data_root)}
    process = subprocess.Popen(
        [str(core)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    hello_line = process.stdout.readline()
    hello = json.loads(hello_line)
    request = {
        "type": "operation.request",
        "requestId": str(uuid.uuid4()),
        "missionId": str(uuid.uuid4()),
        "invocationId": str(uuid.uuid4()),
        "operation": operation,
        "arguments": {"appId": "audit-missing-id"},
    }
    process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
    process.stdin.flush()
    response_line = process.stdout.readline()
    response = json.loads(response_line) if response_line else None
    if process.stdin:
        process.stdin.close()
    try:
        exit_code = process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        exit_code = process.wait(timeout=5)
    stderr = process.stderr.read()
    shutil.rmtree(data_root, ignore_errors=True)
    capability = next(
        item
        for item in hello["capabilities"]
        if item.get("name") == operation
    )
    return {
        "operation": operation,
        "attempt": attempt,
        "argument": "audit-missing-id",
        "argument_length": len("audit-missing-id"),
        "advertised_risk": capability.get("risk"),
        "advertised_schema": capability.get("argumentsSchema"),
        "response": response,
        "exit_code": exit_code,
        "stderr": stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    rows = [
        one(core, operation, attempt)
        for operation in ("game.install.prepare", "game.install.status")
        for attempt in (1, 2)
    ]
    report = {
        "schema": "baxy-night-audit-steam-appid-crash-repro-v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "core": str(core),
        "reproduced": all(
            row["response"] is None
            and row["exit_code"] == 70
            and "InvalidDataException" in row["stderr"]
            for row in rows
        ),
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
