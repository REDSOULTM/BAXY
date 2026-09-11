"""Repeat cumulative Full after restoring two historical receipts to exact Git bytes."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

import psutil

root = Path(__file__).resolve().parents[1]
parent = root / "artifacts/comprobaciones/C03/PROCESS_DEADLINE804"
out = parent / "FULL_RETRY1"
private = Path("C:/Users/usuario/AppData/Local/BAXY/C03-process-deadline804-private/full-retry1")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    assert not path.exists(), path
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


assert read(parent / "VALIDATION_EXIT.json")["exit_code"] == 0
assert read(parent / "FULL_EXIT.json")["exit_code"] == 1
assert read(parent / "LINE_ENDING_REPAIR.json")["owner_exit_code"] == 0
pins_path = parent / "SOURCE_PINS.json"
pins = read(pins_path)
assert all(sha(root / name) == digest for name, digest in pins.items())
busy = [p.info for p in psutil.process_iter(["name", "pid", "cmdline"])
        if (p.info["name"] or "").lower() in {"llama-server.exe", "baxy.exe", "baxy-core.exe", "testhost.exe"}
        or any("pytest" in part for part in p.info["cmdline"] or [])]
assert not busy, busy
assert not out.exists() and not private.exists()
out.mkdir()
private.mkdir()
log_path = private / "full.log"
command = [shutil.which("pwsh"), "-NoProfile", "-File", "scripts/test_source_quality.ps1", "-Mode", "Full"]
assert command[0]
with log_path.open("wb") as log:
    process = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=log,
                               stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    write(out / "FULL_PROCESS.json", {"utc": datetime.now(timezone.utc).isoformat(), "pid": process.pid,
                                      "command": command, "log": str(log_path),
                                      "source_pins_sha256": sha(pins_path), "runner_sha256": sha(Path(__file__))})
    print(json.dumps({"full_retry_started": True, "pid": process.pid}), flush=True)
    code = process.wait()
unchanged = all(sha(root / name) == digest for name, digest in pins.items())
shutil.copyfile(log_path, out / "full.log")
result = {"utc": datetime.now(timezone.utc).isoformat(), "exit_code": code,
          "source_pins_unchanged": unchanged, "source_pins_sha256": sha(pins_path),
          "log_sha256": sha(log_path), "adopted": False,
          "previous_failure": "../FULL_EXIT.json", "repair": "../LINE_ENDING_REPAIR.json"}
write(out / "FULL_EXIT.json", result)
print(json.dumps(result), flush=True)
raise SystemExit(code if code else 0 if unchanged else 1)
