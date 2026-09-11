"""Root-owned handoff from Full798 to the frozen product confirmation799."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
out = root / "artifacts/comprobaciones/C03/PROCESS_VOCABULARY798"
receipt = out / "NEXT799_QUEUE.json"
assert not receipt.exists(), "Do not duplicate the pending product run."


def record(state, **fields):
    value = {"utc": datetime.now(timezone.utc).isoformat(), "state": state,
             "pid": os.getpid(), "full_session": 24887, **fields}
    receipt.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(value), flush=True)


record("waiting_for_full798_terminal_receipt", inference_started=False)
deadline = time.monotonic() + 2400
while True:
    try:
        full = json.loads((out / "FULL_EXIT.json").read_text(encoding="utf-8-sig"))
        break
    except (FileNotFoundError, json.JSONDecodeError):
        if time.monotonic() >= deadline:
            record("receipt_wait_expired", inference_started=False,
                   note="This does not establish that Full stopped; inspect session24887.")
            raise SystemExit(1)
        time.sleep(1)

if full["exit_code"] != 0:
    record("full_failed_no_inference", inference_started=False, full_exit=full["exit_code"])
    raise SystemExit(1)

with (out / "before799-build-server-shutdown.log").open("w", encoding="utf-8") as log:
    shutdown = subprocess.run(
        [str(Path.home() / ".dotnet/dotnet.exe"), "build-server", "shutdown", "--msbuild", "--vbcscompiler"],
        cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW, check=False,
    )
if shutdown.returncode != 0:
    record("build_server_shutdown_failed", inference_started=False, exit_code=shutdown.returncode)
    raise SystemExit(shutdown.returncode)

record("starting_registered_runner799", full_exit=0,
       note="Runner checks current pins, free RAM, absence of concurrent tests, and the frozen50-case panel.")
result = subprocess.run([sys.executable, "-X", "utf8", str(root / "scratchpad/c03-process-batch799.py")],
                        cwd=root, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW,
                        check=False)
record("runner799_terminal", runner_exit=result.returncode,
       note="Inspect PROCESS_BATCH799/EXIT.json and actual responses; no quality verdict inferred here.")
raise SystemExit(result.returncode)
