"""Reproduce sin efectos el cierre del core cuando winget no es resoluble."""

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


def one(core: Path, attempt: int) -> dict[str, Any]:
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / f"package-prepare-repro-{uuid.uuid4().hex}"
    )
    environment = {**os.environ, "BAXY_DATA_DIR": str(data_root)}
    request = {
        "type": "operation.request",
        "requestId": str(uuid.uuid4()),
        "missionId": str(uuid.uuid4()),
        "invocationId": str(uuid.uuid4()),
        "operation": "package.install.prepare",
        "arguments": {"packageId": "Microsoft.PowerToys"},
    }
    process = subprocess.Popen(
        [str(core)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    stdout, stderr = process.communicate(
        input=json.dumps(request, separators=(",", ":")) + "\n",
        timeout=20,
    )
    lines = [line for line in stdout.splitlines() if line.strip()]
    hello = json.loads(lines[0])
    response = json.loads(lines[1]) if len(lines) >= 2 else None
    shutil.rmtree(data_root, ignore_errors=True)
    capability = next(
        item
        for item in hello["capabilities"]
        if item.get("name") == "package.install.prepare"
    )
    return {
        "attempt": attempt,
        "argument": "Microsoft.PowerToys",
        "advertised_risk": capability.get("risk"),
        "advertised_schema": capability.get("argumentsSchema"),
        "response": response,
        "exit_code": process.returncode,
        "stderr": stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    rows = [one(core, attempt) for attempt in (1, 2)]
    report = {
        "schema": "baxy-night-audit-package-prepare-crash-repro-v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "core": str(core),
        "winget_on_path": shutil.which("winget.exe"),
        "reproduced": all(
            row["response"] is None
            and row["exit_code"] == 70
            and "Win32Exception" in row["stderr"]
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
