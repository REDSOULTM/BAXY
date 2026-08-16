"""Resume the exhaustive model gate after native llama-server crashes.

The parallel runner writes one durable JSONL row per completed case.  A retry
therefore starts a fresh server but keeps those rows, so no historical message
is silently skipped or needlessly replayed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARALLEL_RUNNER = ROOT / "scripts" / "run_exhaustive_runtime_model_gate_parallel.py"


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--max-server-restarts", type=int, default=8)
    parser.add_argument("--restart-delay", type=float, default=3.0)
    options, forwarded = parser.parse_known_args()
    if not 0 <= options.max_server_restarts <= 32:
        raise ValueError("max-server-restarts must be between 0 and 32")
    if not 0.0 <= options.restart_delay <= 60.0:
        raise ValueError("restart-delay must be between 0 and 60 seconds")

    for attempt in range(options.max_server_restarts + 1):
        current = list(forwarded)
        if attempt > 0:
            current = [value for value in current if value != "--fresh"]
        print(
            json.dumps(
                {
                    "resilient_attempt": attempt + 1,
                    "maximum_attempts": options.max_server_restarts + 1,
                }
            ),
            flush=True,
        )
        completed = subprocess.run(
            [sys.executable, "-u", str(PARALLEL_RUNNER), *current],
            cwd=ROOT,
            check=False,
        )
        if completed.returncode != 75:
            return completed.returncode
        if attempt == options.max_server_restarts:
            return 75
        time.sleep(options.restart_delay)
    return 75


if __name__ == "__main__":
    raise SystemExit(main())
