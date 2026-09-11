"""Run the required cumulative Full once in a window without product inference."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

import psutil

root = Path(__file__).resolve().parents[1]
out = root / "artifacts/comprobaciones/C03/PROCESS_DEADLINE804"
private = Path("C:/Users/usuario/AppData/Local/BAXY/C03-process-deadline804-private")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    assert not path.exists(), path
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


assert read(out / "VALIDATION_EXIT.json")["exit_code"] == 0
pins = read(out / "SOURCE_PINS.json")
assert all(sha(root / name) == digest for name, digest in pins.items())
busy = [p.info for p in psutil.process_iter(["name", "pid"])
        if (p.info["name"] or "").lower() in {"llama-server.exe", "baxy.exe", "baxy-core.exe", "testhost.exe"}]
assert not busy, busy
log_path = private / "full.log"
assert not log_path.exists() and not (out / "FULL_EXIT.json").exists()
command = [shutil.which("pwsh"), "-NoProfile", "-File", "scripts/test_source_quality.ps1", "-Mode", "Full"]
assert command[0]
with log_path.open("wb") as log:
    process = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=log,
                               stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    write(out / "FULL_PROCESS.json", {"utc": datetime.now(timezone.utc).isoformat(), "pid": process.pid,
                                      "command": command, "log": str(log_path)})
    print(json.dumps({"full_started": True, "pid": process.pid}), flush=True)
    code = process.wait()
unchanged = all(sha(root / name) == digest for name, digest in pins.items())
shutil.copyfile(log_path, out / "full.log")
result = {"utc": datetime.now(timezone.utc).isoformat(), "exit_code": code,
          "source_pins_unchanged": unchanged, "log_sha256": sha(log_path), "adopted": False}
write(out / "FULL_EXIT.json", result)
print(json.dumps(result), flush=True)
raise SystemExit(code if code else 0 if unchanged else 1)
