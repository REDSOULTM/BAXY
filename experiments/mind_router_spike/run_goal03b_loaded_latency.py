"""Goal 03B: measure the turn while the GPU is already busy.

The 3-second bar is about the machine the person is actually using, not an idle
one. Goal 03 measured the difference by hand -- Steam, WhatsApp, two Edge
WebViews and the desktop resident on the same GPU took the model path's p50 from
2.08 s to 3.7-4.0 s -- but that load is not reproducible from a program.

This holds the same amount of the same resource in a way anyone can repeat: a
second ``llama-server`` process with the same registered model, resident on the
same GPU for the whole run. It is a harsher and duller load than a desktop, and
it is the same one every time.

Runs the goal 03 comprehension measurement underneath, so the accuracy figures
of a loaded run are directly comparable with the quiet one.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src", REPO / "scripts"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)
from experiments.mind_router_spike.probe_native_tool_contract_ceiling import (  # noqa: E402
    _start_server,
    _stop_server,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 03B loaded-machine latency")
    parser.add_argument("--label", required=True)
    arguments = parser.parse_args()

    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    process, port = _start_server(runtime, runtime.gguf)
    print(f"competing llama-server on 127.0.0.1:{port}, pid {process.pid}", flush=True)
    try:
        # The competitor must be resident, not merely started: a server that is
        # still loading weights when the corpus begins would leave the first
        # rows measured against a quiet machine.
        time.sleep(20.0)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "experiments.mind_router_spike.run_goal03_comprehension",
                "--label",
                arguments.label,
            ],
            cwd=REPO,
            env={**os.environ},
            check=False,
        )
        return completed.returncode
    finally:
        _stop_server(process)


if __name__ == "__main__":
    raise SystemExit(main())
