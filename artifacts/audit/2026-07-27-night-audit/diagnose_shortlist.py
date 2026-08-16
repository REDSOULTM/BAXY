"""Record the production E5 operation shortlist for failed routing examples."""

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

from baxy_mind.__main__ import configure_tools
from baxy_mind.planner import PlannerCatalog
from baxy_mind.router import ProcessIntentRouter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--cases-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-shortlist-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
    core = subprocess.Popen(
        [str(args.core.resolve(strict=True))],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env={**os.environ, "BAXY_DATA_DIR": str(data_root)},
    )
    hello_line = core.stdout.readline()
    hello = json.loads(hello_line)
    capabilities = [
        {
            key: item[key]
            for key in ("name", "description", "argumentsSchema", "risk")
        }
        for item in hello["capabilities"]
    ]
    tools = configure_tools(capabilities)
    router = ProcessIntentRouter()
    rows = []
    started = time.perf_counter()
    try:
        if not router.try_ready(120):
            raise RuntimeError("production encoder did not become ready")
        catalog = PlannerCatalog(tools, encoder=router.encode)
        cases = json.loads(args.cases_json.read_text(encoding="utf-8"))
        for case in cases:
            text = str(case["text"])
            shortlist = catalog.shortlist(text)
            expected = case.get("expectedOperation")
            rows.append(
                {
                    "text": text,
                    "expectedOperation": expected,
                    "shortlist": [tool.name for tool in shortlist],
                    "expectedPresent": (
                        expected in {tool.name for tool in shortlist}
                        if expected
                        else None
                    ),
                }
            )
    finally:
        router.close()
        core.stdin.close()
        try:
            core.wait(timeout=10)
        except subprocess.TimeoutExpired:
            core.terminate()
            core.wait(timeout=5)
        stderr = core.stderr.read()

    report = {
        "schema": "baxy.audit.routing-shortlist.v1",
        "measuredAt": datetime.now(timezone.utc).isoformat(),
        "coreVersion": hello.get("coreVersion"),
        "catalogCount": len(capabilities),
        "elapsedSeconds": time.perf_counter() - started,
        "total": len(rows),
        "expectedPresent": sum(row["expectedPresent"] is True for row in rows),
        "rows": rows,
        "coreExitCode": core.returncode,
        "stderr": stderr[-2048:],
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(data_root, ignore_errors=True)
    print(
        json.dumps(
            {
                "total": report["total"],
                "expectedPresent": report["expectedPresent"],
                "elapsedSeconds": round(report["elapsedSeconds"], 3),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
